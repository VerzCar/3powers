# Plan 027 — The run artifact workspace: flat per-run folders, stage records, and the completion gate (SRCX, spec 017)

**Spec:** [`specs/017-run-artifact-workspace/spec.md`](../specs/017-run-artifact-workspace/spec.md)
(Spec ID `SRCX`, Standard). The workspace/executive counterpart to PHASE (013) — whose folder split it
**supersedes** — and to RUNLIVE (011) / AUTOX (014), whose dispatch-time artifact contracts and signed
`run`/`failure` records it extends. **Executive/workspace/artifact plumbing only, no trust-spine module
change** — `canonical`/`keys`/`ledger`/`verify` are untouched; no gate threshold, verdict byte, exit-code
contract, signing scheme, or human gate changed (SRCX-NFR-002/005); ledger additions are strictly
additive (two new failure-class *values* + one field on the existing `run`/`start` payload).

## Why

Three seams were left after PHASE/RUNLIVE/AUTOX. (1) The folder layout in code (the `spec/` +
`artifacts/` split) diverged from the layout in use — every spec on disk is flat — and the user wants
one flat folder per run, canonically. (2) The two stages producing real code (`oracle`, `implement`)
left no document in the feature folder, so the folder was not a complete at-a-glance record of the run.
(3) The completion signal was one-sided: the ledger recorded a stage's accepted artifacts, but nothing
cross-checked disk against ledger — and on `--resume` the engine trusted the ledger's `stage` entry
alone, so deleting a completed stage's artifact and resuming silently *skipped* that stage. Since SLIM
removed Spec Kit, the run flow also had no next-number counter to allocate `specs/<NNN>-<slug>/`.

## What was done

- **Flat canonical workspace** (SRCX-FR-001/002/003) in
  [`workspace.py`](../engine/src/threepowers/workspace.py): `stage_artifact_path` now writes
  `feature_dir/spec.md` (specify) / `feature_dir/<step>.md` (every other producing step) — no `spec/`
  or `artifacts/` subfolder; `spec_path` and `find_artifact` resolve flat-first with the PHASE split
  location as the read fallback, so all three layouts keep yielding exactly one path per stage and
  existing features 001–016 run in place (SRCX-NFR-003). `PRODUCING_STEPS` names the exact producing
  set `{specify, plan, tasks, oracle, implement}` (SRCX-FR-004).
- **Deterministic run-folder allocation** (SRCX-FR-008/009/010/011): `slugify` (lowercase, collapse
  non-alphanumerics to single hyphens, trim, bound at 48 chars with no trailing hyphen, fixed
  `feature` fallback; idempotent and pure), `next_feature_number` (max existing `NNN-` prefix + 1),
  `feature_folder_name` (byte-identical given the same listing + intent), and `allocate_feature_dir`
  (fails fast with `FileExistsError` — a folder allocated for a different run is never overwritten).
  `cmd_run` allocates on a fresh live run without `--spec`, derives the folder from an explicit
  `--spec`, records it as an **additive `feature_dir` field on the existing `run`/`start` payload**,
  and a resume reads it back from the signed ledger alone — no modification-time scan. `--dry-run` and
  the simulator allocate nothing (SRCX-NFR-005).
- **A ledger-tracked markdown per producing stage** (SRCX-FR-004/005/006/007) in the new
  [`completion.py`](../engine/src/threepowers/completion.py): the `oracle`/`implement` stages now leave
  engine-written *records* — `oracle.md` linking the authored oracle tests and `implement.md` linking
  the produced change set (a superset of the dispatch-time matched/produced paths), each at its real
  repo path, nothing relocated or duplicated. An N-phase implement yields exactly ONE `implement.md`
  enumerating every phase with its scoped changes in deterministic artifact order, written from the
  collecting thread after all phases complete (SRCX-NFR-006). The record's path rides in the stage's
  `run`/`stage` ledger entry (and its checkpoint commit). Pure gate/verdict/sign-off/advance stages
  stay ledger-only.
- **The deterministic stage-completion gate** (SRCX-FR-012..016): `check_step` asserts BOTH that the
  stage's declared markdown exists on disk (flat, or the split fallback for legacy features — checked
  *at its split path*, SRCX-NFR-003) AND that a `run`/`stage`-or-`checkpoint` entry for the step lists
  that repo-relative POSIX path (`recorded_stage_artifacts` — one pass over injected entries,
  SRCX-NFR-004). The native runner runs the gate after every producing stage; a failure blocks the run
  with a **named, classified** `run`/`failure` record — `artifact_absent` (recorded but gone from disk)
  or `artifact_unrecorded` (on disk but in no entry), both distinct from RUNLIVE's dispatch-time
  `artifact_missing` — surfacing through `3pwr run --status` / `3pwr status` as
  `failed at <stage> (<class>)` and exiting on the setup/dispatch (non-gate-red) path. Pure given
  (disk state, ledger entries, step); no model, no network (SRCX-NFR-001).
