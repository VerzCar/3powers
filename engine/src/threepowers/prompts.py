"""Engine-owned lifecycle stage prompts (EXEC-FR-005).

3Powers owns its executive, so it owns the instructions each stage's agent runs — no external template
package is required. :func:`assemble` composes a stage prompt deterministically from the engine-owned
template for the step plus the run's context (intent, the approved spec, prior-stage notes, and the
declared file scope). The same inputs always yield the same prompt, so prompt assembly never introduces
run-to-run variance (supports EXEC-FR-005's property and 3PWR-NFR-001).

These prompts carry the 3Powers discipline the ``.github/agents/*.agent.md`` files carried under the old
substrate: EARS requirements with namespaced IDs, an explicit risk tier and non-goals, task file-scope,
and — for the oracle step — authoring purely from acceptance criteria without reading the implementation.
"""

from __future__ import annotations

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
        "NOT put implementation detail (named stack, schema, vendor) in the spec."
    ),
    "clarify": (
        "STAGE: Clarify. Find every ambiguous or unmeasurable requirement in the spec and resolve it into "
        "a testable statement. An acceptance criterion that cannot be measured must be made measurable "
        "before it can proceed."
    ),
    "plan": (
        "STAGE: Plan. From the approved spec, produce an implementation plan: the files to change, the "
        "approach per requirement, and the test layers (unit/integration/e2e) the risk tier demands. Do "
        "not expand scope beyond the spec's requirements and non-goals."
    ),
    "tasks": (
        "STAGE: Tasks. Break the plan into ordered tasks, each tracing to exactly one requirement id and "
        "declaring its file scope. Editing outside a task's declared file scope is a signal to stop and "
        "re-spec."
    ),
    "oracle": (
        "STAGE: Oracle (Phase A — judiciary). Author oracle tests SOLELY from the spec's acceptance "
        "criteria. You MUST NOT read the implementation, plan, tasks, or contracts — author only from the "
        "sealed spec bundle. Each oracle test names the requirement id it verifies."
    ),
    "implement": (
        "STAGE: Implement. Make the code satisfy the spec and pass the oracle tests, staying within each "
        "task's file scope. Add the coder's own tests; never modify or weaken the oracle tests."
    ),
}

_GENERIC = (
    "STAGE: {step}. Perform this lifecycle step for the intent below, staying within the spec's scope."
)


def stage_prompt_body(step: str) -> str:
    """The engine-owned instruction body for a lifecycle step (generic fallback for unknown steps)."""
    return _STAGE_PROMPTS.get(step) or _GENERIC.format(step=step)


def assemble(
    step: str,
    *,
    intent: str = "",
    spec_text: str = "",
    context: str = "",
    file_scope: str = "",
) -> str:
    """Compose the full stage prompt deterministically (EXEC-FR-005).

    Order is fixed: preamble, the step's instruction body, then whichever context blocks are present
    (intent, spec, prior notes, file scope). Empty blocks are omitted so the output is a pure function of
    the non-empty inputs.
    """
    parts: list[str] = [_PREAMBLE, "", stage_prompt_body(step)]
    if intent.strip():
        parts += ["", "INTENT:", intent.strip()]
    if spec_text.strip():
        parts += ["", "APPROVED SPEC:", spec_text.strip()]
    if context.strip():
        parts += ["", "PRIOR CONTEXT:", context.strip()]
    if file_scope.strip():
        parts += ["", "FILE SCOPE:", file_scope.strip()]
    return "\n".join(parts) + "\n"
