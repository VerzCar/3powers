---
goal: v1.0 readiness — lifecycle artifacts, oracle traceability, run visibility, onboarding & the first stable release
version: 1.0
date_created: 2026-07-08
last_updated: 2026-07-08
owner: 3Powers maintainers (engine changes via the python-engineer agent)
status: 'Planned'
tags: [feature, refactor, migration, architecture, release]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan operationalizes the source plan
[`plan/033-v1-readiness-and-lifecycle-hardening.md`](033-v1-readiness-and-lifecycle-hardening.md)
(fourteen tracks A–N, finalized 2026-07-08) as seven sequential delivery phases on the existing
branch `feat/033-v1-readiness-and-lifecycle-hardening`. The work sharpens the artifacts, records,
and onboarding a user sees and trusts while driving `3pwr run`, unifies oracle traceability,
makes sessions and cost visible, adds an auditable scanner-ignore knob, improves constitution
onboarding, and cuts the first stable **v1.0** (release candidate first, then `1.0.0`).

The invariants that bound every phase: **the deterministic verdict, the signed ledger's
verification, exit codes, and `--json` byte-stability never change** except where a payload gains a
strictly *additive* field (which `3pwr verify` already tolerates). Token accounting and per-phase
gate runs are **advisory** — a model never touches the verdict. New writes use the new names and
locations; read-resolution stays tolerant of the legacy `specs/`, `tasks.md`, and `implement.md`;
no ledger is ever rewritten.

## 1. Requirements & Constraints

Functional requirements (each traces to a source-plan track and the self-application spec ID it
maps to):

- **REQ-001** (Track K, N — `SRCDIR`): Rename the run-artifact base folder `specs/` → `specs-src/`
  everywhere it is derived, contracted, regex-matched, prompted, templated, and documented; new
  runs write `specs-src/<NNN>-<slug>/`; legacy `specs/` still resolves; the three e2e notebook
  `specs` globs become `specs-src`.
- **REQ-002** (Track A — `LIFEART`): Rename the tasks-stage artifact to `implementation-plan.md`
  (write new, resolve legacy `tasks.md`).
- **REQ-003** (Track B — `LIFEART`): Replace the engine-generated `implement.md` record with an
  engine-generated `changelog.md` (grouped by phase, requirement-id traced, byte-deterministic;
  resolve legacy `implement.md`). Top-level `CHANGELOG.md` stays hand-maintained.
- **REQ-004** (Track C — `LIFEART`): Every generated implementation plan runs the coding-section
  gates after each build phase (agent-run, advisory) and ends with a mandatory final Verification
  phase; the Verify stage remains the sole ledger verdict.
- **REQ-005** (Track D — `LIFEART`): Drop the plan's "Judicial" label and remove the
  role→model-family table (never engine-parsed); keep risk tier & gates and requirement→phase
  coverage.
- **REQ-006** (Track E — `ORATRACE`): Key oracle seal/record/dispatch/verify and `oracle.md` by the
  run's `<NNN>-<slug>` folder id everywhere; decouple the requirement namespace (the spec
  document's Spec ID) from the storage/record key (the folder id).
- **REQ-007** (Track F — `ORATRACE`): Author an implementation-agnostic `oracle.md` (Tests
  Specification) merged into `oracle.agent.md`; keep the runnable oracle tests; the engine validates
  coverage and path-freeness.
- **REQ-008** (Track G — `RUNVIS`): Guarantee and prove a fresh session per stage and phase (with a
  backend hook to force clean sessions where a CLI would resume); make `[P]` sub-agent dispatch
  explicit in the build prompt.
- **REQ-009** (Track H — `RUNVIS`): Persist per-stage and per-phase token consumption — additive,
  in `progress.md`, the ledger, and `--json`; never in the verdict.
- **REQ-010** (Track I — `SCANIGN`): Add `.3powers/config/scan.yaml` with per-tool ignore globs,
  optional per-rule suppression, and a small default ignore set; thread it through `gates.py` into
  the scanners; the core ed25519 walk honors it.
- **REQ-011** (Track J — `ONBRD`): Document `observability.yaml` in-file and in the docs.
- **REQ-012** (Track M — `ONBRD`): Add an init constitution-adaptation CTA plus an in-file
  adaptation guide and mandatory-content checklist (technical baseline + policies).
- **REQ-013** (Track L — `V1REL`): Cut the first stable v1.0 — RC (`1.0.0-rc.1`) then `1.0.0`:
  version bump, STATUS/README/CHANGELOG, constitution version bump + re-ratify, test fixups, release
  checklist.

Security requirement:

- **SEC-001** (Track I): Scanner exclusions are **reported** in the gate output, never silently
  dropped; the core `ed25519-priv` private-key check always runs regardless of any ignore config;
  docs warn that broad ignores weaken the gate. Exclusions are deterministic given the committed
  config.

Constraints:

- **CON-001**: No pull requests. All work stays on the existing branch
  `feat/033-v1-readiness-and-lifecycle-hardening`, delivered as sequential units (AGENTS.md /
  CLAUDE.md).
- **CON-002**: Engine (Python under `engine/`) changes go through the **python-engineer agent**;
  each phase lands green — `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`
  plus self-application `3pwr gate run --path engine` — before the next phase starts.
- **CON-003**: The verdict, ledger verification, exit codes, and `--json` byte-stability never
  change except via strictly-**additive** payload fields (`3pwr verify` already tolerates them).
  Tokens (Track H) and per-phase coding-gate runs (Track C) are advisory and never enter the
  verdict.
- **CON-004**: Backward compatibility — new writes use the new names/locations; read-resolution
  resolves the new name/base first and falls back to the legacy `specs/`, `tasks.md`, `implement.md`;
  **no ledger rewrite** (old signed entries keep their `specs/...` paths and must keep resolving on
  disk).
- **CON-005**: `oracle.md` stays implementation-agnostic — no file paths, frameworks, library
  calls, or source paths; traceability comes from Track E's keyed destination
  `tests/oracle/<NNN>-<slug>/` plus id-named tests, not from paths inside `oracle.md`.
- **CON-006**: Sealed / skeleton-bound assets — the plan and tasks templates are bound by a
  template-skeleton conformance test (`engine/tests/test_phases.py`), and the constitution is
  sealable. Any edit to them updates the conformance test in lockstep and, if the sealed
  constitution/epic trips `spec_integrity`/`gate_gaming`, the maintainer re-seals (documented path)
  or records a signed `3pwr deviation` in the ledger.
- **CON-007**: Trust-spine modules (`canonical`, `keys`, `ledger`, `verify`, and oracle-record code
  touching signed entries) hold coverage ≥95%.

Guideline & patterns:

- **GUD-001**: Open-source readiness — no internal plan/spec/requirement IDs in user-facing text
  (CLI help/messages, engine docstrings/comments, `docs/` prose, scaffold assets); `specs-src/` is
  exempt; format teaching uses `DEMO-FR-###`/`DEMO-NFR-###`; enforced by
  `engine/tests/test_oss_readiness.py`.
- **PAT-001**: Read-resolution tolerance — resolve the new name/base first, then fall back to the
  legacy one (mirrors `workspace.find_artifact` / `spec_path` layout tolerance).
