# 3Powers Constitution

> The supreme, versioned law of this repository. Every lifecycle stage the native executive drives —
> specify, clarify, plan, tasks, oracle, implement (`3pwr run`) — and every 3Powers
> command (`/3pwr.*`) must comply. It encodes the **separation of powers** that keeps validation from
> becoming circular when one model writes the spec, the code, the tests, and the review.

## How to adapt this constitution

This constitution is **mandatory** — every dispatched stage loads it as the rules of the project —
and it ships generic. **Adapt it to this project before the first real run**: keep the Core
Principles below verbatim (see "What stays fixed"), then add project-specific articles covering
everything in the checklist. An unadapted constitution leaves agents guessing at your standards.

**Mandatory content — technical baseline** (add an article covering each):

- [ ] Languages and runtimes, with the exact versions this project builds against.
- [ ] Build / test / lint / type toolchain — including the exact commands the coding gates run.
- [ ] Repository layout and module boundaries: what lives where, and what may import what.
- [ ] Architectural rules: required patterns and forbidden anti-patterns.
- [ ] Dependency policy: how a new dependency is justified, reviewed, and pinned.
- [ ] Coding standards and naming conventions.
- [ ] Testing conventions: test layout, and the coverage / mutation bars per risk tier.
- [ ] Documentation expectations: what must be documented, where, in the same change.

**Mandatory content — policies & rules** (add an article covering each):

- [ ] Risk-tier defaults and thresholds for this project: which tier new work defaults to, and why.
- [ ] Security & privacy rules: credentials, access control, hard-deletes, and security
      configuration — what agents may never touch without human approval.
- [ ] Branch / commit / PR discipline.
- [ ] Definition of done: gates green, tests shipped with the change, docs updated.
- [ ] Gate non-weakening: a gate is never satisfied by weakening it.
- [ ] Oracle independence and requirement traceability, as they apply to this project.

**What stays fixed:** the separation-of-powers Core Principles I–VII below are the point of
3Powers — adapt everything around them, never them.

**How to update:** edit the article, bump the version in the footer, and record the amendment (date
and reason) under Governance. If this repository seals its constitution, an edit may require a
re-seal — or a signed deviation — before `advance` accepts it.

## Core Principles

### I. Separation of Powers (NON-NEGOTIABLE)
Three independent branches govern every change. **Legislative**: the spec is the law every later stage
answers to. **Executive**: agents build against the spec. **Judicial**: an independent oracle, the
deterministic gate suite, and a human reviewer judge whether the code matches the spec. No single
model or actor may occupy two branches for the same change.

### II. The Spec Is the Law
Authoritative specifications live, versioned, in `specs-src/` — never in an external tracker.
Requirements are written in **EARS** form. Every spec declares a **Risk Tier** and an explicit
**Non-Goals** section *before* planning may begin. Implementation detail (a named
database, framework, schema, or stack choice) does not belong in spec text and must be flagged and
routed to planning. Specs carry a **Spec ID**; requirements are namespaced
`<SPECID>-FR-###` / `<SPECID>-NFR-###` so they are globally unique.

### III. Oracle Independence (Phase A before Phase B)
Some acceptance tests are the independent answer key. The **oracle** (Phase A) is authored from the
spec's acceptance criteria *only*, by a judiciary role that does not read the implementation, plan, or
source, and is pinned to a **different model family** than the coder — the engine refuses when they
match. There is at least one oracle test per acceptance criterion, named with its requirement ID, and
a **property-based** test wherever input is parsed, validated, or transformed. The coder's own tests
(Phase B) may self-verify but never replace the oracle.

### IV. Traceability End to End
Every task, commit, test, and verdict traces to exactly one requirement ID. Before code is written,
coverage is two-way: every requirement maps to ≥1 task and every task to a requirement. The
**spec-conformance** gate fails if any requirement lacks a linked test across the required
unit / integration / e2e layers. Artifacts — never chat summaries — are handed between stages.

### V. Risk Tier Drives Every Threshold
`Cosmetic` / `Standard` / `High-risk` is the single knob. All thresholds (coverage, mutation score,
model diversity, verification spend) come from the one risk-tier table
(`.3powers/config/risk-tiers.yaml`). **A gate is never satisfied by weakening it** —
raise the tier instead. Gate-gaming (inline lint disables, type suppressions, deleted assertions,
weakened config) is routed to mandatory human review, not a silent pass.

### VI. The Trust Spine Is Local and Tamper-Evident
There is no mandatory CI/CD enforcer. Trust is recovered in-repo: an append-only, **hash-chained,
signed verdict ledger**; a local `verify` that fails on any tamper, gap, or break; and a local
enforcement gate that refuses to advance when a required gate is red, the ledger fails verification,
or a tier-required **human sign-off** is absent. The signer identity is independent of the executive
agents and never stored in the repo. Enforcement is uniform — no fast path for agent-authored or
administrator changes. The whole record is self-contained and reconstructable offline.

### VII. Agnostic by Construction
No required dependency on a single LLM provider, model vendor, language toolchain, or CI/CD platform.
Language support is a declarative **adapter contract**; adding a language changes no core code.
Executive agents may not touch credentials, access control, hard-deletes, or security configuration
without human approval, and editing outside a task's declared file scope is a signal to stop and
re-spec.

## Self-Application

3Powers is built and maintained using 3Powers. Its own trust-spine code is held to the **High-risk**
tier. Changes to the framework follow the same eight-stage lifecycle and pass the same gates they
impose on others.

## Governance

This constitution supersedes other practices. Amendments are versioned and recorded in the ledger.
Compliance is checked at every stage by the gate engine and the human sign-off — advisory guidance in
`AGENTS.md` complements but never replaces gate enforcement.

**Amendments**: 1.0.0 (2026-07-08) — re-ratified for the v1.0 release; folds in the adaptation
guide, the mandatory-content checklist, the "what stays fixed" note, and the "how to update" rule.

**Version**: 1.0.0 | **Ratified**: 2026-07-08 | **Last Amended**: 2026-07-08
