# Feature Specification: Pipeline Gate View — Live Per-Gate Status Rows, Per-Failure Panels, and Noise-Filtered Gate Output

**Spec ID**: GATEPIPE
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     GATEPIPE turns the gate suite's serial output stream into a pipeline view: the gate engine
     emits start/finish events for every gate it runs, a live renderer shows one compact status row
     per gate — status glyph, `gate · tool`, elapsed + summary — updated in place on a capable TTY,
     and each FAILED gate gets its own panel after the live view exits (dim header, indented error
     lines trimmed to the first 30 meaningful lines, an auto-fix hint when one is configured, and
     one line per scanner finding). The old bottom "failures:" block is removed; the panels replace
     it. Node.js ExperimentalWarning noise and blank lines are filtered from the rendered gate
     output unless verbose, and a skipped `spec_integrity` renders with the info glyph, never the
     failure glyph. Cross-refs: 3PWR-FR-026/033/034, GDIAG-FR-001, TRIX-FR-002/006/007,
     CLIUX-FR-002/007/011. Presentation layer only: the verdict schema, the ledger, the exit codes,
     and the `--json` payload bytes are untouched; no trust-spine module (canonical/keys/ledger/
     verify) is changed. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Rationale: this is a
     rendering layer over the existing gate engine, but it adds an event seam to `run_gates` and
     removes an output block, so the machine contracts — the `--json` payload byte-identity, the
     verdict schema shape, the exit codes — must hold under test. Cosmetic was rejected for exactly
     that reason. High-risk was rejected: no trust-spine module is touched, no gate is added,
     removed, or weakened (3PWR-FR-032), and no verdict byte moves. -->

**Status**: Draft

**Input**: Plan 030, Track D (GATEPIPE): gate output is a serial stream — the operator cannot see
at a glance which gates are still running, which passed, and which failed; the detail lines scroll
off-screen; the "failures:" summary at the bottom repeats raw error text with no structure; Node.js
`ExperimentalWarning` noise pollutes the output; and a skipped `spec_integrity` reads like a
failure.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change the gate suite's composition, ordering, any tier threshold, or how any
  gate's pass/fail is judged (3PWR-FR-026/032) — the pipeline view renders what the engine
  already decided.
- Does **not** change the verdict schema, the ledger, any signing behavior, or any exit code; the
  `--json` payload stays byte-identical and is never routed through the rendering layer
  (TRIX-FR-006 property preserved).
- Does **not** execute any `fix_cmd` — the auto-fix hint is a rendered suggestion only; running
  fixes is a separate opt-in capability outside this spec.
- Does **not** filter, trim, or reword anything in the machine-readable verdict — noise filtering
  and line trimming apply to the rendered human output only.
- Does **not** add any dependency: the live rows and the panels render through the engine's
  existing `rich`-backed presentation layer (TRIX).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The gate run reads as a pipeline (Priority: P1)

An operator running `3pwr gate run` on a capable TTY sees one compact status row per gate — which
gates are running, which passed, and which failed, each with its tool and elapsed time — updated
in place instead of a scrolling wall of tool output.

**Acceptance Scenarios**:

1. **Given** a gate run on a capable TTY, **When** a gate starts, **Then** its row shows the
   running glyph, `gate · tool`, and a running indicator; **When** it finishes, **Then** the same
   row shows the pass/fail glyph, the elapsed time, and — for a failure — an error count.
2. **Given** the same run piped to a file or under `NO_COLOR`, **When** the gates finish, **Then**
   the output is sequential plain-text rows, one line per finished gate, with no ANSI escape and
   no in-place update.
3. **Given** `--json`, **When** the run completes, **Then** the payload is byte-identical to the
   pre-pipeline behavior — no pipeline row enters the machine output.

### User Story 2 - Each failure explains itself in its own panel (Priority: P1)

When gates fail, the operator sees one panel per failed gate — the gate, its tool, its elapsed
time, and its first meaningful error lines — instead of a single undifferentiated "failures:"
block at the bottom.

**Acceptance Scenarios**:

1. **Given** a run with two failed gates, **When** the live view exits, **Then** two panels print —
   each with a dim `gate · tool` header, the elapsed time, and the gate's error lines indented and
   trimmed to the first 30 meaningful lines with a truncation note for the rest.
2. **Given** a failed format gate whose configuration carries a fix command, **When** its panel
   renders, **Then** it ends with an `↳ auto-fix: <fix_cmd>` hint line.
3. **Given** a failed dependency or secret scan, **When** its panel renders, **Then** each finding
   is one line naming the finding ID and the package/file.
4. **Given** any failed run, **When** the output ends, **Then** no bottom "failures:" block
   appears — the panels are the failure surface.

### Edge Cases

