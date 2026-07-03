"""Init experience — config-driven setup, model-pinned judiciary agents, workflow extensions, a
first-run readiness gate, colorized output, and config-drift detection (INITX-FR-001…016, NFR-001…006).

These drive the engine headlessly (pytest has no TTY, so ``3pwr init`` is non-interactive and applies
defaults) and assert the resulting configuration, agent, and output state.
"""

from __future__ import annotations

import io
import json
import subprocess
from argparse import Namespace
from pathlib import Path

from threepowers import agentpins, configdrift, scaffold, style
from threepowers.cli import _maybe_warn_config_drift, main
from threepowers.config import Settings


def _init(root, *extra, key=None):
    argv = ["--root", str(root), "init", "--yes"]
    if key is not None:
        argv += ["--key-path", str(key)]
    return main(argv + list(extra))


def _agent_file(agents_dir: Path, name: str) -> Path:
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / name
    path.write_text(
        "---\n"
        'description: "judiciary agent"\n'
        "handoffs:\n"
        "  - label: Next\n"
        "    agent: other\n"
        "---\n\n"
        "## body\n",
        encoding="utf-8",
    )
    return path


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
    assert pin["integration"] == "copilot"
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


# --------------------------------------------------------------------------- INITX-FR-004, NFR-005/006 (agent pins)
def test_render_pins_judiciary_agents_only(tmp_path):
    """INITX-FR-004: the oracle + review agents get an explicit model selector; others are untouched."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    agents = agentpins.agents_dir(root)
    _agent_file(agents, "3pwr.oracle.agent.md")
    _agent_file(agents, "3pwr.review.agent.md")
    other = _agent_file(agents, "speckit.implement.agent.md")
    before_other = other.read_text(encoding="utf-8")

    statuses = agentpins.render_all(Settings(root=root), root)
    assert statuses == {"oracle": "created", "reviewer": "created"}
    oracle_text = (agents / "3pwr.oracle.agent.md").read_text(encoding="utf-8")
    assert "model: Claude Opus 4.8 (copilot)" in oracle_text
    assert "3pwr:managed-model" in oracle_text
    # the pin sits inside the frontmatter (before the closing fence)
    assert oracle_text.index("model:") < oracle_text.index("\n---")
    assert other.read_text(encoding="utf-8") == before_other  # non-judiciary agent unchanged


def test_render_pins_idempotent_and_deterministic(tmp_path):
    """INITX-NFR-005: re-rendering from unchanged config is byte-identical (kept, no rewrite)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    agents = agentpins.agents_dir(root)
    path = _agent_file(agents, "3pwr.oracle.agent.md")
    _agent_file(agents, "3pwr.review.agent.md")

    s = Settings(root=root)
    agentpins.render_all(s, root)
    first = path.read_text(encoding="utf-8")
    second_status = agentpins.render_all(s, root)
    assert second_status["oracle"] == "kept"
    assert path.read_text(encoding="utf-8") == first  # unchanged


def test_render_does_not_clobber_hand_edited_pin(tmp_path):
    """INITX-NFR-006: a hand-edited model line is never overwritten without --force."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    agents = agentpins.agents_dir(root)
    path = agents / "3pwr.oracle.agent.md"
    agents.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '---\ndescription: "x"\nmodel: MyHandPick (copilot)\n---\nbody\n', encoding="utf-8"
    )
    s = Settings(root=root)
    assert agentpins.render_all(s, root)["oracle"] == "skipped"
    assert "MyHandPick (copilot)" in path.read_text(encoding="utf-8")
    # with force it is updated
    assert agentpins.render_all(s, root, force=True)["oracle"] == "updated"
    assert "Claude Opus 4.8 (copilot)" in path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- INITX-FR-005/007/008 (extension)
def test_install_speckit_extension_renders_from_config(tmp_path):
    """INITX-FR-008: installed templates are rendered from config — no hardcoded literal, no placeholder."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / ".specify").mkdir()  # a Spec Kit workspace is present

    result = scaffold.install_speckit_extension(Settings(root=root), root)
    assert result["status"] == "installed"
    ext_dir = scaffold.speckit_extension_dir(root)
    manifest = (ext_dir / "extension.yml").read_text(encoding="utf-8")
    gaps = (ext_dir / "commands" / "3pwr.tests-gaps.md").read_text(encoding="utf-8")
    # rendered, not hardcoded (INITX-FR-008)
    assert "{{" not in manifest and "{{" not in gaps
    assert "model: Claude Opus 4.8 (copilot)" in gaps
    assert "GPT-5.5" not in gaps  # the bundle's old hardcoded literal is gone
    # test-first hook precedes implementation (INITX-FR-005)
    assert "after_plan" in manifest
    # read-only conformance dry-run (INITX-FR-007)
    assert "3pwr conformance" in gaps


