# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository.

> **The spec is the single source of truth.** [`3Powers_Spec_v0.2.md`](3Powers_Spec_v0.2.md)
> (Spec ID `3PWR`) is the law; always check work against it, and respect the §17 scope phasing.
> Requirement IDs cited below are from that spec.

## What 3Powers is

A portable, open **judiciary kit** for spec-driven, agentic software delivery. Premise: when one model
writes the spec, the code, the tests, *and* the review, validation becomes circular — the
**separation-of-powers collapse**. 3Powers restores three independent branches:

- **Legislative** — the spec is the law every later stage answers to.
- **Executive** — agents do the building.
- **Judicial** — an independent oracle, a deterministic gate suite, and human review judge whether the
  code matches the spec.

It layers on **GitHub Spec Kit** (A1), uses Git as substrate (A2), and is agnostic to model family,
language, LLM provider, and CI/CD platform.

## Current state

Implemented and committed (not yet merged to `main`):

- **Plan 001** (`plan/001-base-setup-and-tech-stack.md`) — base setup + a runnable walking skeleton.
- **Plan 002** (`plan/002-self-application-and-scanners.md`) — self-application + supply-chain scanners.
- **Plan 003** (`plan/003-complete-v0.1-mvp.md`) — completed the remaining **v0.1** trust-spine MVP gaps.

**v0.1 status (honest):** essentially complete. The trust spine (ledger/verify/enforcement), the
deterministic floor + oracle-bearing gates, two reference adapters (TypeScript + Python),
self-application, **reversibility (FR-070)**, **lifecycle/resumability (FR-011/019)**, **two-way
requirement↔task coverage (FR-015)**, and **gate-gaming detection (FR-035)** are all implemented and
self-applied. Remaining gaps → **plan 004**: commit-tagging & file-scope enforcement (FR-016/017) and
work-kind inference (FR-058); context strategy (FR-060/061) is constrained by the Copilot harness.
Deferred to **v0.5** (plan 004+): residual review (FR-036), build provenance + SBOM + deploy gate
(FR-066–068), SAST, the eval harness (FR-050). Secret + dependency scans (v0.5) were brought forward in
plan 002.

## Repository layout

```
engine/                     # the `3pwr` engine — Python, shipped as a uv tool
  src/threepowers/          #   cli, gates, conformance, covdiff, adapters, scanners,
                            #   ledger, verify, keys, verdict, config, canonical
  tests/                    #   pytest suite (the engine gates itself — A6/NFR-006)
.3powers/                   # in-repo trust spine (self-contained; FR-071)
  config/{risk-tiers,roles}.yaml   schemas/*.json   adapters/{CONTRACT.md,<lang>/adapter.yaml}
  ledger.jsonl  keys/ledger.pub    (private key lives OUTSIDE the repo — NFR-005)
.specify/                   # Spec Kit; constitution + spec/plan/tasks templates OVERRIDDEN by 3Powers
.github/{prompts,agents}/   # Spec Kit /speckit.* commands + custom /3pwr.{oracle,verify,signoff,advance}
specs/                      # authoritative specs (FR-010); the epic + per-feature specs
examples/validation-utils/  # the runnable TypeScript sample (spec id VUTIL)
docs/references/            # compacted Spec Kit + trust-spine tooling references
plan/                       # the continuous plan series (001, 002, 003, …)
```

## Build / test / gate commands

Authoritative pinned versions live in [`AGENTS.md`](AGENTS.md) and the lockfiles
(`engine/uv.lock`, `examples/validation-utils/package-lock.json`).

```bash
uv tool install ./engine            # install the `3pwr` command
(cd engine && uv sync --extra dev && uv run pytest)   # engine dev env + tests
(cd engine && uv run ruff check . && uv run mypy src) # engine lint + types

3pwr keygen                         # create the independent signer (key kept OUTSIDE the repo)
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
3pwr gate run --path <dir> --adapter <ts|python> --spec specs/<feature>/spec.md --tier <tier>
3pwr verify                         # recompute ledger chain + signatures, offline
3pwr signoff --approver <you> --stage review --spec-id <ID>
3pwr advance --stage ship           # refuses unless gate green + ledger verifies + sign-off present

# Self-application (3Powers gating its own engine):
3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md \
              --tier Standard --base <pre-engine-commit>
```

