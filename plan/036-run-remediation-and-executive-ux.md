# Plan 036 — Actionable auto-remediation, numeric run identity, per-stage subagent models, native token/output fidelity, and a business-readable changelog

**Git branch:** `feat/036-run-remediation-and-executive-ux` (created and checked out for this plan; the
plan file is **not** auto-committed — the maintainer commits).

**Origin.** A live `3pwr gate run --id 002` on a Next.js/TypeScript sample surfaced a cluster of
experience gaps the maintainer wants closed as one coherent unit of work. Plan 035 already made a red
verdict *legible* (guidance, coder hand-back prompt, deviation-as-last-resort); this plan closes the
loop — it makes the harness **fix what it can**, **speak one identifier**, **cost less by default**,
**show every agent workstep**, **account for what it spent**, and **explain what shipped in business
terms**. Six independently valuable tracks, grounded in a full read of the engine this session.

The trigger observations, each verified in the code:

1. **The re-dispatch hint is broken, not just inconsistent.** The orchestrated `run` ledger is keyed by
   the numeric feature-folder id (`002`), but the verdict header and the `Resume:`/`Inspect:`/`re-dispatch:`
   hints print the `spec.md` front-matter prefix (`GSW`), which `workspace.resolve_feature_dir` **cannot
   resolve**. The command the tool tells the user to paste does not work.
2. **A red gate is a legible dead-end, but still a dead-end.** Plan 035 stopped — deliberately — at "a
   prompt the user pastes or a `--resume`; no model call, no auto re-dispatch". The maintainer now wants
   the harness to actually attempt the fix.
3. **Every stage runs on the coder's full-size model**, even research-shaped sub-work the coder is already
   told to fan out to sub-agents — with no way to send those sub-agents to a cheaper model.
4. **You can't always follow the agent live**, and
5. **token spend is never recorded** in `progress.md` — both rooted in the same disabled JSON-output
   posture.
6. **The generated `changelog.md` is a file-change table**, not a human/business account of what the run
   delivered.

## Tracks

- **Track A — One identifier: the numeric run id, everywhere.** Unify every CLI argument, help string,
  and output line on the numeric feature-folder id. Fix the broken `--spec-id GSW` / `--id GSW` hints so
  the printed resume/inspect/re-dispatch commands actually resolve. The alpha requirement-ID namespace
  (`GSW-FR-002`) stays untouched inside specs — it is load-bearing for conformance tracing and oracle
  seals, and a numeric namespace would collide visually with requirement numbers. (**Decision 1**.)
- **Track B — Richer, legible gate/verdict coloring.** Route the currently-monochrome panel bodies
  (findings, `↳ what it means / fix / last resort`, the deviation command, the coder hand-back block)
  through the existing `Styler`, add a small guidance/border color vocabulary, and wire the **inert
  `layout: compact`** knob. Human-output only; `--json` and verdict bytes stay byte-identical.
- **Track C — Auto-remediation: the harness tries to fix a red gate before it stops.** A bounded auto-fix
  loop that, on a red Verify (in a `run`) or on demand (`3pwr gate fix` after a standalone `gate run`),
  feeds the structured verdict back to the coder via the existing hand-back prompt, re-runs the gate
  suite, and repeats until green or budget-exhausted — **fixing code only, never a bypass, never an
  advisory or deviation**. When it cannot fix (a config/tooling problem, or a case needing human
  acceptance), it prints the same step-by-step human remediation summary plan 035 built. (**Decision 2**.)
- **Track D — Per-stage subagent model selection.** A new `subagent_models` map lets the maintainer pin a
  cheaper model per stage (e.g. Haiku for Discovery/Plan/Build research sub-agents) while the main stage
  agent keeps its role model. Delivered backend-neutrally: a declarative manifest field carries the
  transport (for Claude Code, `--agents` JSON / `CLAUDE_CODE_SUBAGENT_MODEL`). (**Decision 4**.)
- **Track E — Native output fidelity + real token accounting.** Adopt `--output-format stream-json` for
  the JSON-strategy backends and add a stream-event renderer that shows assistant text **live** (closing
  the "can't follow every workstep" gap) **and** reads the final `result` event's `usage` +
  `total_cost_usd`. The token→`progress.md` chain already exists end-to-end; this makes it fire, and
  persists per-stage / per-phase tokens **and cost** for durability. (**Decisions 5–6**.)
- **Track F — A business-readable changelog.** The implement agent authors the run's `changelog.md` as a
  human/business account (features / fixes / changes, traced to requirements), and the engine
  **validates requirement coverage** and places it — mirroring the existing agent-authored-then-validated
  `oracle.md` pattern. Replaces the file-change table. (**Decision 3**.)

**Ordering / dependencies.** Track A lands first (it corrects the identifier every other track prints).
Tracks B, D, E are independent and can land in parallel after A. Track C depends on A (a correct
re-dispatch id) and benefits from E (token/cost surfaced per attempt) — it lands after both. Track F is
independent of the others but shares the implement-stage completion contract with E's per-change capture;
it can land any time after A. No track weakens a gate, changes a verdict, or alters the ledger schema
beyond strictly-additive fields `verify` already tolerates.

### Explicitly out of scope

