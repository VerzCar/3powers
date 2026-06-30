"""Prompt/constitution eval harness (3PWR-FR-050): block on regression."""

from __future__ import annotations

from threepowers.evals import run_evals
from threepowers.verdict import STATUS_FAIL, STATUS_PASS


def _cases(tmp_path, body):
    p = tmp_path / "cases.yaml"
    p.write_text(body, encoding="utf-8")
    return p


def test_passes_when_assertions_hold(tmp_path):
    (tmp_path / "c.md").write_text("we keep a different model family rule\n", encoding="utf-8")
    cases = _cases(
        tmp_path,
        'cases:\n  - name: c\n    file: c.md\n    must_contain: ["different model family"]\n',
    )
    assert run_evals(tmp_path, cases).status == STATUS_PASS


def test_fails_on_missing_required_phrase(tmp_path):
    (tmp_path / "c.md").write_text("the rule was weakened\n", encoding="utf-8")
    cases = _cases(
        tmp_path,
        'cases:\n  - name: c\n    file: c.md\n    must_contain: ["different model family"]\n',
    )
    gate = run_evals(tmp_path, cases)
    assert gate.status == STATUS_FAIL and any("must contain" in f for f in gate.findings)


def test_fails_on_forbidden_phrase(tmp_path):
    (tmp_path / "c.md").write_text("oracle may read the implementation freely\n", encoding="utf-8")
    cases = _cases(
        tmp_path,
        "cases:\n  - name: c\n    file: c.md\n"
        '    must_not_contain: ["read the implementation freely"]\n',
    )
    gate = run_evals(tmp_path, cases)
    assert gate.status == STATUS_FAIL and any("must NOT contain" in f for f in gate.findings)


def test_missing_file_is_flagged(tmp_path):
    cases = _cases(tmp_path, 'cases:\n  - name: c\n    file: nope.md\n    must_contain: ["x"]\n')
    assert run_evals(tmp_path, cases).status == STATUS_FAIL
