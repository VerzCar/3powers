# CLI Reference — `3pwr`

The complete `3pwr` command surface. Generated from and kept in sync with the engine's argparse
definitions ([`cli.py`](../engine/src/threepowers/cli.py)). For a guided walkthrough see
[Getting Started](getting-started.md); for what each gate does see [Engine Architecture](engine-architecture.md).

## Global

```
3pwr [--version] [--root ROOT] <command> [options]
```

- `--root ROOT` — repository root (defaults to discovery: walks up from the cwd to the `.3powers/` dir).
- `--json` — every command accepts `--json` for machine-readable output (the same artifact agents consume).

**Exit codes** (uniform across commands): `0` ok / green · `1` gate failed, verification failed, or
advance refused · `2` usage or environment error (e.g. no signing key, unknown tier).

---

## Setup

### `keygen` — create the independent signer identity
Creates an Ed25519 key pair. The **private key is written outside the repo**; the public key is committed
(`3PWR-NFR-005`).
- `--out OUT` — private-key path (default: `~/.config/3powers/<repo>.key`).
- `--force` — overwrite an existing key.
```bash
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

### `init` — ensure the `.3powers/` layout exists
Creates the trust-spine directory skeleton (config, schemas, adapters, keys, verdicts, runs, empty ledger).
```bash
3pwr init
```

---

## Gates & verification

### `gate run` — run the deterministic gate suite
Runs the tier's gates cheapest-first, emits one normalized verdict, and (unless `--no-ledger`) appends a
signed ledger entry (`3PWR-FR-026/033`).
- `--path PATH` — target project (default: repo root).
- `--tier TIER` — `Cosmetic` | `Standard` | `High-risk` (default: `Standard`).
- `--adapter ADAPTER` — language adapter (default: auto-detect).
- `--spec SPEC` — path to the governing `spec.md`.
- `--base BASE` — git ref for the diff-coverage / diff-scope base.
- `--mutation` — run the (expensive) mutation gate; opt-in (`3PWR-FR-031`, `NFR-002`).
- `--paths [PATHS ...]` — scope diff-coverage + mutation to these files (per-capability tier, spec §4).
- `--report-only` — emit the verdict but **do not block** (exit 0 even on red); brownfield (`3PWR-FR-052`).
- `--diff-scope` — block only on files changed vs `--base` (brownfield, `3PWR-FR-051`).
- `--no-ledger` — run without appending a ledger entry.
```bash
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
```
Exit `0` if the verdict is green, `1` if red (unless `--report-only`).

### `conformance` — spec-conformance trace only
Checks every requirement in a spec has a linked test, without running the full suite (`3PWR-FR-030`).
- `--spec SPEC` · `--tests [TESTS ...]` — test roots to scan.
```bash
3pwr conformance --spec specs/002-engine-trust-spine/spec.md --tests engine/tests engine/src
```

### `verify` — verify the ledger (offline)
Recomputes the hash chain + signatures; fails on any tamper, gap, or break (`3PWR-FR-040`). No flags.
```bash
3pwr verify        # → ledger OK — N entries, chain and signatures intact
```

---

## Lifecycle & enforcement

### `signoff` — record a signed human sign-off
Appends a signed `signoff` entry (`3PWR-FR-037`).
- `--approver APPROVER` (required) · `--stage STAGE` (default `review`) · `--note NOTE` · `--spec-id SPEC_ID`.
```bash
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
```

### `advance` — local enforcement gate
Refuses to advance unless the ledger verifies, the latest *enforced* verdict is green **(or every red gate
is covered by an active deviation)**, and a human sign-off exists at/after it (`3PWR-FR-041/042/057`).
Report-only verdicts don't count, and an overdue emergency cleanup blocks the advance (`3PWR-FR-056`).
- `--stage STAGE` (required) · `--spec-id SPEC_ID`.
```bash
3pwr advance --stage ship --spec-id VUTIL
```
Exit `1` (refused) with reasons, or `0` and a signed `stage_advance` entry (which records any
`deviations_applied`).

### `status` — per-spec lifecycle stage
Derives the eight-stage position of each spec from the ledger (`3PWR-FR-011`).
- `--spec-id SPEC_ID` — filter to one spec.
```bash
3pwr status
```

### `revert` — reverse to a prior recorded state
Appends a signed `reversal` entry returning a spec to its stage at a given ledger seq (`3PWR-FR-070`).
- `--to TO` (required, ledger seq) · `--reason REASON`.
```bash
3pwr revert --to 3 --reason "back out the bad ship"
```

### `abort` — record an abort for a spec's run
- `--spec-id SPEC_ID` (required) · `--reason REASON`.
```bash
3pwr abort --spec-id VUTIL --reason "superseded"
```

---

## Off the happy path (emergency & deviation)

Both paths are **signed, recorded, and reversible** — bending the process without breaking it (spec §14).
They act at the `advance` enforcement boundary; gates always run honestly, so the verdict stays
deterministic. See [Concepts → emergencies & deviations](concepts.md).

### `deviation` — relax named gates, reversibly
Records a signed deviation that lets `advance` accept specific red gates, with a reason, a human approver,
and a way back (an expiry or an explicit revoke). Also the **sanctioned way to accept a `gate_gaming`
flag** (`3PWR-FR-035/057`). Human sign-off and provenance are never deviatable.
- `--gate GATE` (repeatable; required unless `--revoke`) · `--approver APPROVER` (required to record) ·
  `--note NOTE` (reason) · `--until ISO8601` (auto-expiry) · `--revoke SEQ` (the way back) · `--spec-id SPEC_ID`
  (scope; default global).
```bash
# accept a specific red gate, tracked as a follow-up, until a date
3pwr deviation --gate dependency_scan --approver "$(git config user.name)" \
               --note "GHSA-… waiting on upstream fix" --until 2026-07-15T00:00:00Z --spec-id VUTIL
