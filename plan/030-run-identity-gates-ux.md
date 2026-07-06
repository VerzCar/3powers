# Plan 030 — Run identity, configurable gates, diagnostics, progress tracking, and terminal UX

**Git branch:** `feat/030-run-identity-gates-ux`

**Covers seven tracks** planned together because they share a root cause (the run's identity is opaque to the
user and to its own artifacts) and compound each other (better identity → better gate messages →
better progress file → better terminal UX). Each track is independently deliverable and tested.

## Decisions recorded

The following design decisions were made interactively before finalising this plan:

| Decision | Choice | Rationale |
|---|---|---|
| CLIUX spec amendment | Formally amend `specs/015-cli-experience/spec.md` (FR-003) | Rich is a single safe dep; the spec should reflect the delivered code |
| `gates.yaml` git scope | Committed to the repo — shared team config | Seeded by `3pwr init`, versioned like all of `.3powers/config/` |
| Auto-fix default | Opt-in — `--auto-fix` flag required | Agent output must not be silently mutated mid-run |
| Delivery | Two PRs: A+B+E+F first, then G+D+C | Isolates low-risk identity/diagnostics from the larger Rich refactor |
| Progress granularity | Phase-level included | The user explicitly cited phases; phase visibility is the main use-case |

---

## Why now

Plans 017–019 delivered the SRCX workspace (per-run `specs/<NNN>-<slug>/`), git integration, and a
persistent live bar. They leave five rough edges that block real-world enterprise adoption:

1. **Identity collapse.** The auto-allocated `NNN` from the workspace is the run's natural short
   identity, but `spec_id` still defaults to the literal string `"RUN"` throughout the engine
   (ledger entries, oracle folder, gate messages, resume hints). A user cannot tell runs apart in
   the ledger or by folder name.
2. **Gate failure UX.** Gate failures emit a single "gates red" line and generic resume/inspect
   hints. Users see none of the individual gate results, miss prerequisite-missing errors, and
   cannot copy a working resume command.
3. **Gate tooling lock-in.** The engine ships a fixed toolchain per adapter (biome, vitest, semgrep…).
   Enterprise projects already have their own formatters, test runners, and linters. Forcing new
   deps is a blocker.
4. **No durable run progress.** The live bar is ephemeral; the ledger is machine-readable.
   There is no human-readable file in the run folder an operator can `cat` or share.
5. **Terminal UX.** The custom ANSI renderer in `style.py`/`frame.py` has a growing surface area
   and degrades poorly. Gate output is not structured as a pipeline; gate details scroll off-screen.

---

## Track A — Run identity (RUNID)

**Spec ID: `RUNID` (new spec 020)**

### Problem

`cmd_run()` sets `spec_id = args.spec_id or "RUN"` at `cli.py:3869` before the workspace is
allocated (line 4223). So even though `specs/030-add-button/` is correctly created, every ledger
entry, oracle dispatch, gate message, and resume hint uses the opaque string `"RUN"`.

Four concrete symptoms:

| Symptom | Location |
|---|---|
| Ledger `spec_id` field is `"RUN"` | `cli.py:3869` |
| Oracle folder in tests is `MVZ` (spec slug) not `030` | oracle prompt / agent template |
| `requirement_ids` array in ledger entries is always `[]` | conformance gate not writing to gate details |
| Ledger `ledger.jsonl` is never git-committed | `gitflow.commit_stage()` only commits `produced` paths |

### Solution

**A1 — Derive spec_id from the workspace NNN.**

After workspace allocation at `cli.py:4223`, patch `spec_id` in-place when no `--spec-id` was
given:

```python
# cli.py — immediately after feature_dir is resolved
if not args.spec_id and feature_dir is not None:
    spec_id = feature_dir.name.split("-")[0]   # "030-add-button" → "030"
```

All downstream consumers (ledger calls, gate messages, resume hints, oracle dispatch, branch
naming via `gitflow.run_branch_name`) then receive the real NNN automatically, because they all
use the `spec_id` local variable already.

**A2 — Oracle test folder.**

