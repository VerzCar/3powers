# Feature Specification: Run Artifact Workspace — a Flat Per-Run Feature Folder, a Ledger-Tracked Markdown Artifact for Every Producing Stage, Auto-Allocated Run Folders, and a Deterministic Artifact-and-Ledger Stage-Completion Gate

**Spec ID**: SRCX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     SRCX is the workspace/executive counterpart to PHASE (013) — which introduced the per-feature
     artifact workspace and the split `spec/spec.md` + `artifacts/<step>.md` layout, the plan/tasks
     artifact contracts, context-budgeted phases, and one fresh headless session per phase — to
     RUNLIVE (011) — which added the per-stage dispatch-time artifact contracts (a stage that produced
     nothing or only an off-target change is a *named artifact failure*) and commit checkpoints — and
     to AUTOX (014) — which added signed `run`/`failure` ledger records, checkpoint-independent resume,
     and the stable exit-code/status contract. Those delivered the pieces; SRCX changes two things and
     closes one gap. (1) It **supersedes PHASE-FR-001's folder split** with a single FLAT folder per
     run — every stage's artifact lies flat in `specs/<NNN>-<slug>/`, matching the layout every spec
     on disk already uses. (2) It makes **every *producing* stage** leave a ledger-tracked markdown
     artifact in that folder (adding `oracle.md`/`implement.md` *records* to the existing
     spec/plan/tasks documents). (3) It adds a **deterministic stage-completion gate** — a run may only
     advance past a producing stage when BOTH its declared markdown exists on disk AND a matching
     signed ledger entry records it, else the stage must be re-run — which also governs `--resume`,
     closing the confirmed gap where resume trusts the ledger's stage record without re-checking the
     file is still on disk. It also auto-allocates the `<NNN>-<slug>` run folder (the counter Spec Kit
     used to provide, removed by SLIM). Cross-refs: PHASE-FR-001/002/003/010/011, RUNLIVE-FR-001/002/
     010, AUTOX-FR-006/007/010, 3PWR-FR-004/006/011/019/032/037, 3PWR-NFR-001. Executive/workspace
     plumbing only; no trust-spine module (canonical/keys/ledger/verify) is changed and no new ledger
     entry type, signing scheme, or verdict is introduced. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this is executive / workspace / artifact plumbing — the on-disk feature-folder layout,
     the per-stage markdown records, the folder allocator, and a deterministic completion check on the
     run's control flow — NOT the trust-spine modules (canonical/keys/ledger/verify), which are not
     touched. It weakens no gate (3PWR-FR-032) and adds no new trust primitive. The real regression
     risk is twofold and both are turned into explicit, tested requirements: (a) the new completion
     gate could wrongly block a legitimate run or fail to block a broken one — so its logic is a pure,
     unit-tested function of (disk state, ledger entries, step) with no model/network (SRCX-FR-012,
     SRCX-NFR-001/005); and (b) the ledger additions could break offline reconstruction — so they are
     strictly additive (new failure-class VALUES and one additive `run`/`start` field within the
     existing `run` entry type; no new type, no signing change), and `3pwr verify` staying green on old
     and new ledgers is a requirement (SRCX-NFR-002). This is the same latitude and reasoning AUTOX
     (014) used to land on Standard for its `run`/`failure` records and resume contract, and CLIUX (015)
     used for output plumbing. Cosmetic was considered and rejected: this touches run control-flow and
     writes ledger records, so it must hold offline/verify invariants under test. High-risk was
     considered and rejected: no trust-spine module changes, mutation-graded thresholds do not apply to
     this plumbing. Standard applies. -->

**Status**: Draft

