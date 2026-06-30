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


def model_diversity_ok(roles: dict[str, Any], role_a: str, role_b: str) -> bool:
    """True iff the two roles resolve to *different* model families (3PWR-FR-022)."""
    table = roles.get("roles", {})
    fam_a = (table.get(role_a) or {}).get("model_family")
    fam_b = (table.get(role_b) or {}).get("model_family")
    if not fam_a or not fam_b:
        return False
    return fam_a != fam_b
