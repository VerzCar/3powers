# Engine Architecture

How the `3pwr` engine works inside. It's a small Python package under
[`engine/src/threepowers/`](../engine/src/threepowers/), shipped as a `uv` tool. The design goal is a
**language-agnostic core** that drives per-language *adapters* and recovers trust **locally** — no
mandatory CI. Read [Concepts](concepts.md) first for the *why*; this page is the *how*.

## Module map

| Module | Responsibility |
|---|---|
| `cli/` | the argparse entry point as a package — one module per command group (`keys`, `bootstrap`, `gate`, `trust`, `exceptions`, `oracle`, `observe`, `run`, `supply`, `brownfield`), each owning its `cmd_*` handlers and registering its own subparsers; `cli/__init__.py` assembles the parser and exports `main`. See [CLI Reference](cli-reference.md). |
| `gates.py` | the gate **orchestrator** — runs the suite cheapest-first, assembles the verdict |
| `characterize.py` | brownfield: reconstruct a spec + characterization tests from a legacy module |
| `conformance.py` | the `spec_conformance` trace, two-way requirement↔task coverage, the defect regression gate |
| `covdiff.py` | `diff_coverage`: intersect LCOV with the git diff |
| `mutation.py` | mutation gate: run the tool, parse a normalized score, grade vs the tier |
| `design.py` | design oracles: union the design-oracle gates for a `design` change, quarantine if unwired |
| `workkind.py` | work-kind inference: classify intent into kind(s) + a suggested tier, deterministically |
| `scanners.py` | core supply-chain gates: SAST, dependency, secret |
| `keys.py` | Ed25519 signer/verifier identity; key custody outside the repo |
| `provenance.py` | signed build provenance + SBOM; deploy-gate verification |
| `ledger.py` | append-only, hash-chained, signed verdict ledger |
| `verdict.py` | the normalized verdict dataclass + gate order |
| `gaming.py` | `gate_gaming` detection (suppressions, deleted assertions) |
| `config.py` | locate the repo root; load `risk-tiers.yaml` / `roles.yaml` |
| `adapters.py` | load + run the declarative language adapter manifests |
| `deviations.py` | emergency & deviation logic at the enforcement boundary |
| `lifecycle.py` | derive the eight-stage state from the ledger |
| `verify.py` | recompute the ledger chain + signatures, offline |
| `scope.py` | task requirement-ID + file-scope discipline |
| `evals.py` | prompt/constitution eval set; block on regression |
| `canonical.py` | canonical JSON bytes + `sha256:` hashing — the chain's foundation |

The four **High-risk** modules — `canonical`, `keys`, `ledger`, `verify` — are the trust spine; they're
held to the strictest tier and pass their own mutation bar (the engine gates its own code at the strictest
tier).

## The gate pipeline

[`gates.py`](../engine/src/threepowers/gates.py) `run_gates()` is the heart. The flow:

1. **Resolve the tier.** Load [`risk-tiers.yaml`](../.3powers/config/risk-tiers.yaml); the chosen tier's
   `gates:` list is the set of *required* gates and the source of every threshold. A gate not listed for
   the tier doesn't run. A gate is never satisfied by weakening it.
2. **Shape the set by work-kind.** If the change is classified (by `classify`, `run`, or `--work-kind`),
   the inferred kind(s) *union* extra gates onto the tier's list — a `defect` adds `defect_regression`, a
   `design` change adds the design oracles. Inference only ever adds; it never removes a tier gate.
3. **Resolve the adapter.** Auto-detect (or `--adapter`) the language manifest from
   [`.3powers/adapters/<lang>/adapter.yaml`](../.3powers/adapters/). The manifest's gate commands are
   then assembled into the **effective configuration**: the committed per-project overrides in
   [`.3powers/config/gates.yaml`](../.3powers/config/gates.yaml) win over project-native tooling
   auto-detected at startup (biome/prettier, eslint, tsc/pyright, vitest/jest/playwright, go
   test/gofmt), which wins over the manifest defaults — tools move, gates never do. Inspect it with
   `3pwr gate config show` (see the [CLI reference](cli-reference.md)).
4. **Run each required gate in canonical, cheapest-first order** (`verdict.GATE_ORDER`):
   ```
   format → lint → types → tests → diff_coverage → mutation → sast → dependency_scan → secret_scan →
   gate_gaming → spec_conformance → defect_regression → contract_check → component_contract →
   a11y_scan → visual_regression
   ```
   The trailing gates are **work-kind-shaped**: they run only when the inferred kind pulls them in
   (`defect_regression` for a defect; the four design oracles for design work) and never replace a tier
   gate.
