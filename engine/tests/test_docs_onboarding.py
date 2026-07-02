"""Documentation requirements for onboarding (ONBRD-FR-011…014, NFR-006).

3Powers self-applies (3PWR-NFR-006): these tests verify the *documentation* requirements the same way
a gate would, by asserting structural properties of the repo's user-facing docs. They locate the repo
root relative to the engine and skip cleanly if run against a packaged engine without the docs tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"

_GUIDES = [
    REPO / "README.md",
    REPO / "docs" / "cli-reference.md",
    REPO / "docs" / "getting-started.md",
    REPO / "docs" / "brownfield.md",
]

# Run only against the real repo docs tree; skip cleanly otherwise. `README.exists()` alone is not
# enough: under a copied layout (mutmut copies the tests into `mutants/`, so `parents[2]` resolves to
# `engine/`) a *different* README.md exists and would make these tests FAIL instead of skip — which
# silently breaks the mutation baseline, and with it self-application (3PWR-NFR-006). Requiring every
# guide the tests actually read distinguishes the true repo root from a stray README.
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _GUIDES),
    reason="repo docs tree not present (packaged engine or copied layout)",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- FR-011
def test_readme_presents_autonomous_flow_before_manual():
    """ONBRD-FR-011: the autonomous one-command flow appears before the manual flow."""
    t = _read(README)
    i_auto = t.find("## Quickstart — the autonomous path")
    i_manual = t.find("## Prefer to drive it yourself? Manual mode")
    assert i_auto != -1 and i_manual != -1
    assert i_auto < i_manual
    # the autonomous `--mode auto` run precedes the manual slash-command flow
    assert 0 <= t.find("--mode auto") < t.find("/3pwr.oracle")


# --------------------------------------------------------------------------- FR-012
def test_readme_states_enterprise_high_autonomy_positioning_near_top():
    """ONBRD-FR-012: the enterprise, high-autonomy positioning appears above the deep-dive sections."""
    t = _read(README)
    above_fold = t.split("## The problem")[0].lower()
    assert "enterprise-ready" in above_fold
    assert "high autonomy" in above_fold
    assert "agentic" in above_fold


# --------------------------------------------------------------------------- FR-013
def test_readme_has_supported_languages_table_for_self_qualification():
    """ONBRD-FR-013: a supported-languages table lets a reader confirm fit (incl. a Next.js answer)."""
    t = _read(README)
    assert "## Supported languages & technology stack" in t
    assert "| Language | Detected by |" in t  # header row (also ONBRD-NFR-006)
    for lang in ("TypeScript", "Python", "Go"):
        assert lang in t
    for tool in ("Biome", "Ruff", "gofmt", "Vitest", "pytest", "Stryker", "mutmut"):
        assert tool in t
    assert "Next.js" in t  # a TypeScript reader can confirm framework fit


# --------------------------------------------------------------------------- FR-014
def test_guided_init_documented_consistently():
    """ONBRD-FR-014: guided onboarding is documented consistently across the guides."""
    for guide in _GUIDES:
        text = _read(guide)
        assert "3pwr init" in text
        assert "guided" in text.lower()


def test_no_unresolved_open_question_markers_in_docs():
    """ONBRD-FR-014: reviewed user-facing docs carry no unresolved to-do/open-question markers."""
    marker = re.compile(r"\bTODO\b|\bTBD\b|\bFIXME\b|\?\?\?|<placeholder>|your-org")
    for guide in _GUIDES:
        hits = [ln for ln in _read(guide).splitlines() if marker.search(ln)]
        assert not hits, f"{guide.name}: unresolved markers {hits}"


# --------------------------------------------------------------------------- NFR-006
def test_docs_meet_baseline_readability_practices():
    """ONBRD-NFR-006: descriptive link text (no bare 'click here') and header rows on tables."""
    for guide in _GUIDES:
        assert "click here" not in _read(guide).lower()
    assert "| Language | Detected by |" in _read(README)
