"""`3pwr run --redo <stage>` — the deliberate rewind, end to end (spec 039).

Driven with a fake headless agent, fake channels, and no network — the same harness the steering
tests use — so the whole CLI branch is exercised without a live model. The tests prove the run-level
behavior the source plan asks for: the CLI refusals (REQ-003/004/006/CON-002), a Spec rewind that
re-dispatches Specify, re-flows through the human gates, and re-seals the amended spec through the
`review-spec` path (REQ-002/009/012), the completion-floor math that stops a pre-rewind record from
being read as "already complete" (REQ-011), a later-stage rewind that leaves the spec seal untouched
(REQ-012), and the trust spine staying green afterwards (SEC-002).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import completion, keys, lifecycle, orchestrate, runner, runpreflight, speclock
from threepowers.cli import EXIT_OK, EXIT_PAUSED, EXIT_USAGE, main
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_PASS, Verdict

FEATURE = "specs-src/001-add-a-rate-limiter"


# --------------------------------------------------------------------------- fixtures (fake agent, no network)
def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "human@e.st"],
        ["git", "config", "user.name", "human"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _writer(spec_id="RUN", seen: list | None = None):
    """A fake agent writing each stage's declared artifact into the folder the prompt names; every
    received prompt is collected into ``seen`` so a test can assert what a dispatch carried."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if seen is not None:
            seen.append(prompt)
        m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
        d = cwd / (m.group(1) if m else f"specs-src/{spec_id}")
        if "# Discovery agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
        elif "# Specify agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            body = f"# Spec\n**Spec ID**: {spec_id}\n"
            if "REVISION REQUESTED" in prompt:
                body += "REVISED per feedback\n"
            (d / "spec.md").write_text(body, encoding="utf-8")
        elif "# Plan agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "# Oracle agent" in prompt:
            t = cwd / "tests" / "oracle" / spec_id
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "# Implement agent" in prompt:
            src = cwd / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        out = "changes written\nCOMMIT: authored the stage work"
        tee = kw.get("tee")
        if tee is not None:
            tee.write(out + "\n")
            tee.flush()
        return (0, out, "")

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
    monkeypatch.setattr(runner, "dispatch_agent", _writer())
    return root


def _mock_gates_green(monkeypatch):
    import threepowers.cli as climod

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )


def _entries(root: Path) -> list[dict]:
    return Ledger(root / ".3powers" / "ledger.jsonl").entries()


def _state(root: Path, spec_id="RUN") -> dict:
    st = lifecycle.derive(_entries(root)).get(spec_id)
    return {
        "pending_gate": st.pending_gate if st else "",
        "stage": st.stage if st else "",
        "rewound": st.rewound if st else False,
        "redo_target": st.redo_target if st else "",
        "redo_approver": st.redo_approver if st else "",
    }


def _run(root: Path, *extra: str) -> int:
    return main(["--root", str(root), "run", "--no-input", "--spec-id", "RUN", *extra])


def _spec_file(root: Path) -> Path:
    return root / FEATURE / "spec.md"


def _redo_markers(root: Path) -> list[dict]:
    return [
        e["payload"]
        for e in _entries(root)
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "redo"
    ]


# =========================================================================== A. CLI validation (REQ-003/004/006, CON-002)
def test_redo_without_spec_id_is_a_usage_error(run_repo, capsys):
    """Covers: REQ-003 — `--redo` rewinds an EXISTING run: with no `--spec-id` it fails fast with
    the usage code and names the missing flag, dispatching nothing."""
    rc = main(
        ["--root", str(run_repo), "run", "--redo", "spec", "--approver", "x", "--reason", "y"]
    )
    assert rc == EXIT_USAGE
    assert "--spec-id" in capsys.readouterr().err