The oracle prompt template (`.3powers/templates/agents/oracle.agent.md`) and the `oracle dispatch`
command instruct the agent to place tests under `tests/oracle/<spec-id>/`. Because `spec_id` is
now the NNN, the oracle agent naturally creates `tests/oracle/030/` rather than using the spec
slug. No code change required beyond A1; only verify the template uses `{spec_id}` not `{slug}`.

**A3 — Populate `requirement_ids` in the ledger.**

`verdict.requirement_ids()` collects IDs from `gate.details["requirement_ids"]` but the
`spec_conformance` gate (`gates.py`) never writes that key into its details dict. Fix:

In `threepowers/gates.py`, in the `_run_spec_conformance()` function (or equivalent), after
scanning the test files with `conformance.referenced_ids()`, add the discovered IDs to the gate's
`details` dict:

```python
gate_details["requirement_ids"] = sorted(referenced)   # list[str]
```

`Verdict.requirement_ids()` at `verdict.py:99` already aggregates from all gates — no change
needed there. The ledger's `requirement_ids` field will be populated on the next verdict.

**A4 — Commit `ledger.jsonl` with each stage commit.**

`gitflow.commit_stage()` at `gitflow.py:285` commits only the paths in `produced`. The ledger
lives at `.3powers/ledger.jsonl`. Fix: append the ledger's repo-relative path to `produced`
whenever it is non-empty and the stage commit is being made:

```python
# cli.py — in the stage-commit block (≈ line 3573), after produced_box.get("paths")
ledger_rel = str(s.ledger_path.relative_to(s.root))
if ledger_rel not in produced:
    produced = list(produced) + [ledger_rel]
```

This keeps every stage commit self-contained: the ledger state at the time of the stage commit is
atomically bundled with the artifact the stage produced. The `commit_stage` function already
handles paths that are already committed (no-op), so no double-commit risk.

### Acceptance criteria

- `3pwr run "<intent>"` allocates `specs/030-add-button/` and every subsequent ledger entry
  shows `"spec_id": "030"`.
- `3pwr run --resume --spec-id 030` in the gates-red hint is filled with the real NNN.
- Oracle writes `tests/oracle/030/…` (not a spec slug).
- Ledger entries for verify verdicts have a non-empty `requirement_ids` array.
- `git log` after any producing stage shows `.3powers/ledger.jsonl` in the commit.

---

## Track B — Gate failure diagnostics (GDIAG)

**Spec ID: `GDIAG` (new spec 021)**

### Problem

When gates fail the operator sees:

```
✗ gates red — the deterministic gate suite failed. Inspect with `3pwr gate run --spec <spec> --tier
<tier>`, fix the failing gate(s), then `3pwr run --resume --spec-id RUN`.
```

Four specific issues:

1. "Gates red" is a verdict label, not a diagnosis. The user does not see *which* gates failed inline.
2. `--spec <spec>` requires knowing the spec file path; the user just ran `3pwr run` and has a NNN.
3. `--spec-id RUN` is a literal placeholder, not the actual run ID.
4. Prerequisite-missing errors (e.g., `biome` not installed) surface only in raw stderr, buried in
   the gate detail lines with no explicit "install X" message.

### Solution

**B1 — Inline gate failure summary.**

In `orchestrate.py`, the `format_event()` function emits the "gates red" line when
`ev.step == "gate_red"`. Replace the one-liner with a structured summary: the full gate verdict is
already available in `ev.data["verdict"]`; render each failed gate name and its first actionable
error line:

```
✗  gates failed (3 of 9):
   format · biome   ↳ run `biome check --write .` to auto-fix
   types  · tsc     ↳ 2 type errors — see above
   tests  · vitest  ↳ 1 test failed — see above
   Resume: 3pwr run --resume --spec-id 030
   Inspect: 3pwr gate run --id 030
```

**B2 — `3pwr gate run --id <NNN>` shorthand.**

Add `--id <NNN>` as an alias for `--spec <path>` to `gate run`. When `--id 030` is given, the
engine locates `specs/030-*/spec.md` via `workspace.resolve_feature_dir(root, "030")` (a small
helper that globs `specs/030-*/` and asserts exactly one match). This removes the need to know the
full spec path and matches the UX of every other subcommand that takes `--spec-id`.

**B3 — Prerequisite-missing detection and guidance.**

