# Plan 010 — Observe & feedback loop (§13, FR-054/055)

> **Cold-start note.** Read [`docs/STATUS.md`](../docs/STATUS.md) first, then the spec
> [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (the law). Plans 001–009 delivered v0.1, v0.5, and most
> of v1.0 (through portability & dependency stability). This plan closes the lifecycle's **8th stage** —
> Observe — the last fully-engine-buildable v1.0 piece.

## Context — why this is next

The eight-stage lifecycle has always listed **Observe**, but it was a name only — no entry type, no
command, no feedback routing. §13 closes the loop: "production is where software is graded, and the loop
must return what is learned to the **spec** rather than to ad-hoc patches."

- **FR-054** — instrument the target against its NFRs, and route production signal (incidents, missed
  objectives, real usage) **back into the legislature as new intent, not as patches applied in place**.
- **FR-055** — where the target system contains agents taking actions at runtime, require
  **tamper-evident, attributable logging** of every such action.

The engine is **offline** (Git substrate; it does not run the target's production system), so "observe"
is realized as: intake an externally-supplied signal → **route it to a new requirement** (a feedback
backlog the human takes into `/speckit.specify`) → report **NFR-instrumentation coverage** (which NFRs
have a declared live check) → and a **tamper-evident agent-action log** built by reusing the existing
signed hash-chained ledger (so `verify` catches any tamper for free). This is self-contained and
self-applicable, like plans 007/009.

## Scope

**In:**
- **FR-054 — feedback loop.** `3pwr observe signal --spec-id <ID> --kind incident|missed-nfr|usage
  [--nfr <id>] --note "…"` records a signed, attributed `observe` ledger entry **and** appends a
  new-requirement candidate (`<SPEC>-FB-###`) to a feedback backlog (`.3powers/feedback/<spec>.md`) routed
  to `/speckit.specify` — never an in-place patch. A recorded signal moves the spec to the **Observe**
  stage (`lifecycle.derive`).
- **FR-054 — NFR instrumentation coverage.** `.3powers/config/observability.yaml` declares which NFRs have
  a live production check; `3pwr observe coverage --spec <spec.md>` reports covered vs. missing (§13
  acceptance: "a specified NFR has a live check").
- **FR-055 — agentic runtime action log.** `3pwr observe log-action --agent <id> --action "…"` appends a
  signed, attributed entry to a **separate** hash-chained log (`.3powers/runtime/actions.jsonl`, reusing
  `Ledger` + `verify_ledger`); `3pwr observe verify-actions` fails on any tamper/gap/break.

**Out (→ plan 011+):** the *live* production system + real instrumentation runtime (the engine is offline —
it records signals and instrumentation *declarations*, it does not execute production checks); A3 live
headless dispatch (still the FR-021 residual); catalog *publishing*; a third adapter; defect→regression
flow (FR-008); design oracles (FR-009).

## Decisions (proposed — revisit if you find better)

| Area | Proposal | Rationale |
|---|---|---|
| **Route, don't patch** | A signal writes a NEW requirement (`<SPEC>-FB-###`) to a feedback backlog for `/speckit.specify`; the command never edits code. | FR-054's core discipline: lessons re-enter Stage 1–2 as new intent, not ad-hoc fixes. |
| **Signal record** | A signed `observe` entry in the **main** ledger (attributed, tamper-evident) that also flips the spec to the Observe stage. | Observe is part of the delivery record; reuses the trust spine; makes the 8th stage reachable (FR-011). |
| **Agent-action log** | A **separate** signed, hash-chained log (`.3powers/runtime/actions.jsonl`) via the existing `Ledger`/`verify_ledger`; `agent_action` entries carry the acting `agent`. | FR-055 wants the same tamper-evidence/attribution as the ledger for a *different* concern (the target's runtime) — reuse the mechanism, keep the stream separate from delivery verdicts. |
| **NFR instrumentation** | A declarative registry + a **coverage report** (not a live prober). | The engine is offline; it can't run production checks, but it can make the "which NFRs lack a live check" gap visible and routable. |
| **Not a verdict gate** | `observe coverage` / `verify-actions` are standalone commands, never folded into the deterministic verdict. | Environment/target-dependent; keeping them out of the verdict preserves determinism (NFR-001), consistent with `deps-check` and the oracle advisory. |

## Workstreams

1. **`observe.py` + ledger/lifecycle wiring.** `signal_payload`, `route_to_backlog` (+ `next_fb_id`),
   `spec_nfrs` / `instrumented_nfrs` / `nfr_coverage`, `action_payload`. Add `observe` + `agent_action` to
   `ledger.ENTRY_TYPES`; `lifecycle.derive` maps an `observe` entry → the **Observe** stage.
2. **CLI `observe` group.** `signal` (record + route to new intent), `coverage` (NFR instrumentation),
   `log-action` (append to the runtime chain), `verify-actions` (verify that chain). Register the subparser.
3. **Config.** `.3powers/config/observability.yaml` — the NFR → live-check registry (seeded with the
   engine's own trust-spine NFRs so `observe coverage` on `specs/002` is meaningful).
4. **Tests (per-FR) + self-application + docs.** `test_observe.py`: backlog routing creates a new
   requirement (not a patch); NFR coverage covered/missing; an `observe` entry → Observe stage; the
   agent-action log is tamper-evident (a corrupted entry fails `verify-actions`); an empty log verifies.
   Keep the engine green (ruff/mypy/pytest) and the High-risk self-application green; add FR-054/055 to
   `specs/002-engine-trust-spine/spec.md`; update `docs/STATUS.md`, `CLAUDE.md`, `AGENTS.md`, the CLI reference.

## New `3pwr` surface (proposed)

```
3pwr observe signal --spec-id <ID> --kind incident|missed-nfr|usage [--nfr <id>] --note "…"   # FR-054
3pwr observe coverage --spec <spec.md> [--registry <observability.yaml>]                       # FR-054
3pwr observe log-action --agent <id> --action "…" [--spec-id <ID>]                             # FR-055
3pwr observe verify-actions                                                                    # FR-055
```

## Verification (definition of done)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)          # engine green (+ test_observe.py)
3pwr observe signal --spec-id 3PWR --kind incident --note "…"   # → new intent in .3powers/feedback/3PWR.md; Observe stage
3pwr observe coverage --spec specs/002-engine-trust-spine/spec.md               # NFR instrumentation report
3pwr observe log-action --agent bot --action "…" && 3pwr observe verify-actions # tamper-evident runtime log
# self-application stays green at Standard AND High-risk (NFR-006).
```
Done when: `observe signal` records + routes a signal to a new requirement (never a patch) and moves the
spec to the Observe stage; `observe coverage` reports NFR instrumentation; the agent-action log is
tamper-evident; the engine self-applies green; and `docs/STATUS.md` flips FR-054/055 to ✅.

## How to work here

- **The spec is the law.** Validate against §13; respect §17 phasing (this is v1.0). Be honest: the engine
  records signals + instrumentation *declarations*; it does not run the target's production system.
- **Determinism (NFR-001).** `observe` commands are standalone, never folded into the verdict.
- **No inline gate suppressions**; keep the engine green under its own gates. Run `3pwr eval` after touching
  any prompt/constitution/roles file.
- Each new test cites its FR id; add implemented requirements to `specs/002-*/spec.md`.
- Commit on the `plan-010-observe-and-feedback` branch.
