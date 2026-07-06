"""Missing-toolchain detection: a gate that can't run because its tool is absent yields an
actionable install hint, not raw noise (3PWR-FR-034/048). Install commands come from the adapter's
data-driven ``toolchain`` map; a genuine gate failure is never mislabeled."""

from __future__ import annotations

from threepowers import adapters, cli, gates
from threepowers.adapters import CmdResult
from threepowers.config import Settings
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_FAIL

_MANIFEST = {
    "toolchain": {"biome": {"install": "npm i -D @biomejs/biome"}},
    "gates": {"format": {"cmd": "biome ci .", "parser": "biome", "requires": "biome"}},
}


# --------------------------------------------------------------------------- signature detection
def test_looks_missing_tool_recognizes_npx_and_127():
    assert gates._looks_missing_tool(CmdResult(127, "", "tool not found: biome", 0))
    assert gates._looks_missing_tool(
        CmdResult(1, "", "npx canceled due to missing packages and no YES option", 0)
    )
    # A genuine gate failure (real diagnostics, exit 1) is NOT a missing tool.
    assert not gates._looks_missing_tool(CmdResult(1, "src/x.ts:3 lint error", "", 0))


def test_missing_tool_finding_uses_adapter_install_command():
    spec = _MANIFEST["gates"]["format"]
    hit = gates._missing_tool_finding(_MANIFEST, spec, CmdResult(127, "", "tool not found", 0))
    assert hit is not None
    tool, msg, install = hit
    assert tool == "biome" and install == "npm i -D @biomejs/biome"
    assert "biome is not installed — run: npm i -D @biomejs/biome" == msg


def test_missing_tool_finding_none_for_real_failure_or_no_requires():
    spec = _MANIFEST["gates"]["format"]
    # Real failure output → not a missing tool.
    assert gates._missing_tool_finding(_MANIFEST, spec, CmdResult(1, "lint error", "", 0)) is None
    # Gate without `requires:` → never annotated.
    no_req = {"cmd": "biome ci .", "parser": "biome"}
    assert gates._missing_tool_finding(_MANIFEST, no_req, CmdResult(127, "", "x", 0)) is None


def test_result_from_cmd_leads_with_hint_and_sets_details():
    spec = _MANIFEST["gates"]["format"]
    gr = gates._result_from_cmd("format", spec, CmdResult(127, "", "tool not found", 0), _MANIFEST)
    assert gr.status == STATUS_FAIL
    assert gr.details["missing_tool"] == "biome"
    assert gr.details["install_hint"] == "npm i -D @biomejs/biome"
    assert gr.findings[0].startswith("biome is not installed — run:")


# --------------------------------------------------------------------------- adapters helpers
def test_adapter_toolchain_helpers():
    assert adapters.gate_requires({"requires": "biome"}) == "biome"
    assert adapters.gate_requires({}) is None
    assert adapters.install_hint(_MANIFEST, "biome") == "npm i -D @biomejs/biome"
    assert adapters.install_hint(_MANIFEST, "nope") is None


# --------------------------------------------------------------------------- end-to-end
_RISK = "tiers:\n  T: { diff_coverage: 0, gates: [format] }\n"


def _project(tmp_path, gate_yaml):
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(_RISK, encoding="utf-8")
    (tp / "adapters" / "a" / "adapter.yaml").write_text(
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
        'toolchain:\n  biome: { install: "npm i -D @biomejs/biome" }\n'
        f"gates:\n{gate_yaml}\n",
        encoding="utf-8",
    )
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "d").write_text("")
    return Settings(root=tmp_path), proj


def test_run_gates_flags_missing_tool(tmp_path):
    """A gate whose required tool is absent → verdict carries missing_tool + an actionable finding."""
    s, proj = _project(
        tmp_path,
        '  format: { cmd: "definitely-not-a-real-tool-xyz ci .", parser: biome, requires: biome }',
    )
    v = run_gates(s, proj, tier="T", spec_path=None, adapter_name="a", report_only=True)
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == STATUS_FAIL
    assert fmt.details.get("missing_tool") == "biome"
    assert any("npm i -D @biomejs/biome" in f for f in fmt.findings)


def test_cmd_gate_run_prints_install_cta(tmp_path, capsys):
    """`gate run` prints a consolidated install call-to-action when a tool is missing (3PWR-FR-034)."""
    s, proj = _project(
        tmp_path,
        '  format: { cmd: "definitely-not-a-real-tool-xyz ci .", parser: biome, requires: biome }',
    )
    rc = cli.main(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--adapter",
            "a",
            "--report-only",
            "--no-ledger",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "missing toolchain" in out and "npm i -D @biomejs/biome" in out