Before any gate command is run, `gates.py` already calls `adapters.probe_tool()`. When a probe
fails, surface it explicitly in a dedicated "prerequisites missing" section printed before the
pipeline:

```
⚠ prerequisites missing — install before re-running:
  biome     npm install --save-dev @biomejs/biome
  osv-scanner  https://google.github.io/osv-scanner/installation/
```

The tool-to-install mapping is declared in the adapter manifest's `toolchain:` section (already
present). The gate run does not proceed if any required tool for a non-optional gate is missing;
it exits with the setup exit code and emits the install hints in structured form.

**B4 — Resume hint uses actual NNN.**

After A1 lands, this is a no-op because `spec_id` will already be `"030"`. But confirm that every
resume hint in `cli.py` uses the `spec_id` local variable (not a literal), including:
- `cli.py:4427` — gates-red resume line
- `cli.py:3904` — gate-pause status rows
- `cli.py:2949` — notification message

### Acceptance criteria

- Gates-red output shows each failed gate name, its adapter tool, and its first actionable line.
- `3pwr gate run --id 030` works identically to `3pwr gate run --spec specs/030-.../spec.md`.
- A missing prerequisite triggers a named install hint before any gate runs.
- Resume hint in all failure/pause messages contains the real NNN.

---

## Track C — Configurable gates (GATECFG)

**Spec ID: `GATECFG` (new spec 022)**

### Problem

The engine hard-codes the test runner, formatter, and type-checker per adapter (e.g., vitest,
biome, tsc for TypeScript). Enterprise projects already have their own tool choices (jest, playwright,
prettier, eslint, pyright, go test, gofmt…). Adding 3Powers today means adding unwanted deps.

### Solution

**C1 — Per-gate override in `.3powers/config/gates.yaml`.**

A new file `.3powers/config/gates.yaml` overrides any gate key in the adapter manifest on a
project-by-project basis. It is **committed to the repo** and versioned alongside the rest of
`.3powers/config/` — it is a shared team configuration, not a personal local override. It is
seeded (with sensible defaults and comments) by `3pwr init`. The engine reads the adapter manifest
first, then deep-merges overrides from `gates.yaml` before executing. The file is structured as:

```yaml
# .3powers/config/gates.yaml
# Override the adapter's default gate commands for this project.
# Keys match the adapter's gates: section names.

format:
  check_cmd: ["npx", "prettier", "--check", "."]
  fix_cmd:   ["npx", "prettier", "--write", "."]

lint:
  check_cmd: ["npx", "eslint", "."]
  fix_cmd:   ["npx", "eslint", "--fix", "."]

types:
  cmd: ["npx", "tsc", "--noEmit"]

tests:
  cmd: ["npm", "run", "test:unit"]
  coverage_format: lcov
  coverage_path:   coverage/lcov.info
```

Only the keys present override the adapter; everything else falls back to the adapter manifest.
The config is loaded in `adapters.py:load_adapter()` after the base YAML is parsed, in a single
`dict.update()` pass per gate block.

**C2 — Auto-detect project's native tooling.**

When `gates.yaml` does not override a gate, the engine performs a lightweight probe at `gate run`
startup to see if a project-native alternative is already configured:

| Gate | Detection signal | Auto-selected tool |
|---|---|---|
| `format` | `biome.json` present → biome; `.prettierrc`/`prettier.config.*` → prettier | first match |
| `lint` | `biome.json` → biome; `.eslintrc*` / `eslint.config.*` → eslint | first match |
| `types` | `tsconfig.json` → tsc; `pyproject.toml`+`[tool.pyright]` → pyright | first match |
| `tests` | `vitest.config.*` → vitest; `jest.config.*` → jest; `playwright.config.*` → playwright | first match |
| `tests` (Go) | `go.mod` → `go test ./...` | always |
| `format` (Go) | `go.mod` → `gofmt -l .` | always |

The auto-detect result is printed once at gate-run startup (not on every gate), e.g.:

```
auto-detected gates:  format=biome  tests=vitest  types=tsc
```

Auto-detect is overridden by `gates.yaml`. The adapter manifest's explicit `cmd` is the final
fallback.

