# Feature Specification: Remove the Spec Kit Substrate — Sever the Runtime Dependency and Prune Vendored Artifacts

**Spec ID**: SLIM
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     SLIM is the cleanup counterpart to EXEC (spec 009): once the native executive runner is the default
     and green, SLIM removes GitHub Spec Kit as a runtime dependency and prunes the vendored artifacts and
     configuration that only existed to serve it. SLIM is **sequenced strictly after EXEC lands** — the old
     substrate runner cannot be removed until the native runner replaces it. SLIM makes no trust-spine
     change; it deletes and rewires dispatch/config/docs only. It relies on the epic amendments already
     legislated by EXEC (Substrate line, A1′, A3′, §16). Cross-refs are to 3PWR-*, EXEC-*, RUNX-*, INITX-*.
     -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: SLIM is removal and decoupling of orchestration, configuration, and documentation. It
     introduces no new trust-spine primitive and changes no gate, ledger, verify, or oracle-independence
     logic — those modules are untouched and remain governed at High-risk in their own right. The risk it
     carries is regression (a removed path that was still load-bearing), which is bounded by the acceptance
     that the full suite and a live native run pass with the Spec Kit CLI absent. Per spec §4 this is
     config/orchestration work, so Standard applies. -->

**Status**: Draft

**Input**: User description: "Also, if some removals have to be done, write another spec to clear the repo of
not-needed dependencies or things that are not needed anymore. Remove completely Spec Kit and update the
A1/A2 spec accordingly to our newest approach."

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** re-legislate the epic assumptions — the Substrate line, A1′, A3′, and the §16 non-goals are
  amended by EXEC (spec 009). SLIM only ensures the codebase, configuration, and docs match those amended
  assumptions; it re-seals nothing on its own.
- Does **not** remove or weaken the native executive runner, its agent manifests, or its diagnostics
  (delivered by EXEC). SLIM removes the **old** Spec Kit path, not the new one.
- Does **not** change any deterministic gate, risk-tier threshold, ledger format, schema, signing, verify,
  provenance, or oracle-independence logic. The judiciary is untouched.
- Does **not** remove the spec-driven authoring discipline: the engine keeps its own lifecycle prompt
  templates (promoted by EXEC) and the 3Powers constitution/governance text. What is removed is the Spec Kit
  **dispatch substrate** and the artifacts that only served it.
- Does **not** break existing signed ledgers, sealed specs, or historical provenance; already-recorded
  entries remain valid and verifiable.
- Does **not** delete a developer's own already-initialized Spec Kit workspace on their machine as a side
  effect; SLIM removes 3Powers' *dependency on and provisioning of* Spec Kit, and documents a migration for
  repositories initialized under the old path.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The lifecycle runs with Spec Kit absent (Priority: P1)

A developer with no Spec Kit CLI installed anywhere wants the full 3Powers lifecycle — `3pwr run`, the oracle
dispatch, and every gate/trust command — to work end-to-end, so 3Powers stands on its own.

**Acceptance Scenarios**:

1. **Given** a machine with no Spec Kit CLI on PATH, **When** the developer runs `3pwr run` (dry-run and
   live) and `3pwr oracle dispatch`, **Then** both succeed with no reference to and no requirement for the
   Spec Kit CLI.
2. **Given** the engine's own test suite, **When** it runs with the Spec Kit CLI absent, **Then** it passes
   in full, including the orchestration and oracle-dispatch tests.

### User Story 2 - A lean repository, free of substrate-only artifacts (Priority: P1)

A maintainer wants the repository free of the vendored substrate prompts, workflow descriptors, and
dependency pins that only existed to serve Spec Kit, so the repo reflects the native-executive architecture.

**Acceptance Scenarios**:

1. **Given** the repository after SLIM, **When** a maintainer searches the engine source, **Then** there is
   no invocation of the Spec Kit CLI and no code path that reads a Spec Kit workflow descriptor.
2. **Given** the repository after SLIM, **When** a maintainer inspects the vendored prompt/agent files and
   the runtime workflow descriptors that only served Spec Kit dispatch, **Then** they are gone, while the
   engine-owned lifecycle prompts and the constitution remain.

### User Story 3 - Documentation and dependency manifests tell the truth (Priority: P2)

A newcomer reading the docs and dependency manifests wants them to reflect that 3Powers has its own
executive and does not depend on Spec Kit, so the stated architecture matches the code.

**Acceptance Scenarios**:

1. **Given** the top-level docs and the dependency manifests, **When** a newcomer reads them, **Then** Spec
   Kit is not listed as a dependency, a supported-version pin, or a required lifecycle step; any remaining
   mention is clearly marked as optional interop or historical.
2. **Given** the dependency-drift preflight, **When** it runs, **Then** it no longer probes for or reports on
   the Spec Kit CLI.

### Edge Cases

- **A repository was initialized under the old Spec Kit path.** A short migration note explains what is safe
  to delete and that nothing in the trust spine is affected; existing ledgers/specs remain valid.
- **A removed function or flag was still referenced elsewhere.** The full suite and the type/lint gates catch
  a dangling reference; removal is complete only when they are green.
- **The dependency-drift config no longer lists Spec Kit.** The preflight neither errors on its absence nor
  reports it as drift.
- **A stray import or subprocess reference to the substrate remains.** A repository-wide search for the Spec
  Kit CLI invocation and the substrate runner returns nothing in engine source.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable and
  carries an *Acceptance* line. SLIM is a removal spec; its acceptances are largely absence checks
  (a search returns nothing; a command works with the tool absent) and green-suite checks. No
  implementation detail in the normative text (3PWR-FR-007) beyond naming the substrate being removed,
  which is the subject of the feature.
-->

### Functional Requirements

