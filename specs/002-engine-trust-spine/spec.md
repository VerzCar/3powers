# Feature Specification: 3Powers Engine — Trust Spine + Judiciary + Brownfield

**Spec ID**: 3PWR

**Risk Tier**: High-risk
<!-- The trust spine IS the trust (spec §4). Its code is held to the strictest bar (self-application, spec §17). -->

**Status**: Approved

**Input**: The implemented slice of the 3PWR epic — the `3pwr` engine (v0.5 complete + the v1.0 brownfield
Stage Zero and High-risk self-application from plan 006). This scopes spec-conformance to what the engine
actually implements (the full 71-FR epic lives in `3Powers_Spec_v0.2.md`).

---

## Non-Goals *(mandatory)*

- Does **not** cover the *fuller* A3 work still ahead — the **coder** leg also running headless under a
  different-family CLI, and end-to-end verification of a live non-Copilot `workflow run` dispatch (the
  **oracle** leg's *physical* read-path isolation IS delivered here via `oracle dispatch`); nor the
  *live* production instrumentation runtime (observe records signals + declarations, §13), catalog
  publishing, or a third adapter.
- Does **not** re-state the whole epic; only the FRs/NFRs the engine implements today are listed here.

## Requirements *(the implemented subset — each is referenced by ≥1 engine test)*

### Functional Requirements

- **3PWR-FR-020**: The engine shall seal a spec-only oracle bundle (acceptance criteria only) that the judiciary authors from, and bind the authoring record to that bundle's content hash.
  - *Acceptance*: `oracle seal` writes a content-addressed bundle whose hash is stable across re-seals; `oracle verify` fails a record bound to a stale/mismatched bundle hash.
- **3PWR-FR-021**: The engine shall structurally forbid the oracle author from reading the implementation — authoring it headlessly in a sanitized worktree from which the implementation, plan, tasks, and contracts are physically absent (`oracle dispatch`, A3) — and shall additionally record, as a non-blocking advisory, any signal that the author touched the implementation, without weakening the deterministic verdict.
  - *Acceptance*: `oracle dispatch` builds a worktree whose isolation manifest contains no implementation/plan/contracts path and records a signed dispatch attestation; a High-risk `advance` with `require_dispatch` on refuses when no isolated dispatch is recorded or its manifest fails to prove isolation, and proceeds when isolation holds; the peek/touch heuristic stays advisory (`advance` proceeds on an advisory alone).
- **3PWR-FR-022**: The engine shall refuse to proceed when the oracle and coder resolve to the same model — at the configured granularity (`family` default, or `model`), checking the model actually recorded — **unless** a signed `model_diversity` deviation relaxes it (3PWR-FR-057), in which case it warns and records but proceeds. Diversity is recommended, not forced.
  - *Acceptance*: `roles-check` / `oracle record` / `oracle dispatch` in the coder's family is refused; a signed `3pwr deviation --gate model_diversity` turns the refusal into a warned, recorded pass and a High-risk `advance` proceeds; at `diversity_level: model` a different model in one family is accepted; `--revoke` restores the refusal.
- **3PWR-FR-062**: The engine shall separate Phase A (oracle authoring) from Phase B (implementation) and prove, from the ledger sequence, that the oracle was authored before the implementation verdict.
  - *Acceptance*: a High-risk `advance` refuses when the oracle record's ledger seq is at or after the implementation verdict's, and proceeds when it precedes it.
- **3PWR-FR-026**: The engine shall run the gate suite cheapest-first (format → lint → types → tests → diff-coverage → mutation → spec-conformance).
  - *Acceptance*: a verdict's gates appear in canonical order.
- **3PWR-FR-029**: The engine shall measure coverage on changed lines, not the whole repository.
  - *Acceptance*: diff-coverage over a changed covered line is 100%; over a changed uncovered line, 0%.
- **3PWR-FR-030**: The engine shall fail spec-conformance when any requirement has no linked test.
  - *Acceptance*: a spec with an untested requirement yields a failing conformance gate naming that ID.
- **3PWR-FR-031**: The engine shall run mutation testing scoped to changed/high-risk files and report each surviving mutant as an actionable missing assertion.
  - *Acceptance*: the mutation gate executes on the trust-spine modules, grades the score, and lists survivors as findings.
- **3PWR-FR-032**: The engine shall read every gate threshold (incl. mutation score) from the single risk-tier table and never satisfy a gate by weakening it.
  - *Acceptance*: the mutation gate passes only when the score meets the tier's `mutation_score`; a below-threshold score fails.
- **3PWR-FR-033**: The engine shall emit one normalized verdict whose shape is identical across languages.
  - *Acceptance*: a verdict serializes with `schema_version`, `result`, and ordered `gates`.
- **3PWR-FR-034**: The engine shall make each failure actionable, naming its class and offending item.
  - *Acceptance*: an untested requirement appears as a failure with class `untested_requirement` and the requirement id.
- **3PWR-FR-058**: The engine shall infer the kind(s) of work from free-form intent and use the inference only to shape the risk tier / applicable gates and the oracle strategy, never to bypass the human sign-off.
  - *Acceptance*: `classify` returns work kind(s) + a suggested tier deterministically (a payment/auth intent → High-risk; a docs-only intent → Cosmetic); `run` records them without removing the mandatory human gates.
- **3PWR-FR-064**: The engine shall, per risk tier, require the tier's test layers (unit / integration / e2e) for a change, via the spec-conformance gate.
  - *Acceptance*: with a tier's `required_layers` set, spec-conformance fails a change whose tests do not cover a required layer (class `untested_layer`), and passes when all required layers are present.
- **3PWR-FR-065**: The engine's spec-conformance shall account for all three test layers, tracing each requirement to the layers that reference it.
  - *Acceptance*: the conformance verdict reports, per requirement, the set of layers (unit/integration/e2e) whose tests reference it.
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
- **3PWR-FR-048**: The engine shall treat supported third-party versions as configurable and detect drift of the installed toolchain (including Spec Kit) from the supported range.
  - *Acceptance*: `deps-check` reports each component ok/drift/missing against `.3powers/config/dependencies.yaml` and fails a `block`-policy drift or absence.
- **3PWR-FR-054**: The engine shall record a production signal and route it back to the legislature as a new requirement (not an in-place patch), and report which of a spec's NFRs have a live check.
  - *Acceptance*: `observe signal` appends a signed entry + a `<SPEC>-FB-###` new-requirement candidate and moves the spec to the Observe stage; `observe coverage` flags an NFR with no registered live check.
- **3PWR-FR-055**: The engine shall record runtime agent actions in a tamper-evident, attributable log.
  - *Acceptance*: `observe log-action` appends a signed, agent-attributed entry to a hash-chained log; `observe verify-actions` fails on any tamper, gap, or break.
- **3PWR-FR-051**: The engine shall hold only new/changed code to the full process, leaving existing code untouched until modified.
  - *Acceptance*: with `--paths`/`--diff-scope`, diff-coverage and the file-based scanners count only the in-scope files.
- **3PWR-FR-052**: The engine shall support running gates in report-only mode that emits a verdict but does not block.
  - *Acceptance*: `gate run --report-only` flags the verdict advisory, exits 0 on red, and `advance` ignores it.
- **3PWR-FR-053**: The engine shall reconstruct a spec for a legacy module and pin its current behavior with characterization tests as its oracle.
  - *Acceptance*: `3pwr characterize --module <p>` writes a spec stub + runnable tests that trace the reconstructed requirement IDs.
- **3PWR-FR-056**: The engine shall provide an emergency fast path that may defer mutation + coverage but never the security/secret gates, sign-off, or provenance, and shall require a one-working-day cleanup.
  - *Acceptance*: `3pwr emergency` defers only mutation + diff-coverage; an overdue cleanup blocks `advance` until the emergency is revoked.
- **3PWR-FR-057**: The engine shall provide a reversible deviation that relaxes named gates with a recorded reason and a defined way back.
  - *Acceptance*: a signed `deviation` lets `advance` accept a named red gate; revoking or expiring it re-blocks; an uncovered red gate still blocks.

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
