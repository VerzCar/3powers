"""Run preflight — verify the prerequisites for a LIVE **native** ``3pwr run`` before dispatching any stage
(EXEC-FR-015).

Honest diagnostics: a run that cannot start names the missing prerequisite and the exact fix, and always
names the fully-offline ``--dry-run`` alternative — it is never mislabeled "gates red" (EXEC-FR-016).
Provider-, model-, and agent-agnostic: the set of headless-capable agent backends is configuration-driven
and no vendor name is embedded in run logic (EXEC-NFR-003). This module only *reads* configuration and the
environment; it dispatches nothing.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import agents, deviations, keys
from .config import Settings
from .oracle import diverse, family_of

# Agent backends that can be dispatched headlessly (no interactive IDE). Config overrides this
# (roles.yaml `headless_integrations`) so the accepted set is data, not code (EXEC-NFR-003).
DEFAULT_HEADLESS: tuple[str, ...] = (
    "claude",
    "codex",
    "copilot",
    "cursor-agent",
    "opencode",
    "aider",
    "qwen",
    "auggie",
    "amp",
)
# Editor-bound backends that cannot run headless — they need an editor session. Advisory: used only to
# give a clearer message; the authoritative test is membership in the headless set.
IDE_ONLY: tuple[str, ...] = ("windsurf", "kilocode", "roo")

# The always-available offline paths named in every preflight-failure message (EXEC-FR-016).
OFFLINE_ALTERNATIVES: tuple[str, ...] = (
    'run fully offline (no dispatch): 3pwr run "<intent>" --dry-run',
    "or drive stages individually: 3pwr oracle → 3pwr gate run → 3pwr signoff → 3pwr advance",
)


@dataclass(frozen=True)
class Prereq:
    """One run prerequisite and, when unmet, the exact next step to resolve it (RUNX-FR-009).

    ``label`` is the honest status detail for a MET prerequisite (AUTOX-FR-004): it states exactly what
    was probed and what was not — e.g. an agent CLI is "present; authentication not verified" because
    authentication cannot be checked offline. No readiness line ever overstates what was checked."""

    name: str
    ok: bool
    fix: str = ""
    label: str = ""


def headless_set(settings: Settings) -> set[str]:
    """The configured headless-capable integrations, else the built-in default (RUNX-NFR-005)."""
    configured = settings.load_roles().get("headless_integrations")
    if isinstance(configured, list) and configured:
        return {str(x).strip() for x in configured if str(x).strip()}
    return set(DEFAULT_HEADLESS)


def resolve_coder_integration(settings: Settings, cli_integration: str | None) -> str:
    """The coder integration: an explicit ``--integration`` (not the ``auto`` sentinel) wins, else
    ``roles.coder.integration``; '' when neither is set."""
    if cli_integration and cli_integration != "auto":
        return cli_integration.strip()
    return str(settings.role("coder").get("integration") or "").strip()


def resolve_oracle_integration(settings: Settings) -> str:
    return str(settings.role("oracle").get("integration") or "").strip()


def _role_id(settings: Settings, role: str) -> str:
    """A role's full ``<family>/<model>`` if present, else its ``model_family`` (for diversity)."""
    r = settings.role(role)
    return str(r.get("model") or r.get("model_family") or "").strip()


def diversity_ok(settings: Settings, entries: list[dict], spec_id: str | None) -> bool:
    """True iff the oracle resolves to a family different from the coder, OR a signed model-diversity
    deviation is active (RUNX-FR-006 / 3PWR-FR-022 via FR-057)."""
    if diverse(
        _role_id(settings, "coder"), _role_id(settings, "oracle"), settings.diversity_level()
    ):
        return True
    return deviations.covers_model_diversity(deviations.active_deviations(entries), spec_id)


def _agent_prereq(
    settings: Settings,
    label: str,
    agent: str,
    headless: set[str],
    command_present: Callable[[str], bool],
) -> Prereq:
    """Whether one role's agent backend is dispatchable: configured, has a manifest, is headless, and its
    CLI is present. Native counterpart to the coder/oracle checks in :func:`check` (EXEC-FR-015)."""
    if not agent:
        return Prereq(
            label,
            False,
            f"set roles.{label.split()[1]}.integration to a headless agent backend "
            f"(a manifest in .3powers/agents/): {sorted(headless)}",
        )
    try:
        manifest = agents.load_agent(settings, agent)
    except FileNotFoundError:
        return Prereq(label, False, f"add an agent manifest at .3powers/agents/{agent}.yaml")
    if not agents.is_headless(manifest) or agent not in headless:
        hint = " (IDE-only)" if agent in IDE_ONLY else ""
        return Prereq(
            label,
            False,
            f"agent '{agent}'{hint} is not headless-dispatchable; use one of: {sorted(headless)}",
        )
    cmd = agents.agent_command(manifest)
    if not command_present(cmd):
        return Prereq(label, False, f"install/enable the '{cmd}' CLI for agent '{agent}'")
    # The honest offline caveat (AUTOX-FR-004): PATH presence is probeable; provider authentication
    # is not — say so rather than overstating what was checked.
    return Prereq(
        label,
        True,
        label=f"agent '{agent}' ('{cmd}' CLI) present; authentication not verified (offline check)",
    )


