"""Configurable gates (GATECFG): gates.yaml overrides, native-tooling auto-detection, opt-in
auto-fix, and the effective-config view. Configuration replaces TOOLS, never gates."""

from __future__ import annotations

import json
import subprocess

import yaml

from threepowers import adapters, cli, scaffold
from threepowers.config import Settings
from threepowers.gates import fixed_paths, run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_PASS

RISK = (
    "tiers:\n"
    "  T: { diff_coverage: 0, gates: [format] }\n"
    "  TT: { diff_coverage: 0, gates: [tests] }\n"
    "  TY: { diff_coverage: 0, gates: [types] }\n"
)

ADAPTER = (
    'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
    "gates:\n"
    '  format: { check_cmd: "python -c pass", parser: fmt }\n'
    '  tests: { cmd: "definitely-not-a-real-tool-xyz", parser: runner, coverage_format: lcov }\n'
)


def _project(tmp_path, *, adapter_yaml: str = ADAPTER, gates_yaml: str | None = None):
    """A minimal repo: .3powers config + adapter 'a' + a project dir with a spec."""
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK, encoding="utf-8")
    (tp / "adapters" / "a" / "adapter.yaml").write_text(adapter_yaml, encoding="utf-8")
    if gates_yaml is not None:
        (tp / "config" / "gates.yaml").write_text(gates_yaml, encoding="utf-8")
    proj = tmp_path / "p"
    (proj / "tests").mkdir(parents=True)
    (proj / "d").write_text("")
    (proj / "spec.md").write_text(
        "**Spec ID**: ZED\n\n- **ZED-FR-001**: shall.\n", encoding="utf-8"
    )
    return Settings(root=tmp_path), proj


