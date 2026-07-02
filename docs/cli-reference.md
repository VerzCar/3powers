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
Creates an Ed25519 key pair. The **private key is written outside the repo**; the public key is committed.
- `--role ROLE` — `ledger` (default) or `oracle` (a distinct signer for the judiciary).
- `--out OUT` — private-key path (default: `~/.config/3powers/<repo>.key`).
- `--force` — overwrite an existing key.
```bash
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

### `init` — guided onboarding (new or existing project)
Makes a project 3Powers-ready in one step: creates the `.3powers/` layout, an independent signer
(**outside the repo**), the baseline config, and the adapter for your chosen language, then prints
greenfield-vs-brownfield next steps. Interactive by default; falls back to defaults with no TTY.
- `--yes` — non-interactive: prompt for nothing and apply the documented defaults (CI-friendly).
- `--language LANG` — the language adapter to set up (default: auto-detected, else the first supported).
- `--key-path PATH` — signing-key location; **must be outside the repo** (default: `~/.config/3powers/<repo>.key`, with `~/.ssh/` offered interactively).
- `--auto-mode` / `--no-auto-mode` — record whether `3pwr run` defaults to autonomous mode (advisory; never bypasses a human gate).
- `--force` — overwrite an existing signing key (default: keep it).
- `--skeleton-only` — only create the directory layout (the pre-wizard behaviour).
- `--json` — machine-readable summary of what was created vs kept.
```bash
3pwr init                       # guided
3pwr init --yes --language typescript   # non-interactive, e.g. in CI
```
`init` is idempotent — re-running preserves your ledger, keys, and hand-edited config.

---

## Gates & verification

### `gate run` — run the deterministic gate suite
Runs the tier's gates cheapest-first, emits one normalized verdict, and (unless `--no-ledger`) appends a
signed ledger entry.
- `--path PATH` — target project (default: repo root).
- `--tier TIER` — `Cosmetic` | `Standard` | `High-risk` (default: `Standard`).
- `--adapter ADAPTER` — language adapter (default: auto-detect).
- `--spec SPEC` — path to the governing `spec.md`.
- `--base BASE` — git ref for the diff-coverage / diff-scope base.
- `--mutation` — run the (expensive) mutation gate; opt-in.
- `--paths [PATHS ...]` — scope diff-coverage + mutation to these files (risk-tier scoping per capability).
- `--work-kind KIND` — the kind of change (`defect`, `design`, `feature`, `docs`, `refactor`, `chore`);
  repeatable, and usually inferred by `classify`. A `defect` adds the **regression gate**; `design` unions
  the **design oracles** onto the tier's set (see below). Kinds only ever *add* gates, never remove one.
- `--report-only` — emit the verdict but **do not block** (exit 0 even on red); brownfield.
- `--diff-scope` — block only on files changed vs `--base` (brownfield).
- `--no-ledger` — run without appending a ledger entry.
```bash
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
```
Exit `0` if the verdict is green, `1` if red (unless `--report-only`).

**Work-kind-shaped gates.** When a change is classified (by `classify`, `run`, or an explicit
`--work-kind`), the inferred kind adds gates to the tier's set:
- **defect** → `defect_regression`: a defect fix must ship a **failing regression test** — a test marked
  `*regression*`/`*reproduce*` (by file name or body) that references the defect's requirement id and
  fails before the fix. Missing it is the failure class `missing_regression_test`.
- **design** → the **design oracles** `contract_check`, `component_contract`, `a11y_scan`,
  `visual_regression` (from `.3powers/config/design-oracles.yaml`). Each oracle's tool is
  adapter-supplied; if the adapter doesn't declare it, or the tool isn't installed, the oracle is
  **quarantined** — reported `skip` with a surfaced finding, never silently passed.

### `conformance` — spec-conformance trace only
Checks every requirement in a spec has a linked test, without running the full suite.
- `--spec SPEC` · `--tests [TESTS ...]` — test roots to scan.
```bash
3pwr conformance --spec specs/002-engine-trust-spine/spec.md --tests engine/tests engine/src
```

### `verify` — verify the ledger (offline)
Recomputes the hash chain + signatures; fails on any tamper, gap, or break. No flags.
```bash
3pwr verify        # → ledger OK — N entries, chain and signatures intact
```

---

## Oracle independence (Phase A / judiciary)

Moves oracle independence from procedural to **structurally attested** — the judiciary authors from a
sealed, spec-only bundle, and independence is proven from the signed ledger. The binding check runs at
`advance` under **risk-tier scoping** (High-risk); detection that the author *touched/read* the
implementation is an **advisory** flag surfaced for review, never a blocker.

### `oracle seal` — seal a spec-only bundle
Extracts the acceptance criteria (requirement IDs + text — no impl/plan/tasks/contracts) to
`.3powers/oracle/<spec-id>/sealed.json`, hashed with a re-seal-stable content hash, and records a signed
`oracle` seal entry.
- `--spec SPEC` · `--spec-id SPEC_ID`.
```bash
3pwr oracle seal --spec specs/001-validation-utils/spec.md --spec-id VUTIL
```

### `oracle record` — record oracle authoring
Records the authoring event, bound to the sealed bundle: the model actually used, the oracle test files
(hashed), and any advisory peek/touch findings. **Refuses** when the oracle's model family equals the
coder's, checking the model actually recorded (oracle model diversity — a different model family than the
coder).
- `--spec-id SPEC_ID` (required) · `--model FAMILY/MODEL` (required) · `--tests PATHS…` (required) ·
  `--base BASE` (git ref for the touched-implementation advisory scan).
```bash
3pwr oracle record --spec-id VUTIL --model anthropic/claude-opus \
                   --tests examples/validation-utils/tests/unit/validators.test.ts
