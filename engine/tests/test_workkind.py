"""Work-kind inference (3PWR-FR-058) — deterministic classification + suggested tier."""

from __future__ import annotations

import json

from threepowers import workkind
from threepowers.cli import main


def test_classify_defect_and_high_risk_domain():
    """3PWR-FR-058: a bug fix in a payment/checkout flow → defect kind, High-risk tier."""
    wk = workkind.classify("fix the null-pointer bug in checkout")
    assert wk.kinds == ["defect"]
    assert wk.suggested_tier == "High-risk"  # 'checkout' is a high-risk domain


def test_classify_docs_is_cosmetic():
    wk = workkind.classify("update the README documentation and the changelog")
    assert wk.kinds == ["docs"]
    assert wk.suggested_tier == "Cosmetic"  # docs/chore-only → Cosmetic


def test_classify_feature_default_standard():
    wk = workkind.classify("add a rate limiter to the public API")
    assert wk.kinds == ["feature"]  # nothing else matched
    assert wk.suggested_tier == "Standard"


def test_classify_design_and_multi_kind():
    wk = workkind.classify("refactor the CSS and fix the broken responsive layout")
    assert "design" in wk.kinds and "defect" in wk.kinds and "refactor" in wk.kinds
    assert wk.suggested_tier == "Standard"


def test_classify_auth_is_high_risk_regardless_of_kind():
    wk = workkind.classify("refactor the authentication session handling")
    assert "refactor" in wk.kinds
    assert wk.suggested_tier == "High-risk"  # auth/session domain wins


def test_cli_classify_json(capsys):
    """3PWR-FR-058: `3pwr classify` surfaces kinds + suggested tier."""
    assert main(["classify", "fix the login bug", "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["kinds"] == ["defect"]
    assert out["suggested_tier"] == "High-risk"  # 'login' domain


def test_discovery_enabled_by_kind():
    """Plan 034 phase 5: discovery runs iff any inferred kind is feature/design."""
    assert workkind.discovery_enabled(["feature"], override=None) is True
    assert workkind.discovery_enabled(["defect"], override=None) is False
    assert workkind.discovery_enabled(["docs", "chore"], override=None) is False
    assert workkind.discovery_enabled(["design", "chore"], override=None) is True


def test_discovery_override_wins_over_kind():
    """Plan 034 phase 5: an explicit --discovery/--no-discovery override beats the work-kind gate."""
    assert workkind.discovery_enabled(["feature"], override=False) is False
    assert workkind.discovery_enabled(["defect"], override=True) is True
