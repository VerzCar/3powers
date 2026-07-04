# Feature Specification: A First-Class `3pwr` CLI Experience — a Shared Structured-Output Toolkit, Consistent Color & Status Vocabulary, an Auto-Mode "You Are Here" Stage Header, and Opt-In Verbosity & UI Preferences

**Spec ID**: CLIUX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     CLIUX is the presentation-layer counterpart to INITX (007) — which introduced the zero-dependency
     styling primitives (`style.py`: Styler, semantic vocabulary, status glyphs, NO_COLOR/TTY/--json
     handling) — and to EXEC (009) / RUNLIVE (011) / AUTOX (014), which built the native executive and
     its live stage tracker. Those delivered the *pieces*; today they are applied unevenly: only a few of
     the ~36 `3pwr` subcommands render richly, many still print plain run-on one-liners, there is no
     shared *structured*-output vocabulary (headers, key/value blocks, aligned tables, dividers), the run
     tracker is a single in-place line rather than a persistent stage header, and there is no verbosity
     control or user-facing UI configuration. CLIUX makes the CLI's human output first-class and
     consistent across every command while keeping machine output untouched. Cross-refs: INITX-FR-013/014,
     INITX-NFR-004, RUNLIVE-FR-006, AUTOX-FR-007, 3PWR-NFR-001, 3PWR §6/§8. Presentation only; no
     trust-spine module change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: a human-output presentation layer plus verbosity/config plumbing — orchestration + UX, not
     the trust-spine modules (canonical/keys/ledger/verify), which are not touched. It weakens no gate
     (3PWR-FR-032). The one real regression risk is that a changed human line, or color bytes, could
     surprise a script or corrupt a parseable payload; this spec turns "the `--json` payload and exit codes
     are byte-/behavior-identical, machine output never routed through the styler" into an explicit, tested
     requirement (CLIUX-FR-007, CLIUX-NFR-002), the same latitude and reasoning AUTOX (014) used to land on
     Standard. Cosmetic was considered and rejected: this touches shared rendering code used by every
     command and must hold machine-output invariants under test. Standard applies. -->

**Status**: Draft

**Input**: User request: "I want the `3pwr` CLI to have a great CLI UI and user experience. Do we need a
third-party dependency or can we build our own? I want all the `3pwr` command output to be readable and
well structured — no long one-line text, good structured answers, nice color, nice feedback interaction.
And it would be nice to always have a header when in auto mode, or at least to see which stage I'm
currently in and that everything is running in that stage." A codebase review confirmed the answer to the
dependency question: the engine already ships a zero-dependency styling layer (`style.py`) and a live
stage tracker (`orchestrate.py`), and deliberately avoids `rich`/`curses`/`colorama` for offline
self-containment (3PWR-NFR-004/010) and byte-identical `--json` (INITX-FR-014). This spec **extends the
home-grown layer** rather than adopting a TUI library, and closes the consistency, stage-header, and
configurability gaps.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):** `style.py` provides `color_enabled()` (honors `--json`,
  `--yes`, `NO_COLOR`, `THREEPOWERS_FORCE_COLOR`, and TTY detection) and a frozen `Styler` with a semantic
  vocabulary (`ok`/`err`/`warn`/`head`/`bold`/`dim`/`mark`) over ANSI SGR codes, plus status glyphs
  (`✓ ✗ ⚠ ＋ – ⓘ`); a disabled styler is a transparent no-op so plain output is byte-identical to
  un-styled text (INITX-FR-013/014, INITX-NFR-004). `cli.py`'s `_print(obj, as_json, human)` dual-emits a
  JSON payload or a human string per command, and `_format_verdict` already renders a structured gate
  verdict. `orchestrate.py` provides pure, tested rendering — `render_tracker` (a one-line
  `✓/▶/·` stage strip), `format_event`, `tracker_frame` — and a dependency-free `Tracker` that on a TTY
  redraws a single line in place (`\r` + clear-line) and off a TTY falls back to the plain streamed event
  log; the eight stages live in `lifecycle.py` (`STAGES = Discovery, Spec, Plan, Build, Verify, Review,
  Ship, Observe`) and the twelve lifecycle steps in `orchestrate.py`.