- **SLIM-FR-001**: The system shall remove the Spec Kit substrate runner and every invocation of the Spec
  Kit CLI's workflow dispatch/resume from the orchestration and CLI layers, so no live run path depends on
  the substrate.
  - *Acceptance*: a repository-wide search of engine source finds no Spec Kit workflow-dispatch invocation
    and no substrate runner class; `3pwr run` (dry-run and live) works with the Spec Kit CLI absent.
- **SLIM-FR-002**: The system shall remove the Spec-Kit-provisioning init path and its scaffolding helpers
  (workspace init, extension install, workflow install) and shall replace any Spec-Kit-CLI presence probe in
  preflight with the native agent-availability probe (EXEC-FR-015).
  - *Acceptance*: `3pwr init` completes with no Spec Kit provisioning step; preflight reports on the native
    agent, not on the Spec Kit CLI.
- **SLIM-FR-003**: The system shall delete the vendored substrate prompt/agent files and the runtime workflow
  descriptors that only served Spec Kit dispatch, and shall route the oracle authoring leg through the native
  runner's read-path-isolated dispatch (EXEC-FR-009) rather than a Spec Kit workflow descriptor.
  - *Acceptance*: the vendored substrate prompt/agent files and the runtime workflow descriptors are absent;
    the oracle dispatch runs natively and still records the same isolation attestation.
- **SLIM-FR-004**: The system shall remove Spec Kit as a declared/supported dependency — the dependency-pin
  entry, the dependency keyword, and the drift preflight probe — so Spec Kit is neither required nor
  reported.
  - *Acceptance*: the dependency-drift command no longer lists Spec Kit; the dependency manifests carry no
    Spec Kit pin or keyword.
- **SLIM-FR-005**: The system shall resolve each substrate-adjacent artifact explicitly as **keep** or
  **delete**: keep engine-owned lifecycle templates and the 3Powers constitution/governance text (relocating
  them under 3Powers ownership if they lived under the substrate tree); delete substrate scripts, integration
  manifests, and the substrate extension registry.
  - *Acceptance*: a documented keep/delete decision exists for every substrate-adjacent artifact; the kept
    artifacts are present and owned by 3Powers, the deleted ones are absent.
- **SLIM-FR-006**: The system shall re-express the former "Spec Kit integration" concept (including the
  headless-vs-editor-bound distinction and the family-per-backend precheck) as **agent-backend** metadata,
  preserving the model-diversity precheck (3PWR-FR-022) with no dependence on the substrate's integration
  registry.
  - *Acceptance*: the diversity precheck still resolves a backend's model family and still refuses/deviates
    on a same-family coder/oracle pairing, sourcing that metadata from agent-backend configuration rather
    than the substrate registry.
- **SLIM-FR-007**: After removal, the system shall pass its full behavior — `3pwr run`, `3pwr oracle
  dispatch`, the engine test suite, and the type/lint/format gates — with the Spec Kit CLI absent from PATH.
  - *Acceptance*: with the Spec Kit CLI uninstalled, the full suite and the type/lint/format gates are green
    and a live native run completes.
- **SLIM-FR-008**: The system shall provide a short migration note for repositories initialized under the old
  Spec Kit path, stating what is safe to delete and affirming that the trust spine, existing ledgers, and
  sealed specs are unaffected.
  - *Acceptance*: a migration note exists and correctly identifies the removable substrate artifacts and the
    unaffected trust-spine state.

### Non-Functional Requirements

- **SLIM-NFR-001**: No runtime code path shall reference the Spec Kit CLI or a Spec Kit workflow descriptor;
  a repository-wide search of engine source for the substrate CLI invocation returns nothing.
  - *Acceptance*: the search returns zero matches in engine runtime source (test fixtures that assert the
    absence excepted).
- **SLIM-NFR-002**: The top-level documentation (README, contributor/agent guidance, and the status matrix)
  shall no longer present Spec Kit as a dependency or a required lifecycle step; any surviving mention is
  explicitly optional interop or historical.
  - *Acceptance*: a docs review finds no statement that Spec Kit is required; the status matrix reflects the
    native executive.
- **SLIM-NFR-003**: The removal shall change no gate result, no verdict bytes, and no ledger/verify behavior;
  a self-application gate run over the engine before and after SLIM yields the same gate outcomes for
  unchanged code.
  - *Acceptance*: the engine's self-application gate run stays green across SLIM, with no threshold lowered.

## Success Criteria *(mandatory)*

- **SLIM-SC-001**: With the Spec Kit CLI absent from PATH, `3pwr run`, `3pwr oracle dispatch`, and the full
  engine suite all succeed.
- **SLIM-SC-002**: A repository-wide search finds no Spec Kit CLI invocation and no substrate runner in
  engine source; the vendored substrate prompts and runtime workflow descriptors are gone.
- **SLIM-SC-003**: The dependency-drift command no longer lists Spec Kit; no dependency manifest carries a
  Spec Kit pin or keyword.
- **SLIM-SC-004**: The engine-owned lifecycle templates and the constitution remain and are owned by
  3Powers; the model-diversity precheck still works, sourced from agent-backend metadata.
- **SLIM-SC-005**: Docs and the status matrix present 3Powers as having its own executive and no Spec Kit
  dependency; a migration note covers repositories initialized under the old path.
- **SLIM-SC-006**: The engine self-application gate run stays green across the removal, proving no
  trust-spine or gate behavior changed (3PWR-NFR-006).
- **SLIM-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — an
  absence/behavior test (a command succeeds with the tool absent; a search returns nothing) or a recorded
  review where an absence is asserted structurally.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id SLIM --stage spec --spec specs/010-remove-speckit/spec.md`; appended to the signed ledger)_ | | |