def test_install_speckit_extension_requires_workspace(tmp_path):
    """INITX-FR-005: with no Spec Kit workspace, installation is reported, never fabricated."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert scaffold.install_speckit_extension(Settings(root=root), root)["status"] == "no-speckit"


# --------------------------------------------------------------------------- INITX-FR-005 / RUNX-FR-009 (workflows)
def test_install_speckit_workflows_copies_verbatim(tmp_path):
    """INITX-FR-005: init lays the lifecycle + oracle workflows `3pwr run` dispatches, VERBATIM — the
    Spec Kit `{{ inputs.* }}` run-time tokens survive un-rendered (unlike the extension templates)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / ".specify").mkdir()  # a Spec Kit workspace is present

    result = scaffold.install_speckit_workflows(root)
    assert result["status"] == "installed"
    wf_dir = scaffold.speckit_workflows_dir(root) / "3powers"
    lifecycle = (wf_dir / "lifecycle.yml").read_text(encoding="utf-8")
    oracle_wf = (wf_dir / "oracle.yml").read_text(encoding="utf-8")
    # the run-time input token is preserved (NOT rendered/stripped) — needed by `specify workflow run`
    assert "{{ inputs.integration }}" in lifecycle
    assert "3powers-lifecycle" in lifecycle
    assert "3powers-oracle" in oracle_wf


def test_install_speckit_workflows_satisfies_run_preflight(tmp_path):
    """RUNX-FR-009: once the workflow is provisioned, the `3pwr run` preflight's lifecycle-workflow
    prerequisite is met — previously it failed even after `3pwr init --with-speckit`."""
    from threepowers import runpreflight

    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / ".specify").mkdir()
    scaffold.install_speckit_workflows(root)

    wf_path = root / ".specify" / "workflows" / "3powers" / "lifecycle.yml"
    prqs = runpreflight.check(
        Settings(root=root),
        workflow_path=wf_path,
        coder_integration="claude",
        oracle_integration="gemini",
        entries=[],
        spec_id="RUN",
        specify_present=True,
    )
    wf_prq = next(p for p in prqs if p.name == "lifecycle workflow")
    assert wf_prq.ok


def test_install_speckit_workflows_requires_workspace(tmp_path):
    """INITX-FR-005: with no Spec Kit workspace, workflow install is reported, never fabricated."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert scaffold.install_speckit_workflows(root)["status"] == "no-speckit"


def test_install_speckit_workflows_is_non_destructive(tmp_path):
    """INITX-NFR-006: a hand-edited workflow is kept on re-install unless forced."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    (root / ".specify").mkdir()
    scaffold.install_speckit_workflows(root)
    wf = root / ".specify" / "workflows" / "3powers" / "lifecycle.yml"
    wf.write_text("# hand-edited\n", encoding="utf-8")

    again = scaffold.install_speckit_workflows(root)
    assert again["files"]["3powers/lifecycle.yml"] == "kept"
    assert wf.read_text(encoding="utf-8") == "# hand-edited\n"
    scaffold.install_speckit_workflows(root, force=True)
    assert "3powers-lifecycle" in wf.read_text(encoding="utf-8")


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
        "Spec Kit workspace",
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


# --------------------------------------------------------------------------- INITX-FR-015/016 (config drift)
def test_config_drift_detected_after_edit(tmp_path):
    """INITX-FR-015: editing a tracked config file is detected against the recorded fingerprint."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    s = Settings(root=root)
    assert configdrift.detect(s) == []  # freshly recorded — no drift
    s.roles_path.write_text(
        s.roles_path.read_text(encoding="utf-8") + "\n# tweak\n", encoding="utf-8"
    )
    assert configdrift.detect(s) == ["roles.yaml"]


def test_drift_warns_to_stderr_and_touches_no_agent(tmp_path, capsys):
    """INITX-FR-016: drift warns (stderr) + points to `config apply`; it never regenerates an agent."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    agents = agentpins.agents_dir(root)
    oracle = _agent_file(agents, "3pwr.oracle.agent.md")
    before = oracle.read_text(encoding="utf-8")
    # edit a tracked config file
    s = Settings(root=root)
    s.roles_path.write_text(s.roles_path.read_text(encoding="utf-8") + "\n# tweak\n", "utf-8")

    args = Namespace(root=str(root), json=False)
    _maybe_warn_config_drift(args)
    err = capsys.readouterr().err
    assert "config changed" in err
    assert "roles.yaml" in err
    assert "3pwr config apply" in err
    assert oracle.read_text(encoding="utf-8") == before  # agent file untouched


def test_no_drift_warning_when_unchanged(tmp_path, capsys):
    """INITX-FR-015: an unchanged config produces no drift signal."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    _maybe_warn_config_drift(Namespace(root=str(root), json=False))
    assert "config changed" not in capsys.readouterr().err


def test_config_apply_re_renders_pins_and_clears_drift(tmp_path, capsys):
    """INITX-FR-016: `config apply` re-renders the pins and clears the stale-config warning."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    agents = agentpins.agents_dir(root)
    _agent_file(agents, "3pwr.oracle.agent.md")
    _agent_file(agents, "3pwr.review.agent.md")
    s = Settings(root=root)
    s.roles_path.write_text(s.roles_path.read_text(encoding="utf-8") + "\n# tweak\n", "utf-8")
    assert configdrift.detect(s) == ["roles.yaml"]

    capsys.readouterr()  # flush the init output
    rc = main(["--root", str(root), "config", "apply", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["pins"]["oracle"] == "created"
    # fingerprint re-recorded → the drift is cleared
    assert configdrift.detect(s) == []
    assert "model: Claude Opus 4.8 (copilot)" in (agents / "3pwr.oracle.agent.md").read_text(
        "utf-8"
    )


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
        "integration": "copilot",
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
