# CLI Reference — `3pwr`

The complete `3pwr` command surface. Generated from and kept in sync with the engine's argparse
definitions (the [`cli/`](../engine/src/threepowers/cli/) package — one module per command group). For a guided walkthrough see
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
An output path *inside* the working tree is **refused** — an executive agent with repo access could read it.
- `--role ROLE` — `ledger` (default) or `oracle` (a distinct signer for the judiciary).
- `--out OUT` — private-key path (default: `~/.config/3powers/<repo>.key`); must be outside the repo.
- `--force` — overwrite an existing key.
```bash
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

### `rotate-key` — rotate the signer (key continuity)
The **outgoing key signs its successor**: appends a `key_rotation` ledger entry authored by the current
key and carrying the new public key, then installs the new key pair (private outside the repo, public
committed). `verify` thereafter requires the committed public key to descend from the genesis key through
exactly these recorded rotations — a bare pubkey swap becomes a named *unrotated key change* finding.
- `--out OUT` — new private-key path (default: outside the repo); in-repo paths are refused.
- `--reason REASON` — why (recorded in the ledger).
```bash
3pwr rotate-key --reason "annual rotation"
```

### External / hardware-backed signing
Set `$THREEPOWERS_SIGNER_CMD` (or `$THREEPOWERS_ORACLE_SIGNER_CMD` for the judiciary identity) to a
command that reads the bytes to sign on **stdin** and prints the **base64 Ed25519 signature** on stdout.
The engine then never reads a private seed from any file or environment variable; verification is
unchanged (standard Ed25519 against the committed public key). A misconfigured signer **fails loudly** —
there is no silent fallback to a software key.
```bash
export THREEPOWERS_SIGNER_CMD="$HOME/bin/hsm-sign"   # e.g. a YubiKey/ssh-agent/enclave wrapper
```

### `init` — guided onboarding (new or existing project)
Makes a project 3Powers-ready in one step: creates the `.3powers/` layout, an independent signer
(**outside the repo**), the baseline config, and the adapter for your chosen language; writes a starter
**AGENTS.md** if none exists (naming `3pwr` as the main command); and prints a **readiness checklist**
(the 3Powers constitution and the agent backends each role dispatches to) plus greenfield-vs-brownfield
next steps. Interactive by default; falls back to defaults with no TTY. Runs offline by default.
- `--yes` — non-interactive: prompt for nothing and apply the documented defaults (CI-friendly).
- `--language LANG` — the language adapter to set up (default: auto-detected, else the first supported).
- `--key-path PATH` — signing-key location; **must be outside the repo** (default: `~/.config/3powers/<repo>.key`, with `~/.ssh/` offered interactively).
- `--auto-mode` / `--no-auto-mode` — record whether `3pwr run` defaults to autonomous mode (advisory; never bypasses a human gate).
- `--force` — overwrite an existing signing key (default: keep it).
- `--skeleton-only` — only create the directory layout (the pre-wizard behaviour).
- `--json` — machine-readable summary of what was created vs kept (incl. the readiness checklist).
```bash
3pwr init                       # guided, offline
3pwr init --yes --language typescript      # non-interactive, e.g. in CI
```
`init` is idempotent — re-running preserves your ledger, keys, hand-edited config, an existing AGENTS.md,
and an existing constitution. For the autonomous lifecycle you also need the constitution
(`.3powers/memory/constitution.md`) and an agent backend on PATH for each role; `init` reports what's
missing. The seeded constitution is mandatory but generic — **adapt it before the first real run** by
completing its in-file "How to adapt this constitution" checklist (technical baseline + policies);
`init` surfaces this as a call to action in the readiness checklist and as the final `--json`
next step. Judiciary slash-commands (`/3pwr.*`) ship in `.github/`.

`init` also seeds one **editable agent template per dispatched stage** into
`.3powers/templates/agents/<stage>.agent.md` (discovery, specify, clarify, plan, tasks — whose
template is named for its agent, `implementation-plan.agent.md` —, oracle, implement, review,
characterize). The executive uses a repo-local template as that
stage's instruction body when present; an absent, empty, or unreadable template falls back to the
engine's built-in instruction. Seeding is non-clobbering — a hand-edited template is
never overwritten. Declining the recommended defaults interactively also walks the **headless-CLI +
role→model setup** below.

### `config roles setup` — the headless-CLI + role→model setup, any time
Binds each configurable role — planner, coder, oracle, reviewer — to a headless integration and a
model, without reinitializing. Interactive by default: pick the integration you have
installed (no provider is forced), then pick each role's model from the per-integration catalog in
`.3powers/config/models.yaml` — editable data with a documented default; a model the catalog does not
list is accepted free-form (BYOK), its family derived where the id encodes it.
Each role gets a complete `roles.yaml` block — `model_family`, `model`, `integration`, `label` — so
`3pwr run` needs no manual role editing. Non-destructive: only the roles you
reconfigure are rewritten; every other field is preserved.
- `--integration NAME` — the agent backend to bind roles to (e.g. `claude`, `codex`, `copilot`).
- `--planner/--coder/--oracle/--reviewer MODEL` — set a role's model directly (catalog id or free-form).
- `--yes` / `--json` — non-interactive: prompt for nothing, apply the documented defaults; `--json`
  stdout is byte-stable.
```bash
3pwr config roles setup                                   # guided
3pwr config roles setup --yes --integration copilot \
    --planner claude-opus-4.8 --coder gpt-5.5             # scripted
