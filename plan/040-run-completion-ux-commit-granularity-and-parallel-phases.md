# PLAN-040 — Run-completion UX, commit granularity, and dependency-aware parallel phases

- **Branch:** `feat/040-run-ux-commits-scheduling` (already checked out)
- **Epic:** U — Run UX & scheduling
- **Status:** Final (all maintainer decisions confirmed; no open questions)
- **Scope:** `engine/src/threepowers/` + `docs/` + bundled scaffold templates. One unit of work, six work streams (A–F).
- **Internal evidence:** `tmp/run-feature.log.txt` (real run exhibiting all three defects), `tmp/implementation-plan-feature-005.md` (real phased artifact whose `[P]` phases silently serialized).

---

## 1. Context

Three real-world problems were confirmed in a full `3pwr run` lifecycle (see `tmp/run-feature.log.txt`):

1. **Run completion reads as "still pending."** A finished run prints the tracker with `▶ Observe`
   as if a stage were queued, plus the terse line "✓ lifecycle complete — advanced to Ship; observe
   feeds new intent" (`engine/src/threepowers/cli/run.py` ~L2787–2793; `progress.py` ~L350;
   `notify.py` ~L306). The user is left unsure whether anything is still running and what to do next.
2. **The working tree is dirty at every human gate and at run end.** Producing stages commit
   exactly once via the post-stage hook (`cli/run.py` ~L1281–1330 → `gitflow.commit_stage`,
   `gitflow.py` L402+), commit-or-fail (`CLASS_COMMIT_FAILED`). But (a) a phased implement commits
   once for **all** phases together, and (b) the judgment steps — verify (gate verdict ledger
   entries), review-verify, signoff, advance, and the final `{"kind":"complete"}` ledger append —
   never commit. The ledger and `progress.md` are left uncommitted; the maintainer hit
   `3pwr advance --stage ship` refusing on "uncommitted work" at Ship — caused by the engine's own
   uncommitted state.
3. **`[P]` phases never actually parallelize.** `phases.py::_parallel_eligible` (L249–253) admits a
   phase to a concurrent batch only when it is `[P]`-marked **and declares no `depends_on`** and has
   a file scope. Real implementation plans mark Phase 2/3 `[P]` with "Depends on: Phase 1"
   (see `tmp/implementation-plan-feature-005.md`), so they always serialize — silently — defeating
   the engine's documented parallel-dispatch promise.

A fourth inefficiency: the `advance` lifecycle step (`orchestrate.py` L40–54 `LIFECYCLE_STEPS`,
`("advance","action","Ship")`) has no dedicated agent template, falls back to
`generic.agent.md`, and the dispatched agent burns time rediscovering that it must run
`3pwr advance --stage ship`, then improvises remediation when refused.

## 2. Goals

- A completed run **ends visibly**: Ship rendered as done ("ready to push"), an explicit
  "all stages are done" statement, a short business summary rendered from the run's existing
  `changelog.md` record, and an Observe call-to-action block.
- **Nothing uncommitted at run end or at any human-gate pause**: one commit per implement phase
  (deterministic order), and engine-state commits after verify, signoff, advance, and the final
  complete entry.
- **Dependency-aware parallel batching** for `[P]` phases with satisfied dependencies and disjoint
  file scopes, plus **explicit pre-batch log lines** stating what runs in parallel/serially, why a
  `[P]` phase was serialized, and which agent/model executes each phase.
- **In-process advance** with a dedicated remediation template dispatched only on refusal.
- Docs updated everywhere in the same unit of work; engine stays green under its own gates.

## 3. Non-goals

- **Observe stays a stage.** The documented 8-stage lifecycle and `3pwr observe coverage` are
  unchanged; only the run-end presentation changes.
- **The two human gates stay.** No change to spec approval or sign-off semantics.
- **No CI requirement.** Trust remains locally recoverable; no enforcement moves to CI/CD.
- No change to gate ordering, verdict schema semantics (additive fields only where byte contracts
  bind), oracle independence rules, or the `--commit-relaxed`/deviation escape hatches.