**C3 — `fix_cmd` auto-fix mode (opt-in).**

Add a `fix_cmd` key to the adapter's `gates:` YAML (format, lint only; not types/tests/mutation).
Add an **`--auto-fix` flag** to `3pwr gate run` and `3pwr run`. Auto-fix is **opt-in only** —
it does not run by default, so the agent's produced output is never silently mutated mid-run.

When `--auto-fix` is active and a format/lint gate fails:

1. Run `check_cmd` first (standard gate evaluation).
2. If it fails AND `fix_cmd` is configured, run `fix_cmd`, print `  ↳ auto-fixed by <tool>`, then
   re-run `check_cmd`.
3. If the second run passes, the gate is green. The auto-fixed paths are appended to `produced`
   so the stage commit picks them up (GITX-FR-008).
4. If the second run still fails, the gate is red and the failure is reported normally.

Without `--auto-fix`, the gate fails on the first `check_cmd` failure and the `fix_cmd` hint is
printed in the failure panel (Track D) as a suggested manual command.

The default adapter manifests are updated to include `fix_cmd` for `format` and `lint` gates.

**C4 — `3pwr gate config show` command.**

A new subcommand renders the effective gate configuration (adapter base + `gates.yaml` overrides +
auto-detected) as a table, so the user can verify what the engine will actually run:

```
$ 3pwr gate config show --adapter typescript
gate         tool      check_cmd                    fix_cmd
format       biome     biome check .                biome check --write .    [auto-detected]
lint         biome     biome check .                biome check --write .    [auto-detected]
types        tsc       tsc --noEmit                 —
tests        vitest    vitest run --coverage        —
mutation     mutmut    mutmut run                   —
```

### Acceptance criteria

- A project with `gates.yaml` overriding `tests.cmd` to `npm run test:unit` passes gate run
  using that command.
- Auto-detection selects jest when `jest.config.ts` is present and no `vitest.config.*` exists.
- `--auto-fix` on a biome-formatting failure runs `biome check --write .`, re-runs, and marks
  the gate green when the re-run passes.
- `3pwr gate config show` prints the effective tool for every gate without running any gate.

---

## Track D — Pipeline gate view (GATEPIPE)

**Spec ID: `GATEPIPE` (new spec 023)**

### Problem

Gate output is a serial stream. The operator cannot see at a glance which gates are still running,
which have passed, and which have failed. The detail lines (biome diffs, tsc errors, test
failures) scroll off-screen. The "failures:" summary at the bottom repeats raw error text with no
structure.

### Solution

**D1 — Pipeline header row per gate.**

At gate-run time, as each gate starts and finishes, emit a compact pipeline row:

```
  ○ format  · biome        (running…)   → updated in-place to:
  ✓ format  · biome        0.4 s
  ✗ types   · tsc          1.2 s        2 errors
```

Each row is at most one line. Failures are marked but their detail stays anchored below (D2).

**D2 — Expandable gate detail.**

After all gates finish, print a "failures" block — one panel per failed gate — with:

- Gate name + tool + elapsed time
- The error lines, indented, trimmed to the first 30 meaningful lines (not blank/noise).
- A `fix_cmd` hint if one is configured: `  ↳ auto-fix: biome check --write .`
- For dependency/secret scan: the CVE/finding ID, the package/file, and a remediation hint.

```
─────────────────────────────── format · biome ──────────────────────────────
  vite.config.ts:12  +  },
  vite.config.ts:13  +  test: {
  ...
  ↳ auto-fix: biome check --write .
─────────────────────────────── types · tsc ─────────────────────────────────
  tests/unit/foo.test.tsx:178  error TS2345: Argument of type 'HTMLElement' is
    not assignable to parameter of type 'HTMLButtonElement'
─────────────────────────────── dependency_scan · osv-scanner ───────────────
  GHSA-qx2v-qp2m-jg93  postcss  — update to ≥ 8.4.31
  GHSA-q8mj-m7cp-5q26  qs       — update to ≥ 6.10.3
─────────────────────────────── secret_scan · betterleaks ───────────────────
  .next/cache/.rscinfo:1  generic-api-key
  ↳ add .next/ to .gitignore and rotate the exposed key
```

