"""The async hosted agent backend — trigger, poll, collect; judged identically to a local dispatch.

Covers RUNLIVE-FR-008 (the trigger→poll→collect contract, failure + timeout paths) and RUNLIVE-FR-009 (no
credential is interpreted, logged, or stored). All timing seams are injected, so no real process, sleep, or
network is used (RUNLIVE-NFR-002).
"""

from __future__ import annotations

from threepowers import hosted
from threepowers.config import Settings
from threepowers.hosted import HostedAgentRunner


def _manifest(**over):
    m = {
        "mode": "async-hosted",
        "trigger_command": ["gh", "trigger", "--prompt", "{prompt}"],
        "poll_command": ["gh", "poll", "{run_id}"],
        "poll_status_field": "status",
        "completed_values": ["completed"],
        "failed_values": ["failure", "cancelled"],
        "collect_command": ["gh", "pr", "checkout", "{run_id}"],
        "poll_interval_s": 5,
    }
    m.update(over)
    return m


def test_is_hosted_selects_the_backend():
    """RUNLIVE-FR-008/NFR-005: the manifest `mode` selects the hosted backend, not a hardcoded vendor."""
    assert hosted.is_hosted({"mode": "async-hosted"})
    assert not hosted.is_hosted({"command": "claude"})
    assert not hosted.is_hosted({})


def test_trigger_poll_collect_success(tmp_path):
    """RUNLIVE-FR-008: a hosted run is triggered, polled to completion, and its changes collected."""
    s = Settings(root=tmp_path)
    calls: list[list[str]] = []
    poll_seq = iter(['{"status": "running"}', '{"status": "completed"}'])

    def fake_run(argv, cwd):
        calls.append(argv)
        if argv[:2] == ["gh", "trigger"]:
            return (0, "run-123\n", "")
        if argv[:2] == ["gh", "poll"]:
            return (0, next(poll_seq), "")
        if argv[:3] == ["gh", "pr", "checkout"]:
            return (0, "Switched to branch", "")
        return (1, "", "unexpected")

    r = HostedAgentRunner(
        s, _manifest(), intent="add x", command_runner=fake_run, sleep=lambda _s: None
    )
    res = r.dispatch("implement", "Build")
    assert res.ok and "run-123" in res.detail
    # the run id from the trigger stdout flows into poll + collect (placeholder substitution)
    assert ["gh", "poll", "run-123"] in calls
    assert ["gh", "pr", "checkout", "run-123"] in calls


def test_failed_hosted_run_is_a_named_dispatch_failure(tmp_path):
    """RUNLIVE-FR-008: a failed hosted run is a dispatch failure naming the stage — never a gate-red."""
    s = Settings(root=tmp_path)

    def fake_run(argv, cwd):
        if argv[:2] == ["gh", "trigger"]:
            return (0, "run-9", "")
        return (0, '{"status": "failure"}', "")

    r = HostedAgentRunner(s, _manifest(), command_runner=fake_run, sleep=lambda _s: None)
    res = r.dispatch("oracle", "Build")
    assert not res.ok and "failed at Build" in res.detail


def test_hosted_run_timeout(tmp_path):
    """RUNLIVE-FR-008/NFR-004: a hosted run that never completes is reported as a timeout, never a hang."""
    s = Settings(root=tmp_path)
    ticks = iter(
        [0.0, 0.0, 5.0, 10.0, 100.0]
    )  # clock advances past the timeout while status stays running

    def fake_run(argv, cwd):
        if argv[:2] == ["gh", "trigger"]:
            return (0, "run-1", "")
        return (0, '{"status": "running"}', "")

    r = HostedAgentRunner(
        s,
        _manifest(),
        timeout=20,
        command_runner=fake_run,
        sleep=lambda _s: None,
        clock=lambda: next(ticks),
    )
    res = r.dispatch("implement", "Build")
    assert not res.ok and "timed out at Build" in res.detail


def test_trigger_failure_is_reported(tmp_path):
    """RUNLIVE-NFR-004: a failed trigger degrades to an actionable dispatch failure, not a crash."""
    s = Settings(root=tmp_path)
    r = HostedAgentRunner(
        s, _manifest(), command_runner=lambda argv, cwd: (1, "", "boom"), sleep=lambda _s: None
    )
    res = r.dispatch("plan", "Plan")
    assert not res.ok and "trigger failed at Plan" in res.detail


def test_no_credential_is_interpreted_or_logged(tmp_path, monkeypatch):
    """RUNLIVE-FR-009: a secret in the environment never appears in engine output, and is never read."""
    s = Settings(root=tmp_path)
    secret = "ghp_SUPERSECRETVALUE_zzz"
    monkeypatch.setenv("GITHUB_TOKEN", secret)
    seen_argv: list[list[str]] = []

    def fake_run(argv, cwd):
        seen_argv.append(argv)
        if argv[:2] == ["gh", "trigger"]:
            return (0, "run-7", "")
        if argv[:2] == ["gh", "poll"]:
            return (0, '{"status": "completed"}', "")
        return (0, "ok", "")

    r = HostedAgentRunner(s, _manifest(), command_runner=fake_run, sleep=lambda _s: None)
    res = r.dispatch("implement", "Build")
    assert res.ok
    # the engine never injects the secret into the command line or the result
    assert secret not in res.detail
    for argv in seen_argv:
        assert all(secret not in tok for tok in argv)


def test_missing_trigger_command_is_reported(tmp_path):
    """RUNLIVE-NFR-004: a misconfigured hosted manifest yields an actionable message, not a crash."""
    s = Settings(root=tmp_path)
    r = HostedAgentRunner(s, {"mode": "async-hosted"}, command_runner=lambda a, c: (0, "", ""))
    res = r.dispatch("specify", "Spec")
    assert not res.ok and "trigger_command" in res.detail
