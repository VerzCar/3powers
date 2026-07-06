"""Steering an autonomous run (STEER, spec 019) — file-based intent, human-gate notifications with
approve / reject / revise guidance, and the persistent live run frame.

Exercised with fake agents, fake channels, and no network: intent resolution from a file + inline
instruction (STEER-FR-001..004), the three gate actions with revise-with-message re-dispatch
(STEER-FR-005..008), the opt-in best-effort notification channels (STEER-FR-009..011,
STEER-NFR-001/002), the pinned live frame over a reserved scroll region with its degradations and
teardown (STEER-FR-012..016, STEER-NFR-003/004), and the unchanged trust/dependency stance
(STEER-NFR-005).
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import frame, notify, orchestrate, runner, runpreflight, steering, style
from threepowers.cli import EXIT_PAUSED, EXIT_SETUP, EXIT_USAGE, main
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_PASS, Verdict


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
    received prompt is collected into ``seen`` so tests can assert what a dispatch carried."""

    def fake(argv, **kw):
        import re

        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if seen is not None:
            seen.append(prompt)
        m = re.search(r"FEATURE FOLDER: (\S+)", prompt)
        d = cwd / (m.group(1) if m else f"specs/{spec_id}")
        if "STAGE: Specify" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            body = f"# Spec\n**Spec ID**: {spec_id}\n"
            if "REVISION REQUESTED" in prompt:
                body += "REVISED per feedback\n"
            (d / "spec.md").write_text(body, encoding="utf-8")
        elif "STAGE: Plan" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "STAGE: Tasks" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "STAGE: Oracle" in prompt:
            t = cwd / "tests" / "oracle" / spec_id
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "STAGE: Implement" in prompt:
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


def _start_intent(root: Path, spec_id="RUN") -> str:
    starts = [
        e["payload"]["intent"]
        for e in _entries(root)
        if e.get("spec_id") == spec_id
        and e.get("type") == "run"
        and e.get("payload", {}).get("kind") == "start"
    ]
    return starts[-1] if starts else ""


def _run(root: Path, *extra: str) -> int:
    return main(["--root", str(root), "run", "--no-input", "--spec-id", "RUN", *extra])


# =========================================================================== A. file-based intent
def test_file_intent_becomes_the_runs_intent_verbatim(run_repo):
    """STEER-FR-001 + STEER-FR-004: `3pwr run --file <md>` uses the file's contents as the intent,
    recorded verbatim in the signed ledger `start` entry — exactly as if typed."""
    intent_md = run_repo.parent / "my-intent.md"  # outside the tree — the GITX clean-start guard holds
    intent_md.write_text(
        "Build a rate limiter.\n\n- token bucket\n- per client\n", encoding="utf-8"
    )
    assert _run(run_repo, "--file", str(intent_md)) == EXIT_PAUSED
    assert _start_intent(run_repo) == "Build a rate limiter.\n\n- token bucket\n- per client"


def test_file_plus_inline_combines_deterministically(run_repo):
    """STEER-FR-002 (+property): the resolved intent is file-base + appended inline instruction — a
    pure deterministic function with fixed order; the combined text is what the ledger sees."""
    intent_md = run_repo.parent / "my-intent.md"
    intent_md.write_text("Build a rate limiter.\n1..5 points\n", encoding="utf-8")
    assert _run(run_repo, "--file", str(intent_md), "leave out point 5") == EXIT_PAUSED
    recorded = _start_intent(run_repo)
    assert recorded == "Build a rate limiter.\n1..5 points\n\nleave out point 5"
    # the property: pure + deterministic, file first, inline appended
    a = steering.combine("base text", "extra instruction")
    assert a == steering.combine("base text", "extra instruction")
    assert a.index("base text") < a.index("extra instruction")
    assert steering.combine("only base", "") == "only base"
    assert steering.combine("", "only inline") == "only inline"


def test_bad_intent_file_fails_fast_with_setup_exit_and_no_start_entry(run_repo, tmp_path, capsys):
    """STEER-FR-003: a missing / directory / empty / non-decodable --file fails fast with an
    actionable error naming the path, the setup exit code, and NO ledger `start` entry."""
    before = len(_entries(run_repo))
    empty = run_repo.parent / "empty.md"
    empty.write_text("   \n", encoding="utf-8")
    binary = run_repo.parent / "blob.bin"
    binary.write_bytes(b"\xff\xfe\x00\x01\x9c")
    for bad, reason in (
        (str(run_repo.parent / "nope.md"), "not found"),
        (str(run_repo), "directory"),
        (str(empty), "empty"),
        (str(binary), "not decodable"),
    ):
        rc = _run(run_repo, "--file", bad)
        err = capsys.readouterr().err
        assert rc == EXIT_SETUP, bad
        assert bad in err and reason in err  # names the path and the reason
    assert len(_entries(run_repo)) == before  # nothing partially began


