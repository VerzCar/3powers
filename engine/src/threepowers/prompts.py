"""Engine-owned lifecycle stage prompts (EXEC-FR-005) + per-stage agent templates (AGENTX-FR-001/005).

3Powers owns its executive, so it owns the instructions each stage's agent runs — no external template
package is required. :func:`assemble` composes a stage prompt deterministically from the instruction
body for the step plus the run's context (intent, the approved spec, prior-stage notes, and the
declared file scope). The same inputs always yield the same prompt, so prompt assembly never introduces
run-to-run variance (supports EXEC-FR-005's property and 3PWR-NFR-001).

A project can SEE and TUNE each stage's instructions (AGENTX-FR-001): a repo-local stage template at
``.3powers/templates/agents/<step>.agent.md`` (the tasks step's file is named for its agent,
``implementation-plan.agent.md``) — a readable markdown file with a small metadata header
(stage, artifact, role) — supplies that stage's instruction body when present; when the template is
absent, empty, or unreadable, the engine's built-in instruction below applies unchanged
(AGENTX-FR-005). Template resolution is deterministic and offline: identical template bytes and
identical run context yield identical assembled-prompt bytes, and a template changes only the
instruction body, never the surrounding context blocks or their order.

These prompts carry the 3Powers discipline the ``.github/agents/*.agent.md`` files carried under the old
substrate: EARS requirements with namespaced IDs, an explicit risk tier and non-goals, task file-scope,
and — for the oracle step — authoring purely from acceptance criteria without reading the implementation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

# A short standing preamble prepended to every stage prompt.
_PREAMBLE = (
    "You are an agent in the 3Powers judiciary-governed lifecycle. The spec is the law: never invent "
    "scope, never weaken a gate, and keep each change within its declared file scope. Trace every "
    "artifact to a requirement id."
)

# Per-step instruction bodies. Steps absent here fall back to a generic instruction.
_STAGE_PROMPTS: dict[str, str] = {
    "specify": (
        "STAGE: Specify. Turn the intent below into a feature spec in EARS form. Declare a Spec ID, a "
        "risk tier (Cosmetic|Standard|High-risk), and explicit non-goals BEFORE any requirement. Write "
        "each requirement as '<SPECID>-FR-###: the system shall …' with a measurable Acceptance line. Do "
        "NOT put implementation detail (named stack, schema, vendor) in the spec. Write the spec to "
        "specs/<feature>/spec.md — FLAT in the run's feature folder, no spec/ or artifacts/ subfolder — "
        "that file is the artifact this stage must produce."
    ),
    "clarify": (
        "STAGE: Clarify. Find every ambiguous or unmeasurable requirement in the spec and resolve it into "
        "a testable statement. An acceptance criterion that cannot be measured must be made measurable "
        "before it can proceed."
    ),
    "plan": (
        "STAGE: Plan. From the approved spec, produce the implementation plan and write it to "
        "specs/<feature>/plan.md — FLAT in the run's feature folder — that file is the artifact this "
        "stage must produce. "
        "Required sections: Summary (primary requirement + approach); Judicial Plan (the spec's risk "
        "tier, the gates it drives, the role → model-family table); Design (the files to change and the "
        "approach per requirement); Test layers (unit/integration/e2e as the tier demands); and Phases. "
        "Decompose the work into small ORDERED PHASES, each sized so one fresh agent session — the "
        "approved spec + the constitution/rules + the phase's tasks + the files in its scope — fits "
        "comfortably inside the configured context budget (default ~110k tokens; estimate ~4 bytes per "
        "token over those artifacts' bytes). Each phase declares its file scope and its estimated "
        "context size; split any phase whose estimate exceeds the budget. Mark independent phases with "
        "disjoint file scopes '[P]' so they can be dispatched to parallel subagent sessions. Do not "
        "expand scope beyond the spec's requirements and non-goals."
    ),
    "tasks": (
        "STAGE: Tasks. Break the plan into ordered tasks grouped into phases and write them to "
        "specs/<feature>/tasks.md — FLAT in the run's feature folder — that file is the artifact this "
        "stage must produce. "
        "Required sections: one '## Phase N: <name>' section per phase, in execution order, each "
        "carrying a '**File scope**:' line (every file the phase may touch), a '**Depends on**:' line "
        "('none' when independent), an '**Estimated context**:' line (~4 bytes/token over the spec + "
        "rules + this phase's tasks + files in scope, against the configured budget, default ~110k "
        "tokens), and a HANDOFF block naming what a fresh session must reload: the approved spec, the "
        "constitution/rules, this phase's tasks, and the declared file scope. Each task is one line "
        "'- [ ] T### [REQ-ID] description (files: …)' tracing to exactly ONE requirement id and "
        "declaring its file scope; editing outside a task's declared file scope is a signal to stop and "
        "re-spec. Split any phase whose estimate exceeds the budget. Mark independent phases with "
        "disjoint file scopes '[P]' in the heading (or '**Parallel**: yes') so the executive can "
        "dispatch them to parallel subagent sessions."
    ),
    "oracle": (
        "STAGE: Oracle (Phase A — judiciary). Author oracle tests SOLELY from the spec's acceptance "
        "criteria. You MUST NOT read the implementation, plan, tasks, or contracts — author only from the "
        "sealed spec bundle. Each oracle test names the requirement id it verifies. Write the oracle tests "
        "under tests/oracle/<spec-id>/ (or ./oracle-tests/ in a sanitized worktree) — those tests are the "
        "artifact this stage must produce."
    ),
    "implement": (
        "STAGE: Implement. Make the code satisfy the spec and pass the oracle tests, staying within each "
        "task's file scope. Add the coder's own tests; never modify or weaken the oracle tests. This stage "
        "must produce a non-empty implementation change."
    ),
}

_GENERIC = "STAGE: {step}. Perform this lifecycle step for the intent below, staying within the spec's scope."

# The producing stages whose prompt asks the agent for a commit description (GITX-FR-011): the
# post-stage git hook records it as the stage commit's message. A fixed, deterministic block —
# never a gate or ledger input; an agent that yields none falls back to the deterministic default.
COMMIT_NOTE_STEPS: tuple[str, ...] = (
    "specify",
    "clarify",
    "plan",
    "tasks",
    "oracle",
    "implement",
)
_COMMIT_NOTE = (
    "COMMIT MESSAGE: end your final output with a single line 'COMMIT: <one line describing what "
    "this stage changed and why>' — the engine records it as this stage's git commit message."
)

# The lifecycle stages that carry a dedicated agent template (AGENTX-FR-001): every stage that
# dispatches a headless agent. The template file for a step is ``<step>.agent.md`` unless the step
# has a dedicated agent name in ``_TEMPLATE_NAMES``.
TEMPLATE_STEPS: tuple[str, ...] = (
    "discovery",
    "specify",
    "clarify",
    "plan",
    "tasks",
    "oracle",
    "implement",
    "review",
    "characterize",
)

# Steps whose agent template carries a name other than the step's: the tasks step is authored by
# the implementation-plan agent (the detail-level plan derived from the high-level plan).
_TEMPLATE_NAMES: dict[str, str] = {"tasks": "implementation-plan"}


def template_name(step: str) -> str:
    """The agent-template filename for a step (AGENTX-FR-001)."""
    return f"{_TEMPLATE_NAMES.get(step, step)}.agent.md"


def template_path(templates_dir: Path, step: str) -> Path:
    """The well-known repo-local template location for a step (AGENTX-FR-001)."""
    return templates_dir / template_name(step)


def template_body(text: str) -> str:
    """The instruction body of a stage template — its markdown minus the metadata header.

    The header is a leading YAML front-matter block (``---`` … ``---``) declaring the stage, the
    artifact, and the role (AGENTX-FR-004); it orients readers and is not part of the dispatched
    instructions. Pure and deterministic: the same bytes always yield the same body."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return text.strip()


