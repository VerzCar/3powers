# Plan 033 — v1.0 readiness: lifecycle artifacts, oracle traceability, run visibility, onboarding & release

**Git branch:** `feat/033-v1-readiness-and-lifecycle-hardening` — **created from `main`** (main was
clean at authoring). This plan file is committed on that branch.

**Covers fourteen tracks (A–N)** planned together as the coherent push to the **first stable
v1.0**. They are grouped because they all sharpen the same thing — the artifacts, records, and
onboarding a user *sees and trusts* as they drive `3pwr run` — and because v1.0 is the moment to
land the renames and the release in one deliberate pass rather than dribbling breaking changes.
Each track is independently deliverable and tested; the delivery order and dependencies are in the
table near the end.

The invariants that bound every track: **the deterministic verdict, the signed ledger's
verification, exit codes, and `--json` byte-stability never change** except where a payload gains a
strictly *additive* field (which `3pwr verify` already tolerates). Token accounting and per-phase
gate runs are **advisory** — a model never touches the verdict.

---

## Decisions recorded

Four were **confirmed by the user on 2026-07-08** via the planning questions, and the remaining
forks (oracle format, parallelism model, scanner granularity, RC scope, e2e) were **all resolved by
the user on 2026-07-08** (see Open Questions); the rest are engineering defaults proposed here. **No
open questions remain — the plan is finalized.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Plan structure | **One combined v1.0 plan (this file), tracks A–M** — user-confirmed. | A single coherent v1.0 push; the implementation-plan agent phases it, delivered as sequential units on the one branch (no PRs). |
| 2 | `changelog.md` authorship (Track B) | **Engine-generated** — user-confirmed. Deterministic render from the change set + the implement agent's completion report, replacing today's `implement.md` record. | Model-independent and reproducible; consistent with the existing engine-owned record path (`completion.render_implement_record`). |
| 3 | Oracle storage/record key (Track E) | **The run's feature-folder id `<NNN>-<slug>`** — user-confirmed. Tests under `tests/oracle/<NNN>-<slug>/`; every seal/record/dispatch/verify + `oracle.md` keyed the same. | Exactly matches the folder the user browses in `specs-src/`, so which oracle belongs to which spec is self-evident. |
| 4 | v1.0 release shape (Track L) | **Release candidate first, then `1.0.0`** — user-confirmed. Tag `1.0.0-rc.1`, let it settle / optionally close a residual, then cut `1.0.0`. | A clear "newly stable" signal; the RC absorbs any fallout from the renames before the durable tag. |
| 5 | Backward compatibility of renames (A, B, K) | **New writes use the new names/locations; read-resolution stays tolerant of the legacy `specs/`, `tasks.md`, `implement.md`.** | The repo already keeps legacy layouts readable; old signed ledger entries point at old paths and must keep resolving on disk (`completion.recorded_stage_artifacts`, resume re-checks). |
| 6 | Per-phase gate runs (Track C) | **Agent-run and advisory** — the build prompt makes the coding-gate run mandatory *for the agent*; the real Verify stage remains the sole ledger verdict. A mandatory **final verification phase** is added by the implementation-plan agent. | Keeps determinism (no model output in the verdict) while guaranteeing Verify is green because the agent already fixed everything inline. |
| 7 | Oracle `oracle.md` authorship (Track F) | **Authored by the oracle agent** as an **implementation-agnostic Tests Specification** (per FR/NFR Given/When/Then + property invariants + NFR metric/threshold/protocol), *in addition to* the runnable oracle test files. Engine validates coverage + no leaked paths. Format = the user's example, adapted to 3Powers. | The user supplied the exact `oracle.md` template on 2026-07-08; it stays free of filenames/frameworks so traceability comes from Track E's keyed destination + id-named tests, not from paths inside `oracle.md`. |
| 8 | Scanner-ignore config location (Track I) | **A new committed `.3powers/config/scan.yaml`** read by the core gate engine, with per-tool ignore globs; excluded paths are reported, never silently dropped. | The scanners are *core* gates that today read neither the adapter manifest nor `gates.yaml`; a dedicated file keeps the security-sensitive knob explicit and auditable. |
| 9 | Constitution version (Tracks L, M) | **Bump the constitution to `1.0.0`** alongside the engine, because Track M amends it. | The onboarding-guidance amendment is a substantive change; re-ratify it with the release. |

---

## Why now

1. **The artifacts a user sees don't match the vocabulary.** The tasks stage is produced by the
   *implementation-plan agent* yet writes `tasks.md`; the "Implement record" is an opaque
   engine file, not the changelog a human wants; the plan carries a "Judicial Plan" heading and a
   role→model-family table that duplicates `roles.yaml`. v1.0 is the point to make the outputs read
   the way the workflow talks.
2. **Oracle traceability is genuinely broken.** A `3pwr run` files its ledger records under the
   folder `NNN`, its oracle *test files* under the spec-document token (`DEMO`), and manual
   `oracle` commands under whatever `--spec-id` you type — three keys that don't line up
   (`cli/run.py:1697`, the un-interpolated `<spec-id>` placeholder in `prompts.py:82-88`,
   `cli/oracle.py:468`). And the `oracle.md` is a flat list of file paths with no
   requirement→test→justification mapping (`completion.render_oracle_record`). The judiciary is the
   product's thesis; its output must be legible.
3. **Sessions and cost are invisible.** The engine already spawns a fresh subprocess per stage and
   per phase, but there is no way to *prove* it and **no token accounting at all** — so a user who
   sees one long-lived Copilot session can't tell whether context is bleeding across stages.
4. **A real usability sting: scanners can't be told to ignore build caches.** betterleaks flags
   `generic-api-key` in `.next/cache/.rscinfo`, and there is **no config anywhere** to exclude a
   path from any scanner (`scanners.py:129-133`, no `--config`/ignore flag).
5. **Onboarding under-sells the constitution.** `init` seeds it non-destructively but prints no
   "adapt this — it's mandatory" guidance, and the file itself has no "how to update / what's
   mandatory" section. The constitution is where a project encodes *the how*; users need to be told
   to fill it in.