- **PAT-002**: Additive-only payload evolution — new ledger/`--json`/progress fields are added, never
  renamed or removed, so `3pwr verify` and the e2e notebooks' defensive `.get()` parsing stay green.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Rename the run-artifact base folder `specs/` → `specs-src/` across engine literals,
  the critical `artifacts.py`/`gitflow.py` regexes, prompts, templates, docs, and the repo's own
  folders (keeping legacy `specs/` resolvable), and fix the three e2e notebooks' `specs` globs
  (Tracks K + N). This is delivered first because later phases write to and assert on the new paths.
  Completion criterion: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` is
  green, `3pwr gate run --path engine` is green, `./e2e/run.sh {python,typescript,go} --check` each
  exit 0, and a legacy `specs/` layout still resolves.

**File scope**: `engine/src/threepowers/workspace.py`; `engine/src/threepowers/artifacts.py`;
`engine/src/threepowers/gitflow.py`; `engine/src/threepowers/cli/run.py`;
`engine/src/threepowers/cli/brownfield.py`; `engine/src/threepowers/characterize.py`;
`engine/src/threepowers/prompts.py`; `engine/src/threepowers/scaffold/templates/agents/*.agent.md`
and `.3powers/templates/agents/*.agent.md`;
`engine/src/threepowers/scaffold/templates/` + `.3powers/templates/` (`plan-template.md`,
`tasks-template.md`); `engine/src/threepowers/scaffold/constitution.md` +
`.3powers/memory/constitution.md` (line 17); `docs/**`; `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
`README.md`; `e2e/{python-inventory,typescript-orders,go-ratelimit}/run.ipynb`; the repo's own
`specs/` → `specs-src/` (git mv); `engine/tests/**` (~143 references across the 20 test files that
name `specs`).

**Depends on**: none.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | [Track K / SRCDIR] In `engine/src/threepowers/workspace.py` introduce module constants `SPECS_DIR = "specs-src"` and `LEGACY_SPECS_DIR = "specs"`; replace the hardcoded `root / "specs"` write/derive literals at lines 101 (`find_specs`), 124 (`resolve_feature_dir`), 176 (`allocate_feature_dir`) and the module docstring examples with `SPECS_DIR`. Verify: `grep -n '"specs"' engine/src/threepowers/workspace.py` shows no write-side literal and `SPECS_DIR`/`LEGACY_SPECS_DIR` are defined. | ✅ | 2026-07-08 |
| TASK-002 | [Track K / SRCDIR] Make `workspace.find_specs` and `workspace.resolve_feature_dir` read-tolerant (PAT-001): glob `specs-src/` first, then fall back to legacy `specs/`. Verify: a unit test asserts a feature under `specs-src/<NNN>-<slug>/` and a legacy one under `specs/<NNN>-<slug>/` both resolve. | ✅ | 2026-07-08 |
| TASK-003 | [Track K / SRCDIR] Fix `engine/src/threepowers/artifacts.py` `STAGE_ARTIFACTS` regexes at lines 90/96/104 (specify/plan/tasks) to match the new base and keep matching legacy, e.g. `r"(^\|/)specs(-src)?/.+/spec\.md$"`. Verify: `artifacts.verify()` passes for a produced `specs-src/<f>/spec.md` (and `plan.md`, `tasks.md`) and still for legacy `specs/<f>/...`. | ✅ | 2026-07-08 |
| TASK-004 | [Track K / SRCDIR] Fix `engine/src/threepowers/gitflow.py` `_PROGRESS_FILE` regex at line 58 to `r"^specs(-src)?/[^/]+/progress\.md$"`. Verify: `gitflow.unrelated_changes` ignores `specs-src/<f>/progress.md` (and legacy) in a unit test. | ✅ | 2026-07-08 |
| TASK-005 | [Track K / SRCDIR] Replace remaining base literals: `engine/src/threepowers/cli/run.py:1684` (`feature_folder_name(s.root / "specs", …)` and the "specs/…" message at 1686), `engine/src/threepowers/cli/brownfield.py:46` (`root / "specs"` default), and the allocation in `engine/src/threepowers/characterize.py`, all to use `workspace.SPECS_DIR`. Verify: `grep -rn 'root / "specs"' engine/src/threepowers/cli engine/src/threepowers/characterize.py` returns nothing. | ✅ | 2026-07-08 |
| TASK-006 | [Track K / SRCDIR] Reconcile the scaffold/prompt inconsistency to `specs-src`: `engine/src/threepowers/prompts.py` lines 43/53/68 (`specs/<feature>/…` → `specs-src/<feature>/…`), every `scaffold/templates/agents/*.agent.md` + `.3powers/templates/agents/*.agent.md` that says `specs-source`, `plan-template.md`, `tasks-template.md`, and constitution line 17. Verify: `grep -rn 'specs-source' engine/src/threepowers .3powers` returns nothing and `grep -n 'specs/<feature>' engine/src/threepowers/prompts.py` returns nothing. | ✅ | 2026-07-08 |
| TASK-007 | [Track K / SRCDIR] Physically move the repo's own run-artifact base: `git mv specs specs-src` (all 29 existing feature folders). Verify: `test -d specs-src && ! test -d specs`. | ✅ | 2026-07-08 |
| TASK-008 | [Track K / SRCDIR] Update docs and top-level markdown references from `specs/` to `specs-src/` (keeping a legacy mention where back-compat is explained): `docs/**`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`. Verify: `grep -rn '\bspecs/' docs AGENTS.md CLAUDE.md README.md CONTRIBUTING.md` shows only intentional legacy/back-compat mentions. | ✅ | 2026-07-08 |
| TASK-009 | [Track N / SRCDIR] In `e2e/python-inventory/run.ipynb`, `e2e/typescript-orders/run.ipynb`, `e2e/go-ratelimit/run.ipynb` update cell 7 (`(SANDBOX_DIR/"specs").glob("*/spec.md")`, ~line 221) and cell 9 (feature-dir glob, ~line 279) plus the `# writes the spec to specs/<NNN>-<slug>/` comments to `specs-src`. Verify: `grep -rn '"specs"' e2e/*/run.ipynb` returns nothing (only `specs-src`). | ✅ | 2026-07-08 |
| TASK-010 | [Track K / SRCDIR] Mechanically update the ~143 `specs`→`specs-src` references across the 20 `engine/tests/*.py` files; add a back-compat test asserting a legacy `specs/` feature layout still resolves via `find_specs`/`resolve_feature_dir` and that `--resume` re-checks a legacy-path ledger entry (no ledger rewrite, CON-004). Verify: `uv run pytest` green; a `grep -rn '"specs"' engine/tests` shows only the deliberate legacy-compat tests. | ✅ | 2026-07-08 |
| TASK-011 | [Track K / SRCDIR] Update the artifact-contract and gitflow regex tests and the specs-path references inside the template-skeleton conformance test (`engine/tests/test_phases.py` lines 163/168, `engine/tests/test_stage_agents.py`) to `specs-src`. Verify: `uv run pytest engine/tests/test_phases.py engine/tests/test_stage_agents.py` green. | ✅ | 2026-07-08 |
| TASK-012 | [Track N / SRCDIR] Run `./e2e/run.sh python --check`, `./e2e/run.sh typescript --check`, `./e2e/run.sh go --check` after the rename. Verify: each command exits 0 and the sandbox lifecycle stays green. | ✅ | 2026-07-08 |
| TASK-013 | [Track K / SRCDIR] python-engineer lands Phase 1 green and reinstalls: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine`, `uv tool install --force ./engine`; if editing constitution line 17 trips `spec_integrity`/`gate_gaming`, the maintainer re-seals or records a signed `3pwr deviation` (CON-006). Verify: all three green; `3pwr verify` green over the (unrewritten) ledger. | ✅ | 2026-07-08 |

### Phase 2

- GOAL-002: Land the lifecycle-artifact tracks — rename the tasks artifact to
  `implementation-plan.md` (A); replace the `implement.md` record with an engine-generated
  `changelog.md` (B); mandate per-phase coding gates and a final Verification phase (C); and
  de-judicialize the plan doc, dropping the role→model-family table (D). Completion criterion: a
  `3pwr run` writes `specs-src/<NNN>-<slug>/implementation-plan.md` and `changelog.md`; the plan
  emits no "Judicial" label or role table; the template-skeleton conformance test is green; engine
  green under CON-002.

**File scope**: `engine/src/threepowers/workspace.py` (`PRODUCING_STEPS`, `stage_artifact_path`,
`find_artifact`); `engine/src/threepowers/artifacts.py` (`STAGE_ARTIFACTS` tasks + implement);
`engine/src/threepowers/completion.py` (`RECORD_STEPS`, `render_implement_record`→changelog,
`write_record`); `engine/src/threepowers/prompts.py` (`tasks`/`plan`/`implement` bodies);
`engine/src/threepowers/phases.py` (`handoff_context`, the tasks-artifact reader);
`engine/src/threepowers/cli/run.py` (record wiring 889-912); `engine/src/threepowers/cli/gate.py`
(coverage-check / scope-check readers); scaffold + `.3powers` `implementation-plan.agent.md`,
`implement.agent.md`, `plan.agent.md`; scaffold + `.3powers` `plan-template.md`,
`tasks-template.md` (renamed to `implementation-plan-template.md`); `docs/cli-reference.md`,
`AGENTS.md`, `CLAUDE.md`, `docs/getting-started.md`, `docs/concepts.md`;
`engine/tests/{test_phases.py,test_run_workspace.py,test_native_runner.py,test_stage_agents.py}`.

**Depends on**: Phase 1 (all writes/asserts use the `specs-src/` base).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-014 | [Track A / LIFEART] In `workspace.py` map the `tasks` step to `implementation-plan.md` in `stage_artifact_path` and its `PRODUCING_STEPS` metadata; make `find_artifact` resolve `implementation-plan.md` first then legacy `tasks.md` (PAT-001). Verify: `stage_artifact_path(fdir, "tasks").name == "implementation-plan.md"` and `find_artifact` resolves a legacy `tasks.md`. | ✅ | 2026-07-08 |
| TASK-015 | [Track A / LIFEART] Update `artifacts.py` `STAGE_ARTIFACTS["tasks"]` `expected` + `patterns` (lines 98-105) to `implementation-plan.md` while still matching legacy `tasks.md`. Verify: `artifacts.verify()` passes for a produced `specs-src/<f>/implementation-plan.md` and for legacy `tasks.md`. | ✅ | 2026-07-08 |
| TASK-016 | [Track A / LIFEART] Update the `prompts.py` `tasks` instruction body (line 67) to write `specs-src/<feature>/implementation-plan.md`. Verify: `grep -n 'implementation-plan.md' engine/src/threepowers/prompts.py` matches and `grep -n 'tasks.md' engine/src/threepowers/prompts.py` no longer appears in the tasks body. | ✅ | 2026-07-08 |
| TASK-017 | [Track A / LIFEART] Point the phase reader and completion markers at the renamed artifact: `phases.py` locate-tasks-artifact logic + `handoff_context` "update tasks.md" lines (359, 376) → `implementation-plan.md` (reader falls back to legacy `tasks.md`); update `cli/gate.py` coverage-check/scope-check readers. Verify: phases parse from `implementation-plan.md`; `uv run pytest engine/tests/test_phases.py` green. | ✅ | 2026-07-08 |
| TASK-018 | [Track A / LIFEART] Rename the template file `tasks-template.md` → `implementation-plan-template.md` (`git mv` in both scaffold and `.3powers/templates/`), update its `Output` line and `plan-template.md` references; update `implementation-plan.agent.md` front-matter `artifact:` and body from `tasks.md` to `implementation-plan.md` (scaffold + `.3powers` copies). Verify: renamed files exist; `grep -rn 'tasks.md' <renamed template + implementation-plan.agent.md>` returns nothing. | ✅ | 2026-07-08 |
| TASK-019 | [Track A / LIFEART] Update the template-skeleton conformance test (`test_phases.py` line 163 now reads `implementation-plan-template.md`) and `test_stage_agents.py` tasks-artifact assertions; add a regression test that a run writing `implementation-plan.md` passes the completion gate and a legacy `tasks.md` still resolves. Verify: `uv run pytest engine/tests/test_phases.py engine/tests/test_stage_agents.py` green. | ✅ | 2026-07-08 |
| TASK-020 | [Track B / LIFEART] In `completion.py` replace `render_implement_record` with a `render_changelog` renderer: grouped by phase, each entry tracing to its requirement id, listing files changed and a one-line what/why, Keep-a-Changelog-flavored (Added/Changed/Fixed by work-kind) with a machine-parseable requirement-id column, byte-deterministic given the collected phase results + the implement agent's completion report. Verify: a unit test asserts identical bytes for a fixed input and a requirement-id column present. | ✅ | 2026-07-08 |
| TASK-021 | [Track B / LIFEART] Rename the implement step's producing artifact from `implement.md` to `changelog.md`: `workspace.stage_artifact_path("implement")` → `changelog.md` (legacy `implement.md` read fallback in `find_artifact`), `completion.write_record` writes `changelog.md`, keep `RECORD_STEPS = ("oracle","implement")`. Verify: `stage_artifact_path(fdir, "implement").name == "changelog.md"`; `find_artifact` resolves a legacy `implement.md`. | ✅ | 2026-07-08 |
| TASK-022 | [Track B / LIFEART] In `implement.agent.md` (scaffold + `.3powers`) add an instruction to include a concise per-change summary in the completion report that the engine folds into `changelog.md`. Verify: `grep -n 'changelog' engine/src/threepowers/scaffold/templates/agents/implement.agent.md` matches. | ✅ | 2026-07-08 |
| TASK-023 | [Track B / LIFEART] Update the `cli/run.py` record wiring (lines 889-912) so the implement step's record path is `changelog.md`, added to `result.artifact_paths` and `produced_box`; confirm the top-level `CHANGELOG.md` is untouched. Verify: a `3pwr run` writes `specs-src/<NNN>-<slug>/changelog.md`; top-level `CHANGELOG.md` unchanged by the run. | ✅ | 2026-07-08 |
| TASK-024 | [Track B / LIFEART] Update `test_run_workspace.py` / completion tests; add a test asserting the changelog groups by phase, carries each phase's requirement ids and changed files, and is byte-deterministic; assert a legacy `implement.md` still resolves. Verify: `uv run pytest engine/tests/test_run_workspace.py` green. | ✅ | 2026-07-08 |
| TASK-025 | [Track C / LIFEART] In `implementation-plan.agent.md` (scaffold + `.3powers`) add two rules: (1) every phase's tasks include running the coding-section gates (format, lint, types, tests + diff-coverage) over the phase's file scope and fixing failures before the phase is "done"; (2) the last phase is always a dedicated "Verification" phase depending on all prior phases whose goal is a fully green build. Name `3pwr gate run --path <scope>` and the project's own verify commands. Verify: `grep -in 'Verification' engine/src/threepowers/scaffold/templates/agents/implementation-plan.agent.md` matches and the gate-run rule is present. | ✅ | 2026-07-08 |
| TASK-026 | [Track C / LIFEART] In `implement.agent.md` (scaffold + `.3powers`) promote "validate as you go" from soft to mandatory: after each phase run the coding gates (engine or project scripts) and fix everything before reporting `done`; a phase with a red coding gate is not complete. Verify: `grep -in 'coding gate' engine/src/threepowers/scaffold/templates/agents/implement.agent.md` matches the mandatory rule. | ✅ | 2026-07-08 |
| TASK-027 | [Track C / LIFEART] In `phases.py handoff_context` inject the concrete coding-gate command (`3pwr gate run --path <scope>` and/or project verify commands) so a fresh session knows exactly what to run per phase. Verify: `handoff_context(...)` output contains the coding-gate command in a `test_phases.py`/`test_phase_prompt.py` assertion. | ✅ | 2026-07-08 |
| TASK-028 | [Track C / LIFEART] Document the pattern (per-phase gates + mandatory final Verification phase) in `plan-template.md` and `implementation-plan-template.md`, and update the template-skeleton conformance test in lockstep (CON-006). Verify: templates contain the pattern; `uv run pytest engine/tests/test_phases.py` green. | ✅ | 2026-07-08 |
| TASK-029 | [Track C / LIFEART] Add tests: `test_stage_agents.py`/template-content tests assert the new per-phase-gate and final-Verification instructions are present; a plan-shape test asserts a generated implementation plan carries a final verification phase depending on all others. Verify: `uv run pytest engine/tests/test_stage_agents.py` green. | ✅ | 2026-07-08 |
| TASK-030 | [Track D / LIFEART] In `plan.agent.md` (scaffold + `.3powers`) and `prompts.py` `plan` body (lines 53-64): rename the "Judicial Plan" section to a neutral heading ("Risk tier & gates"), delete the "Role → model-family" subsection and its output-skeleton table, drop the "Roles: coder/oracle/reviewer" line from the completion report; keep tier→gates and requirement→phase coverage. Verify: `grep -in 'Judicial\|role → model-family\|model-family table' engine/src/threepowers/prompts.py engine/src/threepowers/scaffold/templates/agents/plan.agent.md` returns nothing. | ✅ | 2026-07-08 |
| TASK-031 | [Track D / LIFEART] In `plan-template.md` (scaffold + `.3powers`) remove the "3Powers Judicial Plan" heading and the "Role → model-family assignment" table; keep risk tier & gates, the Phase-A oracle intent table, phase decomposition, and structure. Verify: `grep -in 'model-family' <both plan-template.md copies>` returns nothing. | ✅ | 2026-07-08 |
| TASK-032 | [Track D / LIFEART] Update the template-skeleton conformance test and `test_stage_agents.py` plan-section assertions in lockstep; add a test asserting the role→model-family table is absent from the plan template. Verify: `uv run pytest engine/tests/test_phases.py engine/tests/test_stage_agents.py` green. | ✅ | 2026-07-08 |
| TASK-033 | [Tracks A+B+C+D / LIFEART] python-engineer lands Phase 2 green: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine`, `3pwr verify`; if the plan/tasks template-skeleton conformance or the sealed constitution trips, update the conformance test and re-seal or record a signed deviation (CON-006). Verify: all green. | ✅ | 2026-07-08 |

