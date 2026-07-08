# Feature Specification: Steering an Autonomous Run — File-Based Intent, Human-Gate Notifications with Approve / Reject / Revise Guidance, and a Persistent Live Run Frame

**Spec ID**: STEER
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     STEER is the human-in-the-loop counterpart to the native executive: EXEC (009) and RUNLIVE (011)
     built `3pwr run` and its live stream, AUTOX (014) made auto-mode land at the two human gates with a
     stable contract, and CLIUX (015) gave the CLI a shared structured-output vocabulary and a single
     in-place "you are here" stage line. STEER closes the three seams that remain in the *operator's* loop
     with a run: (1) intent can only be typed as one CLI argument — you cannot point a run at a file you
     already wrote, nor combine that file with a short inline instruction; (2) when a run pauses at a human
     gate the only signal is a printed resume line plus a best-effort `--notify` command hook — there are no
     first-class channels (Slack/Teams/email/desktop) and no clear "here are your three choices" guidance,
     and there is no way to send a revision back other than editing files by hand; (3) the live view is a
     single line that agent stdout scrolls off-screen, so you lose track of which stage you are in and
     whether it is moving. STEER advances CLIUX-FR-008/009 from one in-place line to a *persistent live
     frame* while staying inside CLIUX's no-dependency / no-alternate-screen boundary (so no CLIUX or epic
     amendment is required). Cross-refs: 3PWR-FR-006/037 (the two human gates), 3PWR §6 (the lifecycle),
     CLIUX-FR-008/009, CLIUX-NFR-002/003, AUTOX-FR-007, RUNLIVE-FR-006, INITX-FR-014,
     3PWR-NFR-004/005/010. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this is orchestration plumbing (intent resolution, a revise re-dispatch of an already-defined
     stage), a human-output presentation layer (the live bar), and ONE deliberately opt-in, best-effort
     outbound notification path. It touches none of the trust-spine modules (canonical/keys/ledger/verify)
     and weakens no gate (3PWR-FR-032). High-risk was considered — because notifications introduce network
     egress and revise re-dispatches an agent — and rejected: notifications are disabled by default and are
     guarded so a channel error/timeout/absence can never block, delay, fail, or alter the run, its verdict,
     its exit code, or the ledger; revise re-runs an already-specified stage through the existing executive
     and records itself via the existing append path (no ledger-format change); and `3pwr verify` plus
     offline reconstruction stay intact. That is the same latitude CLIUX (014/015) used to land on Standard.
     Cosmetic was rejected because this alters the run's control flow (a new revise loop) and adds a network
     capability that must hold trust-isolation and byte-identical machine-output invariants under test. -->

**Status**: Draft

