# Plan 003 — Complete the v0.1 Trust-Spine MVP

**Status**: Implemented & verified. Self-application is green at Standard with the full v0.1 gate set
(format/lint/types/tests/diff-coverage/dependency/secret/gate-gaming/conformance; 63 engine tests,
ruff+mypy clean; 19 requirements traced). Builds on plans [`001`](001-base-setup-and-tech-stack.md) and
[`002`](002-self-application-and-scanners.md). Scope discipline (FR-016/017) and work-kind inference
(FR-058) move to plan 004.

## Context — why (a spec-grounded recalibration)

Re-auditing the as-built framework against the spec's **§17 v0.1 scope** surfaced that several items
the spec scopes to **v0.1** were not yet built, while plan 002 had begun pulling in **v0.5** gates
(secret/dependency scans). The spec is the single source of truth, so plan 003 **finishes v0.1 before
v0.5**. The remaining v0.1 gaps are all *deterministic engine work* and therefore self-applicable.

| Gap | Requirement | Today |
|---|---|---|
| Reversibility | **FR-070** | missing — no "reverse to a prior recorded state" |
| Resumability / run-state | **FR-019**, lifecycle **FR-011** | missing — no persisted/derivable lifecycle state |
| Two-way requirement↔task coverage (pre-code) | **FR-015** | prompt-level only, not an engine check |
| Gate-gaming detection | **FR-035** | missing |
| Scope discipline (commit/file-scope) | FR-016/017 | advisory only → stretch / plan 004 |

Deferred to **v0.5 (plan 004)**: residual review (FR-036), build provenance + SBOM + deploy gate
(FR-066–068), SAST, eval harness (FR-050).

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| **Reversibility** | A reversal is a **new signed `reversal` ledger entry** referencing the target seq + reason — never a deletion | Keeps the append-only chain honest; the reversal is itself auditable (FR-069, open-question §19.9). Git-level revert stays the user's action; the engine records the *logical* reversal. |
| **Lifecycle state** | **Derived from the ledger**, not a separate mutable file | Single source of truth; reconstructable offline from the repo alone (FR-071); no drift. `runs/` holds only transient scratch. |
| **Two-way coverage** | A standalone `3pwr coverage-check` (spec ⇄ tasks.md) | Runs before Build; deterministic; complements the after-the-fact spec-conformance gate. |
| **Gate-gaming** | A **core gate** (language-agnostic) over the diff; a hit is a **fail surfaced for human review**, never a silent pass | FR-035. Accepting a legitimate suppression is a *deviation* (FR-057, v1.0). The engine itself must stay clean of such patterns (self-application). |

## Workstreams

1. **Reversibility (FR-070).** Add `reversal` to the ledger entry types + schema. `3pwr revert --to <seq>
   [--reason …]` appends a signed reversal that names the prior recorded state. `verify` treats it like
   any entry (chain + signature). `status` reflects the reverted stage.
2. **Lifecycle & resumability (FR-011/FR-019).** Enumerate the eight stages
   (Discovery→Spec→Plan→Build→Verify→Review→Ship→Observe). `3pwr status [--spec-id X]` derives each
   spec's current stage from the ledger (verdict/signoff/stage_advance/reversal). `advance` validates
   the target is a known next stage. Resuming = reading `status` (state persists in the committed
   ledger); `3pwr abort --spec-id X --reason` records an abort entry.
3. **Two-way coverage (FR-015).** `3pwr coverage-check --spec <spec.md> --tasks <tasks.md>`: parse
   requirement IDs from the spec and `[REQ]` tags from tasks; fail if any requirement has no task or any
   task has no requirement; actionable findings naming the offending id/task.
4. **Gate-gaming detection (FR-035).** Core gate `gate_gaming`: scan added diff lines for inline
   lint-disables (`biome-ignore`, `eslint-disable`, `noqa`), type suppressions (`# type: ignore`,
   `@ts-ignore`/`@ts-nocheck`), coverage pragmas (`pragma: no cover`), and removed `assert`/`expect`
   lines; flag weakened gate config. A hit ⇒ `fail` with class `gate_gaming` listing each item. Add to
   Standard + High-risk tiers and `GATE_ORDER`; extend the verdict schema enum.
5. **Self-application + tests + docs.** Add unit/CLI tests (each referencing its FR id, feeding
   conformance); remove any coverage pragma in the engine so `gate_gaming` stays green on itself; keep
   `3pwr gate run --path engine` green; update `AGENTS.md`, `CLAUDE.md`, and the scoped engine spec to
   reference the newly implemented FRs.

## New `3pwr` surface

```
3pwr status [--spec-id <ID>]              # lifecycle stage(s) derived from the ledger (FR-011/019)
3pwr revert --to <seq> [--reason <text>]  # signed reversal to a prior recorded state (FR-070)
3pwr abort  --spec-id <ID> [--reason …]   # record an abort (FR-019)
3pwr coverage-check --spec <s> --tasks <t># two-way requirement↔task coverage (FR-015)
# gate_gaming runs inside `3pwr gate run` at Standard+ (FR-035)
```

Ledger entry types become: `verdict | residual | signoff | stage_advance | reversal | abort`.

## Verification

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # engine green
# self-application stays green, now exercising the new core gate:
3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md \
              --tier Standard --base 3e20aad --no-ledger
# new behaviours:
3pwr coverage-check --spec specs/001-validation-utils/spec.md --tasks <tasks.md>   # pass/fail
3pwr status --spec-id VUTIL                                                        # shows stage
# reversibility round-trip on a scratch ledger: advance → revert → status reflects prior stage → verify OK
```
Negative: a planted `# type: ignore` / deleted `assert` in a diff makes `gate_gaming` fail with the
offending lines; a requirement with no task (or a task with no requirement) fails `coverage-check`.

## Out of scope (→ plan 004, v0.5)

Residual review (FR-036), build provenance + SBOM + deploy gate (FR-066–068), SAST (semgrep), the
prompt/constitution eval harness (FR-050), and the mutmut src-layout runner follow-up. Scope-discipline
gates (FR-016/017 file-scope, commit req-ID) are a stretch here, otherwise early plan 004.
