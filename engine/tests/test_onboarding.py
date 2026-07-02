"""Guided onboarding — the interactive ``3pwr init`` wizard (ONBRD-FR-001…010, NFR-001…005).

These drive ``3pwr init`` headlessly (pytest has no TTY, so the wizard is non-interactive and applies
defaults — ONBRD-FR-006) through a temporary project, and assert the resulting trust-spine state.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from threepowers import scaffold
from threepowers.config import Settings
from threepowers.cli import main


def _init(root, *extra, key=None):
    argv = ["--root", str(root), "init", "--yes"]
    if key is not None:
        argv += ["--key-path", str(key)]
    return main(argv + list(extra))


# --------------------------------------------------------------------------- FR-001 / FR-008 / SC-001
def test_greenfield_run_leaves_project_ready(tmp_path):
    """ONBRD-FR-001/008, SC-001: one guided run makes an empty repo ready with no further setup."""
    root = tmp_path / "proj"
    root.mkdir()
    key = tmp_path / "keys" / "signer.key"
    assert _init(root, "--language", "python", key=key) == 0

    s = Settings(root=root)
    assert s.dir.is_dir()
    assert s.ledger_path.exists()
    assert s.pubkey_path.exists()  # public key committed in-repo
    assert s.risk_tiers_path.exists() and s.roles_path.exists()  # baseline config seeded
    assert (s.adapters_dir / "python" / "adapter.yaml").exists()  # selected adapter available
    assert s.onboarding_path.exists()
    assert key.exists()  # private key created OUTSIDE the repo


# --------------------------------------------------------------------------- FR-002
def test_directory_must_exist_and_be_writable(tmp_path):
    """ONBRD-FR-002: a non-existent target directory is a usage error (exit 2)."""
    missing = tmp_path / "nope"
    assert main(["--root", str(missing), "init", "--yes"]) == 2


# --------------------------------------------------------------------------- FR-003
def test_supported_languages_are_adapter_backed_and_selectable(tmp_path):
    """ONBRD-FR-003: the offered languages are exactly the bundled adapters; one is selected."""
    langs = scaffold.bundled_languages()
    assert {"typescript", "python", "go"} <= set(langs)

    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "go", key=tmp_path / "k.key") == 0
    assert (Settings(root=root).adapters_dir / "go" / "adapter.yaml").exists()


def test_unsupported_language_is_rejected(tmp_path):
    """ONBRD-FR-003: an unsupported language is surfaced, never fabricated (exit 2)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "cobol", key=tmp_path / "k.key") == 2
    assert not (Settings(root=root).adapters_dir / "cobol").exists()


# --------------------------------------------------------------------------- FR-004 / FR-007 / NFR-001 / SC-003
def test_key_must_live_outside_the_repo(tmp_path):
    """ONBRD-FR-004, ONBRD-NFR-001, ONBRD-SC-003: a key path inside the repo is refused (exit 2)."""
    root = tmp_path / "proj"
    root.mkdir()
    inside = root / "secret.key"
    assert _init(root, key=inside) == 2
    assert not inside.exists()


def test_is_outside_repo_property(tmp_path):
    """ONBRD-FR-007 (property): every accepted key location resolves outside the repo tree."""
    root = tmp_path / "proj"
    root.mkdir()
    assert scaffold.is_outside_repo(tmp_path / "elsewhere" / "k.key", root)
    assert scaffold.is_outside_repo(scaffold.keys.default_private_path(root), root)
    assert not scaffold.is_outside_repo(root / "k.key", root)
    assert not scaffold.is_outside_repo(root / "sub" / "k.key", root)


def test_existing_key_is_not_clobbered_without_force(tmp_path):
    """ONBRD-FR-007: an existing key is kept; --force regenerates it."""
    root = tmp_path / "proj"
    root.mkdir()
    key = tmp_path / "signer.key"
    assert _init(root, "--language", "python", key=key) == 0
    first = key.read_bytes()

    assert _init(root, "--language", "python", key=key) == 0  # re-run: keep
    assert key.read_bytes() == first

    assert _init(root, "--language", "python", "--force", key=key) == 0  # force: regenerate
    assert key.read_bytes() != first


def test_default_key_path_is_under_home_not_repo(tmp_path, monkeypatch):
    """ONBRD-FR-004: with no --key-path the default is the outside-repo ~/.config/3powers location."""
    # ONBRD-NFR-001: only the public key is committed in-repo; the private key stays outside.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    root = tmp_path / "proj"
    root.mkdir()
    assert main(["--root", str(root), "init", "--yes", "--language", "python"]) == 0
    assert (home / ".config" / "3powers" / "proj.key").exists()
    # And nothing key-shaped landed inside the repo (NFR-001).
    assert not list(root.rglob("*.key"))


