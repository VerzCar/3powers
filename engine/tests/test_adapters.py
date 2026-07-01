"""Adapter contract tests (3PWR-FR-027): declarative manifest; no core change per language."""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import adapters
from threepowers.config import Settings, find_root


def _repo_settings() -> Settings:
    """Settings pointed at the real repo root for the shipped adapters.

    Located by walking up to the actual ``.3powers/`` (like the engine itself), which is robust to
    mutmut relocating the source tree into ``engine/mutants/`` during a mutation run."""
    return Settings(root=find_root(Path(__file__).resolve()))


def _adapter(tmp_path, name, detect):
    s = Settings(root=tmp_path)
    d = s.adapters_dir / name
    d.mkdir(parents=True)
    (d / "adapter.yaml").write_text(f"language: {name}\ndetect: {detect}\ngates: {{}}\n")
    return s


def test_load_and_missing(tmp_path):
    s = _adapter(tmp_path, "py", '["pyproject.toml"]')
    assert adapters.load_adapter(s, "py")["language"] == "py"
    with pytest.raises(FileNotFoundError):
        adapters.load_adapter(s, "nope")


def test_detect(tmp_path):
    s = _adapter(tmp_path, "py", '["pyproject.toml"]')
    target = tmp_path / "proj"
    target.mkdir()
    (target / "pyproject.toml").write_text("")
    assert adapters.detect_adapter(s, target) == "py"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(LookupError):
        adapters.detect_adapter(s, empty)


def test_run_cmd_ok_and_missing_tool(tmp_path):
    ok = adapters.run_cmd("python -c pass", cwd=tmp_path)
    assert ok.ok and ok.returncode == 0
    missing = adapters.run_cmd("this-tool-does-not-exist-xyz", cwd=tmp_path)
    assert missing.returncode == 127 and not missing.ok


def test_command_of_prefers_check_cmd():
    assert adapters.command_of({"check_cmd": "a", "cmd": "b"}) == "a"
    assert adapters.command_of({"cmd": "b"}) == "b"
    assert adapters.command_of({}) is None


def test_wants_shell():
    assert adapters.wants_shell({"shell": True}) is True
    assert adapters.wants_shell({"cmd": "x"}) is False


def test_run_cmd_shell_enables_pipeline(tmp_path):
    """Opt-in shell mode runs a pipeline / command substitution (e.g. Go's gofmt guard)."""
    ok = adapters.run_cmd('test -z "$(echo)"', cwd=tmp_path, shell=True)
    assert ok.returncode == 0  # $(echo) is empty → `test -z` passes
    bad = adapters.run_cmd('test -z "$(echo not-empty)"', cwd=tmp_path, shell=True)
    assert bad.returncode != 0


def test_go_adapter_manifest_is_valid_and_emits_lcov():
    """The Go reference adapter (plan 015) proves the contract is language-agnostic (3PWR-NFR-007)."""
    m = adapters.load_adapter(_repo_settings(), "go")
    assert m["language"] == "go" and m["detect"] == ["go.mod"]
    tests = m["gates"]["tests"]
    # Diff-coverage reuses the core LCOV path unchanged (3PWR-FR-029); the two-step cmd needs shell.
    assert tests["coverage_path"] == "coverage/lcov.info" and tests["shell"] is True
    assert m["gates"]["format"]["shell"] is True


def test_go_adapter_is_detected_on_go_mod(tmp_path):
    proj = tmp_path / "goproj"
    proj.mkdir()
    (proj / "go.mod").write_text("module example.com/x\n\ngo 1.22\n", encoding="utf-8")
    assert adapters.detect_adapter(_repo_settings(), proj) == "go"
