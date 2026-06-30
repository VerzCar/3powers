# Engine Architecture

How the `3pwr` engine works inside. It's a small Python package (~2,900 lines) under
[`engine/src/threepowers/`](../engine/src/threepowers/), shipped as a `uv` tool. The design goal is a
**language-agnostic core** that drives per-language *adapters* and recovers trust **locally** — no
mandatory CI. Read [Concepts](concepts.md) first for the *why*; this page is the *how*.

## Module map

| Module | Lines | Responsibility |
|---|---|---|
| `cli.py` | 693 | argparse entry point; one `cmd_*` per subcommand. See [CLI Reference](cli-reference.md). |
| `gates.py` | 305 | the gate **orchestrator** — runs the suite cheapest-first, assembles the verdict |
| `characterize.py` | 224 | brownfield: reconstruct a spec + characterization tests from a legacy module (`FR-053`) |
| `conformance.py` | 165 | spec-conformance trace + two-way requirement↔task coverage (`FR-030/015/065`) |
| `covdiff.py` | 154 | diff-coverage: intersect LCOV with the git diff (`FR-029`) |
| `mutation.py` | 151 | mutation gate: run the tool, parse a normalized score, grade vs the tier (`FR-031`) |
| `scanners.py` | 146 | core supply-chain gates: SAST, dependency, secret (`FR-028`) |
| `keys.py` | 145 | Ed25519 signer/verifier identity; key custody outside the repo (`FR-039/NFR-005`) |
| `provenance.py` | 112 | signed build provenance + SBOM; deploy-gate verification (`FR-066–068`) |
| `ledger.py` | 110 | append-only, hash-chained, signed verdict ledger (`FR-038`) |
| `verdict.py` | 105 | the normalized verdict dataclass + gate order (`FR-033/034`) |
| `gaming.py` | 104 | gate-gaming detection (suppressions, deleted assertions) (`FR-035`) |
| `config.py` | 90 | locate the repo root; load `risk-tiers.yaml` / `roles.yaml` (`FR-032/049`) |
| `adapters.py` | 91 | load + run the declarative language adapter manifests (`FR-027/NFR-007`) |
| `lifecycle.py` | 80 | derive the eight-stage state from the ledger (`FR-011/019`) |
| `verify.py` | 77 | recompute the ledger chain + signatures, offline (`FR-040`) |
| `scope.py` | 71 | task requirement-ID + file-scope discipline (`FR-016/017`) |
| `evals.py` | 53 | prompt/constitution eval set; block on regression (`FR-050`) |
| `canonical.py` | 36 | canonical JSON bytes + `sha256:` hashing — the chain's foundation (`NFR-001`) |

The four **High-risk** modules — `canonical`, `keys`, `ledger`, `verify` — are the trust spine; they're
held to the strictest tier and pass their own mutation bar (`NFR-006`).

## The gate pipeline

[`gates.py`](../engine/src/threepowers/gates.py) `run_gates()` is the heart. The flow:

1. **Resolve the tier.** Load [`risk-tiers.yaml`](../.3powers/config/risk-tiers.yaml); the chosen tier's
   `gates:` list is the set of *required* gates and the source of every threshold (`FR-032`). A gate not
   listed for the tier doesn't run.
2. **Resolve the adapter.** Auto-detect (or `--adapter`) the language manifest from
   [`.3powers/adapters/<lang>/adapter.yaml`](../.3powers/adapters/).
3. **Run each required gate in canonical, cheapest-first order** (`verdict.GATE_ORDER`, `FR-026`):
   ```
   format → lint → types → tests → diff_coverage → mutation → sast → dependency_scan → secret_scan → gate_gaming → spec_conformance
   ```
4. **Assemble one normalized verdict** and, unless `--no-ledger`, append a signed entry to the ledger.

Two kinds of gate:

- **Adapter gates** (`format`, `lint`, `types`, `tests`, `mutation`) shell out to the language's declared
  tool and map its exit code (and, for mutation, its score) to a result.
- **Core gates** (`diff_coverage`, `sast`, `dependency_scan`, `secret_scan`, `gate_gaming`,
  `spec_conformance`) are computed by the engine itself, independent of any language (`FR-028`).

This split is what makes 3Powers polyglot: adding a language means adding a manifest, not touching the
core (`NFR-007`). See [`CONTRACT.md`](../.3powers/adapters/CONTRACT.md) for the manifest schema.

