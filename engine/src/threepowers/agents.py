"""Agent backends — the provider-agnostic executive plugin contract.

An *agent backend* is a headless coding-agent (Claude Code, an OpenAI Codex-class CLI, the GitHub Copilot
CLI, OpenCode, Aider, …) described by a **declarative manifest** (``.3powers/agents/<name>.yaml``). The
native executive (:mod:`threepowers.runner`) builds the agent invocation from the manifest alone, so adding
an agent is "add a manifest" — no change to the engine core. This mirrors the language
*adapter* contract in :mod:`threepowers.adapters`.

The engine itself never calls a model API: it constructs an invocation for
an external agent process and lets that process do the model work. Enterprise model access (an internal
proxy, a cloud model service, or an OpenAI-compatible gateway) is inherited by pointing the agent at it via
the environment; the engine passes the environment through and interprets no credential.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import yaml

from .config import Settings

# Manifest fields (all optional except ``command``):
#   agent        display name (defaults to the file stem)
#   family       model family for the diversity precheck; '' when it depends on the model
#   headless     bool — dispatchable with no interactive IDE (default True)
#   command      the executable to invoke (required)
#   base_args    list[str] — fixed arguments before the model/prompt
#   model_flag   str | None — the flag that pins a model (e.g. "--model"); omitted when no model configured
#   prompt_flag  str | None — the flag that precedes the prompt (e.g. "-p"); None => positional prompt
#   prompt_via   "arg" | "stdin" — how the assembled stage prompt reaches the agent (default "arg")
#   new_session_args  list[str] — the CLI's no-resume / new-session flag(s), appended to every
#                invocation so each dispatch is guaranteed a clean session even on a backend
#                that would otherwise restore prior conversation state (fresh-session hook)
#   usage        dict | None — how the backend reports token usage in its output (advisory):
#                  source:   the resolution taxonomy — one of:
#                              "inline-json"  usage rides the run's own structured output
#                                             (a JSON line / stream-json event); read via
#                                             field/fields/subtract below (structured-first)
#                              "session-file" usage lives in an on-disk session artifact the
#                                             backend writes; read after the run (populated in
#                                             a later phase — see _usage_from_session_file)
#                              "regex"        parse the backend's prose summary as an explicit
#                                             last resort (fragile, vendor-specific)
#                              "none"         the backend reports no reliable count → unknown
#                            Structured-first: prefer inline-json/session-file; regex is only a
#                            declared fallback; an unknown/absent source reads as "none" (honest
#                            unknown — never a guessed number).
#                  strategy: LEGACY, superseded by `source` — "json" maps to "inline-json" and
#                            "regex" maps to "regex" during the transition (accepted, but `source`
#                            wins when both are present).
#                  field:    dotted path into a JSON output line (inline-json, single count)
#                  fields:   list of dotted paths summed (inline-json; e.g. non-cached
#                            input + output reported separately)
#                  subtract: list of dotted paths subtracted when present (inline-json;
#                            e.g. a cached-input count folded into a total)
#                  aggregate: "sum" | (default) "last" — how the inline-json resolver combines the
#                            matching events. "last" reads the final matching JSON object (the usual
#                            end-of-run summary line). "sum" totals EVERY matching event, for a
#                            backend that emits one usage event per step with no cumulative summary
#                            (e.g. opencode's repeated `step_finish`); applies to both tokens and cost.
#                  pattern:  a regex whose capture groups are summed over the LAST match. Primary
#                            for the `regex` source (one group keeps its plain single-count meaning);
#                            on an `inline-json` source it is an optional declared FALLBACK, tried
#                            only when the structured read finds nothing (never ahead of the JSON).
#                  cost_field: a dotted path to the backend's own reported run cost in USD
#                            (inline-json; e.g. "total_cost_usd" in a stream-json result
#                            event, or a list of alternative paths for session-file — the first
#                            that resolves wins). Read by extract_cost; absent → cost unknown.
#                  --- session-file keys (source == "session-file"): usage lives in an on-disk
#                      JSONL artifact the backend writes; read AFTER the run ---
#                  session_id_pattern: a regex whose first capture group recovers the session id
#                            from the CLI output (e.g. the "--resume=<uuid>" line). The captured id
#                            is validated as a strict UUID before it is templated into a path — a
#                            failing id leaves the source unresolved (no attacker-influenced path).
#                  path_template: the session file's path, with a "{id}" placeholder filled by the
#                            validated captured id (a leading "~" expands to the home dir), OR a
#                            "{log}" placeholder filled by an engine-provided run-scoped log path
#                            (for a backend the engine points at a log file it created).
#                  log_args:  args the engine appends to the invocation so a backend that only
#                            writes usage on request logs to an engine-owned path — the "{log}"
#                            token is replaced with that path (e.g. aider's --analytics-log).
#                  event / event_field: select the usage-bearing JSONL event — the object whose
#                            `event_field` (default "type") equals `event`. Absent `event` reads
#                            every object. `fields`/`subtract` then read tokens off the selected
#                            event(s) and `aggregate: sum` totals them (else the last resolving one).
#                  fallback:  a nested usage spec tried when this source resolves nothing (e.g. a
#                            `regex` prose fallback for a session file that is absent/renamed);
#                            chained generically — a fallback may itself declare a fallback.
#                Counts may be human-formatted ("29,500", "629.8k", "1.2M"). Absent,
#                malformed, or unmatched → usage reads as unknown; never an error.
#   usage_mode   str | None — opt-in structured output: when set (e.g. "json"), build_command
#                appends `usage_mode_args` so the backend emits machine-readable usage; absent
#                (the default) keeps the backend's live text stream untouched. When the appended
#                args select a line-delimited event stream (``--output-format stream-json``), the
#                dispatch/echo path renders the assistant text deltas live (see is_stream_json)
#                while the final ``result`` event still carries the usage/cost the hints read
#   usage_mode_args  list[str] — the backend's own structured-output flag(s) to append when
#                `usage_mode` is set (e.g. ["--output-format", "stream-json", "--verbose"]); inert
#                otherwise. Prefer a *streaming* event format over a single end-of-run JSON blob so
#                the live conversation is preserved
#   subagent_model  dict | None — backend-neutral sub-agent model steering: how a per-stage
#                sub-agent model (roles.yaml `subagent_models`) is delivered on the command line.
#                  flag: the CLI flag that carries the directive (e.g. "--agents")
#                  arg:  a template whose "$MODEL" is replaced with the resolved sub-agent model
#                        id; when empty, the model id itself is passed as the flag's value
#                When this block is declared AND a `subagent_models` entry applies to the dispatched
#                stage, build_command appends `[flag, rendered_arg]` so that stage's *sub-agents*
#                use the cheaper model while the main session keeps its role `model`. A backend
#                whose manifest omits this block declares nothing and the feature no-ops
#                (byte-identical dispatch). The engine never invents a flag — it only appends what
#                the manifest declares.


def load_agent(settings: Settings, name: str) -> dict[str, Any]:
    """Load one agent manifest, or raise ``FileNotFoundError`` naming the expected path."""
    path = settings.agents_dir / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"agent manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def available_agents(settings: Settings) -> list[str]:
    """The agent names for which a manifest exists (sorted); empty when none are configured."""
    d = settings.agents_dir
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def agent_command(manifest: dict[str, Any]) -> str:
    """The executable the manifest invokes (empty string when unset)."""
    return str(manifest.get("command") or "").strip()


def agent_family(manifest: dict[str, Any]) -> str:
    """The declared model family for the diversity precheck; '' when it depends on the chosen model."""
    return str(manifest.get("family") or "").strip()


def is_headless(manifest: dict[str, Any]) -> bool:
    """Whether the agent can be dispatched with no interactive IDE (default True)."""
    return bool(manifest.get("headless", True))


def is_stream_json(manifest: dict[str, Any]) -> bool:
    """Whether the backend is dispatched in a line-delimited JSON *event stream* mode.

    True only when ``usage_mode`` is set AND the appended ``usage_mode_args`` select
    ``stream-json`` (Claude Code's ``--output-format stream-json``): the backend then emits one
    JSON event per line, so the dispatch/echo path renders the assistant text deltas live instead
    of the raw NDJSON, while the final ``result`` event still carries the usage/cost the hints
    read. A backend without ``usage_mode`` set, or one whose structured output is a single
    end-of-run blob (``--output-format json``), reads as False and streams its native text
    untouched."""
    if not str(manifest.get("usage_mode") or "").strip():
        return False
    args = manifest.get("usage_mode_args") or []
    return any("stream-json" in str(a) for a in args)


def build_command(
    manifest: dict[str, Any], prompt: str, *, model: str = "", subagent_model: str = ""
) -> tuple[list[str], Optional[str]]:
    """Build the agent invocation from a manifest.

    Returns ``(argv, stdin)``: ``argv`` is the full argument vector (no shell), and ``stdin`` is the prompt
    text when the manifest passes the prompt via stdin, else ``None``. Deterministic given its inputs — the
    same (manifest, prompt, model, subagent_model) always yields the same invocation.

    ``subagent_model`` (empty by default) steers this stage's *sub-agents* to a cheaper model: it is
    emitted only when it is non-empty AND the manifest declares a ``subagent_model`` transport
    block; otherwise it changes nothing, so an unset stage or a backend without the block dispatches
    byte-identically. The engine never invents a flag — it emits only the manifest-declared directive.

    Raises ``ValueError`` if the manifest declares no ``command``.
    """
    command = agent_command(manifest)
    if not command:
        raise ValueError("agent manifest declares no `command`")
    argv: list[str] = [command]
    argv += [str(a) for a in (manifest.get("base_args") or [])]
    # The fresh-session hook: a backend whose CLI would resume prior conversation state declares
    # its no-resume / new-session flag(s) here, so every dispatch is a clean session by
    # construction. The engine itself never emits a resume/continue flag.
    argv += [str(a) for a in (manifest.get("new_session_args") or [])]
    # Opt-in structured output (usage_mode): when the manifest sets `usage_mode`, its own
    # `usage_mode_args` (e.g. ["--output-format", "json"]) are appended so token usage becomes
    # machine-readable. Default off preserves the live text stream; the engine stays
    # backend-neutral — it never invents a flag, it only appends what the manifest declares.
    if str(manifest.get("usage_mode") or "").strip():
        argv += [str(a) for a in (manifest.get("usage_mode_args") or [])]

    model_flag = manifest.get("model_flag")
    if model_flag and model:
        argv += [str(model_flag), model]

    # Backend-neutral sub-agent model steering: when a `subagent_models` entry (roles.yaml) applies
    # to the dispatched stage AND the manifest declares how to carry it, emit the declared directive
    # so this stage's *sub-agents* use the cheaper model while the main session keeps its role
    # `model`. A backend without a `subagent_model` block declares nothing and this no-ops — the
    # engine never invents a flag, it only appends what the manifest declares.
    if subagent_model:
        directive = manifest.get("subagent_model")
        if isinstance(directive, dict):
            flag = str(directive.get("flag") or "").strip()
            if flag:
                arg_tmpl = str(directive.get("arg") or "")
                rendered = (
                    arg_tmpl.replace("$MODEL", subagent_model) if arg_tmpl else subagent_model
                )
                argv += [flag, rendered]

    via = str(manifest.get("prompt_via") or "arg").strip().lower()
    prompt_flag = manifest.get("prompt_flag")
    if via == "stdin":
        if prompt_flag:
            argv.append(str(prompt_flag))
        return argv, prompt
    # prompt_via == "arg": the prompt is the final argument, optionally preceded by its flag.
    if prompt_flag:
        argv.append(str(prompt_flag))
    argv.append(prompt)
    return argv, None


_COUNT_RE = re.compile(r"^([0-9][0-9,_]*(?:\.[0-9]+)?)\s*([kKmM]?)$")


def _parse_count(raw: str) -> Optional[int]:
    """Parse one human-formatted token count to an integer, or ``None`` when non-numeric.

    Accepts plain integers (``"9200"``), thousands separators (``"29,500"``, ``"29_500"``), and
    the abbreviated units agent CLIs print (``"629.8k"`` → 629800, ``"1.2M"`` → 1200000;
    case-insensitive k/M). Pure and total — any other input reads as ``None``, never an error.
    """
    m = _COUNT_RE.match(str(raw).strip())
    if not m:
        return None
    number = m.group(1).replace(",", "").replace("_", "")
    scale = {"k": 1_000, "m": 1_000_000}.get(m.group(2).lower(), 1)
    try:
        return round(float(number) * scale)
    except ValueError:
        return None


def _json_field(obj: Any, dotted: str) -> Optional[int]:
    """Walk a dotted path into a parsed JSON object and coerce the leaf to ``int``, else ``None``.

    Numeric leaves pass through; string leaves go through :func:`_parse_count`, so a service
    reporting ``"629.8k"`` reads the same as one reporting ``629800``.
    """
    node = obj
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, bool):
        return None
    if isinstance(node, int):
        return node
    if isinstance(node, float):
        return round(node)
    if isinstance(node, str):
        return _parse_count(node)
    return None


_N = TypeVar("_N", int, float)


def _sum_over_json_lines(output: str, extract: Callable[[Any], Optional[_N]]) -> Optional[_N]:
    """Total ``extract(obj)`` over every JSON-object line where it resolves; ``None`` when none do.

    For a backend that emits one usage-bearing event per step (opencode's repeated ``step_finish``)
    with no final cumulative summary, the per-run figure is the SUM across all matching events, not
    the last match. A line that isn't a lone JSON object, or whose ``extract`` yields ``None``, is
    skipped. Generic over ``int`` (tokens) and ``float`` (cost). Never raises.
    """
    total: Optional[_N] = None
    for line in output.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = extract(obj)
        if value is not None:
            total = value if total is None else total + value
    return total


def _sum_fields(obj: Any, fields: list[str], subtract: list[str]) -> Optional[int]:
    """Sum ``fields`` from one JSON object, minus any resolvable ``subtract`` paths, else ``None``.

    The object counts only when EVERY ``fields`` path resolves to a number — their sum, minus the
    ``subtract`` paths that resolve (a missing subtract path reads as 0, so an optional cached-token
    field degrades gracefully). Returns ``None`` when any required field is absent, so a partial or
    unrelated object never contributes a half-count. Shared by the inline-json and session-file
    resolvers so both read a manifest's ``fields``/``subtract`` identically.
    """
    values = [_json_field(obj, f) for f in fields]
    if any(v is None for v in values):
        return None
    total = sum(v for v in values if v is not None)
    return total - sum(v for p in subtract if (v := _json_field(obj, p)) is not None)


def _usage_from_json(
    output: str, fields: list[str], subtract: list[str], *, aggregate: str = "last"
) -> Optional[int]:
    """Sum ``fields`` (minus any resolvable ``subtract`` paths) from the output's JSON usage.

    An object counts only when EVERY ``fields`` path resolves to a number — their sum, minus the
    ``subtract`` paths that resolve (a missing subtract path reads as 0, so an optional
    cached-token field degrades gracefully). With ``aggregate="last"`` (the default) output lines
    are scanned last-to-first — the usage summary is typically the final JSON line an agent prints
    — and a whole-output JSON document is tried last. With ``aggregate="sum"`` the value is totaled
    across EVERY matching line (a step-wise stream with no cumulative summary; the whole-output
    fallback is inapplicable and skipped).
    """

    def from_obj(obj: Any) -> Optional[int]:
        return _sum_fields(obj, fields, subtract)

    if aggregate == "sum":
        return _sum_over_json_lines(output, from_obj)

    for line in reversed(output.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = from_obj(obj)
        if value is not None:
            return value
    try:
        return from_obj(json.loads(output))
    except json.JSONDecodeError:
        return None


def _usage_from_regex(output: str, pattern: str) -> Optional[int]:
    """Sum the capture groups of the LAST ``pattern`` match, each via :func:`_parse_count`.

    A single-group pattern keeps its plain single-count meaning; a multi-group pattern (e.g.
    non-cached input and output captured separately) yields the groups' sum. A groupless pattern
    parses the whole match. A match whose groups all fail to parse falls back to the previous
    match; ``None`` when nothing usable matches or the pattern itself is broken.
    """
    try:
        matches = list(re.finditer(pattern, output))
    except re.error:
        return None
    for m in reversed(matches):  # the last match is the final (cumulative) summary
        groups = m.groups() or (m.group(0),)
        counts = [c for g in groups if g is not None and (c := _parse_count(g)) is not None]
        if counts:
            return sum(counts)
    return None


# The declarative usage-source taxonomy (Track A): usage is resolved structured-first via an
# explicit ``source``, with regex demoted to an explicit last resort and every other case reading
# as honest-unknown. The public helpers below dispatch on the *resolved* source; the resolution is
# the only thing this contract changes — the two-arg signatures and the downstream chain
# (DispatchResult → StageResult → progress.md) are preserved.
_USAGE_SOURCES = frozenset({"inline-json", "session-file", "regex", "none"})
# Back-compat: the legacy ``strategy`` field maps onto the new taxonomy during the transition.
_LEGACY_STRATEGY = {"json": "inline-json", "regex": "regex"}


def _resolve_source(spec: dict[str, Any]) -> str:
    """Resolve a manifest ``usage`` block to one normalized source in the taxonomy.

    Prefers an explicit ``source`` (``inline-json`` | ``session-file`` | ``regex`` | ``none``);
    when ``source`` is absent, maps the legacy ``strategy`` (``json`` → ``inline-json``, ``regex``
    → ``regex``). Anything unrecognized — an explicit bogus ``source``, an unknown ``strategy``, or
    no declaration at all — resolves to ``none`` (honest-unknown), never a guessed count.
    """
    source = str(spec.get("source") or "").strip().lower()
    if source:
        return source if source in _USAGE_SOURCES else "none"
    strategy = str(spec.get("strategy") or "").strip().lower()
    return _LEGACY_STRATEGY.get(strategy, "none")


@dataclass(frozen=True)
class _UsageContext:
    """Extra dispatch context a source resolver may need beyond the manifest + output.

    The public :func:`extract_usage`/:func:`extract_cost` helpers preserve their two-argument
    positional contract (``manifest, output``) that the call sites in :mod:`threepowers.runner`
    depend on; the runner threads any extra context via keyword-only arguments that build this
    internal seam. It carries:

    - ``output``: the dispatch's captured stdout+stderr, from which the ``session-file`` resolver
      recovers the session id;
    - ``home``: the home directory a ``~``-anchored ``path_template`` resolves against (injectable
      so a test points it at a temp dir; defaults to the real home);
    - ``session_log``: a run-scoped log path the engine created and pointed the backend at (a
      ``{log}`` ``path_template``, e.g. aider's ``--analytics-log``); ``None`` when the backend
      writes its own session file.
    """

    output: str
    home: Path = field(default_factory=Path.home)
    session_log: Optional[Path] = None


def _aggregate_mode(spec: dict[str, Any]) -> str:
    """The inline-json cross-event aggregation: ``"sum"`` totals every matching event, else last.

    ``"sum"`` (declared by a backend that emits one usage event per step with no cumulative
    summary, e.g. opencode's repeated ``step_finish``) totals the value across all matching events;
    anything else — including an absent field — reads as ``"last"`` (the final matching object).
    """
    return "sum" if str(spec.get("aggregate") or "").strip().lower() == "sum" else "last"


def _field_paths(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The manifest's token ``field``/``fields`` (summed) and ``subtract`` (removed) dotted paths.

    A single dotted ``field`` collapses to a one-element ``fields`` list; a ``fields`` list is
    taken as-is. ``subtract`` is the optional cached-count paths folded out of the sum. Both are
    normalized (stripped, empties dropped). Shared by the inline-json and session-file resolvers.
    """
    single = str(spec.get("field") or "").strip()
    raw_fields = spec.get("fields")
    fields = (
        [single]
        if single
        else [str(f).strip() for f in raw_fields if str(f).strip()]
        if isinstance(raw_fields, list)
        else []
    )
    raw_sub = spec.get("subtract")
    subtract = (
        [str(p).strip() for p in raw_sub if str(p).strip()] if isinstance(raw_sub, list) else []
    )
    return fields, subtract


def _usage_from_inline_json(spec: dict[str, Any], output: str) -> Optional[int]:
    """Sum the manifest's ``field``/``fields`` (minus ``subtract``) from the output's JSON usage.

    The ``inline-json`` resolver: a single dotted ``field`` or a ``fields`` list is summed, and any
    resolvable ``subtract`` paths (cached counts folded into a total) are removed. With
    ``aggregate: sum`` the total is summed across every matching event rather than read from the
    last one. Returns ``None`` when no usable field is declared or none resolves.
    """
    fields, subtract = _field_paths(spec)
    if not fields:
        return None
    return _usage_from_json(output, fields, subtract, aggregate=_aggregate_mode(spec))


# SEC-001: the captured session id is templated into a filesystem path, so it is accepted only as
# a strict UUID (the shape every session-file backend prints). This inherently rejects path
# separators, ``..`` traversal, and any other attacker-influenced id — a failing id leaves the
# source unresolved (fall to the declared fallback, then honest-unknown), never a path read.
_SESSION_ID_RE = re.compile(
    r"\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)


def _valid_session_id(candidate: str) -> bool:
    """Whether ``candidate`` is a strict UUID safe to template into a path (SEC-001)."""
    return bool(_SESSION_ID_RE.match(candidate))


def _capture_session_id(spec: dict[str, Any], output: str) -> Optional[str]:
    """Recover the session id from the run output via the manifest ``session_id_pattern``.

    The pattern's first capture group (or the whole match when it has no group) is the raw id; it
    is **not** trusted here — :func:`_valid_session_id` validates it before it reaches a path.
    Returns ``None`` when no pattern is declared, the pattern is broken, or nothing matches. Never
    raises.
    """
    pattern = str(spec.get("session_id_pattern") or "")
    if not pattern:
        return None
    try:
        match = re.search(pattern, output)
    except re.error:
        return None
    if not match:
        return None
    return match.group(1) if match.groups() else match.group(0)


def _expand_home(raw: str, home: Path) -> Path:
    """Resolve a path template, expanding a leading ``~`` against ``home`` (not the process env).

    Expanding against the injected ``home`` keeps the resolver deterministic and testable rather
    than depending on ``$HOME`` at read time. A path with no ``~`` prefix is taken verbatim.
    """
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def _resolve_session_path(spec: dict[str, Any], ctx: _UsageContext) -> Optional[Path]:
    """Resolve the session file's path from ``path_template``, or ``None`` when it cannot be.

    Two placeholders are supported: ``{id}`` is filled by the captured, UUID-validated session id
    (SEC-001); ``{log}`` is filled by the engine-provided ``ctx.session_log`` (a run-scoped path the
    engine created for a backend it points at a log file). A template with neither placeholder is a
    literal path. Returns ``None`` — the source stays unresolved — when the template is absent, an
    ``{id}`` cannot be captured or fails UUID validation, or a ``{log}`` was requested but no log
    path was provided. Never raises.
    """
    template = str(spec.get("path_template") or "").strip()
    if not template:
        return None
    if "{id}" in template:
        session_id = _capture_session_id(spec, ctx.output)
        if session_id is None or not _valid_session_id(session_id):
            return None
        return _expand_home(template.replace("{id}", session_id), ctx.home)
    if "{log}" in template:
        if ctx.session_log is None:
            return None
        return _expand_home(template.replace("{log}", str(ctx.session_log)), ctx.home)
    return _expand_home(template, ctx.home)


def _read_jsonl_events(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL session file into its list of JSON objects; ``[]`` on any read/parse trouble.

    One JSON object per line (blank and non-object lines skipped). A missing/unreadable file or a
    malformed line yields no events rather than raising — session-file usage is advisory (PAT-002).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def _select_events(spec: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The events whose ``event_field`` (default ``type``) equals the manifest ``event`` selector.

    An absent/empty ``event`` selector matches every object (the whole file is one usage stream).
    """
    selector = str(spec.get("event") or "").strip()
    if not selector:
        return events
    field_name = str(spec.get("event_field") or "type").strip()
    return [e for e in events if str(e.get(field_name)) == selector]


def _fold_events(
    events: list[dict[str, Any]], extract: Callable[[dict[str, Any]], Optional[_N]], aggregate: str
) -> Optional[_N]:
    """Fold ``extract`` over selected events: total them (``sum``) or take the last resolving one.

    ``aggregate == "sum"`` totals every event that resolves (a per-step stream, e.g. aider's
    repeated ``message_send``); otherwise the last resolving event wins (a single terminal event,
    e.g. copilot's ``session.shutdown``). ``None`` when none resolve. Generic over int/float.
    """
    if aggregate == "sum":
        total: Optional[_N] = None
        for event in events:
            value = extract(event)
            if value is not None:
                total = value if total is None else total + value
        return total
    for event in reversed(events):
        value = extract(event)
        if value is not None:
            return value
    return None


def _usage_from_session_file(spec: dict[str, Any], ctx: _UsageContext) -> Optional[int]:
    """Resolve tokens from the backend's on-disk JSONL session artifact.

    Resolves the session file (``path_template`` with a UUID-validated ``{id}`` or an engine
    ``{log}`` path — SEC-001), reads its JSONL events, selects the usage-bearing ``event``, and
    sums the manifest's ``fields`` (minus ``subtract``) — totalled across events with
    ``aggregate: sum`` (aider), else the last resolving event (copilot's ``session.shutdown``). A
    missing id/file/field or a schema mismatch reads as ``None`` (never raises), so the source
    degrades to its declared fallback and then honest-unknown (PAT-002).
    """
    path = _resolve_session_path(spec, ctx)
    if path is None or not path.is_file():
        return None
    fields, subtract = _field_paths(spec)
    if not fields:
        return None
    events = _select_events(spec, _read_jsonl_events(path))
    return _fold_events(events, lambda e: _sum_fields(e, fields, subtract), _aggregate_mode(spec))


def _usage_for_spec(spec: dict[str, Any], ctx: _UsageContext) -> Optional[int]:
    """Resolve tokens for one usage spec on its ``source``, then chain to a declared ``fallback``.

    Dispatches on the resolved ``source`` (``inline-json`` reads the JSON ``fields``, with a
    declared ``pattern`` as a structured-first regex fallback; ``session-file`` reads the on-disk
    artifact; ``regex`` parses the prose; ``none`` is honest-unknown). When the primary source
    resolves nothing and a nested ``fallback`` spec is declared, that fallback is resolved the same
    way — chained generically, so a fallback may itself declare a fallback. ``None`` when neither
    the source nor any fallback resolves.
    """
    source = _resolve_source(spec)
    value: Optional[int]
    if source == "inline-json":
        value = _usage_from_inline_json(spec, ctx.output)
        if value is None:
            # Declared regex fallback: a backend that normally emits structured JSON but printed
            # only its prose summary this run (structured output unavailable) may declare a
            # `pattern`. It fires ONLY when the structured read found nothing — never ahead of it.
            pattern = str(spec.get("pattern") or "")
            value = _usage_from_regex(ctx.output, pattern) if pattern else None
    elif source == "session-file":
        value = _usage_from_session_file(spec, ctx)
    elif source == "regex":  # explicit last-resort fallback: parse the backend's prose summary
        pattern = str(spec.get("pattern") or "")
        value = _usage_from_regex(ctx.output, pattern) if pattern else None
    else:
        value = None  # source == "none" (or unrecognized) → honest unknown
    if value is not None:
        return value
    fallback = spec.get("fallback")
    return _usage_for_spec(fallback, ctx) if isinstance(fallback, dict) else None


def extract_usage(
    manifest: dict[str, Any],
    output: str,
    *,
    home: Optional[Path] = None,
    session_log: Optional[Path] = None,
) -> Optional[int]:
    """The consumed token count one dispatch's agent output reports, or ``None`` when unknown.

    Driven by the manifest's optional ``usage`` block, dispatched on its resolved ``source``
    (see :func:`_resolve_source`; legacy ``strategy: json``/``regex`` maps to
    ``inline-json``/``regex``):

    - ``inline-json`` reads a dotted ``field`` (or a ``fields`` list summed, minus optional
      ``subtract`` paths for cached counts) from the run's JSON output — totaled across events when
      ``aggregate: sum`` — and, if that resolves nothing but a ``pattern`` is also declared, falls
      back to parsing that regex (structured-first: the regex fires only when the JSON is absent);
    - ``session-file`` reads the backend's on-disk JSONL session artifact (see
      :func:`_usage_from_session_file`);
    - ``regex`` sums the capture groups of the last ``pattern`` match — an explicit last-resort
      *fallback* for backends with no structured output;
    - ``none`` (and any unrecognized source) reads as ``None``.

    When a source resolves nothing and the block declares a nested ``fallback`` spec (e.g. a
    ``regex`` prose fallback under a ``session-file`` source), it is chained generically.

    The two positional arguments ``(manifest, output)`` are the preserved public contract
    (CON-002); ``home``/``session_log`` are keyword-only context a ``session-file`` source needs
    (the home a ``~`` template resolves against and an engine-provided ``{log}`` path), supplied by
    the runner call site and defaulted for two-argument callers.

    Counts tolerate thousands separators and abbreviated units (``629.8k``, ``1.2M``). A backend
    that declares no block, a malformed block, or output carrying no usage all read as ``None`` —
    usage is strictly advisory and never fails a dispatch. Never raises.
    """
    spec = manifest.get("usage")
    if not isinstance(spec, dict) or not output:
        return None
    ctx = _UsageContext(output=output, home=home or Path.home(), session_log=session_log)
    return _usage_for_spec(spec, ctx)


def _json_float(obj: Any, dotted: str) -> Optional[float]:
    """Walk a dotted path into a parsed JSON object and coerce the leaf to ``float``, else ``None``.

    Accepts int/float leaves directly and human-formatted numeric strings (via
    :func:`_parse_count`); a boolean or any non-numeric leaf reads as ``None``."""
    node = obj
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if isinstance(node, bool):
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, str):
        parsed = _parse_count(node)
        return float(parsed) if parsed is not None else None
    return None


def _cost_from_inline_json(spec: dict[str, Any], output: str) -> Optional[float]:
    """Read the manifest's ``cost_field`` (USD) from the output's JSON lines, else ``None``.

    The ``inline-json`` cost resolver: with ``aggregate="last"`` (the default) the output's JSON
    lines are scanned last-to-first — the result summary is typically the final line — and the
    first line whose ``cost_field`` resolves to a number wins; a whole-output JSON document is
    tried last. With ``aggregate: sum`` the cost is totaled across every matching event (a step-wise
    stream with no cumulative summary), in step with the token resolver.
    """
    field = str(spec.get("cost_field") or "").strip()
    if not field:
        return None
    if _aggregate_mode(spec) == "sum":
        return _sum_over_json_lines(output, lambda obj: _json_float(obj, field))
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = _json_float(obj, field)
        if value is not None:
            return value
    try:
        return _json_float(json.loads(output), field)
    except json.JSONDecodeError:
        return None


def _cost_paths(spec: dict[str, Any]) -> list[str]:
    """The manifest's cost dotted path(s): a single ``cost_field`` string or a list of alternatives.

    A string is a one-element list; a list is taken as-is (the session-file resolver tries each in
    order and takes the first that resolves, e.g. aider's ``cost`` then ``total_cost``). Normalized
    (stripped, empties dropped); ``[]`` when no ``cost_field`` is declared.
    """
    raw = spec.get("cost_field")
    if isinstance(raw, str):
        stripped = raw.strip()
        return [stripped] if stripped else []
    if isinstance(raw, list):
        return [str(p).strip() for p in raw if str(p).strip()]
    return []


def _cost_from_session_file(spec: dict[str, Any], ctx: _UsageContext) -> Optional[float]:
    """Resolve run cost (USD) from the backend's on-disk JSONL session artifact.

    Companion to :func:`_usage_from_session_file`: resolves the same session file and selected
    ``event``, then reads the first resolving ``cost_field`` path per event — totalled across
    events with ``aggregate: sum`` (aider's per-message ``cost``), else the last resolving event. A
    backend that reports no USD cost declares no ``cost_field`` and reads as ``None`` (copilot,
    whose credits/premium-requests are not USD). Missing file/field → ``None``; never raises.
    """
    cost_fields = _cost_paths(spec)
    if not cost_fields:
        return None
    path = _resolve_session_path(spec, ctx)
    if path is None or not path.is_file():
        return None
    events = _select_events(spec, _read_jsonl_events(path))

    def from_event(event: dict[str, Any]) -> Optional[float]:
        for field_path in cost_fields:
            value = _json_float(event, field_path)
            if value is not None:
                return value
        return None

    return _fold_events(events, from_event, _aggregate_mode(spec))


def _cost_for_spec(spec: dict[str, Any], ctx: _UsageContext) -> Optional[float]:
    """Resolve cost for one usage spec on its ``source``, then chain to a declared ``fallback``.

    ``inline-json`` reads the ``cost_field`` from the run's JSON; ``session-file`` reads it from the
    on-disk artifact; ``regex``/``none`` carry no machine-stable cost (a prose summary is not a
    trustworthy cost source). When the source resolves nothing and a nested ``fallback`` spec is
    declared, it is chained the same way — so a ``session-file`` cost may fall through to a
    fallback that itself declares a ``cost_field``. ``None`` when nothing resolves.
    """
    source = _resolve_source(spec)
    value: Optional[float]
    if source == "inline-json":
        value = _cost_from_inline_json(spec, ctx.output)
    elif source == "session-file":
        value = _cost_from_session_file(spec, ctx)
    else:
        value = None  # regex / none / unrecognized → no machine-stable cost
    if value is not None:
        return value
    fallback = spec.get("fallback")
    return _cost_for_spec(fallback, ctx) if isinstance(fallback, dict) else None


def extract_cost(
    manifest: dict[str, Any],
    output: str,
    *,
    home: Optional[Path] = None,
    session_log: Optional[Path] = None,
) -> Optional[float]:
    """The run cost in USD one dispatch's agent output reports, or ``None`` when unknown.

    Driven by the manifest's optional ``usage`` block, dispatched on its resolved ``source`` in
    step with :func:`extract_usage`: ``inline-json`` reads the dotted ``cost_field`` (e.g.
    ``total_cost_usd`` in a stream-json ``result`` event) from the run's JSON output;
    ``session-file`` reads the ``cost_field`` (or the first of a list of alternatives) from the
    backend's on-disk session artifact; ``regex`` and ``none`` carry no machine-stable cost and read
    as ``None`` (a prose summary is not a trustworthy cost source). A declared ``fallback`` is
    chained when the source resolves no cost.

    ``home``/``session_log`` are the keyword-only ``session-file`` context, in step with
    :func:`extract_usage`; the two positional arguments are the preserved public contract. A backend
    that declares no ``cost_field``, a malformed value, or output carrying no cost all read as
    ``None`` — cost is strictly advisory and never fails a dispatch. Never raises."""
    spec = manifest.get("usage")
    if not isinstance(spec, dict) or not output:
        return None
    ctx = _UsageContext(output=output, home=home or Path.home(), session_log=session_log)
    return _cost_for_spec(spec, ctx)


def needs_session_log(manifest: dict[str, Any]) -> bool:
    """Whether this backend needs the engine to inject a run-scoped session-log path.

    True when a ``session-file`` usage block declares ``log_args`` — a backend that only writes its
    usage artifact when the engine points it at a log file (aider's ``--analytics-log``). The engine
    creates a per-run path, fills the ``{log}`` placeholder via :func:`session_log_args`, and reads
    that same path back through the ``{log}`` ``path_template``. A backend that writes its own
    session file (copilot) declares no ``log_args`` and reads as False.
    """
    spec = manifest.get("usage")
    if not isinstance(spec, dict) or _resolve_source(spec) != "session-file":
        return False
    return isinstance(spec.get("log_args"), list) and bool(spec.get("log_args"))


def session_log_args(manifest: dict[str, Any], log_path: Path) -> list[str]:
    """The manifest ``log_args`` with the ``{log}`` placeholder filled by ``log_path``.

    These are appended to the invocation so the backend writes its session/analytics artifact to the
    engine-owned ``log_path`` (which the ``{log}`` ``path_template`` then reads back). ``[]`` when
    the manifest declares no ``log_args`` — the engine invents no flag, it only appends what the
    manifest declares (PAT-001).
    """
    spec = manifest.get("usage")
    if not isinstance(spec, dict):
        return []
    raw = spec.get("log_args")
    if not isinstance(raw, list):
        return []
    return [str(arg).replace("{log}", str(log_path)) for arg in raw]