**D3 — Noise filters.**

- Suppress Node.js `ExperimentalWarning` lines unless `--verbose`.
- Suppress blank lines inside gate output.
- The `spec_integrity` "skipped" line is printed at `–` (info) not `✗` (fail).
- The "failures:" block at the bottom of the current output is **removed**; the per-gate panels
  replace it.

### Acceptance criteria

- Running `3pwr gate run` shows one compact status row per gate, updated in-place.
- After all gates finish, each failing gate has its own panel with trimmed, deduplicated errors.
- Node.js `ExperimentalWarning` does not appear in default (non-verbose) output.
- `spec_integrity` "skipped" renders as `–` not `✗`.

---

## Track E — Progress file (PROGFILE)

**Spec ID: `PROGFILE` (new spec 024)**

### Problem

There is no human-readable, persistent record of where a run is and what the operator should do
next. The ledger is the authoritative source but requires `3pwr run --status` to query. An
operator picking up a paused or failed run has no quick reference.

### Solution

**E1 — `progress.md` in the run folder.**

The engine writes and updates `specs/<NNN>-<slug>/progress.md` at every lifecycle event:
stage start, stage complete, gate verdict, human gate pause, failure. The file is committed as
part of each producing stage commit (appended to `produced`, same as the ledger in A4).

**E2 — Content schema.**

The file tracks both stage-level and phase-level progress (decided interactively). Phase detail
is only shown when the current stage has phases.

```markdown
# Run 030 · add-button · 2026-07-06 14:32

## Stage progress

| Stage     | Status       | Completed          |
|-----------|--------------|--------------------|
| discover  | ✓ done       | 2026-07-06 14:32   |
| specify   | ✓ done       | 2026-07-06 14:35   |
| plan      | ✓ done       | 2026-07-06 14:41   |
| build     | ⏳ phase 2/3  |                    |
| verify    | ○ pending    |                    |
| review    | ○ pending    |                    |
| ship      | ○ pending    |                    |
| observe   | ○ pending    |                    |

### Build — phase detail

| Phase | Description              | Status      | Tasks done |
|-------|--------------------------|-------------|------------|
| 1     | ButtonComponent styles   | ✓ done      | 3/3        |
| 2     | HeaderComponent logic    | ⏳ running   | 2/5        |
| 3     | Integration tests [P]    | ○ pending   | —          |

## Current state

**Stage:** build — phase 2 of 3 (2/5 tasks done)
**Since:** 2026-07-06 14:41 (8 min ago)

## Last verdict

— (build not yet gated)

## Helper commands

```bash
# Check current status
3pwr run --status --spec-id 030

# Resume after approval / gate-pause
3pwr run --resume --spec-id 030 --approver <you>

# Abort this run
3pwr abort --spec-id 030

# Re-run gates only
3pwr gate run --id 030 --tier Standard
```

## Gate failures (last verify attempt)

(none yet)
```

**E3 — Update triggers.**

| Trigger | Updated fields |
|---|---|
| Stage start | Row status → `⏳ running`, Current state block |
| Stage complete | Row status → `✓ done` + timestamp |
| Gate verdict PASS | Last verdict block |
| Gate verdict FAIL | Last verdict block + Gate failures section |
| Human gate pause | Current state → `🔒 paused at <gate>` |
| Run failure | Current state → `✗ failed — <class>` |

The file is written by a new `progress.write()` helper in a new `threepowers/progress.py`
module. It takes the current `lifecycle.RunState` and the `feature_dir` path, renders the
markdown, and writes it atomically (write to `.progress.md.tmp`, then rename). It is called
from the run loop in `cli.py` at the same points as the existing `orchestrate.emit_event()`.

### Acceptance criteria

- `specs/030-add-button/progress.md` exists after the first producing stage.
- Stage rows update to `✓ done` with a timestamp when the stage completes.
- Gate failures section shows the failed gate names (not raw errors — those stay in the panel).
- The file is included in the stage commit alongside the stage artifact.

---

## Track F — Phase orchestration prompt (PHASEPR)

**Spec ID: `PHASEPR` (new spec 025)**

### Problem

