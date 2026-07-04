"""The run error contract — recorded, diagnosable failures (AUTOX-FR-006/007/011, AUTOX-NFR-003).

Every terminal run failure appends a signed ``run``/``failure`` ledger record before exiting; both
status commands surface "failed at <stage> (<class>)" until a later record passes that stage; and the
in-run Verify verdict is recorded exactly as a standalone ``3pwr gate run`` records it. All driven with
fake agents — no model, no network.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import runner, runpreflight
from threepowers.cli import main
from threepowers.ledger import Ledger
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


def _spec_writer(spec_id="RUN"):
    """A fake agent that writes each stage's declared artifact (mirrors the native-runner suite)."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if "STAGE: Specify" in prompt:
            d = cwd / "specs" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "STAGE: Plan" in prompt:
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "STAGE: Tasks" in prompt:
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "STAGE: Oracle" in prompt:
            d = cwd / "tests" / "oracle" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "test_oracle.py").write_text(
                "def test_ok():\n    assert True\n", encoding="utf-8"
            )
        elif "STAGE: Implement" in prompt:
            d = cwd / "src"
            d.mkdir(parents=True, exist_ok=True)
            (d / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "changes written", "")

    return fake


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    """A native-runnable trust-spine repo with fake diverse agents and a resolvable signer."""
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
    monkeypatch.setattr(runner, "dispatch_agent", _spec_writer())
    return root


def _last_failure(root: Path) -> dict:
    entries = Ledger(root / ".3powers" / "ledger.jsonl").entries()
    failures = [
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "failure"
    ]
    assert failures, "no run/failure record in the ledger"
    return failures[-1]


def _verify_green(root: Path) -> None:
    assert main(["--root", str(root), "verify"]) == 0


# --------------------------------------------------------------------------- AUTOX-FR-006 (recorded failures)
def test_dispatch_failure_is_recorded_in_the_ledger(run_repo, monkeypatch, capsys):
    """AUTOX-FR-006: a dispatch failure appends a signed run/failure entry naming the stage and
    class before exiting; `3pwr verify` stays green over the new record (AUTOX-NFR-003)."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "boom"))
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    assert rc != 0
    e = _last_failure(run_repo)
    p = e["payload"]
    assert p["class"] == "dispatch_failed" and p["stage"] == "Spec"
    assert p["attempts"] >= 1 and "boom" in p["detail"]
    capsys.readouterr()
    _verify_green(run_repo)


def test_artifact_missing_is_recorded_in_the_ledger(run_repo, monkeypatch, capsys):
    """AUTOX-FR-006: an artifact-missing failure is recorded with its stage and class."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (0, "did nothing", ""))
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    assert rc != 0
    p = _last_failure(run_repo)["payload"]
    assert p["class"] == "artifact_missing" and p["stage"] == "Spec"
    capsys.readouterr()
    _verify_green(run_repo)


def _drive_to_verify(run_repo, monkeypatch) -> None:
    """Run to the spec gate, then resume so the segment reaches the Verify stage."""
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) in (
        0,
        3,
    )
    main(
        [
            "--root",
            str(run_repo),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "t",
        ]
    )


def test_gates_red_is_recorded_and_verdict_matches_standalone(run_repo, monkeypatch, capsys):
    """AUTOX-FR-006 + FR-011: a gate-red at the in-run Verify appends BOTH the verdict entry — with
    the same content a standalone `3pwr gate run` records (spec_id, result, requirement_ids) — and
    the run/failure record with class gates_red."""
    import threepowers.cli as climod

    red = Verdict(spec_id="RUN", tier="Standard", adapter="python", result=STATUS_FAIL)
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(climod, "run_gates", lambda *a, **k: red)
    _drive_to_verify(run_repo, monkeypatch)
    capsys.readouterr()

    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    verdicts = [e for e in entries if e.get("type") == "verdict"]
    assert verdicts, "the in-run Verify verdict was not recorded (AUTOX-FR-011)"
    v = verdicts[-1]
    assert v["spec_id"] == "RUN" and v["payload"]["result"] == STATUS_FAIL
    assert v["payload"] == red.to_dict()  # byte-identical content to a standalone gate run
    p = _last_failure(run_repo)["payload"]
    assert p["class"] == "gates_red" and p["stage"] == "Verify"
    _verify_green(run_repo)


