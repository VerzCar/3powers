# Feature Specification: 3Powers Engine — Trust Spine (v0.1 slice)

**Spec ID**: 3PWR

**Risk Tier**: High-risk
<!-- The trust spine IS the trust (spec §4). Its code is held to the strictest bar (self-application, spec §17). -->

**Status**: Approved

**Input**: The implemented v0.1 slice of the 3PWR epic — the `3pwr` engine. This scopes spec-conformance
to what the engine actually implements (the full 71-FR epic lives in `3Powers_Spec_v0.2.md`).

---

## Non-Goals *(mandatory)*

- Does **not** cover the gates deferred past v0.1 (SAST, residual review, build provenance) — those land
  in plans 003+.
- Does **not** re-state the whole epic; only the FRs the engine implements today are listed here.

## Requirements *(the implemented subset — each is referenced by ≥1 engine test)*

### Functional Requirements

- **3PWR-FR-022**: The engine shall refuse to proceed when the oracle and coder roles resolve to the same model family.
  - *Acceptance*: `roles-check` of two same-family roles exits non-zero; different families exit zero.
- **3PWR-FR-026**: The engine shall run the gate suite cheapest-first (format → lint → types → tests → diff-coverage → mutation → spec-conformance).
  - *Acceptance*: a verdict's gates appear in canonical order.
- **3PWR-FR-029**: The engine shall measure coverage on changed lines, not the whole repository.
  - *Acceptance*: diff-coverage over a changed covered line is 100%; over a changed uncovered line, 0%.
- **3PWR-FR-030**: The engine shall fail spec-conformance when any requirement has no linked test.
  - *Acceptance*: a spec with an untested requirement yields a failing conformance gate naming that ID.
- **3PWR-FR-033**: The engine shall emit one normalized verdict whose shape is identical across languages.
  - *Acceptance*: a verdict serializes with `schema_version`, `result`, and ordered `gates`.
- **3PWR-FR-034**: The engine shall make each failure actionable, naming its class and offending item.
  - *Acceptance*: an untested requirement appears as a failure with class `untested_requirement` and the requirement id.
- **3PWR-FR-038**: The engine shall maintain an append-only, hash-chained ledger.
  - *Acceptance*: each appended entry links to its predecessor's `entry_hash` via `prev_hash`.
- **3PWR-FR-039**: The engine shall sign each ledger entry with an independent signer identity.
  - *Acceptance*: every entry carries a `signer_key_id` and a verifiable Ed25519 `signature`.
- **3PWR-FR-040**: The engine shall provide a `verify` operation that fails on any tamper, gap, or break.
  - *Acceptance*: tampering, reordering, or deleting an entry makes `verify` fail.
- **3PWR-FR-041**: The engine shall refuse to advance when a gate is red, the ledger fails verification, or a sign-off is absent.
  - *Acceptance*: `advance` is refused with no sign-off and succeeds after one is recorded.
- **3PWR-FR-042**: The engine shall apply enforcement uniformly, with no fast path.
  - *Acceptance*: `advance` applies the same checks regardless of caller.
- **3PWR-FR-011**: The engine shall track the eight-stage lifecycle, derivable from the ledger.
  - *Acceptance*: `status` reports a spec's current stage from its ledger entries.
- **3PWR-FR-015**: The engine shall verify two-way requirement↔task coverage before code.
  - *Acceptance*: `coverage-check` fails when a requirement has no task or a task has no requirement.
- **3PWR-FR-019**: The engine shall support resuming/aborting a run with state persisted in the ledger.
  - *Acceptance*: lifecycle state is derived from the committed ledger; an abort is recorded.
- **3PWR-FR-035**: The engine shall flag gate-gaming (suppressions, deleted assertions) for human review.
  - *Acceptance*: an added `# type: ignore` or a removed assertion fails the `gate_gaming` gate.
- **3PWR-FR-070**: The engine shall reverse to a prior recorded state via a signed reversal entry.
  - *Acceptance*: `revert` appends a reversal that returns the stage to its value at the target seq.
- **3PWR-FR-016**: The engine shall require each task to carry its originating requirement ID.
  - *Acceptance*: `scope-check` fails a task line that has no requirement ID.
- **3PWR-FR-017**: The engine shall flag edits outside a task's declared file scope.
  - *Acceptance*: a changed file not in any task's `(files: …)` scope fails `scope-check`.
- **3PWR-FR-036**: The engine shall record a residual review by a different model family.
  - *Acceptance*: `residual` appends a signed residual entry to the ledger.
- **3PWR-FR-066**: The engine shall produce a signed provenance record binding an artifact (by hash) to its commit, repo, run, and SBOM.
  - *Acceptance*: `provenance` writes a signed record whose signature verifies.
- **3PWR-FR-067**: The engine shall verify provenance at a deploy gate and refuse a missing/failed one.
  - *Acceptance*: `deploy-gate` refuses an artifact whose hash does not match its provenance.
- **3PWR-FR-068**: The engine shall sign provenance with the same independent signer identity as the ledger.
  - *Acceptance*: provenance verifies against the committed ledger public key.
- **3PWR-FR-050**: The engine shall treat prompts/commands/constitution as versioned software with an eval set and block on regression.
  - *Acceptance*: `eval` fails when a required phrase is missing from a constitution/command file.

### Non-Functional Requirements

- **3PWR-NFR-001**: Given identical inputs, the verdict shall be deterministic.
  - *Acceptance*: canonical encoding of equal payloads is byte-identical.
- **3PWR-NFR-005**: The signer's private key shall never be stored in the repository.
  - *Acceptance*: `keygen` writes the private key outside the repo; only the public key is in-repo.
- **3PWR-NFR-010**: Every advance shall be auditable from the repository alone, offline.
  - *Acceptance*: `verify` recomputes the chain with no network access.

## Success Criteria

- **3PWR-SC-001**: `3pwr gate run --path engine --adapter python` is green at the declared tier.
- **3PWR-SC-002**: Trust-spine modules (`canonical`, `keys`, `ledger`, `verify`) meet the High-risk bar.

## Sign-off

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id 3PWR`)_ | | |
