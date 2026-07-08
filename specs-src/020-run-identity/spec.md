# Feature Specification: Run Identity — the Workspace `NNN` Flows Through the Ledger, Oracle, Gate Messages, Resume Hints, and Stage Commits, and the Ledger Rides Every Producing Stage Commit

**Spec ID**: RUNID
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     RUNID closes the identity gap left between SRCX (017) — which allocates one flat
     `specs/<NNN>-<slug>/` workspace per run and binds it to the run in the signed ledger — and every
     consumer of the run's spec id: today a run started without `--spec-id` labels ALL of its ledger
     entries, gate messages, resume hints, oracle destination, and notifications with the opaque
     default `"RUN"` instead of the workspace's real `NNN`. RUNID makes the allocated `NNN` the run's
     identity whenever no explicit `--spec-id` was given, ensures the spec-conformance verdict carries
     the requirement ids the tests actually reference (so the ledger's `requirement_ids` field is
     populated), and bundles the ledger file itself into every producing stage commit so each stage
     commit is a self-contained trust snapshot. Cross-refs: SRCX-FR-008/010/011, GITX-FR-008/010/011,
     AUTOX-FR-009/010, 3PWR-FR-034/059. Executive / identity plumbing only; no trust-spine module
     (canonical/keys/ledger/verify) is changed, and no new ledger entry type, signing scheme, or
     verdict schema is introduced. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate
     threshold. Rationale: this is executive / identity plumbing — the spec-id default, the labels on
     messages and ledger payloads, one additive detail key on an existing gate result, and one more
     path staged into the existing stage commit. No trust-spine module (canonical/keys/ledger/verify)
     is touched, no gate is weakened (3PWR-FR-032), and no new trust primitive is added. Cosmetic was
     rejected: the identity drives resume control flow and what the signed ledger records, so it must
     hold determinism and traceability invariants under test. High-risk was rejected: no trust-spine
     change. Standard applies — the same latitude SRCX (017) and GITX (018) used for their identity
     and commit plumbing. -->

**Status**: Draft

**Input**: Plan 030, Track A (RUNID): a run started without `--spec-id` allocates
`specs/030-add-button/` correctly, yet every ledger entry, oracle dispatch, gate message, and resume
hint says `"RUN"`; the ledger's `requirement_ids` array on verdict entries is empty because the
spec-conformance gate result never exposes the referenced ids; and `.3powers/ledger.jsonl` is never
committed with the stages it records.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change how the workspace `NNN` is allocated or slugified — that stays SRCX's
  (SRCX-FR-008/009); RUNID only *consumes* the allocated folder name as the run's identity.
- Does **not** rename, migrate, or re-key any existing ledger entry, and does **not** add a new
  ledger entry type, signing change, or verdict-schema change.
- Does **not** change the gate suite's composition, any tier threshold, exit codes, or the two
  mandatory human gates (3PWR-FR-006, 3PWR-FR-037).
- Does **not** alter the oracle's sealed-bundle independence mechanics (3PWR-FR-020/021/062) — only
  the *destination folder name* the oracle is instructed to use.
- Does **not** commit anything beyond what the stage commit already stages plus the engine's own
  ledger file; unrelated files are never swept in (GITX-FR-010 unchanged).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The run is identified by its real number everywhere (Priority: P1)

A user starting `3pwr run "add a dismiss button"` without `--spec-id` sees the run allocate
`specs/030-add-dismiss-button/` — and wants every trace of that run (ledger entries, status output,
gate-pause messages, failure hints, notifications, the run branch) to carry `030`, not an opaque
default, so `3pwr run --resume --spec-id 030` copied from any hint just works.

**Acceptance Scenarios**:

1. **Given** a fresh run with no `--spec-id` whose workspace allocates `specs/030-add-button/`,
   **When** the run records its start, stages, gates, and failures in the signed ledger, **Then**
   every one of those entries carries `"spec_id": "030"`.
2. **Given** the same run pausing at a human gate or failing at a stage, **When** the resume hint is
   printed, **Then** it reads `3pwr run --resume --spec-id 030 …` — the real `NNN`, never a
   placeholder.
3. **Given** a run started with an explicit `--spec-id PAY`, **When** the workspace is allocated,
   **Then** the run's identity stays `PAY` — the explicit flag always wins over the derived `NNN`.

### User Story 2 - The verdict traces its requirements and the ledger rides the commit (Priority: P1)

A reviewer reading the signed ledger wants verify-stage verdict entries to name the requirement ids
the tests actually reference, and wants the ledger state at each stage boundary to be recoverable
from git history alone — the ledger file committed together with the artifact each producing stage
made.

**Acceptance Scenarios**:

1. **Given** a gate run whose spec-conformance gate scanned tests referencing `X-FR-001`, **When**
   the verdict is appended to the ledger, **Then** the entry's `requirement_ids` array contains
   `X-FR-001` (non-empty whenever any requirement is referenced).
2. **Given** a producing stage whose post-stage commit is made, **When** the commit's file list is
   inspected, **Then** it contains `.3powers/ledger.jsonl` alongside the stage's artifact.

### Edge Cases

- A run started with an explicit `--spec` path but no `--spec-id` → the identity derives from that
  spec's feature folder name the same way.
- A `--dry-run` / simulated run allocates no workspace → no derivation happens; the explicit
  `--spec-id` (or the documented default) applies unchanged.
