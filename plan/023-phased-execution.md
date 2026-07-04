# Plan 023 — Phased execution (PHASE, spec 013)

**Spec:** [`specs/013-phased-execution/spec.md`](../specs/013-phased-execution/spec.md) (Spec ID `PHASE`,
Standard). Extends EXEC (spec 009, the native executive) and RUNLIVE (spec 011, per-stage artifact
contracts). **No trust-spine change** — orchestration, prompts, templates, and config only; no gate,
verdict schema, ledger format, or signing behavior changed (PHASE-SC-005). Delivers the context strategy
the epic demands (3PWR-FR-060/061, previously open) and the playbook's session LAWs.

## Why

The judiciary prompts were strong but the executive's planning content was not: the native `plan`/`tasks`
stage prompts were one sentence each and named no output artifact; `plan`/`tasks` had no artifact
contract, so a stage producing no file still passed (RUNLIVE-FR-003's lenient fallback); `3pwr run` never
injected the approved spec text, prior-stage context, or task file scope into later stage prompts — every
stage depended on the agent rediscovering its inputs; and the plan/tasks templates split work by user
story only, with no context budget, session sizing, or subagent delegation, plus stale `/speckit.*`
references DOCX's sweep did not reach. 3PWR-FR-060/061 (deliberate context strategy; fresh session at
thresholds) had no counterpart in the shipped content.

## What was done

**Feature workspace (PHASE-FR-001) — new [`workspace.py`](../engine/src/threepowers/workspace.py).**
Each feature gets one versioned folder: `specs/<feature>/spec/spec.md` for the legislative artifact and a
sibling `specs/<feature>/artifacts/` folder for every other stage's output (`plan.md`, `tasks.md`, …).
Resolution finds **exactly one** spec per feature folder whichever layout — the workspace form wins, the
legacy flat `specs/<feature>/spec.md` remains resolvable and runnable (no migration of `specs/001–012`,
per the non-goal). `_resolve_spec`/`_resolve_run_spec` now dedupe through `workspace.find_specs`.

**Artifact contracts extended (PHASE-FR-002) — [`artifacts.py`](../engine/src/threepowers/artifacts.py).**
`plan` and `tasks` lost the lenient fallback: each declares a path contract accepting the workspace and
legacy locations, so a dispatch that returns success but writes no artifact is a named
`artifact_missing` failure — never a silent pass. The `specify` contract's wording now names the
workspace path (the pattern already matched both layouts).

**Artifact paths in the ledger (PHASE-FR-003).** `run_stage` records the accepted artifact's
repo-relative path(s) on the `StageResult` (`artifact_paths`), and the per-stage `checkpoint` ledger
entry now carries `artifacts: […]` — the committed artifact trail is reconstructable from the signed
ledger alone.

**Prompts (PHASE-FR-004/005) — [`prompts.py`](../engine/src/threepowers/prompts.py) +
[`cli.py`](../engine/src/threepowers/cli.py) + [`runner.py`](../engine/src/threepowers/runner.py).**
The `plan`/`tasks` stage bodies now specify the output artifact path, required sections, the
phase-decomposition rules (ordered phases; one requirement per task; per-task and per-phase file scope;
`[P]` parallel markers), and the ~4-bytes/token sizing heuristic against the ~110k default budget — at
specify/oracle depth. `CliAgentRunner.dispatch` (and `HostedAgentRunner.dispatch`, judged identically)
accepts per-dispatch `spec_text`/`context`/`file_scope` blocks; the run path now injects the **approved
spec text** into every post-approval stage, a **prior-artifact reference** (path + sha256 digest) into
each next stage, and — for implement phases — that phase's tasks and declared file scope. Assembly stays
a pure function (byte-identical prompts for identical inputs, PHASE-NFR-001).

**Templates (PHASE-FR-006) — [`.3powers/templates/`](../.3powers/templates/).** `plan-template.md` gains
a mandatory *Phase Decomposition* section; `tasks-template.md` was rewritten around phases as
self-contained delegable units — each with `**File scope**:`, `**Depends on**:`, `**Estimated
context**:`, `[P]`/`**Parallel**:` markers, and a **Handoff** block naming the reload set (spec,
constitution/rules, phase tasks, file scope). All `/speckit.*` references are gone from every template
(spec- and checklist-template residue included).

