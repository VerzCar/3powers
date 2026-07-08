# Feature Specification: Gate Failure Diagnostics — Failed Gates Named Inline, `gate run --id <NNN>`, Prerequisite Install Hints Before Any Gate Runs, and Resume Hints That Carry the Real Run Number

**Spec ID**: GDIAG
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     GDIAG closes the gate-failure UX gap left after RUNID (020) resolved the run's real identity:
     today a red gate suite surfaces as a single opaque "gates red" line, inspecting it requires
     knowing the governing spec's file path even though the user only has the run's NNN, and a gate
     that could not run because its tool is absent is buried in raw stderr instead of stopping the
     run up-front with an install hint. GDIAG makes the failure diagnosis inline (each failed gate,
     its adapter tool, and its first actionable line), adds the `--id <NNN>` shorthand to
     `gate run`, detects missing prerequisites BEFORE any gate command executes (setup exit path,
     per-tool install hints from the adapter's declarative toolchain), and guarantees every
     resume/inspect hint interpolates the run's resolved identity. Cross-refs: RUNID-FR-001/003,
     3PWR-FR-026/032/034/048, 3PWR-NFR-007/015, AUTOX-FR-009. Diagnostics and CLI-surface plumbing
     only; no trust-spine module (canonical/keys/ledger/verify) is changed, no gate is added or
     removed from any tier, and no verdict-schema change is introduced. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Rationale: this is
     diagnostics and CLI plumbing — a richer rendering of an existing event, a spec-resolution
     shorthand, a pre-flight probe over data the adapter manifests already declare, and hint
     interpolation. No trust-spine module is touched, no gate threshold changes, and the gate suite's
     composition is unchanged (3PWR-FR-032). Cosmetic was rejected: the prerequisite pre-check
     changes control flow (a run stops on the setup path instead of producing a misleading red
     verdict), so it must hold behavioral invariants under test. High-risk was rejected: no trust
     primitive is involved. Standard applies — the same latitude RUNID (020) used. -->

**Status**: Draft

**Input**: Plan 030, Track B (GDIAG): when gates fail the operator sees one "gates red" line with a
generic `--spec <spec>` inspect hint and, historically, a `--spec-id RUN` placeholder; which gates
failed, with which tool, and why is invisible without re-running; a missing prerequisite (e.g. the
formatter not installed) surfaces only as raw toolchain noise inside a red gate instead of a named
install step before anything runs.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change the gate suite's composition, ordering, any tier threshold, exit-code
  contract values, or the two mandatory human gates (3PWR-FR-006/026/032, AUTOX-FR-009).
- Does **not** change how a gate's *own* failure is judged — a genuine red stays red; only the
  rendering and the pre-run prerequisite path are new.
- Does **not** weaken the quarantine model (3PWR-NFR-015): optional gates, the design oracles, and
  the opt-in mutation gate keep their existing skip/quarantine behavior when their tool is absent;
  the hard stop applies only to non-optional gates.
- Does **not** make the core language-aware: every install hint and probe command is declarative
  adapter-manifest data (`toolchain:`), never core logic (3PWR-NFR-007).
- Does **not** change how the run's identity is derived — that is RUNID's (020); GDIAG only
  *consumes* the resolved identity in its hints.
- Does **not** alter the verdict schema, the ledger, or any signing behavior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A red gate suite diagnoses itself inline (Priority: P1)

An operator whose `3pwr run` goes gates-red wants to see, without re-running anything, *which*
gates failed, with *which* tool, and the first line they can act on — plus copy-pasteable resume
and inspect commands that already carry the run's real number.

**Acceptance Scenarios**:

1. **Given** a run whose Verify verdict fails 3 of 9 gates, **When** the gate-red event is
   rendered, **Then** the output contains a header naming the counts (`gates failed (3 of 9):`) and
   one row per failed gate showing the gate name, its adapter tool, and its first actionable error
   line.
2. **Given** the same failure for a run identified as `030`, **When** the summary is rendered,
   **Then** it ends with `Resume: 3pwr run --resume --spec-id 030` and
   `Inspect: 3pwr gate run --id 030` — the real number, never a placeholder.
3. **Given** a gate-red event carrying no verdict payload (a simulated/legacy emitter), **When** it
   is rendered, **Then** the plain one-line "gates red" message appears unchanged.

### User Story 2 - Inspecting by run number, not file path (Priority: P1)

A user who just watched run `030` fail wants `3pwr gate run --id 030` to re-run the suite against
that run's spec without hunting for the spec file's path.

**Acceptance Scenarios**:

1. **Given** exactly one folder `specs/030-add-button/` with a resolvable spec, **When**
   `3pwr gate run --id 030` runs, **Then** it targets the same spec as
   `3pwr gate run --spec specs/030-add-button/spec.md`.
2. **Given** no folder matching `specs/031-*/`, **When** `--id 031` is passed, **Then** the command
   errors with a message naming the missing folder pattern and exits nonzero without running gates.
3. **Given** two folders matching the prefix, **When** `--id` is passed, **Then** the command
   errors naming both candidates and exits nonzero without running gates.
4. **Given** both `--id` and `--spec` on one invocation, **When** the command is parsed, **Then**
   it is rejected with a clear error and a nonzero exit.

### User Story 3 - Missing prerequisites stop the run before it lies (Priority: P1)

A user on a machine missing the project's formatter wants the gate run to say "install X" up
front — with the exact install command — instead of producing a red verdict that looks like a code
problem.

**Acceptance Scenarios**:

1. **Given** a required tool of a non-optional gate that fails its declared toolchain probe,
   **When** a gate run starts, **Then** no gate command executes, the process exits with the setup
   exit code, and a `⚠ prerequisites missing` block lists each missing tool with the adapter's
   declared install hint.
2. **Given** the mutation gate's tool absent (an opt-in, quarantine-safe gate), **When** a gate run
   starts, **Then** the run proceeds and mutation skips/quarantines exactly as before — the
   pre-check never hard-stops on a quarantine-safe gate.
3. **Given** a report-only brownfield run with a missing tool, **When** it starts, **Then** it
   proceeds (the on-ramp never hard-stops) and the per-gate missing-tool findings surface as
   before.

### Edge Cases

- A tool with no `probe:` declared in the toolchain → assumed present; the existing in-gate
  missing-tool detection still catches it (nothing is silently passed).
- A gate whose manifest declares no command or no `requires:` → nothing to probe; the gate skips as
  before.
- `diff_coverage` required without `tests` → the tests tool is still probed, because diff-coverage
  forces the test run.
- Several gates requiring the same tool → the tool is probed once and listed once.
- An adapter with no `toolchain:` section at all → no probes run; behavior is unchanged.
- `--id` matching a folder that contains no resolvable spec → a clear error naming the folder, not
  a stack trace.

## Requirements *(mandatory)*

### Functional Requirements

- **GDIAG-FR-001**: When a run's deterministic gate suite fails, the gate-red event rendering shall
  present a structured summary: a header naming the failed and total gate counts, and one row per
  failed gate showing the gate name, its adapter tool, and the first actionable line of its
  findings.
  - *Acceptance*: a verdict failing `format` (biome) and `tests` (vitest) renders
    `gates failed (2 of N):` with rows `format · biome` and `tests · vitest`, each carrying its
    first findings line.
  - *Property*: the summary is a pure function of the event's verdict payload; an event with no
    verdict payload renders the pre-existing one-line message byte-for-byte.
- **GDIAG-FR-002**: `3pwr gate run` shall accept `--id <NNN>` as a spec-resolution shorthand: the
  engine resolves `specs/<NNN>-*/` under the repository root, requires exactly one matching
  directory, and targets that feature's resolvable spec.
  - *Acceptance*: with exactly one `specs/030-*/` folder, `gate run --id 030` runs against the same
    spec path as `gate run --spec specs/030-.../spec.md`.
  - *Property*: zero matches and multiple matches each produce a user-facing error naming the
    pattern or the candidates; no gate runs in either case.
- **GDIAG-FR-003**: `3pwr gate run` shall reject `--id` combined with `--spec` with a clear error
  and a nonzero exit — the two spec sources are mutually exclusive.
  - *Acceptance*: `gate run --id 030 --spec x/spec.md` exits nonzero with an error naming the
    conflict; no gate runs.
- **GDIAG-FR-004**: Before executing any gate command, the system shall probe the availability of
  every distinct tool required (via the manifest's `requires:`) by a non-optional gate of the run,
  using the adapter manifest's declarative `toolchain:` probe; when any such tool is missing, the
  run shall stop on the setup path (the setup exit code) and print a prerequisites block with one
  line per missing tool carrying the adapter's declared install hint — without running any gate.
  - *Acceptance*: a required formatter failing its probe yields the setup exit code, the
    `⚠ prerequisites missing` block with the manifest's install command, and no executed gate
    command.
  - *Property*: the missing set is deterministic given the manifest and the local toolchain; every
    hint comes from manifest data, never from core logic.
- **GDIAG-FR-005**: The prerequisite pre-check shall never hard-stop on a quarantine-safe gate:
  the opt-in mutation gate and the design oracles keep their existing skip/quarantine behavior when
  their tool is absent, and a report-only run never hard-stops on prerequisites.
  - *Acceptance*: a missing mutation tool leaves the gate run proceeding with mutation skipped; a
    report-only run with a missing required tool proceeds and surfaces the per-gate missing-tool
    finding as before.
- **GDIAG-FR-006**: Every resume and inspect hint the run and gate surfaces print shall interpolate
  the run's resolved spec id — `Resume: 3pwr run --resume --spec-id <id>` and
  `Inspect: 3pwr gate run --id <id>` — never a literal placeholder.
  - *Acceptance*: after a run resolved to `030` fails or pauses, every printed hint contains `030`;
    no output contains a placeholder identity.

### Non-Functional Requirements

- **GDIAG-NFR-001**: All diagnostics shall be deterministic and fully offline — no model call, no
  network — and shall never enter the deterministic verdict computation (ref 3PWR-NFR-001);
  identical inputs render identical summaries.
  - *Acceptance*: the gate-red summary and the prerequisites block are stable across repeated runs
    with networking disabled.
- **GDIAG-NFR-002**: The core shall stay language-agnostic (ref 3PWR-NFR-007): probe commands and
  install hints are read exclusively from the adapter manifest's `toolchain:` data; adding or
  changing a language's hints requires only a manifest edit.
  - *Acceptance*: no language- or tool-specific string used by the pre-check exists in core code.

## Success Criteria *(mandatory)*

- **GDIAG-SC-001**: A gates-red run shows each failed gate's name, tool, and first actionable line
  inline, plus filled-in Resume/Inspect command lines carrying the run's real number.
- **GDIAG-SC-002**: `3pwr gate run --id <NNN>` works identically to `--spec` with the resolved
  path; zero/multiple matches and `--id`+`--spec` are clear, nonzero-exit errors.
- **GDIAG-SC-003**: A missing required tool of a non-optional gate stops the run with the setup
  exit code and its install hint before any gate command executes; quarantine-safe gates and
  report-only runs are unaffected.
- **GDIAG-SC-004**: No printed hint ever carries a placeholder identity.
- **GDIAG-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a
  test naming the GDIAG-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id GDIAG --stage spec --spec specs/021-gate-diagnostics/spec.md`; appended to the signed ledger)_ | | |
