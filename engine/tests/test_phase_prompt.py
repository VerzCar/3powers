"""The phase orchestration prompt contract and advisory stall detection (PHASEPR, spec 025).

Exercises the PHASE INSTRUCTION prompt rendered for each phased-implement session — the scope
contract (PHASEPR-FR-001), the ``[P]`` subagent-concurrency instruction (PHASEPR-FR-002), the
``[x]``/``[!]`` completion-marker and no-questions contract (PHASEPR-FR-003), the completed-phases
summary (PHASEPR-FR-004) — plus the pure unanswered-question predicate and the transcript tail
reader behind the advisory stall warning (PHASEPR-FR-005), and the determinism/advisory NFRs
(PHASEPR-NFR-001/002). Everything here is offline and deterministic: no model call, no network.
The run-level proof that the warning never alters control flow lives with the phased end-to-end
fixture in ``test_phases.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import threepowers
from threepowers import phases, transcripts

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DIR = Path(threepowers.__file__).resolve().parent

_TASKS_3PHASE = """# Tasks: demo

## Phase 1: core

**File scope**: src/core.py
**Depends on**: none

- [ ] T001 [X-FR-001] build core (files: src/core.py)

## Phase 2: alpha [P]

**File scope**: src/alpha.py
**Depends on**: none

- [ ] T002 [X-FR-002] alpha (files: src/alpha.py)

## Phase 3: beta [P]

**File scope**: src/beta.py
**Depends on**: none

- [ ] T003 [X-FR-003] beta (files: src/beta.py)
"""


def _prompt_for(index: int) -> str:
    lst = phases.parse_phases(_TASKS_3PHASE)
    ph = lst[index - 1]
    return phases.handoff_context(
        ph,
        len(lst),
        constitution_text="RULES HERE",
        spec_id="030",
        completed_summary=phases.completed_phases_summary(lst, ph.index),
    )


# --------------------------------------------------------------------------- the prompt contract
def test_phase_prompt_states_the_scope_contract():
    """PHASEPR-FR-001: phase 2 of 3's prompt limits the session to its own phase — only the tasks
    under "## Phase 2", no files outside the declared scope, no tasks from other phases."""
    p = _prompt_for(2)
    assert "PHASE INSTRUCTION" in p
    assert "You are implementing Phase 2 of 3 for run 030." in p
    assert 'SCOPE: implement only the tasks explicitly listed under "## Phase 2"' in p
    assert "Do NOT modify files outside the declared file scope for this phase." in p
    assert "Do NOT implement tasks from other phases." in p


def test_phase_prompt_instructs_parallel_subagent_dispatch():
    """PHASEPR-FR-002: the prompt instructs [P]-marked tasks be dispatched concurrently via
    subagents, results collected before proceeding."""
    p = _prompt_for(2)
    assert "may be dispatched concurrently via subagents." in p
    assert "Dispatch all [P]-marked tasks in parallel, then collect their results" in p


def test_phase_prompt_instructs_completion_markers_and_forbids_questions():
    """PHASEPR-FR-003: the prompt names the completion-marker contract — `[x]` done, `[!]` plus a
    one-line reason when blocked, written to the implementation plan (implementation-plan.md;
    legacy tasks.md) — and forbids operator questions (assumptions documented in code comments
    instead)."""
    p = _prompt_for(2)
    assert "update the implementation plan (implementation-plan.md; legacy tasks.md)" in p
    assert "mark each completed task with `[x]` in its checkbox" in p
    assert "mark it `[!]` and append a one-line reason." in p
    assert "CLARIFICATIONS: do not ask the operator for input." in p
    assert (
        "document your assumption in a comment in the code (not in the implementation plan)." in p
    )


def test_phase_prompt_names_the_concrete_coding_gate_command():
    """PHASEPR-FR-001 (extension): every phase handoff injects the concrete coding-gate command —
    `3pwr gate run --path <scope>` resolved against the phase's declared file scope — so a fresh
    session knows exactly what to run, and states the gate is advisory (Verify stays the sole
    ledger verdict)."""
    p = _prompt_for(1)  # phase 1's scope is src/core.py → the shared top-level dir is `src`
    assert "CODING GATE:" in p
    assert "`3pwr gate run --path src`" in p
    assert "A phase with a red coding gate is not complete." in p
    assert "the Verify stage remains the sole signed verdict" in p


def test_tasks_stage_template_names_the_same_completion_markers():
    """PHASEPR-FR-003: the tasks-stage agent instruction (repo template and its scaffold mirror)
    describes the same `[x]`/`[!]` marker contract the phase prompt expects."""
    for path in (
        REPO_ROOT / ".3powers" / "templates" / "agents" / "implementation-plan.agent.md",
        PACKAGE_DIR / "scaffold" / "templates" / "agents" / "implementation-plan.agent.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "`[x]`" in text, path
        assert "`[!]`" in text and "reason" in text, path


# --------------------------------------------------------------------------- completed-phases summary
def test_phase_two_prompt_carries_the_phase_one_summary():
    """PHASEPR-FR-004: phase 2's prompt summarizes phase 1 by number and heading name."""
    assert "Phases already completed: Phase 1 (core)" in _prompt_for(2)


