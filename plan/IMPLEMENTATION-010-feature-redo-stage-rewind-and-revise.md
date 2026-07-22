---
goal: Implement `3pwr run --redo <stage>` to rewind an in-flight run to an earlier completed producing stage, optionally revise it, and re-flow the lifecycle through the human gates while preserving the append-only signed trust spine
version: 1.0
date_created: 2026-07-22
last_updated: 2026-07-22
owner: 3Powers maintainers
status: 'Completed'
tags: [feature, cli, ledger, orchestration, lifecycle, documentation]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

This implementation plan derives directly from the source plan `plan/039-redo-stage-rewind-and-revise.md`. It adds a new `3pwr run --redo <stage>` capability that lets a human (or a paused/failed run) deliberately **rewind** an in-flight run to any earlier *completed producing stage* (Discovery / Spec / Plan / Build), optionally attach revision feedback, and re-flow the lifecycle from that stage — while preserving the trust spine (append-only, signed, offline-reconstructable) and the existing gate discipline. The rewind is recorded by **appending** a signed `kind: "redo"` ledger entry (never by deleting or rewriting ledger history or git commits); resume math honors the latest redo entry so re-entry lands exactly at the target step; and a `--redo spec` re-run routes back through the `review-spec` gate so the amended spec is re-approved and re-sealed. All Python changes are executed later by the python-engineer agent; this document contains no code edits.

## 1. Requirements & Constraints

