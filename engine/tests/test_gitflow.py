"""The git-lifecycle commit primitives: the phased-implement commit subject, the engine-state
commit subject, and the engine-state commit that persists the trust spine's own writes.

Everything here runs offline against a throwaway git repo (no network, no agent). The commit
subjects are pure string functions; :func:`gitflow.commit_engine_state` is exercised end to end
against a real index so its path filtering, no-op path, author identity, and failure classification
are proven, not mocked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from threepowers import gitflow


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    return proc.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    """A git repo with one initial commit and a developer identity of its own."""
    root = tmp_path / "repo"
    root.mkdir()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "human@e.st"],
        ["git", "config", "user.name", "human"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)
    (root / "README.md").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)
    return root


# --------------------------------------------------------------------------- phase commit subject
def test_phase_commit_message_names_the_phase_of_the_total_with_description():
    """PLAN-040: the per-phase implement subject is ``implement(phase N/M): <description>``."""
    assert (
        gitflow.phase_commit_message(2, 5, "wire the parser to the loader")
        == "implement(phase 2/5): wire the parser to the loader"
    )


def test_phase_commit_message_falls_back_to_the_bare_label_without_a_description():
    """PLAN-040: with no usable description the bare ``implement(phase N/M)`` label stands — a
    phase commit is never blocked on message generation."""
    assert gitflow.phase_commit_message(1, 1, "") == "implement(phase 1/1)"
    assert gitflow.phase_commit_message(3, 4, "   ") == "implement(phase 3/4)"


def test_phase_commit_message_collapses_whitespace_and_bounds_length():
    """PLAN-040: the description is collapsed to a single line and bounded, so a multi-line or
    runaway agent ``COMMIT:`` line still yields a clean, bounded subject."""
    msg = gitflow.phase_commit_message(1, 2, "first\n\n  second   line\tthird")
    assert msg == "implement(phase 1/2): first second line third"
    long = gitflow.phase_commit_message(1, 2, "x " * 300)
    assert len(long) <= len("implement(phase 1/2): ") + 200


def test_phase_commit_message_is_deterministic_in_its_inputs():
    """PLAN-040: identical (index, total, description) render the identical subject."""
    a = gitflow.phase_commit_message(2, 3, "same work")
    b = gitflow.phase_commit_message(2, 3, "same work")
    assert a == b


# --------------------------------------------------------------------------- engine-state subject
def test_engine_state_commit_message_names_the_step_and_spec_id():
    """PLAN-040: the engine-state subject is ``3pwr(<spec>): record engine state — <step>`` — it
    is not a producing stage and is distinguishable from one in the log."""
    subject = gitflow.engine_state_commit_message("PAY", "verify")
    assert subject == "3pwr(PAY): record engine state — verify"
    # distinguishable from a producing stage commit for the same step (subject prefix differs)
    assert not subject.startswith(gitflow.stage_commit_message("PAY", "verify"))


def test_engine_state_commit_message_is_deterministic():
    """PLAN-040: identical (spec_id, step) always render the identical subject."""
    assert gitflow.engine_state_commit_message(
        "R", "signoff"
    ) == gitflow.engine_state_commit_message("R", "signoff")


# --------------------------------------------------------------------------- engine-state commit
def _dirty_engine_state(root: Path) -> None:
    """Make the ledger, a run's progress.md, and the run lock dirty — the engine-owned writes."""
    (root / ".3powers").mkdir(parents=True, exist_ok=True)
    (root / ".3powers" / "ledger.jsonl").write_text('{"seq":0}\n', encoding="utf-8")
    (root / ".3powers" / "run.lock").write_text('{"pid":1}\n', encoding="utf-8")
    feat = root / "specs-src" / "030-add-x"
    feat.mkdir(parents=True, exist_ok=True)
    (feat / "progress.md").write_text("# Run 030\n", encoding="utf-8")


