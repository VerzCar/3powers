# Plan 037 — Backend-neutral structured token/cost usage providers (Track E hardening)

**Git branch:** `feat/036-run-remediation-and-executive-ux` — authored on the existing branch (the work
corrects and extends plan 036's Track E, which is delivered but unmerged on this branch). No new branch;
the plan file is **not** auto-committed — the maintainer commits.

**Origin.** A live `3pwr run` on the **copilot** backend showed a real token summary in the terminal
(`Tokens ↑ 241.6k (192.8k cached, 46.9k written) • ↓ 5.2k … AI Credits 52.8`) but `progress.md` recorded
`—`. Root cause: the copilot manifest's usage **regex** was written for the CLI's old summary format
(`Tokens ↑ 629.8k (29.5k written) • ↓ 9.2k`) and the CLI drifted — column padding (`Tokens␣␣␣␣␣↑`) and a
new `(… cached, … written)` term both break the pattern (proven: old matches, current is `NO MATCH`). The
drift went uncaught because the only regression test fed a hard-coded *old-format* string, so it never
exercised the current CLI output.

That is a symptom of a deeper design weakness the maintainer flagged: **parsing vendor prose with a regex
is inherently fragile and vendor-specific.** This plan replaces the ad-hoc strategy with a **source-typed,
structured-first `UsageProvider` contract**, migrates every backend that emits structured usage off regex,
gives copilot a structured on-disk source, fixes a **correctness bug** in the shipped Track E (Claude's
token total undercounts sub-agent usage), and adds the per-backend drift guard whose absence let this rot.

**Grounding facts (this session's research + code read).** There is **no universal "ask the CLI for the
tokens" call** — usage is emitted *inline* with a run's structured output, or written to an *on-disk
session file*, or (worst case) only printed as prose. Support falls into three tiers:

| Tier | Backends (that have a manifest today) | Mechanism | Regex droppable |
|---|---|---|---|
| 1 — inline structured | Claude (`--output-format stream-json`), **Codex** (`codex exec --json`), opencode (`run --format json`) | usage in the run's JSON/JSONL event stream | yes |
| 2 — structured, out-of-band | **Copilot** (`~/.copilot/session-state/<id>/events.jsonl` → `session.shutdown`), aider (`--analytics-log`) | read a session file after the run; schema undocumented/version-fragile | via a file provider |
| 3 — regex / none | (cursor-agent has no usage at all; no manifest today) | prose or nothing | no — honest `—` |

Copilot specifically has **no** inline `--output-format json` for runs (GitHub `copilot-cli` issue #52,
unshipped); its only structured usage is the on-disk `session.shutdown` event (or OpenTelemetry, which
needs a collector). Claude's top-level `usage` object **excludes sub-agent tokens**; only `total_cost_usd`
and **`modelUsage`** roll up the whole tree — so with plan 036's Track D (sub-agent models) now shipped,
`progress.md` undercounts tokens on exactly the multi-agent runs sub-agents were built for.

## Tracks

- **Track A — The `UsageProvider` contract.** Replace the manifest's `usage.strategy` with an explicit
  **`usage.source`** taxonomy — `inline-json` · `session-file` · `regex` · `none` — resolved by a single
  provider dispatcher in `agents.py`. Structured-first, backend-neutral, and **honest-unknown**: a backend
  that can produce no reliable count reports `None` (rendered `—`), never a guessed number. (**Decision 1**.)
- **Track B — Tier-1 inline-json migration (drop regex where structured exists).** Move **Codex** off
  regex to `codex exec --json` (its `usage_mode: json` is currently commented out); confirm **opencode**
  reads `run --format json` (`step_finish` events summed); confirm **Claude** stays inline-json. After this,
  regex survives only as an explicit fallback, never a Tier-1 primary.
- **Track C — Tier-2 session-file providers (copilot + aider).** Add a `session-file` source: after a
  dispatch, locate the backend's session artifact and read its structured usage. **Copilot** (the live
  backend, **Decision 2**): capture the session id from the CLI's own `Resume copilot --resume=<uuid>`
  output line (a stable UUID, unlike the drifting token line), read
  `~/.copilot/session-state/<uuid>/events.jsonl`, and take the `session.shutdown` event's usage; **aider**:
  `--analytics --analytics-log <file>` JSONL `message_send` (`prompt_tokens`/`completion_tokens`/`cost`).
  Both parse defensively and are **version-pinned**. The hardened summary-line regex stays as copilot's
  declared fallback (and doubles as the immediate stopgap).
- **Track D — Fix the Claude sub-agent token undercount (shipped-code correctness bug).** Read
  **`modelUsage`** (sum per-model input+output) for the token total instead of the top-level `usage` block;
  keep `total_cost_usd` for cost (it already rolls up). Guarded by a multi-agent fixture. (**Decision 3**.)
- **Track E — Per-backend drift guards + honest-unknown.** Each supported backend gets a committed fixture
  of its **current real output** (or a representative `events.jsonl`) and a test that fails on
  format/schema drift — the regression that was missing. A `none`/unresolved source renders `—` and is
  tested to never fabricate a value. (**Decision 5**.)
- **Track F — Docs.** Document the `usage.source` taxonomy, the per-backend source, the copilot session-file
  dependency + version caveat, and the honest-unknown behavior. Update the manifest header comments to stop
  teaching the fragile-regex-first posture.

### Explicitly out of scope

- **OpenTelemetry as the usage source.** It is the only near-standard cross-vendor path but requires
  running/embedding a collector — too heavyweight for a local run wrapper. Noted as a possible future
  unifying backend, not built here. (**Decision 2** rejected it for now.)
- **Backends without a manifest today** (`amp`, `qwen`, `cursor-agent`, `auggie`). They are named in
  `headless_integrations` but ship no `.3powers/agents/*.yaml`; wiring their providers is a follow-up. The
  contract must simply degrade to `none` (`—`) for any backend whose manifest declares no usable source.
- **Any change to the verdict, ledger schema, exit codes, or `--json` beyond additive token/cost fields.**
  Usage is strictly advisory and never fails a dispatch (unchanged from Track E).

---

## Decisions recorded

Two structural forks were **confirmed by the maintainer on 2026-07-21**; the rest are engineering defaults
grounded in this session's vendor research and code read. **No open questions remain.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Scope of the abstraction | **Full source-typed `UsageProvider`** — user-confirmed. `inline-json`/`session-file`/`regex`/`none`, structured-first, honest-unknown, per-backend drift tests. | Regex-as-primary is inherently vendor-fragile; a declarative source taxonomy makes structured the default and regex an explicit, visible last resort. |
| 2 | Copilot's structured source | **Session file `events.jsonl` → `session.shutdown`** — user-confirmed; regex fallback retained; OTel rejected for now. | Copilot has no inline JSON run output (issue #52). The session id is already printed (`--resume=<uuid>`), so the file is locatable deterministically; OTel needs a collector. |
| 3 | Claude token total | Read **`modelUsage`** (per-model sum), not the top-level `usage` block; `total_cost_usd` for cost. My decision (correctness fix). | The top-level `usage` excludes sub-agent tokens; `modelUsage` and `total_cost_usd` roll up the whole tree. Track D (sub-agents) makes this the common case. |
| 4 | No universal "query usage" command | The contract models **inline event / session file / prose**, not a post-run token query. My decision (grounded). | Research: no vendor exposes a standard post-hoc usage query; usage is inline or in a session artifact. Designing a "request tokens" call would be fiction. |
| 5 | Drift guard is mandatory per backend | Each backend ships a fixture of its **current** output/schema + a test that fails on drift; usage stays advisory (never fails a dispatch). My decision. | The copilot rot happened precisely because the test used a synthetic old-format string. A real-output fixture per backend is the specific fix. |
| 6 | Honest unknown over guess | An unresolved/`none` source renders `—`; a partial/garbled structured payload yields `None`, never a partial guess. My decision. | Usage is advisory; a wrong number is worse than an honest blank, especially for cost. |
| 7 | Session-file parsing is defensive + version-pinned | Copilot/aider file schemas are undocumented; parse tolerantly (missing fields → `None`), pin to a tested CLI version, and document the caveat. My decision. | The vendors do not treat these files as stable public APIs; the parser must never raise and must fail a *test* (not a run) on schema change. |
| 8 | Keep the change additive | The `usage.source` refactor preserves `extract_usage`/`extract_cost` call signatures and the existing `StageResult.tokens`/`cost` → `progress.md` chain; only the resolution *inside* changes. My decision. | Track E already threads tokens+cost end-to-end; this hardens the source, not the plumbing — smallest blast radius. |
| 9 | OSS-readiness | All new manifest comments, help, and docs obey `engine/tests/test_oss_readiness.py`. My decision. | Manifests and docs are user-facing surfaces. |

---

## Why now

1. **A live run recorded `—` for a run that plainly consumed tokens.** The copilot regex in
   `.3powers/agents/copilot.yaml` matches the old format and not the current one (empirically proven this
   session); `agents.extract_usage` (`engine/src/threepowers/agents.py:283`) returns `None`, so
   `progress.py` renders `—`. The engine chain (`runner.py:397` `extract_usage` / `runner.py:401`
   `extract_cost` → `StageResult.tokens`/`cost` → `progress.md`) is otherwise intact.
2. **The failure was silent because the test was synthetic.** `engine/tests/test_native_runner.py:1263`
   feeds a hard-coded old-format line and asserts `38700`; a duplicated old regex sits at
   `test_native_runner.py:1073`. Neither ever saw the current CLI output. A real-output fixture per backend
   is the missing guard.
3. **Codex pays the regex-fragility tax for no reason.** `.3powers/agents/codex.yaml` is `strategy: regex`
   (`pattern: 'tokens used[:\s]+([0-9][0-9,]*)'`) with `usage_mode: json` **commented out**, even though
   `codex exec --json` emits a `turn.completed` event carrying `usage`. It should be Tier-1 inline-json.
4. **Shipped Track E undercounts multi-agent token totals.** `.3powers/agents/claude.yaml` reads
   `fields: [usage.input_tokens, usage.output_tokens]` — the top-level block that, per vendor docs, omits
   sub-agent usage; `total_cost_usd` (also read, via `cost_field`) is correct. With plan 036 Track D
   (sub-agent models) live, the token column is wrong on the very runs that use sub-agents. `modelUsage`
   is the documented whole-tree source.
5. **Copilot can't be made inline-structured — but it can be made structured.** GitHub `copilot-cli` issue
   #52 (inline JSON) never shipped; the `session.shutdown` event in `~/.copilot/session-state/<id>/events.jsonl`
   carries the run's usage, and the session id is already emitted by the CLI (`Resume copilot --resume=<uuid>`),
   so a `session-file` provider is deterministic to wire.

---

## Track A — The `UsageProvider` contract

**Goal.** One declarative, backend-neutral way to obtain a run's tokens and cost, structured-first, with
regex demoted to an explicit last resort and honest-unknown everywhere else.

**Changes (`engine/src/threepowers/agents.py`).**

- Introduce an explicit **`usage.source`** field in the manifest schema: `inline-json` | `session-file` |
  `regex` | `none`. Back-compat: an existing `usage.strategy: json`/`regex` maps to
  `inline-json`/`regex` (accept both during transition; prefer `source`).
- Refactor `extract_usage` (`agents.py:283`) and `extract_cost` (`agents.py:341`) to dispatch on `source`:
  - `inline-json` → today's `_usage_from_json` over the run's JSON lines (fields + optional `subtract`),
    plus the `modelUsage` path for Claude (Track D).
  - `session-file` → a new resolver (Track C) given the dispatch's captured output (to recover the session
    id) and the backend's declared file locator + field paths.
  - `regex` → today's `_usage_from_regex`, explicitly marked fallback.
  - `none` → `None`.
