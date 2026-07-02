"""Design oracles (3PWR-FR-009): design work is judged by adapter-supplied oracles.

A selected oracle the adapter doesn't declare — or whose tool is absent — is QUARANTINED (skip +
surfaced finding), never silently passed (3PWR-NFR-015). The catalog is language-agnostic; the tools
are adapter-supplied (3PWR-NFR-007). Live playwright/axe/schema-diff runs are the residual."""

from __future__ import annotations

from pathlib import Path

from threepowers import design
from threepowers.config import Settings
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP

SPEC = "**Spec ID**: ZED\n\n- **ZED-FR-001**: shall.\n"


def test_selected_gates_default_catalog_covers_all_dimensions(tmp_path):
    """No design-oracles.yaml → the built-in default surfaces every oracle (never silently escapes)."""
    s = Settings(root=tmp_path)
    assert set(design.selected_gates(s)) == set(design.DESIGN_GATES)


def test_selected_gates_from_catalog(tmp_path):
    cfg = tmp_path / ".3powers" / "config"
    cfg.mkdir(parents=True)
    (cfg / "design-oracles.yaml").write_text(
        "oracles:\n  accessibility: { gate: a11y_scan }\n", encoding="utf-8"
    )
    assert design.selected_gates(Settings(root=tmp_path)) == ["a11y_scan"]


def test_load_oracles_falls_back_when_catalog_declares_none(tmp_path):
    """A present-but-oracle-less catalog still surfaces every dimension (never silently escapes)."""
    cfg = tmp_path / ".3powers" / "config"
    cfg.mkdir(parents=True)
    (cfg / "design-oracles.yaml").write_text("version: 1\n", encoding="utf-8")
    assert set(design.load_oracles(Settings(root=tmp_path))) == set(design._DEFAULT_ORACLES)


def test_design_gate_quarantines_when_adapter_undeclared(tmp_path):
    g = design.design_gate("visual_regression", {"gates": {}}, "web", tmp_path)
    assert g.status == STATUS_SKIP and "quarantined" in g.findings[0]


def test_design_gate_quarantines_when_tool_absent(tmp_path):
    manifest = {"gates": {"a11y_scan": {"cmd": "this-tool-does-not-exist-xyz", "parser": "axe"}}}
    g = design.design_gate("a11y_scan", manifest, "web", tmp_path)
    assert g.status == STATUS_SKIP and "not installed" in g.findings[0]


def test_design_gate_quarantines_when_command_missing(tmp_path):
    """A declared-but-command-less oracle is quarantined, not silently passed (3PWR-NFR-015)."""
    g = design.design_gate(
        "a11y_scan", {"gates": {"a11y_scan": {"parser": "axe"}}}, "web", tmp_path
    )
    assert g.status == STATUS_SKIP and "no command" in g.findings[0]


def test_design_gate_passes_and_fails_on_exit_code(tmp_path):
    ok = design.design_gate(
        "contract_check", {"gates": {"contract_check": {"cmd": "python -c pass"}}}, "web", tmp_path
    )
    assert ok.status == STATUS_PASS
    bad = design.design_gate(
        "visual_regression",
        {"gates": {"visual_regression": {"cmd": 'python -c "import sys; sys.exit(1)"'}}},
        "web",
        tmp_path,
    )
    assert bad.status == STATUS_FAIL


def _project(tmp_path: Path, adapter_gates: str, catalog: str) -> tuple[Settings, Path]:
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "web").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(
        "tiers:\n  T: { diff_coverage: 0, gates: [spec_conformance] }\n", encoding="utf-8"
    )
    (tp / "config" / "design-oracles.yaml").write_text(catalog, encoding="utf-8")
    (tp / "adapters" / "web" / "adapter.yaml").write_text(
        f'language: web\ndetect: ["d"]\ntest_roots: ["tests"]\n{adapter_gates}\n', encoding="utf-8"
    )
    proj = tmp_path / "p"
    (proj / "tests").mkdir(parents=True)
    (proj / "d").write_text("")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "t.test.py").write_text("# covers ZED-FR-001\n", encoding="utf-8")
    return Settings(root=tmp_path), proj


def test_design_run_selects_declared_oracle_and_quarantines_the_rest(tmp_path):
    """3PWR-FR-009: a design run runs the oracle the adapter supplies; a missing one is quarantined."""
    s, proj = _project(
        tmp_path,
        adapter_gates="gates:\n  a11y_scan: { cmd: 'python -c pass', parser: axe }",
        catalog=(
            "oracles:\n"
            "  accessibility: { gate: a11y_scan }\n"
            "  visual_regression: { gate: visual_regression }\n"
        ),
    )
    v = run_gates(
        s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="web", work_kind=["design"]
    )
    a11y = next(g for g in v.gates if g.gate == "a11y_scan")
    visual = next(g for g in v.gates if g.gate == "visual_regression")
    assert a11y.status == STATUS_PASS
    assert visual.status == STATUS_SKIP  # quarantined — adapter declares no visual_regression
    assert v.result == STATUS_PASS  # a quarantine (skip) never fails the verdict
    assert v.work_kind == ["design"]


def test_design_oracle_failure_is_actionable(tmp_path):
    """A failing design oracle fails the verdict with its own class (3PWR-FR-034)."""
    s, proj = _project(
        tmp_path,
        adapter_gates=(
            "gates:\n"
            "  visual_regression:\n"
            "    cmd: 'python -c \"import sys; sys.exit(1)\"'\n"
            "    parser: playwright\n"
        ),
        catalog="oracles:\n  visual_regression: { gate: visual_regression }\n",
    )
    v = run_gates(
        s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="web", work_kind=["design"]
    )
    assert v.result == STATUS_FAIL
    assert any(f["class"] == "visual_regression" for f in v.failures)
