# Feature Specification: Validation Utilities

**Spec ID**: VUTIL

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold. -->

**Status**: Approved

**Input**: A small, pure input-validation library used as the 3Powers walking-skeleton sample.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- This library does **not** perform network or DNS validation (e.g. checking that an
  email's domain exists).
- It does **not** localize or normalize Unicode beyond the rules stated below.
- It is **not** a schema/validation framework — just a handful of pure predicates and
  one parser.

## User Scenarios & Testing

### User Story 1 — Validate user-supplied fields (Priority: P1)

A caller validates strings coming from a form (a required field, an email, a slug) and
parses a numeric field, getting a deterministic boolean / parsed value with no side effects.

**Acceptance Scenarios**:

1. **Given** an empty or whitespace-only string, **When** `isNonEmpty` is called, **Then** it returns `false`.
2. **Given** a syntactically valid email, **When** `isEmail` is called, **Then** it returns `true`; otherwise `false`.
3. **Given** a lowercase hyphen-separated token, **When** `isSlug` is called, **Then** it returns `true`; otherwise `false`.
4. **Given** an integer and an inclusive range, **When** `inRange` is called, **Then** it returns whether the value is within `[min, max]`.
5. **Given** an arbitrary string, **When** `parseIntStrict` is called, **Then** it returns the integer for a canonical base-10 integer string and `null` for anything else.

## Requirements *(EARS form — 3PWR-FR-002; IDs namespaced by Spec ID — 3PWR-FR-059)*

### Functional Requirements

- **VUTIL-FR-001**: The system shall reject a string that is empty or contains only whitespace.
  - *Acceptance*: `isNonEmpty("")`, `isNonEmpty("   ")` → `false`; `isNonEmpty("a")` → `true`.
- **VUTIL-FR-002**: The system shall accept a syntactically valid email address and reject any input lacking a single `@` with non-empty local and domain parts containing a dot.
  - *Acceptance*: `isEmail("a@b.com")` → `true`; `isEmail("a@b")`, `isEmail("a b@c.com")`, `isEmail("@b.com")` → `false`.
- **VUTIL-FR-003**: The system shall validate a slug as one or more lowercase alphanumeric groups separated by single hyphens, with no leading/trailing hyphen.
  - *Acceptance*: `isSlug("hello-world-2")` → `true`; `isSlug("Hello")`, `isSlug("a--b")`, `isSlug("-a")` → `false`.
- **VUTIL-FR-004**: The system shall report whether an integer lies within an inclusive `[min, max]` range.
  - *Acceptance*: `inRange(5, 1, 10)` → `true`; `inRange(0, 1, 10)` → `false`.
- **VUTIL-FR-005**: The system shall parse a canonical base-10 integer from a string and return `null` for any non-integer input (no leading zeros, optional leading `-`, no surrounding whitespace).
  - *Acceptance*: `parseIntStrict("42")` → `42`; `parseIntStrict("-7")` → `-7`; `parseIntStrict("007")`, `parseIntStrict("1.0")`, `parseIntStrict(" 1 ")`, `parseIntStrict("x")` → `null`. **Property**: for every integer `n`, `parseIntStrict(String(n)) === n`.

## Success Criteria

- **SC-001**: Every functional requirement has at least one linked test across the unit/integration/e2e layers (3PWR-FR-030/065).
- **SC-002**: Diff coverage on changed lines meets the Standard-tier threshold (3PWR-FR-029).

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you>` — appended to the signed ledger)_ | | |