def test_commit_engine_state_stages_only_engine_owned_paths(tmp_path):
    """PLAN-040: an engine-state commit stages the ledger and the run's progress.md and nothing
    else — a developer's unrelated working-tree change is never swept in."""
    root = _repo(tmp_path)
    _dirty_engine_state(root)
    (root / "notes.txt").write_text("my own scratch\n", encoding="utf-8")  # unrelated

    outcome = gitflow.commit_engine_state(
        root, message=gitflow.engine_state_commit_message("R", "verify")
    )
    assert outcome.sha and not outcome.error and not outcome.noop
    files = _git(root, "show", "--name-only", "--pretty=format:", "HEAD").split()
    assert ".3powers/ledger.jsonl" in files
    assert "specs-src/030-add-x/progress.md" in files
    assert "notes.txt" not in files  # unrelated developer work never committed
    assert _git(root, "status", "--porcelain").count("notes.txt") == 1  # still dirty, untouched


def test_commit_engine_state_never_commits_the_ephemeral_run_lock(tmp_path):
    """PLAN-040 (regression): the ephemeral ``.3powers/run.lock`` — deleted the moment the run
    releases the lock — is NEVER staged into an engine-state commit; committing it would leave a
    "deleted run.lock" dirtying the tree at the next pause and break the clean-tree guarantee."""
    root = _repo(tmp_path)
    _dirty_engine_state(root)

    gitflow.commit_engine_state(root, message=gitflow.engine_state_commit_message("R", "verify"))
    files = _git(root, "show", "--name-only", "--pretty=format:", "HEAD").split()
    assert ".3powers/run.lock" not in files
    # the lock stays a purely local, uncommitted artifact — simulate release and confirm the tree is
    # clean save for the still-present lock (never a "deleted" phantom from a prior commit)
    assert ".3powers/run.lock" in _git(root, "status", "--porcelain")
    (root / ".3powers" / "run.lock").unlink()  # the run releases the lock
    assert _git(root, "status", "--porcelain") == ""  # clean tree — no deleted-lock phantom


def test_commit_engine_state_is_a_noop_success_when_nothing_engine_owned_is_dirty(tmp_path):
    """PLAN-040: with no dirty engine-owned path the commit is a no-op success — no empty commit is
    forced, so it is safe to call at every judgment step and before every human-gate pause."""
    root = _repo(tmp_path)
    head_before = _git(root, "rev-parse", "HEAD")

    outcome = gitflow.commit_engine_state(root, message="unused")
    assert outcome.noop and not outcome.sha and not outcome.error
    assert _git(root, "rev-parse", "HEAD") == head_before  # no commit created


def test_commit_engine_state_keeps_the_configured_3pwr_author(tmp_path):
    """PLAN-040 / GITX-FR-012: an engine-state commit is authored as 3pwr via per-commit overrides;
    the developer's own git identity is never mutated."""
    root = _repo(tmp_path)
    _dirty_engine_state(root)

    gitflow.commit_engine_state(root, message=gitflow.engine_state_commit_message("R", "verify"))
    assert _git(root, "log", "-1", "--pretty=%an <%ae>") == "3pwr <3pwr@3powers.local>"
    assert _git(root, "config", "user.name") == "human"  # developer identity untouched


def test_commit_engine_state_classifies_a_git_failure_as_an_error(tmp_path):
    """PLAN-040: a genuine git failure surfaces as a non-empty ``error`` (the caller classifies it
    :data:`gitflow.CLASS_COMMIT_FAILED`) — it is reported, never forced or silently swallowed."""
    root = _repo(tmp_path)
    _dirty_engine_state(root)
    (root / ".git" / "index.lock").write_text("", encoding="utf-8")  # a locked index fails the add

    outcome = gitflow.commit_engine_state(root, message="x")
    assert outcome.error and not outcome.sha and not outcome.noop
    assert gitflow.CLASS_COMMIT_FAILED == "git_commit_failed"  # the class the caller attaches
