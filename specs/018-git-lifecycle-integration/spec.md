# Feature Specification: Git-Integrated Run Lifecycle — Mandatory Pre/Post-Stage Git Hooks, a Dedicated Branch per Run (Reusing the SRCX `<NNN>-<slug>` Run Identity), Clean-Start / Clean-Stop Enforcement, and Per-Stage Agentic Commits Authored as 3pwr

**Spec ID**: GITX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     GITX is the version-control-safety counterpart to the executive/workspace line: to RUNLIVE (011) —
     which added per-stage dispatch and the opt-out checkpoint commit (`3pwr(<spec-id>): <step>`, system
     git author, `--no-auto-commit`, best-effort/skipped when git is absent) — to SRCX (017), which
     allocates one flat `specs/<NNN>-<slug>/` folder per run, binds it to the run's spec-id in the signed
     ledger at run start, and resolves (never reallocates) it on `--resume` — and to AUTOX (014), which
     gave signed `run`/`failure` records, checkpoint-independent resume, and the stable exit-code/status
     contract. GITX changes the executive from committing *opportunistically* to committing *safely*: it
     makes git handling a mandatory pre-stage and post-stage hook that (A) isolates every run to its own
     branch — reusing SRCX's `<NNN>-<slug>` as the branch identity, NOT inventing a run number — (B)
     refuses to start when the working tree carries uncommitted changes not produced by the run and leaves
     it clean after every stage, and (C) commits each stage with an agent-written message attributed to a
     "3pwr" author whenever 3pwr itself makes the commit. It SUPERSEDES RUNLIVE-FR-010's opt-out
     checkpoint with a mandatory, branch-scoped, agentically-messaged, 3pwr-authored commit, keeping the
     signed-deviation escape hatch (3PWR-FR-057) as the only relaxation. Cross-refs: SRCX-FR-008/009/010/
     011, RUNLIVE-FR-010, AUTOX-FR-006/007/010, 3PWR-FR-006/017/037/057/070, 3PWR-NFR-001. Executive / VCS
     plumbing only; no trust-spine module (canonical/keys/ledger/verify) is changed, and no new ledger
     entry type, signing scheme, or verdict is introduced. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this is executive / version-control plumbing — the pre/post-stage git hook, the per-run
     branch, the clean-tree guard, the stage commit, and the author attribution — NOT the trust-spine
     modules (canonical/keys/ledger/verify), which are not touched. It weakens no gate (3PWR-FR-032) and
     adds no new trust primitive. The real regression risk is DATA SAFETY: switching branches or
     committing on a developer's behalf must never discard, carry, or clobber their unrelated uncommitted
     work, and must never rewrite the user's git config or history. Both halves are turned into explicit,
     tested requirements: the clean-start guard refuses (never force-checks-out) when unrelated changes are
     present (GITX-FR-007, GITX-NFR-003), and the author override + commit path never mutate global git
     config, never force-push, and never rewrite history (GITX-NFR-004). The ledger touch is strictly
     additive — one field on SRCX's existing `run`/`start` payload, within the existing `run` entry type,
     no new type and no signing change — so `3pwr verify` stays green on old and new ledgers (GITX-NFR-002).
     This is the same latitude and reasoning SRCX (017) used to land on Standard for its folder allocation
     and `run`/`start` field, AUTOX (014) for its `run`/`failure` records and resume contract, and CLIUX
     (015) for its output plumbing. Cosmetic was considered and rejected: this drives run control-flow and
     writes to the developer's repository (branches and commits), so it must hold data-safety and
     offline/verify invariants under test. High-risk was considered and rejected: no trust-spine module
     changes and mutation-graded thresholds do not apply to this plumbing. Standard applies. -->

**Status**: Draft

