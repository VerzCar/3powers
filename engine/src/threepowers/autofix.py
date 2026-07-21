"""Bounded, code-only auto-remediation of a red gate verdict.

The auto-fix loop hands a red verdict's failed gates back to the coding agent through the existing
hand-back prompt, re-runs the deterministic gate suite, and repeats until the verdict is green or
the attempt budget is exhausted. It is *code-only*: the loop may only dispatch the coder (which
edits code) and re-run the gates. It NEVER records a deviation or advisory, weakens a check, edits
gate configuration, or mutates a verdict — those are human-only, signed decisions that live on the
deviation path, entirely outside this loop. Every re-check records an honest signed verdict, so the
trust spine sees each attempt.

``gate_gaming`` stays the backstop: a coder that tries to weaken a check (a deleted assertion, an
inline suppression) trips that gate, and the loop stops immediately and hands the failure to the
human remediation summary rather than asking the coder to try again.

The loop is pure orchestration over two injected callables — dispatch the coder, recompute the
verdict — plus a working-tree snapshot for no-progress detection. It runs no model itself and is
unit-tested with fakes. The live ``3pwr run`` (auto mode) path and the standalone ``3pwr gate fix``
command share this one loop.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from . import orchestrate, style

# The backstop gate. A genuine gaming signal on a re-check ends the loop and routes to the human
# summary — the loop never re-dispatches a coder that just tried to weaken a check.
GAMING_GATE = "gate_gaming"

# Why the loop stopped. ``green`` is the only success; the rest hand off to the human summary.
REASON_GREEN = "green"
REASON_BUDGET = "budget"
REASON_NO_PROGRESS = "no_progress"
REASON_GAMING = "gaming"
REASON_DISPATCH_FAILED = "dispatch_failed"
REASON_NOTHING_TO_FIX = "nothing_to_fix"


def failed_gate_names(verdict: Mapping[str, Any]) -> list[str]:
    """The names of every FAILED gate in a verdict dict (``Verdict.to_dict()`` shape), in order."""
    return [
        str(g.get("gate", "")) for g in (verdict.get("gates") or []) if g.get("status") == "fail"
    ]


def failed_gate_files(verdict: Mapping[str, Any]) -> list[str]:
    """The union of files the FAILED gates point at (sorted, deduped) — best-effort, advisory.

    Reads each failed gate's ``details['files']`` when it is a list of path strings; a gate that
    does not name files contributes nothing. Used only to optionally scope a coder dispatch; an
    empty result means the coder sees the whole change, which is always safe."""
    files: set[str] = set()
    for g in verdict.get("gates") or []:
        if g.get("status") != "fail":
            continue
        raw = (g.get("details") or {}).get("files")
        if isinstance(raw, list):
            files.update(str(f) for f in raw if isinstance(f, str) and f.strip())
    return sorted(files)


@dataclass(frozen=True)
class AttemptRecord:
    """One coder dispatch + re-check of the auto-fix loop.

    ``failed_gates`` is the set of gates that were red going into the attempt; ``changed_files`` are
    the working-tree paths the coder altered on this attempt (detected by comparing a pre/post
    snapshot). Both feed the human "what I tried" summary and the loop's no-progress check."""

    number: int
    failed_gates: list[str]
    changed_files: list[str]


@dataclass(frozen=True)
class AutoFixResult:
    """The outcome of an auto-fix loop: whether it reached green, why it stopped, and each attempt.

    ``final`` is ``"pass"`` only when a re-check came back green; every other stop reason leaves it
    ``"fail"`` so the caller preserves the honest gate-red outcome. ``reason`` is one of the
    ``REASON_*`` constants. Presentation and the caller's proceed decision read this; the loop never
    mutates a verdict or the ledger to produce it."""

    final: str
    reason: str
    attempts: list[AttemptRecord] = field(default_factory=list)

    @property
    def fixed(self) -> bool:
        """True iff the loop drove the verdict to green."""
        return self.final == "pass"


def _snapshot_diff(pre: Mapping[str, str], post: Mapping[str, str]) -> list[str]:
    """The paths whose content differs between two worktree snapshots (sorted).

    Mirrors :func:`runner.produced_paths` without importing it, keeping this module pure and free of
    the git/runner layer — a path present in only one snapshot, or with a changed hash, counts."""
    keys = set(pre) | set(post)
    return sorted(p for p in keys if pre.get(p) != post.get(p))


