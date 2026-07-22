# Plan 039 — `3pwr run --redo <stage>`: rewind a run to an earlier completed stage and revise it

**Git branch:** intended `feat/039-redo-stage-rewind-and-revise` (per the mandatory workflow, one
dedicated feature branch per plan; the plan file is **not** auto-committed — the maintainer commits).
*Note:* this plan file was authored during a session whose working tree also carried an unrelated,
uncommitted docs refresh on `docs/pypi-install-and-plan-catchup`; before implementation, land the plan on
its own `feat/039-*` branch cut from `main`.

**Origin (observed this session).** A live `3pwr run` in a test project stalled at **Build** with:

```
✗ artifact missing at Build — stage 'oracle' produced no expected artifact — expected oracle tests
  (tests/oracle/<spec>/… or oracle-tests/…), but the stage produced only off-target changes:
  specs-src/004-…/oracle.md
```

The oracle agent asked for a clarification (it wrote `oracle.md` instead of authoring the oracle tests),
which really means the **Spec is under-specified**. The maintainer wanted to go *back to the Spec stage*,
supply a clarifying revision, and let the lifecycle re-flow from there. Today that is impossible:

- **`--resume` is forward-only.** It re-enters at the *earliest uncompleted* step — `resume_start_index`
  returns `max(step-after-last-approved-gate, step-after-last-completed-step)`
  ([orchestrate.py:169](../engine/src/threepowers/orchestrate.py:169), reading completion from the signed
  ledger via `last_completed_step` [orchestrate.py:152](../engine/src/threepowers/orchestrate.py:152)). It
  will **never** re-dispatch an already-completed stage such as Spec or Plan.
- **`--revise` only works *at a paused human gate*.** A revise anywhere else is refused —
  *"nothing to revise — <ID> is not paused at a human gate"*
  ([cli/run.py:2005](../engine/src/threepowers/cli/run.py:2005)); `steering.revise_target`
  ([steering.py:98](../engine/src/threepowers/steering.py:98)) maps a gate → the paused step to
  re-dispatch. A run in a **stage failure** state (`artifact_missing` at Build) is not paused at a gate, and
  the Spec gate is already behind it.

So the run's only forward option is to keep re-running the failing oracle stage against the same ambiguous
spec. There is **no way to rewind to an arbitrary earlier completed stage and revise it.** This plan adds
one: `3pwr run --redo <stage> [--revise "<feedback>" | --revise-file <path>]`.

---

## Problem statement

Let a human (or a paused/failed run) **deliberately rewind** a run to any earlier *completed producing
stage*, optionally attaching revision feedback, and re-flow the lifecycle from there — while preserving the
trust spine (append-only, signed, offline-reconstructable) and the existing gate discipline.

Concretely, `3pwr run --redo spec --revise "the icon must be keyboard-focusable; name the ARIA label"`
should:

1. validate that `spec` (Spec / the `specify` step) is a **completed producing stage** for this run;
2. append a **signed rewind entry** to the ledger recording the target step, the reason/feedback, and the
   human who asked;
