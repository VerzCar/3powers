"""Work-kind inference — shape the tier + oracle strategy, never the sign-off.

Free-form intent is classified into work kind(s) and a *suggested risk tier* **deterministically**
(keyword heuristics — no model call, so it never perturbs the deterministic verdict). A
single intent may resolve to multiple kinds. The inference only *shapes* the run — the human still
approves the spec and signs off on the evidence. Per-kind gate shaping
(defect → a regression gate, design → visual/a11y oracles) builds on this classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Recognised kinds. "feature" is the default when nothing else matches.
KINDS = ("defect", "design", "docs", "refactor", "chore", "feature")

# keyword → kind (word-boundary matched, case-insensitive).
_KIND_KEYWORDS: dict[str, tuple[str, ...]] = {
    "defect": (
        "bug",
        "fix",
        "fixes",
        "regression",
        "broken",
        "crash",
        "hotfix",
        "defect",
        "incorrect",
    ),
    "design": (
        "ui",
        "ux",
        "css",
        "style",
        "styling",
        "layout",
        "visual",
        "component",
        "a11y",
        "accessibility",
        "design",
        "responsive",
        "theme",
    ),
    "docs": ("docs", "documentation", "readme", "changelog", "docstring", "typo", "wording"),
    "refactor": ("refactor", "rename", "restructure", "cleanup", "extract", "dedupe", "simplify"),
    "chore": ("chore", "bump", "upgrade", "lockfile", "dependencies", "dependency", "tooling"),
}
# High-risk domains (spec §4) → suggested High-risk tier regardless of kind.
_HIGH_RISK_KEYWORDS: tuple[str, ...] = (
    "auth",
    "authentication",
    "authorization",
    "password",
    "credential",
    "payment",
    "billing",
    "checkout",
    "money",
    "crypto",
    "encryption",
    "secret",
    "token",
    "access control",
    "permission",
    "security",
    "login",
    "session",
    "pii",
)
# Kinds that, alone, warrant only the Cosmetic tier.
_COSMETIC_KINDS = frozenset({"docs", "chore"})


@dataclass
class WorkKind:
    kinds: list[str] = field(default_factory=list)
    suggested_tier: str = "Standard"
    signals: list[str] = field(default_factory=list)  # which keywords matched, for transparency


def _matches(text: str, words: tuple[str, ...]) -> list[str]:
    return [w for w in words if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)]


def classify(intent: str) -> WorkKind:
    """Infer work kind(s) + a suggested risk tier from free-form intent (deterministic)."""
    text = (intent or "").lower()
    kinds: list[str] = []
    signals: list[str] = []
    for kind, words in _KIND_KEYWORDS.items():
        hits = _matches(text, words)
        if hits:
            kinds.append(kind)
            signals += [f"{kind}:{h}" for h in hits]
    if not kinds:
        kinds = ["feature"]

    high_risk = _matches(text, _HIGH_RISK_KEYWORDS)
    if high_risk:
        tier = "High-risk"
        signals += [f"high-risk:{h}" for h in high_risk]
    elif all(k in _COSMETIC_KINDS for k in kinds):
        tier = "Cosmetic"
    else:
        tier = "Standard"

    return WorkKind(kinds=sorted(set(kinds)), suggested_tier=tier, signals=sorted(set(signals)))