def test_file_with_resume_is_a_usage_error(run_repo, capsys):
    """STEER-FR-001 (edge): --file feeds a fresh run; combined with --resume it is refused,
    pointing at --revise/--revise-file."""
    f = run_repo.parent / "i.md"
    f.write_text("x\n", encoding="utf-8")
    assert _run(run_repo, "--resume", "--file", str(f)) == EXIT_USAGE
    assert "--revise" in capsys.readouterr().err


# =========================================================================== B. approve / reject / revise
def test_gate_pause_presents_three_actions_with_commands_and_artifact(run_repo, capsys):
    """STEER-FR-005: the on-screen pause names approve, reject, and revise — each with a
    copy-pasteable command carrying the spec id — plus the artifact under review."""
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    out = capsys.readouterr().out
    assert "3pwr run --resume --spec-id RUN --approver <you>" in out  # approve
    assert "3pwr abort --spec-id RUN" in out  # reject (stops — the existing path)
    assert '--revise "<feedback>"' in out  # revise-with-message
    assert "specs/001-steer-the-run/spec.md" in out  # the artifact to review


def test_revise_reruns_the_paused_stage_and_returns_to_the_same_gate(run_repo, monkeypatch, capsys):
    """STEER-FR-006: `--resume --revise "<msg>"` re-dispatches the stage owning the reviewed
    artifact with the original intent, the current artifact, and the feedback; the artifact is
    revised and the run pauses again at the SAME gate."""
    seen: list[str] = []
    monkeypatch.setattr(runner, "dispatch_agent", _writer(seen=seen))
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    spec_file = run_repo / "specs" / "001-steer-the-run" / "spec.md"
    assert "REVISED" not in spec_file.read_text(encoding="utf-8")
    rc = _run(run_repo, "--resume", "--revise", "leave out point 5")
    assert rc == EXIT_PAUSED  # back at the gate, not advanced past it
    prompt = seen[-1]
    assert "REVISION REQUESTED" in prompt and "leave out point 5" in prompt
    assert "steer the run" in prompt  # the ORIGINAL intent rode along
    assert "specs/001-steer-the-run/spec.md" in prompt  # the current artifact is named
    assert "REVISED" in spec_file.read_text(encoding="utf-8")  # a revised artifact was produced
    st = _state(run_repo)
    assert st["pending_gate"] == "review-spec"  # the same gate awaits the human


def _state(root: Path, spec_id="RUN") -> dict:
    from threepowers import lifecycle

    st = lifecycle.derive(_entries(root)).get(spec_id)
    return {"pending_gate": st.pending_gate if st else "", "stage": st.stage if st else ""}


def test_revise_feedback_from_file_and_same_resolution_rule(run_repo, monkeypatch):
    """STEER-FR-007 (+property): feedback is acceptable from a file, resolved by the SAME
    deterministic rule as the intent source — origin does not change the resolved text."""
    seen: list[str] = []
    monkeypatch.setattr(runner, "dispatch_agent", _writer(seen=seen))
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    fb = run_repo.parent / "feedback.md"
    fb.write_text("tighten the non-goals\n", encoding="utf-8")
    assert _run(run_repo, "--resume", "--revise-file", str(fb)) == EXIT_PAUSED
    assert "tighten the non-goals" in seen[-1]
    # the property: one resolution rule for intent and feedback
    fi, _ = steering.resolve_intent(str(fb), "and point 5")
    ff, _ = steering.resolve_feedback(str(fb), "and point 5")
    assert fi == ff == "tighten the non-goals\n\nand point 5"