# the way back
3pwr deviation --revoke 7
```

### `emergency` — the constrained fast path
Opens an emergency deviation that may defer **only mutation + diff-coverage**; it never relaxes the
security/secret gates, sign-off, or provenance, and it sets a one-working-day cleanup deadline. `advance`
refuses while that cleanup is overdue (`3PWR-FR-056`).
- `--approver APPROVER` (required) · `--note NOTE` (reason) · `--cleanup-hours N` (default 24) · `--spec-id SPEC_ID`.
```bash
3pwr emergency --approver "$(git config user.name)" --note "prod down — hotfix" --spec-id VUTIL
# …ship the fix, then clean up within a day:
3pwr deviation --revoke <seq>
```
Active deviations and overdue cleanups are surfaced by `3pwr status`.

---

## Planning discipline

### `coverage-check` — two-way requirement↔task coverage
Every requirement maps to ≥1 task and every task traces to a requirement, *before* code (`3PWR-FR-015`).
- `--spec SPEC` · `--tasks TASKS` (required).
```bash
3pwr coverage-check --spec specs/003-x/spec.md --tasks specs/003-x/tasks.md
```

### `scope-check` — task req-id + file-scope discipline
Fails a task line with no requirement ID, and flags edits outside a task's declared file scope
(`3PWR-FR-016/017`).
- `--tasks TASKS` (required) · `--base BASE` · `--path PATH`.
```bash
3pwr scope-check --tasks specs/003-x/tasks.md --base main
```

---

## Trust artifacts

### `provenance` — sign build provenance + SBOM
Signs a record binding an artifact (by hash) to its commit/repo/SBOM, with the same identity as the
ledger (`3PWR-FR-066/068`).
- `--artifact ARTIFACT` (required) · `--path PATH` (SBOM project dir) · `--spec-id SPEC_ID`.
```bash
3pwr provenance --artifact dist/app.tar.gz --path .
```

### `deploy-gate` — verify an artifact's provenance
Refuses an artifact whose provenance is missing or invalid (`3PWR-FR-067`).
- `--artifact ARTIFACT` (required).
```bash
3pwr deploy-gate --artifact dist/app.tar.gz
```

### `residual` — record a signed residual review
The post-gate review by a different model family, scoped to what gates can't catch (`3PWR-FR-036`).
- `--reviewer REVIEWER` (required) · `--note NOTE` · `--findings [FINDINGS ...]` · `--spec-id SPEC_ID`.
```bash
3pwr residual --reviewer claude-opus --note "intent fit OK" --spec-id VUTIL
```

---

## Brownfield

### `characterize` — reconstruct a spec + pin a legacy module
Reconstructs a spec stub and scaffolds runnable characterization tests that pin a legacy module's current
behavior as its oracle (`3PWR-FR-053`). Works without a pre-existing `.3powers/`. See
[Brownfield Adoption](brownfield.md).
- `--module MODULE` (required) · `--specs SPECS` (default `<root>/specs`) · `--tests TESTS` (default:
  alongside the module).
```bash
3pwr characterize --module src/legacy/money.py
```

---

## Config & quality

### `eval` — run the prompt/constitution eval set
Treats prompts/commands/constitution as versioned software; blocks on regression (`3PWR-FR-050`).
- `--cases CASES` (default `.3powers/eval/cases.yaml`).
```bash
3pwr eval
```

### `roles-check` — model-family diversity between two roles
Fails if two roles resolve to the same model family (enforces oracle independence, `3PWR-FR-022`).
- `--role-a ROLE_A` (default `oracle`) · `--role-b ROLE_B` (default `coder`).
```bash
3pwr roles-check --role-a oracle --role-b coder
```

### `ledger show` — print the ledger
```bash
3pwr ledger show        # one line per entry: seq, type, timestamp, spec, signer
```

---

See also: [Getting Started](getting-started.md) · [Engine Architecture](engine-architecture.md) ·
[Concepts](concepts.md) · [`AGENTS.md`](../AGENTS.md) (the same commands as a quick table).