- Keep the **call signatures and the advisory contract** (`agents.py` "never raises; always `Optional`")
  and the downstream chain unchanged (Decision 8): `runner.py:397/401` still call
  `extract_usage`/`extract_cost`; a `session-file` source needs the dispatch output + a way to read the
  file, so thread the necessary context (captured stdout, cwd/home) into the resolver without changing the
  public two-arg helpers used elsewhere (add a thin provider object or an internal overload).

**Acceptance.**

- A manifest with `source: inline-json` and field paths yields the same result as today's `strategy: json`.
- A manifest with `source: none` (or no usable source) yields `None` → `progress.md` shows `—`.
- Legacy `strategy:` manifests keep working (mapped to the new sources) until migrated.

## Track B — Tier-1 inline-json migration

**Goal.** Every backend that emits structured usage inline reads it structurally; regex is no longer a
Tier-1 primary anywhere.

**Changes.**

- **Codex** (`.3powers/agents/codex.yaml` + bundled `engine/src/threepowers/scaffold/agents/codex.yaml`):
  set `source: inline-json`, enable `usage_mode: json` (`codex exec --json`), and set the field paths to
  the actual `turn.completed` usage shape — **verify against the current CLI** whether the fields are
  `usage.input_tokens`/`usage.output_tokens` (nested under the event) vs bare; keep the regex block as a
  declared `regex` fallback, not the primary. Update the header comment.
