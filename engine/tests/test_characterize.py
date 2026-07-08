"""Characterization tests for the characterize command (3PWR-FR-053).

These verify that a legacy module is reconstructed into a spec stub + characterization
tests, that the generated tests are runnable and trace to the reconstructed requirement
IDs (closing the loop with spec-conformance, 3PWR-FR-030), and that re-running is
idempotent.
"""

from __future__ import annotations

import ast
import subprocess
import sys

from threepowers import characterize
from threepowers.conformance import run_conformance

_LEGACY = '''\
"""A small legacy module with no spec."""


def add(a, b):
    return a + b


def _private(x):
    return x


class Calculator:
    def total(self):
        return 0
'''


def _legacy_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "lib").mkdir(parents=True)
    module = repo / "lib" / "calc.py"
    module.write_text(_LEGACY, encoding="utf-8")
    return repo, module


def test_public_symbols_skips_private():
    syms = characterize.public_symbols(_LEGACY)
    assert syms == ["add", "Calculator"]  # _private excluded, source order kept


def test_characterize_writes_spec_and_runnable_tests(tmp_path):
    repo, module = _legacy_repo(tmp_path)
    res = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "lib"
    )
    assert res.spec_id == "CALC"
    assert res.requirement_ids == ["CALC-FR-001", "CALC-FR-002"]
    # Spec stub exists with the reconstructed requirements and mandatory tier + non-goals.
    spec_text = res.spec_path.read_text(encoding="utf-8")
    assert "**Spec ID**: CALC" in spec_text
    assert "Risk Tier" in spec_text and "Non-Goals" in spec_text
    assert "CALC-FR-001" in spec_text and "CALC-FR-002" in spec_text
    # The generated test file is valid Python and references every requirement ID.
    test_text = res.test_path.read_text(encoding="utf-8")
    ast.parse(test_text)
    assert "CALC-FR-001" in test_text and "CALC-FR-002" in test_text


def test_generated_tests_pass_when_executed(tmp_path):
    repo, module = _legacy_repo(tmp_path)
    res = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "lib"
    )
    # The pinned public surface must actually hold for the current module.
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(res.test_path)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_characterized_module_passes_conformance(tmp_path):
    """The reconstructed spec + characterization tests trace cleanly (3PWR-FR-030)."""
    repo, module = _legacy_repo(tmp_path)
    res = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "lib"
    )
    gate = run_conformance(res.spec_path, [res.test_path])
    assert gate.status == "pass", gate.findings


def test_characterize_is_idempotent(tmp_path):
    repo, module = _legacy_repo(tmp_path)
    first = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "lib"
    )
    second = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "lib"
    )
    assert first.spec_path == second.spec_path  # reuses the same feature dir
    assert len(list((repo / "specs-src").glob("*-calc-characterization"))) == 1


def test_non_python_module_gets_spec_and_scaffold(tmp_path):
    repo = tmp_path / "repo"
    (repo / "web").mkdir(parents=True)
    module = repo / "web" / "app.js"
    module.write_text("export function go() { return 1 }\n", encoding="utf-8")
    res = characterize.characterize_module(
        repo, module, specs_dir=repo / "specs-src", tests_dir=repo / "web"
    )
    assert res.spec_path.exists()
    assert res.test_path.suffix == ".md"  # scaffold note for non-Python
    assert res.spec_id == "APP"
