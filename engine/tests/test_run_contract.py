"""The stable run machine contract + checkpoint-independent resume (AUTOX-FR-009/010).

One documented (status, exit-code) pair per terminal outcome — 0 done · 1 gates_red · 2 usage ·
3 paused_at_gate · 4 setup/dispatch failure — asserted per branch; and `3pwr run --resume` continues
from the last successfully completed stage after a failure even with auto-commit off, never
re-dispatching a completed stage.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import runner, runpreflight
from threepowers.cli import EXIT_FAIL, EXIT_OK, EXIT_PAUSED, EXIT_SETUP, EXIT_USAGE, main
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, Verdict


def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _stage_writer(spec_id="RUN", skip=()):
    """A fake agent writing each stage's declared artifact, except the steps in ``skip``."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if "STAGE: Specify" in prompt and "specify" not in skip:
            d = cwd / "specs" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "STAGE: Plan" in prompt and "plan" not in skip:
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "STAGE: Tasks" in prompt and "tasks" not in skip:
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "STAGE: Oracle" in prompt and "oracle" not in skip:
            d = cwd / "tests" / "oracle" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "STAGE: Implement" in prompt and "implement" not in skip:
            d = cwd / "src"
            d.mkdir(parents=True, exist_ok=True)
            (d / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "changes written", "")

    return fake


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    for name, fam in (("claude", "anthropic"), ("codex", "openai")):
        (root / ".3powers" / "agents" / f"{name}.yaml").write_text(
            yaml.safe_dump({"command": name, "family": fam, "headless": True, "prompt_flag": "-p"}),
            encoding="utf-8",
        )
    (root / ".3powers" / "config" / "roles.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "diversity_level": "family",
                "roles": {
                    "coder": {"integration": "claude", "model_family": "anthropic"},
                    "oracle": {"integration": "codex", "model_family": "openai"},
                },
            }
        ),
        encoding="utf-8",
    )
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    _git_init(root)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", _stage_writer())
    return root


def _run_json(root: Path, *argv: str, capsys) -> tuple[int, dict]:
    rc = main(["--root", str(root), *argv, "--json"])
    return rc, json.loads(capsys.readouterr().out)


# --------------------------------------------------------------------------- AUTOX-FR-009 (the table)
def test_paused_at_gate_is_exit_3(run_repo, capsys):
    """AUTOX-FR-009: a run pausing at a human gate exits 3 with status paused_at_gate — a documented
    code distinct from both a completed run (0) and any failure."""
    rc, obj = _run_json(run_repo, "run", "add x", "--no-input", "--spec-id", "RUN", capsys=capsys)
    assert rc == EXIT_PAUSED == 3 and obj["status"] == "paused_at_gate"


def test_preflight_failure_is_exit_4(run_repo, monkeypatch, capsys):
    """AUTOX-FR-009: an unmet prerequisite exits 4 (setup) with status preflight_failed — distinct
    from usage (2) and gates-red (1)."""
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: None)
    rc, obj = _run_json(run_repo, "run", "add x", "--no-input", "--spec-id", "RUN", capsys=capsys)
    assert rc == EXIT_SETUP == 4 and obj["status"] == "preflight_failed"


def test_dispatch_failed_is_exit_4(run_repo, monkeypatch, capsys):
    """AUTOX-FR-009: a dispatch failure exits 4 with status dispatch_failed."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "boom"))
    rc, obj = _run_json(run_repo, "run", "add x", "--no-input", "--spec-id", "RUN", capsys=capsys)
    assert rc == EXIT_SETUP and obj["status"] == "dispatch_failed"


def test_artifact_missing_is_exit_4(run_repo, monkeypatch, capsys):
    """AUTOX-FR-009: a missing stage artifact exits 4 with status artifact_missing."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (0, "did nothing", ""))
    rc, obj = _run_json(run_repo, "run", "add x", "--no-input", "--spec-id", "RUN", capsys=capsys)
    assert rc == EXIT_SETUP and obj["status"] == "artifact_missing"


def _resume_to_verify(root: Path, capsys) -> tuple[int, dict]:
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    capsys.readouterr()
    return _run_json(
        root, "run", "--resume", "--no-input", "--spec-id", "RUN", "--approver", "t", capsys=capsys
    )


def test_gates_red_is_exit_1_and_verdict_error_is_exit_4(run_repo, monkeypatch, capsys):
    """AUTOX-FR-009: gates-red exits 1 (status gates_red); a Verify that cannot run exits 4 with
    status verdict_error — the two are never conflated."""
    import threepowers.cli as climod

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_FAIL
        ),
    )
    rc, obj = _resume_to_verify(run_repo, capsys)
    assert rc == EXIT_FAIL == 1 and obj["status"] == "gates_red"

    def boom(*a, **k):
        raise ValueError("no adapter")

    monkeypatch.setattr(climod, "run_gates", boom)
    rc2, obj2 = _run_json(
        run_repo,
        "run",
        "--resume",
        "--no-input",
        "--spec-id",
        "RUN",
        "--approver",
        "t",
        capsys=capsys,
    )
    assert rc2 == EXIT_SETUP and obj2["status"] == "verdict_error"


