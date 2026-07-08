"""Phased execution — context-sized phases, the feature workspace, fresh sessions, parallel dispatch (PHASE, spec 013).

Exercises the whole PHASE surface with a fake agent and no network: the per-feature workspace and its
legacy fallback (PHASE-FR-001), the extended artifact contracts (PHASE-FR-002), the artifact-path ledger
record (PHASE-FR-003), the enriched plan/tasks prompts and context injection (PHASE-FR-004/005), the
template guidance (PHASE-FR-006), the advisory context budget (PHASE-FR-007/008/009), and the
fresh-session-per-phase / parallel-subagent dispatch (PHASE-FR-010/011/012), plus the determinism and
trust-spine NFRs (PHASE-NFR-001/002/003).
"""

from __future__ import annotations

import re
import subprocess
import threading
from pathlib import Path

import pytest

from threepowers import artifacts, orchestrate, phases, prompts, runner, runpreflight, workspace
from threepowers.cli import _dispatch_spec_text, main
from threepowers.config import Settings
from threepowers.ledger import Ledger
from threepowers.runner import CliAgentRunner
from threepowers.verify import verify_ledger

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- workspace (PHASE-FR-001 → SRCX-FR-001/002/003)
def test_workspace_layout_resolves_spec_in_spec_subfolder(tmp_path):
    """SRCX-FR-002: a legacy PHASE-split feature's spec (spec/spec.md) still resolves; writes are FLAT."""
    f = tmp_path / "specs-src" / "020-new"
    (f / "spec").mkdir(parents=True)
    (f / "spec" / "spec.md").write_text("# Spec\n", encoding="utf-8")
    assert workspace.spec_path(f) == f / "spec" / "spec.md"
    assert workspace.feature_dir_of(f / "spec" / "spec.md") == f
    assert workspace.artifacts_dir(f) == f / "artifacts"
    # SRCX-FR-001 supersedes the split write locations: every producing step writes FLAT.
    assert workspace.stage_artifact_path(f, "plan") == f / "plan.md"
    assert workspace.stage_artifact_path(f, "specify") == f / "spec.md"


