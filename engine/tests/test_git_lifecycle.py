"""The git-integrated run lifecycle — mandatory pre/post-stage git hooks (GITX, spec 018).

Exercises the whole GITX surface with fake agents and no network: the mandatory hooks and the git
precondition (GITX-FR-001/002), the dedicated per-run branch reusing SRCX's ``<NNN>-<slug>``
identity — created off the base, reused on resume, bound in the signed ledger (GITX-FR-003..006) —
clean start / clean stop (GITX-FR-007/008), the status surfacing (GITX-FR-009), the single
agentically-messaged, 3pwr-authored stage commit (GITX-FR-010..013), the deviation-only relaxation
plus ``git.yaml`` (GITX-FR-014/015), the manual-drive boundary checks (GITX-FR-016), and the
determinism / additive-ledger / data-safety / no-config-mutation NFRs (GITX-NFR-001..005).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import deviations, gitflow, prompts, runner, runpreflight, workspace
from threepowers.cli import EXIT_FAIL, EXIT_PAUSED, EXIT_SETUP, main
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_PASS, Verdict


# --------------------------------------------------------------------------- fixtures (fake agent, no network)
def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    return proc.stdout.strip()


def _git_ok(cwd: Path, *args: str) -> None:
    """Run a git subcommand that must succeed, discarding output (test setup helper)."""
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "human@e.st"],
        ["git", "config", "user.name", "human"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _writer(spec_id="RUN", skip=(), commit_line=True):
    """A fake agent writing each stage's declared artifact flat into the folder the prompt names,
    ending its output with the requested ``COMMIT:`` description line (GITX-FR-011)."""

    def fake(argv, **kw):
        import re

        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
        d = cwd / (m.group(1) if m else f"specs-src/{spec_id}")
        step = ""
        if "# Discovery agent" in prompt and "discovery" not in skip:
            step = "discovery"
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
        elif "# Specify agent" in prompt and "specify" not in skip:
            step = "specify"
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "# Plan agent" in prompt and "plan" not in skip:
            step = "plan"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in prompt and "tasks" not in skip:
            step = "tasks"
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "# Oracle agent" in prompt and "oracle" not in skip:
            step = "oracle"
            t = cwd / "tests" / "oracle" / spec_id
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "# Implement agent" in prompt and "implement" not in skip:
            step = "implement"
            src = cwd / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        out = "changes written"
        if step and commit_line:
            # The agent obeys the fixed COMMIT-line request in the assembled prompt (GITX-FR-011).
            out += f"\nCOMMIT: authored the {step} work for the run"
        tee = kw.get("tee")
        if tee is not None:  # a real dispatch tees stdout into the persisted transcript
            tee.write(out + "\n")
            tee.flush()
        return (0, out, "")

    return fake


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    for name, fam in (("claude", "anthropic"), ("codex", "openai")):
        (root / ".3powers" / "agents" / f"{name}.yaml").write_text(
            yaml.safe_dump({"command": name, "family": fam, "headless": True, "prompt_flag": "-p"}),
            encoding="utf-8",
        )
    (root / ".3powers" / "config" / "roles.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "diversity_level": "family",
                "roles": {
                    "coder": {"integration": "claude", "model_family": "anthropic"},
                    "oracle": {"integration": "codex", "model_family": "openai"},
                },
            }
        ),
        encoding="utf-8",
    )
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    _git_init(root)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", _writer())
    return root


def _mock_gates_green(monkeypatch):
    import threepowers.cli as climod

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )


def _run(root: Path, *extra: str) -> int:
    return main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN", *extra])


def _resume(root: Path) -> int:
    return main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "human",
        ]
    )


def _deviate(root: Path, gate: str) -> int:
    return main(
        ["--root", str(root), "deviation", "--gate", gate, "--approver", "human", "--note", "test"]
    )


def _log_subjects(root: Path, ref: str = "HEAD") -> list[str]:
    out = _git(root, "log", "--pretty=%s", ref)
    return out.splitlines() if out else []


# --------------------------------------------------------------------------- A. mandatory hooks (GITX-FR-001/002)
def test_run_refuses_outside_a_git_repo(tmp_path, monkeypatch, capsys):
    """GITX-FR-002: a working git repository is a run PRECONDITION — a non-git start is refused,
    naming the missing-git condition, on the setup/dispatch (non-gate-red) exit path."""
    root = tmp_path / "norepo"
    (root / ".3powers" / "config").mkdir(parents=True)
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    capsys.readouterr()  # drain the keygen output before the JSON assertion
    rc = main(["--root", str(root), "run", "add x", "--no-input", "--json", "--spec-id", "G"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_SETUP and obj["status"] == "preflight_failed"
    assert any("git" in m["prerequisite"] for m in obj["missing"])


def test_git_precondition_is_pure_and_names_the_condition(tmp_path, monkeypatch):
    """GITX-FR-002 (property): the precondition is a pure function of the environment/repository
    state — git absent and non-repo yield distinct named conditions; a repo yields none."""
    assert "not inside a git repository" in gitflow.precondition(tmp_path)
    (tmp_path / "seed.txt").write_text("x\n", encoding="utf-8")
    _git_init(tmp_path)
    assert gitflow.precondition(tmp_path) == ""
    monkeypatch.setattr(gitflow.shutil, "which", lambda cmd: None)
    assert "not installed" in gitflow.precondition(tmp_path)


def test_hooks_wrap_every_producing_stage(run_repo, monkeypatch):
    """GITX-FR-001 + GITX-FR-013 (property): each producing stage that produced changes is exactly
    one engine commit on the run branch — the hooks are not skippable by any plain flag."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo) == EXIT_PAUSED
    assert _resume(run_repo) == EXIT_PAUSED  # → signoff gate
    subjects = _log_subjects(run_repo, "3pwr/001-add-x")
    for step in ("specify", "plan", "tasks", "oracle", "implement"):
        assert sum(1 for s in subjects if s.startswith(f"3pwr(RUN): {step}")) == 1, subjects


