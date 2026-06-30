"""Config tests: root discovery, the single threshold table, and model diversity (3PWR-FR-022/032)."""

from __future__ import annotations

import pytest

from threepowers.config import Settings, find_root, model_diversity_ok, tier_config


def test_find_root_walks_up(tmp_path):
    (tmp_path / ".3powers").mkdir()
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert find_root(deep) == tmp_path


def test_find_root_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_root(tmp_path)


def test_tier_config_lookup():
    tiers = {"tiers": {"Standard": {"diff_coverage": 80}}}
    assert tier_config(tiers, "Standard")["diff_coverage"] == 80
    with pytest.raises(KeyError):
        tier_config(tiers, "Nope")


def test_model_diversity(tmp_path):
    roles = {
        "roles": {
            "coder": {"model_family": "openai"},
            "oracle": {"model_family": "anthropic"},
            "blank": {"model_family": ""},
        }
    }
    assert model_diversity_ok(roles, "oracle", "coder")  # 3PWR-FR-022: different families
    assert not model_diversity_ok(roles, "coder", "coder")  # same family
    assert not model_diversity_ok(roles, "blank", "coder")  # unknown family => not safe


def test_settings_paths_and_missing_yaml(tmp_path):
    (tmp_path / ".3powers").mkdir()
    s = Settings(root=tmp_path)
    assert s.ledger_path.name == "ledger.jsonl"
    assert s.pubkey_path.parent.name == "keys"
    assert s.load_risk_tiers() == {} and s.load_roles() == {}
