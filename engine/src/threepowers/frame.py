"""The persistent live run bar — a bottom-anchored status bar over ordinary scrollback.

An earlier tracker redrew ONE line in place; a first cut of run steering pinned a header over a
DECSTBM scroll region — but terminals DISCARD lines scrolled out of a partial region, so the
streamed agent conversation never reached scrollback. This module renders a **bottom-anchored live
bar**: the eight lifecycle stages with done / current / upcoming marks, the active step, a
heartbeat spinner with the elapsed time, and the gate guidance stay painted on the
LAST rows of the terminal, while the event log and the dispatched agent's stdout print ABOVE it into
the terminal's ordinary flow — the full conversation lands in scrollback, nothing is lost.

The rendering engine is ``rich``: :class:`LiveFrame` wraps a non-highlighting
``rich.console.Console`` and a ``rich.live.Live`` region pinned at the bottom of the terminal.
Every escape byte is emitted by rich — the hand-rolled cursor-math implementation is gone —
and **no alternate screen buffer and no scroll region** are ever used, preserving
scrollback exactly as before. Bar content is still a pure function of the frame state, the width,
and the styler: identical inputs yield identical text; the heartbeat is a
human-output-only decoration on top.

Degradation is total and safe: off a TTY, under
``NO_COLOR``, on a dumb/width-unknown terminal, or below the minimum size, :func:`build` yields no
bar and the caller keeps the plain streamed event log — no ``\\r`` redraws, no escapes. Teardown
always restores the cursor and leaves the bar's last state as ordinary lines.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping, Optional, TextIO

from rich.console import Console
from rich.live import Live
from rich.text import Text

from . import style
from .lifecycle import STAGES

# The live bar's fixed height: top border, stage strip, status, guidance, bottom border.
BAR_HEIGHT = 5
# Below this the terminal "cannot support the live bar" and the plain log applies.
MIN_COLS = 40
MIN_ROWS = BAR_HEIGHT + 4

# How often the heartbeat repaints while a stage runs — human-only; tests drive it directly.
HEARTBEAT_SECONDS = 0.12

_MARK = {"done": "✓", "current": "▶", "todo": "·"}
_MARK_ASCII = {"done": "v", "current": ">", "todo": "."}

_SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
_SPINNER_ASCII = "|/-\\"


def spinner_glyph(index: int, ascii_only: bool = False) -> str:
    """The heartbeat spinner's frame for ``index`` — pure and cyclic."""
    frames = _SPINNER_ASCII if ascii_only else _SPINNER
    return frames[index % len(frames)]


def format_elapsed(seconds: float) -> str:
    """A compact human elapsed time — ``42s`` under a minute, ``3m 07s`` beyond it."""
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    return f"{s // 60}m {s % 60:02d}s"


# Every terminal control sequence in one alternation: CSI, OSC (BEL- or ST-terminated), then any
# remaining two-byte escape (ESC 7 / ESC 8 / ESC c …) or a trailing lone ESC. Strip/sanitize
# matchers only — never used to construct output.
_CTRL_RE = re.compile(r"\033\[[0-9;:?]*[ -/]*[@-~]|\033\][^\033\a]*(?:\a|\033\\)?|\033.?")
_SGR_RE = re.compile(r"\033\[[0-9;]*m")


def _printable(text: str) -> str:
    """``text`` with every C0 control (except tab) and DEL removed — the plain-text filter
    :func:`sanitize_line` applies between the SGR runs it preserves."""
    return "".join(ch for ch in text if ch == "\t" or (ch >= " " and ch != "\x7f"))


