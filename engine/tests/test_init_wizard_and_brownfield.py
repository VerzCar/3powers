"""The `3pwr init` judiciary wizard, notification setup, and the spec-less brownfield on-ramp.

Covers the guided-setup additions (AGENTX-FR-011/012, 3PWR-FR-022), notification channel setup
(STEER-FR-010/NFR-002), spec-less report-only/diff-scope gate runs (3PWR-FR-051/052), and the
directory-aware `characterize` (3PWR-FR-053).
"""

from __future__ import annotations

import yaml

from threepowers import characterize, cli, notify, scaffold, style
from threepowers.config import Settings, model_diversity_ok
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_SKIP


def _feed(monkeypatch, answers):
    """Drive the interactive prompts; any prompt past ``answers`` accepts the default (empty)."""
    it = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *a, **k: next(it, ""))


def _seeded(tmp_path):
    """A project with the baseline config seeded (roles.yaml + models.yaml present)."""
    s = Settings(root=tmp_path)
    scaffold.seed_config(s)
    return s


# --------------------------------------------------------------------------- _ask_multi
def test_ask_multi_non_interactive_returns_in_option_defaults():
    """AGENTX-NFR-004: no TTY → the (valid) defaults verbatim, no prompt."""
    got = cli._ask_multi("pick", ["a", "b", "c"], ["b", "zzz"], interactive=False)
    assert got == ["b"]  # zzz is not an option and is dropped


def test_ask_multi_parses_indices_names_and_empty(monkeypatch):
    """AGENTX-FR-011: accepts space/comma indices or names; empty keeps the defaults."""
    _feed(monkeypatch, ["1, 3"])
    assert cli._ask_multi("pick", ["a", "b", "c"], ["a"], interactive=True) == ["a", "c"]
    _feed(monkeypatch, ["b c"])
    assert cli._ask_multi("pick", ["a", "b", "c"], ["a"], interactive=True) == ["b", "c"]
    _feed(monkeypatch, [""])  # empty → defaults
    assert cli._ask_multi("pick", ["a", "b", "c"], ["a", "b"], interactive=True) == ["a", "b"]


# --------------------------------------------------------------------------- scaffold writers
def test_set_headless_integrations_dedupes_and_preserves_other_fields(tmp_path):
    """EXEC-FR-015: the selection is recorded; diversity_level and roles are untouched."""
    s = _seeded(tmp_path)
    scaffold.set_headless_integrations(s, ["claude", "copilot", "claude", " "])
    data = yaml.safe_load(s.roles_path.read_text(encoding="utf-8"))
    assert data["headless_integrations"] == ["claude", "copilot"]
    assert data["diversity_level"] == "family"  # preserved
    assert "roles" in data
    # An empty selection never wipes the recorded set.
    scaffold.set_headless_integrations(s, [])
    assert yaml.safe_load(s.roles_path.read_text())["headless_integrations"] == ["claude", "copilot"]


def test_set_diversity_level_validates(tmp_path):
    """3PWR-FR-022: family|model accepted, anything else ignored (file keeps a valid level)."""
    s = _seeded(tmp_path)
    scaffold.set_diversity_level(s, "model")
    assert yaml.safe_load(s.roles_path.read_text())["diversity_level"] == "model"
    scaffold.set_diversity_level(s, "bogus")
    assert yaml.safe_load(s.roles_path.read_text())["diversity_level"] == "model"


def test_set_notification_channel_replaces_by_type_and_stores_no_secret(tmp_path):
    """STEER-FR-010/NFR-002: a slack block carries webhook_env only; re-setting replaces, not dupes."""
    s = _seeded(tmp_path)
    scaffold.set_notification_channel(
        s, {"type": "slack", "events": ["gate"], "webhook_env": "THREEPOWERS_SLACK_WEBHOOK"}
    )
    scaffold.set_notification_channel(
        s, {"type": "slack", "events": ["gate", "failure"], "webhook_env": "MY_HOOK"}
    )
    data = yaml.safe_load(s.notifications_config_path.read_text(encoding="utf-8"))
    slack = [c for c in data["channels"] if c["type"] == "slack"]
    assert len(slack) == 1 and slack[0]["webhook_env"] == "MY_HOOK"
    raw = s.notifications_config_path.read_text(encoding="utf-8")
    assert "https://" not in raw and "hooks.slack" not in raw  # no secret value on disk


# --------------------------------------------------------------------------- guided roles flow
def test_roles_flow_copilot_only_is_family_diverse_by_default(tmp_path, monkeypatch):
    """3PWR-FR-022: one BYOK integration, family-aware defaults → diverse with no second CLI.

    Reproduces the copilot-only setup: coder and oracle both dispatch through `copilot`, but the
    judiciary default lands in a different model family, so `family` diversity holds."""
    s = _seeded(tmp_path)
    st = style.Styler(enabled=False)
    _feed(monkeypatch, ["copilot"])  # select copilot; every later prompt takes its default
    report = cli._roles_setup_flow(s, st, interactive=True)

    assert report["integrations"] == ["copilot"]
    assert s.role("coder")["integration"] == "copilot"
    assert s.role("oracle")["integration"] == "copilot"
    coder_fam = s.role("coder").get("model_family")
    oracle_fam = s.role("oracle").get("model_family")
    assert coder_fam and oracle_fam and coder_fam != oracle_fam
    roles = s.load_roles()
    assert model_diversity_ok(roles, "coder", "oracle", s.diversity_level())
    assert s.diversity_level() == "family"