- **REQ-001**: Add a `--redo STAGE` flag to the `run` subparser in `engine/src/threepowers/cli/run.py` (added near the existing `--resume`/`--revise`/`--revise-file` arguments at `run.py:2748–2764`).
- **REQ-002**: `STAGE` MUST be accepted as either a stage label (`discovery`, `spec`, `plan`, `build`) or a lifecycle step id (`discovery`, `specify`, `plan`, `oracle`, `implement`) and MUST resolve to the **earliest producing step** of that stage.
- **REQ-003**: `--redo` MUST require `--spec-id` (it operates on an existing run; it is not a fresh intent).
- **REQ-004**: `--redo` MUST require an approver identity (`--approver`) and a reason (`--reason`, a new argument) for the rewind — the rewind is a deliberate, audited act.
- **REQ-005**: `--redo` MUST compose with `--revise "<msg>"` / `--revise-file <path>`; feedback resolution MUST reuse `steering.resolve_feedback` (`steering.py:86`).
- **REQ-006**: Validation MUST refuse with an actionable, non-zero (`EXIT_USAGE`) message when: the run does not exist, `STAGE` does not resolve to a producing step, the resolved step is a gate step, or the resolved step is not recorded complete for the spec-id. The refusal MUST list the redo-able stages for the run.
- **REQ-007**: A new additive, signed ledger `run` payload `kind: "redo"` MUST carry `{ target_step, reason, feedback_ref, approver }` and MUST be appended via the existing `Ledger.append` path (`ledger.py:121`) — no new entry `type`, no signing change.
- **REQ-008**: Resume math (`orchestrate.py`) MUST honor the **latest** redo entry so that completions of the target step and every later step recorded *before* that redo entry no longer count; re-entry MUST land exactly at `step_index(target)` (`orchestrate.py:129`).
- **REQ-009**: `--redo <stage> --revise …` MUST build the re-dispatch context from `steering.revise_context` (`steering.py:133`) using the original intent + the target stage's current artifact (`steering.gate_artifact`, `steering.py:103`) + the resolved feedback.
- **REQ-010**: On redo, the run branch MUST be re-entered with `gitflow.ensure_run_branch(..., mode="resume")` (as at `run.py:2078`); each re-dispatched stage commits as usual; no git history is rewritten.
- **REQ-011**: The artifact-∧-ledger completion gate (`completion.resume_entry_index`, `completion.py:140`) MUST treat the latest redo entry as the new floor so a re-dispatched stage is not judged "already complete" on a pre-rewind record.
- **REQ-012**: When the target is Spec, the re-run MUST flow through the `review-spec` gate (`orchestrate.py:44`) so the amended spec is re-approved and re-sealed through the same path a manual `signoff --stage spec` takes (`speclock.py`), never leaving a `spec_modified` state. A redo of a later stage MUST NOT disturb the existing spec seal.
- **SEC-001**: The rewind MUST NOT delete or rewrite ledger history or git commits; superseded artifacts remain in history and are marked superseded only by the appended redo entry.
- **SEC-002**: `3pwr verify` MUST still pass after a redo entry is appended (hash-chain intact, no gap/break); run status MUST render the rewind.
- **CON-001**: No change to `--resume` semantics, `--json` output, exit codes, or verdict bytes (source plan Non-goals).
- **CON-002**: `--redo` MUST be refused once a run has advanced to the Ship stage; the message MUST direct the user to `revert` instead.
- **CON-003**: No git history rewriting (`reset`/`rebase`); no partial/branching runs; only one rewind target at a time (source plan Non-goals).
- **GUD-001**: All user-facing text (CLI help, refusal messages, docs prose) MUST NOT carry internal spec/plan/requirement IDs; the guard `engine/tests/test_oss_readiness.py` enforces this.
- **PAT-001**: Follow the established pattern: pure resolution helpers live in `orchestrate.py`/`steering.py`; the CLI branch in `cli/run.py` wires them and owns I/O; ledger writes go through `Ledger.append`.
- **PAT-002**: Trust-spine modules (`ledger`, `verify`, `canonical`, `keys`) are High-risk; if any is touched, hold its line coverage ≥95%.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Add the pure, deterministic resolution and rewind math in `orchestrate.py` and `steering.py` — stage/step resolution to the earliest producing step, and a redo-aware resume-start index — with unit tests. No CLI or I/O in this phase.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/orchestrate.py`, add `producing_steps() -> list[str]` returning the action-kind step ids from `LIFECYCLE_STEPS` (`orchestrate.py:40`) whose kind is `"action"`: `discovery, specify, clarify, plan, tasks, oracle, implement, advance`; exclude `advance` from redo-eligibility (Ship). Add a module constant listing redo-eligible producing steps: `discovery, specify, plan, oracle, implement`. |           |      |
| TASK-002 | In `orchestrate.py`, add `resolve_redo_target(name: str) -> tuple[str, str]` mapping a stage label (`discovery`/`spec`/`plan`/`build`) OR a step id to `(step, stage)` resolving to the **earliest producing step** of that stage: `spec`→`specify`, `plan`→`plan`, `build`→`oracle`, `discovery`→`discovery`; a bare step id resolves to itself when it is a redo-eligible producing step. Return `("", "")` for unknown/gate/non-producing input. Reuse `lifecycle.canonical_stage` (`lifecycle.py:18`) for stage-label casing. |           |      |
| TASK-003 | In `orchestrate.py`, add `last_redo_target(entries: list[dict], spec_id: str) -> tuple[int, str]` returning the ledger sequence and `target_step` of the **latest** `run` entry with `payload.kind == "redo"` for `spec_id`, else `(-1, "")`. Iterate the same way as `last_completed_step` (`orchestrate.py:152`).                                                                                                    |           |      |
| TASK-004 | In `orchestrate.py`, add `redo_start_index(entries, spec_id, pending_gate="") -> int`: compute the base via `resume_start_index` (`orchestrate.py:169`) but, when a latest redo entry exists (TASK-003), ignore completion records at seq positions **before** that redo entry for the target step and everything after it, so the returned index equals `step_index(target)` (`orchestrate.py:129`). Keep pure — reads only the entries list. |           |      |
| TASK-005 | Add unit tests in `engine/tests/` (new `test_redo_orchestrate.py`) covering TASK-001–004: `resolve_redo_target` for each label + step id + unknown/gate/`advance` rejection; `last_redo_target` picks the latest of multiple redo entries; `redo_start_index` rewinds to `specify`, `plan`, `oracle` given pre-rewind completions, and refuses to rewind past `advance` (Ship).                                          |           |      |

### Phase 2

- GOAL-002: Append the signed `kind: "redo"` rewind marker to the ledger and prove `3pwr verify` still passes with a redo entry present. Depends on Phase 1 (uses `resolve_redo_target`).

| Task     | Description                                                                                                                                                                                                                                                                                                                                                    | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-006 | Define the redo ledger payload schema: append via `Ledger.append("run", {"kind": "redo", "target_step": <step>, "reason": <reason>, "feedback_ref": <verbatim feedback or "">, "approver": <approver>}, sk, spec_id=spec_id)` — mirror the `kind: "revise"` append shape in `_run_revise` (`run.py:1566`). No new entry `type`; reuse the existing signing path (`ledger.py:121`). |           |      |
| TASK-007 | Ensure `lifecycle.derive` (`lifecycle.py`, `SpecState` at `lifecycle.py:33`) does not misclassify a `kind: "redo"` entry as a failure or gate; the redo entry is additive metadata. Confirm status rendering surfaces the rewind (target step + approver) in `3pwr run --status` output.                                                                        |           |      |
| TASK-008 | Add a ledger test in `engine/tests/` (`test_redo_ledger_verify.py`) that builds a run ledger, appends a `kind: "redo"` entry through `Ledger.append`, and asserts `3pwr verify` (the `verify` module) still passes — hash-chain intact, no gap/break. Assert the entry is signed and readable offline.                                                          |           |      |

### Phase 3

- GOAL-003: Add the `--redo`/`--reason` CLI surface and the redo command branch in `cli/run.py`, wiring the resolution (Phase 1), the signed marker (Phase 2), the revise context reuse, and the git/completion re-entry. Depends on Phases 1–2.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                                            | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-009 | In `engine/src/threepowers/cli/run.py` add the argparse arguments to the `run` subparser (`rnp`, near `run.py:2748`): `--redo` (`dest="redo"`, `default=None`, metavar `STAGE`, help without internal IDs) and `--reason` (`dest="reason"`, `default=None`, help: reason recorded with the rewind). Keep `--approver` (`run.py:2794`).                                                    |           |      |
| TASK-010 | In `cmd_run`, add a `--redo` branch that runs before/beside the `args.resume` branch (`run.py:1997`). Guard: if `args.redo` is set, require `args.spec_id` (else `EXIT_USAGE` naming `--spec-id`), require `args.approver` and `args.reason` (else `EXIT_USAGE`). Reject a fresh intent argument combined with `--redo`.                                                                    |           |      |
| TASK-011 | In the `--redo` branch, resolve the target via `orchestrate.resolve_redo_target(args.redo)`; on `("","")` refuse with `EXIT_USAGE` and a message listing the redo-able completed producing stages for the spec-id (derive from `orchestrate.last_completed_step` / recorded completions). Refuse (`EXIT_USAGE`) when the resolved step is not recorded complete for the spec-id.            |           |      |
| TASK-012 | In the `--redo` branch, refuse (`EXIT_USAGE`) with a `revert`-directing message when the run has advanced to Ship — detect via `lifecycle.derive(...).get(spec_id).stage == "Ship"` (`lifecycle.py:14`) or an `advance` completion record.                                                                                                                                              |           |      |
| TASK-013 | In the `--redo` branch, when `--revise`/`--revise-file` is present, resolve feedback via `steering.resolve_feedback` (`steering.py:86`); on error print it and return `EXIT_USAGE`. Store the resolved feedback for the redo ledger entry (`feedback_ref`) and for the dispatch context.                                                                                                    |           |      |
| TASK-014 | In the `--redo` branch, resolve the run's feature folder (`_run_feature_dir_from_ledger`, as at `run.py:2036`) and, when git is on, re-enter the existing branch via `gitflow.branch_from_ledger` + `gitflow.ensure_run_branch(s.root, run_branch, git_prefs.base_branch, mode="resume")` (mirroring `run.py:2056–2083`). Do not allocate a new branch or run number.                       |           |      |
| TASK-015 | In the `--redo` branch, append the signed `kind: "redo"` entry (TASK-006) BEFORE computing the re-entry index, so the marker is the completion floor. Then compute the re-entry index via `orchestrate.redo_start_index(entries_now, spec_id, pending)` intersected with `completion.resume_entry_index` (`completion.py:140`, as at `run.py:2106`) to land at the target step.             |           |      |
| TASK-016 | In the `--redo` branch, build the dispatch context: when feedback is present, `steering.revise_context(<gate-for-target>, steering.gate_artifact(s.root, feature_dir, <gate-for-target>), feedback, templates_dir=s.stage_templates_dir)` (`steering.py:133`/`103`). Map the target producing step to its reviewing gate for artifact resolution (`specify`→`review-spec`, `plan`→`review-plan`). |           |      |
| TASK-017 | In the `--redo` branch, construct the runner at the computed re-entry index (reuse `_make_runner`/`_native_runner` as the resume branch does, `run.py:2111`), record dispatch provenance for the re-entered segment (`_record_dispatch`, `run.py:2112`), and drive the lifecycle forward so it re-flows through the downstream human gates (notably `review-spec` for a Spec redo).             |           |      |

### Phase 4

- GOAL-004: Ensure spec-lock / gate routing correctness for a Spec-target redo and confirm the completion floor prevents false "already complete" skips. Depends on Phase 3.

| Task     | Description                                                                                                                                                                                                                                                                                                                                                          | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-018 | Verify that a `--redo spec` re-run re-dispatches `specify`, then reaches the `review-spec` gate (`orchestrate.py:44`); on approval the spec is re-sealed through the same path as `signoff --stage spec` (`speclock.py` — `spec_approval` `speclock.py:57`, `integrity_gate` `speclock.py:136`), leaving no `spec_modified` state. Add/adjust logic only if the redo floor interferes. | Yes (no change) | 2026-07-22 |
| TASK-019 | Verify a `--redo plan` (or `--redo build`) does NOT disturb the existing spec seal (`speclock.spec_file_hash` unchanged); the `spec_integrity` gate stays green because the sealed spec is not re-dispatched.                                                                                                                                                          | Yes (no change) | 2026-07-22 |
| TASK-020 | Confirm `completion.resume_entry_index` (`completion.py:140`) treats the redo marker as the floor so the re-dispatched target stage is not skipped as "already complete" on its pre-rewind record; confirm no clean-start guard (`gitflow.unrelated_changes`, `run.py:2069`) falsely trips on the run's own recorded paths.                                             | Yes (no change) | 2026-07-22 |

### Phase 5

- GOAL-005: Add run-level and integration tests exercising the whole `--redo` flow via the simulator/dry-run path. Depends on Phases 1–4.

| Task     | Description                                                                                                                                                                                                                                                                                                                                              | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-021 | Add a run-level test in `engine/tests/` (`test_run_redo.py`) using the dry-run/simulator runner (`--dry-run`, as `_run_revise` handles the sim path at `run.py:1535`) proving `3pwr run --redo spec --revise "<msg>" --spec-id <NNN> --approver <x> --reason <y>` re-dispatches Spec, pauses at the spec-approval gate, then re-flows Plan → Build. |           |      |
| TASK-022 | Add CLI validation tests: `--redo` without `--spec-id` → `EXIT_USAGE`; without `--approver`/`--reason` → `EXIT_USAGE`; unknown/gate stage → `EXIT_USAGE` with the redo-able list; a not-yet-completed target stage → `EXIT_USAGE`; a Ship-stage run → `EXIT_USAGE` directing to `revert`.                                                                  |           |      |
| TASK-023 | Add a test asserting `3pwr verify` passes end-to-end after a simulated redo run (extends TASK-008 at the run level). Ensure trust-spine module coverage stays ≥95% if `ledger`/`verify` were touched (PAT-002).                                                                                                                                            |           |      |
| TASK-024 | Add an OSS-readiness assertion path: run `engine/tests/test_oss_readiness.py` against the new CLI help + messages to confirm no internal spec/plan IDs leak (GUD-001).                                                                                                                                                                                     |           |      |

### Phase 6

- GOAL-006: Update user-facing documentation for `--redo` (the source plan's explicit ask). No internal IDs in any prose (GUD-001).

| Task     | Description                                                                                                                                                                                                                                                                                                                                                     | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-025 | In `docs/cli-reference.md` `run` section (around `cli-reference.md:840`, beside `--resume`/`--revise`), document `--redo STAGE`: what it rewinds to (an earlier completed producing stage), that it requires `--spec-id`, `--approver`, and `--reason`, that it re-flows through the human gates (spec approval re-seals the amended spec), and the redo-able stage list. Add a worked example to the code block (`cli-reference.md:851`). |           |      |
| TASK-026 | In `docs/troubleshooting.md`, add the new entry **"Going back to an earlier stage to fix or clarify it"** using the verbatim draft text from `plan/039-redo-stage-rewind-and-revise.md` (lines 159–183).                                                                                                                                                        |           |      |
| TASK-027 | In `docs/troubleshooting.md`, extend the existing **"artifact missing at <stage>"** entry Fix (`troubleshooting.md:60–73`) to cross-link the new `--redo` entry as the way to go back and answer a question the agent asked upstream.                                                                                                                            |           |      |
| TASK-028 | In `docs/getting-started.md`, add one line under the human-gate / "When gates go red" walkthrough noting that a run can also be rewound to an earlier stage with `--redo`.                                                                                                                                                                                       |           |      |

### Phase 7

- GOAL-007: Verification phase — the engine stays green under its own gates and the whole feature is proven end-to-end. Depends on all prior phases.

| Task     | Description                                                                                                                                                                                                    | Completed | Date |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-029 | Run `cd engine && uv run ruff check . && uv run mypy src` — zero lint/type errors.                                                                                                                             |           |      |
| TASK-030 | Run `cd engine && uv run pytest` — all tests pass, including the new `test_redo_orchestrate.py`, `test_redo_ledger_verify.py`, `test_run_redo.py`, and the OSS-readiness guard `test_oss_readiness.py`.          |           |      |
| TASK-031 | Run `3pwr gate run --path engine` — `diff_coverage` and `spec_conformance` green; trust-spine modules (`ledger`/`verify`) coverage ≥95% if touched (PAT-002).                                                   |           |      |
| TASK-032 | Manually exercise `3pwr run --redo spec --revise "<msg>" --spec-id <NNN> --approver <x> --reason <y> --dry-run` on a throwaway run and confirm it rewinds to Spec, pauses at spec approval, and `3pwr verify` passes. |           |      |
| TASK-033 | Confirm docs (`cli-reference.md`, `troubleshooting.md`, `getting-started.md`) render correctly and carry no internal spec/plan IDs; behavior change and docs landed in the same unit of work.                    |           |      |

## 3. Alternatives

- **ALT-001**: Overload `--resume --redo <stage>` instead of a standalone `--redo`. Rejected — the source plan recommends a standalone `--redo` that implies operating on an existing `--spec-id`; overloading resume muddies the forward-only resume semantics (CON-001).
- **ALT-002**: Rewrite ledger/git history to physically remove superseded stages. Rejected — violates SEC-001/CON-003 (append-only, offline-reconstructable trust spine); the redo is recorded additively.
- **ALT-003**: Allow redo of gate steps (e.g. re-run `review-spec` directly). Rejected — a gate is re-reached, not redone; only producing steps are redo-able (source plan decision 3).
- **ALT-004**: Allow a bare `--redo` with no approver/reason. Rejected — a rewind is a deliberate, audited act; requiring `--approver` and `--reason` mirrors gate-action ergonomics (source plan decision 2).

## 4. Dependencies

- **DEP-001**: `engine/src/threepowers/orchestrate.py` — `LIFECYCLE_STEPS`, `step_index`, `resume_start_index`, `last_completed_step` (extended, not replaced).
- **DEP-002**: `engine/src/threepowers/steering.py` — `resolve_feedback`, `revise_target`, `gate_artifact`, `revise_context` (reused as-is).
- **DEP-003**: `engine/src/threepowers/ledger.py` — `Ledger.append` (existing signed-append path; no new entry type).
- **DEP-004**: `engine/src/threepowers/lifecycle.py` — `STAGES`, `canonical_stage`, `derive`/`SpecState`.
- **DEP-005**: `engine/src/threepowers/completion.py` — `resume_entry_index` (redo floor).
- **DEP-006**: `engine/src/threepowers/gitflow.py` — `ensure_run_branch(mode="resume")`, `branch_from_ledger`, `unrelated_changes`.
- **DEP-007**: `engine/src/threepowers/speclock.py` — `spec_approval`, `integrity_gate`, `spec_file_hash` (Spec re-seal path).
- **DEP-008**: `engine/src/threepowers/verify.py` — ledger hash-chain verification (must remain green).
- **DEP-009**: python-engineer agent executes the engine Python changes; this plan only specifies them.

## 5. Files

- **FILE-001**: `engine/src/threepowers/orchestrate.py` — add `producing_steps`, `resolve_redo_target`, `last_redo_target`, `redo_start_index`; redo-eligible producing-step constant.
- **FILE-002**: `engine/src/threepowers/cli/run.py` — add `--redo`/`--reason` args to the `run` subparser; add the `--redo` command branch in `cmd_run`.
- **FILE-003**: `engine/src/threepowers/steering.py` — no change expected (reused); adjust only if artifact/gate mapping for a redo target needs a helper.
- **FILE-004**: `engine/src/threepowers/lifecycle.py` — ensure `derive`/`SpecState` tolerate and (in status) surface the `kind: "redo"` entry.
- **FILE-005**: `engine/tests/test_redo_orchestrate.py` — NEW: unit tests for resolution + rewind math.
- **FILE-006**: `engine/tests/test_redo_ledger_verify.py` — NEW: ledger append + `verify` still passes.
- **FILE-007**: `engine/tests/test_run_redo.py` — NEW: run-level simulator/dry-run flow + CLI validation tests.
- **FILE-008**: `docs/cli-reference.md` — `--redo STAGE` documentation + worked example in the `run` section.
- **FILE-009**: `docs/troubleshooting.md` — new "Going back to an earlier stage…" entry + cross-link from "artifact missing at <stage>".
- **FILE-010**: `docs/getting-started.md` — one line noting `--redo` rewind under the human-gate walkthrough.

## 6. Testing

- **TEST-001**: `resolve_redo_target` maps each stage label (`spec`/`plan`/`build`/`discovery`) and step id to the correct `(step, stage)`; unknown, gate, and `advance` inputs return `("","")`.
- **TEST-002**: `last_redo_target` returns the latest of multiple redo entries; `(-1, "")` when none.
- **TEST-003**: `redo_start_index` rewinds re-entry to `specify`, `plan`, and `oracle` given pre-rewind completions; ignores completions recorded before the latest redo entry.
- **TEST-004**: `3pwr verify` passes after a `kind: "redo"` entry is appended to a run ledger (hash-chain intact).
- **TEST-005**: `3pwr run --redo spec --revise "<msg>" --spec-id <NNN> --approver <x> --reason <y> --dry-run` re-dispatches Spec, pauses at spec approval, re-flows Plan → Build.
- **TEST-006**: CLI refusals — missing `--spec-id`, missing `--approver`/`--reason`, unknown/gate stage (with redo-able list), not-yet-completed target, Ship-stage run (directs to `revert`) — each returns `EXIT_USAGE`.
- **TEST-007**: A `--redo spec` run re-seals the spec through the `review-spec` gate (no residual `spec_modified`); a `--redo plan`/`--redo build` leaves the spec seal untouched.
- **TEST-008**: `engine/tests/test_oss_readiness.py` passes with the new CLI help and messages (no internal spec/plan IDs).
- **TEST-009**: `diff_coverage` and `spec_conformance` green via `3pwr gate run --path engine`; trust-spine coverage ≥95% if `ledger`/`verify` touched.

## 7. Risks & Assumptions

- **RISK-001**: `redo_start_index` mis-computing the floor could re-dispatch too few or too many stages. Mitigation: TASK-004 keeps it pure and TASK-005/TASK-003 fully unit-test the latest-redo-wins math against pre-rewind completions.
- **RISK-002**: The completion gate (`completion.resume_entry_index`) may still treat a pre-rewind record as "already complete". Mitigation: TASK-015/TASK-020 make the redo marker the explicit completion floor and test the re-dispatch of the target stage.
- **RISK-003**: A Spec redo could leave the spec in a `spec_modified` state if the re-run bypasses `review-spec`. Mitigation: TASK-012/TASK-018 route the redo through the normal gate and re-seal via the same `speclock` path as `signoff --stage spec`.
- **RISK-004**: Touching `ledger`/`verify` could drop trust-spine coverage below 95%. Mitigation: TASK-006 reuses the existing append path (no new entry type/signing), and TASK-023/TASK-031 assert coverage.
- **RISK-005**: User-facing text could leak internal IDs. Mitigation: GUD-001 + TASK-024/TASK-033 run the OSS-readiness guard.
- **ASSUMPTION-001**: The run being rewound exists with a signed ledger and recorded completions for the target stage; `--redo` operates only on an existing `--spec-id`.
- **ASSUMPTION-002**: `steering.revise_context`/`gate_artifact` produce the correct artifact reference for the redo target when mapped through its reviewing gate (specify→review-spec, plan→review-plan).
- **ASSUMPTION-003**: The redo target is a producing stage before Ship; a run at Ship uses `revert`, not `--redo` (CON-002).

## 8. Related Specifications / Further Reading

- Source plan: `plan/039-redo-stage-rewind-and-revise.md`
- CLI reference (run section): `docs/cli-reference.md`
- Troubleshooting: `docs/troubleshooting.md`
- Getting started: `docs/getting-started.md`
- Orchestration lifecycle: `engine/src/threepowers/orchestrate.py`, `engine/src/threepowers/lifecycle.py`
- Steering / revise: `engine/src/threepowers/steering.py`
- Trust spine: `engine/src/threepowers/ledger.py`, `engine/src/threepowers/verify.py`, `engine/src/threepowers/speclock.py`, `engine/src/threepowers/completion.py`, `engine/src/threepowers/gitflow.py`
- Workflow rules: `AGENTS.md`; architecture: `CLAUDE.md`; status: `docs/STATUS.md`
