# Plan 028 — The git-integrated run lifecycle: mandatory pre/post-stage hooks, a dedicated branch per run, clean start/stop, agentic 3pwr-authored stage commits (GITX, spec 018)

**Spec:** [`specs/018-git-lifecycle-integration/spec.md`](../specs/018-git-lifecycle-integration/spec.md)
(Spec ID `GITX`, Standard). The version-control-safety counterpart to RUNLIVE (011), AUTOX (014), and
SRCX (017): it turns the executive from committing *opportunistically* (RUNLIVE-FR-010's opt-out
checkpoint — static message, system author, whatever branch was checked out, silently skipped) into
committing *safely*. **Executive / VCS plumbing only, no trust-spine module change** —
`canonical`/`keys`/`ledger`/`verify` are untouched; no gate threshold, verdict byte, exit-code contract,
signing scheme, or human gate changed (GITX-NFR-002/005); the only ledger addition is one additive
`branch` field on SRCX's existing `run`/`start` payload.

## Why

Four seams were left after RUNLIVE/SRCX. (1) A run had **no branch discipline** — its commits landed on
whatever branch the developer happened to be on, including `main`. (2) There was **no clean-start
guard**: a run started on a dirty tree mixed the developer's unrelated uncommitted edits into the run's
history, and nothing guaranteed a clean tree when the run stopped. (3) The commit **message was a static
label** and the **author was the system user** — a reader could not tell what a stage did nor which
commits the engine authored. (4) The whole behavior was **opt-out** (`--no-auto-commit`) and
**best-effort when git was absent**, so the clean-history guarantee did not actually hold. The user's
requirement: git handling as a mandatory pre/post-stage hook, one dedicated branch per run (reusing
SRCX's `<NNN>-<slug>` identity, never a new run number), start clean / stop clean, and each stage as one
agentically-messaged commit authored `3pwr` when 3pwr made it.

## What was done

- **The git discipline module** (new [`gitflow.py`](../engine/src/threepowers/gitflow.py)): the named
  precondition (git on PATH + inside a work tree — a pure environment/repository predicate,
  GITX-FR-002); deterministic branch naming `<prefix><NNN>-<slug>` consuming SRCX's run identity
  (GITX-FR-003 — GITX allocates no number, derives no slug); create-off-base / re-enter-existing branch
  handling that is **never forced** and covers detached-HEAD/unborn/missing-base by branching off the
  current commit (GITX-FR-004/006, GITX-NFR-003); the ledger branch binding + offline read-back
  (GITX-FR-005); the clean-start guard classifying uncommitted paths against the run's
  ledger-recoverable produced set + its feature folder, with the engine's own `.3powers/` state never
  counted as the developer's unrelated work (GITX-FR-007); the produced∩uncommitted clean-stop predicate
  (GITX-FR-008); the single produced-paths-only stage commit (never `add -A`) with the per-invocation
  `-c user.name/-c user.email` 3pwr author — the developer's git config is never mutated, nothing is
  rewritten or force-pushed (GITX-FR-010/012, GITX-NFR-004); and tolerant `git.yaml` preferences
  mirroring `ui.yaml` (defaults `3pwr/` · `main` · `3pwr <3pwr@3powers.local>`; malformed warns once,
  GITX-FR-015).
- **The agentic commit message** (GITX-FR-011): every producing stage's assembled prompt now carries a
  fixed `COMMIT:`-line request (a block outside the tunable AGENTX template body, so a repo template
  cannot drop it); the post-stage hook extracts the LAST `COMMIT: <description>` line from the stage's
  persisted transcript (AUTOX-FR-008) and composes `3pwr(<spec-id>): <step> — <description>`, falling
  back deterministically to the bare `3pwr(<spec-id>): <step>` label so a commit is never blocked on
  message generation. The message is commit data only — never a gate or ledger input (GITX-NFR-001).
- **The hooks wired into the run** ([`cli.py`](../engine/src/threepowers/cli.py)): a live native run
  refuses to start outside a working git repo — the `working git repository` prerequisite joined the
  ONE shared readiness/preflight check set (`3pwr ready`, init, and the run cannot disagree,
  AUTOX-FR-002); the clean-start guard runs before any side effect on a fresh start and before
  re-entering the branch on `--resume` (naming the offending paths and the `git_clean_start` deviation,
  leaving the edits byte-identical); the run branch is established before any stage commit and recorded
  as the additive `run`/`start` `branch` field; the pre-stage hook switches back if the run strayed; the
  post-stage hook commits each producing stage exactly once, superseding the auto-commit block. New
  failure classes `git_branch_failed`/`git_commit_failed` ride the existing `run`/`failure` record and
  exit on the setup/dispatch (non-gate-red) path. `--dry-run`/the simulator stay git-free and offline
  (the SRCX dry-run stance); `runner.commit_checkpoint` was removed (superseded by GITX-FR-010).
- **Mandatory, relievable on the record** (GITX-FR-014): `--no-auto-commit` and the
  `defaults.auto_commit` config toggle are superseded — they warn, name the deviation, and no longer
  disable anything; the only relaxations are the signed, revocable deviations on the three named guards
  now in `deviations.DEVIATABLE_REQUIREMENTS`: `git_clean_start`, `git_stage_commit`, `git_run_branch`.
- **The manual drive gets the same safety** (GITX-FR-016): new `3pwr git start --spec-id <ID>
  [--feature specs/<NNN>-<slug>]` establishes + binds the run branch for a command-by-command drive
  (git precondition + clean-start guard + idempotent re-entry, same additive ledger binding); and
  `advance` — when the spec's run records a branch — refuses off the run branch or with the completed
  stage's recorded work uncommitted, naming the condition and the fix (pre-GITX ledgers record no
  branch and are untouched). `3pwr run --status` / `3pwr status` surface the run branch and the
  per-stage committed indication from the ledger alone (GITX-FR-009).