- **Where the seams are:** the styling primitives are applied unevenly — `init`, `gate` verdicts,
  `deps-check`, and the `run` tracker render richly, but many of the ~36 subcommands still emit a plain
  run-on `print()` line; there is no shared vocabulary for a *section header*, a *key/value block*, an
  *aligned table*, or a *divider*, so each command that wants structure hand-rolls it; the run view is a
  single in-place line, not a persistent header a user can glance at to see "which stage am I in and is it
  running"; there is no `--quiet`/`--verbose`; and there is no UI config file (`.3powers/config/` holds
  `risk-tiers`, `roles`, `context`, `dependencies`, `observability`, `design-oracles` — no `ui.yaml`),
  though `config.py`'s `_load_yaml` + typed `Settings` accessors are the established pattern for adding one.
- **The dependency question, answered:** the engine's runtime dependencies are `cryptography` and `PyYAML`
  only; the presentation layer is intentionally third-party-free and network-free so the tool stays
  offline-reconstructable (3PWR-NFR-004/010) and so color can never corrupt a `--json` payload
  (INITX-FR-014). This spec keeps that stance: build on the home-grown ANSI layer, add no rendering library.
- **Guardrail:** presentation only. No gate, threshold, verdict bytes, ledger chain/signing, exit code, or
  `--json` schema changes; machine-readable output is never routed through the styler; `3pwr verify` and
  the engine's own gates stay green.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** build a full-screen / alternate-screen TUI or a `curses` application — no mouse input, no
  live multi-pane dashboards, no cursor-addressed layouts beyond the existing in-place stage line extended
  to a compact header. The CLI stays a streaming, scrollback-friendly command tool.
- Does **not** add any third-party rendering dependency (`rich`, `curses`, `colorama`, `blessed`, …) and
  makes **no** network call — ANSI SGR sequences only, preserving INITX-NFR-004 and 3PWR-NFR-004/010.
- Does **not** change any `--json` schema, exit code, verdict bytes, gate, threshold, ledger chain/signing
  format, or the two mandatory human gates (3PWR-FR-032, INITX-FR-014); this is a human-output layer.
- Does **not** restyle the `/3pwr.*` markdown command prompts (agent-facing prompt content) or any agent
  transcript — only the `3pwr` CLI's own output to the user.
- Does **not** change *what* a command reports — the same facts, IDs, and numbers — only *how* they are
  presented (structure, grouping, color).
- Does **not** add localization/i18n, Unicode theming, or arbitrary user-supplied templates beyond the
  documented `ui.yaml` keys.
- Does **not** resolve cross-platform terminal validation (3PWR-NFR-003, macOS-only today); it must degrade
  safely on a non-UTF-8 or width-unknown stream, but a full Windows-console pass remains a separate concern.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every command reads well (Priority: P1)

A user running any `3pwr` command wants the human output to be scannable — a short header naming what ran,
then results in labeled blocks or aligned rows with consistent color and status glyphs — instead of a long
run-on line they have to parse by eye.

**Acceptance Scenarios**:

1. **Given** a command that reports several fields (e.g. `classify`, `advance`, `oracle verify`,
   `observe`), **When** it prints human output on a TTY, **Then** the result appears as a titled block with
   labeled key/value rows or an aligned table — not a single unlabeled run-on line.
2. **Given** any two commands that both report a pass/fail/warn/skip status, **When** their output is
   compared, **Then** the same status renders with the same glyph and the same color in both.
3. **Given** the same command run with `--json`, **When** the payload is captured, **Then** it is
   byte-identical to before this change and contains no ANSI escape sequences.

### User Story 2 - You always know which stage you're in (Priority: P1)

A user running `3pwr run --mode auto` wants a persistent header that shows the eight lifecycle stages,
marks which one is complete / current / upcoming, and makes clear that work is actively running in the
current stage — so a glance answers "where am I and is it moving?" without reading the scroll.

**Acceptance Scenarios**:

1. **Given** an auto run on a TTY, **When** the run advances from one stage to the next, **Then** the
   header updates so completed stages show the done mark, the current stage shows the current mark, and the
   rest show the upcoming mark.
2. **Given** a stage whose agent is actively working, **When** the user looks at the header, **Then** it
   names the running step and shows a running indicator — visibly distinct from a paused or failed state.
3. **Given** the run reaches a failure at some stage, **When** the header renders, **Then** it shows the
   run as failed at that stage (consistent with the AUTOX failure taxonomy), not as still running.

### User Story 3 - Human gates are obvious (Priority: P1)

A user in auto mode wants the two human gates (spec approval, evidence sign-off) to stand out when the run
pauses, with the exact command to resume — so the pause never reads like a hang.

**Acceptance Scenarios**:

