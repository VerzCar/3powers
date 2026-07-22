---
goal: Fresh-run isolation (next-free run id over folders+branches+ledger), a fresh-vs-resume branch guard, base-branch fetch off origin, an advisory per-working-tree run lock, and the first v1.0.0 PyPI release
version: 1.0
date_created: 2026-07-22
last_updated: 2026-07-22
owner: 3Powers maintainers
status: 'Planned'
tags: [feature, bug, architecture, infrastructure, process]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This implementation plan operationalizes source plan `plan/038-fresh-run-isolation-and-base-branch.md`. It
fixes a live defect in which a fresh `3pwr run "<intent>"` **silently continued a prior run's branch and
feature folder** — Discovery (the first producing stage) checked out the stale `3pwr/<NNN>-<slug>` branch
and built on top of it — and it makes a fresh run always a completely new, isolated unit of work: its own
next-free run id over the **union** of on-disk folders + git branches + the signed ledger, its own
dedicated branch created off the configured base, branched off the latest `origin/<base>` after a
best-effort fetch, and safe when many developers and agents work concurrently only through 3Powers. Resume
stays explicit and unchanged (`3pwr run --resume --spec-id <NNN>`). Once the fix is green and on the release
commit, this same unit of work cuts the first `v1.0.0` tag release and publishes the `threepowers`
distribution to PyPI via tokenless GitHub Actions Trusted Publishing (OIDC), making it installable with
`uv tool install threepowers` / `uvx threepowers`.

The work is split into seven phases mapping to the source plan's workstreams (A–G) plus a dedicated
Verification phase, in the plan's suggested handover order: Phase 1 (A — union run id) → Phase 2 (B —
fresh-vs-resume intent + guard) → Phase 3 (C — fetch + `origin/<base>` + config) → Phase 4 (D — advisory
run lock) → Phase 5 (E — docs) → Phase 6 (Verification — the regression that fails without the fix + the
whole-engine gates) → **Phase 7 (G — v1.0.0 release + PyPI Trusted Publishing), strictly last**. Workstream
F (tests) does not get its own phase; each behavior-changing phase (1–4) ships its own tests in the same
phase, and Phase 6 adds the cross-cutting regression + full-engine verification. **All phases execute
sequentially (no `[P]` marking)** because Phases 1–4 all edit the two shared hotspots
`engine/src/threepowers/gitflow.py` and `engine/src/threepowers/cli/run.py` (see CON-001, RISK-007), and
Phase 7 must not begin until Phases 1–6 are green on the release commit so the `v1.0.0` tag captures the
fix (CON-002).

Execution note (per `AGENTS.md`/`CLAUDE.md`): **all Python changes under `engine/src/threepowers/` with
tests under `engine/tests/` are performed by the python-engineer agent** at implementation time — Phases
1–4 and Phase 6 are engine phases and each is scoped to hand off to that agent. The release workflow
(`.github/workflows/release.yml`), `engine/pyproject.toml` metadata, and the `docs/`/`README.md`/
`CHANGELOG.md` edits (Phases 5 and 7) are ordinary changes in the same unit of work. Every behavior change
ships with a matching `docs/` update in the same unit of work. The trust spine (`canonical`, `keys`,
`ledger`, `verify`, `speclock`, `anchor`) stays **untouched** and ≥95% coverage; id allocation, fetch, and
the run lock are notifications-style isolation — never a gate, verdict, or ledger *input* (CON-003).

## 1. Requirements & Constraints

- **REQ-A**: A fresh run's `<NNN>` is the next-free over the **union** of on-disk `specs-src/` (and legacy
  `specs/`) `NNN-` prefixes + git branch numbers (`<branch_prefix><NNN>-*`, local and — where cheap —
  remote) + signed ledger `run`/`start` `spec_id`s, computed as `max(union) + 1`, so a fresh run always
  gets a brand-new folder AND a brand-new branch even when a prior run lives only on an unmerged branch or
  only in the ledger (Workstream A, Decision 1).
- **REQ-B**: `ensure_run_branch` takes an explicit fresh-vs-resume intent; a **fresh** run REFUSES with a
  named, actionable error (surfaced as the setup exit) if the computed branch already exists (never adopts
  it) and points at `3pwr run --resume --spec-id <NNN>`; a **resume** run re-enters the ledger-recorded
  branch exactly as today; the pre-stage hook keeps a mid-run stage on its branch (Workstream B, Decision
  2).
- **REQ-C**: A fresh run branches off the latest `origin/<base>` after a best-effort fetch, opt-in via new
  `git.yaml` keys `fetch_base` (default `true`) and `remote` (default `origin`); the local `<base>` ref is
  never fast-forwarded or mutated; offline / no-remote / detached-HEAD / unborn-repo / fetch-failure all
  fall back to local-base then current-HEAD with at most a one-line warning; `base_branch: develop` works
  with and without fetch (Workstream C, Decisions 3, 4, 6).
- **REQ-D**: An advisory per-working-tree run lock (`.3powers/run.lock`, recording `{pid, host, started_at}`)
  is acquired at the top of `cmd_run` for both fresh and resume paths and released in a `finally`; a second
  concurrent run in the SAME working tree fails fast with a message naming the other run; separate
  clones/worktrees each hold their own lock and never contend; a stale lock (dead pid or mtime past a
  generous TTL) self-heals; a lock-write failure degrades to a warning and never blocks the run (Workstream
  D, Decisions 5, 8).
- **REQ-E**: Every behavior change ships with a matching `docs/` update in the same unit of work — the
  fresh-run isolation guarantee, the big-team concurrency model, the new `git.yaml` keys, and the sandbox
  clarification (`3pwr run` isolation = dedicated branch + per-stage commits + signed ledger; the sanitized
  worktree is oracle-dispatch-only; a worktree-isolated run mode is future work) (Workstream E, Decision 7).
