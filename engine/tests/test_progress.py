"""The run's human-readable progress file — ``specs/<NNN>-<slug>/progress.md`` (PROGFILE, spec 024).

Exercises Track E of plan 030 with fake agents and no network: the file written into the run's
feature folder for every live run (PROGFILE-FR-001), the atomic tmp-then-rename write
(PROGFILE-FR-002), the title line (PROGFILE-FR-003), the stage-progress glyph rows with completion
timestamps (PROGFILE-FR-004), the phase-detail table read from the tasks artifact's checkboxes
(PROGFILE-FR-005), the Current state / Last verdict / fenced helper commands / gate-failures
sections carrying the run's real identity (PROGFILE-FR-006), the six lifecycle update triggers
(PROGFILE-FR-007), the progress file riding each producing stage commit (PROGFILE-FR-008), the
never-fail-the-run degradation (PROGFILE-NFR-001), and the clean-start guard treating the file as
engine-owned state (PROGFILE-NFR-002).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import gitflow, progress, runner, runpreflight
from threepowers.cli import EXIT_PAUSED, EXIT_SETUP, _progress_safe, main

NOW = "2026-07-06 14:32"

TASKS_MD = """# Tasks

## Phase 1: ButtonComponent styles
**File scope**: src/a.ts
- [x] T001 style the button (files: src/a.ts)
- [x] T002 theme tokens (files: src/a.ts)

## Phase 2: HeaderComponent logic
**File scope**: src/b.ts
- [x] T003 wire the handler (files: src/b.ts)
- [ ] T004 dismiss state (files: src/b.ts)
- [ ] T005 persistence (files: src/b.ts)

## Phase 3: Integration tests
**File scope**: tests/int.test.ts
- [ ] T006 end-to-end (files: tests/int.test.ts)
"""


# --------------------------------------------------------------------------- unit fixtures
def _feature_dir(tmp_path: Path, name: str = "030-add-button") -> Path:
    d = tmp_path / "specs" / name
    d.mkdir(parents=True)
    return d


def _reporter(feature_dir: Path, **kw) -> progress.Reporter:
    kw.setdefault("now", lambda: NOW)
    return progress.Reporter(feature_dir, **kw)


def _row(text: str, stage: str) -> str:
    m = re.search(rf"^\| {stage} \|.*$", text, re.MULTILINE)
    assert m, f"no stage row for {stage!r} in:\n{text}"
    return m.group(0)


def _advance_to_build(rep: progress.Reporter) -> None:
    """Walk the reporter to a mid-build state: Spec + Plan done, implement running."""
    for step, stage in (
        ("specify", "Spec"),
        ("clarify", "Spec"),
        ("plan", "Plan"),
        ("tasks", "Plan"),
        ("oracle", "Build"),
    ):
        rep.stage_started(step, stage)
        rep.stage_completed(step, stage)
    rep.stage_started("implement", "Build")


# --------------------------------------------------------------------------- schema (FR-003/004/005/006)
def test_write_renders_the_midbuild_schema_with_phases(tmp_path):
    """PROGFILE-FR-003 + PROGFILE-FR-004 + PROGFILE-FR-005: a mid-build state with a phased tasks
    artifact renders the title line, done/running/pending stage rows with completion timestamps,
    the Build row's phase-position label, and the phase-detail table with per-phase checkbox
    counts read from the tasks artifact."""
    fd = _feature_dir(tmp_path)
    (fd / "tasks.md").write_text(TASKS_MD, encoding="utf-8")
    rep = _reporter(fd)
    _advance_to_build(rep)
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert text.splitlines()[0] == f"# Run 030 · add-button · {NOW}"
    assert _row(text, "Spec") == f"| Spec | ✓ done | {NOW} |"
    assert _row(text, "Plan") == f"| Plan | ✓ done | {NOW} |"
    assert _row(text, "Build") == "| Build | ⏳ phase 2/3 |  |"
    assert _row(text, "Verify") == "| Verify | ○ pending |  |"
    assert _row(text, "Observe") == "| Observe | ○ pending |  |"
    assert "### Build — phase detail" in text
    assert "| 1 | ButtonComponent styles | ✓ done | 2/2 |" in text
    assert "| 2 | HeaderComponent logic | ⏳ running | 1/3 |" in text
    assert "| 3 | Integration tests | ○ pending | — |" in text
    assert "running 'implement'" in text


def test_phase_table_absent_without_phases(tmp_path):
    """PROGFILE-FR-005: the phase-detail table renders only when the current stage has phases — a
    phaseless run (no tasks artifact, or no phase headings) carries no phase table."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    _advance_to_build(rep)  # no tasks.md at all
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert "phase detail" not in text
    assert _row(text, "Build") == "| Build | ⏳ running |  |"
    (fd / "tasks.md").write_text("# Tasks\n- [ ] T001 flat task\n", encoding="utf-8")
    rep.stage_started("implement", "Build")  # rewrite with a phaseless artifact present
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert "phase detail" not in text


