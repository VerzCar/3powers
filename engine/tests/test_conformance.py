"""Spec-conformance tests (3PWR-FR-030/034): untested requirements must be flagged."""

from __future__ import annotations

from threepowers.conformance import extract_spec, referenced_ids, run_conformance
from threepowers.verdict import STATUS_FAIL, STATUS_PASS

SPEC = """# Feature Specification: Validation Utils

**Spec ID**: VUTIL

### Functional Requirements
- **VUTIL-FR-001**: The system shall reject an empty string.
- **VUTIL-FR-002**: The system shall accept a valid email.
"""


def _write_spec(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(SPEC, encoding="utf-8")
    return p


def test_extract_spec_id_and_requirements(tmp_path):
    spec_id, ids = extract_spec(_write_spec(tmp_path))
    assert spec_id == "VUTIL"
    assert ids == {"VUTIL-FR-001", "VUTIL-FR-002"}


def test_all_requirements_tested_passes(tmp_path):
    spec = _write_spec(tmp_path)
    tests = tmp_path / "tests" / "unit"
    tests.mkdir(parents=True)
    (tests / "validate.test.ts").write_text(
        'describe("VUTIL-FR-001: empty", () => {});\n'
        'describe("VUTIL-FR-002: email", () => {});\n',
        encoding="utf-8",
    )
    gate = run_conformance(spec, [tmp_path / "tests"])
    assert gate.status == STATUS_PASS
    assert gate.details["untested_requirements"] == []


def test_untested_requirement_is_flagged(tmp_path):
    spec = _write_spec(tmp_path)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "validate.test.ts").write_text('it("VUTIL-FR-001 ok", () => {});\n', encoding="utf-8")
    gate = run_conformance(spec, [tests])
    assert gate.status == STATUS_FAIL
    assert gate.details["untested_requirements"] == ["VUTIL-FR-002"]


def test_layers_are_recorded(tmp_path):
    spec = _write_spec(tmp_path)
    for layer in ("unit", "integration", "e2e"):
        d = tmp_path / "tests" / layer
        d.mkdir(parents=True)
        (d / f"v.{layer}.test.ts").write_text('it("VUTIL-FR-001", ()=>{});', encoding="utf-8")
    refs = referenced_ids([tmp_path / "tests"], "VUTIL")
    assert refs["VUTIL-FR-001"] == {"unit", "integration", "e2e"}