- **REQ-F**: A regression test that FAILS without the fix — a prior run's branch/folder exists only on an
  unmerged branch → a fresh run gets a NEW id + NEW branch off base, never re-entering the stale one —
  exercising `next_run_number` (union) + `ensure_run_branch(mode="fresh")` together (Workstream F).
- **REQ-G**: After Phases 1–6 are green on the release commit, `threepowers 1.0.0` is published to PyPI via
  a tag-triggered (`v*`) tokenless GitHub Actions OIDC Trusted-Publishing workflow with a
  tag-vs-`pyproject.version` guard; `engine/pyproject.toml` bumps `version` `1.0.0rc1` → `1.0.0` and
  classifier `Development Status :: 4 - Beta` → `5 - Production/Stable`; README + Getting Started lead with
  the uv install (from-source secondary); STATUS + CHANGELOG record the release (Workstream G, Decisions 9,
  10, 11).
- **CON-001**: Phases 1–4 execute **sequentially** (no `[P]`) because they all edit the shared hotspots
  `engine/src/threepowers/gitflow.py` and `engine/src/threepowers/cli/run.py`; Phase 1 lands first
  (Workstream A makes Workstream B's fresh-refusal unreachable in the happy path), then B, C, D.
- **CON-002**: Phase 7 (release) MUST NOT begin — and MUST NOT tag/publish — until Phases 1–6 are green on
  the release commit; the `v1.0.0` tag sits on the commit that carries the isolation fix. Publishing a
  `1.0.0` without the fix is worse than no release; `1.0.0` is immutable on PyPI and cannot be re-uploaded.
- **CON-003** (trust-spine boundary): Id allocation, the branch-number scan, the fetch, and the run lock are
  never a gate, a verdict, or a ledger *input*; they are notifications-style isolation only. The High-risk
  modules `canonical`, `keys`, `ledger`, `verify`, `speclock`, `anchor` are **untouched** and stay ≥95%
  coverage. `Ledger.entries()` is only **read** (never written) for the union.
- **CON-004** (offline-first / no forcing): The best-effort fetch never fails the run, never fast-forwards
  or mutates the local base, and never rewrites history. The clean-start guard (`gitflow.uncommitted` /
  `unrelated_changes` → `clean_start_refusal`) stays in front of `ensure_run_branch` at every entry point,
  unchanged; its only bypass remains a signed `git_clean_start` deviation.
- **CON-005** (resume contract unchanged): Resume stays explicit (`3pwr run --resume --spec-id <NNN>`) and
  keeps re-entering the ledger-recorded branch via `branch_from_ledger`; no new subcommand.
- **CON-006** (`workspace` stays pure): `workspace` acquires no git/ledger imports; the union's git and
  ledger inputs are gathered by the caller (`cli/run.py` fresh path) and passed in as plain lists, so the
  allocator stays unit-testable with lists. `allocate_feature_dir` keeps its `mkdir(exist_ok=False)`
  fail-fast as the final race backstop.
- **GUD-001** (OSS readiness): All new/changed user-facing text — CLI help, error/guidance messages,
  `git.yaml` comments, docs prose, the `release.yml` job/step names — obey
  `engine/tests/test_oss_readiness.py`: no internal plan/spec/requirement ids. Requirement IDs live only in
  test docstrings' `Covers:` declarations.
- **GUD-002** (self-application): The engine stays green under its own gates (ruff/mypy/pytest and
  `3pwr gate run --path engine`, including `gate_gaming` and the High-risk coverage floors) after each
  engine phase.
- **PAT-001**: `git.yaml` new keys parse tolerantly, mirroring the existing `load_prefs` posture — a
  missing/malformed file falls back to shipped defaults with `malformed=True` (warn once, never crash).
- **PAT-002**: The advisory run lock is defensive: a write failure, an unreadable lock, or a malformed lock
  file degrades to a warning and proceeds; the lock is filesystem-only, never ledgered (Decision 8).

## 2. Implementation Steps

### Phase 1

- GOAL-001: Workstream A (python-engineer) — make a fresh run's `<NNN>` the next-free over the union of
  on-disk folders + git branch numbers + signed ledger `run`/`start` spec_ids, so a fresh run always gets a
  brand-new folder AND branch even when a prior run lives only on an unmerged branch or only in the ledger.
  `workspace` stays pure (CON-006); `gitflow` owns the branch-number scan; the caller gathers the inputs.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-001 | In `engine/src/threepowers/workspace.py`, add a union-aware allocator (e.g. `next_run_number(specs_root, *, branch_numbers: Iterable[int] = (), ledger_numbers: Iterable[int] = ()) -> int`) computing `max(union) + 1` over: the on-disk `NNN-` prefixes today's `next_feature_number` (`workspace.py:189-197`) scans (under `specs-src/` and the legacy `specs/`), plus the passed-in `branch_numbers` and `ledger_numbers`. Keep `next_feature_number` working (refactor it to delegate, or keep it as the on-disk-only case) so an empty union degrades to today's on-disk-only number (back-compat). Do NOT import git or ledger in `workspace` (CON-006). Thread the union number through `feature_folder_name` (`workspace.py:200-203`) so `allocate_feature_dir` (`workspace.py:206-217`) allocates the union folder; keep its `mkdir(exist_ok=False)` fail-fast as the final race backstop. |  |  |
| TASK-002 | In `engine/src/threepowers/gitflow.py`, add a read-only branch-number scan helper (e.g. `run_branch_numbers(cwd, branch_prefix, *, remote: str | None = None) -> list[int]`) built on `runner._git` (`runner.py:583-591`): parse `<branch_prefix><NNN>-*` from `git for-each-ref refs/heads/` and, when a remote is given and cheaply available, `refs/remotes/<remote>/`; return `[]` on any git error (offline / non-repo / detached / unborn safe — never raises). Keep it out of the trust spine (CON-003). |  |  |
| TASK-003 | In `engine/src/threepowers/cli/run.py` fresh path (`run.py:2062-2085`, before the run_branch is built at `run.py:2095-2105`), gather the union inputs: call the new `gitflow.run_branch_numbers` (with the resolved `branch_prefix` and `remote`) for branch numbers, and derive ledger numbers from `Ledger.entries()` (`ledger.py:98`) — the `run`/`start` `spec_id`s (`ledger.py:127,144`) parsed to ints — then pass both into `workspace.next_run_number` so the fresh feature dir + run_branch are built from the union number. Read the ledger only (never write); keep it notifications-style isolated (CON-003). |  |  |
| TASK-004 | Update `docs/` (the isolation guarantee in `docs/cli-reference.md` and/or `docs/concepts.md`) at a high level: a fresh run's id is unique across on-disk folders, git branches, and the signed ledger. Deeper docs land in Phase 5. No internal ids (GUD-001). |  |  |
| TASK-005 | Tests (Workstream F): in `engine/tests/test_workspace*.py` / `engine/tests/test_run_workspace.py`, assert `next_run_number` over folders + branch numbers + ledger ids yields `max(union)+1`; a branch-only prior id and a ledger-only prior id are each respected; empty/offline inputs (`branch_numbers=[]`, `ledger_numbers=[]`) degrade to the on-disk-only number (back-compat). In `engine/tests/test_gitflow*.py`, assert `run_branch_numbers` parses `<branch_prefix><NNN>-*` from local (and, with a fake remote ref, remote) refs and returns `[]` on a git error / non-repo. Add `Covers: REQ-A` docstrings (GUD-001). |  |  |
| TASK-006 | Confirm `engine/tests/test_oss_readiness.py` stays green for any new help/error/docstring text introduced (GUD-001). |  |  |

### Phase 2

- GOAL-002: Workstream B (python-engineer) — give `ensure_run_branch` an explicit fresh-vs-resume intent so
  re-entry of an existing branch happens ONLY on the resume path; a fresh run that somehow computes an
  existing branch REFUSES with a named, actionable error pointing at `--resume --spec-id <NNN>`. Depends on
  Phase 1 (which makes the fresh refusal unreachable in the happy path — belt-and-suspenders).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-007 | In `engine/src/threepowers/gitflow.py`, give `ensure_run_branch` (`gitflow.py:149-163`) an explicit intent, e.g. `ensure_run_branch(cwd, branch, base, *, mode: Literal["fresh", "resume"])` (or an equivalent `allow_reentry` boolean): `resume` → today's behavior (re-enter an existing branch at `gitflow.py:158-160`, else create off base); `fresh` → if the branch already exists, return a **distinct named refusal error string** (never checkout); otherwise create off base (`gitflow.py:161-162`), unchanged. Preserve every existing safety property: never forced, a refused switch is surfaced not overridden, no history rewrite. |  |  |
| TASK-008 | In `engine/src/threepowers/cli/run.py`, fresh caller (`run.py:2102`, within `run.py:2095-2105`): pass `mode="fresh"`; on the named refusal, exit on the setup path (`EXIT_SETUP`) printing an actionable message pointing at `3pwr run --resume --spec-id <NNN>`, mirroring the empty-resume guidance style at `run.py:1960-1967`. Resume caller (`run.py:2015`): pass `mode="resume"` (no behavior change). |  |  |
| TASK-009 | In `engine/src/threepowers/cli/run.py`, the **pre-stage git hook** (`run.py:1060-1069`) re-invokes `ensure_run_branch` before every stage; once a run is under way its branch legitimately exists, so pass `mode="resume"` there (or a dedicated re-entering `mid_run` intent) so the hook keeps the run on its branch without tripping the fresh guard. Confirm the resume path's `branch_from_ledger` re-entry (`run.py:1994-2015`) is unchanged (CON-005). |  |  |
| TASK-010 | Update `docs/` (`docs/cli-reference.md`): a fresh run never adopts an existing branch (refuses if it computes one, pointing at `--resume --spec-id <NNN>`); resume is explicit and re-enters the ledger-recorded branch. No internal ids (GUD-001). |  |  |
| TASK-011 | Tests (Workstream F): in `engine/tests/test_gitflow*.py`, assert `mode="fresh"` on an existing branch returns the named refusal error and performs NO checkout; `mode="fresh"` on a non-existing branch creates it off base; `mode="resume"` re-enters an existing branch; a mid-run pre-stage-hook invocation keeps the stage on the run branch. In the CLI-level test, assert the fresh refusal exits on the setup path with the `--resume --spec-id <NNN>` guidance. Add `Covers: REQ-B` docstrings. |  |  |
| TASK-012 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new refusal/guidance message (GUD-001). |  |  |

### Phase 3

- GOAL-003: Workstream C (python-engineer) — a fresh run branches off the latest `origin/<base>` after a
  best-effort, offline-safe fetch, opt-in via new `git.yaml` keys `fetch_base`/`remote`, without ever
  mutating the local base. Depends on Phases 1–2 (shares `gitflow.py`/`cli/run.py`).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-013 | Config: add optional keys `fetch_base: true` (default `true`, Decision 6) and `remote: origin` (default `origin`) to `.3powers/config/git.yaml` **and** the scaffold copy `engine/src/threepowers/scaffold/config/git.yaml` (same task), with OSS-clean comments matching the file's existing style. Add the same keys to the schema `.3powers/config/schema/git.schema.json` **and** the scaffold copy `engine/src/threepowers/scaffold/config/schema/git.schema.json` (same task). |  |  |
| TASK-014 | In `engine/src/threepowers/gitflow.py`, extend `GitPrefs` (`gitflow.py:67-75`) with `fetch_base: bool = True` and `remote: str = "origin"`, and `load_prefs` (`gitflow.py:78-105`) to read them tolerantly (same missing/malformed posture as the existing keys; PAT-001). Add the default constants alongside `DEFAULT_BASE_BRANCH` (`gitflow.py:46`). |  |  |
| TASK-015 | In `engine/src/threepowers/gitflow.py`, make base resolution remote-aware: before branching on the fresh-create path only, when `fetch_base` is on, do a best-effort `git fetch <remote> <base>` (short, non-fatal) via `runner._git`; then teach `base_tip` (`gitflow.py:143-146`), or add `base_tip_for_mode`, to prefer `refs/remotes/<remote>/<base>`, fall back to `refs/heads/<base>`, then to current HEAD. Best-effort/offline-safe invariants (CON-004): no remote / offline / detached HEAD / unborn repo / fetch failure → silently fall back with at most a one-line warning; never force, never fast-forward the local base, never block the run. Thread `remote`/`fetch_base` from `GitPrefs` into the fresh `ensure_run_branch` call only — the pre-stage hook must NOT re-fetch (fetch is a fresh-create concern). |  |  |
| TASK-016 | In `engine/src/threepowers/cli/run.py`, thread `remote`/`fetch_base` from the resolved `GitPrefs` down to the fresh `ensure_run_branch` call (`run.py:2102`); confirm the pre-stage hook (`run.py:1060-1069`) does not pass `fetch_base` (no re-fetch mid-run). |  |  |
| TASK-017 | Update `docs/` (`docs/cli-reference.md`): the new `git.yaml` keys `fetch_base` (default `true`) and `remote` (default `origin`); a fresh run branches off `origin/<base>` when reachable, else falls back safely; the local base is never mutated; `base_branch: develop` supported. No internal ids (GUD-001). |  |  |
| TASK-018 | Tests (Workstream F): in `engine/tests/test_gitflow*.py`, with a fake remote-tracking ref the fresh branch points at `origin/<base>`; fetch failure / no remote / detached / unborn all fall back with no error and the local base is never fast-forwarded; `base_branch: develop` honored. In `engine/tests/test_config*.py`, the new `fetch_base`/`remote` keys parse and default (missing file → defaults; malformed → defaults + `malformed=True`). Add `Covers: REQ-C` docstrings. |  |  |
| TASK-019 | Confirm `engine/tests/test_oss_readiness.py` stays green for the new `git.yaml` comments and any new warning string (GUD-001). |  |  |

### Phase 4

- GOAL-004: Workstream D (python-engineer) — an advisory per-working-tree run lock so a second concurrent
  `3pwr run` in the SAME working tree fails fast, separate clones/worktrees are free, a stale lock
  self-heals, and a lock-write failure never wedges a run. Kept OUT of the trust spine (CON-003, Decision
  8).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-020 | Add a new module `engine/src/threepowers/runlock.py` (or an equivalent `workspace` helper) implementing an advisory per-working-tree lock under `.3powers/run.lock` (alongside `ENGINE_STATE_PREFIX` `.3powers/`, `gitflow.py:53`). The lock file records `{pid, host, started_at}`. Provide acquire/release with: on contention, if the recorded pid is alive on this host → refuse fast with an actionable message naming the other run; if the pid is dead or the mtime is older than a generous TTL → treat as stale, reclaim, and proceed (self-heal). Defensive (PAT-002): a lock-write failure (read-only FS, etc.), an unreadable, or a malformed lock file degrades to a warning and proceeds. Never a gate/verdict/ledger entry (CON-003, Decision 8). |  |  |
| TASK-021 | In `engine/src/threepowers/cli/run.py`, acquire the lock at the top of `cmd_run` for BOTH fresh and resume paths — before the clean-start guard and any side effect (fresh `run.py:2050-2057`, resume `run.py:2000-2014`) — and release it in a `finally`. The lock scope is the working tree's `.3powers/`, so two clones / `git worktree` checkouts each hold their own and never contend. |  |  |
| TASK-022 | Update `docs/` (`docs/cli-reference.md`/`docs/concepts.md`): the per-working-tree run lock — a second run in the same checkout fails fast; separate clones/worktrees are unaffected; a stale lock self-heals; the lock is advisory (never a gate/verdict/ledger fact). No internal ids (GUD-001). |  |  |
| TASK-023 | Tests (Workstream F): a new `engine/tests/test_runlock.py` — a second acquire in one tree refuses with a message naming the holder; a stale lock (dead pid or mtime past the TTL) is reclaimed and the run proceeds; two separate trees both acquire; a lock-write failure degrades to a warning (never raises, never blocks). Add `Covers: REQ-D` docstrings. |  |  |
| TASK-024 | Confirm `engine/tests/test_oss_readiness.py` stays green for the run-lock refusal/warning messages (GUD-001). |  |  |

### Phase 5

- GOAL-005: Workstream E (ordinary change) — finalize the `docs/` narrative in the same unit of work: the
  fresh-run isolation guarantee, the big-team concurrency model, the new `git.yaml` keys, and the sandbox
  clarification. Consolidates the per-phase doc stubs from Phases 1–4.

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-025 | `docs/cli-reference.md`: document the new `git.yaml` keys (`fetch_base`, `remote`) and the fresh-run isolation guarantee — a fresh run always gets a new id + a new branch off base; resume is explicit (`3pwr run --resume --spec-id <NNN>`). No internal ids (GUD-001). |  |  |
| TASK-026 | `docs/getting-started.md` and/or `docs/concepts.md`: the big-team story — many developers + agents working only through 3Powers concurrently; the isolation model = each dev on their own clone and/or their own dedicated `3pwr/<NNN>-<slug>` branch, every change tracked on that branch and in the signed ledger, concurrent runs in one working tree guarded by the run lock. No internal ids (GUD-001). |  |  |
| TASK-027 | `docs/concepts.md` sandbox clarification: `3pwr run`'s isolation is the dedicated branch + per-stage commits + signed ledger; the sanitized git worktree is **oracle-dispatch-only**; a worktree-isolated run mode is noted as **future work** (Decision 7). No internal ids (GUD-001). |  |  |
| TASK-028 | Confirm `engine/tests/test_oss_readiness.py` stays green for all consolidated docs prose (GUD-001). Note: the README + Getting Started uv-install reordering is authored in Phase 7 (Workstream G) but in the same unit of work. |  |  |

### Phase 6

- GOAL-006: Verification (python-engineer) — prove the isolation fix with the cross-cutting regression test
  that MUST fail without the fix, then prove the whole engine is green under its own toolchain and gates,
  OSS-readiness holds, and the trust spine is untouched and above its coverage floors. This phase gates the
  release (CON-002).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-029 | Add the cross-cutting **regression test** (Workstream F) that fails on `main` without the fix: a prior run's branch/folder exists **only on an unmerged branch** (and/or only in the ledger) → a fresh run allocates a NEW id and creates a NEW branch off base, never re-entering the stale one. Exercise `workspace.next_run_number` (union) + `gitflow.ensure_run_branch(mode="fresh")` together. Confirm it fails when the union/intent changes are reverted (drives REQ-A + REQ-B + REQ-F). Add `Covers: REQ-A, REQ-B, REQ-F` docstrings. |  |  |
| TASK-030 | Run `cd engine && uv run pytest` — all new and existing tests pass, including `test_workspace*`/`test_run_workspace.py`, `test_gitflow*.py`, `test_config*.py`, `test_runlock.py`, and the regression test. |  |  |
| TASK-031 | Run `cd engine && uv run ruff check .` and `cd engine && uv run mypy src` — clean. |  |  |
| TASK-032 | Run `3pwr gate run --path engine` — the engine stays green under its own gates, including `gate_gaming` and the High-risk coverage floors (GUD-002). |  |  |
| TASK-033 | Confirm the trust spine is **untouched**: `canonical`, `keys`, `ledger`, `verify`, `speclock`, `anchor` are unmodified by this work and hold coverage ≥95%; id allocation, the branch scan, the fetch, and the run lock are never a gate/verdict/ledger input (CON-003). `Ledger.entries()` is read-only for the union. Record this confirmation in the phase note. |  |  |
| TASK-034 | Confirm `engine/tests/test_oss_readiness.py` passes — no internal plan/spec/requirement ids in any new user-facing string across Workstreams A–E (GUD-001). |  |  |

### Phase 7

- GOAL-007: Workstream G (ordinary change) — **strictly last.** After Phases 1–6 are green on the release
  commit, cut the first `v1.0.0` release and publish `threepowers` to PyPI via a tokenless, tag-triggered
  GitHub Actions OIDC Trusted-Publishing workflow, and make uv the documented primary install. The `v1.0.0`
  tag MUST sit on the commit carrying the isolation fix (CON-002).

| Task     | Description | Completed | Date |
| -------- | ----------- | --------- | ---- |
| TASK-035 | **Manual prerequisite (maintainer, NOT a code task — documented here for hand-off).** Before the first tag: on PyPI register the Trusted Publisher for project **`threepowers`** — repository **`VerzCar/3powers`**, workflow filename **`release.yml`**, and the matching **environment** name (e.g. `pypi`) — and reserve/own the `threepowers` project name. `1.0.0` is immutable on PyPI once uploaded; the version/artifact must be correct before tagging. The implementation may not perform this step. |  |  |
| TASK-036 | In `engine/pyproject.toml`, bump `version` `1.0.0rc1` → `1.0.0` (line 3) and classifier `Development Status :: 4 - Beta` → `Development Status :: 5 - Production/Stable` (line 19). Leave `name = "threepowers"` (line 2), the `[project.scripts] "3pwr"` entry, deps, `build-backend = "hatchling.build"`, `readme = "README.md"`, and `[project.urls]` unchanged; sanity-check the README renders as the PyPI long description. |  |  |
| TASK-037 | Create `.github/workflows/release.yml`, triggered on pushing a tag matching `v*`: a `build` job (checkout, install uv via `astral-sh/setup-uv`, `uv build` in `engine/` producing sdist + wheel under `engine/dist/`); a `publish` job with `permissions: id-token: write` and a GitHub `environment:` (e.g. `pypi`) using PyPI Trusted Publishing (OIDC) — either `uv publish` with no token or `pypa/gh-action-pypi-publish` — to upload `engine/dist/*`. No API token stored anywhere. Guardrails: verify the pushed tag version matches `engine/pyproject.toml` `version` before publishing (fail fast on a mismatched tag) and only run publish on the upstream repo (`VerzCar/3powers`), not forks. Job/step names OSS-clean (GUD-001). |  |  |
| TASK-038 | Install docs (with Workstream E): `README.md` (line ~75) — lead with `uv tool install threepowers` (and `uvx threepowers` for a throwaway run), keeping the from-source clone + `uv tool install ./engine` as a secondary "from source" option. `docs/getting-started.md` (lines ~23-26 and ~145-151) — same reordering; keep the `uv`/`git` prerequisites and the `Installed 1 executable: 3pwr` confirmation; state that the distribution is `threepowers` while the CLI is `3pwr`. No internal ids (GUD-001). |  |  |
| TASK-039 | `docs/STATUS.md` — reflect the `1.0.0` release (milestone/validation line) per the "status lives in exactly one place" rule. `CHANGELOG.md` (top-level, hand-maintained) — add the `1.0.0` release entry (Keep-a-Changelog) including the fresh-run isolation fix (new id + new branch off base, base-branch fetch, per-working-tree run lock) and the uv/PyPI availability. |  |  |
| TASK-040 | Confirm `engine/tests/test_oss_readiness.py` stays green for the release docs, README, CHANGELOG, and `release.yml` text (GUD-001). |  |  |
| TASK-041 | **Release procedure (maintainer hand-off, documented).** Merge the feature branch (bump already in) → tag `v1.0.0` on the merge commit that carries the fix → push the tag → the workflow builds + publishes → verify from a clean machine that `uv tool install threepowers` resolves `1.0.0`, `uvx threepowers` works, and `3pwr --version` reports `1.0.0`. Do NOT tag/publish before Phases 1–6 are green on that commit (CON-002). |  |  |

## 3. Alternatives

- **ALT-001**: Derive the fresh run id from the on-disk `specs-src/` listing only (today's
  `next_feature_number`, `workspace.py:189-197`). Rejected: a prior run's folder living only on an unmerged
  branch is invisible on the working tree, so the number is reused and `ensure_run_branch` adopts the stale
  branch — the exact defect. The union over folders + branches + ledger fixes it (Decision 1).
- **ALT-002**: Fix only `ensure_run_branch` (add the fresh guard) and leave id allocation alone. Rejected as
  insufficient: a reused id would then make every fresh run REFUSE instead of proceeding. Workstream A makes
  the happy path allocate a new id; Workstream B is the belt-and-suspenders guard (Decisions 1–2).
- **ALT-003**: Fast-forward / pull the local base before branching. Rejected: it mutates the developer's
  checkout and can fail on network/conflict, breaking offline-first determinism. Branching off the
  remote-tracking ref `origin/<base>` gives "latest" without touching the local base (Decision 4, CON-004).
- **ALT-004**: A cross-repo/remote distributed run lock. Rejected as out of scope: the unsafe interaction is
  the shared working tree + git index, so a per-working-tree advisory lock is the minimal correct guard;
  separate clones are independent by construction (Decision 5, non-goal).
- **ALT-005**: Ledger the run lock as an auditable trust fact. Rejected: a lock is operational hygiene, not
  a trust fact; ledgering it would breach the trust-spine boundary. It stays a filesystem advisory
  (Decision 8, CON-003).
- **ALT-006**: A worktree-isolated run mode (one `git worktree` per run). Rejected for now as a larger
  orthogonal change; the dedicated branch + per-stage commits + signed ledger + the run lock already deliver
  the concurrency guarantee this plan targets. Noted as future work (Decision 7).
- **ALT-007**: Ship the v1.0.0 release as a separate plan after 038. Rejected: the maintainer folded it into
  plan 038 so the `v1.0.0` tag and the published artifact capture the isolation fix; it runs strictly after
  Workstreams A–F (Decision 9).
- **ALT-008**: Publish with a stored PyPI API token in a GitHub secret. Rejected: OIDC Trusted Publishing
  avoids a long-lived secret and standardizes on a tag push; the documented manual `uv publish` fallback is
  out of scope (Decision 10).

## 4. Dependencies

- **DEP-001**: The run/git lifecycle wiring — `gitflow.py` (all git logic) driven from `cli/run.py`, over
  the low-level `runner._git` (`runner.py:583-591`) and `runner._changed_files` (`runner.py:594-612`). All
  four engine workstreams build on this.
- **DEP-002**: The clean-start guard — `gitflow.uncommitted`/`unrelated_changes` (`gitflow.py:183-206`),
  refusal `clean_start_refusal` (`gitflow.py:233-244`), enforced BEFORE `ensure_run_branch` at every entry
  point (fresh `run.py:2050-2057`, resume `run.py:2000-2014`); its only bypass is a signed
  `git_clean_start` deviation (`GATE_CLEAN_START` `gitflow.py:34`). Kept in front and unchanged (CON-004).
- **DEP-003**: The signed ledger read path — `Ledger.entries()` (`ledger.py:98`) exposing each entry's
  `spec_id` (`ledger.py:127,144`), and `gitflow.branch_from_ledger` (`gitflow.py:166-179`) /
  `_run_feature_dir_from_ledger` (`run.py:259-272`). Read-only for the union; never written by this work
  (CON-003).
- **DEP-004**: `GitPrefs`/`load_prefs` (`gitflow.py:67-105`) and the `git.yaml` defaults (`gitflow.py:46`) —
  extended tolerantly with `fetch_base`/`remote` (Workstream C).
- **DEP-005**: `ensure_run_branch` (`gitflow.py:149-163`) and `base_tip` (`gitflow.py:143-146`) — the
  fresh-vs-resume intent + remote-aware base resolution (Workstreams B, C).
- **DEP-006**: `workspace.next_feature_number`/`feature_folder_name`/`allocate_feature_dir`
  (`workspace.py:189-217`) — the union allocator (Workstream A); `workspace` stays free of git/ledger
  imports (CON-006).
- **DEP-007**: `.3powers/config/git.yaml` + `.3powers/config/schema/git.schema.json` and the scaffold
  copies `engine/src/threepowers/scaffold/config/git.yaml` + `.../scaffold/config/schema/git.schema.json`
  — always edited together per key (Workstream C).
- **DEP-008**: `ENGINE_STATE_PREFIX` `.3powers/` (`gitflow.py:53`) — the per-working-tree state root where
  `.3powers/run.lock` lives (Workstream D).
- **DEP-009**: `engine/tests/test_oss_readiness.py` — must pass for all new/changed user-facing text
  (GUD-001).
- **DEP-010**: The `3pwr` CLI installed from `./engine` and the engine test/gate toolchain (`uv run
  pytest`/`ruff`/`mypy`, `3pwr gate run --path engine`) for verification (Phase 6).
- **DEP-011** (Workstream G): `engine/pyproject.toml` (`name = "threepowers"`, `version = "1.0.0rc1"`,
  `build-backend = "hatchling.build"`, `[project.scripts] "3pwr"`); `astral-sh/setup-uv` +
  `uv build`/`uv publish` (or `pypa/gh-action-pypi-publish`) for the release workflow; the existing
  `.github/workflows/` (only `ci.yml`, `pages.yml` today — no publish workflow exists).
- **DEP-012** (Workstream G, manual): a PyPI Trusted-Publisher registration for project `threepowers` (repo
  `VerzCar/3powers`, `release.yml`, environment) + ownership of the `threepowers` name — a maintainer
  prerequisite, not a code task (TASK-035).

## 5. Files

- **FILE-001**: `engine/src/threepowers/workspace.py` — the union-aware `next_run_number` allocator and its
  threading through `feature_folder_name`/`allocate_feature_dir` (`workspace.py:189-217`); stays pure, no
  git/ledger imports (Workstream A, CON-006).
- **FILE-002**: `engine/src/threepowers/gitflow.py` — the shared hotspot: the read-only branch-number scan
  helper (Workstream A); `ensure_run_branch` fresh-vs-resume intent + fresh guard (`gitflow.py:149-163`,
  Workstream B); `GitPrefs`/`load_prefs` new `fetch_base`/`remote` keys (`gitflow.py:67-105`) + the
  best-effort fetch + remote-aware `base_tip` (`gitflow.py:143-146`, Workstream C). Edited across Phases
  1–3, hence sequential.
- **FILE-003**: `engine/src/threepowers/cli/run.py` — the shared hotspot: fresh path gathers union
  branch/ledger ids + builds the union id (`run.py:2062-2105`, Workstream A); fresh caller `mode="fresh"` +
  refusal message and resume caller `mode="resume"` and the pre-stage hook stays on-branch (`run.py:2015`,
  `run.py:2095-2105`, `run.py:1060-1069`, Workstream B); threads `fetch_base`/`remote` to the fresh call
  (Workstream C); acquires/releases the run lock in `cmd_run` (Workstream D). Edited across Phases 1–4,
  hence sequential.
- **FILE-004**: `engine/src/threepowers/runner.py` — the low-level `_git` reused by the new read-only git
  helpers (`runner.py:583-591`); no behavior change to `_changed_files` (`runner.py:594-612`).
- **FILE-005**: `engine/src/threepowers/runlock.py` (new) — the advisory per-working-tree run lock
  (`.3powers/run.lock`) (Workstream D).
- **FILE-006**: `.3powers/config/git.yaml` + `.3powers/config/schema/git.schema.json` + the scaffold copies
  `engine/src/threepowers/scaffold/config/git.yaml` + `.../scaffold/config/schema/git.schema.json` — the new
  `fetch_base`/`remote` keys (Workstream C).
- **FILE-007**: `docs/cli-reference.md`, `docs/getting-started.md`, `docs/concepts.md` — the isolation
  guarantee, the big-team model, the new `git.yaml` keys, the sandbox clarification, and (Workstream G) the
  uv-install reordering (Workstreams E + G).
- **FILE-008**: `engine/tests/test_workspace*.py` / `engine/tests/test_run_workspace.py`,
  `engine/tests/test_gitflow*.py`, `engine/tests/test_config*.py`, new `engine/tests/test_runlock.py`, plus
  the cross-cutting regression test — new/extended (Workstream F).
- **FILE-009**: `engine/tests/test_oss_readiness.py` — must stay green for all new user-facing text
  (GUD-001; satisfied, not modified).
- **FILE-010** (Workstream G): `engine/pyproject.toml` — `version` `1.0.0rc1`→`1.0.0` (line 3), classifier
  `Development Status` `4 - Beta`→`5 - Production/Stable` (line 19).
- **FILE-011** (Workstream G): `.github/workflows/release.yml` (new) — tag-triggered (`v*`) OIDC
  Trusted-Publishing build+publish of `engine/dist/*`, with a tag-vs-version guard and upstream-only publish.
- **FILE-012** (Workstream G): `README.md` (line ~75) — uv install primary, from-source secondary.
- **FILE-013** (Workstream G): `docs/STATUS.md` — the `1.0.0` milestone; `CHANGELOG.md` — the `1.0.0` entry.

## 6. Testing

- **TEST-001** (Workstream A): `test_workspace*`/`test_run_workspace.py` — `next_run_number` over folders +
  branch numbers + ledger ids yields `max(union)+1`; branch-only and ledger-only prior ids are each
  respected; empty/offline inputs degrade to the on-disk-only number (back-compat). `test_gitflow*.py` —
  `run_branch_numbers` parses `<branch_prefix><NNN>-*` from local (and a fake remote ref) and returns `[]`
  on any git error / non-repo.
- **TEST-002** (Workstream B): `test_gitflow*.py` — `mode="fresh"` on an existing branch returns the named
  refusal with NO checkout; `mode="fresh"` on a new branch creates it off base; `mode="resume"` re-enters;
  the pre-stage hook keeps a mid-run stage on its branch. CLI-level — the fresh refusal exits on the setup
  path with `--resume --spec-id <NNN>` guidance.
- **TEST-003** (Workstream C): `test_gitflow*.py` — with a fake remote-tracking ref the fresh branch points
  at `origin/<base>`; fetch failure / no remote / detached / unborn fall back with no error and the local
  base is never fast-forwarded; `base_branch: develop` honored. `test_config*.py` — `fetch_base`/`remote`
  parse and default (missing → defaults; malformed → defaults + `malformed=True`).
- **TEST-004** (Workstream D): `test_runlock.py` — a second acquire in one tree refuses (naming the holder);
  a stale lock (dead pid / old mtime) reclaims and proceeds; two separate trees both acquire; a lock-write
  failure degrades to a warning (never raises/blocks).
- **TEST-005** (Workstream F, regression): a prior run's branch/folder only on an unmerged branch (and/or
  only in the ledger) → a fresh run gets a NEW id + NEW branch off base, never re-entering the stale one;
  the test FAILS when the union/intent changes are reverted (Phase 6, TASK-029).
