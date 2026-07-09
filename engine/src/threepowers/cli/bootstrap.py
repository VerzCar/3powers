"""Onboarding and project-setup commands: ``init``, ``commit-stage``,
``config roles setup`` — plus their layout/readiness/roles/notifications setup flows."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


import threepowers.cli as _cli
from .. import (
    agents,
    catalog,
    keys,
    notify,
    oracle,
    runpreflight,
    scaffold,
    style,
)
from ..config import Settings
from ..ledger import Ledger
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    _ask,
    _ask_choice,
    _ask_yesno,
    _compose,
    _git_out,
    _print,
    _settings,
    _styler,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def _init_interactive(args: argparse.Namespace) -> bool:
    """Onboarding is interactive only with a real TTY and neither --yes nor --json."""
    return (
        (not getattr(args, "json", False))
        and (not getattr(args, "yes", False))
        and sys.stdin.isatty()
    )


def _init_layout(s: Settings) -> str:
    """Create the ``.3powers/`` skeleton idempotently. Returns created|kept."""
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


# The always-on constitution call to action: the seeded constitution is mandatory but ships generic —
# adapting it to the project is a first-run prerequisite the offline engine cannot verify itself, so
# init surfaces it both interactively and as the final --json next step (additive; the auto-run
# fixes keep their dependency order ahead of it).
_CONSTITUTION_CTA = (
    "adapt the constitution: open .3powers/memory/constitution.md and complete its "
    '"How to adapt this constitution" checklist (technical baseline + policies) — '
    "mandatory before the first real run"
)


def _readiness_checklist(
    ready: dict[str, object],
    *,
    model_div_ok: bool,
    auto_prqs: Optional[list[runpreflight.Prereq]] = None,
) -> list[tuple[str, str, str]]:
    """Build the first-run readiness checklist.

    Each item is ``(label, status, detail)`` with status ∈ ``pass`` | ``warn`` | ``fail`` | ``todo``.
    A missing CI/CD configuration is a mandatory prerequisite for secure gate enforcement (fail);
    a 3Powers-generated AGENTS.md starter is an unfinished TODO. No item
    is omitted. ``auto_prqs`` — the SAME check set the live run preflight enforces
    (``runpreflight.check_auto``) — is appended per item, so init's "ready" and the run's refusal can
    never drift."""
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
            'in place — ADAPT IT to this project: complete the "How to adapt this constitution" '
            "checklist in .3powers/memory/constitution.md before the first real run"
            if ready.get("constitution")
            else "seeded by `3pwr init` — adapt it to this project before the first real run",
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
            else "oracle shares the coder's family (or is unset) — recommended to differ",
        )
    )
    # The auto full-mode prerequisites — sourced from the run's own preflight checks, so a "ready"
    # here means `3pwr run --mode auto` will not refuse to start.
    for p in auto_prqs or []:
        items.append(
            (f"auto run: {p.name}", "pass" if p.ok else "fail", p.label if p.ok else p.fix)
        )
    return items


def _checklist_lines(st: style.Styler, items: list[tuple[str, str, str]]) -> list[str]:
    """Render checklist items as colorized ``<mark> <label>: <detail>`` lines."""
    return [f"  {st.mark(status)} {st.bold(label)}: {detail}" for label, status, detail in items]


# The configurable roles the setup walks, in the order they are asked.
_SETUP_ROLES = ("planner", "coder", "oracle", "reviewer")


def _warn_diversity(s: Settings, st: style.Styler) -> list[str]:
    """Warn (stderr) when the oracle or reviewer resolves to the coder's family.

    Diversity is recommended, never forced: the warning names the signed
    deviation path and the setup always proceeds. Warnings go to stderr so a ``--json`` run's
    stdout stays byte-identical. Returns the roles warned about."""
    coder_fam = s.coder_family()
    hit: list[str] = []
    if not coder_fam:
        return hit
    for role in ("oracle", "reviewer"):
        r = s.role(role)
        # The explicit model_family wins — catalog bindings may use bare, integration-native ids
        # whose family the id does not encode.
        fam = (
            str(r.get("model_family") or "") or oracle.family_of(str(r.get("model") or ""))
        ).strip()
        if fam and fam == coder_fam:
            hit.append(role)
            print(
                st.warn(
                    f"⚠ {role} resolves to the coder's model family ({coder_fam}) — model "
                    "diversity is recommended."
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
    box even within a single BYOK integration."""
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
    """The shared headless-CLI + role→model + diversity setup.

    One pass: multi-select which agent-backend CLIs you use (no provider is forced),
    then bind each configurable role — planner, coder, oracle, reviewer — to an integration from that
    selection and a model drawn from its catalog or entered free-form, writing a
    complete block (``model_family``/``model``/``integration``/``label``, ``require_dispatch`` for the
    oracle) so ``3pwr run`` needs no manual role editing. Finally choose how
    diversity is judged — by ``family`` or ``model``.

    Integration and family are orthogonal: one BYOK integration (e.g. copilot) can bind coder and
    oracle to different families, so diversity never forces a second CLI. When ``integration`` is
    given it fixes the single backend (``3pwr config roles setup --integration``).

    Non-interactive: prompts for nothing; explicit choices are applied, and a role
    with no binding yet receives a documented default — already-bound roles are preserved untouched
    (non-destructive). Deterministic and offline; diversity
    only ever warns."""
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
            _cli._ask_multi(
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

    # 3) How is diversity judged — family or model?
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
    """(Re)run the headless-CLI + role→model setup without reinitializing.

    The same integration + per-role selection init performs, non-destructively: only the roles
    reconfigured here are rewritten; every other roles.yaml field is preserved.
    Non-interactive (``--yes``/``--json``/no TTY) prompts for nothing and applies the documented
    defaults. Dispatch configuration only — no gate, verdict, ledger, or human
    gate is touched, and model diversity only ever warns."""
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
            "oracle.require_dispatch: the High-risk read-path-isolation policy — "
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
    """Auto-commit after a successful lifecycle stage.

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
    """Pick one run-notification channel (or none) and write its config.

    Secrets are never stored: slack/teams record only the env-var *name* holding the
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
    """Guided onboarding — make an existing or new project 3Powers-ready in one step.

    Interactive by default; with ``--yes``/``--json`` or no TTY it prompts for nothing and applies the
    documented default for every choice. It creates the signer OUTSIDE the repo, seeds the baseline
    config + the selected language adapter without clobbering, records the autonomy default, is
    idempotent on re-run, and prints greenfield-vs-brownfield next steps. Fully offline."""
    as_json = getattr(args, "json", False)
    interactive = _init_interactive(args)
    st = _styler(args)

    # 1) Target directory — default the current directory.
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

    # 3) Brownfield detection + a suggested default language.
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
    # 4) Language selection from the supported (adapter-backed) set.
    lang = args.language or _ask_choice(
        "Which language adapter?", langs, default_lang, interactive=interactive
    )

    # 5) Signing key — a private location OUTSIDE the repo.
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
                f"error: the signing key must live OUTSIDE the repository: {key_path}",
                file=sys.stderr,
            )
            return EXIT_USAGE
        _sk, key_status = scaffold.create_signer(key_path, s.pubkey_path, force=args.force)

    # 6) Autonomy default — advisory; never bypasses a human gate.
    auto_mode = (
        args.auto_mode
        if args.auto_mode is not None
        else _ask_yesno("Make autonomous mode the default?", True, interactive=interactive)
    )

    # 7) Seed baseline config + the selected adapter, never clobbering.
    cfg = scaffold.seed_config(s)
    scaffold.seed_gitignore(s)
    scaffold.seed_contract(s)
    adapter_status = scaffold.materialize_adapter(s, lang) if lang else "none"

    # 8) Config selection — accept the recommended defaults or customize the choices that can
    #    never weaken a gate: the default risk tier + the headless-CLI/role→model bindings.
    #    The seeded roles.yaml is the documented default,
    #    so a non-interactive init prompts for nothing and stays run-ready.
    tier = getattr(args, "tier", None) or s.default_tier()
    oracle_model = getattr(args, "oracle_model", None)
    oracle_integration = getattr(args, "oracle_integration", None)
    oracle_label = getattr(args, "oracle_label", None)
    customized = bool(oracle_model or getattr(args, "tier", None))
    roles_report: Optional[dict[str, Any]] = None
    notify_report: dict[str, Any] = {"channel": "none"}
    # The guided judiciary setup always runs interactively, each prompt carrying an accept-by-Enter
    # default: risk tier → which agent CLIs → per-role model →
    # diversity mode → notifications. Non-interactive prompts for nothing — the seeded roles.yaml +
    # empty notifications are the documented defaults and stay run-ready.
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
            # Diversity is recommended, not forced. Warn to STDERR so a --json
            # run's stdout stays byte-identical; never a silent accept.
            print(
                st.warn(
                    f"⚠ oracle model shares the coder's family ({coder_fam}) — model diversity is "
                    "recommended."
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

    # 9) AGENTS.md — create a 3Powers starter if the repo has none.
    agents_status = scaffold.seed_agents_md(root)

    # 10) Seed the native agent-backend manifests, the per-stage agent templates, and the 3Powers
    #     constitution (offline, non-clobber). `3pwr run` drives these agents directly — no Spec Kit
    #     substrate — and each dispatched stage's editable
    #     instructions live in .3powers/templates/agents/.
    agents_seeded = scaffold.seed_agents(s)  # .3powers/agents/*.yaml
    templates_seeded = scaffold.seed_stage_templates(s)  # .3powers/templates/agents/*.agent.md
    constitution_status = scaffold.seed_constitution(root)
    ready = scaffold.readiness(root)

    # Judiciary model-diversity readiness (needs config): a concrete oracle model in a family
    # different from the coder's. The oracle's explicit model_family
    # wins over prefix-derivation — catalog bindings may use bare ids.
    oracle_pin = s.role_model_pin("oracle")
    coder_fam = s.coder_family()
    oracle_fam = (
        str(s.role("oracle").get("model_family") or "")
        or oracle.family_of((oracle_pin or {}).get("model", ""))
    ).strip()
    model_div_ok = oracle_pin is not None and (not coder_fam or oracle_fam != coder_fam)

    # Auto full-mode readiness — the SAME check set the live run preflight enforces:
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
        # — derived from the same checks the run preflight enforces.
        "auto_ready": not auto_unmet,
        "auto_run": [
            {"prerequisite": p.name, "ok": p.ok, "label": p.label, "fix": p.fix} for p in auto_prqs
        ],
        # The auto-run fixes first (dependency order), then the always-on constitution-adaptation
        # step — the constitution is mandatory and must be adapted before the first real run.
        "next_steps": [p.fix for p in auto_unmet] + [_CONSTITUTION_CTA],
    }
    if as_json:
        print(json.dumps(report, indent=2))
        return EXIT_OK

    # ---- human, colorized summary ----
    lines = [st.ok("✓") + " " + st.bold(f"3Powers is ready under {s.dir}")]
    if key_status == "created":
        lines.append(f"  signer created (private key OUTSIDE the repo): {key_path}")
        lines.append(f'  point the engine at it:  export THREEPOWERS_SIGNING_KEY_FILE="{key_path}"')
    elif key_status == "kept":
        lines.append(f"  signer: kept existing key at {key_path}")
    else:
        lines.append("  signer: using the key from your environment")
    lines.append(f"  language: {lang or '(none — no adapter selected)'}")
    lines.append(f"  adapter: {adapter_status}")
    lines.append(f"  default tier: {tier}")
    lines.append(f"  autonomous default: {'yes' if auto_mode else 'no'}")
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

    # Readiness checklist. The header keeps the phrase the onboarding
    # contract documents so existing guidance stays discoverable.
    lines.append("")
    lines.append(st.head("Ready for the agentic workflow? — readiness checklist:"))
    lines.extend(_checklist_lines(st, checklist))
    if not git_present:
        lines.append(
            st.warn("  ⚠ no git repo detected")
            + " — `git init` to unlock diff-scoped brownfield gating"
        )

    # The constitution is mandatory and ships generic: adapting it is a first-run prerequisite the
    # offline engine cannot check itself — surface it prominently, always.
    lines.append("")
    lines.append(st.warn("⚠ ") + st.bold("Adapt the constitution before your first real run:"))
    lines.append(
        "  .3powers/memory/constitution.md is mandatory and ships generic — open it and complete"
    )
    lines.append('  its "How to adapt this constitution" checklist (technical baseline + policies)')

    # The remaining auto full-mode steps, as exact fixes in dependency order:
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
    # in the config). Shown as a call-to-action alongside the signer export.
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
    # describe what you want and 3pwr drives the lifecycle.
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

    # Existing code? The now-working brownfield on-ramp, demoted below the primary CTA.
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


def _register_init(sub: SubParsers, common: AddCommon) -> None:
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
        help="default risk tier a new spec starts at (advisory; never weakens a gate)",
    )
    ip.add_argument(
        "--oracle-model",
        dest="oracle_model",
        help="judiciary oracle model as <family>/<model>, pinned into /3pwr.oracle",
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


def _register_commit_stage(sub: SubParsers, common: AddCommon) -> None:
    csp = common(
        sub.add_parser(
            "commit-stage",
            help="auto-commit after a successful lifecycle stage",
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


def _register_config(sub: SubParsers, common: AddCommon) -> None:
    cfp = sub.add_parser("config", help="project configuration surfaces")
    cfsub = cfp.add_subparsers(dest="config_cmd", required=True)
    crp = cfsub.add_parser("roles", help="role → model/integration bindings (roles.yaml)")
    crsub = crp.add_subparsers(dest="roles_cmd", required=True)
    crs = common(
        crsub.add_parser(
            "setup",
            help="(re)run the headless-CLI + per-role model setup without reinitializing",
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