- **opencode** (`opencode.yaml` + bundled copy): declare `source: inline-json` reading `opencode run
  --format json`; sum `step_finish.part.tokens.{input,output}` across the multiple `step_finish` events and
  read `part.cost` for cost. Note the known "exits before final event" bug in the comment; fall back to
  `none` (`—`) if no event is present.
- **Claude** (`claude.yaml` + bundled): confirm `source: inline-json`; the token field change is Track D.

**Acceptance.**

- A Codex `--json` transcript fixture yields the correct summed tokens (and cost if present) with **no**
  regex involved; the regex fallback only fires if the JSON is absent.
- An opencode `--format json` fixture with multiple `step_finish` events sums correctly.

## Track C — Tier-2 session-file providers (copilot + aider)

**Goal.** Backends with no inline structured output still get **structured** usage from their on-disk
session artifact, deterministically located, defensively parsed, version-pinned — with the hardened regex
as an explicit fallback.

**Changes.**

- **The `session-file` resolver (`agents.py`).** Given the dispatch's captured output and a manifest
  `usage` block declaring `source: session-file`, a `session_id_pattern` (regex capturing the id from the
  CLI output), a `path_template` (e.g. `~/.copilot/session-state/{id}/events.jsonl`), an `event`
  selector (e.g. `session.shutdown`), and token/cost field paths: recover the id, resolve+read the file,
  select the event, extract usage. Missing file / id / fields → `None` (never raises).
