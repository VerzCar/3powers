---
goal: One source of truth for agent prompts (markdown templates), wire the Discovery stage, one-line init readability, and real per-backend token accounting
version: 1.0
date_created: 2026-07-08
last_updated: 2026-07-08
owner: 3Powers maintainers (engine changes via the python-engineer agent)
status: 'Completed'
tags: [feature, refactor, architecture]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

This implementation plan operationalizes the source plan
[`plan/034-prompt-templates-and-discovery-stage.md`](034-prompt-templates-and-discovery-stage.md)
(four tracks A–D, finalized 2026-07-08) as eight sequential delivery phases on the existing branch
`feat/034-prompt-templates-and-discovery`. It makes the markdown `*.agent.md` templates the single
source of truth for every dispatched prompt (Track A), wires the Discovery stage into the `3pwr run`
executive loop so it runs first when needed and feeds a discovery note to Specify (Track B), splits
the `3pwr init` readiness summary onto one fact per line (Track C), and captures the real consumed
(non-cached) token count per stage across every headless backend (Track D).

The invariants that bound every phase: **prompt assembly stays byte-deterministic** (same inputs →
the same prompt); the deterministic verdict, the signed ledger's verification, exit codes, and
`--json` byte-stability never change except where a payload gains a strictly *additive* field (which
`3pwr verify` already tolerates); **token accounting is advisory and never enters the verdict**; **no
model call and no new runtime dependency** are added; and everything stays backend-neutral (identical
assembled prompts for Claude, Codex, Copilot, Gemini). Phases 1→5 are ordered (A must land before B);
Phases 6 and 7 are independent; Phase 8 is a dedicated final verification + docs phase.

## 1. Requirements & Constraints

Functional requirements (each traces to a source-plan track):

- **REQ-001** (Track A): The markdown templates are the single source of truth. Delete the inline
  `_STAGE_PROMPTS`, `_PREAMBLE`, `_GENERIC`, `_COMMIT_NOTE` string literals in `prompts.py` and the
  inline revise string in `steering.py`; after the sweep there are **zero inline dispatched-prompt
  string literals** in the engine.
- **REQ-002** (Track A): The engine reads the **bundled** package templates as the built-in default
  (repo-local override → bundled default → generic fragment), so unseeded repos — including the
  engine's own gate run — get full prompts.
- **REQ-003** (Track A): Introduce `string.Template` `safe_substitute` variable substitution over a
  fixed closed vocabulary, applied **only** to template-sourced bodies (never to the engine-framed
  INTENT / APPROVED SPEC / PRIOR CONTEXT / FILE SCOPE blocks); destination placeholders become the
  variables `$FEATURE_FOLDER` and `$ORACLE_DESTINATION`, body-local values `$STEP`, `$GATE`,
  `$ARTIFACT`, `$FEEDBACK`.
- **REQ-004** (Track B): Discovery is dispatched as the first `action` step of `3pwr run`, producing
  `specs-src/<NNN>-<slug>/discovery.md`, verified by an artifact contract and handed to Specify as
  its PRIOR CONTEXT via the existing `prior_box` mechanism.
- **REQ-005** (Track B): Discovery runs **only when needed** — deterministically by work-kind (run
  for `feature`/`design`; skip `defect`/`docs`/`chore`/`refactor` and brownfield Stage Zero) with a
  `--discovery`/`--no-discovery` override; a skipped discovery is a runner short-circuit
  (`outcome="skipped"`), not a list mutation or a failure.
- **REQ-006** (Track B): `SpecState.stage` defaults to `"Discovery"`; a real discovery completion
  advances lifecycle state and renders a running→done tracker cell; the discovery note stays free of
  requirement ids and its suggested work-kind/tier is advisory prose the engine does not consume.
- **REQ-007** (Track C): The `3pwr init` readiness summary prints `language`, `adapter`,
  `default tier`, and `autonomous default` each on its own line; the `--json` report is untouched.
- **REQ-008** (Track D): One advisory integer per stage/phase = **real consumed tokens =
  non-cached input + output**, normalized across Claude, Copilot, Codex, aider, opencode.
- **REQ-009** (Track D): Generalize `agents.extract_usage` — unit-aware number parsing (`k`/`M`/
  decimals), regex summing of multiple/named groups, and JSON summing/subtracting of multiple dotted
  fields — while keeping the existing single-field/single-group forms working.
- **REQ-010** (Track D): Ship per-backend `usage` hints verified against real captured transcript
  fixtures; provide an opt-in per-manifest `usage_mode` for backends whose usage is only in a
  structured mode (Claude), defaulting off to preserve the live text stream.

Security requirement:

- **SEC-001** (Track A): Variable substitution must never be applied to untrusted INTENT / APPROVED
  SPEC / PRIOR CONTEXT / FILE SCOPE text, so a `$` in a spec (e.g. a shell example) is never
  corrupted or interpreted; `safe_substitute` never raises mid-run.

Constraints:

- **CON-001**: No pull requests. All work stays on the existing branch
  `feat/034-prompt-templates-and-discovery`, delivered as sequential units (AGENTS.md / CLAUDE.md).
- **CON-002**: Engine (Python under `engine/`) changes go through the **python-engineer agent**; each
  phase lands green — `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` plus
  self-application `3pwr gate run --path engine` — before the next phase starts.
- **CON-003**: Deterministic assembly — identical inputs yield byte-identical prompts; the verdict,
  ledger verification, exit codes, and `--json` byte-stability change only via strictly-**additive**
  payload fields.
- **CON-004**: Token accounting (Track D) is advisory and never enters `run_gates`, the verdict, or
  the verdict bytes.
- **CON-005**: `LIFECYCLE_STEPS` is a fixed, index-referenced list many resume/ledger computations
  and tests depend on. Discovery is inserted at the head; the "only if needed" behavior is a
  short-circuit inside the dispatch closure, never a runtime mutation of the list.
- **CON-006**: No new runtime dependency — substitution uses the stdlib `string` module; runtime deps
  stay `cryptography` + `PyYAML`.
