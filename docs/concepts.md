# Concepts — how 3Powers thinks

> Plain-English tour of the ideas. The **normative** version lives in the
> [constitution](../.specify/memory/constitution.md) and the [spec](../3Powers_Spec_v0.2.md)
> (Spec ID `3PWR`); this page explains *why* they say what they say. New to the project? Read this,
> then [Getting Started](getting-started.md).

## The problem: validation goes circular

Hand an agent a feature and it will happily write the spec, the code, the tests, *and* the review. The
trouble is that all four now come from **one mind**. The tests pass because the same model that wrote the
code wrote the tests; the review approves because the same model reasoned its way there. Nothing
independent ever checked that the code does what was actually asked. This is the **separation-of-powers
collapse** — confidence with no second opinion.

3Powers fixes this the way governments do: it splits the work into **three branches that hold each other
accountable**, and it makes that separation mechanical rather than a matter of good intentions.

## The three powers

| Branch | Who | Their job | Cannot also… |
|---|---|---|---|
| **Legislative** | the **spec** | be the single source of truth every later stage answers to | — |
| **Executive** | the coding **agents** | build *against* the spec | judge their own output |
| **Judicial** | an independent **oracle** + the **gate suite** + a **human reviewer** | decide whether the code matches the spec | write the code it judges |

The rule (constitution, Principle I): **no single model or actor occupies two branches for the same
change.** The model that wrote the code does not get to write the answer key.

