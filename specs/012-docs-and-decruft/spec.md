# Feature Specification: Docs Truth-Up & De-cruft — Rewrite STATUS for the Native Executive, Sweep Residual Spec-Kit Prose, Retire `agentpins`, and Relocate the `.specify/` Residue

**Spec ID**: DOCX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     DOCX is the documentation + cleanup counterpart to EXEC (spec 009) and SLIM (spec 010). EXEC gave
     3Powers a native executive; SLIM removed GitHub Spec Kit. Those landed with the headline docs fixed
     but the narrative docs (especially docs/STATUS.md) still describe the old Spec-Kit dispatch, and two
     vestigial artifacts remain: the `agentpins` module (which pins a model into `.github/agents/3pwr.*`
     files that no substrate reads anymore) and a kept `.specify/` tree (constitution + templates). DOCX
     makes every document tell the truth and removes the last Spec-Kit-shaped residue. Cross-refs:
     EXEC-*, SLIM-*, 3PWR §17 (phasing), ONBRD/INITX (init). No trust-spine change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: mostly documentation (Cosmetic in isolation), but it also removes/relocates code and config
     — retiring the `agentpins` module and moving the constitution + templates out of `.specify/` into
     3Powers-owned paths, which touches the readers (`scaffold.constitution_path`/`is_threepowers_constitution`
     /`seed_constitution`/`readiness`) and their tests. It changes no gate, verdict, ledger, or signing.
     The regression risk is a dangling reference, bounded by the acceptance that the full suite + type/lint
     gates stay green. Standard applies; a maintainer may treat the pure-docs slice as Cosmetic. -->

**Status**: Draft

**Input**: Follow-up to EXEC (spec 009) + SLIM (spec 010). SLIM fixed the load-bearing Spec-Kit claims but
left residue: `docs/STATUS.md` — the single source of implementation status — still narrates the Spec-Kit
`workflow run` dispatch as the executive; scattered Spec-Kit mentions remain across `README.md`,
`CLAUDE.md`, and `AGENTS.md`; the `agentpins` module still renders judiciary model pins into
`.github/agents/3pwr.*.agent.md` files that nothing dispatches anymore; and a `.specify/` tree lingers
(kept in SLIM for the constitution + spec/plan/tasks templates). This spec truths-up the docs and removes
the last Spec-Kit-shaped residue so a newcomer's mental model matches the code.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What changed just before this spec:** EXEC (spec 009, plan 018) added the native executive
  (`engine/src/threepowers/{runner,agents,prompts}.py`, `3pwr run --runner native|sim`). SLIM (spec 010,
  plan 019) deleted GitHub Spec Kit — see [`plan/019-remove-speckit.md`](../../plan/019-remove-speckit.md)
  and [`docs/migration-remove-speckit.md`](../../docs/migration-remove-speckit.md).
- **STATUS is special:** `docs/STATUS.md` is declared "the only home of implementation status." It currently
  carries a temporary pivot banner (added by SLIM) but its §17 matrix body still describes the Spec-Kit
  dispatch. This spec rewrites it to reflect EXEC/SLIM as the current milestone (plans 001–019).
- **`agentpins`:** `engine/src/threepowers/agentpins.py` renders `model: <label> (<integration>)` frontmatter
  into `.github/agents/3pwr.oracle.agent.md` / `3pwr.review.agent.md`. Under Spec Kit these agent files were
  dispatched; now they are only manual/IDE prompts. Decide: retire `agentpins` entirely, or keep it as an
  explicitly-optional convenience. Tests: `engine/tests/test_init_experience.py` covers the pin rendering.
- **`.specify/` residue:** SLIM kept `.specify/memory/constitution.md` and `.specify/templates/`. Readers:
  `scaffold.constitution_path`, `is_threepowers_constitution`, `seed_constitution`, `readiness`, and
  `_resolve_spec` no longer uses `.specify/feature.json`. Relocate the constitution + templates under a
  3Powers-owned path (e.g. `.3powers/`) so no `.specify/` directory remains, updating those readers + tests.