def test_redo_without_approver_or_reason_is_a_usage_error(run_repo, capsys):
    """Covers: REQ-004 — a rewind is a deliberate, audited act: missing `--approver` or `--reason`
    is refused with the usage code and a message naming both."""
    rc = _run(run_repo, "--redo", "spec", "--reason", "clarify")  # no --approver
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE and "--approver" in err and "--reason" in err
    rc = _run(run_repo, "--redo", "spec", "--approver", "carlo")  # no --reason
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE and "--approver" in err and "--reason" in err


def test_redo_unknown_or_gate_stage_lists_the_redoable_stages(run_repo, capsys):
    """Covers: REQ-006 — a stage that does not resolve to a rewind-able producing step (an unknown
    name or a gate step) is refused with the usage code and the run's redo-able stage list."""
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # specify recorded complete
    capsys.readouterr()
    for bad in ("frobnicate", "review-spec"):
        rc = _run(run_repo, "--redo", bad, "--approver", "carlo", "--reason", "why")
        err = capsys.readouterr().err
        assert rc == EXIT_USAGE, bad
        assert "redo-able stages" in err and "spec" in err  # spec is completed → offered


def test_redo_not_yet_completed_target_is_refused(run_repo, capsys):
    """Covers: REQ-006 — a target stage the run has not yet produced cannot be rewound to; the
    refusal carries the usage code and lists what IS redo-able."""
    assert (
        _run(run_repo, "add a rate limiter") == EXIT_PAUSED
    )  # paused at review-spec, plan not done
    capsys.readouterr()
    rc = _run(run_repo, "--redo", "plan", "--approver", "carlo", "--reason", "why")
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE
    assert "has not completed Plan" in err and "redo-able stages" in err


def test_redo_on_a_shipped_run_directs_to_revert(run_repo, monkeypatch, capsys):
    """Covers: CON-002 — once a run advances to Ship it is undone with `revert`, not rewound; the
    refusal carries the usage code and points at `3pwr revert`."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # review-spec
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # signoff
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_OK  # advanced to Ship
    assert _state(run_repo)["stage"] == "Ship"
    capsys.readouterr()
    rc = _run(run_repo, "--redo", "spec", "--approver", "carlo", "--reason", "why")
    err = capsys.readouterr().err
    assert rc == EXIT_USAGE
    assert "advanced to Ship" in err and "revert" in err


def test_redo_rejects_a_fresh_intent(run_repo, capsys):
    """Covers: REQ-003 — `--redo` takes no fresh intent (it operates on the recorded run); passing
    an intent argument alongside it is a usage error."""
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED
    capsys.readouterr()
    rc = _run(
        run_repo, "a brand new intent", "--redo", "spec", "--approver", "carlo", "--reason", "why"
    )
    assert rc == EXIT_USAGE
    assert "no fresh intent" in capsys.readouterr().err


# =========================================================================== B. the whole rewind flow (REQ-002/009/012)
def test_redo_spec_redispatches_specify_then_reflows_plan_and_build(run_repo, monkeypatch):
    """Covers: REQ-002/009/012 — `--redo spec --revise` re-dispatches Specify with the original
    intent + the feedback, pauses at the spec-approval gate, and on approval re-flows Plan → Build."""
    _mock_gates_green(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(runner, "dispatch_agent", _writer(seen=seen))
    # Drive Spec + Plan + Build to completion (paused at the sign-off gate).
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # review-spec
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # signoff
    # Rewind to Spec, amending it — Specify re-runs and the run returns to the spec gate.
    seen.clear()
    assert (
        _run(
            run_repo,
            "--redo",
            "spec",
            "--revise",
            "narrow the throttle scope",
            "--approver",
            "carlo",
            "--reason",
            "the scope was too broad",
        )
        == EXIT_PAUSED
    )
    assert _state(run_repo)["pending_gate"] == "review-spec"  # re-flowed back to the spec gate
    # the re-dispatch carried the feedback AND the original intent, and revised the artifact
    assert any("REVISION REQUESTED" in p and "narrow the throttle scope" in p for p in seen)
    assert any("add a rate limiter" in p for p in seen)
    assert "REVISED per feedback" in _spec_file(run_repo).read_text(encoding="utf-8")
    # the rewind was recorded as an additive signed marker carrying the reason + feedback
    markers = _redo_markers(run_repo)
    assert markers and markers[-1]["target_step"] == "specify"
    assert markers[-1]["reason"] == "the scope was too broad"
    assert markers[-1]["feedback_ref"] == "narrow the throttle scope"
    assert markers[-1]["approver"] == "carlo"
    # approving re-flows Plan → Build (they are re-dispatched), pausing again at sign-off
    seen.clear()
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # signoff
    assert any("# Plan agent" in p for p in seen)
    assert any("# Oracle agent" in p for p in seen)
    assert any("# Implement agent" in p for p in seen)


def test_redo_surfaces_in_status(run_repo, monkeypatch):
    """Covers: SEC-002 — the rewind renders in `--status`: the target stage + the approver, as
    additive audit context (not a failure, not a pause)."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED
    assert (
        _run(run_repo, "--redo", "spec", "--approver", "carlo", "--reason", "clarify")
        == EXIT_PAUSED
    )
    st = _state(run_repo)
    assert st["rewound"] and st["redo_target"] == "specify" and st["redo_approver"] == "carlo"
    rc = main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN"])
    assert rc == EXIT_OK