**Input**: User request: "When running `3pwr run` we have to create for each stage an artifact (a
markdown) file that is persisted in a folder and every stage-produced file lies there flat in it. I
want the following naming and folder structure. For each new `3pwr run` we create a unique number and
a description — we have that already — but the folder structure is then: a parent folder that always
exists, and inside it a `<continuous-number>-<run-description>` folder in which all the artifacts lie
flat, all of them tracked by the ledger. There must be a deterministic check each time a stage is done
— if a file has been produced and an entry exists in the ledger — otherwise it can not proceed and the
stage must be re-run." A codebase review settled the specifics: the parent folder stays `specs/` (the
established, versioned spec home — 3PWR-FR-010) with the flattening happening *inside* each
`specs/<NNN>-<slug>/`; every *producing* stage emits the markdown (documents plus oracle/implement
*records*), while pure gate/verify/sign-off stages stay ledger-only; and the engine auto-allocates the
`<NNN>-<slug>` folder.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):** PHASE (spec 013) built the per-feature artifact
  workspace in `workspace.py` — `stage_artifact_path` / `spec_path` / `find_artifact` / `feature_dir_of`
  / `find_specs`, all pure path logic (no network, no model, no ledger — 3PWR-NFR-001) — and defined a
  `spec/spec.md` + `artifacts/<step>.md` split, keeping the pre-013 *flat* layout resolvable. In
  practice **every spec on disk (001–016) is flat** (`specs/<f>/spec.md`, sometimes a flat `tasks.md`);
  implementation plans live in the top-level `plan/` series, and no feature ever adopted the split — so
  the resolvers already read the flat locations and making flat canonical is mostly a matter of what
  `stage_artifact_path` *writes*. RUNLIVE (spec 011) added per-stage dispatch-time artifact contracts
  (`artifacts.py`: `ArtifactContract`, `verify()` → a "named artifact failure" when a stage produced
  nothing or only an off-target change) and commit checkpoints. PHASE-FR-003 + AUTOX (spec 014) already
  record each completed producing stage as a signed append-only `run` ledger entry of kind `stage`
  (`{"kind":"stage","step":…,"stage":…,"artifacts":[…paths]}`), always written on stage success even
  with auto-commit off, and reconstruct resume/status from the ledger
  (`orchestrate.last_completed_step` / `resume_start_index`; `lifecycle.derive`). AUTOX also gave a
  signed `run`/`failure` record with an open-string failure class, surfaced by `3pwr run --status` and
  `3pwr status` as "failed at `<stage>` (`<class>`)".
- **Where the seams are:** (1) the folder layout in code (split) diverges from the folder layout in
  use (flat); the user wants one flat folder per run, canonically. (2) Two lifecycle stages that
  *produce* real outputs — `oracle` (authored test files) and `implement` (code changes) — leave those
  outputs at their real repo paths but leave **no document in the feature folder**, so the folder is
  not a complete, at-a-glance record of the run. (3) The completion signal is one-sided: a stage's
  artifact is checked *at dispatch time* against a contract, and the ledger separately records the
  accepted paths, but **nothing cross-checks the two** — and on `--resume` the engine trusts the
  ledger's `stage` entry alone, so deleting a completed stage's artifact and resuming silently *skips*
  that stage rather than re-running it. (4) Since Spec Kit was removed (SLIM, spec 010), the engine has
  no next-number counter for the run flow — `--spec-id` defaults to `RUN` and a fresh `3pwr run` has no
  deterministic way to allocate `specs/<NNN>-<slug>/`; the only next-number helper
  (`characterize._next_feature_number`, which scans `NNN-` prefixes → max+1) lives in the brownfield
  path.
- **Guardrail:** executive/workspace/artifact plumbing only. No gate, threshold, verdict bytes, ledger
  chain/signing format, exit-code contract, or the two mandatory human gates (3PWR-FR-006 spec
  approval, 3PWR-FR-037 sign-off) change. Ledger additions are strictly additive — new failure-class
  values and one additive field on the existing `run`/`start` payload, within the existing `run` entry
  type — so `3pwr verify` stays green on both old and new ledgers, and the whole feature is offline and
  deterministic (3PWR-NFR-001). The rest of PHASE (context budget, phases, one fresh session per phase,
  parallel `[P]` dispatch) is preserved unchanged; only PHASE-FR-001's *folder split* is superseded.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** migrate or rewrite existing features `specs/001`–`016`, nor any existing artifact; both
  legacy layouts (the pre-013 flat layout and the PHASE split layout) stay readable and runnable in
  place. Only NEW runs are written flat.
