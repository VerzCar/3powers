"""Opt-in diff-scoped mutation at a configured tier (HARDN-FR-011) — integration layer.

Drives ``run_gates`` over a fixture repo whose Standard tier sets ``diff_mutation: true``:
with a base given, mutation runs scoped to the changed source files and grades against the
tier's ``mutation_score``; with the knob unset, behavior is unchanged; a missing mutation
tool quarantines, never silently passes (3PWR-NFR-015).
"""

from __future__ import annotations

import subprocess

import pytest

from threepowers.config import Settings
from threepowers.gates import run_gates

RISK_TIERS_ON = """
tiers:
  Standard:
    diff_coverage: 0
    mutation_score: 60
    diff_mutation: true
    gates: [format]
"""
RISK_TIERS_OFF = """
tiers:
  Standard:
    diff_coverage: 0
    mutation_score: 60
    gates: [format]
"""
ADAPTER = """
language: fake
detect: ["detect.txt"]
test_roots: ["tests"]
gates:
  format: { check_cmd: "python -c pass", parser: fake }
  mutation:
    cmd: "python -c pass"
    score_cmd: "python -c \\"print('m.thing.f__mutmut_1: killed'); print('m.thing.f__mutmut_2: survived')\\""
    parser: mutmut
"""
ADAPTER_NO_TOOL = ADAPTER.replace(
    'cmd: "python -c pass"\n', 'cmd: "no-such-mutation-tool-xyz"\n', 1
)
SPEC = "**Spec ID**: DMUT\n\n- **DMUT-FR-001**: The system shall work.\n"


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "repo"
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "fake").mkdir(parents=True)
    (tp / "adapters" / "fake" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")
    proj = root / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "detect.txt").write_text("x", encoding="utf-8")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    # The change under judgment: one new source file.
    (proj / "src" / "thing.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return root, proj


def _run(root, proj, tiers, base):
    (root / ".3powers" / "config" / "risk-tiers.yaml").write_text(tiers, encoding="utf-8")
    return run_gates(
        Settings(root=root),
        proj,
        tier="Standard",
        spec_path=proj / "spec.md",
        adapter_name="fake",
        base=base,
    )


def test_diff_mutation_runs_scoped_and_grades_against_the_tier_threshold(project):
    """HARDN-FR-011 + SC-006: knob on + --base → mutation over the diff, graded vs 60%."""
    root, proj = project
    verdict = _run(root, proj, RISK_TIERS_ON, "HEAD")
    mut = next(g for g in verdict.gates if g.gate == "mutation")
    assert mut.status == "fail"  # 1 of 2 killed = 50% < 60%
    assert mut.details["mutation_score"] == 50.0
    assert mut.details["threshold"] == 60.0
    assert verdict.result == "fail"


def test_knob_unset_leaves_standard_tier_unchanged(project):
    """HARDN-FR-011: without diff_mutation the Standard tier never runs mutation."""
    root, proj = project
    verdict = _run(root, proj, RISK_TIERS_OFF, "HEAD")
    assert not any(g.gate == "mutation" for g in verdict.gates)
    assert verdict.result == "pass"


def test_no_base_means_no_diff_mutation(project):
    """HARDN-FR-011: the knob alone does nothing — the trigger is knob AND --base."""
    root, proj = project
    verdict = _run(root, proj, RISK_TIERS_ON, None)
    assert not any(g.gate == "mutation" for g in verdict.gates)


def test_missing_mutation_tool_quarantines_never_silently_passes(project):
    """HARDN-FR-011 + 3PWR-NFR-015: a missing tool is a visible quarantine, not a pass."""
    root, proj = project
    (root / ".3powers" / "adapters" / "fake" / "adapter.yaml").write_text(
        ADAPTER_NO_TOOL, encoding="utf-8"
    )
    verdict = _run(root, proj, RISK_TIERS_ON, "HEAD")
    mut = next(g for g in verdict.gates if g.gate == "mutation")
    assert mut.status == "skip"
    assert any("quarantined" in f for f in mut.findings)


def test_no_changed_source_files_is_a_visible_skip(project):
    """HARDN-FR-011: nothing mutatable in the diff → an explicit skip, not an empty run."""
    root, proj = project
    (proj / "src" / "thing.py").unlink()
    (proj / "notes.md").write_text("docs only\n", encoding="utf-8")
    verdict = _run(root, proj, RISK_TIERS_ON, "HEAD")
    mut = next(g for g in verdict.gates if g.gate == "mutation")
    assert mut.status == "skip"
    assert any("no changed source files" in f for f in mut.findings)