def test_sections_and_helper_commands_embed_the_real_identity(tmp_path):
    """PROGFILE-FR-006: the Current state / Last verdict / fenced helper commands / gate-failures
    sections are all present, and every helper command interpolates the run's resolved identity —
    the folder's NNN by default, an explicit spec id when one was given."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd, tier="High-risk")
    rep.stage_started("specify", "Spec")
    text = (fd / "progress.md").read_text(encoding="utf-8")
    for section in ("## Current state", "## Last verdict", "## Helper commands", "```bash"):
        assert section in text
    assert "## Gate failures (last verify attempt)" in text and "(none yet)" in text
    assert "— (no verdict yet)" in text
    assert "3pwr run --status --spec-id 030" in text
    assert "3pwr run --resume --spec-id 030 --approver <you>" in text
    assert "3pwr abort --spec-id 030" in text
    assert "3pwr gate run --id 030 --tier High-risk" in text
    explicit = _reporter(_feature_dir(tmp_path, "031-pay"), spec_id="PAY")
    out = explicit.stage_started("specify", "Spec")
    text2 = out.read_text(encoding="utf-8")
    assert "3pwr run --status --spec-id PAY" in text2  # the explicit identity always wins
    assert "--spec-id 031" not in text2


# --------------------------------------------------------------------------- atomicity (FR-002)
def test_write_is_atomic_and_leaves_no_tmp(tmp_path):
    """PROGFILE-FR-002: every write stages to .progress.md.tmp and renames onto progress.md — no
    tmp file survives a successful write, and a rewrite fully replaces the prior content."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    p = rep.stage_started("specify", "Spec")
    assert p == fd / "progress.md" and p.is_file()
    assert not (fd / ".progress.md.tmp").exists()
    rep.paused("review-spec", "Spec")
    assert not (fd / ".progress.md.tmp").exists()
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert text.count("# Run 030") == 1  # replaced, never appended


# --------------------------------------------------------------------------- the six triggers (FR-007)
def test_stage_start_marks_the_row_running(tmp_path):
    """PROGFILE-FR-007 (stage start): the stage's row turns ⏳ running and the Current state block
    names the running step."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("specify", "Spec")
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Spec") == "| Spec | ⏳ running |  |"
    assert "**Stage:** Spec — running 'specify'" in text


def test_stage_complete_marks_the_row_done_with_timestamp(tmp_path):
    """PROGFILE-FR-007 (stage complete) + PROGFILE-FR-004: completing a stage's last step turns
    its row ✓ done with the completion timestamp; an intermediate step keeps the stage running."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("specify", "Spec")
    rep.stage_completed("specify", "Spec")  # clarify still ahead — Spec not done yet
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Spec") == "| Spec | ⏳ running |  |"
    rep.stage_started("clarify", "Spec")
    rep.stage_completed("clarify", "Spec")
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Spec") == f"| Spec | ✓ done | {NOW} |"


def test_verdict_pass_updates_the_last_verdict_block(tmp_path):
    """PROGFILE-FR-007 (gate verdict PASS): a green verdict completes Verify and reports the pass
    in the Last verdict block with no gate failures listed."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("verify", "Verify")
    rep.verdict("pass", [])
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Verify") == f"| Verify | ✓ done | {NOW} |"
    assert f"✓ pass ({NOW})" in text and "(none yet)" in text


def test_verdict_fail_lists_the_failed_gates(tmp_path):
    """PROGFILE-FR-007 (gate verdict FAIL): a red verdict turns the Verify row ✗ failed, reports
    the failure in the Last verdict block, and lists the failed gate NAMES in the gate-failures
    section — names only, never raw error output."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("verify", "Verify")
    rep.verdict("fail", ["lint", "tests"])
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Verify") == "| Verify | ✗ failed |  |"
    assert f"✗ fail ({NOW}) — failed gates: lint, tests" in text
    section = text.split("## Gate failures (last verify attempt)")[1]
    assert "- lint" in section and "- tests" in section and "(none yet)" not in section


def test_pause_marks_the_gates_stage_locked(tmp_path):
    """PROGFILE-FR-007 (human-gate pause): the gate's stage shows 🔒 paused and the Current state
    block names the awaited gate with the copy-pasteable resume command."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("specify", "Spec")
    rep.paused("review-spec", "Spec")
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Spec") == "| Spec | 🔒 paused |  |"
    assert "paused at 'review-spec'" in text
    assert "3pwr run --resume --spec-id 030 --approver <you>" in text


def test_run_failure_marks_the_stage_failed(tmp_path):
    """PROGFILE-FR-007 (run failure): a terminal failure turns the failing stage's row ✗ failed
    and the Current state block carries the recorded failure class."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.stage_started("plan", "Plan")
    rep.failed("dispatch_failed", "Plan", "agent exited 1")
    text = (fd / "progress.md").read_text(encoding="utf-8")
    assert _row(text, "Plan") == "| Plan | ✗ failed |  |"
    assert _row(text, "Spec") == "| Spec | ✓ done |  |"  # earlier stages inferred done
    assert "✗ failed — dispatch_failed at Plan — agent exited 1" in text


