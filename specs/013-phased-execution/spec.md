# Feature Specification: Phased Execution — Context-Sized Phases, a Per-Stage Artifact Workspace, Fresh Sessions per Phase, and Parallel Subagent Dispatch

**Spec ID**: PHASE
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     PHASE delivers the context strategy the epic already demands (3PWR-FR-060/061, both open in
     docs/STATUS.md) and the AI-First SDD Playbook's session LAWs ("work in sessions sized to the
     model's context"; "each artifact is a context boundary — start a fresh session at each handoff").
     It extends EXEC (spec 009, the native executive) and RUNLIVE (spec 011, per-stage artifact
     contracts): the plan/tasks stages get real prompts and hard artifact contracts, every stage's
     output lands in a versioned per-feature workspace, plans decompose work into context-budgeted
     phases, and the executive runs each phase as an independent fresh session — in parallel where
     file scopes are disjoint. Cross-refs: EXEC-*, RUNLIVE-FR-003, SLIM/DOCX (template relocation),
     3PWR §6 (lifecycle), §17 (phasing). No trust-spine change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this changes orchestration (prompt assembly, stage artifact contracts, phase scheduling),
     templates, and config — not the trust-spine modules (canonical/keys/ledger/verify), which are only
     written to through their existing APIs. It weakens no gate (3PWR-FR-032): artifact acceptance gets
     STRICTER (plan/tasks gain contracts) and the context budget is advisory-only. The regression risk is
     an orchestration fault (a stage prompt losing its inputs; parallel phases colliding), bounded by
     determinism requirements below and the engine's own gates staying green. Standard applies; a
     maintainer may escalate the parallel-dispatch slice to High-risk if ledger-ordering doubts arise. -->

**Status**: Draft

