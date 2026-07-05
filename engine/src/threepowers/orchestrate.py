"""The orchestration front-end — drive the whole lifecycle as one loop (3PWR-FR-011, §6).

`3pwr run` walks the lifecycle, streaming progress, and — in ``auto`` mode — auto-continues past the
intermediate review gates while **always** stopping at the two spec-mandated human gates: ``review-spec``
(a human approves the spec, 3PWR-FR-006) and ``signoff`` (a human signs off on the evidence + residual,
3PWR-FR-037). ``commit`` mode stops at every gate.

The mode/gate/progress logic (``drive``) is pure given a *runner*. The live runner is the native
:class:`threepowers.runner.NativeRunner` (EXEC-FR-001) — it dispatches each stage to a headless agent
directly and runs the gate suite in-process; a ``SimulatedRunner`` drives ``--dry-run`` and the tests.
Orchestration never enters the deterministic verdict (3PWR-NFR-001).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from . import style
from .lifecycle import STAGES, canonical_stage

# The two human gates the spec makes mandatory — auto mode NEVER skips these (spec §1).
MANDATORY_GATES: dict[str, str] = {
    "review-spec": "3PWR-FR-006",  # a human approves the spec before implementation begins
    "signoff": "3PWR-FR-037",  # a human signs off on evidence + residual before advance
}

# The lifecycle steps, in order, mapped to their stage — the native executive walks these directly.
# kind: "action" (an executive/judiciary command), "verdict" (the deterministic gate suite), "gate" (human).
LIFECYCLE_STEPS: list[tuple[str, str, str]] = [
    ("specify", "action", "Spec"),
    ("clarify", "action", "Spec"),
    ("review-spec", "gate", "Spec"),
    ("plan", "action", "Plan"),
    ("review-plan", "gate", "Plan"),
    ("tasks", "action", "Plan"),
    ("oracle", "action", "Build"),
    ("implement", "action", "Build"),
    ("verify", "verdict", "Verify"),
    ("review-verify", "gate", "Verify"),
    ("signoff", "gate", "Review"),
    ("advance", "action", "Ship"),
]


@dataclass
class Event:
    """A streamed progress event."""

    kind: str  # step | verdict | gate-auto | gate-stop | done | failed | aborted
    step: str = ""
    stage: str = ""
    detail: str = ""


@dataclass
class Outcome:
    """What a runner returns from ``run()``/``resume()`` — its position + the events since the last call."""

    status: str  # gate | done | failed | aborted
    gate: str = ""
    stage: str = ""
    verdict: str = ""  # pass | fail | ""
    outcome: str = (
        ""  # a finer failure class: gate_red | verdict_error | dispatch_failed | artifact_missing
    )
    detail: str = (
        ""  # a human-readable failure detail (e.g. the missing-artifact message, RUNLIVE-FR-002)
    )
    events: list[Event] = field(default_factory=list)


@dataclass
class RunResult:
    """The driver's result after processing up to the next stop / completion."""

    status: str  # paused_at_gate | done | failed | aborted
    gate: str = ""
    gate_fr: str = ""  # the FR id when the pause is a mandatory gate
    stage: str = ""
    verdict: str = (
        ""  # the deterministic-gate verdict when status == failed: "fail" = a real gate-red,
    )
    # "" = a dispatch/execution failure (not a gate verdict) — the honest-diagnostics split (RUNX-FR-010/011)
    outcome: str = (
        ""  # a finer failure class (RUNLIVE): dispatch_failed | artifact_missing | verdict_error
    )
    detail: str = (
        ""  # a human-readable failure detail (e.g. the missing-artifact message, RUNLIVE-FR-002)
    )

    @property
    def is_gate_red(self) -> bool:
        """True only when a failure carries a real deterministic-gate ``fail`` verdict (RUNX-FR-010)."""
        return self.status == "failed" and self.verdict == "fail"

    @property
    def is_artifact_missing(self) -> bool:
        """True when the failure was a stage producing no declared artifact (RUNLIVE-FR-002)."""
        return self.status == "failed" and self.outcome == "artifact_missing"


class Runner(Protocol):
    def run(self) -> Outcome: ...
    def resume(self, decision: str) -> Outcome: ...


def is_mandatory(gate: str) -> bool:
    return gate in MANDATORY_GATES


def resume_index(gate: str) -> int:
    """The step index just AFTER ``gate`` — where a cross-invocation ``--resume`` picks the run back up."""
    for i, (sid, _kind, _stage) in enumerate(LIFECYCLE_STEPS):
        if sid == gate:
            return i + 1
    return 0