**Input**: User requests (three, verbatim intent): (1) "We need a way of not only describing our intent in
the command line with text only but also to just mention a file where we have described our intent (can be
any text file — preferred markdown) and this will be taken as the intent. Additionally I can of course write
something to that file. For example `3pwr run --file my-intent.md \"take this and create a spec for it but
leave out point 5\"`." (2) "Whenever `3pwr` stops and is awaiting the user we need a way of notifying the
user — either with official channels (Slack, Teams, or mail, or local if possible) — and we need to guide him
on what he needs to do: link to the file to check, and commit, reject, or revise with a message." (3) "We
already have our own CLI UX but it is not good enough. When executing, the command line just adds new text
(e.g. the coding agent's output) and my run-stage information scrolls to the top — I don't know which stage
we are currently in, the progress, or which are done. I need a fixed 3Powers CLI border that gives me all
that in real time, and inside that frame all the stdout output is shown."

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):**
  - *Intent* is a single positional argument to `3pwr run` (`cli.py`), recorded in the ledger's `start`
    entry and injected into each stage prompt by `prompts.assemble(..., intent=...)`; `workkind.classify`
    reads it to infer work kind + suggested tier. There is no file input and no compose step.
  - *The two human gates* live in `orchestrate.py` (`MANDATORY_GATES = {review-spec: 3PWR-FR-006,
    signoff: 3PWR-FR-037}`, `LIFECYCLE_STEPS`, `drive()`). In auto mode `drive()` auto-approves the
    intermediate gates and stops only at these two. At a stop, `cli.py` prints a resume line, and interactive
    mode offers a `[y/N]` prompt; a "no" marks the gate complete and stops (there is no revise path). `--resume`
    records a sign-off (`_run_signoff`) and continues from the next step.
  - *Notification* today is a best-effort command hook: `--notify "<cmd>"` runs `<cmd> "<message>"` at gate
    pause, on each failure class, and at completion (`_notify` in `cli.py`). There is no channel config, no
    Slack/Teams/email/desktop sender. Config files live under `.3powers/config/*.yaml` and are read through
    `config.py`'s `Settings` + tolerant `_load_yaml` (missing = defaults, malformed = warn); JSON schemas
    live under `.3powers/schemas/`. This is the established pattern for adding `notifications.yaml`.
  - *The live view* is `orchestrate.Tracker` with `render_tracker` (a one-line `✓/▶/·` stage strip),
    `format_event`, and `tracker_frame`. On a TTY it redraws a single line in place (`\r` + clear-line);
    off a TTY it prints the plain streamed event log. Agent stdout is teed straight to the terminal by
    `runner.dispatch_agent(stream=..., tee=...)` via pump threads, which is exactly what scrolls the single
    tracker line off-screen. The eight stages are `lifecycle.STAGES` (Discovery … Observe); the twelve
    lifecycle steps are in `orchestrate.py`. `style.py`'s `Styler` provides the zero-dependency ANSI
    vocabulary and status glyphs, honoring `--json`, `NO_COLOR`, `THREEPOWERS_FORCE_COLOR`, and TTY
    detection; `.3powers/config/ui.yaml` holds color/verbosity/layout preferences.
- **The dependency & network stance, inherited:** the engine's only runtime dependencies are `cryptography`
  and `PyYAML`; the presentation layer is deliberately third-party-free and network-free so the tool stays
  offline-reconstructable (3PWR-NFR-004/010) and color can never corrupt a `--json` payload (INITX-FR-014,
  CLIUX-NFR-002/003). STEER keeps that stance for the frame (ANSI only) and confines *all* new network
  egress to the notification channels, which are opt-in, disabled by default, and isolated from the trust
  path so the offline guarantees for the run itself are unchanged.
- **Guardrail:** the two mandatory human gates keep the same meaning and the same *what* they require; STEER
  changes only how a run is fed (file intent), how a pause reaches the user (notifications), what the user can
  do at a pause (approve / reject / revise), and how the run's progress is shown (the live bar). No gate,
  threshold, verdict byte, ledger chain/signing format, exit-code contract, or `--json` schema changes.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** build a full-screen / alternate-screen TUI or a `curses`-style application — no mouse input,
  no multi-pane cursor-addressed layout. The frame is a bottom-anchored status bar over the terminal's
  ordinary output flow, rendered with ANSI sequences only; the CLI stays a streaming, scrollback-friendly
  tool (preserves the CLIUX non-goal and CLIUX-NFR-003).
- Does **not** add any third-party rendering or notification-transport dependency (`rich`, `curses`,
  `blessed`, a Slack SDK, an SMTP library beyond the standard library, …); the frame uses ANSI only, and
  channels use the standard library / already-present `cryptography`+`PyYAML` plus a user-supplied command
  hook where a native sender is not built.
- Notifications are an **opt-in convenience signal, not a trust or enforcement channel**: they are never
  required for any gate, never gate an advance, and carry no authority — approval still happens only through
  the CLI + signed ledger. There is **no inbound control channel** (you cannot approve/reject/revise by
  replying to a Slack/Teams/email message).
- Does **not** change *what* the two mandatory human gates require, the deterministic gate suite, any
  threshold, verdict bytes, the ledger chain/signing format, exit-code contract, or any `--json` schema
  (3PWR-FR-032, INITX-FR-014, AUTOX contract).
- Does **not** guarantee cross-platform terminal behavior or non-macOS desktop notifications; the desktop
  channel targets macOS first and the frame must degrade safely on a non-UTF-8 / width-unknown / dumb / non-TTY
  stream, but a full Windows/Linux pass remains a separate concern (residual, 3PWR-NFR-003).