def _fixable_project(tmp_path, *, gate: str = "format"):
    """A git project whose check fails until fix.py rewrites f.txt to 'ok'."""
    adapter = (
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
        f"gates:\n"
        f'  {gate}: {{ check_cmd: "python check.py", fix_cmd: "python fix.py", parser: fixer }}\n'
    )
    s, proj = _project(tmp_path, adapter_yaml=adapter)
    (proj / "check.py").write_text(
        "import pathlib, sys\nsys.exit(0 if pathlib.Path('f.txt').read_text() == 'ok' else 1)\n",
        encoding="utf-8",
    )
    (proj / "fix.py").write_text(
        "import pathlib\npathlib.Path('f.txt').write_text('ok')\n", encoding="utf-8"
    )
    (proj / "f.txt").write_text("bad", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    return s, proj


# --------------------------------------------------------------------------- FR-001: gates.yaml merge
def test_gates_yaml_override_lands_in_effective_config(tmp_path):
    """GATECFG-FR-001: gates.yaml overriding tests.cmd to `npm run test:unit` yields exactly that
    command in the effective config; unmentioned keys and gates keep the adapter values."""
    s, _ = _project(tmp_path, gates_yaml='tests:\n  cmd: "npm run test:unit"\n')
    manifest = adapters.load_adapter(s, "a")
    assert manifest["gates"]["tests"]["cmd"] == "npm run test:unit"
    # per-key merge, not block replacement: the adapter's other tests keys survive
    assert manifest["gates"]["tests"]["coverage_format"] == "lcov"
    assert manifest["gates"]["format"]["check_cmd"] == "python -c pass"


def test_gates_yaml_override_command_runs_in_the_gate_run(tmp_path):
    """GATECFG-FR-001: the overridden tests command is what the gate run actually executes."""
    marker = "python -c \"open('ran-override','w').write('x')\""
    s, proj = _project(tmp_path, gates_yaml=f"tests:\n  cmd: {json.dumps(marker)}\n")
    v = run_gates(s, proj, tier="TT", spec_path=proj / "spec.md", adapter_name="a")
    tests_gate = next(g for g in v.gates if g.gate == "tests")
    assert tests_gate.status == STATUS_PASS
    assert (proj / "ran-override").exists()


def test_absent_or_empty_gates_yaml_changes_nothing(tmp_path):
    """GATECFG-FR-001: an absent (or fully commented) gates.yaml leaves the adapter unchanged."""
    s, _ = _project(tmp_path, gates_yaml="# all comments\n")
    assert adapters.load_gate_overrides(s) == {}
    assert adapters.load_adapter(s, "a")["gates"]["tests"]["cmd"] == (
        "definitely-not-a-real-tool-xyz"
    )


# --------------------------------------------------------------------------- FR-002: the init seed
def test_init_seeds_gates_yaml_inert_and_never_clobbers(tmp_path):
    """GATECFG-FR-002: `3pwr init` seeds a commented gates.yaml that changes no behavior, and a
    re-seed never clobbers a hand-edited file."""
    s = Settings(root=tmp_path)
    scaffold.seed_config(s)
    seed = s.dir / "config" / "gates.yaml"
    assert seed.is_file()
    assert yaml.safe_load(seed.read_text(encoding="utf-8")) is None  # fully commented — inert
    seed.write_text("tests:\n  cmd: mine\n", encoding="utf-8")
    scaffold.seed_config(s)
    assert "mine" in seed.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- FR-003: precedence
def test_precedence_gates_yaml_beats_autodetect_beats_manifest(tmp_path):
    """GATECFG-FR-003: with all three sources configuring the tests gate, gates.yaml wins; without
    it, auto-detection beats the adapter manifest."""
    s, proj = _project(tmp_path, gates_yaml='tests:\n  cmd: "npm run test:unit"\n')
    (proj / "jest.config.ts").write_text("", encoding="utf-8")
    eff = adapters.effective_gates(s, "a", proj)
    assert eff.manifest["gates"]["tests"]["cmd"] == "npm run test:unit"
    assert eff.sources["tests"] == "gates.yaml"
    assert "tests" not in eff.detected
    # without the override, detection wins over the manifest
    s2, proj2 = _project(tmp_path / "two")
    (proj2 / "jest.config.ts").write_text("", encoding="utf-8")
    eff2 = adapters.effective_gates(s2, "a", proj2)
    assert "jest" in eff2.manifest["gates"]["tests"]["cmd"]
    assert eff2.sources["tests"] == "auto-detected"


# --------------------------------------------------------------------------- FR-004: auto-detection
def test_autodetect_picks_jest_or_vitest_by_config_file(tmp_path):
    """GATECFG-FR-004: only jest.config.ts present ⇒ jest; vitest.config.ts present ⇒ vitest
    (first match in the fixed table order)."""
    jest_dir = tmp_path / "j"
    jest_dir.mkdir()
    (jest_dir / "jest.config.ts").write_text("", encoding="utf-8")
    assert adapters.detect_native_tools(jest_dir)["tests"][0] == "jest"
    vitest_dir = tmp_path / "v"
    vitest_dir.mkdir()
    (vitest_dir / "vitest.config.ts").write_text("", encoding="utf-8")
    assert adapters.detect_native_tools(vitest_dir)["tests"][0] == "vitest"
    both = tmp_path / "b"
    both.mkdir()
    (both / "jest.config.ts").write_text("", encoding="utf-8")
    (both / "vitest.config.ts").write_text("", encoding="utf-8")
    assert adapters.detect_native_tools(both)["tests"][0] == "vitest"


def test_autodetect_table_covers_the_declared_signals(tmp_path):
    """GATECFG-FR-004: biome/prettier (format), biome/eslint (lint), tsc/pyright (types),
    playwright (tests), and the go.mod rules all detect from their signal files."""
    d = tmp_path / "sig"
    d.mkdir()
    (d / "biome.json").write_text("{}", encoding="utf-8")
    (d / "tsconfig.json").write_text("{}", encoding="utf-8")
    (d / "playwright.config.ts").write_text("", encoding="utf-8")
    found = adapters.detect_native_tools(d)
    assert found["format"][0] == "biome"
    assert found["lint"][0] == "biome"
    assert found["types"][0] == "tsc"
    assert found["tests"][0] == "playwright"
    go = tmp_path / "go"
    go.mkdir()
    (go / "go.mod").write_text("module m\n", encoding="utf-8")
    gofound = adapters.detect_native_tools(go)
    assert gofound["tests"] == ("gotest", {"cmd": "go test ./...", "parser": "gotest"})
    assert gofound["format"][1]["check_cmd"] == "gofmt -l ."
    py = tmp_path / "py"
    py.mkdir()
    (py / "pyproject.toml").write_text("[tool.pyright]\n", encoding="utf-8")
    assert adapters.detect_native_tools(py)["types"][0] == "pyright"
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "pyproject.toml").write_text("[tool.mypy]\n", encoding="utf-8")
    assert "types" not in adapters.detect_native_tools(plain)
    eslint = tmp_path / "es"
    eslint.mkdir()
    (eslint / ".eslintrc.json").write_text("{}", encoding="utf-8")
    (eslint / ".prettierrc").write_text("{}", encoding="utf-8")
    esfound = adapters.detect_native_tools(eslint)
    assert esfound["lint"][0] == "eslint"
    assert esfound["format"][0] == "prettier"


def test_detection_confirms_but_never_degrades_a_matching_adapter_gate(tmp_path):
    """GATECFG-FR-004: a detected tool the adapter already configures keeps the adapter's richer
    command (e.g. Go's coverage-emitting test pipeline), while still reporting the detection."""
    adapter = (
        'language: g\ndetect: ["d"]\ntest_roots: ["."]\n'
        "gates:\n"
        '  tests: { cmd: "go test -coverprofile=c.out ./... && gcov2lcov", shell: true, '
        "parser: gotest }\n"
    )
    s, proj = _project(tmp_path, adapter_yaml=adapter)
    (proj / "go.mod").write_text("module m\n", encoding="utf-8")
    eff = adapters.effective_gates(s, "a", proj)
    assert "gcov2lcov" in eff.manifest["gates"]["tests"]["cmd"]  # richer command kept
    assert eff.detected["tests"] == "gotest"
    assert eff.sources["tests"] == "auto-detected"