def step_index(step: str) -> int:
    """The index of ``step`` in the lifecycle, or -1 when unknown."""
    for i, (sid, _kind, _stage) in enumerate(LIFECYCLE_STEPS):
        if sid == step:
            return i
    return -1


def last_checkpoint_step(entries: list[dict], spec_id: str) -> str:
    """The last action step committed as a checkpoint for ``spec_id`` (RUNLIVE-FR-010), else ''.

    Read from the signed ledger's ``run``/``checkpoint`` entries, so a resume knows which stages already
    have a committed artifact and must not be re-dispatched — reconstructed offline from the repo alone."""
    step = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "checkpoint" and payload.get("step"):
            step = str(payload["step"])
    return step


def last_completed_step(entries: list[dict], spec_id: str) -> str:
    """The last action step recorded COMPLETE for ``spec_id``, else '' (AUTOX-FR-010).

    Completion is read from the signed ledger's ``run`` entries — a committed ``checkpoint``
    (RUNLIVE-FR-010) or the lightweight ``stage`` completion record written at stage success even with
    auto-commit off — so a resume knows which stages must not be re-dispatched regardless of the
    auto-commit setting, reconstructed offline from the repo alone."""
    step = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") in ("checkpoint", "stage") and payload.get("step"):
            step = str(payload["step"])
    return step


def resume_start_index(entries: list[dict], spec_id: str, pending_gate: str = "") -> int:
    """Where a ``--resume`` should re-enter the lifecycle (RUNLIVE-FR-010, AUTOX-FR-010).

    The later of: the step after the last approved human ``pending_gate`` (the EXEC behavior) and the
    step after the last recorded completion — a committed checkpoint or a ``run``/``stage`` record, so
    a failed ``--no-auto-commit`` run resumes too (given an intact working tree). Taking the max means
    a mid-segment failure resumes from the next *uncompleted* stage without re-dispatching a completed
    one, while a gate approval still advances past the gate."""
    start = resume_index(pending_gate) if pending_gate else 0
    done = last_completed_step(entries, spec_id)
    if done:
        start = max(start, step_index(done) + 1)
    return start


def segment_actions(resume_from: str = "") -> list[tuple[str, str]]:
    """The executive/judiciary action steps dispatched in the segment after ``resume_from`` — up to (not
    including) the next gate. Used to record one per-stage dispatch provenance entry (RUNX-FR-007), so a
    fresh run records only the stages before the first human gate and a resume records only the next
    segment (no already-completed stage is re-recorded, mirroring RUNX-FR-004)."""
    return segment_actions_from(resume_index(resume_from) if resume_from else 0)


def segment_actions_from(start_index: int) -> list[tuple[str, str]]:
    """The action steps from ``start_index`` up to (not including) the next gate (RUNX-FR-007, RUNLIVE-FR-010).

    Taking an explicit start index lets a resume that skipped committed checkpoints record provenance only
    for the stages it will actually dispatch — never a completed one."""
    out: list[tuple[str, str]] = []
    for sid, kind, stage in LIFECYCLE_STEPS[max(0, start_index) :]:
        if kind == "gate":
            break
        if kind == "action":
            out.append((sid, stage))
    return out


def drive(
    runner: Runner, mode: str, on_event: Callable[[Event], None], *, resuming: bool = False
) -> RunResult:
    """Walk the workflow via ``runner``, applying the auto/commit gate policy and streaming events.

    In ``auto`` mode an intermediate gate is auto-approved (the run continues); a mandatory gate always
    stops. In ``commit`` mode every gate stops. Returns when the run pauses at a stop, completes, fails,
    or aborts. ``resuming`` means we are continuing past a gate the human just approved."""
    outcome = runner.resume("approve") if resuming else runner.run()
    while True:
        for ev in outcome.events:
            on_event(ev)
        if outcome.status == "gate":
            if is_mandatory(outcome.gate) or mode == "commit":
                on_event(Event("gate-stop", outcome.gate, outcome.stage))
                return RunResult(
                    "paused_at_gate",
                    gate=outcome.gate,
                    gate_fr=MANDATORY_GATES.get(outcome.gate, ""),
                    stage=outcome.stage,
                )
            on_event(
                Event("gate-auto", outcome.gate, outcome.stage)
            )  # auto mode: intermediate gate
            outcome = runner.resume("approve")
            continue
        # The failed event carries the finer outcome class in ``step`` so the log can word it precisely
        # (gate-red vs a dispatch/artifact failure — RUNLIVE-FR-002, RUNX-FR-010/011).
        on_event(
            Event(outcome.status, outcome.outcome, outcome.stage, outcome.detail or outcome.verdict)
        )
        return RunResult(
            outcome.status,
            stage=outcome.stage,
            verdict=outcome.verdict,
            outcome=outcome.outcome,
            detail=outcome.detail,
        )