```
**`require_dispatch`** (written on the oracle role, default `false`) is the High-risk read-path-isolation
policy: when `true`, a High-risk `advance` refuses unless an isolated
headless-dispatch attestation (`3pwr oracle dispatch`) proves the oracle was authored with the
implementation, plan, tasks, and contracts physically absent from its worktree. Leave it `false` while
authoring the oracle in-IDE; enable it once the project adopts headless oracle authoring at High-risk.
A judiciary role sharing the coder's model family only ever **warns** — diversity is recommended, never
forced; proceed with `3pwr deviation --gate model_diversity …`.

---

## Gates & verification

### `gate run` — run the deterministic gate suite
Runs the tier's gates cheapest-first, emits one normalized verdict, and (unless `--no-ledger`) appends a
signed ledger entry.
- `--path PATH` — target project (default: repo root).
- `--tier TIER` — `Cosmetic` | `Standard` | `High-risk` (default: `Standard`).
- `--adapter ADAPTER` — language adapter (default: auto-detect).
- `--spec SPEC` — path to the governing `spec.md`.
- `--id NNN` — shorthand for `--spec`: resolves the spec of the feature folder `specs-src/<NNN>-*/`
  (the number `3pwr run` allocated and prints in its hints). Exactly one folder must match — zero
  or multiple matches are a clear error — and `--id` cannot be combined with `--spec`.
- `--base BASE` — git ref for the `diff_coverage` / diff-scope base.
- `--mutation` — run the (expensive) mutation gate; opt-in.
- `--paths [PATHS ...]` — scope `diff_coverage` + mutation to these files (risk-tier scoping per capability).
- `--work-kind KIND` — the kind of change (`defect`, `design`, `feature`, `docs`, `refactor`, `chore`);
  repeatable, and usually inferred by `classify`. A `defect` adds the **regression gate**; `design` unions
  the **design oracles** onto the tier's set (see below). Kinds only ever *add* gates, never remove one.
- `--report-only` — emit the verdict but **do not block** (exit 0 even on red); brownfield.
- `--diff-scope` — block only on files changed vs `--base` (brownfield).
- `--auto-fix` — when a format/lint check fails and a fix command is configured, run the fix and
  re-check (opt-in only — never the default; see below).
- `--no-ledger` — run without appending a ledger entry.
```bash
3pwr gate run --path e2e/typescript-orders/project \
              --spec specs-src/<NNN>-<slug>/spec.md --tier Standard
3pwr gate run --id <NNN> --tier Standard      # same spec, resolved by run number
```
Exit `0` if the verdict is green, `1` if red (unless `--report-only`), `4` when a required tool is
missing (see below).

**Pipeline view.** On a capable terminal the run renders one compact status row per gate — status
glyph, `gate · tool`, and the elapsed time plus a short summary — updated in place as each gate
starts and finishes:

```
  ○ format  · biome   (running…)      → updated in place to:
  ✓ format  · biome   0.4 s
  ✗ types   · tsc     1.2 s  2 errors
  – spec_integrity    skipped
```

Piped output, `NO_COLOR`, and `--json` degrade safely: piped/`NO_COLOR` runs print one plain-text
row per finished gate (no in-place updates, no escape codes), and `--json` output is the unchanged
machine payload — never routed through the rendering layer. A skipped `spec_integrity` (no
approval recorded yet) renders with the `–` info glyph, not a failure mark.

**Failure panels.** After the pipeline finishes, each failed gate gets its own panel: a dim
`gate · tool` header with the elapsed time, the gate's error lines indented and trimmed to the
first 30 meaningful lines (blank lines and Node.js `ExperimentalWarning` noise are filtered out
unless `--verbose`) with a `… N more lines` note for the rest, and — when the gate's adapter
configuration declares a fix command — a suggested manual fix:

```
  ── format · biome  1.2 s
    vite.config.ts:12  formatting drift
    ↳ auto-fix: biome format --write .
```

Dependency- and secret-scan panels list one line per finding (the advisory/rule ID and the
package or file). When a failed gate is covered by an active signed deviation, its panel is
annotated with `↳ waived by active deviation seq=N (approver: …)` — the verdict still records
red (deviations never touch the verdict), but the annotation tells you the deviation is
recognized and that `run`/`advance` will accept it. The annotation is human output only; the
`--json` payload is unchanged. The panels are the failure surface — there is no separate summary
block at the bottom of the output.

**Remediation on every failed gate.** Each failed gate's panel ends with an honest next-step
block, and one coder hand-back section follows the panels:

- *What it means* — one line naming what the failure is (e.g. `types`: the type checker found
  real type errors).
- *Fix* — the honest action, always framed as making the code satisfy the check, never as making
  the check pass. When the gate supplied a finding-specific hint (e.g. the fixed version a
  vulnerability scanner reports) that hint is shown instead of the generic guidance; for
  `dependency_scan` the guidance names the auditable `scan.yaml` `advisories:` allowlist
  (id + required reason + optional expiry, every acceptance reported). The safe auto-fix
  command, when one is configured, stays on its own `↳ auto-fix:` line above.
- *Hand back to your coding agent* — a copy-pasteable prompt naming the failed gates and their
  findings and instructing an honest fix ("never weaken a gate: fix the code, not the check"),
  followed by the re-dispatch command `3pwr run --resume --spec-id <NNN>`, carrying the run's
  numeric feature-folder id so it resolves to `specs-src/<NNN>-*/`.
- *Last resort* — the pre-filled
  `3pwr deviation --gate <gate> --approver <you> --note "<why>" [--until <date>]` command, under
  an explicit label that a deviation is only for a deliberate, justified exception — an
  auditable acceptance of risk, never a fix. A recorded deviation is honoured by both `3pwr run`
  and `3pwr advance`.

The whole remediation surface is presentational and human output only: the deterministic
verdict, the signed ledger entry, and the `--json` payload are byte-identical with or without
it, and no model is ever called to produce it.

**Colorized on a terminal.** On a color-capable TTY the verdict header and the failure panels
render as a readable hierarchy: the verdict result reads `PASS` in bold green / `FAIL` in bold
red; inside each panel the findings keep the default weight, `↳ what it means` is dimmed, the
`↳ fix` / `↳ auto-fix` action is green, and the `↳ last resort` label and its `3pwr deviation`
command are yellow — a warning, never the primary action. The coder hand-back header and the
`re-dispatch:` line carry a distinct accent so the copy-paste block is easy to spot. Color is
presentation only and centrally gated: it is forced off for `--json`, `--yes`, `NO_COLOR`, and any
non-TTY (piped/CI) stream, so the machine payload and the plain-text bytes are unchanged. Set
`color_mode: never` in `.3powers/config/ui.yaml` to keep human output plain everywhere, or
`always` to force it on.

**Denser output with `layout: compact`.** Setting `layout: compact` in
`.3powers/config/ui.yaml` tightens the human output: the failure panels drop their surrounding
padding and the blank separator lines inside the hand-back block are removed, so the panels and
hand-back read as one dense block. `layout: normal` (the default) is unchanged. Like every
`ui.yaml` preference it is presentation only — it never touches the verdict, the ledger, or the
`--json` payload.

**Missing prerequisites stop the run up front.** Before any gate command executes, the engine
probes every tool the run's required gates declare (via the adapter manifest's `toolchain:`
section). When a required tool of a non-optional gate is missing, no gate runs: the command exits
with the setup code (`4`) and prints one install hint per missing tool, taken from the adapter's
declared `install` command:

```
⚠ prerequisites missing — install before re-running:
  biome   npm i -D @biomejs/biome
