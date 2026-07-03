# Feature Specification: Headless Executive Dispatch — a Live, End-to-End `3pwr run` that Drives Real Agents (the A3 Coder Leg)

**Spec ID**: RUNX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     RUNX is a standalone feature spec that completes the executive (coder) leg of the live headless
     dispatch (A3). It cites 3PWR-*, INITX-*, and ONBRD-* ids only as cross-references (the "why"). Its
     rationale lives in the epic law: §6 (the eight-stage lifecycle & one-command orchestration),
     §7 (oracle independence & model diversity), §9 (the trust spine — ledger, verify, advance),
     §10 (agnosticism/adapters) of [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md). It is the
     execution half of the init story whose setup half is INITX (spec 007). -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this feature orchestrates the lifecycle and dispatches agent work through the Spec Kit
     substrate (A1), reusing already-delivered trust-spine primitives — the oracle read-path-isolation
     attestation, the signed ledger, the model-diversity refusal, and the `advance` enforcement gate,
     each already governed at High-risk in its own module (canonical/keys/ledger/verify, oracle). It
     implements no new trust-spine primitive (no new signing, ledger, or gate logic); it composes them
     and records additive provenance. Per spec §4 this is orchestration/config work, so Standard applies.
     The independence-bearing requirements (RUNX-FR-005..008) delegate to those High-risk primitives and
     never relax them. A maintainer may elevate the whole spec to High-risk to demand mutation coverage on
     the new dispatch/attestation code; it is declared Standard here and is adjustable at spec approval. -->

**Status**: Draft

**Input**: User description: "If I run `3pwr run` in a new project after `3pwr init --with-speckit`, it fails
immediately with `✗ gates red — stopped for your decision` and an all-dots stage tracker — but no gate ever ran. The
executive stages still need an IDE (Copilot) to do the work, the oracle step isn't a genuinely different model family,
and the error message points me at `observe signal --kind incident`, which is the wrong remedy. I want `3pwr run` to
actually drive the real agents headlessly through the whole lifecycle — stopping only at the two human gates — with the
oracle really running on a different family, and I want a run that *cannot* start to tell me plainly what's missing and
how to fix it, instead of pretending a gate failed."

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** provision the Spec Kit workspace, render workflow or agent templates, install extensions, or pin
  judiciary agent models — that is the Init Experience feature (INITX, spec 007). This feature **consumes** what INITX
  provisions and, when those artifacts are absent, reports them as unmet prerequisites (cross-ref INITX-FR-005/009); it
  never scaffolds them itself.
- Does **not** reimplement Spec Kit's dispatch, its workflow engine, its preset/extension mechanism, or its model
  registry. It composes the existing `workflow run` / `resume` dispatch (3PWR A1).
- Does **not** make the engine itself call any model or agent API. All agent work is dispatched through the Spec Kit
  substrate; the engine only orchestrates, records, and attests (3PWR A3).
- Does **not** weaken, remove, or bypass any deterministic gate, any risk-tier threshold, or either mandatory human
  gate (3PWR-FR-032/042/006/037).
- Does **not** replace, retire, or weaken the independent-oracle Phase-A flow or its physical read-path isolation
  (3PWR-FR-020/021/062). It **invokes** that authoritative flow for a run's oracle step.
- Does **not** select, pin, or override the model for the coder role or any non-judiciary agent; the coder stays on its
  integration's default model. The only model constraint this feature adds is that the oracle resolve to a **different
  family** than the coder (3PWR-FR-022).
- Does **not** install, configure, or auto-provision a coder or oracle integration, nor a Spec Kit workspace, nor a
  language toolchain. It **detects** availability and reports what is missing; installation is a setup concern
  (ONBRD / INITX).
- Does **not** add auto-commit-per-stage (that is INITX-FR-006), new notification transports beyond the existing
  `--notify <cmd>` hook, or a richer terminal UI (plan 013 residuals).
