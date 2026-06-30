"""Task scope discipline (3PWR-FR-016/017): req-id tagging and file-scope enforcement."""

from __future__ import annotations

import subprocess

from threepowers import scope
from threepowers.verdict import STATUS_FAIL, STATUS_PASS


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init(repo):
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def test_in_scope_change_passes(tmp_path):
    _init(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tasks.md").write_text(
        "- [ ] T001 [VUTIL-FR-001] do a (files: src/a.py)\n", encoding="utf-8"
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / "src" / "a.py").write_text("x = 2\n", encoding="utf-8")  # in-scope edit
    gate = scope.scope_check(tmp_path / "tasks.md", tmp_path, base="HEAD")
    assert gate.status == STATUS_PASS


def test_out_of_scope_edit_is_flagged(tmp_path):
    """3PWR-FR-017: an edit outside the task's declared files is flagged."""
    _init(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("y = 1\n", encoding="utf-8")
    (tmp_path / "tasks.md").write_text(
        "- [ ] T001 [VUTIL-FR-001] do a (files: src/a.py)\n", encoding="utf-8"
    )
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    (tmp_path / "src" / "b.py").write_text("y = 2\n", encoding="utf-8")  # out of scope
    gate = scope.scope_check(tmp_path / "tasks.md", tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("out-of-scope" in f for f in gate.findings)


def test_task_without_requirement_is_flagged(tmp_path):
    """3PWR-FR-016: every task must carry a requirement ID."""
    _init(tmp_path)
    (tmp_path / "x.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "tasks.md").write_text("- [ ] T001 do a thing (files: x.txt)\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    gate = scope.scope_check(tmp_path / "tasks.md", tmp_path, base="HEAD")
    assert gate.status == STATUS_FAIL
    assert any("without requirement" in f for f in gate.findings)