def test_existing_env_key_is_not_overridden(tmp_path, monkeypatch):
    """ONBRD-FR-004 edge: a key already resolvable via the environment is not overridden."""
    root = tmp_path / "proj"
    root.mkdir()
    env_key = tmp_path / "env.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(env_key))
    assert main(["--root", str(root), "init", "--yes", "--language", "python"]) == 0
    assert not env_key.exists()  # the wizard minted no competing key
    assert not list(root.rglob("*.key"))


# --------------------------------------------------------------------------- FR-005
@pytest.mark.parametrize("flag,expected", [("--auto-mode", "auto"), ("--no-auto-mode", "commit")])
def test_auto_mode_preference_recorded_and_drives_run_default(tmp_path, flag, expected):
    """ONBRD-FR-005: the autonomy answer is recorded and becomes the default `3pwr run` mode."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", flag, key=tmp_path / "k.key") == 0
    assert Settings(root=root).default_mode() == expected


# --------------------------------------------------------------------------- FR-006 / NFR-003
def test_json_output_is_machine_readable_and_unblocking(tmp_path, capsys):
    """ONBRD-FR-006, ONBRD-NFR-003: --json emits a parseable summary and never blocks on input."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    report = json.loads(capsys.readouterr().out)
    assert report["language"] == "python"
    assert report["key"] == "created"
    assert report["root"] == str(root)


# --------------------------------------------------------------------------- FR-009
def test_rerun_is_idempotent_and_non_destructive(tmp_path):
    """ONBRD-FR-009 (property): re-running converges to the same on-disk trust-spine state."""
    root = tmp_path / "proj"
    root.mkdir()
    key = tmp_path / "k.key"

    def snapshot():
        s = Settings(root=root)
        return {
            str(p.relative_to(s.dir)): p.read_bytes()
            for p in sorted(s.dir.rglob("*"))
            if p.is_file()
        }

    assert _init(root, "--language", "python", key=key) == 0
    first = snapshot()
    assert _init(root, "--language", "python", key=key) == 0
    assert snapshot() == first  # ledger, keys, and config all byte-identical


# --------------------------------------------------------------------------- FR-008 (kept)
def test_seeding_never_clobbers_hand_edited_config(tmp_path):
    """ONBRD-FR-008: pre-existing configuration is preserved, not overwritten."""
    root = tmp_path / "proj"
    root.mkdir()
    s = Settings(root=root)
    s.roles_path.parent.mkdir(parents=True)
    s.roles_path.write_text("# HAND-EDITED SENTINEL\n", encoding="utf-8")
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert "HAND-EDITED SENTINEL" in s.roles_path.read_text(encoding="utf-8")
    assert s.risk_tiers_path.exists()  # the missing one was still seeded


# --------------------------------------------------------------------------- FR-010
def test_brownfield_detection_and_guidance(tmp_path, capsys):
    """ONBRD-FR-010: an existing project is detected and steered onto the brownfield path."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert _init(root, key=tmp_path / "k.key") == 0  # no --language: auto-detect
    out = capsys.readouterr().out
    assert "Existing project detected" in out
    assert "report-only" in out and "characterize" in out
    # auto-detected the language from the stack marker
    assert (Settings(root=root).adapters_dir / "python" / "adapter.yaml").exists()


def test_greenfield_guidance_points_to_authoring(tmp_path, capsys):
    """ONBRD-FR-010: an empty repo is steered to author its first spec."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    out = capsys.readouterr().out
    assert "author your first spec" in out
    assert "3pwr run" in out


def test_detect_language_matches_adapter_globs(tmp_path):
    """ONBRD-FR-010 (property): the detected default matches the adapter whose globs match."""
    go = tmp_path / "go"
    go.mkdir()
    (go / "go.mod").write_text("module x\n", encoding="utf-8")
    assert scaffold.detect_language(go) == "go"

    ts = tmp_path / "ts"
    ts.mkdir()
    (ts / "package.json").write_text("{}", encoding="utf-8")
    (ts / "tsconfig.json").write_text("{}", encoding="utf-8")
    assert scaffold.detect_language(ts) == "typescript"

    empty = tmp_path / "empty"
    empty.mkdir()
    assert scaffold.detect_language(empty) is None