- Does **not** change the on-disk trust-spine layout, the ledger format, the schemas, or the meaning of any existing
  flag, beyond **additively** recording an executive-dispatch provenance entry alongside the existing verdict and
  oracle-dispatch entries.
- Does **not** alter what the deterministic gate suite checks or how a verdict is computed; a verdict is identical
  whether the stages that produced it were dispatched headlessly or driven step-by-step.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the whole lifecycle headlessly, unattended except at the two human gates (Priority: P1)

A developer wants `3pwr run "<intent>" --mode auto` to carry the intent all the way through the eight-stage lifecycle
with real coding agents doing the spec, plan, and implementation work — without an IDE session open — so the run
proceeds on its own and pauses only where a human must decide.

**Acceptance Scenarios**:

1. **Given** a project whose lifecycle workflow is provisioned and a headless coder integration is available, **When**
   the developer runs auto mode, **Then** each executive stage (specify, clarify, plan, tasks, implement) is dispatched
   to that integration with no interactive IDE, and the stage tracker advances stage-by-stage, pausing only at the spec
   approval gate (3PWR-FR-006) and the sign-off gate (3PWR-FR-037).
2. **Given** a headless run paused at a human gate, **When** the developer records the decision (resume with an approver
   identity), **Then** dispatch continues from the next stage and no already-completed stage is re-dispatched.
3. **Given** commit mode, **When** each stage completes, **Then** the run stops for review at every gate, preserving the
   existing step-by-step behavior.

### User Story 2 - The oracle really runs on a different family, isolated, during the run (Priority: P1)

A developer wants the oracle authored during a run to be genuinely independent — a different model family than the
coder, unable to read the implementation — so the separation of powers holds in a live headless run and not only when
the oracle is dispatched by hand.

**Acceptance Scenarios**:

1. **Given** a run that reaches Phase A, **When** the oracle step executes, **Then** it is authored through the
   read-path-isolated headless oracle dispatch (3PWR-FR-021) under an integration whose model family differs from the
   coder's (3PWR-FR-022), and the isolation attestation (a worktree manifest hash and the proof that excluded paths were
   absent) is recorded in the signed ledger.
2. **Given** the coder and oracle integrations resolve to the same model family, **When** the run reaches the oracle
   step (or preflight), **Then** the tool refuses by default, or proceeds only under a signed, reversible deviation with
   a warning, naming that deviation path (3PWR-FR-022 via 3PWR-FR-057) — never a silent accept.
3. **Given** a High-risk run, **When** it reaches the ship advance, **Then** advance refuses unless the oracle dispatch
   isolation is attested (the require-dispatch policy) and model diversity holds, exactly as today.

### User Story 3 - A run that cannot start says why — it is never mislabeled "gates red" (Priority: P1)

A developer whose project is missing a prerequisite — the lifecycle workflow, the Spec Kit CLI, a headless coder
integration, or a different-family oracle integration — wants a plain, honest message that names the missing piece and
the fix, instead of `✗ gates red — stopped for your decision` (which never ran a gate) and a pointer to the incident
path (which is the wrong remedy).

**Acceptance Scenarios**:

1. **Given** a project missing a run prerequisite, **When** `3pwr run` starts, **Then** it fails fast **before**
   dispatching any stage, with a message naming the specific missing prerequisite and the exact next step to resolve it
   (or the fully-offline `--dry-run` and the step-by-step alternatives), and it exits with a setup/usage status distinct
   from the gate-failure status.
2. **Given** a stage's agent dispatch fails mid-run, **When** the run stops, **Then** the output identifies the stage at
   which dispatch failed and states that the failure was in dispatch/execution — not in the deterministic gate verdict —
   and it does not print "gates red" and does not route the developer to the incident/observe-signal path.
3. **Given** the deterministic gate suite actually returns fail during the Verify stage, **When** the run stops,
   **Then** (and only then) the output reports a gate-red verdict, lists the failing gates, and the tracker shows Verify
   as reached.