def test_empty_feedback_and_revise_outside_a_gate_are_rejected(run_repo, capsys):
    """STEER-FR-007: empty/whitespace feedback, and a revise when not paused at a gate, each yield
    an actionable error — the artifact and gate state are unchanged."""
    # not paused at a gate (no run at all)
    assert _run(run_repo, "--resume", "--revise", "msg") == EXIT_USAGE
    assert "not paused at a human gate" in capsys.readouterr().err
    # paused, but whitespace-only feedback
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    spec_file = run_repo / "specs" / "001-steer-the-run" / "spec.md"
    before = spec_file.read_text(encoding="utf-8")
    capsys.readouterr()
    assert _run(run_repo, "--resume", "--revise", "   ") == EXIT_USAGE
    assert "empty" in capsys.readouterr().err
    assert spec_file.read_text(encoding="utf-8") == before  # artifact untouched
    assert _state(run_repo)["pending_gate"] == "review-spec"  # gate still paused


def test_revision_is_recorded_in_the_ledger_and_verify_stays_green(run_repo):
    """STEER-FR-008: the revision — feedback and outcome — rides the existing run-entry append path;
    `3pwr verify` still succeeds (no ledger-format change)."""
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--revise", "leave out point 5") == EXIT_PAUSED
    revises = [
        e["payload"]
        for e in _entries(run_repo)
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "revise"
    ]
    assert len(revises) == 1
    assert revises[0]["feedback"] == "leave out point 5"
    assert revises[0]["ok"] is True and revises[0]["gate"] == "review-spec"
    assert main(["--root", str(run_repo), "verify"]) == 0


def test_repeated_revises_each_rerun_and_rerecord(run_repo):
    """STEER-FR-006/008 (edge): revise used repeatedly at the same gate re-runs the stage each time,
    records each revision, and re-presents the same gate until the operator approves or rejects."""
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--revise", "first pass") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--revise", "second pass") == EXIT_PAUSED
    feedbacks = [
        e["payload"]["feedback"]
        for e in _entries(run_repo)
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "revise"
    ]
    assert feedbacks == ["first pass", "second pass"]
    assert _state(run_repo)["pending_gate"] == "review-spec"


