"""The persistent live run frame — a pinned stage header over a reserved scroll region (STEER, spec 019).

CLIUX's tracker redrew ONE line in place; the dispatched agent's stdout scrolled it straight
off-screen. This module advances that to a **persistent pinned frame** (STEER-FR-012): the eight
lifecycle stages with done / current / upcoming marks, the active step, and a running indicator stay
pinned at the top of the terminal while all agent stdout streams in a reserved scroll region below —
so a glance always answers "which stage, what's done, is it moving?".

The implementation stays inside the CLIUX boundary (STEER-FR-014): **no third-party dependency, no
network, no alternate screen buffer** — only ANSI control sequences the terminal already understands
(DECSTBM scroll region + cursor addressing). Rendering is a pure function of the frame state, the
width, and the styler (STEER-NFR-003): identical inputs yield identical bytes.

Degradation is total and safe (STEER-FR-015, STEER-NFR-004): off a TTY, under ``NO_COLOR``, on a
dumb/width-unknown terminal, or below the minimum size, :func:`build` yields no frame and the caller
keeps the plain streamed event log — no ``\\r`` redraws, no escapes. Teardown always resets the
scroll region and restores the cursor (STEER-FR-016), and a resize re-lays the frame out.
"""

from __future__ import annotations

import os
import shutil
import signal
from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, TextIO

from . import style
from .lifecycle import STAGES

# The pinned header's fixed height: top border, stage strip, status, guidance, bottom border.
HEADER_HEIGHT = 5
# Below this the terminal "cannot support the pinned region" and the plain log applies (STEER-FR-015).
MIN_COLS = 40
MIN_ROWS = HEADER_HEIGHT + 4

_MARK = {"done": "✓", "current": "▶", "todo": "·"}
_MARK_ASCII = {"done": "v", "current": ">", "todo": "."}


@dataclass(frozen=True)
class FrameState:
    """What the pinned frame shows — a pure value the renderer maps to bytes (STEER-NFR-003)."""

    reached: str = "Discovery"  # the lifecycle stage the run has reached
    status: str = "running"  # running | paused | failed | done | aborted
    activity: str = ""  # the active step / gate / failure class
    guidance: str = ""  # the gate action guidance, shown while paused (STEER-FR-013)


def stage_marks(reached: str) -> list[tuple[str, str]]:
    """Each stage's mark for the strip — a deterministic function of the reached stage
    (STEER-FR-012's property): stages before it are done, the reached one current, the rest upcoming."""
    idx = STAGES.index(reached) if reached in STAGES else -1
    out: list[tuple[str, str]] = []
    for i, s in enumerate(STAGES):
        out.append((s, "done" if i < idx else "current" if i == idx else "todo"))
    return out