```

Quarantine-safe gates are unaffected: the opt-in mutation gate and the design oracles keep their
existing skip/quarantine behavior when their tool is absent, and `--report-only` (the brownfield
on-ramp) never hard-stops — its gates surface per-gate missing-tool findings as before.

**Work-kind-shaped gates.** When a change is classified (by `classify`, `run`, or an explicit
`--work-kind`), the inferred kind adds gates to the tier's set:
- **defect** → `defect_regression`: a defect fix must ship a **failing regression test** — a test marked
  `*regression*`/`*reproduce*` (by file name or body) that references the defect's requirement id and
  fails before the fix. Missing it is the failure class `missing_regression_test`.
- **design** → the **design oracles** `contract_check`, `component_contract`, `a11y_scan`,
  `visual_regression` (from `.3powers/config/design-oracles.yaml`). Each oracle's tool is
  adapter-supplied; if the adapter doesn't declare it, or the tool isn't installed, the oracle is
  **quarantined** — reported `skip` with a surfaced finding, never silently passed.

**Spec integrity (spec-lock).** At every tier the suite includes a `spec_integrity` gate — cheapest-first,
after `types` and **before any test runs**: once a human has sealed the spec's hash via
`signoff --stage spec`, a spec modified afterwards fails with class `spec_modified`, naming the approving
ledger seq. A spec with no recorded approval hash is **skipped, never blocked**. Review a failure with
`3pwr spec diff`; the sanctioned ways forward are a fresh `signoff --stage spec` over the amended document
or a signed, reversible `3pwr deviation --gate spec_integrity`.

**Diff-scoped mutation (opt-in).** A tier configured with `diff_mutation: true` in
`.3powers/config/risk-tiers.yaml` runs the mutation gate over the **changed source files** whenever a
`--base` is given, graded against that tier's `mutation_score` — machine-graded test quality on every
change without the full-sweep cost. Off by default; enabling it only ever *adds* a gate. A missing
mutation tool quarantines, never silently passes.

**Configurable gate tooling (`.3powers/config/gates.yaml`).** Each adapter ships default gate
commands, but a project can pin its own: `gates.yaml` — **committed team configuration**,
versioned with the rest of `.3powers/config/` and seeded (fully commented) by `3pwr init` —
overrides any gate key in the adapter manifest. Keys match the adapter's `gates:` section names;
only the keys you set override, and every absent gate/key keeps the adapter's value:

```yaml
# .3powers/config/gates.yaml
format:
  check_cmd: "npx prettier --check ."
  fix_cmd: "npx prettier --write ."
tests:
  cmd: "npm run test:unit"
  coverage_format: lcov
  coverage_path: "coverage/lcov.info"
```

Overrides replace the **tool** a gate runs — never the gate itself: the risk tier alone decides
which gates run, so no override can remove or weaken one.

**Auto-detected project tooling.** For gates `gates.yaml` does not override, the engine probes the
target once at gate-run startup and picks up the project's native tooling (first match wins):

| Gate | Signal | Tool |
|---|---|---|
| `format` | `biome.json` · `.prettierrc`/`prettier.config.*` · `go.mod` | biome · prettier · gofmt |
| `lint` | `.eslintrc*`/`eslint.config.*` · `biome.json` | eslint · biome |
| `types` | `tsconfig.json` · `pyproject.toml` with `[tool.pyright]` | tsc · pyright |
| `tests` | `vitest.config.*` · `jest.config.*` · `playwright.config.*` · `go.mod` | vitest · jest · playwright · go test |

When something was detected, one startup line names it — e.g.
`auto-detected gates:  format=biome  tests=vitest` — on the human output only (never under
`--json`). A detected tool the adapter already configures for that gate keeps the adapter's richer
command (coverage settings, shell guards); detection confirms, never degrades. Precedence:
**`gates.yaml` > auto-detection > adapter manifest**. Inspect the result with `gate config show`.

**Auto-fix (`--auto-fix`, opt-in).** The format and lint gates — and only those — may declare a
`fix_cmd` alongside their check command (the shipped adapters do). Without `--auto-fix`, a failing
check fails the gate and the fix command appears only as the failure panel's suggested manual fix.
With `--auto-fix` (available on `gate run` and `run`), a failing format/lint check runs its
configured fix, prints `↳ auto-fixed by <tool>`, and re-checks: a passing re-check turns the gate
green and the fixed files join the run's produced set, so a `3pwr run` stage commit picks them up;
a failing re-check reports normally. Auto-fix is never the default — produced output is never
silently mutated — and a `fix_cmd` on any other gate (types, tests, mutation, …) is discarded and
never executed.

**Scanner exclusions (`.3powers/config/scan.yaml`).** The three scanner gates — `secret_scan`,
`dependency_scan`, and `sast` — honor an auditable, committed per-tool ignore config. Each tool
takes `ignore` (path globs relative to the scanned target, `**` allowed); `secret_scan`
additionally takes `ignore_rules`, a list of scanner rule ids to suppress; and
`dependency_scan` additionally takes `advisories`, an expiring allowlist of accepted
vulnerability ids:

```yaml
# .3powers/config/scan.yaml
version: 1
secret_scan:
  ignore:
    - "**/.next/**"
    - "**/dist/**"
    - "**/build/**"
    - "**/node_modules/**"
  ignore_rules: []          # optional: suppress specific secret-scanner rule ids