**Input**: User request: "Whenever `3pwr` runs manually or in auto mode we must check the current git state
and do that with a pre and after stage hook. This is mandatory and MUST exist. Changes will always be done in
a dedicated new branch with the run number and description when no stage exists at all; or if a stage already
exists we must switch to the branch and continue our work there. And we cannot start if there are uncommitted
changes open that are not caused by the run. So we start clean and stop clean in the version history. This is
very important. And each stage commits with an agentically-written commit comment — and the author must be
named `3pwr` if executed by `3pwr` only." Follow-up decisions settled four specifics: (1) the "run number and
description" is NOT redefined here — it is SRCX's already-specified `<NNN>-<slug>` run identity (spec 017),
which GITX reuses as the branch name; (2) on resume / when the run already has stages, GITX **reuses the run's
existing branch** and continues committing there; (3) the discipline is **mandatory by default and relaxable
only via a signed `3pwr deviation`** (3PWR-FR-057), never a silent flag; (4) it applies to **both** `3pwr run`
(auto and manual-gate) **and** the manual command-by-command `/3pwr.*` drive; (5) it is **local only** —
pushing the branch and opening a PR remain the human's step. A codebase review confirmed the seams:
`runner.py` holds `commit_checkpoint` (opt-out, static message, system author, per-produced-path commit) and
the `worktree_state`/`produced_paths` pre/post snapshot; `cli.py`'s `dispatch()` runs the per-stage loop with
`auto_commit = s.auto_commit() and not --no-auto-commit`; SRCX binds the run folder to the spec-id in the
`run`/`start` ledger entry; `3pwr deviation` is the signed, reversible relaxation mechanism.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):** RUNLIVE (spec 011) added the per-stage commit checkpoint —
  `commit_checkpoint(cwd, spec_id, step, paths)` stages only a stage's *produced* paths (never a blanket
  `add -A`), commits with the static message `3pwr(<spec-id>): <step>`, and returns a short SHA or `None`.
  Today it is **opt-out** (`auto_commit = s.auto_commit() and not --no-auto-commit`), uses the **system git
  author**, commits to **whatever branch is checked out**, and is **best-effort** — when git is unavailable or
  nothing is staged it silently returns `None` and the run carries on. The produced-path set is computed by a
  pre/post snapshot (`worktree_state` → `produced_paths`), which excludes engine transcripts
  (`.3powers/runs/`), so the exact files a stage authored are already known. SRCX (spec 017) allocates one flat
  `specs/<NNN>-<slug>/` folder per run — `<NNN>` = max existing prefix + 1, `<slug>` = a deterministic
  slugify of the intent (SRCX-FR-008/009) — records that folder against the run's spec-id via an additive
  field on the signed `run`/`start` ledger entry (SRCX-FR-011), and on `--resume` **resolves the existing
  folder and never reallocates** (SRCX-FR-010). AUTOX (spec 014) gave the signed `run`/`failure` record with a
  named failure class, surfaced by `3pwr run --status` / `3pwr status`, and checkpoint-independent resume from
  the ledger. `3pwr deviation` (3PWR-FR-057) is the first-class signed, reversible relaxation; `3pwr revert`
  (3PWR-FR-070) is the reversibility primitive.
- **Where the seams are:** (1) the run has **no branch discipline** — a `3pwr run` commits onto whatever
  branch the developer happens to be on, including `main`, so a run's work is not isolated and not
  distinguishable in history. (2) There is **no clean-start guard**: a run started on a dirty tree mixes the
  developer's unrelated uncommitted edits into the run's checkpoints (the produced-path staging limits the
  blast radius, but nothing *refuses* the dirty start), and nothing guarantees the tree is clean when the run
  stops. (3) The commit **message is static** (`3pwr(<spec-id>): <step>`) — it does not describe what the
  stage actually did. (4) The commit **author is the system user** — there is no way to attribute a
  3pwr-made commit to a distinct `3pwr` identity, so a reader cannot tell an engine commit from a human one.
  (5) The whole behavior is **opt-out** (`--no-auto-commit`) and **skipped when git is absent**, so the
  "clean history" guarantee the user wants is not actually enforced.
