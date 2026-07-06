---
goal: Implement run identity, gate diagnostics, configurable gates, pipeline gate view, progress file, phase prompt, and Rich terminal UX (plan 030)
version: 1.0
date_created: 2026-07-06
last_updated: 2026-07-06
owner: 3Powers maintainers
status: 'Planned'
tags: [feature, architecture, cli, ux, gates]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan executes [plan/030-run-identity-gates-ux.md](030-run-identity-gates-ux.md). It delivers seven
independently testable tracks in two delivery units on branch `feat/030-run-identity-gates-ux`:

- **Delivery unit 1** (Phases 1–5): Track A run identity (RUNID), Track B gate failure diagnostics
  (GDIAG), Track E progress file (PROGFILE), Track F phase orchestration prompt (PHASEPR), plus
  gate verification.
- **Delivery unit 2** (Phases 6–9): Track G Rich terminal UX (TRIX), Track D pipeline gate view
  (GATEPIPE), Track C configurable gates (GATECFG), plus final verification and docs.

Every task traces to a track/sub-item in plan 030 (noted as `[A1]`, `[B3]`, etc.).

## 1. Requirements & Constraints

Requirements (from plan 030 tracks):

- **REQ-001** (A1): `spec_id` must be derived from the workspace `NNN` (e.g. `specs/030-add-button/` → `"030"`) whenever `--spec-id` is not given; every downstream consumer (ledger, gate messages, resume hints, oracle dispatch, branch naming) must receive the derived value.
- **REQ-002** (A2): The oracle agent template must place oracle tests under `tests/oracle/<spec_id>/` using the `{spec_id}` placeholder, never a spec slug.
- **REQ-003** (A3): The `spec_conformance` gate must write `details["requirement_ids"] = sorted(referenced)` so `Verdict.requirement_ids()` (already aggregating at `engine/src/threepowers/verdict.py:99`) populates the ledger's `requirement_ids` field.
- **REQ-004** (A4): `.3powers/ledger.jsonl` (repo-relative) must be appended to the `produced` paths of every producing stage commit so ledger state is atomically bundled with the stage artifact.
- **REQ-005** (B1): The `gate_red` event rendering in `orchestrate.py` must show each failed gate name, its adapter tool, and its first actionable error line, plus filled-in `Resume:` and `Inspect:` command lines.
- **REQ-006** (B2): `3pwr gate run --id <NNN>` must resolve `specs/<NNN>-*/spec.md` via a new `workspace.resolve_feature_dir(root, nnn)` helper that globs `specs/<NNN>-*/` and asserts exactly one match.
- **REQ-007** (B3): Missing gate prerequisites must be detected before any gate runs; the run exits with the setup exit code and prints per-tool install hints taken from the adapter manifest `toolchain:` section; it must not proceed when a required tool for a non-optional gate is missing.
- **REQ-008** (B4): Every resume hint in `cli.py` (gates-red resume line, gate-pause status rows, notification message) must use the `spec_id` local variable, never a literal.
- **REQ-009** (E1–E3): The engine must write `specs/<NNN>-<slug>/progress.md` atomically (tmp-file + rename) via a new `threepowers/progress.py` module at every lifecycle event (stage start, stage complete, gate verdict, human-gate pause, failure), with stage-level and phase-level tables per the plan's content schema, and include the file in each producing stage commit.
- **REQ-010** (F1): The per-phase dispatch prompt in `cli.py:_dispatch_phased()` must carry the explicit contract: scope limited to the declared phase, no files outside the phase's file scope, `[P]` tasks dispatched concurrently, tasks marked `[x]` / `[!]`+reason in `tasks.md`, no operator questions (document assumptions in code comments).
- **REQ-011** (F2): Before dispatching phase N, the engine must inject a one-line "Phases already completed" summary collected from the task headings of phases 1..N-1.
- **REQ-012** (F3): After a phase session ends, the engine must scan the tail (last 500 bytes) of the transcript for unanswered-question patterns and emit an advisory `warn` event; the run continues.
- **REQ-013** (G1–G2): The engine must depend on `rich>=13.7,<15`; `style.Styler` and `frame.LiveFrame` must be reimplemented on `rich.console.Console`/`rich.live.Live`/`rich.layout.Layout` while preserving their public APIs so `orchestrate.py`, `cli.py`, and `gates.py` call sites are unchanged in the first pass.
- **REQ-014** (G4–G6): The bottom-anchored stage bar becomes a Rich layout region; agent stdout streams unchanged through `Console(highlight=False)`; `--json` output stays byte-identical (no Rich formatting on the JSON path); `NO_COLOR`, `--yes`, and non-TTY all degrade to plain text.
- **REQ-015** (D1): Gate execution must emit one compact, in-place-updated status row per gate (glyph, `gate · tool`, elapsed + summary), rendered as a `rich.table.Table` inside `rich.live.Live` (G3).
- **REQ-016** (D2): After all gates finish, each failed gate gets its own panel: gate + tool + elapsed, first 30 meaningful error lines, `fix_cmd` hint when configured, and CVE/finding + remediation for dependency/secret scans; the old bottom "failures:" block is removed.
- **REQ-017** (D3): Node.js `ExperimentalWarning` lines and blank lines are suppressed unless `--verbose`; the `spec_integrity` "skipped" line renders as `–` (info), not `✗`.
- **REQ-018** (C1): `.3powers/config/gates.yaml` (committed, seeded by `3pwr init`) deep-merges per-gate overrides over the adapter manifest inside `adapters.load_adapter()`; only present keys override.
- **REQ-019** (C2): When `gates.yaml` does not override a gate, auto-detect project-native tooling per the plan's detection table (biome/prettier, biome/eslint, tsc/pyright, vitest/jest/playwright, Go `go test`/`gofmt`), print the result once at gate-run startup; precedence is `gates.yaml` > auto-detect > adapter manifest.
- **REQ-020** (C3): `fix_cmd` (format/lint only) runs only under an opt-in `--auto-fix` flag on `3pwr gate run` and `3pwr run`: check → fix → re-check; on re-check pass the gate is green and fixed paths are appended to `produced`; without the flag the `fix_cmd` is only printed as a manual hint.
- **REQ-021** (C4): A new `3pwr gate config show` subcommand renders the effective per-gate configuration (adapter base + overrides + auto-detected, with source tags) without running any gate.
- **REQ-022** (G, CLIUX amendment): `specs/015-cli-experience/spec.md` FR-003 is revised to permit `rich` (MIT-licensed, pure-Python, no transitive C extensions); the `--json`/`--yes`/`NO_COLOR` and exit-code contracts (CLIUX-NFR-001/002) are explicitly preserved.