- **No renaming of the requirement-ID namespace.** `GSW-FR-002` stays `GSW-FR-002` (Decision 1, Option A).
  Rewriting it to `002-FR-002` would invalidate every existing oracle seal (`bundle_hash` hashes the id)
  and every `Covers:` test reference, and make namespace `002` ambiguous with requirement number `002`.
- **No new model call in the deterministic gate/verify path.** The auto-fix loop (Track C) dispatches the
  *coder* agent that a `run` already owns; the deterministic gate engine still never calls a model.
- **No auto-acceptance, ever.** The auto-fix loop may only edit code and re-run gates. It must never record
  a deviation, add an advisory to `scan.yaml`, weaken a check, or touch the deviation-proceed path.
- **No change to what a gate passes/fails, to the signed verdict, `3pwr verify`, exit codes, or `--json`
  byte-stability**, beyond strictly-additive fields.

---

## Decisions recorded

Four structural forks were **confirmed by the maintainer on 2026-07-21** via planning questions
(Decisions 1–4 below map to those answers); the rest are engineering defaults proposed here and grounded
in the code read this session. **No open questions remain — the plan is finalized.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Spec-id unification scope (Track A) | **CLI + output only** — user-confirmed. Every command/help/output uses the numeric feature-folder id; requirement-ID namespace (`GSW-FR-002`) unchanged. | Fixes the real, resolvable-command bug at low risk; avoids breaking oracle seals / conformance references and the `002`-vs-`002` visual clash. |
| 2 | Auto-fix trigger (Track C) | **Auto in `run`, opt-in for `gate run`** — user-confirmed. Default-on when `3pwr run` hits a red Verify in auto mode (bounded attempts); explicit `3pwr gate fix` for a standalone red `gate run`. | Delivers the "build self-verifies and fixes" intent inside the orchestrated flow while keeping a standalone `gate run` free of surprise model spend. |
| 3 | Changelog authorship (Track F) | **Implement agent authors, engine validates** — user-confirmed. Coder emits business prose in its completion contract; engine validates requirement coverage and places `changelog.md`. | Genuine business prose (an agent capability) with no extra dispatch, reusing the proven `oracle.md` author-then-validate pattern. |
| 4 | Subagent-model granularity (Track D) | **Per-stage model map** — user-confirmed (most granular option). A `subagent_models: { discovery: …, plan: …, implement: … }` map, keyed by stage. | Full per-stage control matches the ask ("choose the model for discovery, spec, build"); keying by **stage** sidesteps the fact that `planner`/`reviewer` roles are not yet wired into the run loop. |
| 5 | Native output vs token capture (Tracks E) | **`--output-format stream-json` + a stream-event renderer** (not plain `--output-format json`). My decision. | Plain JSON buffers one end-of-run blob and destroys the live conversation; `stream-json` preserves live text deltas *and* carries the final `usage`/`total_cost_usd`, which the existing last-JSON-line parser already reads. Only right answer. |
| 6 | Persist cost as well as tokens (Track E) | Persist per-stage/per-phase **tokens and `total_cost_usd`** to `progress.md` and the stage ledger entries (additive fields). My decision. | The maintainer asked for durable token accounting; cost is in the same result payload at no extra request and is the number a business reader actually wants. |
| 7 | Auto-fix budget + safety (Track C) | Default **3 attempts**, configurable; every attempt records an honest signed verdict; the loop runs **before/independently of** the deviation-proceed check and never invokes it. My decision. | Bounded to cap cost/looping; honest per-attempt verdicts are auditable and consistent with the append-only spine; separation from the deviation path preserves the trust model. |
| 8 | `3pwr gate fix` builds a coder backend from `roles.yaml` | The standalone fixer resolves the coder integration/model exactly as a `run` does (`runpreflight` + `roles.yaml`), and refuses with an actionable message if no coder is configured. My decision. | `gate run` today has no agent backend; the fixer needs one. Reusing the run's resolution keeps one source of truth. |
| 9 | Stream-json render degradation (Track E) | The stream renderer degrades to today's behavior when a backend has no `stream-json` support or when off-TTY/`--json`; the persisted transcript is unchanged; a `--raw-events`/verbose escape shows the underlying events. My decision. | Backend-neutrality (some CLIs have no JSON mode) and the AUTOX contract (full output always on disk) must both hold. |
| 10 | OSS-readiness of all new text | Every new help string, guidance line, changelog scaffold prose, and config comment obeys the open-source-readiness rule (no internal plan/spec/requirement ids; format teaching uses bare `FR-###`/`DEMO-FR-###`). Enforced by `engine/tests/test_oss_readiness.py`. | All six tracks add user-facing surfaces. |
| 11 | Changelog determinism trade (Track F) | Accept that agent-authored prose is **not byte-deterministic**; replace the byte-golden changelog assertions with **structural** ones (required sections present, every run requirement covered, no leaked ids). My decision. | Decision 3 chooses prose over a deterministic table; the existing `test_run_workspace.py` byte-determinism assertions must become coverage/structure assertions. |

---

## Why now

Each of these is observed in the code this session; file:line anchors are given so the implementation
plan can go straight to them.

