# Feature Specification: Phase Orchestration Prompt — an Explicit Scope/Completion/Parallelism Contract per Phase Session, a Completed-Phases Summary, and Advisory Stall Detection

**Spec ID**: PHASEPR
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     PHASEPR hardens the per-phase dispatch prompt PHASE (013) introduced: today the phase handoff
     names the phase and its tasks but does not carry an explicit contract, so agents re-do earlier
     phases, silently skip tasks.md completion markers, or end a headless session with a clarifying
     question nobody sees (the process exits, the engine records the session as complete). PHASEPR
     makes the prompt an explicit scope/completion/parallelism contract, injects a one-line summary
     of the phases already completed, and adds an advisory transcript scan that warns — never blocks
     — when a phase session appears to have ended on an unanswered question. Cross-refs:
     PHASE-FR-010/011/012, 3PWR-FR-060/061, AUTOX-FR-008. Executive prompt plumbing only; no
     trust-spine module (canonical/keys/ledger/verify) is changed, no new ledger entry type, and no
     gate or verdict change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Rationale: this is
     executive prompt text plus an advisory, read-only transcript scan. No trust-spine module is
     touched, no gate is weakened (3PWR-FR-032), and the stall warning by construction cannot alter
     run control flow. Cosmetic was rejected: the prompt contract drives what a phased implement
     stage does to the working tree, so its determinism and its never-blocking property must hold
     under test. High-risk was rejected: no trust-spine change. Standard applies — the same
     latitude PHASE (013) used for the phase mechanics themselves. -->

**Status**: Draft

**Input**: Plan 030, Track F (PHASEPR): the phase prompt in the phased implement dispatch sends the
tasks artifact and phase number but does not clearly instruct the agent to (a) implement only the
declared phase, (b) mark tasks completed in `tasks.md`, (c) treat `[P]`-marked tasks as runnable in
parallel via subagents; and a session that ends by asking a question is recorded as complete with
the question unseen.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change how phases are parsed, estimated, scheduled, or executed — batching,
  disjoint-scope concurrency, deterministic result ordering, and the single post-collection ledger
  append all stay PHASE's (PHASE-FR-010/011/012, PHASE-NFR-003).
- Does **not** add any enforcement of the prompt contract: file-scope adherence and completion
  markers are instructions to the agent, verified downstream by the existing gates — no new
  blocking check is introduced.
- Does **not** make stall detection a gate, a retry trigger, or an exit-code input: it is a warning
  on the terminal and nothing else; control flow, ledger content, and exit codes are unchanged.
- Does **not** interpret transcripts semantically — detection is a fixed, deterministic pattern
  match over the transcript tail, no model call (3PWR-NFR-001).
- Does **not** change the transcript sink, its redaction, or its layout (AUTOX-FR-008/NFR-002);
  the scan only reads what the sink already persisted.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Each phase session receives an explicit contract (Priority: P1)

An operator running a phased implement stage wants every phase's fresh session told exactly what it
may do — only this phase's tasks, only this phase's declared files, `[P]` tasks in parallel via
subagents, completion markers written back to `tasks.md`, no questions to an operator who is not
there — so phases neither redo earlier work nor leak outside their scope.

**Acceptance Scenarios**:

1. **Given** a 3-phase tasks artifact, **When** phase 2's session is dispatched, **Then** its
   prompt states the scope contract (only the tasks under `## Phase 2`, no files outside the
   declared scope, no tasks from other phases), the `[P]` concurrency instruction, and the
   completion-marker instruction (`[x]` done, `[!]` plus a one-line reason when blocked).
2. **Given** the same dispatch, **When** the prompt is rendered, **Then** it carries the line
   `Phases already completed: Phase 1 (<phase 1's name>)`.
3. **Given** phase 1 of any run, **When** its prompt is rendered, **Then** the completed-phases
   line reads `none` (nothing is invented).

### User Story 2 - A session that ends on a question is surfaced (Priority: P2)

An operator whose headless phase session printed `Could you clarify the button label?` and exited
wants a visible warning pointing at the transcript — while the run itself continues exactly as it
would have, because the warning is advisory.

**Acceptance Scenarios**:

1. **Given** a phase session whose transcript tail ends with `Could you clarify the button
   label?`, **When** the session ends, **Then** the engine prints an advisory warning naming the
   phase and pointing at the transcript via the run's `--status` hint with the real spec id.
2. **Given** a phase session whose transcript tail ends with a fenced code block, **When** the
   session ends, **Then** no warning is printed.
3. **Given** a detected possible question, **When** the run proceeds, **Then** the stage outcome,
   ledger entries, and the run's exit code are identical to the no-warning case.

### Edge Cases

- A transcript that is missing or unreadable → the scan silently does nothing (advisory means no
  new failure mode).