def test_verdict_error_is_recorded_distinctly(run_repo, monkeypatch, capsys):
    """AUTOX-FR-006: a Verify that cannot even run (verdict error) is recorded as class
    verdict_error — never mislabeled gates_red."""
    import threepowers.cli as climod

    def boom(*a, **k):
        raise ValueError("no adapter")

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(climod, "run_gates", boom)
    _drive_to_verify(run_repo, monkeypatch)
    out = capsys.readouterr().out
    assert "verdict error" in out and "gates red" not in out
    p = _last_failure(run_repo)["payload"]
    assert p["class"] == "verdict_error" and p["stage"] == "Verify"
    _verify_green(run_repo)


def test_green_verify_verdict_is_recorded_too(run_repo, monkeypatch, capsys):
    """AUTOX-FR-011: a green in-run verdict is recorded as well — a run's verdict is never
    invisible to the trust spine, red or green."""
    import threepowers.cli as climod

    green = Verdict(spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS)
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(climod, "run_gates", lambda *a, **k: green)
    _drive_to_verify(run_repo, monkeypatch)
    capsys.readouterr()
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    verdicts = [e for e in entries if e.get("type") == "verdict"]
    assert verdicts and verdicts[-1]["payload"]["result"] == STATUS_PASS
    assert (run_repo / ".3powers" / "verdicts" / "latest.json").exists()
    _verify_green(run_repo)


# --------------------------------------------------------------------------- AUTOX-FR-007 (status surfacing)
def test_status_shows_failed_stage_and_class_then_clears(run_repo, monkeypatch, capsys):
    """AUTOX-FR-007: after a mid-run failure both `3pwr run --status` and `3pwr status` show
    "failed at <stage> (<class>)" — distinct from paused — and stop showing it once a later
    record passes that stage."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "kaput"))
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) != 0
    capsys.readouterr()

    assert main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN"]) == 0
    out = capsys.readouterr().out
    assert "failed at Spec (dispatch_failed)" in out and "paused" not in out

    assert main(["--root", str(run_repo), "status", "--spec-id", "RUN"]) == 0
    out = capsys.readouterr().out
    assert "failed at Spec (dispatch_failed)" in out

    # A later run passing the failed stage clears the failure from both status views.
    monkeypatch.setattr(runner, "dispatch_agent", _spec_writer())
    main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    capsys.readouterr()
    assert main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN"]) == 0
    assert "failed at" not in capsys.readouterr().out
    assert main(["--root", str(run_repo), "status", "--spec-id", "RUN"]) == 0
    assert "failed at" not in capsys.readouterr().out


def test_status_json_carries_the_failure_fields(run_repo, monkeypatch, capsys):
    """AUTOX-FR-007: the machine-readable status carries the failed stage, class, and timestamp."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "kaput"))
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) != 0
    capsys.readouterr()
    assert main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN", "--json"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["failed"] is True
    assert obj["failed_stage"] == "Spec" and obj["failed_class"] == "dispatch_failed"
    assert obj["failed_at"]  # the failure entry's timestamp — "and when" (AUTOX-FR-007)


def test_two_failures_latest_wins_history_remains(run_repo, monkeypatch, capsys):
    """AUTOX edge: two failures in a row — the latest wins in status; earlier ones remain in the
    append-only ledger as history (3PWR-FR-069)."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "first"))
    main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (0, "did nothing", ""))
    main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    capsys.readouterr()
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    failures = [
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "failure"
    ]
    assert len(failures) == 2  # both failures are history in the append-only ledger
    assert main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN"]) == 0
    out = capsys.readouterr().out
    assert "artifact_missing" in out and "dispatch_failed" not in out  # the latest wins