1. **Broken re-dispatch identifier (Track A).** `run` ledger entries are keyed by the folder number
   (`cli/run.py:1838` `spec_id = feature_dir.name.split("-")[0]`), and resume/branch resolution matches on
   that number (`cli/run.py:257-270`, `gitflow.py:166-179`, `orchestrate.py:137-182`). But `verdict`
   entries are keyed by the front-matter prefix (`cli/gate.py:152`, `cli/run.py:450` pass
   `verdict.spec_id`), and the failure surfaces print *that* prefix: `orchestrate.py:378-379`
   (`Resume: … --spec-id GSW` / `Inspect: … --id GSW`), `orchestrate.py:975` (`re-dispatch: … --spec-id GSW`),
   `cli/_common.py:273` (the `spec=GSW` header), `cli/gate.py:206` (panel subject). `--id GSW` fails in
   `resolve_feature_dir` (`workspace.py:146-173`) and `--spec-id GSW` won't match the numeric `run`
   entries on resume. The three identifier conventions are decoupled by design
   (`conformance.py:51-60`, `oracle.py:335-344`), so unifying the *surfaced* id is safe as long as the
   requirement-ID namespace is left alone.
2. **A legible dead-end is still a dead-end (Track C).** The failure panel + `coder_handback`
   (`orchestrate.py:804-841`) + `_handback_block` (`orchestrate.py:965-977`) give the user a paste-ready
   prompt, but plan 035 Decision 8 and CON-002 deliberately declined the automated dispatch+loop. The
   structured verdict needed to drive a loop is already in hand (`verdict.Verdict` / `GateResult.findings`
   / `.details` / `Verdict.failures`, `verdict.py:47-103`), and the run's Verify closure already holds the
   coder backend, ledger, signer, and `feature_dir` (`cli/run.py:800-1185`, verdict at
   `cli/run.py:441`) — the loop is a bounded extension, not new machinery.
3. **Every stage pays for the coder's full model (Track D).** The model is resolved *only* from
   `roles.yaml` at dispatch (`cli/run.py:844,858` → `agents.build_command(..., model=)` →
   `agents.py:113-115`); `models.yaml` is a setup-time catalog. The build prompt already *mandates*
   sub-agent fan-out (`phases.py:402-406`, `implement.agent.md:32`), yet 3powers passes nothing to steer
   those sub-agents' model — no `--agents`, no frontmatter. The cheap targets are already catalogued
   (`anthropic/claude-haiku-4-5`, `google/gemini-2.5-flash` in `models.yaml`).
4. **Can't follow the agent live (Track E).** The tee/stream plumbing never truncates
   (`runner.py:179-246`, `_EchoSink` `orchestrate.py:551-572`), and the full per-attempt transcript is
   always on disk (`transcripts.py`, wired `cli/run.py:840,848,862`, `runner.py:332-348`). The gap is that
   live streaming is off entirely for non-TTY / `--json` (`cli/run.py:492-494`).
5. **Token accounting never fires (Track E).** The whole chain exists —
   `agents.extract_usage` (`agents.py:227-262`, JSON scan `173-204`) → `DispatchResult.tokens`
   (`runner.py:363,371`) → `StageResult.tokens` (`runner.py:106,434`) → `Reporter.stage_completed(tokens=)`
   (`progress.py:260-269`) → the `Tokens` column (`progress.py:133-149`) — but `usage_mode: json` is
   **commented out** in `.3powers/agents/claude.yaml:27`, so `--output-format json` is never added, so the
   CLI prints prose with no usage line, so `extract_usage` returns `None` and the cell renders `—`.
   Enabling plain JSON would fix tokens but kill the live stream (`claude.yaml:25-26` says exactly this);
   hence Decision 5's `stream-json`.
6. **The changelog is a file table (Track F).** `completion.render_changelog` (`completion.py:302-366`) is
   deterministic and emits a `| Requirement | Files changed | Summary |` table (`completion.py:335,349`) +
   a flat `## All changes` file list (`completion.py:362-363`). The inputs for prose already exist but are
   unused: the spec's requirement criteria (`oracle.extract_criteria`, reachable from `feature_dir` already
   at the call site `cli/run.py:994`) and the coder's per-change what/why lines
   (`implement.agent.md:76-77`, captured by `_implement_report` `cli/run.py:611-622`, today dumped
   verbatim at the bottom).

---

## Track A — One identifier: the numeric run id, everywhere

**Goal.** Everything the user types or reads for a run's identity is the numeric feature-folder id
(`002`). Every printed resume/inspect/re-dispatch command resolves. The requirement-ID namespace is
untouched.

**Changes.**

- **Record the number, not the prefix, on the surfaces that must resolve.** Where the verdict/oracle id is
  printed as a re-dispatch/inspect target, source the folder number (or full folder name where a folder
  path is needed) instead of `verdict.spec_id`:
  - `orchestrate.py:365,378-379` (`_gate_red_summary` `Resume:`/`Inspect:`) — print the run's numeric id;
    `--id` must receive `NNN`.
  - `orchestrate.py:971,975` (`_handback_block` `re-dispatch:`) — numeric id; drop the `<spec-id>` literal
    fallback in favor of the resolved number.
  - `cli/_common.py:273` (`_format_verdict` header) and `cli/gate.py:206` (panel subject) — show the
    numeric id as the primary identity (the front-matter prefix may still appear as a secondary,
    clearly-labelled "spec" field if useful, but never as the copy-paste `--spec-id`/`--id` value).
  - The verdict/oracle **ledger** entries may keep their existing keys (Track A does not rewrite the
    ledger), but the run must be able to correlate them to the numeric id; where a `gate run --id NNN`
    produced the verdict, thread `NNN` into the rendered output so the printed command matches what the
    user typed.