def test_legacy_layout_still_resolves(tmp_path):
    """SRCX-FR-002/NFR-003: a flat feature (spec.md directly in the folder — now canonical) resolves."""
    f = tmp_path / "specs-src" / "002-old"
    f.mkdir(parents=True)
    (f / "spec.md").write_text("# Spec\n", encoding="utf-8")
    assert workspace.spec_path(f) == f / "spec.md"
    assert workspace.feature_dir_of(f / "spec.md") == f
    # a flat LEGACY-named tasks artifact next to the spec is still found (SRCX-FR-003)
    (f / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    assert workspace.find_artifact(f, "tasks") == f / "tasks.md"


def test_renamed_stage_artifacts_write_new_names_and_resolve_legacy(tmp_path):
    """SRCX-FR-001/003 (rename): the tasks step WRITES implementation-plan.md and the implement
    step WRITES changelog.md; find_artifact resolves the canonical name first and falls back to
    the legacy tasks.md / implement.md — never yielding two paths for one stage."""
    f = tmp_path / "specs-src" / "030-x"
    f.mkdir(parents=True)
    assert workspace.stage_artifact_path(f, "tasks").name == "implementation-plan.md"
    assert workspace.stage_artifact_path(f, "implement").name == "changelog.md"
    # legacy filenames resolve when the canonical one is absent…
    (f / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    (f / "implement.md").write_text("# Record\n", encoding="utf-8")
    assert workspace.find_artifact(f, "tasks") == f / "tasks.md"
    assert workspace.find_artifact(f, "implement") == f / "implement.md"
    # …and the canonical name wins when both exist
    (f / "implementation-plan.md").write_text("# Plan\n", encoding="utf-8")
    (f / "changelog.md").write_text("# Changelog\n", encoding="utf-8")
    assert workspace.find_artifact(f, "tasks") == f / "implementation-plan.md"
    assert workspace.find_artifact(f, "implement") == f / "changelog.md"


def test_exactly_one_spec_per_feature_whichever_layout(tmp_path):
    """SRCX-FR-002 (property): resolution finds exactly one specification per feature folder —
    the canonical FLAT layout wins when both exist, and find_specs never yields a feature twice."""
    f = tmp_path / "specs-src" / "021-mixed"
    (f / "spec").mkdir(parents=True)
    (f / "spec" / "spec.md").write_text("split\n", encoding="utf-8")
    (f / "spec.md").write_text("flat\n", encoding="utf-8")
    assert workspace.spec_path(f) == f / "spec.md"
    legacy = tmp_path / "specs-src" / "002-old"
    legacy.mkdir(parents=True)
    (legacy / "spec.md").write_text("old\n", encoding="utf-8")
    found = workspace.find_specs(tmp_path)
    assert found == sorted([f / "spec.md", legacy / "spec.md"])
    assert len(found) == len({workspace.feature_dir_of(p) for p in found})


# --------------------------------------------------------------------------- artifact contracts (PHASE-FR-002)
def test_plan_and_tasks_now_carry_hard_contracts():
    """PHASE-FR-002: plan/tasks lost RUNLIVE-FR-003's lenient fallback — each declares its artifact."""
    for step in ("plan", "tasks"):
        c = artifacts.contract_for(step)
        assert c is not None and c.kind == "path"
        # both the workspace and the legacy location satisfy the contract (PHASE-FR-001)
        assert artifacts.verify(c, [f"specs-src/013-x/artifacts/{step}.md"]).ok
        assert artifacts.verify(c, [f"specs-src/013-x/{step}.md"]).ok
        # legacy base back-compat: recorded specs/… paths keep matching
        assert artifacts.verify(c, [f"specs/013-x/artifacts/{step}.md"]).ok
    # the tasks contract's canonical artifact is the renamed implementation-plan.md
    tc = artifacts.contract_for("tasks")
    assert artifacts.verify(tc, ["specs-src/013-x/implementation-plan.md"]).ok
    assert artifacts.verify(tc, ["specs/013-x/implementation-plan.md"]).ok


def test_empty_plan_dispatch_is_a_named_artifact_failure():
    """PHASE-FR-002: a plan/tasks dispatch that writes no artifact fails naming the expected path."""
    chk = artifacts.verify(artifacts.contract_for("plan"), [])
    assert not chk.ok and "plan artifact" in chk.message
    assert "specs-src/<feature>/plan.md" in chk.message
    chk2 = artifacts.verify(artifacts.contract_for("tasks"), ["notes.txt"])
    assert not chk2.ok and "implementation-plan artifact" in chk2.message


def test_specify_contract_accepts_workspace_layout():
    """PHASE-FR-001/002: the spec contract accepts <feature>/spec/spec.md and the legacy flat file."""
    c = artifacts.contract_for("specify")
    assert artifacts.verify(c, ["specs-src/020-new/spec/spec.md"]).ok
    assert artifacts.verify(c, ["specs-src/002-old/spec.md"]).ok
    # legacy base back-compat: recorded specs/… paths keep matching
    assert artifacts.verify(c, ["specs/002-old/spec.md"]).ok


# --------------------------------------------------------------------------- prompts (PHASE-FR-004/005)
def test_plan_tasks_prompts_name_artifact_sections_and_rules():
    """PHASE-FR-004: the plan/tasks prompt bodies name the artifact path, the required sections, the
    phase-decomposition rules, and the context-sizing heuristic — at specify/oracle depth."""
    plan = prompts.resolve_body("plan", None)
    assert "specs-src/<feature>/plan.md" in plan
    assert "Required sections" in plan and "Phases" in plan
    assert "file scope" in plan and "[P]" in plan
    # markdown wraps lines, so compare on whitespace-normalized text
    plan_flat = " ".join(plan.split())
    assert "110k tokens" in plan_flat and "4 bytes per token" in plan_flat
    tasks = prompts.resolve_body("tasks", None)
    assert "specs-src/<feature>/implementation-plan.md" in tasks
    assert "## Phase N" in tasks and "**File scope**" in tasks and "**Depends on**" in tasks
    assert "HANDOFF" in tasks and "Estimated context" in tasks
    assert "exactly ONE requirement id" in tasks
    # comparable depth to the specify/oracle prompts (both are multi-sentence, artifact-naming)
    assert len(plan) > len(prompts.resolve_body("clarify", None))
    assert len(tasks) > len(prompts.resolve_body("clarify", None))


def test_dispatch_injects_spec_context_and_scope_deterministically(tmp_path):
    """PHASE-FR-005: a dispatched stage's prompt contains the approved spec, the prior artifact
    reference, and the phase file scope; identical inputs produce an identical prompt."""
    s = Settings(root=tmp_path)
    manifest = {"command": "agent", "prompt_flag": "-p"}
    seen: list[str] = []

    def fake(argv, **kw):
        seen.append(argv[-1])
        return (0, "", "")

    r = CliAgentRunner(s, manifest, intent="add x", dispatcher=fake)
    r.dispatch(
        "implement",
        "Build",
        spec_text="THE LAW",
        context="prior stage 'tasks' accepted artifact: specs-src/x/artifacts/tasks.md",
        file_scope="src/a.py\nsrc/b.py",
    )
    p = seen[-1]
    assert "APPROVED SPEC:" in p and "THE LAW" in p
    assert "PRIOR CONTEXT:" in p and "artifacts/tasks.md" in p
    assert "FILE SCOPE:" in p and "src/a.py" in p
    # determinism (PHASE-NFR-001): the same inputs assemble byte-identical prompts
    a = prompts.assemble("implement", intent="i", spec_text="S", context="C", file_scope="F")
    b = prompts.assemble("implement", intent="i", spec_text="S", context="C", file_scope="F")
    assert a == b


def test_spec_text_injected_only_after_spec_approval(tmp_path):
    """PHASE-FR-005: stages after the review-spec gate reload the approved spec; specify/clarify do not."""
    s = Settings(root=tmp_path)
    spec = tmp_path / "specs-src" / "f" / "spec.md"
    spec.parent.mkdir(parents=True)
    spec.write_text("APPROVED TEXT\n", encoding="utf-8")
    for step in ("plan", "tasks", "oracle", "implement"):
        assert "APPROVED TEXT" in _dispatch_spec_text(s, step, spec), step
    for step in ("specify", "clarify"):
        assert _dispatch_spec_text(s, step, spec) == "", step


# --------------------------------------------------------------------------- templates (PHASE-FR-006)
def test_templates_carry_handoff_size_and_no_speckit():
    """PHASE-FR-006: the shipped plan/implementation-plan templates present phases as self-contained
    delegable units (handoff block + estimated size + parallel markers), mandate per-phase coding
    gates and a final Verification phase, drop the role→model-family table, and carry no Spec-Kit
    command references."""
    tdir = REPO_ROOT / ".3powers" / "templates"
    tasks = (tdir / "implementation-plan-template.md").read_text(encoding="utf-8")
    assert "**Handoff**" in tasks and "**File scope**" in tasks and "**Depends on**" in tasks
    assert "Estimated context" in tasks and "[P]" in tasks
    for reload_item in ("spec", "constitution", "tasks", "file scope"):
        assert reload_item in tasks.lower()
    # per-phase coding gates + the mandatory final Verification phase
    assert "coding gate" in tasks.lower() and "3pwr gate run --path" in tasks
    assert "Verification" in tasks and "all prior phases" in tasks
    plan = (tdir / "plan-template.md").read_text(encoding="utf-8")
    assert "Phase Decomposition" in plan and "context budget" in plan
    assert "Risk tier & gates" in plan
    assert "coding gate" in plan.lower() and "Verification" in plan
    # the de-judicialized plan doc: no "Judicial" label, no role→model-family table
    assert "Judicial" not in plan and "model-family" not in plan
    for f in tdir.glob("*.md"):
        assert "/speckit." not in f.read_text(encoding="utf-8"), f.name


# --------------------------------------------------------------------------- budget config (PHASE-FR-007)
def test_context_budget_default_and_overrides(tmp_path):
    """PHASE-FR-007: no config → the shipped ~110k default; a config budget and a per-model entry win."""
    s = Settings(root=tmp_path)
    assert s.context_budget() == 110_000
    assert s.context_budget("any/model") == 110_000
    cfg = tmp_path / ".3powers" / "config"
    cfg.mkdir(parents=True)
    (cfg / "context.yaml").write_text(
        "budget_tokens: 50000\nmodels:\n  vendor/big: 200000\n", encoding="utf-8"
    )
    assert s.context_budget() == 50_000
    assert s.context_budget("vendor/big") == 200_000
    assert s.context_budget("vendor/other") == 50_000


def test_budget_resolution_is_deterministic_and_rejects_garbage(tmp_path):
    """PHASE-FR-007 (property): same config bytes, same budget; a non-numeric value falls back."""
    s = Settings(root=tmp_path)
    cfg = tmp_path / ".3powers" / "config"
    cfg.mkdir(parents=True)
    (cfg / "context.yaml").write_text("budget_tokens: banana\n", encoding="utf-8")
    assert s.context_budget() == s.context_budget() == 110_000
    (cfg / "context.yaml").write_text("budget_tokens: 42\n", encoding="utf-8")
    assert s.context_budget() == 42 and s.context_budget() == 42


# --------------------------------------------------------------------------- size estimate (PHASE-FR-008)
_TASKS_3PHASE = """# Tasks: demo

## Phase 1: core

**File scope**: src/core.py
**Depends on**: none

- [ ] T001 [X-FR-001] build core (files: src/core.py)

## Phase 2: alpha [P]

**File scope**: src/alpha.py
**Depends on**: none

- [ ] T002 [X-FR-002] alpha (files: src/alpha.py)

## Phase 3: beta [P]

**File scope**: src/beta.py
**Depends on**: none

- [ ] T003 [X-FR-003] beta (files: src/beta.py)
"""


def test_estimate_is_deterministic_from_reload_set_bytes(tmp_path):
    """PHASE-FR-008 (property): identical reload-set bytes produce an identical estimate — no tokenizer,
    no network; the estimate covers spec + rules + tasks + files in scope."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "core.py").write_bytes(b"x" * 4000)
    spec = tmp_path / "spec.md"
    spec.write_bytes(b"s" * 8000)
    ph = phases.parse_phases(_TASKS_3PHASE)[0]
    e1 = phases.phase_estimate(tmp_path, ph, spec_path=spec, prompt_text="P" * 400)
    e2 = phases.phase_estimate(tmp_path, ph, spec_path=spec, prompt_text="P" * 400)
    assert e1 == e2 > 0
    # ~4 bytes/token: the estimate reflects the reload set's bytes (spec + scope file + body + prompt)
    expected_bytes = 8000 + 4000 + len(ph.body.encode()) + 400
    assert e1 == -(-expected_bytes // phases.BYTES_PER_TOKEN)
    # a bigger reload set yields a bigger estimate
    (tmp_path / "src" / "core.py").write_bytes(b"x" * 40000)
    assert phases.phase_estimate(tmp_path, ph, spec_path=spec, prompt_text="P" * 400) > e1


def test_estimate_tokens_never_negative_and_zero_safe():
    """PHASE-FR-008: the bytes→tokens estimate is total and deterministic on any input."""
    assert phases.estimate_tokens(0) == 0
    assert phases.estimate_tokens(-5) == 0
    assert phases.estimate_tokens(1) == 1
    assert phases.estimate_tokens(4) == 1
    assert phases.estimate_tokens(5) == 2


# --------------------------------------------------------------------------- advisory warning (PHASE-FR-009)
def test_oversize_phase_warns_names_phase_estimate_budget_and_never_raises():
    """PHASE-FR-009: an over-budget phase yields an advisory warning naming the phase, its estimate,
    and the budget, instructing a split; a fitting phase yields none."""
    ph = phases.Phase(
        index=1,
        name="core",
        tasks=("- [ ] T001 [X-FR-001] a", "- [ ] T002 [X-FR-002] b"),
    )
    warn = phases.oversize_warning(ph, estimate=200_000, budget=110_000)
    assert warn is not None
    assert "phase 1" in warn and "200000" in warn and "110000" in warn
    assert "split" in warn and "advisory" in warn and "never blocking" in warn
    assert phases.oversize_warning(ph, estimate=100, budget=110_000) is None


def test_irreducible_oversize_phase_is_told_so():
    """PHASE-FR-009 (edge): one indivisible task over budget → the warning stands, says irreducible."""
    ph = phases.Phase(index=2, name="big", tasks=("- [ ] T001 [X-FR-001] one",))
    warn = phases.oversize_warning(ph, estimate=300_000, budget=110_000)
    assert warn is not None and "irreducible" in warn


# --------------------------------------------------------------------------- parsing & scheduling (PHASE-FR-010/011)
def test_parse_phases_reads_order_scope_parallel_dependencies():
    """PHASE-FR-010/011: phases parse in artifact order with scope (line + per-task), markers, deps."""
    got = phases.parse_phases(_TASKS_3PHASE)
    assert [p.name for p in got] == ["core", "alpha", "beta"]
    assert [p.index for p in got] == [1, 2, 3]
    assert got[0].file_scope == ("src/core.py",) and not got[0].parallel
    assert got[1].parallel and got[2].parallel
    text_dep = _TASKS_3PHASE + "\n## Phase 4: wrap\n\n**Depends on**: Phase 1\n**Parallel**: yes\n"
    p4 = phases.parse_phases(text_dep)[3]
    assert p4.depends_on == ("Phase 1",) and p4.parallel


def test_parse_double_digit_phase_headings():
    """PHASE-FR-010 (edge): 'Phase 10' parses cleanly (no lazy-match truncation of the name)."""
    got = phases.parse_phases("## Phase 10: the tenth\n- [ ] T1 [X-FR-001] t (files: a.py)\n")
    assert got[0].name == "the tenth" and got[0].file_scope == ("a.py",)


def test_no_phase_headings_yields_empty_list_degenerate_case():
    """PHASE-FR-010: a tasks artifact with no phases → [] → the caller runs one single session."""
    assert phases.parse_phases("# Tasks\n- [ ] T001 [X-FR-001] all of it\n") == []


def test_schedule_batches_disjoint_parallel_phases_concurrently():
    """PHASE-FR-011: parallel-marked, dependency-free phases with disjoint scopes share a batch."""
    got = phases.parse_phases(_TASKS_3PHASE)
    batches, notes = phases.schedule(got)
    assert [[p.index for p in b] for b in batches] == [[1], [2, 3]]
    assert notes == []


def test_schedule_serializes_overlapping_scopes_despite_markers():
    """PHASE-FR-011: overlapping declared scopes run sequentially even when marked [P], reported."""
    text = (
        "## Phase 1: a [P]\n\n**File scope**: src/shared.py\n**Depends on**: none\n"
        "- [ ] T1 [X-FR-001] a (files: src/shared.py)\n"
        "## Phase 2: b [P]\n\n**File scope**: src/shared.py\n**Depends on**: none\n"
        "- [ ] T2 [X-FR-002] b (files: src/shared.py)\n"
    )
    batches, notes = phases.schedule(phases.parse_phases(text))
    assert [[p.index for p in b] for b in batches] == [[1], [2]]
    assert notes and "src/shared.py" in notes[0] and "sequentially" in notes[0]


def test_schedule_property_concurrent_only_if_scopes_disjoint():
    """PHASE-FR-011 (property): any two phases sharing a batch have an empty scope intersection."""
    text = _TASKS_3PHASE + (
        "\n## Phase 4: gamma [P]\n\n**File scope**: src/alpha.py src/gamma.py\n"
        "**Depends on**: none\n- [ ] T4 [X-FR-004] g (files: src/gamma.py)\n"
    )
    batches, _ = phases.schedule(phases.parse_phases(text))
    for batch in batches:
        for i, a in enumerate(batch):
            for b in batch[i + 1 :]:
                assert not set(a.file_scope) & set(b.file_scope)


def test_dependent_or_scopeless_phase_never_joins_a_batch():
    """PHASE-FR-011: a declared dependency — or an undeclared scope — forces sequential execution."""
    text = (
        "## Phase 1: a [P]\n\n**File scope**: a.py\n**Depends on**: none\n- [ ] T1 [X-FR-001] a (files: a.py)\n"
        "## Phase 2: b [P]\n\n**File scope**: b.py\n**Depends on**: Phase 1\n- [ ] T2 [X-FR-002] b (files: b.py)\n"
        "## Phase 3: c [P]\n\n**Depends on**: none\n- [ ] T3 [X-FR-003] c\n"
    )
    batches, _ = phases.schedule(phases.parse_phases(text))
    assert [[p.index for p in b] for b in batches] == [[1], [2], [3]]


# --------------------------------------------------------------------------- execution (PHASE-FR-010/012)
def test_run_phases_dispatches_each_phase_concurrent_batch_together():
    """PHASE-FR-010/011: every phase is dispatched once; a batch's phases run concurrently."""
    got = phases.parse_phases(_TASKS_3PHASE)
    batches, _ = phases.schedule(got)
    active = {"n": 0, "max": 0}
    lock = threading.Lock()
    barrier = threading.Barrier(2, timeout=5)

    def run_one(ph):
        with lock:
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
        if ph.parallel:
            barrier.wait()  # both parallel phases must be in flight together
        with lock:
            active["n"] -= 1
        return True, ""

    run = phases.run_phases(batches, run_one)
    assert run.ok and [r.index for r in run.results] == [1, 2, 3]
    assert active["max"] >= 2  # the [P] batch overlapped


def test_run_phases_records_deterministic_order_and_names_failures():
    """PHASE-FR-012: results are recorded in artifact order regardless of completion order; a failing
    phase fails the run with an actionable message naming it; siblings' results are kept."""
    got = phases.parse_phases(_TASKS_3PHASE)
    batches, _ = phases.schedule(got)

    def run_one(ph):
        return (ph.index != 3), ("" if ph.index != 3 else "compile error")

    r1 = phases.run_phases(batches, run_one)
    r2 = phases.run_phases(batches, run_one)
    assert [x.as_dict() for x in r1.results] == [x.as_dict() for x in r2.results]
    assert not r1.ok
    assert "phase 3 'beta' failed: compile error" in r1.failure_detail
    assert r1.results[1].ok  # the successful sibling's completed work is recorded, not discarded


def test_run_phases_never_reports_skipped_later_phases_as_passed():
    """PHASE-FR-012: after a failure, later phases are explicitly skipped — never silently passed."""
    text = (
        "## Phase 1: a\n\n**File scope**: a.py\n- [ ] T1 [X-FR-001] a (files: a.py)\n"
        "## Phase 2: b\n\n**File scope**: b.py\n- [ ] T2 [X-FR-002] b (files: b.py)\n"
    )
    batches, _ = phases.schedule(phases.parse_phases(text))
    run = phases.run_phases(batches, lambda ph: (False, "boom") if ph.index == 1 else (True, ""))
    assert not run.ok
    assert not run.results[1].ok and "skipped" in run.results[1].detail


def test_handoff_context_reloads_the_full_set_and_is_deterministic():
    """PHASE-FR-010: the per-phase handoff names the reload set (spec, rules, tasks, scope) and is
    a pure function of its inputs (PHASE-NFR-001)."""
    ph = phases.parse_phases(_TASKS_3PHASE)[1]
    a = phases.handoff_context(ph, 3, constitution_text="RULES HERE")
    b = phases.handoff_context(ph, 3, constitution_text="RULES HERE")
    assert a == b
    assert "PHASE 2/3" in a and "fresh" in a
    assert "PHASE TASKS:" in a and "T002" in a
    assert "CONSTITUTION / RULES:" in a and "RULES HERE" in a


# --------------------------------------------------------------------------- end-to-end native run (PHASE-SC-001/004)
def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "init"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)


@pytest.fixture()
def phased_project(tmp_path, monkeypatch):
    """A native-executive project whose fake agent produces workspace artifacts and a 3-phase tasks
    file, so a full `3pwr run` exercises the phased implement dispatch offline (no model call)."""
    import yaml

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

    prompts_seen: list[str] = []
    seen_lock = threading.Lock()

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        with seen_lock:
            prompts_seen.append(prompt)
        m = re.search(r"FEATURE FOLDER: (\S+)", prompt)
        d = cwd / (m.group(1) if m else "specs-src/RUN")
        if "# Specify agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text("# Spec\n**Spec ID**: RUN\n", encoding="utf-8")
        elif "# Plan agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "implementation-plan.md").write_text(_TASKS_3PHASE, encoding="utf-8")
        elif "# Oracle agent" in prompt:
            t = cwd / "tests" / "oracle" / "RUN"
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_o.py").write_text("def test_o():\n    assert True\n", encoding="utf-8")
        elif "# Implement agent" in prompt:
            pm = re.search(r"PHASE (\d)/3", prompt)
            name = f"impl_phase{pm.group(1)}" if pm else "impl"
            src = cwd / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / f"{name}.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "ok", "")

    monkeypatch.setattr(runner, "dispatch_agent", fake)
    return root, prompts_seen


def test_native_run_phased_implement_end_to_end(phased_project, monkeypatch, capsys):
    """PHASE-SC-001/002/004 + PHASE-FR-003/005/010/011 + PHASE-NFR-003: a full native run leaves one
    committed artifact per action stage in the workspace, dispatches implement once per phase (fresh
    sessions, parallel batch included), records phase results deterministically, and the ledger verifies."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    root, prompts_seen = phased_project
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )

    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    rc = main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "c",
        ]
    )
    assert rc == 3  # paused at the signoff gate — every executive stage dispatched

    # SRCX-SC-001: the run auto-allocated its feature folder and every artifact lies FLAT in it
    fdir = root / "specs-src" / "001-add-x"
    assert (fdir / "spec.md").is_file()
    assert (fdir / "plan.md").is_file()
    assert (fdir / "implementation-plan.md").is_file()
    assert not (fdir / "spec").exists() and not (fdir / "artifacts").exists()
    log = subprocess.run(
        ["git", "log", "--pretty=%s"], cwd=str(root), capture_output=True, text=True
    ).stdout
    for step in ("specify", "plan", "tasks", "oracle", "implement"):
        assert f"3pwr(RUN): {step}" in log  # committed to git (PHASE-SC-001)

    # PHASE-FR-010/011: implement ran once per phase — three fresh sessions, each with its handoff
    impl = [p for p in prompts_seen if "# Implement agent" in p]
    assert len(impl) == 3
    for i in (1, 2, 3):
        assert any(f"PHASE {i}/3" in p for p in impl)
    for p in impl:  # PHASE-FR-005: each phase prompt reloads the approved spec + its file scope
        assert "APPROVED SPEC:" in p and "**Spec ID**: RUN" in p
        assert "FILE SCOPE:" in p
    # each phase's scope is its own (no carried conversation, disjoint scopes stay disjoint)
    p2 = next(p for p in impl if "PHASE 2/3" in p)
    assert "src/alpha.py" in p2 and "src/beta.py" not in p2.split("FILE SCOPE:")[1]

    # PHASE-FR-005: post-approval stages carry the prior stage's accepted artifact reference
    tasks_prompt = next(p for p in prompts_seen if "# Implementation-plan agent" in p)
    assert "prior stage 'plan' accepted artifact: specs-src/001-add-x/plan.md" in tasks_prompt

    # PHASE-FR-003: the checkpoint ledger entries name the accepted artifact paths
    s = Settings(root=root)
    entries = Ledger(s.ledger_path).entries()
    cp = {
        e["payload"]["step"]: e["payload"]
        for e in entries
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "checkpoint"
    }
    assert "specs-src/001-add-x/plan.md" in cp["plan"]["artifacts"]
    assert "specs-src/001-add-x/implementation-plan.md" in cp["tasks"]["artifacts"]
    assert "specs-src/001-add-x/spec.md" in cp["specify"]["artifacts"]

    # PHASE-FR-012/NFR-003: the phases entry records results in artifact order; the ledger verifies
    ph_entries = [
        e
        for e in entries
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "phases"
    ]
    assert len(ph_entries) == 1
    recorded = ph_entries[0]["payload"]["results"]
    assert [r["phase"] for r in recorded] == [1, 2, 3] and all(r["ok"] for r in recorded)
    vres = verify_ledger(s.ledger_path, s.pubkey_path)
    assert vres.ok, getattr(vres, "problems", vres)


def test_phase_stall_warning_is_advisory_and_never_alters_control_flow(
    phased_project, monkeypatch, capsys
):
    """PHASEPR-FR-005 / PHASEPR-NFR-002: a phase session whose transcript tail ends on a clarifying
    question emits the advisory warning with the run's real spec id — and the run proceeds exactly
    as without it: same pauses, same exit codes, same phase results in the ledger."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    root, prompts_seen = phased_project
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )
    orig = runner.dispatch_agent  # the fixture's fake

    def stalled(argv, **kw):
        rc = orig(argv, **kw)
        prompt = argv[-1] if argv else ""
        tee = kw.get("tee")
        if tee is not None and "PHASE 2/3" in prompt:
            tee.write("I implemented the handler.\nCould you clarify the button label?")
        return rc

    monkeypatch.setattr(runner, "dispatch_agent", stalled)
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    rc = main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "c",
        ]
    )
    assert rc == 3  # identical to the no-warning run: paused at sign-off, never failed
    err = capsys.readouterr().err
    assert "phase 2 ended with a possible unanswered question — review the transcript" in err
    assert "3pwr run --status --spec-id RUN" in err  # the hint carries the real spec id

    # control flow unchanged: all three phases recorded ok in the signed ledger (PHASEPR-NFR-002)
    s = Settings(root=root)
    entries = Ledger(s.ledger_path).entries()
    recorded = next(
        e["payload"]["results"]
        for e in entries
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "phases"
    )
    assert [r["phase"] for r in recorded] == [1, 2, 3] and all(r["ok"] for r in recorded)


