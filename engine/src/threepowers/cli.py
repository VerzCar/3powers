"""``3pwr`` — the 3Powers command line.

Subcommands:
  keygen        generate the independent Ed25519 signer identity (key kept outside repo)
  init          guided onboarding — make a new or existing project 3Powers-ready (layout +
                signer outside the repo + baseline config + a language adapter); --yes for CI
  gate run      run the deterministic gate suite, emit a verdict, append it to the ledger
  conformance   run only the spec-conformance trace
  verify        recompute the ledger hash chain + signatures (offline)
  signoff       append a signed human sign-off entry (a Spec-stage sign-off seals the
                approved document's hash into the signed entry — SLOCK-FR-001)
  advance       local enforcement gate: refuse to proceed unless gate green + ledger
                verifies + the tier-required sign-off is present (+ oracle independence
                at High-risk + the approved spec unchanged, SLOCK-FR-005)
  oracle        structural oracle independence: seal a spec-only bundle, record authoring
                (refusing the coder's model family), dispatch it headlessly + read-path
                isolated (A3), verify from the ledger
  deps-check    probe installed third-party versions against the supported ranges (preflight)
  ready         am I ready for `3pwr run --mode auto`? — the full run preflight + a dependency
                summary; read-only, offline, the same checks init and the run use (AUTOX-FR-003)
  run           drive the whole lifecycle loop (§6): auto mode stops only at the two mandatory
                human gates (spec approval FR-006, sign-off FR-037); the native executive
                dispatches each stage to a headless agent (EXEC-FR-001) and streams progress
  observe       §13 feedback loop: record a production signal → route to new intent, NFR-instrumentation
                coverage, and a tamper-evident, attributable runtime agent-action log
  spec diff     read-only spec-integrity report: does the spec still match its approval
                hash? (SLOCK-FR-007)
  ledger show   print the ledger

Exit codes: 0 = ok/green, 1 = gate failed / verification failed / advance refused,
2 = usage or environment error. `3pwr run` additionally uses the stable terminal contract
(AUTOX-FR-009): 3 = paused at a human gate, 4 = setup/dispatch failure (never a gate verdict).
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from . import (
    __version__,
    agents,
    anchor,
    artifacts,
    canonical,
    catalog,
    completion,
    config,
    covdiff,
    deps,
    deviations,
    gitflow,
    hosted,
    keys,
    lifecycle,
    notify,
    observe,
    oracle,
    orchestrate,
    phases,
    prompts,
    provenance,
    runner as runnermod,
    runpreflight,
    scaffold,
    scope,
    speclock,
    steering,
    style,
    transcripts,
    workkind,
    workspace,
)
from .adapters import detect_adapter, run_cmd
from .config import Settings, model_diversity_ok
from .gates import run_gates
from .ledger import Ledger, rotation_payload
from .runner import CliAgentRunner, NativeRunner, TextSink
from .verdict import GATE_ORDER, STATUS_PASS
from .verify import verify_ledger

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2
# The stable `3pwr run` terminal contract (AUTOX-FR-009): one documented (status, exit-code) pair
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
    # Native fallback: the newest spec under specs/ — exactly one per feature folder, whichever
    # layout (the spec/ workspace subfolder or the legacy flat file — PHASE-FR-001).
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
    the shipped defaults are used. Cached on ``args`` so the file is read at most once (CLIUX-FR-014)."""
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
    ui.yaml ``color_mode`` (CLIUX-FR-005/014). Machine output is never routed through it (CLIUX-FR-007)."""
    prefs, _ = _resolve_ui(args)
    return style.styler(
        stream if stream is not None else sys.stdout,
        as_json=getattr(args, "json", False),
        assume_yes=getattr(args, "yes", False),
        color_mode=prefs["color_mode"],
    )


def _verbosity(args: argparse.Namespace) -> str:
    """The effective verbosity for this command (CLIUX-FR-013): ``quiet`` | ``normal`` | ``verbose``."""
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
    """Assemble a command's human output honoring verbosity (CLIUX-FR-004/006/013).

    ``title`` renders a self-identifying header (hidden at ``quiet``); ``rows`` are the core result
    lines (always shown); ``extra`` are verbose-only detail lines. Detail grows monotonically
    quiet ⊆ normal ⊆ verbose, and none of this touches the ``--json`` payload (CLIUX-FR-007)."""
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
    """Best-effort spec-hash fields for a Spec-stage sign-off (SLOCK-FR-001).

    An unresolvable spec records nothing — the sign-off itself still proceeds.
    """
    try:
        spec_path = _resolve_spec(s, spec)
    except FileNotFoundError:
        return {}
    commit = _git_out(s.root, ["rev-parse", "--short", "HEAD"]).strip()
    return speclock.approval_fields(s.root, spec_path, commit=commit)


def _init_interactive(args: argparse.Namespace) -> bool:
    """Onboarding is interactive only with a real TTY and neither --yes nor --json (ONBRD-FR-006)."""
    return (
        (not getattr(args, "json", False))
        and (not getattr(args, "yes", False))
        and sys.stdin.isatty()
    )


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
    (``--yes``/``--json``/no TTY) prompts for nothing (ONBRD-FR-006), so an init stays byte-stable."""
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
    """Human-readable verdict: failing gate, class, and offending item — no transcript needed (3PWR-NFR-011).

    ``st`` colorizes the status markers consistently with the rest of the CLI (INITX-FR-013); a disabled
    styler (the default) leaves the plain ✓/✗/– glyphs — the text is identical byte-for-byte to before."""
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
    if verdict.failures:
        lines.append("  failures:")
        for fl in verdict.failures:
            detail = fl.get("detail") or fl.get("requirement_id") or fl.get("file") or ""
            lines.append(f"    • {fl['class']}: {detail}")
    if appended:
        lines.append(f"  ↳ ledger entry #{appended['seq']} signed by {appended['signer_key_id']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- commands
def cmd_keygen(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    role = getattr(args, "role", "ledger")
    if args.out:
        out = Path(args.out).resolve()
    elif role == "oracle":
        out = keys.default_oracle_private_path(s.root)
    else:
        out = keys.default_private_path(s.root)
    pub = s.oracle_pubkey_path if role == "oracle" else s.pubkey_path
    env_var = (
        "THREEPOWERS_ORACLE_SIGNING_KEY_FILE"
        if role == "oracle"
        else "THREEPOWERS_SIGNING_KEY_FILE"
    )
    if keys.inside_working_tree(s.root, out):
        print(
            f"refusing to create a private key INSIDE the repository working tree: {out}\n"
            "  an executive agent with repo access could read it (HARDN-FR-002 / 3PWR-NFR-005).\n"
            f"  pass --out with a path outside the repo, e.g. {keys.default_private_path(s.root)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if out.exists() and not args.force:
        print(f"refusing to overwrite existing key at {out} (use --force)", file=sys.stderr)
        return EXIT_USAGE
    sk = keys.generate()
    keys.write_private(out, sk)
    keys.write_public(pub, sk.verify_key)
    label = "judiciary (oracle) signer" if role == "oracle" else "signer"
    kst = _styler(args)
    print(kst.status_row("pass", f"{label} identity created", sk.key_id))
    print(
        kst.kv(
            [
                ("private key (keep OUTSIDE the repo)", str(out)),
                ("public key  (committed)", str(pub)),
            ]
        )
    )
    print()
    print("  " + kst.dim("Point the engine at the private key with:"))
    print(f'  export {env_var}="{out}"')
    return EXIT_OK


def cmd_rotate_key(args: argparse.Namespace) -> int:
    """Rotate the ledger signer (HARDN-FR-004): the OUTGOING key signs its successor.

    Appends a ``key_rotation`` entry authored by the current key and carrying the new public
    key, then installs the successor (private key outside the repo, public key committed).
    ``verify`` thereafter requires the committed key to descend from the genesis key through
    exactly these recorded rotations — a bare pubkey swap becomes a named finding (SC-001).
    """
    s = _settings(args.root)
    try:
        old_sk = keys.resolve_signing_key(s.root)  # rotation needs the software key material
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    if s.pubkey_path.exists():
        committed = keys.load_public(s.pubkey_path)
        if committed.key_id != old_sk.key_id:
            print(
                f"error: the resolved signing key ({old_sk.key_id}) is not the committed "
                f"public key ({committed.key_id}) — a rotation must be authored by the "
                "current key, or verify would report a broken succession",
                file=sys.stderr,
            )
            return EXIT_USAGE
    out = Path(args.out).resolve() if args.out else keys.default_private_path(s.root)
    if keys.inside_working_tree(s.root, out):
        print(
            f"refusing to create a private key INSIDE the repository working tree: {out}\n"
            "  pass --out with a path outside the repo (HARDN-FR-002 / 3PWR-NFR-005)",
            file=sys.stderr,
        )
        return EXIT_USAGE
    new_sk = keys.generate()
    payload = rotation_payload(old_sk.verify_key, new_sk.verify_key, args.reason or "")
    entry = Ledger(s.ledger_path).append("key_rotation", payload, old_sk)
    keys.write_private(out, new_sk)
    keys.write_public(s.pubkey_path, new_sk.verify_key)
    hint = ""
    env_file = os.environ.get("THREEPOWERS_SIGNING_KEY_FILE")
    if env_file and Path(env_file).resolve() != out:
        hint = f'\n  update the pointer:  export THREEPOWERS_SIGNING_KEY_FILE="{out}"'
    rkt = _styler(args)
    rows = [
        rkt.status_row(
            "pass",
            f"key rotated: {old_sk.key_id} → {new_sk.key_id}",
            f"ledger seq={entry['seq']}",
        ),
        rkt.kv(
            [
                ("new private key (OUTSIDE the repo)", str(out)),
                ("committed public key updated", str(s.pubkey_path)),
            ]
        ),
    ]
    if hint:
        rows.append(
            rkt.status_row(
                "warn", f'update the pointer: export THREEPOWERS_SIGNING_KEY_FILE="{out}"'
            )
        )
    _print(
        {
            "rotated": True,
            "previous_key_id": old_sk.key_id,
            "new_key_id": new_sk.key_id,
            "ledger_seq": entry["seq"],
            "private_key": str(out),
        },
        args.json,
        _compose(
            args, rkt, title="rotate-key", subject=f"{old_sk.key_id} → {new_sk.key_id}", rows=rows
        ),
    )
    return EXIT_OK


def _init_layout(s: Settings) -> str:
    """Create the ``.3powers/`` skeleton idempotently (ONBRD-FR-009). Returns created|kept."""
    status = "kept" if s.dir.exists() else "created"
    for d in (
        s.dir / "config",
        s.dir / "schemas",
        s.dir / "adapters",
        s.dir / "keys",
        s.dir / "runs",
        s.dir / "verdicts",
    ):
        d.mkdir(parents=True, exist_ok=True)
    if not s.ledger_path.exists():
        s.ledger_path.touch()
    return status


def _readiness_checklist(
    ready: dict[str, object],
    *,
    model_div_ok: bool,
    auto_prqs: Optional[list[runpreflight.Prereq]] = None,
) -> list[tuple[str, str, str]]:
    """Build the first-run readiness checklist (INITX-FR-009/010/011; AUTOX-FR-001/002).

    Each item is ``(label, status, detail)`` with status ∈ ``pass`` | ``warn`` | ``fail`` | ``todo``.
    A missing CI/CD configuration is a mandatory prerequisite for secure gate enforcement (fail,
    INITX-FR-010); a 3Powers-generated AGENTS.md starter is an unfinished TODO (INITX-FR-011). No item
    is omitted (INITX-FR-009). ``auto_prqs`` — the SAME check set the live run preflight enforces
    (``runpreflight.check_auto``) — is appended per item, so init's "ready" and the run's refusal can
    never drift (AUTOX-FR-002)."""
    items: list[tuple[str, str, str]] = []
    if ready.get("ci"):
        items.append(("CI/CD pipeline", "pass", "gates can run automatically on every change"))
    else:
        items.append(
            (
                "CI/CD pipeline",
                "fail",
                "MISSING — required for secure gates. Gates must run automatically on every "
                "change; add a CI workflow (e.g. under .github/workflows/) that runs `3pwr gate run`.",
            )
        )
    items.append(
        (
            "3Powers constitution",
            "pass" if ready.get("constitution") else "warn",
            "in place" if ready.get("constitution") else "seeded by `3pwr init`",
        )
    )
    if ready.get("agents_md_todo"):
        items.append(
            (
                "AGENTS.md",
                "todo",
                "TODO — a 3Powers starter was written; fill in the [bracketed] parts "
                "(or run your create-agentsmd skill)",
            )
        )
    elif ready.get("agents_md"):
        items.append(("AGENTS.md", "pass", "present — ensure it names `3pwr` as the main command"))
    else:
        items.append(("AGENTS.md", "warn", "none — consider adding agent guidance"))
    items.append(
        (
            "Judiciary model diversity",
            "pass" if model_div_ok else "warn",
            "oracle model differs from the coder's family"
            if model_div_ok
            else "oracle shares the coder's family (or is unset) — recommended to differ (3PWR-FR-022)",
        )
    )
    # The auto full-mode prerequisites — sourced from the run's own preflight checks, so a "ready"
    # here means `3pwr run --mode auto` will not refuse to start (AUTOX-FR-001/002).
    for p in auto_prqs or []:
        items.append(
            (f"auto run: {p.name}", "pass" if p.ok else "fail", p.label if p.ok else p.fix)
        )
    return items


def _checklist_lines(st: style.Styler, items: list[tuple[str, str, str]]) -> list[str]:
    """Render checklist items as colorized ``<mark> <label>: <detail>`` lines (INITX-FR-013)."""
    return [f"  {st.mark(status)} {st.bold(label)}: {detail}" for label, status, detail in items]


# The configurable roles the setup walks, in the order they are asked (AGENTX-FR-012).
_SETUP_ROLES = ("planner", "coder", "oracle", "reviewer")


def _warn_diversity(s: Settings, st: style.Styler) -> list[str]:
    """Warn (stderr) when the oracle or reviewer resolves to the coder's family (AGENTX-FR-018).

    Diversity is recommended, never forced (3PWR-FR-022/057): the warning names the signed
    deviation path and the setup always proceeds. Warnings go to stderr so a ``--json`` run's
    stdout stays byte-identical (INITX-FR-014). Returns the roles warned about."""
    coder_fam = s.coder_family()
    hit: list[str] = []
    if not coder_fam:
        return hit
    for role in ("oracle", "reviewer"):
        r = s.role(role)
        # The explicit model_family wins — catalog bindings may use bare, integration-native ids
        # whose family the id does not encode (AGENTX-FR-012/015).
        fam = (
            str(r.get("model_family") or "") or oracle.family_of(str(r.get("model") or ""))
        ).strip()
        if fam and fam == coder_fam:
            hit.append(role)
            print(
                st.warn(
                    f"⚠ {role} resolves to the coder's model family ({coder_fam}) — model "
                    "diversity is recommended (3PWR-FR-022)."
                ),
                file=sys.stderr,
            )
    if hit:
        print(
            st.dim(
                "    proceed by recording a signed deviation: 3pwr deviation "
                '--gate model_diversity --approver <you> --note "single-model dev"'
            ),
            file=sys.stderr,
        )
    return hit


def _agent_cli_present(s: Settings, name: str) -> bool:
    """True iff the agent backend ``name``'s CLI is on PATH (a manifest's ``command``, else ``name``)."""
    cmd = name
    try:
        cmd = agents.agent_command(agents.load_agent(s, name)) or name
    except FileNotFoundError:
        pass
    return shutil.which(cmd) is not None


def _default_role_model(
    role: str,
    entries: list[dict[str, str]],
    default_entry: Optional[dict[str, str]],
    coder_fam: str,
) -> str:
    """The documented default model for a role, family-aware for the judiciary.

    Coder/planner take the integration's documented default; oracle/reviewer prefer the first entry
    whose *family* differs from the coder's chosen family, so ``family`` diversity holds out of the
    box even within a single BYOK integration (3PWR-FR-022)."""
    fallback = (default_entry or {}).get("model", "") or (entries[0]["model"] if entries else "")
    if role in ("oracle", "reviewer") and coder_fam:
        for e in entries:
            if e["family"] and e["family"] != coder_fam:
                return e["model"]
    return fallback


def _roles_setup_flow(
    s: Settings,
    st: style.Styler,
    *,
    interactive: bool,
    integration: Optional[str] = None,
    role_models: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """The shared headless-CLI + role→model + diversity setup (AGENTX-FR-011/012/014/015).

    One pass: multi-select which agent-backend CLIs you use (no provider is forced — AGENTX-FR-011),
    then bind each configurable role — planner, coder, oracle, reviewer — to an integration from that
    selection and a model drawn from its catalog or entered free-form (AGENTX-FR-016), writing a
    complete block (``model_family``/``model``/``integration``/``label``, ``require_dispatch`` for the
    oracle) so ``3pwr run`` needs no manual role editing (AGENTX-FR-012/013). Finally choose how
    diversity is judged — by ``family`` or ``model`` (3PWR-FR-022).

    Integration and family are orthogonal: one BYOK integration (e.g. copilot) can bind coder and
    oracle to different families, so diversity never forces a second CLI. When ``integration`` is
    given it fixes the single backend (``3pwr config roles setup --integration``).

    Non-interactive (AGENTX-NFR-004): prompts for nothing; explicit choices are applied, and a role
    with no binding yet receives a documented default — already-bound roles are preserved untouched
    (non-destructive, AGENTX-FR-014/NFR-003). Deterministic and offline (AGENTX-NFR-001); diversity
    only ever warns (AGENTX-FR-018)."""
    cat = catalog.load_catalog(s)
    roles_cfg = s.load_roles()
    known = [str(i) for i in (roles_cfg.get("headless_integrations") or [])]
    for name in list(catalog.integrations(cat)) + scaffold.bundled_agents():
        if name not in known:
            known.append(name)

    # 1) Which agent CLIs do you use? Multi-select, default = the ones installed on PATH (else the
    #    configured set, else claude). A forced --integration pins the single backend.
    if integration:
        selected = [integration]
    else:
        configured = [str(i) for i in (roles_cfg.get("headless_integrations") or [])]
        installed = [n for n in known if _agent_cli_present(s, n)]
        default_sel = installed or configured or (["claude"] if "claude" in known else known[:1])
        selected = (
            _ask_multi(
                "Which coding-agent CLIs will you use? (space/comma-separated)",
                known,
                default_sel,
                interactive=interactive,
            )
            or default_sel
        )
    if selected:
        scaffold.set_headless_integrations(s, selected)

    custom_opt = "custom (type a model id)"
    written: dict[str, Any] = {}
    chosen_family: dict[str, str] = {}
    for role in _SETUP_ROLES:
        explicit = str((role_models or {}).get(role) or "").strip()
        cur = s.role(role)
        cur_model = str(cur.get("model") or "").strip()
        cur_intg = str(cur.get("integration") or "").strip()

        # 2a) Integration for this role, from the selected set.
        if len(selected) == 1:
            role_intg = selected[0]
        elif interactive and not explicit:
            # Default the judiciary to a CLI other than the coder's when more than one is selected.
            coder_intg = written.get("coder", {}).get("integration") or selected[0]
            others = [i for i in selected if i != coder_intg]
            pref = (
                cur_intg
                if cur_intg in selected
                else (
                    (others[0] if others else coder_intg)
                    if role in ("oracle", "reviewer")
                    else coder_intg
                )
            )
            role_intg = _ask_choice(
                f"Agent CLI for the {role} role", selected, pref, interactive=interactive
            )
        else:
            role_intg = (
                cur_intg if cur_intg in selected else (selected[0] if selected else cur_intg)
            )

        entries = catalog.models_for(cat, role_intg)
        default_entry = catalog.default_for(cat, role_intg)
        coder_fam = chosen_family.get("coder", "")

        # 2b) Model for this role.
        if explicit:
            model = explicit
        elif interactive:
            options = [e["model"] for e in entries] + [custom_opt]
            preset = _default_role_model(role, entries, default_entry, coder_fam)
            default_opt = cur_model if cur_model in options else (preset or custom_opt)
            pick = _ask_choice(
                f"Model for the {role} role ({role_intg})",
                options,
                default_opt,
                interactive=interactive,
            )
            model = (
                _ask(
                    "  model id (free-form / BYOK)",
                    cur_model or preset,
                    interactive=interactive,
                )
                if pick == custom_opt
                else pick
            )
        elif cur_model:
            written[role] = {"status": "kept", "model": cur_model}
            chosen_family[role] = str(cur.get("model_family") or "") or oracle.family_of(cur_model)
            continue
        else:
            model = _default_role_model(role, entries, default_entry, coder_fam)

        if not model:
            written[role] = {"status": "kept", "model": cur_model or None}
            continue
        entry = catalog.entry_for(cat, role_intg, model)
        family = entry["family"] if entry else catalog.derive_family(model)
        label = entry["label"] if entry else model
        if interactive and entry is None:
            family = _ask("  model family", family, interactive=interactive) or family
            label = _ask("  friendly label", label, interactive=interactive)
        scaffold.set_role_model(
            s, role, model=model, integration=role_intg, label=label, model_family=family
        )
        chosen_family[role] = family
        written[role] = {
            "status": "written",
            "model": model,
            "model_family": family,
            "integration": role_intg,
            "label": label,
        }

    # 3) How is diversity judged — family or model? (3PWR-FR-022)
    level = _ask_choice(
        "Judge model diversity by…",
        ["family", "model"],
        s.diversity_level() or "family",
        interactive=interactive,
    )
    scaffold.set_diversity_level(s, level)
    warned = _warn_diversity(s, st)
    return {
        "integration": (
            written.get("coder", {}).get("integration") or (selected[0] if selected else "")
        ),
        "integrations": selected,
        "roles": written,
        "diversity_level": level,
        "diversity_warned": warned,
    }


def cmd_config_roles_setup(args: argparse.Namespace) -> int:
    """(Re)run the headless-CLI + role→model setup without reinitializing (AGENTX-FR-014).

    The same integration + per-role selection init performs, non-destructively: only the roles
    reconfigured here are rewritten; every other roles.yaml field is preserved (AGENTX-NFR-003).
    Non-interactive (``--yes``/``--json``/no TTY) prompts for nothing and applies the documented
    defaults (AGENTX-NFR-004). Dispatch configuration only — no gate, verdict, ledger, or human
    gate is touched (AGENTX-NFR-002), and model diversity only ever warns (AGENTX-FR-018)."""
    s = _settings(args.root)
    as_json = getattr(args, "json", False)
    interactive = _init_interactive(args)
    st = _styler(args)
    report = _roles_setup_flow(
        s,
        st,
        interactive=interactive,
        integration=getattr(args, "integration", None),
        role_models={role: getattr(args, role, None) or "" for role in _SETUP_ROLES},
    )
    rows = []
    for role, info in report["roles"].items():
        if info.get("status") == "written":
            rows.append(
                st.status_row(
                    "pass",
                    f"{role}: {info.get('label') or info.get('model')} "
                    f"({info.get('model')} · {info.get('integration')})",
                )
            )
        else:
            rows.append(st.status_row("info", f"{role}: kept — {info.get('model') or 'unset'}"))
    rows.append(
        st.status_row(
            "info",
            "oracle.require_dispatch: the High-risk read-path-isolation policy (3PWR-FR-021/A3) — "
            "default false; see .3powers/config/roles.yaml",
        )
    )
    _print(
        report,
        as_json,
        _compose(
            args,
            st,
            title="config roles setup",
            subject=report["integration"],
            rows=rows,
        ),
    )
    return EXIT_OK


def cmd_commit_stage(args: argparse.Namespace) -> int:
    """Auto-commit after a successful lifecycle stage (INITX-FR-006).

    One commit, message ``3pwr(<spec-id>): <stage>``. It commits the currently-staged changes (or the
    files named by ``--paths``), so it never sweeps unrelated changes; when nothing is staged (a failed
    or no-op stage) it makes no commit. It never touches the ledger."""
    s = _settings(args.root)
    as_json = getattr(args, "json", False)
    spec_id = getattr(args, "spec_id", None) or "?"
    stage = args.stage
    paths = getattr(args, "paths", None) or []
    if paths:
        subprocess.run(["git", "add", "--", *paths], cwd=s.root, check=False)
    # Anything staged? `git diff --cached --quiet` exits 0 when the index has no changes.
    staged = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=s.root, check=False
    ).returncode
    cst = _styler(args)
    if staged == 0:
        _print(
            {"committed": False, "reason": "nothing staged"},
            as_json,
            _compose(
                args,
                cst,
                title="commit-stage",
                subject=f"{spec_id}: {stage}",
                rows=[cst.status_row("info", "nothing staged — no stage commit made")],
            ),
        )
        return EXIT_OK
    msg = f"3pwr({spec_id}): {stage}"
    res = subprocess.run(
        ["git", "commit", "-m", msg], cwd=s.root, capture_output=True, text=True, check=False
    )
    if res.returncode != 0:
        print(f"error: git commit failed: {res.stderr.strip()}", file=sys.stderr)
        return EXIT_FAIL
    sha = _git_out(s.root, ["rev-parse", "--short", "HEAD"]).strip()
    _print(
        {"committed": True, "message": msg, "commit": sha},
        as_json,
        _compose(
            args,
            cst,
            title="commit-stage",
            subject=f"{spec_id}: {stage}",
            rows=[cst.status_row("pass", f"committed [{sha}] {msg}")],
        ),
    )
    return EXIT_OK


def _notifications_setup_flow(
    s: Settings, st: style.Styler, *, interactive: bool
) -> dict[str, Any]:
    """Pick one run-notification channel (or none) and write its config (STEER-FR-010).

    Secrets are never stored (STEER-NFR-002): slack/teams record only the env-var *name* holding the
    webhook URL, email records ``password_env``. Non-interactive prompts for nothing — the seeded
    empty ``channels: []`` (notifications off) stands. Returns what to tell the user to export."""
    if not interactive:
        return {"channel": "none"}
    choice = _ask_choice(
        "Send run notifications to… (gate pauses, failures, completion)",
        ["none", "desktop", "slack", "teams", "email"],
        "none",
        interactive=interactive,
    )
    events = list(notify.DEFAULT_EVENTS)
    if choice == "none":
        return {"channel": "none"}
    if choice in ("slack", "teams"):
        env_default = f"THREEPOWERS_{choice.upper()}_WEBHOOK"
        env = (
            _ask(
                f"  env var holding the {choice} webhook URL", env_default, interactive=interactive
            )
            or env_default
        )
        scaffold.set_notification_channel(s, {"type": choice, "events": events, "webhook_env": env})
        return {"channel": choice, "webhook_env": env}
    if choice == "email":
        host = _ask("  SMTP host", "", interactive=interactive)
        port_raw = _ask("  SMTP port", "587", interactive=interactive)
        to = _ask("  recipient address (to)", "", interactive=interactive)
        frm = _ask("  sender address (from, optional)", "", interactive=interactive)
        user = _ask("  SMTP username (optional)", "", interactive=interactive)
        pw_env = (
            _ask(
                "  env var holding the SMTP password",
                "THREEPOWERS_SMTP_PASSWORD",
                interactive=interactive,
            )
            or "THREEPOWERS_SMTP_PASSWORD"
        )
        channel: dict[str, Any] = {
            "type": "email",
            "events": events,
            "host": host,
            "port": int(port_raw) if port_raw.isdigit() else 587,
            "to": to,
            "password_env": pw_env,
        }
        if frm:
            channel["from"] = frm
        if user:
            channel["user"] = user
        scaffold.set_notification_channel(s, channel)
        return {"channel": "email", "password_env": pw_env}
    # desktop
    scaffold.set_notification_channel(s, {"type": "desktop", "events": events})
    return {"channel": "desktop", "macos_only": sys.platform != "darwin"}


def cmd_init(args: argparse.Namespace) -> int:
    """Guided onboarding — make an existing or new project 3Powers-ready in one step (ONBRD-FR-001).

    Interactive by default; with ``--yes``/``--json`` or no TTY it prompts for nothing and applies the
    documented default for every choice (ONBRD-FR-006). It creates the signer OUTSIDE the repo
    (ONBRD-NFR-001), seeds the baseline config + the selected language adapter without clobbering
    (ONBRD-FR-008), records the autonomy default (ONBRD-FR-005), is idempotent on re-run
    (ONBRD-FR-009), and prints greenfield-vs-brownfield next steps (ONBRD-FR-010). Fully offline
    (ONBRD-NFR-002)."""
    as_json = getattr(args, "json", False)
    interactive = _init_interactive(args)
    st = _styler(args)

    # 1) Target directory — default the current directory (ONBRD-FR-002).
    default_dir = str(Path(args.root).resolve() if args.root else Path.cwd())
    root = Path(_ask("Project directory", default_dir, interactive=interactive)).expanduser()
    if not root.is_dir():
        print(f"error: directory does not exist: {root}", file=sys.stderr)
        return EXIT_USAGE
    if not os.access(root, os.W_OK):
        print(f"error: directory is not writable: {root}", file=sys.stderr)
        return EXIT_USAGE
    root = root.resolve()
    s = Settings(root=root)

    # 2) Trust-spine layout (idempotent).
    layout_status = _init_layout(s)
    if getattr(args, "skeleton_only", False):
        _print(
            {"root": str(root), "layout": layout_status},
            as_json,
            f"initialized 3Powers trust-spine layout under {s.dir}",
        )
        return EXIT_OK

    # 3) Brownfield detection + a suggested default language (ONBRD-FR-010).
    langs = scaffold.bundled_languages()
    detected = scaffold.detect_language(root)
    brownfield = scaffold.has_source(root)
    git_present = (root / ".git").exists()

    if args.language and args.language not in langs:
        print(
            f"error: unsupported language {args.language!r}; supported: {', '.join(langs)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    default_lang = args.language or detected or (langs[0] if langs else "")
    # 4) Language selection from the supported (adapter-backed) set (ONBRD-FR-003).
    lang = args.language or _ask_choice(
        "Which language adapter?", langs, default_lang, interactive=interactive
    )

    # 5) Signing key — a private location OUTSIDE the repo (ONBRD-FR-004/007, NFR-001).
    env_key = os.environ.get("THREEPOWERS_SIGNING_KEY_FILE") or os.environ.get(
        "THREEPOWERS_SIGNING_KEY"
    )
    key_status = "env"
    key_path: Optional[Path] = None
    if env_key:
        key_status = "env"
    else:
        default_key = keys.default_private_path(root)
        alt_ssh = Path("~/.ssh").expanduser() / (root.name + "-3pwr.key")
        if args.key_path:
            key_path = Path(args.key_path).expanduser()
        elif interactive:
            pick = _ask_choice(
                "Where should the signing key live (OUTSIDE the repo)?",
                [str(default_key), str(alt_ssh), "custom"],
                str(default_key),
                interactive=interactive,
            )
            key_path = (
                Path(
                    _ask("Custom key path", str(default_key), interactive=interactive)
                ).expanduser()
                if pick == "custom"
                else Path(pick).expanduser()
            )
        else:
            key_path = default_key
        if not scaffold.is_outside_repo(key_path, root):
            print(
                "error: the signing key must live OUTSIDE the repository "
                f"(ONBRD-NFR-001 / 3PWR-NFR-005): {key_path}",
                file=sys.stderr,
            )
            return EXIT_USAGE
        _sk, key_status = scaffold.create_signer(key_path, s.pubkey_path, force=args.force)

    # 6) Autonomy default (ONBRD-FR-005) — advisory; never bypasses a human gate (NFR-004).
    auto_mode = (
        args.auto_mode
        if args.auto_mode is not None
        else _ask_yesno("Make autonomous mode the default?", True, interactive=interactive)
    )

    # 7) Seed baseline config + the selected adapter, never clobbering (ONBRD-FR-008).
    cfg = scaffold.seed_config(s)
    scaffold.seed_gitignore(s)
    scaffold.seed_contract(s)
    adapter_status = scaffold.materialize_adapter(s, lang) if lang else "none"

    # 8) Config selection — accept the recommended defaults or customize the choices that can
    #    never weaken a gate: the default risk tier + the headless-CLI/role→model bindings
    #    (INITX-FR-001/002; AGENTX-FR-011/012). The seeded roles.yaml is the documented default,
    #    so a non-interactive init prompts for nothing and stays run-ready (AGENTX-NFR-004).
    tier = getattr(args, "tier", None) or s.default_tier()
    oracle_model = getattr(args, "oracle_model", None)
    oracle_integration = getattr(args, "oracle_integration", None)
    oracle_label = getattr(args, "oracle_label", None)
    customized = bool(oracle_model or getattr(args, "tier", None))
    roles_report: Optional[dict[str, Any]] = None
    notify_report: dict[str, Any] = {"channel": "none"}
    # The guided judiciary setup always runs interactively, each prompt carrying an accept-by-Enter
    # default (INITX-FR-001/002; AGENTX-FR-011/012): risk tier → which agent CLIs → per-role model →
    # diversity mode → notifications. Non-interactive prompts for nothing — the seeded roles.yaml +
    # empty notifications are the documented defaults and stay run-ready (AGENTX-NFR-004).
    if interactive and not oracle_model:
        customized = True
        tiers = list((s.load_risk_tiers().get("tiers") or {}).keys()) or [
            "Cosmetic",
            "Standard",
            "High-risk",
        ]
        tier = _ask_choice("Default risk tier for new specs?", tiers, tier, interactive=interactive)
        forced = getattr(args, "integration", None)
        forced = forced if forced not in (None, "auto") else None
        roles_report = _roles_setup_flow(s, st, interactive=interactive, integration=forced)
        notify_report = _notifications_setup_flow(s, st, interactive=interactive)
    if oracle_model:
        coder_fam = s.coder_family()
        if coder_fam and oracle.family_of(oracle_model) == coder_fam:
            # Diversity is recommended, not forced (3PWR-FR-022/057). Warn to STDERR so a --json
            # run's stdout stays byte-identical (INITX-FR-014); never a silent accept (INITX-FR-002).
            print(
                st.warn(
                    f"⚠ oracle model shares the coder's family ({coder_fam}) — model diversity is "
                    "recommended (3PWR-FR-022)."
                ),
                file=sys.stderr,
            )
            print(
                st.dim(
                    "    proceed by recording a signed deviation: 3pwr deviation "
                    '--gate model_diversity --approver <you> --note "single-model dev"'
                ),
                file=sys.stderr,
            )
        scaffold.set_role_model(
            s,
            "oracle",
            model=oracle_model,
            integration=oracle_integration or getattr(args, "integration", None) or "copilot",
            label=oracle_label or oracle_model,
        )
    scaffold.write_onboarding(s, auto_mode=auto_mode, tier=tier, auto_commit=True)

    # 9) AGENTS.md — create a 3Powers starter if the repo has none (ONBRD-FR-016).
    agents_status = scaffold.seed_agents_md(root)

    # 10) Seed the native agent-backend manifests, the per-stage agent templates, and the 3Powers
    #     constitution (offline, non-clobber). `3pwr run` drives these agents directly — no Spec Kit
    #     (EXEC-FR-004; SLIM removed the substrate) — and each dispatched stage's editable
    #     instructions live in .3powers/templates/agents/ (AGENTX-FR-001/009).
    agents_seeded = scaffold.seed_agents(s)  # .3powers/agents/*.yaml
    templates_seeded = scaffold.seed_stage_templates(s)  # .3powers/templates/agents/*.agent.md
    constitution_status = scaffold.seed_constitution(root)
    ready = scaffold.readiness(root)

    # Judiciary model-diversity readiness (needs config): a concrete oracle model in a family
    # different from the coder's (INITX-FR-002 / 3PWR-FR-022). The oracle's explicit model_family
    # wins over prefix-derivation — catalog bindings may use bare ids (AGENTX-FR-012/015).
    oracle_pin = s.role_model_pin("oracle")
    coder_fam = s.coder_family()
    oracle_fam = (
        str(s.role("oracle").get("model_family") or "")
        or oracle.family_of((oracle_pin or {}).get("model", ""))
    ).strip()
    model_div_ok = oracle_pin is not None and (not coder_fam or oracle_fam != coder_fam)

    # Auto full-mode readiness — the SAME check set the live run preflight enforces (AUTOX-FR-001/002):
    # a resolvable/usable signer (env keys validated, never trusted silently), a headless coder agent
    # with its CLI on PATH, and a different-family oracle. One source of checks — no drift possible.
    coder_int = runpreflight.resolve_coder_integration(s, getattr(args, "integration", None))
    oracle_int = runpreflight.resolve_oracle_integration(s)
    auto_prqs = runpreflight.check_auto(
        s,
        coder_agent=coder_int,
        oracle_agent=oracle_int,
        entries=Ledger(s.ledger_path).entries(),
        spec_id=None,
    )
    auto_unmet = runpreflight.unmet(auto_prqs)

    mode = "auto" if auto_mode else "commit"
    checklist = _readiness_checklist(ready, model_div_ok=model_div_ok, auto_prqs=auto_prqs)
    report: dict[str, Any] = {
        "root": str(root),
        "layout": layout_status,
        "language": lang or None,
        "adapter": adapter_status,
        "config": cfg,
        "key_path": str(key_path) if key_path else None,
        "key": key_status,
        "auto_mode": bool(auto_mode),
        "tier": tier,
        "customized": customized,
        "brownfield": brownfield,
        "detected_language": detected,
        "git": git_present,
        "agents_md": agents_status,
        "constitution": constitution_status,
        "agents": agents_seeded,
        "stage_templates": templates_seeded,
        "roles_setup": roles_report,
        "notifications": notify_report,
        "model_diversity": model_div_ok,
        "readiness": ready,
        "checklist": [{"item": it[0], "status": it[1], "detail": it[2]} for it in checklist],
        # The auto full-mode verdict + the remaining steps as exact fixes in dependency order
        # (AUTOX-FR-002/005) — derived from the same checks the run preflight enforces.
        "auto_ready": not auto_unmet,
        "auto_run": [
            {"prerequisite": p.name, "ok": p.ok, "label": p.label, "fix": p.fix} for p in auto_prqs
        ],
        "next_steps": [p.fix for p in auto_unmet],
    }
    if as_json:
        print(json.dumps(report, indent=2))
        return EXIT_OK

    # ---- human, colorized summary (INITX-FR-013) ----
    lines = [st.ok("✓") + " " + st.bold(f"3Powers is ready under {s.dir}")]
    if key_status == "created":
        lines.append(f"  signer created (private key OUTSIDE the repo): {key_path}")
        lines.append(f'  point the engine at it:  export THREEPOWERS_SIGNING_KEY_FILE="{key_path}"')
    elif key_status == "kept":
        lines.append(f"  signer: kept existing key at {key_path}")
    else:
        lines.append("  signer: using the key from your environment")
    lines.append(
        f"  language: {lang or '(none — no adapter selected)'} · "
        f"adapter {adapter_status} · default tier: {tier} · autonomous default: "
        f"{'yes' if auto_mode else 'no'}"
    )
    if lang == "" and langs:
        lines.append(
            f"  note: choose a language next time from: {', '.join(langs)} "
            "(or add one — see .3powers/adapters/CONTRACT.md)"
        )
    seeded = [n for n, stt in agents_seeded.items() if stt == "created"]
    if seeded:
        lines.append("  agent backends seeded (.3powers/agents/): " + ", ".join(sorted(seeded)))
    tpl_seeded = [n for n, stt in templates_seeded.items() if stt == "created"]
    if tpl_seeded:
        lines.append(
            f"  stage agent templates seeded (.3powers/templates/agents/): {len(tpl_seeded)} "
            "editable per-stage instruction file(s)"
        )
    notif_channel = str(notify_report.get("channel") or "none")
    if notif_channel != "none":
        lines.append(
            f"  notifications: {notif_channel} channel configured "
            "(.3powers/config/notifications.yaml)"
        )

    # Readiness checklist (INITX-FR-009/010/011). The header keeps the phrase the onboarding
    # contract documents (ONBRD-FR-015) so existing guidance stays discoverable.
    lines.append("")
    lines.append(st.head("Ready for the agentic workflow? — readiness checklist:"))
    lines.extend(_checklist_lines(st, checklist))
    if not git_present:
        lines.append(
            st.warn("  ⚠ no git repo detected")
            + " — `git init` to unlock diff-scoped brownfield gating"
        )

    # The remaining auto full-mode steps, as exact fixes in dependency order (AUTOX-FR-005):
    # key → coder agent (roles + CLI) → different-family oracle. Derived from the same readiness
    # result above — exactly the unmet items, nothing more.
    lines.append("")
    if auto_unmet:
        lines.append(
            st.head(
                f"Auto full mode — {len(auto_unmet)} step(s) remaining, in order "
                "(re-check any time: 3pwr ready):"
            )
        )
        for i, p in enumerate(auto_unmet, 1):
            lines.append(f"  {i}. {p.fix}")
    else:
        lines.append(
            st.ok("✓") + ' auto full mode ready — `3pwr run "<intent>" --mode auto` will start '
            "(re-check any time: 3pwr ready)"
        )

    # Before-you-run env exports for a configured notification channel (secrets live in env, never
    # in the config — STEER-NFR-002). Shown as a call-to-action alongside the signer export.
    notif_hint: list[str] = []
    if notif_channel in ("slack", "teams"):
        env = notify_report.get("webhook_env") or f"THREEPOWERS_{notif_channel.upper()}_WEBHOOK"
        notif_hint.append(
            f'  export {env}="<your {notif_channel} webhook URL>"   # before `3pwr run`'
        )
    elif notif_channel == "email":
        notif_hint.append(
            f"  export {notify_report.get('password_env', 'THREEPOWERS_SMTP_PASSWORD')}="
            '"<smtp password>"   # before `3pwr run`'
        )
    elif notif_channel == "desktop" and notify_report.get("macos_only"):
        notif_hint.append(
            "  note: desktop notifications are macOS-only — they degrade to a warning elsewhere"
        )

    # Getting started — the primary call-to-action, shown ALWAYS (greenfield + brownfield):
    # describe what you want and 3pwr drives the lifecycle (INITX-FR-012).
    lines.append("")
    lines.append(st.head("Get started — describe what you want and 3pwr drives the lifecycle:"))
    lines.append("  " + st.bold(f'3pwr run "<what you want built>" --mode {mode}'))
    lines.append("       spec → plan → oracle → build → verify → ship,")
    lines.append("       stopping only at the two human gates (spec approval, sign-off)")
    lines.append(
        "  " + st.bold(f"3pwr run --file <intent.md> --mode {mode}") + "   # …or a written brief"
    )
    lines.append("  (step-by-step: 3pwr oracle → 3pwr gate run → 3pwr signoff → 3pwr advance)")
    lines.extend(notif_hint)

    # Existing code? The now-working brownfield on-ramp, demoted below the primary CTA (3PWR-FR-051/052).
    if brownfield:
        lines.append("")
        lines.append(st.head("Existing code? Adopt gradually first:"))
        lines.append("  " + st.bold("3pwr gate run --path . --tier Standard --report-only"))
        lines.append("       see your current gate debt without blocking anything (no spec needed)")
        lines.append("  " + st.bold("3pwr characterize --module <file-or-dir>"))
        lines.append("       pin the behaviour of a legacy module (reconstruct spec + oracle)")
        lines.append("  " + st.bold("3pwr gate run --path . --base main --diff-scope"))
        lines.append("       enforce the gates only on the code you change from now on")
    print("\n".join(lines))
    return EXIT_OK


def cmd_gate_run(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else s.root
    # Brownfield adoption (3PWR-FR-051/052): report-only / diff-scope is the on-ramp for a repo that
    # has no 3Powers spec yet, so a missing spec is not an error there — the two spec-bound gates SKIP.
    try:
        spec_path: Path | None = _resolve_spec(s, args.spec)
    except FileNotFoundError:
        if args.report_only or args.diff_scope:
            spec_path = None
        else:
            raise

    verdict = run_gates(
        s,
        target,
        tier=args.tier,
        spec_path=spec_path,
        adapter_name=args.adapter,
        base=args.base,
        allow_mutation=args.mutation,
        paths=args.paths,
        report_only=args.report_only,
        diff_scope=args.diff_scope,
        work_kind=args.work_kind,
    )
    s.verdicts_dir.mkdir(parents=True, exist_ok=True)
    verdict.write(s.verdicts_dir / "latest.json")

    appended = None
    if not args.no_ledger:
        try:
            sk = keys.resolve_signer(s.root)
            appended = Ledger(s.ledger_path).append(
                "verdict",
                verdict.to_dict(),
                sk,
                spec_id=verdict.spec_id,
                requirement_ids=verdict.requirement_ids(),
            )
        except FileNotFoundError as exc:
            print(f"⚠️  ledger entry skipped: {exc}", file=sys.stderr)

    gst = _styler(args)
    human = _format_verdict(verdict, appended, gst)
    if args.report_only and verdict.result != STATUS_PASS:
        human += "\n  " + gst.mark("info") + " report-only: verdict emitted but not enforced"
    # Consolidated install call-to-action: if gates couldn't run because their tools are absent, say
    # exactly what to install so the next `gate run` / `3pwr run` succeeds (3PWR-FR-034). Human-output
    # only — the per-gate `missing_tool`/`install_hint` already ride the JSON verdict.
    missing: list[tuple[str, str]] = []
    seen: set[str] = set()
    for g in verdict.gates:
        tool = (g.details or {}).get("missing_tool")
        if tool and tool not in seen:
            seen.add(tool)
            missing.append((tool, (g.details or {}).get("install_hint", "")))
    if missing:
        human += "\n\n" + gst.warn(
            "⚠ missing toolchain — some gates could not run. Install, then re-run:"
        )
        for tool, inst in missing:
            human += "\n    " + (
                f"{tool}  →  {inst}" if inst else f"{tool}  (install it and re-run)"
            )
    _print(
        {"verdict": verdict.to_dict(), "ledger_seq": (appended or {}).get("seq")},
        args.json,
        _compose(
            args,
            gst,
            title="gate run",
            subject=f"{verdict.spec_id or '?'} · {verdict.tier} · {verdict.adapter}",
            rows=[human],
        ),
    )
    # Report-only never blocks the developer's flow; ratchet to a blocking run
    # (optionally diff-scoped via --base/--paths) once the diff is clean (3PWR-FR-052).
    if args.report_only:
        return EXIT_OK
    return EXIT_OK if verdict.result == STATUS_PASS else EXIT_FAIL


def cmd_conformance(args: argparse.Namespace) -> int:
    from .conformance import run_conformance

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    roots = [Path(t).resolve() for t in args.tests] if args.tests else [s.root]
    gate = run_conformance(spec_path, roots)
    obj = {"gate": gate.gate, "status": gate.status, **gate.details}
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"spec-conformance {gate.status.upper()}",
            gate.details.get("spec_id", "?"),
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        obj,
        args.json,
        _compose(
            args, cst, title="conformance", subject=gate.details.get("spec_id", ""), rows=rows
        ),
    )
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


def cmd_verify(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    res = verify_ledger(s.ledger_path, s.pubkey_path, [s.oracle_pubkey_path])
    # Custody preflight (HARDN-FR-002): a private key inside the working tree or readable
    # by other users is a custody violation — surfaced here, where trust is re-derived.
    custody = keys.custody_findings(s.root)
    ok = res.ok and not custody
    vst = _styler(args)
    rows = [vst.status_row("pass" if res.ok else "fail", res.summary())]
    for c in custody:
        rows.append(vst.status_row("fail", c))
    anchored: Optional[dict] = None
    if getattr(args, "anchored", False):
        # Opt-in anchored mode (HARDN-FR-005): cross-check the chain against the latest
        # local anchor tag. Plain `verify` never reads an anchor (HARDN-NFR-001).
        chk = anchor.check_anchored(Ledger(s.ledger_path).entries(), anchor.latest_anchor(s.root))
        anchored = {"ok": chk.ok, "anchor_seq": chk.anchor_seq, "problems": chk.problems}
        ok = ok and chk.ok
        if chk.ok:
            rows.append(
                vst.status_row(
                    "pass", f"anchor OK — chain extends the witnessed head (seq={chk.anchor_seq})"
                )
            )
        for p in chk.problems:
            rows.append(vst.status_row("fail", p))
    _print(
        {
            "ok": ok,
            "entries": res.entries,
            "problems": res.problems,
            "key_custody": custody,
            **({"anchored": anchored} if anchored is not None else {}),
        },
        args.json,
        _compose(
            args,
            vst,
            title="verify",
            subject="ledger chain + signatures",
            rows=rows,
            extra=[vst.dim(f"{res.entries} entries checked")],
        ),
    )
    return EXIT_OK if ok else EXIT_FAIL


def cmd_anchor(args: argparse.Namespace) -> int:
    """Record the ledger head with an external witness (HARDN-FR-005) — opt-in.

    Creates the annotated git tag ``3powers/anchor/<seq>`` carrying the head's entry hash,
    appends a local ``anchor`` receipt entry, and — only under ``--push`` — pushes the tag
    (the sole network-capable operation, HARDN-NFR-001).
    """
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    head = anchor.head_of(ledger.entries())
    if head is None:
        print("error: the ledger is empty — nothing to anchor", file=sys.stderr)
        return EXIT_USAGE
    seq, entry_hash = head
    ok, msg = anchor.create_anchor(s.root, seq, entry_hash, push=args.push, remote=args.remote)
    if not ok:
        print(f"error: {msg}", file=sys.stderr)
        return EXIT_FAIL
    try:
        sk = keys.resolve_signer(s.root)
        receipt = ledger.append(
            "anchor",
            {
                "anchored_seq": seq,
                "anchored_hash": entry_hash,
                "witness": "git-tag",
                "ref": msg,
                "pushed": bool(args.push),
            },
            sk,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    ast = _styler(args)
    _print(
        {
            "anchored_seq": seq,
            "anchored_hash": entry_hash,
            "ref": msg,
            "pushed": bool(args.push),
            "ledger_seq": receipt["seq"],
        },
        args.json,
        _compose(
            args,
            ast,
            title="anchor",
            subject=f"seq={seq}",
            rows=[
                ast.status_row(
                    "pass",
                    f"anchored ledger head seq={seq} ({entry_hash}) as tag {msg}"
                    + (
                        " — pushed"
                        if args.push
                        else " — local only; push it to complete the witness"
                    ),
                ),
                ast.kv([("receipt", f"ledger seq={receipt['seq']}")]),
            ],
        ),
    )
    return EXIT_OK


def cmd_signoff(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"approver": args.approver, "stage": args.stage, "note": args.note or ""}
    # A Spec-stage sign-off freezes the law: seal the full document's hash inside the
    # signed entry so any later silent mutation is caught (SLOCK-FR-001). A fresh
    # Spec-stage sign-off supersedes the previous hash (SLOCK-FR-006).
    if args.stage.lower() == "spec":
        payload.update(_spec_approval_payload(s, getattr(args, "spec", None)))
    entry = Ledger(s.ledger_path).append("signoff", payload, sk, spec_id=args.spec_id or "")
    sealed = f"; spec hash sealed ({payload['spec_hash']})" if payload.get("spec_hash") else ""
    sst = _styler(args)
    print(
        _compose(
            args,
            sst,
            title="signoff",
            subject=f"{args.spec_id or ''} · {args.stage}".strip(" ·"),
            rows=[
                sst.status_row(
                    "pass",
                    f"sign-off recorded by {args.approver} for stage '{args.stage}'",
                    f"ledger seq={entry['seq']}{sealed}",
                )
            ],
        )
    )
    return EXIT_OK


def cmd_spec_diff(args: argparse.Namespace) -> int:
    """Read-only spec-integrity report (SLOCK-FR-007) — never writes to the ledger.

    Exit 0 when the spec matches its approval hash (or none is recorded); exit 1 on a
    mismatch, with a textual diff when the sign-off commit is known.
    """
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    spec_path: Optional[Path]
    try:
        spec_path = _resolve_spec(s, args.spec)
    except FileNotFoundError:
        spec_path = None  # fall back to the path recorded at approval
    lock = speclock.check(entries, args.spec_id or "", s.root, spec_path=spec_path)

    if lock.status == speclock.NO_APPROVAL:
        _print(
            {"spec_id": args.spec_id, "status": lock.status},
            args.json,
            f"no Spec-stage approval hash recorded for '{args.spec_id}' — nothing to compare "
            "(seal one via `3pwr signoff --stage spec`)",
        )
        return EXIT_OK

    obj = {
        "spec_id": args.spec_id,
        "status": lock.status,
        "approval_seq": lock.approval_seq,
        "approver": lock.approver,
        "approved_hash": lock.approved_hash,
        "current_hash": lock.current_hash,
        "spec_path": lock.spec_path,
    }
    dst = _styler(args)
    if lock.status == speclock.MATCH:
        _print(
            obj,
            args.json,
            _compose(
                args,
                dst,
                title="spec diff",
                subject=args.spec_id or "",
                rows=[
                    dst.status_row(
                        "pass",
                        "spec matches its approval hash",
                        f"ledger seq={lock.approval_seq}, approver={lock.approver}",
                    ),
                    "  " + dst.dim(lock.approved_hash or ""),
                ],
            ),
        )
        return EXIT_OK

    headline = (
        "spec MODIFIED after approval"
        if lock.status == speclock.MISMATCH
        else f"approved spec file is MISSING: {lock.spec_path}"
    )
    lines = [
        dst.status_row("fail", headline),
        f"  approved: {lock.approved_hash} (ledger seq={lock.approval_seq}, "
        f"approver={lock.approver})",
        f"  current:  {lock.current_hash or '(missing file)'}",
    ]
    # Textual diff (best-effort): the version at the sign-off commit vs. the file now.
    target = spec_path or speclock.resolve_target(s.root, lock)
    diff_text = ""
    if lock.commit and lock.spec_path and target is not None and target.exists():
        before = _git_out(s.root, ["show", f"{lock.commit}:{lock.spec_path}"])
        if before:
            diff_text = "\n".join(
                difflib.unified_diff(
                    before.splitlines(),
                    target.read_text(encoding="utf-8").splitlines(),
                    fromfile=f"{lock.spec_path} @ {lock.commit} (approved)",
                    tofile=f"{lock.spec_path} (current)",
                    lineterm="",
                )
            )
    if diff_text:
        obj["diff"] = diff_text
        lines.append(diff_text)
    else:
        lines.append("  (no textual diff available — sign-off commit unknown or file missing)")
    _print(
        obj,
        args.json,
        _compose(args, dst, title="spec diff", subject=args.spec_id or "", rows=lines),
    )
    return EXIT_FAIL


def cmd_advance(args: argparse.Namespace) -> int:
    """Local, CI-independent enforcement (3PWR-FR-041/042)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    active = deviations.active_deviations(entries)
    reasons: list[str] = []
    deviations_applied: list[int] = []

    # 1. Ledger must verify (accepting the primary or a distinct oracle signer).
    vres = verify_ledger(s.ledger_path, s.pubkey_path, [s.oracle_pubkey_path])
    if not vres.ok:
        reasons.append("ledger fails verification")

    # 2. Latest *enforced* verdict must be green — OR every red gate must be covered by an
    #    active, signed deviation (3PWR-FR-057). Report-only verdicts are advisory (3PWR-FR-052)
    #    and never satisfy an advance.
    enforced = [
        e
        for e in entries
        if e.get("type") == "verdict" and not e.get("payload", {}).get("report_only")
    ]
    last_verdict = enforced[-1] if enforced else None
    if not last_verdict:
        reasons.append("no enforced verdict recorded")
    elif last_verdict.get("payload", {}).get("result") != STATUS_PASS:
        red_gates = {
            g["gate"]
            for g in last_verdict.get("payload", {}).get("gates", [])
            if g.get("status") == "fail"
        }
        covered = deviations.covered_gates(active, last_verdict.get("spec_id"))
        uncovered = sorted(red_gates - covered)
        if uncovered:
            reasons.append(f"latest verdict is red on un-deviated gate(s): {', '.join(uncovered)}")
        else:
            deviations_applied = sorted(
                int(d["seq"])
                for d in active
                if red_gates & set(d.get("gates", []))
                and (
                    not (d.get("spec_id") or "") or d.get("spec_id") == last_verdict.get("spec_id")
                )
            )

    # 2b. An emergency cleanup overdue past one working day blocks the advance (3PWR-FR-056).
    overdue = deviations.overdue_emergencies(entries)
    if overdue:
        reasons.append(
            f"emergency cleanup overdue ({len(overdue)}) — file the follow-up requirement and "
            "`3pwr deviation --revoke <seq>`"
        )

    # 3. A human sign-off must exist at or after the latest verdict (3PWR-FR-037).
    last_signoff = ledger.latest_of("signoff")
    if not last_signoff:
        reasons.append("no human sign-off recorded")
    elif last_verdict and last_signoff.get("seq", -1) < last_verdict.get("seq", 0):
        reasons.append("sign-off predates the latest verdict")

    # 4. Oracle independence (3PWR-FR-020/021/022/062). The judiciary must have authored the oracle
    #    from the spec, with a different model family, before the implementation. This binds at the
    #    High-risk tier only (oracle separation IS High-risk, spec §4); lower tiers stay advisory.
    #    Detection that the author *touched* the implementation is advisory — surfaced, never blocking.
    #    At High-risk, physical read-path isolation (FR-021, A3) is also proven when a dispatch
    #    attestation is present — and *required* when the repo opts in (roles.oracle.require_dispatch).
    oracle_ok: Optional[bool] = None
    oracle_advisory: list[str] = []
    oracle_dispatch_ok: Optional[bool] = None
    oracle_isolation: Optional[str] = None
    oracle_diversity_relaxed = False
    spec_for_oracle = args.spec_id or (last_verdict.get("spec_id") if last_verdict else "") or ""
    tier = (last_verdict.get("payload", {}) if last_verdict else {}).get("tier")
    if tier == "High-risk":
        rec = oracle.authoring_record(entries, spec_for_oracle)
        test_roots = [s.root / p for p in rec["payload"].get("test_paths", [])] if rec else []
        oracle_diversity_relaxed = deviations.covers_model_diversity(active, spec_for_oracle)
        ind = oracle.independence(
            entries,
            s.load_roles(),
            spec_for_oracle,
            repo_root=s.root,
            test_roots=test_roots,
            require_dispatch=s.oracle_require_dispatch(),
            diversity_relaxed=oracle_diversity_relaxed,
            diversity_level=s.diversity_level(),
            coder_model=s.coder_model(),
        )
        oracle_ok = ind.ok
        oracle_advisory = ind.advisory
        oracle_dispatch_ok = ind.dispatch_ok
        oracle_isolation = ind.isolation_method
        if not ind.ok:
            reasons += [f"oracle independence — {r}" for r in ind.reasons]

    # 5. Spec integrity (SLOCK-FR-005): once a human has approved the spec, its recorded
    #    hash must still match the document on disk — at every tier. A signed, active
    #    `spec_integrity` deviation (3PWR-FR-057) turns the refusal into a warned,
    #    recorded pass; revoking or expiring it re-blocks. A never-approved spec is
    #    never blocked (SLOCK-FR-003).
    lock = speclock.check(entries, spec_for_oracle, s.root)
    spec_integrity_deviated = False
    if not lock.ok:
        if speclock.GATE_NAME in deviations.covered_gates(active, spec_for_oracle):
            spec_integrity_deviated = True
            dev_seqs = [
                int(d["seq"])
                for d in active
                if speclock.GATE_NAME in d.get("gates", [])
                and (not (d.get("spec_id") or "") or d.get("spec_id") == spec_for_oracle)
            ]
            deviations_applied = sorted(set(deviations_applied) | set(dev_seqs))
        else:
            reasons.append(
                f"spec_modified — spec changed after approval (ledger seq={lock.approval_seq}); "
                "review with `3pwr spec diff`, re-approve via `3pwr signoff --stage spec`, or "
                "record a `3pwr deviation --gate spec_integrity`"
            )

    # 6. Git run discipline (GITX-FR-016): when the spec's run records a dedicated branch, a
    #    stage-boundary advance refuses off the run branch or with the completed stage's work
    #    uncommitted — naming the condition and the fix. Relaxable only via the named signed
    #    deviations (GITX-FR-014); a pre-GITX ledger records no branch and is untouched.
    git_branch = gitflow.branch_from_ledger(entries, spec_for_oracle)
    if git_branch:
        covered_git = deviations.covered_gates(active, spec_for_oracle)
        git_cond = gitflow.precondition(s.root)
        if git_cond:
            reasons.append(f"git — {git_cond}")
        else:
            cur_branch = gitflow.current_branch(s.root)
            if cur_branch != git_branch and deviations.GIT_RUN_BRANCH not in covered_git:
                reasons.append(
                    f"git — not on the run's dedicated branch '{git_branch}' (currently "
                    f"'{cur_branch or 'detached HEAD'}'); `git checkout {git_branch}`, or record "
                    f"`3pwr deviation --gate {deviations.GIT_RUN_BRANCH}`"
                )
            dirty = gitflow.uncommitted_run_paths(s.root, entries, spec_for_oracle)
            if dirty and deviations.GIT_STAGE_COMMIT not in covered_git:
                shown = ", ".join(dirty[:5]) + (" …" if len(dirty) > 5 else "")
                reasons.append(
                    f"git — the completed stage's work is not committed: {shown}; commit it on "
                    f"'{git_branch}', or record `3pwr deviation --gate {deviations.GIT_STAGE_COMMIT}`"
                )

    if reasons:
        cst = _styler(args)
        rows = [cst.status_row("fail", f"REFUSED to advance to '{args.stage}'")]
        rows += [cst.status_row("fail", r, indent=4) for r in reasons]
        rows += [
            cst.status_row("warn", f"advisory (not a blocker): {a}", indent=4)
            for a in oracle_advisory
        ]
        _print(
            {
                "advanced": False,
                "stage": args.stage,
                "reasons": reasons,
                "oracle_advisory": oracle_advisory,
            },
            args.json,
            _compose(args, cst, title="advance", subject=args.spec_id or args.stage, rows=rows),
        )
        return EXIT_FAIL

    payload: dict = {"stage": args.stage}
    if deviations_applied:
        payload["deviations_applied"] = deviations_applied
    if spec_integrity_deviated:
        payload["spec_integrity_deviated"] = True
    if oracle_ok is not None:
        payload["oracle_ok"] = oracle_ok
    if oracle_dispatch_ok is not None:
        payload["dispatch_ok"] = oracle_dispatch_ok
    if oracle_isolation:
        payload["isolation_method"] = oracle_isolation
    if oracle_diversity_relaxed:
        payload["diversity_relaxed"] = True
    try:
        sk = keys.resolve_signer(s.root)
        entry = ledger.append("stage_advance", payload, sk, spec_id=args.spec_id or "")
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    note = f" under deviation {deviations_applied}" if deviations_applied else ""
    cst = _styler(args)
    rows = [
        cst.status_row("pass", f"advanced to '{args.stage}'{note}", f"ledger seq={entry['seq']}")
    ]
    rows += [
        cst.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in oracle_advisory
    ]
    _print(
        {
            "advanced": True,
            "stage": args.stage,
            "ledger_seq": entry["seq"],
            "oracle_advisory": oracle_advisory,
            **payload,
        },
        args.json,
        _compose(args, cst, title="advance", subject=args.spec_id or args.stage, rows=rows),
    )
    return EXIT_OK


def cmd_deviation(args: argparse.Namespace) -> int:
    """Record (or revoke) a signed, reversible gate deviation (3PWR-FR-057)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE

    if args.revoke is not None:
        target = next((e for e in ledger.entries() if e["seq"] == args.revoke), None)
        if target is None or target.get("type") != "deviation":
            print(f"error: no deviation at ledger seq={args.revoke}", file=sys.stderr)
            return EXIT_USAGE
        entry = ledger.append(
            "deviation", {"revokes": args.revoke, "reason": args.note or ""}, sk, spec_id=""
        )
        dvt = _styler(args)
        _print(
            {"revoked": args.revoke, "ledger_seq": entry["seq"]},
            args.json,
            _compose(
                args,
                dvt,
                title="deviation",
                subject=f"revoke seq={args.revoke}",
                rows=[
                    dvt.status_row(
                        "pass",
                        f"deviation at seq={args.revoke} revoked",
                        f"ledger seq={entry['seq']}",
                    )
                ],
            ),
        )
        return EXIT_OK

    if not args.gate:
        print("error: --gate is required (or use --revoke <seq>)", file=sys.stderr)
        return EXIT_USAGE
    if not args.approver:
        print("error: --approver is required — a human accepts the deviation", file=sys.stderr)
        return EXIT_USAGE
    allowed = set(GATE_ORDER) | set(deviations.DEVIATABLE_REQUIREMENTS)
    unknown = sorted(set(args.gate) - allowed)
    if unknown:
        print(
            f"error: unknown gate/requirement(s): {', '.join(unknown)}; known gates: "
            f"{', '.join(GATE_ORDER)}; requirements: {', '.join(deviations.DEVIATABLE_REQUIREMENTS)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.until and deviations.parse_iso(args.until) is None:
        print("error: --until must be ISO-8601 (e.g. 2026-07-01T00:00:00Z)", file=sys.stderr)
        return EXIT_USAGE

    payload = deviations.deviation_payload(args.gate, args.note or "", args.approver, args.until)
    entry = ledger.append("deviation", payload, sk, spec_id=args.spec_id or "")
    way_back = f"until {args.until}" if args.until else "revoke to end"
    dvt = _styler(args)
    _print(
        {"gates": payload["gates"], "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            dvt,
            title="deviation",
            subject=", ".join(payload["gates"]),
            rows=[
                dvt.status_row(
                    "warn",
                    f"deviation recorded by {args.approver} for gate(s) {', '.join(payload['gates'])}",
                    f"{way_back}; ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_emergency(args: argparse.Namespace) -> int:
    """Open the constrained emergency fast path (3PWR-FR-056)."""
    s = _settings(args.root)
    if not args.approver:
        print("error: --approver is required — a human opens the emergency path", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    hours = (
        args.cleanup_hours if args.cleanup_hours is not None else deviations.DEFAULT_CLEANUP_HOURS
    )
    payload = deviations.emergency_payload(args.note or "", args.approver, hours)
    entry = Ledger(s.ledger_path).append("deviation", payload, sk, spec_id=args.spec_id or "")
    est = _styler(args)
    _print(
        {
            "emergency": True,
            "deferring": payload["gates"],
            "cleanup_due": payload["cleanup_due"],
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            est,
            title="emergency",
            subject=args.approver,
            rows=[
                est.status_row(
                    "warn",
                    f"EMERGENCY fast path opened by {args.approver}: deferring "
                    f"{', '.join(deviations.EMERGENCY_DEFERRABLE)}",
                    f"until cleanup by {payload['cleanup_due']}",
                ),
                est.status_row(
                    "info", "the security/secret gates, human sign-off, and provenance still apply"
                ),
                est.status_row(
                    "warn",
                    f"clean up within {hours}h (file a requirement + "
                    f"`3pwr deviation --revoke {entry['seq']}`) or advance will block",
                ),
            ],
        ),
    )
    return EXIT_OK


def cmd_ledger_show(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    if args.json:
        print(json.dumps(entries, indent=2))
        return EXIT_OK
    lst = _styler(args)
    if not entries:
        print(_compose(args, lst, title="ledger", rows=[lst.status_row("info", "empty ledger")]))
        return EXIT_OK
    table_rows = [
        [
            f"#{e['seq']}",
            e["type"],
            e["timestamp"],
            e.get("spec_id", "") or "—",
            e["signer_key_id"],
        ]
        for e in entries
    ]
    out = []
    if _verbosity(args) != "quiet":
        out.append(
            lst.header("ledger", f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
        )
    out.append(lst.table(table_rows, headers=["seq", "type", "timestamp", "spec", "signer"]))
    print("\n".join(out))
    return EXIT_OK


def cmd_roles_check(args: argparse.Namespace) -> int:
    """Check model diversity between two roles (3PWR-FR-022), at the configured granularity.

    Recommended, not forced: a same-family setup passes only under a signed ``model_diversity``
    deviation (3PWR-FR-057), which turns the VIOLATION into a warned RELAXED (exit 0)."""
    s = _settings(args.root)
    level = s.diversity_level()
    ok = model_diversity_ok(s.load_roles(), args.role_a, args.role_b, level)
    dev_seq = None
    if not ok:
        active = deviations.active_deviations(Ledger(s.ledger_path).entries())
        dev_seq = deviations.diversity_deviation(active)  # global scope for a config-level check
    verdict = "OK" if ok else ("RELAXED" if dev_seq is not None else "VIOLATION")
    rct = _styler(args)
    state = "pass" if ok else ("warn" if dev_seq is not None else "fail")
    rows = [
        rct.status_row(
            state, f"model diversity ({level}) {args.role_a} vs {args.role_b}: {verdict}"
        )
    ]
    if dev_seq is not None:
        rows.append(
            rct.status_row(
                "warn",
                f"relaxed by model_diversity deviation #{dev_seq} — "
                f"a different {level} is recommended, not required",
                indent=4,
            )
        )
    _print(
        {
            "diverse": ok,
            "level": level,
            "relaxed_by_deviation": dev_seq,
            "role_a": args.role_a,
            "role_b": args.role_b,
        },
        args.json,
        _compose(
            args, rct, title="roles-check", subject=f"{args.role_a} vs {args.role_b}", rows=rows
        ),
    )
    return EXIT_OK if (ok or dev_seq is not None) else EXIT_FAIL


def cmd_oracle_seal(args: argparse.Namespace) -> int:
    """Seal a spec-only oracle bundle the judiciary authors from (3PWR-FR-020)."""
    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    spec_id, criteria = oracle.extract_criteria(spec_path)
    spec_id = args.spec_id or spec_id
    if not spec_id:
        print("error: could not determine the spec id; pass --spec-id", file=sys.stderr)
        return EXIT_USAGE
    if not criteria:
        print("error: no requirement ids / acceptance criteria found in the spec", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    source = os.path.relpath(spec_path, s.root)
    bundle = oracle.build_bundle(spec_id, source, criteria, deviations.iso(deviations.now_utc()))
    out = s.dir / "oracle" / spec_id / "sealed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    entry = Ledger(s.ledger_path).append(
        "oracle",
        oracle.seal_payload(spec_id, source, criteria),
        sk,
        spec_id=spec_id,
        requirement_ids=sorted(criteria),
    )
    ost = _styler(args)
    _print(
        {
            "sealed": str(out),
            "bundle_hash": bundle["bundle_hash"],
            "requirement_ids": bundle["requirement_ids"],
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            ost,
            title="oracle seal",
            subject=spec_id,
            rows=[
                ost.status_row(
                    "pass",
                    f"sealed oracle bundle for {spec_id}: {len(criteria)} acceptance criteria",
                    str(out),
                ),
                ost.kv([("bundle hash", bundle["bundle_hash"]), ("ledger", f"seq={entry['seq']}")]),
            ],
        ),
    )
    return EXIT_OK


def cmd_oracle_record(args: argparse.Namespace) -> int:
    """Record oracle authoring; refuse the coder's model family (3PWR-FR-022/062)."""
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    seal = oracle.active_seal(entries, args.spec_id)
    if seal is None:
        print(
            f"error: no sealed bundle for {args.spec_id} — run `3pwr oracle seal` first",
            file=sys.stderr,
        )
        return EXIT_USAGE
    fam = oracle.family_of(args.model)
    coder = oracle.coder_family(s.load_roles())
    level = s.diversity_level()
    coder_side = s.coder_model() or coder
    if not fam:
        print("error: --model must be <family/model> (e.g. anthropic/claude-...)", file=sys.stderr)
        return EXIT_USAGE
    if not coder:
        print("error: coder model family is unset in roles.yaml", file=sys.stderr)
        return EXIT_USAGE
    # Diversity is recommended, not forced (3PWR-FR-022): a same-family/model setup proceeds only under
    # a signed model_diversity deviation (3PWR-FR-057) — warned and recorded, never a silent drop.
    diversity_dev: Optional[int] = None
    if not oracle.diverse(coder_side, args.model, level):
        diversity_dev = deviations.diversity_deviation(
            deviations.active_deviations(entries), args.spec_id
        )
        if diversity_dev is None:
            ort = _styler(args)
            _print(
                {
                    "recorded": False,
                    "reason": "same_model_family",
                    "oracle_family": fam,
                    "coder_family": coder,
                    "level": level,
                },
                args.json,
                _compose(
                    args,
                    ort,
                    title="oracle record",
                    subject=args.spec_id,
                    rows=[
                        ort.status_row(
                            "fail",
                            f"REFUSED: oracle model '{args.model}' is not diverse from the coder "
                            f"at {level} level",
                        ),
                        ort.status_row(
                            "info",
                            "the judiciary must differ. Diversity is recommended, not forced: "
                            "record a `3pwr deviation --gate model_diversity --approver <you> "
                            "--note ...` to proceed anyway",
                            indent=4,
                        ),
                    ],
                ),
            )
            return EXIT_FAIL

    test_paths: list[str] = []
    test_hashes: dict[str, str] = {}
    test_texts: dict[str, str] = {}
    for t in args.tests:
        tp = Path(t).resolve()
        if not tp.exists():
            print(f"error: oracle test not found: {tp}", file=sys.stderr)
            return EXIT_USAGE
        rel = os.path.relpath(tp, s.root)
        text = tp.read_text(encoding="utf-8")
        test_paths.append(rel)
        test_hashes[rel] = canonical.sha256_hex(text.encode("utf-8"))
        test_texts[rel] = text

    # Advisory (non-blocking) peek/touch signals for human review (3PWR-FR-021).
    bundle_file = s.dir / "oracle" / args.spec_id / "sealed.json"
    criteria_text = ""
    if bundle_file.exists():
        data = json.loads(bundle_file.read_text(encoding="utf-8"))
        criteria_text = " ".join(c.get("text", "") for c in data.get("criteria", []))
    advisory = oracle.scan_touched_impl(
        covdiff.changed_files(s.root, args.base), set(test_paths)
    ) + oracle.scan_symbol_leakage(test_texts, criteria_text)

    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = oracle.record_payload(
        seal["payload"]["bundle_hash"], args.model, test_paths, test_hashes, advisory, diversity_dev
    )
    entry = Ledger(s.ledger_path).append(
        "oracle",
        payload,
        sk,
        spec_id=args.spec_id,
        requirement_ids=seal["payload"].get("requirement_ids", []),
    )
    ort = _styler(args)
    rows = [
        ort.status_row(
            "pass",
            f"recorded oracle authoring for {args.spec_id} by {args.model}",
            f"family={fam}; {len(test_paths)} test file(s); ledger seq={entry['seq']}",
        )
    ]
    if diversity_dev is not None:
        rows.append(
            ort.status_row(
                "warn",
                f"model diversity RELAXED by deviation #{diversity_dev} — "
                f"same {level} as the coder; not the recommended posture",
                indent=4,
            )
        )
    rows += [ort.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in advisory]
    _print(
        {
            "recorded": True,
            "model_family": fam,
            "test_paths": test_paths,
            "advisory_findings": advisory,
            "diversity_deviation": diversity_dev,
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(args, ort, title="oracle record", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK


def cmd_oracle_verify(args: argparse.Namespace) -> int:
    """Verify oracle independence structurally, from the ledger (3PWR-FR-020/021/022/062)."""
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    rec = oracle.authoring_record(entries, args.spec_id)
    if args.tests:
        test_roots = [Path(t).resolve() for t in args.tests]
    elif rec:
        test_roots = [s.root / p for p in rec["payload"].get("test_paths", [])]
    else:
        test_roots = []
    ind = oracle.independence(
        entries,
        s.load_roles(),
        args.spec_id,
        repo_root=s.root,
        test_roots=test_roots,
        require_dispatch=args.require_dispatch,
        diversity_relaxed=deviations.covers_model_diversity(
            deviations.active_deviations(entries), args.spec_id
        ),
        diversity_level=s.diversity_level(),
        coder_model=s.coder_model(),
    )
    ovt = _styler(args)
    rows = [
        ovt.status_row(
            "pass" if ind.ok else "fail",
            f"oracle independence for {args.spec_id}: {'PASS' if ind.ok else 'FAIL'}",
        )
    ]
    kv_pairs = []
    if ind.model_family:
        kv_pairs.append(("oracle model family", ind.model_family))
    if ind.covered:
        kv_pairs.append(("covered", ", ".join(ind.covered)))
    if kv_pairs:
        rows.append(ovt.kv(kv_pairs))
    if ind.isolation_method:
        rows.append(
            ovt.status_row(
                "pass" if ind.dispatch_ok else "fail",
                f"read-path isolation: {ind.isolation_method}",
                indent=4,
            )
        )
    for r in ind.reasons:
        rows.append(ovt.status_row("fail", r, indent=4))
    for a in ind.advisory:
        rows.append(ovt.status_row("warn", f"advisory (not a blocker): {a}", indent=4))
    _print(
        {
            "ok": ind.ok,
            "reasons": ind.reasons,
            "advisory": ind.advisory,
            "covered": ind.covered,
            "model_family": ind.model_family,
            "dispatch_ok": ind.dispatch_ok,
            "isolation_method": ind.isolation_method,
        },
        args.json,
        _compose(args, ovt, title="oracle verify", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK if ind.ok else EXIT_FAIL


def cmd_oracle_dispatch(args: argparse.Namespace) -> int:
    """Author the oracle headlessly under a non-coder integration, in a sanitized worktree from
    which the implementation is physically absent (3PWR-FR-021/012/013; A3).

    Dispatch is Phase-A provisioning, recorded in the ledger — it never enters the deterministic
    gate verdict (3PWR-NFR-001). The blocking isolation check binds at ``advance`` (High-risk)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    seal = oracle.active_seal(ledger.entries(), args.spec_id)
    if seal is None:
        print(
            f"error: no sealed bundle for {args.spec_id} — run `3pwr oracle seal` first",
            file=sys.stderr,
        )
        return EXIT_USAGE

    # Resolve the oracle model/family. Diversity is recommended, not forced (3PWR-FR-022): a
    # same-family/model dispatch proceeds only under a signed model_diversity deviation (FR-057).
    coder = oracle.coder_family(s.load_roles())
    coder_side = s.coder_model() or coder
    level = s.diversity_level()
    intg_family = oracle.integration_family(args.integration)
    model = args.model or (f"{intg_family}/{args.integration}" if intg_family else "")
    if not model:
        print(
            f"error: cannot resolve a model family for integration '{args.integration}'; "
            "pass --model <family/model>",
            file=sys.stderr,
        )
        return EXIT_USAGE
    fam = oracle.family_of(model)
    diversity_dev: Optional[int] = None
    if coder and not oracle.diverse(coder_side, model, level):
        diversity_dev = deviations.diversity_deviation(
            deviations.active_deviations(ledger.entries()), args.spec_id
        )
        if diversity_dev is None:
            odt = _styler(args)
            _print(
                {
                    "dispatched": False,
                    "reason": "same_model_family",
                    "oracle_family": fam,
                    "coder_family": coder,
                    "level": level,
                },
                args.json,
                _compose(
                    args,
                    odt,
                    title="oracle dispatch",
                    subject=args.spec_id,
                    rows=[
                        odt.status_row(
                            "fail",
                            f"REFUSED: dispatch integration '{args.integration}' (model '{model}') "
                            f"is not diverse from the coder at {level} level",
                        ),
                        odt.status_row(
                            "info",
                            "the judiciary must differ. Record a `3pwr deviation --gate "
                            "model_diversity --approver <you> --note ...` to proceed anyway",
                            indent=4,
                        ),
                    ],
                ),
            )
            return EXIT_FAIL

    sealed_bundle = s.dir / "oracle" / args.spec_id / "sealed.json"
    worktree_dir = s.dir / "worktrees" / args.spec_id
    advisory: list[str] = []
    try:
        try:
            info = oracle.build_sanitized_worktree(
                s.root, worktree_dir, sealed_bundle, base_ref=args.base
            )
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_FAIL
        violations = oracle.isolation_violations(info.manifest)
        if violations:
            print(
                "error: worktree isolation failed — implementation still present: "
                + ", ".join(violations[:5]),
                file=sys.stderr,
            )
            return EXIT_FAIL

        # Dispatch the authoring step to the oracle agent directly, headless, inside the sanitized
        # worktree — no external workflow substrate (EXEC-FR-009; supersedes the Spec Kit dispatch).
        # The engine issues no model call itself; the agent process does (EXEC-NFR-001).
        dispatched_model = model
        if not args.dry_run:
            try:
                oracle_manifest = agents.load_agent(s, args.integration)
            except FileNotFoundError as exc:
                print(f"error: {exc} — add the manifest or use --dry-run", file=sys.stderr)
                return EXIT_USAGE
            if not agents.is_headless(oracle_manifest):
                print(
                    f"error: agent '{args.integration}' is not headless-dispatchable",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            criteria = ""
            if sealed_bundle.exists():
                data = json.loads(sealed_bundle.read_text(encoding="utf-8"))
                criteria = " ".join(c.get("text", "") for c in data.get("criteria", []))
            orc = CliAgentRunner(
                s,
                oracle_manifest,
                model=model,
                cwd=info.path,
                intent=(
                    f"Author oracle tests into ./oracle-tests/ for spec {args.spec_id}, from the "
                    "sealed acceptance criteria ONLY — do not read any implementation."
                ),
                spec_text=criteria,
            )
            res = orc.dispatch("oracle", "Build")
            if not res.ok:
                print("error: oracle dispatch failed:\n  " + res.detail, file=sys.stderr)
                return EXIT_FAIL
            dispatched_model = res.model or model

        # Collect authored oracle tests (from the worktree, or --tests for --dry-run / manual).
        dest_root = s.root / "tests" / "oracle" / args.spec_id
        if args.tests:
            sources = [Path(t).resolve() for t in args.tests]
        else:
            out_dir = info.path / "oracle-tests"
            sources = (
                sorted(f for f in out_dir.rglob("*") if f.is_file()) if out_dir.is_dir() else []
            )
        test_paths: list[str] = []
        test_hashes: dict[str, str] = {}
        test_texts: dict[str, str] = {}
        for src in sources:
            if not src.exists():
                print(f"error: oracle test not found: {src}", file=sys.stderr)
                return EXIT_USAGE
            text = src.read_text(encoding="utf-8")
            dest = dest_root / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            rel = os.path.relpath(dest, s.root)
            test_paths.append(rel)
            test_hashes[rel] = canonical.sha256_hex(text.encode("utf-8"))
            test_texts[rel] = text

        # Advisory (non-blocking) peek/touch signals, unchanged from plan 008 (3PWR-FR-021).
        criteria_text = ""
        if sealed_bundle.exists():
            data = json.loads(sealed_bundle.read_text(encoding="utf-8"))
            criteria_text = " ".join(c.get("text", "") for c in data.get("criteria", []))
        advisory = oracle.scan_touched_impl(
            covdiff.changed_files(s.root, args.base), set(test_paths)
        ) + oracle.scan_symbol_leakage(test_texts, criteria_text)

        # Sign the record + dispatch attestation with the (optional) distinct oracle identity.
        try:
            osk = keys.resolve_signer(s.root, role="oracle")
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_USAGE
        seal_hash = seal["payload"]["bundle_hash"]
        req_ids = seal["payload"].get("requirement_ids", [])
        rec_entry = ledger.append(
            "oracle",
            oracle.record_payload(
                seal_hash, dispatched_model, test_paths, test_hashes, advisory, diversity_dev
            ),
            osk,
            spec_id=args.spec_id,
            requirement_ids=req_ids,
        )
        disp_entry = ledger.append(
            "oracle",
            oracle.dispatch_payload(
                seal_hash,
                args.integration,
                dispatched_model,
                {
                    "method": "git-worktree",
                    "manifest_hash": info.manifest_hash,
                    "file_count": info.file_count,
                    "excluded_absent": True,
                },
            ),
            osk,
            spec_id=args.spec_id,
            requirement_ids=req_ids,
        )

        odt = _styler(args)
        rows = [
            odt.status_row(
                "pass",
                f"dispatched oracle authoring for {args.spec_id} under '{args.integration}'",
                f"family={fam}; {len(test_paths)} test file(s)",
            ),
            odt.status_row(
                "pass",
                f"read-path isolation via git-worktree ({info.file_count} files, "
                "implementation absent)",
                indent=4,
            ),
            odt.kv(
                [
                    ("record", f"seq={rec_entry['seq']}"),
                    ("dispatch", f"seq={disp_entry['seq']}"),
                    ("manifest", info.manifest_hash),
                ]
            ),
        ]
        if diversity_dev is not None:
            rows.append(
                odt.status_row(
                    "warn",
                    f"model diversity RELAXED by deviation #{diversity_dev} — "
                    f"same {level} as the coder; not the recommended posture",
                    indent=4,
                )
            )
        if args.dry_run:
            rows.append(
                odt.status_row(
                    "info",
                    "dry-run: worktree isolation built + attested; no live agent dispatched",
                    indent=4,
                )
            )
        rows += [
            odt.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in advisory
        ]
        _print(
            {
                "dispatched": True,
                "integration": args.integration,
                "model": dispatched_model,
                "model_family": fam,
                "test_paths": test_paths,
                "manifest_hash": info.manifest_hash,
                "file_count": info.file_count,
                "excluded_absent": True,
                "advisory_findings": advisory,
                "diversity_deviation": diversity_dev,
                "record_seq": rec_entry["seq"],
                "dispatch_seq": disp_entry["seq"],
            },
            args.json,
            _compose(args, odt, title="oracle dispatch", subject=args.spec_id, rows=rows),
        )
        return EXIT_OK
    finally:
        if not args.keep_worktree:
            oracle.teardown_worktree(s.root, worktree_dir)


def cmd_observe_signal(args: argparse.Namespace) -> int:
    """Record a production signal and route it to the legislature as new intent (3PWR-FR-054)."""
    s = _settings(args.root)
    if args.kind not in observe.SIGNAL_KINDS:
        print(f"error: --kind must be one of {', '.join(observe.SIGNAL_KINDS)}", file=sys.stderr)
        return EXIT_USAGE
    if not args.note:
        print("error: --note is required — describe the production lesson", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    backlog = s.dir / "feedback" / f"{args.spec_id}.md"
    fb_id = observe.route_to_backlog(backlog, args.spec_id, args.kind, args.nfr or "", args.note)
    entry = Ledger(s.ledger_path).append(
        "observe",
        observe.signal_payload(args.kind, args.note, args.nfr, fb_id),
        sk,
        spec_id=args.spec_id,
        requirement_ids=[args.nfr] if args.nfr else [],
    )
    ost = _styler(args)
    _print(
        {
            "kind": args.kind,
            "routed_to": fb_id,
            "backlog": str(backlog),
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            ost,
            title="observe signal",
            subject=f"{args.kind} · {args.spec_id}",
            rows=[
                ost.status_row(
                    "pass",
                    f"observed [{args.kind}] for {args.spec_id} → routed to the legislature "
                    f"as new intent {fb_id}",
                ),
                ost.kv(
                    [
                        ("backlog", str(backlog)),
                        ("next", "take it into a new `3pwr run` spec — not an in-place patch"),
                    ]
                ),
                ost.status_row(
                    "info", "spec now at the Observe stage", f"ledger seq={entry['seq']}"
                ),
            ],
        ),
    )
    return EXIT_OK


def cmd_observe_coverage(args: argparse.Namespace) -> int:
    """Report NFR-instrumentation coverage — which NFRs have a live check (3PWR-FR-054)."""
    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    reg_path = (
        Path(args.registry).resolve() if args.registry else s.dir / "config" / "observability.yaml"
    )
    observability: dict = {}
    if reg_path.exists():
        observability = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    cov = observe.nfr_coverage(spec_path, observability)
    ost = _styler(args)
    rows = [
        ost.status_row(
            "pass" if cov.ok else "warn",
            f"NFR instrumentation: {len(cov.instrumented)}/{len(cov.nfrs)} NFR(s) have a live check",
            cov.spec_id,
        )
    ]
    for m in cov.missing:
        rows.append(ost.status_row("fail", f"{m}: no live production check registered", indent=4))
    _print(
        {
            "spec_id": cov.spec_id,
            "nfrs": cov.nfrs,
            "instrumented": cov.instrumented,
            "missing": cov.missing,
        },
        args.json,
        _compose(args, ost, title="observe coverage", subject=cov.spec_id, rows=rows),
    )
    return EXIT_OK if cov.ok else EXIT_FAIL


def _actions_path(s: Settings) -> Path:
    return s.dir / "runtime" / "actions.jsonl"


def cmd_observe_log_action(args: argparse.Namespace) -> int:
    """Append a tamper-evident, attributable runtime agent action (3PWR-FR-055)."""
    s = _settings(args.root)
    if not args.agent or not args.action:
        print("error: --agent and --action are required", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = Ledger(_actions_path(s)).append(
        "agent_action",
        observe.action_payload(args.agent, args.action),
        sk,
        spec_id=args.spec_id or "",
    )
    ost = _styler(args)
    _print(
        {"agent": args.agent, "seq": entry["seq"]},
        args.json,
        _compose(
            args,
            ost,
            title="observe log-action",
            subject=args.agent,
            rows=[
                ost.status_row(
                    "pass",
                    f"logged runtime action by {args.agent}",
                    f"runtime log seq={entry['seq']}; tamper-evident — "
                    "check with `3pwr observe verify-actions`",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_observe_verify_actions(args: argparse.Namespace) -> int:
    """Verify the runtime agent-action log's chain + signatures (3PWR-FR-055/040)."""
    s = _settings(args.root)
    res = verify_ledger(_actions_path(s), s.pubkey_path)
    ost = _styler(args)
    _print(
        {"ok": res.ok, "entries": res.entries, "problems": res.problems},
        args.json,
        _compose(
            args,
            ost,
            title="observe verify-actions",
            rows=[ost.status_row("pass" if res.ok else "fail", res.summary())],
        ),
    )
    return EXIT_OK if res.ok else EXIT_FAIL


def cmd_status(args: argparse.Namespace) -> int:
    """Per-spec lifecycle stage, derived from the ledger (3PWR-FR-011/019)."""
    s = _settings(args.root)
    ledger_entries = Ledger(s.ledger_path).entries()
    states = lifecycle.derive(ledger_entries)
    if args.spec_id:
        states = {k: v for k, v in states.items() if k == args.spec_id}
    rows = [
        {
            "spec_id": st.spec_id,
            "stage": st.stage,
            "last_verdict": st.last_verdict,
            "signed_off": st.signed_off,
            "aborted": st.aborted,
            # The most recent unresolved run failure, if any (AUTOX-FR-007).
            "failed": st.failed,
            "failed_stage": st.failed_stage,
            "failed_class": st.failed_class,
            "failed_at": st.failed_at,
        }
        for st in states.values()
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK
    sst = _styler(args)
    out: list[str] = []
    if _verbosity(args) != "quiet":
        out.append(sst.header("status", args.spec_id or "all tracked specs"))
    if not rows:
        out.append(sst.status_row("info", "no tracked specs in the ledger"))
    else:
        table_rows = []
        for r in rows:
            flags = []
            if r["signed_off"]:
                flags.append("signed-off")
            if r["aborted"]:
                flags.append("ABORTED")
            if r["failed"]:
                # Distinct from paused-at-gate and from in-progress (AUTOX-FR-007).
                flags.append(
                    f"failed at {r['failed_stage'] or '?'} ({r['failed_class']}) at "
                    f"{r['failed_at'] or '?'}"
                )
            state = (
                "fail"
                if (r["failed"] or r["aborted"])
                else ("pass" if r["last_verdict"] == "pass" else "info")
            )
            table_rows.append(
                [
                    sst.mark(state),
                    str(r["spec_id"]),
                    str(r["stage"]),
                    str(r["last_verdict"]),
                    " ".join(flags),
                ]
            )
        out.append(sst.table(table_rows, headers=["", "spec", "stage", "verdict", "notes"]))
    # Surface active deviations + overdue emergency cleanups (3PWR-FR-056/057).
    active = deviations.active_deviations(ledger_entries)
    overdue_seqs = {d.get("seq") for d in deviations.overdue_emergencies(ledger_entries)}
    for d in active:
        kind = "emergency" if d.get("emergency") else "deviation"
        tag = " — CLEANUP OVERDUE" if d.get("seq") in overdue_seqs else ""
        out.append(
            sst.status_row(
                "warn" if tag else "todo",
                f"{kind} #{d.get('seq')}: gates={','.join(d.get('gates', []))} "
                f"by {d.get('approver', '?')}{tag}",
            )
        )
    # Surface each run's git lifecycle state (GITX-FR-009): its dedicated branch and the committed
    # stages — derived from the signed ledger alone, consistent with the existing status semantics.
    for r in rows:
        run_branch = gitflow.branch_from_ledger(ledger_entries, str(r["spec_id"]))
        if run_branch:
            done_steps = gitflow.committed_steps(ledger_entries, str(r["spec_id"]))
            out.append(
                sst.status_row(
                    "info",
                    f"{r['spec_id']}: run branch {run_branch}",
                    f"committed stages: {', '.join(done_steps) or '—'}",
                )
            )
    # Surface oracle authoring records + advisory peek/touch findings (3PWR-FR-020/021/062).
    for e in ledger_entries:
        if e.get("type") != "oracle" or (e.get("payload") or {}).get("kind") != "record":
            continue
        p = e["payload"]
        out.append(
            sst.status_row(
                "info",
                f"oracle record #{e.get('seq')} {e.get('spec_id', '') or '(global)'}: "
                f"model={p.get('model', '?')} family={p.get('model_family', '?')}",
            )
        )
        for finding in p.get("advisory_findings", []):
            out.append(sst.status_row("warn", f"advisory (not a blocker): {finding}", indent=6))
    print("\n".join(out))
    return EXIT_OK


def cmd_git_start(args: argparse.Namespace) -> int:
    """Establish the run's dedicated branch for a MANUAL drive (GITX-FR-016).

    The command-by-command `/3pwr.*` path gets the same guarantees as `3pwr run`: a working git
    repository (GITX-FR-002), the clean-start guard (GITX-FR-007), and one dedicated branch named
    from the run's SRCX identity (GITX-FR-003/004) — bound to the run in the signed ledger so a
    later resume or `advance` recovers it offline (GITX-FR-005). Idempotent: an already-established
    run re-enters its recorded branch and appends nothing new."""
    s = _settings(args.root)
    gst = _styler(args)
    cond = gitflow.precondition(s.root)
    if cond:
        print(f"error: {cond}", file=sys.stderr)
        return EXIT_USAGE
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    prefs = gitflow.load_prefs(s.git_config_path)
    if prefs.malformed and not args.json:
        print(
            "warning: .3powers/config/git.yaml is malformed — using the default git preferences",
            file=sys.stderr,
        )
    # Resolve the run's feature identity: an explicit --feature wins, else the ledger's binding.
    feature_dir: Optional[Path] = None
    if args.feature:
        p = Path(args.feature)
        feature_dir = p if p.is_absolute() else (s.root / p)
        if not feature_dir.is_dir():
            print(f"error: feature folder not found: {args.feature}", file=sys.stderr)
            return EXIT_USAGE
    else:
        feature_dir = _run_feature_dir_from_ledger(s, entries, args.spec_id)
    recorded_branch = gitflow.branch_from_ledger(entries, args.spec_id)
    identity = feature_dir.name if feature_dir is not None else workspace.slugify(args.spec_id)
    branch = recorded_branch or gitflow.run_branch_name(prefs.branch_prefix, identity)
    # The clean-start guard (GITX-FR-007) — the run's own recorded paths and its feature folder are
    # tolerated; only unrelated changes refuse, relaxable via the signed deviation (GITX-FR-014).
    covered = deviations.covered_gates(deviations.active_deviations(entries), args.spec_id)
    if deviations.GIT_CLEAN_START not in covered:
        prefix = ""
        if feature_dir is not None:
            try:
                prefix = feature_dir.relative_to(s.root).as_posix() + "/"
            except ValueError:
                prefix = ""
        unrelated = gitflow.unrelated_changes(
            gitflow.uncommitted(s.root),
            gitflow.recorded_run_paths(entries, args.spec_id),
            prefix,
        )
        if unrelated:
            print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
            return EXIT_FAIL
    b_err = gitflow.ensure_run_branch(s.root, branch, prefs.base_branch)
    if b_err:
        print(f"error: {b_err}", file=sys.stderr)
        return EXIT_FAIL
    appended: Optional[int] = None
    if not recorded_branch:
        # Bind the branch to the run — the same additive field on the existing run/start payload
        # the orchestrated path records (GITX-FR-005, GITX-NFR-002).
        try:
            sk = keys.resolve_signer(s.root)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_USAGE
        payload: dict[str, Any] = {"kind": "start", "mode": "manual", "branch": branch}
        if feature_dir is not None:
            try:
                payload["feature_dir"] = feature_dir.relative_to(s.root).as_posix()
            except ValueError:
                payload["feature_dir"] = feature_dir.as_posix()
        appended = ledger.append("run", payload, sk, spec_id=args.spec_id)["seq"]
    rows = [
        gst.status_row(
            "pass",
            f"on run branch {branch}" + (" (recorded)" if recorded_branch else " (bound)"),
            f"ledger seq={appended}" if appended is not None else "already bound in the ledger",
        )
    ]
    _print(
        {"branch": branch, "spec_id": args.spec_id, "ledger_seq": appended},
        args.json,
        _compose(args, gst, title="git start", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK


def cmd_classify(args: argparse.Namespace) -> int:
    """Infer work kind(s) + a suggested risk tier from free-form intent (3PWR-FR-058).

    Deterministic (keyword heuristics, no model call — never perturbs the verdict, 3PWR-NFR-001). The
    inference shapes the tier + oracle strategy; it never bypasses the human sign-off (3PWR-FR-006)."""
    wk = workkind.classify(args.intent)
    cst = _styler(args)
    rows = [
        cst.kv([("work kinds", ", ".join(wk.kinds) or "—"), ("suggested tier", wk.suggested_tier)])
    ]
    if wk.signals:
        rows.append(cst.status_row("info", "signals", ", ".join(wk.signals)))
    _print(
        {"kinds": wk.kinds, "suggested_tier": wk.suggested_tier, "signals": wk.signals},
        args.json,
        _compose(args, cst, title="classify", rows=rows),
    )
    return EXIT_OK


def _notify(cmd: Optional[str], message: str) -> None:
    """Best-effort notification hook: ``<cmd> "<message>"`` (3pwr run --notify). Never blocks the run."""
    if cmd:
        run_cmd(f"{cmd} {shlex.quote(message)}", cwd=Path.cwd())


def _notify_event(s: Settings, args: argparse.Namespace, event: str, message: str) -> None:
    """Fire ``event`` at the ``--notify`` hook AND every configured channel (STEER-FR-009/011).

    Best-effort and fully isolated from the trust path (STEER-NFR-001): the channels are loaded at
    most once per invocation (a malformed file warns once — STEER-FR-010), delivery never raises,
    and every problem is at most a one-line stderr warning that never carries a secret value
    (STEER-NFR-002). With no ``notifications.yaml`` and no ``--notify``, nothing happens and no
    network call is made."""
    _notify(
        args.notify, message
    )  # the existing command hook keeps working alongside (STEER-FR-011)
    channels = getattr(args, "_notify_channels", None)
    if channels is None:
        channels, warns = notify.load_channels(s.notifications_config_path)
        for w in warns:
            print(f"warning: {w}", file=sys.stderr)
        args._notify_channels = channels
    for w in notify.dispatch(channels, event, f"3pwr run {args.spec_id or 'RUN'}", message):
        print(f"warning: {w}", file=sys.stderr)


def _run_feature_dir_from_ledger(s: Settings, entries: list[dict], spec_id: str) -> Optional[Path]:
    """The run's bound feature folder, read back from the signed ``run``/``start`` entry (SRCX-FR-011).

    The latest ``start`` entry carrying a ``feature_dir`` wins — recovered offline from the ledger
    alone, no modification-time scan. ``None`` for a pre-SRCX run (legacy fallback applies)."""
    rel = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "start" and payload.get("feature_dir"):
            rel = str(payload["feature_dir"])
    return (s.root / rel) if rel else None


def _run_pending_gate(ledger: Ledger, spec_id: str) -> str:
    st = lifecycle.derive(ledger.entries()).get(spec_id)
    return st.pending_gate if st else ""


def _run_intent_from_ledger(entries: list[dict], spec_id: str) -> str:
    """The run's resolved intent, read back from the latest signed ``run``/``start`` entry.

    A revise re-dispatches the paused stage WITH the original intent (STEER-FR-006) — recovered from
    the ledger alone (STEER-FR-004's reproducibility), never re-asked."""
    intent = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "start" and payload.get("intent"):
            intent = str(payload["intent"])
    return intent


def _gate_pause_rows(rst: style.Styler, spec_id: str, artifact: str) -> list[str]:
    """The three human-gate actions, each with its copy-pasteable command, plus the artifact under
    review (STEER-FR-005) — one source for the pause screen and the interactive prompt."""
    rows = []
    if artifact:
        rows.append(f"  {rst.dim('review:'.ljust(9))}{artifact}")
    rows.extend(
        f"  {rst.dim((name + ':').ljust(9))}{rst.bold(cmd)}"
        for name, cmd in steering.gate_actions(spec_id)
    )
    return rows


def _run_signoff(
    s: Settings,
    ledger: Ledger,
    sk,
    spec_id: str,
    gate: str,
    approver: Optional[str],
    note: Optional[str],
) -> None:
    """Record the human's gate approval as a signed sign-off (3PWR-FR-006 spec / FR-037 evidence).

    The spec-approval gate additionally seals the approved document's hash into the
    signed entry (SLOCK-FR-001) — same capture as a manual `3pwr signoff --stage spec`.
    """
    stage = "Spec" if gate == "review-spec" else "Review"
    fr = orchestrate.MANDATORY_GATES.get(gate, "")
    payload = {
        "approver": approver or "human",
        "stage": stage,
        "note": note or f"approved gate '{gate}' {fr}".strip(),
    }
    if stage == "Spec":
        payload.update(_spec_approval_payload(s, None))
    ledger.append("signoff", payload, sk, spec_id=spec_id)


def _record_run_failure(
    ledger: Ledger,
    sk,
    spec_id: str,
    *,
    stage: str,
    failure_class: str,
    attempts: int,
    detail: str,
    transcript: str = "",
) -> None:
    """Append the signed run-failure record before exiting (AUTOX-FR-006).

    Stage, failure class, attempt count, and a bounded detail ride in a ``run``/``failure`` entry via
    the existing append API — additive content only, so ``3pwr verify`` stays green (AUTOX-NFR-003).
    The transcript field carries the persisted path, never the output itself (AUTOX-FR-008)."""
    payload: dict[str, Any] = {
        "kind": "failure",
        "stage": stage or "",
        "class": failure_class,
        "attempts": int(attempts),
        "detail": (detail or "")[:400],
    }
    if transcript:
        payload["transcript"] = transcript
    ledger.append("run", payload, sk, spec_id=spec_id)


def _resolve_runner_kind(args: argparse.Namespace) -> str:
    """The executive runner to use: --dry-run forces ``sim``; else --runner, defaulting to ``native``
    (EXEC-FR-013)."""
    if args.dry_run:
        return "sim"
    return getattr(args, "runner", None) or "native"


def _resolve_coder_agent(s: Settings, args: argparse.Namespace) -> str:
    """The coder agent backend: --agent wins, else --integration/roles.coder.integration (EXEC-FR-009)."""
    return getattr(args, "agent", None) or runpreflight.resolve_coder_integration(
        s, args.integration
    )


def _resolve_run_spec(
    s: Settings, args: argparse.Namespace, feature_dir: Optional[Path] = None
) -> Optional[Path]:
    """The spec the native run resolves: --spec if given, else the run's bound feature folder
    (SRCX-FR-011 — no modification-time scan), else the newest feature spec under specs/ (legacy)."""
    if getattr(args, "spec", None):
        p = Path(args.spec)
        return p if p.exists() else None
    if feature_dir is not None:
        return workspace.spec_path(feature_dir)
    specs = sorted(workspace.find_specs(s.root), key=lambda q: q.stat().st_mtime, reverse=True)
    return specs[0] if specs else None


def _native_verdict(
    s: Settings,
    args: argparse.Namespace,
    tier: str,
    kinds: list[str],
    *,
    ledger: Optional[Ledger] = None,
    sk=None,
    feature_dir: Optional[Path] = None,
) -> str:
    """Run the deterministic gate suite IN-PROCESS for the native verify stage (EXEC-FR-006).

    Returns ``pass`` / ``fail``; returns ``error`` when the gates cannot even run (no spec resolvable, no
    adapter detected, bad tier) so the caller reports a setup/dispatch problem, never a false gate-red
    (EXEC-FR-016). The engine computes the verdict itself — no subprocess dispatch, no model (3PWR-NFR-001).

    When a ledger + signer are supplied, the verdict is recorded exactly as a standalone
    ``3pwr gate run`` records it — written to ``verdicts/latest.json`` and appended as a signed
    ``verdict`` entry — so an in-run red or green is never invisible to the trust spine (AUTOX-FR-011).
    The verdict bytes themselves are unchanged (AUTOX-NFR-003)."""
    spec_path = _resolve_run_spec(s, args, feature_dir)
    if spec_path is None:
        return "error"
    try:
        adapter_name = detect_adapter(s, s.root)
        verdict = run_gates(
            s,
            s.root,
            tier=tier,
            spec_path=spec_path,
            adapter_name=adapter_name,
            work_kind=kinds,
        )
    except (KeyError, LookupError, FileNotFoundError, ValueError, OSError):
        return "error"
    if ledger is not None and sk is not None:
        s.verdicts_dir.mkdir(parents=True, exist_ok=True)
        verdict.write(s.verdicts_dir / "latest.json")
        ledger.append(
            "verdict",
            verdict.to_dict(),
            sk,
            spec_id=verdict.spec_id,
            requirement_ids=verdict.requirement_ids(),
        )
    return "pass" if verdict.result == STATUS_PASS else "fail"


def _dispatch_timeout(s: Settings, args: argparse.Namespace) -> int:
    """The per-stage dispatch timeout (RUNLIVE-FR-004): --timeout wins, else the configured default."""
    v = getattr(args, "timeout", None)
    return int(v) if v else s.dispatch_timeout()


def _dispatch_retries(s: Settings, args: argparse.Namespace) -> int:
    """The dispatch retry budget (RUNLIVE-FR-005): --retries wins, else the configured default."""
    v = getattr(args, "retries", None)
    return int(v) if v is not None else s.dispatch_retries()


def _run_stream(args: argparse.Namespace) -> bool:
    """Stream agent output live only on a real TTY and not under --json (RUNLIVE-FR-006)."""
    return bool(sys.stdout.isatty()) and not args.json


def _make_agent_runner(
    s: Settings,
    manifest: dict,
    *,
    model: str,
    intent: str,
    timeout: int,
    stream: bool,
    transcripts_sink: Optional[transcripts.TranscriptSink] = None,
    echo: Optional[TextSink] = None,
):
    """Build the backend that dispatches a role's stages: a local headless CLI (:class:`CliAgentRunner`) or,
    when the manifest declares ``mode: async-hosted``, the async hosted backend (:class:`HostedAgentRunner`,
    RUNLIVE-FR-008). Both satisfy the same ``dispatch(step, stage) -> DispatchResult`` contract, so the
    verdict is judged identically (RUNLIVE-NFR-003). The transcript sink persists each local attempt's
    output (AUTOX-FR-008); a hosted backend's output lives with its hosting service. ``echo`` routes the
    streamed agent conversation above the run's live bar instead of raw stdout (STEER-FR-012)."""
    if hosted.is_hosted(manifest):
        return hosted.HostedAgentRunner(
            s, manifest, model=model, cwd=s.root, intent=intent, timeout=timeout
        )
    return CliAgentRunner(
        s,
        manifest,
        model=model,
        cwd=s.root,
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts=transcripts_sink,
        echo_out=echo,
        echo_err=echo,
    )


def _dispatch_spec_text(s: Settings, step: str, spec_path: Optional[Path]) -> str:
    """The approved-spec text a stage's prompt reloads (PHASE-FR-005).

    Stages after the ``review-spec`` human gate (plan, tasks, oracle, implement, advance) get the
    approved specification injected, so no stage depends on the agent rediscovering the law. Stages
    before approval (specify, clarify) author/refine the spec and get none. Deterministic given the
    tree (PHASE-NFR-001)."""
    if orchestrate.step_index(step) <= orchestrate.step_index("review-spec"):
        return ""
    if spec_path is None:
        return ""
    try:
        return spec_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _prior_artifact_ref(s: Settings, step: str, result: runnermod.StageResult) -> str:
    """A reference to (digest of) an accepted stage artifact for the NEXT stage's prompt (PHASE-FR-005)."""
    if not result.artifact_paths:
        return ""
    path = result.artifact_paths[0]
    try:
        digest = hashlib.sha256((s.root / path).read_bytes()).hexdigest()[:12]
    except OSError:
        digest = ""
    tail = f" (sha256 {digest})" if digest else ""
    return f"prior stage '{step}' accepted artifact: {path}{tail} — read it before starting."


def _implement_phases(s: Settings, spec_path: Optional[Path]) -> list[phases.Phase]:
    """The ordered phases declared by the feature's tasks artifact, or ``[]`` (PHASE-FR-010).

    An empty result — no tasks artifact, or one that declares no phases — means the implement stage
    runs the whole task set as a single fresh session, preserving the pre-phase behavior as the
    degenerate case."""
    if spec_path is None:
        return []
    tasks_art = workspace.find_artifact(workspace.feature_dir_of(spec_path), "tasks")
    if tasks_art is None:
        return []
    try:
        return phases.parse_phases(tasks_art.read_text(encoding="utf-8"))
    except OSError:
        return []


def _report_phase_estimates(
    s: Settings, result: runnermod.StageResult, spec_path: Optional[Path], *, coder_model: str
) -> None:
    """Per-phase context estimates + the advisory oversize warnings after the tasks stage (PHASE-FR-008/009).

    Each phase's deterministic estimate is reported; an over-budget phase gets a warning naming the
    phase, its estimate, and the budget, advising a split — and the run proceeds. Written to stderr
    (never the --json stdout) and carried on the stage result; no gate or verdict is touched
    (PHASE-NFR-002)."""
    phase_list = _implement_phases(s, spec_path)
    if not phase_list:
        return
    budget = s.context_budget(coder_model)
    prompt_text = prompts.resolve_body("implement", s.stage_templates_dir)
    for ph in phase_list:
        est = phases.phase_estimate(
            s.root,
            ph,
            spec_path=spec_path,
            constitution_path=s.constitution_path,
            prompt_text=prompt_text,
        )
        print(
            f"  · phase {ph.index} '{ph.name}': estimated ~{est} tokens (budget {budget})",
            file=sys.stderr,
        )
        warn = phases.oversize_warning(ph, est, budget)
        if warn:
            result.warnings.append(warn)
            print(f"  ⚠ {warn}", file=sys.stderr)


def _dispatch_phased(
    s: Settings,
    step: str,
    stage: str,
    *,
    backend,
    agent_name: str,
    retries: int,
    spec_text: str,
    context: str,
    phase_list: list[phases.Phase],
    verify_artifact,
    ledger: Ledger,
    sk,
    spec_id: str,
) -> runnermod.StageResult:
    """Run the implement stage phase by phase (PHASE-FR-010/011/012).

    Each phase is a NEW headless session whose prompt reloads that phase's handoff set — the approved
    spec, the constitution/rules, the phase's tasks, the declared file scope — with no conversation
    state carried between phases (3PWR-FR-061). Phases marked parallel with disjoint declared scopes
    and no dependency are dispatched concurrently; results are recorded in deterministic artifact
    order via one ledger entry appended AFTER collection, from this thread — parallel completion never
    touches the trust spine concurrently (PHASE-NFR-003). Any phase failure fails the stage naming the
    phase(s); later phases are recorded as explicitly skipped, never as passed (PHASE-FR-012)."""
    t0 = time.monotonic()
    batches, notes = phases.schedule(phase_list)
    for note in notes:
        print(f"  · {note}", file=sys.stderr)
    try:
        constitution = s.constitution_path.read_text(encoding="utf-8")
    except OSError:
        constitution = ""
    total = len(phase_list)
    attempt_counts: list[int] = []  # list.append is atomic — safe across the batch threads

    def run_one(ph: phases.Phase) -> tuple[bool, str]:
        ctx = phases.handoff_context(ph, total, constitution_text=constitution)
        if context:
            ctx = f"{context}\n\n{ctx}"
        file_scope = "\n".join(ph.file_scope)
        res, attempts = runnermod.dispatch_with_retry(
            lambda: backend.dispatch(
                step, stage, spec_text=spec_text, context=ctx, file_scope=file_scope
            ),
            retries=retries,
        )
        attempt_counts.append(attempts)
        return res.ok, ("" if res.ok else res.detail)

    prun = phases.run_phases(batches, run_one)
    results = [r.as_dict() for r in prun.results]
    ledger.append("run", {"kind": "phases", "step": step, "results": results}, sk, spec_id=spec_id)

    def _result(
        ok: bool, outcome: str, detail: str = "", artifact: str = "", paths: list[str] | None = None
    ) -> runnermod.StageResult:
        # Per-phase transcripts share the run's sink; the stage result names its directory so a
        # phased failure still points at the persisted output (AUTOX-FR-008).
        sink = getattr(backend, "transcripts", None)
        return runnermod.StageResult(
            step=step,
            stage=stage,
            ok=ok,
            agent=agent_name,
            model=str(backend.model),
            attempts=sum(attempt_counts),
            duration_s=time.monotonic() - t0,
            artifact=artifact,
            outcome=outcome,
            detail=detail,
            transcript=sink.rel_dir if sink is not None else "",
            artifact_paths=paths or [],
            phases=results,
        )

    if not prun.ok:
        return _result(False, "dispatch_failed", detail=prun.failure_detail)
    check = verify_artifact()
    if not check.ok:
        return _result(
            False,
            "artifact_missing",
            detail=f"stage '{step}' produced no expected artifact — {check.message}",
        )
    return _result(True, "ok", artifact=check.summary, paths=list(check.matched))


def _feature_folder_context(s: Settings, feature_dir: Optional[Path]) -> str:
    """The deterministic prompt line naming the run's feature folder (SRCX-FR-001/008).

    Injected into the agent-authored markdown stages (specify/clarify/plan/tasks) so the agent writes
    the stage's artifact FLAT into the allocated folder — the same location the workspace computes and
    the completion gate asserts (SRCX-FR-013's property)."""
    if feature_dir is None:
        return ""
    try:
        rel = feature_dir.relative_to(s.root).as_posix()
    except ValueError:
        rel = feature_dir.as_posix()
    return (
        f"FEATURE FOLDER: {rel} — the run's allocated feature workspace. Write this stage's markdown "
        f"artifact FLAT into this folder (spec.md for Specify; <step>.md otherwise); create no spec/ "
        f"or artifacts/ subfolder."
    )


def _native_runner(
    s: Settings,
    args: argparse.Namespace,
    start_index: int,
    *,
    ledger: Ledger,
    sk,
    spec_id: str,
    stream: bool,
    feature_dir: Optional[Path] = None,
    run_branch: str = "",
    git_prefs: Optional[gitflow.GitPrefs] = None,
    commit_relaxed: bool = False,
    revise: str = "",
    echo: Optional[TextSink] = None,
    on_progress: Optional[Callable[[orchestrate.Event], None]] = None,
) -> NativeRunner:
    """Build the native executive runner: dispatch each stage to the role's agent (EXEC-FR-001/009), verify
    its declared artifact (RUNLIVE-FR-001/002), retry/timeout-bound the dispatch (RUNLIVE-FR-004/005),
    run the mandatory pre/post-stage git hooks — branch isolation + the agentically-messaged,
    3pwr-authored stage commit (GITX-FR-001/010/011/012, superseding RUNLIVE-FR-010's opt-out
    checkpoint) — write the oracle/implement records and run the deterministic completion gate per
    producing stage (SRCX-FR-004/005/012), and run the gate suite in-process at Verify (EXEC-FR-006)."""
    intent = args.intent or ""
    wk = workkind.classify(intent)
    tier = args.tier or wk.suggested_tier or s.default_tier()
    timeout = _dispatch_timeout(s, args)
    retries = _dispatch_retries(s, args)
    prefs = git_prefs or gitflow.GitPrefs()

    coder_agent = _resolve_coder_agent(s, args)
    oracle_agent = runpreflight.resolve_oracle_integration(s)
    coder_manifest = agents.load_agent(s, coder_agent)
    # One transcript sink per run, shared by both roles: every stage attempt's output is persisted
    # under .3powers/runs/<spec-id>/, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).
    sink = transcripts.TranscriptSink(s.root, spec_id)
    coder = _make_agent_runner(
        s,
        coder_manifest,
        model=str(s.role("coder").get("model") or ""),
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts_sink=sink,
        echo=echo,
    )
    try:
        oracle_manifest = agents.load_agent(s, oracle_agent) if oracle_agent else coder_manifest
    except FileNotFoundError:
        oracle_manifest = coder_manifest
    oracle_runner = _make_agent_runner(
        s,
        oracle_manifest,
        model=str(s.role("oracle").get("model") or ""),
        intent=intent,
        timeout=timeout,
        stream=stream,
        transcripts_sink=sink,
        echo=echo,
    )

    # The prior accepted artifact's reference — injected into the next stage's prompt so each stage
    # knows the committed context boundary it continues from (PHASE-FR-005).
    prior_box: dict[str, str] = {"ref": ""}

    def dispatch(step: str, stage: str) -> runnermod.StageResult:
        # The mandatory PRE-STAGE git hook (GITX-FR-001): every stage of a live run happens on the
        # run's dedicated branch — strayed mid-run (e.g. the user switched away), it switches back
        # before dispatching; a switch git refuses is a named failure, never forced (GITX-NFR-003).
        if run_branch:
            b_err = gitflow.ensure_run_branch(s.root, run_branch, prefs.base_branch)
            if b_err:
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    outcome=gitflow.CLASS_BRANCH_FAILED,
                    detail=b_err,
                )
        # The oracle role (Phase A) runs under its own agent/model — a different family than the coder
        # (3PWR-FR-022). Physical read-path isolation stays with `3pwr oracle dispatch`, which a
        # High-risk `advance` enforces (3PWR-FR-021); the run routes the oracle stage to its backend here.
        backend = oracle_runner if step == "oracle" else coder
        agent_name = oracle_agent if step == "oracle" else coder_agent
        contract = artifacts.contract_for(step)
        pre = runnermod.worktree_state(s.root)
        produced_box: dict[str, list[str]] = {}

        def verify() -> artifacts.ArtifactCheck:
            post = runnermod.worktree_state(s.root)
            produced = runnermod.produced_paths(pre, post)
            produced_box["paths"] = produced
            # A None contract verifies leniently (RUNLIVE-FR-003), so this always runs.
            check = artifacts.verify(contract, produced)
            if not check.ok:
                # A completion-gate re-run (SRCX-FR-017) may regenerate a committed artifact
                # byte-identical to HEAD — an empty diff. The stage still satisfies its contract
                # when every artifact its PRIOR run/stage entry recorded is still on disk; the
                # completion gate then re-asserts disk ∧ ledger. A fresh stage has no prior entry,
                # so nothing is weakened for a first run (3PWR-FR-032).
                prior = completion.recorded_stage_artifacts(ledger.entries(), spec_id).get(step)
                if prior and all((s.root / p).is_file() for p in prior):
                    return artifacts.ArtifactCheck(
                        ok=True, expected=check.expected, matched=list(prior), produced=produced
                    )
            return check

        # Assemble the stage's context: the approved spec text (post-approval stages), the run's
        # feature folder (the agent-authored markdown stages — SRCX-FR-001), and the prior stage's
        # accepted artifact reference — no stage rediscovers its inputs (PHASE-FR-005).
        spec_path = _resolve_run_spec(s, args, feature_dir)
        spec_text = _dispatch_spec_text(s, step, spec_path)
        ctx_parts = []
        if step in ("specify", "clarify", "plan", "tasks"):
            ctx_parts.append(_feature_folder_context(s, feature_dir))
        ctx_parts.append(prior_box["ref"])
        if revise:
            # The revise re-dispatch carries the human's gate feedback + the artifact under review
            # (STEER-FR-006) — assembled deterministically upstream (STEER-NFR-003).
            ctx_parts.append(revise)
        context = "\n".join(p for p in ctx_parts if p)

        phase_list = _implement_phases(s, spec_path) if step == "implement" else []
        if phase_list:
            # A phased tasks artifact: one fresh session per phase, parallel where the declared
            # scopes are disjoint (PHASE-FR-010/011); a phaseless artifact stays a single dispatch.
            result = _dispatch_phased(
                s,
                step,
                stage,
                backend=backend,
                agent_name=agent_name,
                retries=retries,
                spec_text=spec_text,
                context=context,
                phase_list=phase_list,
                verify_artifact=verify,
                ledger=ledger,
                sk=sk,
                spec_id=spec_id,
            )
        else:
            result = runnermod.run_stage(
                step,
                stage,
                attempt=lambda: backend.dispatch(step, stage, spec_text=spec_text, context=context),
                retries=retries,
                verify_artifact=verify,
                agent=agent_name,
                model=str(backend.model),
            )
        if result.ok:
            if step in completion.RECORD_STEPS and feature_dir is not None:
                # The oracle/implement stages leave a markdown *record* in the feature folder linking
                # their real outputs at their real repo paths (SRCX-FR-004/005). For a phased
                # implement this runs on the collecting thread AFTER all phases completed, one record
                # in deterministic order (SRCX-FR-006, SRCX-NFR-006).
                scopes = {ph.index: ph.file_scope for ph in phase_list}
                if step == "implement":
                    # the record links the full produced change set (SRCX-FR-005's property)
                    linked = produced_box.get("paths") or result.artifact_paths
                else:
                    linked = result.artifact_paths  # the contract-matched oracle test paths
                rel = completion.write_record(
                    s.root,
                    feature_dir,
                    step,
                    spec_id=spec_id,
                    linked=linked,
                    phases=result.phases or None,
                    phase_scopes=scopes,
                )
                if rel not in result.artifact_paths:
                    result.artifact_paths.append(rel)
                if rel not in produced_box.get("paths", []):
                    produced_box.setdefault("paths", []).append(rel)
            ref = _prior_artifact_ref(s, step, result)
            if ref:
                prior_box["ref"] = ref
            if step == "tasks":
                # Report each phase's deterministic context estimate; warn (never block) on an
                # over-budget phase (PHASE-FR-008/009).
                _report_phase_estimates(s, result, spec_path, coder_model=str(coder.model))
            # Record the completion itself — lightweight, additive (AUTOX-FR-010, extends
            # RUNLIVE-FR-010): resume progress lives in the signed ledger, not only in checkpoint
            # commits, so a failed `--no-auto-commit` run still resumes from the next stage.
            stage_payload: dict[str, Any] = {"kind": "stage", "step": step, "stage": stage}
            if result.artifact_paths:
                stage_payload["artifacts"] = result.artifact_paths
            ledger.append("run", stage_payload, sk, spec_id=spec_id)
        if result.ok and run_branch and not commit_relaxed:
            # The mandatory POST-STAGE git hook (GITX-FR-001/010, superseding RUNLIVE-FR-010's
            # opt-out checkpoint): the stage's produced paths land as exactly ONE commit on the run
            # branch — never a blanket `add -A` — with an agent-written message carrying the stage
            # and spec id (deterministic fallback — GITX-FR-011) and the 3pwr author applied
            # per-commit (GITX-FR-012, GITX-NFR-004). A stage that produced nothing forces no empty
            # commit; paths a human already committed by hand are a no-op keeping the human's own
            # author. After it, no run-produced change is left uncommitted (GITX-FR-008).
            produced = produced_box.get("paths", [])
            desc = gitflow.agent_commit_description(s.root, result.transcript)
            commit = gitflow.commit_stage(
                s.root,
                produced,
                message=gitflow.stage_commit_message(spec_id, step, desc),
                author_name=prefs.author_name,
                author_email=prefs.author_email,
            )
            if commit.error:
                # Clean-stop would be violated (GITX-FR-008) — a named, recorded failure on the
                # setup/dispatch path, never silently carried on.
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    agent=agent_name,
                    model=str(backend.model),
                    attempts=result.attempts,
                    duration_s=result.duration_s,
                    outcome=gitflow.CLASS_COMMIT_FAILED,
                    detail=f"stage '{step}' could not be committed — {commit.error}",
                    transcript=result.transcript,
                )
            if commit.sha:
                payload: dict[str, Any] = {
                    "kind": "checkpoint",
                    "step": step,
                    "stage": stage,
                    "commit": commit.sha,
                }
                if result.artifact_paths:
                    # The accepted artifact's path rides in the signed stage entry, so the committed
                    # artifact trail is reconstructable from the ledger alone (PHASE-FR-003).
                    payload["artifacts"] = result.artifact_paths
                ledger.append("run", payload, sk, spec_id=spec_id)
        if result.ok and feature_dir is not None and completion.is_producing(step):
            # The deterministic completion gate (SRCX-FR-012): the stage's declared markdown must
            # exist on disk AND be recorded in a matching signed ledger entry before the run may
            # advance — else the run blocks with a named, classified failure and the stage must be
            # re-run (SRCX-FR-014/015). Pure given (disk state, ledger entries, step); one ledger
            # read serves the check (SRCX-NFR-001/004).
            recorded = completion.recorded_stage_artifacts(ledger.entries(), spec_id)
            chk = completion.check_step(s.root, feature_dir, step, recorded)
            if not chk.ok:
                return runnermod.StageResult(
                    step=step,
                    stage=stage,
                    ok=False,
                    agent=agent_name,
                    model=str(backend.model),
                    attempts=result.attempts,
                    duration_s=result.duration_s,
                    outcome=chk.failure_class,
                    detail=chk.message,
                    transcript=result.transcript,
                )
        return result

    def run_verdict(stage: str) -> str:
        # The in-run verdict is recorded exactly as a standalone `3pwr gate run` records it
        # (AUTOX-FR-011): a red or green at Verify is never invisible to the trust spine.
        return _native_verdict(
            s, args, tier, wk.kinds, ledger=ledger, sk=sk, feature_dir=feature_dir
        )

    return NativeRunner(
        dispatch=dispatch, run_verdict=run_verdict, start_index=start_index, on_progress=on_progress
    )


def _run_make_runner(
    s: Settings,
    args: argparse.Namespace,
    mode: str,
    *,
    start_index: int,
    ledger: Ledger,
    sk,
    spec_id: str,
    stream: bool,
    feature_dir: Optional[Path] = None,
    run_branch: str = "",
    git_prefs: Optional[gitflow.GitPrefs] = None,
    commit_relaxed: bool = False,
    revise: str = "",
    echo: Optional[TextSink] = None,
    on_progress: Optional[Callable[[orchestrate.Event], None]] = None,
):
    kind = _resolve_runner_kind(args)
    if kind == "sim":
        return orchestrate.SimulatedRunner(
            verdict=("fail" if args.simulate_fail else "pass"), start_index=start_index
        )
    return _native_runner(
        s,
        args,
        start_index,
        ledger=ledger,
        sk=sk,
        spec_id=spec_id,
        stream=stream,
        feature_dir=feature_dir,
        run_branch=run_branch,
        git_prefs=git_prefs,
        commit_relaxed=commit_relaxed,
        revise=revise,
        echo=echo,
        on_progress=on_progress,
    )


def _run_revise(
    s: Settings,
    args: argparse.Namespace,
    ledger: Ledger,
    sk,
    spec_id: str,
    gate: str,
    feedback: str,
    *,
    feature_dir: Optional[Path],
    run_branch: str,
    git_prefs: Optional[gitflow.GitPrefs],
    commit_relaxed: bool,
    rst: style.Styler,
) -> int:
    """Revise-with-message at a paused human gate (STEER-FR-006..008).

    Re-dispatches the stage that owns the artifact under review — with the ORIGINAL intent (read back
    from the signed ``start`` entry), the current artifact, and the human's feedback — records the
    revision (feedback + outcome) via the existing run-entry append path, and returns the run to the
    SAME gate for review: the pause is re-recorded so approval still requires the human sign-off. The
    revise dispatch runs under the very same retry/artifact/git/completion policy as a first run."""
    step, stage = steering.revise_target(gate)
    if not step:
        print(f"error: gate '{gate}' has no revisable stage", file=sys.stderr)
        return EXIT_USAGE
    gate_stage = next(
        (stg for sid, _kind, stg in orchestrate.LIFECYCLE_STEPS if sid == gate), stage
    )
    artifact = steering.gate_artifact(s.root, feature_dir, gate)
    if _resolve_runner_kind(args) == "sim":
        # --dry-run / the simulator dispatch nothing (the SRCX dry-run stance) — the revise is
        # recorded and the gate re-presented, so the whole loop stays visible offline.
        result = runnermod.StageResult(
            step=step, stage=stage, ok=True, outcome="ok", detail="simulated (dry-run)"
        )
    else:
        args.intent = _run_intent_from_ledger(ledger.entries(), spec_id)  # STEER-FR-006
        runner = _native_runner(
            s,
            args,
            0,
            ledger=ledger,
            sk=sk,
            spec_id=spec_id,
            stream=_run_stream(args),
            feature_dir=feature_dir,
            run_branch=run_branch,
            git_prefs=git_prefs,
            commit_relaxed=commit_relaxed,
            revise=steering.revise_context(gate, artifact, feedback),
        )
        try:
            result = runner.dispatch_once(step, stage)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_SETUP
    # The revision is auditable from the ledger alone (STEER-FR-008): feedback + outcome ride the
    # EXISTING run-entry append path — no new entry type, no signing change, `3pwr verify` unchanged.
    ledger.append(
        "run",
        {
            "kind": "revise",
            "gate": gate,
            "step": step,
            "feedback": feedback,
            "ok": result.ok,
            "outcome": result.outcome or ("ok" if result.ok else "failed"),
            "detail": (result.detail or "")[:400],
        },
        sk,
        spec_id=spec_id,
    )
    # The run returns to the SAME gate (STEER-FR-006): re-record the pause so the ledger-derived
    # state stays paused-at-gate and a later plain --resume still records the human sign-off.
    ledger.append("run", {"kind": "gate", "gate": gate, "stage": gate_stage}, sk, spec_id=spec_id)
    if not result.ok:
        detail = f" — {result.detail}" if result.detail else ""
        _notify_event(
            s,
            args,
            notify.EVENT_FAILURE,
            notify.failure_message(spec_id, "revise failed", gate_stage),
        )
        human = (
            f"{orchestrate.render_tracker(gate_stage, rst)}\n"
            f"  {rst.err('✗')} revise failed at '{step}'{detail}\n"
            f"  the artifact under review is unchanged; the run remains paused at '{gate}'."
        )
        _print(
            {
                "status": "revise_failed",
                "gate": gate,
                "step": step,
                "detail": result.detail,
                "spec_id": spec_id,
                "stages": [result.as_dict()],
            },
            args.json,
            human,
        )
        return EXIT_SETUP
    _notify_event(
        s,
        args,
        notify.EVENT_GATE,
        "revised — "
        + notify.gate_message(
            spec_id,
            gate,
            gate_stage,
            orchestrate.MANDATORY_GATES.get(gate, ""),
            artifact,
            steering.gate_actions(spec_id),
        ),
    )
    action_rows = "\n".join(_gate_pause_rows(rst, spec_id, artifact))
    human = (
        f"{orchestrate.render_tracker(gate_stage, rst)}\n"
        f"  {rst.ok('✓')} revised '{step}' with your feedback — back at "
        f"{rst.warn('HUMAN GATE')} '{gate}' for review:\n{action_rows}"
    )
    _print(
        {
            "status": "paused_at_gate",
            "gate": gate,
            "gate_fr": orchestrate.MANDATORY_GATES.get(gate, ""),
            "stage": gate_stage,
            "spec_id": spec_id,
            "revised": step,
            "stages": [result.as_dict()],
        },
        args.json,
        human,
    )
    return EXIT_PAUSED


def _gate_decision(gate: str, fr: str) -> str:
    """The three-action interactive choice at a paused human gate (STEER-FR-005): approve / revise /
    reject — the same vocabulary the non-interactive pause prints as commands.

    Empty input and EOF mean reject — the conservative default: nothing advances without an explicit
    approval (3PWR-FR-006). An unrecognized answer re-prompts."""
    aliases = {
        "a": "approve",
        "approve": "approve",
        "y": "approve",
        "yes": "approve",
        "r": "revise",
        "revise": "revise",
        "x": "reject",
        "reject": "reject",
        "n": "reject",
        "no": "reject",
    }
    while True:
        try:
            raw = (
                input(f"  gate '{gate}'{fr} — [a]pprove / [r]evise / reject [x]? ").strip().lower()
            )
        except EOFError:
            return "reject"
        if not raw:
            return "reject"
        decision = aliases.get(raw)
        if decision:
            return decision
        print("  answer a (approve), r (revise), or x (reject)")


def _prompt_line(prompt: str) -> str:
    """One line of interactive input; EOF reads as empty (never raises at a gate pause)."""
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def cmd_run(args: argparse.Namespace) -> int:
    """Drive the whole lifecycle loop (3PWR-FR-011; §6). ``auto`` stops only at the two mandatory human
    gates (FR-006 spec approval, FR-037 sign-off); ``commit`` stops at every gate. By default the
    **native** executive dispatches each stage to a headless agent directly (EXEC-FR-001) and runs the
    gate suite in-process at Verify (EXEC-FR-006); ``--runner sim`` uses the offline simulator (also
    forced by ``--dry-run``). The engine makes no model call itself (EXEC-NFR-001) and never enters the
    deterministic verdict (3PWR-NFR-001)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    mode = args.mode or s.default_mode()  # --mode wins; else the `3pwr init` default (ONBRD-FR-005)
    spec_id = args.spec_id or "RUN"
    rst = _styler(
        args
    )  # human-output styler (color per --json/--yes/NO_COLOR/ui.yaml) — CLIUX-FR-005

    if args.status:
        st = lifecycle.derive(ledger.entries()).get(spec_id)
        if st is None:
            _print(
                {"spec_id": spec_id, "found": False},
                args.json,
                _compose(
                    args,
                    rst,
                    title="3pwr run · status",
                    subject=spec_id,
                    rows=[rst.status_row("info", f"no run recorded for {spec_id}")],
                ),
            )
            return EXIT_OK
        rows = [f"  {orchestrate.render_tracker(st.stage, rst)}"]
        if st.pending_gate:
            rows.append(
                rst.status_row(
                    "warn",
                    f"paused at '{st.pending_gate}'",
                    f"`3pwr run --resume --spec-id {spec_id} --approver <you>`",
                )
            )
        if st.failed:
            # A recorded, unresolved run failure — distinct from paused and in-progress (AUTOX-FR-007).
            rows.append(
                rst.status_row(
                    "fail",
                    f"failed at {st.failed_stage or '?'} ({st.failed_class}) at {st.failed_at or '?'}",
                    f"`3pwr run --resume --spec-id {spec_id}`",
                )
            )
            if st.failed_transcript:
                rows.append("      " + rst.dim(f"agent transcript: {st.failed_transcript}"))
        # The run's git lifecycle state (GITX-FR-009): its dedicated branch and the per-stage
        # committed indication — a deterministic function of the ledger and the local branches,
        # no model and no network (GITX-NFR-001).
        entries_st = ledger.entries()
        run_branch_st = gitflow.branch_from_ledger(entries_st, spec_id)
        committed_st = gitflow.committed_steps(entries_st, spec_id)
        if run_branch_st:
            on_it = gitflow.current_branch(s.root) == run_branch_st
            rows.append(
                rst.status_row(
                    "info",
                    f"run branch {run_branch_st}" + (" (checked out)" if on_it else ""),
                    f"committed stages: {', '.join(committed_st) or '—'}",
                )
            )
        _print(
            {
                "spec_id": spec_id,
                "stage": st.stage,
                "pending_gate": st.pending_gate,
                "failed": st.failed,
                "failed_stage": st.failed_stage,
                "failed_class": st.failed_class,
                "failed_at": st.failed_at,
                "failed_transcript": st.failed_transcript,
                "branch": run_branch_st,
                "committed_steps": committed_st,
            },
            args.json,
            _compose(args, rst, title="3pwr run · status", subject=spec_id, rows=rows),
        )
        return EXIT_OK

    # File-based intent (STEER-FR-001..003): resolve --file (+ the optional inline instruction)
    # BEFORE any side effect — a bad file fails fast with the setup exit code and no ledger entry
    # is written; every downstream consumer sees ONLY the resolved intent (STEER-FR-004).
    if getattr(args, "file", None):
        if args.resume:
            print(
                "error: --file feeds a fresh run's intent — to revise at a paused gate use "
                "--revise/--revise-file",
                file=sys.stderr,
            )
            return EXIT_USAGE
        resolved_intent, ierr = steering.resolve_intent(args.file, args.intent)
        if ierr:
            print(f"error: {ierr}", file=sys.stderr)
            return EXIT_SETUP
        args.intent = resolved_intent

    # Resolve the coder + oracle agents from config/flags — provider-agnostic (EXEC-NFR-003).
    coder_int = _resolve_coder_agent(s, args)
    oracle_int = runpreflight.resolve_oracle_integration(s)
    coder_model = str(s.role("coder").get("model") or "")
    oracle_model = str(s.role("oracle").get("model") or "")

    # Preflight — a live run must not dispatch a stage until its prerequisites hold (EXEC-FR-015):
    # a resolvable signer, a headless coder agent, and a different-family oracle agent — the SAME
    # shared check set init's readiness and `3pwr ready` report (AUTOX-FR-002), so they cannot
    # disagree. --dry-run needs none of this: it dispatches nothing and is always available offline
    # (EXEC-FR-016).
    if not args.dry_run and not args.status:
        prqs = runpreflight.check_auto(
            s,
            coder_agent=coder_int,
            oracle_agent=oracle_int,
            entries=ledger.entries(),
            spec_id=spec_id,
        )
        missing = runpreflight.unmet(prqs)
        if missing:
            # Fail fast, BEFORE any dispatch, with a named prerequisite + fix and the offline
            # alternatives — never "gates red", never the incident path (RUNX-FR-010/012, NFR-004).
            # Exits with the setup/dispatch code, distinct from usage and gates-red (AUTOX-FR-009).
            obj = {
                "status": "preflight_failed",
                "spec_id": spec_id,
                "missing": [{"prerequisite": p.name, "fix": p.fix} for p in missing],
                "alternatives": list(runpreflight.OFFLINE_ALTERNATIVES),
            }
            if args.json:
                print(json.dumps(obj, indent=2))
            else:
                est = _styler(args, sys.stderr)
                lines = [
                    est.err("✗ cannot start `3pwr run` — unmet prerequisites")
                    + " (no stage was dispatched):"
                ]
                for p in missing:
                    lines.append(f"  {est.mark('fail')} {est.bold(p.name)}: {p.fix}")
                lines.append("  always available offline:")
                for alt in runpreflight.OFFLINE_ALTERNATIVES:
                    lines.append(f"    • {alt}")
                print("\n".join(lines), file=sys.stderr)
            return EXIT_SETUP

    # The signer itself (a live run just verified it in preflight; --dry-run still needs one to
    # append its ledger records).
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_SETUP

    interactive = (not args.json) and (not args.no_input) and sys.stdin.isatty()
    stream = _run_stream(args)  # stream agent output live on a TTY (RUNLIVE-FR-006)
    tracker = orchestrate.Tracker(sys.stdout, mode, st=rst, subject=spec_id)

    # The git discipline (GITX): applied to every LIVE native run — mandatory, with the recorded
    # signed deviation as the only relaxation (GITX-FR-014). --dry-run / the simulator dispatch
    # nothing and write nothing, so the git hooks are a no-op there (the SRCX dry-run stance).
    git_on = _resolve_runner_kind(args) == "native"
    git_prefs = gitflow.load_prefs(s.git_config_path)
    if git_on and git_prefs.malformed and not args.json:
        print(
            "warning: .3powers/config/git.yaml is malformed — using the default git preferences",
            file=sys.stderr,
        )
    covered_guards = deviations.covered_gates(
        deviations.active_deviations(ledger.entries()), spec_id
    )
    clean_start_relaxed = deviations.GIT_CLEAN_START in covered_guards
    commit_relaxed = deviations.GIT_STAGE_COMMIT in covered_guards
    if git_on and (getattr(args, "no_auto_commit", False) or not s.auto_commit()):
        # The plain opt-out is SUPERSEDED (GITX-FR-014): the stage commit is mandatory; the only
        # relaxation is the signed `git_stage_commit` deviation — warned, never silent.
        if not commit_relaxed and not args.json:
            print(
                "warning: --no-auto-commit / defaults.auto_commit is superseded (GITX-FR-014) — "
                "the per-stage commit is mandatory; relax it on the record with "
                '`3pwr deviation --gate git_stage_commit --approver <you> --note "<why>"`',
                file=sys.stderr,
            )
    run_branch = ""

    def on_event(ev: orchestrate.Event) -> None:
        if not args.json:
            tracker.on_event(ev)

    def _record_dispatch(start_index: int) -> None:
        """Record one signed executive-dispatch provenance entry per stage in the next live segment
        (RUNX-FR-007/NFR-002); the oracle stage carries the oracle integration/model. No-op for --dry-run
        (it dispatches nothing) so the offline simulation records nothing (RUNX-FR-012). Keyed on the actual
        start index, so a resume that skipped committed checkpoints records only the stages it will
        dispatch (RUNLIVE-FR-010)."""
        if args.dry_run:
            return
        for step, _stage in orchestrate.segment_actions_from(start_index):
            is_oracle = step == "oracle"
            ledger.append(
                "run",
                runpreflight.provenance_payload(
                    step,
                    oracle_int if is_oracle else coder_int,
                    oracle_model if is_oracle else coder_model,
                ),
                sk,
                spec_id=spec_id,
            )

    def _make_runner(start_index: int):
        return _run_make_runner(
            s,
            args,
            mode,
            start_index=start_index,
            ledger=ledger,
            sk=sk,
            spec_id=spec_id,
            stream=stream,
            feature_dir=feature_dir,
            run_branch=run_branch,
            git_prefs=git_prefs,
            commit_relaxed=commit_relaxed,
            # The streamed agent conversation prints ABOVE the live bar, into ordinary scrollback
            # (STEER-FR-012); with no bar (off-TTY/degraded) the echo stays the process's stdout.
            echo=(tracker.echo_sink() if (stream and tracker.live) else None),
            # Live event delivery (STEER-FR-013): the bar learns a stage is running the moment its
            # dispatch starts, not one whole segment later; on_event self-guards under --json.
            on_progress=on_event,
        )

    def _stages() -> list[dict]:
        """The per-stage machine-readable results of the dispatched stages, for --json (RUNLIVE-FR-006)."""
        return [sr.as_dict() for sr in getattr(runner, "stage_results", [])]

    # The run's bound feature folder (SRCX-FR-008/010/011) — resolved per branch below.
    feature_dir: Optional[Path] = None

    if args.resume:
        revising = bool(
            getattr(args, "revise", None) is not None or getattr(args, "revise_file", None)
        )
        pending = _run_pending_gate(ledger, spec_id)
        completed = orchestrate.last_completed_step(ledger.entries(), spec_id)
        feedback = ""
        if revising:
            # The third gate action (STEER-FR-006/007): a revise outside a paused gate, or with
            # empty feedback, is an actionable error leaving the artifact and gate state unchanged.
            if not pending:
                st_now = lifecycle.derive(ledger.entries()).get(spec_id)
                where = f"stage {st_now.stage}" if st_now else "no recorded run"
                print(
                    f"error: nothing to revise — {spec_id} is not paused at a human gate "
                    f"(current state: {where})",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            feedback, ferr = steering.resolve_feedback(
                getattr(args, "revise_file", None), getattr(args, "revise", None)
            )
            if ferr:
                print(f"error: {ferr}", file=sys.stderr)
                return EXIT_USAGE
        if not pending and not completed:
            # No recorded progress at all — say so honestly and name the fresh start (AUTOX-FR-010).
            print(
                f"nothing to resume for {spec_id} — no recorded progress; start fresh: "
                f'3pwr run "<intent>" --spec-id {spec_id}',
                file=sys.stderr,
            )
            return EXIT_USAGE
        if pending and not revising:
            # A human gate was awaiting approval — record the sign-off before continuing (FR-006/037).
            _run_signoff(s, ledger, sk, spec_id, pending, args.approver, args.note)
        # A resume resolves the EXISTING feature folder recorded for the run — never allocating a new
        # one (SRCX-FR-010/011); a pre-SRCX run falls back to the resolvable spec's folder.
        entries_now = (
            ledger.entries()
        )  # one read serves resume + the completion checks (SRCX-NFR-004)
        feature_dir = _run_feature_dir_from_ledger(s, entries_now, spec_id)
        if feature_dir is None:
            legacy_spec = _resolve_run_spec(s, args)
            feature_dir = workspace.feature_dir_of(legacy_spec) if legacy_spec else None
        if git_on:
            # The pre-stage git hook on resume (GITX-FR-004/005/007): recover the run's branch from
            # the signed ledger alone (a pre-GITX run derives the same deterministic name from its
            # SRCX identity), refuse a dirty start whose changes the run did not produce, and
            # re-enter the EXISTING branch — never a new one, never a new run number.
            run_branch = gitflow.branch_from_ledger(entries_now, spec_id)
            if not run_branch:
                identity = (
                    feature_dir.name if feature_dir is not None else workspace.slugify(spec_id)
                )
                run_branch = gitflow.run_branch_name(git_prefs.branch_prefix, identity)
            if not clean_start_relaxed:
                prefix = ""
                if feature_dir is not None:
                    try:
                        prefix = feature_dir.relative_to(s.root).as_posix() + "/"
                    except ValueError:
                        prefix = ""
                unrelated = gitflow.unrelated_changes(
                    gitflow.uncommitted(s.root),
                    gitflow.recorded_run_paths(entries_now, spec_id),
                    prefix,
                )
                if unrelated:
                    print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
                    return EXIT_SETUP
            b_err = gitflow.ensure_run_branch(s.root, run_branch, git_prefs.base_branch)
            if b_err:
                print(b_err, file=sys.stderr)
                return EXIT_SETUP
        if revising:
            # Re-dispatch the paused stage with the original intent, the current artifact, and the
            # feedback, then return to the SAME gate (STEER-FR-006..008).
            return _run_revise(
                s,
                args,
                ledger,
                sk,
                spec_id,
                pending,
                feedback,
                feature_dir=feature_dir,
                run_branch=run_branch,
                git_prefs=git_prefs,
                commit_relaxed=commit_relaxed,
                rst=rst,
            )
        # Re-enter after the later of the approved gate and the last committed checkpoint, so a mid-run
        # failure resumes from the next uncompleted stage without re-dispatching a committed one (FR-010)
        # — then intersect with the on-disk completion check (SRCX-FR-017): a recorded stage whose
        # artifact is broken becomes the re-entry point, never skipped on its ledger entry alone.
        start_index = orchestrate.resume_start_index(entries_now, spec_id, pending)
        start_index, broken = completion.resume_entry_index(
            entries_now, spec_id, start_index, root=s.root, feature_dir=feature_dir
        )
        if broken is not None and not args.json:
            print(f"  ⟲ resume re-enters at '{broken.step}' — {broken.message}", file=sys.stderr)
        runner = _make_runner(start_index)
        _record_dispatch(start_index)  # provenance for the resumed segment only (RUNX-FR-004/007)
    else:
        wk = workkind.classify(
            args.intent or ""
        )  # FR-058: shape the tier + oracle, not the sign-off
        if git_on and not clean_start_relaxed:
            # The pre-stage git hook's clean-start guard (GITX-FR-007), BEFORE any side effect: a
            # fresh run owns no paths yet, so any uncommitted change outside the engine's own state
            # blocks — naming the paths and the signed deviation, never discarding them
            # (GITX-NFR-003).
            unrelated = gitflow.unrelated_changes(gitflow.uncommitted(s.root), set())
            if unrelated:
                print(gitflow.clean_start_refusal(unrelated), file=sys.stderr)
                return EXIT_SETUP
        # Bind the run's feature folder (SRCX-FR-008/011): an explicit --spec names it; otherwise a
        # LIVE run auto-allocates specs/<NNN>-<slug>/ deterministically from the intent. --dry-run and
        # the simulator dispatch nothing and write no artifacts, so they allocate nothing.
        if getattr(args, "spec", None):
            spec_arg = Path(args.spec)
            feature_dir = workspace.feature_dir_of(spec_arg) if spec_arg.exists() else None
        elif _resolve_runner_kind(args) != "sim":
            try:
                feature_dir = workspace.allocate_feature_dir(s.root, args.intent or "")
            except FileExistsError:
                target = workspace.feature_folder_name(s.root / "specs", args.intent or "")
                print(
                    f"cannot start `3pwr run` — the feature folder specs/{target} is already "
                    f"allocated (another run?); no folder is ever overwritten (SRCX-FR-008)",
                    file=sys.stderr,
                )
                return EXIT_SETUP
        if git_on:
            # Create + switch to the run's dedicated branch off the configured base BEFORE any
            # stage commit (GITX-FR-003/006): the branch name reuses SRCX's <NNN>-<slug> identity
            # — GITX allocates no number and derives no slug — and the run never commits on the
            # base branch. Detached HEAD / unborn repo: created off the current commit.
            identity = feature_dir.name if feature_dir is not None else workspace.slugify(spec_id)
            run_branch = gitflow.run_branch_name(git_prefs.branch_prefix, identity)
            b_err = gitflow.ensure_run_branch(s.root, run_branch, git_prefs.base_branch)
            if b_err:
                print(b_err, file=sys.stderr)
                return EXIT_SETUP
        start_payload: dict[str, Any] = {
            "kind": "start",
            "intent": args.intent or "",
            "mode": mode,
            "integration": args.integration,
            "inferred_kinds": wk.kinds,
            "suggested_tier": wk.suggested_tier,
        }
        if run_branch:
            # The additive branch binding on the existing run/start payload (GITX-FR-005): a later
            # resume recovers the branch from the signed ledger alone — no branch scan, no
            # guessing; no new entry type and no signing change (GITX-NFR-002).
            start_payload["branch"] = run_branch
        if feature_dir is not None:
            # The additive folder binding on the existing run/start payload (SRCX-FR-011): a later
            # resume reads it back from the signed ledger alone — no mtime scan (SRCX-NFR-002).
            try:
                start_payload["feature_dir"] = feature_dir.relative_to(s.root).as_posix()
            except ValueError:
                start_payload["feature_dir"] = feature_dir.as_posix()
        ledger.append("run", start_payload, sk, spec_id=spec_id)
        if not args.json and _verbosity(args) != "quiet":
            print(rst.header(f"3pwr run · {mode} mode", spec_id))
            print(
                rst.kv(
                    [
                        ("intent", args.intent or "—"),
                        ("work kinds", ", ".join(wk.kinds) or "—"),
                        ("suggested tier", wk.suggested_tier),
                    ]
                )
            )
            print("  " + rst.dim("you still approve the spec — FR-006"))
        runner = _make_runner(0)
        _record_dispatch(0)  # provenance for the first segment (up to the spec-approval gate)
    first_resuming = False  # start_index already positions native/sim runners; resume==run for both

    try:
        if not args.json:
            # The live bar is on screen BEFORE the first dispatch produces any output, so the run
            # shows its heartbeat from the first moment (STEER-FR-012/013). No-op off-TTY/degraded.
            tracker.begin()
        result = orchestrate.drive(runner, mode, on_event, resuming=first_resuming)
        while result.status == "paused_at_gate":
            ledger.append(
                "run",
                {"kind": "gate", "gate": result.gate, "stage": result.stage},
                sk,
                spec_id=spec_id,
            )
            gate_artifact = steering.gate_artifact(s.root, feature_dir, result.gate)
            _notify_event(
                s,
                args,
                notify.EVENT_GATE,
                notify.gate_message(
                    spec_id,
                    result.gate,
                    result.stage,
                    result.gate_fr,
                    gate_artifact,
                    steering.gate_actions(spec_id),
                ),
            )
            if not interactive:
                fr = f" ({result.gate_fr})" if result.gate_fr else ""
                action_rows = "\n".join(_gate_pause_rows(rst, spec_id, gate_artifact))
                human = (
                    f"{orchestrate.render_tracker(result.stage, rst)}\n"
                    f"  {rst.warn('⏸ HUMAN GATE')} '{result.gate}'{fr}"
                    f" — review, then choose (STEER-FR-005):\n{action_rows}"
                )
                _print(
                    {
                        "status": "paused_at_gate",
                        "gate": result.gate,
                        "gate_fr": result.gate_fr,
                        "stage": result.stage,
                        "spec_id": spec_id,
                        "stages": _stages(),
                    },
                    args.json,
                    human,
                )
                # Paused-at-gate is distinguishable from completed by exit code alone (AUTOX-FR-009).
                return EXIT_PAUSED
            fr = f" ({result.gate_fr})" if result.gate_fr else ""
            for line in _gate_pause_rows(rst, spec_id, gate_artifact):
                print(
                    line
                )  # the three actions, on-screen at the interactive pause too (STEER-FR-005)
            while True:
                decision = _gate_decision(result.gate, fr)
                if decision != "revise":
                    break
                # Revise-with-message, inline (STEER-FR-005/006): take the feedback here, re-run the
                # paused stage with it, and come back to the SAME gate for a fresh decision.
                feedback = _prompt_line("  feedback for the revision (required): ")
                if not feedback:
                    print("  revise needs feedback — nothing was changed")
                    continue
                rc_rev = _run_revise(
                    s,
                    args,
                    ledger,
                    sk,
                    spec_id,
                    result.gate,
                    feedback,
                    feature_dir=feature_dir,
                    run_branch=run_branch,
                    git_prefs=git_prefs,
                    commit_relaxed=commit_relaxed,
                    rst=rst,
                )
                if rc_rev != EXIT_PAUSED:
                    return rc_rev  # the revise failed with its own actionable report
            if decision == "reject":
                reason = _prompt_line("  reason (optional): ")
                payload: dict[str, Any] = {"kind": "complete", "stage": result.stage}
                if reason:
                    payload["reason"] = reason
                ledger.append("run", payload, sk, spec_id=spec_id)
                why = f" — {reason}" if reason else ""
                _print(
                    {
                        "status": "rejected",
                        "gate": result.gate,
                        "spec_id": spec_id,
                        **({"reason": reason} if reason else {}),
                    },
                    args.json,
                    f"  ⊘ gate '{result.gate}' rejected — run stopped{why}",
                )
                return EXIT_FAIL
            _run_signoff(s, ledger, sk, spec_id, result.gate, args.approver, args.note)
            _record_dispatch(
                orchestrate.resume_start_index(ledger.entries(), spec_id, result.gate)
            )  # provenance for the next segment (no re-record — RUNX-FR-004, RUNLIVE-FR-010)
            if not args.json:
                # The gate pause finalized the bar; the approved run's next segment gets it back on
                # screen immediately (STEER-FR-012/013).
                tracker.begin()
            result = orchestrate.drive(runner, mode, on_event, resuming=True)
    except FileNotFoundError as exc:  # a role's agent manifest is missing on the live path
        print(str(exc), file=sys.stderr)
        return EXIT_SETUP
    finally:
        # The live bar never outlives the run — its last state left as ordinary lines, cursor
        # restored, on normal exit, interruption, and failure alike (STEER-FR-016, STEER-NFR-004).
        # Idempotent: a bar already finalized by a terminal event is a no-op here.
        tracker.close()

    if result.status == "failed":
        # Every terminal failure is recorded as a signed run-failure ledger entry BEFORE exiting
        # (AUTOX-FR-006), so `--status`/`3pwr status` can say "failed at <stage> (<class>)"
        # afterwards (AUTOX-FR-007). Attempts come from the failing stage's dispatch result.
        failed_srs = [sr for sr in getattr(runner, "stage_results", []) if not sr.ok]
        attempts = failed_srs[-1].attempts if failed_srs else 1
        transcript = failed_srs[-1].transcript if failed_srs else ""

        def record(cls: str) -> None:
            _record_run_failure(
                ledger,
                sk,
                spec_id,
                stage=result.stage,
                failure_class=cls,
                attempts=attempts,
                detail=result.detail or result.verdict,
                transcript=transcript,
            )

        transcript_line = f"\n  agent transcript: {transcript}" if transcript else ""
        if result.is_gate_red:
            # A real deterministic-gate verdict failed at Verify (RUNX-FR-011): report gate-red,
            # show Verify reached. No incident/observe-signal suggestion — that is not the remedy.
            record("gates_red")
            reached = result.stage or "Verify"
            _notify_event(
                s, args, notify.EVENT_FAILURE, notify.failure_message(spec_id, "gates red", reached)
            )
            human = (
                f"{orchestrate.render_tracker(reached, rst)}\n"
                f"  {rst.err('✗')} gates red — the deterministic gate suite failed. Inspect with "
                "`3pwr gate run --spec <spec> --tier <tier>`, fix the failing gate(s), then "
                f"`3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {"status": "gates_red", "stage": reached, "spec_id": spec_id, "stages": _stages()},
                args.json,
                human,
            )
            return EXIT_FAIL
        reached = result.stage or "an early stage"
        if result.outcome == "verdict_error":
            # The gate suite could not even run (no spec resolvable, no adapter, bad tier) — a
            # setup problem, never a false gate-red (EXEC-FR-016).
            record("verdict_error")
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "verdict error", reached),
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} verdict error at {reached} — the deterministic gate suite could not run "
                "(not a gate verdict). Check the spec resolves (--spec), an adapter is detected, "
                f"and the tier exists, then resume: `3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": "verdict_error",
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.is_artifact_missing:
            # A stage produced no declared artifact (RUNLIVE-FR-002): distinct from a gate-red and from a
            # bare dispatch failure — name the stage and the expected artifact; committed checkpoints let a
            # resume pick up here without re-running completed stages (RUNLIVE-FR-010).
            record("artifact_missing")
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "artifact missing", reached),
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} artifact missing at {reached} — {result.detail}\n"
                "  the stage's agent ran but did not produce what the stage is responsible for "
                f"(not a gate verdict). Re-run or resume: `3pwr run --resume --spec-id {spec_id}`."
                f"{transcript_line}"
            )
            _print(
                {
                    "status": "artifact_missing",
                    "stage": result.stage,
                    "detail": result.detail,
                    "transcript": transcript,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.outcome in (gitflow.CLASS_COMMIT_FAILED, gitflow.CLASS_BRANCH_FAILED):
            # The mandatory git hook could not hold its guarantee (GITX-FR-001/008/010): the stage
            # commit failed, or the run branch could not be created/switched (never forced —
            # GITX-NFR-003). Named, recorded, and exiting on the setup/dispatch path — never a
            # gate verdict.
            record(result.outcome)
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "git discipline failed", reached),
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} git discipline failed at {reached} — {result.detail}\n"
                "  the run isolates its work on a dedicated branch and commits every producing "
                f"stage (GITX). Fix the repository state, then resume: "
                f"`3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": result.outcome,
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        if result.outcome in (completion.CLASS_ABSENT, completion.CLASS_UNRECORDED):
            # The deterministic stage-completion gate blocked the run (SRCX-FR-012/014/015): the
            # stage's declared markdown and its matching signed ledger entry must BOTH exist. The
            # named class is recorded (SRCX-FR-016) and surfaced by both status commands; the stage
            # must be re-run — the non-gate-red setup/dispatch exit path.
            record(result.outcome)
            _notify_event(
                s,
                args,
                notify.EVENT_FAILURE,
                notify.failure_message(spec_id, "stage completion failed", reached),
            )
            human = (
                f"{orchestrate.render_tracker(result.stage, rst)}\n"
                f"  {rst.err('✗')} stage completion failed at {reached} — {result.detail}\n"
                "  a stage is complete only when its artifact is on disk AND recorded in the signed "
                f"ledger (not a gate verdict). Re-run the stage: `3pwr run --resume --spec-id {spec_id}`."
            )
            _print(
                {
                    "status": result.outcome,
                    "stage": result.stage,
                    "detail": result.detail,
                    "spec_id": spec_id,
                    "stages": _stages(),
                },
                args.json,
                human,
            )
            return EXIT_SETUP
        # A dispatch/execution failure — NOT a gate verdict (RUNX-FR-010): name the stage, never say
        # "gates red", never route to the incident/observe-signal path; exit with the setup/dispatch code.
        record("dispatch_failed")
        _notify_event(
            s,
            args,
            notify.EVENT_FAILURE,
            notify.failure_message(spec_id, "dispatch failed", reached),
        )
        detail = f" — {result.detail}" if result.detail else ""
        human = (
            f"{orchestrate.render_tracker(result.stage, rst)}\n"
            f"  {rst.err('✗')} dispatch failed at {reached} — a stage could not be executed (a setup/dispatch "
            f"problem, not a gate verdict){detail}.\n"
            "  confirm the coder integration is headless and available (`3pwr run` reports "
            f"prerequisites), then re-run — or resume: `3pwr run --resume --spec-id {spec_id}`."
            f"{transcript_line}"
        )
        _print(
            {
                "status": "dispatch_failed",
                "stage": result.stage,
                "detail": result.detail,
                "transcript": transcript,
                "spec_id": spec_id,
                "stages": _stages(),
            },
            args.json,
            human,
        )
        return EXIT_SETUP
    if result.status == "aborted":
        _notify_event(s, args, notify.EVENT_FAILURE, f"3pwr run {spec_id}: aborted")
        _print(
            {"status": "aborted", "spec_id": spec_id, "stages": _stages()},
            args.json,
            f"  {rst.dim('⊘')} run aborted",
        )
        return EXIT_FAIL

    ledger.append("run", {"kind": "complete", "stage": "Ship"}, sk, spec_id=spec_id)
    _notify_event(s, args, notify.EVENT_COMPLETION, notify.completion_message(spec_id))
    human = (
        f"{orchestrate.render_tracker('Observe', rst)}\n"
        f"  {rst.ok('✓ lifecycle complete')} — advanced to Ship; observe feeds new intent"
    )
    _print({"status": "done", "spec_id": spec_id, "stages": _stages()}, args.json, human)
    return EXIT_OK


def cmd_revert(args: argparse.Namespace) -> int:
    """Reverse to a prior recorded state via a signed reversal entry (3PWR-FR-070)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    target = next((e for e in entries if e["seq"] == args.to), None)
    if target is None:
        print(f"error: no ledger entry with seq={args.to}", file=sys.stderr)
        return EXIT_USAGE
    spec_id = target.get("spec_id") or ""
    state_at = lifecycle.derive([e for e in entries if e["seq"] <= args.to])
    to_stage = state_at[spec_id].stage if spec_id in state_at else lifecycle.STAGES[1]
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = ledger.append(
        "reversal",
        {"to_seq": args.to, "to_stage": to_stage, "reason": args.reason or ""},
        sk,
        spec_id=spec_id,
    )
    rvt = _styler(args)
    _print(
        {"reverted_to_seq": args.to, "to_stage": to_stage, "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            rvt,
            title="revert",
            subject=spec_id or "(global)",
            rows=[
                rvt.status_row(
                    "pass",
                    f"reverted {spec_id or '(global)'} to stage '{to_stage}' (state @seq={args.to})",
                    f"ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_abort(args: argparse.Namespace) -> int:
    """Record an abort for a spec's run (3PWR-FR-019)."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = Ledger(s.ledger_path).append(
        "abort", {"reason": args.reason or ""}, sk, spec_id=args.spec_id
    )
    abt = _styler(args)
    print(
        _compose(
            args,
            abt,
            title="abort",
            subject=args.spec_id,
            rows=[
                abt.status_row("warn", f"aborted '{args.spec_id}'", f"ledger seq={entry['seq']}")
            ],
        )
    )
    return EXIT_OK


def cmd_coverage_check(args: argparse.Namespace) -> int:
    """Two-way requirement<->task coverage before code (3PWR-FR-015)."""
    from .conformance import two_way_coverage

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    gate = two_way_coverage(spec_path, Path(args.tasks).resolve())
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"coverage-map {gate.status.upper()}",
            gate.details.get("spec_id", "?"),
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(
            args, cst, title="coverage-check", subject=gate.details.get("spec_id", ""), rows=rows
        ),
    )
    return EXIT_OK if passed else EXIT_FAIL


def cmd_scope_check(args: argparse.Namespace) -> int:
    """Task requirement-ID + file-scope discipline (3PWR-FR-016/017)."""
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else None
    gate = scope.scope_check(Path(args.tasks).resolve(), s.root, base=args.base, target=target)
    sct = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [sct.status_row("pass" if passed else "fail", f"scope-check {gate.status.upper()}")]
    if gate.findings:
        rows.append(sct.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(args, sct, title="scope-check", rows=rows),
    )
    return EXIT_OK if passed else EXIT_FAIL


def cmd_provenance(args: argparse.Namespace) -> int:
    """Sign build provenance + SBOM for an artifact (3PWR-FR-066/068)."""
    s = _settings(args.root)
    artifact = Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"error: artifact not found: {artifact}", file=sys.stderr)
        return EXIT_USAGE
    target = Path(args.path).resolve() if args.path else s.root
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    signed = provenance.sign_record(provenance.build_record(s.root, target, artifact), sk)
    pdir = s.dir / "provenance"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"{signed['artifact']['sha256'].split(':')[1]}.json").write_text(
        json.dumps(signed, indent=2) + "\n", encoding="utf-8"
    )
    entry = Ledger(s.ledger_path).append(
        "provenance",
        {"artifact": signed["artifact"], "source_commit": signed["source_commit"]},
        sk,
        spec_id=args.spec_id or "",
    )
    pst = _styler(args)
    _print(
        {"artifact": signed["artifact"], "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            pst,
            title="provenance",
            subject=artifact.name,
            rows=[
                pst.status_row(
                    "pass",
                    f"provenance signed for {artifact.name} ({signed['artifact']['sha256']})",
                    f"{len(signed['sbom']['components'])} SBOM components; ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_deploy_gate(args: argparse.Namespace) -> int:
    """Verify an artifact's provenance; refuse if missing or invalid (3PWR-FR-067)."""
    s = _settings(args.root)
    artifact = Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"error: artifact not found: {artifact}", file=sys.stderr)
        return EXIT_USAGE
    digest = provenance.sha256_file(artifact)
    pfile = s.dir / "provenance" / f"{digest.split(':')[1]}.json"
    reasons: list[str] = []
    if not pfile.exists():
        reasons.append("no provenance record for this artifact hash")
    else:
        record = json.loads(pfile.read_text(encoding="utf-8"))
        if record.get("artifact", {}).get("sha256") != digest:
            reasons.append("artifact hash does not match provenance")
        if not s.pubkey_path.exists():
            reasons.append("public key not found")
        elif not provenance.verify_record(record, keys.load_public(s.pubkey_path)):
            reasons.append("provenance signature invalid")
    dgt = _styler(args)
    if reasons:
        rows = [dgt.status_row("fail", f"DEPLOY REFUSED for {artifact.name}")]
        rows += [dgt.status_row("fail", r, indent=4) for r in reasons]
        _print(
            {"deployable": False, "reasons": reasons},
            args.json,
            _compose(args, dgt, title="deploy-gate", subject=artifact.name, rows=rows),
        )
        return EXIT_FAIL
    _print(
        {"deployable": True, "artifact": digest},
        args.json,
        _compose(
            args,
            dgt,
            title="deploy-gate",
            subject=artifact.name,
            rows=[
                dgt.status_row(
                    "pass", f"deploy-gate PASS — provenance verified for {artifact.name}"
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_residual(args: argparse.Namespace) -> int:
    """Record a signed residual review (3PWR-FR-036/037)."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"reviewer": args.reviewer, "note": args.note or "", "findings": args.findings or []}
    entry = Ledger(s.ledger_path).append("residual", payload, sk, spec_id=args.spec_id or "")
    rst = _styler(args)
    print(
        _compose(
            args,
            rst,
            title="residual",
            subject=args.spec_id or "",
            rows=[
                rst.status_row(
                    "pass",
                    f"residual review recorded by {args.reviewer}",
                    f"ledger seq={entry['seq']}",
                )
            ],
        )
    )
    return EXIT_OK


def cmd_characterize(args: argparse.Namespace) -> int:
    """Reconstruct a spec + characterization tests for a legacy module (3PWR-FR-053)."""
    from . import characterize

    # Brownfield Stage Zero runs *before* a repo has adopted 3Powers, so a `.3powers/`
    # trust spine may not exist yet — fall back to --root or cwd rather than requiring it.
    base = Path(args.root).resolve() if args.root else None
    try:
        root = config.find_root(base)
    except FileNotFoundError:
        root = base or Path.cwd()
    module_path = Path(args.module).resolve()
    specs_dir = Path(args.specs).resolve() if args.specs else root / "specs"
    # A directory walk defaults each file's tests alongside it; an explicit --tests pins them all.
    tests_dir = Path(args.tests).resolve() if args.tests else None
    try:
        results = characterize.characterize_path(
            root, module_path, specs_dir=specs_dir, tests_dir=tests_dir
        )
    except (FileNotFoundError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    cst = _styler(args)
    rows = []
    for res in results:
        try:
            rel = str(res.spec_path.parent.relative_to(root)) if root else res.spec_id
        except ValueError:
            rel = res.spec_id
        rows.append(
            cst.status_row(
                "pass",
                f"characterized → spec {res.spec_id} ({rel})",
                f"{len(res.symbols)} symbol(s), {len(res.requirement_ids)} requirement(s)",
            )
        )
    if len(results) > 1:
        rows.insert(0, cst.status_row("info", f"characterized {len(results)} source file(s)"))
    _print(
        {
            "count": len(results),
            "results": [
                {
                    "spec_id": r.spec_id,
                    "spec_path": str(r.spec_path),
                    "test_path": str(r.test_path),
                    "symbols": r.symbols,
                    "requirement_ids": r.requirement_ids,
                }
                for r in results
            ],
        },
        args.json,
        _compose(
            args,
            cst,
            title="characterize",
            subject=module_path.name,
            rows=rows,
        ),
    )
    return EXIT_OK


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the prompt/constitution eval set; block on regression (3PWR-FR-050)."""
    from .evals import run_evals

    s = _settings(args.root)
    cases = Path(args.cases).resolve() if args.cases else (s.dir / "eval" / "cases.yaml")
    gate = run_evals(s.root, cases)
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"eval {gate.status.upper()}",
            f"{gate.details.get('passed')}/{gate.details.get('cases')} cases",
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(args, cst, title="eval", rows=rows),
    )
    return EXIT_OK if passed else EXIT_FAIL


def cmd_deps_check(args: argparse.Namespace) -> int:
    """Probe installed third-party versions against the supported ranges (3PWR-FR-048/NFR-014).

    A preflight command, not a verdict gate — installed versions are environment-dependent, so
    keeping them out of the verdict preserves determinism (3PWR-NFR-001)."""
    s = _settings(args.root)
    manifest_path = (
        Path(args.manifest).resolve() if args.manifest else s.dir / "config" / "dependencies.yaml"
    )
    if not manifest_path.exists():
        print(f"error: no dependencies manifest at {manifest_path}", file=sys.stderr)
        return EXIT_USAGE
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    report = deps.check_dependencies(manifest, probe=lambda cmd: deps.run_probe(cmd, s.root))

    dst = _styler(args)
    strict_block = bool(args.strict and report.drifted)
    ok = report.ok and not strict_block
    table_rows = []
    for c in report.checks:
        state = (
            "pass"
            if c.status == deps.OK
            else (
                "info" if c.status == deps.UNKNOWN else ("fail" if c.policy == "block" else "warn")
            )
        )
        note = "" if c.status == deps.OK else f"{c.status} [{c.policy}]"
        table_rows.append(
            [dst.mark(state), c.name, c.installed or "—", c.supported or "(any)", note]
        )
    rows = [dst.table(table_rows, headers=["", "dependency", "installed", "supported", "status"])]
    if not ok:
        rows.append(
            dst.status_row(
                "fail", "deps-check FAILED: a blocking dependency is out of range or absent"
            )
        )
    _print(
        {
            "ok": ok,
            "checks": [
                {
                    "name": c.name,
                    "installed": c.installed,
                    "supported": c.supported,
                    "status": c.status,
                    "policy": c.policy,
                }
                for c in report.checks
            ],
        },
        args.json,
        _compose(args, dst, title="deps-check", subject=str(manifest_path), rows=rows),
    )
    return EXIT_OK if ok else EXIT_FAIL


def cmd_ready(args: argparse.Namespace) -> int:
    """Standalone, re-runnable auto-run readiness (AUTOX-FR-003): the full ``3pwr run --mode auto``
    preflight — the SAME shared check set init and the run itself use (AUTOX-FR-002) — plus a
    dependency summary (3PWR-FR-048), with one overall ready/not-ready verdict and a per-item fix.

    Read-only and fully offline (AUTOX-NFR-001): it probes config, PATH, and the key custody chain,
    changes nothing on disk, and is never a gate. Exits 0 when ready, 1 when not."""
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    coder_int = runpreflight.resolve_coder_integration(s, getattr(args, "integration", None))
    oracle_int = runpreflight.resolve_oracle_integration(s)
    prqs = runpreflight.check_auto(
        s,
        coder_agent=coder_int,
        oracle_agent=oracle_int,
        entries=entries,
        spec_id=getattr(args, "spec_id", None),
    )
    missing = runpreflight.unmet(prqs)

    # Dependency summary (3PWR-FR-048) — informational; never flips the readiness verdict (never a gate).
    deps_summary: Optional[dict[str, Any]] = None
    manifest_path = s.dir / "config" / "dependencies.yaml"
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        report = deps.check_dependencies(manifest, probe=lambda cmd: deps.run_probe(cmd, s.root))
        deps_summary = {
            "ok": report.ok,
            "total": len(report.checks),
            "drifted_or_missing": [
                {"name": c.name, "status": c.status, "policy": c.policy} for c in report.drifted
            ],
        }

    obj = {
        "ready": not missing,
        "checks": [
            {"prerequisite": p.name, "ok": p.ok, "label": p.label, "fix": p.fix} for p in prqs
        ],
        "deps": deps_summary,
    }
    rst = _styler(args)
    rows = []
    if missing:
        rows.append(
            rst.status_row("fail", "not ready for `3pwr run --mode auto` — remaining steps:")
        )
    else:
        rows.append(rst.status_row("pass", "ready for `3pwr run --mode auto`"))
    for p in prqs:
        rows.append(
            rst.status_row(
                "pass" if p.ok else "fail", rst.bold(p.name), p.label if p.ok else p.fix, indent=4
            )
        )
    if missing:
        rows.append("  " + rst.dim("always available offline:"))
        rows.append(rst.bullet(runpreflight.OFFLINE_ALTERNATIVES, indent=4))
    if deps_summary is not None:
        drift = deps_summary["drifted_or_missing"]
        if drift:
            named = ", ".join(f"{d['name']} ({d['status']})" for d in drift)
            rows.append(
                rst.status_row("warn", f"dependency summary: {named}", "details: 3pwr deps-check")
            )
        else:
            rows.append(
                rst.status_row(
                    "pass", f"dependency summary: {deps_summary['total']} component(s) within range"
                )
            )
    _print(
        obj,
        getattr(args, "json", False),
        _compose(args, rst, title="ready", subject="auto-run preflight", rows=rows),
    )
    return EXIT_OK if not missing else EXIT_FAIL


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="3pwr", description="3Powers judiciary engine.")
    p.add_argument("--version", action="version", version=f"3pwr {__version__}")
    p.add_argument("--root", help="repository root (defaults to discovery from cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        v = sp.add_mutually_exclusive_group()
        v.add_argument(
            "--quiet", action="store_true", help="terser human output — result and failures only"
        )
        v.add_argument(
            "--verbose", action="store_true", help="richer human output — extra per-step detail"
        )
        return sp

    kp = common(sub.add_parser("keygen", help="create the independent signer identity"))
    kp.add_argument("--out", help="private key path (default: outside the repo)")
    kp.add_argument("--force", action="store_true")
    kp.add_argument(
        "--role",
        choices=["ledger", "oracle"],
        default="ledger",
        help="which signer to mint: the primary ledger key or a distinct judiciary oracle key",
    )
    kp.set_defaults(func=cmd_keygen)

    rk = common(
        sub.add_parser("rotate-key", help="rotate the signer: the outgoing key signs its successor")
    )
    rk.add_argument("--out", help="new private key path (default: outside the repo)")
    rk.add_argument("--reason", help="why the key is being rotated (recorded in the ledger)")
    rk.set_defaults(func=cmd_rotate_key)

    ip = common(
        sub.add_parser(
            "init", help="guided onboarding: make a new or existing project 3Powers-ready"
        )
    )
    ip.add_argument(
        "--yes",
        action="store_true",
        help="non-interactive: prompt for nothing and apply the documented defaults",
    )
    ip.add_argument(
        "--language",
        help="language adapter to set up (default: auto-detected, else the first supported)",
    )
    ip.add_argument(
        "--key-path", dest="key_path", help="signing-key location (must be OUTSIDE the repo)"
    )
    ip.add_argument(
        "--auto-mode",
        dest="auto_mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="make autonomous mode the recorded default (advisory; never bypasses a human gate)",
    )
    ip.add_argument(
        "--force", action="store_true", help="overwrite an existing signing key (default: keep it)"
    )
    ip.add_argument(
        "--skeleton-only",
        dest="skeleton_only",
        action="store_true",
        help="only create the .3powers/ layout (the pre-wizard behaviour)",
    )
    ip.add_argument(
        "--integration",
        help="default agent backend to record for the coder/oracle roles (e.g. claude, codex, "
        "copilot); the native executive dispatches this headless agent directly",
    )
    ip.add_argument(
        "--tier",
        help="default risk tier a new spec starts at (advisory; never weakens a gate — INITX-FR-001)",
    )
    ip.add_argument(
        "--oracle-model",
        dest="oracle_model",
        help="judiciary oracle model as <family>/<model>, pinned into /3pwr.oracle (INITX-FR-002/004)",
    )
    ip.add_argument(
        "--oracle-integration",
        dest="oracle_integration",
        help="agent backend for the judiciary model (e.g. copilot); default: --integration or copilot",
    )
    ip.add_argument(
        "--oracle-label",
        dest="oracle_label",
        help="friendly label written into the agent frontmatter (default: the model id)",
    )
    ip.set_defaults(func=cmd_init)

    csp = common(
        sub.add_parser(
            "commit-stage",
            help="auto-commit after a successful lifecycle stage (INITX-FR-006)",
        )
    )
    csp.add_argument("--stage", required=True, help="the lifecycle stage just completed")
    csp.add_argument(
        "--spec-id", dest="spec_id", help="the governing spec id (recorded in the message)"
    )
    csp.add_argument(
        "--paths",
        nargs="*",
        help="stage only these paths before committing (default: commit what is already staged)",
    )
    csp.set_defaults(func=cmd_commit_stage)

    gp = sub.add_parser("gate", help="gate engine")
    gsub = gp.add_subparsers(dest="gate_cmd", required=True)
    gr = common(gsub.add_parser("run", help="run the gate suite and emit a verdict"))
    gr.add_argument("--path", help="target project path (default: repo root)")
    gr.add_argument("--tier", default="Standard", help="risk tier (default: Standard)")
    gr.add_argument("--adapter", help="language adapter (default: auto-detect)")
    gr.add_argument("--spec", help="path to the governing spec.md")
    gr.add_argument("--base", help="git ref for diff-coverage base")
    gr.add_argument("--mutation", action="store_true", help="run the mutation gate")
    gr.add_argument(
        "--paths",
        nargs="*",
        help="scope diff-coverage + mutation to these files",
    )
    gr.add_argument(
        "--report-only",
        action="store_true",
        help="emit the verdict but do not block (for adopting 3Powers in an existing repo)",
    )
    gr.add_argument(
        "--diff-scope",
        action="store_true",
        help="block only on files changed vs --base (for adopting 3Powers in an existing repo)",
    )
    gr.add_argument(
        "--work-kind",
        action="append",
        choices=list(workkind.KINDS),
        help="shape the gate set for an inferred kind (repeatable): defect adds a regression gate, "
        "design adds the design oracles; never weakens a tier gate",
    )
    gr.add_argument("--no-ledger", action="store_true", help="do not append to the ledger")
    gr.set_defaults(func=cmd_gate_run)

    cp = common(sub.add_parser("conformance", help="spec-conformance trace only"))
    cp.add_argument("--spec", help="path to the governing spec.md")
    cp.add_argument("--tests", nargs="*", help="test roots to scan")
    cp.set_defaults(func=cmd_conformance)

    vp = common(sub.add_parser("verify", help="verify the ledger (offline)"))
    vp.add_argument(
        "--anchored",
        action="store_true",
        help="also cross-check the chain against the latest local anchor tag (HARDN-FR-005)",
    )
    vp.set_defaults(func=cmd_verify)

    anp = common(
        sub.add_parser("anchor", help="record the ledger head with an external witness (opt-in)")
    )
    anp.add_argument(
        "--push", action="store_true", help="push the anchor tag to the remote (network)"
    )
    anp.add_argument("--remote", default="origin", help="git remote for --push (default: origin)")
    anp.set_defaults(func=cmd_anchor)

    sp = common(sub.add_parser("signoff", help="record a signed human sign-off"))
    sp.add_argument("--approver", required=True, help="approver identity (a person)")
    sp.add_argument("--stage", default="review")
    sp.add_argument("--note")
    sp.add_argument("--spec-id", dest="spec_id")
    sp.add_argument(
        "--spec",
        help="path to the approved spec.md — its hash is sealed into a Spec-stage sign-off "
        "(default: the newest spec under specs/)",
    )
    sp.set_defaults(func=cmd_signoff)

    ap = common(sub.add_parser("advance", help="enforce gate+ledger+sign-off before advancing"))
    ap.add_argument("--stage", required=True)
    ap.add_argument("--spec-id", dest="spec_id")
    ap.set_defaults(func=cmd_advance)

    dvp = common(
        sub.add_parser("deviation", help="record/revoke a signed, reversible gate exception")
    )
    dvp.add_argument(
        "--gate",
        action="append",
        help="gate or requirement to relax (repeatable), e.g. a gate name or `model_diversity`; "
        "required unless --revoke",
    )
    dvp.add_argument("--approver", help="human who accepts the deviation (required to record)")
    dvp.add_argument("--note", help="recorded reason")
    dvp.add_argument("--until", help="auto-expiry, ISO-8601 (the way back); else use --revoke")
    dvp.add_argument("--revoke", type=int, help="revoke the deviation at this ledger seq")
    dvp.add_argument("--spec-id", dest="spec_id", help="scope to a spec (default: global)")
    dvp.set_defaults(func=cmd_deviation)

    emp = common(sub.add_parser("emergency", help="open the constrained emergency fast path"))
    emp.add_argument("--approver", help="human who opens the emergency path")
    emp.add_argument("--note", help="recorded reason")
    emp.add_argument("--cleanup-hours", dest="cleanup_hours", type=int, help="cleanup window (24)")
    emp.add_argument("--spec-id", dest="spec_id")
    emp.set_defaults(func=cmd_emergency)

    stp = common(sub.add_parser("status", help="per-spec lifecycle stage from the ledger"))
    stp.add_argument("--spec-id", dest="spec_id")
    stp.set_defaults(func=cmd_status)

    gitp = sub.add_parser("git", help="git run discipline: establish the run branch (GITX)")
    gitsub = gitp.add_subparsers(dest="git_cmd", required=True)
    gits = common(
        gitsub.add_parser(
            "start",
            help="establish + bind the run's dedicated branch for a manual drive "
            "(clean-start guarded — GITX-FR-016)",
        )
    )
    gits.add_argument("--spec-id", dest="spec_id", required=True)
    gits.add_argument(
        "--feature",
        help="the run's feature folder (specs/<NNN>-<slug>); default: the ledger's recorded binding",
    )
    gits.set_defaults(func=cmd_git_start)

    clp = common(
        sub.add_parser(
            "classify", help="infer the kind(s) of change + a suggested risk tier from your intent"
        )
    )
    clp.add_argument("intent", help="the free-form intent to classify")
    clp.set_defaults(func=cmd_classify)

    rnp = common(sub.add_parser("run", help="drive the full lifecycle loop (auto/commit modes)"))
    rnp.add_argument(
        "intent", nargs="?", help="the human's one-paragraph intent (omit with --resume/--status)"
    )
    rnp.add_argument(
        "--file",
        default=None,
        help="read the run's intent from a text file (markdown preferred); inline intent text is "
        "appended to it as an instruction (STEER-FR-001/002)",
    )
    rnp.add_argument(
        "--mode",
        choices=["auto", "commit"],
        default=None,
        help="auto = stop only at the two human gates (spec approval, sign-off); commit = stop at "
        "every gate (default: the value recorded by `3pwr init`, else auto)",
    )
    rnp.add_argument(
        "--integration",
        default="auto",
        help="the coder agent backend (a manifest in .3powers/agents/); the oracle should use a "
        "different model family",
    )
    rnp.add_argument(
        "--runner",
        choices=["native", "sim"],
        default=None,
        help="executive runner: native (default; drive headless agents directly, EXEC-FR-001) or "
        "sim (offline). --dry-run forces sim.",
    )
    rnp.add_argument(
        "--agent",
        default=None,
        help="override the coder agent backend for this run (e.g. claude, codex, copilot)",
    )
    rnp.add_argument(
        "--spec",
        default=None,
        help="spec.md the native verify stage gates against (default: the newest under specs/)",
    )
    rnp.add_argument(
        "--tier",
        default=None,
        help="risk tier for the native verify stage (default: the inferred/suggested tier)",
    )
    rnp.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="per-stage dispatch timeout in seconds (RUNLIVE-FR-004; default: configured, 1800)",
    )
    rnp.add_argument(
        "--retries",
        type=int,
        default=None,
        help="retries for a failed dispatch before the stage is reported failed "
        "(RUNLIVE-FR-005; default: configured, 1)",
    )
    rnp.add_argument(
        "--no-auto-commit",
        dest="no_auto_commit",
        action="store_true",
        help="SUPERSEDED (GITX-FR-014): the per-stage commit is mandatory; this flag only warns. "
        "Relax on the record: `3pwr deviation --gate git_stage_commit`",
    )
    rnp.add_argument("--spec-id", dest="spec_id", help="run id (default: RUN)")
    rnp.add_argument(
        "--notify", help='command fired on gate/failure/completion: `<cmd> "<message>"`'
    )
    rnp.add_argument(
        "--resume",
        action="store_true",
        help="continue after a human gate (records the sign-off first)",
    )
    rnp.add_argument(
        "--revise",
        default=None,
        help="with --resume, at a paused human gate: re-run the paused stage with this feedback "
        "and return to the same gate (STEER-FR-006)",
    )
    rnp.add_argument(
        "--revise-file",
        dest="revise_file",
        default=None,
        help="read the revise feedback from a text file (same resolution rule as --file)",
    )
    rnp.add_argument(
        "--status", action="store_true", help="show the run's stage tracker from the ledger"
    )
    rnp.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="simulate the loop offline (no live agents)",
    )
    rnp.add_argument(
        "--simulate-fail",
        dest="simulate_fail",
        action="store_true",
        help="(dry-run) simulate a red gate verdict",
    )
    rnp.add_argument(
        "--no-input",
        dest="no_input",
        action="store_true",
        help="never prompt; stop at gates and print the resume command",
    )
    rnp.add_argument("--approver", help="human approver recorded at gate sign-offs")
    rnp.add_argument("--note", help="note recorded with the gate sign-off")
    rnp.set_defaults(func=cmd_run)

    rvp = common(sub.add_parser("revert", help="reverse to a prior recorded state (signed)"))
    rvp.add_argument("--to", type=int, required=True, help="ledger seq to revert to")
    rvp.add_argument("--reason")
    rvp.set_defaults(func=cmd_revert)

    abp = common(sub.add_parser("abort", help="record an abort for a spec's run"))
    abp.add_argument("--spec-id", dest="spec_id", required=True)
    abp.add_argument("--reason")
    abp.set_defaults(func=cmd_abort)

    ccp = common(sub.add_parser("coverage-check", help="two-way requirement<->task coverage"))
    ccp.add_argument("--spec", help="path to the governing spec.md")
    ccp.add_argument("--tasks", required=True, help="path to tasks.md")
    ccp.set_defaults(func=cmd_coverage_check)

    scp = common(sub.add_parser("scope-check", help="task req-id + file-scope discipline"))
    scp.add_argument("--tasks", required=True, help="path to tasks.md")
    scp.add_argument("--base", help="git ref for the changed-file base")
    scp.add_argument("--path", help="restrict the changed-file scan to this dir")
    scp.set_defaults(func=cmd_scope_check)

    pvp = common(sub.add_parser("provenance", help="sign build provenance + SBOM for an artifact"))
    pvp.add_argument("--artifact", required=True)
    pvp.add_argument("--path", help="project dir for the SBOM (default: repo root)")
    pvp.add_argument("--spec-id", dest="spec_id")
    pvp.set_defaults(func=cmd_provenance)

    dgp = common(
        sub.add_parser("deploy-gate", help="verify an artifact's provenance; refuse if bad")
    )
    dgp.add_argument("--artifact", required=True)
    dgp.set_defaults(func=cmd_deploy_gate)

    rsp = common(sub.add_parser("residual", help="record a signed residual review"))
    rsp.add_argument("--reviewer", required=True)
    rsp.add_argument("--note")
    rsp.add_argument("--findings", nargs="*")
    rsp.add_argument("--spec-id", dest="spec_id")
    rsp.set_defaults(func=cmd_residual)

    chp = common(
        sub.add_parser("characterize", help="reconstruct a spec + pin a legacy module's behavior")
    )
    chp.add_argument(
        "--module",
        required=True,
        help="a legacy source file (e.g. src/foo.py) or a directory to walk and characterize",
    )
    chp.add_argument("--specs", help="specs/ directory (default: <root>/specs)")
    chp.add_argument("--tests", help="tests output dir (default: alongside the module)")
    chp.set_defaults(func=cmd_characterize)

    evp = common(sub.add_parser("eval", help="run the prompt/constitution eval set"))
    evp.add_argument("--cases", help="eval cases.yaml (default: .3powers/eval/cases.yaml)")
    evp.set_defaults(func=cmd_eval)

    dcp = common(
        sub.add_parser(
            "deps-check", help="check installed third-party versions vs supported ranges"
        )
    )
    dcp.add_argument(
        "--manifest", help="dependencies.yaml (default: .3powers/config/dependencies.yaml)"
    )
    dcp.add_argument("--strict", action="store_true", help="treat warn-policy drift as blocking")
    dcp.set_defaults(func=cmd_deps_check)

    rdy = common(
        sub.add_parser(
            "ready",
            help="am I ready for `3pwr run --mode auto`? — the full run preflight + a dependency "
            "summary; read-only, offline, never a gate (AUTOX-FR-003)",
        )
    )
    rdy.add_argument(
        "--integration",
        default=None,
        help="check against this coder agent backend instead of roles.coder.integration",
    )
    rdy.add_argument(
        "--spec-id",
        dest="spec_id",
        help="consider deviations recorded for this spec id (e.g. a model-diversity deviation)",
    )
    rdy.set_defaults(func=cmd_ready)

    lp = sub.add_parser("ledger", help="ledger operations")
    lsub = lp.add_subparsers(dest="ledger_cmd", required=True)
    ls = common(lsub.add_parser("show", help="print the ledger"))
    ls.set_defaults(func=cmd_ledger_show)

    rp = common(
        sub.add_parser("roles-check", help="check model-family diversity between two roles")
    )
    rp.add_argument("--role-a", dest="role_a", default="oracle")
    rp.add_argument("--role-b", dest="role_b", default="coder")
    rp.set_defaults(func=cmd_roles_check)

    orp = sub.add_parser(
        "oracle",
        help="oracle independence: seal / record / dispatch / verify",
    )
    osub = orp.add_subparsers(dest="oracle_cmd", required=True)
    osl = common(osub.add_parser("seal", help="seal a spec-only oracle bundle"))
    osl.add_argument("--spec", help="path to the governing spec.md")
    osl.add_argument("--spec-id", dest="spec_id")
    osl.set_defaults(func=cmd_oracle_seal)
    orc = common(
        osub.add_parser("record", help="record oracle authoring; refuse the coder's model family")
    )
    orc.add_argument("--spec-id", dest="spec_id", required=True)
    orc.add_argument("--model", required=True, help="oracle model as <family/model>")
    orc.add_argument("--tests", nargs="+", required=True, help="oracle test file(s)")
    orc.add_argument("--base", help="git ref for the touched-implementation advisory scan")
    orc.set_defaults(func=cmd_oracle_record)
    ovf = common(osub.add_parser("verify", help="verify oracle independence"))
    ovf.add_argument("--spec-id", dest="spec_id", required=True)
    ovf.add_argument("--tests", nargs="*", help="oracle test roots (default: from the record)")
    ovf.add_argument(
        "--require-dispatch",
        dest="require_dispatch",
        action="store_true",
        help="require an isolated headless-dispatch attestation",
    )
    ovf.set_defaults(func=cmd_oracle_verify)
    odp = common(
        osub.add_parser("dispatch", help="author the oracle headlessly, read-path isolated")
    )
    odp.add_argument("--spec-id", dest="spec_id", required=True)
    odp.add_argument(
        "--integration",
        default="claude",
        help="headless agent backend for the oracle step (a non-coder family; default: claude)",
    )
    odp.add_argument("--model", help="override the resolved oracle model as <family/model>")
    odp.add_argument("--base", help="clean git ref for the sanitized worktree (default: HEAD)")
    odp.add_argument(
        "--tests",
        nargs="*",
        help="treat these as the authored oracle tests (for --dry-run / manual authoring)",
    )
    odp.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="build + attest worktree isolation without a live agent dispatch",
    )
    odp.add_argument(
        "--keep-worktree",
        dest="keep_worktree",
        action="store_true",
        help="do not tear down the worktree (debugging)",
    )
    odp.set_defaults(func=cmd_oracle_dispatch)

    obp = sub.add_parser(
        "observe", help="observe & feedback: signal / coverage / log-action / verify-actions"
    )
    obsub = obp.add_subparsers(dest="observe_cmd", required=True)
    osig = common(
        obsub.add_parser("signal", help="record a production signal → route to new intent")
    )
    osig.add_argument("--spec-id", dest="spec_id", required=True)
    osig.add_argument("--kind", required=True, help="incident | missed-nfr | usage")
    osig.add_argument("--nfr", help="the NFR id the signal relates to (optional)")
    osig.add_argument("--note", help="the production lesson (required)")
    osig.set_defaults(func=cmd_observe_signal)
    ocov = common(
        obsub.add_parser("coverage", help="report which NFRs have a live production check")
    )
    ocov.add_argument("--spec", help="path to the governing spec.md")
    ocov.add_argument(
        "--registry", help="observability.yaml (default: .3powers/config/observability.yaml)"
    )
    ocov.set_defaults(func=cmd_observe_coverage)
    olog = common(
        obsub.add_parser("log-action", help="log a tamper-evident, attributable agent action")
    )
    olog.add_argument("--agent", required=True, help="the acting agent's identity")
    olog.add_argument("--action", required=True, help="the action taken")
    olog.add_argument("--spec-id", dest="spec_id")
    olog.set_defaults(func=cmd_observe_log_action)
    over = common(obsub.add_parser("verify-actions", help="verify the runtime agent-action log"))
    over.set_defaults(func=cmd_observe_verify_actions)

    spp = sub.add_parser("spec", help="spec operations: integrity diff")
    spsub = spp.add_subparsers(dest="spec_cmd", required=True)
    spd = common(
        spsub.add_parser(
            "diff",
            help="read-only: does the spec still match its approval hash? (never writes)",
        )
    )
    spd.add_argument("--spec-id", dest="spec_id", required=True)
    spd.add_argument("--spec", help="path to the spec.md (default: the path recorded at approval)")
    spd.set_defaults(func=cmd_spec_diff)

    cfp = sub.add_parser("config", help="project configuration surfaces")
    cfsub = cfp.add_subparsers(dest="config_cmd", required=True)
    crp = cfsub.add_parser("roles", help="role → model/integration bindings (roles.yaml)")
    crsub = crp.add_subparsers(dest="roles_cmd", required=True)
    crs = common(
        crsub.add_parser(
            "setup",
            help="(re)run the headless-CLI + per-role model setup without reinitializing "
            "(AGENTX-FR-014)",
        )
    )
    crs.add_argument(
        "--yes",
        action="store_true",
        help="non-interactive: prompt for nothing and apply the documented defaults",
    )
    crs.add_argument(
        "--integration",
        help="the headless agent backend to bind roles to (e.g. claude, codex, copilot); "
        "default: the configured coder integration",
    )
    for setup_role in _SETUP_ROLES:
        crs.add_argument(
            f"--{setup_role}",
            help=f"model for the {setup_role} role (a catalog id for the integration, or free-form)",
        )
    crs.set_defaults(func=cmd_config_roles_setup)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _, ui_malformed = _resolve_ui(args)
    if ui_malformed and not getattr(args, "json", False):
        print(
            "warning: .3powers/config/ui.yaml is malformed — using default output preferences",
            file=sys.stderr,
        )
    try:
        return int(args.func(args))
    except (FileNotFoundError, LookupError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