- **Reword the help that hides or misstates the numeric semantics:**
  - `cli/run.py:2356` — `--spec-id` help currently `"run id (default: RUN)"`; reword to state it is the
    numeric feature-folder id and how it is resolved.
  - `cli/oracle.py:674-677` — `key_help` documents the full `<NNN>-<slug>` name; align its user-facing
    wording with the numeric-id vocabulary (oracle keys may remain the full folder name internally, but
    the help must not present a second competing "spec-id" meaning).
  - `cli/gate.py:367-371` — `gate run --id` help is already numeric-correct; keep as the canonical wording
    and mirror it across the other `--spec-id` args (`status`, `abort`, `signoff`, `advance`, `deviation`,
    `observe`, `provenance`, …) so every help string says the same thing.
- **Consistency sweep:** every `--spec-id`/`--id` help string and every user-facing message that names the
  identifier uses one vocabulary ("the run's numeric id, e.g. `002`"). No behavior change to resolution —
  resume/branch already key off the number.

**Non-goals (guardrails).** Do **not** touch `conformance.extract_spec` (`conformance.py:63-81`), the
`_REQ_RE`/namespace logic (`conformance.py:30,51-60`), oracle `bundle_hash` (`oracle.py:70-101`), or
`characterize._spec_id_for` semantics beyond what is needed to keep them internally consistent. The
front-matter `**Spec ID**:` line stays as the requirement-ID namespace source.

**Acceptance.**

- After a red `3pwr gate run --id 002`, the printed `Resume:` / `Inspect:` / `re-dispatch:` commands all
  contain `002` (or the folder path where required) and each **executes without a resolution error**.
- `3pwr run --resume --spec-id 002` resumes the run; the old `--spec-id GSW` form is no longer emitted
  anywhere in output or help.
- `spec_conformance` still traces `GSW-FR-002` requirement references unchanged; existing oracle seals
  still verify (no `bundle_hash` change).
- `--json` payloads are unchanged except where a field already carried an id (no new required fields).

## Track B — Richer, legible gate/verdict coloring

**Goal.** The gate summary, per-gate finding panels, guidance lines, and the coder hand-back read as a
clear, colorized hierarchy on a TTY; identical bytes off-TTY / under `--json` / `NO_COLOR`.

**Changes (`engine/src/threepowers/style.py`, `engine/src/threepowers/orchestrate.py`).**

- **Color the panel body.** `_render_panel` (`orchestrate.py:890-924`) passes the body as one uncolored
  `Text` (`orchestrate.py:915`). Route `_panel_body_lines` (`orchestrate.py:861-887`) and
  `_remediation_lines` (`orchestrate.py:844-858`) through the shared `Styler`:
  - findings — default weight; `↳ what it means` — dim; `↳ fix` / `↳ auto-fix` — success/accent;
    `↳ last resort` + the `3pwr deviation …` command — warning; a `↳ waived by active deviation` line —
    warning/dim.
  - the hand-back header and `re-dispatch:` line in `_handback_block` (`orchestrate.py:965-977`) — a
    distinct accent so the copy-paste block is scannable.
- **Add a small named vocabulary** in `style.py` `_RICH_STYLES` (`style.py:33-43`) + `Styler` helpers
  (`style.py:166-200`) for the guidance/border roles, instead of the hardcoded `"dim"` border/title in
  `_render_panel` (`orchestrate.py:913-919`). The verdict header (`cli/_common.py:263-286`) gains
  status-colored `PASS`/`FAIL`.
- **Wire the inert `layout` knob.** `layout: compact` is parsed and validated (`config.py:218,222`,
  `_common.py:110`) but consumed nowhere. Honor it in `_compose` (`_common.py:140-161`) and panel spacing
  (tighter panels, drop blank separators) so a user can opt into a denser view.

**Safety.** All color is centrally gated by `color_enabled` (`style.py:102-135`), which forces off for
`--json`/`--yes`/`NO_COLOR`/non-TTY; `cmd_gate_run` never builds the styler/panels on the `--json` path
(`cli/gate.py:113,161,170`). The `coder_handback` **return value stays pre-color plain text** (its golden
test at `test_gate_pipeline.py:457-491` compares the full block); coloring is applied only when
`_handback_block` renders it.

**Acceptance.**

- On a TTY, a failed run's panels show colorized findings/guidance and a scannable hand-back block; the
  deviation last-resort reads as a warning, never as the primary action.
- `NO_COLOR=1`, a pipe, and `--json` each produce byte-identical output to before Track B (guarded by
  `test_terminal_ux.py` goldens + the `--json` byte-stability test).
- `layout: compact` measurably tightens the panel/section spacing; `layout: normal` is unchanged.

## Track C — Auto-remediation: the harness tries to fix a red gate

**Goal.** On a red Verify (in a `run`, auto mode) or on demand (`3pwr gate fix`), the harness feeds the
verdict back to the coder, re-runs the gate suite, and loops until green or budget-exhausted — **code
fixes only**. When it cannot get to green, it prints the plan-035 step-by-step remediation summary and
stops honestly.

