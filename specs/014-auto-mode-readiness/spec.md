# Feature Specification: Auto Full-Mode Readiness & the Run Error Contract — One-Command End-User Setup, Recorded & Resumable Failures, Persisted Diagnostics, and a True Getting-Started

**Spec ID**: AUTOX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     AUTOX is the end-user experience counterpart to EXEC (spec 009) / RUNLIVE (spec 011) and the
     onboarding pair ONBRD (003) / INITX (007): those delivered the native executive, hardening, and
     `3pwr init` — but readiness at init and preflight at run are two disjoint mechanisms (init can say
     "ready" while `3pwr run --mode auto` still refuses to start), no run failure is ever recorded (so
     `--status` cannot say "failed at stage X"), agent output is not persisted for diagnosis, exit codes
     conflate distinct failures, failure-resume depends on auto-commit, and the docs walk a maintainer
     through the gates-only path rather than an end user to a green auto run. AUTOX closes those gaps.
     Cross-refs: EXEC-FR-015/016, RUNX-FR-009..012, RUNLIVE-FR-002/004/005/010, ONBRD-FR-015,
     INITX-FR-009/010, PHASE (013, complementary), 3PWR §6. Additive ledger content only; no
     trust-spine module change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: readiness/preflight unification, run failure recording, transcript persistence, exit-code
     contract, and docs — orchestration + UX, not the trust-spine modules (canonical/keys/ledger/verify),
     which are only appended to through their existing APIs with additive entry content. It weakens no
     gate (3PWR-FR-032): failures become MORE visible, never less. The regression risks are a changed
     exit-code surprising a script (mitigated by documenting the contract as part of this spec) and a
     transcript leaking a secret (mitigated by AUTOX-NFR-002). Standard applies. -->

**Status**: Draft

**Input**: Follow-up to the PHASE completeness review (spec 013): "is anything else missing — docs, and
the engine at the init phase, so an end user is fully set up for auto full mode; and what about error
responses during run?" A code review confirmed: `3pwr init`'s readiness checklist covers five facts (CI,
constitution, AGENTS.md, judiciary diversity, git presence) while the real auto-run preflight
(`runpreflight.check_native` + signer resolution) runs only at `3pwr run` time — two disjoint mechanisms
that can disagree; an env-supplied signing key is trusted unverified at init; no run failure
(dispatch_failed / artifact_missing / gates_red / verdict_error) is recorded anywhere, so no status
command can show it; agent stdout/stderr is not persisted (≤400 chars in the message; nothing at all
when streaming); exit code 2 conflates distinct failure classes and a paused human gate exits 0;
failure-resume works only when auto-commit checkpoints exist; and the getting-started walks this repo's
maintainer path, troubleshooting covers no mid-run failure, and shipped `roles.yaml` still carries
Spec-Kit-era language. This spec makes auto full mode reachable, diagnosable, and resumable for an end
user.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):** `3pwr init` seeds the trust-spine layout, signer, configs,
  agent manifests, constitution, and prints a readiness checklist (ONBRD-FR-015, INITX-FR-009/010).
  `3pwr run` fails fast pre-dispatch on an unresolvable signer and on `runpreflight.check_native`
  (headless coder configured + manifest + CLI on PATH; different-family oracle) with per-item fixes and
  the offline alternatives (EXEC-FR-015/016, RUNX-FR-009..012). Dispatch is bounded by timeout + retry
  with per-stage `--json` results (RUNLIVE-FR-004/005/006); successful stages checkpoint-commit and
  resume skips them (RUNLIVE-FR-010). `3pwr deps-check` probes declared third-party tools (3PWR-FR-048).
- **Where the seams are:** readiness (`scaffold.readiness` + `cli.py` `_readiness_checklist`) and run
  preflight (`runpreflight.py`) share no code and check different things; `cmd_run`'s failure branches
  (`cli.py` ~2317–2375) print + exit without appending anything to the ledger; the native Verify path
  (`_native_verdict`) runs the gate suite without a ledger append, unlike standalone `3pwr gate run`;
  `dispatch_agent` captures output in memory only, and `capture_output=not stream` means a streamed run
  keeps nothing; `orchestrate.resume_start_index` derives only from approved gates + committed
  checkpoints; `.3powers/runs/` is already created by init and is empty today.