# --------------------------------------------------------------------------- B. the dedicated branch (GITX-FR-003..006)
def test_fresh_run_creates_branch_from_srcx_identity_off_base(run_repo, capsys):
    """GITX-FR-003 + GITX-FR-006 + GITX-SC-001: a fresh run creates and switches to
    ``<prefix><NNN>-<slug>`` (SRCX's identity — no new number) off the base BEFORE any commit;
    every stage commit lands there and the base branch's tip is unchanged."""
    base_before = _git(run_repo, "rev-parse", "main")
    assert _run(run_repo) == EXIT_PAUSED
    assert gitflow.current_branch(run_repo) == "3pwr/001-add-x"
    assert _git(run_repo, "rev-parse", "main") == base_before  # GITX-FR-006: base tip unchanged
    subjects = _log_subjects(run_repo, "main")
    assert not any(s.startswith("3pwr(") for s in subjects)  # nothing committed on the base
    assert any(s.startswith("3pwr(RUN): specify") for s in _log_subjects(run_repo))


def test_branch_name_is_deterministic():
    """GITX-FR-003 (property): the branch name is a byte-identical pure function of the configured
    prefix and the run's SRCX identity (GITX-NFR-001)."""
    a = gitflow.run_branch_name("3pwr/", "017-run-artifact-workspace")
    b = gitflow.run_branch_name("3pwr/", "017-run-artifact-workspace")
    assert a == b == "3pwr/017-run-artifact-workspace"
    assert gitflow.run_branch_name("wip/", "017-x") == "wip/017-x"


def test_run_branch_numbers_scans_local_and_remote_refs(tmp_path):
    """Covers: REQ-A — run_branch_numbers parses <branch_prefix><NNN>-* from local refs (and, with
    a remote given, refs/remotes/<remote>/*), scopes to the prefix, and returns [] on a git error /
    non-repo without raising."""
    # a non-repo directory: no refs, no crash, no raise
    assert gitflow.run_branch_numbers(tmp_path, "3pwr/") == []
    root = tmp_path / "repo"
    root.mkdir()
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git_init(root)  # branch main, one commit
    head = _git(root, "rev-parse", "HEAD")
    for br in ("3pwr/020-alpha", "3pwr/007-beta", "wip/099-ignored"):
        subprocess.run(["git", "branch", br, head], cwd=str(root), check=True, capture_output=True)
    # a remote-tracking ref planted locally — no network, no remote configured
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/3pwr/044-remote", head],
        cwd=str(root),
        check=True,
        capture_output=True,
    )
    # local-only scan: the run branches, ignoring the other-prefix branch and the remote-tracking ref
    assert sorted(gitflow.run_branch_numbers(root, "3pwr/")) == [7, 20]
    # remote-aware scan: folds in the remote-tracking run branch
    assert sorted(gitflow.run_branch_numbers(root, "3pwr/", remote="origin")) == [7, 20, 44]
    # a different prefix scopes the scan
    assert gitflow.run_branch_numbers(root, "wip/") == [99]
    # an unknown remote is not a crash — its tracking refs simply do not exist
    assert sorted(gitflow.run_branch_numbers(root, "3pwr/", remote="nope")) == [7, 20]


def _seed_repo(tmp_path) -> Path:
    """A throwaway git repo on ``main`` with a single commit — the base for the intent tests."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git_init(root)
    return root


def test_ensure_run_branch_fresh_refuses_an_existing_branch_without_checkout(tmp_path):
    """Covers: REQ-B — mode='fresh' on a branch that already exists returns the distinct refusal
    sentinel and performs NO checkout: the working tree stays on its current branch, so a fresh run
    never adopts a prior run's branch."""
    root = _seed_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "branch", "3pwr/001-x", head], cwd=str(root), check=True, capture_output=True
    )
    assert gitflow.current_branch(root) == "main"
    err = gitflow.ensure_run_branch(root, "3pwr/001-x", "main", mode="fresh")
    assert err == gitflow.FRESH_BRANCH_EXISTS
    assert gitflow.current_branch(root) == "main"  # never switched to the stale branch


def test_ensure_run_branch_fresh_creates_a_new_branch_off_base(tmp_path):
    """Covers: REQ-B — mode='fresh' on a branch that does not exist creates it off the base and
    switches to it, exactly as a fresh run's happy path does."""
    root = _seed_repo(tmp_path)
    base_tip = _git(root, "rev-parse", "main")
    err = gitflow.ensure_run_branch(root, "3pwr/002-y", "main", mode="fresh")
    assert err == ""
    assert gitflow.current_branch(root) == "3pwr/002-y"
    assert _git(root, "rev-parse", "3pwr/002-y") == base_tip  # branched off the base tip