# --------------------------------------------------------------------------- NFR-002
def test_onboarding_runs_fully_offline(tmp_path, monkeypatch):
    """ONBRD-NFR-002: the flow makes no network call (a blocked socket does not stop it)."""

    def _no_network(*_a, **_k):
        raise RuntimeError("network access attempted during onboarding")

    monkeypatch.setattr(socket, "socket", _no_network)
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0


# --------------------------------------------------------------------------- NFR-004
def test_onboarding_does_not_weaken_any_gate_threshold(tmp_path):
    """ONBRD-NFR-004: onboarding seeds the baseline tiers unchanged — no gate threshold is lowered."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--auto-mode", key=tmp_path / "k.key") == 0
    tiers = Settings(root=root).load_risk_tiers()["tiers"]
    assert tiers["Standard"]["diff_coverage"] == 80
    assert tiers["High-risk"]["diff_coverage"] == 95
    assert tiers["High-risk"]["mutation_score"] == 70


# --------------------------------------------------------------------------- NFR-005
def test_no_new_runtime_dependency_for_prompting():
    """ONBRD-NFR-005: the wizard uses the stdlib — no new required prompting dependency is added."""
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    deps = " ".join(
        tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
    ).lower()
    for banned in ("click", "typer", "questionary", "prompt_toolkit", "inquirer", "rich"):
        assert banned not in deps


# --------------------------------------------------------------------------- FR-016 (AGENTS.md)
def test_agents_md_created_when_missing_names_3pwr(tmp_path):
    """ONBRD-FR-016: a repo with no AGENTS.md gains a 3Powers starter naming `3pwr` as main command."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "3pwr" in text and "AGENTS.md" in text
    assert "3pwr run" in text  # names the primary command


def test_agents_md_kept_when_present(tmp_path):
    """ONBRD-FR-016: an existing AGENTS.md is left byte-unchanged."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "AGENTS.md").write_text("# my agents SENTINEL\n", encoding="utf-8")
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert (root / "AGENTS.md").read_text(encoding="utf-8") == "# my agents SENTINEL\n"


# --------------------------------------------------------------------------- FR-015 (Spec Kit + constitution)
def test_readiness_recommends_speckit_when_missing(tmp_path, capsys):
    """ONBRD-FR-015: with no Spec Kit workspace, init reports it and recommends init (still exit 0)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    out = capsys.readouterr().out
    assert "Ready for the agentic workflow?" in out
    assert "Spec Kit not initialized" in out


def test_constitution_overlay_laid_when_speckit_present(tmp_path):
    """ONBRD-FR-015: if Spec Kit exists but the 3Powers constitution is absent, init lays it offline."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".specify" / "memory").mkdir(parents=True)
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert scaffold.is_threepowers_constitution(root)


def test_existing_constitution_is_not_overwritten(tmp_path):
    """ONBRD-FR-015: an existing constitution is never overwritten."""
    root = tmp_path / "proj"
    root.mkdir()
    cpath = root / ".specify" / "memory" / "constitution.md"
    cpath.parent.mkdir(parents=True)
    cpath.write_text("# Custom Constitution SENTINEL\n", encoding="utf-8")
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    assert "SENTINEL" in cpath.read_text(encoding="utf-8")


def test_with_speckit_initializes_speckit_and_lays_constitution(tmp_path, monkeypatch):
    """ONBRD-FR-015: --with-speckit initializes Spec Kit and lays the 3Powers constitution overlay."""
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr(scaffold, "specify_installed", lambda: True)

    def fake_init(r, integration=None):
        # Mirror `specify init`: scaffold .specify/ AND drop a placeholder constitution.
        (r / ".specify" / "memory").mkdir(parents=True, exist_ok=True)
        (r / ".specify" / "memory" / "constitution.md").write_text(
            "# [PROJECT_NAME] Constitution\n", encoding="utf-8"
        )
        return 0

    monkeypatch.setattr(scaffold, "run_specify_init", fake_init)
    assert _init(root, "--language", "python", "--with-speckit", key=tmp_path / "k.key") == 0
    assert scaffold.is_threepowers_constitution(root)  # the placeholder was overlaid


def test_with_speckit_requires_the_specify_cli(tmp_path, monkeypatch):
    """ONBRD-FR-015: --with-speckit without the `specify` CLI is a usage error (exit 2)."""
    root = tmp_path / "proj"
    root.mkdir()
    monkeypatch.setattr(scaffold, "specify_installed", lambda: False)
    assert _init(root, "--language", "python", "--with-speckit", key=tmp_path / "k.key") == 2