- Does **not** relocate, copy, or duplicate the real oracle tests or the implementation code into the
  feature folder; `oracle.md` and `implement.md` are **records that link** to those outputs at their
  existing repository paths, not copies of them.
- Does **not** add a new ledger entry type, change the signing scheme, or alter the verdict schema —
  the only additions are new failure-class *values* and one additive field on the existing `run`/`start`
  payload.
- Does **not** verify the *liveness of every path linked from a record* at completion-gate time — the
  real test/change paths are already gated at dispatch time by RUNLIVE's `oracle`/`implement` contracts;
  the completion gate asserts the *record markdown* and its matching ledger entry.
- Does **not** change the deterministic gate suite, any tier threshold, or the two mandatory human
  gates (3PWR-FR-006, 3PWR-FR-037), and does not route through, alter, or read the deterministic verdict
  (3PWR-NFR-001).
- Does **not** add cross-machine or cross-process allocation/locking; concurrent-run allocation safety
  is local-filesystem, single-run-per-repo only.
- Does **not** validate the internal *content or sections* of a stage's markdown beyond its existence,
  and does **not** garbage-collect or reconcile orphaned artifacts from abandoned runs.
- Does **not** rename the parent folder to `spec-source/` or introduce a new top-level artifact root;
  the parent stays `specs/` (3PWR-FR-010) and the flattening happens within each `specs/<NNN>-<slug>/`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One flat, ledger-tracked folder per run (Priority: P1)

A user running `3pwr run "<intent>"` on a fresh intent wants the engine to create one folder for that
run, named `<continuous-number>-<description>`, under the established `specs/` parent, and to drop every
producing stage's artifact flat inside it — so the whole run is one scannable folder rather than a tree
of subfolders, and every file in it is tracked by the signed ledger.

**Acceptance Scenarios**:

1. **Given** `specs/` whose highest existing folder is `016-…`, **When** the user runs
   `3pwr run "Add run artifact workspace"` with no `--resume` and no `--spec`, **Then** the engine
   allocates `specs/017-add-run-artifact-workspace/` and writes each producing stage's markdown flat in
   it, with no `spec/` or `artifacts/` subfolder created.
2. **Given** a completed run, **When** the feature folder is listed, **Then** it contains `spec.md`,
   `plan.md`, `tasks.md`, `oracle.md`, and `implement.md` directly (given all producing stages ran),
   and each of those files is named in a signed `run`/`stage` ledger entry for the run.
3. **Given** the same intent string and the same `specs/` directory listing, **When** allocation runs
   on two different machines, **Then** the allocated folder name is byte-identical.

### User Story 2 - A stage cannot be "done" without both its file and its ledger entry (Priority: P1)

A user wants each stage's completion to be provable, not assumed: after a stage finishes, the run may
only proceed if the stage actually produced its artifact on disk AND that artifact is recorded in the
ledger. If either is missing, the run stops, says which stage and which artifact, and the stage must be
re-run rather than silently skipped.

**Acceptance Scenarios**:

1. **Given** a producing stage that finished and whose markdown is on disk and named in a `run`/`stage`
   ledger entry, **When** the completion gate runs, **Then** it passes and the run advances to the next
   stage.
2. **Given** a stage whose markdown is present on disk but is named in no matching ledger entry,
   **When** the completion gate runs, **Then** the run is blocked, the failure names the stage and the
   unrecorded artifact and is classified `artifact_unrecorded`, and the stage must be re-run.
3. **Given** a stage recorded in the ledger but whose markdown has been deleted from disk, **When** the
   completion gate runs, **Then** the run is blocked, the failure names the stage and the missing path
   and is classified `artifact_absent`, and the stage must be re-run.

### User Story 3 - Resume re-runs a stage whose artifact vanished (Priority: P1)