def stage_template_body(templates_dir: Optional[Path], step: str) -> str:
    """The repo-local template's instruction body for ``step``, or ``""`` (AGENTX-FR-005).

    ``""`` — template absent, empty (no body after its header), or unreadable — means "use the
    built-in instruction"; the executive never dispatches an empty or broken prompt and never
    crashes on a malformed template. Deterministic and fully offline (AGENTX-NFR-001)."""
    if templates_dir is None:
        return ""
    path = template_path(templates_dir, step)
    try:
        if not path.is_file():
            return ""
        return template_body(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def stage_prompt_body(step: str) -> str:
    """The engine-owned instruction body for a lifecycle step (generic fallback for unknown steps)."""
    return _STAGE_PROMPTS.get(step) or _GENERIC.format(step=step)


def resolve_body(step: str, templates_dir: Optional[Path] = None) -> str:
    """The instruction body the executive dispatches for ``step`` (AGENTX-FR-005).

    The repo-local stage template wins when it yields a non-empty body; otherwise the engine's
    built-in instruction for the step applies unchanged."""
    return stage_template_body(templates_dir, step) or stage_prompt_body(step)


def assemble(
    step: str,
    *,
    intent: str = "",
    spec_text: str = "",
    context: str = "",
    file_scope: str = "",
    body: str = "",
) -> str:
    """Compose the full stage prompt deterministically (EXEC-FR-005).

    Order is fixed: preamble, the step's instruction body, then whichever context blocks are present
    (intent, spec, prior notes, file scope). Empty blocks are omitted so the output is a pure function of
    the non-empty inputs. ``body`` — when non-empty — overrides the built-in instruction body with a
    repo-local stage template's (AGENTX-FR-005); it changes only the instruction body, never the
    surrounding context blocks or their order."""
    parts: list[str] = [_PREAMBLE, "", body.strip() or stage_prompt_body(step)]
    if step in COMMIT_NOTE_STEPS:
        # A fixed block outside the tunable instruction body (GITX-FR-011): a repo-local stage
        # template cannot drop the commit-description request, and assembly stays deterministic.
        parts += ["", _COMMIT_NOTE]
    if intent.strip():
        parts += ["", "INTENT:", intent.strip()]
    if spec_text.strip():
        parts += ["", "APPROVED SPEC:", spec_text.strip()]
    if context.strip():
        parts += ["", "PRIOR CONTEXT:", context.strip()]
    if file_scope.strip():
        parts += ["", "FILE SCOPE:", file_scope.strip()]
    return "\n".join(parts) + "\n"
