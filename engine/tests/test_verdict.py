"""Verdict tests (3PWR-FR-033/034) and canonical determinism (3PWR-NFR-001)."""

from __future__ import annotations

import json

from threepowers import SCHEMA_VERSION
from threepowers.canonical import canonical_bytes
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, GateResult, Verdict, failure


def test_finalize_orders_cheapest_first_and_aggregates_result():
    v = Verdict(spec_id="X", tier="Standard", adapter="py")
    v.add(GateResult(gate="spec_conformance", status=STATUS_PASS))
    v.add(GateResult(gate="format", status=STATUS_PASS))
    v.add(GateResult(gate="tests", status=STATUS_FAIL))
    v.finalize()
    assert v.gates[0].gate == "format"  # reordered (3PWR-FR-026)
    assert v.result == STATUS_FAIL  # any fail => overall fail


def test_failure_record_is_actionable():
    f = failure("untested_requirement", requirement_id="X-FR-001")
    assert f["class"] == "untested_requirement" and f["requirement_id"] == "X-FR-001"


def test_write_and_requirement_ids(tmp_path):
    v = Verdict(spec_id="X", tier="Standard", adapter="py")
    v.add(
        GateResult(
            gate="spec_conformance",
            status=STATUS_PASS,
            details={"requirement_ids": ["X-FR-001", "X-FR-002"]},
        )
    )
    v.finalize()
    p = tmp_path / "v.json"
    v.write(p)
    written = json.loads(p.read_text())
    assert written["spec_id"] == "X" and written["schema_version"] == SCHEMA_VERSION
    assert written["report_only"] is False  # advisory flag defaults off (3PWR-FR-052)
    assert v.requirement_ids() == ["X-FR-001", "X-FR-002"]


def test_canonical_determinism():
    # 3PWR-NFR-001: equal content => byte-identical encoding regardless of key order.
    assert canonical_bytes({"b": 1, "a": 2}) == canonical_bytes({"a": 2, "b": 1})
