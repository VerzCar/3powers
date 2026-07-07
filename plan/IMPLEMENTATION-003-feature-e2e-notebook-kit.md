---
goal: Build a per-adapter Jupyter-notebook e2e testing kit under e2e/ and retire examples/ (plan 032)
version: 1.0
date_created: 2026-07-06
last_updated: 2026-07-07
owner: 3Powers maintainers
status: 'Completed'
tags: [feature, e2e, testing, notebooks, adapters, docs]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This implementation plan executes [plan/032-e2e-adapter-notebook-projects.md](032-e2e-adapter-notebook-projects.md).
It delivers, as one delivery unit on branch `claude/3powers-e2e-testing-plan-lo46g1`, a
notebook-driven end-to-end testing kit for the `3pwr` CLI itself: a new top-level `e2e/` folder
holding one small enterprise-baseline sample project per language adapter (TypeScript, Python, Go),
a shared sandbox harness, a single shared headless-integration config, a fixed Jupyter notebook per
project that provisions a dedicated sandbox and readies the project before any `3pwr` command runs,
a one-command complete-run wrapper (`./e2e/run.sh <lang>`), the deletion of
`examples/validation-utils/`, and the `AGENTS.md`/`CLAUDE.md`/docs updates that redirect real-world
CLI testing to the new kit.

Every task traces to a track in plan 032 (noted `[A]`, `[B]`, `[C]`, `[D]`). All decisions in plan
032's "Decisions recorded" table are confirmed (the user resolved all open questions on 2026-07-06,
choosing `copilot` as the default headless integration) and are not re-opened here.

## 1. Requirements & Constraints

Requirements (from plan 032 tracks):

- **REQ-001** (A): A shared harness lives under `e2e/harness/` — a uv-managed project
  (`pyproject.toml` + committed `uv.lock`) pinning `jupyter`, `papermill`, and `nbclient`, plus
  `e2e/harness/bootstrap.py` (stdlib-only, no engine imports) that provisions a sandbox: copy a
  project template tree to a throwaway directory, `git init` + initial commit, install project
  dependencies from the lockfile per language, run sandbox-scoped `3pwr keygen`, export
  `THREEPOWERS_SIGNING_KEY_FILE`, run `3pwr init --yes --language <lang>`, and overlay
  `e2e/config/roles.yaml`.
- **REQ-002** (A): Exactly one shared headless-integration config, `e2e/config/roles.yaml`, names
  the coder integration `copilot` and the oracle integration `copilot` pinned to a **different
  model family** (honoring the diversity recommendation; copilot makes the family switch a
  config-only change), with `require_dispatch` left at its default. No sample project carries its
  own copy — the config is seeded into every sandbox by `bootstrap.py` after `3pwr init`.
- **REQ-003** (A): One easy run command, `e2e/run.sh`, maps `<typescript|python|go>` to its
  notebook and executes it headlessly via `uv run --project e2e/harness papermill …`; it forwards
  `--intent`, `--integration`, `--keep` (KEEP_SANDBOX), and `--check`; it writes the executed
  notebook (with outputs) and a run log to the sandbox's artifact directory — never back into the
  repo — and propagates the notebook's exit status.
- **REQ-004** (B): Three sample projects under `e2e/`, each a plain template tree at
  `e2e/<name>/project/` with **no inner `.git` and no installed dependencies committed**, built to
  the enterprise baseline of plan 032 decision 5: layered `src/` (config → domain → service), typed
  error handling, a small logging abstraction, unit **and** integration tests, a lockfile,
  `README.md`, `.gitignore`, `.editorconfig`. Names/domains (accepted as proposed):
  `typescript-orders` (order pricing), `python-inventory` (inventory tracking), `go-ratelimit`
  (rate limiting). **Explicitly excluded** from every project: Dockerfiles, Kubernetes/IaC, CI
  pipelines, auth, databases, external network calls.
- **REQ-005** (B): Each project is wired **exactly** to its adapter manifest
  (`engine/src/threepowers/scaffold/adapters/<lang>/adapter.yaml`) so its full gate set is green at
  Standard tier from a fresh sandbox: TypeScript → Biome (`biome ci`), `tsc --noEmit`, Vitest with
  LCOV at `coverage/lcov.info`, Stryker config; Python → `ruff format --check`/`ruff check`,
  `mypy src` (strict), `pytest --cov` LCOV at `coverage/lcov.info`, mutmut config, under uv; Go →
  `gofmt`, `go vet ./...`, `go build ./...`, `go test -coverprofile` piped through `gcov2lcov` to
  `coverage/lcov.info`. Test files follow the adapter's conformance `test_declarations` and
  `assertion_patterns` so `spec_conformance` binding works on runs that add requirements.
