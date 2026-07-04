# Feature Specification: [FEATURE NAME]

**Spec ID**: [SPECID]
<!-- A short uppercase id unique to this spec, e.g. VUTIL. Requirement IDs are namespaced with it (3PWR-FR-059). -->

**Risk Tier**: [Cosmetic | Standard | High-risk]
<!-- MANDATORY before planning (3PWR-FR-003). This single choice drives every gate threshold
     (coverage, mutation, model diversity) via .3powers/config/risk-tiers.yaml. -->

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- [What this feature will deliberately NOT do]
- [Boundary the implementation must not cross]

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [Brief Title] (Priority: P1)

[Describe this user journey in plain language — WHAT and WHY, never HOW.]

**Acceptance Scenarios**:

1. **Given** [initial state], **When** [action], **Then** [expected outcome]
2. **Given** [initial state], **When** [action], **Then** [expected outcome]

### Edge Cases

- What happens when [boundary condition]?
- How does the system handle [error scenario]?

## Requirements *(mandatory)*

<!--
  Write every requirement in EARS form (3PWR-FR-002) and namespace its ID with the Spec ID
  (3PWR-FR-059): [SPECID]-FR-### for functional, [SPECID]-NFR-### for non-functional.
  Each requirement MUST be measurable; an unmeasurable criterion blocks oracle authoring and is
  routed back to the Clarify stage (3PWR-FR-025). Give each an *Acceptance* line — the oracle
  (Phase A) is authored from these alone. Add a **Property** where input is parsed/validated/
  transformed (3PWR-FR-024). Do NOT put implementation detail here (3PWR-FR-007).
-->

### Functional Requirements

- **[SPECID]-FR-001**: The system shall [capability].
  - *Acceptance*: [concrete, checkable example(s)].
- **[SPECID]-FR-002**: When [trigger], the system shall [response].
  - *Acceptance*: [concrete, checkable example(s)].
  - *Property*: [invariant that must hold across many generated inputs, if applicable].

### Non-Functional Requirements *(if applicable)*

- **[SPECID]-NFR-001**: The system shall [quality attribute, measurable].

## Success Criteria *(mandatory)*

- **[SPECID]-SC-001**: [Measurable, technology-agnostic outcome].
- **[SPECID]-SC-002**: Every functional requirement has ≥1 linked test across unit/integration/e2e (3PWR-FR-030/065).

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id [SPECID]`; appended to the signed ledger)_ | | |