### The normalized verdict

Every run emits the same shape regardless of language ([`verdict.py`](../engine/src/threepowers/verdict.py),
`FR-033`), written to `.3powers/verdicts/latest.json` and embedded in the ledger entry. Top-level keys:

```
spec_id, tier, adapter, commit, schema_version, verdict_id, created_at,
result, report_only, gates[], failures[]
```

Each gate carries `{gate, status, tool, duration_ms, details, findings}`. The `result` is `fail` if any
gate failed. Every failure in `failures[]` is **actionable** (`FR-034`): it names a *class*
(`vulnerable_dependency`, `untested_requirement`, `surviving_mutant`, `gate_gaming`, …) and the offending
item, so a human reads it without an agent transcript (`NFR-011`). The schema is versioned (`schema_version`,
`NFR-008`); it's at `1.1` (the `1.1` bump added the additive `report_only` field).

## How each core gate works

### diff-coverage — coverage on *changed* lines only (`FR-029`)

[`covdiff.py`](../engine/src/threepowers/covdiff.py). The adapter's test command emits a standard **LCOV**
report. The core parses it into `{file: {line: hits}}`, computes the lines a change *touched* (`git diff`
added/modified lines, plus whole new files), intersects the two, and reports the covered percentage over
just those lines. Using LCOV (every reference adapter's coverage tool can emit it) keeps this one piece of
core code serving all languages. `--paths` scopes measurement to specific files (per-capability tiers,
spec §4); `--base` sets the diff base.

### spec-conformance — every requirement has a test (`FR-030`)

[`conformance.py`](../engine/src/threepowers/conformance.py). A deterministic, language-agnostic trace:
read the requirement IDs declared in the spec (e.g. `VUTIL-FR-001`), scan the test roots for files that
*mention* each ID, and fail naming any requirement with no linked test. Tests reference a requirement
simply by including its ID in a name or string — `describe("VUTIL-FR-001: rejects empty input", …)`. It
accounts for the unit / integration / e2e layers (`FR-064/065`) and the same module powers two-way
requirement↔task coverage (`coverage-check`, `FR-015`).

### mutation — are the tests actually strong? (`FR-031`)

[`mutation.py`](../engine/src/threepowers/mutation.py). Mutation testing injects small faults
("mutants") into the code and checks the tests *catch* them. The gate runs the adapter's mutation tool
(Python → `mutmut`, TS → Stryker), parses a **normalized score** (`killed / (killed + survived)`), and
compares it to the tier's `mutation_score`. Each surviving mutant is reported as a **missing assertion**
(`FR-034`). The mutated scope is the High-risk files (spec §4); the full sweep is a scheduled concern
(`NFR-002`), so it's opt-in per run via `--mutation`.

> **src-layout note:** `mutmut` 3.x copies the source into a `mutants/` dir and puts `mutants/src` on
> `sys.path`, so the *whole* package must be copied for `import threepowers` to resolve — the
> [`[tool.mutmut]`](../engine/pyproject.toml) config copies the package (`source_paths`) but mutates only
> the four trust-spine files (`only_mutate`). Scoring uses `mutmut results --all true` (the default omits
> killed mutants).

### Supply-chain scanners — SAST, dependency, secret (`FR-028`)

[`scanners.py`](../engine/src/threepowers/scanners.py). Language-agnostic core gates: `semgrep` (SAST
against a local offline ruleset, [`semgrep-rules.yml`](../.3powers/config/semgrep-rules.yml)),
`osv-scanner` (dependency advisories), `gitleaks` (committed secrets). When a tool is **absent**, the gate
is **quarantined** — reported as skipped with a finding, never silently passed (`NFR-015`). Under
`--diff-scope`, the file-based scanners (SAST, secret) only count findings in changed files (`FR-051`).

### gate-gaming — catch the moves that fake green (`FR-035`)

[`gaming.py`](../engine/src/threepowers/gaming.py). Scans the diff and untracked files for the patterns
that make a red gate look green — an inline lint-disable, a `# type: ignore`, a coverage pragma, a deleted
assertion. A hit is a **fail for mandatory human review**, not a silent pass. (The detector uses a
bracketed regex so it doesn't flag its own source — that's how 3Powers gates itself.) Accepting a
legitimate suppression is a recorded *deviation* (roadmap, `FR-057`), not an absorbed one.

## The trust spine

This is the part that "gives trust back" without a CI gatekeeper. Four modules, layered:

### 1. Canonical bytes (`canonical.py`)

The chain's integrity depends on every actor computing **exactly the same bytes** for a payload. So
JSON is serialized with sorted keys, no insignificant whitespace, and UTF-8 (`canonical_bytes`), and
hashed as `sha256:<hex>` (`sha256_hex`). Deterministic regardless of who produced the object (`NFR-001`).

### 2. Independent signer (`keys.py`)

An **Ed25519** identity whose **private key never lives in the repo** (`NFR-005`). Custody resolves in
order: `$THREEPOWERS_SIGNING_KEY_FILE` → `$THREEPOWERS_SIGNING_KEY` (base64 seed) → the default user path
`~/.config/3powers/<repo>.key`. Only the *public* key is committed (`.3powers/keys/ledger.pub`), so
`verify` is fully local and offline.

### 3. The ledger (`ledger.py`)

An append-only JSONL file ([`.3powers/ledger.jsonl`](../.3powers/)). Each entry records one event —
`verdict`, `signoff`, `stage_advance`, `residual`, `reversal`, `abort`, `provenance` — and **chains** to
its predecessor: every entry stores the previous entry's `entry_hash` in `prev_hash`. The signed/chained
bytes are the canonical encoding of the entry *core* (everything except the derived hash/signature
fields), so the hash chain and the signature bind the same content. Committing the ledger keeps the whole
record self-contained and offline-reconstructable (`FR-071`, `NFR-010`).

### 4. verify (`verify.py`)

`verify_ledger()` walks the ledger and fails on **any** tamper, gap, or break (`FR-040`):

1. **sequence** is dense and monotonic from 0 (a deleted/inserted entry breaks it);
2. **chain linkage** — each `prev_hash` matches the predecessor's `entry_hash`;
3. **content** — the recomputed `entry_hash` matches the stored one (a mutated payload won't);
4. **signature** — each entry verifies against the committed public key.

Every problem is reported with its location so a human can find the offending entry. This is
tamper-**evidence**, not tamper-**proofing** (`NFR-013`): evasion is *detectable*, not *impossible*.

### Enforcement, provenance, reversibility

- **`advance`** (in `cli.py`) is the local enforcement gate: it refuses unless the ledger verifies, the
  latest *enforced* verdict is green, and a human sign-off exists at/after that verdict (`FR-041`).
  Report-only verdicts are advisory and never satisfy an advance (`FR-052`).
- **`provenance` / `deploy-gate`** ([`provenance.py`](../engine/src/threepowers/provenance.py)) sign a
  build record binding an artifact (by hash) to its commit/repo/SBOM with the *same* identity, and refuse
  to deploy an artifact whose provenance is missing or invalid (`FR-066–068`).
- **`revert`** appends a signed `reversal` entry returning a spec to a prior recorded stage (`FR-070`) —
  history is reversible, never rewritten.

## Lifecycle, derived

[`lifecycle.py`](../engine/src/threepowers/lifecycle.py) doesn't store stage state anywhere special — it
**derives** the eight-stage position of each spec by replaying the ledger entries (`FR-011`). `3pwr status`
prints it. Because the ledger reconstructs offline, so does the lifecycle.

## Configuration

[`config.py`](../engine/src/threepowers/config.py) walks up from the cwd to find the `.3powers/` root, then
loads the two config files: [`risk-tiers.yaml`](../.3powers/config/risk-tiers.yaml) (the single source of
every threshold, `FR-032/049`) and [`roles.yaml`](../.3powers/config/roles.yaml) (roles → model families,
so `roles-check` can refuse same-family oracle/coder pairs, `FR-022`). Prompts, commands, and the
constitution are themselves treated as versioned software with an eval set
([`evals.py`](../engine/src/threepowers/evals.py), `FR-050`).

## See also

- [CLI Reference](cli-reference.md) · [Concepts](concepts.md) · [Brownfield](brownfield.md)
- [`CONTRACT.md`](../.3powers/adapters/CONTRACT.md) — the adapter manifest schema
- [`trust-spine-tooling.md`](references/trust-spine-tooling.md) — the tool choices behind the gates
- [STATUS](STATUS.md) — what's implemented vs the spec