- **REQ-006** (C): Three fixed `run.ipynb` notebooks (one per project), each implementing the
  identical 10-cell skeleton from plan 032 (parameters → toolchain preflight → sandbox provisioning
  → trust setup → **baseline gates green before the lifecycle run** → lifecycle run → spec approval
  → sign-off → post-run assertions → teardown). All `3pwr` invocations are in plain shell-style
  cells so the transcript reads as a CLI session an agent can mimic. Committed notebooks keep
  **cleared outputs**.
- **REQ-007** (C): The two mandatory human gates are **exercised, never bypassed**: the notebook
  runs `3pwr run "$INTENT" --mode auto --no-input`, expects the documented pause at the spec gate
  (exit code 3), renders the generated spec for the driving agent/human to read, then continues
  with `3pwr run --resume --approver "$APPROVER"`; the same resume mechanics handle the sign-off
  gate. `run.sh` defaults `APPROVER` to `e2e-harness` (overridable per run; confirmed decision 3).
- **REQ-008** (C): A deterministic, zero-credential path exists: `./e2e/run.sh <lang> --check` (or
  `DRY_RUN=true`) provisions the sandbox, runs the baseline gates, and runs `3pwr run --dry-run` —
  no live agent dispatch. Post-run assertions on a full run check **invariants only** (`3pwr verify`
  exits 0; `3pwr status` shows the completed run; the feature folder `specs/<NNN>-<slug>/` holds the
  stage artifacts; one cheap behavioral smoke per project), never exact agent-authored content.
- **REQ-009** (D): `examples/` is deleted in full (`validation-utils` is its only content) in the
  **same unit of work** as the doc updates, so no commit leaves a dangling reference.
