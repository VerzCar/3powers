"""The git-integrated run lifecycle — mandatory pre/post-stage git hooks.

This module turns the executive from committing *opportunistically* (the earlier opt-out
checkpoint) into committing *safely*: every run is isolated to its own **dedicated branch** named
from the run workspace's already-allocated ``<NNN>-<slug>`` run identity (the identity is
consumed, never redefined); a run **refuses to start** on a working tree carrying uncommitted
changes that are not the run's own; each producing stage lands as **exactly one commit** staging
only the run's produced paths, with an **agent-written message** and — when 3pwr itself commits —
a **3pwr author identity** applied per-commit.

Everything here is deterministic, offline path/subprocess logic — no network, no model call.
The agent-written commit *message* is the only model-touched output and it is
captured as commit data, never as a gate or ledger input. Data safety is load-bearing:
branch switches and commits are **refused, never forced**; the user's git
configuration is never mutated (the 3pwr author rides on per-invocation ``-c`` overrides); no
history is rewritten and nothing is force-pushed. The discipline is mandatory by default and
relaxable only via a recorded signed deviation on a named guard.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .runner import _changed_files, _git

# The named guards a signed deviation may relax: each relaxable guard maps to exactly
# one deviation gate — a relaxation is always a signed, revocable ledger entry, never a flag.
GATE_CLEAN_START = "git_clean_start"  # the clean-start guard
GATE_STAGE_COMMIT = "git_stage_commit"  # the mandatory per-stage commit
GATE_RUN_BRANCH = "git_run_branch"  # the branch-isolation guard at stage boundaries
GIT_GUARDS: tuple[str, ...] = (GATE_CLEAN_START, GATE_STAGE_COMMIT, GATE_RUN_BRANCH)

# Failure classes for the run's git hooks — additive values on the existing run/failure record
# (like the run workspace's completion classes), surfaced by `--status` and exiting on the setup path.
CLASS_COMMIT_FAILED = "git_commit_failed"
CLASS_BRANCH_FAILED = "git_branch_failed"

# The documented `git.yaml` defaults: a missing or malformed file falls back to these.
DEFAULT_BRANCH_PREFIX = "3pwr/"
DEFAULT_BASE_BRANCH = "main"
DEFAULT_AUTHOR_NAME = "3pwr"
DEFAULT_AUTHOR_EMAIL = "3pwr@3powers.local"

# Engine-owned state under `.3powers/` — the trust spine's own writes (ledger appends, verdicts,
# transcripts, seeded config). Never a developer's "unrelated work", so the clean-start guard
# ignores the whole prefix (the clean-start guard applies only to work outside the run).
ENGINE_STATE_PREFIX = ".3powers/"

# The engine-written run progress file inside a feature workspace. A paused or
# failed run legitimately leaves it updated after its last stage commit, so — like the ledger — it
# is engine-owned state the clean-start guard never treats as a developer's unrelated work.
_PROGRESS_FILE = re.compile(r"^specs/[^/]+/progress\.md$")

# Bound for the agent-written description folded into a commit subject.
_MESSAGE_MAX_LEN = 200
_COMMIT_LINE = re.compile(r"^\s*COMMIT:\s*(\S.*)$", re.MULTILINE)


# --------------------------------------------------------------------------- preferences
@dataclass(frozen=True)
class GitPrefs:
    """The resolved git-integration preferences — a pure function of ``git.yaml`` + the defaults."""

    branch_prefix: str = DEFAULT_BRANCH_PREFIX
    base_branch: str = DEFAULT_BASE_BRANCH
    author_name: str = DEFAULT_AUTHOR_NAME
    author_email: str = DEFAULT_AUTHOR_EMAIL
    malformed: bool = False  # the file existed but was not a valid mapping — warn once, never crash


def load_prefs(path: Path) -> GitPrefs:
    """Resolve ``.3powers/config/git.yaml`` tolerantly (mirrors ``ui.yaml``).

    A missing file yields the shipped defaults; a malformed one yields the defaults with
    ``malformed=True`` so the caller warns exactly once. Deterministic in the file bytes —
    identical inputs resolve identical branch names and author attribution."""
    if not path.exists():
        return GitPrefs()
    data: Any = {}
    malformed = False
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        malformed = True
        data = {}
    if data is None:
        data = {}
    elif not isinstance(data, dict):
        malformed = True
        data = {}
    author = data.get("author") if isinstance(data.get("author"), dict) else {}
    return GitPrefs(
        branch_prefix=str(data.get("branch_prefix") or DEFAULT_BRANCH_PREFIX),
        base_branch=str(data.get("base_branch") or DEFAULT_BASE_BRANCH),
        author_name=str(author.get("name") or DEFAULT_AUTHOR_NAME),
        author_email=str(author.get("email") or DEFAULT_AUTHOR_EMAIL),
        malformed=malformed,
    )


# --------------------------------------------------------------------------- precondition
def precondition(cwd: Path) -> str:
    """The named missing-git condition, or ``""`` when a working repository is available.

    A pure function of the environment/repository state: git must be on
    PATH and ``cwd`` must lie inside a git work tree (a ``.git`` directory — or file, for a linked
    worktree — on the path upward). No network, no model."""
    if shutil.which("git") is None:
        return "git is not installed / not on PATH — install git; a run requires version control"
    for candidate in [cwd.resolve(), *cwd.resolve().parents]:
        if (candidate / ".git").exists():
            return ""
    return f"{cwd} is not inside a git repository — run `git init` first; a run requires version control"


# --------------------------------------------------------------------------- branch
def run_branch_name(prefix: str, run_identity: str) -> str:
    """The run's dedicated branch name — ``<prefix><NNN>-<slug>``.

    A deterministic, byte-identical function of the configured prefix and the run workspace's
    identity; this module neither allocates the number nor derives the slug — the run workspace
    owns that."""
    return f"{prefix}{run_identity}"


def current_branch(cwd: Path) -> str:
    """The checked-out branch, or ``""`` on a detached HEAD / an unborn or non-repo state."""
    rc, out, _ = _git(cwd, ["symbolic-ref", "--short", "-q", "HEAD"])
    return out.strip() if rc == 0 else ""


def branch_exists(cwd: Path, name: str) -> bool:
    return _git(cwd, ["rev-parse", "--verify", "--quiet", f"refs/heads/{name}"])[0] == 0


def base_tip(cwd: Path, base: str) -> str:
    """The base branch's tip SHA, or ``""`` when the base does not resolve."""
    rc, out, _ = _git(cwd, ["rev-parse", "--verify", "--quiet", f"refs/heads/{base}"])
    return out.strip() if rc == 0 else ""


