"""Diff-coverage against a real git diff (3PWR-FR-029): changed lines come from git."""

from __future__ import annotations

import subprocess

from threepowers import covdiff


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init(repo):
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")


def test_modified_line_is_counted(tmp_path):
    _init(tmp_path)
    f = tmp_path / "a.py"
    f.write_text("l1\nl2\nl3\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    f.write_text("l1\nCHANGED\nl3\nl4\n")  # modify line 2, add line 4
    changed = covdiff.changed_lines(tmp_path, tmp_path, base="HEAD")
    key = str(f.resolve())
    assert key in changed and 2 in changed[key]


def test_untracked_file_counts_fully(tmp_path):
    _init(tmp_path)
    (tmp_path / "committed.py").write_text("x\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    new = tmp_path / "new.py"
    new.write_text("a\nb\n")  # untracked => every line is "changed"
    changed = covdiff.changed_lines(tmp_path, tmp_path, base="HEAD")
    assert changed[str(new.resolve())] == {1, 2}
