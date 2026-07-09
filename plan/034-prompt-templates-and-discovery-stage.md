# Plan 034 — One source of truth for agent prompts, and wire the Discovery stage

**Git branch:** `feat/034-prompt-templates-and-discovery` — **created from `main`** (main was clean at
authoring). This plan file is committed on that branch.

**Covers two coupled core tracks plus two user-requested additions, delivered on one branch:**

- **Track A — Externalize every inline headless-agent prompt into editable markdown templates.** One
  source of truth: the `*.agent.md` templates lead, the inline Python prompt string literals are
  deleted, and the four prompts that have no template today (`_PREAMBLE`, `_GENERIC`, `_COMMIT_NOTE`,
  the steering revise block) get new bundled templates. After Track A there are **zero inline
  dispatched-prompt string literals** in the engine.
- **Track B — Wire the Discovery stage into the `3pwr run` executive loop.** Discovery is the first
  named lifecycle stage but is never dispatched — it's a cosmetic passthrough that jumps straight to
  Spec. Track B makes Discovery run as a real first dispatched stage that produces a discovery note
  and feeds it to Specify as prior context.
- **Track C — One fact per line in the `3pwr init` readiness summary.** The init output packs four
  facts onto one `·`-joined line; expand it to one fact per line for readability. (User-requested.)
