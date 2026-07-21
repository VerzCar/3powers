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
from typing import Any, Optional

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
#                  strategy: "json" | "regex"
#                  field:    dotted path into a JSON output line (json strategy, single count)
#                  fields:   list of dotted paths summed (json strategy; e.g. non-cached
#                            input + output reported separately)
#                  subtract: list of dotted paths subtracted when present (json strategy;
#                            e.g. a cached-input count folded into a total)
#                  pattern:  a regex whose capture groups are summed over the LAST match
#                            (regex strategy; one group keeps its plain single-count meaning)
#                Counts may be human-formatted ("29,500", "629.8k", "1.2M"). Absent,
#                malformed, or unmatched → usage reads as unknown; never an error.
#   usage_mode   str | None — opt-in structured output: when set (e.g. "json"), build_command
#                appends `usage_mode_args` so the backend emits machine-readable usage; absent
#                (the default) keeps the backend's live text stream untouched
#   usage_mode_args  list[str] — the backend's own structured-output flag(s) to append when
#                `usage_mode` is set (e.g. ["--output-format", "json"]); inert otherwise
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


def _usage_from_json(output: str, fields: list[str], subtract: list[str]) -> Optional[int]:
    """Sum ``fields`` (minus any resolvable ``subtract`` paths) from the output's JSON usage line.

    An object counts only when EVERY ``fields`` path resolves to a number — their sum, minus the
    ``subtract`` paths that resolve (a missing subtract path reads as 0, so an optional
    cached-token field degrades gracefully). Output lines are scanned last-to-first — the usage
    summary is typically the final JSON line an agent prints; a whole-output JSON document is
    tried last.
    """

    def from_obj(obj: Any) -> Optional[int]:
        values = [_json_field(obj, f) for f in fields]
        if any(v is None for v in values):
            return None
        total = sum(v for v in values if v is not None)
        return total - sum(v for p in subtract if (v := _json_field(obj, p)) is not None)

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


def extract_usage(manifest: dict[str, Any], output: str) -> Optional[int]:
    """The consumed token count one dispatch's agent output reports, or ``None`` when unknown.

    Driven entirely by the manifest's optional ``usage`` hint — ``strategy: json`` reads a dotted
    ``field`` (or a ``fields`` list summed, minus optional ``subtract`` paths for cached counts)
    from the last JSON line of the output; ``strategy: regex`` sums the capture groups of the
    last ``pattern`` match. Counts tolerate thousands separators and abbreviated units
    (``629.8k``, ``1.2M``). A backend that declares no hint, a malformed hint, or output that
    simply carries no usage all read as ``None`` — usage is strictly advisory and never fails a
    dispatch. Never raises.
    """
    spec = manifest.get("usage")
    if not isinstance(spec, dict) or not output:
        return None
    strategy = str(spec.get("strategy") or "").strip().lower()
    if strategy == "json":
        single = str(spec.get("field") or "").strip()
        raw_fields = spec.get("fields")
        fields = (
            [single]
            if single
            else [str(f).strip() for f in raw_fields if str(f).strip()]
            if isinstance(raw_fields, list)
            else []
        )
        if not fields:
            return None
        raw_sub = spec.get("subtract")
        subtract = (
            [str(p).strip() for p in raw_sub if str(p).strip()] if isinstance(raw_sub, list) else []
        )
        return _usage_from_json(output, fields, subtract)
    if strategy == "regex":
        pattern = str(spec.get("pattern") or "")
        return _usage_from_regex(output, pattern) if pattern else None
    return None
