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
missing. Judiciary slash-commands (`/3pwr.*`) ship in `.github/`.

`init` also seeds one **editable agent template per dispatched stage** into
`.3powers/templates/agents/<stage>.agent.md` (discovery, specify, clarify, plan, tasks — whose
template is named for its agent, `implementation-plan.agent.md` —, oracle, implement, review,
characterize — AGENTX-FR-001/009). The executive uses a repo-local template as that
stage's instruction body when present; an absent, empty, or unreadable template falls back to the
engine's built-in instruction (AGENTX-FR-005). Seeding is non-clobbering — a hand-edited template is
never overwritten. Declining the recommended defaults interactively also walks the **headless-CLI +
role→model setup** below (AGENTX-FR-011/012).

### `config roles setup` — the headless-CLI + role→model setup, any time
Binds each configurable role — planner, coder, oracle, reviewer — to a headless integration and a
model, without reinitializing (AGENTX-FR-014). Interactive by default: pick the integration you have
installed (no provider is forced), then pick each role's model from the per-integration catalog in
`.3powers/config/models.yaml` — editable data with a documented default; a model the catalog does not
list is accepted free-form (BYOK), its family derived where the id encodes it (AGENTX-FR-015/016).
Each role gets a complete `roles.yaml` block — `model_family`, `model`, `integration`, `label` — so
`3pwr run` needs no manual role editing (AGENTX-FR-012/013). Non-destructive: only the roles you
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
policy (3PWR-FR-021, epic A3): when `true`, a High-risk `advance` refuses unless an isolated
headless-dispatch attestation (`3pwr oracle dispatch`) proves the oracle was authored with the
implementation, plan, tasks, and contracts physically absent from its worktree. Leave it `false` while
authoring the oracle in-IDE; enable it once the project adopts headless oracle authoring at High-risk.
A judiciary role sharing the coder's model family only ever **warns** — diversity is recommended, never
forced; proceed with `3pwr deviation --gate model_diversity …` (3PWR-FR-022/057, AGENTX-FR-018).

---

## Gates & verification

### `gate run` — run the deterministic gate suite
Runs the tier's gates cheapest-first, emits one normalized verdict, and (unless `--no-ledger`) appends a
signed ledger entry.
- `--path PATH` — target project (default: repo root).
- `--tier TIER` — `Cosmetic` | `Standard` | `High-risk` (default: `Standard`).
- `--adapter ADAPTER` — language adapter (default: auto-detect).
- `--spec SPEC` — path to the governing `spec.md`.
- `--id NNN` — shorthand for `--spec`: resolves the spec of the feature folder `specs/<NNN>-*/`
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
- `--no-ledger` — run without appending a ledger entry.
```bash
3pwr gate run --path e2e/typescript-orders/project \
              --spec specs/<NNN>-<slug>/spec.md --tier Standard
3pwr gate run --id <NNN> --tier Standard      # same spec, resolved by run number
```
Exit `0` if the verdict is green, `1` if red (unless `--report-only`), `4` when a required tool is
missing (see below).

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

