"""Gate orchestration branches (3PWR-FR-026/034): a red gate fails the verdict; mutation is opt-in."""

from __future__ import annotations

from threepowers import gates as gates_mod
from threepowers.config import Settings
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_SKIP, GateResult

RISK = "tiers:\n  T: { diff_coverage: 0, gates: [format, mutation, spec_conformance] }\n"


def _project(tmp_path, gates_yaml):
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK, encoding="utf-8")
    (tp / "adapters" / "a" / "adapter.yaml").write_text(
        f'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\ngates:\n{gates_yaml}\n',
        encoding="utf-8",
    )
    proj = tmp_path / "p"
    (proj / "tests").mkdir(parents=True)
    (proj / "d").write_text("")
    (proj / "spec.md").write_text(
        "**Spec ID**: ZED\n\n- **ZED-FR-001**: shall.\n", encoding="utf-8"
    )
    (proj / "tests" / "t.test.py").write_text("# covers ZED-FR-001\n", encoding="utf-8")
    return Settings(root=tmp_path), proj


def test_failing_gate_yields_fail_and_actionable(tmp_path):
    s, proj = _project(tmp_path, '  format: { cmd: "definitely-not-a-real-tool-xyz", parser: x }')
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    assert v.result == STATUS_FAIL
    assert any(f["class"] == "gate_failed" for f in v.failures)


def test_mutation_skipped_when_not_allowed(tmp_path):
    s, proj = _project(
        tmp_path,
        '  format: { cmd: "python -c pass", parser: x }\n'
        '  mutation: { cmd: "python -c pass", parser: m }',
    )
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    mutation = next(g for g in v.gates if g.gate == "mutation")
    assert mutation.status == STATUS_SKIP


def test_mutation_enforced_when_allowed_fails_with_surviving_mutant(tmp_path, monkeypatch):
    """A red mutation gate fails the verdict and names a surviving_mutant (3PWR-FR-031/034)."""
    s, proj = _project(
        tmp_path,
        '  format: { cmd: "python -c pass", parser: x }\n'
        '  mutation: { cmd: "python -c pass", parser: mutmut }',
    )
    monkeypatch.setattr(
        gates_mod.mutation,
        "mutation_gate",
        lambda *a, **k: GateResult(
            gate="mutation",
            status=STATUS_FAIL,
            tool="mutmut",
            details={"mutation_score": 50.0, "threshold": 70, "survived": 3},
        ),
    )
    v = run_gates(
        s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", allow_mutation=True
    )
    assert v.result == STATUS_FAIL
    assert any(f["class"] == "surviving_mutant" for f in v.failures)


def test_report_only_run_is_flagged_on_the_verdict(tmp_path):
    s, proj = _project(tmp_path, '  format: { cmd: "python -c pass", parser: x }')
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", report_only=True)
    assert v.report_only is True
