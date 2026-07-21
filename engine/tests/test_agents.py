"""Advisory token-usage capture — the manifest-driven ``usage`` hints (plan 034 Track D).

Every headless backend reports token usage differently (a text summary line, a JSON result
object, a JSONL event stream); the manifest's ``usage`` hint declares where the real consumed
(non-cached input + output) count lives, and :func:`threepowers.agents.extract_usage` reads it.
These tests pin the parsing primitives, the extended hint shapes (multi-group regex sum, json
``fields``/``subtract``), the opt-in ``usage_mode`` invocation flag, and — via the transcript
fixtures under ``tests/fixtures/usage/`` — every shipped reference manifest's hint against its
backend's real output shape. Usage stays strictly advisory: unknown reads as ``None``, never an
error, and never enters the verdict (the byte-identity guard lives in test_native_runner.py).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pytest
import yaml

from threepowers import agents

_FIXTURES = Path(__file__).parent / "fixtures" / "usage"
_SCAFFOLD = Path(agents.__file__).parent / "scaffold" / "agents"


def _manifest(name: str) -> dict[str, Any]:
    """One shipped reference manifest, exactly as `3pwr init` seeds it."""
    loaded = yaml.safe_load((_SCAFFOLD / f"{name}.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _fixture(name: str) -> str:
    """One captured backend transcript sample."""
    return (_FIXTURES / name).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- _parse_count
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("629.8k", 629800),
        ("1.2M", 1200000),
        ("29,500", 29500),
        ("29_500", 29500),
        ("9200", 9200),
        ("12K", 12000),
        ("x", None),
        ("", None),
        ("k", None),
    ],
)
def test_parse_count_handles_plain_separated_and_abbreviated(
    raw: str, expected: Optional[int]
) -> None:
    """Plan 034 Track D: counts parse across every shape agent CLIs print — plain integers,
    thousands separators, and case-insensitive k/M units; non-numeric reads as None."""
    assert agents._parse_count(raw) == expected


# --------------------------------------------------------------------------- source taxonomy (Track A)
def test_source_dispatch_routes_each_source_to_the_right_resolver() -> None:
    """The `usage.source` taxonomy dispatches to the matching resolver: `inline-json` reads the
    JSON fields, `regex` parses the prose fallback, `session-file` reads an on-disk artifact (here
    with no `path_template`, so it is unresolved → None), and `none` is honest-unknown."""
    inline = {"usage": {"source": "inline-json", "field": "usage.total_tokens"}}
    assert agents.extract_usage(inline, '{"usage": {"total_tokens": 4321}}') == 4321

    rx = {"usage": {"source": "regex", "pattern": r"tokens used[:\s]+([0-9][0-9,]*)"}}
    assert agents.extract_usage(rx, "tokens used: 1,000\ntokens used: 7,777\n") == 7777

    session = {"usage": {"source": "session-file", "field": "usage.total_tokens"}}
    assert agents.extract_usage(session, '{"usage": {"total_tokens": 4321}}') is None

    nothing = {"usage": {"source": "none", "field": "usage.total_tokens"}}
    assert agents.extract_usage(nothing, '{"usage": {"total_tokens": 4321}}') is None


def test_legacy_strategy_maps_to_the_new_source_with_an_identical_result() -> None:
    """Back-compat: a legacy `strategy: json` manifest resolves to `inline-json` and a legacy
    `strategy: regex` manifest resolves to `regex`, each yielding exactly the same count as the
    explicit `source:` form — so unmigrated manifests keep working during the transition."""
    out_json = 'prose\n{"usage": {"total_tokens": 5150}}\n'
    legacy_json = {"usage": {"strategy": "json", "field": "usage.total_tokens"}}
    source_json = {"usage": {"source": "inline-json", "field": "usage.total_tokens"}}
    assert (
        agents.extract_usage(legacy_json, out_json)
        == agents.extract_usage(source_json, out_json)
        == 5150
    )

    out_rx = "tokens used: 3,003\n"
    legacy_rx = {"usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9][0-9,]*)"}}
    source_rx = {"usage": {"source": "regex", "pattern": r"tokens used[:\s]+([0-9][0-9,]*)"}}
    assert (
        agents.extract_usage(legacy_rx, out_rx) == agents.extract_usage(source_rx, out_rx) == 3003
    )

    # `source` wins when both are present (prefer the explicit taxonomy over the legacy field)
    both = {"usage": {"source": "none", "strategy": "json", "field": "usage.total_tokens"}}
    assert agents.extract_usage(both, out_json) is None


@pytest.mark.parametrize(
    "spec",
    [
        {"source": "none", "field": "usage.total_tokens"},  # explicit none
        {"field": "usage.total_tokens"},  # no source and no legacy strategy
        {"source": "made-up", "field": "usage.total_tokens"},  # unrecognized source
    ],
)
def test_no_usable_source_yields_none_never_a_guess(spec: dict[str, Any]) -> None:
    """`source: none`, an absent source with no legacy `strategy`, and an unrecognized source all
    resolve to honest-unknown — `None` (rendered `—`), never a fabricated number — even when the
    output plainly carries a parseable count."""
    out = '{"usage": {"total_tokens": 9999}}'
    assert agents.extract_usage({"usage": spec}, out) is None
    assert agents.extract_cost({"usage": {**spec, "cost_field": "total_cost_usd"}}, out) is None


def test_cost_dispatch_matches_the_usage_source() -> None:
    """`extract_cost` dispatches on the same resolved source: `inline-json` reads `cost_field`;
    `session-file` reads it from the on-disk artifact (unresolved here — no `path_template` — so
    None); `regex`/`none` carry no machine-stable cost."""
    payload = '{"total_cost_usd": 0.25}'

    def cost(**spec: Any) -> Optional[float]:
        return agents.extract_cost({"usage": {**spec, "cost_field": "total_cost_usd"}}, payload)

    assert cost(source="inline-json") == pytest.approx(0.25)
    # legacy strategy: json maps to inline-json for cost too
    assert cost(strategy="json") == pytest.approx(0.25)
    assert cost(source="session-file") is None
    assert cost(source="regex") is None


# --------------------------------------------------------------------------- extended hint shapes
def test_regex_hint_sums_all_capture_groups_of_the_last_match() -> None:
    """Plan 034 Track D: a multi-group pattern (non-cached input + output captured separately)
    yields the groups' sum, taken from the LAST match — the final cumulative summary."""
    m = {"usage": {"strategy": "regex", "pattern": r"in ([0-9.,_kKmM]+) out ([0-9.,_kKmM]+)"}}
    out = "in 100 out 50\nprose\nin 29.5k out 9.2k\n"
    assert agents.extract_usage(m, out) == 38700