- **The run identity, reused not redefined:** the "run number and description" the branch is named from is
  SRCX's `<NNN>-<slug>` (spec 017). GITX does not allocate a number or derive a slug — it consumes SRCX's
  allocated run identity and the ledger binding that already recovers it offline on resume. GITX adds one
  thing to that binding: the run's branch name, so a resume recovers the branch the same way it recovers the
  folder.
- **Guardrail:** executive / version-control plumbing only. No gate, threshold, verdict bytes, ledger
  chain/signing format, exit-code contract, or the two mandatory human gates (3PWR-FR-006 spec approval,
  3PWR-FR-037 sign-off) change. The ledger addition is strictly additive — one field on SRCX's existing
  `run`/`start` payload, within the existing `run` entry type — so `3pwr verify` stays green on both old and
  new ledgers, and the whole feature is offline and deterministic in its git mechanics (3PWR-NFR-001). The
  agent-written commit *message* is the only model-touched output, and it is captured as commit data, never
  as a gate or ledger input. Pushing to a remote and opening a pull request stay out of scope (the human's
  step, per the repository's git conventions).

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** push any branch to a remote or open a pull request; GITX is local branch + commit hygiene
  only. Pushing the run branch and opening a PR against the base remain the human's step, per the
  repository's git conventions.
- Does **not** redefine, allocate, or derive the run number or description; the branch name reuses SRCX's
  already-allocated `<NNN>-<slug>` run identity (SRCX-FR-008/009) and its ledger binding (SRCX-FR-011). GITX
  adds only the branch name to that binding.
- Does **not** rebase, squash, cherry-pick, amend, force-push, or otherwise rewrite existing git history, and
  does **not** resolve merge conflicts; it only creates/switches the run branch (off the base) and appends
  one commit per stage.
- Does **not** mutate the user's git configuration (`git config user.name` / `user.email`, global or local);
  the 3pwr author attribution is applied per-commit and leaves the developer's git identity untouched.
- Does **not** add a new ledger entry type, change the signing scheme, or alter the verdict schema — the only
  addition is one field (the branch name) on SRCX's existing `run`/`start` payload, within the existing `run`
  entry type.
- Does **not** change the deterministic gate suite, any tier threshold, exit codes, or the two mandatory
  human gates (3PWR-FR-006, 3PWR-FR-037), and does **not** route through, alter, or read the deterministic
  verdict (3PWR-NFR-001).
- Does **not** change SRCX's flat-folder allocation or completion gate, and does **not** change AGENTX's
  per-role model/integration selection — it only decides *who is credited as author* when 3pwr makes a
  commit, and *on which branch* the run's commits land.
- Does **not** implement user-supplied `.git/hooks` shell hooks; the pre-stage and post-stage hooks in this
  spec are the engine's own mandatory lifecycle hooks, not the git-native client-side hook files.
- Does **not** manage git for non-lifecycle commands (`keygen`, `verify`, `gate` outside a run, etc.), and
  does **not** migrate, rename, or rewrite any existing run's branch or commits.
- Does **not** add cross-machine or cross-process branch locking; branch safety is local-filesystem,
  single-run-per-repo, consistent with SRCX's allocation non-goal.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every run is isolated to its own branch (Priority: P1)

A user running `3pwr run "<intent>"` wants the whole run's work to land on a dedicated branch named for that
run — never scribbled onto `main` or whatever branch they happened to be on — so the run's commits are one
clean, self-identifying line of history they can review, keep, or discard as a unit.

**Acceptance Scenarios**:

1. **Given** a repository checked out on the base branch with a run whose SRCX identity is
   `017-run-artifact-workspace`, **When** a fresh `3pwr run` starts (no prior stage recorded), **Then** the
   engine creates and switches to a dedicated run branch derived from that identity (e.g.
   `3pwr/017-run-artifact-workspace`) before the first stage commits, and every stage commit lands on that
   branch, not on the base.
2. **Given** a run already in progress on its dedicated branch, **When** the user runs
   `3pwr run --resume --spec-id <ID>`, **Then** the engine switches back to that same run branch and
   continues committing there — it does not create a new branch and does not allocate a new run number.
3. **Given** the run's branch name, **When** it is recomputed from the run's SRCX identity and the configured
   prefix on another machine, **Then** it is byte-identical.

### User Story 2 - Start clean, stop clean (Priority: P1)

A user wants a run to begin only from a clean working tree and to leave a clean working tree behind: it must
refuse to start when there are uncommitted changes that are not the run's own, and after each stage nothing
the run produced is left uncommitted — so the version history, not an ambiguous dirty tree, is the record of
what happened.

**Acceptance Scenarios**:

1. **Given** a working tree with uncommitted edits to files unrelated to the run, **When** the user starts a
   run, **Then** the run refuses to start, names the offending uncommitted paths, and names the signed
   deviation that would permit it — it never silently proceeds and never discards those edits.
2. **Given** a clean working tree, **When** each stage of the run completes, **Then** the stage's produced
   changes are committed and the working tree carries no uncommitted changes produced by the run.
3. **Given** a run that pauses at a human gate or completes, **When** the working tree is inspected, **Then**
   every executed stage is committed on the run branch and nothing the run produced is left dangling.

### User Story 3 - Each stage is one meaningful, attributable commit (Priority: P1)

A user reading the run branch wants each stage to be a single commit whose message describes what that stage
actually did (not a fixed label), and — when 3pwr made the commit — whose author is `3pwr`, so the history is
readable and it is unmistakable which commits the engine authored versus a human.

**Acceptance Scenarios**:

1. **Given** a stage that produced changes, **When** the post-stage hook commits them, **Then** there is
   exactly one commit for that stage, its message is an agent-written description of the stage's work carrying
   the stage and the run's spec id, and it stages only the paths the run produced.
2. **Given** the native executive (`3pwr run`) made the commit, **When** the commit's author is inspected,
   **Then** it is the configured `3pwr` identity; **and Given** a human committed a stage by hand in the
   manual drive, **Then** that commit keeps the human's own author identity.
3. **Given** the agent produces no usable commit message, **When** the post-stage hook commits, **Then** it
   falls back to a deterministic default message (naming the stage and spec id) so a commit is never blocked
   on message generation.

### User Story 4 - The manual drive gets the same safety (Priority: P1)

A user driving the lifecycle command-by-command with the `/3pwr.*` prompts (rather than `3pwr run`) wants the
same guarantees — work isolated to the run branch, a clean start, and each completed stage committed — so the
manual path cannot bypass the git discipline the orchestrated path enforces.

**Acceptance Scenarios**:

1. **Given** a manual drive, **When** the user reaches a stage boundary command (e.g. `3pwr advance`),
   **Then** it refuses to advance if the run is not on its dedicated branch or the completed stage is not
   committed, naming the condition and the fix.
2. **Given** a manual drive on a clean tree, **When** the user establishes the run and works through stages,
   **Then** the engine makes the run branch available and the same clean-start / branch-isolation guarantees
   apply as in `3pwr run`.

### User Story 5 - Mandatory, but relievable on the record (Priority: P2)

A user who genuinely must proceed off the happy path — e.g. start a run atop unrelated uncommitted work in an
emergency — wants a recorded, reversible way to relax a specific guard, rather than a silent flag that erases
the guarantee for everyone.

**Acceptance Scenarios**:

1. **Given** the clean-start guard is blocking a run, **When** the user records a signed
   `3pwr deviation --gate git_clean_start --approver <you> --note "<why>"`, **Then** the run proceeds, the
   relaxation is a signed ledger entry, and it is reversible (revocable) — the guarantee is relaxed on the
   record, not removed.
2. **Given** no deviation is recorded, **When** a guard would block, **Then** there is no plain flag that
   disables it; the superseded `--no-auto-commit` no longer silently turns the stage commit off.

### Edge Cases

- The directory is not a git repository, or git is not installed / not on PATH → the run refuses to start and
  names the condition (git is now a precondition, replacing today's best-effort skip).
- The working tree is dirty but *every* uncommitted change is one of the run's own produced paths (e.g. a
  prior stage crashed after writing but before committing) → tolerated: those changes belong to the run and
  are swept into the next post-stage commit; only *unrelated* changes block the start.
- The repository is on a detached HEAD or has no branch yet → the engine still creates the run branch off the
  current commit before committing.
- The run branch already exists on resume → switch to it and continue; do not recreate it. A fresh run cannot
  collide, because SRCX guarantees the `<NNN>` prefix is unique (allocation fails fast if the folder already
  exists), and the branch inherits that uniqueness.
- A stage produced no changes (e.g. a clarify stage that edited nothing) → no empty commit is forced; the
  stage is recorded per SRCX/AUTOX and clean-stop holds trivially.
- In the manual drive, a human already committed the stage's produced paths → the post-stage handling detects
  the paths are already committed and does not create a second commit; that commit keeps the human's author.
- A `--dry-run` / simulated run dispatches nothing and writes nothing → the git hooks are a live-run concern
  and are a no-op (or are not invoked) on the simulated path, keeping `--dry-run` side-effect-free and
  offline, consistent with SRCX's dry-run no-op.
- A stage edits a file outside its declared file scope (3PWR-FR-017) → that is the executive-boundary concern,
  not the git hook's; the post-stage commit still stages only the run's produced paths, and the out-of-scope
  edit is caught by the boundary rule, which pauses for a human decision.
- No `git.yaml` present, or it is malformed → the engine falls back to the shipped defaults (branch prefix,
  base branch, `3pwr` author identity), warning once, never crashing (mirroring `ui.yaml`'s tolerance).

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where a value is derived or parsed (3PWR-FR-024). The branch-name shape,
  the `git.yaml` keys, the 3pwr author identity, and the deviation gate names appear where they ARE the
  contract under specification (the same latitude SRCX took for its folder shape and ledger field, and
  AUTOX/CLIUX for exit codes / `ui.yaml`), not as implementation detail (3PWR-FR-007). Named
  modules/functions/paths are context in the non-normative sections only.
-->

### Functional Requirements

#### A. Mandatory pre/post-stage git hooks

- **GITX-FR-001**: The system shall run a mandatory git pre-stage hook before every lifecycle stage that
  produces changes and a mandatory git post-stage hook after each such stage completes; both hooks shall run
  on every supported way of driving the lifecycle and shall not be silently skippable — the only way to
  relax any guard they enforce is a recorded signed deviation (GITX-FR-014).
  - *Acceptance*: for a live run, each producing stage triggers the pre-stage git check before its work
    begins and the post-stage git commit after it succeeds; there is no plain flag or config that turns the
    hooks off without a signed deviation.
  - *Property*: the set of stages the hooks wrap is exactly the run's producing stages (those that author an
    artifact or code); pure gate/verdict/sign-off/advance steps are not wrapped by the post-stage *commit*
    but are still subject to the branch and clean-tree guarantees.
- **GITX-FR-002**: The system shall treat a working git repository as a precondition for starting a run: when
  the target directory is not a git repository or git is unavailable, the run shall refuse to start and name
  the condition, rather than proceeding without version control.
  - *Acceptance*: starting a run outside a git repository, or with git absent from PATH, yields a blocked
    start naming the missing-git condition on the non-gate-red (setup/dispatch) exit path.
  - *Property*: the git-precondition check is a pure function of the repository/environment state, offline and
    deterministic (3PWR-NFR-001).

#### B. Dedicated branch per run

- **GITX-FR-003**: When a run has no prior recorded stage (a fresh start), the pre-stage hook shall create and
  switch to a dedicated run branch named from the run's SRCX `<NNN>-<slug>` identity (SRCX-FR-008/009) and the
  configured branch prefix, branched off the configured base, before any stage commit occurs.
  - *Acceptance*: a fresh run whose SRCX identity is `017-run-artifact-workspace` and whose prefix default is
    `3pwr/` creates and checks out `3pwr/017-run-artifact-workspace`, and the first stage commit lands on it.
  - *Property*: the branch name is a deterministic function of the configured prefix and the run's SRCX
    identity — identical inputs yield a byte-identical branch name on any machine (3PWR-NFR-001); GITX does
    not allocate the number or derive the slug (that is SRCX's).
- **GITX-FR-004**: When a run already has a recorded stage (a resume, or a run whose branch already exists),
  the pre-stage hook shall switch to that run's existing dedicated branch and continue committing there, and
  shall never create a new branch or allocate a new run number for the same run.
  - *Acceptance*: `3pwr run --resume --spec-id <ID>` for a run on `3pwr/017-…` re-enters that branch and
    creates no new branch; the count of run branches is unchanged by a resume.
  - *Property*: for a given run, at most one dedicated branch exists across its whole lifecycle, regardless of
    how many times it is resumed.
- **GITX-FR-005**: The system shall bind the run's branch name to the run in the signed ledger, as an additive
  field on SRCX's existing `run`/`start` payload, so a later resume recovers the branch offline from the
  ledger alone — without scanning branches or guessing.
  - *Acceptance*: the `run`/`start` ledger entry for a run records its branch name, and a resume reads it back
    to switch onto the branch; `3pwr verify` passes on a ledger carrying the new field.
  - *Property*: the recorded branch value is a pure function of the branch-naming inputs (GITX-FR-003) and is
    verifiable offline; no new ledger entry type is introduced (GITX-NFR-002).
- **GITX-FR-006**: The system shall never commit a run's changes on the configured base/default branch; when
  the repository is on the base branch (or a detached HEAD, or has no branch), the pre-stage hook shall
  establish the run branch first and commit only there.
  - *Acceptance*: starting a run while checked out on the base branch results in the run's commits landing on
    the run branch, and the base branch's tip is unchanged by the run.
  - *Property*: no commit the engine creates during a run has the base branch as its containing ref at the
    time of commit.

#### C. Clean start / clean stop

- **GITX-FR-007**: The pre-stage hook shall refuse to start a run when the working tree contains uncommitted
  changes that were not produced by the run; it shall name the offending paths and the signed deviation that
  would permit proceeding, and it shall never discard or force past those changes.
  - *Acceptance*: a run started with unrelated uncommitted edits is blocked, the message lists those paths and
    names `3pwr deviation --gate git_clean_start …`, and the edits remain untouched on disk.
  - *Property*: "changes produced by the run" is defined by the run's produced-path set (the pre/post
    working-tree snapshot); any uncommitted change outside that set is "unrelated" and triggers the refusal.
- **GITX-FR-008**: After each stage's post-stage commit, the system shall leave no uncommitted changes that
  the run produced; a run that completes or pauses at a human gate shall leave every executed producing stage
  committed on the run branch with nothing the run produced left uncommitted.
  - *Acceptance*: after any stage, `git status` shows no uncommitted run-produced paths; at run completion or
    at a human-gate pause, each executed producing stage has its commit and the tree is clean of run output.
  - *Property*: immediately after a successful producing stage, the run's produced-path set has an empty
    intersection with the working tree's uncommitted-change set.
- **GITX-FR-009**: The system shall surface the git lifecycle state — that the run started clean, which branch
  it is on, and that each executed stage is committed — through the run status view (`3pwr run --status` /
  `3pwr status`), consistent with the existing status semantics.
  - *Acceptance*: the status view reports the run's branch and a per-stage committed indication derived from
    the ledger/branch, alongside the existing stage tracker.
  - *Property*: the reported git state is a deterministic function of the ledger and the branch's commits — no
    model call and no network (3PWR-NFR-001).

#### D. Per-stage commit — agentic message and 3pwr authorship

- **GITX-FR-010**: The post-stage hook shall commit each producing stage's changes as exactly one commit,
  staging only the paths the run produced (never a blanket `add -A`), superseding RUNLIVE-FR-010's opt-out
  checkpoint with a mandatory stage commit.
  - *Acceptance*: after a producing stage, exactly one commit exists for it on the run branch containing only
    the run's produced paths; unrelated files are never swept in.
  - *Property*: the committed path set equals the stage's produced-path set (the pre/post snapshot), minus
    engine transcript paths already excluded (`.3powers/runs/`).
- **GITX-FR-011**: The commit message for each stage shall be an agent-written description of what that stage
  did — not a fixed label — and shall carry the stage and the run's spec/requirement id for traceability;
  when no usable agent message is available, the system shall fall back to a deterministic default message so
  a commit is never blocked on message generation.
  - *Acceptance*: a stage commit's message describes the stage's actual work and includes the stage name and
    the run's spec id; with the agent message absent, the message is the deterministic fallback naming the
    stage and spec id.
  - *Property*: the message always contains the stage identifier and the run's spec id; the descriptive body
    is the agent's output when present and the deterministic fallback otherwise (the message text is commit
    data, never a gate or ledger input).