- A gate that never started (not required by the tier) → no row at all, running or finished.
- A failed gate with zero findings → its panel renders the header with a generic non-zero-exit
  note; nothing crashes on the empty body.
- A finding whose text spans multiple lines → the panel counts and trims *lines*, not findings.
- A terminal that cannot encode the Unicode glyphs → the ASCII glyph set applies unchanged
  (CLIUX-NFR-004).
- Verbose mode → noise lines (blank, `ExperimentalWarning`) are shown, not suppressed.

## Requirements *(mandatory)*

### Functional Requirements

- **GATEPIPE-FR-001**: The gate engine shall emit a start event when each gate begins and a finish
  event carrying the gate's result when it completes, and the gate run shall render these as a
  live per-gate pipeline on a capable TTY: one compact status row per gate — status glyph,
  `gate name · tool`, and elapsed time plus a short summary (an error count for a failure) —
  updated in place from running to finished.
  - *Acceptance*: a run whose `format` gate passes and whose `types` gate fails shows, in gate
    order, a row transitioning `○ format · <tool> (running…)` → `✓ format · <tool> 0.4 s` and a
    row ending `✗ types · <tool> 1.2 s  2 errors`.
  - *Property*: events fire in gate execution order — every start precedes its own finish, and
    finishes arrive in the order the gates ran.
- **GATEPIPE-FR-002**: Off a capable TTY — piped output, `NO_COLOR`, or `--json` — the pipeline
  shall degrade to sequential plain text: one row per *finished* gate, no running-state updates,
  and no ANSI escape; the `--json` payload shall remain byte-identical and never be routed through
  the rendering layer (ref TRIX-FR-006, CLIUX-FR-007/011).
  - *Acceptance*: a piped gate run yields one escape-free line per finished gate; a `--json` run's
    stdout parses as the unchanged verdict payload with no pipeline row in it.
- **GATEPIPE-FR-003**: After the live view exits, the gate run shall print one panel per FAILED
  gate — a dim header naming `gate · tool` and the elapsed time; the gate's error lines indented
  and trimmed to the first 30 meaningful lines (blank and noise lines excluded) with a
  `… N more lines` truncation note; an `↳ auto-fix: <fix_cmd>` hint line when the gate's
  configuration declares a fix command; and, for dependency/secret scan failures, one line per
  finding naming the finding ID and the package/file (plus a remediation hint when the gate
  details carry one). The former bottom "failures:" summary block shall no longer print; the
  panels replace it. Panels shall degrade to plain indented text off a TTY or under `NO_COLOR`.
  - *Acceptance*: a failed gate with 40 meaningful error lines renders exactly 30 plus a
    `… 10 more lines` note; a failed format gate with a configured fix command renders the
    auto-fix hint; a failed run's human output contains no "failures:" block.
- **GATEPIPE-FR-004**: The rendered gate output shall suppress noise unless verbose: blank lines
  and Node.js `ExperimentalWarning` lines are excluded from pipeline summaries and failure panels
  by default and shown under the verbose verbosity; the machine-readable verdict is never
  filtered.
  - *Acceptance*: a failed gate whose output carries `ExperimentalWarning` lines renders a panel
    without them by default and with them under verbose; the verdict JSON carries the unfiltered
    findings either way.
- **GATEPIPE-FR-005**: A skipped `spec_integrity` gate shall render in the pipeline with the
  dim info/skip glyph (`–`), never the failure glyph (`✗`) — a not-yet-approved spec reads as
  informational, not as a failure.
  - *Acceptance*: a gate run whose spec has no recorded approval renders the `spec_integrity` row
    with `–` and the skip summary; no `✗` appears on that row.

### Non-Functional Requirements

- **GATEPIPE-NFR-001**: The pipeline view shall be presentation-only and deterministic given the
  event stream: it never enters the verdict computation (ref 3PWR-NFR-001), makes no network call,
  and identical gate results render identical plain-text degradation output.
  - *Acceptance*: two runs over identical inputs produce identical plain-mode pipeline rows and
    panels; the verdict bytes are unchanged with the pipeline on or off.

## Success Criteria *(mandatory)*

- **GATEPIPE-SC-001**: `3pwr gate run` shows one compact status row per gate, updated in place on
  a capable TTY and degrading to sequential escape-free rows when piped.
- **GATEPIPE-SC-002**: Every failed gate has its own panel with trimmed, noise-filtered error
  lines; the bottom "failures:" block is gone.
- **GATEPIPE-SC-003**: `ExperimentalWarning` does not appear in default (non-verbose) output.
- **GATEPIPE-SC-004**: `spec_integrity` "skipped" renders as `–`, not `✗`.
- **GATEPIPE-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) —
  a test naming the GATEPIPE-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id GATEPIPE --stage spec --spec specs/023-gate-pipeline/spec.md`; appended to the signed ledger)_ | | |
