---
goal: Backend-neutral, source-typed structured token/cost usage providers with per-backend drift guards, a copilot session-file source, and a Claude sub-agent token-total correctness fix
version: 1.0
date_created: 2026-07-21
last_updated: 2026-07-21
owner: 3Powers maintainers
status: 'Planned'
tags: [feature, refactor, bug, architecture]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan operationalizes source plan `plan/037-structured-usage-providers.md`. It replaces
the fragile, regex-first token/cost extraction shipped in plan 036's Track E with a **source-typed
`UsageProvider` contract** (`usage.source`: `inline-json` · `session-file` · `regex` · `none`), migrates
every backend that emits structured usage off prose-regex onto structured sources, gives copilot a
structured on-disk source (its `session.shutdown` event) with a drift-proof regex fallback, fixes a
**shipped correctness bug** (Claude's token total undercounts sub-agent usage because it reads the
top-level `usage` block instead of the whole-tree `modelUsage` rollup), and adds the per-backend
current-output drift guard whose absence let the copilot regex rot go silent.

The work is split into six phases mapping to the source plan's six tracks (A–F), with the final phase
folding Track F (docs) together with a dedicated verification pass. **Phases 1–4 execute strictly
sequentially (no `[P]` marking)** because `engine/src/threepowers/agents.py` is the shared hotspot every
one of Tracks A/B/C/D edits: Phase 1 (Track A) establishes the provider seam the later phases extend, and
the per-source resolvers (Tracks B/C/D) are all added to the same module. The manifest pairs
(`.3powers/agents/<name>.yaml` + `engine/src/threepowers/scaffold/agents/<name>.yaml`) are always updated
**together in the same task** for a given backend. Phase 5 (Track E) adds fixtures and tests only; Phase 6
folds docs (Track F) with verification.

Execution note (per `AGENTS.md`/`CLAUDE.md`): all Python changes under `engine/src/threepowers/` with
tests under `engine/tests/` are performed by the **python-engineer agent** at implementation time. Every
behavior change ships with a matching `docs/` update in the same unit of work; a behavior change without a
docs update is incomplete. **Usage is strictly advisory** — it never fails a dispatch, never raises, and an
unresolvable source renders `—` rather than a fabricated number (Decisions 6, 8; CON-001/CON-002).

## 1. Requirements & Constraints

- **REQ-A**: Usage is resolved by a declarative `usage.source` taxonomy
  (`inline-json`/`session-file`/`regex`/`none`) dispatched by a single provider in `agents.py`;
  structured-first; regex is only a declared fallback; an unknown source yields `None` → `—`, never a guess
  (Track A, Decision 1).
- **REQ-B**: Codex and opencode read structured inline JSON (Codex off regex via `codex exec --json`;
  opencode via `run --format json` summing multiple `step_finish` events); Claude is confirmed
  `inline-json`. After this, regex is never a Tier-1 primary (Track B, Decision 4).
- **REQ-C**: Copilot and aider read structured usage from their session file — deterministically located,
  defensively parsed, version-pinned; copilot retains a drift-proof regex fallback (Track C, Decisions 2, 7).
- **REQ-D**: A Claude dispatch's token total is computed from `modelUsage` (whole-tree, per-model sum), with
  a fallback to the top-level `usage` block when `modelUsage` is absent; cost stays from `total_cost_usd`
  (Track D, Decision 3).
- **REQ-E**: Every supported backend ships a committed fixture of its current real output plus a
  drift-failing test; `none`/unresolved renders `—` and is tested never to fabricate a value (Track E,
  Decisions 5, 6).
- **SEC-001**: Reading a session file must not execute or trust file contents beyond numeric usage fields;
  the captured session id must be validated as a strict UUID before it is templated into a filesystem path
  (no path traversal), per the source plan's SEC-001.
- **CON-001**: The verdict, ledger schema, exit codes, and `--json` are unchanged beyond the additive
  token/cost fields Track E already introduced; usage never fails a dispatch and never raises.
- **CON-002**: The `extract_usage`/`extract_cost` public call signatures and the
  `StageResult.tokens`/`cost` → `progress.md` chain are preserved; only the resolution *inside* the helpers
  changes (Decision 8).
- **CON-003**: Backends with a manifest that declares no usable source degrade cleanly to `none` (`—`);
  manifest-less backends (`amp`/`qwen`/`cursor-agent`/`auggie`) are out of scope and simply render `—`.
- **CON-004**: Phases 1–4 execute sequentially because Tracks A/B/C/D all edit `agents.py`; Phase 1 lands
  first because it establishes the provider seam the others extend.