# =========================================================================== C. spec-lock / completion floor (REQ-011/012)
def test_redo_spec_reseals_the_amended_spec_through_the_review_gate(run_repo, monkeypatch):
    """Covers: REQ-012 — a Spec rewind flows back through `review-spec`: the first approval seals
    hash H1; after the amendment the spec becomes H2; the resume-approval records a fresh Spec
    sign-off with `spec_hash == H2`, so `integrity_gate` is PASS (MATCH) with no residual mismatch."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # review-spec
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # sealed H1, at signoff
    h1 = speclock.spec_file_hash(_spec_file(run_repo))
    sealed_h1 = speclock.spec_approval(_entries(run_repo), "RUN")
    assert sealed_h1 is not None and sealed_h1["payload"]["spec_hash"] == h1
    # rewind + amend Spec — the on-disk spec changes, but the seal is not yet refreshed
    assert (
        _run(
            run_repo,
            "--redo",
            "spec",
            "--revise",
            "tighten the acceptance criteria",
            "--approver",
            "carlo",
            "--reason",
            "underspecified",
        )
        == EXIT_PAUSED
    )
    h2 = speclock.spec_file_hash(_spec_file(run_repo))
    assert h2 != h1  # the amended spec is a different document
    # re-approve at the spec gate — the fresh sign-off re-seals the amended document
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # signoff
    resealed = speclock.spec_approval(_entries(run_repo), "RUN")
    assert resealed is not None and resealed["payload"]["spec_hash"] == h2
    gate = speclock.integrity_gate(_entries(run_repo), "RUN", run_repo, _spec_file(run_repo))
    assert gate.status == STATUS_PASS
    assert speclock.check(_entries(run_repo), "RUN", run_repo).status == speclock.MATCH


def test_redo_floor_lands_the_completion_gate_on_the_target(run_repo):
    """Covers: REQ-011 — the appended rewind marker is the completion floor: even with a pre-rewind
    `specify` completion on record, `redo_start_index` ∩ `resume_entry_index` re-enter exactly at
    `specify`, never skipping it as "already complete"."""
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # specify recorded + on disk
    feature_dir = run_repo / FEATURE
    ledger = Ledger(run_repo / ".3powers" / "ledger.jsonl")
    sk = keys.resolve_signer(run_repo)
    ledger.append(
        "run",
        {
            "kind": "redo",
            "target_step": "specify",
            "reason": "clarify",
            "feedback_ref": "",
            "approver": "carlo",
        },
        sk,
        spec_id="RUN",
    )
    entries = ledger.entries()
    start = orchestrate.redo_start_index(entries, "RUN", "review-spec")
    assert start == orchestrate.step_index("specify")
    capped, broken = completion.resume_entry_index(
        entries, "RUN", start, root=run_repo, feature_dir=feature_dir
    )
    assert capped == orchestrate.step_index("specify")  # the pre-rewind record does not advance it


def test_redo_plan_leaves_the_spec_seal_untouched_and_does_not_rerun_specify(run_repo, monkeypatch):
    """Covers: REQ-012 — a `--redo plan` rewinds only from Plan: Specify is not re-dispatched, the
    Spec-stage approval still points at the original seal, and `integrity_gate` stays PASS."""
    _mock_gates_green(monkeypatch)
    seen: list[str] = []
    monkeypatch.setattr(runner, "dispatch_agent", _writer(seen=seen))
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED  # review-spec
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED  # sealed, at signoff
    sealed = speclock.spec_approval(_entries(run_repo), "RUN")
    assert sealed is not None
    seal_seq, seal_hash = sealed["seq"], sealed["payload"]["spec_hash"]
    # rewind to Plan — no --revise; Specify must not re-run
    seen.clear()
    assert (
        _run(run_repo, "--redo", "plan", "--approver", "carlo", "--reason", "rework the phasing")
        == EXIT_PAUSED
    )
    assert not any("# Specify agent" in p for p in seen)  # Spec is untouched
    assert any("# Plan agent" in p for p in seen)  # Plan re-flowed
    still = speclock.spec_approval(_entries(run_repo), "RUN")
    assert still is not None and still["seq"] == seal_seq  # the SAME approval, not superseded
    assert still["payload"]["spec_hash"] == seal_hash
    gate = speclock.integrity_gate(_entries(run_repo), "RUN", run_repo, _spec_file(run_repo))
    assert gate.status == STATUS_PASS


def test_redo_spec_stops_at_the_mandatory_gate_under_auto_mode(run_repo, monkeypatch):
    """Covers: REQ-012/CON-001 — even in auto mode a Spec rewind stops at `review-spec`: the
    mandatory spec-approval gate is never auto-approved, so the amended spec awaits a human."""
    _mock_gates_green(monkeypatch)
    assert (
        main(
            [
                "--root",
                str(run_repo),
                "run",
                "add a rate limiter",
                "--spec-id",
                "RUN",
                "--no-input",
                "--mode",
                "auto",
            ]
        )
        == EXIT_PAUSED
    )
    assert (
        main(
            [
                "--root",
                str(run_repo),
                "run",
                "--resume",
                "--spec-id",
                "RUN",
                "--no-input",
                "--mode",
                "auto",
                "--approver",
                "carlo",
            ]
        )
        == EXIT_PAUSED
    )  # signoff
    rc = main(
        [
            "--root",
            str(run_repo),
            "run",
            "--redo",
            "spec",
            "--spec-id",
            "RUN",
            "--no-input",
            "--mode",
            "auto",
            "--approver",
            "carlo",
            "--reason",
            "clarify",
        ]
    )
    assert rc == EXIT_PAUSED
    assert _state(run_repo)["pending_gate"] == "review-spec"  # not auto-approved


# =========================================================================== D. trust spine stays green (SEC-002, TASK-023)
def test_verify_passes_after_a_redo_run(run_repo, monkeypatch):
    """Covers: SEC-002 — after a full rewind + re-flow the hash-chained, signed ledger still
    verifies end to end (`3pwr verify` succeeds): the redo marker is additive, no format change."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo, "add a rate limiter") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED
    assert (
        _run(
            run_repo,
            "--redo",
            "spec",
            "--revise",
            "tighten it",
            "--approver",
            "carlo",
            "--reason",
            "clarify",
        )
        == EXIT_PAUSED
    )
    assert _run(run_repo, "--resume", "--approver", "carlo") == EXIT_PAUSED
    assert main(["--root", str(run_repo), "verify"]) == 0