def sanitize_line(text: str) -> str:
    """``text`` with every control sequence that could move the cursor or clear the screen removed.

    SGR color sequences (``CSI … m``) pass through so a dispatched agent's colored output stays
    colored; everything else — cursor addressing, erases, OSC titles, ``\\r``, other C0 controls —
    is stripped, so a streamed line can never corrupt the live bar or the terminal state.
    Pure."""
    text = _CTRL_RE.sub(lambda m: m.group(0) if m.group(0).endswith("m") else "", text)
    parts: list[str] = []
    pos = 0
    for m in _SGR_RE.finditer(text):
        parts.append(_printable(text[pos : m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(_printable(text[pos:]))
    return "".join(parts)


@dataclass(frozen=True)
class FrameState:
    """What the pinned frame shows — a pure value the renderer maps to bytes."""

    reached: str = "Discovery"  # the lifecycle stage the run has reached
    status: str = "running"  # running | paused | failed | done | aborted
    activity: str = ""  # the active step / gate / failure class
    guidance: str = ""  # the gate action guidance, shown while paused


def stage_marks(reached: str) -> list[tuple[str, str]]:
    """Each stage's mark for the strip — a deterministic function of the reached stage:
    stages before it are done, the reached one current, the rest upcoming."""
    idx = STAGES.index(reached) if reached in STAGES else -1
    out: list[tuple[str, str]] = []
    for i, s in enumerate(STAGES):
        out.append((s, "done" if i < idx else "current" if i == idx else "todo"))
    return out


def next_state(
    state: FrameState, *, kind: str, step: str, stage: str, detail: str, reached: str, spec_id: str
) -> FrameState:
    """Fold one streamed run event into the frame state (pure).

    The running, paused-at-gate, and failed states are distinct, consistent with the failure
    taxonomy the event stream already carries; a paused gate picks up the actionable guidance."""
    if kind == "step":
        return replace(state, reached=reached, status="running", activity=step, guidance="")
    if kind == "verdict":
        act = f"{step} → verdict {detail.upper()}" if detail else step
        return replace(state, reached=reached, status="running", activity=act, guidance="")
    if kind == "gate-auto":
        return replace(
            state,
            reached=reached,
            status="running",
            activity=f"{step} (auto-approved)",
            guidance="",
        )
    if kind == "gate-stop":
        # Compact one-line guidance — the full copy-pasteable commands print in the body below;
        # the frame names the three actions at a glance.
        guidance = (
            f"approve `3pwr run --resume --spec-id {spec_id}` · reject `3pwr abort` "
            f'· revise `--revise "<feedback>"`'
        )
        return replace(
            state,
            reached=reached,
            status="paused",
            activity=f"HUMAN GATE '{step}'",
            guidance=guidance,
        )
    if kind == "failed":
        cls = step or "failed"
        return replace(state, reached=reached, status="failed", activity=cls, guidance="")
    if kind == "aborted":
        return replace(state, reached=reached, status="aborted", activity="aborted", guidance="")
    if kind == "done":
        return replace(
            state, reached=reached, status="done", activity="lifecycle complete", guidance=""
        )
    return replace(state, reached=reached)


def _clip(text: str, width: int) -> str:
    """Clip ``text`` to a visible ``width`` — ANSI-safe only for the plain tail it may cut."""
    if style.visible_len(text) <= width:
        return text
    # Only ever called on strips assembled from whole cells (below) or plain text, so a plain cut
    # cannot split an escape sequence.
    return text[: max(0, width - 1)] + "…"


def _strip_line(reached: str, width: int, st: style.Styler) -> str:
    """The stage strip: whole colored cells are added while they fit, so no escape is ever split."""
    marks = _MARK_ASCII if st.ascii_only else _MARK
    cells: list[str] = []
    plain_len = 0
    for stage_name, mark in stage_marks(reached):
        plain = f"{marks[mark]} {stage_name}"
        added = len(plain) + (2 if cells else 0)
        if plain_len + added > width - 2:
            break
        plain_len += added
        if mark == "done":
            cells.append(st.ok(plain))
        elif mark == "current":
            cells.append(st.head(plain))
        else:
            cells.append(st.dim(plain))
    return " " + "  ".join(cells)


def frame_lines(
    state: FrameState,
    width: int,
    st: style.Styler,
    subject: str = "",
    *,
    spinner: str = "",
    elapsed: str = "",
) -> list[str]:
    """Render the live bar — exactly ``BAR_HEIGHT`` lines, pure in its inputs.

    ``spinner``/``elapsed`` decorate the running status line (the heartbeat); left
    empty they leave the line exactly as before, so rendering stays a pure function of its
    arguments."""
    width = max(MIN_COLS, width)
    bar = "-" if st.ascii_only else "─"
    title = f"{bar * 2} 3Powers · run"
    if subject:
        title += f" · {subject}"
    title += " "
    top = st.dim(_clip(title + bar * max(0, width - len(title)), width))
    strip = _strip_line(state.reached, width, st)
    if state.status == "paused":
        status = st.warn(_clip(f" ⏸ {state.activity} — awaiting your decision", width))
    elif state.status == "failed":
        status = st.err(_clip(f" ✗ failed — {state.activity}", width))
    elif state.status == "done":
        status = st.ok(_clip(f" ✓ {state.activity}", width))
    elif state.status == "aborted":
        status = st.dim(_clip(f" ⊘ {state.activity}", width))
    else:
        glyph = spinner or "▶"
        running = f" {glyph} running {state.activity}" if state.activity else f" {glyph} running"
        if elapsed:
            running += f" · {elapsed}"
        status = st.head(_clip(running, width))
    guidance = st.dim(_clip(f" {state.guidance}", width)) if state.guidance else ""
    bottom = st.dim(bar * width)
    return [top, strip, status, guidance, bottom]


# --------------------------------------------------------------------------- capability probing
def _size(stream: TextIO, fallback: tuple[int, int] = (0, 0)) -> tuple[int, int]:
    """(columns, rows) of the terminal behind ``stream``; the fallback when undetectable."""
    try:
        ts = os.get_terminal_size(stream.fileno())
        return ts.columns, ts.lines
    except (OSError, ValueError, AttributeError):
        pass
    try:
        ts2 = shutil.get_terminal_size(fallback)
        return ts2.columns, ts2.lines
    except (OSError, ValueError):
        return fallback


def supported(
    stream: TextIO,
    *,
    tty: Optional[bool] = None,
    env: Optional[Mapping[str, str]] = None,
    size: Optional[tuple[int, int]] = None,
) -> bool:
    """Whether ``stream``'s terminal can carry the live bar.

    False off a TTY, under ``NO_COLOR``, on a dumb/unknown ``TERM``, or when the size is unknown or
    below the minimum — the caller then keeps the plain streamed event log. Never raises."""
    e: Mapping[str, str] = os.environ if env is None else env
    if tty is None:
        try:
            tty = bool(stream.isatty())
        except (AttributeError, ValueError, OSError):
            tty = False
    if not tty:
        return False
    if e.get("NO_COLOR") is not None:
        return False
    if e.get("TERM", "").strip().lower() in ("", "dumb"):
        return False
    cols, rows = size if size is not None else _size(stream)
    return cols >= MIN_COLS and rows >= MIN_ROWS


class LiveFrame:
    """The bottom-anchored live bar on one terminal stream.

    A thin lifecycle wrapper around ``rich.live.Live`` on a non-highlighting
    ``rich.console.Console``: ``open`` starts the live display (rich hides the cursor and pins the
    bar's rows at the bottom); ``emit`` prints a content line ABOVE the bar — rich moves the live
    region down and the (sanitized) line lands in the terminal's ordinary flow, so the full event
    log and agent conversation stay in scrollback; ``note`` folds a run event into the state and
    refreshes; :meth:`heartbeat` advances the spinner + elapsed time while a stage runs (a
    background ticker drives it in production, tests call it directly); ``close`` stops the live
    display, leaving the bar's last state as ordinary lines with the cursor restored, idempotently,
    so exception paths and normal exits converge. One re-entrant lock serializes
    every write — the event thread, the agent-output pump threads, and the ticker never interleave.
    No scroll region and no alternate screen buffer are ever used: DECSTBM discards lines scrolled
    out of a partial region, which is exactly the history loss this design replaces.
    A ``SIGWINCH`` re-lays the bar out."""

    def __init__(
        self,
        stream: TextIO,
        *,
        st: style.Styler,
        subject: str = "",
        size: Optional[tuple[int, int]] = None,
        heartbeat: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._stream = stream
        self._st = st
        self._subject = subject
        self._fixed_size = size
        self._cols, self._rows = size if size is not None else (0, 0)
        self._state = FrameState()
        self._open = False
        self._prev_winch: Any = None
        self._lock = threading.RLock()
        self._clock = clock
        self._spin = 0
        self._since: Optional[float] = None
        self._heartbeat = max(0.0, float(heartbeat))
        self._stop = threading.Event()
        self._ticker: Optional[threading.Thread] = None
        self._console: Optional[Console] = None
        self._live: Optional[Live] = None

    # ------------------------------------------------------------------ lifecycle
    def open(self) -> None:
        """Start the live display — the bar appears at the bottom, cursor hidden."""
        with self._lock:
            if self._open:
                return
            self._cols, self._rows = (
                self._fixed_size if self._fixed_size is not None else _size(self._stream, (80, 24))
            )
            self._open = True
            if self._since is None:
                self._since = self._clock()
            try:
                # A dedicated non-highlighting console on the run's stream: agent content passes
                # through unmodified, and rich owns every escape byte.
                self._console = Console(
                    file=self._stream,
                    force_terminal=True,
                    width=self._cols,
                    height=self._rows,
                    highlight=False,
                )
                # auto_refresh off: repaints happen deterministically on note/emit/heartbeat —
                # the frame's own ticker drives the heartbeat cadence.
                self._live = Live(
                    self._bar(), console=self._console, auto_refresh=False, transient=False
                )
                self._live.start(refresh=True)
            except (OSError, ValueError):
                pass  # never let the bar take the run down
        self._install_winch()
        self._start_ticker()

    def close(self) -> None:
        """Leave the bar's last state on screen as ordinary lines and restore the cursor —
        always safe to call twice."""
        with self._lock:
            if not self._open:
                return
            self._open = False
            try:
                if self._live is not None:
                    self._live.stop()
            except (OSError, ValueError):
                pass  # a vanished stream must not raise on teardown
            self._live = None
            self._console = None
        self._stop_ticker()
        self._restore_winch()

    # ------------------------------------------------------------------ events
    def note(
        self, *, kind: str, step: str, stage: str, detail: str, reached: str, spec_id: str
    ) -> None:
        """Fold one streamed event into the frame and repaint. Opens lazily."""
        with self._lock:
            prev = self._state
            self._state = next_state(
                self._state,
                kind=kind,
                step=step,
                stage=stage,
                detail=detail,
                reached=reached,
                spec_id=spec_id,
            )
            if (self._state.activity, self._state.status) != (prev.activity, prev.status):
                self._spin = 0
                self._since = self._clock()
            if not self._open:
                self.open()
            else:
                self._repaint()

    def emit(self, text: str) -> None:
        """Print content ABOVE the bar, into the terminal's ordinary flow.

        The event log and the dispatched agent's whole conversation stay in scrollback — rich
        prints the sanitized line(s) above the live region and repaints the bar below them.
        Thread-safe: the runner's pump threads and the event thread share the
        frame's lock. On a closed frame this is a plain write, so no caller ever needs to care
        about the bar's lifecycle."""
        payload = "\n".join(sanitize_line(ln) for ln in text.split("\n"))
        with self._lock:
            try:
                if self._open and self._console is not None and self._live is not None:
                    # Text.from_ansi keeps the agent's SGR color; the non-highlighting console
                    # never reformats the content; the explicit refresh flushes the
                    # printed line above the bar deterministically.
                    self._console.print(Text.from_ansi(payload))
                    self._live.refresh()
                else:
                    self._stream.write(payload + "\n")
                    self._stream.flush()
            except (OSError, ValueError):
                pass  # never let output routing take the run down

    def heartbeat(self) -> None:
        """Advance the running spinner one frame and repaint — driven by the
        background ticker in production, called directly (deterministically) in tests."""
        with self._lock:
            if not self._open or self._state.status != "running":
                return
            self._spin += 1
            self._repaint()

    def retitle(self, subject: str) -> None:
        """Adopt a late-resolved run identity as the bar's title subject.

        The run workspace's NNN is derived after the frame is constructed; the bar's title must
        show the derived id, not the pre-derivation default. Repaints when the bar is open."""
        with self._lock:
            self._subject = subject
            if self._open:
                self._repaint()

    # ------------------------------------------------------------------ rendering
    def _bar(self) -> Text:
        """The bar's ``BAR_HEIGHT`` rows as the live region's renderable — the pure
        :func:`frame_lines` text, parsed so its styler color survives rich's rendering."""
        running = self._state.status == "running"
        spin = spinner_glyph(self._spin, self._st.ascii_only) if running else ""
        elapsed = (
            format_elapsed(self._clock() - self._since)
            if running and self._since is not None
            else ""
        )
        lines = frame_lines(
            self._state, self._cols, self._st, self._subject, spinner=spin, elapsed=elapsed
        )
        return Text.from_ansi("\n".join(lines), no_wrap=True)

    def _repaint(self) -> None:
        """Refresh the live region with the current state (lock held by the caller)."""
        try:
            if self._live is not None:
                self._live.update(self._bar(), refresh=True)
        except (OSError, ValueError):
            pass  # never let a repaint take the run down

    def resize(self) -> None:
        """Re-lay the bar out after a terminal resize."""
        with self._lock:
            if not self._open:
                return
            self._cols, self._rows = (
                self._fixed_size if self._fixed_size is not None else _size(self._stream, (80, 24))
            )
            if self._console is not None:
                self._console.width = self._cols
                self._console.height = self._rows
            self._repaint()

    # ------------------------------------------------------------------ heartbeat ticker
    def _start_ticker(self) -> None:
        if self._heartbeat <= 0 or self._ticker is not None:
            return
        self._stop.clear()

        def _loop() -> None:
            while not self._stop.wait(self._heartbeat):
                self.heartbeat()

        self._ticker = threading.Thread(target=_loop, daemon=True, name="3pwr-live-bar")
        self._ticker.start()

    def _stop_ticker(self) -> None:
        self._stop.set()
        ticker, self._ticker = self._ticker, None
        if ticker is not None and ticker is not threading.current_thread():
            ticker.join(timeout=1)

    # ------------------------------------------------------------------ resize signal (best-effort)
    def _install_winch(self) -> None:
        if not hasattr(signal, "SIGWINCH"):
            return
        try:
            self._prev_winch = signal.getsignal(signal.SIGWINCH)
            signal.signal(signal.SIGWINCH, lambda *_a: self.resize())
        except (ValueError, OSError, RuntimeError):
            self._prev_winch = None  # not the main thread / unsupported — resize stays manual

    def _restore_winch(self) -> None:
        if self._prev_winch is None or not hasattr(signal, "SIGWINCH"):
            return
        try:
            signal.signal(signal.SIGWINCH, self._prev_winch)
        except (ValueError, OSError, RuntimeError):
            pass
        self._prev_winch = None


def build(
    stream: TextIO,
    *,
    st: style.Styler,
    subject: str = "",
    tty: Optional[bool] = None,
    env: Optional[Mapping[str, str]] = None,
    size: Optional[tuple[int, int]] = None,
    heartbeat: float = HEARTBEAT_SECONDS,
) -> Optional[LiveFrame]:
    """A :class:`LiveFrame` when the terminal supports the live bar, else ``None``.

    The production path gets the heartbeat ticker; tests constructing
    :class:`LiveFrame` directly stay tick-free and deterministic."""
    if not supported(stream, tty=tty, env=env, size=size):
        return None
    return LiveFrame(stream, st=st, subject=subject, size=size, heartbeat=heartbeat)
