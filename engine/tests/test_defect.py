"""Defect-flow gate (3PWR-FR-008): a defect fix must ship a failing regression test.

Detection is deterministic and language-agnostic (no model call, 3PWR-NFR-001) and only shapes the
suite when work-kind inference tags a change ``defect`` (3PWR-FR-058) — it never weakens a tier gate."""

from __future__ import annotations

from pathlib import Path

from threepowers.config import Settings
from threepowers.conformance import has_regression_test, regression_gate
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_PASS

SPEC = "**Spec ID**: ZED\n\n- **ZED-FR-001**: shall.\n"


def _spec(tmp_path: Path) -> Path:
    p = tmp_path / "spec.md"
    p.write_text(SPEC, encoding="utf-8")
    return p


def test_has_regression_test_detects_named_file_referencing_a_requirement(tmp_path):
    """3PWR-FR-008: a *reproduce*/*regression* test that references the defect's requirement counts."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_regression_zed.py").write_text("# reproduces ZED-FR-001\n", encoding="utf-8")
    present, refs = has_regression_test([tests], "ZED")
    assert present and refs == ["ZED-FR-001"]


def test_regression_test_must_reference_a_requirement(tmp_path):
    """A regression-named test with no requirement id isn't traceable to the defect → not counted."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_regression_misc.py").write_text("# a regression, no id\n", encoding="utf-8")
    present, refs = has_regression_test([tests], "ZED")
    assert not present and refs == []


def test_plain_test_is_not_a_regression_test(tmp_path):
    """A test that references the requirement but isn't marked as a regression doesn't satisfy FR-008."""
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_feature.py").write_text("# covers ZED-FR-001\n", encoding="utf-8")
    present, _ = has_regression_test([tests], "ZED")
    assert not present


def test_regression_gate_fails_then_passes(tmp_path):
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_feature.py").write_text("# covers ZED-FR-001\n", encoding="utf-8")
    fail = regression_gate(_spec(tmp_path), [tests])
    assert fail.status == STATUS_FAIL and fail.findings
    (tests / "test_reproduce_bug.py").write_text("# reproduce ZED-FR-001\n", encoding="utf-8")
    ok = regression_gate(_spec(tmp_path), [tests])
    assert ok.status == STATUS_PASS and ok.details["regression_refs"] == ["ZED-FR-001"]


def _project(tmp_path: Path, *, regression: bool) -> tuple[Settings, Path]:
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(
        "tiers:\n  T: { diff_coverage: 0, gates: [spec_conformance] }\n", encoding="utf-8"
    )
    (tp / "adapters" / "a" / "adapter.yaml").write_text(
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\ngates: {}\n', encoding="utf-8"
    )
    proj = tmp_path / "p"
    (proj / "tests").mkdir(parents=True)
    (proj / "d").write_text("")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "t.test.py").write_text("# covers ZED-FR-001\n", encoding="utf-8")
    if regression:
        (proj / "tests" / "test_regression.py").write_text(
            "# regression ZED-FR-001\n", encoding="utf-8"
        )
    return Settings(root=tmp_path), proj


def test_defect_run_requires_a_regression_test(tmp_path):
    """3PWR-FR-008: work_kind=defect adds the regression gate; without one the verdict is red."""
    s, proj = _project(tmp_path, regression=False)
    v = run_gates(
        s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", work_kind=["defect"]
    )
    assert v.result == STATUS_FAIL
    assert any(f["class"] == "missing_regression_test" for f in v.failures)
    assert v.work_kind == ["defect"]


def test_defect_run_passes_with_a_regression_test(tmp_path):
    s, proj = _project(tmp_path, regression=True)
    v = run_gates(
        s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", work_kind=["defect"]
    )
    assert v.result == STATUS_PASS
    assert any(g.gate == "defect_regression" and g.status == STATUS_PASS for g in v.gates)


def test_non_defect_run_has_no_regression_gate(tmp_path):
    """Work-kind shaping only triggers for the inferred kind — a normal run is unchanged (3PWR-FR-032)."""
    s, proj = _project(tmp_path, regression=False)
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    assert not any(g.gate == "defect_regression" for g in v.gates)
    assert v.result == STATUS_PASS