A user who deletes or loses a completed stage's artifact and then resumes the run wants the resume to
notice the file is gone and re-run that stage — not to skip it on the strength of the old ledger entry
and then fail downstream for a missing input.

**Acceptance Scenarios**:

1. **Given** a run recorded complete through the `tasks` stage, **When** `plan.md` is deleted and the
   user runs `3pwr run --resume --spec-id <ID>`, **Then** the resume re-enters at the `plan` stage
   (the earliest stage whose artifact is broken), names the missing artifact, and does not skip to
   `oracle`.
2. **Given** the same resume, **When** it re-runs `plan`, **Then** the re-run overwrites `plan.md`,
   appends a fresh `run`/`stage` entry, and the completion gate then passes — the earlier failed
   attempt remaining in the append-only ledger as history.

### User Story 4 - Existing features keep working (Priority: P2)

A maintainer with existing features on disk — most flat, some hypothetically in the PHASE split layout
— wants them to keep resolving, resuming, gating, and verifying with no file moved and no ledger
rewritten, because SRCX changes only how *new* runs are written.

**Acceptance Scenarios**:

1. **Given** a pre-013 flat feature (`spec.md`, `tasks.md` flat), **When** it is resolved, resumed, and
   gated, **Then** it resolves to exactly one spec and the completion gate checks its stage artifacts at
   their flat paths, moving nothing.
2. **Given** a feature in the PHASE split layout (`spec/spec.md` + `artifacts/plan.md`), **When** it is
   resumed, **Then** the gate checks each already-written stage's artifact at its split path, while any
   newly written stage lands flat — a mixed folder is tolerated, and `3pwr verify` stays green.

### User Story 5 - The oracle and implement records complete the folder (Priority: P2)

A user wants the two stages that produce real code (`oracle`, `implement`) to also leave a short
markdown record in the feature folder that links to the authored tests / changed code — so the folder
is a complete record — without moving that code out of its real repo location, and with a single
`implement.md` even when the implement stage ran as several parallel phases.

**Acceptance Scenarios**:

1. **Given** a completed `oracle` stage, **When** the folder is inspected, **Then** `oracle.md` exists
   and links the authored oracle test paths, which remain at their real repo locations (e.g. under
   `tests/oracle/…`), not under the feature folder.
2. **Given** an `implement` stage that ran as N parallel phases (PHASE-FR-011), **When** the folder is
   inspected, **Then** exactly one `implement.md` exists, enumerating each phase and linking its code
   changes in deterministic phase order.

### Edge Cases

- A stage's markdown is on disk but recorded in no ledger entry (an orphan file, e.g. hand-created) →
  `artifact_unrecorded`: block, name the stage, require re-run; the orphan is never silently accepted.
- A stage is recorded in the ledger but its markdown was deleted → `artifact_absent`: block, name the
  stage and missing path, require re-run (the headline resume gap).
- A pure gate / verdict stage (`review-spec`, `review-plan`, `review-verify`, `verify`, `signoff`,
  `advance`) legitimately produces no markdown → it is never gated and never flagged for a missing
  document.
- A mid-run deletion of an *intermediate* stage's artifact (e.g. `plan.md` deleted after `tasks`
  completed) → resume re-enters at the earliest broken stage (`plan`), and later stages are re-run in
  order, not skipped-as-passed.
- Two concurrent runs both observe `max = 016` and pick `017` → allocation fails fast when its target
  folder already exists (a clear "folder already allocated" message); cross-process locking is a
  non-goal.
- The intent slugifies to a string that collides with, or is identical to, another run's slug → the
  `<NNN>` prefix keeps folders unique, so a "collision" is really a number reuse; a folder that already
  exists for a *different* run is never overwritten.
- The intent slugifies to empty (all punctuation) → allocation falls back to a fixed token so the
  folder name is always valid.
- The implement stage's phased dispatch has a one-of-N phase failure → implement fails at the phase
  level (PHASE-FR-012) *before* the completion gate is reached; the stage never reports success, so the
  gate is not the thing that catches it.