def run_loop(
    *,
    verdict: Mapping[str, Any],
    max_attempts: int,
    dispatch: Callable[[str, Sequence[str]], bool],
    recompute: Callable[[], tuple[str, Mapping[str, Any]]],
    snapshot: Callable[[], Mapping[str, str]],
    scope_to_failed: bool = False,
    report: Callable[[str], None] = lambda _msg: None,
) -> AutoFixResult:
    """Run the bounded, code-only auto-fix loop over a red ``verdict``.

    Args:
        verdict: the red verdict dict that triggered the loop (``Verdict.to_dict()`` shape).
        max_attempts: the coder-attempt budget (clamped to at least 1).
        dispatch: dispatch the coder with ``(handback_prompt, scope_files)``; returns whether the
            dispatch itself succeeded. This is the ONLY code-editing action the loop performs.
        recompute: re-run the deterministic gate suite, recording an honest signed verdict, and
            return ``(outcome, verdict_dict)`` where ``outcome`` is ``"pass"``/``"fail"``/``"error"``.
        snapshot: a working-tree content snapshot (``{path: hash}``) used only to detect whether a
            coder attempt changed any file (no-progress detection).
        scope_to_failed: when true, scope each dispatch to the failed gates' files (advisory).
        report: an optional human-progress sink; never affects control flow.

    Returns:
        An :class:`AutoFixResult`. The loop records an honest verdict on every re-check, never a
        deviation/advisory, never a config edit, and never a verdict mutation. A ``gate_gaming``
        signal on any re-check stops the loop immediately (``REASON_GAMING``).
    """
    if not failed_gate_names(verdict):
        # Nothing to hand back — a red verdict with no per-gate failure carries no actionable
        # findings. The loop cannot fix what it cannot name, so it stays honestly red rather than
        # claiming success. (It never dispatches the coder or recomputes here.)
        return AutoFixResult("fail", REASON_NOTHING_TO_FIX)

    budget = max(1, int(max_attempts))
    current: Mapping[str, Any] = verdict
    attempts: list[AttemptRecord] = []

    for n in range(1, budget + 1):
        failed = failed_gate_names(current)
        prompt = orchestrate.coder_handback(current)
        scope = failed_gate_files(current) if scope_to_failed else []
        report(f"auto-fix attempt {n}/{budget}: handing {', '.join(failed)} back to the coder")

        pre = snapshot()
        dispatched = dispatch(prompt, scope)
        changed = _snapshot_diff(pre, snapshot())
        attempts.append(AttemptRecord(number=n, failed_gates=failed, changed_files=changed))

        if not dispatched:
            report(f"auto-fix attempt {n}: coder dispatch failed — handing off to you")
            return AutoFixResult("fail", REASON_DISPATCH_FAILED, attempts)

        outcome, current = recompute()
        if outcome == "pass":
            report(f"auto-fix reached green after {n} attempt(s)")
            return AutoFixResult("pass", REASON_GREEN, attempts)

        new_failed = failed_gate_names(current)
        if GAMING_GATE in new_failed:
            # A weaken-the-check move was caught. Stop now; the human must review it — never
            # re-dispatch a coder that just gamed a gate.
            report("auto-fix stopped: gate_gaming tripped — handing off to you")
            return AutoFixResult("fail", REASON_GAMING, attempts)

        if not changed and set(new_failed) == set(failed):
            # The coder changed nothing and the same gates are still red — further attempts would
            # only repeat. Bail to the human summary.
            report("auto-fix stopped: no progress — handing off to you")
            return AutoFixResult("fail", REASON_NO_PROGRESS, attempts)

    report(f"auto-fix exhausted its {budget}-attempt budget — handing off to you")
    return AutoFixResult("fail", REASON_BUDGET, attempts)


_REASON_TAIL: dict[str, str] = {
    REASON_BUDGET: "reached the attempt budget without turning every gate green",
    REASON_NO_PROGRESS: "made no further progress",
    REASON_DISPATCH_FAILED: "could not dispatch the coding agent",
    REASON_GAMING: "stopped because the coder tried to weaken a check (gate_gaming tripped)",
    REASON_NOTHING_TO_FIX: "found no actionable gate findings to hand back",
}


def _tried_block(result: AutoFixResult, verdict: Mapping[str, Any], st: style.Styler) -> str:
    """The 'what I tried / what's left for you' block for a given-up loop.

    Per attempt: the gates it targeted and whether the coder changed any file. Then the honest next
    steps — fix the residual code (the panels above carry the per-gate guidance), or, labelled last
    resort, a human-only signed deviation. Presentation only; ``st`` colorizes and is a plain no-op
    when color is off, so the bytes are identical off a color TTY."""
    tail = _REASON_TAIL.get(result.reason, "could not reach green")
    n = len(result.attempts)
    lines = [
        st.accent(f"auto-fix {tail} after {n} attempt{'' if n == 1 else 's'} — what I tried:"),
    ]
    for a in result.attempts:
        gates = ", ".join(a.failed_gates) or "the failing gate(s)"
        if a.changed_files:
            nf = len(a.changed_files)
            edit = f"changed {nf} file{'' if nf == 1 else 's'}"
        else:
            edit = "changed no files"
        lines.append(f"  · attempt {a.number}: handed back {gates}; the coder {edit}")
    residual = failed_gate_names(verdict)
    lines.append(st.accent("what's left for you:"))
    if result.reason == REASON_GAMING:
        lines.append(
            "  · review the coder's change by hand — it tripped gate_gaming (a weakened check); "
            "revert the weakening and fix the code so the gate genuinely passes"
        )
    else:
        gates = ", ".join(residual) or "the failing gate(s)"
        lines.append(
            f"  · fix the code so {gates} genuinely pass — see the per-gate guidance above, "
            "then re-run the gates"
        )
    lines.append(
        "  · last resort — only for a deliberate, justified exception a human decides: record a "
        "signed deviation (3pwr deviation …); the auto-fix loop never does this for you"
    )
    return "\n".join(lines)


def give_up_summary(
    result: AutoFixResult,
    verdict: Mapping[str, Any],
    st: style.Styler | None = None,
    *,
    run_id: str = "",
    verbose: bool = False,
    layout: str = "normal",
) -> str:
    """The full human remediation surface for a given-up loop.

    Composes the per-gate failure panels (the same renderer a standalone ``gate run`` uses — what
    each residual failure means and the honest fix) with the "what I tried / what's left for you"
    block. Human output only: it never mutates the verdict and never enters the ``--json`` payload.
    Empty string when the verdict is not red."""
    st = st or style.Styler()
    panels = orchestrate.failure_panels(verdict, st, verbose=verbose, run_id=run_id, layout=layout)
    tried = _tried_block(result, verdict, st)
    if not panels:
        return tried
    return f"{panels}\n{tried}"