### Phase 3

- GOAL-003: Unify oracle traceability — key oracle seal/record/dispatch/verify and `oracle.md` by
  the run's `<NNN>-<slug>` folder id, decoupling the requirement namespace from the storage key (E);
  and merge an authored, implementation-agnostic `oracle.md` (Tests Specification) into
  `oracle.agent.md`, keeping the runnable oracle tests and validating them in the engine (F).
  Completion criterion: a `3pwr run` writes oracle tests to `tests/oracle/<NNN>-<slug>/`,
  `oracle verify` resolves seal ↔ record ↔ verdict ↔ `oracle.md` from one id, coverage counts
  `DEMO-FR-*` refs under a numeric folder key, and `oracle.md` is a per-requirement path-free
  specification; trust-spine coverage ≥95% (CON-007); engine green.

**File scope**: `engine/src/threepowers/cli/run.py` (oracle dispatch key wiring around 1691-1697);
`engine/src/threepowers/prompts.py` (oracle body 82-88);
`engine/src/threepowers/conformance.py` (`referenced_ids` 88-105);
`engine/src/threepowers/cli/oracle.py` (`dest_root` line 468, `--spec-id` default);
`engine/src/threepowers/completion.py` (`render_oracle_record` → validator); scaffold + `.3powers`
`oracle.agent.md`;
`engine/tests/{test_oracle_dispatch.py,test_oracle.py,test_conformance.py,test_conformance_binding.py}`.