Security:

- **SEC-001**: Auto-fix is opt-in only (`--auto-fix`); agent-produced output is never silently mutated mid-run (recorded decision in plan 030).
- **SEC-002**: Work-kind/tier gate shaping only ever adds gates; no change in this plan may weaken a tier gate (CLAUDE.md pillar 2). Configurable gates replace *tools*, never remove *gates*.

Constraints:

- **CON-001**: Two delivery units in the recorded order — A+B+E+F first, then G+D+C. A lands before B and E (both depend on the real `spec_id`). G lands before D (pipeline view is built on Rich). C goes last.
- **CON-002**: No pull requests; all work on the existing branch `feat/030-run-identity-gates-ux` (AGENTS.md).
- **CON-003**: Engine must stay green under its own gates after each phase: `ruff check`, `mypy src`, `pytest`, and `3pwr gate run --path engine`. Trust-spine modules (`canonical`, `keys`, `ledger`, `verify`) keep coverage ≥95% (they are not modified by this plan, but the suite-level thresholds must hold).
- **CON-004**: Everything public-facing is open-source ready: no internal plan/spec/requirement references in `docs/` or CLI help; every behavior change lands with a matching docs update in the same unit of work (AGENTS.md).
- **CON-005**: Python engine code changes go through the python-engineer agent role (AGENTS.md).
- **CON-006**: `gates.yaml` is committed team configuration versioned under `.3powers/config/`, not a personal local override (recorded decision).

Guidelines & patterns:

- **GUD-001**: Preserve public APIs (`Styler`, `LiveFrame`, `emit_event`, verdict schema) so the Rich swap is call-site-transparent in the first pass.
- **GUD-002**: Every new CLI surface (`--id`, `--auto-fix`, `gate config show`) is documented in `docs/cli-reference.md` in the same phase that implements it.
- **PAT-001**: Atomic file writes follow the tmp-then-rename pattern (`.progress.md.tmp` → `progress.md`), matching the ledger's durability posture.
- **PAT-002**: New CLI subcommands/flags follow the existing `argparse` registration and `cmd_*` handler pattern in `engine/src/threepowers/cli.py`.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Track A (RUNID) — the run's real `NNN` identity flows through the ledger, oracle, gate messages, resume hints, and stage commits, and the ledger file is committed with every producing stage. Completion criteria: all Phase 1 validation checks pass and the engine test suite is green.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | Create `specs/020-run-identity/spec.md` (spec ID `RUNID`) with FR-001..006 covering A1–A4: NNN-derived `spec_id`, oracle test folder `tests/oracle/<spec_id>/`, populated `requirement_ids`, ledger committed per stage. Follow the structure of existing specs under `specs/`. | ✅ | 2026-07-06 |
| TASK-002 | [A1] In `engine/src/threepowers/cli.py`, immediately after the run workspace `feature_dir` is resolved in `cmd_run()` (allocation currently near line 4223; `spec_id` default set at `cli.py:3869`), add: `if not args.spec_id and feature_dir is not None: spec_id = feature_dir.name.split("-")[0]`. Verify all downstream consumers (ledger writes, gate messages, resume hints, oracle dispatch, `gitflow.run_branch_name` at `gitflow.py:118`) read the `spec_id` local, not `args.spec_id`. | ✅ | 2026-07-06 |
| TASK-003 | [A2] Verify `.3powers/templates/agents/oracle.agent.md` and the `oracle dispatch` prompt path use `{spec_id}` (not `{slug}`) for the `tests/oracle/<spec-id>/` target folder; fix the placeholder if it uses the slug. No engine code change expected beyond TASK-002. | ✅ | 2026-07-06 |
| TASK-004 | [A3] In `engine/src/threepowers/gates.py`, in the `spec_conformance` gate execution path (dispatch near `gates.py:351`), after collecting referenced requirement IDs via `conformance.referenced_ids()`, write `details["requirement_ids"] = sorted(referenced)` into the gate's details dict. `Verdict.requirement_ids()` at `verdict.py:99` needs no change. | ✅ | 2026-07-06 |
| TASK-005 | [A4] In `engine/src/threepowers/cli.py`, in the stage-commit block of the run loop (near line 3573, where `produced_box.get("paths")` is read before `gitflow.commit_stage()` at `gitflow.py:285`), append `str(s.ledger_path.relative_to(s.root))` to `produced` when the ledger file exists and is not already listed. | ✅ | 2026-07-06 |
| TASK-006 | Add/extend pytest coverage in `engine/tests/`: (a) `spec_id` derives `"030"` from a `specs/030-x/` feature dir and stays `args.spec_id` when given; (b) ledger entries after a simulated run carry `"spec_id": "030"`; (c) `spec_conformance` gate details contain the referenced IDs and the verdict's `requirement_ids` is non-empty; (d) the stage commit includes `.3powers/ledger.jsonl`. | ✅ | 2026-07-06 |

