"""Mutation gate tests (3PWR-FR-031/032/034): score vs. tier threshold, survivors as findings.

The tool invocation is stubbed so these stay deterministic and fast (3PWR-NFR-001);
the real mutmut run against the trust spine is exercised by self-application.
"""

from __future__ import annotations

from pathlib import Path

from threepowers import mutation
from threepowers.adapters import CmdResult
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP

_RESULTS = """\
threepowers.canonical.x_a__mutmut_1: killed
threepowers.canonical.x_a__mutmut_2: survived
threepowers.keys.x_b__mutmut_1: killed
threepowers.keys.x_b__mutmut_2: killed
threepowers.ledger.x_c__mutmut_1: timeout
"""


def test_parse_mutmut_results_counts_and_survivors():
    killed, survived, survivors = mutation._parse_mutmut_results(_RESULTS)
    assert killed == 4  # 3 killed + 1 timeout (both count as "caught")
    assert survived == 1
    assert survivors == ["threepowers.canonical.x_a__mutmut_2"]


def test_mutmut_filters_map_paths_to_module_globs():
    globs = mutation._mutmut_filters(["src/threepowers/canonical.py", "src/threepowers/keys.py"])
    assert globs == ["*.canonical.*", "*.keys.*"]


def test_parse_stryker_report(tmp_path):
    report = tmp_path / "mutation.json"
    report.write_text(
        '{"files": {"a.ts": {"mutants": ['
        '{"status": "Killed"}, {"status": "Survived", "location": {"start": {"line": 7}}},'
        '{"status": "Timeout"}]}}}',
        encoding="utf-8",
    )
    parsed = mutation._parse_stryker_report(report)
    assert parsed is not None
    killed, survived, survivors = parsed
    assert killed == 2 and survived == 1 and survivors == ["a.ts:7"]


def _stub(monkeypatch, results_text):
    def fake_run_cmd(command, cwd, timeout=600):
        return CmdResult(0, results_text if "results" in command else "", "", 5)

    monkeypatch.setattr(mutation, "run_cmd", fake_run_cmd)


def test_mutation_gate_passes_at_threshold(monkeypatch):
    _stub(monkeypatch, _RESULTS)  # 4 caught / 5 = 80%
    spec = {"parser": "mutmut", "cmd": "mutmut run", "score_cmd": "mutmut results"}
    gr = mutation.mutation_gate(Path("."), spec, threshold=70)
    assert gr.status == STATUS_PASS
    assert gr.details["mutation_score"] == 80.0


def test_mutation_gate_fails_below_threshold_with_findings(monkeypatch):
    _stub(monkeypatch, _RESULTS)  # 80% < 95%
    spec = {"parser": "mutmut", "cmd": "mutmut run", "score_cmd": "mutmut results"}
    gr = mutation.mutation_gate(Path("."), spec, threshold=95)
    assert gr.status == STATUS_FAIL
    assert any("surviving mutant" in f for f in gr.findings)  # 3PWR-FR-034


def test_mutation_gate_quarantines_when_tool_missing(monkeypatch):
    def fake_run_cmd(command, cwd, timeout=600):
        return CmdResult(127, "", "tool not found", 1)

    monkeypatch.setattr(mutation, "run_cmd", fake_run_cmd)
    spec = {"parser": "mutmut", "cmd": "mutmut run"}
    gr = mutation.mutation_gate(Path("."), spec, threshold=70)
    assert gr.status == STATUS_SKIP and "quarantined" in gr.findings[0]  # 3PWR-NFR-015


def test_mutation_gate_quarantines_on_zero_mutants(monkeypatch):
    _stub(monkeypatch, "")  # no mutants parsed
    spec = {"parser": "mutmut", "cmd": "mutmut run", "score_cmd": "mutmut results"}
    gr = mutation.mutation_gate(Path("."), spec, threshold=70)
    assert gr.status == STATUS_SKIP
