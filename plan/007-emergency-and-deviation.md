# Plan 007 — Emergency & deviation paths (§14, FR-056/057)

> **Cold-start note.** Read [`docs/STATUS.md`](../docs/STATUS.md) first (spec-validated state) and
> [`docs/concepts.md`](../docs/concepts.md) for the model. The spec
> [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) is the law. Plans 001–006 delivered v0.1, v0.5, and
> the first half of v1.0 (High-risk self-application + brownfield Stage Zero). This plan continues v1.0.

## Context — why this is next

The roadmap in [STATUS §6](../docs/STATUS.md) puts **emergency & deviation paths** first among the
remaining v1.0 work: it is **small, high-leverage, and fully engine-implementable** (it builds on the
existing signed ledger), and it unblocks a real pain point — there is currently **no sanctioned way to
accept a `gate_gaming` flag** (e.g. a refactor that legitimately removes an assertion) without weakening
a gate. The spec's deviation mechanism (FR-057) *is* that path (see FR-035: "accepting a legitimate
suppression is a deviation, recorded explicitly").

The bigger remaining items — **structural** oracle independence via Spec Kit headless dispatch
(FR-021/062) and the **observe** loop (§13) — are sequenced after this: the first is harness-level
(A3 headless dispatch in a Copilot-only setting) and the second is a new subsystem. This plan is the
clean, self-applicable slice.

## Scope

**In:**
- **FR-057 — reversible deviation mechanism.** A signed `deviation` ledger entry that relaxes **named
  gates** with a recorded **reason**, an **approver** (a human), and a **defined way back** (an expiry or
  an explicit revoke). `advance` accepts a red gate **iff** an active deviation covers it — recorded and
  surfaced, never silent. This is the sanctioned acceptance of a `gate_gaming` flag.
- **FR-056 — emergency fast path.** A constrained deviation profile that may defer **mutation** and
  **diff-coverage** only, shall **never** relax the security/secret gates, and shall require a recorded
  **cleanup within one working day**. `advance` refuses while an emergency cleanup is overdue.
- `status` surfaces active deviations and overdue emergency cleanups.

**Out (→ plan 008+):** structural oracle independence (FR-021/062, A3 headless dispatch), observe/feedback
(§13, FR-054/055), work-kind inference (FR-058), defect→regression flow (FR-008), design oracles (FR-009),
a third adapter, catalog distribution. Re-tiering "cosmetic code that reached production" (the second
clause of FR-057) is recorded as a deviation reason here; automated re-tier detection is deferred.

## Decisions (proposed — revisit if you find better)

| Area | Proposal | Rationale |
|---|---|---|
| **Where deviations apply** | At the **`advance` enforcement boundary**, not in the verdict. Gates always run honestly; a deviation lets `advance` accept specific red gates. | Determinism (NFR-001): a deviation must not change the verdict for the same code. The override is explicit, signed, and ledgered (FR-057 "recorded reason + way back"). |
| **Entry model** | One new ledger type `deviation`. Payload: `{gates[], reason, approver, emergency, expires_at, cleanup_due, revokes}`. "Active" = not expired and not revoked by a later entry. | Reuses the append-only signed ledger; reversal = append, never rewrite (matches `revert`/FR-070). |
| **Never deviatable** | Human **sign-off** and **provenance** are separate enforcement checks `advance`/`deploy-gate` always require — deviations cover only **verdict gates**. Emergency additionally forbids `sast`/`secret_scan`/`dependency_scan`. | Faithful to FR-056 ("never skip the security and secret gates, the human sign-off, or provenance"). |
| **Emergency cleanup** | Emergency deviation carries `cleanup_due` (default +24h). `advance` **refuses** while any emergency cleanup is overdue and unrevoked. | Faithful to FR-056 ("require a recorded cleanup within one working day"). |

## Workstreams

1. **`deviations.py` + ledger type.** New module: `active_deviations(entries, now)`, `covered_gates(...)`,
   `overdue_emergencies(entries, now)`, the emergency profile (`EMERGENCY_DEFERRABLE = {mutation,
   diff_coverage}`, `EMERGENCY_FORBIDDEN = {sast, secret_scan, dependency_scan}`). Add `deviation` to
   `ledger.ENTRY_TYPES`.
2. **CLI.** `cmd_deviation` (record / `--revoke <seq>`), `cmd_emergency` (constrained profile). Update
   `cmd_advance`: collect the latest enforced verdict's failing gates; subtract active-deviation coverage;
   refuse on any uncovered red gate **or** an overdue emergency; record `deviations_applied` on success.
   Surface active/overdue deviations in `cmd_status`.
3. **Tests (FR-056/057).** A deviation lets `advance` proceed past a named red gate; an uncovered red gate
   still blocks; revoke/expiry deactivates; a deviation covering `gate_gaming` accepts the flag; `emergency`
   refuses a forbidden gate and requires cleanup; an overdue emergency blocks `advance`. Each test cites its FR id.
4. **Self-application + docs.** Keep the engine green (ruff/mypy/pytest) and the High-risk self-application
   green. Add FR-056/057 to `specs/002-engine-trust-spine/spec.md`; flip them in `docs/STATUS.md`; update
   `CLAUDE.md`, `AGENTS.md`, and the CLI reference + a deviation note in `docs/concepts.md`/`brownfield.md`.

## New `3pwr` surface (proposed)

```
3pwr deviation --gate <name>... --reason "..." --approver <human> [--until <iso8601>]   # FR-057
3pwr deviation --revoke <seq> [--reason "..."]                                          # the way back
3pwr emergency --reason "..." --approver <human> [--cleanup-hours 24]                   # FR-056
3pwr advance ...     # accepts deviated red gates; refuses on an overdue emergency cleanup
3pwr status          # also lists active deviations + overdue cleanups
```

## Verification (definition of done)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)        # engine green
# a red gate, accepted under a recorded deviation, then advance proceeds:
3pwr gate run --path <dir> --tier Standard            # red on some gate
3pwr deviation --gate <that-gate> --reason "..." --approver "$(git config user.name)" --spec-id <ID>
3pwr signoff --approver "$(git config user.name)" --spec-id <ID>
3pwr advance --stage ship --spec-id <ID>              # proceeds, records deviations_applied
3pwr verify                                           # ledger still verifies
# High-risk self-application stays green (NFR-006).
```
Done when: deviation + emergency commands work; `advance` honors active deviations and blocks on an
overdue emergency; the engine self-applies green; `docs/STATUS.md` flips FR-056/057 to ✅.

## How to work here

- **The spec is the law.** Validate against `3Powers_Spec_v0.2.md` §14; respect §17 phasing.
- **No inline gate suppressions** in the engine — `gate_gaming` will flag them; fix the underlying issue.
  (This plan adds the *sanctioned* way to accept such a flag — a recorded deviation — but the engine's own
  code should not need one.)
- Each new test references the FR id it exercises; add implemented requirements to `specs/002-*/spec.md`.
- Commit on the `plan-007-*` branch.
