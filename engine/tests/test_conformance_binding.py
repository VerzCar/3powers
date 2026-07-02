"""Conformance anti-gaming — ID binding + assertion-bearing tests (HARDN-FR-008/009).

Unit layer: a requirement traces only when its ID is bound to a test declaration (name,
declaration line, or adjacent docstring); a comment mention alone is `untraced_requirement`;
an assertion-free requirement-bound test is `weak_test`; adapters without patterns degrade
to a visible quarantine (3PWR-NFR-015, HARDN-NFR-003); and the whole check rides a single
read per file (HARDN-NFR-002).
"""

from __future__ import annotations

from pathlib import Path

from threepowers.conformance import conformance_failures, run_conformance

SPEC = (
    "**Spec ID**: DEMO\n\n"
    "- **DEMO-FR-001**: The system shall work.\n"
    "- **DEMO-FR-002**: The system shall also work.\n"
)

PY_CFG = {
    "test_declarations": [r"^\s*(?:async\s+)?def\s+test_\w+"],
    "assertion_patterns": [r"\bassert\b", r"\bpytest\.raises\b"],
}
TS_CFG = {
    "test_declarations": [r"\b(?:describe|it|test)(?:\.\w+)?\s*\("],
    "assertion_patterns": [r"\bexpect\s*\("],
}


def _project(tmp_path: Path, test_name: str, test_body: str) -> tuple[Path, Path]:
    spec = tmp_path / "spec.md"
    spec.write_text(SPEC, encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir(exist_ok=True)
    (tests / test_name).write_text(test_body, encoding="utf-8")
    return spec, tests


# --------------------------------------------------------------------------- HARDN-FR-008
def test_comment_only_mention_is_untraced(tmp_path):
    """HARDN-FR-008: an ID appearing only in a comment yields untraced_requirement, named."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        "# covers DEMO-FR-001\n# and DEMO-FR-002\ndef test_something():\n    assert True\n",
    )
    gate = run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    assert gate.status == "fail"
    assert gate.details["untraced_requirements"] == ["DEMO-FR-001", "DEMO-FR-002"]
    classes = {f["class"] for f in conformance_failures(gate)}
    assert "untraced_requirement" in classes


def test_id_in_declaration_name_traces(tmp_path):
    """HARDN-FR-008: the same ID in a test declaration line traces the requirement."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        "def test_demo_fr_001():\n"
        '    """DEMO-FR-001: docstring binding."""\n'
        "    assert 1 == 1\n"
        "def test_more():  # DEMO-FR-002 on the declaration line\n"
        "    assert 2 == 2\n",
    )
    gate = run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    assert gate.status == "pass", gate.findings
    assert gate.details["untraced_requirements"] == []


def test_ts_describe_title_binds_and_nested_its_carry_the_assertions(tmp_path):
    """HARDN-FR-008/009: a describe() title binds; expect() in nested it() bodies counts."""
    spec, tests = _project(
        tmp_path,
        "demo.test.ts",
        'describe("DEMO-FR-001 + DEMO-FR-002: things work", () => {\n'
        '  it("does the thing", () => {\n'
        "    expect(f()).toBe(1);\n"
        "  });\n"
        "});\n",
    )
    gate = run_conformance(spec, [tests], conformance_cfg=TS_CFG)
    assert gate.status == "pass", gate.findings
    assert gate.details["weak_tests"] == []


def test_existing_engine_and_sample_binding_styles_still_pass(tmp_path):
    """HARDN-FR-008 acceptance: docstring-after-def (engine) and describe-title (sample) bind."""
    spec, tests = _project(
        tmp_path,
        "test_style.py",
        "def test_engine_style():\n"
        '    """DEMO-FR-001: the engine binds IDs in docstrings."""\n'
        "    assert True\n",
    )
    (tests / "sample.test.ts").write_text(
        'describe("DEMO-FR-002: sample style", () => { it("x", () => expect(1).toBe(1)); });\n',
        encoding="utf-8",
    )
    py = run_conformance(spec, [tests / "test_style.py"], conformance_cfg=PY_CFG)
    ts = run_conformance(spec, [tests / "sample.test.ts"], conformance_cfg=TS_CFG)
    assert "DEMO-FR-001" in py.details["layers"]
    assert "DEMO-FR-002" in ts.details["layers"]


