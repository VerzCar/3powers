# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository.

> **The spec is the single source of truth.** [`3Powers_Spec_v0.2.md`](specs/3Powers_Spec_v0.2.md)
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

It owns a **native, provider-agnostic executive** (A1′) — `3pwr run` dispatches headless coding agents
directly — uses Git as substrate (A2), and is agnostic to model family, language, LLM provider, and CI/CD
platform. (GitHub Spec Kit was the original substrate; it was removed by SLIM, spec 010.)

## Current state

**Implementation status lives in exactly one place: [`docs/STATUS.md`](docs/STATUS.md)** — the current
milestone, the validation date, and the open residuals, validated against the spec. Do not infer scope or
progress from this file; read STATUS. The implementation history is the plan series under
[`plan/`](plan/) (001 → …), each plan ending with a Verification section.

Durable facts you can rely on here: the full cheapest-first gate suite (`format → lint → types →
spec_integrity → tests → diff_coverage → mutation → sast → dependency_scan → secret_scan → gate_gaming →
spec_conformance`, plus work-kind-shaped gates) and the signed, hash-chained, offline-verifiable trust
spine (ledger / `verify` / `advance` / reversibility / provenance) are delivered and **self-applied at
High-risk** (NFR-006); three reference adapters (TypeScript, Python, Go); structural oracle independence
with headless, read-path-isolated **oracle** dispatch (A3, oracle leg); one-command orchestration
(`3pwr run`, stopping only at the two human gates FR-006/FR-037); brownfield Stage Zero; emergency &
deviation paths; the observe & feedback loop; the spec-lock (SLOCK) + trust-hardening (HARDN)
mechanisms; and **phased execution** (PHASE, spec 013) with the **run artifact workspace** (SRCX, spec
017) layered on top: each run gets one auto-allocated, FLAT feature folder (`specs/<NNN>-<slug>/` holding
`spec.md`, `plan.md`, `tasks.md`, `oracle.md`, `implement.md`; SRCX supersedes PHASE's `spec/spec.md` +
`artifacts/` split, which stays readable for existing features), every producing stage's markdown is
ledger-tracked and gated by a deterministic artifact-∧-ledger completion check — on `--resume` too —
and plans decompose work into **context-budgeted phases** (advisory ~110k-token default,
`.3powers/config/context.yaml`), the implement stage running **one fresh headless session per phase** —
in parallel for `[P]`-marked phases with disjoint file scopes.

## Repository layout

```
engine/                     # the `3pwr` engine — Python, shipped as a uv tool
  src/threepowers/          #   cli, gates, mutation, characterize, deviations, conformance, covdiff, oracle,
                            #   observe, deps, workkind, design, speclock, orchestrate, runner, agents, prompts,
                            #   artifacts, phases, workspace, hosted, steering, notify, frame, adapters, scanners,
                            #   ledger, verify, anchor, keys, verdict, config, canonical
  tests/                    #   pytest suite (the engine gates itself — A6/NFR-006)
.3powers/                   # in-repo trust spine (self-contained; FR-071)
  config/{risk-tiers,roles,dependencies,observability,design-oracles,context}.yaml   schemas/*.json   adapters/{CONTRACT.md,<lang>/adapter.yaml}  # <lang> ∈ typescript,python,go
  agents/*.yaml (native agent backends)   memory/constitution.md   templates/agents/*.agent.md (per-stage agent templates, AGENTX) + templates/{plan,tasks}-template.md
  ledger.jsonl  keys/ledger.pub   feedback/<spec>.md  runtime/actions.jsonl  (private key OUTSIDE the repo — NFR-005)
.github/{prompts,agents}/   # /3pwr.{oracle,verify,review,signoff,advance,characterize} command prompts for a manual drive (no Spec Kit)
specs/                      # authoritative specs (FR-010); the epic + per-feature specs
                            #   a run's artifacts lie FLAT in its auto-allocated folder: specs/<NNN>-<slug>/
                            #   {spec,plan,tasks,oracle,implement}.md (SRCX-FR-001); the PHASE split layout
                            #   (<f>/spec/spec.md + <f>/artifacts/) and the pre-013 flat <f>/spec.md both resolve
examples/validation-utils/  # the runnable TypeScript sample (spec id VUTIL)
docs/references/            # trust-spine tooling reference + historical Spec Kit reference (removed by SLIM, spec 010)
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
3pwr gate run --path <dir> --adapter <ts|python|go> --spec specs/<feature>/spec.md --tier <tier>
# Work-kind-shaped gates (FR-058 → FR-008/009): a defect adds a regression gate, a design run the design
# oracles. Never weakens a tier gate; the inference is deterministic (NFR-001).
3pwr gate run --path <dir> --spec <spec> --tier <tier> --work-kind defect   # requires a regression test (FR-008)
3pwr gate run --path <dir> --spec <spec> --tier <tier> --work-kind design   # runs design oracles; quarantines missing (FR-009)
3pwr verify                         # recompute ledger chain + signatures, offline
3pwr signoff --approver <you> --stage review --spec-id <ID>
3pwr signoff --approver <you> --stage spec --spec-id <ID> --spec specs/<f>/spec.md  # seals the spec's hash (SLOCK-FR-001)
3pwr spec diff --spec-id <ID>       # read-only: does the spec still match its approval hash? (SLOCK-FR-007)
3pwr advance --stage ship           # refuses unless gate green + ledger verifies + sign-off present + spec unchanged

# The whole lifecycle in one command (§6, FR-011): auto mode stops ONLY at the two human gates (FR-006/037).
# GITX (spec 018): git is a run precondition; the run refuses a dirty unrelated start, works on its own
# branch `3pwr/<NNN>-<slug>` (reusing the SRCX identity), and commits each producing stage as `3pwr`
# with an agent-written message — relaxable only via the signed git_* deviations (FR-057).
3pwr classify "<intent>"                            # FR-058: infer work kind(s) + a suggested risk tier
3pwr run "<intent>" --mode auto                     # streams a live stage tracker; native executive dispatches headless agents (EXEC-FR-001)
3pwr run --resume --spec-id <ID> --approver <you>   # after a human gate: record sign-off + continue
3pwr run --status --spec-id <ID>                    # stage tracker + run branch/committed stages   (try it offline: add --dry-run)
3pwr git start --spec-id <ID> --feature specs/<f>   # manual drive: establish + bind the run branch (GITX-FR-016)

# Oracle independence (Phase A, §7): seal a spec-only bundle, author from it, then record + verify.
# At High-risk, `advance` refuses unless independence holds (FR-020/021/022/062).
3pwr oracle seal   --spec specs/<feature>/spec.md --spec-id <ID>
3pwr oracle record --spec-id <ID> --model <family/model> --tests <oracle-test-paths>  # refuses coder's family
# A3 (physical FR-021): author the oracle HEADLESSLY, read-path isolated — the implementation is absent from
# a sanitized git worktree. The oracle role's headless agent CLI is set in `.3powers/config/roles.yaml`.
3pwr oracle dispatch --spec-id <ID> --integration claude   # + `--dry-run` to build/attest isolation offline
3pwr oracle verify --spec-id <ID> [--require-dispatch]   # seal-binding + diversity + ordering + coverage (+ isolation); advisory peek/touch

3pwr deps-check                     # probe installed third-party versions (scanners, adapter toolchains) vs supported ranges (FR-048)

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
# `--gate model_diversity` is the recommend-not-force relief for FR-022 (single-model dev proceeds, warned):
3pwr deviation --gate model_diversity --approver <you> --note "single-model dev"   # FR-022 via FR-057
3pwr emergency --approver <you> --note "<why>"                                 # FR-056 (defers mutation+coverage; 1-day cleanup)
```

