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
    """Plan 034 Track D: `usage_mode` appends the backend's own `usage_mode_args` (the engine
    invents no flag); absent — the shipped default — the invocation is byte-identical to before,
    preserving the live text stream."""
    base = _manifest("claude")
    assert not str(base.get("usage_mode") or "").strip()  # shipped default: off
    argv_off, _ = agents.build_command(base, "PROMPT")
    assert argv_off == ["claude", "--permission-mode", "acceptEdits", "-p", "PROMPT"]

    on = dict(base, usage_mode="json")
    argv_on, _ = agents.build_command(on, "PROMPT")
    expected = ["claude", "--permission-mode", "acceptEdits", "--output-format", "json"]
    assert argv_on == [*expected, "-p", "PROMPT"]

    # usage_mode set on a manifest that declares no args appends nothing
    bare = {"command": "x", "usage_mode": "json"}
    assert agents.build_command(bare, "P")[0] == ["x", "P"]