- **Guardrail:** this is truth-up + removal. Change no gate/verdict/ledger behavior; keep the engine green
  under its own gates (`ruff`/`mypy`/`pytest`, and the self-application `3pwr gate run --path engine`).

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** change any deterministic gate, risk-tier threshold, ledger format, schema, signing, verify,
  or oracle-independence logic. It is documentation + removal only.
- Does **not** re-introduce Spec Kit, nor alter the native executive delivered by EXEC/SLIM.
- Does **not** rewrite the spec's *law* (the epic assumptions) — A1′/A3′/§16 were already amended by EXEC.
- Does **not** invalidate existing signed ledgers, sealed specs, or historical plan documents (they are a
  record of what happened and stay as-is; only forward-looking docs are truthed-up).
- Does **not** remove the spec/plan/tasks authoring templates or the 3Powers constitution — it *relocates*
  them to a 3Powers-owned path and keeps them functional.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - STATUS tells the current truth (Priority: P1)

A newcomer reading `docs/STATUS.md` — the declared single source of implementation status — wants it to
describe the native executive and the absence of Spec Kit as the current state, so their mental model
matches the code from the first read.

**Acceptance Scenarios**:

1. **Given** the rewritten STATUS, **When** a newcomer reads the executive section and the phasing table,
   **Then** it describes `3pwr run` driving headless agents natively (EXEC) and Spec Kit as removed (SLIM),
   with plans 001–019 reflected and the temporary pivot banner replaced by the settled description.
2. **Given** the rewritten STATUS, **When** they search it for a claim that Spec Kit is required, **Then**
   there is none.

### User Story 2 - No document presents Spec Kit as a dependency (Priority: P1)

A reader of the top-level docs wants no residual statement that 3Powers depends on or is layered on Spec
Kit, so the stated architecture is consistent everywhere.

**Acceptance Scenarios**:

1. **Given** README, CLAUDE, AGENTS, and STATUS, **When** searched for "Spec Kit"/"specify", **Then** any
   remaining mention is explicitly historical or clearly-marked optional interop — never a required
   dependency or lifecycle step.

### User Story 3 - The last Spec-Kit-shaped residue is gone (Priority: P2)

A maintainer wants the vestigial `agentpins` behavior resolved and the `.specify/` tree gone, so nothing
Spec-Kit-shaped lingers and the constitution + templates live under a 3Powers-owned path.

**Acceptance Scenarios**:

1. **Given** the codebase after DOCX, **When** a maintainer inspects it, **Then** either `agentpins` is
   removed (and its callers/tests with it) or it is retained only behind an explicitly-documented optional
   path — decided and recorded, not left ambiguous.
2. **Given** the codebase after DOCX, **When** a maintainer looks for `.specify/`, **Then** it no longer
   exists: the constitution and the spec/plan/tasks templates have been relocated under a 3Powers-owned
   path and every reader points there.
3. **Given** the relocation, **When** `3pwr init` runs, **Then** it seeds the constitution (and templates,
   if seeded) at the new path, and readiness reports the constitution correctly.

### Edge Cases

- A repository still has an old `.specify/` from before SLIM → the migration note (SLIM-FR-008) already
  covers what is safe to delete; DOCX does not delete a user's workspace, only the engine's own tree and
  its readers.
- A user hand-edited a `3pwr.*` agent pin → if `agentpins` is retained, its non-clobber behavior is
  preserved; if removed, the files are left untouched (they become plain prompts).
- Historical plan docs (`plan/001`…`plan/017`) mention Spec Kit → left as-is (they are a record); only
  forward-looking docs are truthed-up.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable with an
  *Acceptance* line. Acceptances here are largely truth/absence checks (a search finds no required-dependency
  claim; a path no longer exists; the suite stays green). No implementation detail in the normative text
  beyond naming the artifacts being removed/relocated, which are the subject of the feature.