5. **Assemble one normalized verdict** and, unless `--no-ledger`, append a signed entry to the ledger.

Two kinds of gate:

- **Adapter gates** (`format`, `lint`, `types`, `tests`, `mutation`, and the design oracles) shell out to
  the language's declared tool and map its exit code (and, for mutation, its score) to a result.
- **Core gates** (`diff_coverage`, `sast`, `dependency_scan`, `secret_scan`, `gate_gaming`,
  `spec_conformance`, `defect_regression`) are computed by the engine itself, independent of any language.

This split is what makes 3Powers polyglot: adding a language means adding a manifest, not touching the
core. **Go** is now a third reference adapter alongside TypeScript and Python, proving the contract is
truly language-agnostic. See [`CONTRACT.md`](../.3powers/adapters/CONTRACT.md) for the manifest schema.

### The normalized verdict

Every run emits the same shape regardless of language ([`verdict.py`](../engine/src/threepowers/verdict.py)),
written to `.3powers/verdicts/latest.json` and embedded in the ledger entry. Top-level keys:

```
spec_id, tier, adapter, commit, schema_version, verdict_id, created_at,
result, report_only, work_kind[], gates[], failures[]
```

Each gate carries `{gate, status, tool, duration_ms, details, findings}`. The `result` is `fail` if any
gate failed. `work_kind[]` records the inferred kinds that shaped the suite. Every failure in `failures[]`
is **actionable**: it names a *class* (`vulnerable_dependency`, `untested_requirement`,
`surviving_mutant`, `gate_gaming`, `missing_regression_test`, `visual_regression`, `a11y_violation`,
`contract_break`, …) and the offending item, so a human reads it without an agent transcript. The schema
is versioned (`schema_version`).

## How each core gate works

### `diff_coverage` — coverage on *changed* lines only

