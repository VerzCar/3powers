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


def _write(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_auto_fix_defaults_when_absent(tmp_path):
    """A repo with no auto-fix.yaml resolves the shipped defaults: the run-path loop is on, the
    budget is 3, and dispatch is not scoped to the failed gates' files."""
    (tmp_path / ".3powers").mkdir()
    prefs = Settings(root=tmp_path).auto_fix()
    assert prefs.enabled is True
    assert prefs.max_attempts == 3
    assert prefs.scope_to_failed is False


def test_auto_fix_reads_and_clamps_values(tmp_path):
    """auto-fix.yaml values are honored; an out-of-range budget clamps to the default."""
    _write(
        tmp_path / ".3powers" / "config" / "auto-fix.yaml",
        "enabled: false\nmax_attempts: 5\nscope_to_failed: true\n",
    )
    prefs = Settings(root=tmp_path).auto_fix()
    assert prefs.enabled is False
    assert prefs.max_attempts == 5
    assert prefs.scope_to_failed is True

    _write(
        tmp_path / ".3powers" / "config" / "auto-fix.yaml",
        "max_attempts: 0\n",
    )
    assert Settings(root=tmp_path).auto_fix().max_attempts == 3  # clamped away from < 1


def test_auto_fix_tolerates_malformed_file(tmp_path):
    """A malformed or wrong-shape auto-fix.yaml falls back to the defaults, never raises."""
    _write(tmp_path / ".3powers" / "config" / "auto-fix.yaml", "max_attempts: not-a-number\n")
    prefs = Settings(root=tmp_path).auto_fix()
    assert prefs.enabled is True and prefs.max_attempts == 3


def test_subagent_models_optional_and_additive(tmp_path):
    """Plan 036 Track D: an absent block yields {}; blank keys/values are dropped; declared entries
    parse — additive and off by default, so unset changes nothing."""
    (tmp_path / ".3powers").mkdir()
    s = Settings(root=tmp_path)
    assert s.subagent_models() == {}
    _write(
        s.roles_path,
        "roles:\n  coder: {integration: claude}\n"
        "subagent_models:\n  implement: anthropic/claude-haiku-4-5\n  plan: ''\n  '': x\n",
    )
    assert s.subagent_models() == {"implement": "anthropic/claude-haiku-4-5"}


def test_subagent_model_warnings_reports_unknown_for_known_integration(tmp_path):
    """Plan 036 Track D (REQ-D): a sub-agent model absent from a curated catalog for the dispatching
    integration is reported (advisory); a catalog-listed model warns nothing."""
    (tmp_path / ".3powers").mkdir()
    s = Settings(root=tmp_path)
    _write(
        s.models_catalog_path,
        "version: 1\nintegrations:\n  claude:\n    default: anthropic/claude-opus-4-8\n"
        "    models:\n      - {model: anthropic/claude-opus-4-8, family: anthropic, label: Opus}\n"
        "      - {model: anthropic/claude-haiku-4-5, family: anthropic, label: Haiku}\n",
    )
    _write(
        s.roles_path,
        "roles:\n  coder: {integration: claude}\n  oracle: {integration: claude}\n"
        "subagent_models:\n  implement: anthropic/claude-haiku-4-5\n  plan: anthropic/typo-model\n",
    )
    warnings = s.subagent_model_warnings()
    assert len(warnings) == 1
    assert "plan" in warnings[0] and "typo-model" in warnings[0]


def test_subagent_model_warnings_silent_for_byok_integration(tmp_path):
    """Plan 036 Track D: a free-form BYOK integration (no curated catalog list) never warns — the
    model is used as-is, matching the existing model-pin tolerance."""
    (tmp_path / ".3powers").mkdir()
    s = Settings(root=tmp_path)
    _write(
        s.models_catalog_path,
        "version: 1\nintegrations:\n  opencode: {default: '', models: []}\n",
    )
    _write(
        s.roles_path,
        "roles:\n  coder: {integration: opencode}\nsubagent_models:\n  implement: whatever/model\n",
    )
    assert s.subagent_model_warnings() == []