**Depends on**: Phase 1 (`specs-src/` base); within the phase, Track E precedes Track F.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-034 | [Track E / ORATRACE] In `cli/run.py` stop shipping the literal `<spec-id>` placeholder to the oracle agent: compute the concrete destination `tests/oracle/<NNN>-<slug>/` from the run's feature-folder id and inject it as an explicit destination/file-scope block (mirroring how `oracle dispatch` re-keys). Verify: the assembled oracle-stage prompt names `tests/oracle/<NNN>-<slug>/` and contains no `<spec-id>` literal on the run path. | ✅ | 2026-07-08 |
| TASK-035 | [Track E / ORATRACE] Key `oracle seal`/`record`/`dispatch` on the run path by the same `<NNN>-<slug>` used for the run's ledger/records, so seal ↔ record ↔ verdict ↔ `oracle.md` share one key. Verify: a run's oracle ledger entries and record all carry the folder-id key. | ✅ | 2026-07-08 |
| TASK-036 | [Track E / ORATRACE] Decouple the requirement namespace from the storage key in `conformance.referenced_ids` (line 102): filter req-ids by the spec document's Spec ID (parsed from `spec.md` front matter, e.g. `DEMO`) while the storage/record key is the folder id. Verify: a coverage test counts `DEMO-FR-*` references under a numeric folder key (`030`) instead of dropping them. | ✅ | 2026-07-08 |
| TASK-037 | [Track E / ORATRACE] In `cli/oracle.py` set `dest_root` (line 468) to the folder id and default `--spec-id` to the run's feature-folder id when invoked inside a run/feature context; document that the id is the `<NNN>-<slug>` folder name. Keep back-compat: old oracle records keyed by other tokens still verify. Verify: a manual `oracle` command inside a feature context defaults its key to the folder id; an old-token record still verifies. | ✅ | 2026-07-08 |
| TASK-038 | [Track E / ORATRACE] Update `test_oracle_dispatch.py` + oracle-independence/coverage tests: a run keys destination and records by `<NNN>-<slug>`; coverage counts `DEMO-FR-*` under a numeric folder key; `oracle verify` is green end-to-end from a single id; assert trust-spine coverage ≥95% is held. Verify: `uv run pytest engine/tests/test_oracle_dispatch.py engine/tests/test_conformance.py` green. | ✅ | 2026-07-08 |
| TASK-039 | [Track F / ORATRACE] Merge the user's Tests-Specification instruction into `oracle.agent.md` (scaffold + `.3powers`) as one instruction with the ordered steps: (1) load the sealed spec-only bundle; (2) refuse on weak law → list under "Open Questions for the Legislature" and STOP (route to `clarify`, invent no thresholds); (3) author `oracle.md` (implementation-agnostic; one section per `FR/NFR` id; Given/When/Then; `type: acceptance\|property\|performance`; property invariant; NFR metric/threshold/boundary/protocol; "Notes for executor"; High-risk mutation flag; Coverage Summary); (4) author runnable oracle tests to `tests/oracle/<NNN>-<slug>/` named by requirement id; (5) self-check. Strip Spec-Kit residue (`$ARGUMENTS`, extension hooks, `.specify/`, `tests.md`); read thresholds from `.3powers/memory/constitution.md` + `.3powers/config/risk-tiers.yaml`; keep the current isolation rules. Verify: `oracle.agent.md` contains the template sections and `grep -in '.specify\|\$ARGUMENTS\|tests.md' <both oracle.agent.md copies>` returns nothing. | ✅ | 2026-07-08 |
| TASK-040 | [Track F / ORATRACE] Update the `prompts.py` oracle body (lines 82-88) to reference authoring the implementation-agnostic `oracle.md` first, then the runnable tests under `tests/oracle/<NNN>-<slug>/`, keeping the isolation rules (author only from the sealed spec; never read implementation/plan/tasks/contracts). Verify: `grep -n 'oracle.md' engine/src/threepowers/prompts.py` matches; the isolation clause is retained. | ✅ | 2026-07-08 |
| TASK-041 | [Track F / ORATRACE] Turn `completion.render_oracle_record` into a validator: if the agent wrote `oracle.md`, verify it names every `FR/NFR` id from the spec and contains no leaked file paths/framework tokens (a path/framework heuristic) and leave it in place; if absent, fall back to a structural stub from the sealed bundle (`requirement_id → criterion`) with sections marked "not authored" so gaps are visible. Keep the machine record of actual oracle test paths in the ledger (`oracle record` `test_paths`), so `oracle.md` stays path-free (CON-005). Verify: a leaked path or missing id is flagged; an absent `oracle.md` yields the visible stub. | ✅ | 2026-07-08 |
| TASK-042 | [Track F / ORATRACE] Add oracle-stage tests: `oracle.md` has a section per `FR/NFR` id, carries Given/When/Then (and metric/protocol for NFRs), and contains no file-path/framework token; a missing id or leaked path is flagged; an unmeasurable-AC spec produces the "Open Questions for the Legislature" stop (no invented tests); the isolation test (reads only the sealed spec) is preserved. Verify: `uv run pytest engine/tests/test_oracle.py` green. | ✅ | 2026-07-08 |
| TASK-043 | [Tracks E+F / ORATRACE] python-engineer lands Phase 3 green: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine` at the tier that exercises oracle independence, `3pwr verify`; hold trust-spine coverage ≥95% (oracle records touch signed entries, CON-007). Verify: all green. | ✅ | 2026-07-08 |

### Phase 4

- GOAL-004: Make sessions and cost visible — prove and harden a fresh session per stage and phase
  (with a backend hook to force clean sessions) and make `[P]` sub-agent parallelism explicit (G);
  and persist per-stage/per-phase token consumption additively in `progress.md`, the ledger, and
  `--json`, never in the verdict (H). Completion criterion: `build_command` never emits a
  session-reuse flag and each dispatch is an independent process; a run records tokens in
  `progress.md` and the stage/phase ledger payloads; `3pwr verify` is green over the new payloads
  and the verdict/`--json` gate bytes are unchanged whether or not usage is captured (CON-003).

**File scope**: `engine/src/threepowers/agents.py` (`build_command` 65-96, new `fresh_session`
handling); `engine/src/threepowers/runner.py` (`DispatchResult`/`StageResult` 58-121 + `as_dict`,
`CliAgentRunner.dispatch`, `HostedAgentRunner.dispatch` usage extraction);
`engine/src/threepowers/phases.py` (`handoff_context`) + `implement.agent.md` (sub-agent
parallelism); `engine/src/threepowers/progress.py` (token column); `engine/src/threepowers/cli/run.py`
(stage/phases/checkpoint ledger payloads); scaffold agent manifests (`usage`/`fresh_session`
fields under `scaffold/agents/`); `docs/concepts.md`, `docs/engine-architecture.md`,
`docs/cli-reference.md`; `engine/tests/{test_native_runner.py,test_phases.py}`.

**Depends on**: Phase 1.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-044 | [Track G / RUNVIS] Investigate whether the headless backends (`copilot -p` and the others) resume prior conversation/context by default; record the findings in the `RUNVIS` spec analysis. Verify: the analysis section documents, per backend, whether a clean session is default and which flag forces it. |  |  |
| TASK-045 | [Track G / RUNVIS] Add a per-manifest capability to force a clean session in `agents.build_command` (65-96): a `fresh_session`/`new_session_args` field that passes the CLI's no-resume / new-session flag (or isolates per-dispatch state via a unique session id / clean state dir). Verify: `build_command` emits the new-session args when the manifest declares `fresh_session`, and a round-trip/adapter test covers the field. |  |  |
| TASK-046 | [Track G / RUNVIS] Prove freshness with a test asserting `build_command` never emits a resume/continue/session-reuse flag and that each dispatch is an independent process (extend the runner tests). Verify: `uv run pytest engine/tests/test_native_runner.py` includes and passes the no-reuse assertion. |  |  |
| TASK-047 | [Track G / RUNVIS] Strengthen `phases.handoff_context` (372-374) and `implement.agent.md` to state plainly that `[P]`-marked parallel work must be executed via the agent's own sub-agents; keep the engine's concurrent dispatch of disjoint `[P]` phases as separate sessions unchanged. Verify: `handoff_context` output and `implement.agent.md` both contain the sub-agent instruction. |  |  |
| TASK-048 | [Track G / RUNVIS] Document the fresh-session guarantee and the sub-agent parallelism in `docs/concepts.md` and `docs/engine-architecture.md`. Verify: both docs describe the per-stage/per-phase clean session and `[P]` sub-agent dispatch. |  |  |
| TASK-049 | [Track H / RUNVIS] Capture agent-reported usage in `CliAgentRunner.dispatch` (and `HostedAgentRunner.dispatch`) via a per-backend extraction strategy declared in the manifest (a `usage` hint: a JSON field name or a regex over the agent's summary), returning `None` gracefully when a backend does not report it. Verify: unit tests over a JSON-strategy and a regex-strategy backend return token counts, and an unreporting backend returns `None`. |  |  |
| TASK-050 | [Track H / RUNVIS] Thread tokens through: add token fields to `DispatchResult` → `StageResult` (runner.py 58-121) and its `as_dict()` (additive, PAT-002). Verify: `StageResult.as_dict()` includes token fields only when present and remains a superset of the prior keys. |  |  |
| TASK-051 | [Track H / RUNVIS] Persist tokens to three places: (1) the `run`/`stage`, `run`/`phases`, and `run`/`checkpoint` ledger payloads as additive fields; (2) a token column in the per-stage/per-phase tables of `progress.md` (`progress.py` render + `_phases_view`); (3) the `StageResult` `--json`. Verify: a run's `progress.md` shows a token column and the stage ledger payload carries an additive token field. |  |  |
| TASK-052 | [Track H / RUNVIS] Determinism guard: ensure tokens never enter `run_gates`, the verdict, or the verdict bytes; add a test asserting the verdict/`--json` gate payloads are byte-identical whether or not usage is captured (CON-003), and an additive-JSON guard test protecting the e2e notebooks' `status`/verdict parsing (Track N). Verify: `uv run pytest` green; verdict bytes unchanged. |  |  |
| TASK-053 | [Track H / RUNVIS] Document where per-stage/per-phase tokens appear (`docs/cli-reference.md` run section + the `progress.md` description). Verify: docs name the token column and the ledger/`--json` fields and note "unknown" when a backend does not report. |  |  |
| TASK-054 | [Track H / RUNVIS] Add extraction unit tests per strategy (regex/JSON + unknown); assert a run records tokens in `progress.md` and the stage ledger payload and that `3pwr verify` is green over the new payloads. Verify: `uv run pytest engine/tests/test_native_runner.py engine/tests/test_phases.py` green. |  |  |
| TASK-055 | [Tracks G+H / RUNVIS] python-engineer lands Phase 4 green: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine`, `3pwr verify`. Verify: all green; verdict bytes unchanged. |  |  |

