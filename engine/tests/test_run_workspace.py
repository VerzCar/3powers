"""The run artifact workspace — flat per-run folder, stage records, allocation, completion gate (SRCX, spec 017).

Exercises the whole SRCX surface with fake agents and no network: the flat canonical layout and its
two readable legacy layouts (SRCX-FR-001/002/003), the producing-stage markdown set and the
oracle/implement records (SRCX-FR-004/005/006/007), the deterministic `<NNN>-<slug>` folder allocation
(SRCX-FR-008/009/010/011), and the artifact-∧-ledger stage-completion gate — in-run and on resume
(SRCX-FR-012..018) — plus the determinism, additive-ledger, legacy, cost, purity, and parallel-phase
NFRs (SRCX-NFR-001..006).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import artifacts, completion, orchestrate, runner, runpreflight, workspace
from threepowers.cli import EXIT_PAUSED, EXIT_SETUP, _run_feature_dir_from_ledger, main
from threepowers.config import Settings
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_PASS, Verdict


# --------------------------------------------------------------------------- flat workspace (SRCX-FR-001)
def test_stage_artifact_paths_are_flat(tmp_path):
    """SRCX-FR-001 (property): every producing step writes its canonical markdown flat in the
    feature folder — spec.md for specify, implementation-plan.md for tasks, changelog.md for
    implement — with no spec/ or artifacts/ subfolder in any write location."""
    f = tmp_path / "specs-src" / "017-x"
    assert workspace.stage_artifact_path(f, "specify") == f / "spec.md"
    assert workspace.stage_artifact_path(f, "discovery") == f / "discovery.md"
    assert workspace.stage_artifact_path(f, "plan") == f / "plan.md"
    assert workspace.stage_artifact_path(f, "tasks") == f / "implementation-plan.md"
    assert workspace.stage_artifact_path(f, "oracle") == f / "oracle.md"
    assert workspace.stage_artifact_path(f, "implement") == f / "changelog.md"
    for step in workspace.PRODUCING_STEPS:
        p = workspace.stage_artifact_path(f, step)
        assert p.parent == f  # flat: never a spec/ or artifacts/ subfolder


def test_spec_resolution_across_three_layouts(tmp_path):
    """SRCX-FR-002: flat (canonical), pre-013 flat (identical), and PHASE split each resolve to
    exactly one spec; when both flat and split exist the single deterministic precedence rule
    (flat wins) still yields exactly one."""
    flat = tmp_path / "specs-src" / "001-flat"
    flat.mkdir(parents=True)
    (flat / "spec.md").write_text("flat\n", encoding="utf-8")
    split = tmp_path / "specs-src" / "002-split"
    (split / "spec").mkdir(parents=True)
    (split / "spec" / "spec.md").write_text("split\n", encoding="utf-8")
    both = tmp_path / "specs-src" / "003-both"
    (both / "spec").mkdir(parents=True)
    (both / "spec.md").write_text("flat\n", encoding="utf-8")
    (both / "spec" / "spec.md").write_text("split\n", encoding="utf-8")
    assert workspace.spec_path(flat) == flat / "spec.md"
    assert workspace.spec_path(split) == split / "spec" / "spec.md"
    assert workspace.spec_path(both) == both / "spec.md"  # exactly one, flat wins
    assert workspace.spec_path(tmp_path / "specs-src" / "004-none") is None
    # property: at most one spec per feature folder, whole-tree
    assert len(workspace.find_specs(tmp_path)) == 3


def test_find_artifact_prefers_flat_never_two(tmp_path):
    """SRCX-FR-003: locating a stage artifact returns the flat path when present, else the split
    fallback, else nothing — never two paths for one stage."""
    f = tmp_path / "specs-src" / "010-f"
    (f / "artifacts").mkdir(parents=True)
    assert workspace.find_artifact(f, "plan") is None
    (f / "artifacts" / "plan.md").write_text("split\n", encoding="utf-8")
    assert workspace.find_artifact(f, "plan") == f / "artifacts" / "plan.md"
    (f / "plan.md").write_text("flat\n", encoding="utf-8")
    assert workspace.find_artifact(f, "plan") == f / "plan.md"


def test_producing_steps_declare_exactly_six_markdowns():
    """SRCX-FR-004 (property): the producing set is exactly {discovery, specify, plan, tasks,
    oracle, implement}; SRCX-FR-007 (property): no gate / verdict / sign-off / advance step is gated."""
    assert workspace.PRODUCING_STEPS == (
        "discovery",
        "specify",
        "plan",
        "tasks",
        "oracle",
        "implement",
    )
    assert workspace.step_filename("discovery") == "discovery.md"  # the default <step>.md branch
    for step in workspace.PRODUCING_STEPS:
        assert completion.is_producing(step)
    for step in (
        "clarify",
        "review-spec",
        "review-plan",
        "review-verify",
        "verify",
        "signoff",
        "advance",
    ):
        assert not completion.is_producing(step)


# --------------------------------------------------------------------------- records (SRCX-FR-005/006)
def test_records_link_real_outputs_without_moving_them(tmp_path):
    """SRCX-FR-005: changelog.md links the real outputs at their existing repo paths and relocates
    nothing; the oracle record is the path-free Tests Specification keyed by the folder id — the
    authored test files stay at their real paths and their machine record lives in the signed
    ledger entries, never inside oracle.md (CON-005)."""
    f = tmp_path / "specs-src" / "017-x"
    f.mkdir(parents=True)
    (f / "spec.md").write_text(
        "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: The system shall work.\n", encoding="utf-8"
    )
    tests_dir = tmp_path / "tests" / "oracle" / "017-x"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_o.py").write_text("def test_o(): ...\n", encoding="utf-8")
    rel = completion.write_record(
        tmp_path, f, "oracle", spec_id="X", linked=["tests/oracle/017-x/test_o.py"]
    )
    assert rel == "specs-src/017-x/oracle.md"
    text = (f / "oracle.md").read_text(encoding="utf-8")
    assert "Tests Specification — 017-x" in text  # keyed by the feature-folder id
    assert "tests/oracle/017-x/test_o.py" not in text  # path-free: no test path leaks in
    assert "DEMO-FR-001" in text and "not authored" in text  # the visible structural stub
    assert (tests_dir / "test_o.py").is_file()  # the real output was not moved
    assert not (f / "test_o.py").exists()  # ...nor copied into the feature folder
    rel2 = completion.write_record(
        tmp_path,
        f,
        "implement",
        spec_id="X",
        linked=["src/a.py", "src/b.py"],
        report="## Business changelog\n\n### Added\n\n- Users can now work. [DEMO-FR-001]\n",
    )
    text2 = (f / "changelog.md").read_text(encoding="utf-8")
    assert rel2 == "specs-src/017-x/changelog.md"
    assert "src/a.py" in text2 and "src/b.py" in text2  # trace appendix ⊇ the produced change set
    assert "Users can now work." in text2  # the authored business prose is the body


def test_phased_implement_yields_one_record_enumerating_phases(tmp_path):
    """SRCX-FR-006: an N-phase implement yields exactly ONE changelog.md enumerating each phase and
    linking its scoped changes in deterministic artifact order; SRCX-NFR-006: identical inputs
    render byte-identical records (written after collection, one record — never one per phase)."""
    f = tmp_path / "specs-src" / "017-x"
    f.mkdir(parents=True)
    phases = [
        {"phase": 1, "name": "core", "ok": True, "detail": ""},
        {"phase": 2, "name": "alpha", "ok": True, "detail": ""},
    ]
    scopes = {1: ("src/core.py",), 2: ("src/alpha.py",)}
    produced = ["src/alpha.py", "src/core.py"]
    a = completion.render_changelog("X", produced, phases=phases, phase_scopes=scopes)
    b = completion.render_changelog("X", produced, phases=phases, phase_scopes=scopes)
    assert a == b  # deterministic (SRCX-NFR-001/006)
    assert a.index("Phase 1: core") < a.index("Phase 2: alpha")  # artifact order
    completion.write_record(
        tmp_path, f, "implement", spec_id="X", linked=produced, phases=phases, phase_scopes=scopes
    )
    records = [p.name for p in f.glob("*.md")]
    assert records == ["changelog.md"]  # exactly one, not one per phase
    text = (f / "changelog.md").read_text(encoding="utf-8")
    assert "src/core.py" in text.split("Phase 2")[0]  # phase 1's scoped change under phase 1
    # a phaseless implement still yields one record for the single session
    solo = completion.render_changelog("X", ["src/one.py"])
    assert "single implement session" in solo.lower() and "src/one.py" in solo


def test_changelog_body_is_authored_prose_with_an_additive_machine_trace(tmp_path):
    """SRCX-FR-006 (changelog, Track F): the changelog body is the implement agent's authored
    business prose (validated, not an engine table); a clearly-separated, additive machine-readable
    requirement→files trace appendix carries each phase's requirement ids with its changed files, so
    nothing that consumed the old table loses data. Structural/coverage, not byte-golden — the prose
    body is non-deterministic across runs; render stays deterministic for identical inputs."""
    phases = [
        {"phase": 1, "name": "core", "ok": True, "detail": ""},
        {"phase": 2, "name": "alpha", "ok": False, "detail": "boom"},
    ]
    scopes = {1: ("src/core.py",), 2: ("src/alpha.py",)}
    reqs = {1: ("DEMO-FR-001", "DEMO-FR-002"), 2: ("DEMO-FR-003",)}
    produced = ["src/alpha.py", "src/core.py"]
    report = (
        "## Business changelog\n\n### Fixed\n\n"
        "- The importer no longer drops rows. [DEMO-FR-001] [DEMO-FR-002]\n"
        "- Exports round-trip correctly again. [DEMO-FR-003]\n"
    )
    kwargs = dict(
        phases=phases,
        phase_scopes=scopes,
        phase_requirements=reqs,
        work_kinds=["defect"],
        report=report,
    )
    a = completion.render_changelog("X", produced, **kwargs)
    b = completion.render_changelog("X", produced, **kwargs)
    assert a.encode("utf-8") == b.encode("utf-8")  # deterministic for identical inputs
    # the authored prose is the body — no engine-invented table headings above it
    assert "The importer no longer drops rows." in a
    body, _, appendix = a.partition("## Requirement trace (machine-readable)")
    assert "### Fixed" in body and "importer no longer drops rows" in body
    # the additive machine-readable appendix keeps the requirement→files trace
    assert "| Requirement | Files changed | Phase |" in appendix
    assert "| DEMO-FR-001 | src/core.py | Phase 1: core — completed |" in appendix
    assert "| DEMO-FR-003 | src/alpha.py | Phase 2: alpha — failed — boom |" in appendix
    assert "failed — boom" in appendix  # a failed phase stays visible, never silently green
    # with no authored prose the body degrades to a visible, work-kind-chosen "not authored" note
    stub = completion.render_changelog("X", produced, phase_requirements=reqs)
    assert "## Changed" in stub and "authored no business changelog" in stub
    assert "## Added" in completion.render_changelog("X", produced, work_kinds=["feature"])
    # an untraced phase stays visibly untraced in the appendix
    solo = completion.render_changelog("X", produced, phases=phases, phase_scopes=scopes)
    assert "(untraced)" in solo


def test_changelog_validation_rejects_uncovered_requirement_and_leaked_id(tmp_path):
    """SRCX-FR-006 (Track F): the engine validates the agent-authored changelog the way it validates
    oracle.md — every requirement the run addressed must be covered, no foreign/internal requirement
    id may leak, and an Added/Changed/Fixed section must be present. A miss fails the step
    (ChangelogValidationError), never silently emitting a bad changelog; a clean changelog places."""
    # pure validator: coverage, structure, and the OSS-readiness leaked-id check
    assert (
        completion.validate_changelog(
            "### Added\n- Shipped it. [DEMO-FR-001] [DEMO-FR-002]\n", ["DEMO-FR-001", "DEMO-FR-002"]
        )
        == []
    )
    miss = completion.validate_changelog(
        "### Added\n- Half of it. [DEMO-FR-001]\n", ["DEMO-FR-001", "DEMO-FR-002"]
    )
    assert miss == ["changelog.md does not name requirement DEMO-FR-002"]
    leak = completion.validate_changelog(
        "### Fixed\n- Fixed it. [DEMO-FR-001] [3PWR-FR-099]\n", ["DEMO-FR-001"]
    )
    assert leak == ["changelog.md leaks a foreign requirement id: 3PWR-FR-099"]
    no_section = completion.validate_changelog("- Just a bullet. [DEMO-FR-001]\n", ["DEMO-FR-001"])
    assert any("no Added/Changed/Fixed section" in m for m in no_section)

    # write_record fails the step on a validation miss (uncovered requirement) ...
    f = tmp_path / "specs-src" / "017-x"
    f.mkdir(parents=True)
    (f / "spec.md").write_text(
        "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: shall a.\n- **DEMO-FR-002**: shall b.\n",
        encoding="utf-8",
    )
    with pytest.raises(completion.ChangelogValidationError) as ei:
        completion.write_record(
            tmp_path,
            f,
            "implement",
            spec_id="X",
            linked=["src/a.py"],
            report="## Business changelog\n\n### Added\n- Only half. [DEMO-FR-001]\n",
        )
    assert "DEMO-FR-002" in str(ei.value)
    assert not (f / "changelog.md").exists()  # nothing bad was written
    # ... and on a leaked foreign id ...
    with pytest.raises(completion.ChangelogValidationError):
        completion.write_record(
            tmp_path,
            f,
            "implement",
            spec_id="X",
            linked=["src/a.py"],
            report="### Added\n- Both. [DEMO-FR-001] [DEMO-FR-002] [3PWR-FR-001]\n",
        )
    # ... but a covered, section-shaped, leak-free changelog places cleanly.
    rel = completion.write_record(
        tmp_path,
        f,
        "implement",
        spec_id="X",
        linked=["src/a.py"],
        report="## Business changelog\n\n### Added\n- Both. [DEMO-FR-001] [DEMO-FR-002]\n",
    )
    assert rel == "specs-src/017-x/changelog.md"
    assert "Both." in (f / "changelog.md").read_text(encoding="utf-8")


def test_write_record_never_touches_top_level_changelog(tmp_path):
    """SRCX-FR-006 (Track F): the run's business changelog is placed at
    specs-src/<NNN>-<slug>/changelog.md; the project's hand-maintained top-level CHANGELOG.md is
    out of scope and byte-untouched by a run."""
    top = tmp_path / "CHANGELOG.md"
    original = "# Changelog\n\nHand-maintained by humans.\n"
    top.write_text(original, encoding="utf-8")
    f = tmp_path / "specs-src" / "017-x"
    f.mkdir(parents=True)
    (f / "spec.md").write_text(
        "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: shall work.\n", encoding="utf-8"
    )
    completion.write_record(
        tmp_path,
        f,
        "implement",
        spec_id="X",
        linked=["src/a.py"],
        report="## Business changelog\n\n### Added\n- It works. [DEMO-FR-001]\n",
    )
    assert (f / "changelog.md").is_file()  # the run's record landed in the feature folder
    assert top.read_text(encoding="utf-8") == original  # the top-level CHANGELOG.md is untouched


def test_legacy_implement_md_still_resolves(tmp_path):
    """SRCX-FR-003 (legacy record name): an existing implement.md keeps resolving through
    find_artifact and satisfies the completion gate at its legacy path — no rewrite required."""
    f = tmp_path / "specs-src" / "013-old"
    f.mkdir(parents=True)
    (f / "implement.md").write_text("# Implement record\n", encoding="utf-8")
    assert workspace.find_artifact(f, "implement") == f / "implement.md"
    recorded = completion.recorded_stage_artifacts(
        [_stage_entry("implement", ["specs-src/013-old/implement.md"])], "RUN"
    )
    chk = completion.check_step(tmp_path, f, "implement", recorded)
    assert chk.ok and chk.path == "specs-src/013-old/implement.md"


# --------------------------------------------------------------------------- allocation (SRCX-FR-008/009)
def test_allocation_is_deterministic_max_plus_one(tmp_path, monkeypatch):
    """SRCX-FR-008: <NNN> is the max existing NNN- prefix plus one, zero-padded; identical listing +
    intent yield a byte-identical name (SRCX-NFR-001); an existing target fails fast, never
    overwritten."""
    specs = tmp_path / "specs-src"
    specs.mkdir()
    (specs / "016-old-feature").mkdir()
    (specs / "notes").mkdir()  # a non-numbered folder is ignored
    name = workspace.feature_folder_name(specs, "Add run artifact workspace")
    assert name == "017-add-run-artifact-workspace"
    assert workspace.feature_folder_name(specs, "Add run artifact workspace") == name  # repeatable
    d = workspace.allocate_feature_dir(tmp_path, "Add run artifact workspace")
    assert d == specs / "017-add-run-artifact-workspace" and d.is_dir()
    # two concurrent runs both observing max=017 pick 018: the loser's mkdir fails fast — a folder
    # allocated for a different run is never overwritten (the SRCX concurrency edge case)
    (specs / "018-boom").mkdir()
    monkeypatch.setattr(workspace, "next_feature_number", lambda p: 18)
    with pytest.raises(FileExistsError):
        workspace.allocate_feature_dir(tmp_path, "boom")
    # an empty specs-src/ starts at 001
    monkeypatch.undo()
    fresh = tmp_path / "other"
    (fresh / "specs-src").mkdir(parents=True)
    assert workspace.feature_folder_name(fresh / "specs-src", "x") == "001-x"


def test_slugify_rules_idempotent_bounded_fallback():
    """SRCX-FR-009: lowercase, non-alphanumeric runs collapse to one hyphen, ends trimmed, bounded
    with no trailing hyphen, fixed fallback when empty; slugify is idempotent and pure."""
    assert (
        workspace.slugify("Fix the OAuth2 token-refresh bug!!")
        == "fix-the-oauth2-token-refresh-bug"
    )
    assert workspace.slugify("  --Weird__ spacing—here  ") == "weird-spacing-here"
    assert workspace.slugify("!!!***") == workspace.SLUG_FALLBACK  # all punctuation → fixed token
    long = workspace.slugify("a" * 40 + " b" * 40)
    assert len(long) <= workspace.SLUG_MAX_LEN and not long.endswith(
        "-"
    )  # bounded, no trailing hyphen
    for s in ("Fix the OAuth2 token-refresh bug!!", "x", "!!!", "A" * 200):
        once = workspace.slugify(s)
        assert workspace.slugify(once) == once  # idempotent


# --------------------------------------------------------------------------- the completion gate (unit)
def _mk_feature(tmp_path: Path) -> Path:
    f = tmp_path / "specs-src" / "017-x"
    f.mkdir(parents=True)
    return f


def _stage_entry(step: str, artifacts: list[str], spec_id="RUN", kind="stage") -> dict:
    return {
        "type": "run",
        "spec_id": spec_id,
        "payload": {"kind": kind, "step": step, "stage": "Plan", "artifacts": artifacts},
    }


def test_completion_check_passes_when_disk_and_ledger_agree(tmp_path):
    """SRCX-FR-012/013: the gate passes iff the declared markdown exists on disk AND a run/stage (or
    checkpoint) entry for the step lists that repo-relative POSIX path; repeated evaluation over the
    same tree and entries yields the identical verdict (SRCX-NFR-001)."""
    f = _mk_feature(tmp_path)
    (f / "plan.md").write_text("# Plan\n", encoding="utf-8")
    entries = [_stage_entry("plan", ["specs-src/017-x/plan.md"])]
    recorded = completion.recorded_stage_artifacts(entries, "RUN")
    chk = completion.check_step(tmp_path, f, "plan", recorded)
    assert chk.ok and chk.path == "specs-src/017-x/plan.md"
    assert completion.check_step(tmp_path, f, "plan", recorded) == chk  # deterministic repeat
    # a checkpoint entry satisfies condition (b) too (SRCX-FR-013)
    cp = completion.recorded_stage_artifacts(
        [_stage_entry("plan", ["specs-src/017-x/plan.md"], kind="checkpoint")], "RUN"
    )
    assert completion.check_step(tmp_path, f, "plan", cp).ok
    # an entry omitting the declared path does NOT satisfy it
    other = completion.recorded_stage_artifacts(
        [_stage_entry("plan", ["specs-src/other/plan.md"])], "RUN"
    )
    assert not completion.check_step(tmp_path, f, "plan", other).ok


def test_resume_entry_index_skips_steps_a_legacy_run_never_recorded(tmp_path):
    """Plan 034 phase 4 (regression): a ledger written before the Discovery step existed carries no
    discovery entries — the resume gate checks only steps the run recorded, so a legacy run still
    resumes at its ledger-derived index instead of being forced back to the new head step."""
    f = _mk_feature(tmp_path)
    (f / "spec.md").write_text("# Spec\n", encoding="utf-8")
    entries = [_stage_entry("specify", ["specs-src/017-x/spec.md"])]
    start = orchestrate.step_index("plan")
    idx, broken = completion.resume_entry_index(entries, "RUN", start, root=tmp_path, feature_dir=f)
    assert idx == start and broken is None


def test_completion_check_absent_and_unrecorded_are_distinct(tmp_path):
    """SRCX-FR-014/015: recorded-but-deleted is artifact_absent; on-disk-but-unrecorded is
    artifact_unrecorded — two distinct named classes, both naming the stage and the path, and both
    distinct from RUNLIVE's dispatch-time artifact_missing."""
    f = _mk_feature(tmp_path)
    recorded = completion.recorded_stage_artifacts(
        [_stage_entry("plan", ["specs-src/017-x/plan.md"])], "RUN"
    )
    absent = completion.check_step(tmp_path, f, "plan", recorded)  # recorded, not on disk
    assert not absent.ok and absent.failure_class == completion.CLASS_ABSENT
    assert "plan" in absent.message and "specs-src/017-x/plan.md" in absent.message
    (f / "plan.md").write_text("# Plan\n", encoding="utf-8")
    orphan = completion.check_step(tmp_path, f, "plan", {})  # on disk, no ledger entry
    assert not orphan.ok and orphan.failure_class == completion.CLASS_UNRECORDED
    assert "plan" in orphan.message
    assert completion.CLASS_ABSENT != completion.CLASS_UNRECORDED
    assert "artifact_missing" not in (completion.CLASS_ABSENT, completion.CLASS_UNRECORDED)