dependency_scan:
  ignore: ["**/.next/**", "**/dist/**", "**/build/**", "**/node_modules/**"]
  advisories:               # optional: accepted vulnerability ids (auditable, expiring)
    - id: "GHSA-xxxx-xxxx-xxxx"
      reason: "not exploitable here — dev-only tooling"   # required, non-empty
      until: "2026-12-31"   # optional ISO date or timestamp; past it the gate fails again
sast:
  ignore: ["**/.next/**", "**/dist/**", "**/build/**", "**/node_modules/**"]
```

**Advisory allowlist (`dependency_scan.advisories`).** The sanctioned way to accept a known,
assessed dependency vulnerability without weakening the gate. Each entry names the advisory
`id` reported by the scanner, a **required non-empty `reason`**, and an optional `until`
ISO-8601 expiry (an expiry is strongly recommended). A matching finding is suppressed only
while the entry has a reason and has not expired — an entry with a blank reason, a past
`until`, or an unparseable `until` suppresses **nothing** (fail-closed; a date-only `until`
lapses at UTC midnight at the start of that day). Every acceptance is **always reported** in
the gate output — the result names each accepted advisory id, its reason, and how many
findings it suppressed, in both the human output and `--json`. It is never silent.

`3pwr init` seeds the file with that small default ignore set — generated and vendored trees
(`**/.next/**`, `**/dist/**`, `**/build/**`, `**/node_modules/**`) for all three tools — and a
re-init never overwrites a hand-edited one. A missing or malformed file simply means **no
exclusions**. Exclusions are deterministic in the file's committed bytes and are **never
silent**: every affected gate result reports the applied globs/rules and how many findings they
excluded, in both the human output and `--json`.

> **Security note.** Every glob removes real scan surface — a broad ignore weakens the gate, so
> keep the set to generated or vendored trees and review changes to this file — including every
> advisory acceptance — like any other trust configuration. The engine's core `ed25519-priv`
> private-key check **always runs** and cannot be disabled by this file: the `secret_scan` globs
> only shape its directory walk, and it still fires on key material anywhere outside them.

### `gate config show` — the effective gate configuration
Renders what the engine would actually run, per gate — the adapter defaults, the `gates.yaml`
overrides, and the auto-detected tooling — **without executing any gate**.
- `--adapter ADAPTER` — language adapter (default: auto-detect).

```
$ 3pwr gate config show --adapter typescript
gate    tool   check_cmd                            fix_cmd                                 source
format  biome  npx --no-install @biomejs/… format . npx … @biomejs/biome format --write .   [adapter]
tests   jest   npm run test:unit                    —                                       [gates.yaml]
types   tsc    npx --no-install tsc --noEmit        —                                       [auto-detected]
```

Each row's source tag names where that gate's configuration came from: `[adapter]` (the manifest),
`[gates.yaml]` (the committed override), or `[auto-detected]` (the startup probe).

### `conformance` — the `spec_conformance` trace only
Checks every requirement in a spec has a linked test, without running the full suite. Under `gate run`
the trace is **anti-gamed**: a requirement counts as traced only when its ID is **bound to a test
declaration** (the test's name/title line or its adjacent docstring — adapter-declared patterns), a
comment-only mention fails as `untraced_requirement`, and every requirement-bound test needs ≥1
assertion (`weak_test` otherwise). Adapters without patterns degrade to a visible quarantine.
- `--spec SPEC` · `--tests [TESTS ...]` — test roots to scan.
```bash
3pwr conformance --spec specs-src/002-engine-trust-spine/spec.md --tests engine/tests engine/src
```

### `verify` — verify the ledger (offline)
Recomputes the hash chain + signatures — including any recorded **key rotations** (the committed public
key must descend from the genesis key) — and runs a **custody preflight** (a resolved private key inside
the working tree, or readable by other users, is a failing `key_custody` finding). Fails on any tamper,
gap, or break. Detection is not only on demand: **every ledger append first re-verifies the current tail
entry** (recomputed hash, plus the signature when the tail's signer is resolvable; O(1)) and refuses to
write on top of provable tamper, pointing here — key-succession issues (e.g. a replaced committed key
with no recorded rotation) never block appends and surface in `verify`, as does damage deeper in the
chain (middle entries, gaps, linkage).
- `--anchored` — also cross-check the chain against the latest local anchor tag (see `anchor`): a ledger
  truncated or rewritten behind the anchored head fails, even if every signature verifies.
```bash
3pwr verify              # → ledger OK — N entries, chain and signatures intact
3pwr verify --anchored   # → also: anchor OK — chain extends the witnessed head
```

### `anchor` — record the ledger head with an external witness (opt-in)
Tags the current head (sequence + entry hash) as the annotated git tag `3powers/anchor/<seq>` and appends
a local signed receipt. Pushing the tag to a remote is what makes the witness external — after that, even
a holder of the signing key cannot silently rewrite the anchored history.
- `--push` — push the tag to the remote (**the only network-capable operation**, explicit opt-in).
- `--remote REMOTE` — git remote for `--push` (default: `origin`).
```bash
3pwr anchor --push       # anchor + publish the witness
```

---

## Oracle independence (Phase A / judiciary)

Moves oracle independence from procedural to **structurally attested** — the judiciary authors from a
sealed, spec-only bundle, and independence is proven from the signed ledger. The binding check runs at
`advance` under **risk-tier scoping** (High-risk); detection that the author *touched/read* the
implementation is an **advisory** flag surfaced for review, never a blocker.

**One key threads everything.** Every keyed `oracle` subcommand takes `--spec-id` — the oracle
**storage key**, by convention the run's `<NNN>-<slug>` feature-folder name. When you omit it inside
a repository whose spec lives in a feature workspace (`specs-src/<NNN>-<slug>/spec.md`), the key
defaults to that folder name, so the sealed bundle, the authoring record, the dispatch attestation,
the collected test destination `tests/oracle/<NNN>-<slug>/`, and the run's own ledger records all
resolve under the one id you browse in `specs-src/`. The key is decoupled from the requirement
namespace: a spec whose requirements are `DEMO-FR-*` keeps that namespace in the sealed criteria and
in coverage, whatever the storage key. Records keyed by older tokens keep verifying — pass the
original `--spec-id` explicitly.

### `oracle seal` — seal a spec-only bundle
Extracts the acceptance criteria (requirement IDs + text — no impl/plan/tasks/contracts) to
`.3powers/oracle/<spec-id>/sealed.json`, hashed with a re-seal-stable content hash, and records a signed
`oracle` seal entry.
- `--spec SPEC` · `--spec-id SPEC_ID` (default: the spec's `<NNN>-<slug>` feature-folder name, else
  the spec document's own Spec ID).
```bash
3pwr oracle seal --spec specs-src/<NNN>-<slug>/spec.md   # keys by the folder id
```

### `oracle record` — record oracle authoring
Records the authoring event, bound to the sealed bundle: the model actually used, the oracle test files
(hashed), and any advisory peek/touch findings. **Refuses** when the oracle's model family equals the
coder's, checking the model actually recorded (oracle model diversity — a different model family than the
coder).
- `--spec-id SPEC_ID` (default: the `<NNN>-<slug>` feature-folder name) · `--model FAMILY/MODEL`
  (required) · `--tests PATHS…` (required) · `--base BASE` (git ref for the touched-implementation
  advisory scan).
```bash
3pwr oracle record --model anthropic/claude-opus \
                   --tests tests/oracle/<NNN>-<slug>/lineItem.test.ts
```

### `oracle verify` — verify independence from the ledger
Checks seal-binding, model-family diversity, Phase-A-before-B ordering (by ledger seq, not git time), and
one oracle test per criterion; prints advisory findings too. Coverage counts references in the spec's own
requirement namespace (e.g. `DEMO-FR-*`), whatever the storage key. With `--require-dispatch`, also
confirms the oracle was authored via a read-path-isolated headless dispatch. Exit `1` if the structural
check fails.
- `--spec-id SPEC_ID` (default: the `<NNN>-<slug>` feature-folder name) · `--tests [ROOTS …]`
  (default: the recorded oracle test paths) · `--require-dispatch` (also require an isolated dispatch
  attestation).
```bash
3pwr oracle verify   # inside a feature workspace: seal ↔ record ↔ verdict from the one folder id
```

### `oracle dispatch` — author the oracle headlessly, read-path isolated
Authors the oracle **headlessly** via the native executive runner, under a non-coder integration inside a
**sanitized git worktree** where the implementation, plan, tasks, and contracts are physically absent —
attested by a worktree manifest hash recorded in the ledger. The authored tests are collected under
`tests/oracle/<spec-id>/` (with the defaulted key: `tests/oracle/<NNN>-<slug>/`). This is the physical
read-path isolation behind oracle sealing; it never enters the deterministic verdict.
- `--spec-id SPEC_ID` (default: the `<NNN>-<slug>` feature-folder name) · `--integration INTEGRATION`
  (the headless CLI, e.g. `claude`) · `--model FAMILY/MODEL` (override the resolved oracle model) ·
  `--workflow WORKFLOW` · `--base BASE` (clean git ref for the worktree, default `HEAD`) ·
  `--tests [PATHS …]` · `--dry-run` (build + attest isolation offline, no model call) ·
  `--keep-worktree` (leave the sanitized worktree in place).
```bash
3pwr oracle dispatch --integration claude
```

---

## Lifecycle & enforcement

### `signoff` — record a signed human sign-off
Appends a signed `signoff` entry. A **Spec-stage** sign-off (`--stage spec`) additionally seals the
approved document into the signed payload — its raw-bytes SHA-256 (`spec_hash`), root-relative
`spec_path`, and the current git commit — which is what the `spec_integrity` gate and `advance` enforce
thereafter. A fresh Spec-stage sign-off supersedes the previous hash.
- `--approver APPROVER` (required) · `--stage STAGE` (default `review`) · `--note NOTE` · `--spec-id SPEC_ID` ·
  `--spec SPEC` — path to the approved `spec.md` (Spec stage; default: the newest `specs-src/**/spec.md`).
```bash
3pwr signoff --approver "$(git config user.name)" --stage spec --spec-id VUTIL \
             --spec specs-src/<NNN>-<slug>/spec.md   # seals the approved spec's hash
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
```

### `spec diff` — does the spec still match its approval hash? (read-only)
Compares the spec on disk against the hash sealed at the latest Spec-stage sign-off. Exits `0` on a match
(or when no approval hash exists — nothing to compare); exits `1` on a mismatch, reporting both hashes and
the approving seq/approver, plus a unified textual diff when the sign-off commit is known to git. **Never
writes to the ledger.**
- `--spec-id SPEC_ID` (required) · `--spec SPEC` — path to the `spec.md` (default: the path recorded at
  approval).
```bash
3pwr spec diff --spec-id VUTIL
```

### `advance` — local enforcement gate
Refuses to advance unless the ledger verifies, the latest *enforced* verdict is green **(or every red gate
is covered by an active deviation)**, and a human sign-off exists at/after it. Report-only verdicts don't
count, and an overdue emergency cleanup blocks the advance. Under **risk-tier scoping** (High-risk) it
additionally requires oracle independence — a sealed spec-only bundle, an authoring record in a different
model family than the coder, authored *before* the implementation verdict. Advisory peek/touch findings
are surfaced but never block. At **every tier** it also re-executes the **`spec_integrity`** check: a spec
modified after its Spec-stage sign-off refuses with reason `spec_modified`, unless an active, signed
`spec_integrity` deviation covers it (recorded in `deviations_applied`; revoking re-blocks). When the
spec's run records a dedicated **run branch** (GITX), a stage-boundary advance also refuses when the
repository is not on that branch or the completed stage's work is uncommitted — naming the condition
and the fix; relaxable only via the signed `git_run_branch` / `git_stage_commit` deviations.
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
Drives the eight-stage lifecycle through the **native executive** — dispatching each stage to the headless
agent named by its role in `.3powers/config/roles.yaml` — while streaming a live stage tracker (the engine
makes no model call itself). `auto` mode auto-approves the intermediate review gates and **stops only at
the two mandatory human gates** — spec approval and sign-off; `commit` mode stops at every gate. It first
classifies the intent and carries the inferred work-kind into the run so the verify step shapes the gate
suite. Sign-offs, per-stage completions, verdicts, and any terminal failure are recorded in the signed
ledger, so a run is resumable and its state is always visible (`--status` / `3pwr status`).

**Discovery — the conditional first stage.** `feature` and `design` work opens with a dispatched
**Discovery** stage that explores the problem space and writes `discovery.md` into the run's feature
folder; the Spec stage then receives it as prior context. `defect`, `docs`, `chore`, and `refactor`
runs skip it — the tracker shows the stage's outcome as *skipped* and nothing is written.
`--discovery` forces the stage and `--no-discovery` skips it, whatever the inferred work kind.

**The run's feature folder (SRCX).** A fresh run (no `--resume`, no `--spec`) deterministically
allocates `specs-src/<NNN>-<slug>/` (`<NNN>` = the highest existing `NNN-` prefix + 1; the slug derives
from the intent) and binds it into the signed `run`/`start` entry, so a resume finds it from the ledger
alone. Every producing stage leaves its markdown FLAT in that folder — `discovery.md` (when the
Discovery stage ran), `spec.md`, `plan.md`,
`implementation-plan.md`, plus two records: **`oracle.md`**, the implementation-agnostic Tests
Specification the oracle agent authors from the sealed spec (one section per requirement id with its
Given/When/Then criterion; the engine validates it names every requirement and leaks no file path or
test framework, and writes a visible structural stub when it is absent — the machine record of the
actual oracle test paths lives in the signed ledger entries, and the runnable tests land under
`tests/oracle/<NNN>-<slug>/`, keyed by the same folder id), and **`changelog.md`**, the run's
engine-generated change record — grouped by phase and traced to requirement ids, linking the real
code outputs at their real repo paths — which never touches the project's top-level `CHANGELOG.md`
(features written by older versions keep their `tasks.md`/`implement.md` names, which stay readable).
A producing stage is complete only when its markdown exists on disk AND a signed `run`/`stage` entry
lists it (the completion gate); `--resume` re-checks the disk and re-runs the earliest stage whose
artifact is broken — never skipping it on the ledger record alone. The engine also maintains a
human-readable **`progress.md`** in the same folder — the stage table with status glyphs and
completion times, per-phase detail during a phased build, the current state, the last verdict,
copy-pasteable helper commands, and the last verify attempt's failed gates — written atomically at
every lifecycle event (stage start/complete, gate verdict, human-gate pause, failure) and committed
with each producing stage, so the run's state is readable at a glance even mid-run.
**Token consumption (advisory).** When an agent backend reports its token usage (declared per
manifest via a `usage` extraction hint — JSON fields or a regex over the agent's output, with
unit-aware parsing of `k`/`M`/comma-formatted counts), the run records the **real consumed** count —
non-cached input plus output tokens — per stage and per phase, **additively**: a **Tokens** column in
both `progress.md` tables (showing `—` — unknown — when a backend does not report), a `tokens` field
on the `--json` per-stage results, and a `tokens` field on the signed `run`/`stage`, `run`/`phases`
(per phase result), and `run`/`checkpoint` ledger payloads. These fields appear only when usage was
captured and are never renamed or removed; tokens never enter the gate suite or the deterministic
verdict, whose bytes are identical whether or not usage was captured. Backends differ in what they
can report: some text-mode totals are cache-inclusive (aider's "sent" includes the cached context;
codex's plain-text total likewise), and a backend that reports nothing shows `—`. Where the backend
supports it, a manifest can opt into structured output for the exact non-cached count: set
`usage_mode: json` plus `usage_mode_args` — the backend's own flag, e.g. `--output-format json`
(claude) or `--json` (codex). Off by default, preserving the live text stream.
**Session freshness.** Every dispatched stage and phase is a **fresh agent session** — an
independent process with no conversation state carried between dispatches; the engine never emits a
resume/continue flag, and a manifest's `new_session_args` passes a backend's no-resume flag where
one exists. `[P]` phases with disjoint file scopes run concurrently as separate engine-dispatched
sessions; `[P]` tasks inside a phase are executed via the agent's own sub-agents.
**Editing the agent prompts.** Every dispatched stage prompt is assembled from markdown
templates — the single source of the stage instructions; no prompt text lives inline in the engine.
A repo-local template at `.3powers/templates/agents/<name>.agent.md` (seeded by `3pwr init`)
overrides the engine's bundled default; an absent, empty, or unreadable file falls back to the
bundled template, then to the generic fragment. Four **fragments** compose the surrounding prompt —
`preamble`, `generic`, `commit-note`, and `revise` — and are overridable the same way. A template
body may reference the closed variable vocabulary `$STEP`, `$GATE`, `$ARTIFACT`, `$FEATURE_FOLDER`,
`$ORACLE_DESTINATION`, `$FEEDBACK`, substituted at dispatch time: an unset variable renders empty,
`$$` escapes a literal `$`, and any other `$name` is left verbatim. The engine-framed INTENT /
APPROVED SPEC / PRIOR CONTEXT / FILE SCOPE blocks are never substituted — a template tunes the
instruction body only.
**The run's git discipline (GITX).** A working git repository is a run **precondition** (a non-git or
git-absent start is refused in preflight). A fresh run creates and switches to a dedicated branch
`<prefix><NNN>-<slug>` (default prefix `3pwr/`, reusing the SRCX run identity) off the configured base
before any commit; a resume re-enters that same branch, recovered from the signed `run`/`start` entry's
additive `branch` field. The run **refuses to start** when the working tree carries uncommitted changes
not produced by the run (naming the paths and the `git_clean_start` deviation — the edits are never
touched). After each producing stage, the post-stage hook commits exactly one commit staging only the
run's produced paths, whose message is the agent's `COMMIT:` description (deterministic
`3pwr(<spec-id>): <step>` fallback) and whose author is the configured `3pwr` identity — applied
per-commit, never mutating the developer's git config, never force-pushing or rewriting history.
Preferences (branch prefix, base branch, 3pwr author) live in `.3powers/config/git.yaml`; the
discipline itself is mandatory and relaxable only via the signed deviations
(`git_clean_start` / `git_stage_commit` / `git_run_branch`).
**Steering the run (STEER).** The intent can come from a **file**: `3pwr run --file my-intent.md`
uses the file's contents as the intent, and `3pwr run --file my-intent.md "<inline>"` appends the
inline text as an instruction — resolved deterministically (file first) and recorded verbatim in the
ledger `start` entry; a missing/empty/binary/directory `--file` fails fast with exit code 4 and no
`start` entry. At every human-gate pause the run presents **three actions** with copy-pasteable
commands and the artifact under review: **approve** (`--resume --approver <you>` — records the
sign-off and continues), **reject** (`3pwr abort` — stops), and **revise**
(`--resume --revise "<feedback>"` or `--revise-file <path>` — re-dispatches the paused stage with the
original intent, the current artifact, and the feedback, records the revision in the signed ledger,
and returns to the *same* gate; empty feedback or a revise outside a gate is refused). Opt-in
**notification channels** in `.3powers/config/notifications.yaml` (Slack / Teams / email / macOS
desktop; secrets referenced from the environment, e.g. `THREEPOWERS_SLACK_WEBHOOK`) fire on gate
pause, failure, and completion — best-effort and fully isolated: a broken channel never blocks or
alters the run, and with none configured no network call is made. On a capable TTY the run shows a
**persistent bottom-anchored live bar** — the eight stages with done/current/upcoming marks, the
active step, a heartbeat spinner with elapsed time, and the running / paused-at-gate / failed state
— rendered by the [Rich](https://github.com/Textualize/rich) library, while agent stdout streams
above it, content unchanged and without syntax highlighting, into ordinary, fully scrollable
history (no alternate screen, no scroll region). The degradation contracts are unchanged: off a
TTY, under `--json`/`NO_COLOR`/`--yes`, or on a dumb/tiny terminal the output degrades to the plain
streamed log with no escape codes, `--json` payloads never pass through the renderer, and the
terminal is always restored on exit or Ctrl-C. When the verify stage goes red, the run prints a
structured failure summary — one row per failed gate (`name · tool`) with its first actionable error
line, followed by ready-to-run commands:

```
✗  gates failed (2 of 11):
     format · biome     ↳ 2 files would be reformatted
     tests  · vitest    ↳ 1 test failed
     Resume:  3pwr run --resume --spec-id 042
     Inspect: 3pwr gate run --id 042
