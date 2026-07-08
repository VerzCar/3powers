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
#                  field:    dotted path into a JSON output line (json strategy)
#                  pattern:  a regex whose group 1 captures the token count (regex strategy)
#                Absent, malformed, or unmatched → usage reads as unknown; never an error.


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
    manifest: dict[str, Any], prompt: str, *, model: str = ""
) -> tuple[list[str], Optional[str]]:
    """Build the agent invocation from a manifest.

    Returns ``(argv, stdin)``: ``argv`` is the full argument vector (no shell), and ``stdin`` is the prompt
    text when the manifest passes the prompt via stdin, else ``None``. Deterministic given its inputs — the
    same (manifest, prompt, model) always yields the same invocation.

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

    model_flag = manifest.get("model_flag")
    if model_flag and model:
        argv += [str(model_flag), model]

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


def _json_field(obj: Any, dotted: str) -> Optional[int]:
    """Walk a dotted path into a parsed JSON object and coerce the leaf to ``int``, else ``None``."""
    node = obj
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    try:
        return int(node)
    except (TypeError, ValueError):
        return None


def _usage_from_json(output: str, field_path: str) -> Optional[int]:
    # Scan output lines last-to-first: the usage summary is typically the final JSON line an
    # agent prints; a whole-output JSON document is tried last.
    for line in reversed(output.splitlines()):
        line = line.strip()
        if not (line.startswith("{") and line.endswith("}")):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        value = _json_field(obj, field_path)
        if value is not None:
            return value
    try:
        return _json_field(json.loads(output), field_path)
    except json.JSONDecodeError:
        return None


def _usage_from_regex(output: str, pattern: str) -> Optional[int]:
    try:
        matches = re.findall(pattern, output)
    except re.error:
        return None
    for raw in reversed(matches):  # the last match is the final (cumulative) summary
        digits = str(raw).replace(",", "").replace("_", "").strip()
        try:
            return int(digits)
        except ValueError:
            continue
    return None


def extract_usage(manifest: dict[str, Any], output: str) -> Optional[int]:
    """The total token count one dispatch's agent output reports, or ``None`` when unknown.

    Driven entirely by the manifest's optional ``usage`` hint — ``strategy: json`` reads a dotted
    ``field`` from the last JSON line of the output, ``strategy: regex`` takes group 1 of the last
    ``pattern`` match (thousands separators tolerated). A backend that declares no hint, a
    malformed hint, or output that simply carries no usage all read as ``None`` — usage is
    strictly advisory and never fails a dispatch. Never raises.
    """
    spec = manifest.get("usage")
    if not isinstance(spec, dict) or not output:
        return None
    strategy = str(spec.get("strategy") or "").strip().lower()
    if strategy == "json":
        field_path = str(spec.get("field") or "").strip()
        return _usage_from_json(output, field_path) if field_path else None
    if strategy == "regex":
        pattern = str(spec.get("pattern") or "")
        return _usage_from_regex(output, pattern) if pattern else None
    return None
