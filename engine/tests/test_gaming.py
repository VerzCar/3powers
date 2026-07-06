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