def test_regex_single_group_keeps_the_legacy_single_count_meaning() -> None:
    """Plan 034 Track D (regression): the pre-existing one-group codex hint keeps returning
    exactly that one count — generalization never changes the single-group behavior."""
    m = {"usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9][0-9,]*)"}}
    out = "step one\ntokens used: 1,000\nmore work\ntokens used: 12,345\n"
    assert agents.extract_usage(m, out) == 12345


def test_json_hint_accepts_fields_summed_and_subtract_for_cached() -> None:
    """Plan 034 Track D: `fields:` paths are summed and `subtract:` paths (cached counts) are
    subtracted when present; a missing subtract path reads as 0, a missing field disqualifies
    the object entirely (no partial sums from unrelated JSON lines)."""
    m = {
        "usage": {
            "strategy": "json",
            "fields": ["input_tokens", "output_tokens"],
            "subtract": ["cached_input_tokens"],
        }
    }
    out = '{"input_tokens": 1000, "cached_input_tokens": 400, "output_tokens": 50}'
    assert agents.extract_usage(m, out) == 650
    # a missing subtract path degrades to plain sum; a missing field reads as unknown
    assert agents.extract_usage(m, '{"input_tokens": 1000, "output_tokens": 50}') == 1050
    assert agents.extract_usage(m, '{"input_tokens": 1000}') is None


