"""Engine-owned lifecycle stage prompts + per-stage agent templates.

3Powers owns its executive, so it owns the instructions each stage's agent runs — no external
template package is required. :func:`assemble` composes a stage prompt deterministically from the
instruction body for the step plus the run's context (intent, the approved spec, prior-stage notes,
and the declared file scope). The same inputs always yield the same prompt, so prompt assembly never
introduces run-to-run variance.

Every dispatched prompt is sourced from template files — no instruction text lives inline in this
module. A project can SEE and TUNE each stage's instructions: a repo-local stage template at
``.3powers/templates/agents/<step>.agent.md`` (the tasks step's file is named for its agent,
``implementation-plan.agent.md``) — a readable markdown file with a small metadata header
(stage, artifact, role) — supplies that stage's instruction body when present; when the template is
absent, empty, or unreadable, the engine's bundled default template applies, and a step with
neither resolves to the generic fragment. Template resolution is deterministic and offline:
identical template bytes and identical run context yield identical assembled-prompt bytes, and a
template changes only the instruction body, never the surrounding context blocks or their order.

The templates carry the 3Powers discipline the ``.github/agents/*.agent.md`` files carried under
the old substrate: EARS requirements with namespaced IDs, an explicit risk tier and non-goals, task
file-scope, and — for the oracle step — authoring purely from acceptance criteria without reading
the implementation.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from pathlib import Path
from typing import Optional

# The engine's bundled default templates — the second resolution tier. A plain path constant
# (not an import of the scaffold module) so prompts stays import-cycle-free.
_BUNDLED_TEMPLATES_DIR = Path(__file__).resolve().parent / "scaffold" / "templates" / "agents"

# The closed variable vocabulary a template body may reference via ``$NAME``. Substitution fills
# every one of these (empty when the caller supplies no value); names outside this set are left
# verbatim so template text stays predictable.
_VARS = ("STEP", "GATE", "ARTIFACT", "FEATURE_FOLDER", "ORACLE_DESTINATION", "FEEDBACK")

# The producing stages whose prompt asks the agent for a commit description: the
# post-stage git hook records it as the stage commit's message. A fixed, deterministic block —
# never a gate or ledger input; an agent that yields none falls back to the deterministic default.
COMMIT_NOTE_STEPS: tuple[str, ...] = (
    "discovery",
    "specify",
    "clarify",
    "plan",
    "tasks",
    "oracle",
    "implement",
)

# The lifecycle stages that carry a dedicated agent template: every stage that
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
    """The agent-template filename for a step."""
    return f"{_TEMPLATE_NAMES.get(step, step)}.agent.md"


def template_path(templates_dir: Path, step: str) -> Path:
    """The well-known repo-local template location for a step."""
    return templates_dir / template_name(step)


def template_body(text: str) -> str:
    """The instruction body of a stage template — its markdown minus the metadata header.

    The header is a leading YAML front-matter block (``---`` … ``---``) declaring the stage, the
    artifact, and the role; it orients readers and is not part of the dispatched
    instructions. Pure and deterministic: the same bytes always yield the same body."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1 :]).strip()
    return text.strip()


def stage_template_body(templates_dir: Optional[Path], step: str) -> str:
    """The repo-local template's instruction body for ``step``, or ``""``.

    ``""`` — template absent, empty (no body after its header), or unreadable — means "use the
    built-in instruction"; the executive never dispatches an empty or broken prompt and never
    crashes on a malformed template. Deterministic and fully offline."""
    if templates_dir is None:
        return ""
    path = template_path(templates_dir, step)
    try:
        if not path.is_file():
            return ""
        return template_body(path.read_text(encoding="utf-8"))
    except OSError:
        return ""


