"""The orchestration front-end — `3pwr run` drives the lifecycle loop (3PWR-FR-011, §6).

The mode/gate logic is exercised directly against a scripted ``SimulatedRunner`` (no live agents); the
CLI is driven end to end in ``--dry-run --no-input`` so the two mandatory human gates (FR-006 spec
approval, FR-037 sign-off) stop while auto mode auto-approves the intermediate gates. Orchestration is
provisioning — it never enters the deterministic verdict (NFR-001).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import lifecycle, orchestrate, style
from threepowers.cli import main
from threepowers.ledger import Ledger


# --------------------------------------------------------------------------- pure: drive() mode/gate logic
def test_drive_auto_stops_only_at_mandatory_gates():
    """3PWR-FR-006/037: auto mode stops at review-spec then signoff, auto-approving the intermediate gates."""
    events: list[orchestrate.Event] = []
    r = orchestrate.SimulatedRunner()
    r1 = orchestrate.drive(r, "auto", events.append)
    assert (
        r1.status == "paused_at_gate" and r1.gate == "review-spec" and r1.gate_fr == "spec approval"
    )
    r2 = orchestrate.drive(r, "auto", events.append, resuming=True)
    assert r2.status == "paused_at_gate" and r2.gate == "signoff" and r2.gate_fr == "sign-off"
    # review-plan + review-verify were auto-approved between the two mandatory gates.
    auto = [e.step for e in events if e.kind == "gate-auto"]
    assert "review-plan" in auto and "review-verify" in auto
    r3 = orchestrate.drive(r, "auto", events.append, resuming=True)
    assert r3.status == "done"


def test_drive_commit_stops_at_every_gate():
    """commit mode stops at the intermediate gates too (which auto mode would skip)."""
    r = orchestrate.SimulatedRunner()
    assert orchestrate.drive(r, "commit", lambda e: None).gate == "review-spec"
    assert orchestrate.drive(r, "commit", lambda e: None, resuming=True).gate == "review-plan"
    assert orchestrate.drive(r, "commit", lambda e: None, resuming=True).gate == "review-verify"
    assert orchestrate.drive(r, "commit", lambda e: None, resuming=True).gate == "signoff"


def test_drive_failed_verdict_stops():
    """A red gate verdict stops the run for a human decision (never auto-ships)."""
    r = orchestrate.SimulatedRunner(verdict="fail")
    assert orchestrate.drive(r, "auto", lambda e: None).gate == "review-spec"  # FR-006 first
    res = orchestrate.drive(r, "auto", lambda e: None, resuming=True)
    assert res.status == "failed"


def test_helpers_tracker_mandatory_resume_index():
    t = orchestrate.render_tracker("Plan")
    assert "▶ Plan" in t and "✓ Spec" in t and "· Ship" in t
    assert orchestrate.is_mandatory("review-spec") and not orchestrate.is_mandatory("review-plan")
    assert orchestrate.resume_index("review-spec") == 4  # step after review-spec
    assert orchestrate.resume_index("signoff") == 12


def test_tracker_frame_is_pure():
    frame = orchestrate.tracker_frame("Plan", orchestrate.Event("step", "plan", "Plan"))
    assert "▶ Plan" in frame and "plan" in frame  # stage tracker + current activity


def test_tracker_plain_fallback_off_tty():
    """Off a TTY (pipe / --json) the tracker falls back to plain streamed lines — no ANSI control."""
    import io

    buf = io.StringIO()
    tr = orchestrate.Tracker(buf, "auto", tty=False)
    tr.on_event(orchestrate.Event("step", "specify", "Spec"))
    tr.on_event(orchestrate.Event("gate-stop", "review-spec", "Spec"))
    out = buf.getvalue()
    assert "specify" in out and "review-spec" in out
    assert "\r" not in out and "\033" not in out  # plain, no in-place cursor control


def test_tracker_on_unsupported_tty_degrades_to_plain_log():
    """STEER-FR-015 (supersedes the CLIUX single in-place line): a TTY that cannot carry the live
    bar (here: a stream with no real terminal behind it) degrades to the existing plain streamed
    event log — no ``\\r`` in-place redraws, no live-bar control codes."""
    import io

    buf = io.StringIO()
    tr = orchestrate.Tracker(buf, "auto", tty=True, st=style.Styler())
    tr.on_event(orchestrate.Event("step", "plan", "Plan"))
    out = buf.getvalue()
    assert "plan" in out
    assert "\r" not in out  # the in-place redraw is gone (STEER advances CLIUX-FR-008/009)
    tr.close()  # closing with no frame is a safe no-op (STEER-NFR-004)


# --------------------------------------------------------------------------- CLI end-to-end (--dry-run)
@pytest.fixture()
def run_project(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root


def _state(root: Path, spec_id: str):
    return lifecycle.derive(Ledger(root / ".3powers" / "ledger.jsonl").entries()).get(spec_id)


def test_cli_run_auto_stops_at_the_two_gates_then_completes(run_project):
    """3PWR-FR-006/037/011: auto run pauses at review-spec, then signoff, then completes — resumable
    across invocations from the ledger."""
    root = run_project
    start = [
        "--root",
        str(root),
        "run",
        "add a rate limiter",
        "--dry-run",
        "--no-input",
        "--spec-id",
        "RUN",
    ]
    resume = [
        "--root",
        str(root),
        "run",
        "--resume",
        "--dry-run",
        "--no-input",
        "--spec-id",
        "RUN",
        "--approver",
        "carlo",
    ]
    assert main(start) == 3  # paused at a human gate (AUTOX-FR-009)
    assert _state(root, "RUN").pending_gate == "review-spec"  # FR-006

    assert main(resume) == 3
    assert _state(root, "RUN").pending_gate == "signoff"  # FR-037 (intermediates auto-approved)

    assert main(resume) == 0
    st = _state(root, "RUN")
    assert st.pending_gate == "" and st.stage == "Ship"
    # the two human commitments were recorded as sign-offs, and the ledger verifies.
    assert main(["--root", str(root), "verify"]) == 0


def test_cli_run_commit_stops_at_intermediate_gate(run_project):
    """commit mode stops at review-plan (which auto mode auto-approves)."""
    root = run_project
    base = [
        "--root",
        str(root),
        "run",
        "--dry-run",
        "--no-input",
        "--mode",
        "commit",
        "--spec-id",
        "C",
    ]
    assert main([*base, "build X"]) == 3
    assert _state(root, "C").pending_gate == "review-spec"
    assert main([*base, "--resume", "--approver", "x"]) == 3
    assert _state(root, "C").pending_gate == "review-plan"  # commit stops here


def test_cli_run_failed_verdict_returns_nonzero(run_project):
    """A simulated red gate verdict stops the run (exit 1) after the spec gate is approved."""
    root = run_project
    base = ["--root", str(root), "run", "--dry-run", "--no-input", "--spec-id", "F"]
    assert main([*base, "risky change"]) == 3  # pause at review-spec
    assert main([*base, "--resume", "--simulate-fail", "--approver", "x"]) == 1  # verify fails


def test_cli_run_status(run_project):
    """`3pwr run --status` shows the stage tracker + the pending gate from the ledger."""
    root = run_project
    assert (
        main(["--root", str(root), "run", "kick off", "--dry-run", "--no-input", "--spec-id", "S"])
        == 3
    )
    assert main(["--root", str(root), "run", "--status", "--spec-id", "S"]) == 0
    assert _state(root, "S").pending_gate == "review-spec"


def test_cli_run_resume_without_pause_errors(run_project):
    """--resume with nothing paused is a usage error."""
    root = run_project
    assert (
        main(
            ["--root", str(root), "run", "--resume", "--dry-run", "--no-input", "--spec-id", "NONE"]
        )
        == 2
    )
