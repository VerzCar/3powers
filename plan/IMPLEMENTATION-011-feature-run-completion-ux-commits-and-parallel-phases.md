---
goal: Run-completion UX, per-phase commit granularity, dependency-aware parallel phase scheduling, and in-process advance with remediation dispatch
version: 1.0
date_created: 2026-07-23
last_updated: 2026-07-23
owner: 3Powers maintainers
status: 'Planned'
tags: [feature, engine, cli, gitflow, scheduling, ux, docs]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan is derived from the finalized source plan
`plan/040-run-completion-ux-commit-granularity-and-parallel-phases.md` (branch
`feat/040-run-ux-commits-scheduling`). It delivers the plan's six work streams: (A) a
run-completion experience that renders Ship as the final completed step with a
changelog-derived business summary and an Observe call-to-action, (B) one commit per
implement phase plus deterministic engine-state commits so a finished run leaves a clean
working tree, (C) dependency-aware `[P]` batch scheduling with visible, named
serialization reasons, (D) an in-process `advance` enforcement core with a dedicated
`advance.agent.md` remediation template dispatched only on refusal, (E) documentation
updates in the same unit of work, and (F) the verification constraints (gates green,
additive byte contracts, trust-spine coverage, e2e, live-run smoke).

Phase ordering rationale: the shared hotspots `engine/src/threepowers/cli/run.py`,
`engine/src/threepowers/gitflow.py`, `engine/src/threepowers/phases.py`, and
`engine/src/threepowers/progress.py` force a mostly sequential plan. Phase 1 lands the
most isolated change (the pure scheduler core in `phases.py`). Phase 2 lands the commit
granularity machinery that later phases rely on. Phase 3 factors `advance` and adds the
remediation template. Phase 4 lands the completion UX, which depends on Phase 2 for the
truthful "everything committed" claim in the CTA. Phase 5 is docs, and Phase 6 is the
dedicated Verification phase.

**Execution note:** ALL Python changes under `engine/src/threepowers/` and
`engine/tests/` are performed by the **python-engineer agent**
(`.github/agents/python-engineer.agent.md`) at implementation time, taking this plan's
phases as input. Docs edits (`docs/`, `AGENTS.md`, `CLAUDE.md`) are ordinary changes in
the same unit of work.

## 1. Requirements & Constraints

Requirements (traceable to the source plan's requirement table, internal IDs
3PWR-FR-U01…U18):

