"""Init experience — config-driven setup, a first-run readiness gate, colorized output, and
per-stage auto-commit (INITX-FR-001…014, NFR-001…004).

These drive the engine headlessly (pytest has no TTY, so ``3pwr init`` is non-interactive and applies
defaults) and assert the resulting configuration and output state.

Note: the judiciary agent-file model pins (INITX-FR-004) and config-drift detection (INITX-FR-015/016)
were retired by DOCX (spec 012) — see ``plan/022-docs-and-decruft.md``. They existed only to keep the
Spec-Kit-dispatched ``.github/agents/3pwr.*.agent.md`` pins fresh; nothing in the native executive reads
that frontmatter (it reads ``.3powers/agents/*.yaml`` + ``roles.yaml``), so both are moot.
"""

from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

from threepowers import scaffold, style
from threepowers.cli import main
from threepowers.config import Settings


def _init(root, *extra, key=None):
    argv = ["--root", str(root), "init", "--yes"]
    if key is not None:
        argv += ["--key-path", str(key)]
    return main(argv + list(extra))


# --------------------------------------------------------------------------- INITX-FR-013/014, NFR-004 (color)
def test_styler_disabled_is_transparent_noop():
    """INITX-NFR-004: a disabled styler never emits escape codes and never fails."""
    st = style.Styler(enabled=False)
    assert st.ok("x") == "x"
    assert st.bold("x") == "x"
    assert st.mark("pass") == "✓"  # glyph without color
    assert "\033[" not in st.err("boom")


def test_styler_enabled_wraps_ansi():
    """INITX-FR-013: an enabled styler colorizes status markers and emphasis."""
    st = style.Styler(enabled=True)
    assert "\033[32m" in st.ok("x")  # green
    assert "\033[31m" in st.mark("fail")  # red ✗
    assert st.paint("x") == "x"  # no code names → unchanged