def bundled_template_body(filename: str) -> str:
    """The instruction body of the engine's bundled default template ``filename``, or ``""``.

    Reads the template shipped inside the package (the second resolution tier, after the
    repo-local copy) and strips its metadata header. ``""`` — file absent or unreadable — means
    "fall through to the next tier"; never raises. Pure and deterministic given the installed
    package bytes."""
    try:
        return template_body((_BUNDLED_TEMPLATES_DIR / filename).read_text(encoding="utf-8"))
    except OSError:
        return ""


def substitute(body: str, variables: Optional[Mapping[str, str]] = None) -> str:
    """Fill a template body's ``$NAME`` placeholders from the closed vocabulary.

    Semantics (``string.Template.safe_substitute``): ``$$`` renders a literal ``$``; a defined
    variable (one of the closed vocabulary) left unfilled renders empty; an unknown ``$x`` is
    left verbatim; malformed ``$`` sequences never raise."""
    filled: dict[str, str] = {name: "" for name in _VARS}
    if variables:
        filled.update(variables)
    return string.Template(body).safe_substitute(filled)


def fragment_body(filename: str, templates_dir: Optional[Path]) -> str:
    """The body of a prompt fragment (``role: fragment`` template), repo-local first.

    Precedence: the repo-local copy at ``templates_dir / filename`` when it yields a non-empty
    body (absent, empty, or unreadable is skipped without error), else the bundled default.
    Fragments have no generic tier — an unknown fragment resolves to ``""``."""
    if templates_dir is not None:
        path = templates_dir / filename
        try:
            if path.is_file():
                body = template_body(path.read_text(encoding="utf-8"))
                if body:
                    return body
        except OSError:
            pass
    return bundled_template_body(filename)


def resolve_body(step: str, templates_dir: Optional[Path] = None) -> str:
    """The instruction body the executive dispatches for ``step``.

    Three-tier fallback, first non-empty wins: the repo-local stage template, the engine's
    bundled default template, then the generic fragment with ``$STEP`` filled with the step
    name. Deterministic and fully offline at every tier."""
    return (
        stage_template_body(templates_dir, step)
        or bundled_template_body(template_name(step))
        or substitute(fragment_body("generic.agent.md", templates_dir), {"STEP": step})
    )


def assemble(
    step: str,
    *,
    intent: str = "",
    spec_text: str = "",
    context: str = "",
    file_scope: str = "",
    templates_dir: Optional[Path] = None,
    variables: Optional[Mapping[str, str]] = None,
) -> str:
    """Compose the full stage prompt deterministically, entirely from template files.

    Order is fixed: the preamble fragment, the step's instruction body (the three-tier
    :func:`resolve_body` chain — repo-local, bundled, generic fragment), the commit-note fragment
    for producing steps, then whichever context blocks are present (intent, spec, prior notes,
    file scope). Empty blocks are omitted so the output is a pure function of the non-empty
    inputs — the same inputs always assemble byte-identical prompts. ``variables`` fills the
    closed ``$NAME`` vocabulary in the template-sourced pieces ONLY; the run-context blocks are
    appended verbatim, so untrusted text (a spec containing ``$``) is never substituted."""
    preamble = substitute(fragment_body("preamble.agent.md", templates_dir), variables)
    body = substitute(resolve_body(step, templates_dir), variables)
    parts: list[str] = [preamble, "", body]
    if step in COMMIT_NOTE_STEPS:
        # A fixed block outside the tunable instruction body: a repo-local stage
        # template cannot drop the commit-description request, and assembly stays deterministic.
        parts += ["", substitute(fragment_body("commit-note.agent.md", templates_dir), variables)]
    if intent.strip():
        parts += ["", "INTENT:", intent.strip()]
    if spec_text.strip():
        parts += ["", "APPROVED SPEC:", spec_text.strip()]
    if context.strip():
        parts += ["", "PRIOR CONTEXT:", context.strip()]
    if file_scope.strip():
        parts += ["", "FILE SCOPE:", file_scope.strip()]
    return "\n".join(parts) + "\n"
