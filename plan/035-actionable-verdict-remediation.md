# Plan 035 — Make a red verdict actionable, and fix the config/detector defects that fake failures

**Git branch:** `feat/034-prompt-templates-and-discovery` — **the plan is authored on the existing
branch at the user's request** ("use the existing branch … I commit myself later"). No new branch is
created and this plan file is **not** auto-committed; the user commits it.

**Origin:** a live `3pwr run` on a Next.js/TypeScript sample repeatedly stopped at the Verify verdict.
Investigation (this session) showed the failures fall into two classes that the current output does not
distinguish, and that the user has to untangle by hand every time:

- **False failures the harness itself causes** — the `format` gate runs biome's *linter* (not just its
  formatter) against a project that already lints with ESLint, and the `gate_gaming` detector flags its
  own ledger and ordinary test imports.
- **True failures with no next step** — a real `tsc` type error and a real `dependency_scan` advisory
  are surfaced correctly, but the user is "irritated and doesn't know what he has to do": there is an
  auto-fix hint for `format`/`lint` and **nothing** for the other gates, and no guidance on how to hand
  the fix back to the coding agent or when a signed deviation is the right move.

This plan does both: **fix the defects that fake failures**, and **turn every red gate into an
actionable next step** — plain-English guidance, an auto-fix command where one safely exists, a
copy-pasteable coder hand-back prompt, and the `3pwr deviation` command shown as an explicit,
labelled *last resort*.

## Tracks

- **Track A — `format` means format-only; `lint` means lint-only (biome).** The TypeScript adapter and
  the two biome auto-detection rules map both gates to `biome ci`/`biome check`, which run
  format + lint + import-organize. Split them: `format` → `biome format`, `lint` → `biome lint`, so
  biome-formats-and-ESLint-lints coexist without double-linting and a gate named `format` stops failing
  on lint rules.
- **Track B — `gate_gaming` stops crying wolf.** Exclude the `.3powers/` trust-spine directory from the
  gaming diff scan (today it re-flags its own recorded findings out of `ledger.jsonl`), and match
  assertion *calls* rather than the bare identifier (today `import { …, expect, … }` counts as a
  removed assertion). Genuine gaming signal is preserved; the two false-positive classes go away.
- **Track C — `dependency_scan` gains an auditable advisory allowlist.** Add an `advisories:` section to
  `scan.yaml` for `dependency_scan` (advisory id + **required reason** + **optional expiry**), reported
  in the gate output exactly like the existing exclusions. Accepting a real, assessed vulnerability
  becomes committed, expiring, and reviewable — not a blanket path glob and not (only) a deviation.
- **Track D — Actionable remediation on every failed gate.** Extend the per-gate failure panel with a
  structured **remediation block**: what the failure means, the safe auto-fix command when one exists,
  a **coder hand-back prompt** the user can paste back to the coding agent (or resume with), and the
  `3pwr deviation` command as a labelled last resort. Guidance is per-gate and data-driven, never a
  wall of text.
- **Track E — E2E sample truth-up.** Migrate the committed `e2e/typescript-orders` `biome.json` off the
  dead biome-v1 schema (`files.ignore`) to v2 (`includes`/format-only posture, `tailwindDirectives`),
  so the sample runs green under a modern biome and demonstrates the Track A split.
- **Track F — Deviations that actually work end-to-end.** Two live-run defects: (1) an expiring
  deviation with a date-only `--until` crashes every `3pwr run` with a naive-vs-aware `datetime`
  `TypeError`; (2) `3pwr run` never honours a recorded deviation at its Verify step (only the separate
  `3pwr advance` does), so a user who deviates a red gate stays stuck at gate-red on `--resume` with no
  indication the deviation was even seen. Fix the crash, make the run loop honour active deviations the
  way `advance` does, and surface "waived by deviation seq=N" wherever a red gate is covered.

- **Track G — Eager tail integrity check before appending.** Ledger tampering is caught today only at a
  verification checkpoint (`3pwr verify` / `advance`), so a manual or agent edit sits silent until the
  end of a run. Before every `append`, verify **the last entry only** — recompute its `entry_hash` and
  verify its Ed25519 signature — so a corrupted tail surfaces immediately, on the very next ledger
  operation, instead of at advance/ship. **Tail-only and O(1) by design**: one hash recompute + one
  signature verify, constant per append regardless of ledger size. Full-chain verification stays where it
  is (`verify`/`advance`); this never becomes an O(n)-per-append cost.

Tracks A, B, C, E, F, G are independent bug/config fixes and can land in any order. **Track D depends on
A–C and F** only in that its guidance strings reference the corrected behaviour (e.g. the deviation hint
for `dependency_scan` names the new allowlist, and the `gate_gaming`/`dependency_scan` guidance must
truthfully state that a recorded deviation is honoured by `run`/`advance` — true only after F); D should
land last.

### Explicitly out of scope

- **No `biome.json` scaffolded into user projects.** (User decision — "fix sample + command only".) Live
  projects keep their own config; Track A's format-only command is correct with or without a biome.json,
  and detection already honours a project's own `biome.json`/ESLint config.
