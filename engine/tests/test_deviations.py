"""Emergency & deviation logic (3PWR-FR-056/057): active/expired/revoked + emergency profile.

These pin the pure enforcement-boundary logic; the CLI wiring is exercised in test_cli.py.
"""

from __future__ import annotations

from datetime import timedelta

from threepowers import deviations
from threepowers.deviations import now_utc


def _dev(seq, payload, spec_id=""):
    return {"seq": seq, "type": "deviation", "spec_id": spec_id, "payload": payload}


def test_active_deviation_is_listed():
    entries = [_dev(0, deviations.deviation_payload(["mutation"], "why", "carlo", None))]
    active = deviations.active_deviations(entries)
    assert len(active) == 1
    assert deviations.covered_gates(active) == {"mutation"}


def test_revoked_deviation_is_inactive():
    """A later revoke entry ends the deviation — the way back (3PWR-FR-057)."""
    entries = [
        _dev(0, deviations.deviation_payload(["sast"], "why", "carlo", None)),
        _dev(1, {"revokes": 0, "reason": "cleaned up"}),
    ]
    assert deviations.active_deviations(entries) == []
    assert deviations.covered_gates(deviations.active_deviations(entries)) == set()


def test_expired_deviation_is_inactive():
    past = deviations.iso(now_utc() - timedelta(hours=1))
    future = deviations.iso(now_utc() + timedelta(hours=1))
    entries = [
        _dev(0, deviations.deviation_payload(["lint"], "old", "carlo", past)),
        _dev(1, deviations.deviation_payload(["types"], "live", "carlo", future)),
    ]
    assert deviations.covered_gates(deviations.active_deviations(entries)) == {"types"}


def test_covered_gates_scoping():
    """A spec-scoped deviation does not leak to another spec; global applies to all."""
    entries = [
        _dev(0, deviations.deviation_payload(["tests"], "scoped", "c", None), spec_id="A"),
        _dev(1, deviations.deviation_payload(["lint"], "global", "c", None), spec_id=""),
    ]
    active = deviations.active_deviations(entries)
    assert deviations.covered_gates(active, "A") == {"tests", "lint"}
    assert deviations.covered_gates(active, "B") == {"lint"}  # the A-scoped one does not apply


def test_emergency_payload_defers_only_mutation_and_coverage():
    """The emergency profile may defer only mutation + coverage, never security/secret (FR-056)."""
    p = deviations.emergency_payload("prod down", "carlo", 24)
    assert set(p["gates"]) == set(deviations.EMERGENCY_DEFERRABLE)
    assert not set(p["gates"]) & set(deviations.EMERGENCY_FORBIDDEN)
    assert p["emergency"] is True and p["cleanup_due"]


def test_overdue_emergency_detected():
    p_due = deviations.emergency_payload("x", "c", 24)
    p_due["cleanup_due"] = deviations.iso(now_utc() - timedelta(minutes=1))  # already past
    p_ok = deviations.emergency_payload("y", "c", 24)  # +24h, not overdue
    entries = [_dev(0, p_due), _dev(1, p_ok)]
    overdue = deviations.overdue_emergencies(entries)
    assert len(overdue) == 1 and overdue[0]["seq"] == 0


def test_revoked_emergency_is_not_overdue():
    p_due = deviations.emergency_payload("x", "c", 24)
    p_due["cleanup_due"] = deviations.iso(now_utc() - timedelta(minutes=1))
    entries = [_dev(0, p_due), _dev(1, {"revokes": 0})]
    assert deviations.overdue_emergencies(entries) == []
