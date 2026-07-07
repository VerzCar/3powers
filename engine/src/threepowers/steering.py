"""Steering an autonomous run — file-based intent and the human-gate actions (STEER, spec 019).

Two seams in the operator's loop with ``3pwr run`` close here:

* **File-based intent** (STEER-FR-001..004): the run's intent can come from a text file
  (``--file <path>``, markdown preferred), optionally combined with a short inline instruction. The
  resolution is a **pure, deterministic function** of (file contents, inline text) with a fixed order —
  file first as the base, the inline text appended as an instruction — so identical inputs always yield
  the identical resolved intent (STEER-FR-002's property), and only the *resolved* text is recorded in
  the ledger ``start`` entry (STEER-FR-004).
* **The three gate actions** (STEER-FR-005..008): at a human-gate pause the operator approves, rejects,
  or *revises with a message*. This module owns the pure pieces — the gate → re-dispatched-step mapping,
  the artifact-under-review resolution, the copy-pasteable action commands, and the deterministic
  revise-context block injected into the re-dispatched stage's prompt (STEER-NFR-003). Revise feedback
  is resolved from inline-or-file by the SAME rule as the intent source (STEER-FR-007's property).

Everything here is pure given its inputs (no network, no model call) — the trust path, verdict bytes,
and ledger format are untouched (STEER-NFR-003, 3PWR-NFR-001).
"""

from __future__ import annotations

from pathlib import Path

from . import workspace

# The step a revise re-dispatches per human gate (STEER-FR-006): the action step that OWNS the artifact
# the gate reviews — deterministic, derived from the lifecycle's own step→stage assignment.
REVISE_TARGETS: dict[str, tuple[str, str]] = {
    "review-spec": ("specify", "Spec"),  # the spec artifact under human review
    "review-plan": ("plan", "Plan"),
    "review-verify": ("implement", "Build"),
    "signoff": (
        "implement",
        "Build",
    ),  # the evidence gate re-works the implementation (3PWR-FR-037)
}


def read_text_file(path: Path) -> tuple[str, str]:
    """Read a UTF-8 intent/feedback file; ``(text, "")`` or ``("", error)`` (STEER-FR-003).

    The error names the path and the reason for every bad-file case — missing, a directory, empty
    (or whitespace-only), or not decodable as text — so the caller can fail fast with an actionable
    message and the setup exit code, writing nothing."""
    if not path.exists():
        return "", f"intent file not found: {path}"
    if path.is_dir():
        return "", f"intent file is a directory, not a text file: {path}"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return "", f"intent file is not decodable as UTF-8 text: {path}"
    except OSError as exc:
        return "", f"intent file could not be read: {path} ({exc.__class__.__name__})"
    if not text.strip():
        return "", f"intent file is empty: {path}"
    return text, ""


def combine(base: str, extra: str) -> str:
    """Combine a base text with an appended instruction — the one deterministic resolution rule
    (STEER-FR-002's property, reused verbatim for revise feedback per STEER-FR-007).

    Fixed order: the base (file) first, the extra (inline) appended; a missing part yields the other
    unchanged. Pure — identical inputs always yield identical output bytes."""
    b, e = base.strip(), extra.strip()
    if b and e:
        return f"{b}\n\n{e}"
    return b or e


def resolve_intent(file_arg: str | None, inline: str | None) -> tuple[str, str]:
    """The run's resolved intent from ``--file`` and/or the inline argument (STEER-FR-001/002).

    Returns ``(resolved, "")`` or ``("", error)`` when the file is unusable (STEER-FR-003). The
    resolved text is what every downstream consumer — authoring prompt, work-kind classification, the
    ledger ``start`` entry — must see."""
    file_text = ""
    if file_arg:
        file_text, err = read_text_file(Path(file_arg))
        if err:
            return "", err
    return combine(file_text, inline or ""), ""


def resolve_feedback(file_arg: str | None, inline: str | None) -> tuple[str, str]:
    """Revise feedback resolved from inline-or-file by the SAME rule as the intent (STEER-FR-007).

    Empty or whitespace-only resolved feedback is an error — a revise must carry a message."""
    resolved, err = resolve_intent(file_arg, inline)
    if err:
        return "", err.replace("intent file", "revise feedback file")
    if not resolved.strip():
        return "", 'revise feedback is empty — pass a message: --revise "<feedback>"'
    return resolved, ""


def revise_target(gate: str) -> tuple[str, str]:
    """The ``(step, stage)`` a revise at ``gate`` re-dispatches, or ``("", "")`` (STEER-FR-006)."""
    return REVISE_TARGETS.get(gate, ("", ""))


def gate_artifact(root: Path, feature_dir: Path | None, gate: str) -> str:
    """The repo-relative path of the artifact under review at ``gate`` (STEER-FR-005), or ``""``.

    The spec-approval gate reviews the feature's spec; the plan gate its plan; the verify/sign-off
    gates review the recorded verdict evidence. Pure given the tree — no scan beyond the feature
    folder the run already bound."""
    p: Path | None = None
    if gate == "review-spec" and feature_dir is not None:
        p = workspace.spec_path(feature_dir)
    elif gate == "review-plan" and feature_dir is not None:
        p = workspace.find_artifact(feature_dir, "plan")
    elif gate in ("review-verify", "signoff"):
        p = root / ".3powers" / "verdicts" / "latest.json"
    if p is None:
        return ""
    try:
        return p.relative_to(root).as_posix()
    except ValueError:
        return p.as_posix()


def gate_actions(spec_id: str) -> list[tuple[str, str]]:
    """The three human-gate actions, each with its copy-pasteable command (STEER-FR-005)."""
    return [
        ("approve", f"3pwr run --resume --spec-id {spec_id} --approver <you>"),
        ("reject", f'3pwr abort --spec-id {spec_id} --reason "<why>"'),
        ("revise", f'3pwr run --resume --spec-id {spec_id} --revise "<feedback>"'),
    ]


def revise_context(gate: str, artifact: str, feedback: str) -> str:
    """The deterministic prompt block a revise injects into the re-dispatched stage (STEER-FR-006).

    Carries the artifact under review and the human's feedback; assembly is a pure function of its
    inputs so a revision reproduces byte-identically from the recorded feedback (STEER-NFR-003)."""
    subject = artifact or "the stage's artifact"
    return (
        f"REVISION REQUESTED (human gate '{gate}'): the artifact under review is {subject}. "
        "Apply the following human feedback and revise that artifact in place — keep everything the "
        f"feedback does not name, and do not advance past this stage:\n{feedback.strip()}"
    )
