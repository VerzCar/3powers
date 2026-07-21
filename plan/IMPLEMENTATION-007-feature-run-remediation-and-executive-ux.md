---
goal: Actionable auto-remediation, a single numeric run id, richer verdict UX, per-stage subagent models, native token/cost fidelity, and a business-readable changelog for `3pwr run`
version: 1.0
date_created: 2026-07-21
last_updated: 2026-07-21
owner: 3Powers maintainers
status: 'Completed'
tags: [feature, refactor, architecture, cli]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

This implementation plan operationalizes source plan `plan/036-run-remediation-and-executive-ux.md`. It
closes the run loop that plan 035 left legible-but-inert: it makes the harness **fix what it can** (a
bounded, code-only auto-remediation loop at Verify and an opt-in `3pwr gate fix`), **speak one
identifier** (the numeric feature-folder id everywhere, repairing the broken `--spec-id GSW` / `--id GSW`
re-dispatch/inspect/resume hints), **cost less by default** (a per-stage `subagent_models` map), **show
every agent workstep** (native `--output-format stream-json` + a live text-delta renderer), **account for
what it spent** (per-stage/per-phase tokens **and** cost persisted to `progress.md`), and **explain what
shipped in business terms** (an implement-agent-authored, engine-validated `changelog.md`). A parallel,
smaller track makes the verdict/gate panels colorized and legible on a TTY while keeping bytes identical
off-TTY.

The work is split into seven phases mapping to the source plan's six tracks plus a dedicated verification
phase. **Phase 1 (Track A) lands first** because it corrects the identifier every other phase prints.
Phases 2–4 implement the independent Tracks B, D, and E; **Phase 5 (Track C, auto-fix) lands after Phase 1
(correct re-dispatch id) and Phase 4 (per-attempt token/cost)**; Phase 6 (Track F, changelog) follows;
Phase 7 verifies. Although the source plan calls Tracks B/D/E "parallel", this plan **executes all phases
sequentially (no `[P]` marking)** because three shared files — `engine/src/threepowers/orchestrate.py`
(Tracks A, B, C, E), `engine/src/threepowers/cli/run.py` (Tracks A, C, D, E, F), and the
`.3powers/agents/*.yaml` manifests (Tracks D, E) — are each touched by multiple tracks, so parallel edits
would collide (see CON-005, RISK-009).

Execution note (per `AGENTS.md`/`CLAUDE.md`): all Python changes under `engine/src/threepowers/` with
tests under `engine/tests/` are performed by the **python-engineer agent** at implementation time. Every
behavior change ships with a matching `docs/` update in the same unit of work; a behavior change without a
docs update is incomplete. Trust-spine modules (`canonical`, `keys`, `ledger`, `verify`) are High-risk and
must hold coverage ≥ 95% — additive token/cost fields must not regress that floor.

## 1. Requirements & Constraints

- **REQ-A**: Every CLI arg, help string, and output line names the run by its numeric feature-folder id
  (`002`); every printed resume/inspect/re-dispatch command resolves without a resolution error. The
  requirement-ID namespace (`GSW-FR-002`) and oracle seals are unchanged (Decision 1, CLI + output only).
- **REQ-B**: Panel bodies, guidance lines, the deviation command, and the coder hand-back render colorized
  on a TTY and byte-identical off-TTY / under `--json` / `NO_COLOR`; the inert `layout: compact` knob is
  honored.
- **REQ-C**: The auto-fix loop only edits code and re-runs gates; it never records a deviation/advisory,
  never weakens a check, never mutates a verdict, and always records an honest signed verdict per attempt;
  on give-up it prints the step-by-step human remediation summary (Decisions 2, 7, 8).
- **REQ-D**: A per-stage `subagent_models` map steers sub-agent models backend-neutrally via a
  manifest-declared field; unset = no change (byte-identical dispatch); an unknown model for a known
  integration is reported (Decision 4).
- **REQ-E**: Live agent output is followable (stream-json text deltas on a TTY), the full per-attempt
  transcript is always on disk, and per-stage/per-phase **tokens and cost** persist to `progress.md` and
  the stage ledger entries (Decisions 5, 6, 9).
- **REQ-F**: `changelog.md` is agent-authored business prose (Added/Changed/Fixed, traced to
  requirements), engine-validated for requirement coverage and OSS-readiness, and placed like `oracle.md`;
  the top-level `CHANGELOG.md` is untouched (Decisions 3, 11).
- **SEC-001**: No new escape hatch weakens a gate. The auto-fix loop cannot produce a bypass; `gate_gaming`
  remains the backstop; deviations/advisories stay human-only, signed, and auditable.
- **CON-001**: The deterministic verdict, signed ledger, `3pwr verify`, exit codes, and `--json`
  byte-stability are unchanged except for strictly-additive fields `verify` already tolerates (token/cost
  fields, changelog appendix).
- **CON-002**: The deterministic gate/verify path adds no model call. Track C dispatches the *coder* the
  run already owns; Track F prose is authored by the implement agent that already runs.
- **CON-003**: Backend-neutrality holds — Tracks D and E no-op cleanly on backends lacking the relevant
  mechanism; the engine only emits manifest-declared flags (never invents a flag).
- **CON-004**: Phase 1 (Track A) MUST land first (it corrects the printed identifier); Phase 5 (Track C)
  MUST land after Phase 1 (a resolvable re-dispatch id) and after Phase 4 (per-attempt token/cost surfaced)
  per the source plan's ordering.
- **CON-005**: Because `orchestrate.py`, `cli/run.py`, and `.3powers/agents/*.yaml` are each edited by
  multiple tracks, phases are executed **sequentially** (no parallel `[P]`), even though Tracks B/D/E are
  conceptually independent.
- **GUD-001** (OSS readiness): All new user-facing strings (help, guidance, config comments, changelog
  scaffold prose, setup prompts) obey `engine/tests/test_oss_readiness.py` — no internal
  plan/spec/requirement ids; format teaching uses bare `FR-###` / `DEMO-FR-###` (Decision 10).
- **GUD-002** (self-application): The engine stays green under its own gates (ruff/mypy/pytest and
  `3pwr gate run --path engine`, including `gate_gaming` and the High-risk coverage floors) after each
  phase.