- **GITX-FR-012**: When 3pwr itself creates the commit (the native executive's post-stage commit, or an
  engine commit command), the system shall attribute the commit's author to the configured `3pwr` identity;
  when a human creates the commit by hand, the commit shall retain the human's own author identity.
  - *Acceptance*: a commit made by `3pwr run` shows the configured `3pwr` author; a commit a human makes in
    the manual drive shows the human's author.
  - *Property*: a commit's author equals the configured `3pwr` identity if and only if the engine created that
    commit.
- **GITX-FR-013**: The system shall make a run auditable from git history alone — one dedicated branch per
  run, one commit per producing stage, each commit attributable (3pwr vs human) and traceable to its stage
  and the run's spec id.
  - *Acceptance*: reading only the run branch's log, a reviewer can enumerate the run's stages in order, see
    what each did, and tell which commits 3pwr authored.
  - *Property*: the number of engine stage commits on the run branch equals the number of producing stages the
    run executed that produced changes.

#### E. Enforcement, configuration, and scope

- **GITX-FR-014**: The git discipline (git precondition, branch isolation, clean start, mandatory stage
  commit) shall be mandatory by default and relaxable only via a recorded, reversible signed deviation
  (3PWR-FR-057) targeting a named guard (at least `git_clean_start` for the clean-start guard and
  `git_stage_commit` for the mandatory commit); the plain `--no-auto-commit` opt-out shall be superseded by
  this deviation path.
  - *Acceptance*: with no deviation, a guard cannot be disabled by a flag; recording the corresponding signed
    deviation lets the run proceed and appears as a signed, revocable ledger entry; `--no-auto-commit` no
    longer silently disables the stage commit.
  - *Property*: each relaxable guard maps to exactly one named deviation gate, and a relaxation is always a
    signed ledger entry (never a silent config toggle).