1. **Given** an auto run that pauses at the spec-approval gate, **When** the pause renders, **Then** the
   header prominently marks the gate as awaiting the user and prints the exact `3pwr run --resume …`
   command with the spec id filled in.
2. **Given** an auto run that pauses at the sign-off gate, **When** the pause renders, **Then** the same
   prominent, actionable treatment applies, distinct from an in-progress stage and from a failure.

### User Story 4 - Machines and CI are unaffected (Priority: P1)

A user wrapping `3pwr` in CI or a pipe wants human presentation changes to never touch machine output:
`--json` stays byte-identical, exit codes are unchanged, and piped / `NO_COLOR` output carries no color or
control codes.

**Acceptance Scenarios**:

1. **Given** any command with `--json`, **When** run with color forced on and with color off, **Then** the
   two payloads are byte-identical and neither contains an ANSI escape.
2. **Given** output redirected to a file or a pipe (non-TTY), **When** any command or an auto run writes to
   it, **Then** the file contains no `\r` in-place redraws and no `\033[` escape sequences, and the
   structure is still readable as plain text.
3. **Given** `NO_COLOR` is set, **When** any command runs on a TTY, **Then** no color is emitted and the
   output is still structured and readable.

### User Story 5 - Tune the density and defaults (Priority: P2)

A user wants to control how much the CLI prints and how it themes color — a quieter mode for routine runs,
a verbose mode for diagnosis, and a config file for their standing preferences — without changing what
machines see.

**Acceptance Scenarios**:

1. **Given** the same command, **When** run with `--quiet`, with defaults, and with `--verbose`, **Then**
   the human detail increases across the three levels while the `--json` payload and the exit code are
   identical for all three.
2. **Given** a `.3powers/config/ui.yaml` that sets color mode and default verbosity, **When** a command
   runs, **Then** the human output reflects those preferences — unless an explicit flag or the environment
   overrides them.
3. **Given** no `ui.yaml` present (or a freshly initialized repo), **When** commands run, **Then** the
   output matches the shipped defaults, i.e. today's behavior, so upgrading changes nothing until the user
   opts in.

### Edge Cases

- The terminal width is very small, or width is undetectable → aligned tables/columns degrade gracefully
  (wrap or truncate with an ellipsis/indicator) and a sensible default width is assumed; rendering never
  raises.
