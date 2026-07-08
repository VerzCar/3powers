# Feature Specification: Live Executive Hardening — Per-Stage Artifact Contracts, Robust Dispatch, a Gated Live End-to-End Proof, and the Async Hosted Backend

**Spec ID**: RUNLIVE
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     RUNLIVE hardens the native executive delivered by EXEC (spec 009) from "walks the lifecycle with a
     fake agent" into "reliably builds real software with a real agent." It builds on EXEC and on SLIM
     (spec 010, which removed GitHub Spec Kit). It introduces no new trust-spine primitive; it makes the
     executive's dispatch honest, verifiable, resumable, and provable end-to-end. Cross-refs: EXEC-FR-*,
     3PWR §6 (lifecycle), §7 (oracle), §9 (trust spine). Its rationale lives in the epic law
     [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) (as amended by EXEC: A1′/A3′/§16). -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this is executive orchestration/dispatch hardening. It adds artifact verification, dispatch
     robustness, a live-run proof, an async backend, and commit checkpoints — but **no new trust-spine
     primitive** (no new signing, ledger, gate, or verdict logic). The thesis invariant it must preserve —
     *a model never produces or alters the verdict* (EXEC-NFR-001, 3PWR-NFR-001) — is enforced by the
     already-High-risk gate engine + ledger, which this feature never enters. Per spec §4, Standard applies.
     A maintainer may elevate to High-risk to demand mutation coverage on the new runner code. -->

**Status**: Draft

**Input**: Follow-up to EXEC (spec 009) + SLIM (spec 010). After those, `3pwr run` drives headless coding
agents directly and Spec Kit is gone. But the executive is still an MVP: all runner logic is tested with a
*fake* agent, the runner treats "agent exited 0" as success and the whole working-tree diff as the stage's
artifact (it never checks the agent actually produced the right thing), there is no dispatch timeout/retry/
streaming, no committed checkpoints between stages, and there is no backend for agents that only expose an
*asynchronous hosted* run (e.g. the GitHub Copilot coding agent) rather than a local headless CLI. This
spec closes those gaps so a real, unattended `3pwr run` produces trustworthy software.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What exists (EXEC, spec 009):** the native executive lives in `engine/src/threepowers/runner.py`
  (`CliAgentRunner`, `NativeRunner`, and a module-level `dispatch_agent` subprocess seam),
  `engine/src/threepowers/agents.py` (declarative agent manifests, `.3powers/agents/<name>.yaml`), and
  `engine/src/threepowers/prompts.py` (engine-owned stage prompts). `NativeRunner` implements the
  `Runner` protocol in `engine/src/threepowers/orchestrate.py` and is driven by the pure `drive()` state
  machine over `LIFECYCLE_STEPS`. `3pwr run` is wired in `engine/src/threepowers/cli.py` (`cmd_run`,
  `_native_runner`, `_native_verdict`, `_resolve_run_spec`). At a `verdict` step the runner calls the
  deterministic gate suite **in-process** (`gates.run_gates` → a normalized `Verdict`). Preflight is
  `runpreflight.check_native`.
- **What exists (SLIM, spec 010):** Spec Kit removed; `--runner native|sim`; `3pwr oracle dispatch` authors
  the oracle via `CliAgentRunner` inside a sanitized git worktree (`oracle.build_sanitized_worktree`).
- **The gap this spec fills** is enumerated in the Handoff of [`plan/019-remove-speckit.md`](../../plan/019-remove-speckit.md).
- **Testing pattern:** the runner is exercised with a fake agent by monkeypatching `runner.dispatch_agent`
  and injecting `dispatch`/`run_verdict` callables (see `engine/tests/test_native_runner.py`). Keep that
  possible — the deterministic suite must never require a live model or network.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** re-introduce GitHub Spec Kit or any external workflow-dispatch substrate; the native
  executive stays the only runner (EXEC, SLIM).