def test_ensure_run_branch_resume_reenters_an_existing_branch(tmp_path):
    """Covers: REQ-B — mode='resume' re-enters an existing branch (never a second one) and returns
    no error: the resume re-entry contract is unchanged."""
    root = _seed_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "branch", "3pwr/003-z", head], cwd=str(root), check=True, capture_output=True
    )
    assert gitflow.current_branch(root) == "main"
    err = gitflow.ensure_run_branch(root, "3pwr/003-z", "main", mode="resume")
    assert err == ""
    assert gitflow.current_branch(root) == "3pwr/003-z"


def test_ensure_run_branch_resume_pre_stage_hook_keeps_the_run_on_its_branch(tmp_path):
    """Covers: REQ-B — the mid-run pre-stage hook re-invokes ensure_run_branch(mode='resume'): a
    run that strayed to another branch is switched back to its dedicated branch without tripping the
    fresh guard."""
    root = _seed_repo(tmp_path)
    assert gitflow.ensure_run_branch(root, "3pwr/004-w", "main", mode="fresh") == ""
    assert gitflow.current_branch(root) == "3pwr/004-w"
    subprocess.run(["git", "checkout", "-q", "main"], cwd=str(root), check=True)  # user wanders off
    assert gitflow.ensure_run_branch(root, "3pwr/004-w", "main", mode="resume") == ""
    assert gitflow.current_branch(root) == "3pwr/004-w"  # the hook re-entered the run branch