- Does **not** add localization/i18n or user-supplied message templates beyond the documented
  `notifications.yaml` keys and the existing `ui.yaml`.
- Does **not** persist secrets in the repo or ledger — webhook URLs and mail credentials are referenced from
  the environment (mirrors 3PWR-NFR-005); STEER neither stores nor logs them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Point a run at a file, and tweak it inline (Priority: P1)

An operator has already written the intent in a markdown file (a paragraph, a checklist, pasted notes). They
want to hand that file to `3pwr run` as the intent instead of retyping it — and optionally add a short inline
instruction that modifies it — so authoring starts from the real, considered intent rather than a one-liner.

**Acceptance Scenarios**:

1. **Given** a readable `my-intent.md`, **When** the operator runs `3pwr run --file my-intent.md`, **Then**
   the file's contents become the run's intent and are recorded verbatim in the ledger `start` entry, exactly
   as if that text had been typed.
2. **Given** the same file, **When** the operator runs `3pwr run --file my-intent.md "take this and create a
   spec for it but leave out point 5"`, **Then** the resolved intent combines the file (as the base) with the
   inline text (as an appended instruction) deterministically, and the combined text is what authoring and the
   ledger see.
3. **Given** `--file` pointing at a path that is missing, a directory, empty, or not decodable as text,
   **When** the run is invoked, **Then** it fails fast with an actionable error naming the path and the setup
   exit code, and no `start` entry is written to the ledger.

### User Story 2 - A pause reaches me, with clear next steps (Priority: P1)

An operator kicks off an auto run and steps away. When it pauses at a human gate — or fails, or completes —
they want to be notified through a channel they actually watch (Slack, Teams, email, or a local desktop
notification), with a message that says which spec and gate, links to the artifact to review, and spells out
exactly how to approve, reject, or revise — so the pause never reads like a silent hang.

**Acceptance Scenarios**:

1. **Given** a `notifications.yaml` enabling a channel, **When** an auto run pauses at the spec-approval gate,
   **Then** that channel receives a message naming the spec id, stage, and gate, a path/link to the artifact to
   review, and the exact approve / reject / revise commands with the spec id filled in.
2. **Given** an enabled channel, **When** a run fails or completes, **Then** the channel receives a
   correspondingly actionable message (the failure class and how to resume, or a completion notice).
3. **Given** a channel that is misconfigured, unreachable, or times out, **When** any notifiable event fires,
   **Then** the run proceeds and terminates exactly as it would with no channel configured — same output, same
   exit code, same ledger — and the delivery failure is at most a one-line local warning.

### User Story 3 - Approve, reject, or revise at the gate (Priority: P1)

At a human gate the operator wants three clear choices, not two: approve and continue, reject and stop, or
**revise with a message** — hand the agent feedback ("leave out point 5", "tighten the non-goals") and have it
redo just that stage and come back to the same gate — without hand-editing files and guessing how to resume.

**Acceptance Scenarios**:

1. **Given** a run paused at a gate, **When** the operator reads the on-screen pause (and any notification),
   **Then** all three actions are named with copy-pasteable commands and the path to the artifact under review.
2. **Given** a run paused at the spec-approval gate, **When** the operator runs the revise command with a
   message (e.g. `3pwr run --resume --spec-id STEER --revise "leave out point 5"`), **Then** the paused stage
   is re-dispatched with the original intent, the current artifact, and that feedback, a revised artifact is
   produced, and the run returns to the *same* gate for review.
3. **Given** a revise action, **When** it completes, **Then** the feedback and its outcome are recorded in the
   ledger, so the revision is auditable and the run remains reproducible; **and** a revise invoked with empty
   feedback is rejected with an actionable error and the gate stays paused.

### User Story 4 - I always see where the run is (Priority: P1)

An operator watching an auto run wants a fixed frame that stays on screen while the agent's stdout streams —
showing the eight stages with which are done, which is current, and that work is actively running — so a glance
answers "which stage am I in, what's finished, is it moving?" even as pages of agent output scroll by.

**Acceptance Scenarios**:

1. **Given** an auto run on a TTY, **When** the agent for the current stage emits many lines of output,
   **Then** the live bar stays visible at the bottom (it is not scrolled away), while the agent output
   prints above it into the terminal's ordinary, fully scrollable history.