- A record markdown exists and is recorded, but a path it *links* (a test or code file) is missing →
  out of the completion gate's scope; the gate asserts the record + its ledger entry, while the real
  linked paths were gated at dispatch time by RUNLIVE's contracts.
- A `--dry-run` / simulated run dispatches nothing and writes no artifacts → the completion gate is a
  live-runner concern only and is a no-op (or is not invoked) on the simulated path, so `--dry-run`
  stays offline and green.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where a value is derived or parsed (3PWR-FR-024). File locations, the
  folder-name shape, the ledger record shape, and failure-class names appear where they ARE the
  contract under specification (the same latitude AUTOX took for its exit codes, transcript paths, and
  `run`/`failure` record, and CLIUX for `ui.yaml`) — not as implementation detail (3PWR-FR-007). Named
  modules/functions are context in the non-normative sections only.
-->

### Functional Requirements

#### A. Flat per-run feature workspace

- **SRCX-FR-001**: The system shall place every lifecycle stage's artifact for a run FLAT in that run's
  feature folder `specs/<NNN>-<slug>/` — `spec.md`, `plan.md`, `tasks.md`, `oracle.md`, `implement.md` —
  with no `spec/` or `artifacts/` subfolder, superseding PHASE-FR-001's split layout for every run
  created after this feature is delivered.
  - *Acceptance*: a fresh `3pwr run` ends with each producing stage's markdown directly under
    `specs/<NNN>-<slug>/`, and no `spec/` or `artifacts/` subfolder is created.
  - *Property*: the artifact path a producing step writes is `feature_dir/"<step>.md"` for every step
    other than `specify`, and `feature_dir/"spec.md"` for `specify`.
- **SRCX-FR-002**: The system shall resolve a feature's single specification across all three layouts —
  the new canonical flat layout, the pre-013 legacy flat layout (identical to it), and the PHASE split
  layout (`spec/spec.md`) — so existing features 001–016 keep resolving to exactly one spec.
  - *Acceptance*: a flat feature and a split feature each resolve to exactly one spec path; a feature
    holding both a flat and a split spec still yields exactly one, by a single deterministic precedence
    rule.
  - *Property*: for any feature folder, resolution yields at most one spec path.
- **SRCX-FR-003**: When locating an existing stage artifact, the system shall return the flat-layout
  path when it exists and fall back to the split-layout path otherwise, never returning two paths for
  one stage.
  - *Acceptance*: locating the `plan` artifact returns `<feature>/plan.md` when present, else
    `<feature>/artifacts/plan.md`, else nothing.

#### B. A ledger-tracked markdown artifact for every producing stage

- **SRCX-FR-004**: The system shall require every *producing* stage to emit a markdown artifact into the
  flat feature folder: `specify`→`spec.md`, `plan`→`plan.md`, `tasks`→`tasks.md`, `oracle`→`oracle.md`,
  and `implement`→`implement.md`.
  - *Acceptance*: after a full run, the flat folder contains exactly these five markdown files, given
    all five producing stages ran.
  - *Property*: the set of producing steps that declare a flat markdown artifact is exactly
    `{specify, plan, tasks, oracle, implement}`.
- **SRCX-FR-005**: The system shall treat `oracle.md` and `implement.md` as *records*: each is a
  markdown summary that links the real authored outputs (oracle test files, implementation code
  changes), which continue to live at their real repository paths; the record shall neither relocate nor
  duplicate those outputs.
  - *Acceptance*: `oracle.md` references the authored oracle test paths and `implement.md` references
    the changed code paths, while the referenced files remain at their existing repo locations, not
    under the feature folder.
  - *Property*: the set of paths a record links is a superset of the stage's dispatch-time
    contract-matched paths (oracle) / produced change set (implement).