**Changes.**

- **Run-path loop (`engine/src/threepowers/cli/run.py`).** Hook inside `run_verdict` (`cli/run.py:1133`)
  at the `outcome == "fail"` branch (`cli/run.py:1148`), **after** the deviation-proceed check
  (`cli/run.py:1152-1159`) and gated on auto mode + `auto_fix` enabled. The loop:
  1. reads the structured verdict from `box["verdict"]` (`cli/run.py:441`);
  2. builds the fix prompt via the existing `orchestrate.coder_handback(verdict)` (`orchestrate.py:804`),
     optionally scoping the dispatch to the failed gates' files;
  3. dispatches the already-constructed `coder` backend (`cli/run.py:841`) as a fresh session (reusing
     `dispatch_once`/`run_stage` policy, `runner.py:401-478,636`);
  4. re-invokes `_native_verdict` (`cli/run.py:390`), which **records an honest signed verdict each pass**
     (`cli/run.py:443-452`);
  5. stops on `pass`, on budget exhaustion (default **3**, from config), or when a pass makes no progress
     (same failing gates + no file changes → bail to summary).
- **Standalone `3pwr gate fix` (`engine/src/threepowers/cli/gate.py`).** A new subcommand (or
  `gate run --fix`) that runs the suite once, and on red builds a coder backend from `roles.yaml` exactly
  as the run does (`runpreflight.resolve_coder_integration` + `roles.coder`), then runs the same loop.
  Refuses with an actionable message if no coder integration is configured (**Decision 8**).
- **Hard safety invariants (enforced + tested).** The loop MUST NOT: record a deviation, call
  `_deviation_proceed_notices` (`cli/run.py:456`), edit `scan.yaml`/gate config, or mutate a `Verdict`.
  It may only dispatch the coder (which edits code) and re-run `gates.run_gates`. `gate_gaming`
  (`gaming.py`) remains the backstop against a coder that tries to weaken a check; a genuine gaming signal
  ends the loop and goes to the human summary.
- **Human summary on give-up.** When the loop exits red, print the plan-035 remediation panels
  (`orchestrate.failure_panels`) + a concise "what I tried / what's left for you" block: per-gate, the
  attempts made, the residual findings, and the honest next steps (code fix, or — labelled last resort —
  a deviation/advisory the human must decide). This is the "step-by-step how to fix" the maintainer
  asked for.
- **Config.** Add `auto_fix` settings to `.3powers/config/` (enabled default per Decision 2: on in `run`
  auto mode, off for standalone unless `gate fix`/`--fix`; `max_attempts: 3`; optional `scope_to_failed`
  toggle). Document in `docs/`.
- **"Build self-verifies" reconciliation.** The engine already runs the full suite at **Verify**,
  immediately after `implement` (`orchestrate.py:49-50`), via the same `run_gates` as `3pwr gate run`
  (`cli/run.py:425`). So the maintainer's "build should end in a gate run" is *already true* — what was
  missing is the self-correction. Track C supplies it. Optionally (documented, advisory), make the
  per-phase coding gate a real in-process `run_gates` over the phase file scope at the tail of
  `_dispatch_phased` (`cli/run.py:749-758`) so a phase surfaces its own gate state before Verify — still
  advisory per the phased-execution contract, never a second blocking verdict.

**Acceptance.**

- A `3pwr run` in auto mode that hits a fixable red Verify (e.g. a missing test dropping `diff_coverage`
  below threshold) dispatches the coder, re-runs gates, and proceeds green **without human intervention**,
  with every attempt's verdict recorded in the ledger and shown.
- The loop never produces a deviation or a `scan.yaml` edit; a test asserts no deviation/advisory entry is
  written during auto-fix.
- On an unfixable red (e.g. a real `dependency_scan` advisory with no upstream fix), the loop stops after
  the budget and prints the step-by-step human summary; exit code is the normal gate-red code.
- `3pwr gate fix` on a standalone red `gate run` runs the same loop; with no coder configured it refuses
  with an actionable message.
- A coder that tries to weaken a check is caught by `gate_gaming` and routed to the human summary, never
  silently accepted.

## Track D — Per-stage subagent model selection

**Goal.** The maintainer pins a cheaper model for the sub-agents a stage spawns (Discovery/Plan/Build
research fan-out), per stage, while the main stage agent keeps its role model — cutting cost with no loss
of the primary model's quality.

**Changes.**

- **Config: a per-stage map.** Add an additive, optional `subagent_models` block (Decision 4). Natural
  home is alongside the role bindings, keyed by **stage/step** so it is independent of the (partly
  unwired) role mapping:
  ```yaml
  # roles.yaml (additive; all optional)
  subagent_models:
    discovery: anthropic/claude-haiku-4-5
    plan:      anthropic/claude-haiku-4-5
    implement: anthropic/claude-haiku-4-5
    # any of: discovery, specify, clarify, plan, tasks, oracle, implement
  ```
  Values are validated against the `models.yaml` catalog for the resolved integration (Haiku/Flash already
  listed), with a free-form BYOK fallback (matching the existing model-pin tolerance).