```

**Active deviations are honoured at Verify.** When every red gate of the just-recorded verdict is
covered by an active signed deviation (scoped to the run's spec id; a global deviation applies
too), the run proceeds past Verify instead of stopping at gate-red, printing one
`proceeding past <gate> under deviation seq=N` notice per waived gate — the same coverage decision
`advance` makes, from the same shared logic. The recorded verdict stays honestly red; only the
proceed decision consults deviations. If any red gate is uncovered, the run stops naming the
uncovered gate(s) exactly as before.
- `intent` (positional) · `--file PATH` (read the intent from a text file; inline intent text is
  appended as an instruction) · `--mode auto|commit` · `--integration INTEGRATION` (coder agent backend) ·
  `--agent AGENT` (override the coder backend for this run) · `--spec-id SPEC_ID` (the run's
  numeric id, e.g. `042`; default: derived from the allocated feature folder, resolving to
  `specs-src/<NNN>-*/`) · `--spec SPEC` + `--tier TIER` (what the verify stage gates against) ·
  `--auto-fix` (at the
  verify stage, let a failing format/lint check run its configured fix command and re-check —
  opt-in, never the default; see `gate run`) · `--discovery` / `--no-discovery` (force or skip the
  Discovery stage, overriding the work-kind default) · `--timeout N` /
  `--retries N` (per-stage dispatch bounds) · `--no-auto-commit` (SUPERSEDED by GITX — warns and
  commits anyway; relax with `3pwr deviation --gate git_stage_commit`) · `--notify CMD` (best-effort
  notification hook; fires alongside the configured channels) ·
  `--resume` (record a sign-off + continue after a human gate, or continue past a failure) ·
  `--revise MSG` / `--revise-file PATH` (with `--resume`: revise the paused stage with feedback and
  return to the same gate) ·
  `--status` (print the stage tracker + the run branch and committed stages) · `--dry-run` (simulate
  offline; no git required) · `--simulate-fail` (force a
  red verdict, for `--dry-run`) · `--no-input` (never prompt) · `--approver APPROVER` · `--note NOTE`.
```bash
3pwr run "add IBAN validation to the address form" --mode auto
3pwr run --file my-intent.md "take this and create a spec for it but leave out point 5"
3pwr run --resume --spec-id 042 --approver "$(git config user.name)"
3pwr run --resume --spec-id 042 --revise "tighten the non-goals; leave out point 5"
3pwr run --status --spec-id 042
```

<a id="run-exit-codes"></a>
**The stable machine contract.** Each terminal outcome maps to exactly one documented
(JSON `status`, exit code) pair — a wrapper branches on the exit code alone, or on the `status` string
under `--json`. This table is a stable interface:

| Outcome | JSON `status` | Exit code |
|---|---|---|
| Lifecycle completed | `done` | `0` |
| Deterministic gate suite failed at Verify | `gates_red` | `1` |
| Human rejected a gate / run aborted | `rejected` / `aborted` | `1` |
| Usage error (incl. nothing to resume) | — | `2` |
| Paused at a human gate (spec approval / sign-off) | `paused_at_gate` | `3` |
| Preflight refused before any dispatch | `preflight_failed` | `4` |
| A stage's agent could not be executed | `dispatch_failed` | `4` |
| A stage produced no declared artifact | `artifact_missing` | `4` |
| A completed stage's markdown is missing from its feature folder | `artifact_absent` | `4` |
| A stage's on-disk markdown is recorded in no ledger entry | `artifact_unrecorded` | `4` |
| The run branch could not be created/switched (never forced) | `git_branch_failed` | `4` |
| A producing stage's mandatory commit failed | `git_commit_failed` | `4` |
| The gate suite could not run at Verify | `verdict_error` | `4` |

**Transcripts (stable).** Every stage attempt's stdout/stderr — streamed or not — is
persisted, credential-redacted, to `.3powers/runs/<spec-id>/<NN>-<step>-attempt<K>.log`; every failure
message and failure ledger record names the transcript path. Failures are also recorded as signed
`run`/`failure` ledger entries, so `3pwr run --status` and `3pwr status` show
`failed at <stage> (<class>)` until a later record passes that stage.

### `git start` — establish the run branch for a manual drive
Gives the command-by-command `/3pwr.*` drive the same git guarantees as `3pwr run`: checks
the git precondition, applies the clean-start guard (unrelated uncommitted changes refuse, naming the
paths and the `git_clean_start` deviation), creates-or-re-enters the run's dedicated branch, and binds
the branch to the spec-id in the signed ledger (the same additive `run`/`start` field the orchestrated
path records). Idempotent — an already-established run re-enters its recorded branch and appends nothing.
- `--spec-id SPEC_ID` (required) · `--feature specs-src/<NNN>-<slug>` (the run's feature folder; default:
  the ledger's recorded binding).
```bash
3pwr git start --spec-id GITX --feature specs-src/018-git-lifecycle-integration
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
at the enforcement boundary — `advance`, and `3pwr run`'s proceed decision at Verify; gates always run
honestly, so the verdict stays deterministic. See
[Concepts → emergencies & deviations](concepts.md).