The current phase prompt in `_dispatch_phased()` sends the tasks artifact and phase number but
does not clearly instruct the agent to:
(a) implement **only** the tasks in the declared phase,
(b) mark tasks as completed in `tasks.md` when done,
(c) treat `[P]`-marked tasks as runnable in parallel via subagents.

This leads to agents either re-doing earlier phases or silently skipping task completion markers.
Also: if a headless session outputs a clarifying question and then waits, the engine records the
session as complete (the process exits), and the operator never sees the question.

### Solution

**F1 — Rewrite the phase dispatch prompt block.**

In `cli.py:_dispatch_phased()` (≈ line 3299), the per-phase context block injected into the agent
instruction is replaced with a structured, explicit contract:

```
═══════════════════ PHASE INSTRUCTION ════════════════════════
You are implementing Phase {N} of {total} for run {spec_id}.

SCOPE: implement only the tasks explicitly listed under "## Phase {N}" in the tasks file below.
Do NOT modify files outside the declared file scope for this phase.
Do NOT implement tasks from other phases.

PARALLEL TASKS: any task marked [P] in this phase may be dispatched concurrently via subagents.
Dispatch all [P]-marked tasks in parallel, then collect their results before proceeding.

COMPLETION: when you have finished every task in this phase, update tasks.md:
mark each completed task with `[x]` in its checkbox. If a task cannot be completed,
mark it `[!]` and append a one-line reason.

CLARIFICATIONS: do not ask the operator for input. If something is unclear, make the most
reasonable decision and document your assumption in a comment in the code (not in tasks.md).

Phases already completed: {completed_phases_summary}
```

**F2 — Completed-phases summary.**

Before dispatching phase N, the engine collects the task headings from phases 1..N-1 (from the
tasks artifact) and injects a one-line summary so the agent does not redo earlier work:

```
Phases already completed: Phase 1 (HeaderComponent styles), Phase 2 (ButtonComponent)
```

**F3 — Question/stall detection.**

After a phase session ends, the engine scans the last 500 bytes of the session transcript for
patterns that suggest the agent ended with an unresolved question (`?` followed by no code block,
`I need clarification`, `Could you clarify`…). When detected, emit a `warn` event to the terminal:

```
⚠ phase 2 ended with a possible unanswered question — review the transcript
  (run: 3pwr run --status --spec-id 030 to see the full transcript path)
```

This is purely advisory — the run continues.

### Acceptance criteria

- Phase 2 of a 3-phase run never touches files declared in Phase 1's scope.
- `tasks.md` checkboxes are `[x]` for all phase-1 tasks after phase 1 completes.
- `[P]`-marked tasks within a phase are dispatched concurrently (existing `ThreadPoolExecutor`
  path, verified by checking that two tasks finish within max(t1,t2)+10% rather than t1+t2).
- A session ending with `Could you clarify…` emits a warn line to the terminal.

---

## Track G — Terminal UX with Rich (TRIX)

**Spec ID: `TRIX` (new spec 026)**

### Supersedes

CLIUX-FR-003 stated "zero external dependency for the structured-output toolkit." This plan
formally supersedes that constraint via an amendment to `specs/015-cli-experience/spec.md`.
The amendment task is part of this plan's delivery — FR-003 is revised to read "the
structured-output toolkit may depend on `rich` (MIT-licensed, pure-Python, no transitive C
extensions)". Rich is a mature library with no transitive C dependencies, making it a safe single
addition to the engine's dependency set. The `--json`/`--yes`/`NO_COLOR` contracts and exit-code
contract (CLIUX-NFR-001/002) are unchanged and explicitly preserved by the Rich integration.

### Problem

`style.py` + `frame.py` implement a custom ANSI renderer that has grown to ~500 lines of
string-manipulation code. It has known freezing issues on slow agent dispatch (the `\r` in-place
redraw races with agent stdout), poor degradation on narrow terminals, and no structured layout
primitives (panels, tables, progress bars). Adding the pipeline view (Track D) would require
another ~200 lines of custom ANSI math.

### Solution

**G1 — Add `rich` to engine dependencies.**

In `engine/pyproject.toml`:

```toml
dependencies = [
    ...
    "rich>=13.7,<15",
]
```