def test_json_single_field_keeps_the_legacy_meaning() -> None:
    """Plan 034 Track D (regression): the original single `field` form keeps working, including
    the last-JSON-line scan."""
    m = {"usage": {"strategy": "json", "field": "usage.total_tokens"}}
    out = 'progress text\n{"usage": {"total_tokens": 1234}, "result": "ok"}\n'
    assert agents.extract_usage(m, out) == 1234


# --------------------------------------------------------------------------- shipped manifests × fixtures
def test_copilot_hint_sums_written_and_output_from_the_real_summary_line() -> None:
    """Plan 034 Track D: the Copilot CLI summary `Tokens ↑ 629.8k (29.5k written) • ↓ 9.2k`
    yields written (non-cached input) + output = 29500 + 9200, never the ↑ cache-inclusive
    total."""
    assert agents.extract_usage(_manifest("copilot"), _fixture("copilot.txt")) == 38700


def test_claude_hint_reads_non_cached_input_plus_output_from_the_json_result() -> None:
    """Claude Code's `--output-format json` result reports input_tokens EXCLUDING cache reads; with
    no `modelUsage` map present (an older CLI) the hint degrades to the flat top-level `usage`,
    summing input + output (312 + 9273) and ignoring the cache_read/cache_creation fields. Plain
    text output stays unknown (usage_mode off)."""
    assert agents.extract_usage(_manifest("claude"), _fixture("claude.json")) == 9585
    assert agents.extract_usage(_manifest("claude"), "plain text, no summary") is None


def test_claude_token_total_is_the_whole_tree_model_usage_sum() -> None:
    """A `result` event carrying a two-model `modelUsage` map (a main model + a sub-agent model)
    yields the WHOLE-TREE token total — input + output summed across every model (312 + 9273 for
    the main + 5000 + 2000 for the sub-agent = 16585) — strictly greater than the top-level `usage`
    block alone (9585), so sub-agent tokens are no longer undercounted. Cache-read tokens are
    excluded, consistent with the flat posture. Cost stays `total_cost_usd`, which already rolls up
    the whole tree."""
    claude = _manifest("claude")
    body = _fixture("claude_stream_modelusage.jsonl")
    top_level_only = 312 + 9273
    whole_tree = agents.extract_usage(claude, body)
    assert whole_tree == top_level_only + 5000 + 2000  # 16585
    assert whole_tree is not None and whole_tree > top_level_only
    assert agents.extract_cost(claude, body) == pytest.approx(0.2913)


def test_claude_degrades_to_top_level_usage_when_model_usage_absent() -> None:
    """Older-CLI back-compat: a stream-json transcript whose `result` event has no `modelUsage`
    map degrades to the flat top-level `usage` block (312 + 9273 = 9585) rather than reading `—`."""
    assert agents.extract_usage(_manifest("claude"), _fixture("claude_stream.jsonl")) == 9585


def test_claude_wrong_model_usage_inner_path_degrades_not_crashes() -> None:
    """Defensive: if the inner token field names do not match the real `modelUsage` schema, every
    map value fails to resolve, so the resolver degrades to the flat top-level `usage` fallback
    (never a crash, never a fabricated number)."""
    manifest = {
        "usage": {
            "source": "inline-json",
            "per_model_field": "modelUsage",
            "per_model_tokens": ["nope_input", "nope_output"],
            "fields": ["usage.input_tokens", "usage.output_tokens"],
            "cost_field": "total_cost_usd",
        }
    }
    assert agents.extract_usage(manifest, _fixture("claude_stream_modelusage.jsonl")) == 9585


