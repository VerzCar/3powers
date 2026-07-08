# Feature Specification: Terminal UX on Rich — the Renderer Rebuilt Behind the Existing Styler/LiveFrame APIs

**Spec ID**: TRIX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     TRIX rebuilds the engine's terminal renderer on the `rich` library behind the EXISTING public
     APIs — `style.Styler` (the structured-output toolkit, CLIUX) and `frame.LiveFrame` (the
     bottom-anchored live run bar, STEER) — so every call site keeps compiling and behaving
     identically while the hand-rolled ANSI string-math (SGR construction, cursor-up/erase-below
     redraw arithmetic) is deleted. The machine contracts are untouched: `--json` stays
     byte-identical and Rich-free, `NO_COLOR`/`--yes`/non-TTY degrade to plain text exactly as
     before, and exit codes are unchanged. CLIUX-FR-003 is amended (2026-07-06) to permit the
     dependency. Cross-refs: CLIUX-FR-002/003/007/011/014, CLIUX-NFR-001..004, STEER-FR-012..016,
     STEER-NFR-003/004. Presentation layer only; no trust-spine module (canonical/keys/ledger/
     verify) is changed and no verdict byte moves. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate
     threshold. Rationale: this swaps the *implementation* of the human-output layer while holding
     its public API and its machine contracts fixed under test. Cosmetic was rejected: the layer
     guards the `--json` byte-identity and degradation invariants, which must hold under test.
     High-risk was rejected: no trust-spine module is touched and no gate is weakened
     (3PWR-FR-032). -->

**Status**: Draft

**Input**: Plan 030, Track G: `style.py` + `frame.py` implement a custom ANSI renderer — hand-built
SGR sequences and `\033[A`/`\033[J` cursor math — that has grown to ~500 lines, races with agent
stdout on slow dispatches, degrades poorly on narrow terminals, and offers no structured layout
primitives for the gate-pipeline view that follows. Rebuild it on `rich` behind the existing APIs.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change any public API of `style.Styler`, the `style` module functions, or
  `frame.LiveFrame`/`frame.build`/`frame.supported` — every existing call site compiles and behaves
  identically without edits.
- Does **not** change any machine-readable output: `--json` payloads, exit codes, verdict bytes,
  and the ledger are byte-for-byte unaffected (CLIUX-NFR-002 preserved).
- Does **not** change the color/verbosity precedence: flag > env (`NO_COLOR` /
  `THREEPOWERS_FORCE_COLOR`) > `ui.yaml` > default stays exactly as CLIUX-FR-014 defines it.
- Does **not** introduce syntax highlighting, markup interpretation, or any reformatting of the
  dispatched agent's streamed output — content passes through unchanged.
- Does **not** add any dependency beyond `rich`, and makes no network call anywhere.
- Does **not** use the alternate screen buffer or a DECSTBM scroll region — the scrollback
  guarantees of the live bar (STEER-FR-012) are preserved.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The terminal experience is unchanged where it must be (Priority: P1)

A user piping `3pwr` output into a file, running under `NO_COLOR`, scripting with `--json`, or
working on a 40-column terminal sees exactly the output they saw before the rewrite: plain,
escape-free, byte-identical where machine-read.

**Acceptance Scenarios**:

1. **Given** a representative command run with `--json`, **When** its output is compared against a
   capture taken before the rewrite, **Then** the bytes are identical.
2. **Given** any command run with `NO_COLOR` set or with stdout piped, **When** the output is
   scanned, **Then** it contains no ANSI escape sequence.
3. **Given** a 40-column terminal, **When** a run renders, **Then** the output degrades to plain
   sequential text without corruption.

### User Story 2 - The live bar keeps its guarantees on a better engine (Priority: P2)

A user watching `3pwr run` on a capable TTY still sees the bottom-anchored stage bar with the full
agent conversation scrolling above it into ordinary history — now rendered by `rich` instead of
hand-rolled cursor arithmetic, with no freezes and no history loss.

**Acceptance Scenarios**:

1. **Given** a live run on a TTY, **When** the agent streams hundreds of lines, **Then** every line
   lands in scrollback above the bar and the bar stays painted at the bottom.
2. **Given** the run reaches a human gate or fails, **When** the bar finalizes, **Then** its last
   state remains on screen as ordinary lines and the cursor is restored.

### Edge Cases

- A dumb/width-unknown terminal → no live bar is built; the plain streamed log applies unchanged.
- A stream whose encoding cannot represent the Unicode glyphs → the ASCII glyph set applies
  unchanged (CLIUX-NFR-004).
- Agent output carrying cursor-moving or screen-clearing control sequences → sanitized exactly as
  before; SGR color survives.
- The frame is closed (or was never opened) → `emit` degrades to a plain write with no Rich
  involvement in the bytes produced.

## Requirements *(mandatory)*

### Functional Requirements