- **SRCX-FR-006**: When the implement stage runs as multiple phases (PHASE-FR-010/011), the system shall
  produce a single `implement.md` record that accounts for every phase — naming each phase and linking
  its code changes — so a parallel-phase implement leaves one complete record rather than one per phase
  or none.
  - *Acceptance*: an N-phase implement yields exactly one `implement.md` enumerating N phases and their
    linked changes; a phaseless implement yields one `implement.md` for the single session.
  - *Property*: the record enumerates one entry per phase in the deterministic artifact order used when
    the phased results are collected.
- **SRCX-FR-007**: The system shall keep the pure human-gate stages (`review-spec`, `review-plan`,
  `review-verify`), the deterministic `verify` stage, `signoff`, and `advance` ledger-only — each shall
  produce its decision / verdict / advance ledger entry and no feature-folder document.
  - *Acceptance*: a completed run's flat folder contains no `review-spec.md`, `verify.md`, `signoff.md`,
    or `advance.md`; those stages appear only as ledger entries.
  - *Property*: the completion gate (Category D) is applied to exactly the producing steps of
    SRCX-FR-004 and to no gate / verdict / sign-off / advance step.

#### C. Auto-allocated `<NNN>-<slug>` run folder

- **SRCX-FR-008**: When `3pwr run "<intent>"` starts a NEW run (no `--resume` and no explicit `--spec`),
  the system shall deterministically allocate `specs/<NNN>-<slug>/` where `<NNN>` is the maximum
  existing `NNN-` prefix under `specs/` plus one, zero-padded to three digits, and `<slug>` is derived
  from the intent.
  - *Acceptance*: with `specs/` topping out at `016-…`, `3pwr run "Add run artifact workspace"`
    allocates `specs/017-add-run-artifact-workspace/`.
  - *Property*: given the same `specs/` directory listing and the same intent string, allocation yields
    a byte-identical folder name (3PWR-NFR-001).
- **SRCX-FR-009**: The system shall derive the slug from the intent deterministically — lowercased,
  runs of non-alphanumeric characters collapsed to a single hyphen, leading/trailing hyphens trimmed —
  and shall bound the slug to a fixed maximum length, falling back to a fixed token when the slug would
  be empty.
  - *Acceptance*: `"Fix the OAuth2 token-refresh bug!!"` yields a slug like
    `fix-the-oauth2-token-refresh-bug`; an over-long intent is truncated at the bound with no trailing
    hyphen; an all-punctuation intent yields the fallback token.
  - *Property*: slugify is idempotent — `slug(slug(x)) == slug(x)` — and pure.
- **SRCX-FR-010**: When `--resume` is given for a run, the system shall resolve the EXISTING feature
  folder recorded for that run and shall never allocate a new `<NNN>-<slug>`.
  - *Acceptance*: resuming a run whose folder is `specs/017-…/` re-enters that folder and creates no new
    numbered folder.
  - *Property*: a resume leaves the count of feature folders under `specs/` unchanged.
- **SRCX-FR-011**: The system shall bind the allocated feature folder to the run's spec-id in the signed
  ledger at run start, via an additive field on the existing `run`/`start` payload, so the folder is
  recoverable offline on a later resume from the ledger alone.
  - *Acceptance*: the `run`/`start` ledger entry for a run records its allocated feature folder (path or
    slug), and a resume reads it back without scanning modification times.
  - *Property*: the recorded folder value is a pure function of the allocation inputs and is verifiable
    offline (3PWR-NFR-001, no new ledger entry type — SRCX-NFR-002).

#### D. Deterministic stage-completion gate (artifact ∧ ledger)

- **SRCX-FR-012**: When a producing stage finishes, the system shall run a deterministic completion
  check that asserts BOTH (a) the stage's declared markdown artifact EXISTS ON DISK in the run's feature
  folder AND (b) a matching stage-completion ledger entry EXISTS in the signed ledger, before allowing
  the run to advance to the next stage.
  - *Acceptance*: a stage whose declared markdown is present on disk and whose ledger entry lists that
    path passes the gate and the run advances; a stage failing either condition does not advance.
  - *Property*: the check's outcome is a pure function of (feature-folder disk state, ledger entries,
    step) — no model call and no network (3PWR-NFR-001).