def test_codex_text_hint_still_reads_the_totals_line() -> None:
    """Plan 034 Track D (regression): the shipped codex hint keeps extracting the cumulative
    `tokens used:` text total (the documented cache-inclusive over-count)."""
    assert agents.extract_usage(_manifest("codex"), _fixture("codex.txt")) == 143265


def test_codex_json_alternative_separates_cached_input() -> None:
    """Plan 034 Track D: the json hint documented (commented) in codex.yaml reads the JSONL
    `token_count` event as non-cached input + output = 143265 + 8125 − 118400."""
    m = {
        "usage": {
            "strategy": "json",
            "fields": ["input_tokens", "output_tokens"],
            "subtract": ["cached_input_tokens"],
        }
    }
    assert agents.extract_usage(m, _fixture("codex.jsonl")) == 32990


def _copilot_home(tmp_path: Path, session_id: str) -> Path:
    """Seed a fake home with the copilot session log for ``session_id`` and return the home dir."""
    events_dir = tmp_path / ".copilot" / "session-state" / session_id
    events_dir.mkdir(parents=True)
    (events_dir / "events.jsonl").write_text(_fixture("copilot_events.jsonl"), encoding="utf-8")
    return tmp_path


def test_copilot_session_file_reads_tokens_from_the_shutdown_event(tmp_path: Path) -> None:
    """Track C: the copilot backend reads the `session.shutdown` event from
    `~/.copilot/session-state/<uuid>/events.jsonl`, recovering the id from the `--resume=<uuid>`
    output line. Tokens are non-cached input (input_tokens − cached_input_tokens) + output_tokens =
    239700 − 192800 + 5200 = 52100. Copilot bills credits, not USD, so cost stays unknown."""
    session_id = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
    home = _copilot_home(tmp_path, session_id)
    output = f"Done.\n\nResume copilot --resume={session_id}\n"
    assert agents.extract_usage(_manifest("copilot"), output, home=home) == 52100
    assert agents.extract_cost(_manifest("copilot"), output, home=home) is None


def test_copilot_falls_back_to_the_hardened_regex_when_the_file_is_absent(tmp_path: Path) -> None:
    """Track C: a run whose session file is missing/renamed falls back to the drift-proof summary
    regex. The current live line `Tokens ↑ 629.8k (192.8k cached, 46.9k written) • ↓ 5.2k` yields
    non-cached written (46900) + output (5200) = 52100 — and with neither the file nor a summary
    line, usage is honest-unknown (`—`), never a fabricated number."""
    session_id = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"  # a valid id, but no file seeded for it
    summary = "Tokens ↑ 629.8k (192.8k cached, 46.9k written) • ↓ 5.2k"
    with_summary = f"Resume copilot --resume={session_id}\n{summary}\n"
    assert agents.extract_usage(_manifest("copilot"), with_summary, home=tmp_path) == 52100
    # the summary line alone (no --resume id at all) still resolves via the fallback
    assert agents.extract_usage(_manifest("copilot"), summary) == 52100
    # missing file AND no summary line → honest unknown
    no_summary = f"Resume copilot --resume={session_id}\nall done, no token line\n"
    assert agents.extract_usage(_manifest("copilot"), no_summary, home=tmp_path) is None


def test_copilot_rejects_a_path_traversal_session_id(tmp_path: Path) -> None:
    """Track C / SEC-001: a captured session id that is not a strict UUID (here a path-traversal
    attempt) is rejected before it is templated into a path — the session file is never read at an
    attacker-influenced location. The source is left unresolved, so it falls to the regex fallback
    and then honest-unknown, never a file read."""
    malicious = "../../../../etc/passwd"
    output = f"Resume copilot --resume={malicious}\nno summary line here\n"
    assert agents.extract_usage(_manifest("copilot"), output, home=tmp_path) is None
    # the raw id is captured but fails strict-UUID validation, so no path is resolved from it
    assert agents._valid_session_id(malicious) is False
    assert agents._valid_session_id("3f2504e0-4f89-41d3-9a0c-0305e82c3301") is True