### `deviation` — relax named gates, reversibly
Records a signed, reversible gate exception that lets `advance` — and `3pwr run` at its Verify stage —
accept specific red gates, with a reason, a human approver, and a way back (an expiry or an explicit
revoke). Also the **sanctioned way to accept a
`gate_gaming` flag**, and the only relaxation of the git run discipline (`git_clean_start`,
`git_stage_commit`, `git_run_branch`). Human sign-off and provenance are never deviatable. A red gate
covered by an active deviation is annotated wherever it is shown (`gate run` failure panels; the run's
proceed notice) — the recorded verdict itself stays red.
- `--gate GATE` (repeatable; required unless `--revoke`) · `--approver APPROVER` (required to record) ·
  `--note NOTE` (the reason — **required** to record: a deviation with no stated reason is refused) ·
  `--until ISO8601` (auto-expiry; a date-only value like `2026-10-01` is taken as UTC) ·
  `--revoke SEQ` (the way back) · `--spec-id SPEC_ID`
  (scope; default global).
```bash
# accept a specific red gate, tracked as a follow-up, until a date
3pwr deviation --gate dependency_scan --approver "$(git config user.name)" \
               --note "GHSA-… waiting on upstream fix" --until 2026-07-15T00:00:00Z --spec-id VUTIL
# the way back
3pwr deviation --revoke 7
```

