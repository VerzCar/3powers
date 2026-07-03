# 3Powers Constitution

> The supreme, versioned law of this repository. Every lifecycle stage the executive drives —
> specify, clarify, plan, tasks, oracle, implement — and every 3Powers command must comply. It encodes
> the **separation of powers** that keeps validation from becoming circular when one model writes the
> spec, the code, the tests, and the review.

## Core Principles

### I. Separation of Powers (NON-NEGOTIABLE)
Three independent branches govern every change. **Legislative**: the spec is the law every later stage
answers to. **Executive**: agents build against the spec. **Judicial**: an independent oracle, the
deterministic gate suite, and a human reviewer judge whether the code matches the spec. No single
model or actor may occupy two branches for the same change.

### II. The Spec Is the Law
Authoritative specifications live, versioned, in `specs/` (3PWR-FR-010) — never in an external tracker.
Requirements are written in **EARS** form. Every spec declares a **Risk Tier** and an explicit
**Non-Goals** section *before* planning may begin (3PWR-FR-003/004). Implementation detail (a named
database, framework, schema, or stack choice) does not belong in spec text and must be flagged and
routed to planning (3PWR-FR-007). Specs carry a **Spec ID**; requirements are namespaced
`<SPECID>-FR-###` / `<SPECID>-NFR-###` so they are globally unique (3PWR-FR-059).

### III. Oracle Independence (Phase A before Phase B)
Some acceptance tests are the independent answer key. The **oracle** (Phase A) is authored from the
spec's acceptance criteria *only*, by a judiciary role that does not read the implementation, plan, or
source (3PWR-FR-020/021), and is pinned to a **different model family** than the coder
(3PWR-FR-022) — the engine refuses when they match. There is at least one oracle test per acceptance
criterion, named with its requirement ID, and a **property-based** test wherever input is parsed,
validated, or transformed (3PWR-FR-023/024). The coder's own tests (Phase B) may self-verify but never
replace the oracle (3PWR-FR-062/063).

### IV. Traceability End to End
Every task, commit, test, and verdict traces to exactly one requirement ID (3PWR-FR-016). Before code is
written, coverage is two-way: every requirement maps to ≥1 task and every task to a requirement
(3PWR-FR-015). The **spec-conformance** gate fails if any requirement lacks a linked test across the
unit / integration / e2e layers (3PWR-FR-030/064/065). Artifacts — never chat summaries — are handed
between stages (3PWR-FR-014).

### V. Risk Tier Drives Every Threshold
`Cosmetic` / `Standard` / `High-risk` is the single knob. All thresholds (coverage, mutation score,
model diversity, verification spend) come from the one risk-tier table
(`.3powers/config/risk-tiers.yaml`, 3PWR-FR-032/049). **A gate is never satisfied by weakening it** —
raise the tier instead. Gate-gaming (inline lint disables, type suppressions, deleted assertions,
weakened config) is routed to mandatory human review, not a silent pass (3PWR-FR-035).

### VI. The Trust Spine Is Local and Tamper-Evident
There is no mandatory CI/CD enforcer. Trust is recovered in-repo: an append-only, **hash-chained,
signed verdict ledger** (3PWR-FR-038/039); a local `verify` that fails on any tamper, gap, or break
(3PWR-FR-040); and a local enforcement gate that refuses to advance when a required gate is red, the
ledger fails verification, or a tier-required **human sign-off** is absent (3PWR-FR-037/041). The
signer identity is independent of the executive agents and never stored in the repo (3PWR-NFR-005).
Enforcement is uniform — no fast path for agent-authored or administrator changes (3PWR-FR-042). The
whole record is self-contained and reconstructable offline (3PWR-FR-071, 3PWR-NFR-004/010).

### VII. Agnostic by Construction
No required dependency on a single LLM provider, model vendor, language toolchain, or CI/CD platform
(3PWR-NFR-014). Language support is a declarative **adapter contract**; adding a language changes no
core code (3PWR-FR-027/045, 3PWR-NFR-007). Executive agents may not touch credentials, access control,
hard-deletes, or security configuration without human approval (3PWR-FR-018), and editing outside a
task's declared file scope is a signal to stop and re-spec (3PWR-FR-017).

## Self-Application

3Powers is built and maintained using 3Powers (3PWR-A6 / 3PWR-NFR-006). Its own trust-spine code is
held to the **High-risk** tier. Changes to the framework follow the same eight-stage lifecycle and pass
the same gates they impose on others.

## Governance

This constitution supersedes other practices. Amendments are versioned and recorded in the ledger.
Compliance is checked at every stage by the gate engine and the human sign-off — advisory guidance in
`AGENTS.md` complements but never replaces gate enforcement (3PWR-FR-047/048).

**Version**: 0.1.0 | **Ratified**: 2026-06-30 | **Last Amended**: 2026-06-30