- **REQ-001** (U01): The tracker end state renders Ship as the final completed step ("ready to push"); Observe is no longer a pending `▶` row but a follow-on pointer/CTA, with a glyph consistent with the tracker vocabulary.
- **REQ-002** (U02): The completion block prints an explicit "All stages are done." statement plus a short business summary rendered from the run's existing `changelog.md` record (highlight bullets capped at 5); NO extra agent dispatch, NO new artifact; graceful fallback to the current one-liner when `changelog.md` is absent or unparseable.
- **REQ-003** (U03): An Observe CTA block states the current state (run branch, Ship reached, everything committed) and next actions — `3pwr observe coverage --spec <spec>`, registering checks in `.3powers/config/observability.yaml`, pushing/merging the run branch — and that production lessons return as a NEW `3pwr run "<intent>"`, never ad-hoc patches.
- **REQ-004** (U04): The `progress.md` final state line and the notification message use the same "complete — ready to push" wording as the tracker.
- **REQ-005** (U05): One commit PER implement phase, in deterministic phase order, issued sequentially from the collecting thread after each batch completes (never from worker threads). Message: phase-aware variant of `stage_commit_message`, e.g. `implement(phase 2/5): <description>`, description taken from the phase's `COMMIT:` transcript line.
- **REQ-006** (U06): Phase commits carry ONLY the phase's produced paths; the ledger "phases" entry plus `progress.md` land in one trailing implement record commit after all phases complete.
- **REQ-007** (U07): New helper `gitflow.commit_engine_state` commits only `ENGINE_STATE_PREFIX` paths (ledger) plus the run's `progress.md`, with deterministic messages; invoked after the verify verdict (including auto-fix verdict entries), review-verify, signoff, advance, and the final complete append.
- **REQ-008** (U08): `commit_engine_state` is ALSO invoked before every human-gate pause; a finished run leaves a CLEAN working tree.
- **REQ-009** (U09): Commit-or-fail (`CLASS_COMMIT_FAILED`) extends to phase and engine-state commits; `--commit-relaxed` and deviation escape hatches keep their existing meaning.
- **REQ-010** (U10): Batching rule: a `[P]` phase joins a concurrent batch when all its declared `depends_on` phases are already completed (in a prior batch), it has a file scope, and its scope is disjoint from every other batch member.
- **REQ-011** (U11): The scheduler stays pure, deterministic, stably ordered by phase number, and ledger-free (`phases.py` never touches the ledger; guard test `test_phases_module_never_touches_the_ledger` stays green).
- **REQ-012** (U12): Pre-batch log lines (CLI renders scheduler-returned decision metadata): batch number; phases running now, parallel vs serial; a named reason for every serialized `[P]` phase ("depends on Phase 3 (not yet complete)", "file scope overlaps Phase 2", "no file scope declared"); executing agent/model per phase including `roles.yaml` `subagent_models` when set.
- **REQ-013** (U13): The `progress.md` phase table gains additive parallel/serial + batch index markers.
- **REQ-014** (U14): `cmd_advance`'s enforcement core is factored into a callable (e.g. `advance_check(...) -> AdvanceResult` with structured refusal reasons); `cmd_advance` and the run orchestrator both call it; CLI behavior unchanged. Default path: the run's advance step executes in-process, no dispatch; on success it records/advances as today plus an engine-state commit.
- **REQ-015** (U15): Refusal path only: dispatch a headless agent with the NEW dedicated template `advance.agent.md` (bundled scaffold twin + repo-local override; frontmatter/role/closed-variable conventions). The template carries the named refusal reasons and instructs: fix named blockers honestly, commit run-produced work on the run branch, re-run `3pwr advance`, never weaken gates, never self-file deviations.
- **REQ-016** (U16): A new template variable (`$REFUSAL_REASONS`) is added to the closed variable set `_VARS` in `prompts.py`, with tests; template-count and oss-readiness tests are updated for the new template.
- **REQ-017** (U17): Docs updated everywhere in the same unit of work (`docs/concepts.md`, `docs/getting-started.md`, `docs/cli-reference.md`, sweep of `docs/engine-architecture.md` + `docs/troubleshooting.md`, `AGENTS.md`/`CLAUDE.md` summaries); OSS-readiness holds: no internal requirement IDs (3PWR-FR-U##) in any user-facing text; teaching uses `DEMO-FR-###`; `engine/tests/test_oss_readiness.py` stays green.
- **REQ-018** (U18): Engine gates green at every phase end; byte-golden tests and verdict-bytes guards changed additively only; trust-spine coverage ≥ 95%; `./e2e/run.sh typescript --check` green.

Constraints:

- **CON-001**: All git commits are issued from the collecting thread only — never from `ThreadPoolExecutor` workers (git index lock contention).
- **CON-002**: `engine/src/threepowers/phases.py` must remain pure and ledger-free.
- **CON-003**: Byte-golden fixtures (`engine/tests/golden/`) and verdict-byte guards may only change additively; no existing byte contract is rewritten.
- **CON-004**: The `[tool.mutmut]` scope in `engine/pyproject.toml` is not widened or narrowed; trust-spine module coverage stays ≥ 95%.
- **CON-005**: No check is weakened: no inline lint-disables, type suppressions, deleted assertions, or loosened gate/tool config.
- **CON-006**: Backward compatibility: phaseless implementation artifacts, legacy runs, and runs with a missing `changelog.md` keep working (fallbacks, never crashes).
- **CON-007**: Every Python change lands with tests mirroring the source layout in the same phase; a behavior change without a matching test is incomplete.
- **CON-008**: No internal plan/spec/requirement IDs in user-facing text (CLI output, template prose, docs prose, scaffold assets).

Risks (mirrored from the source plan):

- **RISK-001**: Git index contention from concurrent phase workers — mitigated by collecting-thread-only commits (CON-001).
- **RISK-002**: Golden/verdict-byte breakage — mitigated by additive-only changes (CON-003) and running the golden suite in every phase's completion check.
- **RISK-003**: Backward-compatibility breaks for phaseless artifacts, legacy runs, or missing `changelog.md` — mitigated by explicit fallback paths and regression tests.
- **RISK-004**: `--commit-relaxed`/deviation interplay changing semantics — mitigated by dedicated tests asserting the escape hatches keep their meaning.
- **RISK-005**: Wrong parallelism after the scheduling fix (overlapping scopes running concurrently) — mitigated by the mandatory disjoint-scope check and scheduler tests.
- **RISK-006**: The advance-core refactor regressing the CLI — mitigated by a pure extraction with the existing `cmd_advance` test suite as the net.
- **RISK-007**: Template-set test assumptions (template counts, oss-readiness scans) breaking on the new template — mitigated by updating those tests in the same phase that adds the template.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Land the dependency-aware, pure scheduler core in `phases.py` with decision metadata, plus its tests (work stream C core; REQ-010, REQ-011, partial REQ-012).

**Parallel execution: NO** — first phase; everything downstream builds on the scheduler's new return shape.
**File scope:** `engine/src/threepowers/phases.py`, `engine/tests/test_phases.py`.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                          | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/phases.py`, replace `_parallel_eligible` (L249–253, currently requiring `parallel AND no depends_on AND file_scope` — the defect that silently serializes `[P]` phases with `Depends on: Phase 1`) with dependency-satisfied eligibility: a `[P]` phase joins a concurrent batch when all its declared `depends_on` phases completed in a prior batch, it declares a file scope, and its scope is disjoint from every other batch member. |           |      |
| TASK-002 | Extend `schedule` (`phases.py` L256+) to return per-batch decision metadata alongside the batches: batch index, per-phase parallel/serial flag, and a machine-usable named serialization reason for every serialized `[P]` phase — exactly one of "depends on Phase N (not yet complete)", "file scope overlaps Phase N", "no file scope declared". Keep ordering stable by phase number, the function pure and deterministic, and the module ledger-free (guard test `test_phases_module_never_touches_the_ledger` must stay green unmodified). |           |      |
| TASK-003 | Keep `run_phases` (ThreadPoolExecutor) and the `[P]`/`**Depends on**`/`**File scope**`/`**Parallel**` header parsing behavior-compatible for phaseless and legacy artifacts; add explicit fallback coverage for artifacts without `[P]` markers or scopes.                                                                                                                |           |      |
| TASK-004 | In `engine/tests/test_phases.py`, add tests: (a) a `[P]` phase whose `depends_on` completed in a prior batch parallelizes with its siblings; (b) overlapping file scopes serialize with the "file scope overlaps Phase N" reason; (c) missing file scope serializes with "no file scope declared"; (d) unmet dependency serializes with "depends on Phase N (not yet complete)"; (e) batch ordering is deterministic and stable by phase number across repeated calls; (f) phaseless artifacts still schedule as a single serial sequence.        |           |      |

**Completion criteria:** `cd engine && uv run ruff check . && uv run mypy src && uv run pytest tests/test_phases.py` green; full `uv run pytest` green; guard test unchanged and passing.

### Phase 2

- GOAL-002: Deliver commit granularity — one commit per implement phase from the collecting thread, the trailing implement record commit, `gitflow.commit_engine_state`, engine-state commits at all judgment steps and before human-gate pauses, and commit-or-fail semantics (work stream B; REQ-005…REQ-009).

**Parallel execution: NO** — depends on Phase 1 (batch/collection structure in `_dispatch_phased`) and touches the hotspots `gitflow.py` and `cli/run.py` that Phases 3–4 also touch.
**File scope:** `engine/src/threepowers/gitflow.py`, `engine/src/threepowers/cli/run.py`, `engine/tests/test_gitflow.py`, run-CLI test files under `engine/tests/`.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                                                                                              | Completed | Date |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-005 | In `engine/src/threepowers/gitflow.py`, add a phase-aware variant of `stage_commit_message` (L394) producing messages of the form `implement(phase 2/5): <description>`, where `<description>` comes from the phase's `COMMIT:` transcript line (fallback to the phase description when absent). Deterministic output for identical inputs.                                                                                                       |           |      |
| TASK-006 | In `engine/src/threepowers/gitflow.py`, add `commit_engine_state(...)`: commits ONLY `ENGINE_STATE_PREFIX` paths (L62, the ledger) plus the run's `progress.md` (matching the existing `_PROGRESS_FILE` regex), with deterministic messages; it is a no-op returning success when there is nothing to commit; failures classify as `CLASS_COMMIT_FAILED`. Public docstring stating the contract.                                                  |           |      |
| TASK-007 | In `engine/src/threepowers/cli/run.py` `_dispatch_phased` (L826–955), after each batch's futures are collected, issue one commit per completed phase in deterministic phase order from the collecting thread only (never from workers), each carrying ONLY that phase's produced paths and using the TASK-005 message. After ALL phases: append the ledger "phases" entry as today, then issue one trailing implement record commit carrying the ledger entry + `progress.md` (REQ-006). Adjust the post-stage commit hook (~L1281–1330) so the implement stage does not double-commit paths already committed per phase. |           |      |
| TASK-008 | In `engine/src/threepowers/cli/run.py`, invoke `gitflow.commit_engine_state` after: the verify verdict in `run_verdict` (~L1420–1470, including auto-fix verdict entries), review-verify, signoff, advance, and the final complete append (~L2787–2793); ALSO before every human-gate pause (spec approval, sign-off). A finished run must leave a clean working tree.                                                                                                                       |           |      |
| TASK-009 | Extend commit-or-fail: phase commits and engine-state commits fail their step with `CLASS_COMMIT_FAILED` on error; `--commit-relaxed` and deviation escape hatches keep their existing meaning for the new commit sites. Add tests asserting both the fail path and the relaxed path.                                                                                                                                                              |           |      |
| TASK-010 | Tests in `engine/tests/test_gitflow.py` and the run-CLI test files: per-phase commit messages and ordering; phase commits contain only the phase's produced paths; the trailing implement record commit contains exactly the ledger entry + `progress.md`; `commit_engine_state` path filtering, no-op behavior, and determinism; clean-tree assertion after a completed run; commits never issued from worker threads (assert call-site/threading discipline).                                    |           |      |

**Completion criteria:** engine gates green (`ruff`, `mypy src`, full `pytest`); `recorded_run_paths`/`uncommitted_run_paths` (gitflow.py L320–341) behavior consistent with the new commit sites; golden suite untouched or additively extended only.

### Phase 3

- GOAL-003: Factor the `advance` enforcement core, run it in-process from the orchestrator, and add the refusal-only remediation dispatch with the new `advance.agent.md` template (work stream D; REQ-014…REQ-016).

**Parallel execution: NO** — depends on Phase 2 (`commit_engine_state` invoked on successful advance) and touches `cli/run.py` again.
**File scope:** `engine/src/threepowers/cli/trust.py`, `engine/src/threepowers/cli/run.py`, `engine/src/threepowers/prompts.py`, `engine/src/threepowers/scaffold/templates/agents/advance.agent.md` (new), `engine/tests/test_trust*.py`, `engine/tests/test_prompts.py`, `engine/tests/test_oss_readiness.py`, template-count tests.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                                                                    | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-011 | In `engine/src/threepowers/cli/trust.py`, factor `cmd_advance`'s enforcement core (L285–460) into a callable `advance_check(...) -> AdvanceResult` carrying structured refusal reasons for the six checks (ledger verifies; latest enforced verdict green or red gates covered by signed deviations; sign-off at/after verdict; oracle independence at High-risk; spec integrity; git discipline: on run branch + run-produced work committed). Pure extraction: `cmd_advance` calls it and its CLI behavior, exit codes, and messages are byte-for-byte unchanged. |           |      |
| TASK-012 | In `engine/src/threepowers/cli/run.py`, make the run's advance step (`LIFECYCLE_STEPS` entry `("advance","action","Ship")` in `orchestrate.py` L40–54 stays as-is) execute `advance_check` in-process by default — no agent dispatch; on success, record/advance exactly as today plus `gitflow.commit_engine_state` (from Phase 2).                                                                                                                                       |           |      |
| TASK-013 | Refusal path only: dispatch a headless agent using the NEW template `advance.agent.md` — bundled at `engine/src/threepowers/scaffold/templates/agents/advance.agent.md` with the repo-local override point `.3powers/templates/agents/advance.agent.md` via the existing 3-tier resolution in `prompts.py`. Template follows the frontmatter/role/closed-variable conventions; its prose carries the named refusal reasons via `$REFUSAL_REASONS` and instructs: fix named blockers honestly, commit run-produced work on the run branch, re-run `3pwr advance`, never weaken gates, never self-file deviations. No internal requirement IDs in the template prose (CON-008). |           |      |
| TASK-014 | In `engine/src/threepowers/prompts.py`, add `REFUSAL_REASONS` to the closed variable set `_VARS` (joining STEP/GATE/ARTIFACT/FEATURE_FOLDER/ORACLE_DESTINATION/FEEDBACK); `substitute()` continues to operate over template bodies only. Add tests for the new variable's substitution and for rejection of unknown variables remaining closed.                                                                                                                              |           |      |
| TASK-015 | Update template-count and oss-readiness tests for the new template (`engine/tests/test_oss_readiness.py` and whichever test asserts the bundled template set); add tests: in-process advance succeeds without dispatch; refusal triggers exactly one remediation dispatch with the structured reasons rendered; `cmd_advance` CLI regression suite unchanged and green.                                                                                                        |           |      |

**Completion criteria:** engine gates green; `cmd_advance` existing tests pass unmodified (RISK-006 net); the new template resolves through all three tiers; oss-readiness test green.

### Phase 4

- GOAL-004: Deliver the run-completion UX — tracker end state, "All stages are done." + changelog-derived summary, Observe CTA block, aligned `progress.md`/notification wording — and the visible-parallelism surfaces deferred from Phase 1 (work stream A + REQ-012/REQ-013 rendering; REQ-001…REQ-004).

**Parallel execution: NO** — depends on Phase 2 (the CTA's "everything committed" claim must be true) and Phase 1 (scheduler decision metadata to render); touches `cli/run.py` and `progress.py`.
**File scope:** `engine/src/threepowers/cli/run.py`, `engine/src/threepowers/progress.py`, `engine/src/threepowers/notify.py`, `engine/src/threepowers/completion.py`, `engine/tests/test_progress.py`, `engine/tests/test_notify.py`, `engine/tests/test_completion.py`, run-CLI test files.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-016 | Tracker end state: in the completion block of `engine/src/threepowers/cli/run.py` (~L2787–2793, currently appending `{"kind":"complete","stage":"Ship"}` then printing `render_tracker('Observe')`), render Ship as the final COMPLETED step ("ready to push") and Observe as a follow-on pointer/CTA line instead of a pending `▶` row, using a glyph consistent with the tracker vocabulary.        |           |      |
| TASK-017 | Completion summary: after the tracker, print an explicit "All stages are done." statement plus a short business summary rendered from the run's `changelog.md` via `completion.py` `render_changelog`/`RECORD_STEPS` (the implement stage's agent-authored Keep-a-Changelog record in the feature folder), capping highlight bullets at 5. NO extra agent dispatch, NO new artifact. Graceful fallback to the current one-liner when `changelog.md` is absent or unparseable (CON-006). |           |      |
| TASK-018 | Observe CTA block: print current state (run branch name, Ship reached, everything committed — guaranteed by Phase 2) and next actions: `3pwr observe coverage --spec <spec>`, register checks in `.3powers/config/observability.yaml`, push/merge the run branch; state that production lessons return as a NEW `3pwr run "<intent>"`, never ad-hoc patches. No internal requirement IDs in output (CON-008). |           |      |
| TASK-019 | Wording alignment: update the `progress.md` final state line (`engine/src/threepowers/progress.py` L350, currently "✓ lifecycle complete — advanced to Ship; observe feeds new intent") and `notify.py` L306 `completion_message` to the same "complete — ready to push" wording as the tracker.                                                                                                            |           |      |
| TASK-020 | Visible parallelism: in `_dispatch_phased` (`cli/run.py`), before each batch, render the Phase 1 scheduler decision metadata as pre-batch log lines — batch number; phases running now, parallel vs serial; the named reason for every serialized `[P]` phase; executing agent/model per phase including `roles.yaml` `subagent_models` when set (REQ-012). Add the additive parallel/serial + batch index markers to the `progress.md` phase table (REQ-013).                                  |           |      |
| TASK-021 | Tests in `engine/tests/test_progress.py`, `test_notify.py`, `test_completion.py`, and the run-CLI test files: new final-state line; notification wording; changelog summary rendering with the 5-bullet cap; fallback on missing/unparseable `changelog.md`; CTA block content; pre-batch log lines with each named serialization reason; additive `progress.md` phase-table markers (existing tables still parse).                                                                                    |           |      |

**Completion criteria:** engine gates green; all completion-path tests pass; legacy runs without `changelog.md` produce the fallback line, never an error.

### Phase 5

- GOAL-005: Documentation for every behavior change, in the same unit of work, OSS-ready (work stream E; REQ-017).

**Parallel execution: NO** — must describe the behavior as actually landed in Phases 1–4; no code files shared, but content depends on all prior phases.
**File scope:** `docs/concepts.md`, `docs/getting-started.md`, `docs/cli-reference.md`, `docs/engine-architecture.md`, `docs/troubleshooting.md`, `AGENTS.md`, `CLAUDE.md`.

| Task     | Description                                                                                                                                                                                                                                                                                                                     | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-022 | `docs/concepts.md`: Observe's purpose, the ready-to-push end state, next-intent guidance (lessons return as a new run), and commit granularity's place in the trust story (per-phase commits + engine-state commits + clean tree).                                                                                                       |           |      |
| TASK-023 | `docs/getting-started.md`: walkthrough of the new completion output; what to do after a run; guidance for a next intent related to an existing spec — new run/new spec vs revising via `--redo`/`revert`/`revise` and when each applies.                                                                                                  |           |      |
| TASK-024 | `docs/cli-reference.md`: run output changes (tracker end state, completion summary, CTA, pre-batch parallelism lines), commit granularity semantics (per-phase, trailing record commit, engine-state commits, `--commit-relaxed` interplay), in-process advance + refusal-only remediation dispatch, and the `advance.agent.md` repo-local override point. |           |      |
| TASK-025 | Sweep `docs/engine-architecture.md` and `docs/troubleshooting.md` for statements made stale by this work (single implement commit, pending Observe row, dispatched advance, always-serialized dependent `[P]` phases); update `AGENTS.md`/`CLAUDE.md` summaries where they describe the affected behavior.                                 |           |      |
| TASK-026 | OSS-readiness pass over all touched user-facing text (docs prose, CLI output added in Phases 1–4, template prose, scaffold assets): no internal requirement IDs (3PWR-FR-U##), epic letters, or plan/spec numbers; requirement-ID teaching uses `DEMO-FR-###` or bare `FR-###`; `cd engine && uv run pytest tests/test_oss_readiness.py` green.       |           |      |

**Completion criteria:** every behavior change from Phases 1–4 is described in `docs/`; `test_oss_readiness.py` green; no stale statements remain in the swept files.

### Phase 6

- GOAL-006: Dedicated Verification phase — full gates, golden/byte contracts, coverage floors, e2e check, and a live-run smoke exercising every new behavior end to end (work stream F; REQ-018).

**Parallel execution: NO** — final phase, verifies the union of all prior phases.
**File scope:** verification only; no production code changes except fixes for defects found (each fix ships with a regression test).

| Task     | Description                                                                                                                                                                                                                                                                                                | Completed | Date |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-027 | Full engine gates: `cd engine && uv run ruff check . && uv run mypy src && uv run pytest`. Confirm trust-spine module coverage (`canonical`, `keys`, `ledger`, `verify`, `speclock`, `anchor`) ≥ 95% and the `[tool.mutmut]` scope in `engine/pyproject.toml` untouched.                                          |           |      |
| TASK-028 | Byte contracts: run the byte-golden suite (`engine/tests/golden/`) and verdict-bytes guards; confirm every change is additive only (CON-003). Any non-additive diff is a defect to fix, not a fixture to regenerate.                                                                                             |           |      |
| TASK-029 | Reinstall the CLI (`uv tool install --force ./engine`) and run the deterministic e2e check: `./e2e/run.sh typescript --check` — must pass green.                                                                                                                                                                  |           |      |
| TASK-030 | Live-run smoke against an e2e sandbox (throwaway, never writes into this repo): verify per-phase commits with `implement(phase N/M): …` messages in deterministic order; the trailing implement record commit; clean working tree at every human-gate pause and at run end; pre-batch parallelism log lines with named serialization reasons and agent/model identities; in-process advance (no dispatch on the green path); and the new completion block (Ship completed "ready to push", "All stages are done.", changelog summary ≤ 5 bullets, Observe CTA). |           |      |
| TASK-031 | Record any defects found, fix them with regression tests in the same unit of work, re-run TASK-027…TASK-030 until all pass; then flip this plan's task tables and status.                                                                                                                                          |           |      |

**Completion criteria:** all of TASK-027…TASK-030 pass in a single consecutive pass; branch `feat/040-run-ux-commits-scheduling` is green and committed; no pull request is opened.

## 3. Alternatives

- **ALT-001**: Commit engine state (ledger + `progress.md`) inside each per-phase commit instead of a trailing record commit — rejected by the source plan's resolved decision: phase commits carry only produced paths, keeping phase diffs reviewable and the ledger append atomic per stage.
- **ALT-002**: Dispatch an agent to author the completion business summary — rejected: the summary renders from the existing `changelog.md` record; no extra dispatch, no new artifact, no new cost or nondeterminism.
- **ALT-003**: Always dispatch the advance step to a headless agent (status quo) — rejected: the enforcement core is deterministic; in-process execution is faster and cheaper, and dispatch is reserved for the refusal/remediation path only.
- **ALT-004**: Issue phase commits from worker threads as each phase finishes — rejected: git index lock contention (RISK-001); commits come only from the collecting thread in deterministic phase order.
- **ALT-005**: Reuse an existing agent template for remediation — rejected: refusal remediation has its own contract (fix named blockers, never weaken gates, never self-file deviations) and needs its own override point (`advance.agent.md`).

## 4. Dependencies

- **DEP-001**: Source plan `plan/040-run-completion-ux-commit-granularity-and-parallel-phases.md` (finalized) on branch `feat/040-run-ux-commits-scheduling`.
- **DEP-002**: python-engineer agent (`.github/agents/python-engineer.agent.md`) for all changes under `engine/`.
- **DEP-003**: Engine dev environment: `cd engine && uv sync --extra dev`; CLI reinstall via `uv tool install --force ./engine`.
- **DEP-004**: e2e kit prerequisites for the TypeScript adapter (Node.js + npm) for `./e2e/run.sh typescript --check`; a headless agent CLI for the live-run smoke.
- **DEP-005**: Signer setup for the live-run smoke: `3pwr keygen` + `THREEPOWERS_SIGNING_KEY_FILE` exported (key outside the repo).

## 5. Files

- **FILE-001**: `engine/src/threepowers/phases.py` — `_parallel_eligible` (L249–253) rewrite, `schedule` (L256+) decision metadata; stays pure/ledger-free.
- **FILE-002**: `engine/src/threepowers/gitflow.py` — phase-aware commit message variant (near `stage_commit_message` L394), new `commit_engine_state`, `CLASS_COMMIT_FAILED` coverage; `ENGINE_STATE_PREFIX` (L62) and `recorded_run_paths`/`uncommitted_run_paths` (L320–341) consistency.
- **FILE-003**: `engine/src/threepowers/cli/run.py` — `_dispatch_phased` (L826–955) per-phase commits + pre-batch logs; post-stage commit hook (~L1281–1330); `run_verdict` (~L1420–1470); in-process advance step; completion block (~L2787–2793) tracker/summary/CTA.
- **FILE-004**: `engine/src/threepowers/cli/trust.py` — `cmd_advance` (L285–460) core factored into `advance_check(...) -> AdvanceResult`.
- **FILE-005**: `engine/src/threepowers/prompts.py` — `REFUSAL_REASONS` added to `_VARS`; 3-tier resolution covers the new template.
- **FILE-006**: `engine/src/threepowers/scaffold/templates/agents/advance.agent.md` — NEW bundled remediation template (repo-local override: `.3powers/templates/agents/advance.agent.md`).
- **FILE-007**: `engine/src/threepowers/progress.py` — final state line (L350) rewording; additive phase-table markers.
- **FILE-008**: `engine/src/threepowers/notify.py` — `completion_message` (L306) rewording.
- **FILE-009**: `engine/src/threepowers/completion.py` — `render_changelog`/`RECORD_STEPS` used for the capped summary + fallback.
- **FILE-010**: `engine/tests/test_phases.py`, `engine/tests/test_gitflow.py`, `engine/tests/test_progress.py`, `engine/tests/test_notify.py`, `engine/tests/test_completion.py`, `engine/tests/test_prompts.py`, trust/advance test files, run-CLI test files, `engine/tests/test_oss_readiness.py`, template-count tests.
- **FILE-011**: `docs/concepts.md`, `docs/getting-started.md`, `docs/cli-reference.md`, `docs/engine-architecture.md`, `docs/troubleshooting.md`, `AGENTS.md`, `CLAUDE.md`.

## 6. Testing

- **TEST-001**: Scheduler: dependency-satisfied `[P]` batching, disjoint-scope enforcement, all three named serialization reasons, deterministic/stable ordering, phaseless fallback, ledger-free guard (`test_phases.py`).
- **TEST-002**: Commit granularity: per-phase commit messages/order/contents, trailing implement record commit contents (ledger "phases" entry + `progress.md` only), collecting-thread-only discipline (`test_gitflow.py` + run-CLI tests).
- **TEST-003**: `commit_engine_state`: path filtering to `ENGINE_STATE_PREFIX` + `progress.md`, deterministic messages, no-op success, invocation at verify/review-verify/signoff/advance/complete and before human-gate pauses, clean tree at run end.
- **TEST-004**: Commit-or-fail: `CLASS_COMMIT_FAILED` on phase/engine-state commit failure; `--commit-relaxed` and deviation escape hatches unchanged in meaning.
- **TEST-005**: Advance: `advance_check` structured refusal reasons for all six checks; `cmd_advance` CLI regression suite byte-identical behavior; in-process green path with no dispatch; refusal-only remediation dispatch rendering `$REFUSAL_REASONS`.
- **TEST-006**: Prompts/templates: `REFUSAL_REASONS` in the closed `_VARS` set, substitution over bodies only, 3-tier resolution of `advance.agent.md`, updated template-count assertions.
- **TEST-007**: Completion UX: tracker end state (Ship completed, no pending Observe row), "All stages are done." statement, changelog summary with 5-bullet cap, fallback on missing/unparseable `changelog.md`, CTA block content (`test_completion.py`, run-CLI tests).
- **TEST-008**: Wording: `progress.md` final line and notification message match the "complete — ready to push" wording (`test_progress.py`, `test_notify.py`); additive phase-table markers keep legacy tables parseable.
- **TEST-009**: OSS-readiness: `engine/tests/test_oss_readiness.py` green over the new template and all new user-facing text.
- **TEST-010**: System: byte-golden suite additive-only; trust-spine coverage ≥ 95%; `./e2e/run.sh typescript --check` green; live-run smoke checklist (TASK-030) passes.

## 7. Risks & Assumptions

- **RISK-001**: Git index contention if any commit escapes the collecting thread — enforced by design (CON-001) and tested (TEST-002).
- **RISK-002**: Byte-golden/verdict-byte contract breakage — additive-only rule (CON-003), verified in TASK-028.
- **RISK-003**: Backward-compat regressions for phaseless artifacts, legacy runs, and missing `changelog.md` — explicit fallbacks + regression tests (TASK-003, TASK-017, TASK-021).
- **RISK-004**: `--commit-relaxed`/deviation semantics drift at the new commit sites — pinned by TEST-004.
- **RISK-005**: Over-parallelization after the scheduling fix — mandatory disjoint-scope check + TEST-001.
- **RISK-006**: `advance` refactor regressing the CLI — pure extraction with the existing test suite as the net (TASK-011, TEST-005).
- **RISK-007**: Template-set/oss-readiness test assumptions breaking — updated in the same phase as the template (TASK-015).
- **ASSUMPTION-001**: The verified line anchors from the source plan (orchestrate.py L40–54, run.py L826–955/~L1281–1330/~L1420–1470/~L2787–2793, gitflow.py L62/L320–341/L394/L402+, phases.py L249–253/L256+, trust.py L285–460, progress.py L350, notify.py L306) are accurate as of branch creation; the implementing agent re-verifies before editing.
- **ASSUMPTION-002**: `changelog.md` is authored by the implement stage per `RECORD_STEPS` and, when present, is well-formed Keep-a-Changelog often enough that the capped summary is useful; the fallback covers the rest.
- **ASSUMPTION-003**: A headless agent CLI and a signing key are available for the Phase 6 live-run smoke.

## 8. Related Specifications / Further Reading

- [plan/040-run-completion-ux-commit-granularity-and-parallel-phases.md](plan/040-run-completion-ux-commit-granularity-and-parallel-phases.md) — source plan (authoritative)
- [plan/IMPLEMENTATION-009-feature-fresh-run-isolation-and-base-branch.md](plan/IMPLEMENTATION-009-feature-fresh-run-isolation-and-base-branch.md) — format reference
- [docs/cli-reference.md](docs/cli-reference.md) — engine command surface
- [docs/STATUS.md](docs/STATUS.md) — implementation status (single source)
- [AGENTS.md](AGENTS.md) — mandatory workflow and open-source-readiness rules
- [e2e/README.md](e2e/README.md) — end-to-end notebook kit