- **Exit codes today:** 0 = done *or* paused-at-human-gate; 1 = gates red; 2 = usage *and* every
  dispatch/timeout/artifact/verdict-error failure.
- **Docs today:** `docs/getting-started.md` §1–7 is the gates-only path inside this repo (auto run is a
  closing mention); `docs/troubleshooting.md` covers signing key, quarantined scanner, missing agent
  CLI, and spec_integrity — no mid-run failure class, no failure-resume; `.3powers/config/roles.yaml`
  still says "in whatever Spec Kit integration you initialized".
- **Guardrail:** additive only. No gate, verdict-bytes, chain, or signing change; new ledger content
  uses existing append APIs; `3pwr verify` stays green over ledgers containing the new records.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** verify agent-CLI *authentication* or account state — no network or provider call is made
  (ONBRD-NFR-002 / EXEC-NFR-001 hold); readiness reports PATH presence and says honestly that
  authentication is not checkable offline.
- Does **not** auto-install any third-party tool (agent CLIs, toolchains); it detects, reports, and
  names the fix — installation stays with the user (3PWR-FR-048 stays a preflight, never a gate).
- Does **not** change any gate, threshold, verdict bytes, ledger chain/signing format, or the two
  mandatory human gates (3PWR-FR-032, ONBRD-NFR-004); ledger additions are additive entry content.
- Does **not** add a model-driven "fix it for me" repair loop for failed runs — remediation stays
  deterministic text; agentic repair is a separate concern.
- Does **not** rewrite historical plan/spec documents or the STATUS invariant — forward-looking docs
  only (per DOCX).
- Does **not** deliver PHASE (spec 013) — phased dispatch is complementary; this spec's run records and
  transcripts must simply not conflict with per-phase dispatch later.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One honest answer to "am I ready for auto mode?" (Priority: P1)

An end user who just ran `3pwr init` in their own repository wants init's readiness report — and a
re-runnable standalone check — to cover *every* prerequisite the auto run will actually enforce, so
"ready" at init means `3pwr run --mode auto` will not refuse to start.

**Acceptance Scenarios**:

1. **Given** a repo where the coder agent CLI is not installed, **When** the user reads init's readiness
   report (or runs the standalone check), **Then** the missing CLI is reported with the exact fix —
   before any run is attempted.
2. **Given** `THREEPOWERS_SIGNING_KEY_FILE` pointing at a missing or unreadable file, **When** init (or
   the check) runs, **Then** the key is reported as unresolved with the fix, not silently trusted.
3. **Given** every prerequisite met, **When** the user runs `3pwr run --mode auto`, **Then** the run's
   own preflight agrees with the readiness report (they cannot drift — one shared source of checks).

### User Story 2 - A failed run says so, everywhere (Priority: P1)

A user whose auto run failed mid-lifecycle wants the failure recorded and visible — `3pwr run --status`
and `3pwr status` name the failed stage and failure class — and wants the agent's output preserved on
disk, so diagnosis does not depend on scrollback or a 400-character excerpt.

**Acceptance Scenarios**:

1. **Given** a dispatch failure at the tasks stage, **When** the user runs `3pwr run --status`, **Then**
   the tracker shows the run failed at `tasks` with the failure class and when — distinct from paused.
2. **Given** any stage attempt (streamed or not), **When** the user opens the run's transcript location,
   **Then** the agent's stdout/stderr for that attempt is there, and the failure message printed the
   path.
3. **Given** a gate-red at Verify during a run, **When** the user inspects the ledger, **Then** the red
   verdict is recorded there just as a standalone `3pwr gate run` would have recorded it.

### User Story 3 - Scripts can react: a stable exit-code and status contract (Priority: P2)