- **Copilot** (`.3powers/agents/copilot.yaml` + bundled copy): `source: session-file`; capture the id from
  the `--resume=<uuid>` line (`session_id_pattern`), read `session.shutdown` from
  `~/.copilot/session-state/{id}/events.jsonl` (note the legacy `history-session-state/` path and the
  v0.0.342 path change in the comment). Keep a `fallback: regex` with the **drift-proof** pattern
  `Tokens[^\n]*?↑[^\n]*?([0-9][0-9.,_kKmM]*)\s+written\)[^\n]*?↓[^\n]*?([0-9][0-9.,_kKmM]*)` (validated
  against old + current + ANSI + no-cache). Cost from copilot is premium-request/credits, not USD — record
  tokens; leave cost `—` unless a USD field is present.
- **aider** (`aider.yaml` + bundled): `source: session-file` reading `--analytics --analytics-log <file>`
  (force `--analytics`; sampled off by default) — `message_send` events →
  `properties.{prompt_tokens, completion_tokens}` summed and `properties.{cost|total_cost}` (USD). The
  `--analytics-log <path>` is passed by the engine (a run-scoped temp path); document that this changes the
  aider invocation.

**Acceptance.**

- A copilot `events.jsonl` fixture with a `session.shutdown` event yields the correct tokens; a run whose
  output carries the `--resume=<uuid>` line resolves the right file; a missing/renamed file falls back to
  the hardened regex, and if that also fails, `—`.
