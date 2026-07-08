---
goal: De-cruft internal requirement-ID citations from all public text and split cli.py into a package (plan 031)
version: 1.0
date_created: 2026-07-06
last_updated: 2026-07-06
owner: 3Powers maintainers
status: 'Completed'
tags: [refactor, cli, docs, oss-readiness, hygiene]
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-brightgreen)

This implementation plan executes [plan/031-public-text-decruft-and-cli-split.md](031-public-text-decruft-and-cli-split.md).
It delivers four tracks in two delivery units on branch `feat/031-public-text-decruft-and-cli-split`
(cut from `main` only after plan 030's branch merges — see CON-001):

- **Delivery unit 1** (Phases 1–7): Track A inventory scanner, Track B rewrite passes B1–B5, and
  Track C durable convention + permanent enforcement test. The unit is self-verifying: the
  enforcement test lands last and proves the rewrite is complete; the disposable scanner and
  inventory are deleted in the unit's closing commit.
- **Delivery unit 2** (Phases 8–9): Track D — the mechanical split of `engine/src/threepowers/cli.py`
  into a `threepowers/cli/` package on already-clean text, plus final verification and docs truth-up.

Every task traces to a track/pass in plan 031 (noted as `[A]`, `[B1]`–`[B5]`, `[C1]`/`[C2]`, `[D]`).
All decisions in plan 031's "Decisions recorded" table are confirmed and are not re-opened here.

## 1. Requirements & Constraints

Requirements (from plan 031 tracks):

- **REQ-001** (A): A disposable, stdlib-only scanner `plan/scratch/scan_public_ids.py` walks the public surfaces (`engine/src/threepowers/**/*.py` including `scaffold/**` assets; `docs/**` minus `STATUS.md`; `README.md`; `CONTRIBUTING.md`; `GOVERNANCE.md`; `CHANGELOG.md`; `.3powers/**` seeded copies — `README.md`, `memory/constitution.md`, `templates/**`, `agents/*.yaml`, `config/*.yaml`, `adapters/**`; `.github/**` non-agent files), matches `\b([A-Z][A-Z0-9]{2,}-)?(FR|NFR)-[0-9]{2,3}\b` plus `\(epic [A-Z][0-9]\)` and `\((plan|spec) [0-9]{3}\)`, classifies each hit (`help-string`, `echoed-message`, `docstring`, `comment`, `doc-prose`, `scaffold-asset`, `format-example`), and emits `plan/scratch/031-id-inventory.md` with per-file tables (line / kind / matched text / excerpt) plus per-kind and per-namespace summary counts.
- **REQ-002** (B): Every must-go inventory entry is resolved: where the citation carried meaning, it is rewritten as plain-English rationale; where it carried none, it is deleted. This applies equally to requirement IDs (`XYZ-FR-###`/`XYZ-NFR-###`) and the sibling forms `(plan NNN)`, `(spec NNN)`, `(epic X#)` (confirmed decision 7).
- **REQ-003** (B3): ALL of `engine/src/threepowers/` is cleaned, docstrings and inline comments included (confirmed decision 1). Rewrites convert the ID citation into the rationale it stood for; **every public module/class/function keeps (or gains) a docstring — this pass rewrites, never deletes**. `engine/tests/**` is untouched.
- **REQ-004** (B4/C): Format-teaching text is preserved: bare `FR-###`/`NFR-###` stays legal (it is how scaffold templates instruct end users to number their own requirements), and doc examples showing the full namespaced format use the reserved `DEMO-` example namespace (e.g. `DEMO-FR-001`) or explicit placeholder forms (`<SPECID>-FR-###`).
- **REQ-005** (B5): Scaffold assets and the repo's own `.3powers/` seeded twins are edited in lockstep (same commit per file pair) per the pairing table in Phase 6; a fresh `3pwr init` in a scratch directory must ship no internal IDs.
- **REQ-006** (C1): The convention is written down: the "Conventions" section of `AGENTS.md` gains the rule (internal requirement IDs, epic letters, and plan/spec numbers live only in `specs/`, `plan/`, engine tests' `Covers:` lines, commit messages, `docs/STATUS.md`, `AGENTS.md`/`CLAUDE.md` — never in end-user-readable text: CLI help and messages, engine source docstrings and comments, `docs/` prose, or scaffold assets shipped by `3pwr init`; format teaching uses `DEMO-FR-###` or bare `FR-###`), with a mirror note in `CLAUDE.md`'s "Working in this repo".
- **REQ-007** (C2): `engine/tests/test_oss_readiness.py` gains a permanent enforcement section: scan surfaces `docs/**` minus `STATUS.md`, `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`, and `engine/src/threepowers/**` (source and scaffold assets; `engine/tests/` excluded by construction); pattern is the namespaced form only — `\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b` — plus `\(epic [A-Z][0-9]\)`; allowlist is a short frozen set (`DEMO-` namespace plus explicit placeholder forms) with a comment pointing at the AGENTS.md rule; failure message names file, line, matched token, and the one-line rule; the scan is file-based (hermetic — no spawning `3pwr --help`).
- **REQ-008** (D): `engine/src/threepowers/cli.py` becomes the package `engine/src/threepowers/cli/` per the module map in Phase 8: each command module owns its `cmd_*` functions and registers its own subparsers via a `register(sub, common)` hook with `set_defaults(func=…)`; `cli/__init__.py` assembles the parser as a short loop over the modules in the current registration order (preserving `3pwr --help` command order byte-for-byte) and re-exports the public surface (`main`, `build_parser`, and every `cmd_*`/helper that `engine/tests/` imports from `threepowers.cli` today); the `[project.scripts]` target `threepowers.cli:main` in `engine/pyproject.toml` keeps working with **zero pyproject change**; `cli.py` is deleted in the same commit.
- **REQ-009** (D): The split is a pure refactor: identical behavior, identical (post-Track-B) help text, identical exit codes and `--json` payloads, verified by diffing captured `--help` output before/after and by the unmodified test suite.
- **REQ-010** (A): Scanner and inventory are disposable: `plan/scratch/scan_public_ids.py` and `plan/scratch/031-id-inventory.md` are deleted in the closing commit of delivery unit 1 (their regex and surface list live on inside the permanent test).

Security:

- **SEC-001**: The scanner is read-only and never modifies files; `.3powers/ledger.jsonl`, `.3powers/verdicts/`, and `.3powers/runs/` are never edited by any task (machine/trust artifacts).
- **SEC-002**: The `spec_conformance` gate's inputs are untouched — `engine/tests/**` `Covers:` declarations (parsed by `engine/src/threepowers/conformance.py`) are out of scope entirely; anti-gaming binding depends on them.

Constraints:

- **CON-001** (hard sequencing precondition): **No implementation work starts until `feat/030-run-identity-gates-ux` has merged to `main`.** At that point the branch `feat/031-public-text-decruft-and-cli-split` is cut fresh from the new `main`, and the two plan files (`plan/031-public-text-decruft-and-cli-split.md` and this file) are committed there. Track A's authoritative inventory run happens against post-030 `main` (030 adds new user-visible text and new spec namespaces RUNID/GDIAG/GATECFG/GATEPIPE/PROGFILE/PHASEPR/TRIX that must be swept too). TASK-001 is the gate; no later task may execute before it completes.
- **CON-002**: No pull requests anywhere — branch-only delivery per AGENTS.md/CLAUDE.md, as two sequential delivery units on the one feature branch (unit 1 = Phases 1–7, unit 2 = Phases 8–9; confirmed decision 7).
- **CON-003**: The engine stays green after every phase: `(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)` and `3pwr gate run --path engine` (self-application). Trust-spine coverage (canonical, keys, ledger, verify, speclock, anchor) stays ≥95%; the `[tool.mutmut]` scope in `engine/pyproject.toml` is neither widened nor narrowed.
- **CON-004**: Tests asserting exact help/message strings are updated **in the same commit** as each text change — never batched separately — so every commit is green.
- **CON-005**: All engine Python changes (Phases 2–4, 7 test code, 8) are executed by the python-engineer agent role (AGENTS.md).
- **CON-006** (exemption list, verbatim from plan 031 — never stripped): `specs/`, `plan/`, engine tests' `Covers:` declarations (the spec_conformance gate parses them), `.3powers/ledger.jsonl` + `verdicts/`, `docs/STATUS.md`, `AGENTS.md`, `CLAUDE.md`, memory files. Legitimate format teaching keeps bare `FR-###`/`NFR-###` and the reserved `DEMO-` namespace.
- **CON-007**: `cli/run.py` may remain at ~1,900 lines (confirmed decision 5); no module other than `cli.py` is split in this plan (confirmed decision 6 — `runner.py`, `gates.py`, `oracle.py`, `orchestrate.py` are future candidates only).
- **CON-008**: Tasks in this plan are anchored to symbols, subcommand names, regexes, and the Track A inventory — **never to line numbers of files plan 030 is rewriting**. `plan/scratch/031-id-inventory.md` is the authoritative worklist for every Track B task; where this plan and the inventory disagree on a hit's location, the inventory wins.

Guidelines & patterns:

- **GUD-001**: Rewrite, never delete: every touched docstring keeps or gains a plain-English sentence; module doc headers survive.
- **GUD-002**: Help text stays next to the implementation it describes — Track D moves each subparser's `help=`/`description=` strings into the module owning the `cmd_*` function, so Track B's cleaned strings migrate exactly once.
- **PAT-001**: `register(sub, common)` hook pattern for every `cli/` command module; `__init__.py` owns only assembly, ordering, and re-exports.
- **PAT-002**: The permanent test reuses `test_oss_readiness.py`'s existing repo-root-relative discovery and skip-when-absent pattern (so it still passes under mutmut's copied layout).

## 2. Implementation Steps

### Phase 1

- GOAL-001: [A] Sequencing gate satisfied, feature branch cut, the disposable scanner built and its authoritative inventory emitted, and the two new specs (PUBTXT, CLIPKG) authored. Completion criteria: `plan/scratch/031-id-inventory.md` exists with a per-namespace census whose engine total roughly matches the raw grep census (~1,100 on pre-030 `main`, higher after 030), and both specs exist under `specs/`.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | **Sequencing gate (CON-001).** Verify `feat/030-run-identity-gates-ux` has merged to `main` (e.g. `git log main --oneline` shows plan 030's final commits and `git branch --merged main` lists the 030 branch). If not merged: STOP — no further task may run. If merged: cut `feat/031-public-text-decruft-and-cli-split` fresh from `main`, then commit `plan/031-public-text-decruft-and-cli-split.md` and `plan/IMPLEMENTATION-002-refactor-public-text-decruft-and-cli-split.md` on it. | ✅ | 2026-07-07 |
| TASK-002 | [A] Write `plan/scratch/scan_public_ids.py` (stdlib only, no engine imports): walk the surfaces in REQ-001, exclude the CON-006 exemptions; match `\b([A-Z][A-Z0-9]{2,}-)?(FR|NFR)-[0-9]{2,3}\b` plus `\(epic [A-Z][0-9]\)` and `\((plan|spec) [0-9]{3}\)`; classify each hit as `help-string` (inside argparse `help=`/`description=`), `echoed-message` (inside a print/styler/notify call), `docstring`, `comment`, `doc-prose`, `scaffold-asset`, or `format-example` (bare `FR-###`/`NFR-###` or `<SPECID>-` placeholder forms). Classification is heuristic; a human reviews it during Track B. No tests (disposable, never shipped). | ✅ | 2026-07-07 |
| TASK-003 | [A] Run the scanner against the post-030 branch; emit `plan/scratch/031-id-inventory.md` — one table per file (columns: line / kind / matched text / surrounding excerpt) plus summary counts per kind and per namespace (the namespace census confirms `DEMO-` is unused and seeds the allowlist). Sanity check: the total over `engine/src/threepowers/` must roughly match plan 031's raw grep census (~1,100 pre-030; expect more, including the RUNID/GDIAG/GATECFG/GATEPIPE/PROGFILE/PHASEPR/TRIX namespaces) — a large shortfall means the walker has a hole; fix before proceeding. Commit scanner + inventory. | ✅ | 2026-07-07 |
| TASK-004 | Author `specs/<NNN>-public-text-hygiene/spec.md` (spec ID `PUBTXT`), where `<NNN>` is the next free workspace number under `specs/` at implementation time (plan 030's branch allocates 020–026, so expect 027 — confirm by listing `specs/`). Contents per plan 031's "Spec files to create": the no-internal-IDs rule, the scanned surface list, the CON-006 exemptions, the `DEMO-`/placeholder allowlist, and the enforcement-test requirements (Tracks A–C), as FR-### items. | ✅ | 2026-07-07 |
| TASK-005 | Author `specs/<NNN+1>-cli-package-split/spec.md` (spec ID `CLIPKG`): Track D's module map, the `register(sub, common)` pattern, the behavior-identity invariants (identical help text, exit codes, `--json` payloads, subcommand order) and the entry-point invariant (`threepowers.cli:main` unchanged, zero `pyproject.toml` edit), as FR-### items. Commit both specs. | ✅ | 2026-07-07 |
Validation: `python plan/scratch/scan_public_ids.py` exits 0 and the inventory census passes the ~1,100+ sanity check; `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green (no engine change yet).

### Phase 2

- GOAL-002: [B1] `cli.py` help strings and echoed messages are clean — the highest-value pass and a prerequisite for Track D. Completion criteria: zero must-go inventory entries of kind `help-string` or `echoed-message` remain in `engine/src/threepowers/cli.py`, and `3pwr --help` output contains no namespaced internal IDs.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-006 | [B1] Working strictly from the `cli.py` sections of `plan/scratch/031-id-inventory.md` (kind `help-string`): rewrite or delete every namespaced ID and `(plan NNN)`/`(spec NNN)`/`(epic X#)` citation in argparse `help=`/`description=` strings. Apply plan 031's target transformations — e.g. `"…latest local anchor tag (HARDN-FR-005)"` → `"…latest local anchor tag"` (ID carried nothing); `"per-stage dispatch timeout in seconds (RUNLIVE-FR-004; default: configured, 1800)"` → `"per-stage dispatch timeout in seconds (default: the configured value, or 1800)"`. Update any test asserting the exact string in the same commit (CON-004). | ✅ | 2026-07-07 |
| TASK-007 | [B1] Same treatment for inventory kind `echoed-message` in `cli.py`: every print/styler/notify/checklist line. Anchor by the quoted message text from the inventory, not line numbers (CON-008). Update exact-string tests in the same commit (CON-004). | ✅ | 2026-07-07 |
| TASK-008 | [B1] Verify the pass: re-run the scanner and confirm zero must-go `help-string`/`echoed-message` entries remain for `cli.py`; smoke `uv tool install --force ./engine && 3pwr --help`, `3pwr verify --help`, `3pwr run --help` show no internal IDs; run the full engine check suite and `3pwr gate run --path engine`. Commit. | ✅ | 2026-07-07 |
Validation: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine` green; `3pwr --help | grep -E '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b'` finds nothing.

### Phase 3

- GOAL-003: [B2] User-visible strings (errors, warnings, hints — raised or printed) in every other engine module are clean. Completion criteria: zero must-go inventory entries of kind `echoed-message` (or message-bearing `help-string`) remain outside `cli.py` under `engine/src/threepowers/`.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-009 | [B2] First batch, ordered by the inventory census: rewrite/delete must-go user-visible strings in `engine/src/threepowers/runner.py`, `orchestrate.py`, `gates.py`, `oracle.py`. Same rewrite rules as Phase 2; exact-string test updates in the same commit (CON-004). | ✅ | 2026-07-07 |
| TASK-010 | [B2] Second batch: `engine/src/threepowers/gitflow.py`, `scaffold.py`, `runpreflight.py`, `steering.py`, and every remaining module the inventory census lists with `echoed-message` hits (including any module plan 030 added, e.g. `progress.py`). Same rules; same-commit test updates (CON-004). | ✅ | 2026-07-07 |
| TASK-011 | [B2] Verify: re-run the scanner — zero must-go string entries remain under `engine/src/threepowers/` outside docstrings/comments; full engine checks + `3pwr gate run --path engine` green. Commit. | ✅ | 2026-07-07 |
Validation: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine` green; scanner shows 0 remaining `echoed-message` must-go entries in engine source.

### Phase 4

- GOAL-004: [B3] Engine docstrings and inline comments are clean across all of `engine/src/threepowers/` (confirmed decision 1) — rewritten into plain-English rationale, never deleted. `engine/tests/**` untouched. Completion criteria: zero must-go inventory entries of kind `docstring` or `comment` remain under `engine/src/threepowers/`.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-012 | [B3] Working from the inventory kinds `docstring` and `comment`, module by module in census order: rewrite each ID citation into the rationale it stood for — e.g. `"""Rotate the ledger signer (HARDN-FR-004): the OUTGOING key signs its successor."""` → `"""Rotate the ledger signer: the OUTGOING key signs its successor, so the chain of custody is unbroken."""`. Rule: rewrite, never delete — every public module/class/function keeps (or gains) a docstring (GUD-001). `(plan NNN)`/`(epic X#)` comment citations are stripped on the same terms (confirmed decision 7). `engine/tests/**` untouched (SEC-002). | ✅ | 2026-07-07 |
| TASK-013 | [B3] Verify: re-run the scanner — zero must-go `docstring`/`comment` entries remain under `engine/src/threepowers/`; spot-check that no docstring was removed (ruff docstring/lint rules green); full engine checks + `3pwr gate run --path engine` green. Commit. | ✅ | 2026-07-07 |
Validation: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine` green; scanner shows 0 remaining `docstring`/`comment` must-go entries.

### Phase 5

- GOAL-005: [B4] Docs are clean (`docs/STATUS.md` untouched per CON-006), including root-level public files. Completion criteria: zero must-go `doc-prose` inventory entries remain outside the exemption list; every format-teaching example uses bare `FR-###` or the `DEMO-` namespace.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-014 | [B4] Clean the `docs/` files per the inventory (plan 031 census: `docs/cli-reference.md` ~14 hits, `docs/threat-model.md` ~11, `getting-started.md` ~3, `brownfield.md` ~3, `migration-remove-speckit.md` ~2, `engine-architecture.md` ~2, `troubleshooting.md` ~1, `concepts.md` ~1 — the post-030 inventory is authoritative). `docs/STATUS.md` untouched. Where a doc teaches the ID *format*, convert any real internal namespace in the example to `DEMO-` (e.g. `DEMO-FR-001`) or leave it bare `FR-###` (REQ-004). | ✅ | 2026-07-07 |
| TASK-015 | [B4] Clean root-level and CI-adjacent public files per the inventory: `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`, and `.github/**` non-agent files. `AGENTS.md`, `CLAUDE.md`, and memory files untouched (CON-006). | ✅ | 2026-07-07 |
| TASK-016 | [B4] Verify: re-run the scanner — zero must-go `doc-prose` entries remain; full engine checks green (docs changes cannot break them, but CON-003 holds per phase). Commit. | ✅ | 2026-07-07 |
Validation: scanner shows 0 remaining `doc-prose` must-go entries; `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green.

### Phase 6

- GOAL-006: [B5] Scaffold assets and the repo's own `.3powers/` seeded twins are clean, edited in lockstep, with the re-seal-or-deviation contingency handled. Completion criteria: a fresh `3pwr init` in a scratch directory ships zero internal IDs, and `3pwr verify` + `3pwr gate run --path engine` are green (with any re-seal or deviation recorded in the ledger).

Scaffold ↔ seeded-twin pairing table (each pair edited in the same commit; REQ-005):

| Scaffold source | Seeded twin under `.3powers/` |
|---|---|
| `engine/src/threepowers/scaffold/constitution.md` | `.3powers/memory/constitution.md` |
| `engine/src/threepowers/scaffold/agents/*.yaml` | `.3powers/agents/*.yaml` |
| `engine/src/threepowers/scaffold/config/*.yaml` | `.3powers/config/*.yaml` |
| `engine/src/threepowers/scaffold/templates/**` | `.3powers/templates/**` |
| `engine/src/threepowers/scaffold/adapters/CONTRACT.md` (+ adapter files) | `.3powers/adapters/**` |
| scaffold `README.md` seed (if present) | `.3powers/README.md` |

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-017 | [B5] Rewrite `engine/src/threepowers/scaffold/constitution.md` (~26 hits, cites `3PWR-FR-###` throughout) converting each citation into the plain rule it encodes — the constitution ships literally into end-user repos and must stand alone. Edit `.3powers/memory/constitution.md` byte-consistently in the same commit. Hold the commit until TASK-019 clears the gate check. | ✅ | 2026-07-07 |
| TASK-018 | [B5] Clean the remaining scaffold assets per the inventory — `scaffold/agents/*.yaml`, `scaffold/config/*.yaml`, `scaffold/templates/**` (agent prompt templates), `scaffold/adapters/CONTRACT.md` — each with its `.3powers/` seeded twin in the same commit per the pairing table above. Format-teaching lines in the spec template (instructing users to write `FR-001`, `FR-002`, …) stay bare (REQ-004). | ✅ | 2026-07-07 |
| TASK-019 | [B5] **Re-seal-or-deviation contingency (plan 031 risk 2).** Before landing the B5 commits: run `3pwr gate run --path engine` and `3pwr verify`. If `spec_integrity` or `gate_gaming` trips on the seeded/sealed asset edits: the preferred path is the documented maintainer re-seal (independent signing key via `THREEPOWERS_SIGNING_KEY_FILE`); the fallback is a signed recorded `3pwr deviation` naming this plan's constitution rewrite — the user decides at that point, and either outcome is recorded in the ledger (confirmed decision 4). | ✅ | 2026-07-07 |
| TASK-020 | [B5] Fresh-init check: `(cd "$(mktemp -d)" && git init -q . && 3pwr init --yes && grep -rE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' .3powers/)` — the grep must find nothing (after reinstalling: `uv tool install --force ./engine`). Re-run the scanner: zero must-go `scaffold-asset` entries remain. Commit; full engine checks green. | ✅ | 2026-07-07 |
Validation: `3pwr gate run --path engine` and `3pwr verify` green (re-seal/deviation recorded if tripped); fresh-init grep clean; `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green.

### Phase 7

- GOAL-007: [C1/C2] The convention is durable — written into `AGENTS.md`/`CLAUDE.md` and enforced by a permanent test — and the disposable scanner + inventory are deleted, closing delivery unit 1. Completion criteria: the new test section passes on the cleaned tree (and demonstrably fails on a seeded violation), and `plan/scratch/scan_public_ids.py` + `plan/scratch/031-id-inventory.md` no longer exist.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-021 | [C1] Extend the "Conventions" section of `AGENTS.md` with the rule, stated positively per plan 031: internal requirement IDs (`3PWR-FR-###` and friends), epic letters, and plan/spec numbers live in `specs/`, `plan/`, engine tests (`Covers:` lines), commit messages, `docs/STATUS.md`, and AGENTS.md itself — **never** in end-user-readable text (CLI help and messages, engine source docstrings and comments, `docs/` prose, scaffold assets shipped by `3pwr init`); docs teaching the ID format use the reserved `DEMO-FR-###` namespace or bare `FR-###`. Note that this composes with plan 022's de-jargon rule (users' own IDs stay in their artifacts). | ✅ | 2026-07-07 |
| TASK-022 | [C1] Add the mirror note to `CLAUDE.md`'s "Working in this repo" section (one small diff, pointing at the AGENTS.md rule). | ✅ | 2026-07-07 |
| TASK-023 | [C2] Extend `engine/tests/test_oss_readiness.py` with the permanent enforcement section per REQ-007: surfaces (`docs/**` minus `STATUS.md`, `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`, `engine/src/threepowers/**` source + scaffold), pattern `\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b` plus `\(epic [A-Z][0-9]\)` (bare `FR-###`/`NFR-###` allowed), frozen allowlist (`DEMO-` + placeholder forms like `<SPECID>-FR-###`) with a comment pointing at the AGENTS.md rule, actionable failure message (file, line, token, one-line rule), reusing the module's existing repo-root discovery and skip-when-absent guard (PAT-002). Add a `Covers:` line referencing the PUBTXT spec. Prove it red-capable: temporarily seed a violation in a scratch copy and confirm the assertion fires, then confirm green on the real tree. | ✅ | 2026-07-07 |
| TASK-024 | [A/C] Closing commit of delivery unit 1: delete `plan/scratch/scan_public_ids.py` and `plan/scratch/031-id-inventory.md` (REQ-010 — their regex and surface list now live in the permanent test). Run the full verification: engine checks, `3pwr gate run --path engine`, and confirm the new test section passes under mutmut's copied layout (skip-guard intact). | ✅ | 2026-07-07 |
Validation: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` and `3pwr gate run --path engine` green; new oss-readiness section green; scanner and inventory deleted.

### Phase 8

- GOAL-008: [D] `cli.py` is split into the `threepowers/cli/` package — pure code motion on already-clean text, identical behavior, zero `pyproject.toml` change. Completion criteria: full test suite green with zero-or-mechanical test edits, and per-command `--help` output byte-identical to the pre-split capture.

Target module map (confirmed decision 5/6; regroup by `cmd_*` names against post-030 `main` — do not rely on any line ranges):

| Module | Commands / contents |
|---|---|
| `cli/__init__.py` | `main()`, parser assembly (loop over each module's `register` in current registration order), re-exports (`main`, `build_parser`, `cmd_*`/helpers that `engine/tests/` imports) |
| `cli/_common.py` | shared helpers: `_settings`, `_resolve_spec`, `_print`, `_resolve_ui`, `_styler`, `_verbosity`, `_compose`, `_ask*`, `_format_verdict`, `_notify*`, exit codes |
| `cli/keys.py` | `keygen`, `rotate-key` |
| `cli/bootstrap.py` | `init` (+ layout/readiness/roles/notifications setup flows), `config roles setup`, `commit-stage` |
| `cli/gate.py` | `gate run`, `conformance`, `coverage-check`, `scope-check`, `classify` (+ post-030 gate subcommands, e.g. `gate config show`) |
| `cli/trust.py` | `verify`, `anchor`, `signoff`, `spec diff`, `advance`, `ledger show`, `revert` |
| `cli/exceptions.py` | `deviation`, `emergency` |
| `cli/oracle.py` | `roles-check`, `oracle seal/record/verify/dispatch` |
| `cli/observe.py` | `observe signal/coverage/log-action/verify-actions` |
| `cli/run.py` | `run` (+ the ~30 dispatch/phase/steering helpers), `status`, `git start`, `abort` — may stay ~1,900 lines (CON-007) |
| `cli/supply.py` | `provenance`, `deploy-gate`, `residual` |
| `cli/brownfield.py` | `characterize`, `eval`, `deps-check`, `ready` |

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-025 | [D] Pre-split capture: reinstall (`uv tool install --force ./engine`), then record `3pwr --help` and one `--help` per command group (every subcommand named in the module map) to files under the working scratch area for the post-split diff. Also record the list of names `engine/tests/` imports from `threepowers.cli` (grep `from threepowers.cli import` / `from threepowers import cli`) — this list defines the `__init__.py` re-export surface. | ✅ | 2026-07-07 |
| TASK-026 | [D] Create the package skeleton: `engine/src/threepowers/cli/_common.py` receives the shared helpers named in the module map (move by symbol name); `cli/__init__.py` gets the `main()`/`build_parser()` assembly shell. No behavior change; each moved symbol keeps its name. | ✅ | 2026-07-07 |
| TASK-027 | [D] Move the command modules per the module map: each module receives its `cmd_*` functions and private helpers, and exposes `register(sub, common)` adding its subparsers (help text moves with the implementation, GUD-002) with `set_defaults(func=…)`. `build_parser()` in `__init__.py` becomes a short loop over the modules in the existing registration order, preserving `3pwr --help` command order byte-for-byte (REQ-008). | ✅ | 2026-07-07 |
| TASK-028 | [D] Finalize: `__init__.py` re-exports the surface recorded in TASK-025 (default outcome: zero test edits; if any import breaks, fix mechanically — import path only); delete `engine/src/threepowers/cli.py` in the same commit; **no `engine/pyproject.toml` change** (`threepowers.cli:main` resolves to the package). Commit message maps each new module to its source content (git detects file-split renames poorly). An optional further `run.py`/`run_dispatch.py` split is noted for the implementer to decide against 030's final shape — not committed to here. | ✅ | 2026-07-07 |
| TASK-029 | [D] Post-split verification: full `(cd engine && uv run pytest)` green with no behavioral test changes; `uv run ruff check .` and `uv run mypy src` green (mypy newly sees package boundaries — fix any revealed type looseness minimally, not refactored); reinstall and diff every captured `--help` output against TASK-025's captures — byte-identical. | ✅ | 2026-07-07 |
Validation: `(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)` green; help-output diff empty; `3pwr --version` works after `uv tool install --force ./engine`.

### Phase 9

- GOAL-009: Final verification of both delivery units against plan 031's post-delivery checklist, plus docs truth-up. Completion criteria: all verification commands green; docs reflect the new package layout; this plan's status set to `Completed`.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-030 | Full self-application: `(cd engine && uv sync --extra dev && uv run pytest && uv run ruff check . && uv run mypy src)` then `3pwr gate run --path engine` with `--base main` as usual. Confirm trust-spine coverage ≥95% and the `[tool.mutmut]` scope unchanged (CON-003). If `diff_coverage` flags moved-but-uncovered legacy cli lines (the split makes the whole package "new" to a diff-based gate), surface it to the user for a deviation decision — do not silently add low-value tests (plan 031 risk 8). | ✅ | 2026-07-07 |
| TASK-031 | Install smoke: `uv tool install --force ./engine`; run `3pwr --version`, `3pwr --help`, one representative subcommand `--help` per `cli/` module, and a `3pwr verify` run in this repo — outputs compared against the pre-split captures; `3pwr --help \| grep -E '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b'` finds nothing. | ✅ | 2026-07-07 |
| TASK-032 | Fresh-init proof that the scaffold ships clean: `(cd "$(mktemp -d)" && git init -q . && 3pwr init --yes && grep -rE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' .3powers/)` — grep finds nothing. | ✅ | 2026-07-07 |
| TASK-033 | Docs truth-up: update `docs/engine-architecture.md` (and any other doc naming `cli.py` as a single module) to describe the `threepowers/cli/` package layout; confirm every behavior-visible change of this plan is reflected in `docs/` (open-source-ready wording — the new text must itself pass the Phase 7 enforcement test). Mark this implementation plan's task tables complete and set front-matter `status` to `Completed`. | ✅ | 2026-07-07 |
Validation: all Phase 9 commands green; the "Verification (post-delivery)" block in plan 031 passes end to end; branch ready for merge per AGENTS.md (no pull request).

## 3. Alternatives

- **ALT-001**: Clean only user-visible strings and leave docstrings/comments as internal traceability. Rejected (confirmed decision 1): the repo is public, so comments are public text; traceability survives in `specs/`, tests' `Covers:` lines, commit messages, and `docs/STATUS.md`; and "strings yes, comments no" is not mechanically checkable by the enforcement test.
- **ALT-002**: Enforce via a blocklist of known internal namespaces (3PWR, HARDN, CLIUX, …) instead of banning all namespaced IDs. Rejected (confirmed decision 4-scope): a blocklist rots as new specs are authored; the general namespaced ban with a `DEMO-` allowlist is future-proof and keeps format teaching legal.
- **ALT-003**: Put the scanner in `engine/` as a shipped tool. Rejected (confirmed decision 3): it is a throwaway; shipping it forces tests/typing/coverage for disposable code. `plan/` is already internal-only.
- **ALT-004**: Split `runner.py`/`gates.py`/`oracle.py`/`orchestrate.py` in the same plan. Rejected (confirmed decision 6): all are ≤ ~620 lines and maintainable; splitting buys churn, not clarity. Listed as future candidates only.
- **ALT-005**: Split `cli/run.py` further into `run.py`/`run_dispatch.py` now. Rejected (confirmed decision 5): ~1,900 lines is one coherent domain (the lifecycle loop); a further split is an optional follow-up the implementer may raise once 030's final shape is visible.
- **ALT-006**: One combined delivery unit for all four tracks. Rejected (confirmed decision 7): keeping D separate makes its diff reviewable as "moved, not changed".
- **ALT-007**: Start Track B/D in parallel with plan 030. Rejected: 030's remaining phases rewrite cli.py heavily (including the Rich terminal-UX refactor); parallel work guarantees severe conflicts (CON-001).

## 4. Dependencies

- **DEP-001**: `feat/030-run-identity-gates-ux` merged to `main` — hard precondition for every task (CON-001); the authoritative inventory and the Track D module regrouping both run against post-030 code.
- **DEP-002**: Existing engine toolchain per lockfiles: `uv`, `pytest`, `ruff`, `mypy` (`engine/uv.lock`). The scanner itself is stdlib-only Python with no engine imports.
- **DEP-003**: Independent signer key via `THREEPOWERS_SIGNING_KEY_FILE` — required for `3pwr verify`, any maintainer re-seal, or a recorded deviation in TASK-019.
- **DEP-004**: Intra-plan ordering: Phase 1 → Phases 2–6 (inventory feeds every Track B pass) → Phase 7 (enforcement test must go green against the cleaned tree) → Phase 8 (the split moves only clean text) → Phase 9.
- **DEP-005**: `plan/scratch/031-id-inventory.md` — the authoritative worklist for all Track B tasks (CON-008); exists only between Phase 1 and Phase 7.

## 5. Files

- **FILE-001**: `plan/scratch/scan_public_ids.py` — **new, disposable** inventory scanner (created Phase 1, deleted Phase 7).
- **FILE-002**: `plan/scratch/031-id-inventory.md` — **new, disposable** classified inventory (created Phase 1, deleted Phase 7).
- **FILE-003**: `specs/<NNN>-public-text-hygiene/spec.md` (PUBTXT) and `specs/<NNN+1>-cli-package-split/spec.md` (CLIPKG) — **new** specs; `<NNN>` allocated at implementation time (expected 027/028 after plan 030's 020–026).
- **FILE-004**: `engine/src/threepowers/cli.py` — B1 text rewrite (Phase 2), B3 docstrings/comments (Phase 4), then **deleted** in Phase 8 in favor of the package.
- **FILE-005**: `engine/src/threepowers/` — all other modules: B2 user-visible strings (Phase 3) and B3 docstrings/comments (Phase 4): `runner.py`, `orchestrate.py`, `gates.py`, `oracle.py`, `gitflow.py`, `scaffold.py`, `runpreflight.py`, `steering.py`, and the rest per the inventory census.
- **FILE-006**: `docs/cli-reference.md`, `docs/threat-model.md`, `docs/getting-started.md`, `docs/brownfield.md`, `docs/migration-remove-speckit.md`, `docs/engine-architecture.md`, `docs/troubleshooting.md`, `docs/concepts.md` — B4 (Phase 5); `docs/engine-architecture.md` again in Phase 9 (package layout). `docs/STATUS.md` untouched.
- **FILE-007**: `README.md`, `CONTRIBUTING.md`, `GOVERNANCE.md`, `CHANGELOG.md`, `.github/**` non-agent files — B4 (Phase 5).
- **FILE-008**: `engine/src/threepowers/scaffold/**` (constitution.md, agents/, config/, templates/, adapters/CONTRACT.md) and their `.3powers/` seeded twins (`memory/constitution.md`, `agents/`, `config/`, `templates/`, `adapters/`, `README.md`) — B5 in lockstep pairs (Phase 6).
- **FILE-009**: `AGENTS.md` (Conventions section) and `CLAUDE.md` (Working in this repo mirror note) — C1 (Phase 7).
- **FILE-010**: `engine/tests/test_oss_readiness.py` — C2 permanent enforcement section with `Covers:` line to PUBTXT (Phase 7).
- **FILE-011**: `engine/src/threepowers/cli/` — **new** package: `__init__.py`, `_common.py`, `keys.py`, `bootstrap.py`, `gate.py`, `trust.py`, `exceptions.py`, `oracle.py`, `observe.py`, `run.py`, `supply.py`, `brownfield.py` (Phase 8).
- **FILE-012**: `engine/tests/**` — exact-string expectation updates only, same commit as each text change (Phases 2–3); import-path edits only if the re-export surface misses a name (Phase 8). `Covers:` declarations never touched.
- **FILE-013**: `engine/pyproject.toml` — explicitly **unchanged** (entry point `threepowers.cli:main` and `[tool.mutmut]` scope both stay as-is).

## 6. Testing

- **TEST-001** (A): Scanner sanity — its engine-source total roughly matches the raw grep census (~1,100 pre-030, more after); a large shortfall fails Phase 1. No shipped tests (disposable).
- **TEST-002** (B, per pass): Existing suite green after every pass — `(cd engine && uv run pytest)`, `ruff check .`, `mypy src` — with exact help/message-string expectations updated in the same commit as each text change (CON-004).
- **TEST-003** (B): `3pwr gate run --path engine` green after each phase; trust-spine coverage ≥95%; `[tool.mutmut]` scope untouched (CON-003).
- **TEST-004** (B5): Fresh `3pwr init` in a scratch dir followed by `grep -rE '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b' .3powers/` finds nothing (Phase 6 and again Phase 9).
- **TEST-005** (C2): The new `test_oss_readiness.py` section — red on a seeded violation, green on the cleaned tree; still passes (or skips correctly) under mutmut's copied layout; carries a `Covers:` line to the PUBTXT spec.
- **TEST-006** (D): Full pytest green with no behavioral test changes; captured pre-split `3pwr --help` and per-group `--help` outputs byte-identical post-split; `uv tool install --force ./engine` then `3pwr --version`, representative subcommand helps, and a `3pwr verify` run in this repo.
- **TEST-007** (D): `mypy src` green across the new package boundaries; `ruff check .` green; `3pwr gate run --path engine` green with the `diff_coverage` contingency handled per TASK-030.
- **TEST-008** (smoke, unit 1): `3pwr --help | grep -E '\b[A-Z][A-Z0-9]{2,}-(FR|NFR)-[0-9]{2,3}\b'` empty; spot-checks of `3pwr verify --help` and `3pwr run --help`.

## 7. Risks & Assumptions

- **RISK-001** (plan 030 merge conflicts): 030's remaining phases rewrite cli.py, orchestrate.py, style.py, frame.py. Mitigation: the hard sequencing rule (CON-001, TASK-001) — nothing runs before 030 merges; the branch is cut from post-030 `main`; the inventory runs then.
- **RISK-002** (re-seal / gate_gaming on constitution edits): Editing seeded/sealed assets can trip `spec_integrity` or `gate_gaming`. Mitigation: B5 is its own commit; TASK-019 runs `3pwr gate run --path engine` + `3pwr verify` before landing; maintainer re-seal preferred, signed recorded deviation as fallback — user decides, ledger records either way.
- **RISK-003** (enforcement regex false positives): A legitimate doc example or a future doc quoting a user's own namespaced ID would fail the permanent test. Mitigation: only the namespaced pattern is forbidden, bare `FR-###` allowed, explicit `DEMO-`/placeholder allowlist named in the failure message; the `spec_conformance` gate is untouched (it reads only `Covers:` lines in tests, which stay).
- **RISK-004** (docstring-presence regressions in B3): Deleting a docstring whose only content was a citation would strip API docs and could trip lint. Mitigation: rewrite-never-delete rule (GUD-001); ruff after each pass.
- **RISK-005** (behavior drift in the D split): Module-import side effects, help-text ordering, exit-code changes. Mitigation: pure-motion discipline — pre-split `--help` captures diffed after (TASK-025/029), full pytest, install smoke, explicit registration-order loop.
- **RISK-006** (tests pinned to exact strings): B1/B2 break verbatim-string assertions. Mitigation: expected-string updates in the same commit as each text change (CON-004) so every commit is green.
- **RISK-007** (scaffold ↔ seeded-copy drift): B5 edits both sides; parity/non-clobbering checks could mask or flag drift. Mitigation: the Phase 6 pairing table; both sides in the same commit; fresh-init grep verifies the shipped result.
- **RISK-008** (`diff_coverage` on the split): Moving ~5,700 lines makes the whole cli package "new" to a diff-based coverage gate. Mitigation: the cli command functions are already exercised by the existing suite; the gate run uses `--base main`; if moved-but-uncovered legacy lines still flag, it is surfaced to the user for a deviation decision, not papered over with low-value tests (TASK-030).
- **ASSUMPTION-001**: Plan 030 merges with its documented shape (specs 020–026 allocated; new namespaces RUNID/GDIAG/GATECFG/GATEPIPE/PROGFILE/PHASEPR/TRIX present in user-visible text and swept by the inventory).
- **ASSUMPTION-002**: The `DEMO-` namespace is unused anywhere in the repo at implementation time (the Phase 1 namespace census confirms; if violated, pick another reserved token with the user).
- **ASSUMPTION-003**: `engine/tests/` imports from `threepowers.cli` are enumerable by grep (TASK-025), so the `__init__.py` re-export surface can be derived mechanically and the default outcome is zero test edits.
- **ASSUMPTION-004**: The post-030 `cmd_*` function set maps onto the Phase 8 module map by command group; any new 030 subcommands (e.g. `gate config show`) join their natural group module.

## 8. Related Specifications / Further Reading

- [plan/031-public-text-decruft-and-cli-split.md](031-public-text-decruft-and-cli-split.md) — the source plan for this implementation plan
- `specs/<NNN>-public-text-hygiene/spec.md` (PUBTXT) — authored in Phase 1 (TASK-004): the no-internal-IDs rule, surfaces, exemptions, allowlist, enforcement test
- `specs/<NNN+1>-cli-package-split/spec.md` (CLIPKG) — authored in Phase 1 (TASK-005): module map, behavior-identity and entry-point invariants
- [AGENTS.md](../AGENTS.md) — mandatory workflow, branch/commit discipline (no pull requests), open-source-readiness rules; gains the convention text in Phase 7
- [CLAUDE.md](../CLAUDE.md) — architecture deep-dive; gains the mirror note in Phase 7
- [docs/cli-reference.md](../docs/cli-reference.md) — the public CLI reference cleaned in Phase 5
- `engine/tests/test_oss_readiness.py` — plan 022's oss-readiness suite, extended with the permanent enforcement section in Phase 7