- No removal of legacy artifact/layout support (`tasks.md`, phaseless plans, `specs/` layouts).

---

## 4. Design

### Work stream A — Run-completion UX (Observe as call-to-action)

**Where:** `cli/run.py` completion block (~L2787–2793), `progress.py` (~L350), `notify.py` (~L306),
`completion.py` (`render_changelog` / `RECORD_STEPS`).

1. **Tracker end state.** When the run advances to Ship and completes, render Ship as the final
   *completed* actionable step — e.g. `✔ Ship — ready to push` — and render Observe not as a
   pending `▶` row but as the follow-on pointer (visually distinct, e.g. `○ Observe — next: …` or
   folded into the CTA block; exact glyph chosen in the implementation plan, consistent with the
   existing tracker vocabulary).
2. **Completion statement + business summary.** Print an explicit "All stages are done." line,
   then a short summary of what the run built, **reused** from the run's agent-authored
   `changelog.md` in the feature folder (the implement stage's Keep-a-Changelog record, already
   validated by `completion.py`). Render its highlight bullets (cap the count, e.g. first 5).
   **No extra agent dispatch, no new artifact.** If `changelog.md` is absent/unparseable
   (legacy runs), degrade gracefully to the current one-liner.
3. **Observe CTA block.** A compact block covering: where the user is now (run branch, Ship
   reached, everything committed); next actions — `3pwr observe coverage --spec <spec>` to see
   which NFRs lack live production checks, register checks in
   `.3powers/config/observability.yaml`, push/merge the run branch; and how production lessons
   return: a **new** `3pwr run "<intent>"`, never ad-hoc patches.
4. **In step:** `progress.md`'s final state line and the notification message updated to the same
   "complete — ready to push" wording.

### Work stream B — Commit granularity: per-phase and per-judgment-step

**Where:** `cli/run.py` (`_dispatch_phased` L826–955, post-stage hook ~L1281–1330, `run_verdict`
~L1420–1470, completion block), `gitflow.py` (`commit_stage` L402+, `stage_commit_message`,
`recorded_run_paths`/`uncommitted_run_paths` L320–341, `ENGINE_STATE_PREFIX` L62).

1. **One commit per implement phase, deterministic order.** Parallel phases cannot commit
   concurrently (git index lock), so per-phase commits land **sequentially from the collecting
   thread after each batch completes, in phase order**. Each phase commit carries the phase's
   produced paths + the agent-written `COMMIT:` description (message shape via a phase-aware
   variant of `stage_commit_message`, e.g. `implement(phase 2/5): <description>`).
2. **Decision — engine state placement:** phase commits carry **only the phase's produced paths**;
   the ledger "phases" entry (appended after collection today) and `progress.md` land in a single
   trailing **implement record commit** after all phases. Rationale: the ledger entry doesn't exist
   until collection; per-phase engine-state churn would create mid-stage ledger commits with no
   corresponding entry, and this keeps `recorded_run_paths` reconciliation simple.
3. **Judgment-step engine-state commits.** New small helper (e.g. `gitflow.commit_engine_state`)
   that commits only paths under `ENGINE_STATE_PREFIX` (ledger) + the run's `progress.md`, with
   deterministic messages. Invoked after: the verify verdict (including auto-fix verdict entries),
   review-verify, signoff, advance, and the final `{"kind":"complete"}` append. Also invoked
   **before every human-gate pause**, so a pause leaves a clean tree (maintainer-confirmed:
   "committing does not hurt — it will be either changed, rejected or accepted").
4. **Contract extension.** A phase/judgment step is only "complete" when its work is committed —
   the existing commit-or-fail discipline (`CLASS_COMMIT_FAILED`) extends to phase commits and
   engine-state commits. `--commit-relaxed` and the deviation escape hatches keep their current
   meaning and skip/soften these commits exactly as they do for stage commits today.
5. **Net effect:** a finished run leaves a **clean working tree**; `3pwr advance` never again
   refuses on the engine's own uncommitted state.

### Work stream C — Dependency-aware parallel scheduling + visible parallelism