- **Shipped config**: `git.yaml` seeded by init's scaffold and added to this repo's
  [`.3powers/config/`](../.3powers/config/git.yaml).

## Verification

- Engine green under its own dev tooling: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest` — **669 passed, 1 skipped** (26 new in
  [`tests/test_git_lifecycle.py`](../engine/tests/test_git_lifecycle.py), naming every
  `GITX-FR-001..016` and `GITX-NFR-001..005`): the missing-git refusal on the preflight path and the
  pure precondition predicate; one commit per producing stage with no plain off-switch; the fresh-run
  branch off the base with the base tip unchanged and nothing committed on it; byte-identical branch
  naming; resume re-entering the recorded branch (recovered from the ledger alone — branch count
  unchanged, no new run number) and the detached-HEAD edge; the dirty-unrelated refusal naming paths +
  deviation with the edits untouched and no forced switch; run-produced dirt tolerated on resume; the
  produced∩uncommitted == ∅ clean-stop property at every pause; both status surfaces; the
  produced-paths-only commit carrying the agent's description (and the deterministic fallback); the
  3pwr author with the developer's `user.name`/`user.email` unchanged and history intact; the
  human-committed-stage no-op keeping the human's author; the branch log enumerating the stages in
  order, all engine commits attributable; the deviation-only relaxation with revoke re-arming the
  guard; `git.yaml` tuning prefix/base/author with tolerant defaults; `3pwr git start` establishment +
  idempotence + its clean-start guard; `advance` refusing off-branch/uncommitted and proceeding once
  both hold; sockets-blocked determinism; a pre-GITX ledger verifying with the binding resolving
  empty; dry-run needing no git; and the unchanged runtime dependency set.
- Superseded-behavior tests reworked honestly: AUTOX's ledger-only-resume proof now runs under a signed
  `git_stage_commit` deviation (the flag no longer disables), and the old no-checkpoint edge became the
  warns-and-commits-anyway assertion.
- Self-application (NFR-006), diff-scoped to this branch: `3pwr gate run --path engine --adapter
  python --spec specs/018-git-lifecycle-integration/spec.md --tier Standard --base main` — **verdict
  PASS** (ledger entry #7): format ✓, lint ✓, types ✓, tests ✓, diff_coverage **91.64% ≥ 80%** ✓,
  sast ✓, dependency_scan ✓, secret_scan ✓, gate_gaming ✓, spec_conformance ✓ (**21 requirements
  traced**); `spec_integrity` correctly *skipped* — no Spec-stage sign-off recorded yet for `GITX` (a
  not-yet-approved spec is never blocked). Two earlier red verdict entries (#5, #6) in the append-only
  ledger are misconfigured runs of the same suite (a wrong `--path`, then a leaked
  `THREEPOWERS_SIGNING_KEY_FILE` in the pytest child env), kept as history.

## Handoff — notes

- Spec 018 still needs the human spec-approval sign-off:
  `3pwr signoff --approver <you> --spec-id GITX --stage spec --spec specs/018-git-lifecycle-integration/spec.md`
  — after which the `spec_integrity` gate grades instead of skipping.
- Non-goals held: nothing is pushed and no PR is opened by the engine (the human's step); no rebase/
  squash/amend/force-push and no merge-conflict resolution; no git-config mutation; no new ledger entry
  type or signing change; no user-supplied `.git/hooks` files; no git management for non-lifecycle
  commands; no migration of any existing run's branch or commits; no cross-process branch locking.
- The engine-state exclusion for the clean-start guard is the whole `.3powers/` prefix (ledger appends,
  verdicts, transcripts, seeded config) — the trust spine's own writes are not the developer's
  "unrelated work"; the ledger itself stays committed by the human at PR time, as before.
- A pre-GITX run being resumed derives its branch deterministically from its SRCX identity (the same
  pure function a fresh run uses) since its `run`/`start` entry carries no branch — noted as the
  intended behavior.
