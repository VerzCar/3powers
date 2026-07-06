"""Diff-coverage tests (3PWR-FR-029): coverage is measured on changed lines."""

from __future__ import annotations

from threepowers.covdiff import diff_coverage, parse_lcov

LCOV = """TN:
SF:/proj/src/validate.ts
DA:1,1
DA:2,0
DA:3,5
end_of_record
"""


def test_parse_lcov(tmp_path):
    p = tmp_path / "lcov.info"
    p.write_text(LCOV, encoding="utf-8")
    parsed = parse_lcov(p)
    f = "/proj/src/validate.ts"
    assert parsed[f] == {1: 1, 2: 0, 3: 5}


def test_diff_coverage_scopes_to_changed_lines():
    """3PWR-FR-029: coverage is measured on the changed lines only, not the whole repository."""
    lcov = {"/proj/src/validate.ts": {1: 1, 2: 0, 3: 5}}
    # Only line 3 (covered) changed → 100%.
    pct, uncovered = diff_coverage(lcov, {"/proj/src/validate.ts": {3}})
    assert pct == 100.0 and uncovered == []
    # Line 2 (uncovered) changed → 0%, reported.
    pct, uncovered = diff_coverage(lcov, {"/proj/src/validate.ts": {2}})
    assert pct == 0.0 and uncovered == [{"file": "/proj/src/validate.ts", "line": 2}]


def test_no_changed_lines_falls_back_to_all_measured():
    lcov = {"/proj/src/validate.ts": {1: 1, 2: 0}}
    pct, _ = diff_coverage(lcov, {})
    assert pct == 50.0


def test_allow_scopes_measurement_to_named_files():
    """--paths / brownfield diff-scope: only the allowed files count (3PWR-FR-051, §4)."""
    lcov = {
        "/proj/src/trust.py": {1: 1, 2: 1},  # fully covered (the high-risk file)
        "/proj/src/legacy.py": {1: 0, 2: 0},  # untested legacy — must be excluded
    }
    pct, uncovered = diff_coverage(lcov, {}, allow={"/proj/src/trust.py"})
    assert pct == 100.0 and uncovered == []
    # Without the allow-list, the legacy file drags the number down.
    pct_all, _ = diff_coverage(lcov, {})
    assert pct_all == 50.0