def next_state(
    state: FrameState, *, kind: str, step: str, stage: str, detail: str, reached: str, spec_id: str
) -> FrameState:
    """Fold one streamed run event into the frame state (pure — STEER-FR-013).

    The running, paused-at-gate, and failed states are distinct, consistent with the AUTOX failure
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
        # Compact one-line guidance — the full copy-pasteable commands print in the body below
        # (STEER-FR-005); the frame names the three actions at a glance (STEER-FR-013).
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


def frame_lines(state: FrameState, width: int, st: style.Styler, subject: str = "") -> list[str]:
    """Render the pinned header — exactly ``HEADER_HEIGHT`` lines, pure in its inputs (STEER-NFR-003)."""
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
        running = f" ▶ running {state.activity}" if state.activity else " ▶ running"
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
    """Whether ``stream``'s terminal can carry the pinned region (STEER-FR-015).

    False off a TTY, under ``NO_COLOR``, on a dumb/unknown ``TERM``, or when the size is unknown or
    below the minimum — the caller then keeps the plain streamed event log. Never raises
    (STEER-NFR-004)."""
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
    """The pinned header + reserved scroll region on one terminal stream (STEER-FR-012..016).

    ``open`` reserves the top ``HEADER_HEIGHT`` rows (DECSTBM) so ordinary writes — the event log,
    the dispatched agent's stdout — scroll only in the region below; ``note`` folds a run event into
    the state and redraws the header in ONE write (cursor save / address / restore — no ``\\r``);
    ``close`` always resets the scroll region and restores the cursor, and is idempotent so exception
    paths and normal exits converge (STEER-NFR-004). A ``SIGWINCH`` re-lays the frame out
    (STEER-FR-016); the alternate screen buffer is never used."""

    def __init__(
        self,
        stream: TextIO,
        *,
        st: style.Styler,
        subject: str = "",
        size: Optional[tuple[int, int]] = None,
    ) -> None:
        self._stream = stream
        self._st = st
        self._subject = subject
        self._fixed_size = size
        self._cols, self._rows = size if size is not None else (0, 0)
        self._state = FrameState()
        self._open = False
        self._prev_winch: Any = None

    # ------------------------------------------------------------------ lifecycle
    def open(self) -> None:
        if self._open:
            return
        self._cols, self._rows = (
            self._fixed_size if self._fixed_size is not None else _size(self._stream, (80, 24))
        )
        # Make room (content scrolls up into scrollback when at the bottom), hide the cursor while
        # the frame owns the header, reserve the region, and park the cursor at its top.
        self._stream.write(
            "\n" * HEADER_HEIGHT
            + "\033[?25l"
            + f"\033[{HEADER_HEIGHT + 1};{self._rows}r"
            + f"\033[{HEADER_HEIGHT + 1};1H"
        )
        self._stream.flush()
        self._open = True
        self._install_winch()
        self._draw()

    def close(self) -> None:
        """Reset the scroll region and restore the cursor — always safe to call twice (STEER-FR-016)."""
        if not self._open:
            return
        self._open = False
        self._restore_winch()
        try:
            self._stream.write("\033[r" + f"\033[{self._rows};1H" + "\033[?25h" + "\n")
            self._stream.flush()
        except (OSError, ValueError):
            pass  # a vanished stream must not raise on teardown (STEER-NFR-004)

    # ------------------------------------------------------------------ events
    def note(
        self, *, kind: str, step: str, stage: str, detail: str, reached: str, spec_id: str
    ) -> None:
        """Fold one streamed event into the frame and redraw (STEER-FR-013). Opens lazily."""
        self._state = next_state(
            self._state,
            kind=kind,
            step=step,
            stage=stage,
            detail=detail,
            reached=reached,
            spec_id=spec_id,
        )
        if not self._open:
            self.open()
        else:
            self._draw()

    # ------------------------------------------------------------------ rendering
    def _draw(self) -> None:
        lines = frame_lines(self._state, self._cols, self._st, self._subject)
        parts = ["\0337"]  # save cursor
        for i, line in enumerate(lines):
            parts.append(f"\033[{i + 1};1H\033[2K{line}")
        parts.append("\0338")  # restore cursor into the scroll region
        try:
            self._stream.write("".join(parts))
            self._stream.flush()
        except (OSError, ValueError):
            pass  # never let a redraw take the run down (STEER-NFR-004)

    def resize(self) -> None:
        """Re-lay the frame out after a terminal resize (STEER-FR-016)."""
        if not self._open:
            return
        self._cols, self._rows = (
            self._fixed_size if self._fixed_size is not None else _size(self._stream, (80, 24))
        )
        self._stream.write(f"\033[{HEADER_HEIGHT + 1};{self._rows}r" + f"\033[{self._rows};1H")
        self._draw()

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
) -> Optional[LiveFrame]:
    """A :class:`LiveFrame` when the terminal supports the pinned region, else ``None`` (STEER-FR-015)."""
    if not supported(stream, tty=tty, env=env, size=size):
        return None
    return LiveFrame(stream, st=st, subject=subject, size=size)