2. **Given** the run advances from one stage to the next, **When** the bar updates, **Then** completed
   stages show the done mark, the current stage shows a running indicator with a heartbeat spinner and
   elapsed time and names the active step, and the remaining stages show the upcoming mark — a running
   state visibly distinct from a paused gate and from a failure.
3. **Given** the run pauses at a human gate or fails, **When** the bar renders, **Then** it shows the
   paused-at-gate or failed-at-stage state prominently (consistent with the AUTOX failure taxonomy), not as
   still running, and — for a gate — the resume/reject/revise guidance is visible.

### User Story 5 - Machines, pipes, and the trust spine are unaffected (Priority: P1)

An operator wrapping `3pwr` in CI or a pipe, and anyone relying on the offline trust guarantees, needs these
new conveniences to never touch machine output or the trust path: `--json` stays byte-identical, exit codes are
unchanged, piped/`NO_COLOR` output carries no frame control codes, and `3pwr verify` plus offline
reconstruction are unaffected whether or not a channel is configured.

**Acceptance Scenarios**:

1. **Given** any run with `--json` or output redirected to a pipe/file, **When** it runs, **Then** the output
   contains no `\r` in-place redraws and no `\033[` escape sequences, the live bar is not emitted, and the
   `--json` per-stage results and exit code are byte-/behavior-identical to before this change.
2. **Given** no `notifications.yaml` and no `--notify`, **When** a run executes end to end, **Then** no network
   call is made at any point, and `3pwr verify` and an offline reconstruction succeed identically to today.
3. **Given** a configured channel that fails, **When** the run finishes, **Then** the verdict bytes, exit code,
   and ledger are identical to a run with notifications disabled.

### Edge Cases

- `--file` names a directory, a missing path, an empty file, or a non-decodable (binary) file → fail fast with
  an actionable error and the setup exit code; no `start` entry is written (nothing partially begins).
- Both `--file` and inline intent are given → combined deterministically, file first as the base and the inline
  text appended as an instruction; only the resolved text is recorded, so the run reproduces from the ledger.
- `notifications.yaml` is malformed or has an unknown key → warn once and fall back to disabled/default
  channels; the run proceeds (mirrors `_load_yaml` tolerance and the `ui.yaml` precedent).
- A channel references a missing environment secret (webhook URL, SMTP credential) → that channel is treated as
  not deliverable: a one-line warning, no crash, no leak of the variable name's value, run unaffected.
- Revise is invoked with empty or whitespace-only feedback → rejected with an actionable error; the gate stays
  paused and the artifact is untouched. Revise invoked when not paused at a gate → actionable error naming the
  current state.
- Revise is used repeatedly at the same gate → each revision re-runs the stage and is recorded; the same gate
  is re-presented after each, until the operator approves or rejects.
- The terminal is not a TTY, is a dumb terminal, is `NO_COLOR`, has unknown/zero width, or is below the
  minimum size → the live bar degrades to the existing plain streamed event log with no `\r`/control-code spam.
- The terminal is resized during a run → the live bar re-lays out without corrupting itself or the
  streamed output.