def test_completion_gate_ignores_non_producing_and_unexecuted_steps(tmp_path):
    """SRCX-FR-018: only producing stages at or before the run's position are gated — a pure gate
    step always passes, and a resume never gates a stage the run has not recorded."""
    f = _mk_feature(tmp_path)
    assert completion.check_step(tmp_path, f, "review-spec", {}).ok
    assert completion.check_step(tmp_path, f, "verify", {}).ok
    # a run recorded only through specify: plan was never executed, so it is not gated on resume
    (f / "spec.md").write_text("# Spec\n", encoding="utf-8")
    entries = [_stage_entry("specify", ["specs-src/017-x/spec.md"])]
    idx, broken = completion.resume_entry_index(entries, "RUN", 5, root=tmp_path, feature_dir=f)
    assert idx == 5 and broken is None


def test_recorded_stage_artifacts_is_a_single_pass(tmp_path):
    """SRCX-NFR-004: one ledger read serves all of a run's checks — the recorded map builds from a
    single pass over the injected entries (a one-shot iterable suffices), and each check is a
    constant number of filesystem stats against that map."""
    entries = iter(
        [
            _stage_entry("plan", ["specs-src/017-x/plan.md"]),
            _stage_entry("tasks", ["specs-src/017-x/tasks.md"]),
            _stage_entry("plan", ["specs-src/017-x/plan.md"], kind="checkpoint"),
        ]
    )
    recorded = completion.recorded_stage_artifacts(entries, "RUN")  # a generator: single pass only
    assert recorded["plan"] == ["specs-src/017-x/plan.md"]  # deduped union across stage+checkpoint
    assert recorded["tasks"] == ["specs-src/017-x/tasks.md"]