def check_native(
    settings: Settings,
    *,
    coder_agent: str,
    oracle_agent: str,
    entries: list[dict],
    spec_id: str | None,
    command_present: Callable[[str], bool] | None = None,
) -> list[Prereq]:
    """Verify the prerequisites for a LIVE **native** run (EXEC-FR-015): a headless coder agent and a
    different-family oracle agent — no Spec Kit CLI and no workflow descriptor. Pure given its inputs;
    ``command_present`` defaults to a PATH probe."""
    if command_present is None:
        command_present = lambda cmd: shutil.which(cmd) is not None  # noqa: E731
    headless = headless_set(settings)
    prqs: list[Prereq] = [
        _agent_prereq(settings, "headless coder agent", coder_agent, headless, command_present)
    ]
    oracle_pr = _agent_prereq(
        settings, "different-family oracle agent", oracle_agent, headless, command_present
    )
    if oracle_pr.ok and not diversity_ok(settings, entries, spec_id):
        oracle_pr = Prereq(
            "different-family oracle agent",
            False,
            f"the oracle's family ({family_of(_role_id(settings, 'oracle')) or '?'}) equals the "
            f"coder's ({settings.coder_family() or '?'}) — pick a different-family headless agent, or "
            "record a signed deviation: 3pwr deviation --gate model_diversity --approver <you> "
            '--note "single-model dev"',
        )
    prqs.append(oracle_pr)
    return prqs


def _git_on_path(cmd: str) -> bool:
    """The default PATH probe for :func:`git_prereq` (injected in tests — EXEC-NFR-004)."""
    return shutil.which(cmd) is not None


def git_prereq(root: Path, command_present: Callable[[str], bool] | None = None) -> Prereq:
    """A working git repository — a PRECONDITION for starting a run (GITX-FR-002).

    Git on PATH and ``root`` inside a work tree (a ``.git`` directory — or file, for a linked
    worktree — on the path upward). A pure function of the repository/environment state: offline,
    deterministic, no subprocess needed for the work-tree test (GITX-NFR-001)."""
    name = "working git repository"
    if command_present is None:
        command_present = _git_on_path
    if not command_present("git"):
        return Prereq(name, False, "install git — a run requires version control (GITX-FR-002)")
    for candidate in [root.resolve(), *root.resolve().parents]:
        if (candidate / ".git").exists():
            return Prereq(name, True, label="git present; repository detected")
    return Prereq(
        name, False, "run `git init` — the target is not inside a git repository (GITX-FR-002)"
    )


def signer_prereq(root: Path) -> Prereq:
    """A resolvable, USABLE signer — an environment-supplied key is validated (exists / readable /
    well-formed), never trusted silently (AUTOX-FR-001)."""
    name = "resolvable signing key"
    env_file = os.environ.get("THREEPOWERS_SIGNING_KEY_FILE")
    env_seed = os.environ.get("THREEPOWERS_SIGNING_KEY")
    try:
        signer = keys.resolve_signer(root)
        _ = (
            signer.key_id
        )  # force key derivation: a malformed/short seed fails HERE, not at first signing
    except FileNotFoundError:
        if env_file:
            return Prereq(
                name,
                False,
                f"$THREEPOWERS_SIGNING_KEY_FILE points at a missing/unreadable file ({env_file}) — "
                "fix the path, or run `3pwr keygen` and re-export the variable it prints",
            )
        return Prereq(
            name,
            False,
            'run `3pwr keygen`, then: export THREEPOWERS_SIGNING_KEY_FILE="<the key path it prints>"',
        )
    except (ValueError, OSError, keys.ExternalSignerError) as exc:
        source = (
            f"$THREEPOWERS_SIGNING_KEY_FILE ({env_file})"
            if env_file
            else ("$THREEPOWERS_SIGNING_KEY" if env_seed else "the default key path")
        )
        return Prereq(
            name,
            False,
            f"the signing key from {source} is not usable ({exc}) — "
            "run `3pwr keygen` and re-export the variable it prints",
        )
    return Prereq(name, True, label=f"signer {signer.key_id}")


def check_auto(
    settings: Settings,
    *,
    coder_agent: str,
    oracle_agent: str,
    entries: list[dict],
    spec_id: str | None,
    command_present: Callable[[str], bool] | None = None,
) -> list[Prereq]:
    """Every prerequisite a live ``3pwr run --mode auto`` enforces before dispatching, as ONE shared
    check set (AUTOX-FR-002): ``3pwr init``'s readiness, the standalone ``3pwr ready``, and the run's
    own preflight all consume this list, so their verdicts cannot drift — one source of checks.

    Ordered so the unmet items' fixes read as executable next steps in dependency order
    (AUTOX-FR-005): signing key → working git repository (GITX-FR-002) → coder agent (roles + CLI)
    → different-family oracle agent."""
    return [
        signer_prereq(settings.root),
        git_prereq(settings.root, command_present),
        *check_native(
            settings,
            coder_agent=coder_agent,
            oracle_agent=oracle_agent,
            entries=entries,
            spec_id=spec_id,
            command_present=command_present,
        ),
    ]


def unmet(prqs: list[Prereq]) -> list[Prereq]:
    return [p for p in prqs if not p.ok]


def provenance_payload(stage: str, integration: str, model: str) -> dict[str, str]:
    """The additive executive-dispatch provenance recorded per dispatched stage (RUNX-FR-007).

    Names the stage, the dispatching integration, and the resolved model — bound into the same signed,
    hash-chained ledger as the run's verdict, so altering one is detectable by ``3pwr verify`` (NFR-002)."""
    return {
        "kind": "dispatch",
        "stage": stage,
        "integration": integration or "",
        "model": model or "",
    }