# --------------------------------------------------------------------------- FR-005: the startup line
def test_detection_line_prints_once_on_the_human_path(tmp_path, capsys):
    """GATECFG-FR-005: a gate run that detected tooling prints exactly one
    `auto-detected gates:` line on the human path."""
    s, proj = _project(tmp_path)
    (proj / "jest.config.ts").write_text("", encoding="utf-8")
    args = cli.build_parser().parse_args(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--spec",
            str(proj / "spec.md"),
            "--adapter",
            "a",
            "--no-ledger",
        ]
    )
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert out.count("auto-detected gates:") == 1
    assert "tests=jest" in out


def test_detection_line_never_enters_the_json_payload(tmp_path, capsys):
    """GATECFG-FR-005: under --json the stdout is pure machine payload — no detection line."""
    s, proj = _project(tmp_path)
    (proj / "jest.config.ts").write_text("", encoding="utf-8")
    args = cli.build_parser().parse_args(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--spec",
            str(proj / "spec.md"),
            "--adapter",
            "a",
            "--no-ledger",
            "--json",
        ]
    )
    assert args.func(args) == 0
    out = capsys.readouterr().out
    payload = json.loads(out)  # parses as one clean JSON document
    assert "auto-detected" not in out
    assert payload["verdict"]["result"] == STATUS_PASS


# --------------------------------------------------------------------------- FR-006: fixable gates only
def test_fix_cmd_is_discarded_on_non_fixable_gates(tmp_path):
    """GATECFG-FR-006: a fix_cmd configured on tests (via gates.yaml) or on types (via the
    manifest) is discarded at assembly — only format/lint may carry one."""
    adapter = ADAPTER + '  types: { cmd: "python -c pass", fix_cmd: "python -c pass", parser: t }\n'
    s, proj = _project(
        tmp_path,
        adapter_yaml=adapter,
        gates_yaml='tests:\n  fix_cmd: "python -c pass"\nformat:\n  fix_cmd: "python fix.py"\n',
    )
    manifest = adapters.load_adapter(s, "a")
    assert "fix_cmd" not in manifest["gates"]["tests"]
    assert "fix_cmd" not in manifest["gates"]["types"]
    assert manifest["gates"]["format"]["fix_cmd"] == "python fix.py"
    eff = adapters.effective_gates(s, "a", proj)
    assert "fix_cmd" not in eff.manifest["gates"]["types"]


def test_fix_never_runs_for_a_non_fixable_gate_even_when_configured(tmp_path):
    """GATECFG-FR-006: even a manifest smuggling fix_cmd onto the types gate past assembly never
    gets it executed — the engine refuses to fix types/tests/mutation."""
    s, proj = _fixable_project(tmp_path, gate="types")
    manifest = {
        "gates": {"types": {"cmd": "python check.py", "fix_cmd": "python fix.py", "parser": "t"}}
    }
    v = run_gates(
        s,
        proj,
        tier="TY",
        spec_path=proj / "spec.md",
        adapter_name="a",
        auto_fix=True,
        manifest=manifest,
    )
    types_gate = next(g for g in v.gates if g.gate == "types")
    assert types_gate.status == STATUS_FAIL
    assert (proj / "f.txt").read_text(encoding="utf-8") == "bad"  # the fix never ran


# --------------------------------------------------------------------------- FR-007: opt-in flag
def test_auto_fix_flag_is_opt_in_on_both_commands():
    """GATECFG-FR-007: `gate run` and `run` accept --auto-fix; it is never the default."""
    p = cli.build_parser()
    assert p.parse_args(["gate", "run"]).auto_fix is False
    assert p.parse_args(["gate", "run", "--auto-fix"]).auto_fix is True
    assert p.parse_args(["run", "intent"]).auto_fix is False
    assert p.parse_args(["run", "intent", "--auto-fix"]).auto_fix is True


# --------------------------------------------------------------------------- FR-008: the green path
def test_auto_fix_fix_recheck_green_records_fixed_paths(tmp_path):
    """GATECFG-FR-008: with --auto-fix, a failing format check runs its fix, re-checks green, and
    records the fixed paths so they join the run's produced set."""
    s, proj = _fixable_project(tmp_path)
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", auto_fix=True)
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == STATUS_PASS
    assert fmt.details["auto_fixed"] == "fixer"
    assert fmt.details["fixed_paths"] == ["f.txt"]
    assert fixed_paths(v.to_dict()) == ["f.txt"]
    assert (proj / "f.txt").read_text(encoding="utf-8") == "ok"