-->

### Functional Requirements

- **DOCX-FR-001**: The system's status document (`docs/STATUS.md`) shall be rewritten to describe the native
  executive (EXEC) and the removal of Spec Kit (SLIM) as the current milestone, reflecting plans 001–019,
  and shall no longer narrate a Spec-Kit dispatch as the executive.
  - *Acceptance*: STATUS describes `3pwr run` as native headless dispatch, lists SLIM as delivered, carries
    no "Spec Kit required" claim, and the temporary pivot banner is replaced by the settled description.
- **DOCX-FR-002**: The forward-looking top-level docs (README, contributor/agent guidance, CLAUDE) shall
  carry no statement that Spec Kit is a dependency or a required lifecycle step; any surviving mention shall
  be explicitly historical or optional interop.
  - *Acceptance*: a documentation review finds no required-dependency Spec-Kit claim in these files.
- **DOCX-FR-003**: The system shall resolve the `agentpins` module explicitly — removed (with its callers
  and tests) or retained only behind a documented optional path — with the decision recorded; no ambiguous
  vestige shall remain.
  - *Acceptance*: `agentpins`' status is decided and documented; if removed, no import or caller references
    it and the suite is green; if retained, its optional nature is documented and tested.
- **DOCX-FR-004**: The system shall relocate the 3Powers constitution and the spec/plan/tasks templates from
  `.specify/` to a 3Powers-owned path, update every reader accordingly, and leave no `.specify/` directory
  created or read by the engine.
  - *Acceptance*: after `3pwr init` there is no engine-created `.specify/`; the constitution and templates
    exist at the new path; `readiness`/constitution checks and `_resolve_spec` read the new location.
  - *Property*: no engine code path references a `.specify/` path.
- **DOCX-FR-005**: `3pwr init` shall seed the constitution (and any seeded templates) at the new
  3Powers-owned path, non-destructively (never clobbering a hand-edited file), consistent with the existing
  onboarding contract (ONBRD-FR-008/015).
  - *Acceptance*: a fresh init seeds the constitution at the new path; a re-run keeps a customized one.

### Non-Functional Requirements

- **DOCX-NFR-001**: The change shall alter no gate result, verdict bytes, ledger, or signing behavior; the
  engine self-application gate run stays green across DOCX (ref 3PWR-NFR-006).
  - *Acceptance*: the engine's own gate run and `ruff`/`mypy`/`pytest` stay green with no threshold lowered.
- **DOCX-NFR-002**: No runtime code path shall reference `.specify/` or a Spec-Kit CLI after DOCX; a
  repository-wide search of engine source returns none (extends SLIM-NFR-001).
  - *Acceptance*: the search returns zero engine-runtime matches (fixtures asserting the absence excepted).
- **DOCX-NFR-003**: Documentation edits shall be deterministic and self-consistent — links resolve, and the
  status document remains the single source of implementation status (ref the STATUS invariant).
  - *Acceptance*: internal doc links resolve; no other document duplicates the implementation-status matrix.

## Success Criteria *(mandatory)*

- **DOCX-SC-001**: `docs/STATUS.md` reads as the current truth — native executive, Spec Kit removed, plans
  001–019 — with no Spec-Kit-required claim and no leftover pivot banner.
- **DOCX-SC-002**: No forward-looking document presents Spec Kit as a dependency or a required step.
- **DOCX-SC-003**: `agentpins` is resolved (removed or documented-optional) and the `.specify/` tree no
  longer exists; the constitution + templates live under a 3Powers-owned path with every reader updated.
- **DOCX-SC-004**: `3pwr init`, the full test suite, and the engine self-application gate stay green; no
  gate, verdict, or ledger behavior changed.
- **DOCX-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a
  truth/absence test (a path is gone; a search returns nothing; init seeds the new location) or a recorded
  documentation review where an absence is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id DOCX --stage spec --spec specs/012-docs-and-decruft/spec.md`; appended to the signed ledger)_ | | |