**Context budget (PHASE-FR-007/008/009) — [`phases.py`](../engine/src/threepowers/phases.py) +
[`config.py`](../engine/src/threepowers/config.py) + [`.3powers/config/context.yaml`](../.3powers/config/context.yaml).**
`Settings.context_budget(model)` reads `context.yaml` (per-model `models:` entry → `budget_tokens` →
the shipped ~110k default; `3pwr init` seeds the file). The per-phase estimate is deterministic ceiling
division of the reload set's **bytes** (spec + constitution + phase tasks + prompt + files in scope) by
4 — no tokenizer, no network. After the tasks stage, the run reports each phase's estimate and warns on
an oversize phase (naming phase, estimate, budget; advising a split; noting irreducibility for a single
over-budget task) — **strictly advisory**: no gate, verdict, or advance decision sees it
(PHASE-NFR-002), and stderr carries it so `--json` stdout stays clean (also on the stage result's
`warnings`).

**Fresh session per phase + parallel subagents (PHASE-FR-010/011/012) — `phases.py` + `cli.py`.**
`parse_phases` reads `## Phase N:` sections (scope line + per-task `(files: …)`, `Depends on`,
`[P]`/`Parallel` markers) — a phaseless artifact yields `[]` and implement runs as today's single
session (the degenerate case). Otherwise `_dispatch_phased` runs implement **phase by phase, each a new
headless agent process** whose prompt reloads the phase handoff set (spec + constitution + phase tasks +
file scope) with no carried conversation (3PWR-FR-061 at the engine level). `schedule` batches
consecutive phases for concurrent dispatch **only** when all are parallel-marked, dependency-free, and
pairwise disjoint in declared scope (an undeclared scope never parallelizes; overlaps are reported and
serialized). Results are collected and ordered by phase index; one `run`/`phases` ledger entry is
appended **after** collection from the orchestrator thread, so concurrent completion never touches the
hash chain (PHASE-NFR-003, `3pwr verify` green after a parallel run). Any phase failure fails the stage
naming the phase(s); undispached later phases are recorded as explicitly *skipped*, never passed.

**Docs (PHASE-NFR-004).** CLAUDE.md, AGENTS.md, and docs/STATUS.md describe the workspace layout, the
budget, and phased dispatch; 3PWR-FR-060/061 flipped to delivered in STATUS.

## Verification

- **Tests:** [`engine/tests/test_phases.py`](../engine/tests/test_phases.py) — 32 tests naming each
  PHASE-FR/NFR id: workspace + legacy resolution and the exactly-one property (FR-001); hard plan/tasks
  contracts with named failures (FR-002); checkpoint entries carrying artifact paths, proven end-to-end
  from the ledger (FR-003); prompt content review + deterministic assembly with spec/context/scope blocks
  (FR-004/005); template handoff/size/no-speckit scan (FR-006); budget default/override/per-model +
  garbage rejection (FR-007); byte-deterministic estimates (FR-008); advisory warnings incl. the
  irreducible edge (FR-009); N-dispatch phased implement with a proven-concurrent `[P]` batch, the
  phaseless single-dispatch case (FR-010/011), overlap serialization + the disjointness property
  (FR-011), deterministic result order, named failures, explicit skips (FR-012); and a full fake-agent
  `3pwr run` whose ledger verifies afterwards (PHASE-NFR-003, PHASE-SC-001/004). The pre-existing
  `test_artifacts`/`test_native_runner` fakes were taught to write plan/tasks artifacts (the FR-002
  behavior change).
- **Engine self-green (PHASE-NFR-004):** `uv run pytest` — **530 passed, 1 skipped**; `ruff check` +
  `ruff format --check` clean; `mypy src` clean.
- **Determinism (PHASE-NFR-001):** estimate/prompt/schedule tests assert byte-identical repeats; the
  scheduler's property test asserts empty scope intersection for every concurrent pair.
- **No trust-spine change (PHASE-SC-005):** `canonical`/`keys`/`ledger`/`verify` untouched; the phases
  module imports no ledger/signing code (asserted by test); the lifecycle steps/gates are unchanged
  (asserted by test).

## Handoff — residuals

- The **budget default is byte-heuristic** (~4 bytes/token); a per-model tokenizer-informed estimate
  stays out of scope by design (deterministic, offline).
- Live proof of parallel dispatch under a real agent CLI rides on the existing gated live-e2e residual
  (RUNLIVE-FR-007) — the suite proves it with a fake agent and a real thread barrier.
- Legacy features keep the flat layout until an explicit maintainer migration (a PHASE non-goal).