- The run is interrupted (Ctrl-C), fails, or exits while the bar is active → the terminal is restored to a
  clean state (cursor visible, the bar's last state left as ordinary lines); the terminal is never left
  corrupted.
- The dispatched agent's own stdout contains ANSI or cursor-movement sequences → it prints above the bar
  with its cursor-moving/screen-clearing controls stripped (color preserved) and must not corrupt or dislodge
  the bar.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an *Acceptance*
  line; a *Property* where a value is parsed/combined/derived (3PWR-FR-024). CLI flags, env vars, and file
  locations appear where they ARE the contract under specification (`--file`, `--revise`,
  `notifications.yaml`), not as implementation detail (3PWR-FR-007) — the latitude CLIUX/AUTOX took for
  `--json`, exit codes, and `ui.yaml`. Named modules/functions are context in the non-normative sections only.
-->

### Functional Requirements

#### File-based intent input

- **STEER-FR-001**: `3pwr run` shall accept an intent source file via `--file <path>` (a UTF-8 text file,
  markdown preferred); when supplied without inline intent text, the file's contents shall be used as the run's
  intent, equivalent to that text having been passed as the intent argument.
  - *Acceptance*: `3pwr run --file my-intent.md` starts a run whose intent equals the file's contents; every
    downstream consumer (authoring prompt, work-kind classification, ledger `start` entry) sees that text.
- **STEER-FR-002**: When both `--file <path>` and an inline intent argument are provided, the system shall
  combine them into one resolved intent — the file content as the base and the inline text as an appended
  instruction — and pass only the resolved intent onward.
  - *Acceptance*: `3pwr run --file my-intent.md "leave out point 5"` yields a resolved intent containing the
    file text followed by the inline instruction; authoring and the ledger receive the combined text.
  - *Property*: the resolved intent is a pure, deterministic function of (file contents, inline text) with a
    fixed order (file first, inline appended); identical inputs always yield identical resolved intent.
- **STEER-FR-003**: When `--file` refers to a path that is missing, a directory, empty, or not decodable as
  text, the system shall fail fast with an actionable error that names the path and the reason, exit with the
  setup exit code, and write no ledger `start` entry.
  - *Acceptance*: each bad-file case prints a clear error and returns the documented setup exit code; the
    ledger gains no entry for the aborted invocation.
- **STEER-FR-004**: The system shall record the resolved intent verbatim in the run's ledger `start` entry,
  regardless of whether it came from `--file`, inline text, or both, so the run is reproducible from the ledger
  alone.
  - *Acceptance*: after a file-sourced run, the ledger `start` entry's intent equals the resolved text used for
    authoring.

#### Human-gate actions: approve, reject, revise-with-message

- **STEER-FR-005**: At each human-gate pause, the system shall present three actions — approve (resume and
  continue), reject (stop), and revise-with-message — each with a copy-pasteable command carrying the spec id,
  and a path/link to the artifact under review.
  - *Acceptance*: the on-screen pause names all three actions with runnable commands and the artifact path;
    the approve and reject paths preserve their current behavior (resume records a sign-off and continues;
    reject stops); an interactive pause lets the operator choose among the same three actions directly,
    taking the revision feedback and the rejection reason as free text.
- **STEER-FR-006**: When the operator revises at a paused gate with a feedback message, the system shall
  re-dispatch the paused stage to the executive with the original intent, the current stage artifact, and the
  feedback; produce a revised artifact; and return the run to the *same* gate for review.
  - *Acceptance*: `3pwr run --resume --spec-id <ID> --revise "<message>"` re-runs the paused stage using the
    feedback, updates the artifact in place, and pauses again at the same gate rather than advancing past it.
- **STEER-FR-007**: Revise feedback shall be acceptable inline (`--revise "<message>"`) or from a file
  (`--revise-file <path>`), and empty/whitespace-only feedback, or a revise invoked when not paused at a gate,
  shall be rejected with an actionable error while leaving the artifact and gate state unchanged.
  - *Acceptance*: a file-sourced revise re-runs the stage with the file's text; empty feedback and a revise
    outside a gate each produce an actionable error and no artifact change.
  - *Property*: the revise feedback is resolved from inline-or-file by the same deterministic rule as the
    intent source (STEER-FR-001/002), so its origin does not change the resolved feedback text.
- **STEER-FR-008**: The system shall record each revision — the feedback used and its outcome — in the ledger
  via the existing append path, without changing the ledger entry format, so revisions are auditable and the
  run stays verifiable and reproducible.
  - *Acceptance*: after a revise, the ledger contains an entry capturing the feedback and outcome; `3pwr
    verify` still succeeds; no new ledger schema/field breaks existing verification.

#### Human-gate notifications & actionable guidance

- **STEER-FR-009**: When an auto run pauses at a human gate, fails, or completes, the system shall dispatch a
  notification to every enabled channel with an actionable message naming the spec id, stage, and gate (or the
  failure class / completion), a path/link to the artifact to review, and the relevant next-step commands.
  - *Acceptance*: with a channel enabled, each of the three event kinds delivers a message containing those
    fields; a gate-pause message includes the approve/reject/revise commands with the spec id filled in.
- **STEER-FR-010**: The system shall read notification channels from `.3powers/config/notifications.yaml`
  through an extensible channel model with tolerant loading (a missing file disables notifications; an unknown
  key or malformed file warns once and falls back), and shall provide reference channels for Slack, Microsoft
  Teams, email, and local desktop.
  - *Acceptance*: enabling a reference channel in `notifications.yaml` routes events to it; a malformed file or
    unknown key warns once and does not crash; the four reference channel types are documented and selectable.
- **STEER-FR-011**: The system shall make event→channel routing configurable, defaulting to notify on gate
  pause, failure, and completion, and the existing `--notify "<cmd>"` command hook shall continue to work
  alongside configured channels.
  - *Acceptance*: routing configured per channel selects which of {gate, failure, completion} it receives; with
    no routing specified the default set applies; a run using both `--notify` and a configured channel fires
    both.

#### Persistent live run bar

- **STEER-FR-012**: During `3pwr run` on a TTY, the system shall display a persistent live status bar,
  anchored at the bottom of the terminal, covering the eight lifecycle stages (Discovery … Observe) —
  marking each completed / current / upcoming, naming the active step, and showing a running indicator —
  that remains visible while the event log and the dispatched agent's stdout print ABOVE it into the
  terminal's ordinary, fully scrollable output flow.
  - *Acceptance*: while a stage's agent emits many lines, the bar stays visible at the bottom (it is not
    scrolled away) and the agent output appears above it and remains in the terminal's scrollback; no
    terminal scroll region is set (which would discard scrolled-out history).
  - *Property*: the per-stage marks are a deterministic function of the reached stage — stages before it are
    completed, the reached one is current, the rest upcoming.
