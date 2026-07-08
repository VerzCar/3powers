"""``3pwr`` — the 3Powers command line.

Subcommands:
  keygen        generate the independent Ed25519 signer identity (key kept outside repo)
  init          guided onboarding — make a new or existing project 3Powers-ready (layout +
                signer outside the repo + baseline config + a language adapter); --yes for CI
  gate run      run the deterministic gate suite, emit a verdict, append it to the ledger
  conformance   run only the spec-conformance trace
  verify        recompute the ledger hash chain + signatures (offline)
  signoff       append a signed human sign-off entry (a Spec-stage sign-off seals the
                approved document's hash into the signed entry)
  advance       local enforcement gate: refuse to proceed unless gate green + ledger
                verifies + the tier-required sign-off is present (+ oracle independence
                at High-risk + the approved spec unchanged)
  oracle        structural oracle independence: seal a spec-only bundle, record authoring
                (refusing the coder's model family), dispatch it headlessly + read-path
                isolated, verify from the ledger
  deps-check    probe installed third-party versions against the supported ranges (preflight)
  ready         am I ready for `3pwr run --mode auto`? — the full run preflight + a dependency
                summary; read-only, offline, the same checks init and the run use
  run           drive the whole lifecycle loop (§6): auto mode stops only at the two mandatory
                human gates (spec approval, sign-off); the native executive
                dispatches each stage to a headless agent and streams progress
  observe       §13 feedback loop: record a production signal → route to new intent, NFR-instrumentation
                coverage, and a tamper-evident, attributable runtime agent-action log
  spec diff     read-only spec-integrity report: does the spec still match its approval
                hash?
  ledger show   print the ledger

Exit codes: 0 = ok/green, 1 = gate failed / verification failed / advance refused,
2 = usage or environment error. `3pwr run` additionally uses the stable terminal contract:
3 = paused at a human gate, 4 = setup/dispatch failure (never a gate verdict).
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional


import threepowers.cli as _cli
from .. import (
    config,
    notify,
    speclock,
    style,
    workspace,
)
from ..adapters import EffectiveGates, effective_gates, run_cmd
from ..config import Settings
from ..verdict import GATE_ORDER

if TYPE_CHECKING:
    from typing import TypeAlias

    SubParsers: TypeAlias = argparse._SubParsersAction[argparse.ArgumentParser]
    AddCommon: TypeAlias = Callable[[argparse.ArgumentParser], argparse.ArgumentParser]


EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
# The stable `3pwr run` terminal contract: one documented (status, exit-code) pair
# per outcome, so a script can branch on the exit code alone —
#   0 done · 1 gates_red (a real deterministic verdict; also rejected/aborted) · 2 usage ·
#   3 paused_at_gate (a human gate awaits) · 4 setup/dispatch failure (preflight_failed,
#   dispatch_failed, artifact_missing, verdict_error — never a gate verdict).
EXIT_PAUSED = 3
EXIT_SETUP = 4


# --------------------------------------------------------------------------- helpers
def _settings(root: Optional[str]) -> Settings:
    base = Path(root).resolve() if root else None
    return Settings(root=config.find_root(base))


def _resolve_spec(s: Settings, spec: Optional[str]) -> Path:
    if spec:
        return Path(spec).resolve()
    # Native fallback: the newest spec under specs-src/ (or the legacy specs/) — exactly one per
    # feature folder, whichever layout (the spec/ workspace subfolder or the legacy flat file).
    specs = sorted(workspace.find_specs(s.root), key=lambda q: q.stat().st_mtime, reverse=True)
    if specs:
        return specs[0]
    raise FileNotFoundError("could not resolve a spec; pass --spec <path/to/spec.md>")


def _print(obj: dict, as_json: bool, human: str) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
    else:
        print(human)


def _resolve_ui(args: argparse.Namespace) -> tuple[dict[str, str], bool]:
    """Resolve ui.yaml preferences (color_mode / verbosity / layout) + a malformed flag, once per run.

    Tolerant of a not-yet-initialized repo: when no ``.3powers/`` is found (e.g. before ``3pwr init``)
    the shipped defaults are used. Cached on ``args`` so the file is read at most once."""
    cached = getattr(args, "_ui_cache", None)
    if cached is not None:
        return cached
    prefs: dict[str, str] = {"color_mode": "auto", "verbosity": "normal", "layout": "normal"}
    malformed = False
    try:
        prefs, malformed = _settings(getattr(args, "root", None)).load_ui()
    except (FileNotFoundError, OSError):
        pass  # no initialized repo yet — use the shipped defaults
    args._ui_cache = (prefs, malformed)
    return prefs, malformed


def _styler(args: argparse.Namespace, stream: Any = None) -> style.Styler:
    """A :class:`style.Styler` for one command's human output, honoring ``--json`` / ``--yes`` and the
    ui.yaml ``color_mode``. Machine output is never routed through it."""
    prefs, _ = _resolve_ui(args)
    return style.styler(
        stream if stream is not None else sys.stdout,
        as_json=getattr(args, "json", False),
        assume_yes=getattr(args, "yes", False),
        color_mode=prefs["color_mode"],
    )


def _verbosity(args: argparse.Namespace) -> str:
    """The effective verbosity for this command: ``quiet`` | ``normal`` | ``verbose``."""
    prefs, _ = _resolve_ui(args)
    return style.resolve_verbosity(
        getattr(args, "quiet", False), getattr(args, "verbose", False), prefs["verbosity"]
    )


def _compose(
    args: argparse.Namespace,
    st: style.Styler,
    *,
    title: str = "",
    subject: str = "",
    rows: Optional[list[str]] = None,
    extra: Optional[list[str]] = None,
) -> str:
    """Assemble a command's human output honoring verbosity.

    ``title`` renders a self-identifying header (hidden at ``quiet``); ``rows`` are the core result
    lines (always shown); ``extra`` are verbose-only detail lines. Detail grows monotonically
    quiet ⊆ normal ⊆ verbose, and none of this touches the ``--json`` payload."""
    v = _verbosity(args)
    out: list[str] = []
    if title and v != "quiet":
        out.append(st.header(title, subject))
    out.extend(rows or [])
    if v == "verbose":
        out.extend(extra or [])
    return "\n".join(out)


def _git_out(root: Path, args: list[str]) -> str:
    """Shell out to git; empty string on any failure (best-effort, never blocks)."""
    try:
        res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
        return res.stdout if res.returncode == 0 else ""
    except OSError:
        return ""


def _spec_approval_payload(s: Settings, spec: Optional[str]) -> dict:
    """Best-effort spec-hash fields for a Spec-stage sign-off.

    An unresolvable spec records nothing — the sign-off itself still proceeds.
    """
    try:
        spec_path = _resolve_spec(s, spec)
    except FileNotFoundError:
        return {}
    commit = _git_out(s.root, ["rev-parse", "--short", "HEAD"]).strip()
    return speclock.approval_fields(s.root, spec_path, commit=commit)


def _ask(prompt: str, default: str, *, interactive: bool) -> str:
    """Free-text prompt with a default; returns the default unchanged when non-interactive."""
    if not interactive:
        return default
    try:
        ans = input(f"{prompt} [{default}]: ").strip()
    except EOFError:
        return default
    return ans or default


def _ask_choice(prompt: str, options: list[str], default: str, *, interactive: bool) -> str:
    """Numbered single-select with a default; returns the default when non-interactive."""
    if not interactive or not options:
        return default
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}{'  (default)' if opt == default else ''}")
    di = options.index(default) + 1 if default in options else 1
    try:
        ans = input(f"select 1-{len(options)} [{di}]: ").strip()
    except EOFError:
        return default
    if not ans:
        return default
    if ans.isdigit() and 1 <= int(ans) <= len(options):
        return options[int(ans) - 1]
    return ans if ans in options else default


def _ask_multi(
    prompt: str, options: list[str], defaults: list[str], *, interactive: bool
) -> list[str]:
    """Numbered multi-select with defaults; returns the (in-option) defaults when non-interactive.

    Accepts space/comma-separated indices or names; empty input keeps the defaults. Non-interactive
    (``--yes``/``--json``/no TTY) prompts for nothing, so an init stays byte-stable."""
    in_opts = [d for d in defaults if d in options]
    if not interactive or not options:
        return in_opts
    print(prompt)
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}{'  (default)' if opt in defaults else ''}")
    di = ", ".join(str(options.index(d) + 1) for d in in_opts)
    try:
        ans = input(f"select (comma/space-separated) [{di or 'none'}]: ").strip()
    except EOFError:
        return in_opts
    if not ans:
        return in_opts
    picks: list[str] = []
    for tok in re.split(r"[,\s]+", ans):
        tok = tok.strip()
        if not tok:
            continue
        if tok.isdigit() and 1 <= int(tok) <= len(options):
            val: Optional[str] = options[int(tok) - 1]
        elif tok in options:
            val = tok
        else:
            val = None
        if val and val not in picks:
            picks.append(val)
    return picks or in_opts


def _ask_yesno(prompt: str, default: bool, *, interactive: bool) -> bool:
    """Yes/no prompt with a default; returns the default when non-interactive."""
    if not interactive:
        return default
    try:
        ans = input(f"{prompt} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
    except EOFError:
        return default
    return default if not ans else ans in ("y", "yes")


def _format_verdict(verdict, appended: Optional[dict], st: Optional[style.Styler] = None) -> str:
    """Human-readable verdict: failing gate, class, and offending item — no transcript needed.

    ``st`` colorizes the status markers consistently with the rest of the CLI; a disabled
    styler (the default) leaves the plain ✓/✗/– glyphs — the text is identical byte-for-byte to before.
    Failure detail is no longer summarized in a bottom "failures:" block: each failed gate gets its
    own panel after the pipeline view instead."""
    st = st or style.Styler()
    result = verdict.result.upper()
    head = "verdict " + (st.ok(result) if verdict.result == "pass" else st.err(result))
    lines = [f"{head}  spec={verdict.spec_id or '?'} tier={verdict.tier} adapter={verdict.adapter}"]
    for g in verdict.gates:
        extra = ""
        if g.gate == "diff_coverage" and g.details:
            extra = f"  ({g.details.get('covered_pct')}% ≥ {g.details.get('threshold')}%)"
        elif g.gate == "spec_conformance" and g.details:
            extra = f"  ({len(g.details.get('requirement_ids', []))} requirements traced)"
        glyph = st.mark(g.status) if g.status in ("pass", "fail", "skip") else "?"
        lines.append(f"  {glyph} {g.gate}{(' · ' + g.tool) if g.tool else ''}{extra}")
        for finding in g.findings[:5]:
            lines.append(f"      - {finding}")
    if appended:
        lines.append(f"  ↳ ledger entry #{appended['seq']} signed by {appended['signer_key_id']}")
    return "\n".join(lines)


def _detection_line(detected: dict[str, str]) -> str:
    """The one auto-detection startup line, e.g.
    ``auto-detected gates:  format=biome  tests=vitest`` — printed once per gate run, human output
    only (never on the ``--json`` path)."""
    pairs = [f"{g}={detected[g]}" for g in GATE_ORDER if g in detected]
    pairs += [f"{g}={t}" for g, t in sorted(detected.items()) if g not in GATE_ORDER]
    return "auto-detected gates:  " + "  ".join(pairs)


def _effective_gates_or_none(
    s: Settings, adapter_name: Optional[str], target: Path
) -> Optional[EffectiveGates]:
    """Assemble the effective gate configuration, or ``None`` when it cannot be.

    ``None`` — no resolvable adapter or an unreadable manifest — hands configuration back to
    :func:`run_gates`, which loads the adapter itself and surfaces the real error on its own
    path; assembly here is an enrichment (overrides + detection), never a new failure mode."""
    try:
        name = adapter_name or _cli.detect_adapter(s, target)
        return effective_gates(s, name, target)
    except (FileNotFoundError, LookupError, OSError):
        return None


def _notify(cmd: Optional[str], message: str) -> None:
    """Best-effort notification hook: ``<cmd> "<message>"`` (3pwr run --notify). Never blocks the run."""
    if cmd:
        run_cmd(f"{cmd} {shlex.quote(message)}", cwd=Path.cwd())


def _notify_event(
    s: Settings, args: argparse.Namespace, event: str, message: str, spec_id: str
) -> None:
    """Fire ``event`` at the ``--notify`` hook AND every configured channel.

    Best-effort and fully isolated from the trust path: the channels are loaded at
    most once per invocation (a malformed file warns once), delivery never raises,
    and every problem is at most a one-line stderr warning that never carries a secret value.
    With no ``notifications.yaml`` and no ``--notify``, nothing happens and no
    network call is made. The subject carries the run's RESOLVED identity — the caller's ``spec_id``
    local, so a workspace-derived NNN reaches the notification too."""
    _notify(args.notify, message)  # the existing command hook keeps working alongside
    channels = getattr(args, "_notify_channels", None)
    if channels is None:
        channels, warns = notify.load_channels(s.notifications_config_path)
        for w in warns:
            print(f"warning: {w}", file=sys.stderr)
        args._notify_channels = channels
    for w in notify.dispatch(channels, event, f"3pwr run {spec_id or 'RUN'}", message):
        print(f"warning: {w}", file=sys.stderr)