def test_phaseless_tasks_artifact_runs_single_implement_dispatch(phased_project, monkeypatch):
    """PHASE-FR-010: a tasks artifact declaring no phases runs implement as ONE fresh session."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    root, prompts_seen = phased_project
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )
    # swap the fake's tasks content for a phaseless list by pre-creating the artifact the fake keeps
    orig = runner.dispatch_agent

    def fake(argv, **kw):
        rc = orig(argv, **kw)
        prompt = argv[-1] if argv else ""
        if "# Implementation-plan agent" in prompt:
            m = re.search(r"FEATURE FOLDER: (\S+)", prompt)
            d = Path(kw["cwd"]) / (m.group(1) if m else "specs-src/RUN")
            (d / "implementation-plan.md").write_text(
                "# Tasks\n- [ ] T001 [RUN-FR-001] everything\n", encoding="utf-8"
            )
        return rc

    monkeypatch.setattr(runner, "dispatch_agent", fake)
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    assert (
        main(
            [
                "--root",
                str(root),
                "run",
                "--resume",
                "--no-input",
                "--spec-id",
                "RUN",
                "--approver",
                "c",
            ]
        )
        == 3
    )
    impl = [p for p in prompts_seen if "# Implement agent" in p]
    assert len(impl) == 1 and "PHASE" not in impl[0].split("# Implement agent")[1].split("\n")[0]


def test_oversize_phase_warns_but_run_and_gates_proceed(phased_project, monkeypatch, capsys):
    """PHASE-FR-009 / PHASE-NFR-002: an over-budget phase yields the advisory warning and the run
    continues; the gate verdict is identical with and without the warning — the budget is never a gate."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    root, prompts_seen = phased_project
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )
    # a tiny budget makes every phase oversize (PHASE-FR-007: config changes the threshold)
    (root / ".3powers" / "config" / "context.yaml").write_text(
        "budget_tokens: 10\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "cfg"], cwd=root, check=True, capture_output=True)
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    rc = main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "c",
        ]
    )
    err = capsys.readouterr().err
    assert rc == 3  # the run reached the signoff gate — warned, never blocked
    assert "exceeds the context budget (10)" in err and "phase 1" in err
    assert "estimated ~" in err  # the estimate is reported per phase (PHASE-FR-008)


