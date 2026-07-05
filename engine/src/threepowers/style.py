"""Colorized, package-manager-style CLI output + a structured-output toolkit (INITX-FR-013/014, CLIUX).

Color is a *presentation* layer only. It is auto-disabled whenever output must stay
machine-parseable or reproducible — a non-TTY stream, ``NO_COLOR`` set, ``--json``, or the
non-interactive ``--yes`` flag — and it NEVER touches machine-readable output or verdict bytes
(3PWR-NFR-001, INITX-FR-014). No third-party dependency and no network (INITX-NFR-004,
CLIUX-FR-003/NFR-003): plain ANSI SGR sequences the terminal already understands, and the styler
degrades to a no-op when color is off (INITX-NFR-004 — its absence never fails a command).

Beyond the semantic color vocabulary, this module provides a small **structured-output toolkit**
(CLIUX-FR-001): section headers, key/value blocks, aligned tables, status rows, dividers, and wrapped
bullet lists. Every primitive is a pure function of its :class:`Styler` — with color off it degrades
to plain, alignment-preserving, escape-free text that equals the colored output with the ANSI removed
(CLIUX-FR-002). Meaning is never carried by color alone: a glyph or word always accompanies it, and an
ASCII glyph set is used when the stream cannot encode the Unicode marks (CLIUX-NFR-004).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import textwrap
from dataclasses import dataclass
from typing import Iterable, Sequence, TextIO

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

# ASCII fallbacks for a stream whose encoding cannot represent the Unicode marks (CLIUX-NFR-004).
_STATUS_GLYPH_ASCII: dict[str, str] = {
    "pass": "v",
    "ok": "v",
    "fail": "x",
    "warn": "!",
    "todo": "+",
    "skip": "-",
    "info": "i",
}

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """The text with every ANSI SGR sequence removed (CLIUX-FR-002)."""
    return _ANSI_RE.sub("", text)


def visible_len(text: str) -> int:
    """The printable width of ``text`` — its length ignoring ANSI color sequences (CLIUX-FR-002)."""
    return len(strip_ansi(text))


def term_width(default: int = 80) -> int:
    """The terminal width in columns, clamped to a sane minimum; ``default`` when undetectable.

    Never raises — a width-unknown stream (pipe, CI) falls back to ``default`` (CLIUX edge case)."""
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except (OSError, ValueError):
        cols = default
    if cols <= 0:
        cols = default
    return max(20, cols)


def _can_encode_glyphs(stream: TextIO | None) -> bool:
    """Whether ``stream``'s encoding can represent the Unicode status/progress marks (CLIUX-NFR-004)."""
    enc = getattr(stream if stream is not None else sys.stdout, "encoding", None) or "utf-8"
    try:
        "✓✗▶⚠·▌─".encode(enc)
        return True
    except (LookupError, UnicodeEncodeError):
        return False


def color_enabled(
    stream: TextIO | None = None,
    *,
    as_json: bool = False,
    assume_yes: bool = False,
    color_mode: str = "auto",
) -> bool:
    """Whether to emit ANSI color for human output (INITX-FR-014, CLIUX-FR-014).

    Machine-readable output (``as_json``) and non-interactive runs (``assume_yes`` / CI) are NEVER
    colored — these win over everything, so styled output can never corrupt a parseable payload
    (INITX-FR-014). The resolution order then follows the CLIUX-FR-014 precedence — environment over
    the ``ui.yaml`` ``color_mode`` over the auto default: ``THREEPOWERS_FORCE_COLOR`` forces it on and
    ``NO_COLOR`` forces it off (env); then ``color_mode`` (``always``/``never``) from the config file;
    then the ``auto`` default, which colors only an interactive TTY. ``color_mode`` defaults to
    ``auto`` so existing callers are unchanged."""
    if as_json or assume_yes:
        return False
    if os.environ.get("THREEPOWERS_FORCE_COLOR"):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return False
    if color_mode == "always":
        return True
    if color_mode == "never":
        return False
    stream = stream if stream is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


