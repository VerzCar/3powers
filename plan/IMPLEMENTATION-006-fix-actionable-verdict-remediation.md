---
goal: Make a red verdict actionable and fix the config/detector defects that fake failures
version: 1.0
date_created: 2026-07-08
last_updated: 2026-07-08
owner: 3Powers maintainers
status: 'Planned'
tags: [bug, feature, refactor, architecture]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan operationalizes source plan `plan/035-actionable-verdict-remediation.md`. It
does two things: (1) fixes the harness defects that manufacture false gate failures (biome double-lint,
`gate_gaming` self-reference and import-identifier false positives), and (2) turns every red gate into an
actionable next step (per-gate guidance, a safe auto-fix command when one exists, a copy-pasteable coder
hand-back prompt, and a labelled deviation last-resort). It also repairs deviations end-to-end (expiring
deviation crash, `run` never honouring deviations, empty-reason acceptance, missing waiver annotation),
adds an auditable `dependency_scan` advisory allowlist, truths-up the TypeScript e2e sample to biome v2,
and adds an O(1) eager tail-integrity check before every ledger append.

The work is split into eight phases. Phases 1–6 implement the six independent tracks (A, B, C, E, G, F).
Phase 7 implements Track D (actionable remediation), which must land last because its guidance strings
reference the corrected behaviour of Tracks A–C and F. Phase 8 is a dedicated verification phase.

Execution note (per `AGENTS.md`/`CLAUDE.md`): all Python changes under `engine/src/threepowers/` with
tests under `engine/tests/` are performed by the **python-engineer agent** at implementation time. Every
behaviour change ships with a matching `docs/` update in the same unit of work. Trust-spine modules
(`canonical`, `keys`, `ledger`, `verify`) are High-risk and must hold coverage ≥ 95%.

## 1. Requirements & Constraints

- **REQ-A**: A gate named `format` never runs a linter and a gate named `lint` never runs a formatter for
  biome; biome (format) and ESLint (lint) coexist with no double-linting.
- **REQ-B**: `gate_gaming` never flags any path under `.3powers/**`, never treats an import identifier as
  an assertion, yet still flags a genuine net assertion loss and added suppressions.
- **REQ-C**: A `dependency_scan` advisory is suppressible only with a non-empty reason and only until an
  optional expiry; every acceptance is reported in the gate output (never silent).
- **REQ-D**: Every failed gate renders an honest remediation block (guidance + auto-fix-if-any + coder
  hand-back prompt + deviation last resort); no guidance ever instructs weakening a check.
- **REQ-E**: The committed `e2e/typescript-orders` sample runs green under a modern biome v2 and
  demonstrates the Track A format-only/lint-only split.
- **REQ-F**: An expiring deviation never crashes any command; `3pwr run` honours active deviations at
  Verify exactly as `advance` does via a shared helper (no drift); a red gate covered by a deviation is
  annotated wherever it is shown; a new deviation requires a non-empty reason.
- **REQ-G**: `Ledger.append` verifies the current tail entry (recomputed `entry_hash` + Ed25519
  signature) before writing and refuses on a broken tail; the check is O(1) and adds no full-chain walk;
  deeper tamper detection stays at `verify`/`advance`; `verify_ledger` results are unchanged by the
  shared-helper refactor.
- **SEC-001**: No new escape hatch weakens a gate silently — Track C acceptances and Track D deviation
  hints are auditable and explicit; Track B only removes provable false positives.
- **CON-001**: The deterministic verdict, signed ledger, `3pwr verify`, exit codes, and `--json`
  byte-stability are unchanged except for strictly additive fields that `verify` already tolerates.
- **CON-002**: No model call is added to the engine; the coder hand-back is a prompt the user pastes or a
  `3pwr run --resume`. Backend-neutral.
- **CON-003**: Track D (Phase 7) MUST be implemented after Tracks A–C and F because its guidance strings
  assert the corrected behaviour of those tracks (dependency_scan allowlist naming; deviation honoured by
  `run`).
- **GUD-001**: All new user-facing strings obey `engine/tests/test_oss_readiness.py` — no internal
  plan/spec/requirement ids in user-facing text; format teaching uses bare `FR-###`/`DEMO-FR-###`.
- **GUD-002**: The engine stays green under its own gates after every phase, including its own
  `gate_gaming` (the `.3powers/` exclusion must not break the engine self-run) and the High-risk coverage
  floors.