def test_aider_session_file_sums_tokens_and_cost_from_message_send(tmp_path: Path) -> None:
    """Track C: aider's usage comes from its `--analytics-log` JSONL, not prose. The engine points
    aider at a run-scoped log (the `{log}` path_template / session_log); each `message_send` event
    contributes `properties.{prompt_tokens, completion_tokens}` and a per-message USD
    `properties.cost`, summed across turns: tokens 12000+1200+8000+900 = 22100, cost 0.0345+0.0210
    = 0.0555. The prose `aider.txt` summary is no longer a usage source."""
    log = tmp_path / "analytics.jsonl"
    log.write_text(_fixture("aider_analytics.jsonl"), encoding="utf-8")
    manifest = _manifest("aider")
    assert manifest["usage"]["source"] == "session-file"
    assert agents.extract_usage(manifest, "aider stdout", session_log=log) == 22100
    assert agents.extract_cost(manifest, "aider stdout", session_log=log) == pytest.approx(0.0555)
    # the old prose summary line is not a source any more → honest unknown
    assert agents.extract_usage(manifest, _fixture("aider.txt"), session_log=None) is None


def test_aider_missing_field_degrades_to_none_never_raises(tmp_path: Path) -> None:
    """Track C / PAT-002: a `message_send` event missing the token fields (a schema drift) yields
    `None` rather than raising or fabricating a value; a missing cost field likewise reads `None`.
    The manifest also declares that the engine must inject the analytics-log flags."""
    manifest = _manifest("aider")
    assert agents.needs_session_log(manifest) is True
    assert agents.session_log_args(manifest, tmp_path / "x.jsonl") == [
        "--analytics",
        "--analytics-log",
        str(tmp_path / "x.jsonl"),
    ]
    renamed = tmp_path / "renamed.jsonl"
    renamed.write_text(
        '{"event": "message_send", "properties": {"input": 100, "output": 5}}\n',
        encoding="utf-8",
    )
    assert agents.extract_usage(manifest, "out", session_log=renamed) is None
    assert agents.extract_cost(manifest, "out", session_log=renamed) is None
    # a session_log the engine never provided (None) leaves the source unresolved, never a read
    assert agents.extract_usage(manifest, "out", session_log=None) is None


def test_copilot_hosted_hint_reads_the_reference_total_tokens_field() -> None:
    """Plan 034 Track D: the hosted reference manifest's enabled json hint reads
    usage.total_tokens from the poll/collect output."""
    out = '{"status": "completed", "usage": {"total_tokens": 9876}}'
    assert agents.extract_usage(_manifest("copilot-hosted"), out) == 9876


def test_codex_json_turn_completed_yields_tokens_with_no_regex() -> None:
    """Track B: the shipped codex backend now reads `codex exec --json` structured-first. Its
    `turn.completed` event's `usage` object gives non-cached input + output (143265 + 8125 −
    118400 = 32990) — and when both the JSON and the prose "tokens used:" line are present the
    STRUCTURED value wins, proving the regex is not the primary path."""
    assert agents.extract_usage(_manifest("codex"), _fixture("codex_json.jsonl")) == 32990
    # JSON present alongside a (deliberately different) prose total → the JSON value wins, not 999
    mixed = _fixture("codex_json.jsonl") + "tokens used: 999\n"
    assert agents.extract_usage(_manifest("codex"), mixed) == 32990


def test_codex_regex_fallback_fires_only_when_json_is_absent() -> None:
    """Track B: the shipped codex regex `pattern` is a declared FALLBACK on the `inline-json`
    source — it fires only when no structured usage resolves. Prose-only output (no JSON usage
    event) falls back to the `tokens used:` total; the shipped `codex.txt` sample does the same."""
    assert agents.extract_usage(_manifest("codex"), "tokens used: 5,000\n") == 5000
    assert agents.extract_usage(_manifest("codex"), _fixture("codex.txt")) == 143265
    # neither structured JSON nor a matching prose line → honest unknown
    assert agents.extract_usage(_manifest("codex"), "no usage anywhere") is None


