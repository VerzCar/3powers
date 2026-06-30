"""Adapter contract tests (3PWR-FR-027): declarative manifest; no core change per language."""

from __future__ import annotations

import pytest

from threepowers import adapters
from threepowers.config import Settings


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
