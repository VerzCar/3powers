# Glossary

The terms of art used across the 3Powers documentation, defined once. Entry documents link here on
first use. The normative definitions live in the [spec](../specs/3Powers_Spec_v0.2.md) (Spec ID `3PWR`)
and the [constitution](../.specify/memory/constitution.md); this page is the plain-English lookup.

## Adapter

A declarative manifest (`.3powers/adapters/<lang>/adapter.yaml`) that teaches the gate engine a
language's format / lint / type / test / coverage / mutation tooling. The core never assumes a language;
adding one is "write a manifest", not a core change. See the
[adapter contract](../.3powers/adapters/CONTRACT.md).

## Advance

The local enforcement gate (`3pwr advance`): it refuses to move a change to the next lifecycle stage
unless the required gates are green, the [ledger](#ledger) verifies, and the tier-required human
sign-off is recorded. It is what a CI branch-protection rule would give you — but local, offline, and
signed.

## Assumptions (A1–A6)

The spec's architectural givens (spec §3). When a document says "A3", it means the third of these:

- **A1 — Built on Spec Kit.** 3Powers ships as GitHub Spec Kit extensions/workflows and reuses Spec
  Kit's integration registry and headless `workflow run` dispatch, rather than building its own agent
  harness.
- **A2 — Git is the substrate.** The repository is the working environment and the home of the
  authoritative spec; a specific Git host is not assumed.
- **A3 — Provider-agnosticism via dispatch.** Any agent Spec Kit can dispatch headlessly is eligible to
  fill a role; 3Powers never calls model APIs directly to satisfy a role.
- **A4 — CI is optional, never the source of trust.** The guarantees (verdicts, provenance,
  reversibility) must hold locally and offline; a CI platform may *re-validate*, never gatekeep.
- **A5 — Polyglot from day one.** Language support is a plugin contract (see [adapter](#adapter)).
- **A6 — Self-application.** 3Powers is built and maintained using 3Powers.

## Deviation

A signed, reversible, time-boundable exception (`3pwr deviation`) that relaxes a *named* gate at the
enforcement boundary with a recorded reason and approver. Gates still run honestly — the verdict never
changes; only `advance` accepts the covered red gate. The way back is an expiry or an explicit revoke.

## Gate / gate suite

A single deterministic check (e.g. `types`, `secret_scan`) or the whole cheapest-first sequence of them.
Same code in, same verdict out, no matter which model wrote the code. The canonical gate names and order
live in the [engine architecture guide](engine-architecture.md).

## Ledger

The append-only, hash-chained, Ed25519-signed record (`.3powers/ledger.jsonl`) of every verdict,
sign-off, and stage advance. `3pwr verify` recomputes the chain and signatures offline and fails on any
tamper, gap, or break. Tamper-**evident**, not tamper-proof — see the [threat model](threat-model.md).

## Oracle

The independent answer key: acceptance tests authored *from the spec's acceptance criteria alone*, by a
different model family than the coder, without reading the implementation. The coder's own tests may
self-check but can never replace the oracle. See [Phase A / Phase B](#phase-a--phase-b).

## Phase A / Phase B

The two authoring phases that keep the oracle independent. **Phase A**: the judiciary role writes the
oracle tests from the spec, before and without reading any implementation. **Phase B**: the coder
implements and must satisfy both its own tests and the oracle's. Phase A must precede Phase B, and the
engine records and checks the ordering.

## Quarantine

What happens when a gate's external tool is not installed: the gate is surfaced as **skipped** with a
named finding, never silently passed. A quarantined gate is visible in the verdict, so absence of
tooling can't masquerade as green.

## Requirement-ID scheme

Every spec has a **Spec ID** (e.g. `VUTIL`, `3PWR`) and namespaced requirement IDs —
`<SPECID>-FR-###` for functional and `<SPECID>-NFR-###` for non-functional requirements. Tasks, commits,
and tests each trace to exactly one requirement ID; the `spec_conformance` gate checks the trace.

## Residual

What the deterministic gates *cannot* judge for a given change — the part explicitly left to a human (or
a documented follow-up). Each plan and the [STATUS](STATUS.md) page name their residuals so no claim
silently exceeds what was verified.

## Risk tier

The single knob (`Cosmetic` / `Standard` / `High-risk`) every spec declares before planning. The tier is
the sole source of every gate threshold — coverage %, mutation score, required test layers, model
diversity. The golden rule: a gate is never satisfied by weakening it; if a change needs a higher bar,
you raise its tier.

## Trust spine

The local machinery that recovers trust without a central gatekeeper: the signed [ledger](#ledger), the
offline `3pwr verify`, the [`advance`](#advance) enforcement gate, reversibility (`3pwr revert`), and
signed build provenance with a deploy gate. Self-contained in the repo and reconstructable offline.

## Verdict

The one normalized result of a gate run: per-gate pass/fail/skip, every failure named with a class and
location, identical shape across languages. Written to `.3powers/verdicts/latest.json` and recorded in
the [ledger](#ledger). A human can read it without opening an agent transcript.

## Work kind

The inferred kind of a change — defect, design, feature, docs, refactor, chore — derived
deterministically from the intent (`3pwr classify`). The kind *shapes* the gate suite (a defect adds a
regression gate; design work adds the design oracles) but only ever adds gates, never removes one a tier
requires, and never touches the human sign-off.