def test_completion_marks_every_stage_done(tmp_path):
    """PROGFILE-FR-007: run completion turns every stage row done and says so in Current state."""
    fd = _feature_dir(tmp_path)
    rep = _reporter(fd)
    rep.completed()
    text = (fd / "progress.md").read_text(encoding="utf-8")
    for stage in ("Discovery", "Spec", "Plan", "Build", "Verify", "Review", "Ship", "Observe"):
        assert "✓ done" in _row(text, stage)
    assert "✓ lifecycle complete" in text


# --------------------------------------------------------------------------- degradation (NFR-001/002)
def test_progress_errors_degrade_to_a_warning(capsys):
    """PROGFILE-NFR-001: a progress-file update that raises is degraded to a stderr warning —
    the guard swallows the error so a write problem can never fail a run or a stage."""

    def boom() -> None:
        raise OSError("disk full")

    _progress_safe(boom)  # must not raise
    assert "progress.md not updated — disk full" in capsys.readouterr().err


def test_clean_start_guard_ignores_the_progress_file():
    """PROGFILE-NFR-002: a feature workspace's progress.md — legitimately dirty after a paused or
    failed run's last commit — is engine-owned state the clean-start guard never blocks on."""
    unrelated = gitflow.unrelated_changes(
        ["specs/030-add-x/progress.md", "notes.txt", "specs/030-add-x/scratch.md"], set()
    )
    assert unrelated == ["notes.txt", "specs/030-add-x/scratch.md"]


# --------------------------------------------------------------------------- live run integration (FR-001/007/008)
def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    return proc.stdout.strip()


def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "human@e.st"],
        ["git", "config", "user.name", "human"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _writer(fail_specify: bool = False):
    """A fake agent writing the specify artifact into the folder the prompt names (or failing the
    dispatch outright), teeing its output like a real headless dispatch."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if fail_specify and "STAGE: Specify" in prompt:
            return (1, "", "agent exploded")
        m = re.search(r"FEATURE FOLDER: (\S+)", prompt)
        d = cwd / (m.group(1) if m else "specs/unknown")
        out = "changes written"
        if "STAGE: Specify" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text("# Spec\n**Spec ID**: FEAT\n", encoding="utf-8")
            out += "\nCOMMIT: authored the specify work for the run"
        tee = kw.get("tee")
        if tee is not None:
            tee.write(out + "\n")
            tee.flush()
        return (0, out, "")

    return fake


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    """A git repo with agents/roles/signer configured and a fake headless coder — no network."""
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
    # Seed specs/029-seed so the run's workspace allocates 030 — committed, so the GITX
    # clean-start guard sees a clean tree.
    seed = root / "specs" / "029-seed"
    seed.mkdir(parents=True)
    (seed / "spec.md").write_text("# seed\n", encoding="utf-8")
    _git_init(root)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", _writer())
    return root


def test_live_run_writes_progress_and_commits_it(run_repo):
    """PROGFILE-FR-001 + PROGFILE-FR-007 + PROGFILE-FR-008: a live run writes progress.md into its
    allocated feature folder, the pause trigger leaves it showing the paused gate with the derived
    NNN in the helper commands, no tmp file survives, and the producing stage's commit bundles
    progress.md alongside the stage artifact and the ledger."""
    assert main(["--root", str(run_repo), "run", "add x", "--no-input"]) == EXIT_PAUSED
    prog = run_repo / "specs" / "030-add-x" / "progress.md"
    assert prog.is_file()
    assert not (run_repo / "specs" / "030-add-x" / ".progress.md.tmp").exists()
    text = prog.read_text(encoding="utf-8")
    assert text.startswith("# Run 030 · add-x · ")
    assert "🔒 paused" in text and "paused at 'review-spec'" in text
    assert "3pwr run --resume --spec-id 030 --approver <you>" in text
    files = _git(run_repo, "show", "--name-only", "--pretty=format:", "HEAD").split()
    assert "specs/030-add-x/progress.md" in files
    assert "specs/030-add-x/spec.md" in files and ".3powers/ledger.jsonl" in files


def test_run_failure_reaches_the_progress_file(run_repo, monkeypatch):
    """PROGFILE-FR-007 (run failure, end-to-end): a dispatch failure leaves progress.md naming the
    failure class with the failing stage's row ✗ failed."""
    monkeypatch.setattr(runner, "dispatch_agent", _writer(fail_specify=True))
    assert (
        main(["--root", str(run_repo), "run", "add x", "--no-input", "--retries", "0"])
        == EXIT_SETUP
    )
    text = (run_repo / "specs" / "030-add-x" / "progress.md").read_text(encoding="utf-8")
    assert "✗ failed — dispatch_failed" in text
    assert re.search(r"^\| Spec \| ✗ failed \|", text, re.MULTILINE)


def test_dry_run_writes_no_progress_file(run_repo):
    """PROGFILE-FR-001: a --dry-run dispatches nothing and writes nothing — no feature folder is
    allocated and no progress.md appears anywhere under specs/."""
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--dry-run"]) == EXIT_PAUSED
    assert list((run_repo / "specs").glob("*/progress.md")) == []