Validation: `cd engine && uv run pytest && uv run ruff check . && uv run mypy src` passes; the four Track A acceptance criteria in plan 030 hold on a scripted run.

### Phase 2

- GOAL-002: Track B (GDIAG) — gate failures name the failing gates inline with actionable lines, `gate run --id <NNN>` works, missing prerequisites produce install hints before any gate runs, and every resume hint carries the real NNN. Depends on Phase 1 (real `spec_id`).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-007 | Create `specs/021-gate-diagnostics/spec.md` (spec ID `GDIAG`) with FR-001..006 covering B1–B4. | ✅ | 2026-07-06 |
| TASK-008 | [B2] Add `resolve_feature_dir(root: Path, nnn: str) -> Path` to `engine/src/threepowers/workspace.py`: glob `specs/<nnn>-*/`, raise a user-facing error unless exactly one match; return the matching directory. | ✅ | 2026-07-06 |
| TASK-009 | [B2] In `engine/src/threepowers/cli.py`, add `--id <NNN>` to the `gate run` argparse subparser as an alias for `--spec <path>`: when given, resolve via `workspace.resolve_feature_dir(root, args.id)` and use `workspace.spec_path(feature_dir)`. Reject `--id` combined with `--spec`. | ✅ | 2026-07-06 |
| TASK-010 | [B1] In `engine/src/threepowers/orchestrate.py`, in `format_event()` where `ev.step == "gate_red"` is rendered (near `orchestrate.py:352`), replace the one-line "gates red" message with the structured summary: header `✗  gates failed (<failed> of <total>):`, one row per failed gate from `ev.data["verdict"]` showing `name · tool` and the first actionable error line, then `Resume: 3pwr run --resume --spec-id <spec_id>` and `Inspect: 3pwr gate run --id <spec_id>`. | ✅ | 2026-07-06 |
| TASK-011 | [B3] In `engine/src/threepowers/gates.py` (with any manifest plumbing in `engine/src/threepowers/adapters.py`), run the tool-availability probe for every required tool of non-optional gates before executing any gate; on failure print the `⚠ prerequisites missing — install before re-running:` block using install hints from the adapter manifest `toolchain:` section, and exit with the setup exit code without running gates. Add `toolchain:` install-hint entries to `.3powers/adapters/{typescript,python,go}/adapter.yaml` where missing (verified already complete — no additions needed). | ✅ | 2026-07-06 |
| TASK-012 | [B4] Audit `engine/src/threepowers/cli.py` for resume-hint literals — the gates-red resume line (≈ line 4427), the gate-pause status rows (≈ line 3904), and the notification message (≈ line 2949) — and confirm/replace each to interpolate the `spec_id` local variable. | ✅ | 2026-07-06 |
| TASK-013 | Add pytest coverage: (a) `resolve_feature_dir` succeeds on exactly one match and errors on zero/two matches; (b) `gate run --id 030` resolves the same spec path as `--spec specs/030-x/spec.md`; (c) `gate_red` formatting lists each failed gate and the two command hints with the real NNN; (d) a missing required tool exits with the setup code and prints its install hint without running gates. | ✅ | 2026-07-06 |
| TASK-014 | Document `3pwr gate run --id <NNN>` and the prerequisites-missing behavior in `docs/cli-reference.md` (no internal spec-ID jargon; CON-004). | ✅ | 2026-07-06 |

Validation: engine gates green; the four Track B acceptance criteria in plan 030 hold.

### Phase 3

- GOAL-003: Track E (PROGFILE) — a human-readable `progress.md` in the run folder tracks stage- and phase-level progress, is updated at every lifecycle event, and is committed with each producing stage. Depends on Phase 1 (real `spec_id`); independent of Phase 2.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-015 | Create `specs/024-progress-file/spec.md` (spec ID `PROGFILE`) with FR-001..008 covering E1–E3 including phase-level detail. | ✅ | 2026-07-06 |
| TASK-016 | [E1/E2] Create `engine/src/threepowers/progress.py` with `write(state: lifecycle.RunState, feature_dir: Path, ...) -> Path`: render the markdown per the plan 030 content schema — title line `# Run <NNN> · <slug> · <timestamp>`, stage-progress table (✓ done / ⏳ running / ○ pending / 🔒 paused / ✗ failed with completion timestamps), a phase-detail table only when the current stage has phases (phase number, description, status, tasks done from the tasks artifact), a "Current state" block, a "Last verdict" block, a fenced "Helper commands" block (`--status`, `--resume --approver`, `abort`, `gate run --id ... --tier`) using the real NNN, and a "Gate failures (last verify attempt)" section listing failed gate names only. Write atomically: `.progress.md.tmp` then `os.replace` to `progress.md`. | ✅ | 2026-07-06 |
| TASK-017 | [E3] In `engine/src/threepowers/cli.py`, call `progress.write()` from the run loop at the same points as the existing `orchestrate.emit_event()` calls for: stage start, stage complete, gate verdict PASS, gate verdict FAIL, human-gate pause, and run failure — mapping each trigger to the updated fields per the plan 030 E3 table. | ✅ | 2026-07-06 |
| TASK-018 | [E1] In the stage-commit block (same site as TASK-005), append the repo-relative `progress.md` path to `produced` so the file is committed alongside the stage artifact and ledger. | ✅ | 2026-07-06 |
| TASK-019 | Add pytest coverage: (a) `progress.write()` output matches the schema for a mid-build state with phases (golden-file or structural assertions); (b) atomic write leaves no `.tmp` on success; (c) status transitions for each E3 trigger; (d) the stage commit includes `progress.md`; (e) helper commands embed the real NNN. | ✅ | 2026-07-06 |

