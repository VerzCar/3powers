# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

This repository is **pre-implementation**. It currently holds a single artifact — [`3Powers_Spec_v0.2.md`](3Powers_Spec_v0.2.md), the epic-level specification — and no source code, build system, tests, or tooling. It is not yet a git repository, though the spec assumes Git as its substrate (constraint A2). There are therefore **no build/lint/test commands yet**; the spec is the source of truth until code lands. As the toolchain arrives, record commands and pinned versions in [`AGENTS.md`](AGENTS.md).

## What 3Powers is

A portable, open "judiciary kit" for spec-driven, agentic software delivery. Its premise: when one model writes the spec, the code, the tests, *and* the review, validation becomes circular — the **separation-of-powers collapse**. 3Powers restores three independent branches:

- **Legislative** — the spec is the law every later stage answers to.
- **Executive** — agents do the building.
- **Judicial** — an independent oracle, a deterministic gate suite, and human review judge whether the code matches the spec.

It ships as a layer on **GitHub Spec Kit** (A1), uses Git as substrate (A2), and is deliberately agnostic to model family, language, LLM provider, and CI/CD platform.

## Architecture (the big picture)

The framework drives an **eight-stage lifecycle** as a resumable workflow with explicit human gates between branches: Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe (§6).

Three pillars carry the trust and are the highest-stakes parts of the system (the "High-risk" tier, §4):

1. **Oracle independence (§7).** Oracle tests are authored from the spec's acceptance criteria by a *judiciary* role that is structurally forbidden from reading the implementation, plan, or source, and is pinned to a **different model family** than the coder. This is **Phase A**. The coder's own tests (**Phase B**) may self-verify the build but never replace the oracle — Phase B depends on Phase A.

2. **Deterministic gate engine (§8).** A cheapest-first gate suite: format/lint → types → tests + diff-coverage → mutation → SAST → dependency scan → secret scan → spec-conformance → build provenance. Language support is a **plugin/adapter contract** — the core never assumes a language; language-agnostic gates (secrets, deps, conformance, provenance) live in the core. Every run emits **one normalized, machine-readable verdict** whose schema is identical across languages. Same code → same verdict regardless of which model authored it (NFR-001).

3. **The trust spine (§9).** Because there is no mandatory CI/CD enforcer, trust is recovered *locally*: an append-only, **hash-chained verdict ledger** signed by an independent signer identity the executive agents do not hold; **signed build provenance + SBOM** verified at a deploy gate; and full **versioning + reversibility** of every artifact and stage transition. A `verify` operation recomputes the chain and signatures and fails on any tampering. Everything is self-contained in the repository — reconstructable offline (NFR-004, NFR-010).

## Key conventions

- **Identifier scheme.** Every spec has a spec ID (this one is `3PWR`). Requirement IDs are namespaced with it — canonical form `3PWR-FR-###` / `3PWR-NFR-###`. The short `FR-###` / `NFR-###` forms are used in prose only. Tasks, commits, tests, and verdicts each trace to exactly one requirement ID.
- **Requirements are written in EARS form.** Every spec must declare a risk tier and an explicit non-goals section before planning may begin.
- **Risk tiers** — `Cosmetic` / `Standard` / `High-risk` — are the single source of every downstream threshold (coverage, mutation score, model diversity, verification spend). They live in one tier-config table; gates are never satisfied by weakening them.
- **Specs live in a versioned `specs/` directory** inside the repo (FR-010), never in an external tracker.
- **Self-application (A6 / NFR-006).** 3Powers is built and maintained *using* 3Powers; its own trust-spine code must pass its own gates at the High-risk tier.

## Working in this repo

- **The spec is the law.** Do not put implementation detail (a named database, framework, schema, or stack choice) into spec text — that belongs in planning and should be flagged out of place (FR-007).
- **Respect the executive boundaries and task file-scope discipline** documented in [`AGENTS.md`](AGENTS.md). Editing outside a task's declared file scope is a signal to stop and re-spec, not to proceed (FR-017).
- **Scope phasing** (§17): v0.1 = trust-spine MVP → v0.5 = full judiciary (remaining gates, provenance, residual review, eval harness) → v1.0 = lifecycle & ecosystem (brownfield, observe loop, catalog distribution).