def test_roles_flow_records_selected_headless_integrations(tmp_path, monkeypatch):
    """EXEC-FR-015: the multi-selected CLIs are persisted to headless_integrations."""
    s = _seeded(tmp_path)
    st = style.Styler(enabled=False)
    _feed(monkeypatch, ["claude, copilot"])
    cli._roles_setup_flow(s, st, interactive=True)
    assert set(s.load_roles()["headless_integrations"]) >= {"claude", "copilot"}


# --------------------------------------------------------------------------- notifications flow
def test_notifications_none_by_default_and_non_interactive(tmp_path):
    """STEER-FR-010: non-interactive writes nothing — notifications stay off."""
    s = _seeded(tmp_path)
    st = style.Styler(enabled=False)
    report = cli._notifications_setup_flow(s, st, interactive=False)
    assert report["channel"] == "none"
    data = yaml.safe_load(s.notifications_config_path.read_text(encoding="utf-8"))
    assert data.get("channels") == []


def test_notifications_slack_records_env_not_url(tmp_path, monkeypatch):
    """STEER-NFR-002: picking slack records the env-var name, never a webhook URL."""
    s = _seeded(tmp_path)
    st = style.Styler(enabled=False)
    _feed(monkeypatch, ["slack", ""])  # choose slack, accept the default env-var name
    report = cli._notifications_setup_flow(s, st, interactive=True)
    assert report["channel"] == "slack"
    channels, warns = notify.load_channels(s.notifications_config_path)
    assert warns == [] and len(channels) == 1 and channels[0].type == "slack"
    assert channels[0].options["webhook_env"] == "THREEPOWERS_SLACK_WEBHOOK"


# --------------------------------------------------------------------------- spec-less gate run
_RISK = "tiers:\n  T: { diff_coverage: 0, gates: [spec_integrity, spec_conformance] }\n"


def _spec_gate_project(tmp_path):
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(_RISK, encoding="utf-8")
    (tp / "adapters" / "a" / "adapter.yaml").write_text(
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\ngates: {}\n', encoding="utf-8"
    )
    proj = tmp_path / "p"
    (proj / "tests").mkdir(parents=True)
    (proj / "d").write_text("")
    return Settings(root=tmp_path), proj


def test_gate_run_without_spec_skips_spec_bound_gates(tmp_path):
    """3PWR-FR-052: a brownfield report-only run has no spec — the two spec gates SKIP, not error."""
    s, proj = _spec_gate_project(tmp_path)
    v = run_gates(s, proj, tier="T", spec_path=None, adapter_name="a", report_only=True)
    integ = next(g for g in v.gates if g.gate == "spec_integrity")
    conf = next(g for g in v.gates if g.gate == "spec_conformance")
    assert integ.status == STATUS_SKIP and conf.status == STATUS_SKIP
    assert v.spec_id in ("", "?", None)


def test_cmd_gate_run_report_only_needs_no_spec(tmp_path, capsys):
    """3PWR-FR-052 end-to-end: `gate run --report-only` on a spec-less repo exits 0."""
    s, proj = _spec_gate_project(tmp_path)
    rc = cli.main(
        [
            "--root", str(tmp_path), "gate", "run", "--path", str(proj),
            "--tier", "T", "--adapter", "a", "--report-only", "--no-ledger",
        ]
    )
    assert rc == 0, capsys.readouterr().out


# --------------------------------------------------------------------------- directory characterize
def test_characterize_path_walks_a_directory(tmp_path):
    """3PWR-FR-053: a directory yields one spec+oracle per source file, skipping tests/vendored."""
    src = tmp_path / "src"
    (src / "pkg").mkdir(parents=True)
    (src / "a.py").write_text("def one():\n    return 1\n", encoding="utf-8")
    (src / "pkg" / "b.py").write_text("def two():\n    return 2\n", encoding="utf-8")
    (src / "test_a.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (src / "node_modules").mkdir()
    (src / "node_modules" / "dep.py").write_text("def skip():\n    return 0\n", encoding="utf-8")

    results = characterize.characterize_path(tmp_path, src, specs_dir=tmp_path / "specs")
    spec_ids = sorted(r.spec_id for r in results)
    assert spec_ids == ["A", "B"]  # a.py + pkg/b.py; test file and node_modules skipped


def test_characterize_single_file_still_one_result(tmp_path):
    """3PWR-FR-053: a file target keeps single-file behavior (one result)."""
    f = tmp_path / "money.py"
    f.write_text("def total():\n    return 0\n", encoding="utf-8")
    results = characterize.characterize_path(tmp_path, f, specs_dir=tmp_path / "specs")
    assert len(results) == 1 and results[0].spec_id == "MONEY"