- The current live copilot output (`Tokens … (192.8k cached, 46.9k written) … ↓ 5.2k …`) yields `52100` via
  the fallback regex (proving the stopgap works even without the file).
- An aider `--analytics-log` fixture yields tokens **and** USD cost.

## Track D — Fix the Claude sub-agent token undercount

**Goal.** The token total for a Claude dispatch reflects the whole agent tree (sub-agents included).

**Changes.**

- In `agents.py`, for the Claude `inline-json` source, compute tokens from **`modelUsage`** (a per-model
  map in the final `result` event): sum each model's input+output (and, per the manifest's existing
  posture, exclude cache reads consistently). Fall back to the top-level `usage` block only if `modelUsage`
  is absent (older CLI). Keep cost from `total_cost_usd` (already whole-tree-correct).
- Update `.3powers/agents/claude.yaml` (+ bundled) `usage` to point at the `modelUsage` shape (e.g. a
  `source: inline-json` with a `model_usage`-aware field spec) and refresh the header comment describing
  the sub-agent rollup.

**Acceptance.**

- A `stream-json` fixture whose final `result` event has `modelUsage` for two models (a main + a sub-agent
  model) yields the **summed** token total, strictly greater than the top-level `usage` block alone; cost
  equals `total_cost_usd`.
- A fixture without `modelUsage` degrades to the top-level `usage` (older-CLI back-compat).

## Track E — Per-backend drift guards + honest-unknown

**Goal.** A vendor output/schema change fails a **test**, never silently zeroes a run's usage; an
unknowable usage renders `—`.

**Changes.**

- Add a committed fixture per supported backend under `engine/tests/fixtures/usage/` capturing the
  **current** real shape: Claude `stream-json` result (with `modelUsage`), Codex `--json` `turn.completed`,
  opencode `--format json` `step_finish`, copilot `events.jsonl` `session.shutdown` **and** a current
  summary-line sample, aider `--analytics-log` `message_send`.
- A parametrized test asserts each backend's provider extracts the expected tokens/cost from its fixture;
  a companion test asserts a **format-drift** sample (e.g. the old copilot line, a renamed field) does not
  silently succeed with a wrong number.
- A test asserts a `none` source and an unresolved `session-file` both yield `None` → `—`.

**Acceptance.**

- Each backend's fixture test passes; mutating a fixture field name makes the test fail (proving the guard).
- `progress.md` shows a real number for backends with a resolvable source and `—` otherwise — never a
  fabricated value.

## Track F — Docs

- Document the `usage.source` taxonomy and per-backend source in the CLI/observability reference; the
  copilot session-file dependency + the undocumented-schema/version caveat; the honest-`—` behavior; and
  the Claude sub-agent rollup. Update every touched manifest header comment. No internal ids (OSS-readiness).

---

## Cross-cutting requirements & constraints

- **REQ-A**: Usage is resolved by a declarative `usage.source` (`inline-json`/`session-file`/`regex`/`none`);
  structured-first; regex only as a declared fallback; unknown → `None`/`—`, never a guess.
- **REQ-B**: Codex and opencode read structured inline JSON; Claude confirmed inline-json.
- **REQ-C**: Copilot and aider read structured usage from their session file, deterministically located,
  defensively parsed, version-pinned; copilot retains a drift-proof regex fallback.
- **REQ-D**: A Claude dispatch's token total is computed from `modelUsage` (whole-tree); cost from
  `total_cost_usd`.
- **REQ-E**: Every supported backend has a current-output fixture + a drift-failing test; `none`/unresolved
  renders `—`.
