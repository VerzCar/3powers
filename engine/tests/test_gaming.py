"""Gate-gaming detection (3PWR-FR-035).

Suppression markers are assembled from fragments so this test's own source does not
contain a contiguous trigger token (which would self-flag during self-application).
"""

from __future__ import annotations

import subprocess

from threepowers import gaming
from threepowers.verdict import STATUS_FAIL, STATUS_PASS

_TYPE_IGNORE = "# type:" + " ignore"
_NOQA = "#" + " noqa"


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init(repo):
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def _commit(repo, name, content):
    (repo / name).write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "x")


def test_clean_diff_passes(tmp_path):
    _init(tmp_path)
    _commit(tmp_path, "a.py", "def f():\n    return 1\n")
    (tmp_path / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    assert gaming.detect_gaming(tmp_path, tmp_path, base="HEAD").status == STATUS_PASS


def test_added_suppression_is_flagged(tmp_path):
    """3PWR-FR-035: an added lint/type suppression is flagged as gate-gaming for human review."""
    _init(tmp_path)
    _commit(tmp_path, "a.py", "x = 1\n")
    (tmp_path / "a.py").write_text(f"x = 1  {_TYPE_IGNORE}\ny = 2  {_NOQA}\n", encoding="utf-8")
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("suppression" in f for f in gate.findings)


def test_removed_assertion_is_flagged(tmp_path):
    """3PWR-FR-035: a deleted test assertion is flagged as gate-gaming for human review."""
    _init(tmp_path)
    _commit(tmp_path, "t.py", "def test():\n    assert foo()\n    assert bar()\n")
    (tmp_path / "t.py").write_text("def test():\n    assert foo()\n", encoding="utf-8")
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("assertion removed" in f for f in gate.findings)


def test_suppression_in_untracked_file_is_flagged(tmp_path):
    """A suppression in a brand-new (untracked) file must not evade the gate."""
    _init(tmp_path)
    _commit(tmp_path, "keep.py", "x = 1\n")
    (tmp_path / "new.py").write_text(f"y = 2  {_TYPE_IGNORE}\n", encoding="utf-8")
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("untracked" in f for f in gate.findings)


# ----------------------------------------------- plan 035 Track B: false-positive removal
def test_trust_spine_diff_is_never_gaming(tmp_path):
    """Plan 035 Track B: a change that only touches .3powers/ (e.g. a ledger append)
    yields zero findings — engine-managed audit state is not reviewed code."""
    _init(tmp_path)
    (tmp_path / ".3powers").mkdir()
    _commit(tmp_path, ".3powers/ledger.jsonl", '{"seq": 1}\n')
    (tmp_path / ".3powers" / "ledger.jsonl").write_text(
        f'{{"seq": 1}}\n{{"seq": 2, "note": "{_NOQA}"}}\n', encoding="utf-8"
    )
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_PASS
    assert gate.findings == []


def test_untracked_trust_spine_file_is_skipped(tmp_path):
    """Plan 035 Track B: an untracked file under .3powers/ never counts as gaming."""
    _init(tmp_path)
    _commit(tmp_path, "keep.py", "x = 1\n")
    (tmp_path / ".3powers").mkdir()
    (tmp_path / ".3powers" / "scratch.txt").write_text(f"note {_TYPE_IGNORE}\n", encoding="utf-8")
    assert gaming.detect_gaming(tmp_path, tmp_path, base="HEAD").status == STATUS_PASS


def test_reordered_testing_import_is_not_an_assertion_removal(tmp_path):
    """Plan 035 Track B: `expect` in a moved import line is an identifier, not an assertion
    call — reordering testing imports must not read as an assertion removal."""
    _init(tmp_path)
    _commit(
        tmp_path,
        "a.test.ts",
        'import { beforeEach, describe, expect, it, vi } from "vitest";\n'
        'it("x", () => {\n  expect(f()).toBe(1);\n});\n',
    )
    (tmp_path / "a.test.ts").write_text(
        'import { describe, expect, it, vi, beforeEach } from "vitest";\n'
        'it("x", () => {\n  expect(f()).toBe(1);\n});\n',
        encoding="utf-8",
    )
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_PASS
    assert gate.findings == []


def test_deleted_expect_call_is_still_flagged(tmp_path):
    """Plan 035 Track B: a genuinely deleted expect(...) call (net per-file loss) still fails."""
    _init(tmp_path)
    _commit(
        tmp_path,
        "a.test.ts",
        'it("x", () => {\n  expect(f()).toBe(1);\n  expect(g()).toBe(2);\n});\n',
    )
    (tmp_path / "a.test.ts").write_text(
        'it("x", () => {\n  expect(f()).toBe(1);\n});\n', encoding="utf-8"
    )
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("assertion removed" in f for f in gate.findings)


def test_added_eslint_suppression_is_still_flagged(tmp_path):
    """Plan 035 Track B: an added eslint suppression stays a gaming finding."""
    _init(tmp_path)
    _commit(tmp_path, "a.ts", "const x = 1;\n")
    eslint_disable = "eslint" + "-disable"  # assembled so this file never self-flags
    (tmp_path / "a.ts").write_text(
        f"// {eslint_disable}-next-line\nconst x: unknown = 1;\n", encoding="utf-8"
    )
    gate = gaming.detect_gaming(tmp_path, tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("eslint suppression" in f for f in gate.findings)


def test_assertion_pattern_matches_calls_not_bare_identifiers():
    """Plan 035 Track B: assertion detection keys on calls (or Python's paren-less assert
    statement), so real matchers still count while identifier mentions do not."""
    matching = [
        "expect(value)",
        "expect(el).toHaveClass('active')",
        "expect(fn).toHaveBeenCalledTimes(2)",
        "expect(n).toBeGreaterThanOrEqual(1)",
        "  .toBe(3)",
        "assert x == 1",
        "    assert foo()",
        "self.assertEqual(a, b)",
        "assert.strictEqual(a, b)",
        "with pytest.raises(ValueError):",
        't.Errorf("bad: %v", err)',
        "require.NoError(t, err)",
    ]
    for line in matching:
        assert gaming._ASSERT.search(line), line
    non_matching = [
        'import { beforeEach, describe, expect, it, vi } from "vitest";',
        "const expected = makeExpectation();",
        "// the assert helpers live elsewhere",
    ]
    for line in non_matching:
        assert not gaming._ASSERT.search(line), line