### `emergency` — the constrained fast path
Opens an emergency deviation that may defer **only `mutation` + `diff_coverage`**; it never relaxes the
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
`.3powers/feedback/<spec>.md` (to take into a fresh spec via `3pwr run` — never an in-place patch), and
moves the spec to the **Observe** stage.
- `--spec-id SPEC_ID` (required) · `--kind incident|missed-nfr|usage` (required) · `--nfr NFR_ID` · `--note NOTE` (required).
```bash
3pwr observe signal --spec-id DEMO --kind incident --nfr DEMO-NFR-002 --note "p99 latency regressed under load"
```

### `observe coverage` — NFR-instrumentation coverage
Reports which of a spec's NFRs have a declared live check in `.3powers/config/observability.yaml`. Exit
`1` if any NFR is uninstrumented.
- `--spec SPEC` · `--registry REGISTRY` (default `.3powers/config/observability.yaml`).
```bash
3pwr observe coverage --spec specs-src/002-engine-trust-spine/spec.md
```

#### Observability registry (`observability.yaml`)
The registry `observe coverage` reads is `.3powers/config/observability.yaml` (seeded by `3pwr init`,
never clobbered). It declares which of a spec's **NFRs have a live check in production** — the engine
is fully offline and never runs or inspects your production system, so it cannot discover this
instrumentation itself; you register it, and `observe coverage --spec <spec.md>` flags every NFR in
the spec with no registered check. Schema (`version: 1`): a top-level `checks` list where each entry
names one NFR —
- `nfr` — the requirement ID exactly as it appears in the spec (e.g. `DEMO-NFR-001`);
- `check` — a human-readable note describing *how* the NFR is verified in production (a probe, an
  SLO monitor, an alert, a scheduled job).