- **GITX-FR-015**: The system shall read git-integration preferences from `.3powers/config/git.yaml` — at
  least the branch prefix, the base branch, and the `3pwr` author identity (name and email) — applied to the
  run's git handling only, with documented defaults; a missing or malformed file shall fall back to those
  defaults.
  - *Acceptance*: a `git.yaml` setting changes the branch prefix / base / author deterministically; with no
    file (or a malformed one) the shipped defaults apply and the run still succeeds with a single warning on a
    malformed file.
  - *Property*: the resolved git configuration is a pure function of `git.yaml` and the shipped defaults —
    identical inputs yield identical branch names and author attribution (3PWR-NFR-001).
- **GITX-FR-016**: The git discipline shall apply to both `3pwr run` (auto and manual-gate modes) and the
  manual command-by-command `/3pwr.*` drive; in the manual drive, a stage-boundary command (e.g. `advance`)
  shall refuse when the run is not on its dedicated branch or the completed stage is not committed, and the
  engine shall provide a way to establish the run branch for a manual drive.
  - *Acceptance*: an `advance` in the manual drive refuses off-branch or with an uncommitted completed stage,
    naming the condition and the fix; a manual drive can establish and work on the run branch with the same
    clean-start guarantee as `3pwr run`.
  - *Property*: no supported way of driving the lifecycle can commit a stage's work off the run branch or from
    a dirty (unrelated) start without a signed deviation.