def test_phased_run_records_per_phase_tokens_additively(phased_project, monkeypatch):
    """Plan 033 Track H (RUNVIS): when the coder backend reports usage, a phased implement records
    each phase's token count as an ADDITIVE field on the run/phases ledger payload, sums them onto
    the stage entry, and ledger verification stays green over the new payloads."""
    import yaml

    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    root, prompts_seen = phased_project
    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )
    (root / ".3powers" / "agents" / "claude.yaml").write_text(
        yaml.safe_dump(
            {
                "command": "claude",
                "family": "anthropic",
                "headless": True,
                "prompt_flag": "-p",
                "usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9,]+)"},
            }
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "usage"], cwd=root, check=True, capture_output=True)
    orig = runner.dispatch_agent

    def with_usage(argv, **kw):
        rc, out, err = orig(argv, **kw)
        return rc, out + "\ntokens used: 100", err

    monkeypatch.setattr(runner, "dispatch_agent", with_usage)
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    rc = main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "c",
        ]
    )
    assert rc == 3  # paused at sign-off — the phased implement ran to completion
    s = Settings(root=root)
    entries = Ledger(s.ledger_path).entries()
    recorded = next(
        e["payload"]["results"]
        for e in entries
        if e.get("type") == "run" and e.get("payload", {}).get("kind") == "phases"
    )
    # every prior key survives (additive-only, PAT-002) and each phase carries its count
    assert all({"phase", "name", "ok", "detail"} <= set(r) for r in recorded)
    assert [r.get("tokens") for r in recorded] == [100, 100, 100]
    implement_stage = next(
        e["payload"]
        for e in entries
        if e.get("type") == "run"
        and e.get("payload", {}).get("kind") == "stage"
        and e["payload"].get("step") == "implement"
    )
    assert implement_stage.get("tokens") == 300  # the stage total sums the phases
    vres = verify_ledger(s.ledger_path, s.pubkey_path)
    assert vres.ok, getattr(vres, "problems", vres)


