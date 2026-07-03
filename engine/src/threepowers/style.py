"""Colorized, package-manager-style CLI output (INITX-FR-013/014).

Color is a *presentation* layer only. It is auto-disabled whenever output must stay
machine-parseable or reproducible — a non-TTY stream, ``NO_COLOR`` set, ``--json``, or the
non-interactive ``--yes`` flag — and it NEVER touches machine-readable output or verdict bytes
(3PWR-NFR-001, INITX-FR-014). No third-party dependency and no network (INITX-NFR-004): plain
ANSI SGR sequences the terminal already understands, and the styler degrades to a no-op when
color is off (INITX-NFR-004 — its absence never fails a command).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import TextIO

# ANSI Select-Graphic-Rendition codes, by semantic name.
_CODES: dict[str, str] = {
    "reset": "0",
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "gray": "90",
}

_STATUS_GLYPH: dict[str, str] = {
    "pass": "✓",
    "ok": "✓",
    "fail": "✗",
    "warn": "⚠",
    "todo": "＋",
    "skip": "–",
    "info": "ⓘ",
}


def color_enabled(
    stream: TextIO | None = None, *, as_json: bool = False, assume_yes: bool = False
) -> bool:
    """Whether to emit ANSI color for human output (INITX-FR-014).

    Machine-readable output (``as_json``) and non-interactive runs (``assume_yes`` / CI) are NEVER
    colored — these win over everything, so styled output can never corrupt a parseable payload
    (INITX-FR-014). Otherwise color is off when ``NO_COLOR`` is set or the stream is not a TTY;
    ``THREEPOWERS_FORCE_COLOR`` forces it on for an otherwise-capable stream (to exercise the colored
    path in tests)."""
    if as_json or assume_yes:
        return False
    if os.environ.get("THREEPOWERS_FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    stream = stream if stream is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


@dataclass(frozen=True)
class Styler:
    """Paints text with ANSI color when ``enabled``; a transparent no-op otherwise.

    Construct one for human output only. Machine-readable output must never be routed through a
    styler — that keeps the ``--json`` payload byte-identical with and without color (INITX-FR-014)."""

    enabled: bool = False

    def paint(self, text: str, *names: str) -> str:
        if not self.enabled or not names:
            return text
        seq = ";".join(_CODES[n] for n in names if n in _CODES)
        if not seq:
            return text
        return f"\033[{seq}m{text}\033[0m"

    # Semantic helpers — the vocabulary the CLI uses.
    def ok(self, text: str) -> str:
        return self.paint(text, "green")

    def err(self, text: str) -> str:
        return self.paint(text, "red")

    def warn(self, text: str) -> str:
        return self.paint(text, "yellow")

    def head(self, text: str) -> str:
        return self.paint(text, "bold", "cyan")

    def bold(self, text: str) -> str:
        return self.paint(text, "bold")

    def dim(self, text: str) -> str:
        return self.paint(text, "dim")

    def mark(self, status: str) -> str:
        """A colorized status glyph for a checklist / verdict row (``pass``/``fail``/``warn``/…)."""
        glyph = _STATUS_GLYPH.get(status, "•")
        if status in ("pass", "ok"):
            return self.ok(glyph)
        if status == "fail":
            return self.err(glyph)
        if status in ("warn", "todo"):
            return self.warn(glyph)
        if status == "info":
            return self.paint(glyph, "cyan")
        return self.dim(glyph)


def styler(
    stream: TextIO | None = None, *, as_json: bool = False, assume_yes: bool = False
) -> Styler:
    """Build a :class:`Styler` whose ``enabled`` reflects :func:`color_enabled`."""
    return Styler(enabled=color_enabled(stream, as_json=as_json, assume_yes=assume_yes))