### Non-Functional Requirements

- **GITX-NFR-001**: The git mechanics — branch naming and creation/switch selection, clean-tree detection,
  produced-path selection, and author attribution — shall be deterministic and fully offline (no network, no
  model, no provider tokenizer); the agent-written commit message is the only model-touched output and is
  captured as commit data, never as a gate or ledger input (ref 3PWR-NFR-001).
  - *Acceptance*: the feature's git-mechanic tests run with networking disabled and yield identical branch
    names, clean-tree verdicts, and author attribution for identical inputs; message generation is exercised
    with a simulated agent.
- **GITX-NFR-002**: The feature shall add only one additive field (the branch name) on SRCX's existing
  `run`/`start` payload, within the existing `run` entry type; it shall introduce no new ledger entry type, no
  signing change, and no verdict-schema change, so `3pwr verify` stays green across old and new ledgers.
  - *Acceptance*: `3pwr verify` passes on a ledger containing the branch field, and a pre-GITX ledger still
    verifies unchanged.
- **GITX-NFR-003**: The feature shall never discard, carry, or clobber a developer's unrelated uncommitted
  work: branch creation/switch and commits shall be refused (not forced) whenever they would move or overwrite
  changes outside the run's produced-path set.
  - *Acceptance*: with unrelated uncommitted edits present, the run refuses rather than switching branches or
    committing over them, and those edits are byte-identical on disk afterward.