```

### `oracle verify` — verify independence from the ledger
Checks seal-binding, model-family diversity, Phase-A-before-B ordering (by ledger seq, not git time), and
one oracle test per criterion; prints advisory findings too. With `--require-dispatch`, also confirms the
oracle was authored via a read-path-isolated headless dispatch. Exit `1` if the structural check fails.
- `--spec-id SPEC_ID` (required) · `--tests [ROOTS …]` (default: the recorded oracle test paths) ·
  `--require-dispatch` (also require an isolated dispatch attestation).
```bash
3pwr oracle verify --spec-id VUTIL
```

### `oracle dispatch` — author the oracle headlessly, read-path isolated
Authors the oracle **headlessly** (via `specify workflow run`) under a non-coder integration inside a
**sanitized git worktree** where the implementation, plan, tasks, and contracts are physically absent —
attested by a worktree manifest hash recorded in the ledger. This is the physical read-path isolation
behind oracle sealing; it never enters the deterministic verdict.
- `--spec-id SPEC_ID` (required) · `--integration INTEGRATION` (the headless CLI, e.g. `claude`) ·
  `--model FAMILY/MODEL` (override the resolved oracle model) · `--workflow WORKFLOW` · `--base BASE`
  (clean git ref for the worktree, default `HEAD`) · `--tests [PATHS …]` · `--dry-run` (build + attest
  isolation offline, no model call) · `--keep-worktree` (leave the sanitized worktree in place).
```bash
3pwr oracle dispatch --spec-id VUTIL --integration claude
```

---

## Lifecycle & enforcement

### `signoff` — record a signed human sign-off
Appends a signed `signoff` entry.
- `--approver APPROVER` (required) · `--stage STAGE` (default `review`) · `--note NOTE` · `--spec-id SPEC_ID`.
```bash
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
```

### `advance` — local enforcement gate
Refuses to advance unless the ledger verifies, the latest *enforced* verdict is green **(or every red gate
is covered by an active deviation)**, and a human sign-off exists at/after it. Report-only verdicts don't
count, and an overdue emergency cleanup blocks the advance. Under **risk-tier scoping** (High-risk) it
additionally requires oracle independence — a sealed spec-only bundle, an authoring record in a different
model family than the coder, authored *before* the implementation verdict. Advisory peek/touch findings
are surfaced but never block.
- `--stage STAGE` (required) · `--spec-id SPEC_ID`.
```bash
3pwr advance --stage ship --spec-id VUTIL
```
Exit `1` (refused) with reasons, or `0` and a signed `stage_advance` entry (which records any
`deviations_applied`).

### `status` — per-spec lifecycle stage
Derives the eight-stage position of each spec from the ledger.
- `--spec-id SPEC_ID` — filter to one spec.
```bash
3pwr status
```

### `classify` — infer the kind(s) of change + a suggested tier
Classifies free-form intent into work kind(s) (`defect`, `design`, `feature`, `docs`, `refactor`, `chore`)
and a suggested risk tier, **deterministically** — offline keyword heuristics, no model call. The
inference *shapes* the gate set and the oracle strategy (a `defect` pulls in the regression gate; `design`
pulls in the design oracles) but **never** bypasses the human sign-off.
- `intent` (positional, required) — the free-form intent to classify.
```bash
3pwr classify "fix the off-by-one in the checkout total"
# → work kind(s): defect  |  suggested tier: High-risk
```

### `run` — drive the whole lifecycle in one command
Drives the eight-stage lifecycle by composing Spec Kit's `workflow run`, streaming a live stage tracker
(the engine makes no model call itself). `auto` mode auto-approves the intermediate review gates and
**stops only at the two mandatory human gates** — spec approval and sign-off; `commit` mode stops at every
gate. It first classifies the intent and carries the inferred work-kind into the run so the verify step
shapes the gate suite. Sign-offs and progress are recorded in the ledger, so a run is resumable; a red
verdict stops the run, `--notify`s, and suggests `observe signal`.
- `intent` (positional) · `--mode auto|commit` · `--integration INTEGRATION` · `--spec-id SPEC_ID`
  (run id, default `RUN`) · `--workflow WORKFLOW` · `--notify CMD` (best-effort notification hook) ·
  `--resume` (record a sign-off + continue after a human gate) · `--status` (print the stage tracker) ·
  `--dry-run` (simulate offline) · `--simulate-fail` (force a red verdict, for `--dry-run`) ·
  `--no-input` (never prompt) · `--approver APPROVER` · `--note NOTE`.
```bash
3pwr run "add IBAN validation to the address form" --mode auto
3pwr run --resume --spec-id RUN --approver "$(git config user.name)"
3pwr run --status --spec-id RUN
```

### `revert` — reverse to a prior recorded state
Appends a signed `reversal` entry returning a spec to its stage at a given ledger seq.
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

Both paths are **signed, recorded, and reversible** — bending the process without breaking it. They act
at the `advance` enforcement boundary; gates always run honestly, so the verdict stays deterministic. See
[Concepts → emergencies & deviations](concepts.md).

### `deviation` — relax named gates, reversibly
Records a signed, reversible gate exception that lets `advance` accept specific red gates, with a reason, a
human approver, and a way back (an expiry or an explicit revoke). Also the **sanctioned way to accept a
`gate_gaming` flag**. Human sign-off and provenance are never deviatable.
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
refuses while that cleanup is overdue.
- `--approver APPROVER` (required) · `--note NOTE` (reason) · `--cleanup-hours N` (default 24) · `--spec-id SPEC_ID`.
```bash
3pwr emergency --approver "$(git config user.name)" --note "prod down — hotfix" --spec-id VUTIL
# …ship the fix, then clean up within a day:
3pwr deviation --revoke <seq>
```
Active deviations and overdue cleanups are surfaced by `3pwr status`.

---

## Observe & feedback

Closing the loop: production lessons return to the **spec as new intent**, not ad-hoc patches. These are
standalone commands (like `verify` / `deps-check`), never folded into the deterministic verdict.

### `observe signal` — record a production signal → route to new intent
Records a signed, attributed `observe` ledger entry, appends a `<SPEC>-FB-###` new-requirement candidate to
`.3powers/feedback/<spec>.md` (to take into `/speckit.specify` — never an in-place patch), and moves the
spec to the **Observe** stage.
- `--spec-id SPEC_ID` (required) · `--kind incident|missed-nfr|usage` (required) · `--nfr NFR_ID` · `--note NOTE` (required).
```bash
3pwr observe signal --spec-id VUTIL --kind incident --nfr VUTIL-NFR-002 --note "p99 latency regressed under load"
```

