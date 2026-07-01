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
    def adapters_dir(self) -> Path:
        return self.dir / "adapters"

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