- **Transport: a declarative manifest field (backend-neutral).** The engine "never invents a flag, it only
  appends what the manifest declares" (`agents.py:108-111`). Add a manifest field to
  `.3powers/agents/<name>.yaml` that expresses how a subagent model is delivered, and teach
  `agents.build_command` (`agents.py:86-127`) to emit it when a `subagent_models` entry applies to the
  stage being dispatched. For **Claude Code**, delivery is via `--agents` JSON with a `model` field per
  sub-agent definition, or the `CLAUDE_CODE_SUBAGENT_MODEL` env var (external research). Backends without a
  subagent-model mechanism simply declare nothing and the feature no-ops for them.
- **Resolution at dispatch.** In the dispatch closure (`cli/run.py:870` / `CliAgentRunner.dispatch`
  `runner.py:296-373`), look up `subagent_models[step]` and thread it into `build_command` alongside the
  main `model`. The main-session `--model` (from `roles.<role>.model`) is unchanged.
- **Setup + docs.** Extend the `3pwr config roles setup` flow (`cli/bootstrap.py:226-356`) to optionally
  offer a per-stage subagent model from the catalog (cheap models highlighted). Document the map and the
  cost intent in `docs/`.

**Acceptance.**

- With `subagent_models.implement: anthropic/claude-haiku-4-5`, a build dispatch to Claude Code carries
  the sub-agent model directive (verified by the assembled argv/`--agents` payload in a unit test); the
  main implement session still uses `roles.coder.model`.