def test_auto_fix_announces_the_fix_in_the_human_output(tmp_path, capsys):
    """GATECFG-FR-008: the gate run's human output carries the `↳ auto-fixed by <tool>` line."""
    s, proj = _fixable_project(tmp_path)
    args = cli.build_parser().parse_args(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--spec",
            str(proj / "spec.md"),
            "--adapter",
            "a",
            "--no-ledger",
            "--auto-fix",
        ]
    )
    assert args.func(args) == 0
    assert "↳ auto-fixed by fixer" in capsys.readouterr().out


def test_auto_fix_failing_recheck_reports_normally(tmp_path):
    """GATECFG-FR-008: when the fix does not make the re-check pass, the gate is red and reports
    normally — no fixed paths are recorded."""
    s, proj = _fixable_project(tmp_path)
    (proj / "fix.py").write_text("pass\n", encoding="utf-8")  # a fix that fixes nothing
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", auto_fix=True)
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == STATUS_FAIL
    assert "auto_fixed" not in fmt.details
    assert fixed_paths(v.to_dict()) == []


# --------------------------------------------------------------------------- FR-009: without the flag
def test_without_auto_fix_the_gate_fails_first_check_with_the_hint(tmp_path):
    """GATECFG-FR-009: without --auto-fix the gate fails on the first check, the fix_cmd surfaces
    only as the failure-panel hint, and the working tree is untouched."""
    s, proj = _fixable_project(tmp_path)
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == STATUS_FAIL
    assert fmt.details["fix_cmd"] == "python fix.py"  # the rendered hint's source
    assert "auto_fixed" not in fmt.details
    assert (proj / "f.txt").read_text(encoding="utf-8") == "bad"  # nothing was mutated


# --------------------------------------------------------------------------- FR-010: gate config show
def test_gate_config_show_renders_sources_and_executes_nothing(tmp_path, capsys):
    """GATECFG-FR-010: `gate config show` renders every gate with its tool, commands, and source
    tag ([adapter] / [gates.yaml] / [auto-detected]) and runs no gate command."""
    adapter = (
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
        "gates:\n"
        "  format: { check_cmd: \"python -c \\\"open('ran-fmt','w')\\\"\", parser: fmt }\n"
        '  tests: { cmd: "definitely-not-a-real-tool-xyz", parser: runner }\n'
    )
    s, proj = _project(
        tmp_path, adapter_yaml=adapter, gates_yaml='tests:\n  cmd: "npm run test:unit"\n'
    )
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")  # detectable at the root
    args = cli.build_parser().parse_args(
        ["--root", str(tmp_path), "gate", "config", "show", "--adapter", "a"]
    )
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "[adapter]" in out and "format" in out
    assert "npm run test:unit" in out and "[gates.yaml]" in out
    assert "tsc" in out and "[auto-detected]" in out
    assert not (tmp_path / "ran-fmt").exists()  # no gate command executed


def test_gate_config_show_json_names_each_gate_source(tmp_path, capsys):
    """GATECFG-FR-010: the --json view carries the same per-gate tool/commands/source data."""
    s, proj = _project(tmp_path, gates_yaml='tests:\n  cmd: "npm run test:unit"\n')
    args = cli.build_parser().parse_args(
        ["--root", str(tmp_path), "gate", "config", "show", "--adapter", "a", "--json"]
    )
    assert args.func(args) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["adapter"] == "a"
    assert obj["gates"]["tests"]["source"] == "gates.yaml"
    assert obj["gates"]["tests"]["check_cmd"] == "npm run test:unit"
    assert obj["gates"]["format"]["source"] == "adapter"


# --------------------------------------------------------------------------- NFR-001: tools, not gates
def test_configuration_replaces_tools_never_gates(tmp_path):
    """GATECFG-NFR-001: the tier's required gate set is identical with and without gates.yaml and
    detection, and assembly is deterministic given the same inputs."""
    s, proj = _project(tmp_path)
    plain = [g.gate for g in run_gates(s, proj, tier="T", spec_path=None, adapter_name="a").gates]
    s2, proj2 = _project(tmp_path / "cfg", gates_yaml='format:\n  check_cmd: "python -c pass"\n')
    (proj2 / "jest.config.ts").write_text("", encoding="utf-8")
    eff = adapters.effective_gates(s2, "a", proj2)
    configured = [
        g.gate
        for g in run_gates(
            s2, proj2, tier="T", spec_path=None, adapter_name="a", manifest=eff.manifest
        ).gates
    ]
    assert plain == configured  # the gate set never moves with configuration
    again = adapters.effective_gates(s2, "a", proj2)
    assert again.manifest == eff.manifest and again.sources == eff.sources