### User Story 4 - Auditable, reconstructable headless run (Priority: P2)

A developer wants a headless run to leave the same tamper-evident, offline-verifiable trail as a hand-driven run, so the
provenance of who (which integration/model) did what stage is recoverable after the fact.

**Acceptance Scenarios**:

1. **Given** a completed or paused headless run, **When** the developer inspects the ledger, **Then** each dispatched
   stage recorded its integration and resolved model as a provenance entry, and the run status and ledger verification
   reconstruct the run offline.
2. **Given** a headless run and an otherwise-identical step-by-step run of the same approved spec, **When** their
   verdicts are compared, **Then** the verdict bytes are identical (dispatch is a delivery mechanism, not a source of
   verdict variance).

### Edge Cases

- **Spec Kit CLI absent.** Preflight reports it as a setup failure with the existing install guidance — not "gates red"
  (reuses the current `specify`-not-found message, reclassified as a setup/prerequisite failure).
- **Lifecycle workflow absent (not provisioned by INITX).** Preflight names the missing workflow and points to the
  setup/init step that provisions it (cross-ref INITX); it never fabricates the workflow.
- **Only one model family / integration available.** Diversity is recommended, not forced: the tool warns and names the
  signed, reversible deviation path (3PWR-FR-057/022); the oracle still runs read-path-isolated, under the same family,
  with a recorded deviation. It never walls the developer off and never silently drops the requirement.
- **An IDE-only integration is selected for a headless run.** It is detected as not headless-dispatchable; the tool
  explains this and names a headless alternative, rather than shelling out and failing opaquely.
- **`--dry-run`.** The simulated path dispatches nothing, requires neither the workflow nor an integration nor the
  network, and is always available offline; preflight-failure guidance names it.
- **Human rejects at a gate.** The run aborts cleanly (existing on-reject behavior); no ship, no advance.
- **Resume after a gate.** The run continues from the paused stage; completed stages are not re-dispatched.
- **Mid-run dispatch failure.** Partial progress and its attestations are preserved in the ledger; a subsequent run
  resumes from the last completed stage rather than restarting.
- **Non-interactive / CI.** Prompts degrade to documented defaults and the run's status and failures are emitted in
  machine-readable form (ref ONBRD-NFR-003).

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable and carries an
  *Acceptance* line — the oracle (Phase A) is authored from these alone. A **Property** is added where input is
  parsed/validated/transformed (3PWR-FR-024). No implementation detail here (3PWR-FR-007): no named integration vendor,
  workflow filename, config key, or subprocess flag — those are decided at plan time.
-->

### Functional Requirements

#### Headless executive dispatch

- **RUNX-FR-001**: When run live, the system shall dispatch each executive stage (specify, clarify, plan, tasks,
  implement) to a headless, non-interactive coder integration through the Spec Kit substrate, requiring no interactive
  IDE, so the lifecycle proceeds unattended between human gates.
  - *Acceptance*: with a headless coder integration configured, a live auto run advances through every executive stage
    without an IDE session, producing that stage's expected artifact before proceeding.
- **RUNX-FR-002**: The system shall itself make no model or agent API call; all agent work shall be dispatched through
  the Spec Kit substrate (3PWR A3).
  - *Acceptance*: with the engine process's own outbound network disabled, a live run performs no model call from the
    engine; any agent traffic originates from the dispatched substrate, not the engine.
- **RUNX-FR-003**: In auto mode the system shall auto-continue past intermediate review gates and shall always stop at
  the two mandatory human gates — spec approval (3PWR-FR-006) and sign-off (3PWR-FR-037); in commit mode it shall stop
  at every gate.
  - *Acceptance*: an auto run stops exactly at review-spec and sign-off; a commit run stops at every gate; no flag or
    mode causes either mandatory gate to be skipped.
  - *Property*: for any mode, the set of stops always includes both mandatory human gates.
