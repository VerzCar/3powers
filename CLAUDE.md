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
- **Plan 004** (`plan/004-scope-provenance-residual.md`) — scope discipline + first **v0.5** pillars.
- **Plan 005** (`plan/005-sast-and-eval-harness.md`) — SAST gate + eval harness; **completes v0.5**.
- **Plan 006** (`plan/006-v1.0-and-hardening.md`) — **High-risk self-application (NFR-006)** + **brownfield
  Stage Zero** (report-only, diff-scoped gating, characterization); starts **v1.0**.
- **Plan 007** (`plan/007-emergency-and-deviation.md`) — **emergency & deviation paths** (§14, FR-056/057):
  `3pwr deviation` (signed, reversible, named-gate relaxation; sanctioned `gate_gaming` acceptance) and
  `3pwr emergency` (defer only mutation+coverage; overdue cleanup blocks `advance`).
- **Plan 008** (`plan/008-oracle-independence.md`) — **structural oracle independence** (§7, FR-020/021/022/062):
  `3pwr oracle seal` (spec-only sealed bundle), `oracle record` (actual model + signer + test hashes; refuses
  the coder's family), `oracle verify`; High-risk `advance` proves independence from the ledger seq, and
  peeking/touching the implementation is an **advisory** flag (never a blocker).
- **Plan 009** (`plan/009-portability-and-dependencies.md`) — **portability & dependency stability**
  (A1/A3, FR-044/046/048, NFR-014): `3pwr deps-check` (a supported-versions manifest + drift detection,
  incl. Spec Kit) and a **provider-agnostic Spec Kit extension** (`.specify/extensions/3powers/`) with
  substrate-neutral, eval-gated role config. Live multi-integration dispatch stays the residual.
- **Plan 010** (`plan/010-observe-and-feedback.md`) — **observe & feedback loop** (§13, FR-054/055):
  `3pwr observe signal` routes a production signal to a new-requirement backlog (not a patch) + moves the
  spec to the Observe stage; `observe coverage` reports NFR instrumentation; `observe log-action`/
  `verify-actions` is a tamper-evident, attributable runtime agent-action log. Closes the 8th stage.
- **Plan 011** (`plan/011-a3-live-headless-dispatch.md`) — **A3 live headless dispatch + physical oracle
  read-path isolation** (FR-021; oracle leg of FR-012/013): `3pwr oracle dispatch` authors the oracle
  headlessly via `specify workflow run` under a non-coder integration (default `claude`), inside a
  **sanitized git worktree** with the implementation/plan/tasks/contracts physically absent — attested by a
  worktree manifest hash in the ledger. A High-risk `advance` blocks a missing/non-isolated dispatch when
  `roles.oracle.require_dispatch` is on; the 008 peek/touch signal stays advisory; dispatch never enters
  `gate run` (NFR-001). Optional distinct oracle signer key + two-key `verify` (NFR-005). Runs in-IDE by
  default (opt-in, High-risk only); the fuller dual-headless (coder leg) proof is the residual.

**Status (honest): v0.5 complete; v1.0 in progress.** Implemented across plans 001–006: the trust spine
(ledger / verify / enforcement / **reversibility** / **build provenance + deploy gate**), the **full gate
suite** cheapest-first (floor + tests/diff-coverage + **mutation** + **SAST** + dependency + secret +
gate-gaming + spec-conformance), two reference adapters (TypeScript + Python), **lifecycle/resumability**,
**two-way coverage**, **scope discipline**, **residual review**, the **prompt/constitution eval harness
(FR-050)**, **brownfield Stage Zero** (report-only FR-052, diff-scoped gating FR-051, `characterize`
FR-053), **emergency & deviation paths** (FR-056/057: `emergency` + `deviation`), **structural oracle
independence** (FR-020/021/022/062: `oracle seal`/`record`/`verify` + High-risk `advance`), **portability
& dependency stability** (FR-048/A1/A3: `deps-check` + a provider-agnostic Spec Kit extension), and the
**observe & feedback loop** (FR-054/055: `observe signal`/`coverage`/`log-action`), and **A3 live headless
dispatch** (FR-021 physical oracle read-path isolation + oracle leg of FR-012/013: `oracle dispatch` runs
the judiciary headlessly in a sanitized worktree, attested in the ledger, blocking at High-risk when
`require_dispatch` is on). **NFR-006 is met:**
the trust-spine modules pass their own **High-risk** bar — ≥95% diff-coverage **and** mutation (≈89% ≥ the
70% threshold) — via the fixed mutmut src-layout runner and per-path tier scoping; the engine runs green at
`--tier High-risk`. Next → rest of **v1.0**: **recommend-not-force model diversity** (plan 012 — relax the
same-family refusal via a signed `deviation` so single-model users are never walled off), the **fuller A3**
(coder leg also headless under a second, different-family CLI + a live non-Copilot end-to-end run), catalog
publishing, and a third adapter. Known approximations (command/harness-level): work-kind inference (FR-058),
context strategy (FR-060/061); the fuller dual-headless dispatch (the **oracle** leg is delivered).

## Repository layout

```
engine/                     # the `3pwr` engine — Python, shipped as a uv tool
  src/threepowers/          #   cli, gates, mutation, characterize, deviations, conformance, covdiff, oracle,
                            #   observe, deps, adapters, scanners, ledger, verify, keys, verdict, config, canonical
  tests/                    #   pytest suite (the engine gates itself — A6/NFR-006)
.3powers/                   # in-repo trust spine (self-contained; FR-071)
  config/{risk-tiers,roles,dependencies,observability}.yaml   schemas/*.json   adapters/{CONTRACT.md,<lang>/adapter.yaml}
  ledger.jsonl  keys/ledger.pub   feedback/<spec>.md  runtime/actions.jsonl  (private key OUTSIDE the repo — NFR-005)
.specify/                   # Spec Kit; constitution + templates OVERRIDDEN by 3Powers; extensions/3powers/ (A1)
.github/{prompts,agents}/   # Spec Kit /speckit.* commands + custom /3pwr.{oracle,verify,review,signoff,advance,characterize}
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

# Oracle independence (Phase A, §7): seal a spec-only bundle, author from it, then record + verify.
# At High-risk, `advance` refuses unless independence holds (FR-020/021/022/062).
3pwr oracle seal   --spec specs/<feature>/spec.md --spec-id <ID>
3pwr oracle record --spec-id <ID> --model <family/model> --tests <oracle-test-paths>  # refuses coder's family
# A3 (physical FR-021): author the oracle HEADLESSLY, read-path isolated — the implementation is absent from
# a sanitized git worktree. One-time: `specify integration install claude` (a non-coder, headless integration).
3pwr oracle dispatch --spec-id <ID> --integration claude   # + `--dry-run` to build/attest isolation offline
3pwr oracle verify --spec-id <ID> [--require-dispatch]   # seal-binding + diversity + ordering + coverage (+ isolation); advisory peek/touch

3pwr deps-check                     # probe installed third-party versions (incl. Spec Kit) vs supported ranges (FR-048)

# Observe & feedback (§13): route a production signal to new intent; NFR coverage; tamper-evident agent log.
3pwr observe signal --spec-id <ID> --kind incident|missed-nfr|usage --note "..."   # FR-054 → new-requirement backlog
3pwr observe coverage --spec specs/<feature>/spec.md                               # FR-054 NFR instrumentation
3pwr observe log-action --agent <id> --action "..."   # FR-055; then: 3pwr observe verify-actions

# Self-application (3Powers gating its own engine), Standard tier:
3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md \
              --tier Standard --base <pre-engine-commit>

# Self-application at HIGH-RISK — the NFR-006 proof (mutation on the trust-spine modules):
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)   # mutation_score ≈ 89% ≥ 70%

# Brownfield (existing repos): emit-don't-block, diff-scope, and characterize a legacy module:
3pwr gate run --path <dir> --tier Standard --report-only            # FR-052
3pwr gate run --path <dir> --tier Standard --base main --diff-scope # FR-051 (block only the diff)
3pwr characterize --module <path/to/legacy.py>                      # FR-053 (reconstruct spec + oracle)

# Off the happy path (§14): signed, reversible relaxations — never weaken a gate, record a deviation:
3pwr deviation --gate <name> --approver <you> --note "<why>" [--until <iso>]   # FR-057 (way back: --revoke <seq>)
3pwr emergency --approver <you> --note "<why>"                                 # FR-056 (defers mutation+coverage; 1-day cleanup)
```

The lifecycle runs through GitHub Copilot slash commands: `/speckit.specify → clarify → plan → tasks`
then (switch model for the judiciary) `/3pwr.oracle`, then `/speckit.implement → /3pwr.verify →
/3pwr.signoff → /3pwr.advance`. For an existing repo, start with `/3pwr.characterize` on a legacy module.

## Architecture (the big picture)

The framework drives an **eight-stage lifecycle** with explicit human gates: Discovery → Spec → Plan →
Build → Verify → Review → Ship → Observe (§6). Three pillars carry the trust (the High-risk tier, §4):

1. **Oracle independence (§7).** Oracle tests are authored from the spec's acceptance criteria by a
   *judiciary* role pinned to a **different model family** than the coder, forbidden from reading the
   implementation (**Phase A**). The coder's tests (**Phase B**) may self-verify but never replace the
   oracle. *As built:* `/3pwr.oracle` authors from a **sealed spec-only bundle** (`3pwr oracle seal`);
   `oracle record` captures the actual model + signer + test hashes and refuses the coder's family (FR-022);
   `oracle verify` and a **High-risk `advance`** prove independence from the signed ledger seq — seal-binding,
   diversity, Phase-A-before-B ordering, and per-criterion coverage (FR-020/062). **Physical read-path
   isolation is delivered (FR-021, A3):** `3pwr oracle dispatch` authors the oracle *headlessly* via
   `specify workflow run` under a non-coder integration, inside a **sanitized git worktree** with the
   implementation/plan/tasks/contracts physically absent — attested by a worktree manifest hash and enforced
   at a High-risk `advance` (`roles.oracle.require_dispatch`). Reading/touching heuristics stay **advisory**,
   never a blocker (NFR-001). Opt-in and High-risk-only — the default flow stays in-IDE and watchable; the
   coder leg also running headless (the fuller dispatch) is the residual.

2. **Deterministic gate engine (§8).** Cheapest-first: format/lint → types → tests + diff-coverage →
   mutation → SAST → dependency → secret → gate-gaming → spec-conformance. Language support is a
   **declarative adapter manifest** — the core never assumes a language (NFR-007); language-agnostic
   gates (diff-coverage, conformance, secret, dependency) live in the core. One normalized **verdict**
   per run, identical across languages (NFR-001/FR-033), every failure actionable (FR-034).

3. **The trust spine (§9).** No mandatory CI/CD enforcer; trust is recovered locally: an append-only
   **hash-chained, Ed25519-signed verdict ledger**; a `verify` that fails on any tamper/gap/break; a
   local `advance` enforcement gate; full **reversibility** (`revert`, FR-070); and signed build
   **provenance + SBOM** verified at a **deploy gate** (`provenance`/`deploy-gate`, FR-066–068), signed
   by the same independent identity as the ledger. Self-contained and offline-reconstructable (NFR-004/010).

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