- **No auto-fix for `gate_gaming` or `dependency_scan`.** By design a gaming signal must never be
  silently erasable; the only paths to green are an honest code fix or a signed deviation. Track D makes
  those paths *legible*, it does not add a bypass.
- **No change to what any gate passes/fails** beyond removing the two `gate_gaming` false-positive
  classes and honouring the new `dependency_scan` allowlist. The deterministic verdict, the signed
  ledger, `3pwr verify`, exit codes, and `--json` byte-stability are otherwise untouched (Track C/D add
  only strictly *additive* `--json`/details fields that `verify` already tolerates).

---

## Decisions recorded

Three were **confirmed by the user on 2026-07-08** via the planning questions; the rest are engineering
defaults proposed here and grounded in the code read this session. **No open questions remain — the plan
is finalized.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Remediation depth (Track D) | **Guidance + coder hand-back** — user-confirmed. Per-gate guidance, safe auto-fix cmd where one exists, a copy-pasteable coder fix-prompt, and the deviation cmd as a labelled last resort. | The user's explicit ask ("how can I go back to the coder and give him this prompt"). Turns the verdict from a verdict-only stop into a next-step. |
| 2 | biome config for live projects | **Fix sample + command only** — user-confirmed. Do **not** scaffold a `biome.json` into user projects. | Track A's `biome format` is correct with or without a project config; detection already honours a project's own config. Avoids 3Powers imposing style config on a user's repo. |
| 3 | Accepting a real dep vuln (Track C) | **`advisories:` allowlist in `scan.yaml`** — user-confirmed. Advisory id + required reason + optional expiry; reported in gate output. Plus an upgrade/remediation hint. | Auditable, committed, expiring, and scoped to *one* advisory — unlike a path glob (too broad) or a bare deviation (not vuln-specific). Mirrors the secret scanner's existing `ignore_rules`. |
| 4 | `format`/`lint` biome commands (Track A) | `format` → `biome format .` (`--write` fix); `lint` → `biome lint .` (`--write` fix). Applied in **both** the TS adapter manifest and the two biome `DETECT_RULES`. My decision. | `biome format` is formatter-only; `biome lint` is linter-only; only `ci`/`check` bundle both. The gate engine keys pass/fail off exit code, so the existing `biome` parser is unaffected. |
| 5 | `.3powers/` exclusion scope (Track B) | Exclude the whole `.3powers/` directory (relative to repo root) from the `gate_gaming` diff and untracked scans. My decision. | It is engine-managed trust state, never coder-authored source; the ledger provably contains the text of prior findings, so scanning it is a self-referential loop by construction. |
| 6 | Assertion-match precision (Track B) | Match assertion **calls** — require a `(` (allowing whitespace) after the assertion token, and keep the language-aware Go/pytest forms — so an identifier in an `import { … }` list no longer matches. My decision. | The current `\b(expect|assert|…)\b` matches `expect` inside `import { …, expect, … }`. Anchoring to a call removes that class without weakening real removed-assertion detection. |
| 7 | Guidance data model (Track D) | Guidance is **data keyed by gate**, resolved at render time in the failure-panel renderer; each `GateResult` may also carry a `details.remediation` string that overrides the static table. Purely presentational — never enters the verdict or the ledger. | Keeps the deterministic verdict and `--json` stable; lets scanner gates supply a finding-specific hint (e.g. the fixed version osv reports) while every gate still gets a sensible default. |
| 8 | Coder hand-back mechanism (Track D) | Emit a **copy-pasteable remediation prompt block** naming the failed gate(s), the offending findings, and the honest-fix instruction (never "make the check pass" — always "make the code satisfy it"); plus surface the existing `3pwr run --resume` as the re-dispatch path. No new model call, no auto re-dispatch. | The engine never calls a model; a prompt the user pastes into their coding agent (or a resume) keeps the human in control and stays backend-neutral. The wording must not teach gaming. |
| 9 | Deviation framing (Track D) | The `3pwr deviation …` command is shown under an explicit **"last resort — only if this is a deliberate, justified exception"** label, pre-filled with the failed gate, and never presented as the first or easy option. | A deviation is an auditable acceptance of risk, not a fix; presenting it casually would erode the gate. It must read as the exception. |
| 10 | E2E biome.json (Track E) | Rewrite to biome v2: `formatter.enabled: true`, `linter.enabled: false`, `assist.enabled: false`, `css.parser.tailwindDirectives: true`, v2 `$schema`, drop `files.ignore`. My decision, modelled on the user-supplied v2 config. | Format-only posture matches Track A (ESLint owns lint in the sample too); `tailwindDirectives` fixes the `@theme` parse error; dropping `files.ignore` fixes the v2 deserialization crash. |
| 11 | OSS-readiness of all new text | All new guidance/prompt/hint strings, `scan.yaml` comments, and template prose follow the open-source-readiness rule: no internal plan/spec/requirement ids in user-facing text; format teaching uses bare `FR-###`/`DEMO-FR-###`. Enforced by `engine/tests/test_oss_readiness.py`. | Guidance and the coder hand-back prompt are user-facing surfaces. |
| 12 | Deviation expiry crash fix (Track F) | Normalize `parse_iso` to **always return a timezone-aware UTC datetime** — when the parsed value is naive (a date-only or offset-less `--until`), attach `timezone.utc`. My decision. | The crash is a naive-vs-aware comparison at `deviations.py:118`; fixing it once in the parser fixes both `active_deviations` and `overdue_emergencies`, and every downstream comparison. Fail-safe: a value that still won't parse stays `None` (never expires) as today. |
| 13 | `run` honours deviations at Verify (Track F) | The `run` loop's Verify→proceed decision applies the **same coverage logic as `advance`**: if every red gate in the just-recorded verdict is covered by an active, signed deviation (scoped to the run's spec id; global applies), the run **proceeds** instead of stopping at gate-red — recorded and surfaced, never silent. My decision. | `3pwr run` is the orchestrated equivalent of stepping through `advance`; today only the standalone `advance` honours deviations (`trust.py:316-328`), so a `run`-driven user can never get past a deviated gate. The honest verdict is still recorded red (determinism preserved); only the *proceed* decision consults the deviation — exactly `advance`'s contract. |
| 14 | Visible waiver annotation (Track F/D) | Wherever a red gate is covered by an active deviation, annotate it — `gate run`, the `run` gate-red surface, and Track D's panel — with "waived by active deviation seq=N (approver: …)"; `gate run`'s verdict still records red (deviations never touch the verdict), but the output tells the user the deviation is recognized and that `run`/`advance` will accept it. My decision. | The user recorded deviations and saw a bare FAIL with no acknowledgement. The annotation closes the feedback gap without weakening the deterministic verdict. |
| 15 | Deviation requires a non-empty reason (Track F, minor) | `3pwr deviation` (non-revoke) **requires a non-empty `--note`/reason**, consistent with Track C's allowlist rule; an empty-reason deviation is rejected at record time with an actionable message. My decision. | A signed acceptance of risk with no stated reason is not auditable; the live run recorded `reason: ""` for the `dependency_scan` deviation. Symmetric with the advisory allowlist (Decision 3). Applies going forward; existing empty-reason ledger entries stay honoured (never rewrite the ledger). |
| 16 | Eager integrity check is **tail-only** (Track G) | Before each `append`, verify **only the last entry** (recompute `entry_hash`, verify its signature). **Not** a full-chain re-verify. User-confirmed constraint ("at least the tail … if this check costs performance don't add it"). | Tail-only is O(1) — one hash + one Ed25519 verify — so it is effectively free and safe to run on every append; full-chain would be O(n) per append (O(n²) per run) and is deliberately left to `verify`/`advance`. Catches the common case (a tampered/edited tail) immediately; deeper tamper is still caught at the next `verify`/`advance`. |