### `observe coverage` — NFR-instrumentation coverage
Reports which of a spec's NFRs have a declared live check in `.3powers/config/observability.yaml`. Exit
`1` if any NFR is uninstrumented.
- `--spec SPEC` · `--registry REGISTRY` (default `.3powers/config/observability.yaml`).
```bash
3pwr observe coverage --spec specs/002-engine-trust-spine/spec.md
```

### `observe log-action` / `observe verify-actions` — tamper-evident agent log
Appends a signed, agent-attributed entry to a separate hash-chained log (`.3powers/runtime/actions.jsonl`)
for a target system's runtime agents, and verifies it — the same tamper-evidence as the ledger.
- `log-action`: `--agent ID` (required) · `--action TEXT` (required) · `--spec-id SPEC_ID`. `verify-actions`: no flags.
```bash
3pwr observe log-action --agent ops-bot --action "scaled replicas 3→6"
3pwr observe verify-actions
```

---

## Planning discipline

### `coverage-check` — two-way requirement↔task coverage
Every requirement maps to ≥1 task and every task traces to a requirement, *before* code.
- `--spec SPEC` · `--tasks TASKS` (required).
```bash
3pwr coverage-check --spec specs/003-x/spec.md --tasks specs/003-x/tasks.md
```

### `scope-check` — task req-id + file-scope discipline
Fails a task line with no requirement ID, and flags edits outside a task's declared file scope.
- `--tasks TASKS` (required) · `--base BASE` · `--path PATH`.
```bash
3pwr scope-check --tasks specs/003-x/tasks.md --base main
```