[`covdiff.py`](../engine/src/threepowers/covdiff.py). The adapter's test command emits a standard **LCOV**
report. The core parses it into `{file: {line: hits}}`, computes the lines a change *touched* (`git diff`
added/modified lines, plus whole new files), intersects the two, and reports the covered percentage over
just those lines. Using LCOV (every reference adapter's coverage tool can emit it) keeps this one piece of
core code serving all languages. `--paths` scopes measurement to specific files (risk-tier scoping per
capability); `--base` sets the diff base.

### `spec_conformance` — every requirement has a test

[`conformance.py`](../engine/src/threepowers/conformance.py). A deterministic, language-agnostic trace:
read the requirement IDs declared in the spec (e.g. `DEMO-FR-001`), scan the test roots for files that
*mention* each ID, and fail naming any requirement with no linked test. Tests reference a requirement
simply by including its ID in a name or string — `describe("DEMO-FR-001: rejects empty input", …)`. It
accounts for the unit / integration / e2e layers (each tier declares the layers a change must exercise)
and the same module powers two-way requirement↔task coverage (`coverage-check`).

### defect regression — a fix must ship a failing regression test

[`conformance.py`](../engine/src/threepowers/conformance.py) `regression_gate()`. Added to the suite only
when the change is classified as a **defect**. Deterministically (no model call), it looks for a test that
is *marked* as a regression — by file name (`*regression*` / `*reproduce*`) or an inline mention — **and**
references a requirement id of this spec, so it is traceable to the defect it guards. A defect fix with no
such test fails with the class `missing_regression_test`. The idea is the classic discipline: reproduce
the bug with a test that fails before the fix, then make it pass.

### design oracles — how *design* work is judged

[`design.py`](../engine/src/threepowers/design.py). When a change is classified as **design**, the engine
unions a set of **design-oracle gates** onto the tier's set: `contract_check` (API/schema contract),
`component_contract` (component props/events), `a11y_scan` (accessibility), `visual_regression` (rendered
output vs an approved baseline). Which oracles apply is a config catalog
([`.3powers/config/design-oracles.yaml`](../.3powers/config/design-oracles.yaml)); the *tool* for each is
**adapter-supplied**, keeping the core language-agnostic. A selected oracle the adapter doesn't declare —
or whose tool isn't installed — is **quarantined** (reported `skip` with a surfaced finding), never
silently passed. An adapter for a non-UI language may declare none, and design runs then quarantine every
oracle rather than fake a pass.

### mutation — are the tests actually strong?

[`mutation.py`](../engine/src/threepowers/mutation.py). Mutation testing injects small faults
("mutants") into the code and checks the tests *catch* them. The gate runs the adapter's mutation tool
(Python → `mutmut`, TS → Stryker, Go → go-mutesting), parses a **normalized score**
(`killed / (killed + survived)`), and compares it to the tier's `mutation_score`. Each surviving mutant is
reported as a **missing assertion**. The mutated scope is the trust-critical files under risk-tier
scoping; the full sweep is a scheduled concern, so it's opt-in per run via `--mutation`.

> **src-layout note:** `mutmut` 3.x copies the source into a `mutants/` dir and puts `mutants/src` on
> `sys.path`, so the *whole* package must be copied for `import threepowers` to resolve — the
> [`[tool.mutmut]`](../engine/pyproject.toml) config copies the package (`source_paths`) but mutates only
> the four trust-spine files (`only_mutate`). Scoring uses `mutmut results --all true` (the default omits
> killed mutants).

### Supply-chain scanners — SAST, dependency, secret

[`scanners.py`](../engine/src/threepowers/scanners.py). Language-agnostic core gates: `semgrep` (SAST
against a local offline ruleset, [`semgrep-rules.yml`](../.3powers/config/semgrep-rules.yml)),
`osv-scanner` (dependency advisories), and for committed secrets **betterleaks** — a maintained Gitleaks
successor — with **gitleaks** as the fallback. When a tool is **absent**, the gate is **quarantined** —
reported as skipped with a finding, never silently passed. Under `--diff-scope`, the file-based scanners
(SAST, secret) only count findings in changed files.

### `gate_gaming` — catch the moves that fake green

[`gaming.py`](../engine/src/threepowers/gaming.py). Scans the diff and untracked files for the patterns
that make a red gate look green — an inline lint-disable, a `# type: ignore`, a coverage pragma, a deleted
assertion. A hit is a **fail for mandatory human review**, not a silent pass. (The detector uses a
bracketed regex so it doesn't flag its own source — that's how 3Powers gates itself.) Accepting a
legitimate suppression is a recorded, signed, reversible gate exception, not an absorbed one.

## The trust spine

This is the part that "gives trust back" without a CI gatekeeper. Four modules, layered:

### 1. Canonical bytes (`canonical.py`)

The chain's integrity depends on every actor computing **exactly the same bytes** for a payload. So
JSON is serialized with sorted keys, no insignificant whitespace, and UTF-8 (`canonical_bytes`), and
hashed as `sha256:<hex>` (`sha256_hex`). Deterministic regardless of who produced the object.

### 2. Independent signer (`keys.py`)

An **Ed25519** identity whose **private key never lives in the repo**. Custody resolves in order:
`$THREEPOWERS_SIGNING_KEY_FILE` → `$THREEPOWERS_SIGNING_KEY` (base64 seed) → the default user path
`~/.config/3powers/<repo>.key`. Only the *public* key is committed (`.3powers/keys/ledger.pub`), so
`verify` is fully local and offline.

### 3. The ledger (`ledger.py`)

An append-only JSONL file ([`.3powers/ledger.jsonl`](../.3powers/)). Each entry records one event —
`verdict`, `signoff`, `stage_advance`, `residual`, `reversal`, `abort`, `provenance` — and **chains** to
its predecessor: every entry stores the previous entry's `entry_hash` in `prev_hash`. The signed/chained
bytes are the canonical encoding of the entry *core* (everything except the derived hash/signature
fields), so the hash chain and the signature bind the same content. Committing the ledger keeps the whole
record self-contained and offline-reconstructable.

### 4. verify (`verify.py`)

`verify_ledger()` walks the ledger and fails on **any** tamper, gap, or break:

1. **sequence** is dense and monotonic from 0 (a deleted/inserted entry breaks it);
2. **chain linkage** — each `prev_hash` matches the predecessor's `entry_hash`;
3. **content** — the recomputed `entry_hash` matches the stored one (a mutated payload won't);
4. **signature** — each entry verifies against the committed public key.

Every problem is reported with its location so a human can find the offending entry. This is
tamper-**evidence**, not tamper-**proofing**: evasion is *detectable*, not *impossible*.

### Enforcement, provenance, reversibility

- **`advance`** (in the `cli/` package's trust module) is the local enforcement gate: it refuses unless the ledger verifies, the
  latest *enforced* verdict is green, and a human sign-off exists at/after that verdict. Report-only
  verdicts are advisory and never satisfy an advance.
- **`deviation` / `emergency`** ([`deviations.py`](../engine/src/threepowers/deviations.py)) bend the
  process without breaking it. Deviations act at the **enforcement boundary**, not in the verdict — gates
  run honestly; a signed, reversible `deviation` ledger entry lets `advance` accept specific named red
  gates (including a `gate_gaming` flag), and the constrained `emergency` profile defers only
  mutation+coverage with a one-day cleanup that `advance` enforces.
- **`provenance` / `deploy-gate`** ([`provenance.py`](../engine/src/threepowers/provenance.py)) sign a
  build record binding an artifact (by hash) to its commit/repo/SBOM with the *same* identity, and refuse
  to deploy an artifact whose provenance is missing or invalid.
- **`revert`** appends a signed `reversal` entry returning a spec to a prior recorded stage — history is
  reversible, never rewritten.

## Session freshness and cost visibility

**Every dispatched stage and phase is a fresh agent session.** The native executive
([`runner.py`](../engine/src/threepowers/runner.py)) builds each invocation from the agent manifest
alone and runs it as an independent external process — no conversation state is carried between
dispatches, and the engine never emits a resume/continue/session-reuse flag. Each session's prompt
*reloads* everything it needs (the approved spec, the constitution/rules, the phase's tasks and file
scope), so correctness never depends on a backend remembering anything. For a backend whose CLI could
restore prior state, the manifest's `new_session_args` field passes the CLI's no-resume/new-session
flag(s) on every invocation, making the clean session explicit rather than assumed.

Per-backend session behavior of the shipped reference manifests (from each CLI's documented
non-interactive conventions):

| Backend | Invocation | Clean session by default? | Reuse is opt-in via (never emitted) | Manifest hook |
|---|---|---|---|---|
| Claude Code | `claude -p "<prompt>"` | yes — each `-p` call starts a new session | `--continue` / `--resume` | none needed |
| Copilot CLI | `copilot -p "<prompt>"` | yes — new session per invocation | `--resume` / `--continue` | none needed |
| Codex CLI | `codex exec` | yes — `exec` is a fresh non-interactive run | `codex exec resume` | none needed |
| OpenCode | `opencode run` | yes — new session per `run` | `--session` / `--continue` | none needed |
| Aider | `aider --message` | yes — history restore is opt-in (default off), but chat history *is* persisted to `.aider.chat.history.md` | `--restore-chat-history` | `new_session_args: ["--no-restore-chat-history"]` makes freshness explicit |
| Hosted (async) | manifest-declared trigger/poll/collect | yes — each trigger starts a new hosted run | n/a | none needed |

**`[P]` parallelism is two-level.** Whole phases marked `[P]` with disjoint declared file scopes are
dispatched by the *engine* as concurrent, separate fresh sessions
([`phases.py`](../engine/src/threepowers/phases.py) `schedule`/`run_phases`). *Inside* a phase, tasks
marked `[P]` must be executed via the agent's **own sub-agents** — the phase handoff prompt and the
implement agent template both mandate it — so intra-phase parallelism happens in the agent's runtime,
never by the engine splitting a phase.

**Token consumption is captured advisorily.** A manifest's optional `usage` hint declares how the
backend reports usage in its output — `strategy: json` (a dotted field read from the last JSON output
line) or `strategy: regex` (group 1 of a pattern match). The extracted per-stage/per-phase token
counts ride as strictly **additive** fields: `tokens` on the `--json` per-stage results, on the signed
`run`/`stage`, `run`/`phases` (per phase result), and `run`/`checkpoint` ledger payloads, and a Tokens
column in `progress.md`. A backend that reports no usage reads as unknown (the fields stay absent; the
column shows `—`). Tokens never enter the gate suite, the verdict, or the verdict bytes — the
deterministic verdict is byte-identical whether or not usage was captured.

## Lifecycle, derived

[`lifecycle.py`](../engine/src/threepowers/lifecycle.py) doesn't store stage state anywhere special — it
**derives** the eight-stage position of each spec by replaying the ledger entries. `3pwr status` prints
it. Because the ledger reconstructs offline, so does the lifecycle.

## Configuration

[`config.py`](../engine/src/threepowers/config.py) walks up from the cwd to find the `.3powers/` root, then
loads the config files: [`risk-tiers.yaml`](../.3powers/config/risk-tiers.yaml) (the single source of
every threshold), [`roles.yaml`](../.3powers/config/roles.yaml) (roles → model families, so `roles-check`
can refuse same-family oracle/coder pairs — oracle model diversity), and, for design work, the
design-oracle catalog [`design-oracles.yaml`](../.3powers/config/design-oracles.yaml). Prompts, commands,
and the constitution are themselves treated as versioned software with an eval set
([`evals.py`](../engine/src/threepowers/evals.py)).

## See also

- [CLI Reference](cli-reference.md) · [Concepts](concepts.md) · [Brownfield](brownfield.md)
- [`CONTRACT.md`](../.3powers/adapters/CONTRACT.md) — the adapter manifest schema
- [`trust-spine-tooling.md`](references/trust-spine-tooling.md) — the tool choices behind the gates
- [STATUS](STATUS.md) — what's implemented vs the spec