def test_legacy_split_feature_still_gates_at_split_path(tmp_path):
    """SRCX-NFR-003 / SRCX-FR-003: an already-written split-layout artifact is checked AT its split
    path (nothing relocated), while the flat location stays the canonical write target."""
    f = tmp_path / "specs-src" / "013-legacy"
    (f / "artifacts").mkdir(parents=True)
    (f / "artifacts" / "plan.md").write_text("# Plan\n", encoding="utf-8")
    recorded = completion.recorded_stage_artifacts(
        [_stage_entry("plan", ["specs-src/013-legacy/artifacts/plan.md"])], "RUN"
    )
    chk = completion.check_step(tmp_path, f, "plan", recorded)
    assert chk.ok and chk.path == "specs-src/013-legacy/artifacts/plan.md"
    assert (f / "artifacts" / "plan.md").is_file()  # no file was moved


# --------------------------------------------------------------------- legacy base folder back-compat
def test_legacy_specs_base_still_resolves(tmp_path):
    """SRCX-FR-002 (legacy base): features under the legacy ``specs/`` base keep resolving through
    find_specs and resolve_feature_dir, while the canonical ``specs-src/`` base is searched first
    and wins when both bases hold the same number."""
    canonical = tmp_path / "specs-src" / "020-new"
    canonical.mkdir(parents=True)
    (canonical / "spec.md").write_text("new\n", encoding="utf-8")
    legacy = tmp_path / "specs" / "010-old"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("old\n", encoding="utf-8")
    # both bases contribute — one spec per feature, across the mixed tree
    assert workspace.find_specs(tmp_path) == sorted([canonical / "spec.md", legacy / "spec.md"])
    assert workspace.resolve_feature_dir(tmp_path, "020") == canonical
    assert workspace.resolve_feature_dir(tmp_path, "010") == legacy
    # the same number in both bases: the canonical base wins, deterministically
    shadow = tmp_path / "specs" / "020-shadow"
    shadow.mkdir(parents=True)
    (shadow / "spec.md").write_text("shadow\n", encoding="utf-8")
    assert workspace.resolve_feature_dir(tmp_path, "020") == canonical