### `conformance` — the `spec_conformance` trace only
Checks every requirement in a spec has a linked test, without running the full suite. Under `gate run`
the trace is **anti-gamed**: a requirement counts as traced only when its ID is **bound to a test
declaration** (the test's name/title line or its adjacent docstring — adapter-declared patterns), a
comment-only mention fails as `untraced_requirement`, and every requirement-bound test needs ≥1
assertion (`weak_test` otherwise). Adapters without patterns degrade to a visible quarantine.
- `--spec SPEC` · `--tests [TESTS ...]` — test roots to scan.
```bash
3pwr conformance --spec specs/002-engine-trust-spine/spec.md --tests engine/tests engine/src
```

### `verify` — verify the ledger (offline)
Recomputes the hash chain + signatures — including any recorded **key rotations** (the committed public
key must descend from the genesis key) — and runs a **custody preflight** (a resolved private key inside
the working tree, or readable by other users, is a failing `key_custody` finding). Fails on any tamper,
gap, or break.
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

### `oracle seal` — seal a spec-only bundle
Extracts the acceptance criteria (requirement IDs + text — no impl/plan/tasks/contracts) to
`.3powers/oracle/<spec-id>/sealed.json`, hashed with a re-seal-stable content hash, and records a signed
`oracle` seal entry.
- `--spec SPEC` · `--spec-id SPEC_ID`.
```bash
3pwr oracle seal --spec specs/<NNN>-<slug>/spec.md --spec-id VUTIL
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
                   --tests e2e/typescript-orders/project/tests/unit/lineItem.test.ts
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
Authors the oracle **headlessly** via the native executive runner, under a non-coder integration inside a
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
Appends a signed `signoff` entry. A **Spec-stage** sign-off (`--stage spec`) additionally seals the
approved document into the signed payload — its raw-bytes SHA-256 (`spec_hash`), root-relative
`spec_path`, and the current git commit — which is what the `spec_integrity` gate and `advance` enforce
thereafter. A fresh Spec-stage sign-off supersedes the previous hash.
- `--approver APPROVER` (required) · `--stage STAGE` (default `review`) · `--note NOTE` · `--spec-id SPEC_ID` ·
  `--spec SPEC` — path to the approved `spec.md` (Spec stage; default: the newest `specs/**/spec.md`).
```bash
3pwr signoff --approver "$(git config user.name)" --stage spec --spec-id VUTIL \
             --spec specs/<NNN>-<slug>/spec.md   # seals the approved spec's hash
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

**The run's feature folder (SRCX).** A fresh run (no `--resume`, no `--spec`) deterministically
allocates `specs/<NNN>-<slug>/` (`<NNN>` = the highest existing `NNN-` prefix + 1; the slug derives
from the intent) and binds it into the signed `run`/`start` entry, so a resume finds it from the ledger
alone. Every producing stage leaves its markdown FLAT in that folder — `spec.md`, `plan.md`, `tasks.md`,
plus the `oracle.md`/`implement.md` records linking the real test/code outputs at their real repo paths.
A producing stage is complete only when its markdown exists on disk AND a signed `run`/`stage` entry
lists it (the completion gate); `--resume` re-checks the disk and re-runs the earliest stage whose
artifact is broken — never skipping it on the ledger record alone. The engine also maintains a
human-readable **`progress.md`** in the same folder — the stage table with status glyphs and
completion times, per-phase detail during a phased build, the current state, the last verdict,
copy-pasteable helper commands, and the last verify attempt's failed gates — written atomically at
every lifecycle event (stage start/complete, gate verdict, human-gate pause, failure) and committed
with each producing stage, so the run's state is readable at a glance even mid-run.
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
— while agent stdout prints above it into ordinary, fully scrollable history; off a TTY, under
`--json`/`NO_COLOR`, or on a dumb/tiny terminal it degrades to the plain streamed log, and the
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
- `intent` (positional) · `--file PATH` (read the intent from a text file; inline intent text is
  appended as an instruction) · `--mode auto|commit` · `--integration INTEGRATION` (coder agent backend) ·
  `--agent AGENT` (override the coder backend for this run) · `--spec-id SPEC_ID` (run id, default
  `RUN`) · `--spec SPEC` + `--tier TIER` (what the verify stage gates against) · `--timeout N` /
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
3pwr run --resume --spec-id RUN --approver "$(git config user.name)"
3pwr run --resume --spec-id RUN --revise "tighten the non-goals; leave out point 5"
3pwr run --status --spec-id RUN
```

<a id="run-exit-codes"></a>
**The stable machine contract (AUTOX-FR-009).** Each terminal outcome maps to exactly one documented
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

**Transcripts (AUTOX-FR-008, stable).** Every stage attempt's stdout/stderr — streamed or not — is
persisted, credential-redacted, to `.3powers/runs/<spec-id>/<NN>-<step>-attempt<K>.log`; every failure
message and failure ledger record names the transcript path. Failures are also recorded as signed
`run`/`failure` ledger entries, so `3pwr run --status` and `3pwr status` show
`failed at <stage> (<class>)` until a later record passes that stage.

### `git start` — establish the run branch for a manual drive
Gives the command-by-command `/3pwr.*` drive the same git guarantees as `3pwr run` (GITX-FR-016): checks
the git precondition, applies the clean-start guard (unrelated uncommitted changes refuse, naming the
paths and the `git_clean_start` deviation), creates-or-re-enters the run's dedicated branch, and binds
the branch to the spec-id in the signed ledger (the same additive `run`/`start` field the orchestrated
path records). Idempotent — an already-established run re-enters its recorded branch and appends nothing.
- `--spec-id SPEC_ID` (required) · `--feature specs/<NNN>-<slug>` (the run's feature folder; default:
  the ledger's recorded binding).
```bash
3pwr git start --spec-id GITX --feature specs/018-git-lifecycle-integration
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
`gate_gaming` flag**, and the only relaxation of the git run discipline (`git_clean_start`,
`git_stage_commit`, `git_run_branch` — GITX-FR-014). Human sign-off and provenance are never deviatable.
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
One honest answer, re-runnable any time (AUTOX-FR-003): performs the auto run's own preflight — a
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