- **Track D — Real per-stage token accounting across every headless backend.** `progress.md` renders
  `—` for tokens on every stage even though the backend (Copilot, observed) prints a usage summary,
  because most manifests declare no usage-extraction hint and the extractor can't parse abbreviated or
  broken-down counts. Track D captures the **real consumed (non-cached) tokens** — normalized across
  Claude, Copilot, Codex, aider, opencode — and gets them into `progress.md`, the ledger, and
  `--json`. (User-requested; extends plan 033's token-accounting work.)

A and B are tightly coupled and lead: Discovery's prompt must come from the `discovery.agent.md`
template (never a throwaway inline body), which only works cleanly once Track A makes the **bundled**
template the built-in default. **Track A lands first; Track B builds on it.** C and D are independent,
smaller, and can land in any order relative to A/B.

The invariants that bound every track: **prompt assembly stays deterministic** (same inputs → the
same prompt bytes); the deterministic verdict, the signed ledger's verification, exit codes, and
`--json` byte-stability are untouched except where a payload gains a strictly *additive* field that
`3pwr verify` already tolerates; **token accounting is strictly advisory and never enters the
verdict**; **no model call is ever added to the engine**; and everything stays backend-neutral
(identical assembled prompts for Claude, Codex, Copilot, Gemini).

---

## Decisions recorded

Three were **confirmed by the user on 2026-07-08** via the planning questions; the rest are
engineering defaults proposed here, several delegated to the plan by the intents ("you decide" / "the
plan picks one"). **No open questions remain — the plan is finalized.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Plan structure | **One combined plan — core tracks A→B (externalization first), plus user-requested C & D** — user-confirmed structure. | A and B are coupled (Discovery's prompt resolves through Track A's bundled-default loader); doing A first avoids a throwaway inline discovery body. C (init line) and D (tokens) were added at user request and are independent. Delivered as sequential units on one branch — **no pull requests**. |
| 2 | Discovery gate ("only if needed") | **Work-kind gate + override flag** — user-confirmed. Skip Discovery for `defect`/`docs`/`chore`/`refactor` and brownfield Stage Zero; run it for `feature`/`design`. `--discovery`/`--no-discovery` overrides either way. | Reuses the existing deterministic `workkind.classify` (no model call, no new heuristic); work-kind-shaped like the gate suite (plan 015); human-overridable. |
| 3 | Discovery prompt source | **The `discovery.agent.md` template** (via Track A's loader), never an inline `_STAGE_PROMPTS` body — user-confirmed (intent 1 Q1). | Consistent with Track A's single-source rule; the complete template already ships. |
| 4 | Discovery as a human gate? | **No** — an automatic `action` step in `auto` mode; no new mandatory gate — user-confirmed (intent 1 Q2 default). | Discovery frames the problem; the existing spec-approval gate remains the first human checkpoint. |
| 5 | Discovery work-kind / tier signal | **Advisory prose in the note only.** The engine does **not** consume the note's suggested kind/tier into the deterministic tier logic. My decision (intent 1 Q4 "you decide"). | Preserves determinism; the note "introduces no requirement ids" and "is not itself the spec" (per `discovery.agent.md`). `workkind.classify` stays the single tier signal. |
| 6 | Substitution mechanism | **`string.Template` (stdlib), `$NAME`-delimited, `safe_substitute` over a fixed closed vocabulary** — every defined variable always supplied (empty string when absent); a literal `$` is written `$$`; an unknown `$X` is left verbatim (a test catches it). My decision (intent 2 decision 3 delegated). | No new runtime dependency (runtime deps stay `cryptography` + `PyYAML`); `$`-delimited is safe against the literal `{}`/braces common in prompt prose; `safe_substitute` **never raises mid-run**, and pre-seeding the vocabulary makes an unfilled variable render empty rather than leaking a placeholder. |
| 7 | Non-agent template location | **New bundled fragments `preamble.agent.md`, `generic.agent.md`, `commit-note.agent.md`, `revise.agent.md`** under the existing `scaffold/templates/agents/`, each with YAML front-matter, seeded like the stage templates. My decision (intent 2 decisions 5–6). | Reuses one loader, one seeding path, one front-matter-stripping rule; `role: fragment` in the front-matter distinguishes them from dispatched stage templates so the stage-template test set is unaffected. |
| 8 | Loader precedence | **repo-local `.3powers/templates/agents/<name>` → bundled package default → generic fragment.** My decision (intent 2 decision 5). | The bundled template is the built-in default so **unseeded** repos — including the engine's own gate run — always get full prompts; a hand-edited repo-local file still wins. |
| 9 | Context-block framing | **INTENT / APPROVED SPEC / PRIOR CONTEXT / FILE SCOPE stay engine-framed trailing blocks** with the omit-if-empty rule; only **destination** placeholders (`$FEATURE_FOLDER`, `$ORACLE_DESTINATION`) and body-local values (`$STEP`, `$GATE`, `$ARTIFACT`, `$FEEDBACK`) become template variables. My decision (intent 2 decision 4). | Those four blocks carry *real* threaded values today (never hardcoded placeholders), and their deterministic omit-if-empty behavior is worth preserving; decision 4's target — hardcoded placeholder *destination* prose in bodies — becomes variables. |
| 10 | Init readiness layout (Track C) | **Split the `·`-joined summary line into one fact per line** (`language`, `adapter`, `default tier`, `autonomous default`); keep homogeneous comma-lists (agent backends) as single-line lists; the `--json` payload is untouched. My decision (user asked for "each in a new line"). | The only multi-fact line is the `·`-joined one; short filename lists read fine inline and the `--json` report must stay byte-stable for scripted callers. |
| 11 | Token metric (Track D) | **Real consumed = non-cached input + output**, one advisory integer per stage/phase, **normalized across every backend** — user-confirmed ("the real consumed tokens not the cached ones … must work for all the headless CLIs"). Each backend maps its own fields to this metric. | Cached/context-read tokens are cheap and not what a user means by "consumed for this task"; a single normalized number is comparable across Claude/Copilot/Codex/aider/opencode. |
| 12 | Token capture mode (Track D) | **Prefer each CLI's default output + a parser that reads its native usage report; keep the live conversation text UX by default.** Where a CLI exposes usage *only* in a JSON/structured mode that would replace the live text stream (notably Claude `-p`), the JSON-mode hint is provided but **opt-in per manifest**, defaulting off so the streamed conversation stays readable; that backend reads "unknown" until opted in. My decision (intent delegated). | The user's backend (Copilot) and most others print usage in default text; forcing JSON output everywhere would turn the live view into machine JSON. Getting Claude's usage requires JSON mode, so it is offered but not forced. |

---

## Why now

1. **Two sources of truth for every prompt.** The engine ships `*.agent.md` templates **and** carries
   inline `_STAGE_PROMPTS` bodies that duplicate — and have drifted from — them
   (`prompts.py:37-101`). A prompt is just text, yet changing one means editing Python and re-running
   gates. The engine's *own* repo is already seeded (`.3powers/templates/agents/` present), so it runs
   off the templates while the inline bodies sit as a stale, unexercised fallback — the worst of both.
2. **Unseeded repos silently get the terse fallback.** `stage_template_body` only reads the repo-local
   seeded copy; a repo that never ran `3pwr init` (or a fresh checkout of a governed repo) falls back
   to the inline bodies, which are markedly terser than the shipped templates. There is no built-in
   bundled default.
3. **Discovery is advertised but never runs.** `STAGES` leads with `"Discovery"`
   (`lifecycle.py:14`), a complete `discovery.agent.md` ships and is installed, and `"discovery"` is
   first in `TEMPLATE_STEPS` (`prompts.py:124`) — but `LIFECYCLE_STEPS` starts at `specify`
   (`orchestrate.py:40`), so no discovery agent is ever dispatched. The tracker inits its reached
   stage to `"Discovery"` (`orchestrate.py:471`) only for the first real event to advance it to
   `Spec`. It is a wired-up-but-not-connected feature.
4. **The coupling makes now the moment.** Wiring Discovery *correctly* wants its prompt to come from
   the template, which wants the bundled-default loader — exactly what Track A delivers. Doing A then B
   in one pass avoids a discovery body that Track A would immediately delete.

---

## What's true today (grounded — the starting point every track builds on)

| Area | Current reality (evidence) |
|---|---|
| Inline prompt literals | `_PREAMBLE` (`prompts.py:30-34`), `_STAGE_PROMPTS` for `specify/clarify/plan/tasks/oracle/implement` (`prompts.py:37-101`), `_GENERIC` (`prompts.py:103`), `_COMMIT_NOTE` (`prompts.py:116-119`), and `steering.revise_context`'s inline `"REVISION REQUESTED …"` string (`steering.py:133-143`). `characterize.py:104` writes requirement text to an artifact — **not** a dispatch prompt; out of scope. |
| Template loader | `template_name`/`template_path`/`template_body`/`stage_template_body` read `.3powers/templates/agents/<step>.agent.md` (tasks → `implementation-plan.agent.md` via `_TEMPLATE_NAMES`), strip front-matter, OSError-safe `""` (`prompts.py:141-179`). `resolve_body = stage_template_body(...) or stage_prompt_body(...)` (`prompts.py:187-192`). **No bundled-default read** — repo-local only. |
| Assembly | `assemble(step, *, intent, spec_text, context, file_scope, body)` concatenates `_PREAMBLE`, the body, an optional `_COMMIT_NOTE`, then omit-if-empty `INTENT:` / `APPROVED SPEC:` / `PRIOR CONTEXT:` / `FILE SCOPE:` blocks (`prompts.py:195-224`). **No variable substitution.** |
| Dispatch call sites | Two: `CliAgentRunner.dispatch` (`runner.py:294-367`, `assemble(..., body=stage_template_body(...))`) and `HostedAgentRunner.dispatch` (`hosted.py:138-165`, identical shape). Both → `agents.build_command` (`agents.py:75`). |
| Bundled templates | 9 files under `scaffold/templates/agents/`: `discovery, specify, clarify, plan, implementation-plan, oracle, implement, review, characterize` — each with `name/description/stage/role/artifact` front-matter + a rich body (`scaffold.py:147-168` seeds them non-clobbering). |
| Placeholder destinations in bodies | Bodies say "the destination the engine has given … default `specs-src/<feature>/spec.md`" (specify.agent.md:65-68), the same for plan/discovery, and oracle names `tests/oracle/<NNN>-<slug>/` (oracle.agent.md:57-59). The **real** destination is injected separately as an engine-built context block: `_feature_folder_context` and `_oracle_destination_context` (`cli/run.py:731-770`) appended to `ctx_parts` → the PRIOR CONTEXT block (`cli/run.py:898-911`). |
| Lifecycle steps | `LIFECYCLE_STEPS` starts at `("specify","action","Spec")` — **no `discovery` entry** (`orchestrate.py:40-53`). `NativeRunner._walk` (`runner.py:573-620`) and `SimulatedRunner._walk` (`orchestrate.py:266-279`) walk the same list; only `kind=="action"` dispatches. |
| Discovery contract/artifact | No `discovery` entry in `STAGE_ARTIFACTS` (`artifacts.py:87-129`); not in `workspace.PRODUCING_STEPS` / `_STEP_FILENAMES` (`workspace.py:44-54`); not in `_STAGE_PROMPTS` or `COMMIT_NOTE_STEPS` (`prompts.py`). `SpecState.stage` defaults to `"Spec"` (`lifecycle.py:36`). |
| Feature-folder timing | A live run allocates `specs-src/<NNN>-<slug>/` **on disk** (`workspace.allocate_feature_dir` mkdir, `workspace.py:205-216`) at `cli/run.py:1762` — **before** `_native_runner` is built (`cli/run.py:1909`) and the walk begins. So a discovery step at the head *can* write into it. |
| Prior-context plumbing | After a successful action stage, `_prior_artifact_ref(step, result)` (`cli/run.py:526-536`) sets `prior_box["ref"]`, and the next stage appends it to `ctx_parts` (`cli/run.py:906`). `_dispatch_spec_text` (`cli/run.py:509-523`) injects the approved spec only for stages **after** `review-spec`. |
| Work-kind | `workkind.classify(intent)` → `kinds` (`defect/design/docs/refactor/chore/feature`) + `suggested_tier`, deterministic keyword match, already called at `cli/run.py:810`. |
| Init readiness output | `cli/bootstrap.py:793-797` packs four facts on one `·`-joined line (`language … · adapter … · default tier … · autonomous default …`); the rest of the block (`bootstrap.py:785-817`) is already one-per-line. Built as a `lines` list, printed via `print("\n".join(lines))` at `bootstrap.py:899`. The machine `report`/`--json` is a separate dict (`bootstrap.py:768-781`). |
| Token capture pipeline | `agents.extract_usage` supports only single-field `strategy: json` or single-group `strategy: regex` with plain-int parsing (`agents.py:126-181`; `_usage_from_regex` strips only `,`/`_`, so `629.8k` fails). Manifest hints: **codex** has `tokens used[:\s]+([0-9][0-9,]*)` (a *total*, includes cached); **copilot/claude/aider/opencode** declare **none** (comments claim "no token summary" — now false for Copilot); **copilot-hosted** has a commented `usage.total_tokens` JSON example. Downstream is intact: `DispatchResult.tokens`→`StageResult.tokens`→ ledger `run`/`stage` `tokens` (additive) + `progress.Reporter.stage_completed(tokens=…)` accumulates into `_stage_tokens`, rendered by `progress._tokens_cell` (`—` when `None`). So only **extraction** is broken. |
| Backend usage formats (researched 2026-07) | **claude** `-p`: default text has no usage; `--output-format json` → `usage.{input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens}` + `total_cost_usd`. **copilot** `-p`: text `Tokens ↑ 629.8k (600.2k cached, 29.5k written) • ↓ 9.2k (4.2k reasoning)` (user-observed; abbreviated units). **codex** `exec`: text `tokens used: N` (total incl. cached); `exec --json` NDJSON `token_count` events `{input, cached input, output, reasoning}`. **aider** `--message`: clean text `Tokens: 2.8k sent, 112 received. Cost: …` (sent may include cached context). **opencode** `run`: usage in session JSON; text `run` summary unconfirmed. |
| Tests that bind this | `test_stage_agents.py` (`STAGES` incl. `discovery`, `FORBIDDEN` substrate list, `_front_matter` requires `---` on every template, `resolve_body`/`stage_prompt_body` precedence at lines 136/146/161-162/226); `test_phases.py:131-143` (`stage_prompt_body("plan"/"tasks"/"clarify")`), `test_phases.py:868-874` (LIFECYCLE_STEPS gate list + `("implement","action","Build")` present); `test_run_identity.py:220` + `test_oracle.py:482` (`stage_prompt_body("oracle")`); `test_run_steering.py:685` + `test_progress.py:275` (Discovery already in the 8-stage strip); `test_oss_readiness.py` scans the whole engine source tree **including scaffold assets** for namespaced requirement ids. |

---

## Track A — Externalize every inline agent prompt into editable markdown templates

### Problem
Every dispatched prompt has two potential sources (inline `_STAGE_PROMPTS` vs. `*.agent.md`), the
loader reads only the repo-local seeded copy (no bundled default), and four prompts
(`_PREAMBLE`/`_GENERIC`/`_COMMIT_NOTE`/revise) exist only inline. Editing a prompt means editing
Python. The goal: one maintainable source — the markdown templates — with runtime values threaded in
as variables.

### Approach (decisions 6–9)

**A1 — New bundled fragment templates (decision 7).** Add four files under
`scaffold/templates/agents/`, each with YAML front-matter (`role: fragment`, a `name`/`description`,
and no `stage`) so they load through the existing machinery but are excluded from the dispatched-stage
set:
- `preamble.agent.md` — the standing preamble (was `_PREAMBLE`), static.
- `generic.agent.md` — the unknown-step fallback (was `_GENERIC`), body uses `$STEP`.
- `commit-note.agent.md` — the commit-message request (was `_COMMIT_NOTE`), static.
- `revise.agent.md` — the revision block (was `steering.revise_context`'s literal), body uses
  `$GATE`, `$ARTIFACT`, `$FEEDBACK`.

**A2 — A bundled-default loader (decision 8).** Introduce a package-relative bundled-templates
resolver (reuse `scaffold._TEMPLATES_SCAFFOLD_DIR`) and a `bundled_template_body(name)` that reads
the shipped file with the same `read_text(encoding="utf-8")` + front-matter-strip + OSError-safe `""`
discipline as `stage_template_body`. Change `resolve_body(step, templates_dir)` to a three-tier
fallback: **repo-local template → bundled template → generic fragment**. Add a `fragment_body(name,
templates_dir)` with the same precedence for the four non-stage fragments. No new loader is invented —
this is the existing loader pointed at a second, packaged root.

**A3 — Delete the inline literals (decision, intent 2 §1–2).** Remove `_STAGE_PROMPTS`, `_PREAMBLE`,
`_GENERIC`, `_COMMIT_NOTE` from `prompts.py`, and the inline string in `steering.revise_context`.
`stage_prompt_body` is either removed or reduced to "bundled body for step, else generic fragment";
all callers move to `resolve_body`/`fragment_body`. After this, `grep` for a dispatched-prompt string
literal in the engine returns nothing (a test asserts it — see Tests).

**A4 — Introduce `string.Template` substitution in `assemble` and the revise path (decision 6).**
- Add a single `substitute(body: str, **vars) -> str` helper in `prompts.py`: it builds the fixed
  vocabulary mapping (every variable defaulted to `""`), overlays the supplied values, and returns
  `string.Template(body).safe_substitute(mapping)`. Pure, deterministic, never raises.
- `assemble` runs each template body it composes (preamble, stage body, commit-note) through
  `substitute(...)` with the run's values. The engine-framed context blocks
  (INTENT/APPROVED SPEC/PRIOR CONTEXT/FILE SCOPE) keep their omit-if-empty framing (decision 9) — the
  values are already real, not placeholders.
- `steering.revise_context` becomes: load `revise.agent.md`'s body, `substitute(body, GATE=…,
  ARTIFACT=…, FEEDBACK=…)`. Same signature and byte-deterministic output for fixed inputs.

**A5 — Destinations become variables (decision 9, intent 2 §4).** Replace the hardcoded placeholder
destination prose in the bodies with variables:
- `$FEATURE_FOLDER` in `specify`/`clarify`/`plan`/`tasks`/`discovery` bodies (the flat write
  location).
- `$ORACLE_DESTINATION` in the `oracle` body (the `tests/oracle/<id>/` test destination).
- The engine threads the real values from the dispatch closure: `_feature_folder_context` /
  `_oracle_destination_context` (`cli/run.py:731-770`) are refactored from "build a context block" to
  "return the destination *value*", passed into `assemble` as substitution vars rather than appended
  to `ctx_parts`. The `<feature>` / `<NNN>-<slug>` placeholder tokens leave the template bodies; the
  templates keep a human-readable default sentence only where a value may be absent (offline
  `resolve_body` with no destination renders the variable empty).

**A6 — Thread the vocabulary through both dispatch sites.** `CliAgentRunner.dispatch`
(`runner.py:294`) and `HostedAgentRunner.dispatch` (`hosted.py:138`) already call `assemble`; extend
both to pass the destination values (they already receive `context`/`file_scope`). Keep the two sites
byte-identical to each other.

### Deliverables
Zero inline dispatched-prompt string literals in the engine; the four fragments and the six stage
bodies all served from markdown (bundled default + repo-local override); `assemble` and the revise
path substitute a defined variable vocabulary; unseeded repos (incl. the engine itself) get full
prompts; assembly stays byte-deterministic.

### Tests
- `test_stage_agents.py`: extend `STAGES`/front-matter checks to the four new fragments (assert
  `role: fragment`, present front-matter, non-empty body, none of `FORBIDDEN`); update the
  `resolve_body`/`stage_prompt_body` precedence tests to the new three-tier chain (repo-local →
  bundled → generic); assert an **unseeded** `Settings` still yields the full bundled body (not the
  generic fallback) for every stage.
- New `test_prompt_templates.py` (or extend `test_run_identity.py`): `substitute` renders a supplied
  var, renders an **unfilled** defined var as empty (no leaked `$NAME`), treats `$$` as a literal `$`,
  and never raises on a malformed `$`; `assemble` is byte-identical for fixed inputs; a guard test
  greps `prompts.py`/`steering.py` and asserts no multi-line dispatched-prompt string literal remains.
- Substitution equivalence: for each stage, the assembled prompt with the new mechanism contains the
  same instruction body the shipped template carries (migration is behavior-preserving except the
  destination placeholders now resolve to real values).
- Update `test_phases.py:131-143`, `test_run_identity.py:220`, `test_oracle.py:482` to source bodies
  via `resolve_body`/bundled loader instead of the deleted `stage_prompt_body` inline path.
- `test_oss_readiness.py` stays green over the four new templates (no namespaced ids; `DEMO-FR-###` /
  bare `FR-###` only if any id appears).

---

## Track B — Wire the Discovery stage into the `3pwr run` executive loop

### Problem
Discovery is named but never dispatched (Why-now #3). We want it to run as the first dispatched stage
**when needed** (decision 2), produce a discovery note, and feed that note to Specify as prior
context — with the tracker showing a real running→done cell.

### Approach (decisions 2–5)

**B1 — Add the step to the walk.** Insert `("discovery", "action", "Discovery")` at the head of
`LIFECYCLE_STEPS` (`orchestrate.py:40`). Both `NativeRunner._walk` and `SimulatedRunner._walk` then
walk it; `--dry-run` shows a Discovery step, live runs dispatch it. `resume_index`/`step_index`/
`segment_actions` are index-based and adjust automatically.

**B2 — Conditional dispatch by work-kind + flag (decision 2).** Discovery must run only when needed:
- Add a pure `discovery_enabled(work_kinds, *, flag) -> bool` helper (in `workkind.py` or a small
  `orchestrate` seam): run when any kind is `feature`/`design`; skip when all kinds are in
  `{defect, docs, chore, refactor}`; `--discovery` forces on, `--no-discovery` forces off, else the
  work-kind rule decides. Brownfield Stage Zero (the `characterize` entry, `cli/brownfield.py`) never
  includes discovery.
- Implement the skip **without** breaking the fixed `LIFECYCLE_STEPS` list (which the ledger/resume
  indices and many tests depend on): the runner still *walks* the discovery step, but the injected
  `dispatch(step, stage)` closure **short-circuits** a skipped discovery — it emits the step event,
  records no artifact, sets no `prior_box["ref"]`, and returns an `ok` `StageResult` with
  `outcome="skipped"` (a new, additive outcome value) so the walk advances to `specify` exactly as
  today. This keeps step indices stable and the simulator/`--dry-run` unchanged, while a live run only
  *dispatches an agent* when discovery is enabled. Add `--discovery`/`--no-discovery` to the `run`
  argparser and thread the resolved flag into the closure.

**B3 — Discovery prompt from the template (decision 3).** With Track A's bundled default in place,
`resolve_body("discovery", templates_dir)` returns the `discovery.agent.md` body for any repo. Add
`discovery` to the `_feature_folder_context` step set (`cli/run.py:899`) — after Track A this means
threading `$FEATURE_FOLDER` — so the discovery agent is told to write `discovery.md` flat into the
allocated folder. Discovery is a producing stage, so add it to `COMMIT_NOTE_STEPS` (`prompts.py:108`)
if we want its stage commit message agentically authored (consistent with the other producing
stages).

**B4 — Discovery artifact contract + producing-step wiring.**
- Add a `discovery` contract to `STAGE_ARTIFACTS` (`artifacts.py`): `kind="path"`, pattern
  `r"(^|/)specs(-src)?/.+/discovery\.md$"`, expected "a discovery note
  (specs-src/<feature>/discovery.md)".
- Add `"discovery"` to `workspace.PRODUCING_STEPS` (`workspace.py:44`) and to `_STEP_FILENAMES`
  (`discovery` → `discovery.md`; the default `<step>.md` already yields `discovery.md`, so this is a
  no-op confirmation) so `stage_artifact_path`/`find_artifact` resolve it like other stage artifacts.
- Discovery is **not** an oracle/implement record step, so `completion.RECORD_STEPS` is unchanged; the
  note is verified by its contract and recorded via the normal `run`/`stage` ledger entry
  (`cli/run.py:982-989`) with its `artifact_paths`.

**B5 — Feed the note to Specify (already plumbed).** No new mechanism: after discovery succeeds,
`_prior_artifact_ref("discovery", result)` sets `prior_box["ref"]` to the note's path + digest, and
Specify appends it via `ctx_parts` (`cli/run.py:906`). `_dispatch_spec_text` returns `""` for
discovery (it is before `review-spec`), so discovery gets no approved-spec block — correct. Confirm
the discovery note reference is the first PRIOR CONTEXT Specify sees.

**B6 — Lifecycle state + tracker.** Change `SpecState.stage` default to `"Discovery"`
(`lifecycle.py:36`) so a spec with a discovery record (but no spec yet) reports the right stage.
`derive` already folds `run`/`stage` records into `st.stage` via `canonical_stage`, so a discovery
completion advances state to `Discovery` and the tracker renders it as a real running→done cell
(`orchestrate.py:524` sets `_reached` from each event's stage). A skipped discovery emits its step but
the next event (`specify`) advances to `Spec` — the pre-Track-B behavior, which is correct for a
skipped run.

**B7 — Boundary preserved (decision 5).** The discovery note "introduces no requirement ids" and "is
not itself the spec"; the engine treats it as free-form prior context only. The note's suggested
work-kind/tier is advisory prose the human reads — it does **not** feed `workkind.classify` or the
tier the run uses. Keep `discovery.agent.md` unchanged except for the `$FEATURE_FOLDER` variable
(Track A A5).

### Deliverables
`3pwr run "<feature intent>"` dispatches Discovery first (producing
`specs-src/<NNN>-<slug>/discovery.md`), hands it to Specify as prior context, and shows Discovery as a
running→done tracker cell; a `defect`/`docs`/`chore`/`refactor` intent (or `--no-discovery`) skips the
dispatch and proceeds to Specify as before; `--discovery` forces it on.

### Tests
- `test_phases.py:868-874`: update the LIFECYCLE_STEPS assertions to include
  `("discovery","action","Discovery")` at index 0 (and keep the gate-list/`implement` assertions).
- New `test_discovery_stage.py`: (1) a `feature` intent walks discovery → produces `discovery.md`
  satisfying its contract → `prior_box` ref reaches specify (assert the specify prompt's PRIOR CONTEXT
  names the discovery note); (2) a `defect`/`docs` intent (and `--no-discovery`) short-circuits — no
  agent dispatched, `outcome="skipped"`, walk still reaches specify; (3) `--discovery` forces a
  `defect` intent to dispatch discovery; (4) the discovery contract matches
  `specs-src/x/discovery.md` and rejects off-target paths.
- Artifact-contract test extended for the `discovery` pattern; `test_run_workspace`/`workspace` tests
  for `discovery` in `PRODUCING_STEPS` and `stage_artifact_path`.
- `test_lifecycle`: `SpecState().stage == "Discovery"`; a `run`/`stage` discovery record derives
  `stage == "Discovery"`.
- `--dry-run` / `SimulatedRunner` test: the simulated walk emits a Discovery step event (the tracker
  shows the cell) — deterministic.
- Confirm `test_run_steering.py:685` and `test_progress.py:275` (Discovery already in the strip) stay
  green.

---

## Track C — One fact per line in the `3pwr init` readiness summary

### Problem
The init readiness summary packs four facts onto one line with ` · ` separators
(`cli/bootstrap.py:793-797`):

```
  language: typescript · adapter created · default tier: Standard · autonomous default: yes
```

The user wants each fact on its own line for readability; the rest of the block is already
one-per-line.

### Approach (decision 10)
- Replace the single `·`-joined `lines.append(...)` (`bootstrap.py:793-797`) with one `lines.append`
  per fact, each indented `  ` to match the block:
  ```
    language: typescript
    adapter: created
    default tier: Standard
    autonomous default: yes
  ```
  (When no adapter was selected, keep the existing `(none — no adapter selected)` phrasing on the
  language line.)
- Keep the homogeneous comma-lists (agent backends `bootstrap.py:805`, template count `:807-811`,
  notifications `:812-817`) as they are — each is already its own line and a single logical fact.
- **Do not touch** the `--json` report dict (`bootstrap.py:768-781`) — scripted callers depend on its
  shape; this is a human-output-only change.

### Deliverables
`3pwr init` prints the language/adapter/tier/autonomy facts one per line; `--json` unchanged.

### Tests
`test_init_experience.py` / `test_init_wizard_and_brownfield.py`: update any assertion that matches the
`·`-joined line to the one-per-line form; assert each fact appears on its own line and the `--json`
payload is unchanged. OSS-readiness stays green (no internal ids in the text).

---

## Track D — Real per-stage token accounting across every headless backend

### Problem
`progress.md` shows `—` for tokens on every stage even though the backend prints a usage summary
(the user's Copilot run showed `Tokens ↑ 629.8k … ↓ 9.2k`). Root cause: most manifests declare no
`usage` hint (copilot/claude/aider/opencode), the one that does (codex) captures a cached-inclusive
*total*, and `extract_usage` can't parse abbreviated (`629.8k`) or broken-down counts. The whole
downstream pipeline (result → ledger → progress → `--json`) already works — only extraction is
missing. The user wants the **real consumed (non-cached) tokens** to show, for **every** backend.

### Approach (decisions 11–12 — advisory, never in the verdict)

**D1 — Define the normalized metric (decision 11).** One integer per stage/phase:
`consumed = non_cached_input + output`, where cache-read / cached-context tokens are **excluded** and
a backend's output-side sub-counts (e.g. reasoning) count as output. Document the per-backend field
mapping so the number means the same thing everywhere.

**D2 — Generalize `extract_usage` (`agents.py`).** Today's single-field-json / single-group-regex is
too weak. Extend it (keeping it pure, `None`-safe, never-raises):
- **Unit-aware number parsing** — a shared `_parse_count("629.8k") -> 629800` helper handling `k`/`M`
  (and plain integers with `,`/`_`), used by every strategy.
- **Regex sum** — allow the regex strategy to sum **named/multiple capture groups** (e.g. Copilot's
  `written` + `↓ output`), not just group 1.
- **JSON compute** — allow the json strategy to sum **multiple dotted fields** and/or subtract a
  cached field (e.g. claude `input_tokens + output_tokens`; codex `(input − cached) + output +
  reasoning`), rather than reading one field.
- Backwards-compatible: the existing single-field / single-group forms keep working (codex's current
  hint still parses), so no other backend regresses.

**D3 — Per-backend `usage` hints (bundled `scaffold/agents/*.yaml`), each grounded in D1 and verified
against a real captured transcript before it ships:**
- **copilot** — new `strategy: regex` capturing the `written` and `↓` numbers from the text summary,
  summed via D2; drop the now-false "no token summary" comment.
- **codex** — switch from the total-only text regex to the `token_count` structured counts
  (`exec --json`) computing non-cached per D1 — **only if** the JSON mode is adopted (see D4);
  otherwise keep the text total with a comment that it includes cached tokens.
- **aider** — `strategy: regex` on `Tokens: <sent> sent, <received> received`; note in the manifest
  that `sent` may include cached context (an over-count when caching is on) — the best the text
  exposes.
- **claude** — usage requires `--output-format json`; provide the `strategy: json` hint
  (`input_tokens + output_tokens`) but gate it behind the opt-in of D4.
- **opencode** — verify whether `opencode run` prints a usage line or exposes it only via session
  JSON; add the matching hint, or document "unknown" if neither is capturable from the dispatch
  output.
- **copilot-hosted** — keep the JSON-field hint (uncomment/adjust `usage.total_tokens`), documented as
  hosted-reported and possibly cached-inclusive.

**D4 — Capture-mode policy (decision 12).** Prefer each CLI's **default output** so the live
conversation stays readable text. Where usage is *only* in a structured mode that would replace the
live stream (Claude `-p`, and codex if `--json` is chosen), make that mode an **opt-in manifest
field** (e.g. `usage_mode: json` toggling the extra base-arg) defaulting off; that backend reads
"unknown" until a user opts in. Document the tradeoff (clean usage vs. machine-JSON live view).

**D5 — Prerequisite verification.** Extraction only sees what 3Powers **captures**. The user observed
the Copilot summary streamed through the run frame, so it is in the captured stdout/stderr, but
confirm per backend that the usage report lands in the persisted transcript
(`.3powers/runs/<spec-id>/`) — not a TTY-only region — before relying on a hint. Ship a captured
sample per backend as a test fixture.

**D6 — No pipeline changes needed downstream.** `DispatchResult.tokens` → `StageResult.tokens` →
ledger `run`/`stage` `tokens` (additive) → `progress.Reporter` → `_tokens_cell` already carry and
render the value; Track D only makes extraction return a real number. Confirm the phased path
(`_dispatch_phased`) sums per-phase tokens into the stage total and `phase_tokens` populates the
phase-detail column.

### Deliverables
`progress.md`, the ledger `stage`/`phase` entries, and `--json` show the **real consumed (non-cached)
tokens** per stage for Copilot out of the box, and for the other backends where their output exposes
it; "unknown" (`—`) only when a backend genuinely does not report capturable usage. The metric means
the same thing across backends. The verdict and its bytes are unchanged.

### Tests
- `test_agents.py` (usage extraction): `_parse_count` handles `k`/`M`/decimals/plain/`,`; the regex-sum
  strategy sums the Copilot `written`+`↓` sample to the expected int; the json-compute strategy
  computes claude `input+output` and codex `(input−cached)+output+reasoning` from captured NDJSON;
  malformed / missing usage → `None`; the legacy single-field/single-group forms still parse (codex
  regression).
- Per-backend fixture tests: a real captured transcript sample per backend → the manifest hint yields
  the expected non-cached integer.
- A run records the token count in `progress.md`'s Tokens cell, the ledger `stage` payload, and
  `--json`; a `None`/unknown backend still renders `—` and does not break parsing.
- **Determinism guard**: the verdict and the gate `--json` bytes are identical whether or not usage is
  captured (tokens never enter the verdict) — extends the plan-033 Track H guard.

---

## Variable vocabulary (defined — decision 6)

`$`-delimited, closed set; every variable is always supplied to `safe_substitute` (empty when
absent), so an unfilled one renders empty rather than leaking a placeholder.

| Variable | Meaning | Used by |
|---|---|---|
| `$STEP` | the lifecycle step id | `generic.agent.md` fallback |
| `$GATE` | the human gate id under revision | `revise.agent.md` |
| `$ARTIFACT` | the artifact under review | `revise.agent.md` |
| `$FEEDBACK` | the human's revise feedback | `revise.agent.md` |
| `$FEATURE_FOLDER` | the run's allocated feature folder (repo-relative) | `discovery/specify/clarify/plan/tasks` bodies |
| `$ORACLE_DESTINATION` | the oracle test destination `tests/oracle/<id>/` | `oracle` body |

INTENT / APPROVED SPEC / PRIOR CONTEXT / FILE SCOPE remain **engine-framed trailing blocks** with the
omit-if-empty rule (decision 9), not substitution variables. New variables may be added later by
extending the vocabulary map and a template; the mechanism is open to extension, closed against
mid-run failure.

---

## Delivery order and dependencies

Delivered as sequential units on the one feature branch — **no pull requests** (AGENTS.md/CLAUDE.md).
Engine changes go through the **python-engineer agent**; each unit lands green (ruff/mypy/pytest +
self-application `3pwr gate run --path engine`) before the next.

| Unit | Track | Depends on | Risk | Effort |
|---|---|---|---|---|
| 1 — bundled fragments + bundled-default loader + `substitute` | A (A1–A2, A4 helper) | none | Low–Medium | Medium |
| 2 — delete inline literals; move callers to `resolve_body`/`fragment_body`; revise via template | A (A3, revise) | 1 | Medium (breadth: prompts.py, steering.py, tests) | Medium |
| 3 — destinations become variables; thread through both dispatch sites | A (A5–A6) | 1–2 | Medium (touches cli/run.py closure) | Medium |
| 4 — Discovery in LIFECYCLE_STEPS + contract + producing-step wiring + state default | B (B1, B4, B6) | 3 (bundled default so discovery body resolves) | Low–Medium | Medium |
| 5 — conditional dispatch (work-kind + `--discovery`/`--no-discovery`) + feed-to-specify | B (B2, B3, B5, B7) | 4 | Medium | Medium |
| 6 — init readiness one-fact-per-line | C | none | Low | Small |
| 7 — token extraction generalization + per-backend hints + fixtures | D | none (independent; extends plan-033 Track H) | Medium (per-backend formats drift; needs real captured samples) | Medium |
| 8 — docs + final verification | A+B+C+D | all | Low | Small |

**Suggested grouping:** (1+2+3) Track A externalization; (4+5) Track B discovery; (6) Track C init
line; (7) Track D tokens; (8) docs + verify. C and D are independent and may be delivered in any order
relative to A/B.

---

## Docs to update (same unit of work — AGENTS.md open-source-readiness)

- `docs/cli-reference.md` — the `3pwr run` section: Discovery as the first dispatched stage, the
  `--discovery`/`--no-discovery` flags and the work-kind default; a short "editing agent prompts"
  note pointing at `.3powers/templates/agents/*.agent.md` (repo-local override) and the bundled
  defaults, listing the variable vocabulary.
- `docs/concepts.md` / lifecycle description — Discovery now runs (when needed) and feeds Specify.
- `CLAUDE.md` / `AGENTS.md` — the "prompt templates are the one source of truth" note where prompt
  assembly is described (keep free of internal spec ids).
- `docs/cli-reference.md` (Track D) — the token-accounting section: what the per-stage token number
  means (real consumed = non-cached input + output), which backends report it and how, the opt-in
  JSON `usage_mode` for backends that only expose usage in a structured mode, and where it appears
  (progress.md, ledger, `--json`).
- Confirm no internal plan/spec/requirement ids leak into any template or CLI text
  (`test_oss_readiness.py`). Track C is human-output-only (no docs change beyond any init sample).

---

## Spec files to create (self-application)

This work is built with 3Powers, so each track gets a spec (`specs-src/` is exempt from the
OSS-readiness id rule). Numbers are the next free workspace numbers **at implementation time**; the
specify stage may split further.

| Path | Spec ID | Track |
|---|---|---|
| `specs-src/<NNN>-prompt-templates/spec.md` | `PROMPTPL` | A |
| `specs-src/<NNN>-discovery-stage/spec.md` | `DISCOV` | B |
| `specs-src/<NNN>-token-accounting/spec.md` | `TOKUSE` | D (Track C — the one-line init tweak — may fold in here as a UX requirement, or ride Track D's spec) |

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Byte-drift in assembled prompts.** Moving from inline concat to template + substitution could change prompt bytes and perturb determinism tests. | Keep the context-block framing and order identical (decision 9); a test asserts `assemble` is byte-identical for fixed inputs; the migration is behavior-preserving except destination placeholders now resolve to real values (an explicitly asserted, intended change). |
| **`safe_substitute` leaks a stray `$word` from prose.** A template author writes `$5` or `$foo` unintentionally. | `$$` is the documented literal-`$` escape; a template lint test greps the bundled bodies for `$` tokens outside the defined vocabulary and fails; `safe_substitute` never raises, so at worst the literal survives (caught by the test, not a run failure). |
| **Unseeded-repo regression.** If the bundled-default loader misfires, unseeded repos silently fall back to the generic fragment (worse prompts) instead of the full body. | A test constructs an unseeded `Settings` and asserts every stage resolves the full bundled body, not the generic fallback. |
| **Discovery breaks resume/ledger indices.** Inserting a step at index 0 shifts `LIFECYCLE_STEPS` indices; old ledgers reference step ids, not indices, but resume math is index-based. | Resume/segment math is computed from step *ids* via `step_index`/`resume_index` against the live list, so inserting a head step is self-consistent; a back-compat test drives `--resume` over a ledger authored before discovery existed (its `checkpoint`/`stage` records name `specify`+, which still resolve). |
| **Skipped discovery must be a true no-op, not a failure.** A short-circuited discovery must not trip the artifact contract or record a phantom artifact. | The skip returns an `ok` `StageResult` with `outcome="skipped"` and no `artifact_paths`; `verify` is not run (no dispatch happened); the walk advances exactly as the pre-Track-B path. A test asserts no `discovery.md` is written and no ledger `stage` artifact is recorded on a skipped run. |
| **`outcome="skipped"` is a new StageResult value.** `--json`/progress consumers may not expect it. | It is additive (a new enum value on an existing field); the value only appears for a skipped discovery; a test asserts `--json` stays parseable and the verdict/gate payloads are unchanged. |
| **Two dispatch sites drift.** `runner.py` and `hosted.py` must thread the same vocabulary. | A shared `assemble` signature carries the vars; a test asserts both sites produce the same prompt for the same inputs (extends the existing hosted/cli parity coverage). |
| **Template edits trip `spec_integrity`/`gate_gaming` or the conformance template-skeleton test.** New/edited templates are scaffold assets some tests bind. | Update `test_stage_agents.py` in lockstep; run `3pwr gate run --path engine` + `3pwr verify` before landing; if a sealed asset trips, the maintainer re-seals (documented) or records a signed `3pwr deviation`. |
| **Per-backend token formats drift or aren't captured.** A CLI changes its summary wording, or prints usage to a TTY region 3Powers doesn't capture, so a hint silently reads "unknown". | Every hint is verified against a **real captured transcript fixture** before it ships (D5); extraction is `None`-safe so a stale hint degrades to `—`, never a failure; the determinism guard proves the verdict is unaffected. Formats are documented as of 2026-07 with a note that they may change. |
| **The non-cached metric can't be isolated for a backend.** aider's text `sent` may include cached context; a CLI may only report a cached-inclusive total. | Document the per-backend limitation in the manifest and the metric mapping; prefer the structured (JSON) counts where they split cached out (claude/codex); accept the documented over-count only where the output exposes nothing finer, rather than silently mislabeling it. |
| **JSON usage-mode degrades the live conversation.** Forcing `--output-format json` (claude) / `--json` (codex) to get usage turns the streamed view into machine JSON. | `usage_mode` is opt-in per manifest, defaulting off (decision 12); the default keeps the readable text stream and reads "unknown" for a JSON-only backend until the user opts in. |
| **Init-line test churn (Track C).** Tests that assert the `·`-joined summary string break when it is split. | Update `test_init_experience.py` assertions in the same change; assert the one-per-line form and that `--json` is unchanged. |

---

## Verification (post-delivery)

```bash
(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)
3pwr gate run --path engine            # self-application, Standard tier
uv tool install --force ./engine
# one source of truth: no inline dispatched-prompt literal remains
grep -nE 'STAGE: |REVISION REQUESTED' engine/src/threepowers/prompts.py engine/src/threepowers/steering.py || echo "no inline prompt literals"
# unseeded repo still gets full prompts (bundled default) — a dry run shows Discovery first
3pwr run "add a user-facing dashboard" --dry-run
# feature intent dispatches discovery; defect intent skips it
3pwr run "add a dashboard" --dry-run           # Discovery cell shown
3pwr run "fix the crash on empty input" --no-discovery --dry-run
# Track C: init prints one fact per line (no ' · '-joined summary), --json unchanged
3pwr init --yes | grep -E '^\s+(language|adapter|default tier|autonomous default):'
# Track D: a live run records real (non-cached) tokens in progress.md (backend that reports usage)
grep -E '^\| (Spec|Plan) .*\| [0-9]' specs-src/<NNN>-*/progress.md   # Tokens cell is a number, not —
```

---

## Open questions — all resolved 2026-07-08

The plan is **finalized** and ready for handover to the implementation-plan agent. Resolutions:

1. **Plan structure** — RESOLVED: one combined plan; two coupled core tracks (A externalization first,
   then B discovery) plus two independent user-requested additions (C init readability, D token
   accounting) (user-confirmed structure; C/D added at user request).
2. **Discovery "only if needed" gate** — RESOLVED: work-kind gate (skip
   `defect`/`docs`/`chore`/`refactor` + brownfield; run `feature`/`design`) plus
   `--discovery`/`--no-discovery` override (user-confirmed).
3. **Discovery prompt source** — RESOLVED: the `discovery.agent.md` template via Track A's loader, not
   an inline body (user-confirmed).
4. **Discovery as a human gate** — RESOLVED: no; automatic action step (user-confirmed default).
5. **Discovery work-kind/tier signal** — RESOLVED: advisory prose only, not consumed by the engine's
   tier logic (plan decision, intent delegated "you decide").
6. **Substitution mechanism & vocabulary** — RESOLVED: stdlib `string.Template` `safe_substitute`
   over a fixed closed vocabulary (plan decision, intent delegated "the plan picks one"); vocabulary
   defined above.
7. **Init readiness layout (Track C)** — RESOLVED: split the `·`-joined summary into one fact per
   line; keep comma-lists inline; `--json` untouched (user asked "each in a new line").
8. **Token metric (Track D)** — RESOLVED: real consumed = non-cached input + output, normalized
   across all backends (user-confirmed); researched per-backend field mappings recorded above.
9. **Token capture mode (Track D)** — RESOLVED: default text output + native-report parser; JSON-only
   backends (Claude) get an opt-in `usage_mode`, default off, to preserve the live text stream (plan
   decision, intent delegated). Per-backend hints verified against real captured fixtures before
   shipping.