---

## Trust artifacts

### `provenance` — sign build provenance + SBOM
Signs a record binding an artifact (by hash) to its commit/repo/SBOM, with the same identity as the
ledger.
- `--artifact ARTIFACT` (required) · `--path PATH` (SBOM project dir) · `--spec-id SPEC_ID`.
```bash
3pwr provenance --artifact dist/app.tar.gz --path .
```

### `deploy-gate` — verify an artifact's provenance
Refuses an artifact whose provenance is missing or invalid.
- `--artifact ARTIFACT` (required).
```bash
3pwr deploy-gate --artifact dist/app.tar.gz
```

### `residual` — record a signed residual review
The post-gate review by a different model family, scoped to what gates can't catch.
- `--reviewer REVIEWER` (required) · `--note NOTE` · `--findings [FINDINGS ...]` · `--spec-id SPEC_ID`.
```bash
3pwr residual --reviewer claude-opus --note "intent fit OK" --spec-id VUTIL
```

---

## Brownfield

### `characterize` — reconstruct a spec + pin a legacy module
Reconstructs a spec stub and scaffolds runnable characterization tests that pin a legacy module's current
behavior as its oracle. Works without a pre-existing `.3powers/`. See [Brownfield Adoption](brownfield.md).
- `--module MODULE` (required) · `--specs SPECS` (default `<root>/specs`) · `--tests TESTS` (default:
  alongside the module).
```bash
3pwr characterize --module src/legacy/money.py
```

---

## Config & quality

### `eval` — run the prompt/constitution eval set
Treats prompts/commands/constitution as versioned software; blocks on regression.
- `--cases CASES` (default `.3powers/eval/cases.yaml`).
```bash
3pwr eval
```

### `deps-check` — third-party version compatibility (preflight)
Probes the installed versions (Spec Kit, scanners, adapter toolchains) against the supported ranges in
`.3powers/config/dependencies.yaml` and reports each `ok | drift | missing | unknown`; a `block`-policy
drift or absence fails. A **preflight** command, *not* a verdict gate — installed versions are
environment-dependent, so they stay out of the verdict to preserve determinism. Pins a known-good Spec Kit
and flags an upstream release that needs adaptation.
- `--manifest MANIFEST` (default `.3powers/config/dependencies.yaml`) · `--strict` (treat `warn` as blocking).
```bash
3pwr deps-check
```

### `roles-check` — model-family diversity between two roles
Fails if two roles resolve to the same model family (enforces oracle model diversity — a different model
family than the coder).
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
