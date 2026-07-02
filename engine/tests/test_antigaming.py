"""Gaming flag for hollow tests + opt-in diff-scoped mutation (HARDN-FR-010/011).

Unit layer: a diff that adds an assertion-free requirement-referencing test raises a
gate_gaming finding routed to human review (sanctioned only via the signed deviation
path); a tier with `diff_mutation: true` and a --base runs mutation scoped to the changed
files against the tier's threshold, quarantining when the tool is missing.
"""

from __future__ import annotations

import subprocess

from threepowers import gates
from threepowers.config import Settings
from threepowers.gaming import _scan_diff, detect_gaming


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def _repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    return root


def _commit_all(root, msg="c"):
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)


# --------------------------------------------------------------------------- HARDN-FR-010
def test_added_assertion_free_requirement_test_is_flagged(tmp_path):
    """HARDN-FR-010: a diff adding a hollow requirement-referencing test yields gate_gaming."""
    root = _repo(tmp_path)
    (root / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _commit_all(root)
    (root / "test_demo.py").write_text(
        "def test_ok():\n"
        "    assert True\n"
        "def test_hollow():\n"
        '    """DEMO-FR-001: bound, no assertion."""\n'
        "    pass\n",
        encoding="utf-8",
    )
    gr = detect_gaming(root, root, "HEAD")
    assert gr.status == "fail"
    assert any("assertion-free requirement-referencing test" in f for f in gr.findings)


def test_added_test_with_assertion_is_not_flagged(tmp_path):
    """HARDN-FR-010: an added requirement-referencing test WITH an assertion is fine."""
    root = _repo(tmp_path)
    (root / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _commit_all(root)
    (root / "test_demo.py").write_text(
        "def test_ok():\n"
        "    assert True\n"
        "def test_real():\n"
        '    """DEMO-FR-001: bound, asserted."""\n'
        "    assert 1 == 1\n",
        encoding="utf-8",
    )
    gr = detect_gaming(root, root, "HEAD")
    assert not any("assertion-free requirement" in f for f in gr.findings)


def test_untracked_hollow_test_file_is_flagged(tmp_path):
    """HARDN-FR-010: a brand-new (untracked) hollow test file cannot evade the diff."""
    root = _repo(tmp_path)
    (root / "seed.txt").write_text("x\n", encoding="utf-8")
    _commit_all(root)
    (root / "test_new.py").write_text(
        'def test_hollow():\n    """DEMO-FR-002: new + hollow."""\n    ...\n', encoding="utf-8"
    )
    gr = detect_gaming(root, root, "HEAD")
    assert any(
        "assertion-free requirement-referencing test" in f and "untracked" in f for f in gr.findings
    )


def test_ts_added_hollow_it_block_is_flagged():
    """HARDN-FR-010: the declaration union covers describe/it/test titles too."""
    diff = '+++ b/demo.test.ts\n+it("DEMO-FR-003: hollow", () => {\n+  // TODO\n+});\n'
    assert any("assertion-free requirement" in f for f in _scan_diff(diff))
    with_assert = (
        '+++ b/demo.test.ts\n+it("DEMO-FR-003: real", () => {\n+  expect(f()).toBe(1);\n+});\n'
    )
    assert not any("assertion-free requirement" in f for f in _scan_diff(with_assert))


def test_gaming_scan_is_deterministic():
    """HARDN-NFR-001: same diff → same findings."""
    diff = '+++ b/t.py\n+def test_h():\n+    """DEMO-FR-001."""\n+    pass\n'
    assert _scan_diff(diff) == _scan_diff(diff)


# --------------------------------------------------------------------------- HARDN-FR-011
def test_diff_mutation_paths_pick_changed_source_not_tests(tmp_path):
    """HARDN-FR-011: the scope is the changed SOURCE files; tests and non-code are excluded."""
    root = _repo(tmp_path)
    (root / ".3powers").mkdir()
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "seed.txt").write_text("x\n", encoding="utf-8")
    _commit_all(root)
    (root / "src" / "thing.py").write_text("A = 1\n", encoding="utf-8")
    (root / "src" / "latest_util.py").write_text("B = 2\n", encoding="utf-8")
    (root / "tests" / "test_thing.py").write_text("def test_t():\n    assert 1\n", encoding="utf-8")
    (root / "notes.md").write_text("n\n", encoding="utf-8")
    s = Settings(root=root)
    got = gates._diff_mutation_paths(s, "HEAD", root)
    assert got == ["src/latest_util.py", "src/thing.py"]


def test_is_test_file_hints():
    """HARDN-FR-011: test-file detection is name-based and does not over-match source names."""
    assert gates._is_test_file("tests/test_x.py")
    assert gates._is_test_file("src/x.test.ts")
    assert gates._is_test_file("pkg/thing_test.go")
    assert not gates._is_test_file("src/latest_util.py")  # 'test_' inside a word is not a test
    assert not gates._is_test_file("src/contested.py")