- An empty transcript tail → no match, no warning.
- A `?` earlier in the tail followed by a fenced code block → not a stall; the session produced
  work after the question.
- A single-phase (degenerate, unphased) implement run → no phase prompt is rendered; nothing here
  applies (PHASE's degenerate case is unchanged).

## Requirements *(mandatory)*

### Functional Requirements

- **PHASEPR-FR-001**: The per-phase dispatch prompt shall state an explicit scope contract: the
  session implements only the tasks listed under its `## Phase {N}` heading, shall not modify
  files outside the phase's declared file scope, and shall not perform tasks from other phases.
  - *Acceptance*: the rendered prompt for phase 2 of 3 contains all three scope clauses naming
    phase 2.
  - *Property*: the rendered prompt is a pure, deterministic function of the phase, the phase
    count, the run's spec id, the constitution text, and the completed-phases summary
    (PHASE-NFR-001 carried forward).
- **PHASEPR-FR-002**: The per-phase dispatch prompt shall instruct that tasks marked `[P]` within
  the phase may be dispatched concurrently via subagents, collecting their results before
  proceeding.
  - *Acceptance*: the rendered prompt contains the `[P]` concurrency instruction.
- **PHASEPR-FR-003**: The per-phase dispatch prompt shall instruct the completion-marker contract:
  every finished task is marked `[x]` in `tasks.md`; a task that cannot be completed is marked
  `[!]` with a one-line reason appended; and the session shall never ask the operator questions —
  when something is unclear it makes the most reasonable decision and documents the assumption in
  a code comment, not in `tasks.md`. The tasks-stage agent instruction shall describe the same
  marker contract, so the artifact and the prompt agree.
  - *Acceptance*: the rendered prompt contains the `[x]`/`[!]` instruction and the no-questions
    instruction; the tasks-stage template names the same `[x]`/`[!]` markers.
- **PHASEPR-FR-004**: Before dispatching phase N, the system shall inject into the prompt a
  one-line summary of the phases already completed, built from the headings of phases 1..N-1 in
  the tasks artifact (e.g. `Phase 1 (HeaderComponent styles), Phase 2 (ButtonComponent)`); for
  phase 1 the line shall read `none`.
  - *Acceptance*: phase 3's prompt lists phases 1 and 2 by number and name; phase 1's prompt says
    `none`.
  - *Property*: the summary is a pure function of the parsed phase list and the current phase's
    index — deterministic, offline.
- **PHASEPR-FR-005**: After a phase session ends, the system shall scan the last 500 bytes of the
  session's persisted transcript for unanswered-question patterns — case-insensitive: a trailing
  `?` with no subsequent fenced code block, `I need clarification`, `Could you clarify` — and on a
  match emit an advisory warning naming the phase and pointing at the transcript via the run's
  `--status` hint carrying the run's real spec id. The warning shall never alter control flow:
  no retry, no failure, no exit-code change, no ledger change.
  - *Acceptance*: a transcript tail ending `Could you clarify the button label?` triggers the
    warning; a tail ending with a fenced code block does not; in both cases the run's outcome and
    exit code are identical.
  - *Property*: the match is a pure predicate over the tail text; a missing or unreadable
    transcript yields no warning and no error.

### Non-Functional Requirements

- **PHASEPR-NFR-001**: Prompt rendering, the completed-phases summary, and stall detection shall
  be deterministic and fully offline — no model call, no network — and shall never enter the
  deterministic verdict computation (ref 3PWR-NFR-001).
  - *Acceptance*: identical inputs yield identical prompts and identical detection outcomes with
    networking disabled.
- **PHASEPR-NFR-002**: The stall scan shall be strictly advisory: it shall not raise, block,
  retry, or change any exit code, stage outcome, or ledger content (ref PHASE-NFR-002's advisory
  discipline).
  - *Acceptance*: a run with a detected question and the same run without it produce identical
    stage results and exit codes.

## Success Criteria *(mandatory)*

- **PHASEPR-SC-001**: Phase 2 of a 3-phase run receives a prompt carrying the scope contract, the
  `[P]` concurrency instruction, the completion-marker contract, and the phase-1 summary line.
- **PHASEPR-SC-002**: `tasks.md` checkbox instructions and the phase prompt name the same markers:
  `[x]` done, `[!]` plus reason when blocked.
- **PHASEPR-SC-003**: A session ending with a clarifying question produces a visible warning with
  the real spec id in its hint; the run continues unchanged.
- **PHASEPR-SC-004**: `[P]`-marked phases with disjoint scopes still dispatch concurrently
  (PHASE-FR-011 unchanged, existing concurrency verification stays green).
- **PHASEPR-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) —
  a test naming the PHASEPR-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id PHASEPR --stage spec --spec specs/025-phase-prompt/spec.md`; appended to the signed ledger)_ | | |
