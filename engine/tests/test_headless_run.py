"""Headless executive dispatch — a live, end-to-end ``3pwr run`` (RUNX-FR-001…012, NFR-001…005).

The live headless dispatch of real agents cannot run in the suite, so — per RUNX-SC-007 — the preflight,
honest-diagnostics, provenance, and diversity logic are exercised directly and through the CLI with the
live runner stubbed, while the fully-offline ``--dry-run`` path is driven end to end.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from threepowers import orchestrate, runpreflight
from threepowers.cli import main
from threepowers.config import Settings
from threepowers.ledger import Ledger


def _settings_with_roles(tmp_path: Path, roles_yaml: str) -> Settings:
    root = tmp_path / "proj"
    (root / ".3powers" / "config").mkdir(parents=True, exist_ok=True)
    (root / ".3powers" / "config" / "roles.yaml").write_text(roles_yaml, encoding="utf-8")
    return Settings(root=root)


_DIVERSE_ROLES = (
    "version: 1\ndiversity_level: family\n"
    "headless_integrations: [claude, gemini, codex]\n"
    "roles:\n"
    "  coder: {model_family: openai, integration: claude}\n"
    "  oracle: {model_family: anthropic, model: anthropic/opus, integration: gemini}\n"
)


@pytest.fixture()
def run_project(tmp_path, monkeypatch):
    """A trust-spine project with a resolvable signer (mirrors the orchestrate suite's fixture)."""
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    # A working git repository is a run precondition (GITX-FR-002).
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True, capture_output=True)
    return root