**G2 — Replace `style.py` and `frame.py` with a Rich-backed implementation.**

Preserve the public API (`Styler`, `LiveFrame`) so call sites in `orchestrate.py`, `cli.py`, and
`gates.py` need no changes in the first pass. Internally:

- `Styler` wraps `rich.console.Console` and `rich.style.Style` instead of hand-rolled SGR codes.
- `LiveFrame` wraps `rich.live.Live` + `rich.layout.Layout` instead of the `\033[A`/`\033[J`
  cursor trick. The bottom-anchored bar becomes a `rich.layout` region pinned to the bottom of
  the console.
- Color/NO_COLOR/quiet/verbose behaviour remains controlled by the existing `ui.yaml` + env vars;
  Rich's own `FORCE_COLOR`/`NO_COLOR` detection is used as a fallback.

**G3 — Pipeline gate view (integration with Track D).**

The per-gate status rows (Track D1) are rendered as a `rich.table.Table` with three columns:
`status glyph`, `gate name · tool`, `elapsed + summary`. The table is inside a `rich.live.Live`
context so rows update in-place without re-drawing the entire screen.

The gate-failure panels (Track D2) are rendered as `rich.panel.Panel` instances with a dim header,
printed after the live context exits.

**G4 — Bottom-anchored stage bar.**

The persistent stage bar (`render_tracker`) becomes a `rich.layout` bottom section pinned at 1–2
lines. It shows:

```
▌ build  ○ specify ✓  ○ plan ✓  ● build  ○ verify  ○ review  ○ ship   [08:42]
```

This replaces the `frame.py` `LiveFrame` bottom-anchor logic.

**G5 — Agent transcript streaming.**

Agent stdout (currently emitted line-by-line via `orchestrate.emit_event`) is displayed in the
main scrollback area above the live bottom bar, unchanged. Rich does not interfere with existing
print/sys.stdout writes; they are routed through `Console(highlight=False)` to preserve raw agent
output.

**G6 — Degradation.**

- `--json`: Rich Console is created with `force_terminal=False`, `highlight=False`; all output is
  plain text as before.
- `NO_COLOR` / `--yes`: `Console(no_color=True, highlight=False)`.
- Non-TTY (piped output): `Console(force_terminal=False)` — plain text, no live updates.

### Acceptance criteria

- `uv sync` in the engine dev env pulls in `rich` with no conflicts.
- `3pwr run` and `3pwr gate run` produce visually identical output to the current implementation
  on a narrow (40-col) terminal (plain-text degradation).
- `--json` output is byte-for-byte identical to pre-TRIX (Rich Console not used for JSON path).
- The bottom stage bar is always visible while a run is in progress on a TTY.
- No `style.py` or `frame.py` ANSI string-math survives; all rendering goes through Rich.

---

## Delivery order and dependencies

| Track | Spec ID | Depends on | Risk | Effort |
|---|---|---|---|---|
| A — Run identity | RUNID | — | Low | Small |
| B — Gate diagnostics | GDIAG | A (spec_id fix) | Low | Small |
| E — Progress file | PROGFILE | A (spec_id) | Low | Small |
| F — Phase prompt | PHASEPR | — | Low | Small |
| G — Terminal UX (Rich) | TRIX | — | Medium | Medium |
| D — Pipeline gate view | GATEPIPE | G (Rich) | Low | Small |
| C — Configurable gates | GATECFG | — | Medium | Medium |

### PR 1 — Identity + diagnostics + progress + phase prompt (A → B → E → F)

Tracks A, B, E, and F are low-risk, independently testable, and unblock real usability gaps
immediately. They share no dependency on the Rich refactor and can be reviewed as a focused set.

- A lands first (all other tracks in this PR depend on the real spec_id).
- B and E follow in parallel (both depend on A but not each other).
- F is independent and can be merged any time in this PR.

### PR 2 — Rich terminal UX + pipeline gate view + configurable gates (G → D → C)

- G (Rich adoption) is the prerequisite for D (pipeline view is implemented on top of Rich).
- C (configurable gates) is the most cross-cutting change and goes last, fully isolated.
- The CLIUX spec amendment (`specs/015-cli-experience/spec.md`) is part of PR 2 (delivered with G).

