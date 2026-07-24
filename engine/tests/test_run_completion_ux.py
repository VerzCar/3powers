"""Run-completion presentation: the pre-batch dispatch log, the completion tracker and business
summary, the Observe call-to-action, and the completion notification wording.

These are pure rendering helpers — no agent, no git, no network. Each is driven directly with a
constructed schedule / feature folder so the exact lines a finished run prints (and the notice it
sends) are pinned, including the scheduler's three named serialization reasons.
"""

from __future__ import annotations

from threepowers import completion, notify, orchestrate, phases, style
from threepowers.cli import run as runmod

_STYLE = style.Styler(enabled=False)  # a transparent styler → assert on content, not ANSI


# --------------------------------------------------------------------------- completion notice
def test_completion_message_says_complete_ready_to_push():
    """PLAN-040: the completion notice states the settled end state — the run is complete and the
    branch is ready to push (not merged for the developer)."""
    assert notify.completion_message("PAY") == "3pwr run PAY: complete — ready to push"


# --------------------------------------------------------------------------- pre-batch dispatch log
def _mixed_schedule() -> phases.Schedule:
    """A schedule whose three serialized [P] phases each hit a DIFFERENT named reason."""
    text = (
        "## Phase 1: alpha [P]\n\n**File scope**: a.py\n**Depends on**: none\n"
        "- [ ] T1 [X-FR-001] a (files: a.py)\n"
        "## Phase 2: beta [P]\n\n**File scope**: a.py\n**Depends on**: none\n"
        "- [ ] T2 [X-FR-002] b (files: a.py)\n"
        "## Phase 3: gamma [P]\n\n**Depends on**: none\n- [ ] T3 [X-FR-003] c\n"
        "## Phase 4: delta [P]\n\n**File scope**: d.py\n**Depends on**: Phase 3\n"
        "- [ ] T4 [X-FR-004] d (files: d.py)\n"
    )
    return phases.schedule(phases.parse_phases(text))


def test_prebatch_log_names_each_batch_and_every_serialization_reason():
    """PLAN-040: the pre-batch log renders one group per batch (number + parallel/serial) and, for a
    serialized [P] phase, the scheduler's named reason — overlap, no scope, and an unmet dependency
    all appear verbatim."""
    lines = runmod._prebatch_log_lines(_mixed_schedule(), agent_name="claude", model="opus")
    joined = "\n".join(lines)
    assert "batch 1 — 1 phase(s), serial" in joined
    assert "· phase 1 (alpha) → claude / opus" in joined
    assert "· phase 2 (beta) → claude / opus — serialized: file scope overlaps Phase 1" in joined
    assert "· phase 3 (gamma) → claude / opus — serialized: no file scope declared" in joined
    assert (
        "· phase 4 (delta) → claude / opus — serialized: depends on Phase 3 (not yet complete)"
        in joined
    )


def test_prebatch_log_marks_a_real_parallel_batch_as_parallel():
    """PLAN-040: a batch that actually holds >1 phase is labelled parallel, and its members carry
    no serialization reason."""
    text = (
        "## Phase 1: core\n\n**File scope**: core.py\n**Depends on**: none\n"
        "- [ ] T1 [X-FR-001] core (files: core.py)\n"
        "## Phase 2: a [P]\n\n**File scope**: a.py\n**Depends on**: none\n"
        "- [ ] T2 [X-FR-002] a (files: a.py)\n"
        "## Phase 3: b [P]\n\n**File scope**: b.py\n**Depends on**: none\n"
        "- [ ] T3 [X-FR-003] b (files: b.py)\n"
    )
    sched = phases.schedule(phases.parse_phases(text))
    lines = runmod._prebatch_log_lines(sched, agent_name="codex", model="gpt")
    joined = "\n".join(lines)
    assert "batch 2 — 2 phase(s), parallel" in joined
    assert "serialized:" not in joined.split("batch 2", 1)[1]  # the parallel batch names no reason


# --------------------------------------------------------------------------- completion tracker
def test_completion_tracker_marks_every_stage_done_and_omits_observe():
    """PLAN-040: a finished run's tracker renders every stage through Ship as done (✓) — not the
    reached stage as current — and Observe is not a row (it becomes the follow-on CTA)."""
    tracker = runmod._completion_tracker(_STYLE)
    for stage in orchestrate.STAGES:
        if stage == "Observe":
            continue
        assert f"✓ {stage}" in tracker
    assert "Observe" not in tracker


# --------------------------------------------------------------------------- completion summary
def test_completion_summary_uses_changelog_highlights_when_present(tmp_path):
    """PLAN-040: the "what shipped" digest lists the run's changelog highlights when the implement
    record carried authored entries."""
    feat = tmp_path / "specs-src" / "040-x"
    feat.mkdir(parents=True)
    completion.write_record(
        tmp_path, feat, "implement", spec_id="X", report="### Added\n\n- a shiny new thing\n"
    )
    lines = runmod._completion_summary_lines(feat, _STYLE)
    joined = "\n".join(lines)
    assert "All stages are done." in joined
    assert "what shipped:" in joined
    assert "· a shiny new thing" in joined


def test_completion_summary_falls_back_when_no_changelog(tmp_path):
    """PLAN-040: with no changelog record (a legacy run, or none bound) the digest degrades to the
    single-line fallback — never an error, never an empty business summary."""
    lines = runmod._completion_summary_lines(None, _STYLE)
    joined = "\n".join(lines)
    assert "All stages are done." in joined
    assert "what shipped: recorded in this run’s changelog.md" in joined


# --------------------------------------------------------------------------- Observe CTA
def test_observe_cta_states_clean_state_and_next_actions(tmp_path):
    """PLAN-040: the Observe CTA states the settled state (branch, Ship reached, every run-produced
    change committed) and the next actions — measure coverage, register checks, push the branch —
    closing with the harness's iteration rule (a lesson returns as a NEW run, never a patch)."""
    feat = tmp_path / "specs-src" / "040-x"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("**Spec ID**: X\n", encoding="utf-8")
    lines = runmod._observe_cta_lines(
        _STYLE, root=tmp_path, feature_dir=feat, run_branch="feat/040-x"
    )
    joined = "\n".join(lines)
    assert "on branch feat/040-x: Ship reached, every run-produced change committed." in joined
    assert "3pwr observe coverage --spec specs-src/040-x/spec.md" in joined
    assert "push / merge feat/040-x to ship it" in joined
    assert (
        'a production lesson returns as a NEW 3pwr run "<intent>" — never an ad-hoc patch.'
        in joined
    )


def test_observe_cta_uses_a_placeholder_spec_when_unbound(tmp_path):
    """PLAN-040: with no bound feature folder (a dry run) the coverage command still reads sensibly
    via a ``<path/to/spec.md>`` placeholder rather than a broken path."""
    lines = runmod._observe_cta_lines(_STYLE, root=tmp_path, feature_dir=None, run_branch="")
    joined = "\n".join(lines)
    assert "3pwr observe coverage --spec <path/to/spec.md>" in joined
