"""The orchestration front-end — drive the whole lifecycle as one loop.

`3pwr run` walks the lifecycle, streaming progress, and — in ``auto`` mode — auto-continues past the
intermediate review gates while **always** stopping at the two mandatory human gates: ``review-spec``
(a human approves the spec) and ``signoff`` (a human signs off on the evidence + residual).
``commit`` mode stops at every gate.

The mode/gate/progress logic (``drive``) is pure given a *runner*. The live runner is the native
:class:`threepowers.runner.NativeRunner` — it dispatches each stage to a headless agent
directly and runs the gate suite in-process; a ``SimulatedRunner`` drives ``--dry-run`` and the tests.
Orchestration never enters the deterministic verdict.
"""

from __future__ import annotations

import io
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional, Protocol, TextIO

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import frame, style
from .lifecycle import STAGES, canonical_stage
from .verdict import GateResult

# The two human gates the spec makes mandatory — auto mode NEVER skips these.
# The values are the human-readable labels rendered at a gate pause and recorded in run state.
MANDATORY_GATES: dict[str, str] = {
    "review-spec": "spec approval",  # a human approves the spec before implementation begins
    "signoff": "sign-off",  # a human signs off on evidence + residual before advance
}

# The lifecycle steps, in order, mapped to their stage — the native executive walks these directly.
# kind: "action" (an executive/judiciary command), "verdict" (the deterministic gate suite), "gate" (human).
LIFECYCLE_STEPS: list[tuple[str, str, str]] = [
    ("discovery", "action", "Discovery"),
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
    # Optional structured payload an emitter attaches for a richer rendering — a gate-red event
    # carries the failed verdict dict + the run's resolved spec id. Rendering
    # degrades to the plain one-liner when absent, so every existing emitter stays valid.
    data: dict[str, Any] = field(default_factory=dict)


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
    detail: str = ""  # a human-readable failure detail (e.g. the missing-artifact message)
    events: list[Event] = field(default_factory=list)


@dataclass
class RunResult:
    """The driver's result after processing up to the next stop / completion."""

    status: str  # paused_at_gate | done | failed | aborted
    gate: str = ""
    gate_fr: str = ""  # the gate's human-readable label when the pause is a mandatory gate
    stage: str = ""
    verdict: str = (
        ""  # the deterministic-gate verdict when status == failed: "fail" = a real gate-red,
    )
    # "" = a dispatch/execution failure (not a gate verdict) — the honest-diagnostics split
    outcome: str = ""  # a finer failure class: dispatch_failed | artifact_missing | verdict_error
    detail: str = ""  # a human-readable failure detail (e.g. the missing-artifact message)

    @property
    def is_gate_red(self) -> bool:
        """True only when a failure carries a real deterministic-gate ``fail`` verdict."""
        return self.status == "failed" and self.verdict == "fail"

    @property
    def is_artifact_missing(self) -> bool:
        """True when the failure was a stage producing no declared artifact."""
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
    """The last action step committed as a checkpoint for ``spec_id``, else ''.

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
    """The last action step recorded COMPLETE for ``spec_id``, else ''.

    Completion is read from the signed ledger's ``run`` entries — a committed ``checkpoint``
    or the lightweight ``stage`` completion record written at stage success even with
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
    """Where a ``--resume`` should re-enter the lifecycle.

    The later of: the step after the last approved human ``pending_gate`` (the native executive's
    established behavior) and the
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
    including) the next gate. Used to record one per-stage dispatch provenance entry, so a
    fresh run records only the stages before the first human gate and a resume records only the next
    segment (no already-completed stage is re-recorded)."""
    return segment_actions_from(resume_index(resume_from) if resume_from else 0)


def segment_actions_from(start_index: int) -> list[tuple[str, str]]:
    """The action steps from ``start_index`` up to (not including) the next gate.

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
    # A live-delivering runner (NativeRunner with on_progress) has already surfaced each event the
    # moment it happened — replaying the batched history here would report it twice.
    live = bool(getattr(runner, "delivers_live_events", False))
    while True:
        if not live:
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
        # (gate-red vs a dispatch/artifact failure).
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
# Event glyphs, with an ASCII fallback for a stream that cannot encode the Unicode marks.
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
    so the same "you are here" view reads consistently live and in ``--status``.
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


def _first_actionable(gate: dict[str, Any]) -> str:
    """The first non-empty findings line of a failed gate — the line the user acts on.

    Missing-tool findings already lead with the install fix; adapter failures lead with the tool's
    first diagnostic. Empty when the gate carried no findings."""
    for finding in gate.get("findings") or []:
        line = str(finding).strip().splitlines()[0].strip() if str(finding).strip() else ""
        if line:
            return line
    return ""


def _gate_red_summary(ev: Event, st: style.Styler, g: dict[str, str]) -> str:
    """The structured gates-failed summary for a gate-red event.

    Renders one row per failed gate — ``name · tool`` plus its first actionable error line — from
    the verdict dict the emitter attached under ``ev.data['verdict']``, then the filled-in
    ``Resume:``/``Inspect:`` command hints carrying the run's resolved spec id. Returns ``""`` when
    the event carries no verdict (the plain one-liner then applies), so a simulated or legacy
    emitter renders exactly as before."""
    verdict = ev.data.get("verdict") or {}
    gates = verdict.get("gates") or []
    failed = [x for x in gates if x.get("status") == "fail"]
    if not failed:
        return ""
    spec_id = str(ev.data.get("spec_id") or verdict.get("spec_id") or "").strip()
    header = st.err(f"gates failed ({len(failed)} of {len(gates)}):")
    lines = [f"  {st.err(g['fail'])}  {header}"]
    width = max(len(str(x.get("gate", ""))) for x in failed)
    for x in failed:
        name = str(x.get("gate", "?"))
        tool = str(x.get("tool") or "").strip() or "?"
        row = f"     {name:<{width}} · {tool}"
        first = _first_actionable(x)
        if first:
            row += f"   ↳ {first}"
        lines.append(row)
    if spec_id:
        lines.append(f"     Resume:  3pwr run --resume --spec-id {spec_id}")
        lines.append(f"     Inspect: 3pwr gate run --id {spec_id}")
    return "\n".join(lines)


def format_event(ev: Event, mode: str, st: style.Styler | None = None) -> str:
    """Human-readable one-liner for a streamed event.

    With a color-enabled ``st`` the glyph and key words are colored — a running step, a green/red
    verdict, a prominent paused gate, a red failure — distinct at a glance. With no
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
        # failure is reported distinctly and names the stage reached.
        if ev.step == "gate_red" or ev.detail == "fail":
            summary = _gate_red_summary(ev, st, g)
            if summary:
                return summary
            return (
                f"  {st.err(g['fail'])} {st.err('gates red')} — the deterministic gate suite failed"
            )
        where = f" at {ev.stage}" if ev.stage else ""
        if ev.step == "artifact_missing":
            return f"  {st.err(g['fail'])} artifact missing{where} — {ev.detail}"
        if ev.step in ("artifact_absent", "artifact_unrecorded"):
            # The run-workspace completion gate blocked the stage — named, actionable.
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


# --------------------------------------------------------------------------- richer progress
_TERMINAL_KINDS = ("gate-stop", "done", "failed", "aborted")


def tracker_frame(reached_stage: str, ev: Event, st: style.Styler | None = None) -> str:
    """One rendered progress frame (pure, testable): the stage tracker + the current activity line.

    On a TTY this is the persistent, colored "you are here" header — the full stage strip re-rendered
    with the running step alongside it."""
    return f"{render_tracker(reached_stage, st)}   {format_event(ev, '', st).strip()}"


class Tracker:
    """The progress view for ``3pwr run``. On a capable TTY it anchors a **persistent
    live bar** at the bottom of the terminal — the eight stages with done/current/upcoming marks, the
    active step, and a heartbeat spinner with the elapsed time — while the event log and the
    dispatched agent's stdout print ABOVE it into ordinary, fully scrollable history. Off a TTY
    (pipe / ``--json``), under ``NO_COLOR``, or on a terminal that cannot support the bar, it
    degrades to the plain streamed ``format_event`` log with no ``\\r`` in-place redraws and no
    ANSI/control codes. The bar is rendered by ``rich`` behind the frame API; the machine
    contracts are unchanged.
    Color is tied to the TTY: the off-TTY log is always plain, even under
    ``THREEPOWERS_FORCE_COLOR``, so a captured/piped run never carries escapes."""

    def __init__(
        self,
        stream,
        mode: str,
        *,
        tty: Optional[bool] = None,
        st: style.Styler | None = None,
        subject: str = "",
        frame_view: Optional["frame.LiveFrame"] = None,
    ) -> None:
        self._stream = stream
        self._mode = mode
        self._subject = subject
        self._tty = bool(getattr(stream, "isatty", lambda: False)()) if tty is None else tty
        # Color only on the live TTY view. The off-TTY log is ALWAYS plain — a disabled
        # styler wins even over a passed-in enabled one (e.g. color_mode: always) so a piped/captured
        # run never carries escapes.
        self._st = (st if st is not None else style.styler(stream)) if self._tty else style.Styler()
        self._reached = "Discovery"
        # The live bar — only when the terminal can carry it;
        # ``frame_view`` lets tests inject one deterministically.
        self._frame = (
            frame_view
            if frame_view is not None
            else (frame.build(stream, st=self._st, subject=subject) if self._tty else None)
        )

    def close(self) -> None:
        """Tear the live bar down — last state left on screen, cursor restored.

        Idempotent, so the exception path (``finally``) and the terminal-event path converge."""
        if self._frame is not None:
            self._frame.close()

    def retitle(self, subject: str) -> None:
        """Adopt the run's resolved identity after construction.

        The tracker is built before the run workspace is allocated, so a workspace-derived spec id
        (the folder's NNN) arrives late; the live bar's title and its pause/resume
        hints must carry that derived value, never the pre-derivation default."""
        self._subject = subject
        if self._frame is not None:
            self._frame.retitle(subject)

    def begin(self) -> None:
        """Open the live bar eagerly — the stage strip and heartbeat are on screen BEFORE the first
        dispatch produces an event, so the run never looks frozen. A no-op off a
        TTY or on a degraded terminal (the plain log needs no opening)."""
        if self._frame is not None:
            self._frame.open()

    @property
    def live(self) -> bool:
        """Whether the live bar carries this run — the cue to route agent output through it."""
        return self._frame is not None

    def emit(self, line: str) -> None:
        """Print one content line into the terminal's ordinary flow — above the live bar when it is
        open (scrollback keeps the whole conversation), plain otherwise."""
        if self._frame is not None:
            self._frame.emit(line)
        else:
            self._stream.write(line.rstrip("\n") + "\n")
            self._stream.flush()

    def echo_sink(self) -> "_EchoSink":
        """A ``write``/``flush`` sink the runner's pump threads feed the dispatched agent's streamed
        stdout/stderr into — routed line-by-line through :meth:`emit` so the conversation prints
        above the live bar in real time instead of clobbering it."""
        return _EchoSink(self)

    def on_event(self, ev: Event) -> None:
        if ev.stage:
            self._reached = ev.stage
        if self._frame is not None:
            # The event history prints ABOVE the live bar, into ordinary scrollback, while the bar
            # reflects the current state.
            self._frame.emit(format_event(ev, self._mode, self._st))
            self._frame.note(
                kind=ev.kind,
                step=ev.step,
                stage=ev.stage,
                detail=ev.detail,
                reached=self._reached,
                spec_id=self._subject,
            )
            if ev.kind in _TERMINAL_KINDS:
                # A terminal event finalizes the bar: its last state stays on screen as ordinary
                # lines so the follow-up guidance prints in normal flow.
                self._frame.close()
            return
        # The plain streamed event log — off a TTY, and the degraded TTY path:
        # no in-place redraws, no pinned region.
        self._stream.write(format_event(ev, self._mode, self._st) + "\n")
        self._stream.flush()


class _EchoSink:
    """A line-buffered ``write``/``flush`` adapter routing a dispatched agent's streamed output
    through the tracker — above the live bar on a capable TTY, plain otherwise.

    Fed concurrently by the runner's stdout/stderr pump threads; the frame's lock serializes the
    actual terminal writes. Lines are emitted as they complete; ``flush`` releases a trailing
    unterminated line so no output is ever held back."""

    def __init__(self, tracker: Tracker) -> None:
        self._tracker = tracker
        self._buf = ""

    def write(self, s: str) -> None:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._tracker.emit(line)

    def flush(self) -> None:
        if self._buf:
            line, self._buf = self._buf, ""
            self._tracker.emit(line)


# --------------------------------------------------------------------------- gate pipeline view
# Tool-output noise the rendered gate view suppresses unless verbose.
# Node.js prints ExperimentalWarning banners on stderr for perfectly healthy runs.
_NOISE_MARKERS = ("ExperimentalWarning",)

# A failed gate's panel shows at most this many meaningful error lines.
PANEL_MAX_LINES = 30


def meaningful_lines(lines: Iterable[str], verbose: bool = False) -> list[str]:
    """Flatten gate findings into rendered lines, filtering noise unless ``verbose``.

    Each finding may span multiple lines; blank lines and known tool noise (Node.js
    ``ExperimentalWarning`` banners) are excluded by default and kept under verbose. Rendering
    only — the machine-readable verdict is never filtered."""
    out: list[str] = []
    for raw in lines:
        for ln in str(raw).splitlines() or [""]:
            if not verbose and (not ln.strip() or any(n in ln for n in _NOISE_MARKERS)):
                continue
            out.append(ln)
    return out


def _gate_elapsed(duration_ms: int) -> str:
    """A compact elapsed-time label for a finished gate row/panel — ``0.4 s`` style."""
    return f"{max(0, duration_ms) / 1000:.1f} s"


@dataclass
class _PipelineRow:
    """One gate's pipeline row state — running until its finish event lands."""

    gate: str
    tool: str = ""
    status: str = "running"  # running | pass | fail | skip
    duration_ms: int = 0
    errors: int = 0


class GatePipeline:
    """The per-gate pipeline view of a gate run.

    Consumes the gate engine's start/finish events (the ``gates.GateObserver`` seam) and renders
    one compact status row per gate — status glyph, ``gate · tool``, elapsed + summary. On a
    capable TTY with color the rows live inside a ``rich`` live region and update in place:
    ``○ gate · tool (running…)`` → ``✓ gate · tool 0.4 s`` / ``✗ gate · tool 1.2 s  2 errors``.
    Off a TTY or under ``NO_COLOR`` it degrades to sequential plain-text rows — one escape-free
    line per *finished* gate, no in-place updates. A ``--json`` run never
    constructs one, so the machine payload stays byte-identical. Presentation only: it never
    enters the verdict."""

    def __init__(
        self,
        stream: TextIO | None = None,
        st: style.Styler | None = None,
        *,
        verbose: bool = False,
        live: Optional[bool] = None,
    ) -> None:
        self._stream: TextIO = stream if stream is not None else sys.stdout
        self._st = st if st is not None else style.Styler()
        self._verbose = verbose
        if live is None:
            tty = bool(getattr(self._stream, "isatty", lambda: False)())
            live = self._st.enabled and tty
        self._live_mode = bool(live)
        self._rows: list[_PipelineRow] = []
        self._index: dict[str, int] = {}
        self._console: Optional[Console] = None
        self._live: Optional[Live] = None
        self._opened = False

    # ------------------------------------------------------------------ lifecycle
    def open(self) -> None:
        """Start the live region (TTY mode). Idempotent; a plain-mode open is a no-op."""
        if self._opened:
            return
        self._opened = True
        if not self._live_mode:
            return
        try:
            self._console = Console(file=self._stream, force_terminal=True, highlight=False)
            self._live = Live(
                self._table(), console=self._console, auto_refresh=False, transient=False
            )
            self._live.start(refresh=True)
        except (OSError, ValueError):
            # A broken stream must never take the gate run down — degrade to plain rows.
            self._live = None
            self._console = None
            self._live_mode = False

    def close(self) -> None:
        """Stop the live region, leaving the final rows on screen. Always safe to call twice."""
        if not self._opened:
            return
        self._opened = False
        try:
            if self._live is not None:
                self._live.stop()
        except (OSError, ValueError):
            pass
        self._live = None
        self._console = None

    def __enter__(self) -> "GatePipeline":
        self.open()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ gate events (GateObserver)
    def gate_started(self, gate: str, tool: str) -> None:
        """Show ``gate`` as running (live mode); plain mode waits for the finish."""
        self._index[gate] = len(self._rows)
        self._rows.append(_PipelineRow(gate=gate, tool=tool))
        self._refresh()

    def gate_finished(self, result: GateResult) -> None:
        """Fold the gate's result into its row — update in place live, one plain line otherwise."""
        i = self._index.get(result.gate)
        if i is None:
            i = len(self._rows)
            self._index[result.gate] = i
            self._rows.append(_PipelineRow(gate=result.gate))
        row = self._rows[i]
        if result.tool:
            row.tool = result.tool
        row.status = result.status
        row.duration_ms = int(result.duration_ms or 0)
        row.errors = len(meaningful_lines(result.findings)) if result.status == "fail" else 0
        if self._live_mode:
            self._refresh()
            return
        self._stream.write(self._row_text(row) + "\n")
        self._stream.flush()

    # ------------------------------------------------------------------ rendering
    def _row_cells(self, row: _PipelineRow) -> tuple[str, str, str]:
        """The row's (glyph, label, detail) cells — a pure function of the row and the styler."""
        st = self._st
        label = f"{row.gate} · {row.tool}" if row.tool else row.gate
        if row.status == "running":
            glyph = st.dim("o" if st.ascii_only else "○")
            return glyph, label, st.dim("(running…)" if not st.ascii_only else "(running...)")
        # A skipped spec_integrity (and every skip) carries the dim info glyph, never ✗;
        # pass/fail keep the shared status vocabulary.
        glyph = st.mark(row.status)
        detail = _gate_elapsed(row.duration_ms)
        if row.status == "fail" and row.errors:
            detail += f"  {row.errors} error{'' if row.errors == 1 else 's'}"
        elif row.status == "skip":
            detail = st.dim("skipped")
        return glyph, label, detail

    def _row_text(self, row: _PipelineRow) -> str:
        glyph, label, detail = self._row_cells(row)
        return f"  {glyph} {label}  {detail}"

    def _table(self) -> Table:
        """The live region's renderable: one three-column grid row per gate."""
        table = Table.grid(padding=(0, 1))
        for row in self._rows:
            glyph, label, detail = self._row_cells(row)
            table.add_row(
                Text.from_ansi("  " + glyph), Text.from_ansi(label), Text.from_ansi(detail)
            )
        return table

    def _refresh(self) -> None:
        if self._live is None:
            return
        try:
            self._live.update(self._table(), refresh=True)
        except (OSError, ValueError):
            pass  # never let a repaint take the gate run down


# ------------------------------------------------------------------ remediation guidance
# Per-gate honest remediation, keyed by gate name: (what a failure means, the honest way out).
# The framing is always "make the code satisfy the check" — never "make the check pass" — so the
# guidance can never read as an instruction to weaken a gate. Purely presentational: it renders
# in the human failure panels only and never enters the verdict dict, the ledger, or the
# machine (--json) payload. A gate result may override the fix half with a finding-specific
# hint via ``details["remediation"]`` (e.g. the fixed version a vulnerability scanner reports).
_GENERIC_GUIDANCE: tuple[str, str] = (
    "this gate's check failed — the findings above say exactly where",
    "make the code satisfy the check; never weaken the check itself",
)

GATE_GUIDANCE: dict[str, tuple[str, str]] = {
    "format": (
        "the code's formatting drifts from the configured style",
        "run the auto-fix command above — formatting is safely auto-fixable",
    ),
    "lint": (
        "the linter found rule violations in the code",
        "fix each finding in the code so it satisfies the rule "
        "(the auto-fix command above handles the safely fixable ones)",
    ),
    "types": (
        "the type checker found real type errors",
        "make the code satisfy its declared types — correct the code or the annotations",
    ),
    "tests": (
        "the test suite has failing tests",
        "make the code satisfy the failing tests and the spec they trace to — never weaken a test",
    ),
    "gate_gaming": (
        "a check appears weakened — a lost assertion or an added waiver; review before accepting",
        "restore the weakened check and make the code satisfy it; only a deliberate, justified "
        "exception belongs in a recorded deviation, which 3pwr run and 3pwr advance both honour",
    ),
    "dependency_scan": (
        "a dependency carries a known vulnerability",
        "upgrade the dependency to a fixed version; a vetted advisory can be accepted in "
        ".3powers/config/scan.yaml under advisories: (id + reason, optional until expiry — "
        "every acceptance is reported in the gate output); a recorded deviation is honoured "
        "by both 3pwr run and 3pwr advance",
    ),
}

# The findings ceiling per gate inside the coder hand-back prompt — enough to act on,
# small enough to paste.
HANDBACK_MAX_FINDINGS = 5


def coder_handback(verdict: Mapping[str, Any]) -> str:
    """The copy-pasteable coder hand-back prompt for a failed verdict — deterministic text.

    Names every failed gate and its first findings and instructs an honest fix, consistent
    with the implement-stage instructions ("never weaken a gate; make the code satisfy the
    spec"). It never instructs weakening, silencing, or removing a check. Pure and
    presentation-only: built from the verdict *dict* (the ``Verdict.to_dict()`` shape), it
    never mutates it and never enters the ledger or the machine payload. Empty string when
    nothing failed."""
    failed = [g for g in (verdict.get("gates") or []) if g.get("status") == "fail"]
    if not failed:
        return ""
    lines = [
        "The deterministic gate suite rejected this change. Make the code satisfy the spec",
        "and every failed check below. Never weaken a gate: fix the code, not the check —",
        "keep every existing test, assertion, and check configuration intact.",
        "",
        "Failed gates:",
    ]
    for g in failed:
        name = str(g.get("gate", "?"))
        tool = str(g.get("tool") or "").strip()
        lines.append(f"- {name} · {tool}" if tool else f"- {name}")
        findings = meaningful_lines(g.get("findings") or [])
        for finding in findings[:HANDBACK_MAX_FINDINGS]:
            lines.append(f"    {finding}")
        hidden = len(findings) - HANDBACK_MAX_FINDINGS
        if hidden > 0:
            lines.append(f"    … plus {hidden} more finding{'' if hidden == 1 else 's'}")
    lines.extend(
        [
            "",
            "For each finding, correct the underlying code so it genuinely satisfies the",
            "check, keep the change minimal and traceable to the spec, then re-run the",
            "failed checks and report the honest result.",
        ]
    )
    return "\n".join(lines)


def _remediation_lines(gate: Mapping[str, Any]) -> list[str]:
    """The per-gate remediation tail of a failure panel — guidance plus the labelled last resort.

    Resolves the fix hint from ``details["remediation"]`` (a finding-specific hint the gate
    supplied) when present, else the static :data:`GATE_GUIDANCE` table, with a generic
    default for unknown gates. Presentation only — never enters the verdict."""
    name = str(gate.get("gate", "?"))
    meaning, fix_hint = GATE_GUIDANCE.get(name, _GENERIC_GUIDANCE)
    specific = str((gate.get("details") or {}).get("remediation") or "").strip()
    return [
        f"↳ what it means: {meaning}",
        f"↳ fix: {specific or fix_hint}",
        "↳ last resort — only if this is a deliberate, justified exception:",
        f'    3pwr deviation --gate {name} --approver <you> --note "<why>" [--until <date>]',
    ]


def _panel_body_lines(
    gate: Mapping[str, Any], verbose: bool = False, waiver: str = ""
) -> list[str]:
    """A failed gate's panel body: meaningful error lines trimmed to :data:`PANEL_MAX_LINES`
    with a truncation note, then the configured auto-fix hint when present, then the waiver
    annotation when the gate is covered by an active deviation, then the honest remediation
    tail (what the failure means, the honest fix, and the deviation last resort).

    Scanner gates (dependency/secret scan) already carry one finding per line — ID plus
    package/file (and a remediation hint when the gate details supply one) — so the generic
    line path renders them one per line. ``waiver`` is a pre-built human annotation line
    (e.g. "↳ waived by active deviation seq=1 (approver: …)"); it never touches the verdict
    dict itself."""
    lines = meaningful_lines(gate.get("findings") or [], verbose)
    if not lines:
        lines = ["non-zero exit — the tool reported no output"]
    shown = lines[:PANEL_MAX_LINES]
    hidden = len(lines) - len(shown)
    if hidden > 0:
        shown.append(f"… {hidden} more line{'' if hidden == 1 else 's'}")
    fix = (gate.get("details") or {}).get("fix_cmd")
    if fix:
        shown.append(f"↳ auto-fix: {fix}")
    if waiver:
        shown.append(waiver)
    shown.extend(_remediation_lines(gate))
    return shown


def _render_panel(
    gate: Mapping[str, Any],
    st: style.Styler,
    *,
    verbose: bool,
    width: Optional[int],
    waiver: str = "",
) -> str:
    """One failed gate's panel — a rich panel with a dim ``gate · tool`` header on a color TTY,
    plain indented text otherwise."""
    name = str(gate.get("gate", "?"))
    tool = str(gate.get("tool") or "").strip() or "?"
    elapsed = _gate_elapsed(int(gate.get("duration_ms") or 0))
    title = f"{name} · {tool}  {elapsed}"
    body = _panel_body_lines(gate, verbose, waiver)
    if st.enabled:
        buf = io.StringIO()
        console = Console(
            file=buf,
            force_terminal=True,
            width=width if width is not None else style.term_width(),
            highlight=False,
        )
        console.print(
            Panel(
                Text("\n".join(f"  {ln}" for ln in body)),
                title=Text(title, style="dim"),
                title_align="left",
                border_style="dim",
            )
        )
        return buf.getvalue().rstrip("\n")
    ch = "-" if st.ascii_only else "─"
    head = f"  {ch * 2} {title}"
    return "\n".join([head, *(f"    {ln}" for ln in body)])


def failure_panels(
    verdict: Mapping[str, Any],
    st: style.Styler | None = None,
    *,
    verbose: bool = False,
    width: Optional[int] = None,
    waivers: Optional[Mapping[str, str]] = None,
) -> str:
    """The post-run failure surface: one panel per FAILED gate of ``verdict``, followed by one
    coder hand-back block (a copy-pasteable prompt for the coding agent plus the re-dispatch
    command) covering all failed gates.

    Rendered after the live pipeline exits; replaces the former bottom "failures:" block. Takes
    the verdict *dict* (the ``Verdict.to_dict()`` shape the emitters already carry) so run-path
    and gate-run callers share one renderer. Empty string when nothing failed. Degrades to plain
    indented text with a disabled styler — never an ANSI byte off a color TTY. Human output
    only: callers never route it through ``--json``, and nothing here mutates the verdict.

    ``waivers`` maps a failed gate's name to a pre-built waiver annotation line (a red gate
    covered by an active deviation); the annotation is human rendering only and never mutates
    the verdict mapping."""
    st = st or style.Styler()
    failed = [g for g in (verdict.get("gates") or []) if g.get("status") == "fail"]
    if not failed:
        return ""
    panels = "\n".join(
        _render_panel(
            g,
            st,
            verbose=verbose,
            width=width,
            waiver=(waivers or {}).get(str(g.get("gate", "")), ""),
        )
        for g in failed
    )
    return panels + "\n" + _handback_block(verdict, st)


def _handback_block(verdict: Mapping[str, Any], st: style.Styler) -> str:
    """The rendered coder hand-back section — the prompt indented under a dim header, then the
    re-dispatch command. Presentation only; empty when nothing failed."""
    prompt = coder_handback(verdict)
    if not prompt:
        return ""
    spec_id = str(verdict.get("spec_id") or "").strip() or "<spec-id>"
    lines = [
        "  " + st.dim("hand back to your coding agent — copy-paste:"),
        *(f"    {ln}" for ln in prompt.splitlines()),
        f"  re-dispatch: 3pwr run --resume --spec-id {spec_id}",
    ]
    return "\n".join(lines)