---

## Headless execution and user feedback (track not required)

The user raised whether headless agents can await user input. Current behaviour: the native
executive (`NativeRunner.dispatch_once`) launches the headless CLI and streams its stdout. The
headless Claude session is given a fully self-contained prompt and **does not read stdin**; when
the process exits, the engine records the output. If Claude outputs a question and then exits,
Track F's stall-detection (F3) surfaces it as a warning. No architectural change is needed to
the executive itself — the Phase F prompt rewrite is the primary mitigation.

---

## Spec files to create / amend

| Path | Spec ID | Action | Contents |
|---|---|---|---|
| `specs/020-run-identity/spec.md` | RUNID | Create | FR-001..006 for A1–A4 |
| `specs/021-gate-diagnostics/spec.md` | GDIAG | Create | FR-001..006 for B1–B4 |
| `specs/022-gate-config/spec.md` | GATECFG | Create | FR-001..010 for C1–C4 |
| `specs/023-gate-pipeline/spec.md` | GATEPIPE | Create | FR-001..005 for D1–D3 |
| `specs/024-progress-file/spec.md` | PROGFILE | Create | FR-001..008 for E1–E3 (incl. phase-level) |
| `specs/025-phase-prompt/spec.md` | PHASEPR | Create | FR-001..005 for F1–F3 |
| `specs/026-terminal-ux/spec.md` | TRIX | Create | FR-001..008 for G1–G6 |
| `specs/015-cli-experience/spec.md` | CLIUX | **Amend** | Revise FR-003: permit `rich` as a declared engine dependency |

---

## Engine files affected

| File | Track(s) | Change |
|---|---|---|
| `engine/src/threepowers/cli.py` | A, B, C, E, F | spec_id derivation; ledger in produced; fix_cmd dispatch; progress.write calls; phase prompt |
| `engine/src/threepowers/orchestrate.py` | B, D | gates-red event formatting; pipeline rows |
| `engine/src/threepowers/gates.py` | B, C, D | prerequisite check; fix_cmd loop; requirement_ids in details; pipeline events |
| `engine/src/threepowers/adapters.py` | C | gates.yaml merge; auto-detect probe |
| `engine/src/threepowers/gitflow.py` | A | ledger path included in commit_stage paths |
| `engine/src/threepowers/style.py` | G | rewrite backed by Rich |
| `engine/src/threepowers/frame.py` | G | rewrite backed by Rich Live |
| `engine/src/threepowers/progress.py` | E | **new** — progress.md writer |
| `engine/src/threepowers/workspace.py` | B | new `resolve_feature_dir(root, nnn)` helper |
| `engine/src/threepowers/phases.py` | F | phase prompt block rewrite |
| `engine/pyproject.toml` | G | add `rich>=13.7,<15` |
| `.3powers/adapters/typescript/adapter.yaml` | C | add `fix_cmd` to format/lint gates |
| `.3powers/adapters/python/adapter.yaml` | C | add `fix_cmd` to format/lint gates |
| `.3powers/adapters/go/adapter.yaml` | C | add `fix_cmd` to format gate |
| `.3powers/config/gates.yaml` | C | **new** — project-level gate overrides (seeded by init) |
| `.3powers/templates/agents/oracle.agent.md` | A | verify uses `{spec_id}` for test folder |
| `.3powers/templates/agents/tasks.agent.md` | F | phase prompt contract |

---

## Verification (post-delivery)

Run the engine's own gate suite at Standard to confirm no regression:

```bash
3pwr gate run --path engine --adapter python \
     --spec specs/002-engine-trust-spine/spec.md --tier Standard --base main
```

Run a live end-to-end against the test environment (`3powers-test-env`) to confirm:

```bash
3pwr run "add a dismiss button to the overflow menu" --mode auto \
    --path ../3powers-test-env --adapter typescript
```

Verify:
- `specs/<NNN>-*/progress.md` exists and stages check out.
- `git log` shows ledger.jsonl in each stage commit.
- Ledger entries for the verify stage have non-empty `requirement_ids`.
- Gate failure output shows the pipeline view with per-gate panels.
- Resume hint in the failure message contains the actual NNN.
