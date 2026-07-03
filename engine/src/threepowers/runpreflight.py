"""Run preflight — verify the prerequisites for a LIVE **native** ``3pwr run`` before dispatching any stage
(EXEC-FR-015).

Honest diagnostics: a run that cannot start names the missing prerequisite and the exact fix, and always
names the fully-offline ``--dry-run`` alternative — it is never mislabeled "gates red" (EXEC-FR-016).
Provider-, model-, and agent-agnostic: the set of headless-capable agent backends is configuration-driven
and no vendor name is embedded in run logic (EXEC-NFR-003). This module only *reads* configuration and the
environment; it dispatches nothing.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable

from . import agents, deviations
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
    """One run prerequisite and, when unmet, the exact next step to resolve it (RUNX-FR-009)."""

    name: str
    ok: bool
    fix: str = ""


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
    return Prereq(label, True)


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