- **SRCX-FR-013**: The system shall define "a matching ledger entry" as a `run` entry of kind `stage`
  (or `checkpoint`) for that step, for the run's spec-id, whose recorded `artifacts` list includes the
  declared on-disk artifact path (compared as a repo-relative POSIX path).
  - *Acceptance*: a `run`/`stage` entry for `plan` whose `artifacts` contains
    `specs/017-…/plan.md` satisfies condition (b) for the plan stage; an entry that omits that path does
    not.
  - *Property*: the declared artifact path used for the comparison is the same value the workspace
    computes for that step's write location.
- **SRCX-FR-014**: When the completion check fails because the declared artifact is absent on disk, the
  system shall block advancing, name the stage and the missing path, classify the failure
  `artifact_absent`, and require the stage to be re-run.
  - *Acceptance*: deleting `plan.md` after the plan stage but before advance yields a blocked run naming
    `plan` and `specs/017-…/plan.md`, exiting on the setup/dispatch (non-gate-red) path.
  - *Property*: `artifact_absent` is a named failure class distinct from RUNLIVE's dispatch-time
    `artifact_missing`.
- **SRCX-FR-015**: When the completion check fails because no matching ledger entry records the on-disk
  artifact, the system shall block advancing, name the stage and the unrecorded artifact, classify the
  failure `artifact_unrecorded` (distinctly from the disk-absent case), and require the stage to be
  re-run.
  - *Acceptance*: an artifact present on disk with no `run`/`stage` entry listing it yields a blocked
    run naming the stage and classified `artifact_unrecorded`.
  - *Property*: `artifact_unrecorded` and `artifact_absent` are two distinct named classes.
- **SRCX-FR-016**: The system shall record every completion-gate failure as a signed `run`/`failure`
  ledger entry (extending AUTOX-FR-006) carrying the failing stage and the new failure class, so
  `3pwr run --status` and `3pwr status` report "failed at `<stage>` (`<class>`)".
  - *Acceptance*: after a completion-gate failure, both status commands show the stage and the
    `artifact_absent` / `artifact_unrecorded` class until a later record passes that stage.
  - *Property*: the new classes fold through the existing `run`/`failure` handling exactly like existing
    classes — no schema change, only new class values (SRCX-NFR-002).
- **SRCX-FR-017**: When resuming a run, the system shall apply the completion gate to each already-
  recorded producing stage before treating it as complete, and shall re-run any stage whose declared
  artifact is no longer on disk — never skipping a stage on the strength of a ledger entry alone.
  - *Acceptance*: a run recorded complete through `tasks`, then `plan.md` deleted, then `--resume`,
    re-runs from `plan` (not from `oracle`) and names the missing artifact.
  - *Property*: the resume entry point is the earliest producing stage whose artifact is both recorded
    in the ledger AND still present on disk — i.e. the ledger-derived resume index intersected with the
    on-disk completion check.

#### E. Boundaries of the gate

- **SRCX-FR-018**: The system shall apply the completion gate only to the producing stages at or before
  the run's current position in the lifecycle, and to no stage the run has not yet reached or did not
  execute.
  - *Acceptance*: a run paused at the `review-spec` human gate is not failed for a missing `plan.md`; a
    completed `implement` (even a single-session, phaseless one) is gated on `implement.md`.
  - *Property*: the gated set at any point equals the producing stages at or before the run's current
    position.

### Non-Functional Requirements

- **SRCX-NFR-001**: The completion gate, folder allocation, slugify, and layout resolution shall be
  deterministic and fully offline — no model call, no network, no provider tokenizer — so identical
  inputs (feature-folder disk state, ledger entries, intent string) produce identical outcomes on any
  machine (ref 3PWR-NFR-001).
  - *Acceptance*: repeating the gate evaluation over the same tree and ledger yields the identical
    verdict; repeating allocation over the same listing and intent yields the identical folder name;
    tests run with networking disabled.