- `ui.yaml` is malformed or has an unknown key → the CLI falls back to shipped defaults and warns once,
  never crashing (mirroring `_load_yaml`'s tolerance of a missing/empty file).
- `--json` is combined with `--verbose`/`--quiet` → `--json` wins: the machine payload is emitted with no
  color and is unchanged by the verbosity flag.
- Output is piped mid-run → the stage header never emits `\r`/clear-line spam; it degrades to the plain
  streamed event log (as the current `Tracker` already does off a TTY).
- The output stream cannot encode the Unicode glyphs (non-UTF-8) → an ASCII marker fallback is used so
  status is still conveyed (cross-platform validation remains a residual per 3PWR-NFR-003).
- A command has only a single scalar result (e.g. a key id) → it still prints a self-identifying header but
  is not forced into an over-heavy block; presentation stays proportionate to the content.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where a value is derived or parsed (3PWR-FR-024). CLI flags, env vars, and
  file locations appear where they ARE the contract under specification (`--json`, `NO_COLOR`, `--quiet`,
  `ui.yaml`), not as implementation detail (3PWR-FR-007) — the same latitude AUTOX took for exit codes and
  transcript paths. Named modules/functions are context in the non-normative sections only.
-->

### Functional Requirements

#### Shared structured-output toolkit

- **CLIUX-FR-001**: The system shall provide a reusable set of human-output primitives — at minimum a
  section header, a key/value block, an aligned column/table, a status row, and a horizontal rule/divider —
  through which commands render, so structured output is produced from one shared vocabulary rather than
  hand-built per command.
  - *Acceptance*: the primitives exist as a documented, tested rendering API; the restyled commands render
    their human output through them; no restyled command computes its own column alignment inline.
- **CLIUX-FR-002**: When color is disabled (a non-TTY stream, `NO_COLOR`, `--json`, or `--yes`), the toolkit
  shall degrade to plain, escape-free text that preserves the structure's alignment and labels.
  - *Acceptance*: with color off, rendered output contains no `\033[` sequence yet remains readable as
    aligned, labeled text.
  - *Property*: for identical inputs, the color-off rendering equals the color-on rendering with every ANSI
    SGR sequence removed — the styler adds only color, never structure.
- **CLIUX-FR-003**: The toolkit shall introduce no third-party rendering dependency and make no network
  call, building only on ANSI SGR sequences the terminal already understands.
  - *Acceptance*: the engine's declared runtime dependencies are unchanged (`cryptography`, `PyYAML`);
    importing the presentation layer pulls in no additional distribution; no code path opens a socket.
- **CLIUX-FR-004**: Human output shall not present a multi-field result as a single unstructured run-on
  line: results with more than one field shall render as labeled blocks or aligned rows, and long lists
  shall wrap or align rather than overflow one line.
  - *Acceptance*: a review of the restyled commands finds no multi-field human result emitted as one
    unlabeled line; a representative wide result wraps/aligns to the available width.

#### Consistent color & status vocabulary across all commands

- **CLIUX-FR-005**: Every `3pwr` subcommand's human output shall use the shared semantic vocabulary and
  status glyphs, so a given status (`pass`/`fail`/`warn`/`skip`/`info`) renders with the same glyph and
  color in every command.
  - *Acceptance*: for the same status, the glyph+color emitted by `gate`, `verify`, `advance`, `run`,
    `deps-check`, `oracle`, `observe`, `status`, and the remaining subcommands are identical.
- **CLIUX-FR-006**: Each command shall open its human output with a short header naming the operation and
  its subject (e.g. spec id, tier, path, or target) where one applies, so captured or scrolled output is
  self-identifying.
  - *Acceptance*: each restyled command prints a header line/block naming the operation; where a subject
    exists it appears in the header.
- **CLIUX-FR-007**: The `--json` payload of every command shall be byte-identical before and after this
  change, and machine-readable output shall never be routed through the styler.
  - *Acceptance*: captured `--json` payloads for representative commands are unchanged from the pre-change
    baseline; a test asserts no ANSI escape appears in any `--json` payload even with
    `THREEPOWERS_FORCE_COLOR=1` set.
  - *Property*: presence or absence of color changes zero bytes of any machine-readable payload.

#### Auto-mode stage header ("you are here")

- **CLIUX-FR-008**: During `3pwr run`, the system shall display a persistent stage header covering the eight
  lifecycle stages (Discovery … Observe), marking each as completed, current, or upcoming, and shall update
  it as the run advances.
  - *Acceptance*: on a TTY, the header shows a completed/current/upcoming mark for each of the eight stages
    and re-renders on each stage transition.
  - *Property*: the header's per-stage marks are a deterministic function of the reached stage — the stages
    before the reached one are completed, the reached one is current, the rest are upcoming.
- **CLIUX-FR-009**: The stage header shall indicate that work is actively running in the current stage — the
  active step plus a running indicator — visibly distinct from a paused (awaiting-human-gate) state and from
  a failed state.
  - *Acceptance*: while a stage's agent runs, the header shows the running step; at a human gate it shows a
    paused treatment; on failure it shows failed at the reached stage.
- **CLIUX-FR-010**: In auto mode, when the run pauses at one of the two human gates (spec approval,
  sign-off), the header shall make the gate prominent and shall name the exact resume command with the spec
  id filled in.
  - *Acceptance*: at each human-gate pause, the rendered header marks the gate as awaiting the user and
    prints `3pwr run --resume --spec-id <ID> --approver <you>` (or the current resume invocation) verbatim.
- **CLIUX-FR-011**: Off a TTY or under `--json`, the stage view shall degrade to the existing plain streamed
  event log with no `\r` in-place redraws and no ANSI/control codes, and the `--json` run's per-stage
  results shall remain byte-identical.
  - *Acceptance*: a piped or `--json` run's output contains no `\r`/`\033`; the `--json` per-stage results
    match the pre-change baseline (preserve RUNLIVE-FR-006).
- **CLIUX-FR-012**: `3pwr run --status` and `3pwr status` shall render the same stage header and vocabulary
  as a live run — a static snapshot derived from the ledger — so paused / failed / in-progress states read
  identically whether shown live or recalled.
  - *Acceptance*: `--status` renders the multi-stage header consistent with the live view, and shows
    paused/failed/in-progress with the same semantics AUTOX-FR-007 defines.

#### Verbosity & configuration

- **CLIUX-FR-013**: The CLI shall accept a `--quiet` and a `--verbose` flag controlling human-output density
  — `--quiet` reduces to the result and any failures, the default gives a structured summary, and
  `--verbose` adds per-step detail (e.g. durations, attempt counts, artifact/transcript paths) — without
  affecting `--json` output or exit codes.
  - *Acceptance*: the three levels produce monotonically increasing human detail; the `--json` payload and
    exit code are identical across all three for the same command.
- **CLIUX-FR-014**: The system shall read optional UI preferences from `.3powers/config/ui.yaml` — color
  mode (`auto`/`always`/`never`), default verbosity, and header/layout style — applied to human output
  only, with a deterministic precedence: an explicit flag overrides the environment
  (`NO_COLOR`/`THREEPOWERS_FORCE_COLOR`), which overrides `ui.yaml`, which overrides the shipped default.
  - *Acceptance*: a `ui.yaml` setting changes human rendering deterministically; `NO_COLOR` and `--json`
    still force color off; a conflicting explicit flag wins over the file.
  - *Property*: for any combination of flag, env, and file, the resolved color/verbosity is the highest-
    precedence source present — flag > env > `ui.yaml` > default — and is a pure function of those inputs.
- **CLIUX-FR-015**: The shipped `ui.yaml` seeded by `3pwr init` shall document every key and default to
  values that reproduce today's behavior, so an upgrade changes nothing about the output until the user opts
  in; a missing or malformed file shall fall back to those same defaults.
  - *Acceptance*: with the shipped default `ui.yaml` (or none), human output matches the pre-change default;
    `3pwr init` seeds the documented file; a malformed file warns once and uses defaults.

### Non-Functional Requirements

- **CLIUX-NFR-001**: All rendering and preference resolution shall be deterministic and fully offline —
  identical input, environment, and config yield identical bytes; no network or model call anywhere in this
  feature (ref 3PWR-NFR-001).
  - *Acceptance*: rendering tests run with networking disabled; identical state yields identical output.
- **CLIUX-NFR-002**: This shall be a human-output-only layer: it shall never alter machine-readable output,
  exit codes, verdict bytes, or the ledger (preserve INITX-FR-014, 3PWR-FR-032/NFR-001).
  - *Acceptance*: existing `--json`, exit-code, and verdict-bytes tests are untouched and green; a test
    proves no `--json` payload changes with color forced on.
- **CLIUX-NFR-003**: No third-party runtime dependency and no network access shall be introduced (ANSI SGR
  only); the engine remains offline-reconstructable (ref 3PWR-NFR-004/010, INITX-NFR-004).
  - *Acceptance*: dependency manifest unchanged; an offline install renders full color output.
- **CLIUX-NFR-004**: Output shall be accessible: color is never the sole carrier of meaning — a glyph or
  word always accompanies it — `NO_COLOR` yields fully readable structure, and an ASCII marker fallback is
  used when the stream cannot encode the Unicode glyphs.
  - *Acceptance*: with color and Unicode both unavailable, each status is still distinguishable by an ASCII
    marker or word.
- **CLIUX-NFR-005**: The engine shall stay green under its own gates across this change, and
  `docs/STATUS.md` shall remain the single home of implementation status (ref 3PWR-NFR-006, DOCX-NFR-003).
  - *Acceptance*: self-application gate run + ruff/mypy/pytest green; STATUS updated once at delivery.

## Success Criteria *(mandatory)*

- **CLIUX-SC-001**: Every `3pwr` command renders its human output as structured, colored, self-identifying
  blocks or aligned rows — no multi-field result remains a run-on one-line dump.
- **CLIUX-SC-002**: A user running `3pwr run --mode auto` always sees a header naming the current stage and
  showing that work is running, updating across the eight stages, with the two human gates made prominent
  and actionable.
- **CLIUX-SC-003**: `--json` payloads are byte-identical and exit codes behavior-identical before and after;
  a test proves no ANSI escape appears in any `--json` payload, even with `THREEPOWERS_FORCE_COLOR=1`.
- **CLIUX-SC-004**: `NO_COLOR`, non-TTY pipes, and `--json` all yield clean, escape-free, still-structured
  text, and color is never the only signal (a glyph/word/ASCII marker always conveys status too).
- **CLIUX-SC-005**: No third-party rendering dependency is added and no network call is introduced; the
  engine stays offline-reconstructable and green under its own gates.
- **CLIUX-SC-006**: `--quiet`/`--verbose` and `.3powers/config/ui.yaml` deterministically control human
  density and color/layout with the documented precedence (flag > env > file > default), and the shipped
  defaults reproduce prior behavior.
- **CLIUX-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test
  naming the CLIUX-FR id, or a recorded output/documentation review where the rendered text is what is
  asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id CLIUX --stage spec --spec specs/015-cli-experience/spec.md`; appended to the signed ledger)_ | | |
