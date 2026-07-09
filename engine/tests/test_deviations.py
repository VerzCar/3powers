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


# --------------------------------------------------------------------------- expiry parsing (aware)
def test_parse_iso_date_only_is_timezone_aware():
    """Covers: 3PWR-FR-057 — a date-only expiry parses timezone-aware (taken as UTC), so every
    downstream comparison against now_utc() is aware-to-aware and can never raise."""
    parsed = deviations.parse_iso("2026-10-01")
    assert parsed is not None and parsed.tzinfo is not None
    assert deviations.parse_iso("not-a-date") is None  # fail-safe: never expires
    assert deviations.parse_iso(None) is None
    zulu = deviations.parse_iso("2026-10-01T00:00:00Z")
    assert zulu is not None and zulu.tzinfo is not None


def test_date_only_expiry_never_crashes_active_deviations():
    """Covers: 3PWR-FR-057 — a deviation with a date-only expires_at is active before the date and
    expired after; neither call raises a naive/aware comparison error."""
    from datetime import datetime, timezone

    entries = [_dev(0, deviations.deviation_payload(["tests"], "why", "c", "2026-10-01"))]
    before = datetime(2026, 9, 30, tzinfo=timezone.utc)
    after = datetime(2026, 10, 2, tzinfo=timezone.utc)
    assert deviations.covered_gates(deviations.active_deviations(entries, before)) == {"tests"}
    assert deviations.active_deviations(entries, after) == []


def test_date_only_cleanup_due_never_crashes_overdue_emergencies():
    """Covers: 3PWR-FR-056 — a date-only cleanup_due compares aware-to-aware; overdue after."""
    from datetime import datetime, timezone

    p = deviations.emergency_payload("x", "c", 24)
    p["cleanup_due"] = "2026-10-01"
    entries = [_dev(0, p)]
    before = datetime(2026, 9, 30, tzinfo=timezone.utc)
    after = datetime(2026, 10, 2, tzinfo=timezone.utc)
    assert deviations.overdue_emergencies(entries, before) == []
    overdue = deviations.overdue_emergencies(entries, after)
    assert len(overdue) == 1 and overdue[0]["seq"] == 0


# --------------------------------------------------------------------------- shared coverage helper
def _verdict_payload(*failed, passed=()):
    gates = [{"gate": g, "status": "fail"} for g in failed]
    gates += [{"gate": g, "status": "pass"} for g in passed]
    return {"gates": gates}


def test_uncovered_red_gates_fully_covered_is_empty():
    """Covers: 3PWR-FR-057 — every red gate covered by an active deviation → empty set."""
    entries = [_dev(0, deviations.deviation_payload(["lint", "tests"], "why", "c", None))]
    active = deviations.active_deviations(entries)
    payload = _verdict_payload("lint", "tests", passed=["types"])
    assert deviations.uncovered_red_gates(payload, active) == set()


def test_uncovered_red_gates_partially_covered_names_the_rest():
    entries = [_dev(0, deviations.deviation_payload(["lint"], "why", "c", None))]
    active = deviations.active_deviations(entries)
    payload = _verdict_payload("lint", "tests")
    assert deviations.uncovered_red_gates(payload, active) == {"tests"}


def test_uncovered_red_gates_scoped_by_spec_id():
    """A deviation scoped to another spec does NOT cover; a global one does."""
    entries = [
        _dev(0, deviations.deviation_payload(["tests"], "scoped", "c", None), spec_id="A"),
        _dev(1, deviations.deviation_payload(["lint"], "global", "c", None), spec_id=""),
    ]
    active = deviations.active_deviations(entries)
    payload = _verdict_payload("tests", "lint")
    assert deviations.uncovered_red_gates(payload, active, "A") == set()
    assert deviations.uncovered_red_gates(payload, active, "B") == {"tests"}


def test_red_gates_reads_only_failed_gates():
    payload = _verdict_payload("sast", passed=["format", "lint"])
    assert deviations.red_gates(payload) == {"sast"}
    assert deviations.red_gates({}) == set()


def test_covering_deviation_names_seq_and_respects_scope():
    """Covers: 3PWR-FR-057 — the waiver annotation's lookup: the covering deviation's seq/approver,
    scoped to the spec id (global applies)."""
    entries = [
        _dev(3, deviations.deviation_payload(["tests"], "scoped", "ann", None), spec_id="A"),
        _dev(4, deviations.deviation_payload(["lint"], "global", "bob", None), spec_id=""),
    ]
    active = deviations.active_deviations(entries)
    dev = deviations.covering_deviation("tests", active, "A")
    assert dev is not None and dev["seq"] == 3 and dev["approver"] == "ann"
    assert deviations.covering_deviation("tests", active, "B") is None  # A-scoped: no leak
    glob = deviations.covering_deviation("lint", active, "B")
    assert glob is not None and glob["seq"] == 4
    assert deviations.covering_deviation("sast", active) is None


# --------------------------------------------------------------------------- run-path proceed decision
def test_run_proceeds_past_verify_when_every_red_gate_is_covered():
    """Covers: 3PWR-FR-057 — a red Verify fully covered by an active signed deviation lets the run
    proceed, surfacing the applied deviation seq per gate; the recorded verdict stays red."""
    from threepowers.cli.run import _deviation_proceed_notices

    entries = [_dev(2, deviations.deviation_payload(["lint", "tests"], "why", "c", None))]
    payload = _verdict_payload("lint", "tests")
    notices = _deviation_proceed_notices(payload, entries, "A")
    assert notices == [
        "proceeding past lint under deviation seq=2",
        "proceeding past tests under deviation seq=2",
    ]


def test_run_stops_at_gate_red_when_any_red_gate_is_uncovered():
    """Covers: 3PWR-FR-057 — a partially covered red Verify stops the run (None = stop), exactly
    as an un-deviated red does today."""
    from threepowers.cli.run import _deviation_proceed_notices

    entries = [_dev(2, deviations.deviation_payload(["lint"], "why", "c", None))]
    assert _deviation_proceed_notices(_verdict_payload("lint", "tests"), entries, "A") is None
    # a deviation scoped to another spec does not cover this run's gates
    scoped = [_dev(2, deviations.deviation_payload(["lint"], "why", "c", None), spec_id="OTHER")]
    assert _deviation_proceed_notices(_verdict_payload("lint"), scoped, "A") is None
    # a green (or gate-less) verdict never consults deviations
    assert _deviation_proceed_notices(_verdict_payload(passed=["lint"]), entries, "A") is None