# --------------------------------------------------------------------------- simulated runner (--dry-run / tests)
class SimulatedRunner:
    """A scripted runner — no live agents. Walks ``steps``, emitting a step/verdict event per action and
    returning at each gate. Drives ``3pwr run --dry-run`` (so the UX is visible offline) and the tests."""

    def __init__(
        self,
        steps: Optional[list[tuple[str, str, str]]] = None,
        verdict: str = "pass",
        start_index: int = 0,
    ) -> None:
        self._steps = steps if steps is not None else LIFECYCLE_STEPS
        self._i = start_index
        self._verdict = verdict
        self.stage_results: list = []  # symmetry with NativeRunner; --dry-run dispatches nothing

    def _walk(self) -> Outcome:
        events: list[Event] = []
        while self._i < len(self._steps):
            sid, kind, stage = self._steps[self._i]
            self._i += 1
            if kind == "gate":
                return Outcome("gate", gate=sid, stage=stage, events=events)
            if kind == "verdict":
                events.append(Event("verdict", sid, stage, self._verdict))
                if self._verdict != "pass":
                    return Outcome("failed", stage=stage, verdict=self._verdict, events=events)
            else:
                events.append(Event("step", sid, stage))
        return Outcome("done", events=events)

    def run(self) -> Outcome:
        return self._walk()

    def resume(self, decision: str) -> Outcome:
        if decision == "reject":
            return Outcome("aborted", events=[Event("aborted")])
        return self._walk()


# --------------------------------------------------------------------------- progress rendering (pure)
_MARK = {"done": "✓", "current": "▶", "todo": "·"}
_MARK_ASCII = {"done": "v", "current": ">", "todo": "."}
# Event glyphs, with an ASCII fallback for a stream that cannot encode the Unicode marks (CLIUX-NFR-004).
_GLYPHS = {
    "step": "▶",
    "pass": "✓",
    "fail": "✗",
    "auto": "⏩",
    "pause": "⏸",
    "abort": "⊘",
    "done": "✓",
}
_GLYPHS_ASCII = {
    "step": ">",
    "pass": "v",
    "fail": "x",
    "auto": ">>",
    "pause": "||",
    "abort": "/",
    "done": "v",
}


def _glyphs(st: style.Styler) -> dict[str, str]:
    return _GLYPHS_ASCII if st.ascii_only else _GLYPHS


def render_tracker(reached_stage: str, st: style.Styler | None = None) -> str:
    """A one-line stage tracker: stages up to ``reached_stage`` are ✓, the reached one ▶, the rest ·.

    With a color-enabled ``st`` each cell is colored — done green, current bold-cyan, upcoming dim —
    so the same "you are here" view reads consistently live and in ``--status`` (CLIUX-FR-008/012).
    With no styler (the default) it is the plain glyph+name text, byte-for-byte as before."""
    st = st or style.Styler()
    m = _MARK_ASCII if st.ascii_only else _MARK
    reached = canonical_stage(reached_stage)
    idx = STAGES.index(reached) if reached in STAGES else -1
    cells = []
    for i, s in enumerate(STAGES):
        if i < idx:
            cells.append(st.ok(f"{m['done']} {s}"))
        elif i == idx:
            cells.append(st.head(f"{m['current']} {s}"))
        else:
            cells.append(st.dim(f"{m['todo']} {s}"))
    return "  ".join(cells)


