"""Locate the 3Powers root and load the single-source-of-truth configuration.

Every gate threshold (diff-coverage, mutation score, model diversity, verification
spend) is read from one risk-tier table (3PWR-FR-032/049). Roles are bound to model
*families* so the engine can refuse to run when judicial independence is violated
(3PWR-FR-022/044).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

THREEPOWERS_DIRNAME = ".3powers"


@dataclass
class Settings:
    root: Path

    @property
    def dir(self) -> Path:
        return self.root / THREEPOWERS_DIRNAME

    @property
    def ledger_path(self) -> Path:
        return self.dir / "ledger.jsonl"

    @property
    def pubkey_path(self) -> Path:
        return self.dir / "keys" / "ledger.pub"

    @property
    def oracle_pubkey_path(self) -> Path:
        """The distinct judiciary (oracle) public key, if one was minted (3PWR-FR-021/039)."""
        return self.dir / "keys" / "oracle.pub"

    @property
    def verdicts_dir(self) -> Path:
        return self.dir / "verdicts"

    @property
    def risk_tiers_path(self) -> Path:
        return self.dir / "config" / "risk-tiers.yaml"

    @property
    def roles_path(self) -> Path:
        return self.dir / "config" / "roles.yaml"

    @property
    def design_oracles_path(self) -> Path:
        return self.dir / "config" / "design-oracles.yaml"

    @property
    def adapters_dir(self) -> Path:
        return self.dir / "adapters"

    @property
    def agents_dir(self) -> Path:
        """Declarative agent-backend manifests for the native executive (EXEC-FR-002)."""
        return self.dir / "agents"

    @property
    def onboarding_path(self) -> Path:
        """Advisory onboarding preferences written by ``3pwr init`` (3PWR-ONBRD-FR-005)."""
        return self.dir / "config" / "onboarding.yaml"

    @property
    def context_config_path(self) -> Path:
        """The advisory per-model context-budget configuration (PHASE-FR-007)."""
        return self.dir / "config" / "context.yaml"

    @property
    def constitution_path(self) -> Path:
        """The project constitution — part of every phase's reload set (PHASE-FR-008)."""
        return self.dir / "memory" / "constitution.md"

    def context_budget(self, model: str = "") -> int:
        """The advisory context budget in tokens for ``model`` (PHASE-FR-007).

        Read from ``context.yaml``: a per-model entry under ``models:`` wins, else the file's
        ``budget_tokens``, else the shipped default (~110k). Deterministic — the same config bytes
        always resolve the same budget — and strictly advisory: exceeding it warns and advises a
        split, never a failed gate (PHASE-FR-009, PHASE-NFR-002)."""
        from .phases import DEFAULT_BUDGET_TOKENS

        data = _load_yaml(self.context_config_path)
        candidate: Any = None
        models = data.get("models") or {}
        if model and isinstance(models, dict) and model in models:
            candidate = models[model]
        if candidate is None:
            candidate = data.get("budget_tokens")
        try:
            n = int(candidate) if candidate is not None else 0
        except (TypeError, ValueError):
            n = 0
        return n if n > 0 else DEFAULT_BUDGET_TOKENS

    def default_mode(self) -> str:
        """The recorded ``3pwr run`` autonomy default (advisory — ONBRD-FR-005): ``auto`` | ``commit``.

        Defaults to ``auto`` when no preference was recorded. Advisory only: it selects the *default*
        mode when ``--mode`` is omitted and never suppresses a mandatory human gate (ONBRD-NFR-004)."""
        auto = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("auto_mode")
        if auto is None:
            return "auto"
        return "auto" if bool(auto) else "commit"

    def auto_commit(self) -> bool:
        """Whether per-stage auto-commit is enabled (INITX-FR-006). Defaults to True (the wanted workflow).

        Advisory: it commits each successful lifecycle stage; it never touches the ledger or a gate."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("auto_commit")
        return True if v is None else bool(v)

    def dispatch_timeout(self) -> int:
        """The per-stage dispatch timeout in seconds (RUNLIVE-FR-004). Defaults to 1800 (30 min).

        Advisory config only: it bounds how long one agent dispatch may run before it is terminated and
        reported as a dispatch failure. Never affects a gate, verdict, or the ledger."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("dispatch_timeout_s")
        if not isinstance(v, (int, str)):
            return 1800
        try:
            n = int(v)
        except ValueError:
            return 1800
        return n if n > 0 else 1800

    def dispatch_retries(self) -> int:
        """How many times a *failed* dispatch is retried before the stage is reported failed (RUNLIVE-FR-005).

        Defaults to 1 (one retry on a transient failure). A stage is attempted at most ``retries + 1`` times;
        a successful stage is never retried. Advisory config only — never a gate or verdict."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("dispatch_retries")
        if not isinstance(v, (int, str)):
            return 1
        try:
            n = int(v)
        except ValueError:
            return 1
        return n if n >= 0 else 1

    def default_tier(self) -> str:
        """The recorded default risk tier a new spec starts at (advisory — INITX-FR-001).

        Defaults to ``Standard`` when no preference was recorded. Advisory only: it never lowers a
        threshold or removes a gate (INITX-NFR-002); it seeds the tier a fresh spec is authored at."""
        tier = str(
            (_load_yaml(self.onboarding_path).get("defaults") or {}).get("tier") or ""
        ).strip()
        return tier or "Standard"

    def load_risk_tiers(self) -> dict[str, Any]:
        return _load_yaml(self.risk_tiers_path)

    def load_roles(self) -> dict[str, Any]:
        return _load_yaml(self.roles_path)

    def oracle_require_dispatch(self) -> bool:
        """Policy: require an isolated headless-dispatch attestation at High-risk (3PWR-FR-021/A3).

        Default False — the manual/in-IDE oracle flow (model-switch in the agent window) stays valid;
        a repo opts in by setting ``roles.oracle.require_dispatch: true`` once it adopts the workflow."""
        roles = self.load_roles()
        oracle = (roles.get("roles") or {}).get("oracle") or {}
        return bool(oracle.get("require_dispatch", False))

    def diversity_level(self) -> str:
        """How strictly model diversity is compared (3PWR-FR-022): ``family`` (default) or ``model``.

        ``family`` — the oracle and coder must be different model *families*.
        ``model``  — a different *model* in the same family qualifies (e.g. opus vs sonnet)."""
        level = str(self.load_roles().get("diversity_level", "family")).strip().lower()
        return level if level in ("family", "model") else "family"

    def coder_model(self) -> str:
        """The coder's full ``<family>/<model>`` if declared (for model-level diversity); else ''."""
        return ((self.load_roles().get("roles") or {}).get("coder") or {}).get("model", "") or ""

    def role(self, name: str) -> dict[str, Any]:
        """The raw configuration block for one role (empty dict when absent)."""
        return (self.load_roles().get("roles") or {}).get(name) or {}

    def coder_family(self) -> str:
        """The coder's model *family* — from its full ``model`` if present, else ``model_family``."""
        from .oracle import family_of

        c = self.role("coder")
        return (family_of(str(c.get("model") or "")) or str(c.get("model_family") or "")).strip()

    def role_model_pin(self, name: str) -> dict[str, str] | None:
        """The concrete model pin for a role — ``{model, integration, label}`` — or ``None`` (INITX-FR-003).

        Reading a roles configuration that predates this feature (family-only, no ``model``) simply
        yields ``None`` here and never fails — the concrete-model fields are additive. ``label``
        falls back to the model id, so a pin always renders as ``<label> (<integration>)`` (INITX-FR-004)."""
        r = self.role(name)
        model = str(r.get("model") or "").strip()
        if not model:
            return None
        return {
            "model": model,
            "integration": str(r.get("integration") or "").strip(),
            "label": str(r.get("label") or "").strip() or model,
        }


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` (default cwd) to the directory holding ``.3powers/``."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / THREEPOWERS_DIRNAME).is_dir():
            return candidate
    raise FileNotFoundError(
        f"no {THREEPOWERS_DIRNAME}/ directory found from {cur} upward — run `3pwr init`"
    )


def tier_config(tiers: dict[str, Any], tier: str) -> dict[str, Any]:
    table = tiers.get("tiers", {})
    if tier not in table:
        raise KeyError(f"unknown risk tier {tier!r}; known: {sorted(table)}")
    return table[tier]


def model_diversity_ok(
    roles: dict[str, Any], role_a: str, role_b: str, level: str = "family"
) -> bool:
    """True iff two roles are *diverse enough* at ``level`` (3PWR-FR-022).

    Compares each role's declared ``model`` (full ``<family>/<model>``) when present, else its
    ``model_family``. Delegates to ``oracle.diverse`` for a single source of truth."""
    from .oracle import diverse  # local import avoids any import cycle at module load

    table = roles.get("roles", {})
    a = table.get(role_a) or {}
    b = table.get(role_b) or {}
    a_id = (a.get("model") or a.get("model_family") or "").strip()
    b_id = (b.get("model") or b.get("model_family") or "").strip()
    return diverse(a_id, b_id, level)