### Phase 5

- GOAL-005: Add an auditable, per-tool scanner-ignore config `.3powers/config/scan.yaml` (per-tool
  ignore globs + optional per-rule suppression + a small default ignore set), thread it through
  `gates.py` into the scanners, and honor it in the always-on core ed25519 walk — while the core
  private-key check always runs and every exclusion is reported (I / SEC-001). Completion criterion:
  an ignored path is excluded and reported, a non-ignored finding still fails, a malformed/absent
  `scan.yaml` falls back to no-exclusions, the core ed25519 check still fires, and the exclusion is
  deterministic; engine green.

**File scope**: `engine/src/threepowers/scaffold/config/scan.yaml` (new) +
`.3powers/config/scan.yaml` (new, committed); `engine/src/threepowers/config.py` (new
`scan_config_path` accessor + tolerant loader); `engine/src/threepowers/gates.py` (dispatch 547-559);
`engine/src/threepowers/scanners.py` (`secret_scan` 105, `dependency_scan` 174, `sast_scan` 208
signatures; core walk skip 62-102); `engine/src/threepowers/scaffold.py` (seed `scan.yaml`);
`docs/cli-reference.md`; `engine/tests/test_scanners.py`.

**Depends on**: Phase 1.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-056 | [Track I / SCANIGN] Add `engine/src/threepowers/scaffold/config/scan.yaml` and `.3powers/config/scan.yaml` with `version: 1`, per-tool `ignore` globs, optional per-tool `ignore_rules`, and a small default ignore set (`**/.next/**`, `**/dist/**`, `**/build/**`, `**/node_modules/**`) for `secret_scan`/`dependency_scan`/`sast`. Verify: both files exist and parse; the default ignore set covers `.next`. |  |  |
| TASK-057 | [Track I / SCANIGN] Add `Settings.scan_config_path` (`self.dir / "config" / "scan.yaml"`) in `config.py` and a tolerant loader (missing/malformed → no exclusions, mirroring `git.yaml` handling) returning per-tool `ignore` + `ignore_rules`. Verify: the loader returns the parsed ignores; a malformed file falls back to no-exclusions. |  |  |
| TASK-058 | [Track I / SCANIGN] Thread the loaded ignore config through the `gates.py` scanner dispatch (lines 547-559) into `scanners.sast_scan`/`dependency_scan`/`secret_scan`. Verify: the dispatch passes the per-tool ignore lists to each scanner call. |  |  |
| TASK-059 | [Track I / SCANIGN] Extend `scanners.py` signatures — `secret_scan` (105, +`ignore`/`ignore_rules`), `dependency_scan` (174, +`ignore`), `sast_scan` (208, +`ignore`) — and build the tool exclusions: semgrep `--exclude <glob>` (repeatable), betterleaks/gitleaks via a generated ignore/`--config` allowlist or path pre-filter, osv-scanner via config/path filtering; report excluded paths in the gate output (SEC-001). Verify: an ignored path is excluded and reported; a non-ignored finding still fails. |  |  |
| TASK-060 | [Track I / SCANIGN] Honor the ignore set in the always-on core ed25519 walk skip logic (`scanners.py` `_scan_candidates` 62-102): add the configured globs to the hardcoded skip set (which currently excludes `.git/node_modules/.venv/__pycache__/dist/build` but not `.next`), while the core private-key check still runs on everything else. Verify: the core walk skips configured globs but still fires on `ed25519-priv` material outside them. |  |  |
| TASK-061 | [Track I / SCANIGN] Seed `scan.yaml` non-clobbering at init in `scaffold.py` (mirroring the other seeded config). Verify: `3pwr init` writes `.3powers/config/scan.yaml` and does not overwrite an existing one. |  |  |
| TASK-062 | [Track I / SCANIGN] Add a `scan.yaml` section to `docs/cli-reference.md` plus a scanning note warning that broad ignores weaken the gate and that the core private-key check always runs (SEC-001). Verify: the doc describes the schema, the default ignore set, and the security caveats. |  |  |
| TASK-063 | [Track I / SCANIGN] Add per-scanner tests in `test_scanners.py`: an ignored path is excluded, a non-ignored finding still fails, the exclusion is reported, a malformed/absent `scan.yaml` falls back to no-exclusions, the core ed25519 check still fires, and results are deterministic. Verify: `uv run pytest engine/tests/test_scanners.py` green. |  |  |
| TASK-064 | [Track I / SCANIGN] python-engineer lands Phase 5 green: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine`, `3pwr verify`. Verify: all green. |  |  |

### Phase 6

- GOAL-006: Improve onboarding and observability documentation — explain `observability.yaml`
  in-file and in the docs (J); and add an init constitution-adaptation CTA plus an in-file
  adaptation guide and mandatory-content checklist covering the technical baseline and the policies
  (M). Completion criterion: `observability.yaml` carries explanatory headers using the reserved
  `DEMO-NFR-###` namespace; `3pwr init` output and `--json` next-steps flag adapting the
  constitution; the seeded constitution ships the guidance section and checklist; OSS-readiness
  stays green.