- **SRCX-NFR-002**: The feature shall add only new *values* (the failure classes `artifact_absent` and
  `artifact_unrecorded`) and one additive field on the existing `run`/`start` payload, within the
  existing `run` entry type; it shall introduce no new ledger entry type, no signing change, and no
  verdict-schema change, so `3pwr verify` stays green across old and new ledgers.
  - *Acceptance*: `3pwr verify` passes on a ledger containing the new records, and a pre-SRCX ledger
    still verifies unchanged.
- **SRCX-NFR-003**: The engine shall keep both legacy layouts (pre-013 flat, PHASE split) resolvable and
  runnable for existing features 001–016; only new runs are written flat, and no existing feature folder
  is migrated or rewritten.
  - *Acceptance*: resuming, gating, and verifying over a flat feature and a split feature each succeed
    with no file relocated.
- **SRCX-NFR-004**: The completion gate's cost per run shall be linear in the number of executed
  producing stages — each check bounded by a constant number of filesystem stats and served by a single
  ledger read — with no quadratic re-scan per stage.
  - *Acceptance*: gate overhead grows linearly with stage count over a synthetic many-stage run, and a
    single ledger read serves all of a run's checks.
- **SRCX-NFR-005**: The gate, allocation, and resolution logic shall be pure given injected inputs and
  unit-testable with a simulated agent and no network (ref RUNLIVE-NFR-002); the deterministic gate
  suite, verdict computation, ledger signing, and the two mandatory human gates (3PWR-FR-006,
  3PWR-FR-037) shall be unchanged (3PWR-NFR-001).
  - *Acceptance*: tests exercise the pass / absent / unrecorded / resume cases with a simulated runner;
    gate-suite, verdict, signing, and sign-off behavior are byte-/behavior-identical to pre-SRCX.
- **SRCX-NFR-006**: Parallel phase dispatch (PHASE-FR-011) shall not race the completion gate or the
  ledger: the `implement.md` record and its `run`/`stage` entry shall be written from the collecting
  thread after all phases complete, in a deterministic order, keeping the hash-chain valid (ref
  PHASE-NFR-003).
  - *Acceptance*: after a parallel-phase implement, `3pwr verify` passes and the ordering of
    `implement.md` and its ledger record is reproducible.

## Success Criteria *(mandatory)*

- **SRCX-SC-001**: A fresh `3pwr run` over a new intent auto-allocates `specs/<NNN>-<slug>/` and leaves
  each producing stage's markdown flat in it (`spec.md`, `plan.md`, `tasks.md`, `oracle.md`,
  `implement.md`); no `spec/` or `artifacts/` subfolder is created.
- **SRCX-SC-002**: For every completed producing stage, both its declared markdown exists on disk AND a
  `run`/`stage` (or `checkpoint`) ledger entry lists that path; a run cannot advance past a stage where
  either is missing.
- **SRCX-SC-003**: Deleting a completed stage's artifact and then resuming re-runs that stage (naming
  it) rather than skipping it — demonstrably closing the "resume trusts the ledger" gap.
- **SRCX-SC-004**: The `oracle.md` and `implement.md` records link the real test/code outputs at their
  existing repo paths, and a multi-phase implement yields exactly one `implement.md` accounting for all
  phases.
- **SRCX-SC-005**: Existing features under both legacy layouts (pre-013 flat, PHASE split) still
  resolve, resume, gate, and verify green with no file relocation, and `3pwr verify` passes on both old
  and new ledgers.
- **SRCX-SC-006**: Two distinct, named failure classes (`artifact_absent`, `artifact_unrecorded`)
  surface through `3pwr run --status` and `3pwr status`, each with an actionable, stage-named message on
  the non-gate-red exit path.
- **SRCX-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test
  naming the SRCX-FR id, or a recorded output/documentation review where the rendered artifact/folder
  state is what is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id SRCX --stage spec --spec specs/017-run-artifact-workspace/spec.md`; appended to the signed ledger)_ | | |