def test_legacy_base_ledger_entry_still_passes_completion(tmp_path):
    """SRCX-FR-012 (legacy base, no ledger rewrite): a signed entry recording the old
    ``specs/<f>/...`` path keeps satisfying the stage-completion gate for a feature that still
    lives under the legacy base — resume/re-check never requires rewriting ledger history."""
    f = tmp_path / "specs" / "013-x"
    f.mkdir(parents=True)
    (f / "plan.md").write_text("# Plan\n", encoding="utf-8")
    recorded = completion.recorded_stage_artifacts(
        [_stage_entry("plan", ["specs/013-x/plan.md"])], "RUN"
    )
    chk = completion.check_step(tmp_path, f, "plan", recorded)
    assert chk.ok and chk.path == "specs/013-x/plan.md"


# --------------------------------------------------------------------------- live runs (fake agent, no network)
def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _feature_dir_of_prompt(prompt: str, cwd: Path, spec_id: str) -> Path:
    import re

    m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
    return cwd / (m.group(1) if m else f"specs-src/{spec_id}")


def _writer(spec_id="RUN", skip=(), spec_folder: str | None = None):
    """A fake agent writing each stage's declared artifact flat into the folder the prompt names
    (SRCX-FR-001); ``spec_folder`` overrides the specify target (the wrong-folder case)."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        d = _feature_dir_of_prompt(prompt, cwd, spec_id)
        if "# Discovery agent" in prompt and "discovery" not in skip:
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
        elif "# Specify agent" in prompt and "specify" not in skip:
            t = (cwd / spec_folder) if spec_folder else d
            t.mkdir(parents=True, exist_ok=True)
            (t / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "# Plan agent" in prompt and "plan" not in skip:
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in prompt and "tasks" not in skip:
            d.mkdir(parents=True, exist_ok=True)
            (d / "implementation-plan.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "# Oracle agent" in prompt and "oracle" not in skip:
            import re

            m = re.search(r"tests/oracle/([^`<\s/]+)/", prompt)
            t = cwd / "tests" / "oracle" / (m.group(1) if m else spec_id)
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "# Implement agent" in prompt and "implement" not in skip:
            src = cwd / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "changes written", "")

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
            "t",
        ]
    )


def test_full_run_leaves_one_flat_ledger_tracked_folder(run_repo, monkeypatch, capsys):
    """SRCX-FR-001/004/005/007/011 + SRCX-SC-001/002: a fresh run allocates specs-src/<NNN>-<slug>/,
    every producing stage's markdown lies FLAT in it and is named in a signed run/stage entry;
    the gate/verdict/sign-off stages leave no document; the run/start entry binds the folder;
    `3pwr verify` stays green over the new records (SRCX-NFR-002)."""
    _mock_gates_green(monkeypatch)
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    assert _resume(run_repo) == 3  # → signoff gate
    capsys.readouterr()

    fdir = run_repo / "specs-src" / "001-add-x"
    changelog_before = (
        (run_repo / "CHANGELOG.md").read_text(encoding="utf-8")
        if (run_repo / "CHANGELOG.md").is_file()
        else None
    )
    for name in (
        "discovery.md",
        "spec.md",
        "plan.md",
        "implementation-plan.md",
        "oracle.md",
        "changelog.md",
    ):
        assert (fdir / name).is_file(), name  # SRCX-FR-004: the six producing markdowns, flat
    for legacy in ("tasks.md", "implement.md"):
        assert not (fdir / legacy).exists(), legacy  # legacy names are never written
    assert not (fdir / "spec").exists() and not (fdir / "artifacts").exists()  # SRCX-FR-001
    for name in ("review-spec.md", "verify.md", "signoff.md", "advance.md", "clarify.md"):
        assert not (fdir / name).exists(), name  # SRCX-FR-007: ledger-only stages
    # the changelog links the real outputs at their real repo paths (SRCX-FR-005); the oracle
    # tests land under the run's keyed destination tests/oracle/<NNN>-<slug>/ and oracle.md is
    # the path-free Tests Specification keyed by the same folder id (CON-005)
    oracle_md = (fdir / "oracle.md").read_text(encoding="utf-8")
    assert "Tests Specification — 001-add-x" in oracle_md
    assert "tests/oracle/" not in oracle_md  # path-free: the machine record lives in the ledger
    assert "src/impl.py" in (fdir / "changelog.md").read_text(encoding="utf-8")
    assert (run_repo / "tests" / "oracle" / "001-add-x" / "test_oracle.py").is_file()
    # the top-level project CHANGELOG.md is untouched by a run
    changelog_after = (
        (run_repo / "CHANGELOG.md").read_text(encoding="utf-8")
        if (run_repo / "CHANGELOG.md").is_file()
        else None
    )
    assert changelog_after == changelog_before

    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    recorded = completion.recorded_stage_artifacts(entries, "RUN")
    # the machine record of the actual oracle test paths lives in the signed stage entry —
    # keyed by the run's folder id — so oracle.md can stay path-free
    assert "tests/oracle/001-add-x/test_oracle.py" in recorded["oracle"]
    for step in workspace.PRODUCING_STEPS:  # SRCX-SC-002: every markdown named in a signed entry
        rel = f"specs-src/001-add-x/{workspace.step_filename(step)}"
        assert rel in recorded[step], (step, recorded)
    # SRCX-FR-011: the run/start payload binds the allocated folder, recoverable offline
    assert _run_feature_dir_from_ledger(Settings(root=run_repo), entries, "RUN") == fdir
    assert main(["--root", str(run_repo), "verify"]) == 0  # SRCX-NFR-002


def test_run_walks_discovery_first_and_feeds_the_note_to_specify(run_repo, monkeypatch, capsys):
    """Plan 034 phase 4: a fresh run dispatches Discovery FIRST, its note lands flat in the run's
    feature folder satisfying the discovery contract, and Specify's dispatched prompt carries the
    accepted note as PRIOR CONTEXT — the existing prior-artifact handoff, one stage further back."""
    prompts_seen: list[str] = []

    def recording(argv, **kw):
        prompts_seen.append(argv[-1] if argv else "")
        return _writer()(argv, **kw)

    monkeypatch.setattr(runner, "dispatch_agent", recording)
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    capsys.readouterr()
    assert "# Discovery agent" in prompts_seen[0]  # the walk's head step, dispatched first
    note = run_repo / "specs-src" / "001-add-x" / "discovery.md"
    assert note.is_file()
    chk = artifacts.verify(
        artifacts.contract_for("discovery"), ["specs-src/001-add-x/discovery.md"]
    )
    assert chk.ok  # the produced note satisfies the discovery contract
    # ...and the signed stage entry records it, like every other producing stage
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    recorded = completion.recorded_stage_artifacts(entries, "RUN")
    assert "specs-src/001-add-x/discovery.md" in recorded["discovery"]
    spec_prompt = next(p for p in prompts_seen if "# Specify agent" in p)
    assert "PRIOR CONTEXT:" in spec_prompt
    assert (
        "prior stage 'discovery' accepted artifact: specs-src/001-add-x/discovery.md" in spec_prompt
    )


def test_wrong_folder_spec_is_blocked_as_artifact_absent(run_repo, monkeypatch, capsys):
    """SRCX-FR-012/014/016: a stage whose declared markdown is NOT in the run's feature folder (the
    agent wrote elsewhere; the dispatch contract still matched) is blocked by the completion gate —
    classified artifact_absent, naming the stage and the missing path, on the non-gate-red exit
    path — and both status commands report it until a later record passes the stage."""
    monkeypatch.setattr(runner, "dispatch_agent", _writer(spec_folder="specs-src/elsewhere"))
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json", "--spec-id", "RUN"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_SETUP == 4  # blocked, not a gate verdict
    assert obj["status"] == "artifact_absent"
    assert "specify" in obj["detail"] and "specs-src/001-add-x/spec.md" in obj["detail"]
    # the failure is a signed run/failure record carrying the new class (SRCX-FR-016)
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    failures = [
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "failure"
    ]
    assert failures and failures[-1]["payload"]["class"] == "artifact_absent"
    assert main(["--root", str(run_repo), "run", "--status", "--spec-id", "RUN"]) == 0
    assert "failed at Spec (artifact_absent)" in capsys.readouterr().out
    assert main(["--root", str(run_repo), "status", "--spec-id", "RUN"]) == 0
    assert "failed at Spec (artifact_absent)" in capsys.readouterr().out
    assert main(["--root", str(run_repo), "verify"]) == 0  # additive values only (SRCX-NFR-002)


def test_unrecorded_artifact_blocks_via_the_failure_branch(run_repo, monkeypatch, capsys):
    """SRCX-FR-015/016: an on-disk artifact no matching ledger entry records blocks the run with the
    distinct artifact_unrecorded class — recorded, surfaced, and exiting on the setup path."""

    def unrecorded(root, feature_dir, step, recorded):
        return completion.CompletionCheck(
            ok=False,
            step=step,
            path=f"specs-src/001-add-x/{'spec' if step == 'specify' else step}.md",
            failure_class=completion.CLASS_UNRECORDED,
        )

    monkeypatch.setattr(completion, "check_step", unrecorded)
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json", "--spec-id", "RUN"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_SETUP and obj["status"] == "artifact_unrecorded"
    assert "no ledger entry records it" in obj["detail"]
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    failures = [
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "failure"
    ]
    assert failures[-1]["payload"]["class"] == "artifact_unrecorded"
    assert main(["--root", str(run_repo), "verify"]) == 0


def test_resume_reruns_stage_whose_artifact_vanished(run_repo, monkeypatch, capsys):
    """SRCX-FR-017 + SRCX-SC-003 (the headline gap): a run recorded complete through tasks, plan.md
    then deleted, resumes AT plan — naming the missing artifact, not skipping to oracle — re-runs the
    later stages in order, overwrites plan.md, appends a fresh run/stage entry, and the gate passes;
    the earlier entries remain in the append-only ledger as history."""
    _mock_gates_green(monkeypatch)
    assert main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    # segment 2: plan+tasks complete, oracle produces nothing → the run stops at Build
    monkeypatch.setattr(runner, "dispatch_agent", _writer(skip=("oracle",)))
    assert _resume(run_repo) == EXIT_SETUP
    plan_md = run_repo / "specs-src" / "001-add-x" / "plan.md"
    assert plan_md.is_file()
    plan_md.unlink()  # the artifact vanishes after its stage completed

    seen: list[str] = []

    def recording(argv, **kw):
        prompt = argv[-1] if argv else ""
        for key, marker in (
            ("specify", "# Specify agent"),
            ("clarify", "# Clarify agent"),
            ("plan", "# Plan agent"),
            ("tasks", "# Implementation-plan agent"),
            ("oracle", "# Oracle agent"),
            ("implement", "# Implement agent"),
        ):
            if marker in prompt:
                seen.append(key)
        return _writer()(argv, **kw)

    monkeypatch.setattr(runner, "dispatch_agent", recording)
    capsys.readouterr()
    rc = _resume(run_repo)
    err = capsys.readouterr().err
    assert rc == 3  # reached the signoff gate — the broken stage was re-run, not skipped
    assert "resume re-enters at 'plan'" in err and "specs-src/001-add-x/plan.md" in err
    assert seen and seen[0] == "plan"  # re-entered at plan, NOT at oracle (SRCX-SC-003)
    assert "oracle" in seen and "implement" in seen  # later stages re-ran in order
    assert "specify" not in seen  # an intact completed stage is never re-dispatched
    assert plan_md.is_file()  # the re-run overwrote the artifact
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    plan_entries = [
        e
        for e in entries
        if e.get("type") == "run"
        and e["payload"].get("kind") in ("stage", "checkpoint")
        and e["payload"].get("step") == "plan"
    ]
    assert len(plan_entries) >= 2  # the fresh entry appended; history remains append-only
    assert main(["--root", str(run_repo), "verify"]) == 0


def test_resume_never_allocates_and_a_paused_run_is_not_failed_early(run_repo, monkeypatch, capsys):
    """SRCX-FR-010: a resume re-enters the recorded folder and creates no new numbered folder;
    SRCX-FR-018: a run paused at the review-spec human gate is never failed for a missing plan.md
    (a stage the run has not reached)."""
    _mock_gates_green(monkeypatch)
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    assert (
        rc == EXIT_PAUSED
    )  # paused at review-spec — no completion failure about plan/tasks (FR-018)
    folders_before = sorted(p.name for p in (run_repo / "specs-src").iterdir() if p.is_dir())
    assert _resume(run_repo) == 3
    folders_after = sorted(p.name for p in (run_repo / "specs-src").iterdir() if p.is_dir())
    assert folders_before == folders_after == ["001-add-x"]  # resume allocated nothing (FR-010)


def test_dry_run_allocates_nothing_and_stays_green(run_repo, capsys):
    """SRCX-NFR-005: --dry-run dispatches nothing and writes no artifacts — the completion gate is a
    live-runner concern — so it allocates no folder and stays offline and green."""
    rc = main(
        ["--root", str(run_repo), "run", "add x", "--dry-run", "--no-input", "--spec-id", "D"]
    )
    assert rc == EXIT_PAUSED
    assert not (run_repo / "specs-src").exists() or not any((run_repo / "specs-src").iterdir())


def test_pre_srcx_ledger_still_verifies_and_resolves(run_repo, capsys):
    """SRCX-NFR-002/003: a ledger whose run/start carries no feature_dir (pre-SRCX) still verifies
    unchanged, and the folder binding simply resolves to None (the legacy fallback applies)."""
    from threepowers import keys

    s = Settings(root=run_repo)
    ledger = Ledger(s.ledger_path)
    sk = keys.resolve_signer(run_repo)
    ledger.append("run", {"kind": "start", "intent": "old", "mode": "auto"}, sk, spec_id="OLD")
    ledger.append(
        "run",
        {"kind": "stage", "step": "specify", "stage": "Spec", "artifacts": ["specs-src/x/spec.md"]},
        sk,
        spec_id="OLD",
    )
    assert main(["--root", str(run_repo), "verify"]) == 0
    assert _run_feature_dir_from_ledger(s, ledger.entries(), "OLD") is None