**File scope**: `engine/src/threepowers/scaffold/config/observability.yaml` +
`.3powers/config/observability.yaml` (header comments); `docs/cli-reference.md`, `docs/concepts.md`;
`engine/src/threepowers/cli/bootstrap.py` (constitution CTA + readiness line 99-105);
`engine/src/threepowers/scaffold/constitution.md` + `.3powers/memory/constitution.md` (adaptation
guide + checklist);
`engine/tests/{test_oss_readiness.py,test_auto_docs.py,test_init_experience.py,test_init_wizard_and_brownfield.py}`.

**Depends on**: Phase 1.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-065 | [Track J / ONBRD] Improve the `observability.yaml` header comments (bundled `scaffold/config/observability.yaml` + `.3powers/config/observability.yaml`): explain it is the NFR-instrumentation registry for `3pwr observe coverage`; each NFR with a live production check lists its `nfr:` id and a human `check:` note; the engine is offline so it cannot discover this itself; `observe coverage --spec <spec.md>` flags any NFR with no registered check. Confirm the shipped example uses the reserved `DEMO-NFR-###` namespace (GUD-001). Verify: both files carry the explanatory header and the example uses `DEMO-NFR-###`. |  |  |
| TASK-066 | [Track J / ONBRD] Add an "Observability registry" subsection to `docs/cli-reference.md` (near `observe coverage`) and `docs/concepts.md`. Verify: both docs describe the file's purpose and schema. |  |  |
| TASK-067 | [Track M / ONBRD] In `cli/bootstrap.py` add a prominent post-init advisory that the constitution at `.3powers/memory/constitution.md` is mandatory and must be adapted before the first real run (surfaced both interactively and in `--json` next-steps), and upgrade the readiness-checklist line (99-105) from the passive "in place / seeded" to an "adapt it" CTA pointing at the guidance section. Verify: `3pwr init --yes --json` output includes a constitution-adaptation next-step and the readiness line reads as a CTA. |  |  |
| TASK-068 | [Track M / ONBRD] Add to the constitution template (bundled `scaffold/constitution.md` + `.3powers/memory/constitution.md`) a top "How to adapt this constitution" block and a mandatory-content checklist: technical baseline (languages/runtime + versions; build/test/lint/type toolchain + the exact coding-gate commands; layout/module boundaries; architectural rules/patterns/anti-patterns; dependency policy; coding standards/naming; testing conventions + coverage/mutation per tier; docs expectations) and policies & rules (risk-tier defaults/thresholds; security/privacy rules — credentials, access control, hard-deletes, security config; branch/commit/PR discipline; definition of done; gate non-weakening; oracle-independence + traceability); a "What stays fixed" note (separation-of-powers principles I–VII); and "How to update" (edit, bump the version footer, record the amendment; note re-seal / signed deviation may be needed). Verify: the seeded constitution contains the guide, checklist, "what stays fixed", and "how to update" sections. |  |  |
| TASK-069 | [Track M / ONBRD / CON-006] Editing the sealable constitution may trip `spec_integrity`/`gate_gaming`: run `3pwr gate run --path engine` + `3pwr verify`; the maintainer re-seals (documented path) or records a signed `3pwr deviation`. Verify: gate + verify green; any re-seal/deviation recorded in the ledger. |  |  |
| TASK-070 | [Tracks J+M / ONBRD] Add/adjust tests: `test_init_experience.py` / `test_init_wizard_and_brownfield.py` assert init output/next-steps mention adapting the constitution and that the seeded constitution contains the guidance section + checklist; keep `test_oss_readiness.py` / `test_auto_docs.py` green (no internal spec IDs in shipped text; `DEMO-NFR-###`). Verify: `uv run pytest engine/tests/test_init_experience.py engine/tests/test_init_wizard_and_brownfield.py engine/tests/test_oss_readiness.py engine/tests/test_auto_docs.py` green. |  |  |
| TASK-071 | [Tracks J+M / ONBRD] python-engineer lands Phase 6 green: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)`, `3pwr gate run --path engine`, `3pwr verify`. Verify: all green. |  |  |

### Phase 7

- GOAL-007: Cut the first stable v1.0 (RC → `1.0.0`) — bump the engine and constitution versions,
  re-ratify the constitution, update STATUS/README/CHANGELOG, apply the test fixups, and execute the
  release checklist (L). Completion criterion: `3pwr --version` reports the bumped version; STATUS,
  README, CHANGELOG, and the constitution reflect the stable release; full self-application is green;
  a fresh `3pwr init` smoke passes; tags `1.0.0-rc.1` then `1.0.0` land on `main` after the RC
  settles.

**File scope**: `engine/pyproject.toml` (line 3); `engine/src/threepowers/__init__.py` (line 17);
`engine/src/threepowers/scaffold/constitution.md` + `.3powers/memory/constitution.md` (footer);
`docs/STATUS.md`, `README.md`, `docs/getting-started.md`; `CHANGELOG.md`;
`engine/tests/test_oss_readiness.py` (lines 263-264), `engine/tests/test_auto_docs.py` (line 65).

**Depends on**: all prior phases (1–6) green.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-072 | [Track L / V1REL] Bump the engine version in `engine/pyproject.toml` line 3 and `engine/src/threepowers/__init__.py` line 17 to `1.0.0` (RC path: `1.0.0-rc.1` first). Leave `SCHEMA_VERSION` unless a schema changed. Verify: after `uv tool install --force ./engine`, `3pwr --version` reports the bumped version. |  |  |
| TASK-073 | [Track L / V1REL / CON-006] Bump the constitution footer to `1.0.0` and re-ratify (together with Track M's amendment), re-sealing or recording a signed deviation if `spec_integrity`/`gate_gaming` trips. Verify: the constitution footer reads `1.0.0`; any re-seal/deviation is recorded in the ledger. |  |  |
| TASK-074 | [Track L / V1REL] Update `docs/STATUS.md` milestone to v1.0 (RC/released) and reframe the residuals section as accepted post-1.0 residuals (cross-platform NFR-003, fuller A3, live design/Go runs, catalog publishing, model-driven eval); update the `README.md` milestone line and the `docs/getting-started.md` `--version` example. Verify: STATUS milestone reads v1.0; README milestone matches; getting-started `--version` example updated. |  |  |
| TASK-075 | [Track L / V1REL] Move CHANGELOG's `[Unreleased] — v1.0 (in progress)` to `## [1.0.0]` (via `1.0.0-rc.1`), summarize plans 023–033, and update the compare/tag links. Verify: `CHANGELOG.md` contains a `## [1.0.0]` section and the tag/compare links resolve to the release tag. |  |  |
| TASK-076 | [Track L / V1REL] Apply the version test fixups: `engine/tests/test_oss_readiness.py` lines 263-264 (`## [0.5.0]` → `## [1.0.0]`, `releases/tag/v0.5.0` → `.../v1.0.0`, README `v0.5` → `v1.0`) and `engine/tests/test_auto_docs.py` line 65 (the stale pinned version string). Verify: `uv run pytest engine/tests/test_oss_readiness.py engine/tests/test_auto_docs.py` green. |  |  |
| TASK-077 | [Track L / V1REL] Execute the release checklist: all gates green self-applied at High-risk on the trust spine; `3pwr verify` green; `uv tool install --force ./engine` smoke; `3pwr --version` → the release version; a fresh `3pwr init` smoke; run the source-plan Verification block (`3pwr run "demo intent" --dry-run --spec-id DEMO`; `ls specs-src/<NNN>-demo-intent/` shows `spec.md plan.md implementation-plan.md oracle.md changelog.md progress.md`; `scan.yaml` present; init flags the constitution). Tag `1.0.0-rc.1` then `1.0.0` on `main` after the RC settles (branch discipline — no PR). Verify: the checklist commands all pass and both tags exist. |  |  |
| TASK-078 | [Track L / V1REL] python-engineer confirms final green across the engine: `(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine`. Verify: all green; the dry-run shows the new artifact names and fresh-session/token behavior. |  |  |