- Does **not** make the engine call a model/agent API itself, nor let a model produce or alter the verdict,
  the ledger, or a sign-off (EXEC-NFR-001, 3PWR-NFR-001).
- Does **not** change any deterministic gate, risk-tier threshold, ledger format, schema, or signing.
- Does **not** require a live model or network in the deterministic test suite; the live end-to-end proof is
  a separate, opt-in path that is skipped when no agent/credentials are available.
- Does **not** implement a model gateway, budgets, keys, RBAC, or SSO; per-run spend telemetry, if added,
  only *reports* what the dispatched agent emits — governance stays inherited from the org's gateway.
- Does **not** remove or replace the two mandatory human gates (spec approval 3PWR-FR-006, sign-off
  3PWR-FR-037).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stage that produced nothing is caught, not silently passed (Priority: P1)

A developer runs the lifecycle and wants each stage's agent to actually produce the artifact that stage is
responsible for — a spec file at Specify, oracle tests at Oracle, an implementation change at Implement —
so a no-op or off-target agent run is caught immediately instead of surfacing as a confusing later failure.

**Acceptance Scenarios**:

1. **Given** a run where the Specify agent exits 0 but writes no spec, **When** the stage completes, **Then**
   the run stops with a dispatch/artifact failure naming the stage and what artifact was expected — not a
   silent pass and not a gate-red verdict.
2. **Given** a run where the Oracle agent writes tests into the expected location, **When** the stage
   completes, **Then** the artifact is accepted and the run advances.
3. **Given** a run where the Implement agent makes no change to the working tree, **When** the stage
   completes, **Then** the run reports the empty-artifact failure at Implement.

### User Story 2 - Dispatch is robust and observable (Priority: P1)

A developer running unattended wants each stage's agent bounded by a timeout, retried on transient failure
per policy, its output streamed to the tracker, and a machine-readable per-stage result on `--json`, so a
long or flaky run is diagnosable and never hangs forever.

**Acceptance Scenarios**:

1. **Given** an agent that exceeds the configured per-stage timeout, **When** the stage runs, **Then** it is
   terminated and reported as a dispatch failure at that stage (not a hang, not a gate-red).
2. **Given** a transient dispatch failure and a retry policy of N, **When** the stage runs, **Then** it is
   retried up to N times before being reported as failed, and each attempt is recorded.
3. **Given** `--json`, **When** the run completes or stops, **Then** the output carries a per-stage result
   (agent, model, attempts, duration, artifact summary, outcome).

### User Story 3 - A gated live end-to-end proof (Priority: P1)

A maintainer wants an opt-in path that drives one real agent through the whole lifecycle against a tiny
sample and asserts a green verdict, so "the executive really builds software" is proven — while the default
deterministic suite still runs with no model and no network.

**Acceptance Scenarios**:

1. **Given** a real headless agent CLI on PATH and credentials configured, **When** the live proof runs,
   **Then** it drives a trivial intent to a green deterministic verdict and a completed run.
2. **Given** no agent CLI or no credentials, **When** the deterministic suite runs, **Then** the live proof
   is skipped (reported as skipped, never failed) and no network call is made.

### User Story 4 - An agent that only exposes an async hosted run (Priority: P2)

An enterprise (e.g. a GitHub Copilot shop) whose only programmatic entry to its agent runtime is an
asynchronous, hosted run — not a local headless CLI — wants the executive to dispatch that hosted run, wait
for it, collect its produced changes, and have 3Powers judge the result, all within their policy boundary.

**Acceptance Scenarios**:

1. **Given** an async-hosted agent backend configured for a role, **When** the executive reaches that role's
   stage, **Then** it triggers the hosted run, polls to completion, and collects the produced branch/pull
   request as the stage artifact, which the verdict stage then judges by the same deterministic gate suite.
2. **Given** the hosted run fails or times out, **When** the stage completes, **Then** it is reported as a
   dispatch failure naming the stage — never a gate-red.