- **SEC-001**: Reading a session file must not execute or trust file contents beyond numeric usage fields;
  no path traversal from an untrusted session id (validate the captured id shape before templating a path).
- **CON-001**: The verdict, ledger schema, exit codes, and `--json` are unchanged beyond the additive
  token/cost fields Track E already introduced; usage never fails a dispatch and never raises.
- **CON-002**: The `extract_usage`/`extract_cost` public contract and the `StageResult`→`progress.md` chain
  are preserved (Decision 8).
- **GUD-001**: All new manifest comments, help, and docs pass `engine/tests/test_oss_readiness.py`.
- **GUD-002**: The engine stays green under its own gates (ruff/mypy/pytest + `3pwr gate run --path engine`).

## Testing strategy

- **Track A**: `test_agents.py` — `source` dispatch table (each source → right resolver); legacy
  `strategy:` maps to the new source; `none` → `None`.
- **Track B**: fixtures for Codex `--json` and opencode `--format json`; assert structured extraction with
  no regex; the regex fallback fires only when JSON is absent.
- **Track C**: copilot `events.jsonl` fixture + session-id capture from a `--resume=<uuid>` output sample;
  missing-file fallback to the hardened regex; the current live summary line → `52100`; a path-traversal
  attempt in the captured id is rejected (SEC-001). aider `--analytics-log` fixture → tokens + USD cost.
- **Track D**: `stream-json` fixture with two-model `modelUsage` → summed tokens > top-level `usage`; cost =
  `total_cost_usd`; no-`modelUsage` fixture degrades gracefully.
- **Track E**: parametrized per-backend fixture test; drift samples fail; `none`/unresolved → `—`; replace
  the synthetic old-format assertions in `test_native_runner.py:1073,1263` with fixture-driven ones.
- **Whole engine**: `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green; `test_oss_readiness.py` green.

## Risks & mitigations

- **Session-file schema drift (copilot/aider)** — undocumented, may change. *Mitigation:* defensive parse
  (missing → `None`, never raise), version-pin in the manifest comment, a drift-failing fixture test, and
  the regex fallback for copilot.
- **Session id not in output / wrong session** — the `--resume=<uuid>` line could be absent or ambiguous.
  *Mitigation:* validate the captured id shape; if unresolved, fall back to regex then `—`; never guess a
  file.
- **Codex/opencode field path guessed wrong** — the exact JSON shape must be verified against the current
  CLI. *Mitigation:* build the fixture from real CLI output during implementation; the test pins it.
- **`modelUsage` absent on older Claude** — *Mitigation:* documented fallback to the top-level `usage`.
- **Path traversal from a crafted session id** (SEC-001) — *Mitigation:* accept only a strict UUID for the
  id before templating the path.
- **Regression in the preserved chain** — *Mitigation:* Decision 8 keeps signatures + the
  `StageResult`→`progress.md` path; existing Track E tests must stay green.

## Definition of done

- All six tracks' acceptance criteria pass; the engine is green under its own toolchain and gates.
- A live copilot run records real tokens in `progress.md` (via the session file, or the hardened regex
  fallback); a live Claude multi-agent run records the whole-tree token total and correct cost; Codex runs
  record structured tokens with no regex.
- `docs/` updated in the same unit of work (usage sources, copilot caveat, honest-`—`, Claude rollup).
- No internal ids leak (OSS-readiness green).

---

## Open questions

None — the two structural forks were resolved by the maintainer on 2026-07-21 (Decisions 1–2); the rest are
engineering defaults grounded in this session's vendor research and code read.

## Suggested handover

Next step is the **implementation-plan agent** → `plan/IMPLEMENTATION-008-feature-structured-usage-providers.md`
(phased, file-scoped). Suggested phase order: A (contract) → B (Tier-1 inline-json) → C (session-file
providers) → D (Claude modelUsage fix) → E (drift guards) → Verification. All `engine/` changes go through
the python-engineer agent. Per AGENTS.md the handover is explicit — say the word and I'll dispatch it.
