"""Tier-required test layers, enforced by the spec-conformance gate (3PWR-FR-064 / 3PWR-FR-065).

A per-change union: the change's tests must cover the tier's required layers (not every requirement in
every layer)."""

from __future__ import annotations

from pathlib import Path

from threepowers.conformance import run_conformance

SPEC = "**Spec ID**: LAY\n\n- **LAY-FR-001**: The system shall work.\n"


def _spec(tmp_path: Path) -> Path:
    p = tmp_path / "spec.md"
    p.write_text(SPEC, encoding="utf-8")
    return p


def _mk_test(dirpath: Path, rid: str = "LAY-FR-001") -> None:
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "test_layer.py").write_text(f"# covers {rid}\n", encoding="utf-8")


def test_layers_none_required_is_backward_compatible(tmp_path):
    """required_layers=None (a tier that doesn't set it) behaves exactly as before."""
    _mk_test(tmp_path / "tests")
    gate = run_conformance(_spec(tmp_path), [tmp_path / "tests"])
    assert gate.status == "pass"


def test_high_risk_missing_layers_fails(tmp_path):
    """3PWR-FR-064: only a unit test present, but the tier requires integration + e2e → FAIL."""
    _mk_test(tmp_path / "tests")  # a plain test file → 'unit' layer by default
    gate = run_conformance(
        _spec(tmp_path), [tmp_path / "tests"], required_layers=["unit", "integration", "e2e"]
    )
    assert gate.status == "fail"
    assert gate.details["missing_layers"] == ["integration", "e2e"]
    assert any("integration" in f and "e2e" in f for f in gate.findings)


def test_all_layers_present_passes(tmp_path):
    """3PWR-FR-064: with unit + integration + e2e tests for the change, the layer check passes."""
    _mk_test(tmp_path / "tests" / "unit")
    _mk_test(tmp_path / "tests" / "integration")
    _mk_test(tmp_path / "tests" / "e2e")
    gate = run_conformance(
        _spec(tmp_path), [tmp_path / "tests"], required_layers=["unit", "integration", "e2e"]
    )
    assert gate.status == "pass" and gate.details["missing_layers"] == []
    assert set(gate.details["covered_layers"]) == {"unit", "integration", "e2e"}


def test_untested_requirement_does_not_add_spurious_layer_failure(tmp_path):
    """With no tests at all, the untested-requirement failure covers it — no double layer failure."""
    gate = run_conformance(_spec(tmp_path), [tmp_path / "tests"], required_layers=["unit"])
    assert gate.status == "fail"
    assert gate.details["untested_requirements"] == ["LAY-FR-001"]
    assert gate.details["missing_layers"] == []  # no tests → not a layer failure