### User Story 5 - Resume from a committed checkpoint (Priority: P2)

A developer whose long run fails mid-way wants each successful stage committed as a checkpoint, so a resume
continues from the last good state rather than re-running completed stages.

**Acceptance Scenarios**:

1. **Given** auto-commit enabled, **When** a stage completes successfully, **Then** its artifact is committed
   as a checkpoint attributable to that stage.
2. **Given** a run that failed after several committed stages, **When** it is resumed, **Then** it continues
   from the next uncompleted stage without re-dispatching the committed ones.

### Edge Cases

- An agent writes the right artifact in the wrong location → artifact verification fails with a message
  naming the expected location.
- A stage's artifact contract is unknown/undeclared → the stage falls back to the current behavior (accept a
  non-empty diff) rather than blocking, so unconfigured stages still run.
- The async hosted run needs credentials the engine must not read → the engine passes configuration through
  and never logs or stores a credential (EXEC-FR-012).
- Streaming to a non-TTY / `--json` → output degrades to the machine-readable per-stage log, no ANSI.
- Auto-commit disabled → the runner does not commit; resume falls back to re-dispatching the segment (the
  current EXEC behavior).

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable with an
  *Acceptance* line — the oracle (Phase A) is authored from these alone. A **Property** is added where input
  is parsed/validated/transformed (3PWR-FR-024). No implementation detail in the normative text
  (3PWR-FR-007): no vendor name, filename, flag, or REST path — those are decided at plan time.
-->

### Functional Requirements

#### Per-stage artifact contracts

- **RUNLIVE-FR-001**: Each executive (action) stage shall declare the artifact it is responsible for
  producing, and after dispatch the system shall verify that artifact was produced before advancing.
  - *Acceptance*: with a per-stage contract configured, a stage whose agent produced its declared artifact
    advances; one that produced nothing (or only an off-target change) does not advance.
  - *Property*: the run advances past an action stage only if that stage's declared artifact is present.
- **RUNLIVE-FR-002**: When a stage's declared artifact is absent after dispatch, the system shall report a
  dispatch/artifact failure naming the stage and the expected artifact — distinct from a gate-red verdict
  and never a silent pass (extends EXEC-FR-016).
  - *Acceptance*: an empty or off-target stage yields a named artifact failure, a non-verdict exit status,
    and no "gates red" text.
- **RUNLIVE-FR-003**: A stage with no declared artifact contract shall fall back to the prior behavior
  (accept a non-empty produced change), so unconfigured stages still run.
  - *Acceptance*: a stage without a contract behaves as it did under EXEC.

#### Robust, observable dispatch

- **RUNLIVE-FR-004**: The system shall bound each stage's dispatch by a configurable timeout and terminate a
  stage that exceeds it, reporting a dispatch failure at that stage.
  - *Acceptance*: an over-long agent is terminated and reported at its stage; the run never hangs
    indefinitely.
- **RUNLIVE-FR-005**: The system shall retry a failed dispatch up to a configurable count before reporting
  the stage failed, recording each attempt.
  - *Acceptance*: with retries=N, a stage is attempted at most N+1 times; the attempt count is reported.
  - *Property*: successful stages are never retried; the recorded attempt count never exceeds the policy.
- **RUNLIVE-FR-006**: The system shall stream agent progress to the live tracker on a TTY and shall emit a
  per-stage machine-readable result (agent, resolved model, attempts, duration, artifact summary, outcome)
  under `--json`.
  - *Acceptance*: a `--json` run carries one structured result per dispatched stage; a TTY run shows live
    progress; a non-TTY run degrades to the plain log.

#### Live end-to-end proof

- **RUNLIVE-FR-007**: The system shall provide an opt-in live end-to-end path that drives one real headless
  agent through the full lifecycle against a minimal sample and asserts a green deterministic verdict.
  - *Acceptance*: with an agent CLI + credentials available, the live path completes a run to a green
    verdict; the deterministic suite otherwise skips it (reported skipped, never failed) and makes no
    network call.
  - *Property*: the deterministic (non-live) suite performs zero outbound model calls.