- **GUD-001** (OSS readiness): All new/changed manifest comments, help, and docs obey
  `engine/tests/test_oss_readiness.py` — no internal plan/spec/requirement ids; format teaching uses bare
  `FR-###` / `DEMO-FR-###` (Decision 9).
- **GUD-002** (self-application): The engine stays green under its own gates (ruff/mypy/pytest and
  `3pwr gate run --path engine`, including `gate_gaming` and the High-risk coverage floors) after each phase.
- **PAT-001**: Each backend's usage is delivered by a manifest-declared `usage` block consumed by the
  provider dispatcher in `agents.py`; the engine reads only what the manifest declares (never invents a
  field path or CLI flag).
- **PAT-002**: Session-file resolution is defensive and version-pinned: missing file/id/field → `None`
  (never raises); a schema change fails a *test*, never a run (Decision 7).

## 2. Implementation Steps

### Phase 1

- GOAL-001: Track A — introduce the source-typed `UsageProvider` contract. Add an explicit `usage.source`
  field (`inline-json`/`session-file`/`regex`/`none`) to the manifest schema and refactor `extract_usage`
  (`agents.py:283`) and `extract_cost` (`agents.py:341`) to dispatch on it, preserving the public call
  signatures, the advisory "never raises; always `Optional`" contract, and the `StageResult.tokens`/`cost`
  → `progress.md` chain unchanged (Decision 8). Legacy `usage.strategy: json`/`regex` maps to
  `inline-json`/`regex`.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/agents.py`, add an explicit `usage.source` field to the manifest usage schema with the taxonomy `inline-json` \| `session-file` \| `regex` \| `none`. Add back-compat mapping so an existing `usage.strategy: json` maps to `inline-json` and `usage.strategy: regex` maps to `regex` (accept both during transition; prefer `source`). Keep `is_stream_json` (`agents.py:105`) semantics intact for the inline-json path. |  |  |
| TASK-002 | Refactor `extract_usage` (`agents.py:283`) and `extract_cost` (`agents.py:341`) to dispatch on the resolved `source`: `inline-json` → today's `_usage_from_json` over the run's JSON lines (fields + optional `subtract`); `session-file` → a new resolver stub (populated in Phase 3); `regex` → today's `_usage_from_regex`, explicitly commented as a fallback; `none` → `None`. Keep the two-arg public signatures used at `runner.py:397` (`extract_usage`) / `runner.py:401` (`extract_cost`) unchanged; thread the additional context a `session-file` source needs (captured stdout, cwd/home) via a thin internal provider object or an internal overload, not by changing the public helpers (Decision 8). |  |  |
| TASK-003 | Guardrail (no-op verification): confirm the downstream chain — `DispatchResult.tokens`/`cost` → `StageResult.tokens`/`cost` → `progress.md` — is byte-unchanged; the resolution *inside* the helpers is the only change (CON-002, Decision 8). Confirm the helpers still never raise and always return `Optional` (advisory contract, CON-001). Record this confirmation in the phase note. |  |  |
| TASK-004 | Update `docs/` (the CLI/observability reference) to introduce the `usage.source` taxonomy at a high level and state the honest-`—` behavior; deeper per-backend detail is folded into Phase 6. No internal ids (GUD-001). |  |  |
| TASK-005 | Confirm `engine/tests/test_oss_readiness.py` stays green for any new manifest-schema comment or user-facing string introduced by the contract (GUD-001). |  |  |
| TASK-006 | Tests: in `engine/tests/test_agents.py`, assert the `source` dispatch table (each of `inline-json`/`session-file`/`regex`/`none` routes to the right resolver); a legacy `strategy: json`/`regex` manifest maps to the new source and yields the same result as today; a `source: none` (or no usable source) yields `None`. Confirm existing Track E extraction tests stay green (preserved chain). |  |  |

### Phase 2

- GOAL-002: Track B — Tier-1 inline-json migration. Move Codex off regex to `codex exec --json`, confirm
  opencode reads `run --format json` (summing multiple `step_finish` events), and confirm Claude stays
  `inline-json`. Update both the repo manifests `.3powers/agents/*.yaml` and the bundled scaffold copies
  `engine/src/threepowers/scaffold/agents/*.yaml` in the same task per backend. After this, regex survives
  only as an explicit declared fallback.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-007 | Migrate **Codex** off regex: in `.3powers/agents/codex.yaml` **and** `engine/src/threepowers/scaffold/agents/codex.yaml` (same task), set `source: inline-json`, enable the currently commented-out `usage_mode: json` (`codex exec --json`), and set the field paths to the actual `turn.completed.usage.*` shape emitted by the current CLI — verify whether the tokens live at `usage.input_tokens`/`usage.output_tokens` nested under the `turn.completed` event vs bare. Retain the existing `pattern: 'tokens used[:\s]+([0-9][0-9,]*)'` as a declared `regex` fallback, not the primary. Refresh the header comment to stop teaching regex-first. |  |  |
| TASK-008 | Confirm **opencode**: in `.3powers/agents/opencode.yaml` **and** the scaffold copy (same task), declare `source: inline-json` reading `opencode run --format json`; sum `step_finish.part.tokens.{input,output}` across the multiple `step_finish` events and read `part.cost` for cost. Note the known "exits before final event" bug in the header comment; fall back to `none` (`—`) if no `step_finish` event is present. |  |  |
| TASK-009 | Confirm **Claude**: in `.3powers/agents/claude.yaml` **and** the scaffold copy (same task), confirm `source: inline-json` (its `fields: [usage.input_tokens, usage.output_tokens]` and `cost_field: total_cost_usd` are the current shape). The token-field change to `modelUsage` is Track D (Phase 4); this task only asserts the source classification, leaving the field paths for Phase 4. |  |  |
| TASK-010 | Update `docs/` to record that Codex and opencode now read structured inline JSON (no Tier-1 regex), including the opencode multi-`step_finish` summing note. No internal ids (GUD-001). |  |  |
| TASK-011 | Confirm `engine/tests/test_oss_readiness.py` stays green for the refreshed Codex/opencode/Claude manifest header comments (GUD-001). |  |  |
| TASK-012 | Tests: in `engine/tests/test_agents.py` (and fixtures under `engine/tests/fixtures/usage/`), a Codex `--json` `turn.completed` transcript fixture yields the correct tokens (and cost if present) with **no** regex involved, and the regex fallback fires only when the JSON is absent; an opencode `--format json` fixture with multiple `step_finish` events sums correctly. (Codex fixture builds on the existing `codex.jsonl`; add/refresh an opencode fixture.) |  |  |

### Phase 3

- GOAL-003: Track C — Tier-2 session-file providers for copilot and aider. Add a `session-file` resolver in
  `agents.py` that recovers a captured session id, resolves+reads the backend's on-disk session artifact,
  selects the usage-bearing event, and extracts tokens/cost defensively. Copilot reads
  `~/.copilot/session-state/<id>/events.jsonl` → `session.shutdown`; aider reads its `--analytics-log`
  JSONL `message_send` events. Both manifest pairs are updated together. SEC-001: the captured id is
  validated as a strict UUID before it is templated into a path.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-013 | Add the `session-file` resolver in `engine/src/threepowers/agents.py`: given the dispatch's captured output and a manifest `usage` block declaring `source: session-file`, a `session_id_pattern` (regex capturing the id from CLI output), a `path_template` (e.g. `~/.copilot/session-state/{id}/events.jsonl`), an `event` selector, and token/cost field paths — recover the id, resolve+read the file, select the event, extract usage. Missing file/id/fields → `None` (never raises), honoring PAT-002. Wire it into the Phase 1 dispatcher stub. |  |  |
| TASK-014 | SEC-001 hardening: before templating the captured session id into `path_template`, validate it against a strict UUID pattern; reject any id containing path separators or `..` traversal. An id that fails validation → treat the session-file source as unresolved (fall to the declared fallback, then `—`); never read an attacker-influenced path. |  |  |
| TASK-015 | Wire **copilot**: in `.3powers/agents/copilot.yaml` **and** `engine/src/threepowers/scaffold/agents/copilot.yaml` (same task), set `source: session-file`; capture the id from the CLI's `Resume copilot --resume=<uuid>` output line via `session_id_pattern`; read the `session.shutdown` event from `~/.copilot/session-state/{id}/events.jsonl`; note the legacy `history-session-state/` path and the version path change in the header comment. Keep a declared `regex` fallback with the drift-proof pattern `Tokens[^\n]*?↑[^\n]*?([0-9][0-9.,_kKmM]*)\s+written\)[^\n]*?↓[^\n]*?([0-9][0-9.,_kKmM]*)`. Copilot cost is premium-request/credits, not USD — record tokens; leave cost `—` unless a USD field is present. |  |  |
| TASK-016 | Wire **aider**: in `.3powers/agents/aider.yaml` **and** the scaffold copy (same task), set `source: session-file` reading `--analytics --analytics-log <file>` (force `--analytics`, which is sampled off by default; the engine passes a run-scoped temp `--analytics-log <path>`) — `message_send` events → `properties.{prompt_tokens, completion_tokens}` summed and `properties.{cost|total_cost}` (USD). Document in the header comment that this changes the aider invocation. |  |  |
| TASK-017 | Update `docs/` to document the copilot session-file dependency (the `~/.copilot/session-state/<id>/events.jsonl` → `session.shutdown` source, the `--resume=<uuid>` id capture, and the undocumented-schema/version caveat), the aider `--analytics-log` source and the invocation change, and the copilot USD-cost caveat. No internal ids (GUD-001). |  |  |
| TASK-018 | Confirm `engine/tests/test_oss_readiness.py` stays green for the copilot/aider manifest header comments and any new user-facing strings (GUD-001). |  |  |
| TASK-019 | Tests (copilot): in `engine/tests/` (fixtures under `engine/tests/fixtures/usage/`), a copilot `events.jsonl` fixture with a `session.shutdown` event yields the correct tokens; a run whose output carries the `--resume=<uuid>` line resolves the right file; a missing/renamed file falls back to the hardened regex, and if that also fails, `—`; the current live summary line (`Tokens … (192.8k cached, 46.9k written) … ↓ 5.2k …`) yields `52100` via the fallback regex; a path-traversal attempt in the captured id is rejected (SEC-001). |  |  |
| TASK-020 | Tests (aider): an aider `--analytics-log` `message_send` fixture yields tokens **and** USD cost; a missing/renamed field degrades to `None` (never raises). |  |  |

### Phase 4

- GOAL-004: Track D — fix the Claude sub-agent token undercount. For the Claude `inline-json` source,
  compute the token total from `modelUsage` (per-model sum of input+output, whole-tree) instead of the
  top-level `usage` block, falling back to the top-level `usage` only when `modelUsage` is absent (older
  CLI); keep cost from `total_cost_usd` (already whole-tree-correct). Update the `claude.yaml` manifest pair.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-021 | In `engine/src/threepowers/agents.py`, for the Claude `inline-json` source compute tokens from `modelUsage` (the per-model map in the final `result` event): sum each model's input+output, excluding cache reads consistently with the manifest's existing posture. Fall back to the top-level `usage` block only when `modelUsage` is absent (older CLI back-compat). Keep cost from `total_cost_usd`. |  |  |
| TASK-022 | Update `.3powers/agents/claude.yaml` **and** `engine/src/threepowers/scaffold/agents/claude.yaml` (same task): change the token field spec from the top-level `fields: [usage.input_tokens, usage.output_tokens]` to the `modelUsage`-aware spec, keep `cost_field: total_cost_usd`, and refresh the header comment to describe the whole-tree sub-agent rollup and the older-CLI fallback. No internal ids (GUD-001). |  |  |
| TASK-023 | Update `docs/` to document that a Claude dispatch's token total is the whole-tree `modelUsage` rollup (sub-agents included) with an older-CLI fallback to the top-level `usage`, and that cost comes from `total_cost_usd`. No internal ids (GUD-001). |  |  |
| TASK-024 | Confirm `engine/tests/test_oss_readiness.py` stays green for the refreshed `claude.yaml` header comment (GUD-001). |  |  |
| TASK-025 | Tests: a `stream-json` fixture whose final `result` event has `modelUsage` for two models (a main + a sub-agent model) yields the **summed** token total, strictly greater than the top-level `usage` block alone, and cost equal to `total_cost_usd`; a fixture without `modelUsage` degrades to the top-level `usage` (older-CLI back-compat). Build on the existing `engine/tests/fixtures/usage/claude_stream.jsonl` / `claude.json`. |  |  |
| TASK-026 | Guardrail: confirm the additive token/cost fields do not regress the High-risk trust-spine coverage floors (`canonical`, `keys`, `ledger`, `verify` ≥ 95%) and that no verdict/ledger/exit-code/`--json` behavior changes beyond additive fields (CON-001). Record this confirmation in the phase note. |  |  |

### Phase 5

- GOAL-005: Track E — per-backend drift guards + honest-unknown. Commit a fixture of each supported
  backend's **current** real output under `engine/tests/fixtures/usage/`, add a parametrized test that
  extracts the expected tokens/cost, add a companion drift-sample test that fails on format/schema change,
  and assert `none`/unresolved renders `—`. Replace the synthetic old-format assertions in
  `test_native_runner.py` with fixture-driven ones.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-027 | Under `engine/tests/fixtures/usage/`, commit a fixture per supported backend capturing the **current** real shape: Claude `stream-json` `result` (with `modelUsage`), Codex `--json` `turn.completed`, opencode `--format json` `step_finish`, copilot `events.jsonl` `session.shutdown` **and** a current summary-line sample, aider `--analytics-log` `message_send`. Refresh the existing partial set (`aider.txt`, `claude.json`, `claude_stream.jsonl`, `codex.jsonl`, `codex.txt`, `copilot.txt`) and add the missing shapes (copilot `events.jsonl`, opencode `step_finish`). |  |  |
| TASK-028 | Add a parametrized test asserting each backend's provider extracts the expected tokens/cost from its fixture (Claude → `modelUsage` sum + `total_cost_usd`; Codex → `turn.completed.usage`; opencode → summed `step_finish.part.tokens`; copilot → `session.shutdown`; aider → `message_send`). |  |  |
| TASK-029 | Add a companion drift-guard test asserting a **format-drift** sample does not silently succeed with a wrong number: the OLD copilot summary line (padded columns + `(… cached, … written)`) must NOT match the current provider path silently, and a renamed field in a structured fixture must fail the test rather than zero the value. Mutating a fixture field name must make the test fail (proving the guard). |  |  |
| TASK-030 | Replace the synthetic old-format assertions at `engine/tests/test_native_runner.py:1073` (the duplicated old regex) and `engine/tests/test_native_runner.py:1263` (the hard-coded old-format line asserting `38700`) with fixture-driven assertions sourced from `engine/tests/fixtures/usage/`, so no test exercises a format the current CLI no longer emits. |  |  |
| TASK-031 | Add tests asserting a `source: none` and an unresolved `session-file` (missing id/file) both yield `None` → `progress.md` shows `—`, never a fabricated value (Decision 6). |  |  |
| TASK-032 | Confirm `engine/tests/test_oss_readiness.py` stays green for any fixture-adjacent comment or user-facing string introduced by the drift guards (GUD-001). |  |  |

### Phase 6

- GOAL-006: Track F + Verification — finalize the docs (the `usage.source` taxonomy, per-backend source, the
  copilot session-file dependency + version caveat, the honest-`—` behavior, and the Claude sub-agent
  rollup) and prove all six tracks' acceptance criteria pass, the engine is green under its own toolchain
  and gates, OSS-readiness holds, verdict/ledger/`--json` determinism is preserved (additive fields only),
  and the definition-of-done scenario holds.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-033 | Finalize `docs/` (CLI/observability reference and any usage/output guide): the `usage.source` taxonomy and per-backend source table; the copilot session-file dependency and undocumented-schema/version caveat; the honest-`—` behavior; the Claude sub-agent (`modelUsage`) rollup. Update every touched manifest header comment to stop teaching the regex-first posture. No internal ids (GUD-001). |  |  |
| TASK-034 | Confirm `engine/tests/test_oss_readiness.py` passes — no internal plan/spec/requirement ids in any new user-facing string across all six tracks (GUD-001). |  |  |
| TASK-035 | Run `cd engine && uv run pytest` — all new and existing tests pass, including `test_agents.py`, the new per-backend fixture/drift tests, the rewritten `test_native_runner.py` fixture-driven usage assertions, and the preserved Track E extraction tests. |  |  |
| TASK-036 | Run `cd engine && uv run ruff check .` and `cd engine && uv run mypy src` — clean. |  |  |
| TASK-037 | Run `3pwr gate run --path engine` — the engine stays green under its own gates, including `gate_gaming` and the High-risk coverage floors (GUD-002). |  |  |
| TASK-038 | Confirm verdict/ledger/exit-code/`--json` byte-stability is preserved (strictly-additive token/cost fields only) and the `extract_usage`/`extract_cost` signatures + the `StageResult`→`progress.md` chain are unchanged (CON-001, CON-002, Decision 8). |  |  |
| TASK-039 | Scenario — copilot: a copilot run records real tokens in `progress.md` via the session file, or via the hardened regex fallback when the file is absent/renamed (never `—` for a run that consumed tokens where a source resolves). |  |  |
| TASK-040 | Scenario — Claude multi-agent: a Claude run using sub-agents records the whole-tree token total (strictly greater than the top-level `usage` block) and the correct cost (`total_cost_usd`) in `progress.md`. |  |  |
| TASK-041 | Scenario — Codex: a Codex run records structured tokens via `codex exec --json` with **no** regex involved; the regex fallback fires only when the JSON is absent. |  |  |

## 3. Alternatives

- **ALT-001**: Keep regex as the primary usage strategy and just harden each backend's pattern
  (source plan §"deeper design weakness"). Rejected: parsing vendor prose is inherently fragile and
  vendor-specific; the copilot rot proved a padded column + a new `(… cached, … written)` term silently
  breaks a pattern. The source-typed taxonomy makes structured the default and regex a visible last resort
  (Decision 1).
- **ALT-002**: Use OpenTelemetry as a single cross-vendor usage source (source plan "Explicitly out of
  scope"). Rejected for now: it is the only near-standard cross-vendor path but requires running/embedding a
  collector — too heavyweight for a local run wrapper. Noted as a possible future unifying backend, not
  built here (Decision 2).
- **ALT-003**: Design a post-run "query the CLI for tokens" call. Rejected: research found no vendor exposes
  a standard post-hoc usage query; usage is emitted inline with a run's structured output or written to an
  on-disk session artifact. The contract models inline-event / session-file / prose, not a token query
  (Decision 4).
- **ALT-004**: Keep reading Claude's top-level `usage` block for tokens. Rejected: it excludes sub-agent
  tokens, so with plan 036 Track D (sub-agent models) live the token column is wrong on exactly the
  multi-agent runs sub-agents were built for; `modelUsage` and `total_cost_usd` roll up the whole tree
  (Decision 3).
- **ALT-005**: Guess a partial number from a garbled structured payload rather than reporting `—`.
  Rejected: usage is advisory and a wrong number (especially cost) is worse than an honest blank; an
  unresolved/`none` source renders `—`, a partial/garbled payload yields `None` (Decision 6).
- **ALT-006**: Locate the copilot session file by scanning for the newest state directory. Rejected: the
  CLI already prints a stable session id (`Resume copilot --resume=<uuid>`), so the file is locatable
  deterministically without guessing; guessing risks reading the wrong session (Decision 2, SEC-001).

## 4. Dependencies

- **DEP-001**: The preserved usage chain — `agents.extract_usage` (`agents.py:283`) / `extract_cost`
  (`agents.py:341`) → `DispatchResult.tokens`/`cost` → `StageResult.tokens`/`cost` → `progress.md`, called
  at `runner.py:397` (`extract_usage`) / `runner.py:401` (`extract_cost`). Track A refactors the resolution
  inside without changing the chain (Decision 8).
- **DEP-002**: The manifest-declared-field mechanism in `agents.py` (`is_stream_json` at `agents.py:105`,
  the existing `_usage_from_json`/`_usage_from_regex` helpers, and `usage_mode`/`usage_mode_args`) — reused
  and extended by the new `source` dispatcher.
- **DEP-003**: The manifest pairs `.3powers/agents/{claude,codex,opencode,copilot,copilot-hosted,aider}.yaml`
  and their scaffold copies under `engine/src/threepowers/scaffold/agents/` — always edited together per
  backend.
- **DEP-004**: The existing partial fixture set under `engine/tests/fixtures/usage/` (`aider.txt`,
  `claude.json`, `claude_stream.jsonl`, `codex.jsonl`, `codex.txt`, `copilot.txt`) — refreshed to current
  shapes and extended (copilot `events.jsonl`, opencode `step_finish`) by Track E.
- **DEP-005**: The current vendor CLIs and their output shapes — `codex exec --json`
  (`turn.completed.usage.*`), `opencode run --format json` (`step_finish.part.tokens.*` / `part.cost`),
  Claude `--output-format stream-json` (`modelUsage`, `total_cost_usd`), copilot
  `~/.copilot/session-state/<id>/events.jsonl` (`session.shutdown`) with the `--resume=<uuid>` output line,
  aider `--analytics --analytics-log <file>` (`message_send`).
- **DEP-006**: `engine/tests/test_oss_readiness.py` — must pass for all new/changed manifest comments, help,
  and docs.
- **DEP-007**: The `3pwr` CLI installed from `./engine` and the engine test/gate toolchain
  (`uv run pytest`/`ruff`/`mypy`, `3pwr gate run --path engine`) for verification.

## 5. Files

- **FILE-001**: `engine/src/threepowers/agents.py` — the shared hotspot: the `usage.source` schema +
  dispatcher and `extract_usage` (`agents.py:283`)/`extract_cost` (`agents.py:341`) refactor (Track A,
  Phase 1); the `inline-json` field-path handling and `is_stream_json` (`agents.py:105`) reuse (Track B,
  Phase 2); the `session-file` resolver + UUID validation (Track C, Phase 3); the Claude `modelUsage`
  token computation (Track D, Phase 4). Edited across Phases 1–4, hence sequential.
- **FILE-002**: `engine/src/threepowers/runner.py` — the `extract_usage`/`extract_cost` call sites at
  `runner.py:397`/`runner.py:401` (signatures preserved; guardrail only, Decision 8).
- **FILE-003**: `.3powers/agents/codex.yaml` + scaffold copy — `source: inline-json`, enable the commented
  `usage_mode: json`, `turn.completed.usage.*` field paths, regex-as-fallback (Track B).
- **FILE-004**: `.3powers/agents/opencode.yaml` + scaffold copy — `source: inline-json`, `step_finish`
  summing, `part.cost`, no-event → `none` (Track B).
- **FILE-005**: `.3powers/agents/claude.yaml` + scaffold copy — `source: inline-json`; token field spec
  changed from the top-level `usage.input_tokens`/`usage.output_tokens` to `modelUsage`, `cost_field:
  total_cost_usd` kept, header comment refreshed for the sub-agent rollup (Tracks B + D).
- **FILE-006**: `.3powers/agents/copilot.yaml` + scaffold copy — `source: session-file`,
  `session_id_pattern` for `--resume=<uuid>`, `path_template` `~/.copilot/session-state/{id}/events.jsonl`,
  `session.shutdown` selector, drift-proof `regex` fallback, USD-cost caveat (Track C).
- **FILE-007**: `.3powers/agents/aider.yaml` + scaffold copy — `source: session-file` reading
  `--analytics --analytics-log <file>` `message_send`, invocation-change note (Track C).
- **FILE-008**: `engine/tests/fixtures/usage/` — refreshed + new current-output fixtures per backend
  (Claude `modelUsage`, Codex `turn.completed`, opencode `step_finish`, copilot `events.jsonl` +
  summary-line, aider `message_send`) (Track E).
- **FILE-009**: `engine/tests/test_agents.py` — the `source` dispatch table, legacy `strategy` mapping,
  Codex/opencode structured extraction, and the parametrized per-backend fixture + drift tests (Tracks
  A/B/C/D/E).
- **FILE-010**: `engine/tests/test_native_runner.py` — the synthetic old-format assertions at
  `test_native_runner.py:1073` (duplicated old regex) and `test_native_runner.py:1263` (hard-coded
  old-format line asserting `38700`) replaced with fixture-driven assertions (Track E).
- **FILE-011**: `docs/cli-reference.md` + the `docs/` usage/output reference — the `usage.source`
  taxonomy, per-backend source table, copilot session-file caveat, honest-`—`, and Claude rollup (Track F).
- **FILE-012**: `engine/tests/test_oss_readiness.py` — must stay green for all new/changed user-facing text
  (GUD-001; not modified, only satisfied).

## 6. Testing

- **TEST-001** (Track A): `engine/tests/test_agents.py` — the `source` dispatch table (each source → right
  resolver); a legacy `strategy: json`/`regex` manifest maps to the new source with an identical result;
  `source: none` → `None`; the preserved chain's existing extraction tests stay green.
- **TEST-002** (Track B): Codex `--json` `turn.completed` fixture yields the correct tokens (and cost)
  with no regex; the regex fallback fires only when JSON is absent; an opencode `--format json` fixture with
  multiple `step_finish` events sums correctly.
- **TEST-003** (Track C): a copilot `events.jsonl` `session.shutdown` fixture yields correct tokens; a
  `--resume=<uuid>` output sample resolves the right file; a missing/renamed file falls back to the hardened
  regex and then `—`; the current live summary line yields `52100` via the fallback; a path-traversal id is
  rejected (SEC-001); an aider `--analytics-log` `message_send` fixture yields tokens **and** USD cost.
- **TEST-004** (Track D): a two-model `modelUsage` `stream-json` fixture → summed tokens strictly greater
  than the top-level `usage` block; cost = `total_cost_usd`; a no-`modelUsage` fixture degrades to the
  top-level `usage` (older-CLI back-compat).
- **TEST-005** (Track E): the parametrized per-backend fixture test passes; mutating a fixture field name
  makes the test fail (drift guard); the old copilot line and a renamed field do not silently succeed; a
  `none` source and an unresolved `session-file` both render `—`; the rewritten `test_native_runner.py`
  usage assertions are fixture-driven.
- **TEST-006** (whole engine): `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (self-application incl. `gate_gaming` and High-risk coverage ≥ 95%),
  and `engine/tests/test_oss_readiness.py` green.
- **TEST-007** (definition-of-done scenarios): a live copilot run records real tokens in `progress.md` (via
  the session file, or the hardened regex fallback); a live Claude multi-agent run records the whole-tree
  token total and correct cost; a Codex run records structured tokens with no regex.

## 7. Risks & Assumptions

- **RISK-001** (Track C): session-file schema drift for copilot/aider — the file schemas are undocumented
  and may change. *Mitigation:* defensive parse (missing → `None`, never raise), version-pin in the manifest
  header comment, a drift-failing fixture test (Track E), and the regex fallback for copilot.
- **RISK-002** (Track C): the session id is absent from the output or ambiguous. *Mitigation:* validate the
  captured id as a strict UUID; if unresolved, fall back to regex then `—`; never guess a file (SEC-001).
- **RISK-003** (Track B): the Codex/opencode JSON field paths are guessed wrong. *Mitigation:* build the
  fixture from real CLI output during implementation and pin it with a test; the drift guard fails on a
  wrong path.
- **RISK-004** (Track D): `modelUsage` is absent on an older Claude CLI. *Mitigation:* documented fallback
  to the top-level `usage` block, covered by a no-`modelUsage` fixture.
- **RISK-005** (Track C, SEC-001): path traversal from a crafted session id. *Mitigation:* accept only a
  strict UUID before templating the path; reject separators/`..`.
- **RISK-006** (all tracks): a regression in the preserved chain. *Mitigation:* Decision 8 keeps the
  `extract_usage`/`extract_cost` signatures and the `StageResult`→`progress.md` path; existing Track E
  tests must stay green; a byte-stability check on the additive fields (CON-001).
- **RISK-007** (Phases 1–4): file-scope contention on `engine/src/threepowers/agents.py`. *Mitigation:*
  sequential phase execution (no `[P]`), Phase 1 establishes the seam first, and each phase re-anchors to
  current source before editing.
- **ASSUMPTION-001**: The file:line anchors carried from the source plan — `agents.py:283`
  (`extract_usage`), `agents.py:341` (`extract_cost`), `agents.py:105` (`is_stream_json`); `runner.py:397`
  (`extract_usage` call) / `runner.py:401` (`extract_cost` call); `claude.yaml` `fields: [usage.input_tokens,
  usage.output_tokens]` + `cost_field: total_cost_usd`; `codex.yaml` commented `usage_mode: json`;
  `test_native_runner.py:1073` (duplicated old regex) and `test_native_runner.py:1263` (synthetic
  old-format assertion) — **and** the exact vendor JSON field paths (Codex `turn.completed.usage.*`,
  opencode `step_finish.part.tokens.*`, Claude `modelUsage`, copilot `session.shutdown`) are re-verified
  against the **current** CLI/output (fixtures built from real output) by the python-engineer agent before
  finalizing.
- **ASSUMPTION-002**: The two structural forks (Decisions 1–2) were confirmed by the maintainer on
  2026-07-21; Decisions 3–9 are engineering defaults grounded in this session's vendor research and code
  read; no open questions remain in the source plan.
- **ASSUMPTION-003**: Copilot has no inline `--output-format json` for runs (GitHub `copilot-cli` issue #52
  unshipped), so its only structured usage is the on-disk `session.shutdown` event; the CLI prints the
  session id via `Resume copilot --resume=<uuid>`.
- **ASSUMPTION-004**: The `StageResult.tokens`/`cost` → `progress.md` chain (already threaded by plan 036
  Track E) is intact; this plan hardens the *source* of the value, not the plumbing, so enabling structured
  sources makes the existing chain report correct numbers (Decision 8).
- **ASSUMPTION-005**: Manifest-less backends (`amp`, `qwen`, `cursor-agent`, `auggie`) are out of scope;
  the contract degrades them to `none` (`—`) and wiring their providers is a follow-up (CON-003).

## 8. Related Specifications / Further Reading

- `plan/037-structured-usage-providers.md` — the source plan this implementation plan derives from.
- `plan/036-run-remediation-and-executive-ux.md` and
  `plan/IMPLEMENTATION-007-feature-run-remediation-and-executive-ux.md` — the predecessor whose Track E
  (native token/cost persisted to `progress.md`) this plan corrects and hardens; the copilot regex rot and
  the Claude sub-agent undercount are the two bugs plan 037 fixes.
- `AGENTS.md` — the mandatory intent → plan → implementation plan → implementation workflow, branch/commit
  discipline, python-engineer routing, and open-source-readiness rules.
- `CLAUDE.md` — architecture deep-dive (eight-stage lifecycle, three pillars, trust spine, declarative
  adapter model).
- `docs/cli-reference.md` — the public `3pwr` command surface.
- `docs/STATUS.md` — the single source of truth for implementation status.
- `engine/tests/test_oss_readiness.py` — the enforced open-source-readiness rule for user-facing text.