3. re-dispatch the Spec stage with the **original intent + the current `spec.md` + the feedback** (the same
   context shape STEER's revise builds), then follow the normal flow — pausing at the **spec-approval gate**
   for re-approval, then Plan → Build → … — with every downstream stage re-running because its input changed.

## Grounding (read this session; anchors for the implementation-plan agent)

- Lifecycle steps, in order, with kind + stage:
  [orchestrate.py:40 `LIFECYCLE_STEPS`](../engine/src/threepowers/orchestrate.py:40) —
  `discovery, specify, clarify, review-spec(gate), plan, review-plan(gate), tasks, oracle, implement,
  verify(verdict), review-verify(gate), signoff(gate), advance`. Stage labels:
  [lifecycle.py:14 `STAGES`](../engine/src/threepowers/lifecycle.py:14).
- Forward-only resume math: [orchestrate.py:169 `resume_start_index`](../engine/src/threepowers/orchestrate.py:169),
  [orchestrate.py:129 `step_index`](../engine/src/threepowers/orchestrate.py:129),
  [orchestrate.py:152 `last_completed_step`](../engine/src/threepowers/orchestrate.py:152),
  [orchestrate.py:137 `last_checkpoint_step`](../engine/src/threepowers/orchestrate.py:137).
- Resume/revise CLI wiring + the "not paused at a gate" refusal:
  [cli/run.py:1997](../engine/src/threepowers/cli/run.py:1997) (resume branch),
  [cli/run.py:2005](../engine/src/threepowers/cli/run.py:2005) (revise-outside-gate refusal),
  [cli/run.py:1505 `_run_revise`](../engine/src/threepowers/cli/run.py:1505),
  [cli/run.py:840–841](../engine/src/threepowers/cli/run.py:840) (`--resume` / `--revise` / `--revise-file`
  argument docs).
- Revise context builders to reuse: [steering.py:98 `revise_target`](../engine/src/threepowers/steering.py:98),
  [steering.py:103 `gate_artifact`](../engine/src/threepowers/steering.py:103),
  [steering.py:133 `revise_context`](../engine/src/threepowers/steering.py:133),
  [steering.py:86 `resolve_feedback`](../engine/src/threepowers/steering.py:86).
- Per-stage git commits + branch re-entry (GITX): `gitflow.ensure_run_branch(..., mode="resume")`
  ([cli/run.py:2079](../engine/src/threepowers/cli/run.py:2079)); the artifact-∧-ledger stage-completion
  gate lives in `completion` (`completion.resume_entry_index` [cli/run.py:2106](../engine/src/threepowers/cli/run.py:2106)).
- Spec-lock interaction: a spec edited after its Spec-stage seal fails `spec_integrity` with
  `spec_modified` ([docs/troubleshooting.md:175](../docs/troubleshooting.md:175),
  [docs/cli-reference.md:283](../docs/cli-reference.md:283)); the sanctioned re-seal is a fresh
  `signoff --stage spec`. A `--redo spec` re-run naturally regenerates and re-approves the spec, which
  **re-seals** it through the normal Spec gate — so the redo path must route through that gate, not around it.
- Existing troubleshooting entry to extend: **"artifact missing at <stage>"**
  ([docs/troubleshooting.md:60](../docs/troubleshooting.md:60)) — its Fix already notes "a common cause: it
  asked a question"; the new `--redo` doc is the missing "…and here's how to go back and answer it."

## Goals

- A `3pwr run --redo <stage>` flag that rewinds to an earlier **completed producing stage** and re-flows.
- Accept `<stage>` as either a stage label (`spec`, `plan`, `discovery`, `build`) or a step id
  (`specify`, `plan`, `oracle`, `implement`, …); resolve to the **earliest producing step** of that stage.
- Compose with `--revise "<msg>"` / `--revise-file <path>` to attach feedback (reusing `revise_context`).
- Preserve the trust spine: rewind is recorded by **appending** a signed entry, never by deleting/rewriting
  ledger history or git commits.
- Downstream stages re-run because their input changed; the redo routes back through the normal human gates
  (notably spec-approval re-seals the amended spec).
- Works from any run state a rewind makes sense in: a **stage failure** (the origin case), a **paused gate**,
  or a **completed-but-not-advanced** run.

## Non-goals

- No rewriting of git history (no `reset`/`rebase` of prior stage commits). The redo re-dispatches forward,
  producing new commits on the run branch; superseded artifacts stay in history, marked superseded in the ledger.
- No partial/branching runs or multiple concurrent redo targets. One rewind target at a time.
- No change to `--resume` semantics, `--json`, exit codes, or verdict bytes.
- Not a `revert` (that already exists for shipped work); `--redo` operates within an in-flight run.

## Workstreams

**A — CLI surface (`cli/run.py`).** Add `--redo STAGE` to the `run` subparser, valid only with neither a
fresh intent nor `--resume` semantics that contradict it (decide: `--redo` implies resuming an existing
`--spec-id`; require `--spec-id`). Allow `--revise`/`--revise-file` alongside `--redo`. Validate: the run
exists, `STAGE` resolves to a producing step, and that step is **recorded complete** for the spec-id
(else refuse with an actionable message listing the redo-able stages). Require an approver/reason for the
rewind (mirror the gate-action ergonomics).

**B — Rewind marker in the ledger + resume math (`ledger`, `orchestrate.py`).** Define an additive,
signed `run` payload `kind: "redo"` carrying `{ target_step, reason, feedback_ref, approver }`. Teach
`last_completed_step`/`resume_start_index` (or a new `redo_start_index`) to honor the **latest** redo entry:
completions of the target step and everything after it, recorded *before* that redo entry, no longer count —
so re-entry lands exactly at `step_index(target)`. Keep the append-only, offline-reconstructable guarantee:
`3pwr verify` must still pass, and status must render the rewind.

**C — Revise context reuse (`steering.py`, `cli/run.py`).** For `--redo <stage> --revise …`, build the
dispatch context from `revise_context` — original intent + the target stage's current artifact
(`gate_artifact`/the flat `specs-src/<NNN>-<slug>/<artifact>.md`) + the feedback — so the re-dispatched
stage sees why it's being redone. Record the feedback verbatim (as STEER does) in the redo ledger entry.

**D — Git + artifact-completion interaction (`gitflow`, `completion`).** On redo, re-enter the run branch
with `mode="resume"`; each re-dispatched stage commits as usual. Ensure the artifact-∧-ledger completion
gate treats the redo entry as the new floor so a re-dispatched stage is not judged "already complete" by a
pre-rewind record. Confirm no clean-start guard falsely trips.

**E — Spec-lock / gate routing (`speclock`, `orchestrate.py`).** When the target is Spec, the re-run must
flow through the `review-spec` gate so the amended spec is **re-approved and re-sealed** — never leaving a
`spec_modified` state. Verify the sealed-hash update path is the same one a manual `signoff --stage spec`
takes. Redo of a later stage (Plan/Build) must not disturb the existing spec seal.

**F — Documentation (this plan's explicit ask).**
- **`docs/cli-reference.md`** `run` section: document `--redo STAGE` next to `--resume`/`--revise`
  ([around cli-reference.md:840](../docs/cli-reference.md:840)) — what it rewinds to, that it re-flows
  through the human gates, and the redo-able stage list. Add a worked example.
- **`docs/troubleshooting.md`**: add a new entry (draft below) *and* cross-link it from the existing
  **"artifact missing at <stage>"** Fix ([troubleshooting.md:60](../docs/troubleshooting.md:60)).
- **`docs/getting-started.md`**: one line under "When gates go red" / the human-gate walkthrough noting
  that a run can also be rewound to an earlier stage with `--redo`.
- Keep internal spec/plan IDs out of all user-facing text (OSS-readiness convention; the guard
  `engine/tests/test_oss_readiness.py` enforces it).

**G — Tests (`engine/tests/`).** Unit-test the redo resolution + `redo_start_index` (rewind to specify,
plan, oracle; refuse gates/unknown/uncompleted stages). A ledger test proving `verify` still passes after a
redo entry. A run-level test (simulator/dry-run path) proving a `--redo spec --revise` re-dispatches Spec,
pauses at spec-approval, then re-flows Plan/Build. Trust-spine coverage stays ≥95% if `ledger`/`verify`
change.

## Draft troubleshooting entry (to land in `docs/troubleshooting.md`)

> ## Going back to an earlier stage to fix or clarify it
>
> **Symptom** — a stage keeps failing (commonly **"artifact missing at Build"** because the oracle wrote a
> question into `oracle.md` instead of authoring tests), and the real fix is upstream — the **spec or plan
> was ambiguous or wrong**. `--resume` only ever moves *forward* to the next unfinished stage, and
> `--revise` only works while the run is paused at a human gate, so neither lets you reopen an
> already-completed stage.
>
> **Cause** — the run recorded the earlier stage as complete, so 3Powers won't re-dispatch it on a plain
> resume. You need to explicitly *rewind* the run to that stage.
>
> **Fix** — rewind with `--redo`, optionally attaching the clarification as revision feedback. Naming the
> stage re-dispatches it and every stage after it (their inputs changed), re-flowing through the normal
> human gates:
>
> ```bash
> # go back to the Spec stage and hand the agent the clarification the oracle asked for
> 3pwr run --redo spec --revise "the user icon must be keyboard-focusable; specify its ARIA label" \
>          --spec-id 004 --approver "$(git config user.name)"
> ```
>
> The run re-generates the spec, pauses at **spec approval** for you to approve the amended (and re-sealed)
> document, then continues Plan → Build → Verify … from there. To rewind to a different stage, name it
> (`--redo plan`, `--redo build`); the redo-able stages are the completed producing stages of the run. The
> rewind is recorded in the signed ledger (verifiable offline); nothing in git history is rewritten.

## Open questions / decisions for the implementation-plan agent

1. **Flag shape.** `--redo <stage>` as its own flag vs. `--resume --redo <stage>`. Recommendation:
   standalone `--redo` that implies operating on an existing `--spec-id` (cleaner than overloading resume).
2. **Approver requirement.** Require `--approver`/`--reason` for a rewind (recommended — it's a deliberate,
   audited act) or allow a bare `--redo`? Recommend requiring them.
3. **Redo of a gate step vs. producing step.** Only allow producing steps (specify/plan/oracle/implement/
   discovery); a gate isn't a thing you "redo" — you re-reach it. Confirm the resolution maps a stage label
   to its earliest producing step.
4. **Interaction with an active deviation / partially shipped state.** Confirm `--redo` is refused once a
   run has advanced to Ship (use `revert` there instead).
