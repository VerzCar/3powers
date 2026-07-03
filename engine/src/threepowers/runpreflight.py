"""Run preflight — verify the prerequisites for a LIVE ``3pwr run`` before dispatching any stage (RUNX-FR-009).

Honest diagnostics: a run that cannot start names the missing prerequisite and the exact fix, and always
names the fully-offline ``--dry-run`` and the step-by-step alternatives (RUNX-FR-012) — it is never
mislabeled "gates red" (RUNX-FR-010). Integration-, provider-, and model-agnostic: the set of
headless-capable integrations is configuration-driven and no integration name is embedded in run logic
(RUNX-NFR-005). This module only *reads* configuration and the environment; it dispatches nothing.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import deviations
from .config import Settings
from .oracle import diverse, family_of

# Integrations that can be dispatched headlessly (no interactive IDE). Config overrides this
# (roles.yaml `headless_integrations`) so the accepted set is data, not code (RUNX-NFR-005).
DEFAULT_HEADLESS: tuple[str, ...] = (
    "claude",
    "gemini",
    "codex",
    "cursor-agent",
    "opencode",
    "qwen",
    "auggie",
    "amp",
)
# IDE-bound integrations that cannot run headless — they need an editor session. Advisory: used only to
# give a clearer message; the authoritative test is membership in the headless set.
IDE_ONLY: tuple[str, ...] = ("copilot", "windsurf", "kilocode", "roo")

# The always-available offline paths named in every preflight-failure message (RUNX-FR-012).
OFFLINE_ALTERNATIVES: tuple[str, ...] = (
    'run fully offline (no dispatch): 3pwr run "<intent>" --dry-run',
    "or drive it step-by-step: /speckit.specify → … → /3pwr.advance",
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


def check(
    settings: Settings,
    *,
    workflow_path: Path,
    coder_integration: str,
    oracle_integration: str,
    entries: list[dict],
    spec_id: str | None,
    specify_present: bool | None = None,
) -> list[Prereq]:
    """Verify every live-run prerequisite (RUNX-FR-009). Pure given its inputs — the caller supplies the
    resolved integrations and the ledger entries; ``specify_present`` defaults to a PATH probe."""
    if specify_present is None:
        specify_present = shutil.which("specify") is not None
    headless = headless_set(settings)
    prqs: list[Prereq] = [
        Prereq(
            "lifecycle workflow",
            workflow_path.exists(),
            f"provision it with `3pwr init --with-speckit` (expected at {workflow_path})",
        ),
        Prereq(
            "Spec Kit CLI",
            bool(specify_present),
            "install Spec Kit's `specify` CLI (https://github.com/github/spec-kit)",
        ),
    ]

    # A headless coder integration (RUNX-FR-001).
    if not coder_integration:
        prqs.append(
            Prereq(
                "headless coder integration",
                False,
                "set roles.coder.integration (or pass --integration) to a headless one: "
                f"{sorted(headless)}",
            )
        )
    elif coder_integration not in headless:
        hint = " (IDE-only)" if coder_integration in IDE_ONLY else ""
        prqs.append(
            Prereq(
                "headless coder integration",
                False,
                f"integration '{coder_integration}'{hint} is not headless-dispatchable; "
                f"use one of: {sorted(headless)}",
            )
        )
    else:
        prqs.append(Prereq("headless coder integration", True))

    # A different-family oracle integration (RUNX-FR-005/006).
    if not oracle_integration:
        prqs.append(
            Prereq(
                "different-family oracle integration",
                False,
                "set roles.oracle.integration to a headless integration whose model family "
                "differs from the coder's",
            )
        )
    elif oracle_integration not in headless:
        hint = " (IDE-only)" if oracle_integration in IDE_ONLY else ""
        prqs.append(
            Prereq(
                "different-family oracle integration",
                False,
                f"oracle integration '{oracle_integration}'{hint} is not headless-dispatchable; "
                f"use one of: {sorted(headless)}",
            )
        )
    elif not diversity_ok(settings, entries, spec_id):
        prqs.append(
            Prereq(
                "different-family oracle integration",
                False,
                f"the oracle's family ({family_of(_role_id(settings, 'oracle')) or '?'}) equals the "
                f"coder's ({settings.coder_family() or '?'}) — pick a different-family headless "
                "integration, or record a signed deviation: 3pwr deviation --gate model_diversity "
                '--approver <you> --note "single-model dev"',
            )
        )
    else:
        prqs.append(Prereq("different-family oracle integration", True))

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