- **Resume applies the gate** (SRCX-FR-017/018): `resume_entry_index` intersects the ledger-derived
  resume index with the on-disk completion check — a recorded producing stage whose artifact is broken
  becomes the re-entry point (naming the missing artifact on stderr), later stages re-run in order, and
  a stage the run never recorded is out of the gate's scope, so a run paused at the spec gate is never
  failed for a missing `plan.md`. This demonstrably closes the "resume trusts the ledger" gap
  (SRCX-SC-003).
- **Prompt/template alignment**: the executive injects a deterministic `FEATURE FOLDER: specs/<NNN>-…`
  context line into the agent-authored markdown stages (specify/clarify/plan/tasks) so the agent writes
  exactly where the workspace computes and the gate asserts (SRCX-FR-013's property); the built-in
  specify/plan/tasks instructions and the seeded stage templates (scaffold +
  [`.3powers/templates/agents/`](../.3powers/templates/agents/)) now name the flat locations; the
  RUNLIVE contract patterns keep accepting both layouts, with `expected` naming flat first.
- **Two real executive seams fixed en route:** `produced_paths` now counts a path restored to its
  committed content (present pre-dispatch, clean post-dispatch), and a completion-gate re-run whose
  regenerated artifact is byte-identical to HEAD (an empty diff) satisfies its dispatch contract via
  the stage's prior recorded artifacts still on disk — nothing weakened for a first run.

## Verification

- Engine green under its own dev tooling: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest` — **643 passed, 1 skipped** (20 new in
  [`tests/test_run_workspace.py`](../engine/tests/test_run_workspace.py), naming every
  `SRCX-FR-001..018` and `SRCX-NFR-001..006`): flat write paths and three-layout resolution with the
  flat-wins precedence; the exact producing set; records linking real outputs without relocation; one
  `implement.md` per N-phase implement in deterministic order; ledger-only gate stages; deterministic
  max-plus-one allocation with the fail-fast collision edge; slugify rules + idempotence + bound +
  fallback; the completion gate's pass/absent/unrecorded/legacy-split cases as pure unit checks; a full
  fake-agent run leaving one flat, fully ledger-tracked folder (`3pwr verify` green); the wrong-folder
  spec blocked as `artifact_absent` and surfaced by both status commands; the headline
  delete-plan.md-then-resume scenario re-entering AT `plan` (never skipping to `oracle`), re-running
  later stages in order, with append-only history intact; resume-never-allocates; dry-run allocating
  nothing; and a pre-SRCX ledger verifying unchanged with the folder binding resolving to `None`.
- Self-application (NFR-006), diff-scoped to this branch: `3pwr gate run --path engine --adapter
  python --spec specs/017-run-artifact-workspace/spec.md --tier Standard --base main` — **verdict
  PASS**: format ✓, lint ✓, types ✓, tests ✓, diff_coverage **92.21% ≥ 80%** ✓, sast ✓,
  dependency_scan ✓, secret_scan ✓, gate_gaming ✓, spec_conformance ✓ (**24 requirements traced**);
  `spec_integrity` correctly *skipped* — no Spec-stage sign-off recorded yet for `SRCX` (a
  not-yet-approved spec is never blocked).

## Handoff — notes

- Spec 017 still needs the human spec-approval sign-off:
  `3pwr signoff --approver <you> --spec-id SRCX --stage spec --spec specs/017-run-artifact-workspace/spec.md`
  — after which the `spec_integrity` gate grades instead of skipping.
- Non-goals held: no existing feature migrated (both legacy layouts stay readable and runnable in
  place); no oracle test or code relocated into the feature folder; no new ledger entry type, signing
  change, or verdict-schema change; linked-path liveness stays a dispatch-time (RUNLIVE) concern; no
  cross-process allocation locking; markdown *content* beyond existence is not validated; the parent
  folder stays `specs/` (3PWR-FR-010).
- A legacy mid-flight run recorded before SRCX has no `oracle.md`/`implement.md`; resuming one re-runs
  those stages (producing the records) rather than skipping them — deterministic and safe, noted here
  as the intended behavior.
