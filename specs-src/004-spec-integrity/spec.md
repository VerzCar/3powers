# Feature Specification: Spec-Integrity Gate (spec-lock)

**Spec ID**: SLOCK

**Risk Tier**: High-risk
<!-- The spec is the single source of truth. Protecting it against silent post-approval mutation is as
     trust-critical as protecting the ledger itself, so it is held to the strictest bar. -->

**Status**: Draft

**Input**: The 3Powers engine as delivered through plan 015. Motivation: today the spec is *not* protected
against silent modification after a human approves it. `signoff --stage spec` records only
`{approver, stage, note}` — no fingerprint of the approved document — and neither `gate run` nor `advance`
ever re-reads the spec to confirm it is unchanged. An agent (or anyone) can therefore alter, add, or delete
requirements during Build / Verify / Review / Ship and nothing detects it. The only existing spec-level
fingerprint (`oracle seal`'s `bundle_hash`) covers just the acceptance-criteria slice, is High-risk-only,
and is checked solely in the oracle-independence flow. This feature captures a full-document hash of the
spec at the human approval moment and enforces it thereafter — at all tiers, reusing the existing signed
ledger with no new trust primitive.

---

## Non-Goals *(mandatory)*

- Does **not** protect the spec *before* the first human sign-off — the spec is a living document through
  the Discovery → Specify stages, and the gate skips (never blocks) until an approval hash exists.
- Does **not** prevent a human from legitimately amending the spec; the Clarify stage plus a signed,
  reversible `spec_integrity` deviation, or a fresh `signoff --stage spec`, remains the sanctioned path.
- Does **not** normalize whitespace/formatting — the hash covers the document byte-for-byte; a deliberate
  edit of any kind is a change and must be re-approved.
- Does **not** alter how `oracle seal` / `oracle verify` work; the criteria-slice `bundle_hash` stays
  separate from the full-document spec hash introduced here.
- Does **not** introduce a new ledger entry kind — it extends the existing `signoff` entry — and does
  **not** require CI/CD; enforcement is local, offline, and ledger-derived.

## Requirements *(each is referenced by ≥1 engine test)*

### Functional Requirements

- **SLOCK-FR-001**: The engine shall record a SHA-256 hash of the full spec document in the signed `signoff` ledger entry when a human signs off the Spec stage, without adding a new ledger entry kind.
  - *Acceptance*: a `signoff` with `stage: spec` and a resolvable spec carries `spec_hash` (equal to a raw-bytes SHA-256 of the file) and `spec_path` in its payload; a `signoff` for any other stage carries neither; the same fields are captured whether sign-off is manual (`3pwr signoff`) or via the orchestration gate (`3pwr run`).
- **SLOCK-FR-002**: The engine shall derive the current approved-spec hash for a spec from the committed ledger alone, with no file I/O.
  - *Acceptance*: a `spec_approval_hash` query returns the latest Spec-stage `signoff` carrying a `spec_hash` for a given spec id, the later one when several exist, and nothing when none exists.
- **SLOCK-FR-003**: The engine shall provide a `spec_integrity` gate that, when an approval hash exists, re-hashes the current spec file and fails the verdict if it differs; when no approval hash exists the gate shall pass (skip), never blocking a not-yet-approved spec.
  - *Acceptance*: a `gate run` over a spec modified after approval yields a failing `spec_integrity` gate with class `spec_modified` naming the approving ledger seq; an unmodified spec yields a passing gate; a spec with no recorded Spec-stage sign-off yields a passing (skipped) gate with an informational note.
- **SLOCK-FR-004**: The engine shall run the `spec_integrity` gate cheapest-first — after format/lint/types and before tests/diff-coverage — so a spec mutation fails fast.
  - *Acceptance*: a verdict that includes `spec_integrity` orders it after the type gate and before the tests gate in the canonical gate order.
- **SLOCK-FR-005**: The engine shall re-execute the spec-integrity check at `advance` and refuse to proceed on a mismatch, unless a signed `spec_integrity` deviation covers it.
  - *Acceptance*: `advance` with a spec modified after approval is refused with reason `spec_modified`; a signed `3pwr deviation --gate spec_integrity` turns the refusal into a warned, recorded pass; revoking or expiring the deviation re-blocks `advance`.
- **SLOCK-FR-006**: The engine shall let a fresh Spec-stage sign-off supersede the previous approval hash, so a legitimately amended-and-re-approved spec passes again.
  - *Acceptance*: after a second `signoff --stage spec` over the amended spec, `gate run` and `advance` pass against the new hash and treat the earlier hash as superseded.
- **SLOCK-FR-007**: The engine shall provide a read-only `spec diff` command that reports whether the current spec matches its approval hash (with the approving seq/approver) and, when possible, a textual diff, and shall never write to the ledger.
  - *Acceptance*: `3pwr spec diff --spec-id <ID>` exits non-zero and reports a mismatch (falling back to a `git diff` textual view when the sign-off commit is known) when the spec has changed, and exits zero reporting a match when it has not; the ledger is unchanged either way.

### Non-Functional Requirements

- **SLOCK-NFR-001**: The spec-integrity check shall be deterministic — identical spec bytes always hash the same, and the gate result depends only on committed ledger state and the file on disk (no model call, no network).
  - *Acceptance*: two `gate run`s over identical inputs produce an identical `spec_integrity` result.
- **SLOCK-NFR-002**: The approval hash shall reside inside a signed ledger entry so that tampering with the recorded hash is caught by `verify`.
  - *Acceptance*: altering the `spec_hash` field of a `signoff` entry makes `3pwr verify` fail on that entry's signature — with no additional verification code.
- **SLOCK-NFR-003**: The gate shall skip in O(1) when a spec has no approval hash, imposing no measurable cost during pre-approval authoring.
  - *Acceptance*: `gate run` over a never-signed-off spec completes the `spec_integrity` gate without reading the spec file more than once.

## Success Criteria

- **SLOCK-SC-001**: A spec modified after `signoff --stage spec` causes `gate run` to fail at `spec_integrity` before any test executes.
- **SLOCK-SC-002**: `advance` refuses an agent-mutated spec with no deviation, and proceeds under a signed `spec_integrity` deviation.
- **SLOCK-SC-003**: `3pwr verify` detects tampering with the `spec_hash` field of a `signoff` entry, with no new verification code.
- **SLOCK-SC-004**: `3pwr spec diff` surfaces the change that caused an integrity failure.
- **SLOCK-SC-005**: The gate is skipped (never blocking) for a spec that has never been through `signoff --stage spec`.
- **SLOCK-SC-006**: Self-application — sealing the engine's own spec via `signoff --stage spec` and then mutating it is caught by `spec_integrity`, proving 3Powers protects its own law.

## Sign-off

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id SLOCK --stage spec --spec specs/004-spec-integrity/spec.md`)_ | | |
