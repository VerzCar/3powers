# Feature Specification: Progress File — a Human-Readable `progress.md` in the Run's Feature Folder, Updated at Every Lifecycle Event and Committed with Each Producing Stage

**Spec ID**: PROGFILE
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     PROGFILE closes the durable-progress gap left after SRCX (017), GITX (018), STEER (019), and
     RUNID (020): the live bar is ephemeral, the signed ledger is machine-readable and needs
     `3pwr run --status` to query — there is no persistent, human-readable record in the run folder
     an operator can `cat` or share to see where a run is and what to do next. PROGFILE makes the
     engine write and maintain `specs/<NNN>-<slug>/progress.md` — stage-level and phase-level
     progress, the current state, the last deterministic-gate verdict, copy-pasteable helper
     commands carrying the run's real identity (RUNID-FR-003), and the failed gate names of the
     last verify attempt — updated atomically at every lifecycle event and committed with each
     producing stage alongside the artifact and the ledger (RUNID-FR-005's posture). Cross-refs:
     SRCX-FR-008/011, GITX-FR-007/010, RUNID-FR-001/003/005, PHASE-FR-010, 3PWR-FR-011/034. An
     operator-convenience view only: the signed ledger stays the single authoritative record; no
     trust-spine module (canonical/keys/ledger/verify) is changed and no new ledger entry type,
     signing scheme, or verdict schema is introduced. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate
     threshold. Rationale: this is executive / reporting plumbing — one new rendering module, calls
     at the run loop's existing event points, and one more path staged into the existing stage
     commit. No trust-spine module is touched, no gate is weakened (3PWR-FR-032), and the file
     never feeds a verdict. Cosmetic was rejected: the file's update triggers, its atomic-write
     durability, and its never-fail-the-run property must hold under test — an operator will act on
     what it says. High-risk was rejected: no trust-spine change; the ledger stays the only
     authority. Standard applies — the same latitude SRCX (017), GITX (018), and RUNID (020) used
     for their run plumbing. -->

**Status**: Draft

**Input**: Plan 030, Track E (PROGFILE): the live bar vanishes with the terminal; the ledger
answers only `3pwr run --status`; an operator picking up a paused or failed run — or a teammate
asked to look at one — has no quick reference for what completed, what is running, which phase the
build is in, what the gates said, or which command to type next.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** replace or duplicate the signed ledger as a source of truth — `progress.md` is a
  derived, human-readable convenience; the ledger stays authoritative (3PWR-FR-019) and lifecycle
  state is never *read back* from the progress file.
- Does **not** add a new ledger entry type, signing change, or verdict-schema change, and never
  enters the deterministic verdict computation (3PWR-NFR-001).
- Does **not** change the gate suite's composition, any tier threshold, exit codes, or the two
  mandatory human gates (3PWR-FR-006, 3PWR-FR-037).
- Does **not** render raw gate output or error lines — those stay with the gate-red event rendering
  (GDIAG); the progress file lists failed gate *names* only.
- Does **not** write anything for a `--dry-run` / simulated run — those dispatch nothing and write
  nothing (the SRCX dry-run stance), so they also progress-report nothing.
- Does **not** commit anything beyond what the stage commit already stages plus the progress file
  itself; unrelated files are never swept in (GITX-FR-010 unchanged) and no commit is ever forced
  for a stage that produced nothing.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator reads the run's state from one file (Priority: P1)

An operator returning to a paused, running, or failed run — or a teammate who was just linked the
run's feature folder — opens `specs/030-add-button/progress.md` and immediately sees which stages
completed (and when), what is running or paused right now, the last gate verdict, and the exact
commands (with the real `030`) to check status, resume, abort, or re-run the gates.

**Acceptance Scenarios**:

1. **Given** a live run whose workspace is `specs/030-add-button/`, **When** its first stage is
   dispatched, **Then** `specs/030-add-button/progress.md` exists, titled
   `# Run 030 · add-button · <timestamp>`, with one stage-progress row per lifecycle stage.
2. **Given** the run pauses at the spec-approval gate, **When** the operator opens the file,
   **Then** the paused stage's row shows the paused glyph and the "Current state" block names the
   gate and the resume command carrying `030`.
3. **Given** the run's verify gates went red, **When** the operator opens the file, **Then** the
   "Last verdict" block reports the failure and the "Gate failures (last verify attempt)" section
   lists the failed gate names.

### User Story 2 - The build's phases are visible (Priority: P1)

A user watching a phased implement stage wants to see phase-level progress — which phases are done,
which is running, and how many of each phase's tasks are checked off in the tasks artifact — without
reading `tasks.md` themselves.

**Acceptance Scenarios**:

1. **Given** a run whose tasks artifact declares three phases, **When** the implement stage is the
   current stage, **Then** the file carries a phase-detail table with one row per phase — number,
   description, status glyph, and tasks done (e.g. `2/5`) read from the artifact's checkboxes.
2. **Given** a run whose current stage has no phases (or is not the implement stage), **When** the
   file is written, **Then** no phase-detail table is rendered.

### User Story 3 - The progress rides the stage commits (Priority: P2)

A reviewer walking the run branch's history wants each producing stage's commit to carry the
progress file alongside the stage artifact and the ledger, so the run's human-readable state at
each boundary is recoverable from git history alone.

**Acceptance Scenarios**:

1. **Given** a producing stage whose post-stage commit is made, **When** the commit's file list is
   inspected, **Then** it contains the feature folder's `progress.md` alongside the stage artifact
   and `.3powers/ledger.jsonl`.

### Edge Cases

- A `--dry-run` / simulated run allocates no workspace → no reporter is bound, no file is written.
- A resume rebinds the recorded workspace → the same `progress.md` keeps updating; stages completed
  in a prior session show done without replaying that session's events.
- The tasks artifact is missing or declares no phases → the phase-detail table is simply absent.
- The progress file cannot be written (permissions, disk) → the run continues unchanged; at most a
  warning is printed (never a stage failure, never a gate).
- A paused or failed run leaves the file updated after its last stage commit → the clean-start
  guard treats it as engine-owned state (like the ledger), so it never blocks a later run.
- A reader `cat`s the file mid-write → the tmp-then-rename write means it always sees a complete
  file, never a torn one.

## Requirements *(mandatory)*

### Functional Requirements

- **PROGFILE-FR-001**: For every live (native) run bound to a feature workspace, the system shall
  write and maintain a `progress.md` file flat in the run's feature folder
  (`specs/<NNN>-<slug>/progress.md`).
  - *Acceptance*: after the first lifecycle event of a live run allocating `specs/030-add-x/`,
    `specs/030-add-x/progress.md` exists; a `--dry-run` writes none.
- **PROGFILE-FR-002**: Every write of the progress file shall be atomic — rendered to a temporary
  file in the same directory, then renamed onto `progress.md` — so a concurrent reader never
  observes a torn or partial file, and no temporary file survives a successful write.
  - *Acceptance*: after any update, `progress.md` is complete and no `.progress.md.tmp` remains.
  - *Property*: the rename is the only operation that makes new content visible (the ledger's
    durability posture, ref PAT-001).
- **PROGFILE-FR-003**: The file's first line shall be the title `# Run <NNN> · <slug> · <timestamp>`
  — the workspace number and slug from the run's feature folder name.
  - *Acceptance*: a run in `specs/030-add-button/` titles the file `# Run 030 · add-button · …`.
- **PROGFILE-FR-004**: The file shall carry a stage-progress table with one row per lifecycle stage
  showing a status glyph — `✓` done, `⏳` running, `○` pending, `🔒` paused, `✗` failed — and, for a
  completed stage, its completion timestamp.
  - *Acceptance*: mid-run, completed stages show `✓` with timestamps, the current stage shows `⏳`,
    later stages show `○`; a pause shows `🔒` on the gate's stage; a failure shows `✗`.
- **PROGFILE-FR-005**: When and only when the current stage has declared phases (an implement stage
  whose tasks artifact declares phases), the file shall carry a phase-detail table with one row per
  phase — phase number, description, status, and tasks done (`<checked>/<total>`) read from the
  tasks artifact's checkboxes at write time.
  - *Acceptance*: a phased build renders the table with per-phase checkbox counts; a phaseless run
    renders no phase table.
  - *Property*: the counts are a pure function of the tasks artifact's bytes at write time.
- **PROGFILE-FR-006**: The file shall carry: a "Current state" block naming what the run is doing or
  waiting on; a "Last verdict" block (pass/fail and, on fail, the failed gate names); a fenced
  "Helper commands" block — status, resume-with-approver, abort, and gate re-run — each carrying the
  run's resolved identity, never a placeholder; and a "Gate failures (last verify attempt)" section
  listing failed gate names only.
  - *Acceptance*: after a derivation to `030`, the helper block contains
    `3pwr run --status --spec-id 030`, `3pwr run --resume --spec-id 030 --approver <you>`,
    `3pwr abort --spec-id 030`, and `3pwr gate run --id 030 --tier <tier>`.
- **PROGFILE-FR-007**: The system shall update the file at each of these lifecycle triggers: stage
  start (row → running, current state), stage complete (row → done + timestamp), gate verdict PASS
  (last verdict), gate verdict FAIL (last verdict + gate-failures section), human-gate pause
  (row → paused, current state names the gate), and run failure (row → failed, current state names
  the recorded failure class).
  - *Acceptance*: each trigger observably changes the corresponding fields on the very next read.
- **PROGFILE-FR-008**: When a producing stage's post-stage commit is made and the progress file
  exists, the system shall include its repo-relative path in the committed path set — alongside the
  stage artifact and the ledger — never duplicating an already-listed path and never forcing a
  commit for a stage that produced nothing.
  - *Acceptance*: after any producing stage of a live run, the stage's commit contains
    `specs/<NNN>-<slug>/progress.md`.

### Non-Functional Requirements

- **PROGFILE-NFR-001**: A failure writing the progress file shall never fail a run, a stage, or a
  gate — the engine degrades it to at most a warning; the file never feeds the deterministic
  verdict or the lifecycle state (the signed ledger stays the only authority, 3PWR-FR-019,
  3PWR-NFR-001). Rendering is deterministic and fully offline given the tracked state and the tasks
  artifact bytes.
  - *Acceptance*: with the feature folder unwritable, the run proceeds and exits exactly as it
    would have; identical inputs render byte-identical files.
- **PROGFILE-NFR-002**: The progress file is engine-owned run state: legitimately left updated
  after a run's last stage commit (a pause or failure), it shall never be treated as a developer's
  unrelated work by the clean-start guard (GITX-FR-007) and so never blocks a later run.
  - *Acceptance*: with a dirty `specs/<NNN>-<slug>/progress.md` from a paused run, a fresh
    unrelated `3pwr run` starts normally.

## Success Criteria *(mandatory)*

- **PROGFILE-SC-001**: `specs/<NNN>-<slug>/progress.md` exists after the first producing stage of a
  live run and reads correctly at every later trigger.
- **PROGFILE-SC-002**: Stage rows update to `✓ done` with a timestamp when the stage completes; the
  paused/failed states render `🔒`/`✗` on the right rows.
- **PROGFILE-SC-003**: The gate-failures section shows the failed gate names (not raw errors), and
  the helper commands carry the run's real identity.
- **PROGFILE-SC-004**: The file is included in each producing stage's commit alongside the stage
  artifact and the ledger.
- **PROGFILE-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) —
  a test naming the PROGFILE-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id PROGFILE --stage spec --spec specs/024-progress-file/spec.md`; appended to the signed ledger)_ | | |