- **CON-007**: Backend-neutral — the assembled prompt is identical for any headless agent; templates
  ship as public scaffold assets.
- **CON-008**: The `discovery.md` note introduces no requirement ids and is not the spec; it is
  free-form prior context only.

Guidelines & patterns:

- **GUD-001**: Open-source readiness — no internal plan/spec/requirement IDs in user-facing text or
  scaffold assets (templates included); format teaching uses `DEMO-FR-###`/bare `FR-###`; enforced by
  `engine/tests/test_oss_readiness.py`.
- **PAT-001**: Template resolution precedence — repo-local `.3powers/templates/agents/<name>` →
  bundled package default → generic fragment (mirrors the existing `find_artifact`/`spec_path`
  tolerance idiom).
- **PAT-002**: Additive-only payload evolution — new ledger/`--json`/progress fields and the new
  `outcome="skipped"` value are added, never renamed or removed, so `3pwr verify` and defensive
  `.get()` parsers stay green.
- **PAT-003**: Reuse the existing template-loading discipline — `read_text(encoding="utf-8")`,
  leading `---` front-matter strip via `prompts.template_body`, OSError-safe `""` fallback.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Add the Track A foundation **without deleting anything yet** — the bundled-default
  template loader, the `string.Template` substitution helper + closed vocabulary, the four new
  fragment templates, and the three-tier `resolve_body` — so the engine stays green while the new
  machinery lands. Completion criterion: `(cd engine && uv run pytest && uv run ruff check . &&
  uv run mypy src)` green; `3pwr gate run --path engine` green; an unseeded `Settings` resolves the
  full bundled body for every stage.

**File scope**: `engine/src/threepowers/prompts.py`;
`engine/src/threepowers/scaffold/templates/agents/preamble.agent.md`,
`generic.agent.md`, `commit-note.agent.md`, `revise.agent.md` (new);
`engine/tests/test_stage_agents.py`; `engine/tests/test_prompt_templates.py` (new).