A user wrapping `3pwr run` in CI or a script wants documented, stable exit codes and JSON status strings
that distinguish done / paused-at-human-gate / gates-red / setup-or-dispatch-failed, so automation can
branch without parsing prose.

**Acceptance Scenarios**:

1. **Given** a run that pauses at a human gate, **When** the wrapper checks the exit code, **Then** it is
   a documented code distinct from both a completed run and any failure.
2. **Given** the documented contract, **When** any failure branch fires, **Then** the JSON `status`
   string and exit code match the documentation exactly (covered by tests).

### User Story 4 - Resume works after a failure, not only after a gate (Priority: P2)

A user whose run failed mid-way — including with auto-commit off — wants `3pwr run --resume` to continue
from the last successfully completed stage instead of refusing with "no paused run to resume".

**Acceptance Scenarios**:

1. **Given** a run that failed at the oracle stage with auto-commit off (working tree intact), **When**
   the user resumes, **Then** execution continues at the oracle stage; completed stages are not
   re-dispatched.
2. **Given** nothing to resume (no progress recorded), **When** the user resumes, **Then** the message
   says so and names how to start fresh.

### User Story 5 - An end user can get to a green auto run from the docs alone (Priority: P1)

A newcomer with their own repository wants a linear getting-started — install, `3pwr init`, key export,
roles + agent CLI (including the note that login/auth is the provider's business), `3pwr run --mode
auto`, what success looks like, what the two human gates look like — plus troubleshooting entries for
each run failure class keyed to the words the CLI actually prints.

**Acceptance Scenarios**:

1. **Given** only the docs, **When** a newcomer follows the end-user path in order on a prepared
   machine, **Then** they reach a completed auto run without consulting the repo's maintainer docs.
2. **Given** a printed failure ("dispatch failed at …", "artifact missing at …", "gates red"), **When**
   the user searches troubleshooting, **Then** an entry with that wording explains cause, fix, and the
   resume command.

### Edge Cases

- Init runs on a machine with no agent CLI at all → init still completes (seeding is independent);
  readiness reports the auto path as not-ready with fixes, and names the offline alternatives
  (RUNX-FR-012).
- The readiness check is run outside an initialized repo → actionable "run `3pwr init` first", not a
  stack trace (EXEC-NFR-005).
- A transcript would capture a secret an agent CLI echoes → known credential-shaped env values are
  redacted before persisting (AUTOX-NFR-002); pass-through to the child process is unchanged.
- The ledger already contains old-format entries → `3pwr verify` still passes; new records are additive
  and older tools that ignore unknown entry kinds keep working.
- A failure occurs before any stage completes → status shows failed-at-first-stage; resume offers a
  fresh start rather than pretending progress exists.
- Two failures in a row → the latest failure record wins in status; earlier ones remain in the ledger
  as history (append-only, 3PWR-FR-069).

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where a value is derived or parsed (3PWR-FR-024). CLI/file locations
  appear where they ARE the contract under specification (readiness, transcripts, exit codes), not as
  implementation detail (3PWR-FR-007).
-->

### Functional Requirements

#### Readiness for auto full mode (init + standalone)

- **AUTOX-FR-001**: When a signing key is supplied via environment (file or inline), `3pwr init` shall
  verify it resolves to a usable signer and shall report an unresolved key in the readiness output with
  the exact fix, instead of trusting the environment silently.
  - *Acceptance*: init with `THREEPOWERS_SIGNING_KEY_FILE` pointing at a missing/unreadable/invalid file
    reports the key as not-ready with a fix; a valid env key reports ready.
- **AUTOX-FR-002**: The readiness report shall cover every prerequisite the auto run's preflight
  enforces — resolvable signer, headless coder integration (configured, manifest present, CLI on PATH),
  and a different-family oracle (or a recorded diversity deviation) — sourced from the same checks the
  run uses, so the two can never drift.
  - *Acceptance*: any condition that would make `3pwr run --mode auto` refuse pre-dispatch appears as a
    not-ready item in readiness with the same named fix.
  - *Property*: for identical repo + config + PATH state, readiness's auto-run verdict and the run
    preflight's verdict are identical.
- **AUTOX-FR-003**: The system shall provide a standalone, re-runnable readiness command that performs
  the full auto-run preflight plus a dependency summary (3PWR-FR-048) and reports one overall
  ready/not-ready verdict with a per-item fix — offline, read-only, and never a gate.
  - *Acceptance*: the command exits distinctly for ready vs not-ready, lists each unmet item with its
    fix, supports `--json`, and changes nothing on disk.
- **AUTOX-FR-004**: Readiness output shall state honestly what is not checkable offline — agent-CLI
  authentication is reported as "present, authentication not verified" — and shall never claim a
  prerequisite it did not probe.
  - *Acceptance*: a present-but-logged-out CLI is reported as present with the authentication caveat;
    no readiness line overstates what was checked.
- **AUTOX-FR-005**: When init completes with unmet auto-run prerequisites, the system shall print the
  remaining steps as exact commands in dependency order (e.g. export line, CLI install, roles change),
  derived from the readiness result.
  - *Acceptance*: after an init with N unmet items, the next-steps list contains exactly those N fixes
    in an executable order.

#### The run error contract (recorded, diagnosable, resumable)

- **AUTOX-FR-006**: When a run terminates in a failure (dispatch failure, timeout, missing artifact,
  gate-red, verdict-error), the system shall append a signed run-failure record — stage, failure class,
  attempt count, and a bounded detail — to the ledger before exiting, using existing append APIs.
  - *Acceptance*: after each failure class, the ledger's newest entry names the stage and class;
    `3pwr verify` stays green.
- **AUTOX-FR-007**: `3pwr run --status` and `3pwr status` shall show a failed run as failed — naming the
  stage, failure class, and time of the most recent failure — distinctly from paused-at-gate and from
  in-progress.
  - *Acceptance*: after a mid-run failure, both commands show "failed at <stage> (<class>)"; after a
    successful resume past it, they no longer show the run as failed.
- **AUTOX-FR-008**: The system shall persist each stage attempt's agent output (stdout and stderr) to a
  per-run transcript location under the existing runs directory — including when streaming to a TTY —
  and every failure message shall name the transcript path.
  - *Acceptance*: after any attempt, the transcript file exists and contains the attempt's output; the
    printed failure includes its path; streaming mode no longer loses output.
- **AUTOX-FR-009**: The system shall document and stabilize the run's machine contract: the JSON
  `status` strings and exit codes, with distinct exit codes for completed, paused-at-human-gate,
  gates-red, and setup/dispatch failure (usage errors keeping their own).
  - *Acceptance*: the documented table matches behavior under test for every branch; paused-at-gate is
    distinguishable from completed by exit code alone.
  - *Property*: each terminal run outcome maps to exactly one documented (status, exit-code) pair.
- **AUTOX-FR-010**: The system shall record run progress such that `3pwr run --resume` continues from
  the last successfully completed stage after a failure regardless of the auto-commit setting (given the
  working tree is intact), never re-dispatching a completed stage (extends EXEC-FR-008 /
  RUNLIVE-FR-010); with no recorded progress it shall say so and name the fresh-start command.
  - *Acceptance*: a `--no-auto-commit` run failing at stage k resumes at stage k; stages 1..k-1 are not
    re-dispatched; with nothing to resume the message names the fresh start.
- **AUTOX-FR-011**: When the in-run Verify stage produces a verdict, the system shall record it in the
  ledger with the same content a standalone `3pwr gate run` records, so a run's red or green verdict is
  never invisible to the trust spine.
  - *Acceptance*: after an in-run Verify, the ledger contains the verdict entry; `3pwr verify` and
    `advance` see it exactly as a standalone gate run's.

#### Documentation for the end user

- **AUTOX-FR-012**: The getting-started documentation shall lead with a linear end-user path — install,
  `3pwr init` in the user's own repository, key export, roles + agent-CLI setup (naming that
  authentication belongs to the provider's CLI), readiness check, `3pwr run --mode auto`, what a
  successful run and its two human gates look like — separate from this repo's maintainer walkthrough.
  - *Acceptance*: a doc review confirms the path is complete, in order, and self-sufficient; each
    command shown is copy-runnable; the stale version string is corrected.
- **AUTOX-FR-013**: The troubleshooting documentation shall carry an entry for each run failure class —
  dispatch failed, timeout, artifact missing, gates red, verdict error, nothing-to-resume — keyed to the
  exact phrases the CLI prints, each with cause, fix, and the resume command.
  - *Acceptance*: for every failure phrase the CLI can print, a search of troubleshooting finds a
    matching entry.
- **AUTOX-FR-014**: The CLI reference shall document the run exit-code and JSON-status contract
  (AUTOX-FR-009) and the transcript location (AUTOX-FR-008) as stable interfaces.
  - *Acceptance*: the reference table exists and matches the tested behavior.
- **AUTOX-FR-015**: Shipped configuration and templates shall carry no residual Spec-Kit-era language
  (e.g. the roles config's "Spec Kit integration" wording), extending the DOCX sweep to the files it
  missed.
  - *Acceptance*: a search of shipped `.3powers/` config/templates finds no Spec-Kit reference
    presented as current.

### Non-Functional Requirements

- **AUTOX-NFR-001**: Readiness, preflight, status, and the failure taxonomy shall be deterministic and
  fully offline — no network or model call anywhere in this feature (ref 3PWR-NFR-001, ONBRD-NFR-002,
  EXEC-NFR-001).
  - *Acceptance*: all new checks/records run with networking disabled; identical state yields identical
    output.
- **AUTOX-NFR-002**: Transcripts and failure records shall never persist a credential: known
  credential-shaped environment values are redacted before writing, and no provider secret is logged or
  stored (preserves EXEC-FR-012 / RUNLIVE-FR-009).
  - *Acceptance*: a test seeding fake credentials in the environment finds none of their values in any
    persisted transcript or ledger detail.
- **AUTOX-NFR-003**: All ledger additions shall be additive: the chain, signing, and `verify` behavior
  are unchanged, existing ledgers remain valid, and no verdict bytes change (ref 3PWR-NFR-006,
  3PWR-FR-032).
  - *Acceptance*: `3pwr verify` passes over ledgers with and without the new records; existing
    verdict-bytes tests are untouched and green.
- **AUTOX-NFR-004**: The engine stays green under its own gates across this change, and
  `docs/STATUS.md` remains the single home of implementation status (ref 3PWR-NFR-006, DOCX-NFR-003).
  - *Acceptance*: self-application gate run + ruff/mypy/pytest green; STATUS updated once at delivery.

## Success Criteria *(mandatory)*

- **AUTOX-SC-001**: On a machine with an unmet prerequisite, init's readiness and the standalone check
  name it with the fix, and `3pwr run --mode auto`'s preflight agrees — one source of truth, no drift.
- **AUTOX-SC-002**: Every terminal run failure is visible afterwards: in the ledger, in `--status` /
  `3pwr status` (stage + class), and in a persisted transcript whose path the failure message printed.
- **AUTOX-SC-003**: A script can distinguish done / paused / gates-red / setup-failure from documented
  exit codes alone; the JSON status contract is documented and covered by tests.
- **AUTOX-SC-004**: `3pwr run --resume` continues after a mid-run failure with auto-commit off; no
  completed stage is ever re-dispatched.
- **AUTOX-SC-005**: A newcomer reaches a completed auto run from the docs alone, and every failure
  phrase the CLI prints has a troubleshooting entry; no shipped config presents Spec Kit as current.
- **AUTOX-SC-006**: No gate, verdict bytes, chain, or signing behavior changed; `3pwr verify` green over
  new-format ledgers; the engine's own gates stay green.
- **AUTOX-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test
  naming the AUTOX-FR id, or a recorded documentation review where prose is what is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id AUTOX --stage spec --spec specs/014-auto-mode-readiness/spec.md`; appended to the signed ledger)_ | | |