- **Legislative — the spec is law.** Requirements live versioned in [`specs/`](../specs/), in
  [EARS](https://alistairmavin.com/ears/) form, each with a unique ID like `VUTIL-FR-001`. Every spec
  declares a **risk tier** and an explicit **non-goals** section *before* planning starts. Implementation
  detail (a database, a framework) does **not** belong in a spec and is flagged out (`3PWR-FR-007`).
- **Executive — agents build.** Agents turn the spec into a plan, tasks, and code. They may write their
  own tests to self-check, but those tests can never *replace* the independent oracle.
- **Judicial — independent judgement.** Three judges, none of which the coder controls: an **oracle**
  (acceptance tests written from the spec by a *different model family*), a **deterministic gate suite**
  (same verdict no matter who wrote the code), and a **human** who signs off.

## Oracle independence (the heart of it)

The oracle is the **answer key**: acceptance tests authored *from the spec's acceptance criteria alone*.
Two rules make it independent (constitution, Principle III; `3PWR-FR-020/021/022`):

1. **Different mind.** The oracle is pinned to a **different model family** than the coder. The engine
   refuses to proceed when they match (`3pwr roles-check`).
2. **No peeking.** The oracle author (called **Phase A**) writes tests from the spec *before* and
   *without reading* the implementation. The coder (**Phase B**) then implements and must satisfy both
   their own tests and the oracle's.

> **Honest status:** today this separation is enforced *procedurally* — by the `/3pwr.oracle` prompt,
> the `roles-check` gate, authoring order, and the ledger record. Making it *structural* (the oracle
> literally cannot read the implementation, via headless dispatch) is the project's top remaining
> hardening item. See [STATUS](STATUS.md).

## Risk tiers — one knob for every threshold

Not all code carries the same blast radius. A bug in the trust spine lets bad code through *everywhere*;
a typo in a CLI banner does not. So every capability declares a **risk tier**, and that tier is the
**single source** of every gate threshold — coverage %, mutation score, model diversity (`3PWR-FR-032`,
[`risk-tiers.yaml`](../.3powers/config/risk-tiers.yaml)):

| Tier | What it's for | Gates |
|---|---|---|
| **Cosmetic** | docs, CLI formatting | format + lint + types only |
| **Standard** | most app code; failures are visible & recoverable | + tests, diff-coverage, SAST, dependency, secret, gate-gaming, conformance |
| **High-risk** | the trust spine; a defect re-opens circular validation | + **mutation** + model diversity, at the strictest thresholds |

**The golden rule: a gate is never satisfied by weakening it.** If a change needs a higher bar, you raise
its tier — you never lower the gate. Attempts to game a gate (an inline lint-disable, a `# type: ignore`,
a deleted assertion, a weakened config) are flagged for **mandatory human review**, not silently absorbed
(`3PWR-FR-035`).

## The deterministic gate suite

The judiciary's tireless half. Gates run **cheapest-first** so failures surface fast (`3PWR-FR-026`):

```
format → lint → types → tests (+ diff-coverage) → mutation → SAST → dependency → secret → gate-gaming → spec-conformance
```

Two properties matter:

- **Deterministic** (`3PWR-NFR-001`): the same code yields the same verdict no matter which model wrote
  it. There is no judgement in a gate for an agent to argue with.
- **Polyglot by contract** (`3PWR-FR-027`): each language plugs in a declarative *adapter* manifest that
  supplies its own format/lint/type/test/coverage/mutation tools. The core never assumes a language;
  language-agnostic gates (diff-coverage, conformance, secret, dependency, SAST) live in the core.

Every run emits **one normalized verdict** (`3PWR-FR-033`) whose every failure is **actionable** — it
names the failing gate, the failure class, and the offending requirement or file, so a human can act on
it without opening an agent transcript (`3PWR-FR-034/NFR-011`). See
[Engine Architecture](engine-architecture.md) for how each gate works.

## The trust spine — recovering trust locally

3Powers deliberately has **no mandatory CI/CD enforcer** (`3PWR-NFR-004`). That raises a question: if
there's no central gatekeeper, what stops someone from just ignoring a red gate? The answer is a local,
tamper-**evident** record (constitution, Principle VI):

- An append-only, **hash-chained, Ed25519-signed verdict ledger** ([`.3powers/ledger.jsonl`](../.3powers/)).
  Each entry chains to its predecessor's hash and is signed by an **independent identity** whose private
  key never lives in the repo (`3PWR-FR-038/039`, `NFR-005`).
- A `3pwr verify` that recomputes the chain + signatures **offline** and fails on any tamper, gap, or
  break (`3PWR-FR-040`).
- A local `3pwr advance` enforcement gate that refuses to proceed unless the gates are green, the ledger
  verifies, and a **human sign-off** is present (`3PWR-FR-041`) — uniformly, with no fast path
  (`3PWR-FR-042`).
- **Build provenance + SBOM** signed by the same identity and verified at a **deploy gate**
  (`3PWR-FR-066/067/068`), plus full **reversibility** (`3pwr revert`, `3PWR-FR-070`).

It guarantees tamper-**evidence**, not tamper-**proofing** (`3PWR-NFR-013`): someone *can* bypass local
enforcement, but the ledger and provenance make it **detectable**. The whole record reconstructs from the
repository alone, offline (`3PWR-NFR-010`).

## Off the happy path — emergencies & deviations

A process that cannot bend under fire gets abandoned; one that bends without discipline rots. So both
ways off the happy path are **pre-agreed, signed, and reversible** (spec §14):

- A **deviation** (`3pwr deviation`, `3PWR-FR-057`) relaxes *named gates* with a recorded reason, a human
  approver, and a **way back** (an expiry or an explicit revoke). `advance` will accept a red gate **only**
  when an active deviation covers it — recorded and surfaced, never silent. This is also the sanctioned way
  to **accept a `gate_gaming` flag** (a refactor that legitimately removed an assertion): you don't weaken
  the gate, you record a reversible deviation that a human signed.
- An **emergency fast path** (`3pwr emergency`, `3PWR-FR-056`) is a *constrained* deviation: it may defer
  only **mutation** and **coverage**, never the security/secret gates, the human sign-off, or provenance —
  and it requires a **cleanup within one working day** (file the follow-up requirement and revoke it), or
  `advance` blocks.

Crucially, deviations act at the **enforcement boundary**, not in the verdict: gates always run honestly,
so the verdict stays deterministic (`3PWR-NFR-001`). The deviation is an explicit, ledgered override —
exactly the discipline the constitution's "never satisfy a gate by weakening it" demands.

## The eight-stage lifecycle

Every change flows through eight stages with explicit human gates (`3PWR-FR-011`, spec §6):

```
Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe
```

The state isn't stored in some external tracker — it's **derived from the ledger** (`3pwr status`), so it
reconstructs offline and survives a fresh checkout. In practice the stages run through GitHub Copilot
slash commands: Spec Kit drives the legislative/executive stages (`/speckit.*`) and 3Powers adds the
judiciary (`/3pwr.*`). See [Getting Started](getting-started.md#driving-the-full-lifecycle).

## Agnostic by construction

No required dependency on any single LLM provider, model vendor, language toolchain, or CI/CD platform
(`3PWR-NFR-014`). Roles bind to model *families* in config so you can swap models without touching the
workflow; languages plug in via the adapter contract with **zero core changes** (`3PWR-NFR-007`). It
layers on **GitHub Spec Kit** (constraint A1) and uses **Git** as its substrate (A2).

## Self-application

3Powers is **built using 3Powers** (`3PWR-A6`, `NFR-006`). The `3pwr` engine gates its own code, and its
trust-spine modules are held to the **High-risk** tier — they pass their own mutation bar. If the
framework's own crown-jewel code couldn't survive its own gates, why would you trust it on yours?

## Where to go next

- **[Getting Started](getting-started.md)** — run the whole thing end-to-end in five minutes.
- **[Engine Architecture](engine-architecture.md)** — how the gates, verdict, and trust spine work inside.
- **[CLI Reference](cli-reference.md)** — every `3pwr` command.
- **[Brownfield Adoption](brownfield.md)** — bring 3Powers to an existing codebase.
- **[STATUS](STATUS.md)** — exactly how far the implementation is, validated against the spec.