**Input**: Follow-up to EXEC (spec 009) + RUNLIVE (spec 011), triggered by a completeness review of the
shipped executive content against the AI-First SDD Playbook (`landing/`). The judiciary prompts
(`.github/agents/3pwr.*.agent.md`) are strong, but the executive's planning content is not: the native
`plan`/`tasks` stage prompts are one sentence each and name no output artifact; `plan`/`tasks` have no
artifact contract, so a stage producing no file still passes; `3pwr run` never injects the approved spec
text, prior-stage context, or task file scope into later stage prompts; and the plan/tasks templates
split work by user story only — no context budget, no session sizing, no subagent delegation, plus stale
Spec-Kit references. The playbook's session LAWs and the epic's 3PWR-FR-060/061 therefore have no
counterpart in the shipped content. This spec closes that gap.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **Where the gap lives:** `engine/src/threepowers/prompts.py` (the `plan` and `tasks` stage bodies are
  single sentences; `assemble()` already supports APPROVED SPEC / PRIOR CONTEXT / FILE SCOPE blocks but
  the run path never passes them — see `cli.py` `_native_runner` and `runner.py` `CliAgentRunner`);
  `engine/src/threepowers/artifacts.py` (`STAGE_ARTIFACTS` covers only `specify`/`oracle`/`implement`;
  `plan`/`tasks` fall to RUNLIVE-FR-003's lenient acceptance); `.3powers/templates/{plan,tasks}-template.md`
  (user-story decomposition inherited from Spec Kit; no sizing or delegation guidance; residual
  `/speckit.*` mentions that DOCX's sweep did not reach).
- **The playbook's LAWs this delivers:** work in sessions sized to the model's context; split large work
  into separate sessions per coherent chunk and reload the spec and rules at the start of each; each
  committed artifact is a context boundary — never one long conversation across the whole feature; the
  executive may delegate coherent chunks to dedicated subagents.
- **What the epic already says:** 3PWR-FR-060 (deliberate context strategy — what stays in context, what
  is summarized, what is reloaded per task) and 3PWR-FR-061 (fresh session at configurable thresholds)
  are both marked open in `docs/STATUS.md` ("context strategy approximated at command level").
- **Why ~110k tokens:** a practical fill indicator for today's common context windows, at which model
  performance is still dependable. It is a *default*, per-model-configurable, and advisory — a good
  indicator, not a hard rule.
- **The workspace shape (user decision):** each feature gets one folder holding a `spec/` subfolder for
  the legislative artifact and a sibling folder for every other stage's artifact, so that *all* stages —
  driven by `3pwr run` or manually — leave a versioned, checkable output. For now only the spec lives in
  the spec folder.
- **Guardrail:** orchestration, prompts, templates, and config only. No gate, verdict schema, ledger
  format, or signing change; the engine stays green under its own gates.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** meter or govern token *spend*, billing, or provider quotas — that stays with the
  organization's gateway (per EXEC's inherited scope); the budget here bounds *session content size*.
- Does **not** count tokens exactly. Sizes are deterministic estimates from artifact bytes; no provider
  tokenizer or network call is involved.
- Does **not** block on the context budget. Exceeding it warns and advises a split — never a failed gate
  (3PWR-NFR-001 determinism; the "not a hard rule" intent).
- Does **not** migrate the existing `specs/001`–`012` directories to the new workspace layout; the layout
  applies to features created after delivery, and the legacy layout remains readable.
- Does **not** weaken any tier gate or acceptance (3PWR-FR-032) — artifact acceptance only tightens.
- Does **not** add distributed or cross-machine execution; parallel phases are local concurrent headless
  sessions.
- Does **not** change subagent *model routing* — role→family assignment stays with `roles.yaml` and the
  diversity rules (3PWR-FR-022).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plans split work into context-sized phases (Priority: P1)

A maintainer running `3pwr run` on a large intent wants the plan/tasks stages to decompose the work into
small phases, each sized so one fresh agent session (spec + rules + phase tasks + files in scope) fits
comfortably inside the configured context budget, so the executing model stays performant end to end.

**Acceptance Scenarios**:

1. **Given** a configured budget and an approved spec, **When** the tasks stage completes, **Then** the
   tasks artifact groups tasks into ordered phases, each declaring its file scope and an estimated
   context size, every estimate at or under the budget (or carrying an explicit oversize warning).
2. **Given** a phase whose estimate exceeds the budget, **When** the run reports the stage, **Then** a
   warning names the phase and its estimate, and the run proceeds (advisory, never blocking).

### User Story 2 - Every stage leaves a checked, versioned artifact (Priority: P1)

A maintainer wants each lifecycle stage — run natively or driven manually — to write its output into the
feature's workspace (a `spec/` folder for the spec; a sibling folder for all other stage artifacts) and
wants the run to fail a stage whose artifact was not created, so the committed artifact trail is the
context boundary the playbook promises.

**Acceptance Scenarios**:

1. **Given** a completed `3pwr run` over a new feature, **When** the maintainer inspects the feature's
   folder, **Then** the spec sits in the spec subfolder and every other action stage's artifact
   (plan, tasks, …) sits in the artifacts folder, all committed to git.
2. **Given** a dispatch that returns success but wrote no artifact, **When** the stage is accepted,
   **Then** the stage is marked failed with an actionable message naming the missing artifact path.

### User Story 3 - Each phase executes as an independent fresh session (Priority: P1)

A maintainer wants the implement stage to run phase by phase, each phase as a *new* headless session
that reloads its handoff set (the approved spec, the constitution/rules, the phase's tasks and file
scope), so quality does not decay from an over-full carried context (3PWR-FR-061).

**Acceptance Scenarios**:

1. **Given** a tasks artifact with three phases, **When** implement runs, **Then** three separate
   dispatches occur, each prompt containing that phase's handoff set and no carried conversation.
2. **Given** a phase failure, **When** the run reports, **Then** the failing phase is identified and
   later phases are not silently skipped-as-passed.

### User Story 4 - Independent phases are dispatched to parallel subagents (Priority: P2)

A maintainer wants phases whose file scopes are disjoint and that declare no dependency on each other to
be dispatched to parallel subagent sessions, so a large feature completes faster without the phases
interfering — while the ledger record stays deterministic.

**Acceptance Scenarios**:

1. **Given** two phases marked parallel with disjoint file scopes, **When** implement runs, **Then** both
   are dispatched concurrently and both results are recorded in a deterministic order.
2. **Given** two phases whose declared file scopes overlap, **When** implement schedules them, **Then**
   they run sequentially regardless of a parallel marker.

### User Story 5 - The manual drive gets the same guidance (Priority: P2)

A user driving the lifecycle by hand (IDE prompts + CLI) wants the plan/tasks templates to carry the same
phase-decomposition, sizing, and delegation guidance the native prompts use, so both drives produce the
same shape of artifact.

**Acceptance Scenarios**:

1. **Given** the shipped templates, **When** a user authors a tasks artifact from them, **Then** the
   template instructs phase grouping, per-phase file scope and size estimate, a self-contained per-phase
   handoff block, and parallel markers — and contains no Spec-Kit command references.

### Edge Cases

- A phase cannot be split further (one indivisible task over budget) → the oversize warning stands and
  the run proceeds; the warning tells the planner the phase is irreducible.
- A parallel phase fails while its sibling succeeds → the stage fails, the failing phase is named, the
  sibling's completed work is not discarded silently.
- A legacy-layout feature (`specs/<f>/spec.md`, no workspace subfolders) → still resolvable and runnable;
  new artifacts follow the new layout without breaking spec resolution.
- The tasks artifact declares no phases at all → implement treats the whole task set as a single phase
  (one fresh session), preserving today's behavior as the degenerate case.
- The budget config is absent → the shipped default (~110k tokens) applies; estimates and warnings still
  work.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where an input is parsed or a value derived (3PWR-FR-024). The artifact
  paths and template names appear in normative text because they ARE the subject of the feature (the
  committed-artifact contract), not implementation detail (3PWR-FR-007).
-->

### Functional Requirements

#### Feature workspace & per-stage artifacts

- **PHASE-FR-001**: The system shall give each feature a single versioned workspace folder containing a
  `spec/` subfolder for the specification artifact and a sibling artifacts folder for every other
  lifecycle stage's output (plan, tasks, and subsequent stage artifacts), used by both the native run and
  the manual drive; features in the legacy layout (`spec.md` directly in the feature folder) shall remain
  resolvable.
  - *Acceptance*: a fresh feature ends with `…/<feature>/spec/spec.md` plus the other stages' artifacts
    in the sibling folder; a legacy-layout feature still resolves and runs.
  - *Property*: spec resolution finds exactly one specification per feature folder, whichever layout.
- **PHASE-FR-002**: When a lifecycle *action* stage completes, the system shall check that the stage's
  declared artifact exists in the feature workspace and shall mark the stage failed when it is missing —
  extending the artifact contracts to every action stage (the `plan` and `tasks` stages lose
  RUNLIVE-FR-003's lenient fallback).
  - *Acceptance*: a plan or tasks dispatch that writes no artifact is reported failed with the expected
    path named; each action stage has a declared artifact contract.
- **PHASE-FR-003**: The system shall record each accepted stage artifact's path with the stage's ledger
  entry, so the committed artifact trail is reconstructable from the signed ledger alone.
  - *Acceptance*: for a completed run, each recorded stage names its artifact path and the file exists at
    the recorded commit.

#### Prompt & template content

- **PHASE-FR-004**: The native executive's `plan` and `tasks` stage prompts shall specify the output
  artifact path, the required artifact sections, the phase-decomposition rules (ordered phases; one
  requirement per task; per-task and per-phase declared file scope; parallel markers for independent
  phases), and the context-sizing heuristic — at a depth comparable to the `specify` and `oracle` stage
  prompts.
  - *Acceptance*: the assembled plan/tasks prompts name their artifact path and required sections; a
    content review finds the decomposition and sizing rules present.
- **PHASE-FR-005**: When the native executive dispatches a stage, the system shall include in the prompt
  the approved specification text, a reference to (or digest of) the prior stage's accepted artifact, and
  — for build stages — the active phase's tasks and declared file scope, so no stage depends on the agent
  independently rediscovering its inputs.
  - *Acceptance*: for each dispatched stage after spec approval, the assembled prompt contains the spec
    content block and the prior artifact reference; implement-phase prompts contain that phase's tasks
    and file scope.
  - *Property*: prompt assembly is deterministic — identical inputs produce an identical prompt.
- **PHASE-FR-006**: The shipped plan and tasks templates shall present phases as self-contained delegable
  units — each phase carrying a handoff block naming what a fresh session must reload (the spec, the
  constitution/rules, the phase's tasks, the declared file scope) and an estimated context size — and
  shall carry no residual Spec-Kit command references.
  - *Acceptance*: the templates contain the per-phase handoff block and size line; a search of
    `.3powers/templates/` finds no `/speckit.*` reference.

#### Context budget (advisory)

- **PHASE-FR-007**: The system shall read a configurable per-model context budget from the repository's
   3Powers config, with a shipped default of approximately 110k tokens applying when unset.
  - *Acceptance*: setting a budget changes the warning threshold; with no config the default applies.
  - *Property*: budget resolution is deterministic — same config bytes, same budget.
- **PHASE-FR-008**: The system shall compute a deterministic estimated context size for each phase from
  the byte sizes of its reload set (the specification, the constitution/rules, the phase's tasks and
  prompt, and the files in its declared scope), without any network or provider-tokenizer dependency.
  - *Acceptance*: the estimate is reported per phase in the tasks artifact check and the run output.
  - *Property*: identical reload-set bytes produce an identical estimate, on any machine (3PWR-NFR-001).
- **PHASE-FR-009**: When a phase's estimated context size exceeds the budget, the system shall emit an
  advisory warning naming the phase, its estimate, and the budget, and instruct splitting the phase — and
  shall never fail a stage or gate on the budget alone.
  - *Acceptance*: an oversize phase produces the warning and the run continues; no gate result changes.

#### Fresh session per phase & parallel subagent dispatch

- **PHASE-FR-010**: When the implement stage runs a phased tasks artifact, the system shall execute
  phase by phase, dispatching each phase as a new headless session whose prompt reloads that phase's
  handoff set, carrying no conversation state between phases (delivers 3PWR-FR-061 at the engine level);
  a tasks artifact with no phases shall run as a single phase.
  - *Acceptance*: an N-phase feature produces N implement dispatches, each prompt containing only its
    phase's handoff set; the phaseless case produces one dispatch.
- **PHASE-FR-011**: The system shall dispatch phases concurrently to parallel subagent sessions only when
  the phases are marked parallel, declare no dependency on each other, and have disjoint declared file
  scopes; otherwise it shall run them sequentially in artifact order.
  - *Acceptance*: two disjoint parallel phases run concurrently; two overlapping ones run sequentially
    even when marked parallel, with the overlap reported.
  - *Property*: two phases execute concurrently only if the intersection of their declared file-scope
    sets is empty.
- **PHASE-FR-012**: The system shall record parallel phases' results in a deterministic order, and when
  any phase fails, shall fail the implement stage identifying the failing phase(s) with an actionable
  message (3PWR-FR-034) — never reporting a partially-implemented stage as passed.
  - *Acceptance*: reruns of the same outcome set record the same order; a one-of-two phase failure fails
    the stage naming the phase.

### Non-Functional Requirements

- **PHASE-NFR-001**: Phase scheduling, prompt assembly, size estimation, and budget resolution shall be
  deterministic — identical artifacts and config produce identical prompts, estimates, schedules, and
  ledger ordering on any machine (ref 3PWR-NFR-001).
  - *Acceptance*: a repeated dry run over the same tree yields byte-identical prompts and estimates.
- **PHASE-NFR-002**: The context budget shall remain strictly advisory: no gate, verdict, or advance
  decision shall depend on it, and no existing gate threshold is lowered by this feature (3PWR-FR-032).
  - *Acceptance*: gate results with and without an oversize warning are identical.
- **PHASE-NFR-003**: Parallel dispatch shall not corrupt the trust spine: ledger entries remain
  hash-chain-valid and `3pwr verify` stays green across concurrent phase completion.
  - *Acceptance*: after a parallel run, `3pwr verify` passes; entry order matches the deterministic rule.
- **PHASE-NFR-004**: The engine shall stay green under its own gates across this change, and the
  forward-looking docs (CLAUDE.md, AGENTS.md, docs/STATUS.md) shall describe the workspace layout, the
  budget, and phased dispatch at delivery (ref 3PWR-NFR-006).
  - *Acceptance*: self-application gate run + ruff/mypy/pytest green; docs review finds the new behavior
    described and 3PWR-FR-060/061 status updated.

## Success Criteria *(mandatory)*

- **PHASE-SC-001**: A native run over a multi-phase feature leaves one committed artifact per action
  stage in the feature workspace (spec in `spec/`, the rest in the artifacts folder), and a stage without
  its artifact fails.
- **PHASE-SC-002**: The plan/tasks prompts and templates carry the decomposition, sizing, handoff, and
  delegation guidance; assembled stage prompts contain the approved spec, prior artifact reference, and
  phase file scope.
- **PHASE-SC-003**: An oversize phase yields an advisory warning (never a blocked gate); estimates and
  budgets resolve deterministically.
- **PHASE-SC-004**: Implement runs one fresh session per phase, in parallel for disjoint independent
  phases, with deterministic ledger ordering and `3pwr verify` green afterwards.
- **PHASE-SC-005**: The legacy spec layout keeps working; no existing gate, verdict, ledger, or signing
  behavior changes; the engine's own gates stay green.
- **PHASE-SC-006**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test
  naming the PHASE-FR id, or a recorded documentation/content review where prose is what is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id PHASE --stage spec --spec specs/013-phased-execution/spec.md`; appended to the signed ledger)_ | | |