Validation: engine gates green; the four Track E acceptance criteria in plan 030 hold.

### Phase 4

- GOAL-004: Track F (PHASEPR) — the per-phase dispatch prompt carries an explicit scope/completion/parallelism contract, injects a completed-phases summary, and the engine warns when a phase transcript ends in an unanswered question. Independent of Phases 1–3.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-020 | Create `specs/025-phase-prompt/spec.md` (spec ID `PHASEPR`) with FR-001..005 covering F1–F3. | ✅ | 2026-07-06 |
| TASK-021 | [F1] In `engine/src/threepowers/cli.py` `_dispatch_phased()` (defined at `cli.py:3263`; prompt block near line 3299) and/or the prompt-assembly helper in `engine/src/threepowers/phases.py`, replace the per-phase context block with the structured `PHASE INSTRUCTION` contract from plan 030: scope limited to `## Phase {N}` tasks, no files outside the declared file scope, no tasks from other phases, `[P]` tasks dispatched concurrently via subagents, completion markers `[x]`/`[!]`+reason in `tasks.md`, no operator questions (document assumptions in code comments), and the `Phases already completed: {completed_phases_summary}` line. | ✅ | 2026-07-06 |
| TASK-022 | [F2] In `engine/src/threepowers/phases.py`, add a helper that extracts phase headings/descriptions for phases 1..N-1 from the tasks artifact and formats the one-line summary (e.g. `Phase 1 (HeaderComponent styles), Phase 2 (ButtonComponent)`); wire it into TASK-021's prompt. | ✅ | 2026-07-06 |
| TASK-023 | [F1] Update `.3powers/templates/agents/tasks.agent.md` so the generated tasks artifact instructs the same completion-marker contract (`[x]` / `[!]`+reason) the phase prompt expects. (The tasks-stage template is named `implementation-plan.agent.md`; that pair — repo + scaffold mirror — was updated.) | ✅ | 2026-07-06 |
| TASK-024 | [F3] After a phase session ends in `_dispatch_phased()`, read the last 500 bytes of the session transcript (via `engine/src/threepowers/transcripts.py` helpers) and match unanswered-question patterns (trailing `?` with no subsequent code block, `I need clarification`, `Could you clarify`, case-insensitive). On match, emit an advisory `warn` event: `⚠ phase <N> ended with a possible unanswered question — review the transcript` plus the `--status` hint. The run continues. | ✅ | 2026-07-06 |
| TASK-025 | Add pytest coverage: (a) the rendered phase prompt for phase 2 of 3 contains the scope contract, the `[P]` instruction, the completion-marker instruction, and the phase-1 summary; (b) stall detection fires on a transcript ending `Could you clarify the button label?` and stays silent on one ending with a code block; (c) the warn event does not alter run control flow. | ✅ | 2026-07-06 |

Validation: engine gates green; Track F acceptance criteria hold (the concurrency criterion is covered by the existing `ThreadPoolExecutor` path test, extended if absent).

### Phase 5