- **STEER-FR-013**: The bar shall update in real time on each stage transition, step change, gate pause, and
  failure, rendering the running, paused-at-gate, and failed-at-stage states as visibly distinct (consistent
  with the AUTOX failure taxonomy); while a stage runs it shall show a heartbeat (an animated spinner plus the
  stage's elapsed time) so a long-running dispatch is never mistaken for a hang; and it shall show the
  resume/reject/revise guidance while paused at a gate.
  - *Acceptance*: advancing a stage, pausing at a gate, and failing each change the bar to the corresponding
    distinct state; a running stage advances its spinner and elapsed time over time; the gate state shows the
    actionable guidance and carries no spinner.
- **STEER-FR-014**: The bar shall introduce no third-party dependency and make no network call, building only
  on ANSI control sequences the terminal already understands (cursor movement, line erase, SGR color); it
  shall not use the alternate screen buffer or a terminal scroll region.
  - *Acceptance*: the engine's declared runtime dependencies are unchanged (`cryptography`, `PyYAML`);
    rendering the bar opens no socket and pulls in no additional distribution.
- **STEER-FR-015**: Off a TTY, under `--json`, under `NO_COLOR`, or on a terminal that cannot support the
  live bar, the bar shall degrade to the existing plain streamed event log with no `\r` in-place redraws
  and no ANSI/control codes, and the `--json` per-stage results and exit code shall remain byte-/behavior-
  identical (preserve RUNLIVE-FR-006, INITX-FR-014).
  - *Acceptance*: a piped or `--json` run's output contains no `\r`/`\033`; its per-stage results match the
    pre-change baseline; the bar is never written to a non-TTY stream.
- **STEER-FR-016**: The bar shall adapt to terminal resize without corrupting itself or the streamed output,
  and shall restore the terminal to a clean state (cursor visible, the bar's last state left as ordinary
  lines) on normal exit, interruption (e.g. Ctrl-C), or failure; a dispatched agent's own cursor-moving or
  screen-clearing control sequences shall be stripped from the echoed output (color preserved) so they can
  never dislodge the bar or corrupt the terminal.
  - *Acceptance*: resizing mid-run does not corrupt output; after the run — including an interrupted or failed
    run — the cursor is restored and subsequent commands render normally; an agent line carrying a
    screen-clear escape prints above the bar with that escape removed.

### Non-Functional Requirements

- **STEER-NFR-001**: Notifications shall be best-effort and fully isolated from the trust path — disabled by
  default, and a channel error, timeout, or absence shall never block, materially delay, fail, or alter the
  run, its verdict bytes, its exit code, or the ledger; notification delivery is the only deliberate, opt-in
  outbound network egress this feature adds.
  - *Acceptance*: with a broken/unreachable channel, a run's stdout tail, exit code, verdict bytes, and ledger
    equal those of the same run with notifications disabled; with none configured, no network call occurs.
- **STEER-NFR-002**: Channel secrets (webhook URLs, SMTP credentials) shall be referenced from the environment
  and never required to be stored in the repository or written to the ledger, transcripts, or logs (mirrors
  3PWR-NFR-005).
  - *Acceptance*: `notifications.yaml` references environment variables for secrets; a committed config
    contains no plaintext secret; no secret value appears in ledger entries, transcripts, or warnings.
- **STEER-NFR-003**: The live bar shall be a human-output-only layer and, together with intent resolution and
  revise-prompt assembly, shall be deterministic — it shall never alter machine-readable output, exit codes,
  verdict bytes, or the ledger, and identical inputs shall yield identical rendered/resolved bytes (preserve
  CLIUX-NFR-002/003, INITX-FR-014, ref 3PWR-NFR-001). The heartbeat animation is a presentation-only
  decoration and carries no state.
  - *Acceptance*: existing `--json`, exit-code, and verdict-bytes tests stay green; a test proves no `--json`
    payload changes with color/frame forced on; rendering and intent/feedback resolution are reproducible.
- **STEER-NFR-004**: The system shall never leave the terminal in a corrupted state: the bar shall not depend
  on the alternate screen buffer or a terminal scroll region, shall always restore the cursor on teardown, and
  shall degrade rather than raise on an unsupported or width-unknown terminal.
  - *Acceptance*: after normal, interrupted, and failed runs, the terminal is usable and uncorrupted; a
    width-unknown/dumb terminal produces the plain streamed log without an exception.
- **STEER-NFR-005**: The engine shall stay green under its own gates across this change; `docs/STATUS.md` shall
  remain the single home of implementation status; every functional requirement shall be exercised by at least
  one test naming its `STEER-FR` id; and the engine shall remain offline-reconstructable except for the
  explicitly opt-in notification egress (ref 3PWR-NFR-004/006/010, DOCX-NFR-003).
  - *Acceptance*: self-application gate run + ruff/mypy/pytest green; STATUS updated once at delivery; an
    offline reconstruction with notifications unconfigured succeeds.

## Success Criteria *(mandatory)*

- **STEER-SC-001**: An operator can drive a run from a file — `3pwr run --file <md>` and `3pwr run --file <md>
  "<inline>"` — with the resolved intent (file base + optional inline modifier) recorded verbatim in the
  ledger, and a bad `--file` fails fast with the setup exit code and no `start` entry.
- **STEER-SC-002**: When a run pauses at a human gate, fails, or completes, every enabled channel (Slack /
  Teams / email / desktop) receives an actionable message with the spec id, gate/stage, artifact link, and the
  approve/reject/revise commands — and a misconfigured or unreachable channel never blocks or alters the run.
- **STEER-SC-003**: At a gate the operator can approve, reject, or revise-with-message; revise re-runs the
  paused stage with the feedback, updates the artifact, returns to the same gate, and is recorded in the
  ledger, with `3pwr verify` still succeeding.
- **STEER-SC-004**: On a TTY, `3pwr run` shows a persistent bottom-anchored live bar (eight stages with done /
  current / upcoming marks, active step, and a running heartbeat spinner with elapsed time) that stays visible
  while agent stdout prints above it into scrollback, so a glance answers "which stage, what's done, is it
  moving?".
- **STEER-SC-005**: No third-party dependency is added and no new mandatory network path is introduced;
  notifications are the only opt-in egress and are fully isolated; off-TTY / `--json` / `NO_COLOR` output stays
  escape-free and byte-/behavior-identical; `3pwr verify` and offline reconstruction are unaffected; and the
  engine stays green under its own gates.
- **STEER-SC-006**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test naming
  the `STEER-FR` id, or a recorded output/behavior review where the rendered text or delivered message is what
  is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id STEER --stage spec --spec specs/019-run-steering/spec.md`; appended to the signed ledger)_ | | |
