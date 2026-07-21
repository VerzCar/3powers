"""Live rendering of a backend's ``stream-json`` event stream — assistant text, never raw JSON.

A JSON-strategy backend dispatched in event-stream mode (Claude Code's ``--output-format
stream-json``) emits one JSON object per line: a ``system`` init event, one ``assistant`` event per
model turn (carrying the visible text), ``user`` tool-result events, and a final ``result`` event
(carrying ``usage`` and ``total_cost_usd``). The persisted transcript keeps every byte of that
stream verbatim (ground truth); the *live* view a human follows should read as a conversation, so
this module parses each event and echoes only the assistant text deltas.

:class:`StreamRenderer` is a ``write``/``flush`` sink that wraps the run's echo sink: the dispatch
pump feeds it the raw NDJSON line by line, and it forwards only rendered assistant text onward.
Parsing is defensive (:func:`render_event_line`): a non-JSON line (e.g. a stderr warning) falls
back to a raw echo, a recognized non-assistant event is suppressed, and a ``--raw-events`` escape
disables rendering entirely so the underlying events show. Sub-agent messages (carrying
``parent_tool_use_id``) are marked with an indent so external fan-out is visible in the flow; their
usage still rolls into the stage total through the final ``result`` event the hints read.
"""

from __future__ import annotations

import json
from typing import Optional, Protocol

# The indent marking a sub-agent's (fan-out) text so it reads as nested in the live conversation.
_SUBAGENT_MARK = "  ↳ "


class _Sink(Protocol):
    """The downstream echo sink rendered text is forwarded to."""

    def write(self, s: str) -> object: ...
    def flush(self) -> None: ...


def assistant_text(event: dict) -> str:
    """The visible assistant text of one stream-json event, or ``""`` for a non-text event.

    Reads an ``assistant`` event's ``message.content`` — the concatenated ``text`` blocks (or a
    bare string content) — and returns ``""`` for every other event type (``system`` / ``user`` /
    ``result``) or a malformed shape. Pure and total; never raises."""
    if event.get("type") != "assistant":
        return ""
    message = event.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def render_event_line(line: str) -> str:
    """Render one raw NDJSON line to the text to echo live — ``""`` to suppress it.

    Defensive by design: a blank line is suppressed; a line that is not valid JSON falls back to a
    raw echo (a plain stderr warning still reaches the user); a valid ``assistant`` event yields
    its visible text (a newline appended, indented when it is a sub-agent's fan-out message); every
    other recognized event (``system`` / ``user`` / ``result``) is suppressed so the live view stays
    a clean conversation. Pure given ``line``; never raises."""
    stripped = line.strip()
    if not stripped:
        return ""
    try:
        event = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        # Not an event — a stderr warning or a non-JSON backend line. Echo it verbatim.
        return line if line.endswith("\n") else line + "\n"
    if not isinstance(event, dict):
        return ""
    text = assistant_text(event)
    if not text:
        return ""
    prefix = _SUBAGENT_MARK if event.get("parent_tool_use_id") else ""
    return f"{prefix}{text}\n"


class StreamRenderer:
    """A line-buffered ``write``/``flush`` sink that renders a stream-json event stream live.

    Wraps the run's echo sink: the dispatch pump writes the backend's raw NDJSON into it, and it
    forwards only the rendered assistant text (via :func:`render_event_line`) onward — never the raw
    JSON. Buffers a partial trailing line until its newline arrives; ``flush`` releases any held
    fragment so nothing is lost at end-of-stream. With ``raw=True`` (the ``--raw-events`` escape)
    rendering is bypassed and every line is echoed verbatim."""

    def __init__(self, sink: _Sink, *, raw: bool = False) -> None:
        self._sink = sink
        self._raw = raw
        self._buf = ""

    def write(self, s: str) -> None:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._forward(line + "\n")

    def flush(self) -> None:
        if self._buf:
            self._forward(self._buf)
            self._buf = ""
        self._sink.flush()

    def _forward(self, line: str) -> None:
        if self._raw:
            self._sink.write(line)
            return
        rendered = render_event_line(line)
        if rendered:
            self._sink.write(rendered)


def wrap_echo(sink: Optional[_Sink], *, raw: bool = False) -> Optional[_Sink]:
    """Wrap ``sink`` in a :class:`StreamRenderer` when one is present, else pass ``None`` through.

    Used at dispatch time for a stream-json backend so the live echo renders assistant text; a
    ``None`` sink (no live echo — off-TTY without opt-in) needs no wrapping."""
    if sink is None:
        return None
    return StreamRenderer(sink, raw=raw)