#### Async hosted backend (EXEC-FR-011 shape-b)

- **RUNLIVE-FR-008**: The system shall provide an asynchronous hosted agent backend that satisfies the
  agent-runner contract: it triggers a hosted agent run, polls to completion, and collects the produced
  changes (a branch or pull request) as the stage artifact, which the same in-process deterministic gate
  suite then judges.
  - *Acceptance*: a run using the async backend produces a collected artifact that the verdict stage judges
    identically to a locally-dispatched one; a failed/timed-out hosted run is reported as a dispatch failure
    naming the stage.
- **RUNLIVE-FR-009**: The system shall pass the hosted backend's credentials/configuration through from the
  environment without interpreting, logging, or storing any secret (consistent with EXEC-FR-012).
  - *Acceptance*: no credential value appears in engine output, logs, or ledger entries when the async
    backend runs.

#### Commit checkpoints

- **RUNLIVE-FR-010**: When auto-commit is enabled, the system shall commit each successfully completed stage
  as a checkpoint attributable to that stage, and a resume shall continue from the next uncompleted stage
  without re-dispatching a committed one.
  - *Acceptance*: after several committed stages and a failure, a resume dispatches only the remaining
    stages; with auto-commit disabled the runner commits nothing and resume falls back to the segment.
  - *Property*: the number of successful dispatches for any stage across a run and its resumes never exceeds
    one.

### Non-Functional Requirements

- **RUNLIVE-NFR-001**: The engine shall make no model/agent API call itself; all model traffic originates
  from the dispatched agent process or hosted run (ref EXEC-NFR-001).
- **RUNLIVE-NFR-002**: Artifact verification, retry/timeout policy, and per-stage result rendering shall be
  deterministic and unit-testable with a fake agent and no network (ref EXEC-NFR-004).
- **RUNLIVE-NFR-003**: The deterministic verdict shall be identical whether a stage was produced by a local
  CLI backend, the async hosted backend, or a fake agent (ref 3PWR-NFR-001).
- **RUNLIVE-NFR-004**: Dispatch shall degrade gracefully — a timeout, an exhausted retry, a failed hosted
  run, or a missing artifact shall never surface as an unhandled crash; each yields an actionable message
  and a clean non-zero exit (ref 3PWR-FR-034).
- **RUNLIVE-NFR-005**: The feature shall remain provider-, model-, and agent-agnostic — no vendor is
  embedded in core logic; backend-specific behavior lives in a manifest or in pass-through env/config (ref
  EXEC-NFR-003, 3PWR-NFR-007).

## Success Criteria *(mandatory)*

- **RUNLIVE-SC-001**: A stage whose agent produced nothing (or the wrong artifact) is caught and reported at
  that stage — never a silent pass, never a false gate-red.
- **RUNLIVE-SC-002**: Every dispatched stage is bounded by a timeout, retried per policy, and reported with a
  structured per-stage result on `--json`; a run never hangs indefinitely.
- **RUNLIVE-SC-003**: An opt-in live run drives a real agent end-to-end to a green verdict, while the default
  suite runs with no model and no network.
- **RUNLIVE-SC-004**: An async-hosted-only agent (e.g. a hosted coding agent) can drive a stage end-to-end,
  its result judged identically to a local dispatch — so an enterprise without a local headless CLI is
  covered.
- **RUNLIVE-SC-005**: A failed long run resumes from the last committed stage without re-running completed
  stages.
- **RUNLIVE-SC-006**: Every functional requirement has ≥1 linked verification across the appropriate layers
  (3PWR-FR-030/065) — a behavioral test driven by a fake agent for the deterministic logic, plus the opt-in
  live proof for the real end-to-end path.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id RUNLIVE --stage spec --spec specs/011-live-executive-hardening/spec.md`; appended to the signed ledger)_ | | |