**Depends on**: none.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/prompts.py` add a module constant `_BUNDLED_TEMPLATES_DIR = Path(__file__).resolve().parent / "scaffold" / "templates" / "agents"` (no `scaffold` import — avoids a cycle) and a pure function `bundled_template_body(filename: str) -> str` that reads `_BUNDLED_TEMPLATES_DIR / filename`, strips front-matter via the existing `template_body`, and returns `""` OSError-safe (PAT-003). Verify: a unit test asserts `bundled_template_body("specify.agent.md")` is non-empty and `bundled_template_body("missing.agent.md") == ""`. | ✅ | 2026-07-08 |
| TASK-002 | In `prompts.py` define the closed variable vocabulary `_VARS = ("STEP","GATE","ARTIFACT","FEATURE_FOLDER","ORACLE_DESTINATION","FEEDBACK")` and a pure helper `substitute(body: str, variables: Optional[Mapping[str,str]] = None) -> str` returning `string.Template(body).safe_substitute({**{k: "" for k in _VARS}, **(variables or {})})`. Document: `$$`→literal `$`, an unfilled defined var renders empty, an unknown `$x` is left verbatim, and it never raises (SEC-001). Verify: `test_prompt_templates.py` asserts a supplied var renders, an unfilled `$STEP` renders empty, `$$` → `$`, and a lone malformed `$` does not raise. | ✅ | 2026-07-08 |
| TASK-003 | Create the four fragment templates under `engine/src/threepowers/scaffold/templates/agents/`, each opening with YAML front-matter carrying `name`, `description`, and `role: fragment` (NO `stage:` key, so they are excluded from the dispatched-stage set): `preamble.agent.md` (body = the current `_PREAMBLE` text), `generic.agent.md` (body = the current `_GENERIC` text with `{step}` rewritten to `$STEP`), `commit-note.agent.md` (body = the current `_COMMIT_NOTE` text), `revise.agent.md` (body = the current `steering.revise_context` string with `$GATE`, `$ARTIFACT`, `$FEEDBACK` in place of the f-string fields). All OSS-clean (GUD-001). Verify: each file opens with `---`; `grep -l "role: fragment"` matches all four; `grep '\$STEP' generic.agent.md` and `grep -E '\$GATE|\$ARTIFACT|\$FEEDBACK' revise.agent.md` match. | ✅ | 2026-07-08 |
| TASK-004 | In `prompts.py` add `fragment_body(filename: str, templates_dir: Optional[Path]) -> str` with precedence repo-local (`templates_dir / filename` via `template_body`) → bundled (`bundled_template_body(filename)`); no generic tier for fragments (PAT-001). Verify: a unit test asserts `fragment_body("preamble.agent.md", None)` returns the bundled preamble body, and a repo-local override file wins when present. | ✅ | 2026-07-08 |
| TASK-005 | In `prompts.py` rewrite `resolve_body(step, templates_dir)` to a three-tier fallback: repo-local template body (`stage_template_body`) → bundled template body (`bundled_template_body(template_name(step))`) → the generic fragment (`fragment_body("generic.agent.md", templates_dir)`). Do NOT yet delete `_STAGE_PROMPTS`/`stage_prompt_body` (Phase 2). Verify: with an unseeded `Settings`, `resolve_body("plan", s.stage_templates_dir)` equals the bundled `plan.agent.md` body (not the generic fragment); `resolve_body("unknown-step", None)` returns the generic fragment. | ✅ | 2026-07-08 |
| TASK-006 | Update `engine/tests/test_stage_agents.py`: add a `FRAGMENTS = ("preamble","generic","commit-note","revise")` set and assert each `*.agent.md` opens with front-matter, declares `role: fragment`, and has a non-empty body carrying none of `FORBIDDEN`; add a test that an unseeded repo resolves the full bundled body per `STAGES` entry via `resolve_body`. Verify: `uv run pytest tests/test_stage_agents.py tests/test_prompt_templates.py` green. | ✅ | 2026-07-08 |

### Phase 2

- GOAL-002: Switch the dispatch path to the templates and **delete every inline dispatched-prompt
  literal** (REQ-001, REQ-002). `assemble` resolves the preamble, stage body, and commit-note from
  templates (substituting the vocabulary on template bodies only), the two dispatch sites call it with
  `templates_dir`, `steering.revise_context` loads its template, and `_STAGE_PROMPTS`/`_PREAMBLE`/
  `_GENERIC`/`_COMMIT_NOTE` are removed. Completion criterion: a grep finds no multi-line dispatched
  prompt literal; all gates green.

**File scope**: `engine/src/threepowers/prompts.py`; `engine/src/threepowers/runner.py`;
`engine/src/threepowers/hosted.py`; `engine/src/threepowers/steering.py`;
`engine/src/threepowers/cli/run.py`; `engine/tests/test_stage_agents.py`,
`engine/tests/test_phases.py`, `engine/tests/test_run_identity.py`, `engine/tests/test_oracle.py`,
`engine/tests/test_run_steering.py`, `engine/tests/test_prompt_templates.py`.

**Depends on**: Phase 1.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-007 | Rewrite `prompts.assemble` (currently `prompts.py:195-224`) to the signature `assemble(step, *, intent="", spec_text="", context="", file_scope="", templates_dir=None, variables=None)` (drop the `body=` param). Internally: `preamble = substitute(fragment_body("preamble.agent.md", templates_dir), variables)`; `body = substitute(resolve_body(step, templates_dir), variables)`; when `step in COMMIT_NOTE_STEPS`, `commit = substitute(fragment_body("commit-note.agent.md", templates_dir), variables)`. Keep the trailing INTENT/APPROVED SPEC/PRIOR CONTEXT/FILE SCOPE blocks and their omit-if-empty framing EXACTLY as today, and do NOT run `substitute` on them (SEC-001, CON-003). Verify: `test_prompt_templates.py` asserts `assemble` output is byte-identical for fixed inputs and that a `$` inside `spec_text` survives verbatim. | ✅ | 2026-07-08 |
| TASK-008 | Update the two dispatch sites to the new `assemble` signature: `engine/src/threepowers/runner.py:309-319` (`CliAgentRunner.dispatch`) and `engine/src/threepowers/hosted.py:151-159` (`HostedAgentRunner.dispatch`) — replace `body=prompts.stage_template_body(self.settings.stage_templates_dir, step)` with `templates_dir=self.settings.stage_templates_dir` (variables threaded in Phase 3). Verify: both sites compile; a runner test asserts the CLI and hosted sites produce the identical assembled prompt for the same inputs. | ✅ | 2026-07-08 |
| TASK-009 | Delete the inline literals from `engine/src/threepowers/prompts.py`: `_PREAMBLE` (30-34), `_STAGE_PROMPTS` (37-101), `_GENERIC` (103), `_COMMIT_NOTE` (116-119). Keep `COMMIT_NOTE_STEPS` (data, not a prompt). Remove `stage_prompt_body` (now unused) OR reduce it to `return substitute(resolve_body(step, None), {"STEP": step})` if any caller still needs it — then remove that caller. Verify: `grep -nE "^_STAGE_PROMPTS|^_PREAMBLE|^_GENERIC|^_COMMIT_NOTE" engine/src/threepowers/prompts.py` returns nothing. | ✅ | 2026-07-08 |
| TASK-010 | Rewrite `engine/src/threepowers/steering.py:133-143` `revise_context(gate, artifact, feedback, templates_dir=None)` to load the body via `prompts.fragment_body("revise.agent.md", templates_dir)` and return `prompts.substitute(body, {"GATE": gate, "ARTIFACT": artifact or "the stage's artifact", "FEEDBACK": feedback.strip()})`. Update the one caller `engine/src/threepowers/cli/run.py:1233` to pass `templates_dir=s.stage_templates_dir`. Verify: `test_run_steering.py:823` (determinism) still passes; a new test asserts the revised block still names the gate, the artifact, and the feedback. | ✅ | 2026-07-08 |
| TASK-011 | Update `engine/src/threepowers/cli/run.py:568` (`_report_phase_estimates`) — `prompts.resolve_body("implement", s.stage_templates_dir)` still resolves (now bundled-backed); no change needed beyond confirming it returns the full body. Verify: a phase-estimate test asserts a non-empty implement body under an unseeded repo. | ✅ | 2026-07-08 |
| TASK-012 | Update the prompt-body tests to the file-sourced bodies: `engine/tests/test_phases.py:131-143` (replace `prompts.stage_prompt_body("plan"/"tasks"/"clarify")` with `prompts.resolve_body(..., None)` bundled bodies), `engine/tests/test_run_identity.py:220` and `engine/tests/test_oracle.py:482` (`stage_prompt_body("oracle")` → bundled `resolve_body`), and `engine/tests/test_stage_agents.py:136,146,161-162,226` (precedence assertions to the three-tier chain). Verify: `uv run pytest tests/test_phases.py tests/test_run_identity.py tests/test_oracle.py tests/test_stage_agents.py` green. | ✅ | 2026-07-08 |
| TASK-013 | Add a guard test in `engine/tests/test_prompt_templates.py` (or `test_oss_readiness.py`) that reads `prompts.py` and `steering.py` source and asserts no remaining multi-line dispatched-prompt string literal (e.g. no triple-quoted or concatenated block assigned to a `_*PROMPT*`/`_PREAMBLE`/`_GENERIC`/`_COMMIT_NOTE`/`REVISION` name). Verify: the guard passes and would fail if an inline body were reintroduced. | ✅ | 2026-07-08 |

### Phase 3

- GOAL-003: Turn the hardcoded destination placeholder prose into the `$FEATURE_FOLDER` and
  `$ORACLE_DESTINATION` variables and thread the real values through `assemble` and both dispatch
  sites (REQ-003), removing the separate `_feature_folder_context` / `_oracle_destination_context`
  context-block injection. Completion criterion: the oracle prompt carries the real
  `tests/oracle/<id>/` path and the write-stage prompts carry the real feature folder — with no
  `<feature>`/`<NNN>-<slug>` placeholder token in the assembled prompt; all gates green.

**File scope**: `engine/src/threepowers/prompts.py`; `engine/src/threepowers/runner.py`;
`engine/src/threepowers/hosted.py`; `engine/src/threepowers/cli/run.py`;
`engine/src/threepowers/scaffold/templates/agents/{specify,clarify,plan,implementation-plan,discovery,oracle}.agent.md`;
`engine/tests/test_run_identity.py`, `engine/tests/test_oracle.py`, `engine/tests/test_native_runner.py`.

**Depends on**: Phase 2.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-014 | Add an optional `variables: Optional[dict[str,str]] = None` parameter to `CliAgentRunner.dispatch` (`engine/src/threepowers/runner.py:294-302`) and `HostedAgentRunner.dispatch` (`engine/src/threepowers/hosted.py:138-150`), threading it into the `assemble(..., variables=variables)` call added in TASK-008. Also thread it through `_dispatch_phased`'s `backend.dispatch(...)` call (`engine/src/threepowers/cli/run.py:675`). Verify: a runner test passes `variables={"FEATURE_FOLDER":"specs-src/001-x"}` and asserts the token is substituted into the assembled prompt. | ✅ | 2026-07-08 |
| TASK-015 | In `engine/src/threepowers/scaffold/templates/agents/`, replace the placeholder destination prose with variables: in `specify.agent.md` (65-68), `clarify.agent.md`, `plan.agent.md` (82-85), `implementation-plan.agent.md`, `discovery.agent.md` (37-39) change the "default `specs-src/<feature>/…`" prose to reference `$FEATURE_FOLDER` (keep a human default sentence for the offline/empty case); in `oracle.agent.md` (57-59) replace `tests/oracle/<NNN>-<slug>/` with `$ORACLE_DESTINATION`. OSS-clean. Verify: `grep -rn '<feature>\|<NNN>-<slug>' engine/src/threepowers/scaffold/templates/agents/` returns nothing in the write-destination lines; `grep -rn '\$FEATURE_FOLDER\|\$ORACLE_DESTINATION'` matches the six files. | ✅ | 2026-07-08 |
| TASK-016 | In the `engine/src/threepowers/cli/run.py` dispatch closure (851-911) compute the destination values and pass them as `variables` to `backend.dispatch(...)` / `_dispatch_phased(...)`: `FEATURE_FOLDER` = the feature folder's repo-relative POSIX path (the value `_feature_folder_context` computed), `ORACLE_DESTINATION` = `tests/oracle/<feature_dir.name>/` (the value `_oracle_destination_context` computed). Remove the `_feature_folder_context`/`_oracle_destination_context` appends to `ctx_parts` (899-905); keep `prior_box["ref"]` and `revise` in `ctx_parts`. Delete the now-unused helper functions `_feature_folder_context` (731-747) and `_oracle_destination_context` (750-770), or repoint them to return the raw value used above. Verify: `grep -n "_feature_folder_context\|_oracle_destination_context" engine/src/threepowers/cli/run.py` shows no ctx_parts append. | ✅ | 2026-07-08 |
| TASK-017 | Update `engine/tests/test_oracle.py` and `engine/tests/test_run_identity.py`/`test_native_runner.py`: assert the oracle stage's assembled prompt contains the real `tests/oracle/<id>/` (substituted from `$ORACLE_DESTINATION`) and a write stage's prompt contains the real feature folder (from `$FEATURE_FOLDER`), and that no `<feature>`/`<NNN>-<slug>` placeholder survives. Verify: `uv run pytest tests/test_oracle.py tests/test_run_identity.py tests/test_native_runner.py` green. | ✅ | 2026-07-08 |
| TASK-018 | Full Track A gate: run `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine`; confirm an unseeded checkout (temporarily rename `.3powers/templates/agents/`) still assembles full prompts (bundled default). Verify: all green; a dry run `3pwr run "x" --dry-run` still renders. | ✅ | 2026-07-08 |

### Phase 4

- GOAL-004: Wire Discovery structurally as the first `action` step that always dispatches (gating
  comes in Phase 5): add it to `LIFECYCLE_STEPS`, give it an artifact contract and producing-step
  wiring, default `SpecState.stage` to `"Discovery"`, and confirm the note flows to Specify via
  `prior_box` (REQ-004, REQ-006). Completion criterion: a live/simulated run walks a Discovery step;
  a produced `specs-src/<f>/discovery.md` satisfies its contract; all gates green.

**File scope**: `engine/src/threepowers/orchestrate.py`; `engine/src/threepowers/artifacts.py`;
`engine/src/threepowers/workspace.py`; `engine/src/threepowers/lifecycle.py`;
`engine/src/threepowers/prompts.py`; `engine/tests/test_phases.py`,
`engine/tests/test_artifacts.py`, `engine/tests/test_run_workspace.py`,
`engine/tests/test_lifecycle.py`.

**Depends on**: Phase 3 (bundled default so the discovery body + `$FEATURE_FOLDER` resolve).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-019 | Insert `("discovery", "action", "Discovery")` at index 0 of `LIFECYCLE_STEPS` in `engine/src/threepowers/orchestrate.py:40`. Verify: `orchestrate.LIFECYCLE_STEPS[0] == ("discovery","action","Discovery")`; `orchestrate.step_index("specify") == 1`; `orchestrate.step_index("discovery") == 0`. | ✅ | 2026-07-08 |
| TASK-020 | Add a `discovery` contract to `STAGE_ARTIFACTS` in `engine/src/threepowers/artifacts.py:87`: `ArtifactContract(step="discovery", kind="path", expected="a discovery note (specs-src/<feature>/discovery.md)", patterns=(r"(^|/)specs(-src)?/.+/discovery\.md$",))`. Verify: `artifacts.verify(contract_for("discovery"), ["specs-src/001-x/discovery.md"]).ok is True` and an off-target path fails. | ✅ | 2026-07-08 |
| TASK-021 | Add `"discovery"` to `workspace.PRODUCING_STEPS` (`engine/src/threepowers/workspace.py:44`); confirm `step_filename("discovery")` returns `discovery.md` via the default branch (no `_STEP_FILENAMES` entry needed). Verify: `workspace.stage_artifact_path(fd, "discovery").name == "discovery.md"`; `"discovery" in workspace.PRODUCING_STEPS`. | ✅ | 2026-07-08 |
| TASK-022 | Add `"discovery"` to `COMMIT_NOTE_STEPS` in `engine/src/threepowers/prompts.py:108` so the discovery stage commit message is agent-authored (consistent with other producing stages). Verify: `"discovery" in prompts.COMMIT_NOTE_STEPS`; assembling the discovery prompt includes the commit-note fragment. | ✅ | 2026-07-08 |
| TASK-023 | Change `SpecState.stage` default from `"Spec"` to `"Discovery"` in `engine/src/threepowers/lifecycle.py:36`. Verify: `lifecycle.SpecState(spec_id="x").stage == "Discovery"`; `derive` folds a `run`/`stage` discovery record to `stage == "Discovery"` (existing `canonical_stage` path). | ✅ | 2026-07-08 |
| TASK-024 | Update `engine/tests/test_phases.py:868-874` LIFECYCLE_STEPS assertions to include the head discovery entry and keep the gate-list + `("implement","action","Build")` checks; add/adjust artifact-contract (`test_artifacts.py`), producing-step (`test_run_workspace.py`), and `SpecState` default (`test_lifecycle.py`) tests. Confirm `test_run_steering.py:685` and `test_progress.py:275` still pass. Verify: `uv run pytest tests/test_phases.py tests/test_artifacts.py tests/test_run_workspace.py tests/test_lifecycle.py` green. | ✅ | 2026-07-08 |

### Phase 5

- GOAL-005: Make Discovery run **only when needed** — deterministic work-kind gate plus a
  `--discovery`/`--no-discovery` override implemented as a short-circuit in the dispatch closure — and
  confirm an enabled discovery feeds Specify (REQ-005, CON-005). Completion criterion: a `feature`
  intent dispatches discovery and Specify's prompt names the note; a `defect` intent (or
  `--no-discovery`) short-circuits with `outcome="skipped"` and still reaches Specify; all gates
  green.

**File scope**: `engine/src/threepowers/workkind.py`; `engine/src/threepowers/runner.py`
(`StageResult.outcome` doc); `engine/src/threepowers/cli/run.py`;
`engine/tests/test_workkind.py`, `engine/tests/test_native_runner.py`,
`engine/tests/test_headless_run.py`, `engine/tests/test_run_steering.py`.

**Depends on**: Phase 4.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-025 | Add a pure `discovery_enabled(kinds: list[str], *, override: Optional[bool]) -> bool` to `engine/src/threepowers/workkind.py`: `override` wins when not None; else `True` iff any kind ∈ `{"feature","design"}` (so the default `["feature"]` runs; an all-`{defect,docs,chore,refactor}` set skips). Verify: unit tests — `["feature"]`→True, `["defect"]`→False, `["docs","chore"]`→False, `["design","chore"]`→True, `override=False`→False, `override=True`→True. | ✅ | 2026-07-08 |
| TASK-026 | Register `--discovery` / `--no-discovery` (a `BooleanOptionalAction` or paired flags resolving to `Optional[bool]` default `None`) on the `run` subparser in `engine/src/threepowers/cli/run.py`, and resolve the override into the `_native_runner` build. Verify: `3pwr run --help` lists both flags; parsing `--no-discovery` yields the override `False`. | ✅ | 2026-07-08 |
| TASK-027 | In the dispatch closure (`engine/src/threepowers/cli/run.py:851`), at the TOP, short-circuit a skipped discovery: `if step == "discovery" and not discovery_enabled(wk.kinds, override=discovery_override): return runnermod.StageResult(step=step, stage=stage, ok=True, outcome="skipped", detail="discovery skipped (work-kind)")` — before the pre-stage git hook, dispatch, artifact verify, recording, and commit, so nothing is written and `prior_box` is untouched (feature intent unaffected because it is enabled). Verify: a native-runner test with a `defect` intent records no `discovery.md`, appends no `run`/`stage` discovery entry, and the walk proceeds to `specify`. | ✅ | 2026-07-08 |
| TASK-028 | Document the new `outcome="skipped"` value on `StageResult` (`engine/src/threepowers/runner.py:78-80` docstring) and confirm `StageResult.as_dict()` carries it (existing `outcome` key — additive value only, PAT-002). Verify: a test asserts `--json` for a run with a skipped discovery is parseable and the verdict/gate `--json` bytes are unchanged. | ✅ | 2026-07-08 |
| TASK-029 | Add a feed-to-specify test: an enabled discovery run sets `prior_box["ref"]` to the `discovery.md` path (via existing `_prior_artifact_ref`) and the specify dispatch's assembled `context` (PRIOR CONTEXT block) names `discovery.md`. Also assert `_dispatch_spec_text("discovery", ...)` returns `""` (discovery precedes `review-spec`). Verify: `uv run pytest tests/test_native_runner.py tests/test_headless_run.py tests/test_workkind.py` green. | ✅ | 2026-07-08 |

### Phase 6

- GOAL-006: Split the `3pwr init` readiness summary onto one fact per line, leaving `--json`
  untouched (REQ-007, Track C). Completion criterion: init prints `language`/`adapter`/`default
  tier`/`autonomous default` on separate lines; `--json` byte-stable; all gates green.

**File scope**: `engine/src/threepowers/cli/bootstrap.py`; `engine/tests/test_init_experience.py`.

**Depends on**: none (independent).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-030 | Replace the single `·`-joined `lines.append(...)` at `engine/src/threepowers/cli/bootstrap.py:793-797` with four separate indented `lines.append("  language: …")`, `"  adapter: …"`, `"  default tier: …"`, `"  autonomous default: yes|no"` calls (keep the `(none — no adapter selected)` phrasing on the language line). Do not change the `--json` report dict (`bootstrap.py:768-781`). Verify: `grep -n " · " engine/src/threepowers/cli/bootstrap.py` shows the summary line is gone; the block still prints via `print("\n".join(lines))` at line 899. | ✅ | 2026-07-08 |
| TASK-031 | Update `engine/tests/test_init_experience.py` (and `test_init_wizard_and_brownfield.py` if it asserts the summary text): change any assertion matching the `·`-joined line to the one-per-line form; assert each fact is on its own line and the `--json` payload is unchanged. Verify: `uv run pytest tests/test_init_experience.py tests/test_init_wizard_and_brownfield.py` green; `3pwr init --yes | grep -E '^\s+(language|adapter|default tier|autonomous default):'` shows four lines. | ✅ | 2026-07-08 |

### Phase 7

- GOAL-007: Capture the real consumed (non-cached) tokens per stage across every backend — generalize
  `extract_usage`, add verified per-backend `usage` hints, and add the opt-in `usage_mode` (REQ-008,
  REQ-009, REQ-010, CON-004). Completion criterion: a Copilot run records a real number in
  `progress.md`/ledger/`--json`; extraction unit + per-backend fixture tests pass; the verdict bytes
  are unchanged whether or not usage is captured.

**File scope**: `engine/src/threepowers/agents.py`;
`engine/src/threepowers/scaffold/agents/{copilot,claude,codex,aider,opencode,copilot-hosted}.yaml`;
`engine/tests/test_agents.py`; `engine/tests/fixtures/usage/*.txt` (new);
`engine/tests/test_native_runner.py` / `engine/tests/test_progress.py`.

**Depends on**: none (independent; extends plan-033 Track H). Requires captured real transcript
samples per backend (D5).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-032 | In `engine/src/threepowers/agents.py` add a pure `_parse_count(raw: str) -> Optional[int]` handling plain integers, `,`/`_` separators, and abbreviated units (`629.8k`→629800, `1.2M`→1200000; case-insensitive), returning `None` on non-numeric. Verify: unit tests for `"629.8k"`, `"1.2M"`, `"29,500"`, `"9200"`, `"x"`→None. | ✅ | 2026-07-08 |
| TASK-033 | Generalize `_usage_from_regex` (`agents.py:146`) to sum ALL capture groups of the last match through `_parse_count` (so a pattern capturing `written` and `↓ output` yields their sum); keep the single-group behavior as the one-group case. Generalize `_usage_from_json` (`agents.py:126`) to accept either a single `field` (current) or a `fields: [dotted, …]` list summed, with an optional `subtract: [dotted, …]` (for cached) — all via `_parse_count`. Update `extract_usage` (`agents.py:160`) to route the extended hints. Keep the codex single-group regex working (regression). Verify: `test_agents.py` covers regex-sum, json-fields-sum, json-subtract, and the legacy single forms. | ✅ | 2026-07-08 |
| TASK-034 | Capture real transcript samples (D5) into `engine/tests/fixtures/usage/`: `copilot.txt` (the `Tokens ↑ …(… written) • ↓ …` summary), `claude.json` (`--output-format json` object with `usage.*`), `codex.jsonl` (`token_count` events), `aider.txt` (`Tokens: X sent, Y received`), plus `opencode.*` if it exposes usage. Verify: fixtures exist and contain the documented shapes. | ✅ | 2026-07-08 |
| TASK-035 | Add/repair per-backend `usage` hints in `engine/src/threepowers/scaffold/agents/*.yaml`, each matching REQ-008 (non-cached input + output) and verified against its fixture: **copilot.yaml** — regex capturing the `written` and `↓` numbers, summed (drop the false "no token summary" comment); **aider.yaml** — regex `Tokens:\s*([0-9.,kM]+)\s*sent,\s*([0-9.,kM]+)\s*received` summed (comment the cached-context caveat); **codex.yaml** — keep the text-total regex OR switch to json `token_count` per D4 (only if `usage_mode` adopted); **claude.yaml** — `strategy: json` `fields: [usage.input_tokens, usage.output_tokens]`, gated behind `usage_mode`; **opencode.yaml** — add the matching hint or document "unknown"; **copilot-hosted.yaml** — uncomment/adjust the `usage.total_tokens` json field. Verify: for each backend, `extract_usage(manifest, fixture_text)` returns the expected non-cached integer in a fixture test. | ✅ | 2026-07-08 |
| TASK-036 | Implement the opt-in `usage_mode` (D4, decision 12): a manifest field (e.g. `usage_mode: json`) that, when set, makes `agents.build_command` (`agents.py:75`) append the backend's structured-output flag (`--output-format json` for claude; `--json` for codex) so usage is extractable; default off preserves the live text stream. Verify: a unit test asserts `build_command` appends the flag only when `usage_mode` is set, and omits it by default. | ✅ | 2026-07-08 |
| TASK-037 | Add pipeline tests: a native-runner run with a fake dispatcher returning the copilot fixture text records the expected token count in the ledger `run`/`stage` payload, the `progress.md` Tokens cell (not `—`), and the stage `--json`; a backend returning no usage still renders `—`; the phased path sums per-phase tokens (`_dispatch_phased` + `progress.phase_tokens`). Determinism guard: verdict and gate `--json` bytes identical with usage present vs absent (extends plan-033 Track H guard). Verify: `uv run pytest tests/test_agents.py tests/test_native_runner.py tests/test_progress.py` green. | ✅ | 2026-07-08 |

### Phase 8

- GOAL-008: Land the docs for every track and run the full self-application verification — the
  dedicated final Verification phase (AGENTS.md). Completion criterion: docs updated with no internal
  ids; the full command matrix in §6/plan §Verification is green.

**File scope**: `docs/cli-reference.md`; `docs/concepts.md`; `CLAUDE.md`; `AGENTS.md`;
`engine/tests/test_oss_readiness.py`, `engine/tests/test_auto_docs.py` (only if a doc-structure test
requires it).

**Depends on**: Phases 1–7.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-038 | Update `docs/cli-reference.md`: the `3pwr run` section documents Discovery as the first (conditional) dispatched stage, the `--discovery`/`--no-discovery` flags and the work-kind default; add an "editing agent prompts" note (repo-local `.3powers/templates/agents/*.agent.md` override → bundled default) listing the variable vocabulary; add the token-accounting section (real consumed = non-cached input + output; per-backend support; opt-in `usage_mode`; appears in progress.md/ledger/`--json`). No internal ids (GUD-001). Verify: `uv run pytest tests/test_oss_readiness.py` green. | ✅ | 2026-07-08 |
| TASK-039 | Update `docs/concepts.md` (lifecycle: Discovery now runs when needed and feeds Specify; prompt templates are the one source of truth) and add a short note to `CLAUDE.md` / `AGENTS.md` where prompt assembly / templates are described. Keep free of internal ids. Verify: `uv run pytest tests/test_oss_readiness.py tests/test_auto_docs.py` green. | ✅ | 2026-07-08 |
| TASK-040 | Full verification matrix: `(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)`; `3pwr gate run --path engine`; `uv tool install --force ./engine`; `grep -nE 'STAGE: \|REVISION REQUESTED' engine/src/threepowers/prompts.py engine/src/threepowers/steering.py` (empty); `3pwr run "add a dashboard" --dry-run` (Discovery cell shown); `3pwr run "fix the crash" --no-discovery --dry-run`; `3pwr init --yes | grep -E '^\s+(language|adapter|default tier|autonomous default):'` (four lines). Verify: every command exits 0 / matches its expectation. | ✅ | 2026-07-08 |

## 3. Alternatives

- **ALT-001**: A third-party templating package (Jinja2) for substitution — rejected: it would add a
  runtime dependency (CON-006); `string.Template` covers named `$`-substitution and is stdlib.
- **ALT-002**: `str.format` for substitution — rejected: prompt prose commonly contains literal
  `{`/`}` (code, JSON), which `str.format` misinterprets; `$`-delimited `string.Template` is far safer
  against prose, and `safe_substitute` never raises (SEC-001).
- **ALT-003**: Keep INTENT/APPROVED SPEC/PRIOR CONTEXT/FILE SCOPE as template variables too —
  rejected: those carry untrusted spec/intent text (may contain `$`), and their deterministic
  omit-if-empty framing is worth keeping engine-side; only destination placeholders become variables.
- **ALT-004**: Gate Discovery by intent length / richness — rejected in the source plan in favor of
  the deterministic work-kind gate + flag (no fuzzy heuristic; reuses `workkind.classify`).
- **ALT-005**: Implement the Discovery skip by mutating `LIFECYCLE_STEPS` per run — rejected:
  the list is index-referenced by resume/ledger/tests (CON-005); a dispatch-closure short-circuit
  keeps indices stable.
- **ALT-006**: Force `--output-format json` on every backend to always get usage — rejected: it turns
  the live conversation into machine JSON; usage-only-in-JSON backends get an opt-in `usage_mode`
  instead (decision 12).

## 4. Dependencies

- **DEP-001**: Python stdlib `string.Template` (substitution) — no new package.
- **DEP-002**: The existing bundled `*.agent.md` templates and the `scaffold` seeding path
  (`scaffold.seed_stage_templates`) — the new fragments ride the same seeding.
- **DEP-003**: The plan-033 Track H token pipeline (`DispatchResult.tokens` → `StageResult.tokens` →
  ledger/progress/`--json`) — Track D only supplies the extraction that feeds it.
- **DEP-004**: Real captured transcript samples per backend (Copilot confirmed from the user's run;
  Claude/Codex/aider/opencode to be captured for fixtures — TASK-034).

## 5. Files

- **FILE-001**: `engine/src/threepowers/prompts.py` — bundled loader, `substitute`, `fragment_body`,
  three-tier `resolve_body`, rewritten `assemble`; deletion of all inline literals; discovery in
  `COMMIT_NOTE_STEPS`.
- **FILE-002**: `engine/src/threepowers/scaffold/templates/agents/{preamble,generic,commit-note,revise}.agent.md`
  — new fragment templates (front-matter, `role: fragment`).
- **FILE-003**: `engine/src/threepowers/scaffold/templates/agents/{specify,clarify,plan,implementation-plan,discovery,oracle}.agent.md`
  — destination placeholders → `$FEATURE_FOLDER` / `$ORACLE_DESTINATION`.
- **FILE-004**: `engine/src/threepowers/runner.py`, `engine/src/threepowers/hosted.py` — `assemble`
  call sites updated; `dispatch` gains `variables`; `StageResult` `outcome="skipped"` documented.
- **FILE-005**: `engine/src/threepowers/steering.py` — `revise_context` loads the revise template.
- **FILE-006**: `engine/src/threepowers/cli/run.py` — thread destination variables; remove the
  feature-folder/oracle-destination context blocks; `--discovery`/`--no-discovery`; discovery skip
  short-circuit; revise caller passes `templates_dir`.
- **FILE-007**: `engine/src/threepowers/orchestrate.py` — discovery head of `LIFECYCLE_STEPS`.
- **FILE-008**: `engine/src/threepowers/artifacts.py` — discovery artifact contract.
- **FILE-009**: `engine/src/threepowers/workspace.py` — discovery in `PRODUCING_STEPS`.
- **FILE-010**: `engine/src/threepowers/lifecycle.py` — `SpecState.stage` default `"Discovery"`.
- **FILE-011**: `engine/src/threepowers/workkind.py` — `discovery_enabled`.
- **FILE-012**: `engine/src/threepowers/cli/bootstrap.py` — one-fact-per-line readiness summary.
- **FILE-013**: `engine/src/threepowers/agents.py` — `_parse_count`, generalized `_usage_from_regex`/
  `_usage_from_json`/`extract_usage`, `usage_mode` in `build_command`.
- **FILE-014**: `engine/src/threepowers/scaffold/agents/*.yaml` — per-backend `usage` hints +
  `usage_mode`.
- **FILE-015**: `engine/tests/**` — updated + new tests (`test_prompt_templates.py`,
  `test_stage_agents.py`, `test_phases.py`, `test_run_identity.py`, `test_oracle.py`,
  `test_native_runner.py`, `test_headless_run.py`, `test_workkind.py`, `test_artifacts.py`,
  `test_run_workspace.py`, `test_lifecycle.py`, `test_init_experience.py`, `test_agents.py`,
  `test_progress.py`, `fixtures/usage/*`).
- **FILE-016**: `docs/cli-reference.md`, `docs/concepts.md`, `CLAUDE.md`, `AGENTS.md` — docs.

## 6. Testing

- **TEST-001**: `substitute` — supplied var renders; unfilled defined var → empty; `$$`→`$`; malformed
  `$` never raises; a `$` inside `spec_text`/`intent` is never substituted (SEC-001).
- **TEST-002**: `assemble` is byte-identical for fixed inputs (CON-003) and the CLI and hosted sites
  produce the same prompt.
- **TEST-003**: Loader precedence — unseeded repo resolves the full bundled body per stage (not the
  generic fragment); a repo-local override wins.
- **TEST-004**: Guard — no inline dispatched-prompt literal remains in `prompts.py`/`steering.py`.
- **TEST-005**: Destination variables — oracle prompt carries the real `tests/oracle/<id>/`; a write
  stage carries the real feature folder; no placeholder token survives.
- **TEST-006**: `LIFECYCLE_STEPS` head is discovery; indices/gate-list correct; the discovery contract
  matches `discovery.md` and rejects off-target; `SpecState().stage == "Discovery"`.
- **TEST-007**: `discovery_enabled` truth table (feature/design run; defect/docs/chore/refactor skip;
  override wins).
- **TEST-008**: A `feature` intent dispatches discovery, writes `discovery.md`, and Specify's PRIOR
  CONTEXT names it; a `defect` intent / `--no-discovery` short-circuits (`outcome="skipped"`, no file,
  no ledger stage entry) and reaches Specify.
- **TEST-009**: `--json` with a skipped discovery is parseable; verdict/gate `--json` bytes unchanged.
- **TEST-010**: init prints four separate fact lines; `--json` unchanged.
- **TEST-011**: `_parse_count` units; regex-sum and json-sum/subtract extraction; legacy single forms
  still parse (codex regression).
- **TEST-012**: Per-backend fixture → expected non-cached integer (copilot/claude/codex/aider[/opencode]).
- **TEST-013**: A run records the token count in `progress.md`/ledger/`--json`; unknown → `—`; phased
  path sums per-phase; determinism guard (verdict bytes unchanged with/without usage).
- **TEST-014**: OSS-readiness green over all new/edited templates and docs (no internal ids).

## 7. Risks & Assumptions

- **RISK-001**: Byte-drift in assembled prompts. Mitigation: keep context-block framing/order
  identical; TEST-002 asserts byte-identity; the only intended change is destination placeholders
  resolving to real values (explicitly asserted, TEST-005).
- **RISK-002**: A stray `$word` in template prose is dropped by `safe_substitute`. Mitigation: `$$`
  is the documented escape; a template lint test flags `$` tokens outside the vocabulary; extraction
  never raises.
- **RISK-003**: Unseeded-repo regression to the generic fallback. Mitigation: TEST-003 asserts the
  full bundled body for an unseeded repo (and Phase 8 exercises a renamed templates dir).
- **RISK-004**: Discovery insertion breaks resume/ledger indices. Mitigation: resume/segment math is
  computed from step ids against the live list; TASK-019 tests indices; a legacy-ledger resume test.
- **RISK-005**: A skipped discovery leaves a phantom artifact or trips the completion gate.
  Mitigation: the short-circuit returns before any write/verify/commit (TASK-027); TEST-008 asserts
  no file and no ledger stage entry.
- **RISK-006**: Per-backend token formats drift or aren't captured (TTY-only). Mitigation: every hint
  is verified against a captured fixture (TASK-034); extraction is `None`-safe (degrades to `—`);
  determinism guard proves the verdict is unaffected.
- **RISK-007**: The non-cached metric can't be isolated for a backend (aider `sent` includes cache).
  Mitigation: document the per-backend limitation; prefer structured counts where cached is split;
  accept the documented over-count only where nothing finer is exposed.
- **ASSUMPTION-001**: The Copilot `-p` token summary the user observed is in the captured
  stdout/stderr (it streamed through the run frame) — confirmed by capture into the transcript in
  Phase 7 before the hint is relied on.
- **ASSUMPTION-002**: `prompts.py` may compute its own bundled-templates path (no `scaffold` import) —
  confirmed: `scaffold` does not import `prompts`, so there is no cycle.

## 8. Related Specifications / Further Reading

- Source plan: [`plan/034-prompt-templates-and-discovery-stage.md`](034-prompt-templates-and-discovery-stage.md)
- Prior token-accounting work: [`plan/033-v1-readiness-and-lifecycle-hardening.md`](033-v1-readiness-and-lifecycle-hardening.md) (Track H) and [`plan/IMPLEMENTATION-004-feature-v1-readiness-and-lifecycle-hardening.md`](IMPLEMENTATION-004-feature-v1-readiness-and-lifecycle-hardening.md)
- Workflow & OSS-readiness rules: [`AGENTS.md`](../AGENTS.md), [`CLAUDE.md`](../CLAUDE.md)
- Public CLI surface: [`docs/cli-reference.md`](../docs/cli-reference.md)
- Backend token-report references (2026-07): Claude Code headless `--output-format json`
  (`code.claude.com/docs/en/headless`); GitHub Copilot CLI command reference
  (`docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference`); OpenAI Codex
  CLI `exec --json` `token_count` (`developers.openai.com/codex/cli/reference`); aider usage
  (`aider.chat/docs/usage.html`); opencode CLI (`opencode.ai/docs/cli/`).