def test_approve_after_revise_still_records_the_human_signoff(run_repo, monkeypatch):
    """STEER-FR-005/006: revise never substitutes for approval — after a revision, a plain --resume
    still records the human sign-off before the run continues past the gate (3PWR-FR-006)."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--revise", "polish") == EXIT_PAUSED
    assert _run(run_repo, "--resume", "--approver", "human") == EXIT_PAUSED  # → signoff gate
    signoffs = [e for e in _entries(run_repo) if e.get("type") == "signoff"]
    assert signoffs and signoffs[-1]["payload"]["approver"] == "human"


# =========================================================================== C. notifications
def _channels_yaml(root: Path, channels: list[dict]) -> None:
    (root / ".3powers" / "config" / "notifications.yaml").write_text(
        yaml.safe_dump({"version": 1, "channels": channels}), encoding="utf-8"
    )


def test_gate_pause_notifies_enabled_channel_with_actionable_message(run_repo, monkeypatch):
    """STEER-FR-009: with a channel enabled, a gate pause delivers a message naming the spec id,
    stage and gate, the artifact to review, and the approve/reject/revise commands filled in."""
    sent: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        notify, "_post_json", lambda url, payload, timeout: sent.append((url, payload))
    )
    monkeypatch.setenv("THREEPOWERS_SLACK_WEBHOOK", "https://hooks.example/T00/B00")
    _channels_yaml(run_repo, [{"type": "slack"}])
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    assert sent and sent[0][0] == "https://hooks.example/T00/B00"
    text = sent[0][1]["text"]
    assert "RUN" in text and "review-spec" in text and "3PWR-FR-006" in text
    assert "specs/001-steer-the-run/spec.md" in text
    assert "3pwr run --resume --spec-id RUN --approver <you>" in text
    assert "3pwr abort --spec-id RUN" in text and "--revise" in text


def test_failure_and_completion_notify_with_next_steps(run_repo, monkeypatch):
    """STEER-FR-009: a failed run and a completed run each deliver a correspondingly actionable
    message — the failure class and how to resume, or the completion notice."""
    sent: list[str] = []
    monkeypatch.setattr(
        notify, "_post_json", lambda url, payload, timeout: sent.append(payload["text"])
    )
    monkeypatch.setenv("THREEPOWERS_SLACK_WEBHOOK", "https://hooks.example/x")
    _channels_yaml(run_repo, [{"type": "slack"}])
    _mock_gates_green(monkeypatch)
    # a failing dispatch → failure event with the resume command
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (1, "", "boom"))
    assert _run(run_repo, "steer the run", "--retries", "0") == EXIT_SETUP
    assert any("dispatch failed" in t and "3pwr run --resume --spec-id RUN" in t for t in sent)
    # a completing run → completion notice
    sent.clear()
    monkeypatch.setattr(runner, "dispatch_agent", _writer())
    assert main(["--root", str(run_repo), "abort", "--spec-id", "RUN"]) == 0
    assert _run(run_repo, "run it clean", "--spec-id", "RUN2", "--no-input") in (EXIT_PAUSED,)
    # walk RUN2 to completion through both human gates
    r2 = ["--root", str(run_repo), "run", "--resume", "--no-input", "--spec-id", "RUN2"]
    assert main([*r2, "--approver", "human"]) == EXIT_PAUSED
    assert main([*r2, "--approver", "human"]) == 0
    assert any("lifecycle complete" in t for t in sent)


def test_broken_channel_never_blocks_or_alters_the_run(run_repo, monkeypatch, capsys):
    """STEER-NFR-001 + STEER-SC-002: a misconfigured/unreachable channel changes NOTHING — same exit
    code and same ledger as a run with notifications disabled; the delivery failure is at most a
    one-line warning."""

    def _boom(url, payload, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(notify, "_post_json", _boom)
    monkeypatch.setenv("THREEPOWERS_SLACK_WEBHOOK", "https://hooks.example/x")
    _channels_yaml(run_repo, [{"type": "slack"}])
    rc = _run(run_repo, "steer the run")
    err = capsys.readouterr().err
    assert rc == EXIT_PAUSED  # exactly the no-channel outcome
    assert "delivery failed" in err and "OSError" in err
    assert _state(run_repo)["pending_gate"] == "review-spec"
    assert main(["--root", str(run_repo), "verify"]) == 0  # ledger identical in kind


def test_no_channels_and_no_notify_makes_no_network_call(run_repo, monkeypatch):
    """STEER-NFR-001/STEER-SC-005: with no notifications.yaml and no --notify, no network call is
    made at any point (a blocked socket does not stop the run)."""
    import socket

    def _no_network(*_a, **_k):
        raise AssertionError("network call attempted")

    monkeypatch.setattr(socket, "socket", _no_network)
    assert _run(run_repo, "steer the run") == EXIT_PAUSED


def test_notifications_yaml_is_tolerant_and_extensible(tmp_path):
    """STEER-FR-010: a missing file disables notifications; malformed/unknown input warns once and
    falls back; the four reference channel types are selectable."""
    missing = tmp_path / "notifications.yaml"
    assert notify.load_channels(missing) == ([], [])
    missing.write_text("channels: [unclosed", encoding="utf-8")
    chans, warns = notify.load_channels(missing)
    assert chans == [] and len(warns) == 1 and "malformed" in warns[0]
    missing.write_text(
        yaml.safe_dump(
            {
                "channels": [
                    {"type": "slack"},
                    {"type": "teams"},
                    {"type": "email", "host": "smtp.e", "to": "a@b"},
                    {"type": "desktop"},
                    {"type": "pager"},  # unknown type → warned, skipped
                    {"type": "slack", "frobnicate": True},  # unknown key → warned, kept
                    {"type": "slack", "enabled": False},  # disabled → skipped silently
                ]
            }
        ),
        encoding="utf-8",
    )
    chans, warns = notify.load_channels(missing)
    assert [c.type for c in chans] == ["slack", "teams", "email", "desktop", "slack"]
    assert any("pager" in w for w in warns) and any("frobnicate" in w for w in warns)


def test_event_routing_is_configurable_with_defaults_and_notify_hook_alongside(
    run_repo, monkeypatch, tmp_path
):
    """STEER-FR-011: per-channel routing selects which of {gate, failure, completion} it receives;
    no routing = the default all-three; the --notify command hook fires alongside channels."""
    # pure routing
    ch_gate = notify.Channel(type="slack", events=("gate",))
    ch_all = notify.Channel(type="slack")
    assert ch_all.events == notify.DEFAULT_EVENTS
    sent: list[str] = []
    monkeypatch.setattr(
        notify, "_post_json", lambda url, payload, timeout: sent.append(payload["text"])
    )
    env = {"THREEPOWERS_SLACK_WEBHOOK": "https://x"}
    assert notify.dispatch([ch_gate], "failure", "s", "m", env=env) == []
    assert sent == []  # a gate-only channel receives no failure
    notify.dispatch([ch_gate, ch_all], "gate", "s", "m", env=env)
    assert len(sent) == 2
    # CLI: --notify hook + configured channel both fire on the same pause
    sent.clear()
    hooklog = tmp_path / "hook.log"
    monkeypatch.setenv("THREEPOWERS_SLACK_WEBHOOK", "https://x")
    _channels_yaml(run_repo, [{"type": "slack", "events": ["gate"]}])
    hook = f"sh -c 'echo notified >> {hooklog}' --"
    assert _run(run_repo, "steer the run", "--notify", hook) == EXIT_PAUSED
    assert sent and hooklog.exists()


def test_missing_env_secret_skips_channel_without_leaking(run_repo, monkeypatch, capsys):
    """STEER-NFR-002: a channel whose environment secret is missing is skipped with a one-line
    warning naming the VARIABLE, never a value; a committed config carries no plaintext secret."""
    monkeypatch.delenv("THREEPOWERS_SLACK_WEBHOOK", raising=False)
    _channels_yaml(run_repo, [{"type": "slack"}])
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    err = capsys.readouterr().err
    assert "THREEPOWERS_SLACK_WEBHOOK is not set" in err
    # the shipped scaffold config references env vars only — no URL/credential values
    scaffold_cfg = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "threepowers"
        / "scaffold"
        / "config"
        / "notifications.yaml"
    ).read_text(encoding="utf-8")
    assert "https://hooks.slack.com" not in scaffold_cfg and "password:" not in scaffold_cfg


def test_no_secret_value_reaches_ledger_or_warnings(run_repo, monkeypatch, capsys):
    """STEER-NFR-002: the secret's VALUE appears in no ledger entry and no warning, even when
    delivery fails."""
    secret = "https://hooks.example/SECRET-TOKEN-XYZ"

    def _boom(url, payload, timeout):
        raise OSError("cannot reach host")

    monkeypatch.setattr(notify, "_post_json", _boom)
    monkeypatch.setenv("THREEPOWERS_SLACK_WEBHOOK", secret)
    _channels_yaml(run_repo, [{"type": "slack"}])
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    err = capsys.readouterr().err
    assert secret not in err
    assert all(secret not in json.dumps(e) for e in _entries(run_repo))


def test_email_and_desktop_channels_deliver_through_their_seams(monkeypatch):
    """STEER-FR-010: the email and desktop reference channels route through the standard-library
    senders — exercised via their seams, no live SMTP/osascript."""
    mails: list = []
    monkeypatch.setattr(
        notify, "_send_email", lambda host, port, msg, **kw: mails.append((host, port, msg))
    )
    ch = notify.Channel(
        type="email", options={"host": "smtp.example", "port": 2525, "to": "you@e.st"}
    )
    assert notify.dispatch([ch], "gate", "subject", "body", env={}) == []
    assert mails and mails[0][0] == "smtp.example" and mails[0][1] == 2525
    assert mails[0][2]["To"] == "you@e.st" and "body" in mails[0][2].get_content()
    pops: list = []
    monkeypatch.setattr(notify, "_display_desktop", lambda title, body, timeout: pops.append(title))
    assert notify.dispatch([notify.Channel(type="desktop")], "gate", "s", "m", env={}) == []
    assert pops == ["s"]


# =========================================================================== D. the persistent live frame
class _FakeTty(io.StringIO):
    def isatty(self):  # a capable terminal for the frame tests
        return True


def _tty_frame(subject="RUN", size=(100, 24), enabled=True):
    buf = _FakeTty()
    lf = frame.LiveFrame(buf, st=style.Styler(enabled=enabled), subject=subject, size=size)
    return buf, lf


def test_frame_stays_pinned_while_output_streams(run_repo, monkeypatch):
    """STEER-FR-012: the frame reserves a scroll region so the header rows stay pinned while stdout
    streams below — the header is drawn by absolute cursor addressing, never scrolled."""
    buf, lf = _tty_frame()
    lf.note(kind="step", step="specify", stage="Spec", detail="", reached="Spec", spec_id="RUN")
    out = buf.getvalue()
    assert f"\033[{frame.HEADER_HEIGHT + 1};24r" in out  # the reserved region below the header
    assert "\033[1;1H" in out and "\0337" in out and "\0338" in out  # pinned redraw, cursor saved
    for _ in range(200):  # agent output streams as ordinary writes — the region confines it
        buf.write("agent output line\n")
    lf.note(kind="step", step="plan", stage="Plan", detail="", reached="Plan", spec_id="RUN")
    tail = buf.getvalue()[len(out) :]
    assert "\033[1;1H" in tail  # the header is re-addressed at the top, not appended at the bottom
    lf.close()


def test_frame_marks_are_a_deterministic_function_of_the_reached_stage():
    """STEER-FR-012 (property): stages before the reached one are done, the reached one current,
    the rest upcoming — pure and deterministic."""
    marks = dict(frame.stage_marks("Build"))
    assert marks["Discovery"] == marks["Spec"] == marks["Plan"] == "done"
    assert marks["Build"] == "current"
    assert marks["Verify"] == marks["Review"] == marks["Ship"] == marks["Observe"] == "todo"
    assert frame.stage_marks("Build") == frame.stage_marks("Build")


def test_frame_states_running_paused_failed_are_distinct_with_gate_guidance():
    """STEER-FR-013: stage transitions, gate pauses, and failures render visibly distinct states
    (per the AUTOX failure taxonomy), and the paused frame shows the resume/reject/revise guidance."""
    st = style.Styler()
    running = frame.next_state(
        frame.FrameState(),
        kind="step",
        step="plan",
        stage="Plan",
        detail="",
        reached="Plan",
        spec_id="X",
    )
    paused = frame.next_state(
        running,
        kind="gate-stop",
        step="review-spec",
        stage="Spec",
        detail="",
        reached="Spec",
        spec_id="X",
    )
    failed = frame.next_state(
        running,
        kind="failed",
        step="dispatch_failed",
        stage="Build",
        detail="",
        reached="Build",
        spec_id="X",
    )
    r = "\n".join(frame.frame_lines(running, 100, st))
    p = "\n".join(frame.frame_lines(paused, 100, st))
    f = "\n".join(frame.frame_lines(failed, 100, st))
    assert "▶ running plan" in r
    assert "⏸" in p and "HUMAN GATE 'review-spec'" in p and "awaiting your decision" in p
    assert "--revise" in p and "--resume --spec-id X" in p  # the guidance while paused
    assert "✗ failed — dispatch_failed" in f  # the AUTOX failure class, named
    assert r != p != f


def test_frame_adds_no_dependency_and_no_network(monkeypatch):
    """STEER-FR-014 + STEER-NFR-005: the declared runtime dependencies stay exactly
    {cryptography, PyYAML}, and rendering the frame opens no socket."""
    import socket
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
    assert sorted(d.split(">=")[0].lower() for d in deps) == ["cryptography", "pyyaml"]

    def _no_network(*_a, **_k):
        raise AssertionError("the frame opened a socket")

    monkeypatch.setattr(socket, "socket", _no_network)
    buf, lf = _tty_frame()
    lf.note(kind="step", step="plan", stage="Plan", detail="", reached="Plan", spec_id="RUN")
    lf.close()
    assert buf.getvalue()


def test_frame_degrades_off_tty_json_no_color_and_small_terminals(run_repo, monkeypatch, capsys):
    """STEER-FR-015: off a TTY, under --json, under NO_COLOR, or on a terminal that cannot carry the
    region, the plain streamed log applies — no \\r, no escapes — and the --json per-stage results
    and exit code are unchanged."""
    env_ok = {"TERM": "xterm-256color"}
    assert not frame.supported(io.StringIO(), env=env_ok)  # off a TTY
    assert not frame.supported(_FakeTty(), env={"TERM": "xterm", "NO_COLOR": "1"}, size=(100, 24))
    assert not frame.supported(_FakeTty(), env={"TERM": "dumb"}, size=(100, 24))
    assert not frame.supported(_FakeTty(), env=env_ok, size=(100, 4))  # too small
    assert frame.supported(_FakeTty(), env=env_ok, size=(100, 24))
    # a piped --json run carries no frame control codes and keeps its per-stage results + exit code
    rc = _run(run_repo, "steer the run", "--json")
    out = capsys.readouterr().out
    assert rc == EXIT_PAUSED
    assert "\r" not in out and "\033" not in out
    obj = json.loads(out)
    assert obj["status"] == "paused_at_gate" and obj["gate"] == "review-spec"
    assert [s["step"] for s in obj["stages"]] == ["specify", "clarify"]


def test_frame_resize_relayouts_and_teardown_restores_the_terminal():
    """STEER-FR-016 + STEER-NFR-004: a resize re-lays the frame out without corruption; teardown —
    normal or after an interrupt — resets the scroll region and restores the cursor, idempotently,
    and never uses the alternate screen buffer."""
    buf, lf = _tty_frame(size=(100, 24))
    lf.note(kind="step", step="plan", stage="Plan", detail="", reached="Plan", spec_id="RUN")
    lf.resize()
    lf.close()
    lf.close()  # idempotent — the exception path may close again (STEER-NFR-004)
    out = buf.getvalue()
    assert "\033[?25l" in out and "\033[?25h" in out  # cursor hidden while owned, restored after
    assert "\033[r" in out  # the scroll region is reset
    assert out.count("\033[?25h") == 1  # close is idempotent
    assert "\033[?1049" not in out  # never the alternate screen buffer (non-goal)
    # an interrupted run converges through the same idempotent close (the CLI's finally)
    buf2, lf2 = _tty_frame()
    lf2.note(kind="step", step="plan", stage="Plan", detail="", reached="Plan", spec_id="RUN")
    try:
        raise KeyboardInterrupt
    except KeyboardInterrupt:
        lf2.close()
    assert "\033[?25h" in buf2.getvalue() and "\033[r" in buf2.getvalue()


def test_tracker_routes_events_through_an_injected_frame_and_closes_on_terminal_event():
    """STEER-FR-012/013: the run tracker streams the event log INTO the region and folds each event
    into the pinned frame; a terminal event (gate pause) finalizes the frame — region released."""
    buf = _FakeTty()
    lf = frame.LiveFrame(buf, st=style.Styler(), subject="RUN", size=(100, 24))
    tr = orchestrate.Tracker(buf, "auto", tty=True, st=style.Styler(), subject="RUN", frame_view=lf)
    tr.on_event(orchestrate.Event("step", "specify", "Spec"))
    assert "▶ running specify" in buf.getvalue()  # the pinned status line
    tr.on_event(orchestrate.Event("gate-stop", "review-spec", "Spec"))
    out = buf.getvalue()
    assert "HUMAN GATE 'review-spec'" in out  # the paused state rendered
    assert "\033[r" in out and "\033[?25h" in out  # the frame released the terminal at the pause
    tr.close()  # idempotent after the terminal event


def test_rendering_and_resolution_are_deterministic_and_json_is_frame_free(
    run_repo, monkeypatch, capsys
):
    """STEER-NFR-003: frame rendering and intent/feedback resolution are pure — identical inputs,
    identical bytes — and forcing color/frames on never touches a --json payload."""
    st = style.Styler(enabled=True)
    state = frame.FrameState(reached="Build", status="running", activity="implement")
    assert frame.frame_lines(state, 90, st, "X") == frame.frame_lines(state, 90, st, "X")
    assert steering.revise_context("g", "a.md", "fb") == steering.revise_context("g", "a.md", "fb")
    monkeypatch.setenv("THREEPOWERS_FORCE_COLOR", "1")
    rc = _run(run_repo, "steer the run", "--json")
    out = capsys.readouterr().out
    assert rc == EXIT_PAUSED and "\033" not in out
    json.loads(out)  # still a clean machine payload


def test_width_unknown_terminal_yields_plain_log_without_exception():
    """STEER-NFR-004: a width-unknown/dumb terminal produces the plain streamed log — no exception,
    no control codes (the tracker builds no frame)."""
    buf = _FakeTty()
    tr = orchestrate.Tracker(
        buf,
        "auto",
        tty=True,
        st=style.Styler(),
        subject="RUN",
        frame_view=frame.build(buf, st=style.Styler(), env={"TERM": "dumb"}),
    )
    tr.on_event(orchestrate.Event("step", "plan", "Plan"))
    out = buf.getvalue()
    assert "plan" in out and "\033" not in out and "\r" not in out
    tr.close()


def test_engine_stays_offline_reconstructable_with_notifications_unconfigured(run_repo):
    """STEER-NFR-005: with notifications unconfigured the run, `3pwr verify`, and an offline
    reconstruction succeed exactly as before this feature (see also STEER-SC-005); STATUS stays the
    single home of implementation status (asserted in the docs suite)."""
    assert _run(run_repo, "steer the run") == EXIT_PAUSED
    assert main(["--root", str(run_repo), "verify"]) == 0