def _seed_repo_with_remote(tmp_path) -> Path:
    """A work repo cloned from a bare ``origin`` whose ``main`` has since advanced.

    The remote's ``main`` is one commit ahead of both the work repo's local ``main`` and its stale
    remote-tracking ref, so only a fresh fetch reveals the newer tip — the setup for asserting a
    fresh run branches off ``origin/main`` while leaving the local base untouched."""
    origin = tmp_path / "origin.git"
    _git_ok(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "work"
    work.mkdir()
    (work / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git_init(work)  # branch main, commit C1
    _git_ok(work, "remote", "add", "origin", str(origin))
    _git_ok(work, "push", "-q", "-u", "origin", "main")
    other = tmp_path / "other"
    _git_ok(tmp_path, "clone", "-q", str(origin), str(other))
    _git_ok(other, "config", "user.email", "o@e.st")
    _git_ok(other, "config", "user.name", "o")
    (other / "more.txt").write_text("more\n", encoding="utf-8")
    _git_ok(other, "add", "-A")
    _git_ok(other, "commit", "-q", "-m", "c2")
    _git_ok(other, "push", "-q", "origin", "main")
    return work


def test_ensure_run_branch_fresh_branches_off_remote_base_after_a_best_effort_fetch(tmp_path):
    """Covers: REQ-C — with fetch_base on, a fresh run best-effort fetches the base and branches off
    the up-to-date ``origin/<base>`` tip; the local base ref is never fast-forwarded."""
    work = _seed_repo_with_remote(tmp_path)
    local_main_before = _git(work, "rev-parse", "main")
    err = gitflow.ensure_run_branch(
        work, "3pwr/001-x", "main", mode="fresh", remote="origin", fetch_base=True
    )
    assert err == ""
    origin_tip = _git(work, "rev-parse", "refs/remotes/origin/main")
    assert origin_tip != local_main_before  # the remote was genuinely ahead
    assert (
        _git(work, "rev-parse", "3pwr/001-x") == origin_tip
    )  # branched off the fetched remote tip
    assert _git(work, "rev-parse", "main") == local_main_before  # local base NEVER fast-forwarded


def test_ensure_run_branch_fresh_fetch_failure_falls_back_to_local_base(tmp_path):
    """Covers: REQ-C — fetch_base on but no reachable remote (unknown remote / offline): the
    best-effort fetch fails silently, the branch is created off the LOCAL base with no error, and
    the local base ref is unchanged."""
    root = _seed_repo(tmp_path)  # no remote configured — the fetch cannot resolve one
    base_tip = _git(root, "rev-parse", "main")
    err = gitflow.ensure_run_branch(
        root, "3pwr/002-y", "main", mode="fresh", remote="origin", fetch_base=True
    )
    assert err == ""
    assert gitflow.current_branch(root) == "3pwr/002-y"
    assert _git(root, "rev-parse", "3pwr/002-y") == base_tip  # fell back to the local base tip
    assert _git(root, "rev-parse", "main") == base_tip  # local base untouched


def test_ensure_run_branch_fresh_detached_and_unborn_fall_back_without_error(tmp_path):
    """Covers: REQ-C — a detached HEAD (base still resolves locally) and an unborn repo (no base at
    all) both fall back cleanly with no error even when fetch_base is on and no remote is reachable."""
    root = _seed_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _git_ok(root, "checkout", "-q", "--detach", head)
    err = gitflow.ensure_run_branch(
        root, "3pwr/003-a", "main", mode="fresh", remote="origin", fetch_base=True
    )
    assert err == "" and gitflow.current_branch(root) == "3pwr/003-a"
    assert _git(root, "rev-parse", "3pwr/003-a") == head  # off the resolved local base
    # an unborn repo: no commits, no base ref → the empty start-point, still no error
    unborn = tmp_path / "unborn"
    unborn.mkdir()
    _git_ok(tmp_path, "init", "-q", "-b", "main", str(unborn))
    _git_ok(unborn, "config", "user.email", "h@e.st")
    _git_ok(unborn, "config", "user.name", "h")
    err2 = gitflow.ensure_run_branch(
        unborn, "3pwr/001-x", "main", mode="fresh", remote="origin", fetch_base=True
    )
    assert err2 == "" and gitflow.current_branch(unborn) == "3pwr/001-x"


def test_ensure_run_branch_fresh_honors_a_non_main_base_branch(tmp_path):
    """Covers: REQ-C — base_branch: develop is honored both without a fetch and with fetch_base on
    when no remote-tracking develop exists (it falls back to the local develop)."""
    root = _seed_repo(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _git_ok(root, "branch", "develop", head)
    _git_ok(root, "checkout", "-q", "develop")
    (root / "d.txt").write_text("d\n", encoding="utf-8")
    _git_ok(root, "add", "-A")
    _git_ok(root, "commit", "-q", "-m", "d")
    develop_tip = _git(root, "rev-parse", "develop")
    _git_ok(root, "checkout", "-q", "main")
    # without a fetch
    err = gitflow.ensure_run_branch(root, "3pwr/005-a", "develop", mode="fresh")
    assert err == "" and _git(root, "rev-parse", "3pwr/005-a") == develop_tip
    _git_ok(root, "checkout", "-q", "main")
    # with fetch on but no remote develop → falls back to the local develop
    err2 = gitflow.ensure_run_branch(
        root, "3pwr/006-b", "develop", mode="fresh", remote="origin", fetch_base=True
    )
    assert err2 == "" and _git(root, "rev-parse", "3pwr/006-b") == develop_tip


def test_fresh_run_refuses_to_adopt_an_existing_branch_and_points_at_resume(
    run_repo, monkeypatch, capsys
):
    """Covers: REQ-B — defense-in-depth at the CLI: when a fresh run still computes a branch that
    already exists (the branch-number scan missed it — a remote-only ref, a race), it refuses on
    the setup path WITHOUT a checkout and points the user at an explicit resume, never continuing
    the prior run's branch."""
    # Plant the branch the fresh allocation will compute, then blind the branch-number scan to it so
    # the union reuses id 001 and only the fresh guard can catch the collision.
    head = _git(run_repo, "rev-parse", "HEAD")
    subprocess.run(
        ["git", "branch", "3pwr/001-add-x", head],
        cwd=str(run_repo),
        check=True,
        capture_output=True,
    )
    monkeypatch.setattr(gitflow, "run_branch_numbers", lambda *a, **k: [])
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input"])
    err = capsys.readouterr().err
    assert rc == EXIT_SETUP
    assert "3pwr run --resume --spec-id 001" in err
    assert "already" in err
    assert gitflow.current_branch(run_repo) == "main"  # never checked out the stale branch


def test_fresh_run_isolation_regression_new_id_and_branch_off_base(tmp_path):
    """Covers: REQ-A, REQ-B, REQ-F — the cross-cutting fresh-run isolation regression.

    A prior run survives ONLY on an unmerged branch (its feature folder absent from the working
    tree) and in the signed ledger. A fresh run must NOT re-enter it: the union allocator
    (:func:`workspace.next_run_number`) clears the stale id over folders + branches + ledger, and
    :func:`gitflow.ensure_run_branch` in ``mode="fresh"`` then creates a genuinely NEW branch off
    the base — never adopting the stale one.

    This fails without the fix: revert the union (drop ``branch_numbers``/``ledger_numbers`` from
    ``next_run_number``) and the id collapses back to ``1``, so the fresh path would recompute the
    stale branch name — which already exists — and ``ensure_run_branch(mode="fresh")`` would refuse
    with :data:`gitflow.FRESH_BRANCH_EXISTS` instead of starting clean. Exercises the union
    allocator and the fresh-vs-resume guard together, as the fresh path wires them (REQ-A + REQ-B).
    """
    root = _seed_repo(tmp_path)  # git repo on main, one commit; no specs-src/ on the checkout
    base_tip = _git(root, "rev-parse", "HEAD")
    # A prior run's branch lives only here, unmerged; its feature folder is NOT on this checkout.
    _git_ok(root, "branch", "3pwr/001-add-feature", base_tip)
    specs_root = root / workspace.SPECS_DIR
    assert not specs_root.exists()  # the stale run's folder survives only on the unmerged branch

    # Gather the union inputs exactly as the fresh path does: the branch scan sees the stale branch,
    # and the ledger still records the prior run's id even though its folder is otherwise gone.
    branch_numbers = gitflow.run_branch_numbers(root, "3pwr/")
    assert branch_numbers == [1]
    ledger_numbers = [1]  # the prior run also survives in the signed ledger

    new_num = workspace.next_run_number(
        specs_root, branch_numbers=branch_numbers, ledger_numbers=ledger_numbers
    )
    assert new_num == 2  # the union clears the stale id — WITHOUT the fix this collapses to 1

    new_branch = gitflow.run_branch_name("3pwr/", f"{new_num:03d}-add-feature")
    assert new_branch == "3pwr/002-add-feature"
    err = gitflow.ensure_run_branch(root, new_branch, "main", mode="fresh")
    assert err == ""  # a genuinely new branch is created — WITHOUT the fix this would refuse
    assert gitflow.current_branch(root) == "3pwr/002-add-feature"  # never the stale 3pwr/001-*
    assert _git(root, "rev-parse", "3pwr/002-add-feature") == base_tip  # branched off the base tip
    assert gitflow.branch_exists(root, "3pwr/001-add-feature")  # the stale branch is left untouched


def test_resume_reuses_the_existing_branch_never_a_new_one(run_repo, monkeypatch, capsys):
    """GITX-FR-004 + GITX-FR-005: a resume recovers the branch from the signed ledger alone and
    re-enters it — the run-branch count is unchanged and no new run number is allocated."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo) == EXIT_PAUSED
    # the human wanders off to another branch between segments — branched off the run tip, since
    # the tracked ledger carries post-commit appends the run still needs (RUNID-FR-005)
    subprocess.run(["git", "checkout", "-q", "-b", "detour"], cwd=str(run_repo), check=True)
    branches_before = {
        b.lstrip("* ") for b in _git(run_repo, "branch", "--list", "3pwr/*").splitlines()
    }
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    assert gitflow.branch_from_ledger(entries, "RUN") == "3pwr/001-add-x"  # GITX-FR-005
    assert _resume(run_repo) == EXIT_PAUSED
    assert gitflow.current_branch(run_repo) == "3pwr/001-add-x"  # re-entered, not recreated
    branches_after = {
        b.lstrip("* ") for b in _git(run_repo, "branch", "--list", "3pwr/*").splitlines()
    }
    assert branches_after == branches_before  # GITX-FR-004: no second run branch
    folders = sorted(p.name for p in (run_repo / "specs-src").iterdir() if p.is_dir())
    assert folders == ["001-add-x"]  # no new run number
    assert (
        main(["--root", str(run_repo), "verify"]) == 0
    )  # the branch field verifies (GITX-NFR-002)


def test_detached_head_still_gets_the_run_branch(run_repo):
    """GITX-FR-006 (edge): on a detached HEAD the run branch is created off the current commit and
    the run proceeds on it."""
    head = _git(run_repo, "rev-parse", "HEAD")
    subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=str(run_repo), check=True)
    assert _run(run_repo) == EXIT_PAUSED
    assert gitflow.current_branch(run_repo) == "3pwr/001-add-x"


# --------------------------------------------------------------------------- C. clean start / stop (GITX-FR-007/008)
def test_dirty_unrelated_start_is_refused_naming_paths_and_deviation(run_repo, capsys):
    """GITX-FR-007 + GITX-NFR-003 + GITX-SC-002: unrelated uncommitted edits block the start,
    naming the offending paths and the signed deviation; the edits stay byte-identical on disk
    and no branch switch is forced."""
    stray = run_repo / "notes.txt"
    stray.write_text("precious uncommitted work\n", encoding="utf-8")
    rc = _run(run_repo)
    err = capsys.readouterr().err
    assert rc == EXIT_SETUP
    assert "notes.txt" in err and "git_clean_start" in err and "deviation" in err
    assert stray.read_text(encoding="utf-8") == "precious uncommitted work\n"  # untouched
    assert gitflow.current_branch(run_repo) == "main"  # never force-switched


def test_run_produced_dirt_is_tolerated_on_resume(run_repo, monkeypatch, capsys):
    """GITX-FR-007 (edge): uncommitted changes that ARE the run's own (a stage that recorded its
    artifacts but was not committed — the stage commit relaxed by deviation) do not block a
    resume; only unrelated changes refuse."""
    assert _deviate(run_repo, "git_stage_commit") == 0
    assert _run(run_repo) == EXIT_PAUSED  # spec.md written, recorded, NOT committed
    assert (run_repo / "specs-src" / "001-add-x" / "spec.md").is_file()
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    assert "specs-src/001-add-x/spec.md" in gitflow.recorded_run_paths(entries, "RUN")
    assert _resume(run_repo) in (EXIT_PAUSED, EXIT_SETUP, EXIT_FAIL)  # tolerated, not refused
    err = capsys.readouterr().err
    assert "cannot start" not in err


def test_clean_stop_after_every_stage_and_at_the_pause(run_repo, monkeypatch):
    """GITX-FR-008 + GITX-SC-002: after the run pauses at a human gate, every executed producing
    stage is committed on the run branch and the run's produced-path set has an empty intersection
    with the uncommitted set."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo) == EXIT_PAUSED
    assert _resume(run_repo) == EXIT_PAUSED  # → signoff gate: specify..implement all executed
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    assert gitflow.uncommitted_run_paths(run_repo, entries, "RUN") == []  # produced ∩ dirty == ∅
    committed = gitflow.committed_steps(entries, "RUN")
    for step in ("specify", "plan", "tasks", "oracle", "implement"):
        assert step in committed


def test_status_reports_branch_and_committed_stages(run_repo, capsys):
    """GITX-FR-009: `3pwr run --status` and `3pwr status` surface the run's branch and the
    per-stage committed indication — derived from the ledger alone (GITX-NFR-001)."""
    assert _run(run_repo) == EXIT_PAUSED
    capsys.readouterr()  # drain the run output before the JSON assertion
    assert main(["--root", str(run_repo), "run", "--status", "--json", "--spec-id", "RUN"]) == 0
    obj = json.loads(capsys.readouterr().out)
    assert obj["branch"] == "3pwr/001-add-x"
    assert "specify" in obj["committed_steps"]
    assert main(["--root", str(run_repo), "status", "--spec-id", "RUN"]) == 0
    out = capsys.readouterr().out
    assert "3pwr/001-add-x" in out and "committed stages" in out


# --------------------------------------------------------------------------- D. the stage commit (GITX-FR-010..013)
def test_stage_commit_stages_only_produced_paths_with_agent_message(run_repo, capsys):
    """GITX-FR-010 + GITX-FR-011 + GITX-SC-003: one commit per producing stage staging only the
    run's produced paths (unrelated files never swept in), whose message is the agent's description
    carrying the stage and spec id."""
    assert _run(run_repo) == EXIT_PAUSED
    subjects = _log_subjects(run_repo)
    specify = next(s for s in subjects if s.startswith("3pwr(RUN): specify"))
    assert "authored the specify work for the run" in specify  # the agent-written description
    # HEAD at the pause is the engine's own state commit (ledger + progress.md refreshed for the
    # gate); the specify *producing* commit is what stages the produced artifact — inspect it.
    specify_hash = _git(run_repo, "log", "-1", "-F", "--grep", "3pwr(RUN): specify", "--pretty=%H")
    files = _git(run_repo, "show", "--name-only", "--pretty=format:", specify_hash).split()
    # only the produced path plus the engine's ledger (RUNID-FR-005) and the run's progress file
    # (PROGFILE-FR-008) — never add -A
    assert sorted(files) == [
        ".3powers/ledger.jsonl",
        "specs-src/001-add-x/progress.md",
        "specs-src/001-add-x/spec.md",
    ]


def test_missing_agent_message_falls_back_deterministically(run_repo, monkeypatch, capsys):
    """GITX-FR-011 (fallback): with no usable COMMIT line the message is the deterministic default
    naming the stage and spec id — a commit is never blocked on message generation."""
    monkeypatch.setattr(runner, "dispatch_agent", _writer(commit_line=False))
    assert _run(run_repo) == EXIT_PAUSED
    subjects = _log_subjects(run_repo)
    assert "3pwr(RUN): specify" in subjects  # the bare deterministic label


def test_engine_commits_are_authored_as_3pwr_and_config_is_untouched(run_repo):
    """GITX-FR-012 + GITX-NFR-004 + GITX-SC-004: a commit 3pwr creates carries the configured 3pwr
    author; the developer's git config is never mutated and no history is rewritten."""
    assert _run(run_repo) == EXIT_PAUSED
    author = _git(run_repo, "log", "-1", "--pretty=%an <%ae>")
    assert author == "3pwr <3pwr@3powers.local>"
    # the developer's own configured identity is untouched (applied per-commit via -c)
    assert _git(run_repo, "config", "user.name") == "human"
    assert _git(run_repo, "config", "user.email") == "human@e.st"
    # the pre-run history is intact — nothing rewritten (GITX-NFR-004)
    assert _log_subjects(run_repo)[-1] == "init"


def test_human_committed_stage_keeps_the_human_author(run_repo, monkeypatch, capsys):
    """GITX-FR-012 (edge): paths a human already committed by hand are not re-committed — the
    stage's post-hook is a no-op and the commit keeps the human's own author."""
    assert _deviate(run_repo, "git_stage_commit") == 0
    assert _run(run_repo) == EXIT_PAUSED  # spec.md left uncommitted (relaxed)
    subprocess.run(["git", "add", "specs-src/001-add-x/spec.md"], cwd=str(run_repo), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "spec: written by hand"], cwd=str(run_repo), check=True
    )
    assert _git(run_repo, "log", "-1", "--pretty=%an") == "human"
    # revoke the relaxation; the next segments commit as 3pwr but never re-commit the human's work
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    dev_seq = next(
        e["seq"]
        for e in entries
        if e.get("type") == "deviation" and not e["payload"].get("revokes")
    )
    assert main(["--root", str(run_repo), "deviation", "--revoke", str(dev_seq)]) == 0
    assert _resume(run_repo) in (EXIT_PAUSED, EXIT_SETUP, EXIT_FAIL)
    subjects = _log_subjects(run_repo)
    assert subjects.count("spec: written by hand") == 1  # no second commit for the same paths


def test_run_is_auditable_from_the_branch_log_alone(run_repo, monkeypatch):
    """GITX-FR-013: reading only the run branch's log enumerates the producing stages in order,
    each attributable (3pwr vs human) and traceable to its stage and spec id."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo) == EXIT_PAUSED
    assert _resume(run_repo) == EXIT_PAUSED
    subjects = [s for s in reversed(_log_subjects(run_repo)) if s.startswith("3pwr(RUN):")]
    steps = [s.split(":")[1].split("—")[0].strip() for s in subjects]
    # the engine's own state commits (ledger + progress.md, recorded at judgment steps and before
    # human gates) are interleaved but are not producing stages — drop them from the stage walk
    steps = [st for st in steps if st != "record engine state"]
    # lifecycle order (discovery heads the walk since it became the first producing stage)
    assert steps == ["discovery", "specify", "plan", "tasks", "oracle", "implement"]
    authors = set(_git(run_repo, "log", "--pretty=%an", "--grep", "3pwr(RUN)", "-F").splitlines())
    assert authors == {"3pwr"}  # every engine stage commit is attributable


# --------------------------------------------------------------------------- E. enforcement + config (GITX-FR-014/015)
def test_relaxation_is_a_signed_revocable_deviation_never_a_flag(run_repo, capsys):
    """GITX-FR-014 + GITX-SC-005: the clean-start guard yields only to a signed, revocable
    deviation — recorded as a ledger entry — and blocks again once revoked."""
    (run_repo / "notes.txt").write_text("stray\n", encoding="utf-8")
    assert _run(run_repo) == EXIT_SETUP  # blocked
    capsys.readouterr()
    assert _deviate(run_repo, "git_clean_start") == 0
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    dev = next(e for e in entries if e.get("type") == "deviation")
    assert "git_clean_start" in dev["payload"]["gates"]  # a signed ledger entry (GITX-FR-014)
    capsys.readouterr()
    assert _run(run_repo) == EXIT_PAUSED  # proceeds under the recorded relaxation
    assert (run_repo / "notes.txt").read_text(encoding="utf-8") == "stray\n"  # still untouched
    # the way back: revoking re-arms the guard for a later fresh run (GITX-FR-014 property)
    assert main(["--root", str(run_repo), "deviation", "--revoke", str(dev["seq"])]) == 0
    rc = main(["--root", str(run_repo), "run", "more y", "--no-input", "--spec-id", "R2"])
    assert rc == EXIT_SETUP and "notes.txt" in capsys.readouterr().err


def test_git_yaml_tunes_prefix_base_and_author_with_tolerant_fallback(run_repo, tmp_path, capsys):
    """GITX-FR-015: git.yaml deterministically changes the branch prefix / base / author; a missing
    file applies the documented defaults; a malformed one warns once and still runs."""
    cfg = run_repo / ".3powers" / "config" / "git.yaml"
    cfg.write_text(
        "version: 1\nbranch_prefix: wip/\nbase_branch: main\n"
        "author: {name: robo, email: robo@corp.example}\n",
        encoding="utf-8",
    )
    assert _run(run_repo) == EXIT_PAUSED
    assert gitflow.current_branch(run_repo) == "wip/001-add-x"
    assert _git(run_repo, "log", "-1", "--pretty=%an <%ae>") == "robo <robo@corp.example>"
    # defaults when the file is absent (GITX-FR-015 property; pure in the file bytes)
    prefs = gitflow.load_prefs(tmp_path / "nope.yaml")
    assert (prefs.branch_prefix, prefs.base_branch) == ("3pwr/", "main")
    assert (prefs.author_name, prefs.author_email) == ("3pwr", "3pwr@3powers.local")
    assert prefs.malformed is False
    # a malformed file falls back with the malformed flag for the single warning
    bad = tmp_path / "bad.yaml"
    bad.write_text("- just\n- a list\n", encoding="utf-8")
    p2 = gitflow.load_prefs(bad)
    assert p2.malformed is True and p2.branch_prefix == "3pwr/"


def test_deviation_gates_include_the_named_git_guards():
    """GITX-FR-014 (property): each relaxable guard maps to exactly one named deviation gate,
    accepted by the deviation command's known set."""
    assert deviations.GIT_CLEAN_START == "git_clean_start"
    assert deviations.GIT_STAGE_COMMIT == "git_stage_commit"
    assert deviations.GIT_RUN_BRANCH == "git_run_branch"
    for g in ("git_clean_start", "git_stage_commit", "git_run_branch"):
        assert g in deviations.DEVIATABLE_REQUIREMENTS


# --------------------------------------------------------------------------- F. the manual drive (GITX-FR-016)
def test_git_start_establishes_the_branch_for_a_manual_drive(run_repo, capsys):
    """GITX-FR-016 + GITX-SC-006: `3pwr git start` gives the manual `/3pwr.*` drive the same
    clean-start + branch-isolation guarantees, binding the branch in the signed ledger."""
    (run_repo / "specs-src" / "018-manual").mkdir(parents=True)
    rc = main(
        [
            "--root",
            str(run_repo),
            "git",
            "start",
            "--spec-id",
            "MAN",
            "--feature",
            "specs-src/018-manual",
            "--json",
        ]
    )
    obj = json.loads(capsys.readouterr().out)
    assert rc == 0 and obj["branch"] == "3pwr/018-manual"
    assert gitflow.current_branch(run_repo) == "3pwr/018-manual"
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    assert gitflow.branch_from_ledger(entries, "MAN") == "3pwr/018-manual"  # bound (GITX-FR-005)
    # idempotent: re-running re-enters the recorded branch and appends nothing new
    n = len(entries)
    assert main(["--root", str(run_repo), "git", "start", "--spec-id", "MAN"]) == 0
    assert len(Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()) == n
    assert main(["--root", str(run_repo), "verify"]) == 0


def test_git_start_applies_the_clean_start_guard(run_repo, capsys):
    """GITX-FR-016: the manual drive cannot bypass the clean-start guard — unrelated uncommitted
    edits refuse `git start` the same way they refuse `3pwr run`."""
    (run_repo / "stray.txt").write_text("x\n", encoding="utf-8")
    rc = main(["--root", str(run_repo), "git", "start", "--spec-id", "MAN"])
    err = capsys.readouterr().err
    assert rc == EXIT_FAIL and "stray.txt" in err and "git_clean_start" in err


def test_advance_refuses_off_branch_or_uncommitted_stage(run_repo, monkeypatch, capsys):
    """GITX-FR-016 + GITX-SC-006: with a run branch recorded, a stage-boundary `advance` refuses
    off the run branch and with the completed stage's work uncommitted — naming the condition and
    the fix — and proceeds once both hold."""
    _mock_gates_green(monkeypatch)
    assert _run(run_repo) == EXIT_PAUSED
    assert _resume(run_repo) == EXIT_PAUSED  # → signoff gate (verdict recorded green)
    assert (
        main(["--root", str(run_repo), "signoff", "--approver", "human", "--spec-id", "RUN"]) == 0
    )
    # off the run branch → refused, naming the branch and the deviation (the detour branches off
    # the run tip — the tracked ledger carries post-signoff appends, RUNID-FR-005)
    subprocess.run(["git", "checkout", "-q", "-b", "detour"], cwd=str(run_repo), check=True)
    capsys.readouterr()
    rc = main(["--root", str(run_repo), "advance", "--stage", "ship", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc == EXIT_FAIL and "3pwr/001-add-x" in out and "git_run_branch" in out
    # back on the branch with an uncommitted run-produced change → refused naming the path
    subprocess.run(["git", "checkout", "-q", "3pwr/001-add-x"], cwd=str(run_repo), check=True)
    (run_repo / "src" / "impl.py").write_text("VALUE = 2\n", encoding="utf-8")
    rc2 = main(["--root", str(run_repo), "advance", "--stage", "ship", "--spec-id", "RUN"])
    out2 = capsys.readouterr().out
    assert rc2 == EXIT_FAIL and "not committed" in out2 and "src/impl.py" in out2
    # both hold → the advance proceeds
    subprocess.run(["git", "checkout", "-q", "--", "src/impl.py"], cwd=str(run_repo), check=True)
    assert main(["--root", str(run_repo), "advance", "--stage", "ship", "--spec-id", "RUN"]) == 0


# --------------------------------------------------------------------------- NFRs
def test_git_mechanics_are_deterministic_and_offline(tmp_path, monkeypatch):
    """GITX-NFR-001: branch naming, clean-tree classification, message composition, and the
    transcript extraction are pure/offline — identical inputs, identical outputs, sockets blocked."""
    import socket

    def _no_network(*_a, **_k):
        raise RuntimeError("gitflow attempted a network call")

    monkeypatch.setattr(socket, "socket", _no_network)
    assert gitflow.run_branch_name("3pwr/", "018-x") == gitflow.run_branch_name("3pwr/", "018-x")
    changed = ["src/a.py", ".3powers/ledger.jsonl", "specs-src/018-x/spec.md", "notes.txt"]
    got = gitflow.unrelated_changes(changed, {"src/a.py"}, "specs-src/018-x/")
    assert got == ["notes.txt"]  # engine state + run paths + feature folder are never "unrelated"
    assert gitflow.unrelated_changes(changed, {"src/a.py"}, "specs-src/018-x/") == got  # repeatable
    assert gitflow.stage_commit_message("GITX", "plan") == "3pwr(GITX): plan"
    assert (
        gitflow.stage_commit_message("GITX", "plan", "split the work")
        == "3pwr(GITX): plan — split the work"
    )
    t = tmp_path / "t.log"
    t.write_text("noise\nCOMMIT: first\nmore\nCOMMIT: the real one\n", encoding="utf-8")
    assert gitflow.agent_commit_description(tmp_path, "t.log") == "the real one"  # last wins
    assert gitflow.agent_commit_description(tmp_path, "missing.log") == ""  # fallback path
    # the COMMIT request is a fixed prompt block on the producing stages (GITX-FR-011)
    assert "COMMIT:" in prompts.assemble("plan", intent="x")
    assert "COMMIT:" not in prompts.assemble("advance", intent="x")


def test_ledger_addition_is_additive_and_old_ledgers_verify(run_repo, capsys):
    """GITX-NFR-002: the only ledger addition is the branch field on the existing run/start
    payload — a pre-GITX ledger (no branch) still verifies and resolves to no branch."""
    assert _run(run_repo) == EXIT_PAUSED
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    start = next(
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "start"
    )
    assert start["payload"]["branch"] == "3pwr/001-add-x"  # one additive field, same entry type
    assert main(["--root", str(run_repo), "verify"]) == 0
    # a start entry WITHOUT the field (pre-GITX) resolves to "" — the legacy fallback applies
    pre = [{"type": "run", "spec_id": "OLD", "payload": {"kind": "start", "intent": "x"}}]
    assert gitflow.branch_from_ledger(pre, "OLD") == ""


def test_dry_run_needs_no_git_and_touches_nothing(tmp_path, monkeypatch):
    """GITX (edge) + SRCX-NFR-005: --dry-run dispatches nothing and writes nothing — the git hooks
    are a live-run concern, so a dry run outside any git repo stays green and offline."""
    root = tmp_path / "norepo"
    (root / ".3powers" / "config").mkdir(parents=True)
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    rc = main(["--root", str(root), "run", "add x", "--dry-run", "--no-input", "--spec-id", "D"])
    assert rc == EXIT_PAUSED  # no git precondition, no branch, no commit — nothing dispatched
    assert not (root / ".git").exists()


def test_no_new_runtime_dependency():
    """GITX-NFR-005: git rides the existing subprocess path — no git-related runtime dependency.
    The full set is {cryptography, PyYAML, rich}; rich is the rendering dependency TRIX-FR-001
    permits, unrelated to the git integration."""
    import tomllib

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    deps = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["dependencies"]
    names = sorted(d.split(">=")[0].split("==")[0].strip() for d in deps)
    assert names == ["PyYAML", "cryptography", "rich"]
    assert not any("git" in d.lower() for d in deps)  # nothing git-related was added