def test_color_disabled_for_json_and_nontty_and_no_color(monkeypatch):
    """INITX-FR-014: color is off for --json, a non-TTY stream, --yes, or NO_COLOR."""
    monkeypatch.delenv("THREEPOWERS_FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    nontty = io.StringIO()  # isatty() is False
    assert style.color_enabled(nontty, as_json=True) is False
    assert style.color_enabled(nontty, assume_yes=True) is False
    assert style.color_enabled(nontty) is False  # not a tty
    monkeypatch.setenv("NO_COLOR", "1")
    assert style.color_enabled(nontty) is False


def test_json_output_wins_over_force_color(monkeypatch):
    """INITX-FR-014 (property): machine-readable output is never colored, even under FORCE_COLOR."""
    monkeypatch.setenv("THREEPOWERS_FORCE_COLOR", "1")
    assert style.color_enabled(as_json=True) is False
    assert style.color_enabled(assume_yes=True) is False


def test_init_json_payload_has_no_ansi(tmp_path, capsys, monkeypatch):
    """INITX-SC-004: the --json payload contains no color escape codes (parseable + reproducible)."""
    monkeypatch.setenv("THREEPOWERS_FORCE_COLOR", "1")  # even forced, json stays clean
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    out = capsys.readouterr().out
    assert "\033[" not in out
    payload = json.loads(out)  # still valid JSON
    assert payload["tier"] == "Standard"


# --------------------------------------------------------------------------- INITX-FR-002/003 (roles schema)
def test_default_roles_carry_concrete_judiciary_model(tmp_path):
    """INITX-FR-002/003: accepting defaults yields a concrete oracle pin (model + integration + label)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    pin = Settings(root=root).role_model_pin("oracle")
    assert pin is not None
    assert pin["model"] == "anthropic/claude-opus-4-8"
    assert pin["integration"] == "claude"
    assert pin["label"] == "Claude Opus 4.8"


def test_family_only_roles_still_load(tmp_path):
    """INITX-FR-003 (property): a pre-existing family-only roles config still loads; pin is None."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    s = Settings(root=root)
    s.roles_path.write_text(
        "version: 1\ndiversity_level: family\nroles:\n"
        '  coder: {model_family: "openai"}\n'
        '  oracle: {model_family: "anthropic"}\n',
        encoding="utf-8",
    )
    assert s.role_model_pin("oracle") is None  # no concrete model — never raises
    assert s.coder_family() == "openai"


def test_customize_oracle_model_via_flags(tmp_path):
    """INITX-FR-002/003: the judiciary model can be set non-interactively and is recorded in roles.yaml."""
    root = tmp_path / "proj"
    root.mkdir()
    assert (
        _init(
            root,
            "--language",
            "python",
            "--oracle-model",
            "anthropic/claude-sonnet-5",
            "--oracle-integration",
            "claude",
            "--oracle-label",
            "Claude Sonnet 5",
            key=tmp_path / "k.key",
        )
        == 0
    )
    pin = Settings(root=root).role_model_pin("oracle")
    assert pin == {
        "model": "anthropic/claude-sonnet-5",
        "integration": "claude",
        "label": "Claude Sonnet 5",
    }


def test_oracle_sharing_coder_family_warns_but_proceeds(tmp_path, capsys):
    """INITX-FR-002: a judiciary model in the coder's family warns (never silently) but still proceeds."""
    root = tmp_path / "proj"
    root.mkdir()
    rc = _init(
        root,
        "--language",
        "python",
        "--oracle-model",
        "openai/gpt-5.5",  # coder family is openai
        key=tmp_path / "k.key",
    )
    assert rc == 0  # recommended, not forced (3PWR-FR-022/057)
    err = capsys.readouterr().err
    assert "shares the coder's family" in err
    assert "deviation" in err  # names the recorded-deviation path


# NOTE: the Spec Kit extension/workflow install tests were removed with the substrate (SLIM, spec 010).
# The native executive seeds agent manifests instead — see test_native_runner.py.


def test_conformance_dry_run_names_untested_requirement(tmp_path):
    """INITX-FR-007: the dry-run names a requirement with no linked test and exits non-zero."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    spec = root / "specs" / "demo" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "**Spec ID**: DEMO\n\n### Functional Requirements\n"
        "- **DEMO-FR-001**: The system shall do a thing.\n",
        encoding="utf-8",
    )
    rc = main(["--root", str(root), "conformance", "--spec", str(spec)])
    assert rc == 1  # a requirement has no linked test


# --------------------------------------------------------------------------- INITX-FR-006 (auto-commit)
def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _git_repo(root: Path) -> None:
    _git(root, "init")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Test")


def test_commit_stage_makes_one_tagged_commit(tmp_path):
    """INITX-FR-006: a completed stage yields one commit tagged with the spec id + stage."""
    root = tmp_path / "proj"
    root.mkdir()
    _git_repo(root)
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / "feature.txt").write_text("work\n", encoding="utf-8")
    _git(root, "add", "feature.txt")
    rc = main(["--root", str(root), "commit-stage", "--stage", "plan", "--spec-id", "INITX"])
    assert rc == 0
    log = _git(root, "log", "--oneline", "-1").stdout
    assert "3pwr(INITX): plan" in log


def test_commit_stage_no_commit_when_nothing_staged(tmp_path):
    """INITX-FR-006: a failed / no-op stage (nothing staged) yields no commit."""
    root = tmp_path / "proj"
    root.mkdir()
    _git_repo(root)
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / "x.txt").write_text("x\n", encoding="utf-8")
    _git(root, "add", "x.txt")
    _git(root, "commit", "-m", "base")
    before = _git(root, "rev-list", "--count", "HEAD").stdout.strip()
    rc = main(["--root", str(root), "commit-stage", "--stage", "implement", "--spec-id", "INITX"])
    assert rc == 0
    after = _git(root, "rev-list", "--count", "HEAD").stdout.strip()
    assert before == after  # nothing staged → no new commit


# --------------------------------------------------------------------------- INITX-FR-009/010/011/012 (readiness)
def test_detect_ci_recognizes_common_platforms(tmp_path):
    """INITX-FR-010 (property): CI presence is by a recognized config, independent of platform."""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert scaffold.detect_ci(empty) is False

    gha = tmp_path / "gha"
    (gha / ".github" / "workflows").mkdir(parents=True)
    (gha / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    assert scaffold.detect_ci(gha) is True

    gl = tmp_path / "gl"
    gl.mkdir()
    (gl / ".gitlab-ci.yml").write_text("stages: [test]\n", encoding="utf-8")
    assert scaffold.detect_ci(gl) is True


def test_checklist_flags_missing_ci_as_mandatory(tmp_path, capsys):
    """INITX-FR-009 / INITX-FR-010 / SC-003: the readiness checklist is emitted (no item omitted) and a
    missing CI/CD config is flagged as a mandatory prerequisite."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    report = json.loads(capsys.readouterr().out)
    items = {i["item"] for i in report["checklist"]}
    # no checklist item is silently omitted (INITX-FR-009)
    assert {
        "CI/CD pipeline",
        "3Powers constitution",
        "AGENTS.md",
        "Judiciary model diversity",
    } <= items
    ci = next(i for i in report["checklist"] if i["item"] == "CI/CD pipeline")
    assert ci["status"] == "fail"
    assert "required for secure gates" in ci["detail"]


def test_checklist_ci_present_passes(tmp_path, capsys):
    """INITX-FR-010: a repo with a recognized CI config marks the item satisfied."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("on: push\n", encoding="utf-8")
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    report = json.loads(capsys.readouterr().out)
    ci = next(i for i in report["checklist"] if i["item"] == "CI/CD pipeline")
    assert ci["status"] == "pass"


def test_checklist_flags_agents_md_starter_as_todo(tmp_path, capsys):
    """INITX-FR-011 / SC-003: a generated AGENTS.md starter is flagged as an unfinished TODO."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    report = json.loads(capsys.readouterr().out)
    agents = next(i for i in report["checklist"] if i["item"] == "AGENTS.md")
    assert agents["status"] == "todo"
    assert scaffold.agents_md_is_starter(root) is True

    # once the placeholders are filled, it is no longer a TODO
    (root / "AGENTS.md").write_text("# Real project docs\nUse 3pwr run.\n", encoding="utf-8")
    assert scaffold.agents_md_is_starter(root) is False


def test_next_steps_are_explained_not_bare(tmp_path, capsys):
    """INITX-FR-012 / SC-006: brownfield and greenfield next steps carry a per-step explanation."""
    brown = tmp_path / "brown"
    brown.mkdir()
    (brown / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert _init(brown, key=tmp_path / "kb.key") == 0
    out = capsys.readouterr().out
    assert "Existing project detected" in out
    assert "report-only" in out and "characterize" in out
    assert "see your current gate debt" in out  # explanation, not a bare command

    green = tmp_path / "green"
    green.mkdir()
    assert _init(green, "--language", "python", key=tmp_path / "kg.key") == 0
    out = capsys.readouterr().out
    assert "author your first spec" in out and "3pwr run" in out
    assert "one command drives" in out


# --------------------------------------------------------------------------- INITX-FR-001, NFR-001/002/003
def test_default_flow_makes_no_network_call(tmp_path, monkeypatch):
    """INITX-NFR-001: the default flow completes fully offline (a blocked socket does not stop it)."""
    import socket

    def _no_network(*_a, **_k):
        raise RuntimeError("network access attempted during init")

    monkeypatch.setattr(socket, "socket", _no_network)
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0


def test_noninteractive_defaults_match_recommended(tmp_path):
    """INITX-NFR-003: a non-interactive run degrades to the recommended defaults (equivalent config)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    s = Settings(root=root)
    assert s.default_tier() == "Standard"  # the recommended default
    assert s.role_model_pin("oracle") == {
        "model": "anthropic/claude-opus-4-8",
        "integration": "claude",
        "label": "Claude Opus 4.8",
    }


def test_default_tier_recorded_and_never_weakens_thresholds(tmp_path):
    """INITX-FR-001 / INITX-NFR-002: the default tier is recorded; no threshold is lowered by the flow."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--tier", "High-risk", key=tmp_path / "k.key") == 0
    s = Settings(root=root)
    assert s.default_tier() == "High-risk"
    tiers = s.load_risk_tiers()["tiers"]
    assert tiers["Standard"]["diff_coverage"] == 80  # unchanged
    assert tiers["High-risk"]["mutation_score"] == 70  # unchanged


def test_auto_commit_default_is_on(tmp_path):
    """INITX-FR-006: per-stage auto-commit is on by default (the wanted workflow)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert Settings(root=root).auto_commit() is True