**Where:** `phases.py` (`_parallel_eligible` L249–253, `schedule` L256+, `run_phases`),
`cli/run.py` (batch dispatch logging), `progress.py` (phase table).

1. **Batching rule change.** A `[P]` phase joins a concurrent batch when: all its declared
   `depends_on` phases are **already completed** (in a prior batch), it has a file scope, and its
   file scope is disjoint from every other phase in the batch. Scheduling stays **pure and
   deterministic** (stable ordering by phase number); `phases.py` remains ledger-free (the existing
   guard test that the module never touches the ledger must keep passing).
2. **Pre-batch log lines.** Before dispatching each batch, print for the end user: the batch
   number; which phases run now and whether in parallel or serially; for every serialized
   `[P]` phase a **named reason** (e.g. "depends on Phase 3 (not yet complete)", "file scope
   overlaps Phase 2", "no file scope declared"); and which agent/model executes each phase,
   including the configured subagent model from `roles.yaml` `subagent_models` when set. The
   scheduler returns this decision metadata (reasons attached to the schedule result); the CLI
   layer renders it.
3. **progress.md.** Extend the phase table with a parallel/serial marker (and batch index) where it
   fits the existing table shape; purely additive.

### Work stream D — In-process advance + dedicated remediation template

**Where:** `orchestrate.py` (advance step), `cli/trust.py` (`cmd_advance` L285–460), `prompts.py`
(closed variable set, `substitute()`/`_VARS`), bundled templates
`engine/src/threepowers/scaffold/templates/agents/` + repo-local `.3powers/templates/agents/`.

1. **Factor, don't duplicate.** Extract the enforcement core of `cmd_advance` (ledger verifies,
   latest verdict green or deviated, sign-off exists, oracle independence at High-risk, spec
   integrity, git discipline — the six refusal reasons) into a callable (e.g.
   `advance_check(...) -> AdvanceResult` with structured refusal reasons). `cmd_advance` and the
   run orchestrator both call it; behavior of the CLI command is unchanged.
2. **Default path: no dispatch.** The run's advance step executes the check in-process. On success
   it records/advances exactly as today (plus the engine-state commit from work stream B).
3. **Refusal path: remediation dispatch.** Only on refusal does the run dispatch a headless agent,
   using a **new dedicated template** `advance.agent.md` (bundled scaffold twin + repo-local
   override, following existing template conventions: frontmatter, role, `$VARIABLES` from the
   closed set). The template carries the **named refusal reasons** and instructs: fix the named
   blockers honestly; commit run-produced work on the run branch; re-run `3pwr advance`; **never**
   weaken gates; **never** self-file deviations. If the closed variable set lacks a slot for the
   refusal reasons, add one (e.g. `$REFUSAL_REASONS`) in `prompts.py` — extending `_VARS` and the
   substitution tests is in scope.
4. The generic-fragment fallback for `advance` disappears (the step no longer dispatches by
   default); the bundled template count grows by one — update any test asserting the template set.

### Work stream E — Documentation (same unit of work)

- [docs/concepts.md](../docs/concepts.md): what Observe is *for*; run-end "ready to push" state; how
  production lessons return as new intent; per-phase/per-step commit granularity as part of the
  trust story (clean tree at every gate).
- [docs/getting-started.md](../docs/getting-started.md): the new completion output walk-through; what
  to do after a run (observe coverage, `observability.yaml`, push/merge); how to proceed with the
  next intent when it relates to an existing spec — new run/new spec vs. revising via the existing
  `--redo`/`revert`/revise mechanisms and when each applies.
- [docs/cli-reference.md](../docs/cli-reference.md): run output changes (completion block, pre-batch
  scheduling lines), commit granularity, in-process advance + remediation dispatch,
  `advance.agent.md` template override point.
- [docs/engine-architecture.md](../docs/engine-architecture.md) and
  [docs/troubleshooting.md](../docs/troubleshooting.md): sweep for stale statements ("one commit per
  stage", "`[P]` phases run concurrently" caveats, "uncommitted work at Ship" troubleshooting entry
  becomes obsolete/reworded).