def test_opencode_sums_multiple_step_finish_events() -> None:
    """Track B: opencode's `run --format json` emits one `step_finish` per step with no cumulative
    summary, so the shipped backend sums `part.tokens.{input,output}` (1200+300+800+150 = 2450)
    and `part.cost` (0.0021+0.0013) across every event."""
    manifest = _manifest("opencode")
    assert manifest["usage"]["source"] == "inline-json"
    assert manifest["usage"]["aggregate"] == "sum"
    assert agents.extract_usage(manifest, _fixture("opencode.jsonl")) == 2450
    assert agents.extract_cost(manifest, _fixture("opencode.jsonl")) == pytest.approx(0.0034)


def test_opencode_with_no_step_finish_event_reads_unknown() -> None:
    """Track B: the known "exits before the final event" case — output carrying no `step_finish`
    event — yields no fabricated number; usage and cost both read as unknown (`—`)."""
    manifest = _manifest("opencode")
    no_event = '{"type":"step_start","part":{"id":"step_1"}}\n{"type":"text","part":{"text":"hi"}}\n'
    assert agents.extract_usage(manifest, no_event) is None
    assert agents.extract_cost(manifest, no_event) is None


# --------------------------------------------------------------------------- usage_mode (opt-in)
def test_usage_mode_appends_the_manifest_declared_args_only_when_set() -> None:
    """Plan 034 Track D / plan 036 Track E: `usage_mode` appends the backend's own
    `usage_mode_args` (the engine invents no flag). The shipped claude backend now enables it with
    `--output-format stream-json --verbose` — a streaming event format that preserves the live
    conversation while carrying the final usage/cost. A manifest with `usage_mode` cleared
    dispatches byte-identically to the bare invocation, and a manifest that declares no args
    appends nothing."""
    base = _manifest("claude")
    assert str(base.get("usage_mode") or "").strip() == "json"  # shipped default: on (streaming)
    argv_on, _ = agents.build_command(base, "PROMPT")
    expected = [
        "claude",
        "--permission-mode",
        "acceptEdits",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    assert argv_on == [*expected, "-p", "PROMPT"]

    off = dict(base, usage_mode="")
    argv_off, _ = agents.build_command(off, "PROMPT")
    assert argv_off == ["claude", "--permission-mode", "acceptEdits", "-p", "PROMPT"]

    # usage_mode set on a manifest that declares no args appends nothing
    bare = {"command": "x", "usage_mode": "json"}
    assert agents.build_command(bare, "P")[0] == ["x", "P"]


def test_shipped_claude_is_stream_json_and_reads_cost_from_the_result_event() -> None:
    """Plan 036 Track E: the shipped claude backend is dispatched in stream-json mode (so the live
    echo renders assistant text deltas), and its `usage.cost_field` reads `total_cost_usd` from the
    final `result` event — in step with the token hint. A backend without `usage_mode` set, or one
    without a `cost_field`, reads as not-streaming / unknown-cost."""
    claude = _manifest("claude")
    assert agents.is_stream_json(claude) is True
    assert agents.extract_cost(claude, _fixture("claude.json")) == pytest.approx(0.2913)
    # a plain-JSON (non-streaming) usage_mode, and a manifest with no cost_field, both read false/None
    plain = dict(claude, usage_mode_args=["--output-format", "json"])
    assert agents.is_stream_json(plain) is False
    no_cost = {"usage": {"strategy": "json", "fields": ["a"]}}
    assert agents.extract_cost(no_cost, '{"a": 1, "total_cost_usd": 0.5}') is None
    assert agents.is_stream_json({"command": "x"}) is False
