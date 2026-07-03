"""Render the configured judiciary model into the Spec Kit judiciary agents' frontmatter (INITX-FR-004).

Only the judiciary roles are pinned — ``/3pwr.oracle`` (oracle) and ``/3pwr.review`` (reviewer). The
coder and every other agent stay on the Spec Kit integration's default model (an explicit non-goal).
Rendering is deterministic — the same configuration yields byte-identical output (INITX-NFR-005) — and
non-destructive: a hand-edited ``model:`` line is never overwritten without ``force`` (INITX-NFR-006). A
managed pin carries a marker comment so re-rendering and drift re-apply stay idempotent.
"""

from __future__ import annotations

from pathlib import Path

from .config import Settings

# role -> the agent file (under .github/agents/) whose frontmatter it pins.
JUDICIARY_AGENTS: dict[str, str] = {
    "oracle": "3pwr.oracle.agent.md",
    "reviewer": "3pwr.review.agent.md",
}

_MARKER = "# 3pwr:managed-model"  # marks a model line this tool wrote (INITX-NFR-006)


def agents_dir(root: Path) -> Path:
    return root / ".github" / "agents"


def model_field(pin: dict[str, str]) -> str:
    """The frontmatter value for a pin: ``<label> (<integration>)``, or ``<label>`` if no integration."""
    label = pin["label"]
    integration = pin.get("integration") or ""
    return f"{label} ({integration})" if integration else label


def _render(text: str, value: str, *, force: bool) -> tuple[str, str]:
    """Inject/update a managed ``model:`` line in the leading frontmatter block.

    Returns ``(new_text, status)`` with status one of ``created`` | ``updated`` | ``kept`` |
    ``skipped`` (a hand-edited model line, not forced) | ``no-frontmatter``."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text, "no-frontmatter"
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return text, "no-frontmatter"

    fm = lines[1:close]
    managed_line = f"model: {value}  {_MARKER}"
    idx = next((j for j, ln in enumerate(fm) if ln.lstrip().startswith("model:")), None)
    if idx is None:
        fm.insert(0, managed_line)
        status = "created"
    else:
        existing = fm[idx]
        if _MARKER not in existing and not force:
            return text, "skipped"  # hand-edited — never clobber without force (INITX-NFR-006)
        if existing.strip() == managed_line.strip():
            status = "kept"
        else:
            fm[idx] = managed_line
            status = "updated"

    new_text = "\n".join(["---", *fm, "---", *lines[close + 1 :]])
    if text.endswith("\n") and not new_text.endswith("\n"):
        new_text += "\n"
    return new_text, status


def render_all(settings: Settings, root: Path, *, force: bool = False) -> dict[str, str]:
    """Pin each configured judiciary role's model into its agent file (INITX-FR-004).

    Returns a ``role -> status`` map. A role with no concrete model pin is ``unconfigured``; a missing
    agent file is ``absent`` (reported, never fabricated). Only ``created``/``updated`` write to disk."""
    out: dict[str, str] = {}
    adir = agents_dir(root)
    for role, filename in JUDICIARY_AGENTS.items():
        pin = settings.role_model_pin(role)
        if pin is None:
            out[role] = "unconfigured"
            continue
        path = adir / filename
        if not path.exists():
            out[role] = "absent"
            continue
        new_text, status = _render(path.read_text(encoding="utf-8"), model_field(pin), force=force)
        if status in ("created", "updated"):
            path.write_text(new_text, encoding="utf-8")
        out[role] = status
    return out