- [AGENTS.md](../AGENTS.md) / [CLAUDE.md](../CLAUDE.md): update the one-commit-per-stage and lifecycle-end
  summaries where they describe the old behavior.
- **OSS-readiness:** no internal requirement IDs (`3PWR-FR-U##`) in any user-facing text — docs,
  CLI output, template prose, scaffold assets. Teaching examples use `DEMO-FR-###`/bare `FR-###`.
  `engine/tests/test_oss_readiness.py` must stay green (it also scans scaffold assets — the new
  `advance.agent.md` is in its scope).

### Work stream F — Constraints threaded through the implementation

- Engine self-gating: ruff, mypy (clean `mypy src`), pytest — green at every commit point.
- Tests ship with the change, mirroring source layout: extend
  `engine/tests/test_gitflow.py`, `test_phases.py`, `test_orchestrate.py`, `test_progress.py`,
  `test_notify.py`, `test_completion.py`, plus `cli/run` coverage where it lives today.
- Trust-spine coverage (`canonical`, `keys`, `ledger`, `verify`, `speclock`, `anchor`) stays ≥95%;
  the `[tool.mutmut]` scope is not touched.
- Byte-golden tests (`engine/tests/golden/`) and verdict-bytes guards: **additive fields only**
  where those contracts bind; new ledger-adjacent data must not change existing canonical bytes.

---

## 5. Requirements

| ID | Requirement |
|----|-------------|
| 3PWR-FR-U01 | At run completion the tracker renders Ship as the final completed step ("ready to push"); Observe is no longer rendered as a pending `▶` stage. |
| 3PWR-FR-U02 | Run completion prints an explicit all-stages-done statement plus a short business summary rendered from the run's existing `changelog.md` record; no extra agent dispatch, no new artifact; graceful fallback when the record is absent. |
| 3PWR-FR-U03 | Run completion prints an Observe call-to-action block: current state, `observe coverage` usage, `observability.yaml` registration, push/merge guidance, and next-intent guidance. |
| 3PWR-FR-U04 | `progress.md`'s final state line and the completion notification carry the same "complete — ready to push" wording. |
| 3PWR-FR-U05 | A phased implement lands one commit per phase, in deterministic phase order, sequenced from the collecting thread after each batch; each carries the phase's produced paths + agent `COMMIT:` description. |
| 3PWR-FR-U06 | The implement-stage ledger "phases" entry and `progress.md` land in a single trailing implement record commit after all phase commits. |
| 3PWR-FR-U07 | Verify (incl. auto-fix verdicts), review-verify, signoff, advance, and the final complete ledger append each commit their engine state (ledger + progress.md). |
| 3PWR-FR-U08 | Every human-gate pause is preceded by an engine-state commit; a finished run leaves a clean working tree. |
| 3PWR-FR-U09 | Phase and judgment-step commits follow the commit-or-fail discipline (`CLASS_COMMIT_FAILED`); `--commit-relaxed` and deviation escape hatches keep working. |
| 3PWR-FR-U10 | A `[P]` phase whose declared dependencies are all completed joins a concurrent batch with other such phases having disjoint file scopes. |
| 3PWR-FR-U11 | Scheduling stays pure and deterministic; `phases.py` remains ledger-free (guard test intact). |
| 3PWR-FR-U12 | Before each batch, the run logs which phases run, parallel vs. serial, a named reason for every serialized `[P]` phase, and the executing agent/model (incl. `subagent_models` when configured). |
| 3PWR-FR-U13 | `progress.md`'s phase table surfaces the parallel/serial (batch) information additively. |
| 3PWR-FR-U14 | The run's advance step executes the advance enforcement in-process by default, reusing a factored core of `cmd_advance` (no duplicated logic). |
| 3PWR-FR-U15 | On refusal, the run dispatches a remediation agent using a new dedicated `advance.agent.md` template (bundled + repo-local override) carrying the named refusal reasons and honest-remediation instructions. |
| 3PWR-FR-U16 | Any new template variable (e.g. refusal reasons) is added to the closed variable set in `prompts.py` with tests. |
| 3PWR-FR-U17 | Docs (`concepts`, `getting-started`, `cli-reference`; sweep `engine-architecture`, `troubleshooting`) and AGENTS.md/CLAUDE.md summaries are updated in the same unit of work; OSS-readiness holds everywhere. |
| 3PWR-FR-U18 | Engine gates stay green; golden/verdict-byte contracts are only extended additively; trust-spine coverage does not regress below 95%; `./e2e/run.sh typescript --check` stays green. |