def test_phase_three_summary_lists_both_earlier_phases_in_order():
    """PHASEPR-FR-004: phase 3's summary names phases 1 and 2, in artifact order."""
    assert "Phases already completed: Phase 1 (core), Phase 2 (alpha)" in _prompt_for(3)


def test_phase_one_summary_is_none():
    """PHASEPR-FR-004: phase 1 has nothing completed — the line reads `none`, nothing is invented."""
    lst = phases.parse_phases(_TASKS_3PHASE)
    assert phases.completed_phases_summary(lst, 1) == "none"
    assert "Phases already completed: none" in _prompt_for(1)


def test_prompt_and_summary_are_deterministic():
    """PHASEPR-NFR-001: identical inputs render identical prompts and summaries — pure functions,
    no clock, no network (3PWR-NFR-001)."""
    assert _prompt_for(2) == _prompt_for(2)
    lst = phases.parse_phases(_TASKS_3PHASE)
    assert phases.completed_phases_summary(lst, 3) == phases.completed_phases_summary(lst, 3)


# --------------------------------------------------------------------------- stall detection (predicate)
@pytest.mark.parametrize(
    "tail",
    [
        "Could you clarify the button label?",
        "…done with T001.\nI NEED CLARIFICATION on the second field",
        "which color should the banner be?",
    ],
)
def test_unanswered_question_fires_on_question_tails(tail):
    """PHASEPR-FR-005: a tail ending in `?` or carrying a clarify phrase (case-insensitive) with no
    subsequent code block reads as a possible unanswered question."""
    assert transcripts.unanswered_question(tail) is True


@pytest.mark.parametrize(
    "tail",
    [
        "",
        "   \n",
        "all tasks complete; tasks.md updated.",
        "Could you clarify? Never mind — resolved it:\n```python\nVALUE = 1\n```\n",
    ],
)
def test_unanswered_question_stays_silent_on_resolved_or_empty_tails(tail):
    """PHASEPR-FR-005: an empty tail, a plain completion, or a question followed by a fenced code
    block (the session produced work past it) never matches."""
    assert transcripts.unanswered_question(tail) is False


def test_tail_text_reads_only_the_last_bytes_and_swallows_missing_files(tmp_path):
    """PHASEPR-FR-005: the scan reads exactly the transcript's last 500 bytes; a missing file reads
    as empty — the advisory path introduces no new failure mode (PHASEPR-NFR-002)."""
    log = tmp_path / "t.log"
    log.write_text("x" * 1000 + "Could you clarify the button label?", encoding="utf-8")
    tail = transcripts.tail_text(log, limit=500)
    assert len(tail.encode("utf-8")) == 500
    assert tail.endswith("Could you clarify the button label?")
    assert transcripts.tail_text(tmp_path / "absent.log") == ""