# --------------------------------------------------------------------------- HARDN-FR-009
def test_assertion_free_bound_test_is_weak(tmp_path):
    """HARDN-FR-009: an empty/assertion-free body bound to an ID fails as weak_test, naming both."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        "def test_demo():\n"
        '    """DEMO-FR-001: bound but hollow."""\n'
        "    pass\n"
        "def test_other():\n"
        '    """DEMO-FR-002: real."""\n'
        "    assert True\n",
    )
    gate = run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    assert gate.status == "fail"
    weak = gate.details["weak_tests"]
    assert len(weak) == 1 and weak[0][0] == "DEMO-FR-001" and "test_demo.py" in weak[0][1]
    fails = [f for f in conformance_failures(gate) if f["class"] == "weak_test"]
    assert (
        fails and fails[0]["requirement_id"] == "DEMO-FR-001" and "test_demo.py" in fails[0]["file"]
    )


def test_no_assertion_patterns_quarantines_never_silently_passes(tmp_path):
    """HARDN-FR-009 + 3PWR-NFR-015: an adapter without assertion patterns is quarantined, visibly."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        'def test_demo():\n    """DEMO-FR-001 + DEMO-FR-002: bound, no assertion."""\n    pass\n',
    )
    cfg = {"test_declarations": PY_CFG["test_declarations"]}  # no assertion_patterns
    gate = run_conformance(spec, [tests], conformance_cfg=cfg)
    assert gate.status == "pass"  # binding satisfied; assertions not judged...
    assert any("no assertion patterns" in f and "quarantined" in f for f in gate.findings)
    assert gate.details["weak_tests"] == []


def test_no_declaration_patterns_degrades_to_quarantined_mention_tracing(tmp_path):
    """HARDN-NFR-003: a legacy adapter (no conformance block) keeps mention-based tracing,
    with a visible quarantine finding — never a failure, never silent."""
    spec, tests = _project(tmp_path, "test_demo.py", "# covers DEMO-FR-001 DEMO-FR-002\n")
    gate = run_conformance(spec, [tests], conformance_cfg=None)
    assert gate.status == "pass"
    assert any("no test-declaration patterns" in f and "quarantined" in f for f in gate.findings)


def test_invalid_pattern_is_reported_not_crashed(tmp_path):
    """3PWR-NFR-015: a malformed regex in the manifest is surfaced, not swallowed."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        'def test_a():\n    """DEMO-FR-001 + DEMO-FR-002."""\n    assert True\n',
    )
    cfg = {
        "test_declarations": PY_CFG["test_declarations"] + ["([unclosed"],
        "assertion_patterns": PY_CFG["assertion_patterns"],
    }
    gate = run_conformance(spec, [tests], conformance_cfg=cfg)
    assert any("invalid conformance pattern" in f for f in gate.findings)
    assert gate.status == "pass"  # the valid patterns still did their job


# --------------------------------------------------------------------------- HARDN-NFR-001/002
def test_single_read_per_file(tmp_path, monkeypatch):
    """HARDN-NFR-002: binding + assertion checks ride the existing scan — one read per test file."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        'def test_a():\n    """DEMO-FR-001 + DEMO-FR-002."""\n    assert True\n',
    )
    reads: dict[str, int] = {}
    orig = Path.read_text

    def counting(self, *a, **kw):
        if self.suffix in (".py", ".ts"):
            reads[str(self)] = reads.get(str(self), 0) + 1
        return orig(self, *a, **kw)

    monkeypatch.setattr(Path, "read_text", counting)
    run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    test_reads = {k: v for k, v in reads.items() if "tests" in k}
    assert test_reads and all(v == 1 for v in test_reads.values()), test_reads


def test_conformance_is_deterministic(tmp_path):
    """HARDN-NFR-001: identical inputs → identical findings, twice."""
    spec, tests = _project(
        tmp_path,
        "test_demo.py",
        '# DEMO-FR-002 in a comment only\ndef test_a():\n    """DEMO-FR-001."""\n    pass\n',
    )
    a = run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    b = run_conformance(spec, [tests], conformance_cfg=PY_CFG)
    assert a.findings == b.findings and a.status == b.status