## 3. Alternatives

- **ALT-001**: Split the fourteen tracks into separate plans/branches. Rejected (source-plan
  decision 1) — a single coherent v1.0 push landed as sequential units on one branch avoids
  dribbling breaking changes and lets the RC absorb rename fallout once.
- **ALT-002**: Have the implement agent author `changelog.md` directly. Rejected (decision 2) —
  engine-generated keeps it model-independent, reproducible, and consistent with the existing
  engine-owned record path.
- **ALT-003**: Key oracle artifacts by the spec-document token (`DEMO`) instead of the folder id.
  Rejected (decision 3) — the folder id `<NNN>-<slug>` is what the user browses in `specs-src/`, so
  keying there makes "which oracle belongs to which spec" self-evident; the requirement namespace is
  decoupled separately.
- **ALT-004**: Let `oracle.md` carry test file paths for traceability. Rejected (decision 7 /
  CON-005) — `oracle.md` stays implementation-agnostic; traceability comes from the keyed
  destination + id-named tests, and the machine record of paths lives in the ledger.
- **ALT-005**: Put scanner ignores in the adapter manifest or `gates.yaml`. Rejected (decision 8) —
  a dedicated committed `.3powers/config/scan.yaml` keeps the security-sensitive knob explicit and
  auditable, and the scanners are core gates that read neither today.
- **ALT-006**: Release `1.0.0` directly without an RC or after closing a residual. Rejected
  (decision 4) — an RC first absorbs rename fallout; no residual blocks the release (the maintainer
  verifies manually), and STATUS reframes residuals as accepted post-1.0 items.
- **ALT-007**: Make per-phase gate runs part of the ledger verdict. Rejected (decision 6 / CON-003)
  — per-phase runs are the agent's own advisory checks; the Verify stage remains the sole signed
  verdict, preserving determinism.

## 4. Dependencies

- **DEP-001**: The source plan `plan/033-v1-readiness-and-lifecycle-hardening.md` (finalized
  2026-07-08) — the higher-order plan every phase traces to.
- **DEP-002**: The Python toolchain pinned by `engine/uv.lock` — `uv`, `pytest`, `ruff`, `mypy` —
  used to land each phase green (CON-002).
- **DEP-003**: `git` on PATH — the run lifecycle precondition and the `git mv` in Phase 1.
- **DEP-004**: The external scanners for Track I / Phase 5 tests — `betterleaks` (or `gitleaks`),
  `osv-scanner`, `semgrep`; absent binaries quarantine the external portion (never a false fail),
  and the core ed25519 check runs regardless.
- **DEP-005**: The signed verdict ledger and `3pwr verify` — the trust spine the additive payload
  fields (Track H) must remain compatible with (no rewrite; verify tolerant).
- **DEP-006**: `roles.yaml` + `oracle record` diversity enforcement — untouched by Track D (the
  removed role table was never engine-parsed); Track E must not regress it.
- **DEP-007**: The user-supplied Tests-Specification template (recorded verbatim in the source plan
  Track F) — the exact `oracle.md` shape merged into `oracle.agent.md`.
- **DEP-008**: The e2e harness (`e2e/harness/`, `e2e/config/roles.yaml`, per-adapter lockfiles) —
  left unchanged; only the three notebooks' `specs` globs change (Track N).

## 5. Files

- **FILE-001**: `engine/src/threepowers/workspace.py` — `SPECS_DIR` constant, `PRODUCING_STEPS`,
  `stage_artifact_path`, `find_artifact`, base-literal replacement (Tracks K, A, B).
- **FILE-002**: `engine/src/threepowers/artifacts.py` — `STAGE_ARTIFACTS` regexes/contracts for
  specify/plan/tasks (→ implementation-plan)/implement (Tracks K, A, B).
- **FILE-003**: `engine/src/threepowers/gitflow.py` — `_PROGRESS_FILE` regex for the `specs-src`
  base (Track K).
- **FILE-004**: `engine/src/threepowers/completion.py` — `render_implement_record` → changelog
  renderer, `render_oracle_record` → validator, `RECORD_STEPS`, `write_record` (Tracks B, F).
- **FILE-005**: `engine/src/threepowers/prompts.py` — specs-src base + tasks/plan/oracle/implement
  instruction bodies (Tracks K, A, D, F).
- **FILE-006**: `engine/src/threepowers/phases.py` — `handoff_context` (coding-gate command,
  sub-agent parallelism, renamed artifact) + the tasks-artifact reader (Tracks A, C, G).
- **FILE-007**: `engine/src/threepowers/conformance.py` — `referenced_ids` namespace decoupling
  (Track E).
- **FILE-008**: `engine/src/threepowers/cli/run.py` — feature-folder allocation base, oracle
  dispatch keying, record wiring, additive token ledger payloads (Tracks K, E, B, H).
- **FILE-009**: `engine/src/threepowers/cli/oracle.py` — `dest_root` + `--spec-id` default keyed by
  folder id (Track E).
- **FILE-010**: `engine/src/threepowers/cli/brownfield.py` + `characterize.py` — specs-src base
  defaults (Track K).
- **FILE-011**: `engine/src/threepowers/cli/bootstrap.py` — constitution-adaptation CTA + readiness
  line (Track M).
- **FILE-012**: `engine/src/threepowers/runner.py` — `DispatchResult`/`StageResult` token fields +
  usage extraction (Track H).
- **FILE-013**: `engine/src/threepowers/agents.py` — `build_command` fresh-session capability
  (Track G).
- **FILE-014**: `engine/src/threepowers/progress.py` — per-stage/per-phase token column (Track H).
- **FILE-015**: `engine/src/threepowers/scanners.py` — scanner ignore signatures + core walk skip
  (Track I).
- **FILE-016**: `engine/src/threepowers/gates.py` — scanner-ignore dispatch (Track I).
- **FILE-017**: `engine/src/threepowers/config.py` — `scan_config_path` accessor + loader (Track I).
- **FILE-018**: `engine/src/threepowers/scaffold.py` — seed `scan.yaml` (Track I).
- **FILE-019**: `engine/src/threepowers/scaffold/config/scan.yaml` + `.3powers/config/scan.yaml` —
  new scanner-ignore config (Track I).
- **FILE-020**: `engine/src/threepowers/scaffold/config/observability.yaml` +
  `.3powers/config/observability.yaml` — explanatory headers (Track J).
- **FILE-021**: `engine/src/threepowers/scaffold/constitution.md` + `.3powers/memory/constitution.md`
  — specs-src line, adaptation guide + checklist, version footer (Tracks K, M, L).
- **FILE-022**: `engine/src/threepowers/scaffold/templates/agents/*.agent.md` +
  `.3powers/templates/agents/*.agent.md` — `implementation-plan.agent.md`, `implement.agent.md`,
  `plan.agent.md`, `oracle.agent.md`, and specs-src reconciliation across all (Tracks K, A, B, C,
  D, F, G).
- **FILE-023**: `engine/src/threepowers/scaffold/templates/plan-template.md` +
  `tasks-template.md` → `implementation-plan-template.md` (and the `.3powers/templates/` mirrors) —
  de-judicial edits, rename, per-phase-gate/Verification pattern (Tracks A, C, D, K).
- **FILE-024**: `engine/pyproject.toml` + `engine/src/threepowers/__init__.py` — version bump to
  `1.0.0` (Track L).
- **FILE-025**: `docs/STATUS.md`, `README.md`, `docs/getting-started.md`, `CHANGELOG.md`,
  `docs/cli-reference.md`, `docs/concepts.md`, `docs/engine-architecture.md`, `AGENTS.md`,
  `CLAUDE.md`, `CONTRIBUTING.md` — release + specs-src + feature docs (Tracks K, G, H, I, J, L).
