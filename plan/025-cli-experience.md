# Plan 025 — A first-class `3pwr` CLI experience (CLIUX, spec 015)

**Spec:** [`specs/015-cli-experience/spec.md`](../specs/015-cli-experience/spec.md) (Spec ID `CLIUX`,
Standard). The presentation-layer counterpart to INITX (007) — which introduced the zero-dependency
styling primitives — and to EXEC (009) / RUNLIVE (011) / AUTOX (014), which built the native executive
and its live stage tracker. **Presentation only, no trust-spine module change** — `canonical`/`keys`/
`ledger`/`verify` are untouched; `--json` payloads, exit codes, and verdict bytes are byte-for-byte
unchanged (CLIUX-FR-007 / NFR-002), and the styler is never routed through machine output.

## Why

The styling pieces existed but were applied unevenly: only a handful of ~36 `3pwr` subcommands
(`init`, the `gate` verdict, `deps-check`, the `run` tracker) rendered richly, while most still printed
plain run-on one-liners; there was no shared *structured*-output vocabulary (headers, key/value blocks,
aligned tables, dividers), the run view was a single in-place line rather than a persistent "you are
here" stage header, and there was no verbosity control or user-facing UI configuration. The dependency
question ("third-party or our own?") was already answered by the codebase: the engine deliberately
avoids `rich`/`curses`/`colorama` to stay offline-reconstructable (3PWR-NFR-004/010) and keep `--json`
byte-identical (INITX-FR-014). CLIUX extends the home-grown layer rather than adopting a TUI library.

## What was done

- **Structured-output toolkit** in [`engine/src/threepowers/style.py`](../engine/src/threepowers/style.py)
  (CLIUX-FR-001..004): `Styler.header`/`status_row`/`kv`/`table`/`rule`/`bullet` over the existing ANSI
  vocabulary, plus `strip_ansi`/`visible_len`/`term_width`. With color off (non-TTY / `NO_COLOR` /
  `--json` / `--yes`) each primitive degrades to plain, alignment-preserving text equal to the colored
  output with the ANSI stripped; column widths use the *visible* width so colored cells still align. An
  ASCII glyph set is used when the stream can't encode the Unicode marks (CLIUX-NFR-004); the default
  `Styler` keeps the Unicode marks (preserves the INITX contract). No third-party dependency (NFR-003).
- **Consistent color + status vocabulary across every command** (CLIUX-FR-005/006): a shared `_styler` /
  `_compose` helper pair in [`cli.py`](../engine/src/threepowers/cli.py) routes all ~36 subcommands
  through the toolkit — each opens with a self-identifying header and renders status via the one
  glyph+color mapping. `--json` stays byte-identical (CLIUX-FR-007).
- **Auto-mode stage header** in [`orchestrate.py`](../engine/src/threepowers/orchestrate.py)
  (CLIUX-FR-008..012): `render_tracker`/`format_event`/`tracker_frame`/`Tracker` take an optional styler
  and colorize the eight-stage "you are here" strip (done green / current bold-cyan / upcoming dim),
  distinguishing running, paused-at-human-gate (prominent, with the exact resume command), and failed.
  The off-TTY log is always plain — a disabled styler wins even over `THREEPOWERS_FORCE_COLOR`, so a
  piped/captured run never carries escapes; `run --status` and `status` render the same snapshot.
- **Verbosity + preferences** (CLIUX-FR-013..015): global `--quiet`/`--verbose` (mutually exclusive) on
  every subcommand; `style.resolve_verbosity` and an extended `color_enabled(color_mode=...)`; a tolerant
  `Settings.load_ui()` reads `.3powers/config/ui.yaml` (color mode / verbosity / layout) with
  deterministic precedence **flag > env > file > default**, a missing/malformed file falling back to the
  shipped defaults (a malformed file warns once on stderr, never on `--json`). The documented `ui.yaml`
  is seeded by `3pwr init` via the scaffold glob and its defaults reproduce prior behavior.

## Verification

- Engine green under its own dev tooling: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest` — **598 passed, 1 skipped**.
- New suite [`tests/test_cli_experience.py`](../engine/tests/test_cli_experience.py) (21 tests) names
  every `CLIUX-FR-001..015` and `CLIUX-NFR-001..005`: toolkit strip-equality + ANSI presence,
  ASCII/accessibility fallback, no-third-party-dep, color/verbosity precedence, `ui.yaml`
  defaults/valid/malformed, `init` seeding, `--json` ANSI-free even under forced color, verbosity leaves
  `--json`/exit unchanged while human detail grows, the colorized tracker + distinct event states, the
  off-TTY-always-plain guarantee, and the prominent human-gate + resume command.
- Self-application (NFR-006), `3pwr gate run --path engine --tier Standard --base HEAD`: **format ✓,
  lint ✓, types ✓, tests ✓, diff_coverage 92.45% ≥ 80% ✓, sast ✓, dependency_scan ✓, secret_scan ✓,
  gate_gaming ✓**. Full-repo `spec_conformance` **passes**.
- Manual smoke: `classify` / `status` / `run` render structured, colored, headered output on a TTY;
  `--json` is clean JSON with zero ANSI even under `THREEPOWERS_FORCE_COLOR` + `color_mode: always`.

## Handoff — notes

- Two gate lines are **not** CLIUX-caused and pre-exist this change: `spec_integrity` fails on a local
  ledger seal drift for spec 002 (spec 002 is untouched here — the same result with or without this
  change; a maintainer re-seal / `spec_integrity` deviation is the standing follow-up, see plan 022),
  and the in-gate `spec_conformance` under `--base HEAD` is a diff-scope artifact of a tiny diff whose
  only changed test binds CLIUX ids — full-repo conformance is green.
- Spec 015 still needs the human spec-approval sign-off before it is formally advanced:
  `3pwr signoff --approver <you> --spec-id CLIUX --stage spec --spec specs/015-cli-experience/spec.md`.
- Non-goals held: no full-screen/curses TUI, no third-party rendering dependency, no change to `--json`
  schemas, exit codes, gates, or the two human gates; the `/3pwr.*` prompts were not restyled.