- **RUNX-FR-004**: After a human gate decision is recorded, the system shall resume headless dispatch from the paused
  stage without re-executing any already-completed stage.
  - *Acceptance*: resuming after spec approval continues at the plan stage; no completed stage is dispatched a second
    time.
  - *Property*: the count of dispatches for any stage across a run and its resumes never exceeds one successful
    dispatch per stage.

#### Oracle independence within a run

- **RUNX-FR-005**: When a run reaches Phase A, the system shall author the oracle through the read-path-isolated headless
  dispatch (3PWR-FR-021), under an integration whose model family differs from the coder's (3PWR-FR-022).
  - *Acceptance*: the oracle step runs via the isolated worktree dispatch under a different-family integration; the
    implementation, plan, tasks, and contracts are absent from the oracle's working tree.
  - *Property*: the model family recorded for the oracle dispatch never equals the coder integration's family unless a
    signed diversity deviation is present in the ledger.
- **RUNX-FR-006**: When the coder and oracle integrations resolve to the same model family, the system shall apply the
  diversity policy — refuse by default, or proceed under a signed, reversible deviation with a warning — never silently
  proceeding (3PWR-FR-022/057).
  - *Acceptance*: same-family resolution without a deviation stops the run and names the deviation path; with a recorded
    deviation the run proceeds and emits the warning.
- **RUNX-FR-007**: The system shall record, for each dispatched stage, a provenance entry in the signed ledger naming
  the stage, the integration, and the resolved model; and for the oracle step, the isolation attestation (the worktree
  manifest hash and the excluded-absent proof) exactly as the delivered oracle dispatch does.
  - *Acceptance*: after a run the ledger carries one provenance entry per dispatched stage plus the oracle isolation
    attestation, and the offline ledger verification validates the chain.
  - *Property*: every provenance entry is bound into the same hash-chained, signed ledger as the run's verdict, so
    removing or altering one is detectable by verification.
- **RUNX-FR-008**: At the High-risk tier, the ship advance shall continue to refuse unless the oracle dispatch isolation
  is attested (the require-dispatch policy) and model diversity holds; a live headless run shall relax no independence
  check (3PWR-FR-020/021/022/062).
  - *Acceptance*: a High-risk run whose oracle isolation is not attested is refused at advance with the existing reason;
    attested isolation plus diversity permits advance.

#### Honest orchestration diagnostics & preflight

- **RUNX-FR-009**: Before dispatching any stage, the system shall verify the run prerequisites — the lifecycle workflow
  present, the Spec Kit CLI available, a headless coder integration available, and a different-family oracle integration
  available — and, when any is missing, fail fast with a message naming the missing prerequisite and the exact next step
  to resolve it.
  - *Acceptance*: each missing prerequisite yields a distinct, named error carrying a fix, emitted before any stage is
    dispatched; a project that satisfies every prerequisite passes preflight without a spurious warning.
- **RUNX-FR-010**: When the lifecycle cannot start, or a stage's agent dispatch fails, the system shall report it as a
  setup/dispatch failure — naming the stage at which dispatch failed — distinct from a deterministic gate verdict, and
  shall neither present it as "gates red" nor route the user to the incident/observe-signal path.
  - *Acceptance*: a dispatch failure names the failing stage and the setup/dispatch cause and exits with a status
    distinct from the gate-failure status; no "gates red" text and no incident-signal suggestion is emitted for a
    non-verdict failure.
  - *Property*: the "gates red" verdict message is emitted only when the deterministic gate suite (the Verify stage)
    actually returned fail.
- **RUNX-FR-011**: When the deterministic gate suite returns fail during Verify, the system shall report a gate-red
  verdict identifying the failing gate(s), and the run stage tracker shall show the stages actually reached.
  - *Acceptance*: a real gate failure lists the failing gate(s) and shows Verify as reached; the tracker never renders
    every stage as unstarted when at least one stage completed.
  - *Property*: the tracker's rendered progress is a monotonic function of the stages actually completed in the run.