```yaml
version: 1
checks:
  - nfr: DEMO-NFR-001
    check: "p99 latency SLO monitor on the checkout endpoint, alerting at 250 ms"
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
3pwr coverage-check --spec specs-src/003-x/spec.md --tasks specs-src/003-x/implementation-plan.md
```

### `scope-check` — task req-id + file-scope discipline
Fails a task line with no requirement ID, and flags edits outside a task's declared file scope.
- `--tasks TASKS` (required) · `--base BASE` · `--path PATH`.
```bash
3pwr scope-check --tasks specs-src/003-x/implementation-plan.md --base main
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
Probes the installed versions (scanners, adapter toolchains) against the supported ranges in
`.3powers/config/dependencies.yaml` and reports each `ok | drift | missing | unknown`; a `block`-policy
drift or absence fails. A **preflight** command, *not* a verdict gate — installed versions are
environment-dependent, so they stay out of the verdict to preserve determinism. Flags an upstream release
that needs adaptation.
- `--manifest MANIFEST` (default `.3powers/config/dependencies.yaml`) · `--strict` (treat `warn` as blocking).
```bash
3pwr deps-check
```

### `ready` — am I ready for `3pwr run --mode auto`?
One honest answer, re-runnable any time: performs the auto run's own preflight — a
resolvable/usable signing key (an env-supplied key is validated, never trusted silently), a headless
coder agent with its CLI on PATH, a different-family oracle (or a recorded diversity deviation) — plus
a dependency summary. **The same shared checks** `3pwr init`'s readiness and the run's refusal use, so
the three can never disagree. Read-only, fully offline, never a gate; a present agent CLI is reported
honestly as "present; authentication not verified". Exits `0` ready, `1` not ready (each unmet item
lists its exact fix).
- `--integration INTEGRATION` (check against this coder backend instead of `roles.coder.integration`)
  · `--spec-id SPEC_ID` (consider deviations recorded for this spec id).
```bash
3pwr ready
3pwr ready --json      # {"ready": …, "checks": [...], "deps": …}
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
