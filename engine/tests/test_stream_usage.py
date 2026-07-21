"""Stream-json live rendering + token/cost persistence (plan 036 Track E).

The shipped JSON-strategy backend (Claude Code) is dispatched with ``--output-format stream-json``:
it emits one JSON event per line, the persisted transcript keeps every byte verbatim (ground
truth), and the *live* echo renders only the assistant text so a human follows a conversation, not
raw JSON. The final ``result`` event carries ``usage`` and ``total_cost_usd``, which the manifest
hints read into the per-stage tokens **and** cost surfaced in ``progress.md`` and the ledger.

These tests pin that contract end to end: :mod:`threepowers.stream` renders assistant text (never
raw JSON), :func:`agents.extract_usage`/:func:`agents.extract_cost` read the ``result`` event, the
real dispatch pump tees the stream byte-for-byte while echoing only rendered text, and
:class:`progress.Reporter` renders both a non-``—`` Tokens and Cost cell.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

from threepowers import agents, progress, runner
from threepowers.stream import StreamRenderer, assistant_text, render_event_line

_STREAM = Path(__file__).parent / "fixtures" / "usage" / "claude_stream.jsonl"
_SCAFFOLD = Path(__file__).resolve().parents[1] / "src" / "threepowers" / "scaffold" / "agents"


class _Capture:
    """A minimal ``write``/``flush`` text sink that accumulates everything written to it."""

    def __init__(self) -> None:
        self.text = ""

    def write(self, s: str) -> int:
        self.text += s
        return len(s)

    def flush(self) -> None:  # noqa: D401 - part of the sink protocol
        pass


def _claude_manifest() -> dict:
    return yaml.safe_load((_SCAFFOLD / "claude.yaml").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- pure renderer contract
def test_assistant_text_reads_text_blocks_and_ignores_non_text_events() -> None:
    """``assistant_text`` concatenates an assistant event's text blocks and returns ``""`` for a
    tool-use turn or any non-assistant event — pure and total."""
    turn = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}]}}
    assert assistant_text(turn) == "hi"
    tool = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash"}]}}
    assert assistant_text(tool) == ""
    assert assistant_text({"type": "result", "total_cost_usd": 0.1}) == ""
    assert assistant_text({"type": "assistant"}) == ""  # malformed, never raises


def test_render_event_line_suppresses_json_events_but_echoes_non_json_verbatim() -> None:
    """A recognized non-assistant event renders to ``""`` (suppressed); a non-JSON line (a stderr
    warning) falls back to a verbatim echo; a sub-agent turn is indented."""
    assert render_event_line('{"type":"system","subtype":"init"}') == ""
    assert render_event_line('{"type":"result","total_cost_usd":0.2913}') == ""
    assert render_event_line("") == ""
    assert render_event_line("plain warning") == "plain warning\n"
    sub = '{"type":"assistant","parent_tool_use_id":"t1","message":{"content":[{"type":"text","text":"nested"}]}}'  # noqa: E501
    assert render_event_line(sub) == "  ↳ nested\n"


def test_stream_renderer_forwards_only_assistant_text_never_raw_json() -> None:
    """Fed the full stream-json fixture line by line, the renderer forwards the assistant text
    deltas (sub-agent turn indented) and never a byte of raw JSON — no ``{`` and no ``result``/
    ``total_cost_usd`` leaks into the live view."""
    echo = _Capture()
    renderer = StreamRenderer(echo)
    for line in _STREAM.read_text(encoding="utf-8").splitlines(keepends=True):
        renderer.write(line)
    renderer.flush()
    assert "Reading the spec now." in echo.text
    assert "Implemented the rate limiter; the suite is green." in echo.text
    assert "  ↳ Sub-agent researching the rate-limit approach." in echo.text
    assert "{" not in echo.text
    assert "total_cost_usd" not in echo.text
    assert '"type"' not in echo.text


def test_raw_events_escape_echoes_every_line_verbatim() -> None:
    """``--raw-events`` (``raw=True``) bypasses rendering: every raw NDJSON line is echoed
    verbatim so the underlying events show for debugging."""
    echo = _Capture()
    renderer = StreamRenderer(echo, raw=True)
    body = _STREAM.read_text(encoding="utf-8")
    for line in body.splitlines(keepends=True):
        renderer.write(line)
    renderer.flush()
    assert echo.text == body  # byte-for-byte passthrough


# ----------------------------------------------------------------- usage + cost from the result event
def test_result_event_yields_both_tokens_and_cost_for_the_shipped_backend() -> None:
    """The shipped claude backend reads stream-json, and its hints pull the *final* ``result``
    event's usage (312 + 9273) and ``total_cost_usd`` (0.2913) out of the full transcript — the
    per-turn assistant events (which carry no top-level ``usage``) never shadow it."""
    manifest = _claude_manifest()
    body = _STREAM.read_text(encoding="utf-8")
    assert agents.is_stream_json(manifest) is True
    assert agents.extract_usage(manifest, body) == 312 + 9273
    assert agents.extract_cost(manifest, body) == pytest.approx(0.2913)


# ----------------------------------------------------------------------- real dispatch pump: tee vs echo
def test_dispatch_tees_the_stream_verbatim_while_echoing_only_rendered_text(tmp_path) -> None:
    """The real dispatch pump persists the transcript byte-for-byte (the ``tee`` sink equals the
    fixture exactly — ground truth) while the wrapped echo sink shows only rendered assistant
    text; the captured stdout still yields the usage and cost."""
    tee, echo = _Capture(), _Capture()
    script = f"import sys; sys.stdout.write(open({str(_STREAM)!r}).read())"
    rc, out, _err = runner.dispatch_agent(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        timeout=30,
        stream=True,
        tee=tee,
        echo_out=StreamRenderer(echo),
    )
    assert rc == 0
    body = _STREAM.read_text(encoding="utf-8")
    assert tee.text == body  # persisted transcript is the stream verbatim, every byte
    assert out == body
    assert "Implemented the rate limiter; the suite is green." in echo.text
    assert "{" not in echo.text  # no raw JSON reached the live view
    manifest = _claude_manifest()
    assert agents.extract_usage(manifest, out) == 312 + 9273
    assert agents.extract_cost(manifest, out) == pytest.approx(0.2913)


# --------------------------------------------------------------------- progress renders tokens AND cost
def test_progress_renders_non_dash_tokens_and_cost_from_the_result_event(tmp_path) -> None:
    """Feeding the extracted tokens and cost through the reporter renders both a non-``—`` Tokens
    and a non-``—`` Cost cell for the stage — the two surface in step."""
    manifest = _claude_manifest()
    body = _STREAM.read_text(encoding="utf-8")
    tokens = agents.extract_usage(manifest, body)
    cost = agents.extract_cost(manifest, body)
    feature = tmp_path / "specs-src" / "007-demo"
    feature.mkdir(parents=True)
    rep = progress.Reporter(feature, spec_id="007-demo")
    rep.stage_started("specify", "Spec")
    rep.stage_completed("specify", "Spec", tokens=tokens, cost=cost)
    text = (feature / "progress.md").read_text(encoding="utf-8")
    row = next(ln for ln in text.splitlines() if ln.startswith("| Spec |"))
    assert "| 9585 |" in row
    assert "| $0.2913 |" in row


# ------------------------------------------------------------ a non-JSON backend: tokens ok, cost unknown
def test_non_stream_backend_reads_no_cost_and_is_not_stream_json() -> None:
    """A regex-strategy backend (no ``cost_field``, no stream-json args) still resolves its tokens
    but reports an unknown cost, and is never rendered as an event stream."""
    codex = yaml.safe_load((_SCAFFOLD / "codex.yaml").read_text(encoding="utf-8"))
    assert agents.is_stream_json(codex) is False
    assert agents.extract_cost(codex, "some plain text output") is None
