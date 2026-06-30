"""Two-way requirement<->task coverage (3PWR-FR-015)."""

from __future__ import annotations

from threepowers.conformance import two_way_coverage
from threepowers.verdict import STATUS_FAIL, STATUS_PASS

SPEC = "**Spec ID**: VUTIL\n\n- **VUTIL-FR-001**: a\n- **VUTIL-FR-002**: b\n"


def _spec(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text(SPEC, encoding="utf-8")
    return p


def test_full_two_way_coverage_passes(tmp_path):
    tasks = tmp_path / "tasks.md"
    tasks.write_text(
        "- [ ] T001 [VUTIL-FR-001] implement a\n- [ ] T002 [VUTIL-FR-002] implement b\n",
        encoding="utf-8",
    )
    assert two_way_coverage(_spec(tmp_path), tasks).status == STATUS_PASS


def test_requirement_without_task_fails(tmp_path):
    tasks = tmp_path / "tasks.md"
    tasks.write_text("- [ ] T001 [VUTIL-FR-001] implement a\n", encoding="utf-8")
    gate = two_way_coverage(_spec(tmp_path), tasks)
    assert gate.status == STATUS_FAIL
    assert "VUTIL-FR-002" in gate.details["requirements_without_task"]


def test_task_without_requirement_fails(tmp_path):
    tasks = tmp_path / "tasks.md"
    tasks.write_text(
        "- [ ] T001 [VUTIL-FR-001] a\n- [ ] T002 orphan with no req\n- [ ] T003 [VUTIL-FR-002] b\n",
        encoding="utf-8",
    )
    gate = two_way_coverage(_spec(tmp_path), tasks)
    assert gate.status == STATUS_FAIL
    assert gate.details["tasks_without_requirement"]