- **REQ-010** (D): Every instruction surface is updated per the Track D table: `AGENTS.md`
  (repository-layout block, key-technologies line, setup commands, testing instructions — plus the
  new rule that real-world CLI testing happens in the `e2e/` notebook projects and that `examples/`
  is deleted), `CLAUDE.md` (lockfile line + the same real-world-testing instruction in "Working in
  this repo"), `README.md` (quickstart gate-run demo re-targeted), `docs/getting-started.md`,
  `docs/cli-reference.md` (four example blocks), `docs/STATUS.md` (sample references + the e2e kit
  recorded as the runnable sample surface), and both `dependencies.yaml` comment copies
  (`.3powers/config/dependencies.yaml` and `engine/src/threepowers/scaffold/config/dependencies.yaml`,
  edited in the same commit for seeded-copy parity).

Constraints:

- **CON-001**: Branch-only delivery — all work on `claude/3powers-e2e-testing-plan-lo46g1`, **no
  pull requests** (AGENTS.md/CLAUDE.md). Committed per track: A → B (three commits, one per project,
  parallelizable) → C → D.
- **CON-002**: **No engine source changes are anticipated** — this is a pure `e2e/` + docs unit, so
  the python-engineer agent gate for `engine/` work is not triggered. If implementation reveals an
  engine bug (an e2e kit exists precisely to surface CLI bugs), that fix is its **own** plan/fix
  unit, never smuggled into this one.
- **CON-003**: `specs/001-validation-utils/` is **untouched** (confirmed decision 6) — it is history
  bound into the signed ledger; only `examples/validation-utils/` is deleted. Docs referencing the
  deleted example are re-pointed in Track D; the spec folder itself may reference the past freely.
- **CON-004**: The engine stays green after the delivery unit: `(cd engine && uv run ruff check . &&
  uv run mypy src && uv run pytest)`. No engine code changes are expected; if any test fixture
  references `examples/validation-utils`, it is re-pointed in the same commit as the deletion
  (Track D).
- **CON-005**: Committed template trees contain committed source + lockfiles only — never an inner
  `.git`, never installed dependencies (`node_modules/`, `.venv/`, Go module cache). Dependency
  install happens only inside the sandbox (`bootstrap.py`). After authoring each template, `git
  status` at repo root must be clean and the template complete.
- **CON-006** (open-source readiness): Everything under `e2e/` and every doc edit is public and
  open-source ready — no internal requirement IDs, plan numbers, or spec citations in `e2e/README.md`,
  notebook prose, project READMEs, or the docs prose touched here (AGENTS.md's OSS-readiness rule).
- **CON-007** (sandbox/gitignore hygiene): A `project/.gitignore` (e.g. `coverage/`,
  `node_modules/`) must not hide template source from the **outer** repo; verify each template's
  files are all tracked after authoring.
- **CON-008** (notebook output hygiene): Committed notebooks keep **cleared outputs**; `run.sh`
  writes executed copies to the sandbox only. This invariant is stated in `e2e/README.md`.

Guidelines & patterns:

- **GUD-001**: Every project domain is deliberately I/O-free (in-memory, no network, no DB) so runs
  are deterministic and the excluded-artifacts list (REQ-004) holds.
- **GUD-002**: Each project ships a canned default `INTENT` that produces representative work for a
  lifecycle run (real layers to modify, real tests to extend), so every adapter gate has genuine
  work to chew on.
- **PAT-001**: The 10-cell notebook skeleton is **identical** across all three notebooks; only the
  parameters cell's language/intent defaults and the single behavioral smoke assertion differ.
- **PAT-002**: One `bootstrap.py` implementation, three thin per-notebook call sites — the sandbox
  provisioning logic is not duplicated per language.

## 2. Implementation Steps

### Phase 1

- GOAL-001: [A] The shared harness, the single headless-integration config, and the one-command run
  wrapper exist and work end-to-end in `--check` mode against a placeholder/first project.
  Completion criteria: `e2e/harness/` installs from its committed lockfile; `bootstrap.py`
  provisions a sandbox (copy → git init → deps → keygen → init → config overlay) for at least one
  language; `e2e/run.sh <lang> --check` exits 0.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | [A] Create `e2e/harness/pyproject.toml` (a uv project pinning `papermill`, `jupyter`, `nbclient`) and generate + commit `e2e/harness/uv.lock`. The harness venv stays papermill-only; `bootstrap.py` imports nothing from it beyond the stdlib. | ✅ | 2026-07-07 |
| TASK-002 | [A] Write `e2e/harness/bootstrap.py` (stdlib only, no engine imports) exposing a provisioning entry point per REQ-001: copy `e2e/<name>/project/` to a fresh `tempfile.mkdtemp()` dir (excluding any `.git`, `node_modules`, `.venv`, coverage artifacts), `git init` + initial commit, install project deps from the lockfile by language (`npm ci` for TypeScript, `uv sync` for Python, `go mod download` for Go), run `3pwr keygen` with a sandbox-scoped key file, export `THREEPOWERS_SIGNING_KEY_FILE`, run `3pwr init --yes --language <lang>`, then copy `e2e/config/roles.yaml` over the initialized `.3powers/config/roles.yaml`. Print the sandbox path. Return the sandbox path + artifact dir. | ✅ | 2026-07-07 |
| TASK-003 | [A] Create `e2e/config/roles.yaml` per REQ-002: coder integration `copilot`; oracle integration `copilot` pinned to a different `model_family` than the coder (diversity recommendation); `require_dispatch` at default. Match the schema of `.3powers/config/roles.yaml` (the engine's `headless_integrations` list includes `copilot`). No internal IDs (CON-006). | ✅ | 2026-07-07 |
| TASK-004 | [A] Write `e2e/run.sh` (POSIX sh, `set -eu`): map `<typescript\|python\|go>` → `e2e/<name>/run.ipynb`; parse `--intent`, `--integration`, `--keep`, `--check`; invoke `uv run --project e2e/harness papermill <notebook> <sandbox-artifact>/executed.ipynb -p INTENT … -p DRY_RUN <check> …`; write the executed notebook + run log to the sandbox artifact dir (never the repo); exit with papermill's status. `--check` sets `DRY_RUN=true`. Make it executable (`chmod +x`). | ✅ | 2026-07-07 |
| TASK-005 | [A] Commit Track A (`e2e/harness/`, `e2e/config/roles.yaml`, `e2e/run.sh`). Do not yet wire the notebooks (Phase 5); a minimal smoke here uses a throwaway project fixture or is deferred to Phase 5's first notebook. | ✅ | 2026-07-07 |

Validation: `uv sync --project e2e/harness` succeeds from the committed lockfile; `python
e2e/harness/bootstrap.py --help` (or its documented invocation) runs; `git status` clean at repo
root (no sandbox artifacts tracked).

### Phase 2

- GOAL-002: [B] The `e2e/typescript-orders/project/` template exists at the enterprise baseline and
  is green under the full TypeScript adapter gate set from a fresh sandbox. Completion criteria:
  from a bootstrap-provisioned sandbox, `3pwr gate run` (Standard tier) is green; no inner `.git` or
  `node_modules` is committed.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-006 | [B] Scaffold `e2e/typescript-orders/project/`: an order-pricing service — `src/config/` (pricing config types), `src/domain/` (line items, tax rules, currency rounding — pure functions), `src/service/` (order service over the pricing domain), a small logging abstraction, typed error handling. No I/O (GUD-001). | ✅ | 2026-07-07 |
| TASK-007 | [B] Wire the toolchain exactly to `scaffold/adapters/typescript/adapter.yaml`: `package.json` + committed `package-lock.json`, strict `tsconfig.json`, `biome.json`, `vitest.config.ts` emitting LCOV to `coverage/lcov.info`, `stryker.conf.json`. Add `tests/unit/` and `tests/integration/` using describe/it + `expect` (matching the adapter's conformance patterns). `README.md`, `.gitignore` (ignoring `node_modules/`, `coverage/`), `.editorconfig`. | ✅ | 2026-07-07 |
| TASK-008 | [B] Verify from a fresh sandbox (via `bootstrap.py`): `npm ci` installs from the lockfile; `biome ci .`, `tsc --noEmit`, `vitest run --coverage` all green; `3pwr gate run` Standard tier green. Confirm the outer repo tracks only source + lockfile (CON-005/CON-007: `git status` clean, no `node_modules`/`coverage` staged). Commit the TypeScript project. | ✅ | 2026-07-07 |

Validation: fresh-sandbox `3pwr gate run` green for `typescript-orders`; `git ls-files
e2e/typescript-orders` lists source + `package-lock.json` only (no `.git`, no `node_modules`).

### Phase 3

- GOAL-003: [B] The `e2e/python-inventory/project/` template exists at the enterprise baseline and
  is green under the full Python adapter gate set from a fresh sandbox. Completion criteria:
  bootstrap-provisioned sandbox `3pwr gate run` (Standard tier) green; no `.venv`/`.git` committed.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-009 | [B] Scaffold `e2e/python-inventory/project/`: an inventory-tracking service in src-layout — `src/<pkg>/config/`, `src/<pkg>/domain/` (stock levels, reservations, reorder thresholds — typed models), `src/<pkg>/service/` (service layer over the domain), a small logging abstraction, typed error handling. No I/O (GUD-001). | ✅ | 2026-07-07 |
| TASK-010 | [B] Wire the toolchain exactly to `scaffold/adapters/python/adapter.yaml`: `pyproject.toml` + committed `uv.lock`, ruff config, strict mypy config, `pytest`/`pytest-cov` emitting LCOV to `coverage/lcov.info`, mutmut config. Add `tests/unit/` and `tests/integration/` using `def test_*` + `assert` (matching the adapter's conformance patterns). `README.md`, `.gitignore` (ignoring `.venv/`, `coverage/`, `__pycache__/`), `.editorconfig`. | ✅ | 2026-07-07 |
| TASK-011 | [B] Verify from a fresh sandbox: `uv sync` installs from the lockfile; `ruff format --check .`, `ruff check .`, `mypy src`, `pytest --cov` all green; `3pwr gate run` Standard tier green. Confirm outer repo tracks source + `uv.lock`/`pyproject.toml` only (CON-005/CON-007). Commit the Python project. | ✅ | 2026-07-07 |

Validation: fresh-sandbox `3pwr gate run` green for `python-inventory`; `git ls-files
e2e/python-inventory` lists source + lockfile only.

### Phase 4

- GOAL-004: [B] The `e2e/go-ratelimit/project/` template exists at the enterprise baseline and is
  green under the full Go adapter gate set from a fresh sandbox. Completion criteria:
  bootstrap-provisioned sandbox `3pwr gate run` (Standard tier) green; no build/module cache
  committed.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-012 | [B] Scaffold `e2e/go-ratelimit/project/`: a rate-limiter service — an idiomatic package layout with token-bucket and sliding-window strategies behind one interface, a limiter registry, a small logging abstraction, typed error handling. No I/O (GUD-001). | ✅ | 2026-07-07 |
| TASK-013 | [B] Wire the toolchain exactly to `scaffold/adapters/go/adapter.yaml`: `go.mod` + committed `go.sum`; ensure `gofmt -l .` is empty, `go vet ./...` and `go build ./...` clean; `go test -covermode=atomic -coverprofile=cover.out ./...` piped through `gcov2lcov` to `coverage/lcov.info`. Add table-driven unit tests + integration tests using `func TestX` + `t.Errorf`/`t.Fatalf` (matching the adapter's conformance patterns). `README.md`, `.gitignore` (ignoring `coverage/`, `cover.out`), `.editorconfig`. | ✅ | 2026-07-07 |
| TASK-014 | [B] Verify from a fresh sandbox: `go mod download`; `gofmt`/`go vet`/`go build` clean; `go test` + `gcov2lcov` produce `coverage/lcov.info`; `3pwr gate run` Standard tier green (mutation stays opt-in per the adapter's `tier_min: High-risk`). Confirm outer repo tracks source + `go.mod`/`go.sum` only (CON-005/CON-007). Commit the Go project. | ✅ | 2026-07-07 |

Validation: fresh-sandbox `3pwr gate run` green for `go-ratelimit`; `git ls-files e2e/go-ratelimit`
lists source + `go.mod`/`go.sum` only.

### Phase 5

- GOAL-005: [C] The three fixed notebooks and the complete-run path exist; `./e2e/run.sh <lang>`
  drives a full lifecycle run (both human gates exercised via resume) and `--check` drives the
  deterministic no-agent path. Completion criteria: `--check` green for all three; one full
  agent-driven run per language succeeds and its post-run invariant assertions pass.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-015 | [C] Author `e2e/typescript-orders/run.ipynb` implementing the identical 10-cell skeleton (PAT-001): (1) papermill Parameters cell — `INTENT` default "add a percentage-based bulk discount rule to order pricing", `INTEGRATION` from config, `MODE=auto`, `TIER=Standard`, `APPROVER=e2e-harness`, `KEEP_SANDBOX=false`, `DRY_RUN=false`; (2) toolchain preflight via the adapter's `probe` commands + `3pwr` + (unless DRY_RUN) the agent CLI, failing fast with the exact install hint; (3) sandbox provisioning via `bootstrap.py`; (4) trust setup (keygen/init/config overlay already done by bootstrap — assert it); (5) **baseline `3pwr gate run` must be green before the lifecycle run**; (6) `3pwr run "$INTENT" --mode auto --no-input` (`--dry-run` when DRY_RUN), assert the documented spec-gate pause (exit 3); (7) render the generated spec, then `3pwr run --resume --approver "$APPROVER"`; (8) same resume at sign-off; (9) post-run invariant assertions (`3pwr verify` exit 0; `3pwr status` shows the completed run; `specs/<NNN>-<slug>/` has stage artifacts; one behavioral smoke — the bulk-discount rule is present); (10) teardown (remove sandbox unless KEEP_SANDBOX; print path first). Commit with **cleared outputs** (CON-008). | ✅ | 2026-07-07 |
| TASK-016 | [C] Author `e2e/python-inventory/run.ipynb` and `e2e/go-ratelimit/run.ipynb` as byte-identical copies of the skeleton, differing only in the Parameters cell (language, canned INTENT — "add a low-stock reorder suggestion to the inventory service" / "add a fixed-window rate-limiting strategy") and the single behavioral smoke assertion in cell 9. Committed with cleared outputs. | ✅ | 2026-07-07 |
| TASK-017 | [C] Run `./e2e/run.sh typescript --check`, `./e2e/run.sh python --check`, `./e2e/run.sh go --check` — each provisions its sandbox, passes baseline gates, and runs `3pwr run --dry-run` with no agent dispatch. All three exit 0. Fix any harness/notebook wiring issues. | ✅ | 2026-07-07 |
| TASK-018 | [C] Run one full agent-driven lifecycle run per language (`./e2e/run.sh typescript`, then python, then go) with a working `copilot` CLI; confirm the post-run invariant assertions pass and the run completes green. Record each run's outcome in the delivery commit message (invariants only — never assert exact agent-authored content, plan 032 risk 2). Commit Track C. | ⏳ | needs live `copilot` creds |

Validation: `./e2e/run.sh <lang> --check` exits 0 for all three; one full run per language completes
with `3pwr verify` green and post-run invariants satisfied; committed notebooks have empty outputs
(`git diff --stat` shows no output churn on re-open).

> **Residual (TASK-018):** the deterministic `--check` path is verified for all three languages
> (baseline gates green → both human gates exercised via `--resume` on the sim runner → `3pwr verify`
> green → teardown). The live agent-driven run per language is credential-gated (a working `copilot`
> CLI + credentials, DEP-004 / RISK-001) and was not executed in the delivery environment; run it where
> that CLI is available to close TASK-018.

### Phase 6

- GOAL-006: [C] `e2e/README.md` documents the kit as its public guide. Completion criteria: the
  README covers prerequisites, the sandbox model, the one-command runs, the agent-driving procedure,
  and the fixed-notebook/cleared-output invariants — and contains no internal IDs (CON-006).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-019 | [C] Write `e2e/README.md`: prerequisites (uv, node, go, `gcov2lcov`, a `copilot` agent CLI); the ephemeral-sandbox model (why runs are copied out of the repo); the one-command runs (`./e2e/run.sh <lang>` for a full run, `--check` for the deterministic no-agent path); how an agent should drive a notebook (run cells top-to-bottom, read the rendered spec at the pause, then resume); and the invariants — committed notebooks are the fixed configuration (edit the procedure in the notebook, nowhere else) and are committed with cleared outputs. Open-source ready, no internal IDs. | ✅ | 2026-07-07 |

Validation: `e2e/README.md` renders; `grep -nE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' e2e/README.md`
finds nothing; links to the per-project notebooks resolve.

### Phase 7

- GOAL-007: [D] `examples/` is deleted and every instruction surface reflects the e2e kit, in one
  unit of work so no commit leaves a dangling reference. Completion criteria: `examples/` no longer
  exists; a repo-wide grep for `examples/validation-utils` (minus history-exempt paths) is empty;
  the engine suite is still green.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-020 | [D] Update `AGENTS.md`: repository-layout block (drop `examples/validation-utils/`, add `e2e/` with a one-line description); key-technologies line (replace the TypeScript-sample mention with the e2e kit); setup commands (replace the `cd examples/validation-utils && npm install` line with the e2e prerequisites + `./e2e/run.sh <lang> --check`); testing instructions (replace the validation-utils commands with the e2e run commands and add the rule: **real-world testing of the `3pwr` CLI happens in the `e2e/` notebook projects — drive them via `./e2e/run.sh`; the former `examples/` folder is deleted**). | ✅ | 2026-07-07 |
| TASK-021 | [D] Update `CLAUDE.md`: replace the `examples/validation-utils/package-lock.json` lockfile reference with the e2e lockfiles; add the same real-world-testing instruction to "Working in this repo". | ✅ | 2026-07-07 |
| TASK-022 | [D] Update `README.md` (quickstart gate-run demo re-targeted at an e2e project path or the engine itself), `docs/getting-started.md` ("try it on the sample" section rewritten around `e2e/` + `run.sh`, linking `e2e/README.md`), `docs/cli-reference.md` (the four example blocks using `examples/validation-utils`/`specs/001-validation-utils` paths → neutral e2e-based or placeholder paths; behavior text unchanged), and `docs/STATUS.md` (sample references updated; the e2e kit recorded as the runnable sample surface — STATUS stays the single status source). | ✅ | 2026-07-07 |
| TASK-023 | [D] Update the two `dependencies.yaml` comment copies in lockstep (same commit): `.3powers/config/dependencies.yaml` and `engine/src/threepowers/scaffold/config/dependencies.yaml` — the comments citing "supported ranges vs. the `examples/validation-utils/package-lock.json` lockfile" now cite `e2e/typescript-orders/project/package-lock.json`. | ✅ | 2026-07-07 |
| TASK-024 | [D] Delete the `examples/` folder (`git rm -r examples/`). Run the closing checks: `grep -rn "examples/validation-utils" .` excluding `specs/`, `plan/`, `.git`, `.3powers/ledger.jsonl`, `.3powers/verdicts/` returns nothing; `test ! -d examples`; `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green (re-point any test fixture referencing the examples path in this same commit, CON-004). `specs/001-validation-utils/` left untouched (CON-003). Set this plan's front-matter `status` to `Completed` and mark task tables done. Commit Track D. | ✅ | 2026-07-07 |

Validation: `test ! -d examples && echo gone`; the repo-wide grep is empty; engine suite green;
`specs/001-validation-utils/` unchanged.

## 3. Alternatives

- **ALT-001**: Run `3pwr` in-place inside each committed project instead of an ephemeral sandbox
  copy. Rejected (decision 1): a real `3pwr run` creates branches, a ledger, `specs/`, and verdicts;
  running in-place would nest git repos inside this repo or pollute it with run artifacts on every
  execution. The sandbox makes runs repeatable, disposable, and parallelizable — and is the
  "dedicated sandbox" the intent asks for.
- **ALT-002**: Drive notebooks with `nbclient`/`jupyter nbconvert --execute` directly instead of
  papermill. Rejected (decision 2): papermill gives parameterized, deterministic top-to-bottom
  execution with a clean parameters cell — the "fixed written notebook configuration" — and writes
  an executed copy without mutating the committed notebook.
- **ALT-003**: Bypass the two human gates in the notebook (e.g. a hypothetical `--auto-approve`).
  Rejected (decision 3): the gates are exercised via the CLI's own sanctioned `--resume --approver`
  path; the ledger records the approver, and an agent driving the notebook genuinely reads the spec
  between cells.
- **ALT-004**: Per-project headless-integration config. Rejected (decision 4): the intent says
  "configured once and used for all the sample projects" — the single `e2e/config/roles.yaml` is
  seeded into every sandbox; no project carries its own copy.
- **ALT-005**: Richer enterprise projects (Docker, CI, DB, auth). Rejected (decision 5): every extra
  artifact is surface the e2e kit must keep green forever; the baseline is chosen to be rich enough
  for representative lifecycle work but no more.
- **ALT-006**: Delete/edit `specs/001-validation-utils/` alongside the example. Rejected (decision
  6): the spec artifacts are history bound into the signed ledger; deleting them risks tripping
  `verify`/`spec_integrity` and erases the traceability record.
- **ALT-007**: Wire full lifecycle runs into CI. Rejected (decision 7): full runs dispatch a live
  coding agent (cost, credentials, nondeterminism); the deterministic `--check` path is the
  CI-friendly surface, and wiring it in is a separate follow-up, not this plan.
- **ALT-008**: Default the seeded integration to `claude`. Superseded by the user's decision:
  `copilot` is easier to access and can switch model families within one backend, which also makes
  coder-vs-oracle family diversity a config-only choice.

## 4. Dependencies

- **DEP-001**: The three language adapter manifests at
  `engine/src/threepowers/scaffold/adapters/{typescript,python,go}/adapter.yaml` — each project is
  wired to match its manifest's declared gate commands, coverage paths, and conformance patterns.
- **DEP-002**: The `3pwr` CLI installed (`uv tool install ./engine`) — every notebook drives
  `keygen`, `init`, `gate run`, `run`, `verify`, `status`.
- **DEP-003**: Language toolchains where the kit runs: Node + npm (TypeScript), uv + Python
  (Python), Go + `gcov2lcov` (Go). Probed by each notebook's preflight cell with the adapter's own
  install hints.
- **DEP-004**: A working `copilot` headless agent CLI + credentials for full lifecycle runs
  (Phase 5 TASK-018); the `--check`/`DRY_RUN` path needs none.
- **DEP-005**: The harness toolchain (`papermill`, `jupyter`, `nbclient`) pinned in
  `e2e/harness/uv.lock`.
- **DEP-006**: Intra-plan ordering: Phase 1 (harness) → Phases 2–4 (projects; parallelizable, each
  its own commit) → Phase 5–6 (notebooks + README, need both harness and projects) → Phase 7 (docs
  point at a working kit).

## 5. Files

- **FILE-001**: `e2e/harness/pyproject.toml`, `e2e/harness/uv.lock` — **new**: the papermill-pinned
  harness project (Phase 1).
- **FILE-002**: `e2e/harness/bootstrap.py` — **new**: stdlib-only shared sandbox provisioning
  (Phase 1).
- **FILE-003**: `e2e/config/roles.yaml` — **new**: the single shared headless-integration config,
  coder + oracle on `copilot` with distinct families (Phase 1).
- **FILE-004**: `e2e/run.sh` — **new**: the one-command run wrapper (Phase 1).
- **FILE-005**: `e2e/typescript-orders/project/**` — **new**: order-pricing sample wired to the
  TypeScript adapter (Phase 2).
- **FILE-006**: `e2e/python-inventory/project/**` — **new**: inventory sample wired to the Python
  adapter (Phase 3).
- **FILE-007**: `e2e/go-ratelimit/project/**` — **new**: rate-limiter sample wired to the Go adapter
  (Phase 4).
- **FILE-008**: `e2e/typescript-orders/run.ipynb`, `e2e/python-inventory/run.ipynb`,
  `e2e/go-ratelimit/run.ipynb` — **new**: the three fixed notebooks, cleared outputs (Phase 5).
- **FILE-009**: `e2e/README.md` — **new**: the kit's public guide (Phase 6).
- **FILE-010**: `AGENTS.md` — layout block, key-technologies line, setup commands, testing
  instructions + the real-world-testing rule (Phase 7).
- **FILE-011**: `CLAUDE.md` — lockfile line + the real-world-testing instruction (Phase 7).
- **FILE-012**: `README.md`, `docs/getting-started.md`, `docs/cli-reference.md`, `docs/STATUS.md` —
  re-targeted sample references (Phase 7).
- **FILE-013**: `.3powers/config/dependencies.yaml` and
  `engine/src/threepowers/scaffold/config/dependencies.yaml` — the two lockfile-citation comments,
  edited in lockstep (Phase 7).
- **FILE-014**: `examples/` — **deleted** in full (Phase 7).
- **FILE-015**: `specs/001-validation-utils/` — explicitly **untouched** (CON-003).
- **FILE-016**: `engine/` source — explicitly **unchanged** (CON-002); only a test fixture is
  re-pointed if it references the deleted examples path (CON-004).

## 6. Testing

- **TEST-001** (A): `uv sync --project e2e/harness` installs cleanly from the committed lockfile;
  `bootstrap.py` provisions a sandbox for each language (copy → git init → deps → keygen → init →
  config overlay) with no artifacts leaking into the outer repo.
- **TEST-002** (B, per project): From a fresh bootstrap-provisioned sandbox, dependency install from
  the lockfile succeeds and the full adapter gate set is green at Standard tier
  (`3pwr gate run`) — the standing kit invariant, encoded permanently by each notebook's baseline
  gate cell (cell 5).
- **TEST-003** (B, hygiene): `git ls-files e2e/<name>` lists source + lockfile only — no inner
  `.git`, no `node_modules`/`.venv`/build cache (CON-005/CON-007).
- **TEST-004** (C): `./e2e/run.sh <lang> --check` exits 0 for all three languages — the
  deterministic, zero-credential path (baseline gates + `3pwr run --dry-run`, no agent dispatch).
- **TEST-005** (C): One full agent-driven lifecycle run per language completes with both human gates
  exercised via `--resume`; post-run **invariant** assertions pass (`3pwr verify` exit 0; `3pwr
  status` shows the completed run; `specs/<NNN>-<slug>/` holds the stage artifacts; one behavioral
  smoke per project) — never exact agent-authored content (plan 032 risk 2).
- **TEST-006** (C, hygiene): Committed notebooks have cleared outputs — re-opening produces no diff
  churn (CON-008).
- **TEST-007** (D): `grep -rn "examples/validation-utils"` (minus `specs/`, `plan/`,
  `.3powers/ledger.jsonl`, `.3powers/verdicts/`, `.git`) is empty; `test ! -d examples`;
  `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green; the engine
  oss-readiness test still passes.
- **TEST-008** (CON-006): No internal requirement IDs in any `e2e/` file or touched docs prose —
  `grep -rnE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' e2e/` finds nothing.

## 7. Risks & Assumptions

- **RISK-001** (live runs need a real agent + credentials): On a machine without a working `copilot`
  CLI the kit looks broken. Mitigation: the preflight cell fails fast with the exact backend +
  install hint; `--check`/`DRY_RUN=true` gives a zero-credential deterministic path; `e2e/README.md`
  states the split plainly.
- **RISK-002** (nondeterminism/cost of live runs): An agent-authored spec/implementation differs run
  to run. Mitigation: post-run assertions check invariants (verify green, artifacts exist, gates
  passed, one behavioral smoke), never exact content; full runs are agent/human-driven, not CI
  (decision 7).
- **RISK-003** (sample projects drift red as adapters evolve): An adapter command change can silently
  break a `project/` tree. Mitigation: the baseline-gate cell (cell 5) fails the notebook before any
  agent is dispatched; `--check` makes that a one-command regression test; AGENTS.md's testing
  instructions tell agents to run it.
- **RISK-004** (sandbox/gitignore interference): A `project/.gitignore` must not hide template source
  from the outer repo; a template must never contain an inner `.git` or installed deps. Mitigation:
  bootstrap installs deps only in the sandbox; templates are committed source + lockfiles only;
  Phase 2–4 verification asserts `git ls-files` completeness (CON-005/CON-007).
- **RISK-005** (notebook output churn): Executed outputs committed by accident make every run a diff.
  Mitigation: committed notebooks keep cleared outputs (CON-008, stated in `e2e/README.md`);
  `run.sh` writes executed copies to the sandbox only.
- **RISK-006** (Go toolchain breadth): `gcov2lcov` (and optionally `go-mutesting`) are extra installs
  beyond `go`. Mitigation: preflight probes them with the adapter's own install hints;
  `e2e/README.md` prerequisites list them; mutation stays opt-in per the adapter's `tier_min:
  High-risk`.
- **RISK-007** (stray `examples/` reference survives): Mitigation: Track D closes with the repo-wide
  grep gate (history-exempt paths excluded) in TASK-024's delivery checklist.
- **RISK-008** (an engine bug surfaces during e2e runs): An e2e kit exists precisely to expose CLI
  bugs. Mitigation (CON-002): such a fix is a **separate** plan/fix unit, never folded into this
  delivery.
- **ASSUMPTION-001**: `copilot` is available in the engine's `headless_integrations` list and can be
  pinned to two different model families for the coder/oracle diversity split (confirmed by the
  user's decision).
- **ASSUMPTION-002**: The three adapter manifests' declared gate commands run green against a
  correctly-wired baseline project on the target machine's installed toolchains.
- **ASSUMPTION-003**: `papermill` supports the parameterized headless execution the notebooks rely
  on (Parameters-tagged cell, `-p` overrides, executed-copy output path).
- **ASSUMPTION-004**: No engine test fixture depends on `examples/validation-utils` beyond a path
  string; if one does, re-pointing it is mechanical and lands in TASK-024's commit.

## 8. Related Specifications / Further Reading

- [plan/032-e2e-adapter-notebook-projects.md](032-e2e-adapter-notebook-projects.md) — the source
  plan for this implementation plan
- `specs/<NNN>-e2e-notebook-kit/spec.md` (spec ID `E2EKIT`) — the kit's invariants (per-adapter
  project green under its full gate set from a fresh sandbox; fixed notebook skeleton; single shared
  headless config; one-command complete run; no `examples/` references outside history); `<NNN>` =
  next free workspace number at implementation time
- `engine/src/threepowers/scaffold/adapters/{typescript,python,go}/adapter.yaml` — the adapter
  manifests each sample project is wired to
- `engine/src/threepowers/scaffold/adapters/CONTRACT.md` — the language-adapter contract
- [docs/cli-reference.md](../docs/cli-reference.md) — the `3pwr` command surface the notebooks drive
- [AGENTS.md](../AGENTS.md) — mandatory workflow, branch/commit discipline (no pull requests),
  open-source-readiness rules; gains the real-world-testing rule in Phase 7
- [CLAUDE.md](../CLAUDE.md) — architecture deep-dive; gains the real-world-testing instruction in
  Phase 7
