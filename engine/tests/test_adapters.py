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


# --------------------------------------------------------------- plan 035 Track A: biome split
def test_biome_detect_rules_are_format_only_and_lint_only():
    """Plan 035 Track A: the biome detection specs are formatter-only / linter-only —
    a gate named format never lints and a gate named lint never formats."""
    biome = {r.gate: r.spec for r in adapters.DETECT_RULES if r.tool == "biome"}
    assert biome["format"]["check_cmd"] == "npx --no-install @biomejs/biome format ."
    assert biome["format"]["fix_cmd"] == "npx --no-install @biomejs/biome format --write ."
    assert biome["lint"]["check_cmd"] == "npx --no-install @biomejs/biome lint ."
    assert biome["lint"]["fix_cmd"] == "npx --no-install @biomejs/biome lint --write ."


def test_typescript_adapter_manifest_splits_biome_format_and_lint():
    """Plan 035 Track A: the shipped TS adapter maps format→`biome format` and
    lint→`biome lint` (no combined `ci`/`check` command on either gate)."""
    gates_ = adapters.load_adapter(_repo_settings(), "typescript")["gates"]
    assert gates_["format"]["check_cmd"] == "npx --no-install @biomejs/biome format ."
    assert gates_["format"]["fix_cmd"] == "npx --no-install @biomejs/biome format --write ."
    assert gates_["lint"]["cmd"] == "npx --no-install @biomejs/biome lint ."
    assert gates_["lint"]["fix_cmd"] == "npx --no-install @biomejs/biome lint --write ."


def test_eslint_repo_resolves_biome_format_and_eslint_lint(tmp_path):
    """Plan 035 Track A: on a repo with both biome and ESLint configs, biome formats and
    ESLint owns lint — no double-linting."""
    proj = tmp_path / "both"
    proj.mkdir()
    (proj / "biome.json").write_text("{}", encoding="utf-8")
    (proj / "eslint.config.js").write_text("", encoding="utf-8")
    found = adapters.detect_native_tools(proj)
    assert found["format"][0] == "biome"
    assert "biome format" in found["format"][1]["check_cmd"]
    assert found["lint"][0] == "eslint"


def test_biome_only_repo_resolves_lint_to_biome_lint(tmp_path):
    """Plan 035 Track A: a biome-only repo still lints — via `biome lint`, not `format`."""
    proj = tmp_path / "solo"
    proj.mkdir()
    (proj / "biome.json").write_text("{}", encoding="utf-8")
    found = adapters.detect_native_tools(proj)
    assert found["lint"][0] == "biome"
    assert "biome lint" in found["lint"][1]["check_cmd"]
    assert "biome format" in found["format"][1]["check_cmd"]


def test_eslint_only_repo_uses_eslint_for_format_and_lint_not_biome(tmp_path):
    """A project that formats and lints with ESLint (no biome.json, no prettier config) resolves
    BOTH `format` and `lint` to ESLint — the engine never imposes (or installs) biome over a
    project's own native tooling; biome is only the adapter's last-resort default."""
    proj = tmp_path / "eslint-only"
    proj.mkdir()
    (proj / "eslint.config.js").write_text("", encoding="utf-8")
    found = adapters.detect_native_tools(proj)
    assert found["format"][0] == "eslint"
    assert "eslint" in found["format"][1]["check_cmd"]
    assert found["lint"][0] == "eslint"
    # biome is never imposed on a project that has its own tooling
    assert not any("biome" in spec.get("check_cmd", "") for _tool, spec in found.values())


def test_prettier_and_eslint_repo_formats_with_prettier_lints_with_eslint(tmp_path):
    """A dedicated formatter outranks ESLint-as-formatter: prettier owns `format`, ESLint owns
    `lint`. ESLint is used for `format` only when no dedicated formatter is configured."""
    proj = tmp_path / "pretty"
    proj.mkdir()
    (proj / ".prettierrc").write_text("{}", encoding="utf-8")
    (proj / "eslint.config.js").write_text("", encoding="utf-8")
    found = adapters.detect_native_tools(proj)
    assert found["format"][0] == "prettier"
    assert found["lint"][0] == "eslint"