# --------------------------------------------------------------------------- docs (PHASE-NFR-004)
def test_docs_describe_workspace_budget_and_phased_dispatch():
    """PHASE-NFR-004: the forward-looking docs (CLAUDE.md, AGENTS.md, docs/STATUS.md) describe the
    workspace layout, the context budget, and phased dispatch, and 3PWR-FR-060/061 are updated."""
    claude = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "spec/spec.md" in claude and "context.yaml" in claude
    assert "fresh headless session per phase" in claude
    agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "specs/<feature>/artifacts/" in agents_md and "context budget" in agents_md
    assert "[P]" in agents_md
    status = (REPO_ROOT / "docs" / "STATUS.md").read_text(encoding="utf-8")
    assert "FR-060 ✅ / FR-061 ✅" in status  # the previously-open context strategy is delivered
    assert "context strategy approximated" not in status
    assert "023-phased-execution" in status


# --------------------------------------------------------------------------- lifecycle wiring sanity
def test_phases_module_never_touches_the_ledger():
    """PHASE-NFR-003: the phases module holds no ledger/signing import — results are appended by the
    orchestrator after collection, from one thread."""
    src = (REPO_ROOT / "engine" / "src" / "threepowers" / "phases.py").read_text(encoding="utf-8")
    assert "ledger" not in src.lower().replace("the ledger is never touched here", "")
    assert "import" not in [ln.strip() for ln in src.splitlines() if "keys" in ln]


def test_lifecycle_steps_unchanged_by_phase_dispatch():
    """PHASE-SC-005: the lifecycle stages, gates, and verdict steps are untouched by phased dispatch."""
    assert [sid for sid, kind, _ in orchestrate.LIFECYCLE_STEPS if kind == "gate"] == [
        "review-spec",
        "review-plan",
        "review-verify",
        "signoff",
    ]
    assert ("implement", "action", "Build") in orchestrate.LIFECYCLE_STEPS