- GOAL-005: Delivery-unit-1 verification — the engine passes its own gate suite and a live end-to-end run confirms the identity/diagnostics/progress behavior before the Rich refactor starts.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-026 | Run `cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src`; then `3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md --tier Standard --base main` (reinstall the tool first: `uv tool install ./engine --force`). Fix any regression before proceeding. (Gate run surfaced and fixed: format drift in 7 files, the two AGENTS/CLAUDE docs-test regressions from an external rewrite, 5 untraced 3PWR requirement ids bound to their real tests, and a 3PWR spec seal recorded against the wrong file — re-sealed by the operator, ledger seq=10. Final self-application run: verdict PASS, all 11 gates green, diff_coverage 92.35%, 53 requirements traced, signed ledger entry #12.) | ✅ | 2026-07-06 |
| TASK-027 | Live E2E against the test environment: `3pwr run "add a dismiss button to the overflow menu" --mode auto --path ../3powers-test-env --adapter typescript`. Verify: `specs/<NNN>-*/progress.md` exists with correct stage rows; `git log` shows `.3powers/ledger.jsonl` in each producing stage commit; verify-stage ledger entries have non-empty `requirement_ids`; failure/pause messages carry the real NNN; the oracle wrote `tests/oracle/<NNN>/`. Record outcomes in the plan file. (DEFERRED by the operator on 2026-07-06 — to be exercised together with the Phase 9 live E2E, TASK-053.) | ⏸ deferred |      |
| TASK-028 | Update `docs/` for delivery unit 1: `docs/cli-reference.md` gains the gate-failure summary format, `gate run --id`, and the `progress.md` file description (open-source-ready wording, CON-004). | ✅ | 2026-07-06 |

Validation: gate suite green at Standard; all delivery-unit-1 acceptance criteria checked off.

### Phase 6

- GOAL-006: Track G (TRIX) — the terminal renderer is rebuilt on Rich behind the existing `Styler`/`LiveFrame` APIs, with unchanged `--json`/`NO_COLOR`/non-TTY contracts, and the CLIUX spec is amended.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-029 | Amend `specs/015-cli-experience/spec.md`: revise FR-003 to read that the structured-output toolkit may depend on `rich` (MIT-licensed, pure-Python, no transitive C extensions); state explicitly that the `--json`/`--yes`/`NO_COLOR` and exit-code contracts (NFR-001/002) are unchanged. Handle the spec re-seal per the maintainer re-seal procedure if `spec_integrity` tracks this spec's hash. |           |      |
| TASK-030 | Create `specs/026-terminal-ux/spec.md` (spec ID `TRIX`) with FR-001..008 covering G1–G6. |           |      |
| TASK-031 | [G1] Add `"rich>=13.7,<15"` to `dependencies` in `engine/pyproject.toml`; run `cd engine && uv sync --extra dev` to update `engine/uv.lock`. |           |      |
| TASK-032 | [G2] Rewrite `engine/src/threepowers/style.py`: `Styler` (currently at `style.py:133`) wraps `rich.console.Console` + `rich.style.Style`; remove hand-rolled SGR code paths; color/quiet/verbose behavior stays driven by the existing `ui.yaml` + env vars, with Rich's `FORCE_COLOR`/`NO_COLOR` detection as fallback. Public API unchanged so `orchestrate.py`, `cli.py`, `gates.py` call sites compile untouched. |           |      |
| TASK-033 | [G2/G4] Rewrite `engine/src/threepowers/frame.py`: `LiveFrame` (currently at `frame.py:265`) wraps `rich.live.Live` + `rich.layout.Layout`; the bottom-anchored stage bar (fed by `orchestrate.render_tracker` at `orchestrate.py:309`) becomes a 1–2 line bottom layout region; delete the `\033[A`/`\033[J` cursor-math implementation. |           |      |
| TASK-034 | [G5/G6] Route agent stdout through `Console(highlight=False)` in the scrollback region above the live bar, unchanged in content; wire degradation: `--json` → `Console(force_terminal=False, highlight=False)` and Rich unused on the JSON serialization path; `NO_COLOR`/`--yes` → `Console(no_color=True, highlight=False)`; non-TTY → `Console(force_terminal=False)`, no live updates. |           |      |
| TASK-035 | Add/adapt pytest coverage: (a) `--json` output byte-identical to a pre-TRIX golden capture for a representative command; (b) `NO_COLOR` and piped (non-TTY) output contain no ANSI escapes; (c) `Styler`/`LiveFrame` public API signatures unchanged (import-and-call smoke tests); (d) narrow-terminal (40-col) rendering degrades to plain text; (e) assert no raw `\033[` escape construction remains in `style.py`/`frame.py` (source scan test). |           |      |
| TASK-036 | Update `docs/cli-reference.md` and any UX docs for the Rich-backed output and unchanged degradation contracts (CON-004). |           |      |

Validation: `uv sync` resolves `rich` cleanly; engine gates green; Track G acceptance criteria hold.

### Phase 7

- GOAL-007: Track D (GATEPIPE) — gate runs render a live per-gate pipeline with in-place status rows, per-failure panels replace the bottom "failures:" block, and noise is filtered. Depends on Phase 6 (Rich).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-037 | Create `specs/023-gate-pipeline/spec.md` (spec ID `GATEPIPE`) with FR-001..005 covering D1–D3. |           |      |
| TASK-038 | [D1/G3] In `engine/src/threepowers/gates.py` + `engine/src/threepowers/orchestrate.py`, emit gate start/finish events and render them as a three-column `rich.table.Table` (`status glyph`, `gate name · tool`, `elapsed + summary`) inside `rich.live.Live`, updating each row in place: `○ … (running…)` → `✓ name · tool 0.4 s` / `✗ name · tool 1.2 s  2 errors`. |           |      |
| TASK-039 | [D2/G3] After the live context exits, print one `rich.panel.Panel` per failed gate (dim header `gate · tool`, elapsed): error lines indented and trimmed to the first 30 meaningful lines (blank/noise lines excluded); `↳ auto-fix: <fix_cmd>` hint when a `fix_cmd` is configured; for `dependency_scan`/`secret_scan`, one line per finding with ID, package/file, and remediation hint. Remove the old bottom "failures:" block. |           |      |
| TASK-040 | [D3] Add noise filters in the gate-output path: suppress Node.js `ExperimentalWarning` lines and blank lines unless `--verbose`; render the `spec_integrity` "skipped" line with the `–` info glyph, not `✗`. |           |      |
| TASK-041 | Add pytest coverage: (a) pipeline rows for a mixed pass/fail run (captured via a recording Console) show correct glyphs/order; (b) a failed gate panel trims to ≤30 meaningful lines and includes the `fix_cmd` hint; (c) `ExperimentalWarning` absent by default, present with `--verbose`; (d) `spec_integrity` skip renders `–`; (e) non-TTY output degrades to sequential plain-text rows. |           |      |
| TASK-042 | Update `docs/cli-reference.md` gate-run output description for the pipeline view (CON-004). |           |      |

Validation: engine gates green; Track D acceptance criteria hold.

### Phase 8

- GOAL-008: Track C (GATECFG) — projects override gate tooling via committed `gates.yaml`, native tooling is auto-detected, `--auto-fix` runs configured `fix_cmd`s opt-in, and `gate config show` reveals the effective configuration. Depends on Phase 7 (failure panels print the `fix_cmd` hint).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-043 | Create `specs/022-gate-config/spec.md` (spec ID `GATECFG`) with FR-001..010 covering C1–C4. |           |      |
| TASK-044 | [C1] In `engine/src/threepowers/adapters.py` `load_adapter()` (at `adapters.py:41`), after parsing the base adapter YAML, load `.3powers/config/gates.yaml` if present and deep-merge per-gate keys over the adapter's `gates:` blocks (one `dict.update()` pass per gate block; only present keys override). |           |      |
| TASK-045 | [C1] Create the seed `.3powers/config/gates.yaml` (commented defaults per the plan 030 example: `format`/`lint` `check_cmd`+`fix_cmd`, `types.cmd`, `tests.cmd`+`coverage_format`+`coverage_path`) and extend `3pwr init` scaffolding (`engine/src/threepowers/scaffold.py` / `scaffold/`) to seed it into new projects. |           |      |
| TASK-046 | [C2] Implement auto-detection in `engine/src/threepowers/adapters.py`, run once at `gate run` startup for gates not overridden by `gates.yaml`, per the plan 030 detection table: `format` (biome.json → biome; .prettierrc/prettier.config.* → prettier), `lint` (biome.json → biome; .eslintrc*/eslint.config.* → eslint), `types` (tsconfig.json → tsc; pyproject.toml+[tool.pyright] → pyright), `tests` (vitest.config.* → vitest; jest.config.* → jest; playwright.config.* → playwright), Go (`go.mod` → `go test ./...` / `gofmt -l .`). Print one startup line: `auto-detected gates:  format=biome  tests=vitest  types=tsc`. Precedence: `gates.yaml` > auto-detect > adapter manifest. |           |      |
| TASK-047 | [C3] Add `fix_cmd` support: extend the adapter `gates:` schema (format and lint only — never types/tests/mutation); add the `--auto-fix` flag to the `gate run` and `run` argparse subparsers in `cli.py`; in `gates.py`, when `--auto-fix` is active and a format/lint `check_cmd` fails with a configured `fix_cmd`: run `fix_cmd`, print `  ↳ auto-fixed by <tool>`, re-run `check_cmd`; on pass mark the gate green and append the fixed paths to `produced` (stage commit picks them up per GITX-FR-008); on fail report normally. Without the flag, fail on first check and surface `fix_cmd` only as the Phase-7 panel hint. |           |      |
| TASK-048 | [C3] Add `fix_cmd` entries to the default adapter manifests: `.3powers/adapters/typescript/adapter.yaml` (format+lint), `.3powers/adapters/python/adapter.yaml` (format+lint), `.3powers/adapters/go/adapter.yaml` (format). |           |      |
| TASK-049 | [C4] Add the `3pwr gate config show [--adapter <name>]` subcommand in `cli.py`: render the effective per-gate table (`gate`, `tool`, `check_cmd`, `fix_cmd`, source tag such as `[auto-detected]`/`[gates.yaml]`) from adapter base + `gates.yaml` overrides + auto-detection, without executing any gate. |           |      |
| TASK-050 | Add pytest coverage: (a) `gates.yaml` overriding `tests.cmd` to `npm run test:unit` yields that command in the effective config and the gate run; (b) auto-detect picks jest when only `jest.config.ts` exists and vitest when `vitest.config.ts` exists; (c) precedence order gates.yaml > auto-detect > manifest; (d) `--auto-fix` fix→recheck→green path appends fixed paths to `produced`; (e) without `--auto-fix` the gate fails on first check and the hint is emitted; (f) `fix_cmd` never runs for types/tests/mutation; (g) `gate config show` renders all gates with correct source tags and runs no gate. |           |      |
| TASK-051 | Document `gates.yaml`, auto-detection, `--auto-fix`, and `gate config show` in `docs/cli-reference.md` and the configuration docs (CON-004; no internal spec IDs). |           |      |

Validation: engine gates green; the four Track C acceptance criteria in plan 030 hold.

### Phase 9

- GOAL-009: Final verification — the full engine gate suite and a live end-to-end run confirm all seven tracks against plan 030's post-delivery checklist.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-052 | Reinstall (`uv tool install ./engine --force`), then run `3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md --tier Standard --base main`; confirm green and trust-spine coverage ≥95%. |           |      |
| TASK-053 | Live E2E: `3pwr run "add a dismiss button to the overflow menu" --mode auto --path ../3powers-test-env --adapter typescript`. Verify the plan 030 post-delivery checklist: `specs/<NNN>-*/progress.md` correct; ledger.jsonl in each stage commit; verify-stage `requirement_ids` non-empty; gate failures render the pipeline view with per-gate panels; resume hints carry the actual NNN. Additionally exercise `gate run --id <NNN>`, `gate config show`, and one `--auto-fix` format failure in the test env. |           |      |
| TASK-054 | Docs sweep for open-source readiness (CON-004): no internal plan/spec/requirement IDs leaked into `docs/` or CLI help by this plan; mark this implementation plan's task tables complete and set front-matter `status` to `Completed`. |           |      |

Validation: full checklist green; branch ready for merge per AGENTS.md (no pull request).

## 3. Alternatives

- **ALT-001**: Thread `feature_dir`-derived identity through a new `RunIdentity` object instead of patching the `spec_id` local (A1). Rejected by plan 030: all downstream consumers already read the `spec_id` local, so the in-place patch is the minimal faithful change; a broader refactor is out of scope.
- **ALT-002**: Run `fix_cmd` by default and gate mutation behind `--no-auto-fix`. Rejected — recorded decision: agent output must never be silently mutated mid-run; auto-fix is opt-in only.
- **ALT-003**: Keep `gates.yaml` as an untracked personal override (gitignored). Rejected — recorded decision: it is shared team configuration, committed and seeded by `3pwr init`.
- **ALT-004**: Extend the custom ANSI renderer in `style.py`/`frame.py` for the pipeline view instead of adopting Rich. Rejected — ~200 more lines of cursor math on an already fragile ~500-line renderer with known redraw races; Rich is a single safe dependency and the CLIUX spec is formally amended.
- **ALT-005**: Single delivery unit for all seven tracks. Rejected — recorded decision: two units isolate the low-risk identity/diagnostics work from the larger Rich refactor.
- **ALT-006**: Making the executive interactive so headless agents can await operator input (raised during planning). Rejected as not required — the F1 prompt contract plus F3 stall detection are the mitigation; no architectural change to `NativeRunner.dispatch_once`.

## 4. Dependencies

- **DEP-001**: `rich>=13.7,<15` — new engine runtime dependency (MIT, pure-Python, no transitive C extensions); pinned in `engine/uv.lock` via `uv sync`.
- **DEP-002**: Existing engine toolchain per lockfiles: `uv`, `pytest`, `ruff`, `mypy` (`engine/uv.lock`).
- **DEP-003**: `3powers-test-env` sibling project (TypeScript) for live E2E verification (Phases 5 and 9), plus its adapter tooling (biome/vitest/tsc) for gate exercises.
- **DEP-004**: Independent signer key via `THREEPOWERS_SIGNING_KEY_FILE` for ledger-writing E2E runs and any spec re-seal (TASK-029).
- **DEP-005**: Intra-plan ordering: Phase 1 → Phases 2–3 (spec_id); Phase 6 → Phase 7 (Rich); Phase 7 → Phase 8 (panels print `fix_cmd` hints); Phase 4 is independent within delivery unit 1.

## 5. Files

- **FILE-001**: `engine/src/threepowers/cli.py` — spec_id derivation (A1); ledger+progress in `produced` (A4/E1); `--id` on gate run (B2); resume-hint audit (B4); progress.write calls (E3); phase prompt dispatch (F1–F3); `--auto-fix` flags and `gate config show` (C3/C4).
- **FILE-002**: `engine/src/threepowers/orchestrate.py` — gates-red structured summary (B1); pipeline rows rendering (D1/G3).
- **FILE-003**: `engine/src/threepowers/gates.py` — `requirement_ids` in conformance details (A3); prerequisite pre-check (B3); pipeline events (D1); noise filters (D3); `fix_cmd` loop (C3).
- **FILE-004**: `engine/src/threepowers/adapters.py` — `gates.yaml` deep-merge (C1); auto-detect probes (C2); toolchain install hints (B3).
- **FILE-005**: `engine/src/threepowers/gitflow.py` — verify `commit_stage()` (line 285) handles the appended ledger/progress paths idempotently (A4/E1).
- **FILE-006**: `engine/src/threepowers/workspace.py` — new `resolve_feature_dir(root, nnn)` helper (B2).
- **FILE-007**: `engine/src/threepowers/progress.py` — **new** module: progress.md renderer + atomic writer (E1/E2).
- **FILE-008**: `engine/src/threepowers/phases.py` — completed-phases summary helper; phase prompt block (F1/F2).
- **FILE-009**: `engine/src/threepowers/style.py` — rewritten on `rich.console` (G2).
- **FILE-010**: `engine/src/threepowers/frame.py` — rewritten on `rich.live`/`rich.layout` (G2/G4).
- **FILE-011**: `engine/pyproject.toml` + `engine/uv.lock` — add `rich` (G1).
- **FILE-012**: `.3powers/adapters/typescript/adapter.yaml`, `.3powers/adapters/python/adapter.yaml`, `.3powers/adapters/go/adapter.yaml` — `fix_cmd` entries (C3) and toolchain install hints (B3).
- **FILE-013**: `.3powers/config/gates.yaml` — **new** seeded project-level gate overrides (C1); `3pwr init` scaffolding updated in `engine/src/threepowers/scaffold.py`/`scaffold/`.
- **FILE-014**: `.3powers/templates/agents/oracle.agent.md` — `{spec_id}` test-folder placeholder verified (A2).
- **FILE-015**: `.3powers/templates/agents/tasks.agent.md` — completion-marker contract (F1).
- **FILE-016**: `specs/020-run-identity/spec.md`, `specs/021-gate-diagnostics/spec.md`, `specs/022-gate-config/spec.md`, `specs/023-gate-pipeline/spec.md`, `specs/024-progress-file/spec.md`, `specs/025-phase-prompt/spec.md`, `specs/026-terminal-ux/spec.md` — new specs; `specs/015-cli-experience/spec.md` — FR-003 amendment.
- **FILE-017**: `docs/cli-reference.md` (+ configuration docs) — all new flags, commands, output formats, and `gates.yaml`/`progress.md` documentation.
- **FILE-018**: `engine/tests/` — new/extended pytest modules per phase (TASK-006, 013, 019, 025, 035, 041, 050).

## 6. Testing

- **TEST-001** (A): spec_id derivation unit tests — NNN extracted from feature dir name; explicit `--spec-id` wins; ledger entries carry the derived ID; `requirement_ids` populated from conformance details; stage commit contains `.3powers/ledger.jsonl`.
- **TEST-002** (B): `resolve_feature_dir` match/zero/ambiguous cases; `--id` ↔ `--spec` equivalence; `gate_red` structured summary content incl. real-NNN hints; prerequisite-missing exits with setup code + install hints and runs no gate.
- **TEST-003** (E): `progress.md` schema rendering (stage + phase tables), atomicity, all six E3 trigger transitions, inclusion in stage commit.
- **TEST-004** (F): phase-prompt contract contents incl. completed-phases summary; stall-detection positive/negative transcripts; warn is advisory only; `[P]` concurrency (two parallel tasks finish within max(t1,t2)+10%, existing executor path).
- **TEST-005** (G): `--json` byte-identical golden test; no ANSI escapes under `NO_COLOR`/non-TTY; `Styler`/`LiveFrame` API-compat smoke tests; 40-col plain-text degradation; source-scan assertion that no raw `\033[` math remains in `style.py`/`frame.py`.
- **TEST-006** (D): pipeline row glyphs/updates via recording Console; failure panels trimmed to ≤30 meaningful lines with `fix_cmd` hints; `ExperimentalWarning` filtered by default; `spec_integrity` skip renders `–`; sequential plain-text fallback on non-TTY.
- **TEST-007** (C): `gates.yaml` override effectiveness; auto-detect selection matrix (jest vs vitest, biome vs prettier, tsc vs pyright, Go); precedence chain; `--auto-fix` green-after-fix path with `produced` append; opt-out default; `fix_cmd` restricted to format/lint; `gate config show` table with source tags, zero gate executions.
- **TEST-008** (regression): full engine suite (`uv run pytest`), `ruff check`, `mypy src`, and `3pwr gate run --path engine ... --tier Standard` after every phase (CON-003); trust-spine coverage ≥95% maintained.
- **TEST-009** (E2E): live `3pwr run` against `3powers-test-env` at the end of each delivery unit (TASK-027, TASK-053) validating plan 030's post-delivery checklist.

## 7. Risks & Assumptions

- **RISK-001**: The Rich rewrite (G2) changes rendering internals of code exercised by many tests; goldens for `--json` and plain-text paths must be captured **before** the rewrite (TASK-035 depends on a pre-TRIX capture) or the byte-identity criterion cannot be proven.
- **RISK-002**: Line numbers in plan 030 (`cli.py:3869`, `:4223`, `:3573`, `:4427`, `:3904`, `:2949`, `:3299`) drift as Phase 1–4 edits land; each task must re-locate its anchor by the quoted code, not the number (anchors verified against current HEAD at plan-creation time).
- **RISK-003**: `spec_integrity` may flag the amended `specs/015-cli-experience/spec.md` (TASK-029); the maintainer re-seal procedure (with the independent signing key, DEP-004) must be executed as part of Phase 6 or the engine's own gate run goes red.
- **RISK-004**: Auto-detection (C2) probing project files could mis-select tooling in repos with leftover config files (e.g., both `jest.config.*` and `vitest.config.*`); mitigated by the fixed first-match order in the detection table, the startup print, `gates.yaml` override precedence, and `gate config show`.
- **RISK-005**: `rich.live.Live` interacting with streamed agent stdout (G5) can reintroduce redraw races the custom renderer already suffers from; mitigated by routing all writes through the single Console and validating with the live E2E run (TASK-053).
- **RISK-006**: Committing `ledger.jsonl` and `progress.md` in stage commits (A4/E1) could conflict with `commit_stage()` path handling for already-committed or ignored paths; the function's existing no-op behavior for committed paths is asserted in TEST-001/TEST-003.
- **ASSUMPTION-001**: `conformance.referenced_ids()` (or its equivalent in `engine/src/threepowers/conformance.py`) already returns the requirement IDs referenced by the oracle/coder tests; A3 only wires them into the gate details.
- **ASSUMPTION-002**: The adapter manifests' `toolchain:` section exists (per plan 030) or is added in TASK-011 as declarative data only — the core stays language-agnostic (NFR-007).
- **ASSUMPTION-003**: `3powers-test-env` exists as a sibling directory and is usable for auto-mode runs with the TypeScript adapter.
- **ASSUMPTION-004**: The two human gates (spec approval, sign-off) in the E2E runs are exercised by the operator running TASK-027/TASK-053; they are not automated.
- **ASSUMPTION-005**: The seven new specs (`specs/020`–`026`) do not collide with run-workspace NNN allocation — the workspace allocator picks the next free NNN, so run folders created after this plan start at `027+` or coexist by design.

## 8. Related Specifications / Further Reading

- [plan/030-run-identity-gates-ux.md](030-run-identity-gates-ux.md) — the source plan for this implementation plan
- [specs/015-cli-experience/spec.md](../specs/015-cli-experience/spec.md) — CLIUX, amended by Phase 6
- [docs/cli-reference.md](../docs/cli-reference.md) — the public CLI reference updated in Phases 2, 5, 6, 7, 8
- [AGENTS.md](../AGENTS.md) — mandatory workflow, branch/commit discipline, open-source-readiness rules
- [CLAUDE.md](../CLAUDE.md) — architecture deep-dive (gate engine, trust spine, oracle independence)
- [Rich documentation](https://rich.readthedocs.io/) — `Console`, `Live`, `Layout`, `Table`, `Panel` primitives used in Phases 6–7