- A resume names the run by `--spec-id` (the ledger lookup key) → no re-derivation; the recorded
  identity is authoritative.
- A stage that produced nothing forces no commit (GITX unchanged) → the ledger file alone does not
  fabricate a stage commit for a non-producing stage.
- The spec-conformance gate finds no referenced ids (no tests yet) → the detail key is present and
  empty; nothing is invented.

## Requirements *(mandatory)*

### Functional Requirements

- **RUNID-FR-001**: When a run is started without an explicit `--spec-id` and a run workspace
  (feature folder) is resolved, the system shall derive the run's spec id from the workspace's
  `NNN` prefix — e.g. `specs/030-add-button/` yields the spec id `030`.
  - *Acceptance*: a fresh run with no `--spec-id` allocating `specs/030-add-button/` records
    `"spec_id": "030"` on its ledger entries.
  - *Property*: the derived id is a pure function of the feature folder's name (the text before the
    first `-`), deterministic and offline (3PWR-NFR-001).
- **RUNID-FR-002**: When a run is started with an explicit `--spec-id`, the system shall use that
  value as the run's identity unchanged; the derived workspace `NNN` shall never override it.
  - *Acceptance*: `3pwr run "<intent>" --spec-id PAY` records `"spec_id": "PAY"` on every ledger
    entry even though a numbered workspace was allocated.
- **RUNID-FR-003**: The system shall deliver the run's resolved identity (derived or explicit) to
  every downstream consumer of the run — ledger writes, gate-pause and failure messages, resume
  hints, status output, notifications, oracle dispatch, and the run branch name — so no consumer
  falls back to a literal or the pre-derivation default.
  - *Acceptance*: after a derivation to `030`, the gate-pause/failure output's
    `3pwr run --resume --spec-id 030` hint, the `--status` lookup, the notification subject, and the
    run branch all carry `030`.
  - *Property*: within one run invocation there is exactly one resolved identity value; every
    consumer reads it, none re-reads the raw flag after resolution.
- **RUNID-FR-004**: The spec-conformance gate result shall expose, in its verdict details under
  `requirement_ids`, the sorted requirement ids the scanned tests actually reference for the spec
  under test, so the ledger's verdict entries carry a populated `requirement_ids` array whenever any
  requirement is referenced.
  - *Acceptance*: a gate run over tests referencing `X-FR-001` yields a verdict whose
    spec-conformance details contain `requirement_ids == ["X-FR-001"]` and a ledger verdict entry
    whose `requirement_ids` is non-empty.
  - *Property*: the exposed set equals the referenced-id set the conformance scan computed — sorted,
    deduplicated, and empty exactly when nothing is referenced.
- **RUNID-FR-005**: When a producing stage's post-stage commit is made, the system shall include the
  engine's ledger file (`.3powers/ledger.jsonl`, repo-relative) in the committed path set whenever
  the ledger file exists and is not already listed, so every producing stage commit atomically
  bundles the ledger state that recorded the stage.
  - *Acceptance*: after any producing stage of a live run, the stage's commit contains
    `.3powers/ledger.jsonl` alongside the stage's artifact.
  - *Property*: a stage that produced nothing still forces no commit; the ledger path is appended
    only when a stage commit is being made and never duplicates an already-listed path.
- **RUNID-FR-006**: The oracle stage's instructions shall target the oracle test destination
  `tests/oracle/<spec-id>/` — named by the run's spec id, never by a spec slug — so oracle tests for
  a run identified as `030` land under `tests/oracle/030/`.
  - *Acceptance*: the oracle stage instruction (engine built-in and repo-local template) names
    `tests/oracle/<spec-id>/` as the default destination and contains no slug-based destination;
    a standalone `3pwr oracle dispatch --spec-id 030` collects into `tests/oracle/030/`.

### Non-Functional Requirements

- **RUNID-NFR-001**: The identity derivation and every label it feeds shall be deterministic and
  fully offline — no model call, no network — and shall never enter the deterministic verdict
  computation (ref 3PWR-NFR-001).
  - *Acceptance*: identical folder names yield identical derived ids and identical downstream labels
    with networking disabled.
- **RUNID-NFR-002**: The feature shall introduce no new ledger entry type, no signing change, and no
  verdict-schema change; `3pwr verify` shall stay green on ledgers written before and after this
  change.
  - *Acceptance*: `3pwr verify` passes on a ledger mixing pre-RUNID and post-RUNID entries.

## Success Criteria *(mandatory)*

- **RUNID-SC-001**: A run started without `--spec-id` that allocates `specs/<NNN>-<slug>/` carries
  `<NNN>` as its spec id on every ledger entry, message, hint, notification, and its branch name;
  an explicit `--spec-id` always wins.
- **RUNID-SC-002**: Verify-stage ledger entries carry a non-empty `requirement_ids` array whenever
  the conformance scan found referenced requirements.
- **RUNID-SC-003**: `git log` after any producing stage shows `.3powers/ledger.jsonl` in that
  stage's commit.
- **RUNID-SC-004**: Oracle tests land under `tests/oracle/<spec-id>/`, never under a slug-named
  folder.
- **RUNID-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a
  test naming the RUNID-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id RUNID --stage spec --spec specs/020-run-identity/spec.md`; appended to the signed ledger)_ | | |