- **PAT-001**: The `dependency_scan` advisory allowlist mirrors the secret scanner's existing
  `ignore_rules` pattern (rule-id keyed, reported via `_with_exclusion_report`).
- **PAT-002**: The `run`/`advance` deviation coverage decision is a single shared helper in
  `deviations.py`; both call sites consume it and cannot diverge.

## 2. Implementation Steps

### Phase 1

- GOAL-001: Track A — split biome so `format` runs `biome format` (formatter-only) and `lint` runs
  `biome lint` (linter-only) in both the TypeScript adapter manifest and the biome auto-detection rules,
  with matching docs and adapter tests.

| Task     | Description                                                                                                                                                                                                                                                                                                                          | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/scaffold/adapters/typescript/adapter.yaml`: set `format.check_cmd` → `npx --no-install @biomejs/biome format .`, `format.fix_cmd` → `npx --no-install @biomejs/biome format --write .`, `lint.cmd` → `npx --no-install @biomejs/biome lint .`, `lint.fix_cmd` → `npx --no-install @biomejs/biome lint --write .`. |           |      |
| TASK-002 | In the same `adapter.yaml`, update the manifest header comment that currently states biome covers both format and lint via `ci` to describe the format-only/lint-only split.                                                                                                                                                          |           |      |
| TASK-003 | In `engine/src/threepowers/adapters.py` `DETECT_RULES` (biome `format` rule ~236, biome `lint` rule ~262): change the biome `format` spec to `biome format .` / `biome format --write .` and the biome `lint` spec to `biome lint .` / `biome lint --write .`. Leave `parser: biome` and the ESLint `lint` rule (~272-281) unchanged.  |           |      |
| TASK-004 | Confirm no change is required to `engine/src/threepowers/gates.py` (pass/fail keys off process exit code; `biome format`/`biome lint` exit non-zero on findings). Record confirmation in the phase note; make no code change if none is needed.                                                                                        |           |      |
| TASK-005 | Update `docs/cli-reference.md` (and any gate/verdict reference doc that names the biome commands) so the documented `format`/`lint` commands are the format-only/lint-only biome commands. No internal ids in prose (GUD-001).                                                                                                          |           |      |
| TASK-006 | Add/extend `engine/tests/test_adapters.py`: assert the biome `DETECT_RULES` specs equal the format-only / lint-only commands; a fixture repo with an ESLint config resolves `format`→`biome format` and `lint`→`eslint`; a biome-only repo resolves `lint`→`biome lint`.                                                               |           |      |

### Phase 2

- GOAL-002: Track B — remove the two `gate_gaming` false-positive classes by excluding `.3powers/**` from
  the gaming scans and by matching assertion **calls** rather than the bare identifier, while preserving
  genuine gaming detection.

| Task     | Description                                                                                                                                                                                                                                                                                                                                  | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-007 | In `engine/src/threepowers/gaming.py` `_diff`: restrict the `git diff` pathspec to exclude the trust spine — add `':(exclude).3powers/**'` to the `git diff … -- <target>` args, relative to the repo root and robust when `target` is the repo root. If the magic pathspec is fragile, fall back to filtering `+++ b/` file headers under `.3powers/`. |           |      |
| TASK-008 | In `engine/src/threepowers/gaming.py` `_scan_untracked`: skip any path under `.3powers/`.                                                                                                                                                                                                                                                     |           |      |
| TASK-009 | In `engine/src/threepowers/gaming.py` tighten `_ASSERT` (~32-35) to match assertion calls: require an opening `(` (whitespace-tolerant) after the token — conceptually `\b(assert\|expect\|self\.assert\|pytest\.raises\|require\.\w+)\s*\(` plus `\.(toBe\|toEqual)\w*\s*\(` and the existing Go `t.(Error\|Fatal\|…)` forms. Do not weaken real detection. |           |      |
| TASK-010 | Confirm no other change to the red→deviation path, the untracked-file suppression scan, or the weak-added-test logic beyond the shared `_ASSERT` tightening. Verify `_scan_diff` still consumes the tightened `_ASSERT`.                                                                                                                       |           |      |
| TASK-011 | Add gaming tests in `engine/tests/`: (1) a diff that only appends `.3powers/ledger.jsonl` yields zero findings; (2) a removed/reordered testing-import line (`import { beforeEach, describe, expect, it, vi }`) yields no "assertion removed"; (3) a genuinely deleted `expect(...)` (net loss per file) still fails; (4) an added `eslint-disable` still fails. |           |      |

### Phase 3

- GOAL-003: Track C — add an auditable, expiring `advisories:` allowlist to `dependency_scan` in
  `scan.yaml`, suppress matched non-expired advisories with a required reason, and report every accepted
  advisory in the gate output.

| Task     | Description                                                                                                                                                                                                                                                                                                                             | Completed | Date |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-012 | Add the `advisories:` schema under `dependency_scan` in both `.3powers/config/scan.yaml` and `engine/src/threepowers/scaffold/config/scan.yaml`: a list of `{ id, reason (required), until (optional ISO date) }` alongside the existing `ignore` path globs.                                                                              |           |      |
| TASK-013 | Update the `scan.yaml` "SECURITY — read before widening" comment in both files to cover advisory acceptance: reason required, expiry recommended, each acceptance reported, never silent. No internal ids (GUD-001).                                                                                                                       |           |      |
| TASK-014 | In `engine/src/threepowers/scanners.py`: add an `advisories` parameter (list of `{id, reason, until}`) to `dependency_scan(...)` (~284-327), threaded from the same `scan.yaml` loader that already supplies `ignore` (update the plumbing that calls the scanners).                                                                        |           |      |
| TASK-015 | In `engine/src/threepowers/scanners.py` at the finding-append site (~302-308): before appending a finding, drop it when `v.get("id")` matches an allowlisted advisory that has a non-empty reason and is not expired; count it into `excluded`. Reuse `deviations.parse_iso` semantics for `until`; expired or reason-less entries do NOT suppress (fail-closed). |           |      |
| TASK-016 | Surface accepted advisories through `_with_exclusion_report` so the gate output names each advisory id, its reason, and the count — exactly like path-glob exclusions today (SEC-001: never silent).                                                                                                                                        |           |      |
| TASK-017 | Update `docs/` (the gate/verdict reference and the `scan.yaml` reference under `docs/`) to document the advisory allowlist: id + required reason + optional expiry, and that each acceptance is reported. No internal ids (GUD-001).                                                                                                        |           |      |
| TASK-018 | Add scanner tests in `engine/tests/`: an allowlisted advisory with a reason suppresses and is reported; a no-reason or past-`until` entry does NOT suppress; an unrelated advisory still fails; the reported count/text is asserted.                                                                                                        |           |      |

### Phase 4

- GOAL-004: Track E — migrate the committed TypeScript e2e sample's `biome.json` to biome v2 (format-only
  posture) so it runs green under a modern biome and demonstrates the Track A split.

| Task     | Description                                                                                                                                                                                                                                                                                          | Completed | Date |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-019 | Rewrite `e2e/typescript-orders/project/biome.json` to biome v2: v2 `$schema`, drop `files.ignore`, `formatter.enabled: true` (keep the existing indent/quote style), `linter.enabled: false`, `assist.enabled: false`, `css.parser.tailwindDirectives: true`.                                          |           |      |
| TASK-020 | Verify `e2e/typescript-orders/project/package.json`'s `check` script and biome pin are consistent with the format-only posture and do not reintroduce double-lint under `./e2e/run.sh typescript --check` (move the `check` script to `biome format`/`biome lint` if needed, else leave as-is).        |           |      |
| TASK-021 | Do NOT edit worktree copies under `.claude/worktrees/**` (throwaway). Confirm only the committed sample file is changed.                                                                                                                                                                              |           |      |

### Phase 5

- GOAL-005: Track G — add an O(1) eager tail-integrity check before every `Ledger.append` by factoring a
  shared `verify_entry` helper out of `verify_ledger`, so a corrupted tail surfaces on the next ledger
  operation without any full-chain walk. (High-risk trust-spine phase — coverage ≥ 95%.)

| Task     | Description                                                                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-022 | In `engine/src/threepowers/verify.py`: factor the per-entry checks currently inline in `verify_ledger` (~99-130 — `seq`, `prev_hash` linkage, recomputed `entry_hash`, signature against active key) into a reusable `verify_entry(entry, expected_prev, candidates)` helper. Rewire `verify_ledger` to call it; results must be identical.            |           |      |
| TASK-023 | Add a specific `LedgerTamperError` exception (name the offending seq, point at `3pwr verify`). Place it where ledger exceptions live (co-locate with `Ledger` in `engine/src/threepowers/ledger.py` or the existing exceptions module — match the module conventions).                                                                                |           |      |
| TASK-024 | In `engine/src/threepowers/ledger.py` `Ledger.append` (~97-127): before writing the new entry, run `verify_entry` on the current last entry only (recompute `entry_hash`, verify Ed25519 signature). On failure raise `LedgerTamperError`; do not append. No-op on an empty/genesis ledger and on an intact tail. O(1): one hash + one verify, no full-chain walk. |           |      |
| TASK-025 | Update `docs/cli-reference.md` (and the trust/verify reference) to document that an append now refuses on a tampered ledger tail and points the user at `3pwr verify`. No internal ids (GUD-001).                                                                                                                                                      |           |      |
| TASK-026 | Add tests in `engine/tests/test_ledger.py`: a hand-edited last entry makes the next `append` raise `LedgerTamperError` naming the seq; an intact ledger appends a byte-identical entry; `verify_entry` and `verify_ledger` agree on the same fixtures (parity); a middle-entry tamper is NOT caught by `append` but IS caught by `verify_ledger` (scope boundary); include a benchmark note asserting no full-chain walk. Keep trust-spine coverage ≥ 95%. |           |      |

### Phase 6

- GOAL-006: Track F — make deviations work end-to-end: fix the naive/aware `datetime` crash, factor a
  shared coverage helper so `run` honours active deviations at Verify exactly as `advance` does, annotate
  every waived gate, and require a non-empty reason on new deviations. (High-risk-adjacent: touches
  `deviations.py`, `cli/run.py`, `cli/trust.py`, `cli/exceptions.py`, `orchestrate.py`.)

| Task     | Description                                                                                                                                                                                                                                                                                                                                     | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-027 | F1: In `engine/src/threepowers/deviations.py` `parse_iso` (~59-66): after `datetime.fromisoformat(...)`, if the result's `tzinfo is None`, attach `timezone.utc`; still return `None` on a malformed/absent value (fail-safe: never expires). This fixes `active_deviations` (~118) and `overdue_emergencies` (~162) comparisons.                  |           |      |
| TASK-028 | F2: Add a shared helper in `engine/src/threepowers/deviations.py`, e.g. `uncovered_red_gates(verdict_payload, active, spec_id)`, that reproduces the exact coverage/scope logic `advance` uses (`covered_gates` at ~124-132, scoped by spec id; global applies). Returns the set of red gates NOT covered by an active signed deviation.            |           |      |
| TASK-029 | F2: Refactor `engine/src/threepowers/cli/trust.py` `cmd_advance` coverage logic (~311-328) to call the new `uncovered_red_gates` helper — no behavioural change to `advance`. Confirm `advance`'s existing tests still pass (PAT-002, no drift).                                                                                                    |           |      |
| TASK-030 | F2: In `engine/src/threepowers/cli/run.py` `run_verdict` (~1096-1131): after the Verify verdict is produced/recorded, compute red gates and `uncovered_red_gates(...)` (scoped to the run's spec id). If empty, the run proceeds past Verify (pass-for-proceed) and records/surfaces which deviation seq(s) applied; if any gate is uncovered, stop at gate-red naming the uncovered gate(s). The ledger verdict stays honestly red (only the proceed decision consults deviations). |           |      |
| TASK-031 | F3: In `gate run` output (`engine/src/threepowers/cli/gate.py`) and where failure panels render (`engine/src/threepowers/orchestrate.py`), when a failed gate is covered by an active deviation append `↳ waived by active deviation seq=N (approver: <who>)`; for `run` emit `proceeding past <gate> under deviation seq=N`. The lookup is read-only over the ledger and must not alter the verdict dict, ledger entry, or `--json`. |           |      |
| TASK-032 | F4: In `engine/src/threepowers/cli/exceptions.py` `cmd_deviation` (non-revoke path): reject an empty/whitespace `--note` with an actionable error ("a deviation must state a reason — pass `--note \"<why>\"`"), mirroring the existing `--approver` requirement (~71). Revoke entries unaffected; existing empty-reason ledger entries stay honoured (never rewrite the ledger). |           |      |
| TASK-033 | Update `docs/cli-reference.md` (and the gate/verdict + deviation reference): document that `3pwr run` (not only `advance`) honours an active deviation at Verify, that a deviation now requires a reason, and the waiver annotation. No internal ids (GUD-001).                                                                                     |           |      |
| TASK-034 | Add Track F tests: `engine/tests/test_deviations.py` — date-only `expires_at` parses aware and `active_deviations`/`overdue_emergencies` don't raise; `uncovered_red_gates` returns the right set for covered/partial/uncovered verdicts scoped by spec id. `run` tests — a red Verify fully covered proceeds (with applied-seq notice), a partially covered one stops. Renderer test — the waiver annotation appears only when covered and never mutates `--json`. `exceptions` test — empty-reason rejected, non-empty accepted. `advance` existing suite still green. |           |      |

### Phase 7

- GOAL-007: Track D — extend the per-gate failure panel with a data-driven, honest remediation block
  (what it means, safe auto-fix when one exists, a copy-pasteable coder hand-back prompt, and the
  `3pwr deviation` command as a labelled last resort). Human output only; the verdict, ledger, and
  `--json` payload are untouched. MUST land after Phases 1–6 (CON-003).

| Task     | Description                                                                                                                                                                                                                                                                                                                                       | Completed | Date |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------- | ---- |
| TASK-035 | In `engine/src/threepowers/orchestrate.py`: add a small static per-gate guidance data structure (keyed by gate name, with a sensible generic default for unknown gates) — one-line "what it means" plus the honest "fix" framing ("make the code satisfy it", never "make the check pass") for `format`, `lint`, `types`, `tests`, `gate_gaming`, `dependency_scan`. |           |      |
| TASK-036 | Extend `_panel_body_lines` (~754) so after findings and the existing `↳ auto-fix:` line it appends a remediation block resolved from `gate.details["remediation"]` (finding-specific hint, e.g. osv fixed version) if present, else the static guidance table. Keep it to a few lines; render via the existing `style.Styler` (rich panel on TTY, plain indent otherwise); suppress under `--json`; respect verbosity. |           |      |
| TASK-037 | Add a deterministic coder hand-back prompt helper (new small function, unit-tested for stable text) that names the failed gate(s) and their findings and instructs an honest fix. Wording is drawn from / consistent with `implement.agent.md` ("never weaken a gate; make the code satisfy the spec"); it MUST NOT contain any "suppress/delete/disable" instruction. Surface `3pwr run --resume --spec-id <id>` as the re-dispatch path. |           |      |
| TASK-038 | In the remediation block, print the `3pwr deviation --gate <failed-gate> --approver <you> --note "<why>" [--until <date>]` command under an explicit "last resort — only if this is a deliberate, justified exception" label, pre-filled with the failed gate. Confirm `gate_gaming` and `dependency_scan` are in the deviatable set (`GATE_ORDER` in `engine/src/threepowers/cli/exceptions.py`) so the command is valid as printed. |           |      |
| TASK-039 | Guarantee Track D is human output only: no change to `Verdict.to_dict()`, the ledger, or the `--json` payload. Guidance for `dependency_scan` names the new `scan.yaml` advisory allowlist (Phase 3); guidance for `gate_gaming`/`dependency_scan` truthfully states a recorded deviation is honoured by `run`/`advance` (true after Phase 6). |           |      |
| TASK-040 | Update `docs/` (the gate/verdict reference) to describe the remediation surface: guidance, auto-fix, coder hand-back prompt, and the deviation last resort. No internal ids (GUD-001).                                                                                                                                                             |           |      |
| TASK-041 | Add Track D tests: per-gate remediation block presence (a passing run shows none); `format`/`lint` still show the auto-fix command; `types`/`tests`/`gate_gaming`/`dependency_scan` show code-fix guidance + coder hand-back prompt + labelled deviation last resort; snapshot test for stable OSS-ready wording; the coder hand-back prompt never contains a suppress/delete/disable instruction; a `--json` byte-stability regression test proving the payload is identical to before Track D. |           |      |

### Phase 8

- GOAL-008: Verification — prove all seven tracks' acceptance criteria pass, the engine is green under its
  own toolchain and gates (including its own `gate_gaming` and High-risk coverage floors), the e2e sample
  runs green, no internal ids leak, and `--json`/ledger determinism is preserved.

| Task     | Description                                                                                                                                                                                                                                                                                                          | Completed | Date |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------- | ---- |
| TASK-042 | Run `cd engine && uv run pytest` — all new and existing tests pass, including the new Track A/B/C/D/F/G suites and the `--json` byte-stability regressions.                                                                                                                                                            |           |      |
| TASK-043 | Run `cd engine && uv run ruff check .` and `cd engine && uv run mypy src` — clean.                                                                                                                                                                                                                                    |           |      |
| TASK-044 | Run `3pwr gate run --path engine` — the engine stays green under its own gates, including its own `gate_gaming` after the `.3powers/` exclusion (GUD-002).                                                                                                                                                             |           |      |
| TASK-045 | Confirm `engine/tests/test_oss_readiness.py` passes — no internal plan/spec/requirement ids in any new user-facing string; format teaching uses bare `FR-###`/`DEMO-FR-###` (GUD-001).                                                                                                                                 |           |      |
| TASK-046 | Run `./e2e/run.sh typescript --check` — the sample's `format`/`lint` gates run green under biome v2 and the sample `biome.json` parses (Track E acceptance).                                                                                                                                                            |           |      |
| TASK-047 | Confirm High-risk coverage ≥ 95% for `canonical`, `keys`, `ledger`, `verify` after the Track G refactor (via `diff_coverage`/coverage report in the engine gate run).                                                                                                                                                  |           |      |
| TASK-048 | Manual/scenario verification of the live-run defects: a deviation with `--until 2026-10-01` no longer crashes `3pwr run`/`gate run`/`advance`; an active deviation covering `dependency_scan`+`gate_gaming` lets `3pwr run --resume` proceed past Verify with the applied-seq notice; a hand-edited last ledger entry makes the next append raise `LedgerTamperError`. |           |      |

## 3. Alternatives

- **ALT-001**: Scaffold a `biome.json` into user projects (Track A). Rejected (Decision 2, user-confirmed):
  `biome format` is correct with or without a project config and detection already honours a project's own
  config; 3Powers must not impose style config on a user's repo. Fix sample + command only.
- **ALT-002**: Accept a real dependency vulnerability via a broad path glob or a bare deviation (Track C).
  Rejected (Decision 3, user-confirmed): a path glob is too broad and a deviation is not vuln-specific; an
  `advisories:` allowlist is scoped to one advisory, committed, expiring, and auditable.
- **ALT-003**: Auto-fix `gate_gaming`/`dependency_scan`. Rejected (out of scope, by design): a gaming
  signal must never be silently erasable; the only paths to green are an honest fix or a signed deviation.
  Track D makes those paths legible, it does not add a bypass.
- **ALT-004**: Full-chain re-verify on every `append` (Track G). Rejected (Decision 16, user-confirmed):
  O(n) per append (O(n²) per run); tail-only is O(1) and catches the common case; full-chain stays at
  `verify`/`advance`.
- **ALT-005**: Duplicate the deviation coverage decision in `run` and `advance` (Track F). Rejected: two
  copies could diverge; a single shared `uncovered_red_gates` helper is used by both (PAT-002).
- **ALT-006**: Add the remediation guidance to the `--json`/verdict payload (Track D). Rejected: would
  break `--json` byte-stability and the deterministic verdict (CON-001); guidance is presentational only.

## 4. Dependencies

- **DEP-001**: `biome` v2 CLI (`@biomejs/biome`) providing `biome format` and `biome lint` subcommands and
  the v2 config schema (`includes`, `css.parser.tailwindDirectives`).
- **DEP-002**: The existing `scan.yaml` loader plumbing that supplies `ignore` to the scanners (Track C
  threads `advisories` through the same path).
- **DEP-003**: `engine/src/threepowers/deviations.py` `parse_iso`, `active_deviations`, `covered_gates`
  (Track C reuses `parse_iso`; Track F extends these).
- **DEP-004**: The trust-spine `verify_ledger` per-entry logic in `engine/src/threepowers/verify.py`
  (Track G factors `verify_entry` out of it) and `canonical`/`keys` for hash + signature.
- **DEP-005**: `implement.agent.md` wording ("never weaken a gate; make the code satisfy the spec") — the
  source of the Track D coder hand-back prompt phrasing.
- **DEP-006**: The `3pwr` CLI installed from `./engine` and the e2e harness (`./e2e/run.sh typescript
  --check`) for verification.
- **DEP-007**: `engine/tests/test_oss_readiness.py` (must pass for all new user-facing text).

## 5. Files

- **FILE-001**: `engine/src/threepowers/scaffold/adapters/typescript/adapter.yaml` — biome `format`/`lint`
  commands split to format-only/lint-only; header comment updated (Track A).
- **FILE-002**: `engine/src/threepowers/adapters.py` — biome `format` (~236) and `lint` (~262)
  `DETECT_RULES` specs updated (Track A).
- **FILE-003**: `engine/src/threepowers/gaming.py` — `_diff` `.3powers/**` exclusion, `_scan_untracked`
  skip, tightened `_ASSERT` (Track B).
- **FILE-004**: `.3powers/config/scan.yaml` and `engine/src/threepowers/scaffold/config/scan.yaml` —
  `advisories:` schema + SECURITY comment (Track C).
- **FILE-005**: `engine/src/threepowers/scanners.py` — `dependency_scan` `advisories` param + filter
  (~302-308) + `_with_exclusion_report` reporting (Track C).
- **FILE-006**: `e2e/typescript-orders/project/biome.json` — rewritten to biome v2 (Track E).
- **FILE-007**: `e2e/typescript-orders/project/package.json` — `check` script/biome pin verified (Track E).
- **FILE-008**: `engine/src/threepowers/verify.py` — new `verify_entry` helper; `verify_ledger` rewired
  (Track G).
- **FILE-009**: `engine/src/threepowers/ledger.py` — `Ledger.append` tail check + `LedgerTamperError`
  (Track G).
- **FILE-010**: `engine/src/threepowers/deviations.py` — `parse_iso` tz-normalization + new
  `uncovered_red_gates` shared helper (Track F).
- **FILE-011**: `engine/src/threepowers/cli/run.py` — `run_verdict` honours active deviations at Verify
  (Track F).
- **FILE-012**: `engine/src/threepowers/cli/trust.py` — `cmd_advance` coverage logic refactored onto the
  shared helper (Track F).
- **FILE-013**: `engine/src/threepowers/cli/exceptions.py` — `cmd_deviation` requires a non-empty reason
  (Track F).
- **FILE-014**: `engine/src/threepowers/cli/gate.py` — waiver annotation in `gate run` output (Track F).
- **FILE-015**: `engine/src/threepowers/orchestrate.py` — `_panel_body_lines` remediation block, static
  guidance table, coder hand-back prompt helper, waiver annotation (Tracks D + F).
- **FILE-016**: `docs/cli-reference.md` and the `docs/` gate/verdict + scan.yaml references — updated for
  every behaviour change in the same unit of work.
- **FILE-017**: `engine/tests/test_adapters.py`, `engine/tests/test_deviations.py`,
  `engine/tests/test_ledger.py`, the gaming/scanner/renderer tests under `engine/tests/`, and the `--json`
  byte-stability + OSS-readiness suites — new/extended tests.

## 6. Testing

- **TEST-001** (Track A): `engine/tests/test_adapters.py` asserts the biome `DETECT_RULES` format-only /
  lint-only commands; an ESLint-configured fixture resolves `format`→`biome format`, `lint`→`eslint`; a
  biome-only fixture resolves `lint`→`biome lint`.
- **TEST-002** (Track B): a diff appending only `.3powers/ledger.jsonl` yields zero findings; a
  removed/reordered testing-import line yields no "assertion removed"; a deleted `expect(...)` (net loss)
  still fails; an added `eslint-disable` still fails.
- **TEST-003** (Track C): an allowlisted advisory with a reason suppresses and is reported; a no-reason or
  past-`until` entry does not suppress; an unrelated advisory still fails.
- **TEST-004** (Track D): per-gate remediation block presence (none on a passing run); auto-fix shown for
  `format`/`lint`; code-fix guidance + coder hand-back prompt + labelled deviation for
  `types`/`tests`/`gate_gaming`/`dependency_scan`; snapshot for stable OSS-ready wording; the coder
  hand-back prompt never contains suppress/delete/disable; `--json` byte-identical to before Track D.
- **TEST-005** (Track E): `./e2e/run.sh typescript --check` green; the sample `biome.json` parses under
  biome v2.
- **TEST-006** (Track F): date-only `expires_at` parses aware and `active_deviations`/`overdue_emergencies`
  do not raise; `uncovered_red_gates` correct for covered/partial/uncovered scoped by spec id; `advance`
  existing suite green after refactor; a fully-covered red Verify proceeds in `run` with the applied-seq
  notice, a partially-covered one stops; the waiver annotation appears only when covered and never mutates
  `--json`; empty-reason deviation rejected, non-empty accepted.
- **TEST-007** (Track G): a hand-edited last entry makes the next `append` raise `LedgerTamperError` naming
  the seq; an intact ledger appends a byte-identical entry; `verify_entry`/`verify_ledger` parity on shared
  fixtures; a middle-entry tamper is not caught by append but is caught by `verify_ledger`; benchmark note
  asserts no full-chain walk; trust-spine coverage ≥ 95%.
- **TEST-008** (whole engine): `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (self-application, incl. the engine's own `gate_gaming`), and
  `engine/tests/test_oss_readiness.py` green.

## 7. Risks & Assumptions

- **RISK-001**: `git diff` `:(exclude).3powers/**` magic pathspec may behave differently when `target` is
  the repo root vs a subdir. Mitigation: test both; fall back to filtering `+++ b/` header prefixes.
- **RISK-002**: Over-tightening `_ASSERT` could miss a real removed assertion. Mitigation: regression tests
  built from the live-run findings (`toHaveClass`, `toHaveBeenCalledTimes`, `toBeGreaterThanOrEqual`, bare
  `expect(`); keep language-aware Go/pytest forms.
- **RISK-003**: `biome lint` uses recommended rules by default; a project using ESLint would still see
  noise if detection picks biome for `lint`. Mitigation: detection precedence already prefers a project's
  ESLint config; document that a biome-linting project opts in via its own `biome.json`.
- **RISK-004**: Track D remediation text could drift toward teaching gaming ("make the check pass").
  Mitigation: snapshot tests assert honest framing; OSS-readiness test guards ids.
- **RISK-005**: `--json` regressions from Tracks C/D/F. Mitigation: additive fields only; byte-stability
  test guards the payload.
- **RISK-006**: `run`/`advance` deviation logic could diverge. Mitigation: one shared
  `uncovered_red_gates` helper covered directly; both call sites consume it.
- **RISK-007**: A deviation could silently mask a real regression in `run`. Mitigation: mandatory,
  tested applied-seq notice + "waived by …" annotation; the recorded verdict stays red; deviations stay
  signed, revocable, and (when set) expiring.
- **RISK-008**: A bug in the Track G tail check could refuse a valid append and wedge the trust spine.
  Mitigation: reuse the exact `verify_entry` logic `verify_ledger` trusts (no second implementation), no-op
  on empty/genesis, and a parity test; O(1) with a benchmark asserting no full-chain walk.
- **ASSUMPTION-001**: The line references in the source plan (adapters.py ~236-281, gaming.py 24/32-35,
  scanners.py 284-327/302-308, orchestrate.py 754/806, deviations.py 59-66/97-132/162, run.py
  1096-1131/1529, trust.py 285-/311-328, ledger.py 97-127, verify.py 99-130) are accurate at
  implementation time; the python-engineer agent re-anchors to the current source before editing.
- **ASSUMPTION-002**: `gate_gaming` and `dependency_scan` are already in the deviatable `GATE_ORDER` set
  in `engine/src/threepowers/cli/exceptions.py`, so the Track D pre-filled `3pwr deviation` command is
  valid as printed (Decision, Track D).
- **ASSUMPTION-003**: The three structural forks (Decisions 1–3) were confirmed by the user on 2026-07-08;
  no open questions remain in the source plan.

## 8. Related Specifications / Further Reading

- `plan/035-actionable-verdict-remediation.md` — the source plan this implementation plan derives from.
- `AGENTS.md` — the mandatory intent → plan → implementation plan → implementation workflow, branch/commit
  discipline, python-engineer routing, and open-source-readiness rules.
- `CLAUDE.md` — architecture deep-dive (eight-stage lifecycle, three pillars, trust spine, adapter model).
- `docs/cli-reference.md` — the public `3pwr` command surface (gate runs, deviations, verify, run).
- `docs/STATUS.md` — the single source of truth for implementation status.
- `engine/tests/test_oss_readiness.py` — the enforced open-source-readiness rule for user-facing text.
- `e2e/README.md` — the notebook-project e2e harness and `./e2e/run.sh` usage.