The lifecycle runs through GitHub Copilot slash commands: `/speckit.specify → clarify → plan → tasks`
then (switch model for the judiciary) `/3pwr.oracle`, then `/speckit.implement → /3pwr.verify →
/3pwr.signoff → /3pwr.advance`.

## Architecture (the big picture)

The framework drives an **eight-stage lifecycle** with explicit human gates: Discovery → Spec → Plan →
Build → Verify → Review → Ship → Observe (§6). Three pillars carry the trust (the High-risk tier, §4):

1. **Oracle independence (§7).** Oracle tests are authored from the spec's acceptance criteria by a
   *judiciary* role pinned to a **different model family** than the coder, forbidden from reading the
   implementation (**Phase A**). The coder's tests (**Phase B**) may self-verify but never replace the
   oracle. *As built:* the `/3pwr.oracle` command + `roles.yaml` + `3pwr roles-check` (engine refuses
   same family); full structural isolation is a known approximation in a Copilot-only setting.

2. **Deterministic gate engine (§8).** Cheapest-first: format/lint → types → tests + diff-coverage →
   mutation → dependency → secret → spec-conformance (→ SAST, provenance later). Language support is a
   **declarative adapter manifest** — the core never assumes a language (NFR-007); language-agnostic
   gates (diff-coverage, conformance, secret, dependency) live in the core. One normalized **verdict**
   per run, identical across languages (NFR-001/FR-033), every failure actionable (FR-034).

3. **The trust spine (§9).** No mandatory CI/CD enforcer; trust is recovered locally: an append-only
   **hash-chained, Ed25519-signed verdict ledger**; a `verify` that fails on any tamper/gap/break; a
   local `advance` enforcement gate; full **reversibility** (`revert`, FR-070); (v0.5) signed build
   provenance + SBOM. Self-contained and offline-reconstructable (NFR-004/010).

## Key conventions

- **Identifier scheme.** Spec ID per spec (this repo's epic: `3PWR`); requirement IDs are namespaced
  `<SPECID>-FR-###` / `<SPECID>-NFR-###`. Tasks, commits, tests, and verdicts each trace to exactly one
  requirement ID. (The conformance matcher accepts digit-leading ids like `3PWR` and `FR-038/039/040`
  shorthand.)
- **EARS form**; every spec declares a **risk tier** and explicit **non-goals** before planning.
- **Risk tiers** `Cosmetic`/`Standard`/`High-risk` are the single source of every threshold
  (`.3powers/config/risk-tiers.yaml`); **never satisfy a gate by weakening it** (FR-032).
- **Specs live in versioned `specs/`** (FR-010), never an external tracker.
- **Self-application (A6/NFR-006).** 3Powers is built using 3Powers; the engine gates its own code
  (trust-spine modules at High-risk). Add tests that reference the FR id they exercise.

## Working in this repo

- **The spec is the law.** Don't put implementation detail (a named database, framework, schema, stack)
  into spec text — flag it out of place (FR-007). When in doubt, re-read the spec; don't infer scope.
- **Respect executive boundaries and task file-scope discipline** (see [`AGENTS.md`](AGENTS.md)): editing
  outside a task's declared file scope is a signal to stop and re-spec (FR-017).
- **Engine changes must keep the engine green under its own gates** (ruff/mypy/pytest; diff-coverage and
  conformance via `3pwr gate run --path engine`). Trust-spine modules (`canonical`, `keys`, `ledger`,
  `verify`) are High-risk — hold their coverage ≥95%.
- **Scope phasing** (§17): v0.1 = trust-spine MVP → v0.5 = full judiciary (remaining gates, provenance,
  residual review, eval harness) → v1.0 = lifecycle & ecosystem (brownfield, observe, catalog).