- **TEST-006** (whole engine): `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (self-application incl. `gate_gaming` and High-risk coverage ≥95%),
  and `engine/tests/test_oss_readiness.py` green; the trust spine (`canonical`, `keys`, `ledger`, `verify`,
  `speclock`, `anchor`) confirmed untouched and above its floors (CON-003).
- **TEST-007** (Workstream G, release verification, maintainer): pushing `v1.0.0` builds and publishes
  `threepowers==1.0.0` to PyPI with no stored token; from a clean environment `uv tool install threepowers`
  and `uvx threepowers` resolve `1.0.0` and `3pwr --version` reports `1.0.0`; the tag-vs-`pyproject.version`
  guard blocks a mismatched tag.

## 7. Risks & Assumptions

- **RISK-001** (Workstream C): detached HEAD / unborn repo — `current_branch` already returns `""`
  (`gitflow.py:133-136`) and creation falls back to current HEAD (`gitflow.py:161`). *Mitigation:* the
  union scan (`run_branch_numbers`) and the fetch must both no-op cleanly here; tested (TEST-001, TEST-003).
- **RISK-002** (Workstream C): offline / no remote / fetch failure. *Mitigation:* best-effort fetch never
  fails the run; fall back to local-base / current-HEAD with at most a one-line warning; never
  fast-forward the local base (CON-004, TEST-003).
- **RISK-003** (Workstream C): diverged base — branching off `origin/<base>` deliberately ignores an
  out-of-date local base. *Mitigation:* the local base is never fast-forwarded, so no surprise mutation of
  the developer's checkout; documented (TASK-017).
- **RISK-004** (Workstream C): non-`origin` remotes / an unknown remote → fetch fails. *Mitigation:* the
  `remote` config key; an unknown remote → fetch fails → fall back (no crash), tested.
- **RISK-005** (Workstream D): a crashed run leaves a lock that wedges the next run. *Mitigation:*
  pid-liveness + mtime-TTL self-heal (Decision 5); a lock-write failure degrades to advisory-warning, never
  blocks (PAT-002, TEST-004).
- **RISK-006** (Workstream A): a concurrent same-tree id race. *Mitigation:* the union narrows the window,
  `mkdir(exist_ok=False)` (`workspace.py:216`) is the final backstop, and the run lock removes the same-tree
  race entirely.
- **RISK-007** (Phases 1–4): file-scope contention on `gitflow.py` and `cli/run.py`. *Mitigation:*
  sequential phase execution (no `[P]`, CON-001), Phase 1 establishes the union first, and each phase
  re-anchors to current source before editing.
- **RISK-008** (trust-spine boundary): id allocation, the branch scan, the fetch, or the lock accidentally
  becoming a gate/verdict/ledger input. *Mitigation:* keep them notifications-style isolated;
  `Ledger.entries()` read-only; verified by the untouched High-risk coverage + `gate_gaming` staying green
  (CON-003, TASK-033).
- **RISK-009** (Workstream G, ordering): tagging/publishing `1.0.0` before the fix is green. *Mitigation:*
  Phase 7 is strictly last; tag the merge commit that carries the fix, not the feature branch mid-flight
  (CON-002); the workflow's tag-vs-`pyproject.version` guard prevents a mismatched-tag publish.
- **RISK-010** (Workstream G, prerequisites): the OIDC publish fails until the maintainer registers the
  trusted publisher on PyPI and owns the `threepowers` name; `1.0.0` is immutable once uploaded.
  *Mitigation:* TASK-035 records the exact registration values as a manual prerequisite completed before the
  first tag.
- **RISK-011** (Workstream G): package-vs-CLI name mismatch — the distribution is `threepowers` but the
  command is `3pwr`. *Mitigation:* docs state both so `uv tool install threepowers` users know to run `3pwr`
  (TASK-038).
- **ASSUMPTION-001**: The file:line anchors carried from the source plan (`workspace.py:189-217`;
  `gitflow.py:34,46,53,67-105,133-136,143-146,149-163,166-179,183-206,233-244`; `run.py:259-272,1060-1069,
  1935,1960-1967,1994-2015,2000-2014,2048,2050-2057,2062-2105,2102`; `runner.py:583-591,594-612`;
  `ledger.py:98,127,144`) are accurate at implementation time; the python-engineer agent re-anchors to the
  current source before editing.
- **ASSUMPTION-002**: The current packaging state is `engine/pyproject.toml` `name = "threepowers"`,
  `version = "1.0.0rc1"`, `Development Status :: 4 - Beta` (line 19), `[project.scripts] "3pwr"`,
  `build-backend = "hatchling.build"`, urls at `github.com/VerzCar/3powers`; `.github/workflows/` holds only
  `ci.yml`, `pages.yml`; no `runlock.py` exists yet — all confirmed this session.
- **ASSUMPTION-003**: The eleven decisions (5 substantive forks chosen by the maintainer; the rest
  engineering defaults grounded in the session's code read) are settled; no open questions remain in the
  source plan.
- **ASSUMPTION-004**: The resume contract is unchanged — resume stays explicit (`--resume --spec-id <NNN>`)
  and re-enters the ledger-recorded branch via `branch_from_ledger` (`gitflow.py:166-179`), the empty-resume
  refusal (`run.py:1960-1967`) is preserved (CON-005).
- **ASSUMPTION-005**: `astral-sh/setup-uv` + `uv build`/`uv publish` (or `pypa/gh-action-pypi-publish`)
  support tokenless OIDC publishing to PyPI on a `v*` tag from GitHub Actions with `id-token: write` + a
  GitHub environment.

## 8. Related Specifications / Further Reading

- `plan/038-fresh-run-isolation-and-base-branch.md` — the source plan this implementation plan derives from.
- `plan/IMPLEMENTATION-008-feature-structured-usage-providers.md` and
  `plan/IMPLEMENTATION-007-feature-run-remediation-and-executive-ux.md` — the immediate predecessors whose
  run/git/ledger lifecycle this plan builds on and whose house style this plan follows.
- `AGENTS.md` — the mandatory intent → plan → implementation plan → implementation workflow, branch/commit
  discipline (dedicated feature branch, no pull requests), python-engineer routing, and
  open-source-readiness rules.
- `CLAUDE.md` — architecture deep-dive (eight-stage lifecycle, three pillars, trust spine, declarative
  adapter model).
- `docs/cli-reference.md` — the public `3pwr` command surface (including `3pwr run` and `--resume`).
- `docs/getting-started.md` / `docs/concepts.md` — the install path and the run/isolation model.
- `docs/STATUS.md` — the single source of truth for implementation status (the 1.0.0 milestone lands here).
- `engine/tests/test_oss_readiness.py` — the enforced open-source-readiness rule for user-facing text.
</content>
</invoke>