def ensure_run_branch(cwd: Path, branch: str, base: str) -> str:
    """Create-or-switch to the run's dedicated branch; ``""`` on success, else the error detail.

    An existing branch is re-entered (a resume never creates a second one); a missing
    one is created off the configured base when it resolves, else off the current commit (the
    detached-HEAD / unborn-repo / no-base edge). Never forced: a switch git refuses (it would
    clobber changes) is surfaced, not overridden, and no history is rewritten."""
    if current_branch(cwd) == branch:
        return ""
    if branch_exists(cwd, branch):
        rc, _, err = _git(cwd, ["checkout", "-q", branch])
        return "" if rc == 0 else f"cannot switch to run branch '{branch}': {err.strip()}"
    start_point = [base] if base and base_tip(cwd, base) else []
    rc, _, err = _git(cwd, ["checkout", "-q", "-b", branch, *start_point])
    return "" if rc == 0 else f"cannot create run branch '{branch}': {err.strip()}"


def branch_from_ledger(entries: Iterable[dict], spec_id: str) -> str:
    """The run's recorded branch, read back from the signed ``run``/``start`` entry.

    The latest ``start`` entry carrying a ``branch`` wins — recovered offline from the ledger alone,
    no branch scan and no guessing. ``""`` for a run predating the git discipline (the caller
    derives it from the run's workspace identity instead — the same deterministic function)."""
    branch = ""
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "start" and payload.get("branch"):
            branch = str(payload["branch"])
    return branch


# --------------------------------------------------------------------------- clean start / stop
def uncommitted(cwd: Path) -> list[str]:
    """Repo-relative uncommitted (modified/untracked) paths — engine transcripts already excluded."""
    return _changed_files(cwd)


def unrelated_changes(
    changed: Iterable[str], run_paths: Iterable[str], feature_prefix: str = ""
) -> list[str]:
    """The uncommitted paths NOT produced by the run — the clean-start guard's subjects.

    Pure and deterministic given its inputs. "Produced by the run" is the run's
    recorded produced-path set plus anything inside the run's feature folder; the engine's own
    trust-spine state under ``.3powers/`` (ledger appends, verdicts, transcripts, seeded config)
    and any feature workspace's engine-written ``progress.md`` are never a
    developer's unrelated work and are ignored."""
    owned = set(run_paths)
    out: list[str] = []
    for p in changed:
        if p in owned or p.startswith(ENGINE_STATE_PREFIX) or _PROGRESS_FILE.match(p):
            continue
        if feature_prefix and p.startswith(feature_prefix):
            continue
        out.append(p)
    return sorted(out)