def format_event(ev: Event, mode: str, st: style.Styler | None = None) -> str:
    """Human-readable one-liner for a streamed event (CLIUX-FR-009).

    With a color-enabled ``st`` the glyph and key words are colored — a running step, a green/red
    verdict, a prominent paused gate, a red failure — distinct at a glance (CLIUX-FR-009). With no
    styler the plain text is unchanged, byte-for-byte."""
    st = st or style.Styler()
    g = _glyphs(st)
    if ev.kind == "step":
        return f"  {st.head(g['step'])} {ev.stage:<8} {ev.step}"
    if ev.kind == "verdict":
        sym = st.ok(g["pass"]) if ev.detail == "pass" else st.err(g["fail"])
        return f"  {sym} {ev.stage:<8} {ev.step} → verdict {ev.detail.upper()}"
    if ev.kind == "gate-auto":
        return f"  {st.dim(g['auto'])} {ev.stage:<8} {ev.step} — intermediate gate auto-approved ({mode} mode)"
    if ev.kind == "gate-stop":
        fr = MANDATORY_GATES.get(ev.step)
        tag = f" — HUMAN GATE ({fr})" if fr else " — review gate (commit mode)"
        return f"  {st.warn(g['pause'])} {ev.stage:<8} {ev.step}{st.warn(tag)}: awaiting your commitment"
    if ev.kind == "failed":
        # "gates red" is emitted ONLY for a real deterministic-gate verdict; a dispatch/artifact
        # failure is reported distinctly and names the stage reached (RUNX-FR-010/011, RUNLIVE-FR-002).
        if ev.step == "gate_red" or ev.detail == "fail":
            return (
                f"  {st.err(g['fail'])} {st.err('gates red')} — the deterministic gate suite failed"
            )
        where = f" at {ev.stage}" if ev.stage else ""
        if ev.step == "artifact_missing":
            return f"  {st.err(g['fail'])} artifact missing{where} — {ev.detail}"
        if ev.step in ("artifact_absent", "artifact_unrecorded"):
            # The SRCX completion gate blocked the stage (SRCX-FR-014/015) — named, actionable.
            return f"  {st.err(g['fail'])} stage completion failed{where} — {ev.detail}"
        extra = f": {ev.detail}" if ev.detail else ""
        return (
            f"  {st.err(g['fail'])} dispatch failed{where} — a stage could not be executed "
            f"(not a gate verdict){extra}"
        )
    if ev.kind == "aborted":
        return f"  {st.dim(g['abort'])} aborted"
    if ev.kind == "done":
        return f"  {st.ok(g['done'])} lifecycle complete"
    return f"  {st.dim('·')} {ev.kind}"


# --------------------------------------------------------------------------- richer progress (dependency-free)
_TERMINAL_KINDS = ("gate-stop", "done", "failed", "aborted")


def tracker_frame(reached_stage: str, ev: Event, st: style.Styler | None = None) -> str:
    """One rendered progress frame (pure, testable): the stage tracker + the current activity line.

    On a TTY this is the persistent, colored "you are here" header — the full stage strip re-rendered
    with the running step alongside it (CLIUX-FR-008/009)."""
    return f"{render_tracker(reached_stage, st)}   {format_event(ev, '', st).strip()}"


class Tracker:
    """A dependency-free progress view for ``3pwr run``. On a TTY it redraws a colored, persistent
    stage header **in place** (``\\r`` + clear-line) as steps stream — the "you are here" view
    (CLIUX-FR-008/009); off a TTY (pipe / ``--json``) it falls back to the plain streamed
    ``format_event`` log with no ANSI/control codes (CLIUX-FR-011). No ``rich``/``curses`` dependency
    (INITX-NFR-004, CLIUX-FR-003). Color is tied to the TTY: the off-TTY log is always plain, even
    under ``THREEPOWERS_FORCE_COLOR``, so a captured/piped run never carries escapes (CLIUX-FR-011)."""

    def __init__(
        self, stream, mode: str, *, tty: Optional[bool] = None, st: style.Styler | None = None
    ) -> None:
        self._stream = stream
        self._mode = mode
        self._tty = bool(getattr(stream, "isatty", lambda: False)()) if tty is None else tty
        # Color only on the live in-place header (a TTY). The off-TTY log is ALWAYS plain — a disabled
        # styler wins even over a passed-in enabled one (e.g. color_mode: always) so a piped/captured
        # run never carries escapes (CLIUX-FR-011).
        self._st = (st if st is not None else style.styler(stream)) if self._tty else style.Styler()
        self._reached = "Discovery"
        self._live = False  # an in-place line is currently drawn

    def on_event(self, ev: Event) -> None:
        if ev.stage:
            self._reached = ev.stage
        if not self._tty:
            self._stream.write(format_event(ev, self._mode, self._st) + "\n")
            self._stream.flush()
            return
        if ev.kind in _TERMINAL_KINDS:
            if self._live:  # finalize the in-place line before the terminal detail
                self._stream.write("\r\033[2K")
                self._live = False
            self._stream.write(format_event(ev, self._mode, self._st) + "\n")
        else:
            self._stream.write("\r\033[2K" + tracker_frame(self._reached, ev, self._st))
            self._live = True
        self._stream.flush()
