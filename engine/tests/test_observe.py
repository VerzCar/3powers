"""Observe & feedback loop (3PWR-FR-054/055, §13).

Pure routing/coverage logic is pinned directly; the `observe` CLI (signal → new intent, NFR coverage,
and the tamper-evident agent-action log) is driven end to end through `3pwr`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import lifecycle, observe
from threepowers.cli import main


# --------------------------------------------------------------------------- pure logic
def _write_spec(p: Path) -> Path:
    p.write_text(
        "**Spec ID**: OBS\n\n"
        "- **OBS-NFR-001**: The system shall respond within 200ms.\n"
        "- **OBS-NFR-002**: The system shall stay available 99.9%.\n"
        "- **OBS-FR-001**: The system shall work.\n",
        encoding="utf-8",
    )
    return p


def test_route_to_backlog_creates_new_intent(tmp_path):
    """3PWR-FR-054: a signal becomes a NEW requirement in the backlog, routed to /speckit.specify."""
    backlog = tmp_path / "feedback" / "OBS.md"
    fb1 = observe.route_to_backlog(backlog, "OBS", "incident", "OBS-NFR-001", "500s under load")
    fb2 = observe.route_to_backlog(backlog, "OBS", "usage", "", "users paste huge inputs")
    assert fb1 == "OBS-FB-001" and fb2 == "OBS-FB-002"  # ids increment
    text = backlog.read_text(encoding="utf-8")
    assert "OBS-FB-001" in text and "OBS-FB-002" in text
    assert "/speckit.specify" in text and "not an in-place patch" in text
    assert "(re: OBS-NFR-001)" in text  # the NFR reference is carried


def test_spec_nfrs_and_coverage(tmp_path):
    """3PWR-FR-054 (§13 acceptance): NFR-instrumentation coverage over a spec."""
    spec = _write_spec(tmp_path / "spec.md")
    spec_id, nfrs = observe.spec_nfrs(spec)
    assert spec_id == "OBS" and nfrs == {"OBS-NFR-001", "OBS-NFR-002"}

    partial = observe.nfr_coverage(
        spec, {"checks": [{"nfr": "OBS-NFR-001", "check": "latency SLO"}]}
    )
    assert partial.instrumented == ["OBS-NFR-001"]
    assert partial.missing == ["OBS-NFR-002"] and partial.ok is False

    full = observe.nfr_coverage(spec, {"checks": [{"nfr": "OBS-NFR-001"}, {"nfr": "OBS-NFR-002"}]})
    assert full.ok is True and full.missing == []


def test_observe_entry_moves_spec_to_observe_stage():
    """3PWR-FR-054: a recorded production signal advances the spec to the Observe stage."""
    entries = [
        {"seq": 0, "type": "verdict", "spec_id": "OBS", "payload": {"result": "pass"}},
        {"seq": 1, "type": "observe", "spec_id": "OBS", "payload": {"kind": "incident"}},
    ]
    assert lifecycle.derive(entries)["OBS"].stage == "Observe"


# --------------------------------------------------------------------------- CLI
@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path
    (root / ".3powers" / "config").mkdir(parents=True)
    # observability registry covers OBS-NFR-001 but not OBS-NFR-002 (a visible gap).
    (root / ".3powers" / "config" / "observability.yaml").write_text(
        "checks:\n  - nfr: OBS-NFR-001\n    check: latency SLO\n", encoding="utf-8"
    )
    proj = root / "proj"
    proj.mkdir()
    _write_spec(proj / "spec.md")
    keyfile = root / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root, proj


def test_observe_signal_routes_new_intent_and_sets_stage(project, capsys):
    """3PWR-FR-054: `observe signal` records + routes to the backlog, and the spec reaches Observe."""
    root, proj = project
    rc = main(
        [
            "--root",
            str(root),
            "observe",
            "signal",
            "--spec-id",
            "OBS",
            "--kind",
            "incident",
            "--nfr",
            "OBS-NFR-001",
            "--note",
            "500s on /checkout",
        ]
    )
    assert rc == 0
    backlog = root / ".3powers" / "feedback" / "OBS.md"
    assert backlog.exists() and "OBS-FB-001" in backlog.read_text(encoding="utf-8")
    assert main(["--root", str(root), "verify"]) == 0  # the observe entry is signed + chained
    capsys.readouterr()
    assert main(["--root", str(root), "status", "--spec-id", "OBS"]) == 0
    assert "Observe" in capsys.readouterr().out


def test_observe_signal_rejects_bad_kind_and_missing_note(project):
    root, _ = project
    assert (
        main(
            [
                "--root",
                str(root),
                "observe",
                "signal",
                "--spec-id",
                "OBS",
                "--kind",
                "bogus",
                "--note",
                "x",
            ]
        )
        == 2
    )
    assert (
        main(["--root", str(root), "observe", "signal", "--spec-id", "OBS", "--kind", "usage"]) == 2
    )


def test_observe_coverage_flags_uninstrumented_nfr(project):
    """3PWR-FR-054: coverage fails when a declared NFR has no live check registered."""
    root, proj = project
    assert main(["--root", str(root), "observe", "coverage", "--spec", str(proj / "spec.md")]) == 1
    # a registry covering both NFRs passes
    full = root / "full.yaml"
    full.write_text("checks:\n  - nfr: OBS-NFR-001\n  - nfr: OBS-NFR-002\n", encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(root),
                "observe",
                "coverage",
                "--spec",
                str(proj / "spec.md"),
                "--registry",
                str(full),
            ]
        )
        == 0
    )


def test_agent_action_log_is_tamper_evident(project):
    """3PWR-FR-055: runtime agent actions are attributable + tamper-evident (a separate signed chain)."""
    root, _ = project
    assert (
        main(
            [
                "--root",
                str(root),
                "observe",
                "log-action",
                "--agent",
                "agent-x",
                "--action",
                "purged cache",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "--root",
                str(root),
                "observe",
                "log-action",
                "--agent",
                "agent-y",
                "--action",
                "scaled up",
            ]
        )
        == 0
    )
    assert main(["--root", str(root), "observe", "verify-actions"]) == 0
    actions = root / ".3powers" / "runtime" / "actions.jsonl"
    actions.write_text(
        actions.read_text(encoding="utf-8").replace("agent-x", "impostor"), encoding="utf-8"
    )
    assert main(["--root", str(root), "observe", "verify-actions"]) == 1  # tamper caught


def test_verify_actions_empty_log_ok(project):
    """An empty/absent runtime log trivially verifies (no actions yet)."""
    root, _ = project
    assert main(["--root", str(root), "observe", "verify-actions"]) == 0