def recorded_run_paths(entries: Iterable[dict], spec_id: str) -> set[str]:
    """Every path the run's signed ``run``/``stage``-or-``checkpoint`` entries record as produced.

    The offline-recoverable run-produced set: a prior stage that crashed
    after writing but before committing recorded its artifacts in its ``stage`` entry, so its
    changes are tolerated and swept into the next post-stage commit — only *unrelated* changes
    block."""
    paths: set[str] = set()
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") in ("stage", "checkpoint"):
            paths.update(str(p) for p in payload.get("artifacts", []))
    return paths


def uncommitted_run_paths(cwd: Path, entries: Iterable[dict], spec_id: str) -> list[str]:
    """The run-produced paths still uncommitted — must be empty after a post-stage commit
    (produced ∩ uncommitted == ∅) and at every stage boundary."""
    produced = recorded_run_paths(entries, spec_id)
    return sorted(produced & set(_changed_files(cwd)))


def clean_start_refusal(unrelated: list[str]) -> str:
    """The refusal message naming the offending paths and the signed deviation.

    The guard never discards or forces past the changes — they stay byte-identical on disk;
    the only way through is the recorded, revocable relaxation."""
    shown = ", ".join(unrelated[:8]) + (" …" if len(unrelated) > 8 else "")
    return (
        f"cannot start — the working tree has uncommitted changes not produced by this run: {shown}. "
        "Commit or stash them first, or relax the guard on the record: "
        f'`3pwr deviation --gate {GATE_CLEAN_START} --approver <you> --note "<why>"` '
        "(your edits are left untouched)"
    )


# --------------------------------------------------------------------------- stage commit
@dataclass(frozen=True)
class CommitOutcome:
    """One post-stage commit's result: a new commit, a no-op (already committed), or an error."""

    sha: str = ""  # non-empty: a new commit was created
    error: str = ""  # non-empty: the commit failed (clean-stop would be violated)

    @property
    def noop(self) -> bool:
        return not self.sha and not self.error


def agent_commit_description(root: Path, transcript_rel: str) -> str:
    """The agent-written stage description, extracted from the persisted transcript.

    The stage prompt asks the agent to end its output with one ``COMMIT: <description>`` line; the
    LAST such line in the attempt's transcript wins (an agent may echo the instruction earlier).
    ``""`` — no transcript, an unreadable one, or no usable line — means the caller falls back to
    the deterministic default so a commit is never blocked on message generation."""
    if not transcript_rel:
        return ""
    path = root / transcript_rel
    if not path.is_file():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    matches = _COMMIT_LINE.findall(text)
    if not matches:
        return ""
    desc = " ".join(matches[-1].split())  # one line, collapsed whitespace
    return desc[:_MESSAGE_MAX_LEN].rstrip()


def stage_commit_message(spec_id: str, step: str, description: str = "") -> str:
    """The stage commit's subject: ALWAYS carries the stage identifier and
    the run's spec id; the agent's description is appended when present, and the deterministic
    fallback is the bare ``3pwr(<spec-id>): <step>`` label."""
    base = f"3pwr({spec_id}): {step}"
    return f"{base} — {description}" if description else base


def commit_stage(
    cwd: Path,
    paths: list[str],
    *,
    message: str,
    author_name: str = DEFAULT_AUTHOR_NAME,
    author_email: str = DEFAULT_AUTHOR_EMAIL,
) -> CommitOutcome:
    """Commit one producing stage's ``paths`` as exactly one commit, authored as 3pwr.

    Stages only the named produced paths (never a blanket ``add -A`` — unrelated files are never
    swept in). The 3pwr identity rides on per-invocation ``-c user.name/-c user.email`` overrides,
    so the developer's configured git identity is never mutated. Paths a human
    already committed by hand stage to an empty index — a no-op, keeping the human's own commit and
    author. Only an actual git failure is an error; it is surfaced, never forced."""
    if not paths:
        return CommitOutcome()
    rc, _, err = _git(cwd, ["add", "--", *paths])
    if rc != 0:
        return CommitOutcome(error=f"git add failed: {err.strip()}")
    if _git(cwd, ["diff", "--cached", "--quiet"])[0] == 0:  # nothing actually staged
        return CommitOutcome()
    rc, _, err = _git(
        cwd,
        [
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-q",
            "-m",
            message,
        ],
    )
    if rc != 0:
        return CommitOutcome(error=f"git commit failed: {err.strip()}")
    rc, out, _ = _git(cwd, ["rev-parse", "--short", "HEAD"])
    return CommitOutcome(sha=out.strip() if rc == 0 else "committed")


def committed_steps(entries: Iterable[dict], spec_id: str) -> list[str]:
    """The producing steps with a recorded stage commit, in ledger order.

    Derived from the signed ``run``/``checkpoint`` entries alone — deterministic, offline, no
    model — so the status view's per-stage committed indication needs no git scan."""
    steps: list[str] = []
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") == "checkpoint" and payload.get("step"):
            step = str(payload["step"])
            if step not in steps:
                steps.append(step)
    return steps