- An unset `subagent_models` (today's default) changes nothing — no flag added, byte-identical dispatch.
- A backend manifest with no subagent-model field no-ops cleanly (no error, no flag).
- The catalog validation accepts `anthropic/claude-haiku-4-5` and a BYOK free-form value, and reports an
  unknown model for a known integration.

## Track E — Native output fidelity + real token accounting

**Goal.** The user follows every agent workstep live, and per-stage/per-phase **token and cost** land
durably in `progress.md` — using the headless CLI's native usage reporting.

**Changes.**

- **Adopt `stream-json` for JSON-strategy backends.** Enable native usage without killing the live stream:
  set the JSON-strategy manifests (`.3powers/agents/claude.yaml`, and `codex.yaml` where applicable) to
  request `--output-format stream-json` (with `--verbose` as the CLI requires) via the existing
  `usage_mode`/`usage_mode_args` mechanism (`agents.py:106-111`) — **not** plain `--output-format json`
  (which buffers one end-of-run blob, `claude.yaml:25-26`).
- **A stream-event renderer** in the dispatch/echo path (`runner.py` pump `201-211` → `_EchoSink`
  `orchestrate.py:551-572` → `frame.emit`). When a backend is in stream-json mode, parse the NDJSON events
  and (a) echo assistant **text deltas** live (so the conversation reads naturally, not as raw JSON), and
  (b) let `agents.extract_usage` (`agents.py:173-204`, already a last-JSON-line scan) read the final
  `{"type":"result", …, "usage":{…}, "total_cost_usd":…}` event. Sub-agent messages carry
  `parent_tool_use_id`; roll their usage into the stage total (external research) and optionally show a
  sub-agent indicator.
- **Persist tokens and cost (Decision 6).** The chain to `progress.md` already exists
  (`runner.py:363,371` → `StageResult.tokens` → `Reporter.stage_completed(tokens=)`
  `progress.py:260-269` → `Tokens` column `progress.py:133-149`). Extend `DispatchResult`/`StageResult`
  and the `progress.py` schema with a `cost` field (additive), populate from `total_cost_usd`, and render
  a `Cost` column beside `Tokens`. Thread the same additive fields into the stage ledger entries
  (`cli/run.py:1022-1042,1105-1108`).
- **Close the non-TTY / `--json` live gap.** Streaming is off when stdout is not a TTY or `--json` is set
  (`cli/run.py:492-494`). Keep that default (JSON/pipes must stay clean), but (a) surface the persisted
  transcript path (`transcripts.py`, `.3powers/runs/<id>/…`) prominently at stage start/failure so the
  user always knows where the full output is, and (b) offer an explicit opt-in to stream even off-TTY
  where sensible.
- **Degradation + caveats (Decision 9).** Backends without stream-json declare nothing and behave exactly
  as today (regex-usage backends like `aider`/`codex`-text still populate tokens from their summary lines).
  Note the **pre-v2.1.208** `stream-json` final-line truncation caveat (external research) in docs; the
  persisted transcript is unaffected regardless.

**Acceptance.**

- A live `3pwr run` on a TTY shows the agent's text as it works (unchanged readability) **and**
  `progress.md` shows non-`—` `Tokens` **and** `Cost` for each completed stage/phase.
- The persisted per-attempt transcript still contains the full output (AUTOX contract), byte-for-byte
  independent of the live view.
- `--json` / piped output remains clean (no interleaved event noise) and byte-stable; the transcript path
  is surfaced so output is followable after the fact.
- A backend with no JSON mode runs exactly as before (no regression, tokens `—` if it prints none).

## Track F — A business-readable changelog

**Goal.** `changelog.md` reads as a human/business account of what the run delivered — features, fixes,
notable changes — traced to requirements, not a file-change table.

**Changes.**

- **Author it in the implement stage (Decision 3).** Extend the implement agent's completion contract
  (`.3powers/templates/agents/implement.agent.md`, and the bundled copy
  `engine/src/threepowers/scaffold/templates/agents/implement.agent.md`) to author a business-readable
  changelog section: for each requirement the run addressed, a plain-language "what changed and why it
  matters" entry, grouped (Added / Changed / Fixed), written for a non-engineer reader. The agent already
  produces per-change what/why lines (`implement.agent.md:76-77`); this promotes them into a first-class,
  reader-facing artifact.
- **Engine validates + places it (mirror `oracle.md`).** Replace the deterministic table body in
  `completion.render_changelog` (`completion.py:302-366`) with the agent-authored prose, validated the way
  `oracle.md` is (`completion.write_record` oracle branch `completion.py:398-415`,
  `validate_oracle_spec` `completion.py:202-225`): the engine checks that **every requirement the run
  addressed is covered** by an entry (using `oracle.extract_criteria` `oracle.py:54-67`, reachable from
  `feature_dir` at `cli/run.py:994`), that no internal ids leak (OSS-readiness), and that the required
  sections exist — then writes it to `specs-src/<NNN>-<slug>/changelog.md`. On a validation miss, fail the
  step with an actionable message (same posture as the oracle validator), never silently emit a bad
  changelog.
- **Keep a machine-readable appendix (optional, additive).** Retain the requirement→files trace as a
  clearly-separated appendix section (or in `--json`) for tooling, so nothing that consumes the old table
  loses data — but the **body** is prose.
- **Determinism trade (Decision 11).** Update `test_run_workspace.py:164-198` from byte-golden assertions
  to structural/coverage assertions (sections present, every run requirement covered, no leaked ids,
  top-level `CHANGELOG.md` untouched). The top-level hand-maintained `CHANGELOG.md` stays out of scope.

**Acceptance.**

- After a run, `specs-src/<NNN>-<slug>/changelog.md` reads as business prose (grouped Added/Changed/Fixed
  entries in plain language), with every addressed requirement represented and no file-path table as the
  body.
- The engine rejects a changelog that omits an addressed requirement or leaks an internal id, with an
  actionable message.
- The top-level `CHANGELOG.md` is untouched; the machine-readable trace remains available as an appendix
  or in `--json`.

---

## Cross-cutting requirements & constraints

- **REQ-A**: Every CLI arg, help string, and output line names the run by its numeric id; every printed
  resume/inspect/re-dispatch command resolves. The requirement-ID namespace (`GSW-FR-002`) and oracle
  seals are unchanged.
- **REQ-B**: Panel bodies, guidance, and the hand-back render colorized on a TTY and byte-identical
  off-TTY/`--json`/`NO_COLOR`; `layout: compact` is honored.
- **REQ-C**: The auto-fix loop only edits code and re-runs gates; it never records a deviation/advisory,
  never weakens a check, never mutates a verdict, and always records an honest signed verdict per attempt.
  On give-up it prints the step-by-step human summary.
- **REQ-D**: A per-stage `subagent_models` map steers sub-agent models backend-neutrally via a manifest
  field; unset = no change; unknown model for a known integration is reported.
- **REQ-E**: Live agent output is followable (stream-json text deltas on TTY), the full transcript is
  always on disk, and per-stage/per-phase tokens **and** cost persist to `progress.md`.
- **REQ-F**: `changelog.md` is agent-authored business prose, engine-validated for requirement coverage
  and OSS-readiness; the top-level `CHANGELOG.md` is untouched.
- **SEC-001**: No new escape hatch weakens a gate. The auto-fix loop cannot produce a bypass; `gate_gaming`
  remains the backstop; deviations/advisories stay human-only and auditable.
- **CON-001**: The deterministic verdict, signed ledger, `3pwr verify`, exit codes, and `--json`
  byte-stability are unchanged except for strictly-additive fields `verify` already tolerates (token/cost,
  changelog appendix).
- **CON-002**: The deterministic gate engine adds no model call. Track C dispatches the *coder* the run
  already owns; Track F prose is authored by the implement agent that already runs.
- **CON-003**: Backend-neutrality holds — Tracks D and E no-op cleanly on backends lacking the relevant
  mechanism; the engine only emits manifest-declared flags.
- **GUD-001 (OSS readiness)**: All new user-facing strings obey `engine/tests/test_oss_readiness.py`.
- **GUD-002 (self-application)**: The engine stays green under its own gates (ruff/mypy/pytest and
  `3pwr gate run --path engine`, incl. `gate_gaming` and the High-risk coverage floors).

## Testing strategy

- **Track A**: `test_run_identity.py` (extend) — a fake spec with `**Spec ID**: FEAT` and folder `NNN-…`
  asserts every printed resume/inspect/re-dispatch command contains `NNN` and resolves; no `--spec-id
  FEAT`/`--id FEAT` string is emitted. `test_conformance*.py` / `test_oracle.py` — unchanged behavior
  (namespace tracing + seal verify still green), proving the requirement-ID namespace is untouched.
- **Track B**: `test_gate_pipeline.py` — substring guidance assertions survive (text unchanged, wrapped in
  ANSI); the `coder_handback` golden (`457-491`) stays plain (colored only at render). `test_terminal_ux.py`
  goldens + SGR-byte asserts + the `--json` byte-stability test guard byte-identity off-TTY. New: a
  `layout: compact` test asserts tighter spacing; a color-on test asserts guidance/deviation lines carry
  the expected styles.
- **Track C**: new `test_auto_fix.py` — (1) a fixable red (missing test) drives coder dispatch and reaches
  green within budget, recording N honest verdicts; (2) the loop writes **no** deviation/advisory entry
  (assert ledger has none); (3) an unfixable red exits after budget with the human summary and the normal
  gate-red exit code; (4) a coder that deletes an assertion is caught by `gate_gaming` and routed to the
  summary; (5) `gate fix` with no coder configured refuses actionably. Reuse `SimulatedRunner` for a
  deterministic coder.
- **Track D**: `test_agents.py` / `test_native_runner.py` — `subagent_models[implement]` produces the
  expected `--agents`/subagent directive in the assembled argv; unset adds nothing; unknown-model
  validation; backend without the field no-ops. `test_bootstrap*.py` — setup flow offers the catalog cheap
  models.
- **Track E**: `test_headless_run.py` / new `test_stream_usage.py` — a fixture stream-json transcript
  yields live text deltas (no raw JSON echoed) **and** parsed `usage`+`total_cost_usd`; `progress.py`
  renders non-`—` Tokens and Cost; the persisted transcript equals the full fixture; `--json`/pipe stays
  clean and byte-stable; a no-JSON backend still populates via regex or shows `—`.
- **Track F**: `test_run_workspace.py:164-198` (rewrite) — structural/coverage assertions (sections
  present, every addressed requirement covered, no leaked ids, top-level `CHANGELOG.md` untouched); a
  validation-miss (uncovered requirement / leaked id) fails the step. `test_stage_agents.py` — the
  implement template instructs authoring the business changelog.
- **Whole engine**: `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (self-application, incl. `gate_gaming` and High-risk coverage ≥ 95%
  on trust-spine modules).

## Risks & mitigations

- **Identifier surfaces missed (Track A)** — a stray print keeps emitting the prefix. *Mitigation:* a test
  that greps rendered run/gate output for a non-numeric `--spec-id`/`--id` argument and fails; sweep all
  call sites listed in "Why now" #1.
- **Auto-fix loops or burns tokens (Track C)** — a coder that never converges. *Mitigation:* hard attempt
  budget (default 3), no-progress bail (same failures + no file change), every attempt recorded; cost is
  visible via Track E. All bounded and configurable.
- **Auto-fix masks a real problem (Track C)** — silent green after weakening. *Mitigation:* `gate_gaming`
  backstop; the loop cannot touch deviations/advisories/config; honest verdict recorded each pass; a
  no-deviation-written test.
- **stream-json renderer complexity / event-shape drift (Track E)** — CLI event schema changes.
  *Mitigation:* parse defensively (only the assistant text and the final `result.usage`), fall back to raw
  echo on unrecognized events (Decision 9), and keep the transcript as ground truth. Note the pre-v2.1.208
  truncation caveat in docs.
- **Live output regression under stream-json (Track E)** — users see JSON instead of prose. *Mitigation:*
  the renderer echoes only text deltas; a fixture test asserts no raw JSON reaches the echo sink; off-TTY
  behavior unchanged.
- **Backend without subagent-model or JSON support (Tracks D/E)** — feature silently expected but absent.
  *Mitigation:* manifest-declared, no-op-by-default; document per-backend support; unit tests for the
  no-op path.
- **Changelog non-determinism breaks tooling (Track F)** — consumers of the old table. *Mitigation:* keep
  the machine-readable trace as an additive appendix / `--json`; structural (not byte) tests; validator
  guarantees requirement coverage.
- **`--json` / verdict byte drift (all tracks)** — additive fields only; the byte-stability tests and
  TRIX goldens guard the payload and terminal bytes.

## Definition of done

- All six tracks' acceptance criteria pass; the engine is green under ruff/mypy/pytest and its own
  `3pwr gate run --path engine` (including `gate_gaming` and High-risk coverage floors).
- `docs/` updated in the same unit of work: the CLI reference and gate/verdict guide reflect the numeric
  id everywhere, the auto-fix loop + `3pwr gate fix` and its safety guarantees, the `subagent_models` map,
  the stream-json output posture + token/cost in `progress.md` (and the transcript path), and the
  business-readable changelog. (Per AGENTS.md, a behavior change without a docs update is incomplete.)
- No internal ids leak into any user-facing string (OSS-readiness test green).
- e2e: `./e2e/run.sh typescript --check` stays green; a live TypeScript run demonstrates auto-fix reaching
  green, tokens/cost in `progress.md`, a resolvable numeric re-dispatch id, and a business-readable
  changelog.

---

## Open questions

None — the four structural forks were resolved by the maintainer on 2026-07-21 (Decisions 1–4); the rest
are engineering defaults grounded in the code read this session.

## Suggested handover

When you're ready, the next step is the **implementation-plan agent**, which turns this plan into
`plan/IMPLEMENTATION-007-feature-run-remediation-and-executive-ux.md` (phased, file-scoped tasks). Per
AGENTS.md the handover is explicit — say the word and I'll dispatch it. All Python changes under `engine/`
then go through the python-engineer agent. Suggested phase order: A (identity) → B/D/E (parallel,
disjoint scopes) → C (auto-fix, depends on A + benefits from E) → F (changelog) → a dedicated Verification
phase.