- **FILE-026**: `e2e/python-inventory/run.ipynb`, `e2e/typescript-orders/run.ipynb`,
  `e2e/go-ratelimit/run.ipynb` — `specs` → `specs-src` globs/comments (Track N).
- **FILE-027**: `engine/tests/**` — ~143 specs-src references, artifact/contract/regex updates,
  template-skeleton conformance, oracle/coverage, session/token, scanner, init, version, and
  back-compat tests (all tracks).
- **FILE-028**: The repo's own `specs/` → `specs-src/` (git mv, 29 feature folders) (Track K).

## 6. Testing

- **TEST-001** (Tracks K, N): specs-src back-compat — a legacy `specs/` layout still resolves via
  `find_specs`/`resolve_feature_dir`; the artifact-contract + gitflow regex tests pass under the new
  base; `--resume` re-checks a legacy-path ledger entry (no rewrite); `./e2e/run.sh {python,
  typescript,go} --check` green.
- **TEST-002** (Track A): a run writing `implementation-plan.md` passes the completion gate and a
  legacy `tasks.md` still resolves; template-skeleton conformance green after the rename.
- **TEST-003** (Track B): the changelog groups by phase, carries each phase's requirement ids and
  changed files, and is byte-deterministic for a fixed input; legacy `implement.md` resolves.
- **TEST-004** (Track C): template-content tests assert the per-phase-gate and final-Verification
  instructions are present; a plan-shape test asserts a generated implementation plan carries a final
  verification phase depending on all others.
- **TEST-005** (Track D): the role→model-family table is absent from the plan template and the plan
  sections; template-skeleton conformance updated in lockstep.
- **TEST-006** (Track E): a run keys the destination and records by `<NNN>-<slug>`; coverage counts
  `DEMO-FR-*` references under a numeric folder key; `oracle verify` green end-to-end from a single
  id; trust-spine coverage ≥95% held.
- **TEST-007** (Track F): `oracle.md` has a section per `FR/NFR` id with Given/When/Then (and
  metric/protocol for NFRs) and no file-path/framework token; a missing id or leaked path is flagged;
  an unmeasurable-AC spec produces the "Open Questions for the Legislature" stop; the isolation test
  is preserved.
- **TEST-008** (Track G): `build_command` never emits a resume/continue/session-reuse flag; each
  dispatch is an independent process; the phase prompt contains the sub-agent instruction; a new
  manifest field has adapter/round-trip coverage.
- **TEST-009** (Track H): per-strategy extraction unit tests (regex/JSON + unknown); a run records
  tokens in `progress.md` and the stage ledger payload; `3pwr verify` green over the new payloads;
  the verdict/`--json` gate bytes are unchanged whether or not usage is captured (additive-JSON
  guard).
- **TEST-010** (Track I): an ignored path is excluded and reported, a non-ignored finding still
  fails, a malformed/absent `scan.yaml` falls back to no-exclusions, the core ed25519 check still
  fires, and results are deterministic.
- **TEST-011** (Tracks J, M): init output/next-steps mention adapting the constitution; the seeded
  constitution contains the guidance section + checklist; `test_oss_readiness.py`/`test_auto_docs.py`
  stay green (no internal spec IDs; `DEMO-NFR-###`).
- **TEST-012** (Track L): version/changelog asserts updated (`1.0.0`/`v1.0`); full self-application
  green; a fresh `3pwr init` smoke; `3pwr --version` reports the release version.

## 7. Risks & Assumptions

- **RISK-001**: The renames break the completion gate / clean-start guard (`artifacts.py` and
  `gitflow.py` regexes hardcode `specs/…`). Mitigation — update those regexes in the same phase as
  the rename (TASK-003/TASK-004) with explicit tests that specify/plan/tasks/implement pass the
  completion gate under `specs-src` and the clean-start guard recognizes
  `specs-src/.../progress.md`.
- **RISK-002**: Ledger back-compat — old signed entries point at `specs/…`, `tasks.md`,
  `implement.md`; renaming without tolerant resolution breaks resume/re-check of old runs.
  Mitigation — read-resolution accepts new-then-legacy names/bases (PAT-001 / CON-004); no ledger
  rewrite; a back-compat test drives resume over a legacy-path ledger (TASK-010).
- **RISK-003**: Editing the sealed/approved constitution + the plan/tasks templates trips
  `spec_integrity`/`gate_gaming`. Mitigation — update the template-skeleton conformance test in
  lockstep and, before landing, run `3pwr gate run --path engine` + `3pwr verify`; the maintainer
  re-seals or records a signed `3pwr deviation` (CON-006; TASK-013/033/069/073).
- **RISK-004**: The oracle namespace decoupling (Track E) regresses coverage. Mitigation — separate
  the storage key (folder id) from the requirement namespace (spec.md Spec ID); a coverage test
  asserts `DEMO-FR-*` refs count under a numeric folder key before the phase is done (TASK-036/038).
- **RISK-005**: Token extraction is backend-specific and brittle. Mitigation — per-backend strategy
  + graceful `unknown`; tokens never in the verdict; a test asserts the verdict/`--json` are
  unchanged with usage absent (TASK-052), so a broken extractor degrades to "unknown", not a
  failure.
- **RISK-006**: Scanner ignores could hide real secrets. Mitigation — exclusions are reported in the
  gate output, the core ed25519 private-key check always runs, docs warn broad ignores weaken the
  gate, and excludes are deterministic and committed (SEC-001; TASK-059/060/062).
- **RISK-007**: Copilot session reuse may be un-fixable from the engine. Mitigation — Track G first
  investigates (TASK-044); if a CLI truly cannot start clean, document the limitation and use Track
  H's token counts to surface context bleed, preferring a backend that supports clean sessions for
  isolation-critical roles (oracle).
- **RISK-008**: Declaring v1.0 with open residuals reads as "everything done". Mitigation — RC first
  (decision 4); STATUS reframes residuals as explicitly accepted post-1.0 items; the release
  checklist gates the tag (TASK-074/077).
- **RISK-009**: Test churn — ~143 tests touch `specs/`. Mitigation — mechanical updates land with
  the rename phase; a `specs-src` grep in the self-application catches stragglers (TASK-010).
- **ASSUMPTION-001**: The branch `feat/033-v1-readiness-and-lifecycle-hardening` already carries the
  source plan and remains the sole delivery branch (no PRs, CON-001).
- **ASSUMPTION-002**: Each phase is delivered as a discrete unit that lands fully green (CON-002)
  before the next begins; later phases assume the `specs-src/` base from Phase 1.
- **ASSUMPTION-003**: The workspace numbering at implementation time places the new self-application
  specs at their next free numbers under `specs-src/` (the source plan cites `028`+); `specs-src/`
  is exempt from the OSS-readiness ID rule.
- **ASSUMPTION-004**: The full agent-driven e2e path (headless CLI) is run manually by the
  maintainer; automated verification uses the deterministic `--check` path.

## 8. Related Specifications / Further Reading

- Source plan: [`plan/033-v1-readiness-and-lifecycle-hardening.md`](033-v1-readiness-and-lifecycle-hardening.md)
- Self-application specs to create (post-rename, under `specs-src/`): `SRCDIR` (Tracks K, N),
  `LIFEART` (Tracks A, B, C, D), `ORATRACE` (Tracks E, F), `RUNVIS` (Tracks G, H), `SCANIGN`
  (Track I), `ONBRD` (Tracks J, M), `V1REL` (Track L)
- Workflow & discipline: [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md)
- Implementation status: [`docs/STATUS.md`](../docs/STATUS.md)
- CLI surface: [`docs/cli-reference.md`](../docs/cli-reference.md)
- Concepts & architecture: [`docs/concepts.md`](../docs/concepts.md),
  [`docs/engine-architecture.md`](../docs/engine-architecture.md)
- Getting started: [`docs/getting-started.md`](../docs/getting-started.md)
- e2e notebook kit: [`e2e/README.md`](../e2e/README.md)
- Prior implementation plans: [`plan/IMPLEMENTATION-001-feature-run-identity-gates-ux.md`](IMPLEMENTATION-001-feature-run-identity-gates-ux.md),
  [`plan/IMPLEMENTATION-002-refactor-public-text-decruft-and-cli-split.md`](IMPLEMENTATION-002-refactor-public-text-decruft-and-cli-split.md),
  [`plan/IMPLEMENTATION-003-feature-e2e-notebook-kit.md`](IMPLEMENTATION-003-feature-e2e-notebook-kit.md)