- **TRIX-FR-001**: The engine shall declare `rich>=13.7,<15` as a runtime dependency — MIT-licensed,
  pure-Python, with no transitive C extensions — as the single rendering dependency permitted by
  the amended CLIUX-FR-003.
  - *Acceptance*: the declared runtime dependencies are exactly `cryptography`, `PyYAML`, and
    `rich`; `uv sync` resolves cleanly offline from the lockfile.
- **TRIX-FR-002**: `style.Styler` shall generate every ANSI escape it emits through `rich` style
  primitives (no hand-rolled SGR construction), while preserving its public API — fields
  (`enabled`, `ascii_only`), painting methods, the status vocabulary, and the structured-output
  toolkit — so all existing call sites compile and behave identically without edits.
  - *Acceptance*: no call site in the orchestration, CLI, or gates modules changes; the color-off
    rendering still equals the color-on rendering with ANSI stripped (CLIUX-FR-002 property).
- **TRIX-FR-003**: `frame.LiveFrame` shall render the live run bar through a `rich` live display on
  a `rich` console, while preserving its public API — `supported`, `build`, `open`, `close`,
  `emit`, `note`, `heartbeat`, `retitle`, `resize`, and the self-closing/idempotent-teardown
  semantics — so all existing call sites compile and behave identically without edits.
  - *Acceptance*: the run tracker drives the Rich-backed frame with zero call-site edits; teardown
    restores the cursor exactly once and is safe to call twice.
- **TRIX-FR-004**: The bottom-anchored stage bar shall be the live region of the Rich display —
  pinned at the bottom of the terminal — with all other output printed above it into ordinary
  scrollback; no alternate screen buffer and no DECSTBM scroll region shall ever be used.
  - *Acceptance*: hundreds of emitted lines all land in scrollback while the bar stays visible; the
    output stream never contains a scroll-region or alternate-screen sequence.
- **TRIX-FR-005**: The dispatched agent's streamed stdout/stderr shall pass to the terminal with
  content unchanged — routed through a non-highlighting console (no syntax highlighting, no markup
  interpretation) — with SGR color preserved and cursor/screen control sequences sanitized exactly
  as before.
  - *Acceptance*: an agent line with color keeps its color; a line attempting a screen clear or
    cursor move is stripped of the attempt; the visible text is unmodified.
- **TRIX-FR-006**: `--json` output shall remain byte-identical to the pre-rewrite behavior: the
  JSON serialization path shall not pass through any Rich formatting.
  - *Acceptance*: a representative command's `--json` bytes equal a golden capture taken before the
    rewrite; forcing color on changes zero bytes of any `--json` payload.
- **TRIX-FR-007**: Under `NO_COLOR`, `--yes`, or a non-TTY stream, output shall degrade to plain
  sequential text with no ANSI escapes and no live updates — identical to the pre-rewrite
  degradation contract (CLIUX-FR-002/011, STEER-FR-015).
  - *Acceptance*: piped and `NO_COLOR` outputs contain no `\033[` sequence; a non-TTY run produces
    the plain streamed event log with no in-place redraws.
- **TRIX-FR-008**: No raw ANSI escape construction shall remain in the renderer modules: every
  escape sequence emitted is produced by `rich`, and escape literals appear in the renderer source
  only inside the patterns used to *strip or sanitize* incoming sequences.
  - *Acceptance*: a source scan of the style and frame modules finds no escape literal outside the
    declared strip/sanitize matchers.

### Non-Functional Requirements

- **TRIX-NFR-001**: Rendering shall stay deterministic and fully offline — identical state,
  environment, and config yield identical bytes; no network or model call (ref 3PWR-NFR-001,
  CLIUX-NFR-001).
  - *Acceptance*: rendering tests pass with networking disabled; pure render functions are
    byte-stable across calls.
- **TRIX-NFR-002**: Accessibility is unchanged: color is never the sole carrier of meaning, and the
  ASCII glyph fallback still applies when the stream cannot encode the Unicode marks
  (CLIUX-NFR-004 preserved).
  - *Acceptance*: with color and Unicode both unavailable, every status stays distinguishable.
- **TRIX-NFR-003**: The engine shall stay green under its own gates across this change, and
  `docs/STATUS.md` shall remain the single home of implementation status (ref 3PWR-NFR-006).
  - *Acceptance*: self-application gate run + ruff/mypy/pytest green; STATUS updated once at
    delivery.

## Success Criteria *(mandatory)*

- **TRIX-SC-001**: `uv sync` in the engine dev environment pulls in `rich` with no conflicts.
- **TRIX-SC-002**: A representative command's `--json` output is byte-for-byte identical to its
  pre-rewrite golden capture.
- **TRIX-SC-003**: On a 40-column or degraded terminal the output is plain text; the bottom stage
  bar is visible throughout a live run on a capable TTY.
- **TRIX-SC-004**: No hand-rolled ANSI string-math survives in the style or frame modules — all
  escape emission goes through Rich.