@dataclass(frozen=True)
class Styler:
    """Paints text with ANSI color when ``enabled``; a transparent no-op otherwise, and renders the
    structured-output toolkit (CLIUX-FR-001).

    Construct one for human output only. Machine-readable output must never be routed through a
    styler — that keeps the ``--json`` payload byte-identical with and without color (INITX-FR-014).
    ``ascii_only`` swaps the Unicode glyphs for an ASCII set when the stream cannot encode them
    (CLIUX-NFR-004); it defaults off, so a directly-constructed ``Styler`` still uses the Unicode
    marks."""

    enabled: bool = False
    ascii_only: bool = False

    def paint(self, text: str, *names: str) -> str:
        if not self.enabled or not names:
            return text
        seq = ";".join(_CODES[n] for n in names if n in _CODES)
        if not seq:
            return text
        return f"\033[{seq}m{text}\033[0m"

    # Semantic helpers — the color vocabulary the CLI uses.
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

    def _glyph(self, status: str) -> str:
        table = _STATUS_GLYPH_ASCII if self.ascii_only else _STATUS_GLYPH
        return table.get(status, "*" if self.ascii_only else "•")

    def mark(self, status: str) -> str:
        """A colorized status glyph for a checklist / verdict row (``pass``/``fail``/``warn``/…)."""
        glyph = self._glyph(status)
        if status in ("pass", "ok"):
            return self.ok(glyph)
        if status == "fail":
            return self.err(glyph)
        if status in ("warn", "todo"):
            return self.warn(glyph)
        if status == "info":
            return self.paint(glyph, "cyan")
        return self.dim(glyph)

    # ----------------------------------------------------------- structured-output toolkit (CLIUX-FR-001)
    def header(self, title: str, subject: str = "") -> str:
        """A self-identifying section header (CLIUX-FR-006): an emphasized title + optional dim subject."""
        bar = "|" if self.ascii_only else "▌"
        line = f"{self.paint(bar, 'cyan')} {self.head(title)}"
        if subject:
            line += f"  {self.dim(subject)}"
        return line

    def rule(self, width: int | None = None) -> str:
        """A horizontal divider (CLIUX-FR-001)."""
        ch = "-" if self.ascii_only else "─"
        n = width if width is not None else min(60, term_width())
        return self.dim(ch * max(1, n))

    def status_row(self, status: str, text: str, detail: str = "", indent: int = 2) -> str:
        """One status line — a colored glyph + text (+ dim detail). The canonical row every command
        uses, so a given status reads the same everywhere (CLIUX-FR-005). Color is never the sole
        signal: the glyph (or its ASCII fallback) and the text always carry the meaning (CLIUX-NFR-004)."""
        line = f"{' ' * indent}{self.mark(status)} {text}"
        if detail:
            line += f"  {self.dim(detail)}"
        return line

    def kv(self, pairs: Sequence[tuple[str, str]], indent: int = 2) -> str:
        """An aligned key/value block (CLIUX-FR-001/004): dim labels padded to a common width, then the
        value. Multi-field results render here instead of as one run-on line (CLIUX-FR-004)."""
        rows = list(pairs)
        if not rows:
            return ""
        kw = max(len(k) for k, _ in rows)
        pad = " " * indent
        return "\n".join(f"{pad}{self.dim(k)}{' ' * (kw - len(k) + 2)}{v}" for k, v in rows)

    def table(
        self,
        rows: Sequence[Sequence[str]],
        headers: Sequence[str] | None = None,
        indent: int = 2,
    ) -> str:
        """Aligned columns (CLIUX-FR-001/004). Column widths use the *visible* cell width, so colored
        cells still line up and — with color off — the output equals the colored output with the ANSI
        stripped (CLIUX-FR-002)."""
        body = [[str(c) for c in row] for row in rows]
        if not body and not headers:
            return ""
        ncol = max((len(r) for r in body), default=0)
        if headers:
            ncol = max(ncol, len(headers))
        allrows = ([[self.bold(h) for h in headers]] if headers else []) + body
        widths = [0] * ncol
        for r in allrows:
            for i in range(ncol):
                cell = r[i] if i < len(r) else ""
                widths[i] = max(widths[i], visible_len(cell))
        pad = " " * indent
        out = []
        for r in allrows:
            cells = [
                (r[i] if i < len(r) else "")
                + " " * (widths[i] - visible_len(r[i] if i < len(r) else ""))
                for i in range(ncol)
            ]
            out.append((pad + "  ".join(cells)).rstrip())
        return "\n".join(out)

    def bullet(self, items: Iterable[str], indent: int = 2, width: int | None = None) -> str:
        """A wrapped bullet list (CLIUX-FR-004): long items wrap to the terminal width, never one line."""
        glyph = "-" if self.ascii_only else "•"
        w = max(20, width if width is not None else term_width())
        pad = " " * indent
        cont = " " * (indent + 2)
        return "\n".join(
            textwrap.fill(str(it), width=w, initial_indent=f"{pad}{glyph} ", subsequent_indent=cont)
            for it in items
        )


def styler(
    stream: TextIO | None = None,
    *,
    as_json: bool = False,
    assume_yes: bool = False,
    color_mode: str = "auto",
) -> Styler:
    """Build a :class:`Styler` whose ``enabled`` reflects :func:`color_enabled` and whose glyph set
    matches what ``stream`` can encode (CLIUX-NFR-004)."""
    return Styler(
        enabled=color_enabled(
            stream, as_json=as_json, assume_yes=assume_yes, color_mode=color_mode
        ),
        ascii_only=not _can_encode_glyphs(stream),
    )


VERBOSITY_LEVELS = ("quiet", "normal", "verbose")


def resolve_verbosity(
    quiet: bool = False, verbose: bool = False, file_default: str = "normal"
) -> str:
    """The effective human-output verbosity (CLIUX-FR-013/014): ``quiet`` | ``normal`` | ``verbose``.

    Precedence: an explicit flag wins over the ``ui.yaml`` default (there is no verbosity environment
    layer). ``--quiet`` and ``--verbose`` are mutually exclusive at the CLI; if both are somehow set,
    the more-informative ``verbose`` wins. A pure function of its inputs (CLIUX-FR-014 property)."""
    if verbose:
        return "verbose"
    if quiet:
        return "quiet"
    return file_default if file_default in VERBOSITY_LEVELS else "normal"