- **GITX-NFR-004**: The feature shall not mutate the user's git configuration (global or local
  `user.name`/`user.email`) and shall never force-push or rewrite existing history; the `3pwr` author
  attribution shall be applied per-commit without changing the developer's configured git identity.
  - *Acceptance*: after a run, the developer's `git config user.name`/`user.email` are unchanged, no history
    is rewritten, and no force operation is performed; only the run branch and its new commits are added.
- **GITX-NFR-005**: No third-party runtime dependency shall be introduced (git via the existing subprocess
  path), the engine shall stay green under its own gates across this change, and `docs/STATUS.md` shall remain
  the single home of implementation status (ref 3PWR-NFR-004/006, DOCX-NFR-003).
  - *Acceptance*: the dependency manifest is unchanged; the self-application gate run plus ruff/mypy/pytest are
    green; STATUS is updated once at delivery.

## Success Criteria *(mandatory)*

- **GITX-SC-001**: Every `3pwr run` isolates its work to a dedicated branch named from SRCX's `<NNN>-<slug>`
  run identity — created off the base on a fresh start, reused on resume — and never commits the run's changes
  on the base branch.
- **GITX-SC-002**: A run refuses to start when the working tree has uncommitted changes not produced by the
  run (naming them and the deviation), and after every stage — and at completion or a human-gate pause — the
  working tree carries no uncommitted run-produced changes.
- **GITX-SC-003**: Each producing stage is exactly one commit that stages only the run's produced paths, with
  an agent-written message carrying the stage and spec id (deterministic fallback when the agent yields none).
- **GITX-SC-004**: A commit's author is the configured `3pwr` identity when the engine created it and the
  human's identity when a human created it; the developer's git config is never mutated and no history is
  rewritten or force-pushed.
- **GITX-SC-005**: The discipline is mandatory by default and relaxable only via a signed, reversible
  deviation on a named guard; the plain `--no-auto-commit` opt-out is superseded, and git is a precondition
  (a non-git or git-absent start is refused).
- **GITX-SC-006**: The discipline holds on both `3pwr run` (auto and manual-gate) and the manual `/3pwr.*`
  drive — no supported lifecycle path commits off the run branch or from a dirty unrelated start without a
  deviation — and the run's branch + committed state is surfaced by `--status`; `3pwr verify` passes on old
  and new ledgers with only the additive branch field.
- **GITX-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test naming
  the GITX-FR id, or a recorded output/documentation review where the rendered git/branch/commit state is what
  is asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id GITX --stage spec --spec specs/018-git-lifecycle-integration/spec.md`; appended to the signed ledger)_ | | |
