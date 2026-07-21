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
    JSON fields, `regex` parses the prose fallback, `session-file` is a stub (returns None until
    its resolver lands), and `none` is honest-unknown."""
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
    `session-file` is the stubbed resolver (None); `regex`/`none` carry no machine-stable cost."""
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
    """Plan 034 Track D: Claude Code's `--output-format json` result reports input_tokens
    EXCLUDING cache reads; the hint sums it with output_tokens (312 + 9273), ignoring the
    cache_read/cache_creation fields. Plain text output stays unknown (usage_mode off)."""
    assert agents.extract_usage(_manifest("claude"), _fixture("claude.json")) == 9585
    assert agents.extract_usage(_manifest("claude"), "plain text, no summary") is None


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


def test_aider_hint_sums_sent_and_received_abbreviated_counts() -> None:
    """Plan 034 Track D: aider's `Tokens: 12k sent, 1.2k received.` summary yields
    12000 + 1200 (sent may include cached context — the documented over-count)."""
    assert agents.extract_usage(_manifest("aider"), _fixture("aider.txt")) == 13200


def test_copilot_hosted_hint_reads_the_reference_total_tokens_field() -> None:
    """Plan 034 Track D: the hosted reference manifest's enabled json hint reads
    usage.total_tokens from the poll/collect output."""
    out = '{"status": "completed", "usage": {"total_tokens": 9876}}'
    assert agents.extract_usage(_manifest("copilot-hosted"), out) == 9876


def test_opencode_declares_no_hint_and_reads_unknown() -> None:
    """Plan 034 Track D: opencode exposes no documented machine-stable token summary — the
    manifest ships no hint and usage reads as unknown."""
    manifest = _manifest("opencode")
    assert "usage" not in manifest
    assert agents.extract_usage(manifest, "any run output") is None


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