---

## Why now

1. **The same run fails the same way every time, and the output can't tell the user why.** A live run
   stops at Verify with `format`, `types`, and `dependency_scan` red (and on a second run `gate_gaming`
   red). Three of those are the judiciary working correctly; two are the harness mis-configured. The
   user cannot tell which is which from the panel, so every run becomes a manual investigation.
2. **`format` double-lints by construction.** `engine/src/threepowers/scaffold/adapters/typescript/adapter.yaml`
   maps `format.check_cmd` to `npx --no-install @biomejs/biome ci .`, and the biome `format`/`lint`
   `DETECT_RULES` in `engine/src/threepowers/adapters.py:236-281` both use `biome check .`. `ci` and
   `check` run the full recommended lint ruleset. When detection picks ESLint for `lint`
   (`adapters.py:272-281`), the `format` gate still lints via biome — a second, conflicting linter. Every
   biome failure in the live run (`noSvgWithoutTitle`, `noExplicitAny`, `noNonNullAssertion`,
   `noConfusingVoidType`, `noUnusedImports`, the Tailwind `@theme` parse error) is a *lint* rule, not
   formatting.
3. **`gate_gaming` is partly self-inflicted.** `engine/src/threepowers/gaming.py:149-153` diffs the whole
   tree, including `.3powers/ledger.jsonl`. The ledger *records prior gate_gaming findings*, whose text
   contains `eslint-disable-next-line`; the `eslint[-]disable` pattern (`gaming.py:24`) then re-flags the
   newly-appended ledger line — every finding re-triggers itself on the next run. Separately, `_ASSERT`
   (`gaming.py:32-35`) matches the bare word `expect`, so `import { beforeEach, describe, expect, it, vi }`
   being removed/reordered is counted as "assertion removed". Both were observed in the live output.
4. **A true dep advisory has no auditable acceptance path.** `scan.yaml` today supports path globs
   (`ignore`) and, for the secret scanner only, rule ids (`ignore_rules`). There is no way to accept a
   single assessed advisory (`GHSA-qx2v-qp2m-jg93` in a transitive `postcss`) short of a broad glob or a
   full deviation — neither is right for "dev-only transitive, no upstream fix yet, accept until <date>".