**`3pwr run "<intent>"` drives the whole lifecycle** (§6, plans 013/018/019/023): the native executive
dispatches each stage to a headless coding agent, streams a stage tracker, runs the gate suite in-process,
and in `auto` mode stops only at the two human gates (spec approval, sign-off). Post-approval stage
prompts reload the approved spec + the prior stage's artifact reference (PHASE-FR-005); a phased tasks
artifact makes implement run **one fresh session per phase** — concurrently for `[P]`-marked phases with
disjoint file scopes — with per-phase context estimates warned (never blocked) against the advisory
budget in `.3powers/config/context.yaml` (PHASE-FR-007..012). For a hands-on,
step-by-step run, drive the stages with the `3pwr` CLI and the judiciary `/3pwr.*` prompts (`/3pwr.oracle`
→ `/3pwr.verify` → `/3pwr.review` → `/3pwr.signoff` → `/3pwr.advance`); for an existing repo, start with
`/3pwr.characterize` on a legacy module.

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
   the native runner under a non-coder integration, inside a **sanitized git worktree** with the
   implementation/plan/tasks/contracts physically absent — attested by a worktree manifest hash and enforced
   at a High-risk `advance` (`roles.oracle.require_dispatch`). Reading/touching heuristics stay **advisory**,
   never a blocker (NFR-001). Opt-in and High-risk-only — the default flow stays in-IDE and watchable; the
   coder leg also running headless (the fuller dispatch) is the residual.

2. **Deterministic gate engine (§8).** Cheapest-first: `format`/`lint` → `types` → **`spec_integrity`** (the
   approved spec's sealed hash still matches — SLOCK) → `tests` + `diff_coverage` →
   `mutation` → `sast` → `dependency_scan` → `secret_scan` → `gate_gaming` → `spec_conformance`. **Work-kind inference then
   *shapes* the set** (FR-058, plan 015): a `defect` run adds a regression gate (FR-008), a `design` run
   adds the adapter-supplied design oracles (FR-009) — it only ever *adds*, never weakening a tier gate
   (FR-032). Language support is a **declarative adapter manifest** — the core never assumes a language
   (NFR-007; TypeScript + Python + **Go**); language-agnostic gates (`diff_coverage`, `spec_conformance`, `secret_scan`,
   `dependency_scan`) live in the core. One normalized **verdict** per run, identical across languages
   (NFR-001/FR-033), every failure actionable (FR-034).

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
- **Engine changes must keep the engine green under its own gates** (ruff/mypy/pytest; `diff_coverage` and
  conformance via `3pwr gate run --path engine`). Trust-spine modules (`canonical`, `keys`, `ledger`,
  `verify`) are High-risk — hold their coverage ≥95%.
- **Scope phasing** (§17): v0.1 = trust-spine MVP → v0.5 = full judiciary (remaining gates, provenance,
  residual review, eval harness) → v1.0 = lifecycle & ecosystem (brownfield, observe, catalog).