## 6. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| **Git index contention** if per-phase commits ran from worker threads. | Commits are issued only from the collecting thread, sequentially, in phase order (U05) — never from workers. |
| **Byte-golden / verdict-bytes breakage** from new ledger-adjacent data or message changes. | No changes to canonical bytes; only additive fields; run the golden suite early in each phase. |
| **Backward compatibility: phaseless artifacts and legacy runs** (legacy `tasks.md`, missing `changelog.md`, old feature-folder layouts). | Phaseless implement keeps the single-commit path unchanged; completion summary degrades to the current one-liner; scheduling change only affects artifacts that declare `depends_on`. |
| **Auto-mode vs. commit-mode gates:** engine-state commits could surprise `--commit-relaxed`/deviation flows or repos with commit hooks. | Escape hatches gate the new commits identically to stage commits (U09); commit-or-fail failure classes reuse `CLASS_COMMIT_FAILED` so remediation guidance stays uniform. |
| **Wrong parallelism after the scheduling fix** (overlapping scopes racing). | Disjoint-file-scope check is unchanged and mandatory; new tests cover dependency-satisfied batching, overlap serialization, and the named-reason output. |
| **Advance-core refactor regressing the CLI command.** | Pure extraction with the existing `cmd_advance` tests as the safety net; the six refusal reasons become structured data asserted in both call sites. |
| **Template-set assumptions in tests/scaffold.** | Update template-count/oss-readiness tests together with the new `advance.agent.md`. |

## 7. Validation strategy

1. **Engine gates:** `cd engine && uv run ruff check . && uv run mypy src && uv run pytest` — green
   at the end of every phase of the implementation plan.
2. **Targeted tests (new/extended):**
   - `test_gitflow.py`: per-phase commit messages/paths, trailing implement record commit,
     `commit_engine_state`, commit-or-fail on phase commits, relaxed-mode skips.
   - `test_phases.py`: dependency-satisfied `[P]` batching, overlap/no-scope serialization with
     named reasons, determinism, ledger-free guard.
   - `test_orchestrate.py` / run-CLI tests: in-process advance success path (no dispatch),
     refusal → remediation dispatch with `advance.agent.md`, pre-batch log lines, clean-tree
     invariant at pauses and completion.
   - `test_progress.py` / `test_notify.py` / `test_completion.py`: final-state wording, CTA block,
     changelog-derived summary + fallback.
   - `test_oss_readiness.py`: new template and all new user-facing strings pass.
3. **Byte contracts:** full `engine/tests/golden/` + verdict-bytes guards pass unmodified except
   documented additive extensions.
4. **e2e:** `./e2e/run.sh typescript --check` green (deterministic, no agent).
5. **Live-run smoke:** one real `3pwr run "<small feature intent>"` against an e2e sandbox with a
   headless agent, verifying: per-phase commits in order, clean tree at each pause and at end,
   pre-batch parallelism lines, in-process advance (no generic-fragment dispatch), and the new
   completion block — compared against the failure modes captured in `tmp/run-feature.log.txt`.

## 8. Docs impact

Covered by work stream E / 3PWR-FR-U17: `docs/concepts.md`, `docs/getting-started.md`,
`docs/cli-reference.md` (mandatory); `docs/engine-architecture.md`, `docs/troubleshooting.md`
(stale-statement sweep); `AGENTS.md` + `CLAUDE.md` (stage-commit and lifecycle-end summaries).
No internal requirement IDs in any of them.

## 9. Open questions

None — all maintainer decisions are confirmed in the intent. The one design decision delegated to
this plan (engine-state placement for phase commits) is resolved in work stream B item 2: phase
commits carry produced paths only; ledger + progress land in a trailing implement record commit.