- **RUNX-FR-012**: The system shall always offer a fully-offline path — a simulated dry-run that dispatches nothing, and
  the documented step-by-step slash-command flow — and shall name these in preflight-failure guidance.
  - *Acceptance*: the dry-run completes offline with no dispatch on any project; every preflight-failure message names
    the dry-run and the step-by-step alternatives.

### Non-Functional Requirements

- **RUNX-NFR-001**: The verdict bytes and any machine-readable run output shall be identical whether the stages were
  dispatched headlessly or driven step-by-step (ref 3PWR-NFR-001) — dispatch is a delivery mechanism, not a source of
  verdict variance.
  - *Acceptance*: the verdict produced by a headless run and a step-by-step run of the same approved spec over the same
    code is byte-for-byte identical.
- **RUNX-NFR-002**: A headless run shall be offline-reconstructable and tamper-evident — every dispatched stage and every
  gate verdict is recorded in the signed, hash-chained ledger and re-verifiable offline (ref 3PWR-NFR-004/010).
  - *Acceptance*: after a run, ledger verification succeeds offline and fails if any run entry is altered, reordered, or
    removed.
- **RUNX-NFR-003**: The flow shall not weaken, remove, or bypass any gate, any risk-tier threshold, or either mandatory
  human gate (ref 3PWR-FR-032/042/006/037).
  - *Acceptance*: no threshold is lowered by the flow; headless dispatch never removes the two mandatory human gates.
- **RUNX-NFR-004**: Preflight and dispatch shall degrade gracefully — an unavailable integration, a missing CLI, or an
  absent workflow shall never surface as an unhandled crash; each yields an actionable message and a clean non-zero exit
  (ref 3PWR-FR-034).
  - *Acceptance*: inducing each failure mode produces a readable, actionable message and a clean non-zero exit, never a
    stack trace as the primary output.
- **RUNX-NFR-005**: The engine shall remain model-, provider-, and integration-agnostic — no coder or oracle integration
  is hardcoded; the set of acceptable headless integrations is configuration-driven (ref 3PWR-NFR-007).
  - *Acceptance*: changing the configured integrations changes which integrations the run accepts, with no engine code
    change; no integration name is embedded in the engine's logic.

## Success Criteria *(mandatory)*

- **RUNX-SC-001**: On a provisioned project with a headless coder integration and a different-family oracle integration,
  a single `3pwr run "<intent>" --mode auto` drives every executive stage via real agents and stops only at the two
  human gates — no IDE required.
- **RUNX-SC-002**: A run's oracle step is authored under a different model family than the coder, read-path-isolated,
  with the isolation attested in the signed ledger; a same-family resolution is refused or proceeds only under a
  recorded deviation.
- **RUNX-SC-003**: A project missing any run prerequisite receives, before any dispatch, a named prerequisite and a fix
  — never "gates red" and never an incident-signal suggestion.
- **RUNX-SC-004**: "Gates red" appears only when the deterministic gate suite actually failed; a dispatch or setup
  failure is reported distinctly and names the stage reached.
- **RUNX-SC-005**: A completed or paused headless run is fully reconstructable offline (run status and ledger
  verification), with per-stage provenance for who did what.
- **RUNX-SC-006**: A High-risk headless run cannot advance unless the oracle isolation is attested and model diversity
  holds.
- **RUNX-SC-007**: Every functional requirement has ≥1 linked verification across the appropriate layers
  (3PWR-FR-030/065) — a behavioral test for preflight/diagnostics/dispatch-orchestration logic, or a recorded review
  plus a structural check where a live end-to-end dispatch cannot be exercised deterministically in the suite.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id RUNX --stage spec`; appended to the signed ledger)_ | | |