# --------------------------------------------------------------------------- EXEC-FR-015/016 (native preflight)
def _native_settings(tmp_path, roles_yaml: str, agents: dict) -> Settings:
    root = tmp_path / "proj"
    (root / ".3powers" / "config").mkdir(parents=True, exist_ok=True)
    (root / ".3powers" / "config" / "roles.yaml").write_text(roles_yaml, encoding="utf-8")
    adir = root / ".3powers" / "agents"
    adir.mkdir(parents=True, exist_ok=True)
    import yaml

    for name, data in agents.items():
        (adir / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return Settings(root=root)


_PRESENT = lambda cmd: True  # noqa: E731 — probe stub (EXEC-NFR-004)


def test_preflight_reports_every_missing_prerequisite_with_a_fix(tmp_path):
    """EXEC-FR-015: each unmet prerequisite is named with an exact fix, before any dispatch."""
    s = _native_settings(tmp_path, "version: 1\nroles: {}\n", {})
    prqs = runpreflight.check_native(
        s, coder_agent="", oracle_agent="", entries=[], spec_id="X", command_present=_PRESENT
    )
    unmet = {p.name: p.fix for p in runpreflight.unmet(prqs)}
    assert set(unmet) == {"headless coder agent", "different-family oracle agent"}
    assert all(fix for fix in unmet.values())  # every unmet prereq carries a fix


def test_preflight_flags_non_headless_coder_agent(tmp_path):
    """EXEC-FR-015 (edge): an agent whose manifest is not headless is flagged as not dispatchable."""
    s = _native_settings(
        tmp_path,
        _DIVERSE_ROLES,
        {"windsurf": {"command": "windsurf", "headless": False}, "claude": {"command": "claude"}},
    )
    prqs = runpreflight.check_native(
        s,
        coder_agent="windsurf",
        oracle_agent="claude",
        entries=[],
        spec_id="X",
        command_present=_PRESENT,
    )
    coder = next(p for p in prqs if p.name == "headless coder agent")
    assert not coder.ok and "not headless-dispatchable" in coder.fix


def test_preflight_passes_when_all_satisfied(tmp_path):
    """EXEC-FR-015: a project meeting every prerequisite passes preflight with no spurious warning."""
    roles = (
        "version: 1\ndiversity_level: family\nroles:\n"
        "  coder: {model_family: openai, integration: codex}\n"
        "  oracle: {model_family: anthropic, integration: claude}\n"
    )
    s = _native_settings(
        tmp_path,
        roles,
        {
            "claude": {"command": "claude", "headless": True},
            "codex": {"command": "codex", "headless": True},
        },
    )
    prqs = runpreflight.check_native(
        s,
        coder_agent="codex",
        oracle_agent="claude",
        entries=[],
        spec_id="X",
        command_present=_PRESENT,
    )
    assert runpreflight.unmet(prqs) == []


def test_headless_set_is_configuration_driven(tmp_path):
    """EXEC-NFR-003: the accepted headless set is data — no agent name is hardcoded in the check."""
    s = _native_settings(
        tmp_path,
        "version: 1\nheadless_integrations: [only-this]\nroles: {}\n",
        {"claude": {"command": "claude", "headless": True}},
    )
    assert runpreflight.headless_set(s) == {"only-this"}
    # a normally-headless agent is now rejected because it is not in the configured set
    prqs = runpreflight.check_native(
        s,
        coder_agent="claude",
        oracle_agent="only-this",
        entries=[],
        spec_id="X",
        command_present=_PRESENT,
    )
    coder = next(p for p in prqs if p.name == "headless coder agent")
    assert not coder.ok


def test_offline_alternatives_name_dry_run_and_step_by_step():
    """EXEC-FR-016: the always-available offline paths name --dry-run and the step-by-step flow."""
    joined = " ".join(runpreflight.OFFLINE_ALTERNATIVES)
    assert "--dry-run" in joined and "3pwr oracle" in joined


# --------------------------------------------------------------------------- RUNX-FR-010, NFR-003/004 (CLI preflight)
def test_cli_live_run_preflight_fails_fast_never_gates_red(run_project, capsys):
    """RUNX-FR-010 / SC-003 / RUNX-NFR-003 / RUNX-NFR-004: a live run missing prerequisites fails fast
    with a named prerequisite + fix — a clean non-zero exit distinct from a gate failure, in
    machine-readable form, never 'gates red', never the incident path."""
    root = run_project
    rc = main(["--root", str(root), "run", "build X", "--no-input", "--json", "--spec-id", "P"])
    assert (
        rc == 4
    )  # the setup/dispatch code, distinct from usage (2) and gate failure (1) — AUTOX-FR-009
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "preflight_failed"
    assert payload["missing"] and payload["alternatives"]
    assert "gates red" not in out
    assert "observe signal" not in out and "incident" not in out


def test_cli_dry_run_needs_no_prerequisites(run_project):
    """RUNX-FR-012: the simulated dry-run dispatches nothing and needs neither workflow nor integration."""
    root = run_project
    rc = main(["--root", str(root), "run", "build X", "--dry-run", "--no-input", "--spec-id", "D"])
    assert rc == 3  # pauses cleanly at the first human gate, offline (AUTOX-FR-009)


def test_engine_dry_run_makes_no_network_call(run_project, monkeypatch):
    """RUNX-FR-002: the engine itself makes no model/agent call — a blocked socket does not stop a run."""

    def _no_network(*_a, **_k):
        raise RuntimeError("engine attempted a network call")

    monkeypatch.setattr(socket, "socket", _no_network)
    root = run_project
    assert main(["--root", str(root), "run", "x", "--dry-run", "--no-input", "--spec-id", "N"]) == 3


# --------------------------------------------------------------------------- RUNX-FR-010/011 (honest diagnostics)
def test_auto_stops_at_two_gates_commit_stops_at_every_gate():
    """RUNX-FR-003: auto mode auto-continues past intermediate gates and stops only at the mandatory
    human gates; commit mode stops at every gate — no mode skips a mandatory gate."""
    # auto: pause at review-spec (mandatory), then resume auto-approves review-plan and stops at signoff.
    auto = orchestrate.SimulatedRunner()
    assert orchestrate.drive(auto, "auto", lambda _e: None).gate == "review-spec"
    assert orchestrate.drive(auto, "auto", lambda _e: None, resuming=True).gate == "signoff"
    # commit: the intermediate review-plan gate (auto-approved above) now stops the run.
    commit = orchestrate.SimulatedRunner()
    assert orchestrate.drive(commit, "commit", lambda _e: None).gate == "review-spec"
    assert orchestrate.drive(commit, "commit", lambda _e: None, resuming=True).gate == "review-plan"


def test_runresult_is_gate_red_only_on_fail_verdict():
    """RUNX-FR-010: only a failure carrying a real 'fail' verdict is a gate-red."""
    assert orchestrate.RunResult("failed", verdict="fail").is_gate_red is True
    assert orchestrate.RunResult("failed", verdict="").is_gate_red is False
    assert orchestrate.RunResult("done").is_gate_red is False


def test_format_event_distinguishes_dispatch_failure_from_gates_red():
    """RUNX-FR-010/011: a dispatch failure names the stage and is NOT 'gates red'; a verdict fail is."""
    dispatch = orchestrate.format_event(
        orchestrate.Event("failed", stage="Build", detail=""), "auto"
    )
    assert "dispatch failed" in dispatch and "Build" in dispatch and "gates red" not in dispatch
    verdict = orchestrate.format_event(
        orchestrate.Event("failed", stage="Verify", detail="fail"), "auto"
    )
    assert "gates red" in verdict


def test_cli_gates_red_only_on_real_verdict(run_project, capsys):
    """RUNX-FR-011: a real red gate verdict reports gate-red, shows Verify reached, and exits 1."""
    root = run_project
    base = ["--root", str(root), "run", "--dry-run", "--no-input", "--spec-id", "G"]
    assert main([*base, "risky"]) == 3  # pause at review-spec
    capsys.readouterr()
    rc = main([*base, "--resume", "--simulate-fail", "--approver", "x", "--json"])
    assert rc == 1  # gate-failure status
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "gates_red"
    assert payload["stage"] == "Verify"


def test_cli_dispatch_failure_is_not_gates_red(run_project, monkeypatch, capsys):
    """EXEC-FR-016: a mid-run dispatch failure names the stage, exits 4, and is never 'gates red'."""
    import threepowers.cli as climod

    root = run_project
    monkeypatch.setattr(runpreflight, "check_native", lambda *a, **k: [])  # prerequisites hold
    monkeypatch.setattr(climod, "_run_make_runner", lambda *a, **k: orchestrate.SimulatedRunner())
    monkeypatch.setattr(
        orchestrate,
        "drive",
        lambda *a, **k: orchestrate.RunResult("failed", stage="Build", verdict=""),
    )
    rc = main(["--root", str(root), "run", "x", "--no-input", "--json", "--spec-id", "DF"])
    assert rc == 4  # the setup/dispatch code — distinct from the gate-failure status (AUTOX-FR-009)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["status"] == "dispatch_failed" and payload["stage"] == "Build"
    assert "gates red" not in out and "incident" not in out


# --------------------------------------------------------------------------- RUNX-FR-004/007 (segments, provenance)
def test_segment_actions_are_per_segment_and_never_recount_completed():
    """RUNX-FR-004/007: each segment yields only its own action stages, up to the next gate."""
    assert orchestrate.segment_actions("") == [
        ("discovery", "Discovery"),
        ("specify", "Spec"),
        ("clarify", "Spec"),
    ]
    assert orchestrate.segment_actions("review-spec") == [("plan", "Plan")]
    assert orchestrate.segment_actions("review-plan") == [
        ("tasks", "Plan"),
        ("oracle", "Build"),
        ("implement", "Build"),
    ]


def test_provenance_payload_names_stage_integration_model():
    """RUNX-FR-007: a provenance entry names the stage, the integration, and the resolved model."""
    assert runpreflight.provenance_payload("plan", "claude", "anthropic/opus") == {
        "kind": "dispatch",
        "stage": "plan",
        "integration": "claude",
        "model": "anthropic/opus",
    }


def test_live_run_records_per_stage_provenance_and_ledger_verifies(run_project, monkeypatch):
    """EXEC-FR-014: a (stubbed) run records one provenance entry per dispatched stage, bound into the
    signed ledger, which then verifies offline."""
    import threepowers.cli as climod

    root = run_project
    (root / ".3powers" / "config" / "roles.yaml").write_text(_DIVERSE_ROLES, encoding="utf-8")
    monkeypatch.setattr(runpreflight, "check_native", lambda *a, **k: [])  # prerequisites hold
    monkeypatch.setattr(climod, "_run_make_runner", lambda *a, **k: orchestrate.SimulatedRunner())
    # A run pauses at the first human gate after dispatching specify + clarify.
    rc = main(["--root", str(root), "run", "build X", "--no-input", "--spec-id", "PR"])
    assert rc == 3  # paused at the first human gate (AUTOX-FR-009)
    entries = Ledger(root / ".3powers" / "ledger.jsonl").entries()
    dispatched = [
        e["payload"]
        for e in entries
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "dispatch"
    ]
    stages = {d["stage"] for d in dispatched}
    assert {"specify", "clarify"} <= stages  # first-segment stages recorded
    assert all(d["integration"] == "claude" for d in dispatched)  # coder integration
    assert (
        main(["--root", str(root), "verify"]) == 0
    )  # the chain (incl. provenance) verifies offline


# --------------------------------------------------------------------------- RUNX-FR-005/006 (oracle diversity)
def test_diversity_ok_true_for_different_family(tmp_path):
    """RUNX-FR-005: a different-family oracle satisfies diversity without a deviation."""
    s = _settings_with_roles(tmp_path, _DIVERSE_ROLES)
    assert runpreflight.diversity_ok(s, entries=[], spec_id="X") is True


def test_diversity_refused_same_family_without_deviation(tmp_path):
    """RUNX-FR-006: a same-family coder/oracle without a signed deviation is not diverse."""
    same = (
        "version: 1\ndiversity_level: family\n"
        "roles:\n"
        "  coder: {model_family: openai}\n"
        "  oracle: {model_family: openai, model: openai/o1}\n"
    )
    s = _settings_with_roles(tmp_path, same)
    assert runpreflight.diversity_ok(s, entries=[], spec_id="X") is False


def test_diversity_allowed_via_signed_deviation(tmp_path):
    """RUNX-FR-006: a same-family setup proceeds under a signed, active model-diversity deviation."""
    same = (
        "version: 1\ndiversity_level: family\n"
        "roles:\n"
        "  coder: {model_family: openai}\n"
        "  oracle: {model_family: openai}\n"
    )
    s = _settings_with_roles(tmp_path, same)
    entries = [
        {"type": "deviation", "seq": 1, "spec_id": "X", "payload": {"gates": ["model_diversity"]}}
    ]
    assert runpreflight.diversity_ok(s, entries=entries, spec_id="X") is True


def test_cli_same_family_oracle_refused_at_preflight(tmp_path, monkeypatch, capsys):
    """EXEC-FR-015: a same-family resolution is refused at preflight, naming the deviation path."""
    root = tmp_path / "proj"
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    import yaml

    (root / ".3powers" / "agents" / "claude.yaml").write_text(
        yaml.safe_dump({"command": "claude", "headless": True}), encoding="utf-8"
    )
    keyfile = tmp_path / "s.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    (root / ".3powers" / "config" / "roles.yaml").write_text(
        "version: 1\ndiversity_level: family\n"
        "headless_integrations: [claude]\n"
        "roles:\n"
        "  coder: {model_family: openai, integration: claude}\n"
        "  oracle: {model_family: openai, model: openai/o1, integration: claude}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    capsys.readouterr()  # flush the keygen output
    rc = main(["--root", str(root), "run", "x", "--no-input", "--json", "--spec-id", "SF"])
    assert rc == 4
    payload = json.loads(capsys.readouterr().out)
    missing = {m["prerequisite"]: m["fix"] for m in payload["missing"]}
    assert "different-family oracle agent" in missing
    assert "deviation" in missing["different-family oracle agent"]


def test_drive_passes_runner_verdict_through_unchanged():
    """RUNX-NFR-001: dispatch is a delivery mechanism — drive never alters the runner's verdict."""
    verify_idx = next(
        i for i, (sid, _k, _s) in enumerate(orchestrate.LIFECYCLE_STEPS) if sid == "verify"
    )
    events: list = []
    result = orchestrate.drive(
        orchestrate.SimulatedRunner(verdict="fail", start_index=verify_idx), "auto", events.append
    )
    assert result.status == "failed" and result.verdict == "fail"


def test_highrisk_dispatch_policy_knob_is_intact(tmp_path):
    """RUNX-FR-008: the High-risk require-dispatch policy still reads from config — no relaxation added."""
    s = _settings_with_roles(
        tmp_path,
        "version: 1\nroles:\n  oracle: {model_family: anthropic, require_dispatch: true}\n",
    )
    assert s.oracle_require_dispatch() is True
