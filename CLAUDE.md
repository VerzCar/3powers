# CLAUDE.md

This file guides Claude Code (claude.ai/code) when working in this repository. It carries the
architecture deep-dive; the **workflow rules are in [`AGENTS.md`](AGENTS.md)** — the mandatory
intent → plan → implementation plan → implementation chain, the agent roles under
[.github/agents/](.github/agents/), branch and commit discipline (dedicated feature branch, **no pull
requests**), and the open-source-readiness rules. Those rules are binding here too.

## What 3Powers is

A portable, open **judiciary kit** for spec-driven, agentic software delivery. Premise: when one model
writes the spec, the code, the tests, *and* the review, validation becomes circular — the
**separation-of-powers collapse**. 3Powers restores three independent branches:

- **Legislative** — the spec is the law every later stage answers to.
- **Executive** — agents do the building.
- **Judicial** — an independent oracle, a deterministic gate suite, and human review judge whether the
  code matches the spec.

It owns a **native, provider-agnostic executive** — `3pwr run` dispatches headless coding agents
directly — uses Git as substrate, and is agnostic to model family, language, LLM provider, and CI/CD
platform.

**Implementation status lives in exactly one place: [docs/STATUS.md](docs/STATUS.md)** — the current
milestone, the validation date, and the open residuals. Do not infer scope or progress from this file;
read STATUS.

## Build / test / gate commands

Authoritative pinned versions live in the lockfiles (`engine/uv.lock`, the e2e harness
`e2e/harness/uv.lock`, and the per-adapter sample lockfiles under `e2e/<name>/project/`).

```bash
uv tool install ./engine            # install the `3pwr` command (reinstall with --force after engine changes)
(cd engine && uv sync --extra dev && uv run pytest)   # engine dev env + tests
(cd engine && uv run ruff check . && uv run mypy src) # engine lint + types

3pwr keygen                         # create the independent signer (key kept OUTSIDE the repo)
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

The full `3pwr` command surface — gate runs, ledger verification, lifecycle runs (`3pwr run`), oracle
independence, brownfield Stage Zero, deviations/emergency, observe — is documented once, publicly, in
[docs/cli-reference.md](docs/cli-reference.md). Consult it there; it is not duplicated in this file.

**`3pwr run "<intent>"` drives the whole lifecycle**: the native executive
dispatches each stage to a headless coding agent, streams a stage tracker, runs the gate suite in-process,
and in `auto` mode stops only at the two human gates (spec approval, sign-off). Post-approval stage
prompts reload the approved spec + the prior stage's artifact reference; a phased tasks
artifact makes implement run **one fresh headless session per phase** — concurrently for `[P]`-marked phases with
disjoint file scopes — with per-phase context estimates warned (never blocked) against the advisory
budget in `.3powers/config/context.yaml`. Each run's artifacts lie flat in its auto-allocated feature
folder `specs/<NNN>-<slug>/`, alongside an engine-maintained `progress.md`; the legacy split layout
(`specs/<feature>/spec/spec.md` + `specs/<feature>/artifacts/`) stays readable. For a hands-on,
step-by-step run, drive the stages with the `3pwr` CLI and the judiciary `/3pwr.*` prompts (`/3pwr.oracle`
→ `/3pwr.verify` → `/3pwr.review` → `/3pwr.signoff` → `/3pwr.advance`);

## Architecture (the big picture)

The framework drives an **eight-stage lifecycle** with explicit human gates: Discovery → Spec → Plan →
Build → Verify → Review → Ship → Observe. Three pillars carry the trust (the High-risk tier):

1. **Oracle independence.** Oracle tests are authored from the spec's acceptance criteria by a
   *judiciary* role pinned to a **different model family** than the coder, forbidden from reading the
   implementation. The coder's tests may self-verify but never replace the
   oracle. *As built:* `/3pwr.oracle` authors from a **sealed spec-only bundle** (`3pwr oracle seal`);
   `oracle record` captures the actual model + signer + test hashes and refuses the coder's family;
   `oracle verify` and a **High-risk `advance`** prove independence from the signed ledger seq — seal-binding,
   diversity, Phase-A-before-B ordering, and per-criterion coverage (FR-020/062). **Physical read-path
   isolation is delivered (FR-021, A3):** `3pwr oracle dispatch` authors the oracle *headlessly* via
   the native runner under a non-coder integration, inside a **sanitized git worktree** with the
   implementation/plan/tasks/contracts physically absent — attested by a worktree manifest hash and enforced
   at a High-risk `advance` (`roles.oracle.require_dispatch`). Reading/touching heuristics stay **advisory**,
   never a blocker.

2. **Deterministic gate engine.** Cheapest-first: `format`/`lint` → `types` → **`spec_integrity`** (the
   approved spec's sealed hash still matches) → `tests` + `diff_coverage` →
   `mutation` → `sast` → `dependency_scan` → `secret_scan` → `gate_gaming` → `spec_conformance`. **Work-kind inference then
   *shapes* the set**: a `defect` run adds a regression gate, a `design` run
   adds the adapter-supplied design oracles — it only ever *adds*, never weakening a tier gate. Language support is a **declarative adapter manifest** — the core never assumes a language
   (NFR-007; TypeScript + Python + **Go**); language-agnostic gates (`diff_coverage`, `spec_conformance`, `secret_scan`,
   `dependency_scan`) live in the core. One normalized **verdict** per run, identical across languages
   (NFR-001/FR-033), every failure actionable (FR-034).

3. **The trust spine.** No mandatory CI/CD enforcer; trust is recovered locally: an append-only
   **hash-chained, Ed25519-signed verdict ledger**; a `verify` that fails on any tamper/gap/break; a
   local `advance` enforcement gate; full **reversibility** (`revert`); and signed build
   **provenance + SBOM** verified at a **deploy gate** (`provenance`/`deploy-gate`), signed
   by the same independent identity as the ledger. Self-contained and offline-reconstructable.

## Working in this repo

- **Follow the mandatory workflow in [`AGENTS.md`](AGENTS.md).** Intent → plan (planning agent, `plan/PLAN-*`)
  → implementation plan (implementation-plan agent, `plan/IMPLEMENTATION-*`) → implementation. Code
  changes are always instructed by an implementation plan; Python changes under `engine/` go through the
  python-engineer agent. Work on a dedicated feature branch; **do not open pull requests**.
- **Engine changes must keep the engine green under its own gates** (ruff/mypy/pytest; `diff_coverage` and
  conformance via `3pwr gate run --path engine`). Trust-spine modules (`canonical`, `keys`, `ledger`,
  `verify`) are High-risk — hold their coverage ≥95%.
- **Real-world testing of the `3pwr` CLI happens in the `e2e/` notebook projects** — one small sample per
  language adapter, each driven through the whole lifecycle in a throwaway sandbox via `./e2e/run.sh <lang>`
  (`--check` for the deterministic, no-agent path). See [`e2e/README.md`](e2e/README.md). There is no
  top-level `examples/` folder.
- **Everything public-facing must be open-source ready** (see [`AGENTS.md`](AGENTS.md)): no internal
  plan/spec/requirement references in `docs/` or CLI help, and every behavior change lands with a
  matching docs update in the same unit of work.