5. **A red gate is a dead end, not a next step.** `engine/src/threepowers/orchestrate.py:754-771`
   (`_panel_body_lines`) appends `↳ auto-fix:` only when the gate carries a `fix_cmd` — today only
   `format`/`lint`. `types`, `tests`, `dependency_scan`, and `gate_gaming` get findings and nothing else.
   The user has no in-product guidance on how to fix, how to hand the fix back to the coder, or when a
   deviation is appropriate.
6. **An expiring deviation crashes the run.** Recording a deviation with a date-only `--until` (e.g.
   `2026-10-01`) makes `parse_iso` (`engine/src/threepowers/deviations.py:59-66`) return a **naive**
   datetime; `active_deviations` (`deviations.py:118`) then compares it against the tz-aware `now_utc()`
   and raises `TypeError: can't compare offset-naive and offset-aware datetimes`. It fires at
   `engine/src/threepowers/cli/run.py:1529` — the *first* thing `cmd_run` does — so **every** `3pwr run`
   aborts with a traceback the moment any expiring deviation exists in the ledger. Observed live.
7. **`run` ignores the deviations the user records.** Deviations are honoured only by the standalone
   `3pwr advance` (`trust.py:316-328`); the `run` loop's `run_verdict` (`run.py:1096-1131`) returns
   pass/fail straight from the honest verdict and never consults `covered_gates`. So a user driving the
   lifecycle with `3pwr run` records a valid deviation, re-runs, and is stopped at the same gate-red —
   with no message that the deviation was seen. The mechanism is effectively unreachable from the primary
   workflow. Observed live (once the crash in #6 is worked around).
8. **Ledger tampering is caught only lazily.** A manual (or agent) edit to `.3powers/ledger.jsonl` raises
   nothing at write time; `append` (`engine/src/threepowers/ledger.py:97-127`) only reads the last
   entry's `entry_hash` to chain forward and never re-verifies, and `gate run` does not verify the chain.
   `verify_ledger` runs only at `3pwr verify` and `3pwr advance` (`trust.py:46,295`). The ledger is
   **tamper-evident and unforgeable** (the Ed25519 private key lives outside the repo — `keys.py:7-10`),
   so a corrupted ledger cannot advance/ship — but the corruption stays silent until that late checkpoint
   rather than surfacing on the next ledger touch. Observed live (a manual edit passed unremarked).

---

## Track A — `format` = format-only, `lint` = lint-only (biome)

**Goal.** A gate named `format` checks only formatting; a gate named `lint` checks only lint. Biome and
ESLint coexist (biome formats, ESLint lints) with no double-linting.

**Changes.**

- `engine/src/threepowers/scaffold/adapters/typescript/adapter.yaml`
  - `format.check_cmd` → `npx --no-install @biomejs/biome format .`
  - `format.fix_cmd` → `npx --no-install @biomejs/biome format --write .`
  - `lint.cmd` → `npx --no-install @biomejs/biome lint .`
  - `lint.fix_cmd` → `npx --no-install @biomejs/biome lint --write .`
  - Update the manifest's header comment (it currently states biome covers both via `ci`).
- `engine/src/threepowers/adapters.py` — the two biome `DETECT_RULES` (`format` at ~236, `lint` at ~262):
  - `format` spec → `biome format .` / `biome format --write .`
  - `lint` spec → `biome lint .` / `biome lint --write .`
- Parser: unchanged (`parser: biome`); the gate engine determines pass/fail from the process exit code
  (`engine/src/threepowers/gates.py`), and `biome format`/`biome lint` exit non-zero on findings.

**Acceptance.**

- On a repo with ESLint configured, a `3pwr gate run` shows `format · biome` failing *only* on
  formatting diffs and `lint · eslint` owning lint; biome lint rules no longer appear under `format`.
- On a repo where biome owns both, `lint` runs `biome lint` and still catches lint issues.
- `3pwr gate config show` reflects the new commands for both gates.

## Track B — `gate_gaming` false-positive removal

**Goal.** Preserve genuine gaming detection; eliminate the ledger self-reference and the import-identifier
false positives.

**Changes (`engine/src/threepowers/gaming.py`).**

- Exclude `.3powers/` from the diff and untracked scans:
  - In `_diff`, restrict the `git diff` pathspec to exclude the trust spine, e.g. add
    `':(exclude).3powers/**'` to the `git diff … -- <target>` args (or filter `+++ b/` file headers whose
    path is under `.3powers/`). The exclusion must be relative to the repo root and robust when `target`
    *is* the repo root.
  - In `_scan_untracked`, skip any path under `.3powers/`.
- Tighten `_ASSERT` to match assertion **calls**, not identifiers:
  - Require an opening parenthesis after the token, tolerant of whitespace — conceptually
    `\b(assert|expect|self\.assert|pytest\.raises|require\.\w+)\s*\(` plus `\.(toBe|toEqual)\w*\s*\(`
    and the existing Go `t.(Error|Fatal|…)` forms. The change must still match the real removed
    assertions from the live run (`expect(addButton).toHaveClass("bg-black")`) and no longer match
    `import { …, expect, … }`.
- No change to the red → deviation path, the untracked-file suppression scan, or the weak-added-test
  logic beyond the shared `_ASSERT` tightening.

**Acceptance.**

- A run whose only `.3powers/` change is appended ledger entries produces **zero** `gate_gaming`
  findings from the ledger.
- Removing/reordering a `vitest`/testing import line does not produce an "assertion removed" finding.
- A test that genuinely deletes an `expect(...)` assertion (net loss per file) **still** fails
  `gate_gaming` — regression-guarded.

## Track C — `dependency_scan` advisory allowlist

**Goal.** Accept a single assessed advisory in a committed, auditable, expiring way.

**Changes.**

- `scan.yaml` schema (docs in both `.3powers/config/scan.yaml` and
  `engine/src/threepowers/scaffold/config/scan.yaml`): add under `dependency_scan`:
  ```yaml
  dependency_scan:
    ignore: [ … ]           # existing path globs
    advisories:             # NEW — accept specific assessed vulnerabilities
      - id: "GHSA-xxxx-xxxx-xxxx"   # osv/GHSA/CVE id, matched against the scanner's finding id
        reason: "why this is accepted (required — a blank reason is ignored)"
        until: "2026-10-01"          # optional ISO date; after it, the advisory blocks again
  ```
- `engine/src/threepowers/scanners.py`
  - `dependency_scan(...)` gains an `advisories` parameter (list of `{id, reason, until}`), threaded from
    the same `scan.yaml` loader that already supplies `ignore` (the plumbing that calls the scanners).
  - At `scanners.py:302-308`, before appending a finding, drop it when its `v.get("id")` matches an
    allowlisted, non-expired advisory **with a non-empty reason**; count it into `excluded`.
  - Expiry: reuse the existing ISO parser (`deviations.parse_iso`) semantics; an expired or
    reason-less entry does **not** suppress (fail-closed).
  - Surface accepted advisories through `_with_exclusion_report` so the gate output names them and the
    count — exactly like path-glob exclusions today (security invariant: never silent).
- Update the `scan.yaml` "SECURITY — read before widening" comment to cover advisory acceptance
  (reason required, expiry recommended, each acceptance is reported, never silent).

**Acceptance.**

- With `postcss`'s `GHSA-qx2v-qp2m-jg93` allowlisted with a reason, `dependency_scan` passes and the
  panel reports "1 advisory accepted (scan.yaml): GHSA-… — <reason>".
- An allowlist entry with no reason, or past its `until`, does **not** suppress the finding.
- A different advisory is still reported and still fails.

## Track D — Actionable remediation on every failed gate

**Goal.** Every failed gate's panel ends with a short, honest next-step: what it means, the safe auto-fix
(when one exists), a coder hand-back prompt, and the deviation last-resort.

**Changes (rendering — `engine/src/threepowers/orchestrate.py`).**

- Extend `_panel_body_lines` (`orchestrate.py:754`) so that after the findings and the existing
  `↳ auto-fix:` line it appends a **remediation block** resolved from:
  1. `gate.details["remediation"]` if the gate supplied a finding-specific hint (e.g. osv's fixed
     version), else
  2. a static per-gate guidance table (a new small data structure in this module), keyed by gate name,
     with a sensible generic default for unknown gates.
- The block, kept to a few lines, contains for a failing gate:
  - **What it means** — one line (e.g. `gate_gaming`: "the coder weakened a check — review before
    accepting").
  - **Fix** — the honest action. For fixable gates, the auto-fix command (already shown). For
    `types`/`tests`/`gate_gaming`, the *code* fix framed as "make the code satisfy it" — never "make the
    check pass".
  - **Hand back to your coding agent** — a copy-pasteable prompt block (see below) and the
    `3pwr run --resume --spec-id <id>` re-dispatch path.
  - **Last resort** — `3pwr deviation --gate <gate> --approver <you> --note "<why>" [--until <date>]`,
    under an explicit label that it is an auditable exception, not a fix, and only for a deliberate,
    justified case.
- The coder hand-back prompt is assembled deterministically from the failed gate(s) and their findings
  (a new small helper, unit-tested for stable text). Wording is drawn from / consistent with
  `implement.agent.md` ("never weaken a gate; make the code satisfy the spec") so the user is handing the
  coder a spec-faithful instruction, not a gaming one.
- All of this is **human output only** — it must not touch `Verdict.to_dict()`, the ledger, or the
  `--json` payload. It renders through the existing `style.Styler` (rich panel on a TTY, plain indent
  otherwise), degrades cleanly, and respects `--json` (suppressed) and verbosity.

**Deviation pre-fill.** The shown `3pwr deviation` command pre-fills `--gate <failed-gate>`; `gate_gaming`
and `dependency_scan` are already in the deviatable set (`GATE_ORDER`, see
`engine/src/threepowers/cli/exceptions.py`), so the command is valid as printed.

**Acceptance.**

- Each failed gate's panel ends with a remediation block; a passing run shows none.
- `format`/`lint` still show the auto-fix command; `types`/`tests`/`gate_gaming`/`dependency_scan` show
  code-fix guidance + the coder hand-back prompt + the labelled deviation last resort.
- The coder hand-back prompt names the failed gate and its findings and instructs an honest fix; it never
  instructs suppressing/deleting a check. Snapshot-tested for stable, OSS-ready wording.
- `--json` output is byte-identical to before this track (verified by an existing/added byte-stability
  test).

## Track E — E2E sample truth-up

**Goal.** The committed sample runs green under modern biome and demonstrates the Track A split.

**Changes.**

- `e2e/typescript-orders/project/biome.json`: rewrite to biome v2 — `$schema` v2, drop `files.ignore`,
  `formatter.enabled: true` (keep indent/quote style), `linter.enabled: false`, `assist.enabled: false`,
  `css.parser.tailwindDirectives: true`.
- Confirm `e2e/typescript-orders/project/package.json`'s `check` script and biome pin are consistent with
  the format-only posture (the `check` script may move to `biome format`/`biome lint` to match the gate
  split, or stay as the project's own convenience script — verify it does not reintroduce double-lint in
  `./e2e/run.sh typescript --check`).
- (Worktree copies of this file under `.claude/worktrees/**` are throwaway and are not edited.)

**Acceptance.**

- `./e2e/run.sh typescript --check` runs the sample's `format`/`lint` gates green under a v2 biome.

## Track F — Deviations that actually work end-to-end

**Goal.** An expiring deviation never crashes a run; a recorded deviation is honoured by `3pwr run` (not
only by `3pwr advance`); and wherever a red gate is covered by a deviation the user is told so.

**F1 — Fix the naive/aware crash (`engine/src/threepowers/deviations.py`).**

- `parse_iso` normalizes to timezone-aware UTC: after `datetime.fromisoformat(...)`, if the result's
  `tzinfo is None`, attach `timezone.utc`; still return `None` on a malformed/absent value.
- With that single fix, `active_deviations` (`deviations.py:118`) and `overdue_emergencies`
  (`deviations.py:162`) compare aware-to-aware and no longer raise.
- Add a regression test: a deviation with `expires_at: "2026-10-01"` (date-only) is parsed, and
  `active_deviations` returns it as active (not crash) when `now` precedes it, expired after.

**F2 — `run` honours active deviations at Verify (`engine/src/threepowers/cli/run.py`).**

- After the Verify verdict is produced/recorded in `run_verdict` (`run.py:1096-1131`), compute the red
  gates of that verdict and the `covered_gates(active_deviations(ledger.entries()), spec_id)` set —
  reusing the exact coverage/scope logic `advance` uses (`trust.py:311-328`), ideally factored into a
  shared helper in `deviations.py` (e.g. `uncovered_red_gates(verdict_payload, active, spec_id)`) so
  `advance` and `run` cannot drift.
- If **every** red gate is covered, the run **proceeds** past Verify (treat the step as pass-for-proceed)
  and records/surfaces which deviation seq(s) applied; if any red gate is **uncovered**, the run stops at
  gate-red exactly as today, naming the uncovered gate(s).
- The honest verdict recorded in the ledger is **unchanged** (still red) — only the run's *proceed*
  decision consults deviations. Determinism and the trust spine are untouched.
- The emergency-cleanup-overdue and other `advance` refusals that are **not** about gate coverage are out
  of scope here (they remain `advance`'s concern); F2 only unifies the red-gate-coverage decision.

**F3 — Visible waiver annotation (rendering).**

- In `gate run` output and the Track D failure panel, when a failed gate is covered by an active
  deviation, append a line: `↳ waived by active deviation seq=N (approver: <who>)` — and for `run`, a
  proceed notice: `proceeding past <gate> under deviation seq=N`. The deviation lookup for annotation is
  read-only over the ledger; it must not alter the verdict dict, the ledger entry, or `--json`.
- `gate run`'s verdict stays honestly red (deviations never touch the verdict); the annotation only tells
  the user the deviation is recognized and that `run`/`advance` will accept it.

**F4 — Require a non-empty reason (`engine/src/threepowers/cli/exceptions.py`).**

- `cmd_deviation` (non-revoke path) rejects an empty/whitespace `--note` with an actionable error
  ("a deviation must state a reason — pass `--note \"<why>\"`"), mirroring `--approver`'s existing
  requirement (`exceptions.py:71`) and Track C's allowlist rule. Revoke entries are unaffected.
- Existing empty-reason deviations already in a ledger stay honoured — the ledger is append-only and is
  never rewritten.

**Acceptance.**

- A deviation recorded with `--until 2026-10-01` does not crash `3pwr run` / `3pwr gate run` /
  `3pwr advance`; the deviation is active until that date and inactive after.
- With an active deviation covering `dependency_scan` and `gate_gaming`, `3pwr run --resume` proceeds
  past Verify (does not stop at gate-red), and prints which deviation seq(s) applied.
- `3pwr gate run` still records a red verdict for the deviated gates but annotates each with
  "waived by active deviation seq=N".
- `3pwr advance` behaviour is unchanged (already correct) — verified by its existing tests, plus the new
  shared-helper refactor keeps it green.
- `3pwr deviation --gate dependency_scan --approver x` (no `--note`) is rejected; with a non-empty
  `--note` it succeeds.

## Track G — Eager tail integrity check before appending

**Goal.** A corrupted ledger surfaces on the next ledger operation, not only at `advance`/`ship` — at
zero meaningful cost.

**Changes.**

- Factor the per-entry check that `verify_ledger` already performs inline
  (`engine/src/threepowers/verify.py:99-130` — `seq`, `prev_hash` linkage, recomputed `entry_hash`,
  signature against the active key) into a small reusable `verify_entry(entry, expected_prev, candidates)`
  helper, so `verify_ledger` and the append path share one implementation and cannot drift.
- In `Ledger.append` (`engine/src/threepowers/ledger.py:97-127`), **before** writing the new entry,
  run `verify_entry` on the **current last entry only**: recompute its `entry_hash` from its canonical
  core and verify its Ed25519 signature. On failure, raise a clear `LedgerTamperError` (a new, specific
  exception) naming the offending seq and pointing at `3pwr verify` — do **not** append onto a broken
  tail.
- Empty ledger (genesis append) and a legitimately intact tail are no-ops; the check only fires on real
  tail corruption.
- Cost: **O(1)** per append — one hash recompute + one signature verify on a single entry, independent of
  ledger length. No full-chain walk is added anywhere in the hot path.
- Scope boundary: this is a *tail* check. Tamper of a **middle** entry is still caught at the next
  `3pwr verify` / `3pwr advance` (unchanged) — Track G does not turn append into a full verifier.

**Acceptance.**

- Editing the last ledger entry's payload by hand, then running any command that appends (`gate run`,
  a stage commit in `run`), fails immediately with a tamper error naming the seq — instead of silently
  appending and only failing later at `advance`.
- An intact ledger appends exactly as before (byte-identical new entry); no observable latency change on
  a realistic ledger (benchmark note in the test).
- `verify_ledger` output and behaviour are unchanged (it now calls the shared `verify_entry` but the
  results are identical) — guarded by its existing suite.

---

## Cross-cutting requirements & constraints

- **REQ-A**: `format` never runs a linter; `lint` never runs a formatter (biome).
- **REQ-B**: `gate_gaming` never flags `.3powers/**`; never treats an import identifier as an assertion;
  still flags a genuine net assertion loss and added suppressions.
- **REQ-C**: A `dependency_scan` advisory is suppressible only with a non-empty reason and only until an
  optional expiry; every acceptance is reported in the gate output.
- **REQ-D**: Every failed gate renders an honest remediation block (guidance + auto-fix-if-any + coder
  hand-back prompt + deviation last resort). No guidance ever instructs weakening a check.
- **REQ-F**: An expiring deviation never crashes any command; `3pwr run` honours active deviations at
  Verify exactly as `advance` does (shared helper, no drift); a red gate covered by a deviation is
  annotated wherever it is shown; a new deviation requires a non-empty reason.
- **REQ-G**: `append` verifies the current tail entry (hash + signature) before writing and refuses on a
  broken tail; the check is O(1) and adds no full-chain walk; deeper tamper detection stays at
  `verify`/`advance`; `verify_ledger` results are unchanged by the shared-helper refactor.
- **SEC-001**: No new escape hatch weakens a gate silently — Track C acceptances and Track D deviation
  hints are auditable/explicit; Track B only removes provable false positives.
- **CON-001**: The deterministic verdict, signed ledger, `3pwr verify`, exit codes, and `--json`
  byte-stability are unchanged except for strictly additive fields `verify` already tolerates.
- **CON-002**: No model call is added to the engine; the coder hand-back is a prompt the user pastes or a
  `--resume`. Backend-neutral.
- **GUD-001 (OSS readiness)**: All new user-facing strings obey `engine/tests/test_oss_readiness.py` — no
  internal plan/spec/requirement ids; format teaching uses bare `FR-###`/`DEMO-FR-###`.
- **GUD-002 (self-application)**: The engine must stay green under its own gates after these changes,
  including its own `gate_gaming` (the `.3powers/` exclusion must not break the engine's self-run) and
  the High-risk coverage floors.

## Testing strategy

- **Track A**: `engine/tests/test_adapters.py` — the biome `DETECT_RULES` specs assert the format-only /
  lint-only commands; a fixture repo with an ESLint config resolves `format→biome format` and
  `lint→eslint`.
- **Track B**: `engine/tests/` gaming tests — (1) a diff that only appends `.3powers/ledger.jsonl` yields
  no findings; (2) a removed testing-import line yields no "assertion removed"; (3) a genuinely deleted
  `expect(...)` assertion still fails; (4) an added `eslint-disable` still fails.
- **Track C**: scanner tests — allowlisted advisory (with reason) suppresses and is reported; no-reason /
  expired does not; unrelated advisory still fails.
- **Track D**: renderer tests — per-gate remediation block presence and OSS-ready wording (snapshot);
  coder hand-back prompt is deterministic and never contains a "suppress/delete/disable" instruction;
  `--json` byte-stability regression test.
- **Track E**: `./e2e/run.sh typescript --check` green; a smoke that the sample `biome.json` parses under
  biome v2.
- **Track G**: `engine/tests/test_ledger.py` — a hand-edited last entry makes the next `append` raise
  `LedgerTamperError` naming the seq; an intact ledger appends a byte-identical entry; `verify_entry`
  and `verify_ledger` agree on the same fixtures (shared-helper parity); a middle-entry tamper is *not*
  caught by append but *is* caught by `verify_ledger` (scope boundary). Trust-spine coverage stays ≥ 95%.
- **Track F**: `engine/tests/test_deviations.py` — (1) date-only `expires_at` parses aware and
  `active_deviations`/`overdue_emergencies` don't raise; (2) the shared `uncovered_red_gates` helper
  returns the right set for covered / partially-covered / uncovered verdicts, scoped by spec id;
  (3) `advance` still passes its existing suite after the refactor. `run` tests — a red Verify fully
  covered by an active deviation proceeds (with the applied-seq notice) and one with an uncovered gate
  still stops at gate-red. Renderer test — the "waived by active deviation seq=N" annotation appears only
  when covered and never mutates `--json`. `exceptions` test — empty-reason deviation rejected, non-empty
  accepted.
- **Whole engine**: `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` stays green (self-application, incl. the engine's own `gate_gaming`).

## Risks & mitigations

- **`git diff` pathspec exclusion portability** (Track B) — the `:(exclude)` magic pathspec must behave
  when `target` is the repo root vs a subdir. *Mitigation:* test both; fall back to filtering by
  `+++ b/` header prefix if the pathspec form is fragile.
- **Tightened `_ASSERT` misses a real removed assertion** (Track B) — over-tightening could let a genuine
  weakening slip. *Mitigation:* regression test built from the live-run findings (`toHaveClass`,
  `toHaveBeenCalledTimes`, `toBeGreaterThanOrEqual`, bare `expect(` calls); keep language-aware forms.
- **`biome lint` behaviour when a project has no biome linter config** (Track A) — `biome lint` uses
  recommended rules by default, which for a project that uses ESLint would still be noise *if* detection
  picks biome for `lint`. *Mitigation:* detection precedence already prefers a project's ESLint config
  for the `lint` gate; document that a biome-linting project opts in via its own `biome.json`.
- **Remediation text drift / gaming-teaching** (Track D) — guidance must never read as "make the check
  pass". *Mitigation:* snapshot tests assert the honest framing and the OSS-readiness test guards ids.
- **`--json` regressions** (Tracks C/D/F) — additive fields only; byte-stability test guards the payload.
- **`run`/`advance` deviation logic drift** (Track F) — two copies of the coverage decision could diverge.
  *Mitigation:* factor one shared helper in `deviations.py` and cover it directly; `advance` and `run`
  both call it. The honest verdict recorded to the ledger is never altered by either path.
- **A deviation silently masking a real regression** (Track F) — honouring a deviation in `run` must never
  become invisible. *Mitigation:* the applied-seq notice and the panel "waived by …" annotation are
  mandatory and tested; the recorded verdict stays red; deviations remain signed, revocable, and (when
  set) expiring.
- **Tail check false-blocking a legitimate append** (Track G) — a bug in the tail check could refuse a
  valid append and wedge the trust spine. *Mitigation:* reuse the exact `verify_entry` logic
  `verify_ledger` already trusts (no second implementation), no-op on an empty/genesis ledger, and a
  parity test that `verify_entry` agrees with `verify_ledger` on the same last entry. Cost is O(1); a
  benchmark asserts no full-chain walk was introduced.

## Definition of done

- All seven tracks' acceptance criteria pass; the engine is green under ruff/mypy/pytest and its own
  `3pwr gate run --path engine` (including `gate_gaming` and High-risk coverage).
- `docs/` updated in the same unit of work: the gate/verdict reference gains the remediation surface and
  the `scan.yaml` advisory allowlist; the CLI reference reflects the format-only/lint-only biome commands
  and documents that `3pwr run` (not only `advance`) honours an active deviation, that a deviation now
  requires a reason, and that an append now refuses on a tampered ledger tail (pointing at `3pwr verify`).
  (Per AGENTS.md, a behaviour change without a docs update is incomplete.)
- No internal ids leak into any user-facing string (OSS-readiness test green).

---

## Open questions

None — the three structural forks were resolved by the user on 2026-07-08 (see Decisions 1–3); the
remaining decisions are engineering defaults grounded in the code read this session.

## Suggested handover

When you're ready, the next step is the **implementation-plan agent**, which turns this plan into
`plan/IMPLEMENTATION-006-fix-actionable-verdict-remediation.md` (phased, file-scoped tasks). Per AGENTS.md
the handover is explicit — say the word and I'll dispatch it. All Python changes under `engine/` then go
through the python-engineer agent.