- **PAT-001**: Subagent-model and stream-json transport are delivered via a manifest-declared field
  consumed by `agents.build_command` — the engine appends only what the manifest declares (Tracks D + E).
- **PAT-002**: The business changelog mirrors the proven `oracle.md` author-then-validate-then-place
  pattern (`completion.write_record` oracle branch + `validate_oracle_spec`).
- **PAT-003**: The auto-fix loop reuses `orchestrate.coder_handback` + `gates.run_gates` and runs
  **before/independently of** the deviation-proceed check; it never invokes the deviation path.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Track A — unify every CLI argument, help string, and output line on the numeric
  feature-folder id and fix the broken `--spec-id GSW` / `--id GSW` re-dispatch/inspect/resume hints so
  every printed command resolves, while leaving the requirement-ID namespace (`GSW-FR-002`), oracle
  `bundle_hash`, and `conformance` tracing untouched (Decision 1).

| Task     | Description                                                                                                                                                                                                                                                                                                              | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/orchestrate.py` `_gate_red_summary` (`orchestrate.py:365,378-379`): print the run's numeric feature-folder id in the `Resume:` / `Inspect:` lines so the emitted `--spec-id`/`--id` argument is `NNN` (a value `workspace.resolve_feature_dir` can resolve), never the front-matter prefix `verdict.spec_id`. | ✅ | 2026-07-21 |
| TASK-002 | In `orchestrate.py` `_handback_block` (`orchestrate.py:971,975`): print the numeric id in the `re-dispatch:` line and drop the `<spec-id>` literal fallback in favor of the resolved number.                                                                                                                             | ✅ | 2026-07-21 |
| TASK-003 | In `engine/src/threepowers/cli/_common.py` `_format_verdict` header (`cli/_common.py:273`, `spec=GSW`) and `engine/src/threepowers/cli/gate.py` panel subject (`cli/gate.py:206`): show the numeric id as the primary identity; the front-matter prefix may appear only as a clearly-labelled secondary "spec" field, never as the copy-paste `--spec-id`/`--id` value. Where a `gate run --id NNN` produced the verdict, thread `NNN` into the rendered output so the printed command matches what the user typed. | ✅ | 2026-07-21 |
| TASK-004 | Reword the help strings that hide or misstate the numeric semantics: `cli/run.py:2356` (`--spec-id` help, currently `"run id (default: RUN)"`) to state it is the numeric feature-folder id and how it resolves; `engine/src/threepowers/cli/oracle.py:674-677` (`key_help`) to align with the numeric-id vocabulary without presenting a competing "spec-id" meaning; treat `cli/gate.py:367-371` (`gate run --id`) as the canonical wording. | ✅ | 2026-07-21 |
| TASK-005 | Consistency sweep: mirror the canonical numeric-id wording across every other `--spec-id`/`--id` help string and user-facing identifier message (`status`, `abort`, `signoff`, `advance`, `deviation`, `observe`, `provenance`, …) so all say "the run's numeric id, e.g. `002`". No behavior change to resolution — resume/branch already key off the number (`cli/run.py:257-270`, `gitflow.py:166-179`, `orchestrate.py:137-182`). | ✅ | 2026-07-21 |
| TASK-006 | Guardrail (no-op verification): do NOT touch `conformance.extract_spec` (`conformance.py:63-81`), the `_REQ_RE`/namespace logic (`conformance.py:30,51-60`), oracle `bundle_hash` (`oracle.py:70-101`), or `characterize._spec_id_for` semantics beyond keeping them internally consistent. The front-matter `**Spec ID**:` line stays as the requirement-ID namespace source. Record this confirmation in the phase note. | ✅ | 2026-07-21 |
| TASK-007 | Update `docs/cli-reference.md` and any gate/verdict reference under `docs/` so the documented identifier is the numeric feature-folder id everywhere and every documented resume/inspect/re-dispatch command resolves. No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-008 | Confirm `engine/tests/test_oss_readiness.py` stays green for every new/changed help string and identifier message (GUD-001). | ✅ | 2026-07-21 |
| TASK-009 | Extend `engine/tests/test_run_identity.py`: a fake spec with `**Spec ID**: FEAT` and folder `NNN-<slug>` asserts every printed `Resume:`/`Inspect:`/`re-dispatch:` command contains `NNN` and resolves via `resolve_feature_dir`, and that no `--spec-id FEAT` / `--id FEAT` string is emitted anywhere in output or help; add a rendered-output guard that fails on a non-numeric `--spec-id`/`--id` argument. Confirm `engine/tests/test_conformance*.py` and `engine/tests/test_oracle.py` are unchanged (namespace tracing + seal verify still green). Add a `--json` byte-stability assertion (no new required id field). | ✅ | 2026-07-21 |

### Phase 2

- GOAL-002: Track B — route the currently-monochrome panel bodies, guidance lines, deviation command, and
  coder hand-back block through the shared `Styler`, add a small guidance/border color vocabulary, and wire
  the inert `layout: compact` knob; human-output only, `--json`/verdict bytes byte-identical.

| Task     | Description                                                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-010 | In `engine/src/threepowers/orchestrate.py`: `_render_panel` (`orchestrate.py:890-924`) currently passes the body as one uncolored `Text` (`orchestrate.py:915`). Route `_panel_body_lines` (`orchestrate.py:861-887`) and `_remediation_lines` (`orchestrate.py:844-858`) through the shared `Styler`: findings — default weight; `↳ what it means` — dim; `↳ fix` / `↳ auto-fix` — success/accent; `↳ last resort` + the `3pwr deviation …` command — warning; a `↳ waived by active deviation` line — warning/dim. | ✅ | 2026-07-21 |
| TASK-011 | Color the hand-back header and the `re-dispatch:` line in `_handback_block` (`orchestrate.py:965-977`) with a distinct accent so the copy-paste block is scannable. | ✅ | 2026-07-21 |
| TASK-012 | In `engine/src/threepowers/style.py`: add a small named vocabulary to `_RICH_STYLES` (`style.py:33-43`) + `Styler` helpers (`style.py:166-200`) for the guidance/border roles, replacing the hardcoded `"dim"` border/title in `_render_panel` (`orchestrate.py:913-919`). Give the verdict header (`cli/_common.py:263-286`) status-colored `PASS`/`FAIL`. | ✅ | 2026-07-21 |
| TASK-013 | Wire the inert `layout` knob: `layout: compact` is parsed and validated (`config.py:218,222`, `cli/_common.py:110`) but consumed nowhere. Honor it in `_compose` (`cli/_common.py:140-161`) and panel spacing (tighter panels, drop blank separators) so a user can opt into a denser view; `layout: normal` is unchanged. | ✅ | 2026-07-21 |
| TASK-014 | Safety: confirm all color is centrally gated by `color_enabled` (`style.py:102-135`), which forces off for `--json`/`--yes`/`NO_COLOR`/non-TTY; confirm `cmd_gate_run` never builds the styler/panels on the `--json` path (`cli/gate.py:113,161,170`). Keep the `coder_handback` return value pre-color plain text (its golden at `engine/tests/test_gate_pipeline.py:457-491` compares the full block); apply color only when `_handback_block` renders it. | ✅ | 2026-07-21 |
| TASK-015 | Update the `docs/` gate/verdict guide to describe the colorized output hierarchy and the `layout: compact` option. No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-016 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new guidance/border vocabulary and any new user-facing strings (GUD-001). | ✅ | 2026-07-21 |
| TASK-017 | Tests: in `engine/tests/test_gate_pipeline.py` confirm substring guidance assertions survive (text unchanged, ANSI-wrapped) and the `coder_handback` golden (`457-491`) stays plain. In `engine/tests/test_terminal_ux.py` keep the goldens + SGR-byte asserts + the `--json` byte-stability test guarding byte-identity off-TTY. Add: a `layout: compact` test asserting tighter spacing, and a color-on test asserting guidance/deviation lines carry the expected styles. | ✅ | 2026-07-21 |

### Phase 3

- GOAL-003: Track D — add an additive, optional per-stage `subagent_models` map (keyed by stage) and a
  backend-neutral manifest transport field so the maintainer can pin a cheaper sub-agent model per stage
  while the main stage agent keeps its role model; unset changes nothing (Decision 4).

| Task     | Description                                                                                                                                                                                                                                                                                                                             | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-018 | Add an additive, optional `subagent_models` block to `.3powers/config/roles.yaml` and its scaffold copy `engine/src/threepowers/scaffold/config/roles.yaml`, keyed by **stage/step** (`discovery`, `specify`, `clarify`, `plan`, `tasks`, `oracle`, `implement`). Validate values against the `models.yaml` catalog for the resolved integration (Haiku/Flash already listed) in `engine/src/threepowers/config.py`, with a free-form BYOK fallback matching the existing model-pin tolerance. | ✅ | 2026-07-21 |
| TASK-019 | Add a manifest field to `.3powers/agents/<name>.yaml` (and the scaffold copies under `engine/src/threepowers/scaffold/`) expressing how a subagent model is delivered, and teach `agents.build_command` (`agents.py:86-127`; "never invents a flag" `agents.py:108-111`) to emit it when a `subagent_models` entry applies to the dispatched stage. For Claude Code, delivery is via `--agents` JSON with a per-sub-agent `model` field, or the `CLAUDE_CODE_SUBAGENT_MODEL` env var. Backends with no such mechanism declare nothing and the feature no-ops. | ✅ | 2026-07-21 |
| TASK-020 | Resolution at dispatch: in the dispatch closure (`cli/run.py:870` / `CliAgentRunner.dispatch` `runner.py:296-373`) look up `subagent_models[step]` and thread it into `build_command` alongside the main `model`. The main-session `--model` (from `roles.<role>.model`, `cli/run.py:844,858` → `agents.py:113-115`) is unchanged. | ✅ | 2026-07-21 |
| TASK-021 | Extend the `3pwr config roles setup` flow (`engine/src/threepowers/cli/bootstrap.py:226-356`) to optionally offer a per-stage subagent model from the catalog, with cheap models highlighted. | ✅ | 2026-07-21 |
| TASK-022 | Update `docs/` to document the `subagent_models` map, the cost intent, and per-backend support (which backends honor it, which no-op). No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-023 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new config comments, help text, and setup prompts (GUD-001). | ✅ | 2026-07-21 |
| TASK-024 | Tests: in `engine/tests/test_agents.py` / `engine/tests/test_native_runner.py` assert `subagent_models[implement]` produces the expected `--agents`/subagent directive in the assembled argv; unset adds nothing (byte-identical dispatch); an unknown model for a known integration is reported; a backend manifest without the field no-ops cleanly. In `engine/tests/test_bootstrap*.py` assert the setup flow offers the catalog cheap models. | ✅ | 2026-07-21 |

### Phase 4

- GOAL-004: Track E — adopt `--output-format stream-json` for the JSON-strategy backends, add a
  stream-event renderer that echoes live assistant text deltas and reads the final `result` event's
  `usage` + `total_cost_usd`, and persist per-stage/per-phase **tokens and cost** to `progress.md` and the
  stage ledger (additive fields) (Decisions 5, 6, 9).

| Task     | Description                                                                                                                                                                                                                                                                                                                             | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-025 | Enable native usage without killing the live stream: set the JSON-strategy manifests (`.3powers/agents/claude.yaml`, `codex.yaml` where applicable, and their scaffold copies) to request `--output-format stream-json` (with `--verbose` as the CLI requires) via the existing `usage_mode`/`usage_mode_args` mechanism (`agents.py:106-111`) — flipping the currently commented-out `usage_mode: json` at `.3powers/agents/claude.yaml:27`. Do NOT use plain `--output-format json` (buffers one end-of-run blob, `claude.yaml:25-26`). | ✅ | 2026-07-21 |
| TASK-026 | Add a stream-event renderer in the dispatch/echo path (`runner.py` pump `201-211` → `_EchoSink` `orchestrate.py:551-572` → `frame.emit`): when a backend is in stream-json mode, parse the NDJSON events and (a) echo assistant **text deltas** live (never raw JSON), and (b) let `agents.extract_usage` (`agents.py:173-204`, already a last-JSON-line scan) read the final `{"type":"result", …, "usage":{…}, "total_cost_usd":…}` event. Roll sub-agent messages (carrying `parent_tool_use_id`) into the stage total; optionally show a sub-agent indicator. | ✅ | 2026-07-21 |
| TASK-027 | Persist tokens and cost (Decision 6): the chain to `progress.md` already exists (`agents.extract_usage` `agents.py:227-262` → `DispatchResult.tokens` `runner.py:363,371` → `StageResult.tokens` `runner.py:106,434` → `Reporter.stage_completed(tokens=)` `progress.py:260-269` → `Tokens` column `progress.py:133-149`). Extend `DispatchResult`/`StageResult` and the `progress.py` schema with an additive `cost` field, populate it from `total_cost_usd`, render a `Cost` column beside `Tokens`, and thread the same additive fields into the stage ledger entries (`cli/run.py:1022-1042,1105-1108`). | ✅ | 2026-07-21 |
| TASK-028 | Close the non-TTY / `--json` live gap: streaming is off when stdout is not a TTY or `--json` is set (`cli/run.py:492-494`). Keep that default (JSON/pipes stay clean), but (a) surface the persisted transcript path (`transcripts.py`, `.3powers/runs/<id>/…`, wired `cli/run.py:840,848,862`, `runner.py:332-348`) prominently at stage start/failure, and (b) offer an explicit opt-in to stream even off-TTY where sensible. | ✅ | 2026-07-21 |
| TASK-029 | Degradation (Decision 9): backends without stream-json declare nothing and behave exactly as today (regex-usage backends like `aider`/`codex`-text still populate tokens from their summary lines); provide a `--raw-events`/verbose escape that shows the underlying events. Parse defensively (only the assistant text and the final `result.usage`) and fall back to raw echo on unrecognized events; the persisted transcript is ground truth and unchanged. | ✅ | 2026-07-21 |
| TASK-030 | Update `docs/` to document the stream-json output posture, tokens **and** cost in `progress.md`, the surfaced transcript path, and the pre-v2.1.208 stream-json final-line truncation caveat. No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-031 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new `Cost` column header, transcript-path notice, and manifest/config comments (GUD-001). | ✅ | 2026-07-21 |
| TASK-032 | Tests: in `engine/tests/test_headless_run.py` and a new `engine/tests/test_stream_usage.py`, a fixture stream-json transcript yields live text deltas (no raw JSON echoed) **and** parsed `usage` + `total_cost_usd`; `progress.py` renders non-`—` `Tokens` **and** `Cost`; the persisted transcript equals the full fixture byte-for-byte; `--json`/piped output stays clean and byte-stable; a no-JSON backend still populates tokens via regex or shows `—`. | ✅ | 2026-07-21 |

### Phase 5

- GOAL-005: Track C — a bounded, code-only auto-fix loop that, on a red Verify in a `run` (auto mode) or on
  demand via `3pwr gate fix`, feeds the structured verdict back to the coder through the existing hand-back
  prompt, re-runs the gate suite, and loops until green or budget-exhausted; on give-up it prints the
  step-by-step human remediation summary. MUST land after Phase 1 (resolvable re-dispatch id) and Phase 4
  (per-attempt token/cost) per CON-004 (Decisions 2, 7, 8).

| Task     | Description                                                                                                                                                                                                                                                                                                                                    | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-033 | Run-path loop in `engine/src/threepowers/cli/run.py`: hook inside `run_verdict` (`cli/run.py:1133`) at the `outcome == "fail"` branch (`cli/run.py:1148`), **after** the deviation-proceed check (`cli/run.py:1152-1159`), gated on auto mode + `auto_fix` enabled. The loop: (1) reads the structured verdict from `box["verdict"]` (`cli/run.py:441`); (2) builds the fix prompt via `orchestrate.coder_handback(verdict)` (`orchestrate.py:804`), optionally scoping the dispatch to the failed gates' files; (3) dispatches the already-constructed `coder` backend (`cli/run.py:841`) as a fresh session (reusing `dispatch_once`/`run_stage` policy, `runner.py:401-478,636`); (4) re-invokes `_native_verdict` (`cli/run.py:390`), which records an honest signed verdict each pass (`cli/run.py:443-452`); (5) stops on `pass`, on budget exhaustion (default 3, from config), or on no-progress (same failing gates + no file changes → bail to summary). | ✅ | 2026-07-21 |
| TASK-034 | Standalone `3pwr gate fix` in `engine/src/threepowers/cli/gate.py`: a new subcommand (or `gate run --fix`) that runs the suite once and, on red, builds a coder backend from `roles.yaml` exactly as a run does (`runpreflight.resolve_coder_integration` + `roles.coder`), then runs the same loop. It refuses with an actionable message if no coder integration is configured (Decision 8). | ✅ | 2026-07-21 |
| TASK-035 | Hard safety invariants (enforced + tested): the loop MUST NOT record a deviation, call `_deviation_proceed_notices` (`cli/run.py:456`), edit `scan.yaml`/gate config, or mutate a `Verdict`. It may only dispatch the coder (which edits code) and re-run `gates.run_gates`. It runs before/independently of the deviation-proceed check and never invokes it (Decision 7, PAT-003). `gate_gaming` (`gaming.py`) remains the backstop; a genuine gaming signal ends the loop and routes to the human summary. | ✅ | 2026-07-21 |
| TASK-036 | Human summary on give-up: when the loop exits red, print the plan-035 remediation panels (`orchestrate.failure_panels`) plus a concise "what I tried / what's left for you" block — per gate, the attempts made, the residual findings, and the honest next steps (code fix, or — labelled last resort — a deviation/advisory the human must decide). | ✅ | 2026-07-21 |
| TASK-037 | Config: add `auto_fix` settings to `.3powers/config/` and the scaffold copy under `engine/src/threepowers/scaffold/config/` — enabled default per Decision 2 (on in `run` auto mode, off for standalone unless `gate fix`/`--fix`), `max_attempts: 3`, optional `scope_to_failed` toggle. Validate/load via `engine/src/threepowers/config.py`. | ✅ | 2026-07-21 |
| TASK-038 | "Build self-verifies" reconciliation: confirm the engine already runs the full suite at Verify immediately after `implement` (`orchestrate.py:49-50`) via the same `run_gates` as `3pwr gate run` (`cli/run.py:425`). Optionally (documented, advisory) make the per-phase coding gate a real in-process `run_gates` over the phase file scope at the tail of `_dispatch_phased` (`cli/run.py:749-758`) so a phase surfaces its own gate state before Verify — still advisory per the phased-execution contract, never a second blocking verdict. | ✅ | 2026-07-21 |
| TASK-039 | Update `docs/` to document the auto-fix loop, `3pwr gate fix` / `--fix`, the safety guarantees (code-only, never a deviation/advisory/verdict mutation, `gate_gaming` backstop), and the `auto_fix` config. No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-040 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new `gate fix` help, the "what I tried"/give-up block, and the `auto_fix` config comments (GUD-001). | ✅ | 2026-07-21 |
| TASK-041 | Tests: new `engine/tests/test_auto_fix.py` (reusing `SimulatedRunner` for a deterministic coder) — (1) a fixable red (missing test dropping `diff_coverage`) drives coder dispatch and reaches green within budget, recording N honest verdicts; (2) the loop writes **no** deviation/advisory entry (assert the ledger has none); (3) an unfixable red exits after the budget with the human summary and the normal gate-red exit code; (4) a coder that deletes an assertion is caught by `gate_gaming` and routed to the summary; (5) `gate fix` with no coder configured refuses actionably. | ✅ | 2026-07-21 |

### Phase 6

- GOAL-006: Track F — the implement agent authors the run's `changelog.md` as human/business prose
  (Added/Changed/Fixed, traced to requirements); the engine validates requirement coverage + OSS-readiness
  and places it, mirroring the `oracle.md` author-then-validate pattern; the top-level `CHANGELOG.md` is
  untouched (Decisions 3, 11, PAT-002).

| Task     | Description                                                                                                                                                                                                                                                                                                                             | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-042 | Extend the implement agent's completion contract in `.3powers/templates/agents/implement.agent.md` and the bundled copy `engine/src/threepowers/scaffold/templates/agents/implement.agent.md` to author a business-readable changelog section: for each requirement the run addressed, a plain-language "what changed and why it matters" entry, grouped Added/Changed/Fixed, written for a non-engineer reader — promoting the existing per-change what/why lines (`implement.agent.md:76-77`) into a first-class artifact. | ✅ | 2026-07-21 |
| TASK-043 | Replace the deterministic table body in `engine/src/threepowers/completion.py` `render_changelog` (`completion.py:302-366`) with the agent-authored prose, validated the way `oracle.md` is (`completion.write_record` oracle branch `completion.py:398-415`, `validate_oracle_spec` `completion.py:202-225`): the engine checks that every requirement the run addressed is covered by an entry (via `oracle.extract_criteria` `oracle.py:54-67`, reachable from `feature_dir` at `cli/run.py:994`), that no internal ids leak (OSS-readiness), and that the required sections exist — then writes it to `specs-src/<NNN>-<slug>/changelog.md`. On a validation miss, fail the step with an actionable message; never silently emit a bad changelog. | ✅ | 2026-07-21 |
| TASK-044 | Keep the requirement→files trace as a clearly-separated, additive machine-readable appendix section (or in `--json`) so nothing that consumes the old table loses data — but the changelog **body** is prose. | ✅ | 2026-07-21 |
| TASK-045 | Determinism trade (Decision 11): update `engine/tests/test_run_workspace.py:164-198` from byte-golden assertions to structural/coverage assertions (required sections present, every addressed run requirement covered, no leaked ids, top-level `CHANGELOG.md` untouched). The top-level hand-maintained `CHANGELOG.md` stays out of scope. | ✅ | 2026-07-21 |
| TASK-046 | Update `docs/` to document the business-readable changelog: agent authorship, engine validation (requirement coverage + OSS-readiness), placement at `specs-src/<NNN>-<slug>/changelog.md`, and the additive machine-readable appendix. No internal ids (GUD-001). | ✅ | 2026-07-21 |
| TASK-047 | Confirm `engine/tests/test_oss_readiness.py` stays green for the changelog scaffold prose and the implement-template instructions (GUD-001). | ✅ | 2026-07-21 |
| TASK-048 | Tests: the rewritten `engine/tests/test_run_workspace.py` (structural/coverage) plus a validation-miss case (an uncovered requirement or a leaked id) that fails the step; in `engine/tests/test_stage_agents.py` assert the implement template instructs authoring the business changelog. | ✅ | 2026-07-21 |

### Phase 7

- GOAL-007: Verification — prove all six tracks' acceptance criteria pass, the engine is green under its
  own toolchain and gates (including `gate_gaming` and the High-risk coverage floors), OSS-readiness holds,
  `--json`/ledger determinism is preserved (additive fields only), the TypeScript e2e sample runs green,
  and a live run demonstrates the end-to-end wins.

| Task     | Description                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-049 | Run `cd engine && uv run pytest` — all new and existing tests pass, including `test_run_identity.py`, `test_gate_pipeline.py`, `test_terminal_ux.py`, `test_agents.py`/`test_native_runner.py`, `test_stream_usage.py`, `test_auto_fix.py`, `test_run_workspace.py`, `test_stage_agents.py`, and the `--json` byte-stability regressions. | ✅ | 2026-07-21 |
| TASK-050 | Run `cd engine && uv run ruff check .` and `cd engine && uv run mypy src` — clean. | ✅ | 2026-07-21 |
| TASK-051 | Run `3pwr gate run --path engine` — the engine stays green under its own gates, including its own `gate_gaming` and the High-risk coverage floors (GUD-002). | ✅ | 2026-07-21 |
| TASK-052 | Confirm `engine/tests/test_oss_readiness.py` passes — no internal plan/spec/requirement ids in any new user-facing string across all six tracks (GUD-001). | ✅ | 2026-07-21 |
| TASK-053 | Confirm High-risk coverage ≥ 95% for `canonical`, `keys`, `ledger`, `verify` — the additive token/cost ledger fields (Track E) must not regress the trust-spine floor. | ✅ | 2026-07-21 |
| TASK-054 | Confirm `--json`/verdict byte-stability and ledger determinism are preserved (strictly-additive fields only) — the byte-stability tests and `test_terminal_ux.py` goldens are green (CON-001). | ✅ | 2026-07-21 |
| TASK-055 | Run `./e2e/run.sh typescript --check` — the deterministic no-agent path stays green. | ✅ | 2026-07-21 |
| TASK-056 | Live TypeScript run scenario: a `3pwr run` in auto mode that hits a fixable red Verify reaches green without human intervention (auto-fix); `progress.md` shows non-`—` `Tokens` **and** `Cost`; the printed `Resume:`/`Inspect:`/`re-dispatch:` commands carry a resolvable numeric id; and `specs-src/<NNN>-<slug>/changelog.md` reads as business prose covering every addressed requirement. | ⏳ Deferred | — |

## 3. Alternatives

- **ALT-001**: Rename the requirement-ID namespace `GSW-FR-002` → `002-FR-002` (Track A, Decision 1 Option
  B). Rejected: rewriting it invalidates every existing oracle seal (`bundle_hash` hashes the id) and every
  `Covers:` test reference, and makes namespace `002` visually ambiguous with requirement number `002`.
  Only the *surfaced* identifier is unified (CLI + output).
- **ALT-002**: Use plain `--output-format json` to capture tokens (Track E, Decision 5). Rejected: it
  buffers one end-of-run blob and destroys the live conversation; `stream-json` preserves live text deltas
  *and* carries the final `usage`/`total_cost_usd` the existing last-JSON-line parser already reads.
- **ALT-003**: Let the auto-fix loop reach green by recording a deviation, adding an advisory to
  `scan.yaml`, or weakening a check (Track C). Rejected (out of scope by design, SEC-001): the loop may
  only edit code and re-run gates; a bypass would collapse the trust model. `gate_gaming` is the backstop.
- **ALT-004**: Default-on auto-fix for a standalone `3pwr gate run` (Track C, Decision 2). Rejected: keeps
  a standalone `gate run` free of surprise model spend; the standalone path is explicit via `3pwr gate fix`
  / `--fix`.
- **ALT-005**: Have the engine author the changelog deterministically (keep the file-change table)
  (Track F, Decision 3). Rejected: a table is not a business account; the agent authors genuine prose and
  the engine validates coverage — reusing the proven `oracle.md` author-then-validate pattern with no extra
  dispatch.
- **ALT-006**: Persist tokens only, not cost (Track E, Decision 6). Rejected: cost is in the same `result`
  payload at no extra request and is the number a business reader actually wants.
- **ALT-007**: Key the subagent-model map by role rather than by stage (Track D, Decision 4). Rejected: the
  `planner`/`reviewer` roles are not yet wired into the run loop; keying by stage gives full per-stage
  control today without depending on that wiring.
- **ALT-008**: Execute Tracks B/D/E as parallel phases (as the source plan's ordering note suggests).
  Rejected here: `orchestrate.py`, `cli/run.py`, and `.3powers/agents/*.yaml` are each edited by multiple
  tracks, so parallel edits would collide; phases run sequentially (CON-005).

## 4. Dependencies

- **DEP-001**: The existing token→`progress.md` chain — `agents.extract_usage` (`agents.py:227-262`, JSON
  scan `173-204`) → `DispatchResult.tokens` (`runner.py:363,371`) → `StageResult.tokens`
  (`runner.py:106,434`) → `Reporter.stage_completed(tokens=)` (`progress.py:260-269`) → `Tokens` column
  (`progress.py:133-149`). Track E makes it fire and extends it with cost.
- **DEP-002**: `orchestrate.coder_handback` (`orchestrate.py:804-841`) + `_handback_block`
  (`orchestrate.py:965-977`) — the plan-035 hand-back prompt Track C reuses to drive the loop.
- **DEP-003**: `orchestrate.failure_panels` + the plan-035 remediation guidance — the give-up human summary
  Track C prints.
- **DEP-004**: The `oracle.md` author-then-validate-then-place pattern — `completion.write_record` oracle
  branch (`completion.py:398-415`), `validate_oracle_spec` (`completion.py:202-225`), and
  `oracle.extract_criteria` (`oracle.py:54-67`) — mirrored by Track F.
- **DEP-005**: The manifest-declared-flag mechanism in `agents.build_command` (`agents.py:86-127`, "never
  invents a flag" `108-111`) and the `usage_mode`/`usage_mode_args` fields (`agents.py:106-111`) — used by
  Tracks D and E.
- **DEP-006**: `runpreflight.resolve_coder_integration` + `roles.yaml` `roles.coder` — the coder backend
  `3pwr gate fix` builds, exactly as a run resolves it (Decision 8).
- **DEP-007**: The `models.yaml` catalog (`anthropic/claude-haiku-4-5`, `google/gemini-2.5-flash`) — Track
  D validates subagent-model values against it.
- **DEP-008**: The transcript machinery (`transcripts.py`, wired `cli/run.py:840,848,862`,
  `runner.py:332-348`) and the AUTOX full-output-on-disk contract — Track E surfaces the transcript path.
- **DEP-009**: `gate_gaming` (`gaming.py`) — the Track C backstop against a coder trying to weaken a check.
- **DEP-010**: `style.Styler` + `color_enabled` (`style.py:102-135`) — Track B routes panel bodies through
  it and relies on its central `--json`/`NO_COLOR`/non-TTY gating.
- **DEP-011**: `engine/tests/test_oss_readiness.py` — must pass for all new user-facing text.
- **DEP-012**: The `3pwr` CLI installed from `./engine` and the e2e harness (`./e2e/run.sh typescript
  --check`) for verification.

## 5. Files

- **FILE-001**: `engine/src/threepowers/orchestrate.py` — `_gate_red_summary`/`_handback_block` numeric id
  (Track A); `_render_panel`/`_panel_body_lines`/`_remediation_lines`/`_handback_block` coloring (Track B);
  reuses `coder_handback`/`failure_panels` (Track C); `_EchoSink` stream renderer (Track E). Shared —
  edited across four tracks, hence sequential phases.
- **FILE-002**: `engine/src/threepowers/cli/run.py` — id strings in output (Track A); the `run_verdict`
  auto-fix hook `~1133/1148` (Track C); the dispatch-closure subagent-model thread `~870` (Track D);
  token/cost threading, the streaming gap `492-494`, and ledger fields `1022-1042,1105-1108` (Track E);
  changelog placement at `~994` (Track F). Shared across five tracks.
- **FILE-003**: `engine/src/threepowers/cli/_common.py` — `_format_verdict` header `~273` (Track A);
  verdict header `263-286` PASS/FAIL color, `_compose` `140-161` + layout parse `110` (Track B).
- **FILE-004**: `engine/src/threepowers/cli/gate.py` — panel subject `206` + `--id` help `367-371`
  (Track A); the `gate fix` subcommand / `--fix` (Track C).
- **FILE-005**: `engine/src/threepowers/cli/oracle.py` — `key_help` `674-677` vocabulary alignment
  (Track A).
- **FILE-006**: `engine/src/threepowers/style.py` — `_RICH_STYLES` `33-43` + `Styler` helpers `166-200`
  guidance/border vocabulary; `color_enabled` `102-135` gating unchanged (Track B).
- **FILE-007**: `engine/src/threepowers/config.py` — `layout` consumption `218,222` (Track B),
  `subagent_models` validation (Track D), `auto_fix` config load (Track C).
- **FILE-008**: `.3powers/agents/claude.yaml` (+ `codex.yaml`) and their scaffold copies under
  `engine/src/threepowers/scaffold/` — subagent-model transport field (Track D); `usage_mode: stream-json`
  flipping the commented line at `claude.yaml:27` (Track E). Shared across Tracks D and E.
- **FILE-009**: `engine/src/threepowers/agents.py` — `build_command` `86-127` emits the subagent directive
  (Track D); `extract_usage` `173-204` reads the final result event, `usage_mode`/`usage_mode_args`
  `106-111` (Track E).
- **FILE-010**: `engine/src/threepowers/runner.py` — `CliAgentRunner.dispatch` `296-373` threads the
  subagent model (Track D); pump `201-211` stream parse, `DispatchResult`/`StageResult` cost field
  `106,363,371,434` (Track E); `dispatch_once`/`run_stage` reuse `401-478,636` (Track C).
- **FILE-011**: `engine/src/threepowers/progress.py` — `Cost` column beside `Tokens`, schema `133-149`,
  `stage_completed` `260-269` (Track E).
- **FILE-012**: `engine/src/threepowers/cli/bootstrap.py` — `config roles setup` `226-356` offers a
  per-stage subagent model (Track D).
- **FILE-013**: `.3powers/config/roles.yaml` (+ scaffold `engine/src/threepowers/scaffold/config/roles.yaml`) —
  the additive `subagent_models` stage map (Track D).
- **FILE-014**: `.3powers/config/` auto-fix settings (+ the scaffold copy under
  `engine/src/threepowers/scaffold/config/`) — `auto_fix` (enabled default, `max_attempts: 3`,
  `scope_to_failed`) (Track C).
- **FILE-015**: `engine/src/threepowers/completion.py` — `render_changelog` `302-366` replaced with
  validated prose; `write_record` oracle branch `398-415`, `validate_oracle_spec` `202-225` pattern
  reused (Track F).
- **FILE-016**: `engine/src/threepowers/oracle.py` — `extract_criteria` `54-67` reused for coverage
  validation (Track F); guardrail: `bundle_hash` `70-101` untouched (Track A).
- **FILE-017**: `.3powers/templates/agents/implement.agent.md` + bundled
  `engine/src/threepowers/scaffold/templates/agents/implement.agent.md` — the completion contract authors
  the business changelog; per-change what/why lines `76-77` (Track F).
- **FILE-018**: `docs/cli-reference.md` + the `docs/` gate/verdict, roles/config, and output references —
  every behavior change lands with a docs update in the same unit of work (all tracks).
- **FILE-019**: Tests under `engine/tests/` — `test_run_identity.py`, `test_gate_pipeline.py`,
  `test_terminal_ux.py`, `test_agents.py`, `test_native_runner.py`, `test_bootstrap*.py`,
  `test_headless_run.py`, new `test_stream_usage.py`, new `test_auto_fix.py`, `test_run_workspace.py`,
  `test_stage_agents.py`, `test_conformance*.py`, `test_oracle.py`, `test_oss_readiness.py`, and the
  `--json` byte-stability suites — new/extended.

## 6. Testing

- **TEST-001** (Track A): `engine/tests/test_run_identity.py` — every printed
  `Resume:`/`Inspect:`/`re-dispatch:` command contains the numeric `NNN` and resolves; no
  `--spec-id FEAT`/`--id FEAT` string is emitted; a rendered-output guard fails on a non-numeric
  `--spec-id`/`--id`. `test_conformance*.py`/`test_oracle.py` unchanged (namespace tracing + seal verify
  green). `--json` byte-stability preserved.
- **TEST-002** (Track B): `engine/tests/test_gate_pipeline.py` substring guidance survives (ANSI-wrapped)
  and the `coder_handback` golden (`457-491`) stays plain; `engine/tests/test_terminal_ux.py` goldens +
  SGR-byte asserts + the `--json` byte-stability test guard byte-identity off-TTY; a new `layout: compact`
  test asserts tighter spacing and a color-on test asserts guidance/deviation styles.
- **TEST-003** (Track D): `engine/tests/test_agents.py`/`test_native_runner.py` — `subagent_models[implement]`
  produces the expected `--agents`/subagent directive; unset adds nothing (byte-identical dispatch); an
  unknown model for a known integration is reported; a backend without the field no-ops.
  `test_bootstrap*.py` — setup offers the catalog cheap models.
- **TEST-004** (Track E): `engine/tests/test_headless_run.py` + new `engine/tests/test_stream_usage.py` — a
  fixture stream-json transcript yields live text deltas (no raw JSON echoed) **and** parsed
  `usage`+`total_cost_usd`; `progress.py` renders non-`—` `Tokens` and `Cost`; the persisted transcript
  equals the full fixture; `--json`/pipe stays clean and byte-stable; a no-JSON backend populates via regex
  or shows `—`.
- **TEST-005** (Track C): new `engine/tests/test_auto_fix.py` (using `SimulatedRunner`) — (1) a fixable red
  reaches green within budget recording N honest verdicts; (2) the loop writes **no** deviation/advisory
  entry; (3) an unfixable red exits after the budget with the human summary and the normal gate-red exit
  code; (4) an assertion-deleting coder is caught by `gate_gaming` and routed to the summary; (5)
  `gate fix` with no coder configured refuses actionably.
- **TEST-006** (Track F): `engine/tests/test_run_workspace.py:164-198` (rewritten) — structural/coverage
  assertions (required sections present, every addressed requirement covered, no leaked ids, top-level
  `CHANGELOG.md` untouched); a validation-miss (uncovered requirement or leaked id) fails the step.
  `engine/tests/test_stage_agents.py` — the implement template instructs authoring the business changelog.
- **TEST-007** (whole engine): `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (self-application incl. `gate_gaming` and High-risk coverage ≥ 95%),
  and `engine/tests/test_oss_readiness.py` green.
- **TEST-008** (e2e + live scenario): `./e2e/run.sh typescript --check` green; a live TypeScript run
  demonstrates auto-fix reaching green without human intervention, tokens/cost in `progress.md`, a
  resolvable numeric re-dispatch id, and a business-readable `changelog.md`.

## 7. Risks & Assumptions

- **RISK-001** (Track A): a stray print keeps emitting the front-matter prefix. *Mitigation:* the
  `test_run_identity.py` rendered-output guard fails on any non-numeric `--spec-id`/`--id`; sweep every call
  site listed in the source plan's "Why now" #1.
- **RISK-002** (Track C): a coder that never converges loops or burns tokens. *Mitigation:* a hard attempt
  budget (default 3), a no-progress bail (same failures + no file change), every attempt recorded, and cost
  visible via Track E.
- **RISK-003** (Track C): auto-fix masks a real problem via a silent green after weakening. *Mitigation:*
  the `gate_gaming` backstop; the loop cannot touch deviations/advisories/config; an honest verdict is
  recorded each pass; a no-deviation-written test asserts it.
- **RISK-004** (Track E): stream-json event-shape drift breaks the renderer. *Mitigation:* parse
  defensively (only assistant text + the final `result.usage`), fall back to raw echo on unrecognized
  events (Decision 9), keep the transcript as ground truth, and note the pre-v2.1.208 truncation caveat in
  docs.
- **RISK-005** (Track E): a live-output regression where users see JSON instead of prose. *Mitigation:* the
  renderer echoes only text deltas; a fixture test asserts no raw JSON reaches the echo sink; off-TTY
  behavior is unchanged.
- **RISK-006** (Tracks D/E): a backend without the subagent-model or JSON mechanism is silently expected but
  absent. *Mitigation:* manifest-declared, no-op-by-default; document per-backend support; unit tests for
  the no-op path.
- **RISK-007** (Track F): changelog non-determinism breaks consumers of the old table. *Mitigation:* keep
  the machine-readable trace as an additive appendix / `--json`; structural (not byte) tests; the validator
  guarantees requirement coverage.
- **RISK-008** (all tracks): `--json`/verdict byte drift. *Mitigation:* strictly-additive fields only; the
  byte-stability tests and terminal-UX goldens guard the payload and terminal bytes (CON-001).
- **RISK-009** (all tracks): file-scope contention on `orchestrate.py`, `cli/run.py`, and
  `.3powers/agents/*.yaml` across tracks. *Mitigation:* sequential phase execution (no `[P]`, CON-005),
  Phase 1 first, and re-anchoring to current source before each edit.
- **ASSUMPTION-001**: The file:line anchors carried from the source plan (`orchestrate.py`
  `137-182/365/378-379/551-572/804-841/844-858/861-887/890-924/965-977`; `cli/run.py`
  `257-270/390/425/441/443-452/456/492-494/611-622/749-758/840-870/994/1022-1042/1105-1108/1133/1148/1152-1159/2356`;
  `cli/_common.py` `110/140-161/263-286/273`; `cli/gate.py` `113/152/161/170/206/367-371`; `cli/oracle.py`
  `674-677`; `agents.py` `86-127/106-111/108-111/113-115/173-204/227-262`; `runner.py`
  `106/179-246/201-211/296-373/332-348/363/371/401-478/434/636`; `progress.py` `133-149/260-269`;
  `completion.py` `202-225/302-366/398-415`; `oracle.py` `54-67/70-101`; `config.py` `218,222`;
  `.3powers/agents/claude.yaml:25-27`; `implement.agent.md:76-77`) are accurate at implementation time; the
  python-engineer agent re-anchors to the current source before editing.
- **ASSUMPTION-002**: The four structural forks (Decisions 1–4) were confirmed by the maintainer on
  2026-07-21 and Decisions 5–11 are engineering defaults grounded in the code read; no open questions
  remain in the source plan.
- **ASSUMPTION-003**: `anthropic/claude-haiku-4-5` and `google/gemini-2.5-flash` are already in the
  `models.yaml` catalog, and Claude Code supports `--agents` JSON / `CLAUDE_CODE_SUBAGENT_MODEL` (Track D)
  and `--output-format stream-json` with `--verbose` (Track E).
- **ASSUMPTION-004**: The token→`progress.md` chain is wired end-to-end and only disabled by the commented
  `usage_mode: json` at `.3powers/agents/claude.yaml:27`; enabling stream-json makes the existing chain
  fire (no new chain to build).
- **ASSUMPTION-005**: The stage names the `subagent_models` map keys on (`discovery`, `specify`, `clarify`,
  `plan`, `tasks`, `oracle`, `implement`) match the run loop's step names at dispatch.

## 8. Related Specifications / Further Reading

- `plan/036-run-remediation-and-executive-ux.md` — the source plan this implementation plan derives from.
- `plan/035-actionable-verdict-remediation.md` and `plan/IMPLEMENTATION-006-fix-actionable-verdict-remediation.md`
  — the predecessor that made a red verdict legible (guidance, coder hand-back, deviation last resort);
  Track C builds the auto-fix loop on top of its hand-back prompt and failure panels.
- `AGENTS.md` — the mandatory intent → plan → implementation plan → implementation workflow, branch/commit
  discipline, python-engineer routing, and open-source-readiness rules.
- `CLAUDE.md` — architecture deep-dive (eight-stage lifecycle, three pillars, trust spine, adapter model).
- `docs/cli-reference.md` — the public `3pwr` command surface (gate runs, deviations, verify, run).
- `docs/STATUS.md` — the single source of truth for implementation status.
- `engine/tests/test_oss_readiness.py` — the enforced open-source-readiness rule for user-facing text.
- `e2e/README.md` — the notebook-project e2e harness and `./e2e/run.sh` usage.