6. **It's the v1.0 boundary.** Renaming `specs/` → `specs-src/` and declaring the API stable are
   breaking-ish moves best done once, deliberately, at the version line.

---

## What's true today (grounded — the starting point every track builds on)

| Area | Current reality (evidence) |
|---|---|
| Tasks artifact | Hardcoded `tasks.md` in `workspace.py` (`PRODUCING_STEPS`, `stage_artifact_path`), the completion-gate contract in `artifacts.py`, `prompts.py`, both `.3powers/templates/{plan,tasks}-template.md`, the scaffold `implementation-plan.agent.md`, and ~143 tests. |
| Implement record | **Engine-generated** `implement.md` via `completion.render_implement_record`/`write_record` (`RECORD_STEPS=("oracle","implement")`), wired at `cli/run.py:889-912`, tracked by the completion gate + ledger. No `changelog.md` exists. |
| Per-phase validation | Soft "validate as you go" in `implement.agent.md`; no mandatory per-phase gate run, no required final verification phase. |
| Plan doc | `plan.agent.md` §4 "Judicial Plan" + `plan-template.md` "3Powers Judicial Plan" with a role→model-family table. The engine does **not** parse that table (diversity is from `roles.yaml`+`oracle record`). A conformance test binds the plan-template skeleton. |
| Oracle key | Three-way divergence (see Why-now #2). `referenced_ids(test_roots, spec_id)` drops refs whose namespace ≠ `spec_id` (`conformance.py:102`) — so keying by `NNN` breaks coverage against `DEMO-FR-*` req-ids. |
| `oracle.md` | Flat bullet list of test paths only (`completion.render_oracle_record`). |
| Sessions | Fresh subprocess per stage *and* per phase; no session/resume flag in any manifest; `copilot -p` one-shot; `[P]` phases concurrent via `ThreadPoolExecutor` (`runner.py:284-298`, `agents.py:65-96`, `phases.py:293-328`). The phase prompt already tells the agent to sub-dispatch `[P]` tasks (`phases.py:372-374`). |
| Tokens | None captured. Only a bytes→token *estimate* for budgeting (`phases.py:33,154-157`). `StageResult` has no token field (`runner.py:69-121`). |
| Scanner ignores | None. `secret_scan`/`dependency_scan`/`sast_scan` take only `target`(+changed scope), ignore `settings`/`gates.yaml`; betterleaks scans the whole tree (`scanners.py:105-171,174,208`). Core ed25519 walk has a hardcoded skip set (`scanners.py:72`) that excludes `.git/node_modules/.venv/__pycache__/dist/build` but **not** `.next`. |
| observability.yaml | NFR-instrumentation registry for `3pwr observe coverage`; only `checks[].nfr` is read (`observe.py:77-78`), `check:` is human doc; loaded inline in `cli/observe.py:97-103`; seeded by init. |
| `specs/` name | Hardcoded literal `root / "specs"` (no constant/config) in `workspace.py:101,124,176`; **critical regexes** in `artifacts.py:90,96,104` and `gitflow.py:58`; also `cli/run.py:1684`, `cli/brownfield.py:46`, `prompts.py`; scaffold agent prompts already say the never-matching `specs-source`; ~143 tests + 3 e2e notebooks; ledger history holds `specs/...` paths. |
| Version | `0.1.0` (`engine/pyproject.toml:3`, `engine/src/threepowers/__init__.py:17`); `SCHEMA_VERSION="1.1"` is separate. Constitution footer `0.1.0`. |
| Init/constitution | `scaffold.seed_constitution` copies the bundled `scaffold/constitution.md` non-clobbering (`scaffold.py:396-409`); readiness checklist shows a passive "constitution in place/seeded" line (`cli/bootstrap.py:99-105`) — no "adapt it" CTA. |

---

## Track A — Rename the tasks artifact to `implementation-plan.md`

### Problem
The implementation-plan agent produces `tasks.md`; the name no longer matches the agent or the
document ("an implementation plan"). The user wants the artifact renamed to
`implementation-plan.md`.

### Approach
Rename the tasks-stage artifact everywhere it is derived, contracted, prompted, templated, and
documented, keeping legacy `tasks.md` readable for old runs (decision 5).

- **Engine:** `workspace.stage_artifact_path` (the `tasks` → filename map) and `PRODUCING_STEPS`
  metadata; the `artifacts.py` `STAGE_ARTIFACTS` contract pattern for the tasks step; any
  `completion.py` step→file mapping; `prompts.py` tasks-stage body; the phased-execution reader
  that locates the tasks artifact to parse phases (`phases.py`) and the coverage/scope commands that
  read it (`cli/gate.py` coverage-check/scope-check, `conformance.py` if it names the file).
- **Read tolerance:** where the engine resolves the tasks artifact on disk, accept
  `implementation-plan.md` first, then fall back to `tasks.md` (legacy) — mirrors the existing
  legacy-layout tolerance.
- **Templates/prompts:** scaffold `implementation-plan.agent.md` (its front-matter `artifact:` and
  body — currently says `tasks.md`), `.3powers/templates/tasks-template.md` (rename its `Output`
  line; consider renaming the file to `implementation-plan-template.md` — **note** the conformance
  test binds this template as a document skeleton, so update that test in lockstep), and
  `plan-template.md`'s references.
- **Docs:** `docs/cli-reference.md`, `AGENTS.md`, `CLAUDE.md`, `getting-started.md`, `concepts.md`.

### Deliverables
New runs write `specs-src/<NNN>-<slug>/implementation-plan.md`; old `tasks.md` still resolves.

### Tests
Update the ~tasks-artifact tests (`test_phases.py`, `test_run_workspace.py`, `test_native_runner.py`,
`test_stage_agents.py`, artifact-contract tests) to the new name; add a regression test that a run
writing `implementation-plan.md` passes the completion gate and that a legacy `tasks.md` still
resolves. Template-skeleton conformance test updated.

---

## Track B — Replace the implement record with an engine-generated `changelog.md`

### Problem
The producing `implement.md` "Implement record" is opaque; the user wants a **changelog** for the
implementation, in the spec-id folder, and does not want the separate record.

### Approach
Repurpose the engine's record path (decision 2): rename the implement step's producing artifact from
`implement.md` to `changelog.md` and upgrade its renderer to a real changelog.

- **Engine:** in `completion.py`, replace `render_implement_record` output with a changelog
  renderer — grouped by phase, each entry tracing to its requirement id, listing the files changed
  and a one-line "what changed / why", sourced from the collected phase results + the implement
  agent's completion report (already parsed for the record). Update `RECORD_STEPS`/`stage_artifact_path`
  so the implement step's artifact is `changelog.md`; update `artifacts.py` contract + `workspace.py`.
- **Format:** Keep-a-Changelog-flavored per run (Added/Changed/Fixed where inferable from work-kind),
  with a machine-parseable requirement-id column so it stays traceable. Deterministic given the
  inputs.
- **Implement agent prompt:** add an instruction to include, in its completion report, a concise
  per-change summary the engine folds into the changelog (so the prose is good without the agent
  owning the file).
- **Read tolerance:** resolve `changelog.md` first, `implement.md` legacy fallback.
- **Top-level `CHANGELOG.md` is untouched** — it stays hand-maintained (Track L edits it for the
  release).

### Deliverables
New runs write `specs-src/<NNN>-<slug>/changelog.md`; the old `implement.md` record is gone for new
runs, still readable for old ones.

### Tests
`test_run_workspace.py`/completion tests updated; a new test asserts the changelog groups by phase,
carries each phase's requirement ids and changed files, and is byte-deterministic for a fixed input.

---

## Track C — Run the coding gates after every build phase + a mandatory final verification phase

### Problem
Errors surface at the Verify stage that could have been fixed during the build. The user wants the
coding-section gates run after each phase (agent fixes inline), and the implementation plan to always
end with a verification phase that leaves build/lint/tests green.

### Approach (decision 6 — agent-run, advisory; Verify stays the verdict)
- **implementation-plan agent** (`implementation-plan.agent.md`): add two rules — (1) every phase's
  tasks include running the coding-section gates (format, lint, types, tests + diff-coverage) over
  the phase's file scope and fixing failures before the phase is "done"; (2) the **last phase is
  always a dedicated "Verification" phase** whose goal is a fully green `format`+`lint`+`types`+`tests`
  (build) run across the change, depending on all prior phases. Name the engine command
  (`3pwr gate run --path <scope>`) *and* the project's own verify commands as acceptable ways to run
  them.
- **implement agent** (`implement.agent.md`): promote "validate as you go" from soft to
  **mandatory** — after each phase, run the coding gates (engine or project scripts) and fix
  everything before reporting `done`; a phase with a red coding gate is not complete.
- **Phase prompt** (`phases.py handoff_context`): inject the concrete coding-gate command for the
  project so the fresh session knows exactly what to run.
- **No verdict change:** the per-phase runs are the agent's own checks; the Verify stage still
  records the one signed verdict. This is why the outcome is "Verify is already green".

### Deliverables
Every generated implementation plan ends with a Verification phase; the build prompt mandates
per-phase gate runs; the tasks/plan templates document the pattern.

### Tests
`test_stage_agents.py`/template-content tests assert the new instructions are present; a plan-shape
test asserts a generated implementation plan carries a final verification phase depending on all
others. (No engine-logic test — this is prompt/template behavior.)

---

## Track D — Plan artifact: drop the "Judicial" label and remove the role→model-family table

### Problem
The plan's "Judicial Plan" section is really just the plan; the role (model-family) table duplicates
`roles.yaml` and the user wants it removed.

### Approach
- **`plan.agent.md`:** rename §4 "Judicial Plan" to a neutral heading (e.g. fold "Tier & gates"
  into the plan body as "Risk tier & gates"); **delete** the "Role → model-family" subsection and
  the output-skeleton table; drop the "Roles: coder/oracle/reviewer" line from the completion
  report. Keep the tier→gates content and the requirement→phase coverage.
- **`plan-template.md`:** same edits — remove the "3Powers Judicial Plan" heading and the
  "Role → model-family assignment" table; keep risk tier & gates, the Phase-A oracle intent table
  (that's legitimate planning), phase decomposition, structure.
- **Conformance:** the plan-template skeleton is bound by a conformance test — update it in lockstep.
- **No engine logic changes** (the table was never parsed); diversity enforcement via `roles.yaml`
  + `oracle record` is untouched.

### Deliverables
Plans no longer emit a role→model-family table or a "Judicial" label; the section reads as the plan.

### Tests
Template-skeleton conformance test + any `test_stage_agents.py` assertions on the plan sections
updated; a test asserts the role→model-family table is absent from the plan template.

---

## Track E — Oracle keyed by the run's `<NNN>-<slug>` everywhere

### Problem
The three-way key divergence (Why-now #2) makes it impossible to tell which oracle belongs to which
spec, and breaks `oracle verify`/coverage across `3pwr run` vs manual `oracle` commands.

### Approach (decision 3 — unify on `<NNN>-<slug>`)
- **Run dispatch:** stop shipping a literal `<spec-id>` placeholder to the oracle agent. Compute the
  concrete destination `tests/oracle/<NNN>-<slug>/` and inject it into the oracle prompt (an explicit
  destination/file-scope block, the way `oracle dispatch` already re-keys), so a `3pwr run` oracle
  lands under the feature-folder id, not the spec-document token.
- **Records:** in the run path, key `oracle seal`/`record` (and `dispatch`) by the same
  `<NNN>-<slug>` used for the run's ledger/records, so seal ↔ record ↔ verdict ↔ `oracle.md` all
  share one key.
- **Decouple the requirement namespace from the storage key:** coverage's
  `referenced_ids(test_roots, spec_id)` must filter req-ids by the **spec document's Spec ID**
  (parsed from `spec.md` frontmatter, e.g. `DEMO`) while the *storage/record* key is the folder id —
  otherwise keying by `NNN` drops every `DEMO-FR-*` reference (`conformance.py:102`). This is the
  crux fix: separate "where it's filed" from "what namespace its requirements use".
- **Manual `oracle` commands:** keep `--spec-id` but make it default to the run's feature-folder id
  when invoked inside a run/feature context, and document that the id is the `<NNN>-<slug>` folder
  name for traceability.
- **Back-compat:** old oracle records keyed by other tokens still verify; only new runs adopt the
  unified key.

### Deliverables
A `3pwr run` writes oracle tests to `tests/oracle/<NNN>-<slug>/`, and seal/record/verify/`oracle.md`
all resolve under that one id; `oracle verify` on a run's spec id finds seal, record, verdict, and
coverage consistently.

### Tests
`test_oracle_dispatch.py` + oracle-independence/coverage tests: a run keys destination and records by
`<NNN>-<slug>`; coverage counts `DEMO-FR-*` refs correctly under a numeric folder key; `oracle verify`
green end-to-end from a single id. Trust-spine coverage held (oracle records touch signed entries).

---

## Track F — An authored, verifiable `oracle.md` (the Tests Specification)

### Problem
`oracle.md` is a flat path list; the user needs a document a human *and* a machine can read that
states, per requirement, the measurable acceptance test and why — the trackable law the later
stages are judged against. The runnable oracle tests are still created; `oracle.md` is added
alongside them.

### Approach (decision 7 — oracle agent authors `oracle.md`; runnable tests unchanged; engine validates)
Merge the user's supplied instruction into `oracle.agent.md` as one instruction, adapted to 3Powers
conventions. The **existing** behavior (authoring the runnable red-phase oracle test files) is kept;
`oracle.md` is a **new, implementation-agnostic** artifact authored *first*, from the sealed spec
only.

The merged oracle stage does, in order:

1. **Load the law.** Read the sealed spec-only bundle (the `APPROVED SPEC` block). Extract every
   `FR-###`/`NFR-###` and its measurable acceptance criteria. Read the project's risk-tier
   thresholds from `.3powers/memory/constitution.md` and `.3powers/config/risk-tiers.yaml` (NOT the
   old `.specify/` path in the raw example).
2. **Refuse on weak law.** If any FR/NFR lacks a measurable AC, or uses vague language ("fast",
   "intuitive", "robust") instead of numbers/units/observable outcomes, list them under **Open
   Questions for the Legislature** and STOP — route back to `clarify`, invent no thresholds. (This
   promotes the existing "unmeasurable criterion is a finding" to a hard stop.)
3. **Author `oracle.md`** using the user's Tests-Specification template — one section per FR/NFR
   tagged with its id; Given/When/Then criterion; `type: acceptance | property | performance`; a
   property invariant where input is parsed/validated/transformed; metric/threshold/boundary/
   measurement-protocol for NFRs with numeric thresholds; a "Notes for executor" line stating what
   the test must NOT assume about the implementation; a High-risk mutation flag; and a Coverage
   Summary. **No filenames, frameworks, library calls, or source paths may appear in `oracle.md`.**
4. **Author the runnable oracle test files** implementing that specification — the existing red-phase
   behavior — named with the requirement id, in the project's native framework, written to Track E's
   destination `tests/oracle/<NNN>-<slug>/`. (Traceability of which oracle belongs to which spec
   comes from this keyed destination + the id in each test name — *not* from paths inside
   `oracle.md`.)
5. **Self-check:** every `FR/NFR` id in the spec appears in `oracle.md`; no implementation detail
   leaked into `oracle.md`; no vague language survived; each criterion has ≥1 runnable test named
   with its id. Print the completion report from computed values — run no shell command after
   writing.

Also strip the Spec-Kit residue from the raw example when merging: no `$ARGUMENTS`/"user input"
block, no "Extension hooks", no `.specify/`, no `tests.md` (the artifact is `oracle.md`) — per the
repo's template convention. Keep the isolation rules from the current `oracle.agent.md` (author from
the sealed spec only; never read implementation/plan/tasks/contracts).

**Engine (`completion.render_oracle_record`)** becomes a *validator*, not the author: if the agent
wrote `oracle.md`, verify it names every `FR/NFR` id from the spec and contains no leaked file paths
(a simple path/framework heuristic), and leave it in place; if it is absent, fall back to a generated
structural stub from the sealed bundle (`requirement_id → criterion`) with the sections marked "not
authored" so the gap is visible, never silently passed. The engine's machine record of the actual
oracle test paths stays in the ledger (`oracle record` `test_paths`), keeping `oracle.md`
path-free.

### `oracle.md` shape (the merged template, 3Powers-adapted)
```markdown
# Tests Specification — Feature: <feature>

> Authored by the judiciary. Derived ONLY from the approved spec.
> Never reference implementation files, frameworks, or source paths here.

## Coverage Summary
- Requirements in spec: <count>   - Covered here: <count>   - Open questions: <count>

## Acceptance Tests
### Test for DEMO-FR-001
- **Source AC:** spec §DEMO-FR-001
- **Type:** acceptance | property | performance
- **Criterion (Given / When / Then):** Given … / When … / Then …
- **Property invariant (if applicable):** …
- **Notes for executor:** what the test must NOT assume about the implementation.

### Test for DEMO-NFR-001
- **Source AC:** spec §DEMO-NFR-001   - **Type:** performance
- **Metric / Threshold / Boundary:** …   - **Measurement protocol:** …

## Open Questions for the Legislature
List any AC that is not measurable as written. STOP and route these back to `clarify`.
```

### Deliverables
`specs-src/<NNN>-<slug>/oracle.md` is a per-requirement, implementation-agnostic Tests Specification
authored by the oracle agent; the runnable oracle tests still land under `tests/oracle/<NNN>-<slug>/`;
the engine validates coverage and path-freeness.

### Tests
An oracle-stage test asserts `oracle.md` has a section per `FR/NFR` id, carries Given/When/Then (and
metric/protocol for NFRs), and contains no file path / framework token; a missing id or a leaked path
is flagged; an unmeasurable-AC spec produces the "Open Questions for the Legislature" stop, not
invented tests. Isolation test (reads only the sealed spec) preserved.

---

## Track G — Guarantee (and prove) a fresh session per stage & phase; make `[P]` sub-agent dispatch explicit

### Problem
The engine already starts a fresh subprocess per stage/phase, but the user observed one continuous
Copilot session — almost certainly the **Copilot CLI reusing its own session state**, not the
engine. The user wants it MANDATORY that every stage and every phase starts clean (0 carried
context), and the build prompt to instruct sub-agent parallel execution.

### Approach
- **Investigate the backend session behavior:** determine whether `copilot -p` (and the other
  headless CLIs) resume a prior conversation/context by default. If a backend can carry context,
  add a per-manifest capability to force a clean session — e.g. a `fresh_session`/`new_session_args`
  field in the agent manifest (`agents.py build_command`) that passes the CLI's "no-resume / new
  session" flag, or isolates per-dispatch state (unique session id / clean state dir) — so freshness
  is enforced, not assumed.
- **Prove it:** a test asserts `build_command` never emits a resume/continue/session-reuse flag and
  that each dispatch is an independent process (extends the existing runner tests). Track H's token
  accounting makes freshness *observable* to the user (each stage/phase starts at 0).
- **Explicit sub-agent parallelism:** strengthen the phase/implement prompt
  (`phases.py handoff_context` + `implement.agent.md`) to state plainly that `[P]`-marked parallel
  work defined in the implementation plan must be executed via the agent's own sub-agents. Keep the
  engine's existing concurrent dispatch of disjoint `[P]` *phases* as separate sessions.
- **Docs:** document the fresh-session guarantee and the sub-agent parallelism in
  `docs/concepts.md`/`engine-architecture.md`.

### Deliverables
A documented, tested guarantee that each stage and phase is a clean session, with a backend hook to
force it where a CLI would otherwise resume; the build prompt explicitly delegates `[P]` work to
sub-agents.

### Tests
`test_native_runner.py`/`test_phases.py`: no session-reuse flag; independent processes; prompt
contains the sub-agent instruction. Any new manifest field has adapter/round-trip tests.

---

## Track H — Persist per-stage and per-phase token consumption

### Problem
No usage/cost is recorded anywhere; the user wants each stage's token consumption persisted.

### Approach (additive, never in the verdict)
- **Capture:** parse the agent CLI's reported usage in `CliAgentRunner.dispatch` (and
  `HostedAgentRunner.dispatch`) — where the captured stdout/stderr already live — via a per-backend
  extraction strategy declared in the manifest (a `usage` hint: a JSON field name or a regex over the
  agent's own summary), returning `None` gracefully when a backend doesn't report it.
- **Thread it:** add token fields to `DispatchResult` → `StageResult` (`runner.py:58-121`) and its
  `as_dict()` for `--json`.
- **Persist to three places:** (1) the `run`/`stage`, `run`/`phases`, and `run`/`checkpoint` ledger
  payloads as **additive** fields (verify stays green — the existing tolerance); (2) a token column
  in the per-stage/per-phase tables of `progress.md` (`progress.py`); (3) the `StageResult` `--json`.
- **Determinism guard:** tokens never enter `run_gates`, the verdict, or the verdict bytes; a test
  asserts the verdict/`--json` gate payloads are unchanged whether or not usage is captured.
- **Docs:** document where per-stage tokens appear (`docs/cli-reference.md` run section, progress.md
  description).

### Deliverables
Each stage/phase shows tokens consumed in `progress.md`, the ledger, and `--json`; "unknown" when the
backend doesn't report.

### Tests
Extraction unit tests per strategy (regex/JSON + unknown); a run records tokens in progress.md and
the stage ledger payload; `3pwr verify` green over the new payloads; verdict bytes unchanged.

---

## Track I — Configurable per-tool ignore paths for the verdict-gate scanners

### Problem
betterleaks flags secrets in build caches like `.next/cache/.rscinfo`, and there is no way to exclude
a path from any scanner.

### Approach (decision 8 — a dedicated, auditable config)
- **New config `.3powers/config/scan.yaml`** (seeded by `init`, committed, shared): per-tool ignore
  globs **plus** optional per-finding-rule suppression (user Q3 = the recommended granularity), e.g.
  ```yaml
  version: 1
  # per-tool path/dir/file globs to exclude from scanning
  secret_scan:
    ignore: ["**/.next/**", "**/dist/**", "**/build/**", "**/node_modules/**"]
    ignore_rules: ["generic-api-key"]      # optional: suppress a specific finding rule id
  dependency_scan: { ignore: [] }
  sast:            { ignore: ["**/vendor/**"] }
  ```
  A **small sensible default ignore set** ships in the seeded template (common build-cache/vendor
  dirs — `.next`, `dist`, `build`, `node_modules`), so the reported `.next/cache/.rscinfo` case is
  handled out of the box while staying visible and editable. Read by the core gate engine (a new
  `Settings` accessor in `config.py`).
- **Thread through** `gates.py:547-559` into each scanner call; extend `secret_scan`/`dependency_scan`/
  `sast_scan` signatures (`scanners.py:105,174,208`) with an `ignore` list and build the tool
  exclusion: semgrep `--exclude <glob>` (native, repeatable); betterleaks/gitleaks via a generated
  ignore/`--config` allowlist or path pre-filter; osv-scanner via config/path filtering. Also honor
  the ignore set in the always-on core ed25519 walk skip logic (`scanners.py:62-102`).
- **Security discipline:** excluded paths are **reported** in the gate output (so an exclusion is
  never invisible), the exclusion is deterministic given the config, and the core private-key check
  still runs. Document that broad ignores weaken the gate.
- **Docs:** a `scan.yaml` section in `docs/cli-reference.md` + a `gate config`/scanning note.

### Deliverables
A user can exclude a path/dir/file per scanner via `scan.yaml`; the `.next/cache` false positive is
suppressible; exclusions are visible in output.

### Tests
Per-scanner: an ignored path is excluded, a non-ignored finding still fails, the exclusion is
reported; malformed/absent `scan.yaml` falls back to no-exclusions; the core ed25519 check still
fires. Determinism preserved.

---

## Track J — Document `observability.yaml`

### Problem
The user doesn't know why `observability.yaml` exists or what to configure.

### Approach (doc-only)
- Improve the file's own header comments (bundled `scaffold/config/observability.yaml` + this repo's
  copy) to explain: it's the **NFR-instrumentation registry** for `3pwr observe coverage`; list each
  NFR that has a live production check under `checks:` with its `nfr:` id (matching your spec) and a
  human `check:` note; the engine is offline so it can't discover this itself; running
  `observe coverage --spec <spec.md>` flags any NFR with no registered check.
- Add a short "Observability registry" subsection to `docs/cli-reference.md` (near `observe
  coverage`) and `docs/concepts.md`.
- Confirm the shipped template uses the reserved `DEMO-NFR-###` example namespace (OSS-readiness).

### Deliverables
Clear in-file and docs explanation of the file's purpose and schema.

### Tests
`test_oss_readiness.py`/`test_auto_docs.py` stay green; no code change.

---

## Track K — Rename `specs/` → `specs-src/`

### Problem
The user wants the run-artifact base folder renamed to `specs-src`. It's a hardcoded literal in a few
functional spots plus a critical pair of regexes, and there's a pre-existing `specs-source`
inconsistency in the scaffold prompts.

### Approach (decision 5 — new writes to `specs-src`, legacy `specs/` still resolves)
- **Introduce a constant** `SPECS_DIR = "specs-src"` in `workspace.py` and replace the literals at
  `workspace.py:101,124,176` (+ message strings) and `cli/run.py:1684`, `cli/brownfield.py:46`
  (default), `characterize.py` allocation.
- **Fix the critical regexes** to match the new base (and keep matching legacy `specs/` for
  resolution/back-compat): `artifacts.py:90,96,104` (`STAGE_ARTIFACTS` — else every specify/plan/tasks
  stage reports `artifact_missing`) and `gitflow.py:58` (`_PROGRESS_FILE` — else the clean-start guard
  misfires on `specs-src/.../progress.md`).
- **Reconcile the scaffold inconsistency:** the 8 scaffold agent prompts currently say `specs-source`
  and the templates say `specs/` — set them all to `specs-src` (`prompts.py:43,53,68`, scaffold
  `*.agent.md`, `plan-template.md`, `tasks-template.md`, constitution line 17).
- **Physically move** the repo's own `specs/` → `specs-src/` (`git mv`), and reinstall the engine.
- **Ledger history:** old entries keep their `specs/...` paths; read-resolution must find either base
  so `resume`/`recorded_stage_artifacts`/completion re-checks still resolve old runs. No ledger
  rewrite.
- **Docs + e2e:** update `docs/**`, top-level md (`AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`,
  `README`), and the 3 e2e notebooks' functional globs (`run.ipynb:222,278`).

### Deliverables
New runs allocate `specs-src/<NNN>-<slug>/`; the repo's specs live under `specs-src/`; old `specs/`
paths still resolve.

### Tests
The ~143 test references updated to `specs-src`; add a back-compat test that a legacy `specs/` layout
still resolves; artifact-contract + gitflow regex tests updated; e2e notebooks updated.

---

## Track L — Cut the first stable v1.0 (RC → 1.0.0)

### Problem
The user wants this to be the first stable v1.0.

### Approach (decision 4 — RC first; no residual blocks the release)
**No STATUS residual is closed before 1.0** (user, 2026-07-08): the maintainer verifies everything
manually and we cut 1.0 anyway. The RC exists only to absorb fallout from the renames, not to gate a
residual.
- **Version bump:** `engine/pyproject.toml:3` and `engine/src/threepowers/__init__.py:17` → `1.0.0`
  (RC path: `1.0.0-rc.1` first, then `1.0.0`). Leave `SCHEMA_VERSION` unless a schema changed.
- **Constitution:** bump its footer to `1.0.0` and re-ratify (decision 9), together with Track M's
  amendment.
- **Docs:** `docs/STATUS.md` milestone → v1.0 (RC/released), with the residuals section reframed as
  **accepted post-1.0 residuals** (cross-platform NFR-003, fuller A3, live design/Go runs, catalog
  publishing, model-driven eval); `README.md` milestone line; `docs/getting-started.md` `--version`
  example.
- **CHANGELOG.md:** move `[Unreleased] — v1.0 (in progress)` to `## [1.0.0]` (via `1.0.0-rc.1`),
  summarize plans 023–033, update the compare/tag links.
- **Release checklist:** all gates green self-applied at High-risk on the trust spine; `3pwr verify`
  green; `uv tool install --force ./engine` smoke; tag on `main` after the RC settles (per branch
  discipline — no PR).
- **Test fixups:** `test_oss_readiness.py:263-264` (`0.5.0` → `1.0.0` tag/changelog asserts) and
  `test_auto_docs.py:65` (version string).

### Deliverables
`3pwr --version` reports `1.0.0`; STATUS/README/CHANGELOG/constitution reflect the stable release;
tags `1.0.0-rc.1` then `1.0.0` on `main`.

### Tests
Version/changelog asserts updated; full self-application green; a fresh `3pwr init` smoke.

---

## Track M — Init constitution advisory + adaptation guidance

### Problem
`init` doesn't tell users the constitution is mandatory and must be adapted, and the file has no
guidance on how to update it or what mandatory content it needs — especially the *technical* parts
and the policies/rules (the "how" the user delegates to the constitution while they work on the what
and why).

### Approach
- **Init CTA:** add a prominent post-init advisory (in `cli/bootstrap.py`'s onboarding output, and
  the readiness-checklist line) that the constitution at `.3powers/memory/constitution.md` is
  **mandatory** and **must be adapted to this project before the first real run** — pointing at the
  guidance section below. Surfaced both interactively and in `--json` next-steps.
- **Guidance in the constitution template** (bundled `scaffold/constitution.md` + this repo's copy):
  add a top "How to adapt this constitution" block and a **mandatory-content checklist** the project
  must fill, especially the **technical baseline** and **policies/rules** — because a spec-driven run
  keeps the *how* out of specs, the *how* must live here. Draft content to include:
  - **Technical baseline (the "how"):** the language(s)/runtime + versions; the build/test/lint/type
    toolchain and the exact commands the coding gates run; the project layout and module boundaries;
    architectural rules and patterns to follow (and anti-patterns to avoid); dependency policy;
    coding standards and naming; the testing conventions and coverage/mutation expectations per tier;
    documentation expectations.
  - **Policies & rules:** the risk-tier defaults and thresholds this project uses; security/privacy
    rules (what agents may never touch without human approval — credentials, access control,
    hard-deletes, security config); the branch/commit/PR discipline; the definition of done; the gate
    non-weakening rule; the oracle-independence and traceability rules the project commits to.
  - **What stays fixed:** the separation-of-powers principles (I–VII) are the framework's law — a
    project adapts the *technical* and *policy* specifics, not the branch structure.
  - **How to update:** edit the file, bump its version footer, and (for a governed repo) record the
    amendment; note that changing an approved/sealed constitution may trip `spec_integrity`/
    `gate_gaming` and require a re-seal or a signed deviation.
- **Advisory text** (draft, to be refined): a short, strong paragraph for init output, e.g. *"Your
  constitution is the law every run answers to — it's where your project's* how *lives (stack,
  toolchain, architecture, security policy, coding & testing standards) so your specs can stay about*
  what *and* why*. The seeded file is a starting point: open* `.3powers/memory/constitution.md` *and
  fill in the technical baseline and policies for this project before your first `3pwr run` — an
  unadapted constitution means the judiciary is judging against someone else's rules."*

### Deliverables
`init` prompts the user to adapt the constitution; the constitution ships with an adaptation guide +
mandatory-content checklist covering the technical parts and policies.

### Tests
`test_init_experience.py`/`test_init_wizard_and_brownfield.py`: init output/next-steps mention
adapting the constitution; the seeded constitution contains the guidance section and checklist;
OSS-readiness stays green (no internal spec IDs in the shipped text).

---

## Track N — e2e notebook-kit adaptations

### Problem
The per-adapter e2e Jupyter notebooks drive the whole lifecycle in a sandbox and must keep passing.
The user asked whether this plan requires e2e changes — it does, but narrowly.

### What actually breaks vs. what is safe (from inspecting the 3 notebooks + harness)
- **Breaks — the rename (Track K).** All three notebooks glob `SANDBOX_DIR / "specs"`:
  `python-inventory/run.ipynb`, `typescript-orders/run.ipynb`, `go-ratelimit/run.ipynb` — cell 7
  (`(SANDBOX_DIR/"specs").glob("*/spec.md")`, ~line 221) and cell 9 (feature-dir glob, ~line 279),
  plus the `# writes the spec to specs/<NNN>-<slug>/` comments. These must become `specs-src`.
- **Safe — Tracks A/B (artifact renames).** The notebooks assert only that `spec.md` exists and a
  feature dir is present, plus a behavioral `grep`; they never assert on `tasks.md`/`implement.md`,
  so `implementation-plan.md`/`changelog.md` don't break them.
- **Safe — Tracks E/F/G (oracle/session).** No notebook asserts oracle paths or session behavior.
- **Safe — Track H (tokens) & status/JSON.** Cell 9 parses `3pwr status --json` with `.get()` and
  the verdict JSON defensively; additive token fields don't break it. A guard test confirms the
  status/verdict JSON the notebooks read stays additive.
- **Safe — Tracks I/M (scan.yaml / constitution CTA).** The harness overlays only `roles.yaml`
  (`e2e/harness/bootstrap.py`); the seeded `scan.yaml` + constitution guidance arrive via `3pwr
  init` and are not asserted on. Confirm no sample project trips `secret_scan` under the new default
  ignore set (it shouldn't — the samples have no build cache).
- **Safe — Track L (v1.0).** Notebooks don't check the engine version; the `e2e/harness` and sample
  project versions are independent demo versions and are **not** bumped.

### Approach
- Update the `specs` → `specs-src` glob + comment in all three notebooks (cells 7 and 9), as part of
  the Track K commit.
- Re-run `./e2e/run.sh <typescript|python|go> --check` (deterministic, no-agent) for all three to
  confirm the sandbox lifecycle stays green after the rename; note the full agent-driven path needs a
  headless CLI and is run manually by the maintainer.
- Leave `e2e/config/roles.yaml`, `e2e/harness/*`, and the sample lockfiles unchanged.

### Deliverables
The three notebooks pass `--check` after the rename; no other e2e change is required.

### Tests
`./e2e/run.sh <lang> --check` green for all three adapters; the additive-JSON guard test (with
Track H) protects the notebooks' `status`/verdict parsing.

---

## Delivery order and dependencies

Delivered as sequential units on the one feature branch — **no pull requests** (AGENTS.md/CLAUDE.md).
Engine changes go through the **python-engineer agent**; each unit lands green (ruff/mypy/pytest +
self-application) before the next.

| Track | Depends on | Risk | Effort |
|---|---|---|---|
| K — `specs/`→`specs-src/` | none (do early to cut later churn) | Medium (breadth: regexes, 143 tests, ledger back-compat) | Medium |
| N — e2e notebook adaptations | K | Low | Small |
| A — tasks→implementation-plan | K (paths) | Low–Medium | Small–Medium |
| B — changelog.md | K | Medium | Medium |
| D — plan doc de-judicial | none | Low | Small |
| C — per-phase gates + final verify phase | A (implementation-plan template) | Low | Small |
| E — oracle key unification | K | Medium (coverage namespace decoupling) | Medium |
| F — authored oracle.md | E, **user's example** | Medium | Medium |
| G — fresh-session guarantee + subagent | none (H makes it observable) | Medium (backend investigation) | Medium |
| H — token accounting | none | Medium (per-backend extraction) | Medium |
| I — scanner ignore config | none | Medium (security-sensitive) | Medium |
| J — observability docs | none | Low | Small |
| M — constitution onboarding | none | Low | Small–Medium |
| L — v1.0 RC→release | **all others green** | Medium (release) | Small–Medium |

**Suggested unit grouping:** (1) K rename + N e2e; (2) A+B+C+D lifecycle artifacts; (3) E+F oracle
traceability; (4) G+H run visibility; (5) I scanner config; (6) J+M onboarding/docs; (7) L release
last.

---

## Spec files to create (self-application)

This work is built with 3Powers, so each unit gets a spec (specs may cite IDs freely — `specs-src/`
is exempt from the OSS-readiness ID rule). Numbers are the next free workspace numbers **at
implementation time** (current specs go to `028`); after Track K they live under `specs-src/`.
Grouping is a recommendation — the specify stage may split further.

| Path (post-rename) | Spec ID | Tracks |
|---|---|---|
| `specs-src/<NNN>-specs-src-rename/spec.md` | `SRCDIR` | K, N |
| `specs-src/<NNN>-lifecycle-artifacts/spec.md` | `LIFEART` | A, B, C, D |
| `specs-src/<NNN>-oracle-traceability/spec.md` | `ORATRACE` | E, F |
| `specs-src/<NNN>-run-visibility/spec.md` | `RUNVIS` | G, H |
| `specs-src/<NNN>-scanner-ignore-config/spec.md` | `SCANIGN` | I |
| `specs-src/<NNN>-onboarding-and-observability/spec.md` | `ONBRD` | J, M |
| `specs-src/<NNN>-v1-release/spec.md` | `V1REL` | L |

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Renames break the completion gate / clean-start guard.** `artifacts.py` and `gitflow.py` regexes hardcode `specs/…` and `…\.md` names. | Update those regexes in the *same* commit as each rename; add explicit tests that a run's specify/plan/tasks/implement stages pass the completion gate under the new names, and that the clean-start guard recognizes `specs-src/.../progress.md`. |
| **Ledger back-compat.** Old signed entries point at `specs/…`, `tasks.md`, `implement.md`; renaming without tolerant resolution breaks resume/re-check of old runs. | Read-resolution accepts new-then-legacy names/bases (decision 5); no ledger rewrite; a back-compat test drives resume over a legacy-path ledger. |
| **Editing sealed/approved constitution + templates trips `spec_integrity`/`gate_gaming`.** Tracks D, M, K, L edit the constitution and the plan/tasks templates, and the plan/tasks templates are bound by a conformance test. | Update the template-skeleton conformance test in lockstep; before landing, run `3pwr gate run --path engine` + `3pwr verify`; if the sealed epic/constitution trips, the maintainer re-seals (documented path) or records a signed `3pwr deviation` — decided by the user at that point, recorded in the ledger. |
| **Oracle namespace decoupling (Track E) regresses coverage.** Filing by folder id while req-ids use the doc Spec ID could double-break coverage if the split is wrong. | The fix explicitly separates storage key (folder id) from req-namespace (spec.md Spec ID); a coverage test asserts `DEMO-FR-*` refs count under a numeric folder key before the track is "done". |
| **Token extraction is backend-specific and brittle.** CLIs report usage differently or not at all. | Per-backend strategy + graceful `unknown`; never in the verdict; a test asserts the verdict/`--json` are unchanged with usage absent, so a broken extractor degrades to "unknown", not a failure. |
| **Scanner ignores could hide real secrets.** A broad glob silences a genuine finding. | Exclusions are reported in gate output; the core ed25519 private-key check always runs; docs warn that broad ignores weaken the gate; excludes are deterministic and committed (reviewable). |
| **Copilot session reuse may be un-fixable from the engine.** If `copilot -p` resumes context with no flag to stop it. | Track G first *investigates*; if a CLI truly can't start clean, document the limitation and use Track H's token counts to surface any context bleed, and prefer a backend that supports clean sessions for isolation-critical roles (oracle). |
| **Declaring v1.0 with open residuals.** Users may read "1.0" as "everything done". | RC first (decision 4); STATUS reframes residuals as explicitly accepted post-1.0 items; the release checklist gates the tag. |
| **Test churn (~143 tests touch `specs/`).** | Mechanical updates land with the rename commit; a `specs-src` grep in CI-equivalent self-application catches stragglers. |

---

## Verification (post-delivery)

```bash
(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)
3pwr gate run --path engine            # self-application, Standard tier
uv tool install --force ./engine
3pwr --version                          # -> 1.0.0
# a dry-run shows the new artifact names + fresh-session/token behavior
3pwr run "demo intent" --dry-run --spec-id DEMO
ls specs-src/<NNN>-demo-intent/         # spec.md plan.md implementation-plan.md oracle.md changelog.md progress.md
# scanner ignore works
grep -q "ignore" .3powers/config/scan.yaml && echo "scan.yaml present"
# constitution onboarding CTA present
3pwr init --yes --json | grep -qi constitution && echo "init flags constitution"
```

---

## Open questions — all resolved 2026-07-08

The plan is **finalized** and ready for handover to the implementation-plan agent. Resolutions:

1. **Track F — `oracle.md` format:** RESOLVED. The user supplied the exact Tests-Specification
   template; merged into `oracle.agent.md` per Track F (implementation-agnostic; Given/When/Then;
   property invariants; NFR metric/threshold/protocol; Open-Questions-to-legislature stop),
   3Powers-adapted (`.3powers/memory/constitution.md`, no `.specify/`/`$ARGUMENTS`/extension hooks,
   artifact is `oracle.md`), keeping the runnable oracle tests.
2. **Track G — parallelism model:** RESOLVED — recommended path (both). *Engine-level concurrency*
   means the `NativeRunner`/`phases.py` scheduler itself dispatches disjoint `[P]` **phases** as
   concurrent separate subprocess sessions (a `ThreadPoolExecutor`). That stays. *Additionally*, the
   build prompt tells the coding agent to spawn its own **sub-agents** for `[P]` work **within** a
   phase. No change to engine-level phase concurrency.
3. **Track I — config granularity:** RESOLVED — recommended path: per-tool ignore globs **plus**
   optional per-finding-rule suppression, **plus** a small default ignore set shipped in the
   template.
4. **Track L — RC scope:** RESOLVED — no residual closed before 1.0; the maintainer verifies
   manually and cuts 1.0 anyway (RC first only to absorb rename fallout).
5. **e2e (user question):** RESOLVED — captured as Track N; only the Track K rename touches the
   notebooks (three `specs`→`specs-src` globs); everything else is e2e-safe.