def test_done_is_exit_0(run_repo, monkeypatch, capsys):
    """AUTOX-FR-009: a completed lifecycle exits 0 with status done."""
    import threepowers.cli as climod

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )
    rc, obj = _resume_to_verify(run_repo, capsys)
    assert rc == EXIT_PAUSED and obj["status"] == "paused_at_gate"  # sign-off gate
    rc2, obj2 = _run_json(
        run_repo,
        "run",
        "--resume",
        "--no-input",
        "--spec-id",
        "RUN",
        "--approver",
        "t",
        capsys=capsys,
    )
    assert rc2 == EXIT_OK == 0 and obj2["status"] == "done"


def test_usage_error_keeps_exit_2(run_repo, capsys):
    """AUTOX-FR-009: usage errors keep their own code (2), distinct from every run outcome."""
    rc = main(["--root", str(run_repo), "run", "--resume", "--spec-id", "FRESH"])
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE == 2 and "nothing to resume" in err


def test_each_outcome_maps_to_exactly_one_pair():
    """AUTOX-FR-009 property: the documented (status, exit-code) pairs are distinct per outcome."""
    table = {
        "done": EXIT_OK,
        "gates_red": EXIT_FAIL,
        "paused_at_gate": EXIT_PAUSED,
        "preflight_failed": EXIT_SETUP,
        "dispatch_failed": EXIT_SETUP,
        "artifact_missing": EXIT_SETUP,
        "verdict_error": EXIT_SETUP,
    }
    # the four contract classes are mutually distinguishable by exit code alone
    assert (
        len({table["done"], table["gates_red"], table["paused_at_gate"], EXIT_SETUP, EXIT_USAGE})
        == 5
    )


# --------------------------------------------------------------------------- AUTOX-FR-010 (resume)
def test_no_auto_commit_failure_resumes_at_the_failed_stage(run_repo, monkeypatch, capsys):
    """AUTOX-FR-010 / AUTOX-SC-004: with auto-commit OFF, a run failing at the oracle stage resumes
    AT oracle; stages 1..k-1 are recorded in the ledger and never re-dispatched."""
    # Segment 1: specify+clarify complete (recorded as run/stage entries, no commits) → spec gate.
    assert (
        main(
            [
                "--root",
                str(run_repo),
                "run",
                "add x",
                "--no-input",
                "--no-auto-commit",
                "--spec-id",
                "RUN",
            ]
        )
        == EXIT_PAUSED
    )
    # Segment 2: plan+tasks complete; the oracle stage dispatch fails.
    monkeypatch.setattr(runner, "dispatch_agent", _stage_writer(skip=("oracle",)))
    rc = main(
        [
            "--root",
            str(run_repo),
            "run",
            "--resume",
            "--no-input",
            "--no-auto-commit",
            "--spec-id",
            "RUN",
            "--approver",
            "t",
        ]
    )
    assert rc == EXIT_SETUP
    out = capsys.readouterr().out
    assert "artifact missing" in out and "Build" in out
    # No checkpoint commits were made — resume progress must come from the ledger alone.
    log = subprocess.run(
        ["git", "log", "--pretty=%s"], cwd=str(run_repo), capture_output=True, text=True
    ).stdout
    assert "3pwr(RUN)" not in log

    # Segment 3: a fixed agent — the resume re-enters AT oracle; completed stages do not re-run.
    seen: list[str] = []

    def recording(argv, **kw):
        prompt = argv[-1] if argv else ""
        for key in ("Specify", "Clarify", "Plan", "Tasks", "Oracle", "Implement"):
            if f"STAGE: {key}" in prompt:
                seen.append(key.lower())
        return _stage_writer()(argv, **kw)

    monkeypatch.setattr(runner, "dispatch_agent", recording)
    rc3 = main(
        [
            "--root",
            str(run_repo),
            "run",
            "--resume",
            "--no-input",
            "--no-auto-commit",
            "--spec-id",
            "RUN",
            "--approver",
            "t",
        ]
    )
    capsys.readouterr()
    assert rc3 in (EXIT_PAUSED, EXIT_FAIL, EXIT_SETUP)  # proceeds to verify/sign-off territory
    assert "oracle" in seen and "implement" in seen
    assert not {"specify", "clarify", "plan", "tasks"} & set(seen)  # never re-dispatched


def test_nothing_to_resume_names_the_fresh_start(run_repo, capsys):
    """AUTOX-FR-010: with no recorded progress the resume says so and names the fresh-start
    command."""
    rc = main(["--root", str(run_repo), "run", "--resume", "--spec-id", "NEW"])
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE
    assert "nothing to resume" in err and '3pwr run "<intent>" --spec-id NEW' in err
