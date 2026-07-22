# Plan 038 — Fresh-run isolation, next-free run identity, base-branch fetch, a per-working-tree run lock, and the first v1.0.0 release (PyPI/uv)

**Git branch:** `feat/038-fresh-run-isolation-and-base-branch` (created and checked out for this plan; the
plan file is **not** auto-committed — the maintainer commits).

**Origin.** A live `3pwr run "<intent>"` was observed to **silently continue a prior run's branch and
feature folder** instead of starting a brand-new, isolated run: Discovery (the first producing stage)
checked out the stale `3pwr/<NNN>-<slug>` branch and built on top of it. That breaks the core promise of a
fresh run — a new run id, a new dedicated branch, traceable in the signed ledger, never an accidental
resume. The intent is that a fresh `3pwr run` is **always** a completely new, isolated run; resuming stays
explicit (`3pwr run --resume --spec-id <NNN>`). Alongside the isolation fix, the maintainer wants a fresh
run to always branch off the configured `base_branch`, to **pull the latest** before branching, to support
a non-`main` base (e.g. `develop`), and to be safe when many developers and agents work concurrently only
through 3Powers.

**Release addition (maintainer, this session).** Once the isolation fix lands, this same unit of work cuts
the **first `v1.0.0` tag release** and publishes the `threepowers` distribution to PyPI so it is installable
directly with uv (`uv tool install threepowers` / `uvx threepowers`), replacing the from-a-clone install as
the primary path in the README and Getting Started. Publishing is via **GitHub Actions PyPI Trusted
Publishing (OIDC) on a `v*` tag** — no stored token. This is folded into plan 038 (maintainer's choice), so
it runs *after* Workstreams A–F are green and the tag captures the fix.

This plan is grounded in a full read of the run/git lifecycle this session; every claim below carries a
`file:line` anchor so the implementation-plan agent can go straight to the code. Current packaging state
(read this session): `engine/pyproject.toml` — `name = "threepowers"`, `version = "1.0.0rc1"`,
`build-backend = "hatchling.build"`, `[project.scripts] "3pwr" = "threepowers.cli:main"`, urls point at
`github.com/VerzCar/3powers`, classifier `Development Status :: 4 - Beta`. Install today is
`uv tool install ./engine` from a clone (README:75, getting-started:23-26 & 145-151). No publish workflow
exists (`.github/workflows/` holds only `ci.yml`, `pages.yml`).

---

## Problem statement

A fresh run must be a completely new, isolated unit of work:

1. its **own run id** (`<NNN>`), never a reused number;
2. its **own dedicated branch** `<branch_prefix><NNN>-<slug>`, created off the configured base — never an
   adopted pre-existing branch;
3. **traceable** via a signed `run`/`start` ledger entry binding `branch` + `feature_dir` to the id;
4. branched off `base_branch` (configurable; e.g. `develop`) with the **latest** changes pulled first;
5. **safe under concurrency** — many developers and agents, each on their own clone/branch, plus a guard
   against two runs racing in the *same* working tree.

Today (1)–(2) can silently fail: a fresh run re-enters a prior run's branch/folder. (4) is unmet (no fetch
anywhere; base resolves local-only). (5) has no per-working-tree guard.

## Root-cause analysis

The silent re-entry is three interacting spots in `engine/src/threepowers/`:

1. **Run id is derived from the on-disk listing only.** `workspace.next_feature_number`
   (`workspace.py:189-197`) computes the next `<NNN>` as `max(existing "NNN-" prefixes under specs-src/) + 1`
   — a pure function of the `specs-src/` directory listing (`feature_folder_name` `workspace.py:200-203`,
   `allocate_feature_dir` `workspace.py:206-217`). When a prior run's folder lives **only on an unmerged
   branch**, it is invisible on the current working tree, so the same number is **reused**. It never
   consults git branches or the signed ledger.

2. **`ensure_run_branch` unconditionally re-enters an existing branch.** `gitflow.ensure_run_branch`
   (`gitflow.py:149-163`): `if branch_exists(...): checkout -q branch`. Correct for a resume, wrong for a
   fresh run — it has no notion of "fresh vs resume intent", so a reused id (from spot 1) points it at the
   stale branch and it adopts it.

3. **The fresh-run path calls `ensure_run_branch` with no fresh-vs-resume guard.** `cli/run.py`
   fresh path (`run.py:2095-2105`) builds `run_branch` from the (possibly reused) identity and calls the
   same `ensure_run_branch` (`run.py:2102`) that will re-enter. The mandatory **pre-stage** git hook
   (`run.py:1060-1069`) re-invokes `ensure_run_branch` before every stage, reinforcing re-entry — so
   Discovery (the first producing stage) lands on the stale branch. The resume path (`run.py:1994-2015`)
   *correctly* re-enters via `branch_from_ledger`; the two paths are distinguished only by `args.resume`
   (`run.py:1935` resume vs `run.py:2048` fresh), and the fresh path carries no "must not adopt" guard.

Net effect: reused id (1) → existing branch → unconditional re-entry (2) with no guard (3) = a fresh run
that silently continues a prior run.

## Current git behavior (the plan builds on this)

- All git logic lives in `gitflow.py`, driven from `cli/run.py`; the low-level shell-out is
  `runner._git` (`runner.py:583-591`) and `runner._changed_files` (`runner.py:594-612`).
- **`base_branch` is fully configurable.** Default `"main"` (`DEFAULT_BASE_BRANCH` `gitflow.py:46`), read
  from `.3powers/config/git.yaml` via `load_prefs` (`gitflow.py:78-105`, key at `gitflow.py:101`), flowing
  into `ensure_run_branch(base=...)`. Nothing hardcodes `main` except the fallback constant — `base_branch:
  develop` already works end to end. GOOD; keep it.
- **Branch creation off base:** `start_point = [base] if base and base_tip(cwd, base) else []`, then
  `git checkout -q -b <branch> <start_point>` (`gitflow.py:161-162`). `base_tip` (`gitflow.py:143-146`)
  resolves **only local** `refs/heads/<base>`; it never consults `refs/remotes/origin/<base>`. If base does
  not resolve locally, the branch is created off current HEAD.
- **No fetch/pull/merge anywhere** in the run lifecycle. A fresh run branches off the local base tip as-is;
  staleness vs origin is inherited silently. (`grep` for `fetch`/`origin`/`refs/remotes` across
  `gitflow.py` and `runner.py` returns nothing.)
- **Clean-start guard.** `runner._changed_files` → `git status --porcelain` (`runner.py:594-612`), wrapped
  by `gitflow.uncommitted`/`unrelated_changes` (`gitflow.py:183-206`), refusal `clean_start_refusal`
  (`gitflow.py:233-244`), enforced BEFORE `ensure_run_branch` at every entry point (fresh
  `run.py:2050-2057`, resume `run.py:2000-2014`). Never forces/stashes; only bypass is a signed
  `git_clean_start` deviation (`GATE_CLEAN_START` `gitflow.py:34`). KEEP THIS unchanged and in front.
- **No cross-process locking.** `allocate_feature_dir` uses `mkdir(exist_ok=False)` fail-fast and states
  "Cross-process locking is an explicit non-goal" (`workspace.py:206-217`). No `.git/index.lock` handling.
  The oracle uses ephemeral git worktrees for read-isolation only (`oracle.py`), not concurrency.
- **Ledger linkage.** A signed `run`/`start` entry (`run.py:2106-2126`) binds `branch` + `feature_dir`,
  keyed by `spec_id` (the `<NNN>`), read back by `gitflow.branch_from_ledger` (`gitflow.py:166-179`) and
  `_run_feature_dir_from_ledger` (`run.py:259-272`). `Ledger.entries()` (`ledger.py:98`) exposes every
  entry with its `spec_id` (`ledger.py:127,144`) — the authoritative, offline-recoverable record of every
  allocated run id.
- **Resume vs fresh.** One `3pwr run` command; `--resume` + `--spec-id` (no separate subcommand). The fork
  is `args.resume` (`run.py:1935` vs `run.py:2048`). Empty-resume already refuses with guidance
  (`run.py:1960-1967`).

---

## Goals

- A fresh `3pwr run` **always** gets a brand-new run id AND a brand-new dedicated branch off the configured
  base; it never silently adopts a prior run's branch/folder.
- The run id is the **next-free over the union** of on-disk folders + git branches + the signed ledger, so
  the number is unique even when prior runs live only on unmerged branches.
- A fresh run branches off `base_branch`, optionally after a best-effort fetch of `origin/<base>`, and
  supports a non-`main` base.
- A second concurrent run in the **same working tree** fails fast; runs in **separate** clones/working
  trees are entirely unaffected.
- Every behavior change ships with docs (the big-team isolation guarantee + new `git.yaml` keys) and tests
  (including a regression that fails without the fix).
- After the fix is green, the `threepowers` distribution is published to PyPI as **`1.0.0`** and is
  installable directly via uv (`uv tool install threepowers`, `uvx threepowers`); README + Getting Started
  lead with the uv install; a `v1.0.0` tag on the merged commit triggers the publish.

## Non-goals

- **No change to the resume contract.** Resume stays explicit (`3pwr run --resume --spec-id <NNN>`) and
  keeps re-entering the ledger-recorded branch (`run.py:1994-2015`, `gitflow.branch_from_ledger`).
- **No change to the trust spine.** Id allocation, fetch, and the run lock are notifications-style
  isolation: never a gate, verdict, or ledger *input*; the High-risk modules (`canonical`, `keys`,
  `ledger`, `verify`, `speclock`, `anchor`) are untouched.
- **No forcing, stashing, or history rewrite.** The clean-start guard stays in front and unchanged; a fetch
  never fast-forwards the local base and never blocks the run.
- **No worktree-isolated run mode** (see Workstream F rationale — deferred as future work).
- **No cross-repo/remote distributed lock.** The lock is strictly per working tree.

---

## Decisions recorded

The five substantive forks were **chosen by the maintainer** (Intent + "Confirmed design decisions"); the
rest are engineering defaults grounded in this session's code read. **No open questions remain.**

| # | Decision | Choice | Rationale |
|---|---|---|---|
| 1 | Fresh run id source | **Next-free over the UNION** of on-disk `specs-src/` folders + git branches (`<branch_prefix><NNN>-*`, local and — where cheap — remote) + signed ledger `run`/`start` spec_ids. Auto-advance (max+1). | Guarantees a brand-new id AND branch on every fresh run, so `ensure_run_branch` always takes the create-off-base path. The ledger is authoritative for allocated ids even when branches/folders are off the working tree. |
| 2 | Fresh-vs-resume in `ensure_run_branch` | Add an explicit **intent** parameter; a **fresh** run REFUSES if the computed branch already exists (defense-in-depth) and points to `--resume --spec-id <NNN>`; re-entry only on the **resume** path. | The unconditional re-enter (`gitflow.py:158-160`) is the direct bug; making intent explicit removes the ambiguity and adds a belt-and-suspenders guard even if id allocation ever regresses. |
| 3 | Base branch, non-`main`, off-base creation | Keep the existing configurable `base_branch`; branch off base regardless of HEAD (already does); confirm `develop` end to end. | Creation already branches off base (`gitflow.py:161`) — the only bug was the wrong re-entry; (1)/(2) fix that. Nothing hardcodes `main`. |
| 4 | Pull latest before branching | **FETCH + branch off `origin/<base>`**, opt-in via `git.yaml` (`fetch_base`, plus `remote` name). Best-effort, offline-safe; the LOCAL base is left untouched (never fast-forwarded). | Branching off the remote-tracking ref gives "latest" without mutating the developer's local base or blocking on network. Fully degradable preserves offline-first determinism. |
| 5 | Concurrency guard | **Advisory per-working-tree run lock**; second concurrent run in the same tree fails fast; separate clones/trees unaffected; self-heals from a stale lock (pid/mtime). Kept OUT of the trust spine. | The shared working tree + git index make concurrent runs in one checkout unsafe; a per-tree advisory lock is the minimal correct guard without a distributed system. |
| 6 | `fetch_base` default | Propose **`fetch_base: true`** (best-effort). | The maintainer asked that a fresh run pull latest; making it the default matches the intent, and it is fully degradable so it never harms offline/no-remote users. Flip to `false` to opt out. |
| 7 | Worktree-isolated run mode | **Out of scope; noted as future work.** | `3pwr run`'s isolation is the dedicated branch + per-stage commits + signed ledger; the sanitized git worktree is oracle-dispatch-only. A worktree-per-run mode is a larger orthogonal change; the lock + branch isolation already deliver the concurrency guarantee this plan targets. |
| 8 | Lock is not ledgered | The lock is a filesystem advisory only — never a gate, verdict, or ledger entry. | Consistent with the trust-spine boundary; a lock is operational hygiene, not an auditable trust fact. |
| 9 | Release structure | **Folded into plan 038** (not a separate plan). | Maintainer's choice; the release ships as the final workstream of this unit of work, sequenced after A–F so the tag captures the fix. |
| 10 | Publish mechanism | **GitHub Actions PyPI Trusted Publishing (OIDC)** on a `v*` tag; no stored token. Documented manual `uv publish` fallback is out of scope. | Maintainer's choice; OIDC avoids a long-lived secret and standardizes releases on a tag push. Requires a one-time PyPI "trusted publisher" registration in the PyPI UI (recorded as a manual prerequisite, not a code task). |
| 11 | Distribution name / version | Publish as **`threepowers`** (unchanged; CLI stays `3pwr`); bump `version` `1.0.0rc1` → **`1.0.0`** and classifier `Development Status` `4 - Beta` → `5 - Production/Stable`. | `threepowers` is already the pyproject name and the intended `uv tool install` target; the RC → final bump + status classifier is the actual 1.0.0 cut. |

---

## Why now

1. **A live fresh run silently continued a prior run** — the exact three-spot interaction in Root-cause
   analysis (`workspace.py:189-197`, `gitflow.py:149-163`, `run.py:2095-2105` + the pre-stage hook
   `run.py:1060-1069`). The user watched Discovery build on the stale branch.
2. **The next-free id ignores git and the ledger** — a folder on an unmerged branch is invisible, so the
   number is reused (`workspace.py:189-197`). The authoritative sources (branches, ledger) are right there
   but unconsulted.
3. **"Pull latest" is entirely absent** — no `fetch`, and `base_tip` is local-only (`gitflow.py:143-146`),
   so a fresh run branches off a possibly-stale local base and inherits the staleness silently.
4. **Concurrency has no guard for the shared working tree** — `allocate_feature_dir` fails fast on a folder
   collision (`workspace.py:206-217`) but nothing prevents two runs racing the git index / branch switches
   in one checkout.

---

## Workstreams

Ordering: **A** (id union) and **B** (fresh-vs-resume intent + guard) are the core fix and land first
(B depends on nothing; A makes B's refusal unreachable in the happy path). **C** (fetch/origin base) and
**D** (run lock) are independent and can land in parallel after A/B. **E** (docs) and **F** (tests) ride
with each workstream in the same unit of work.

### Workstream A — Next-free run id over the union (folders + branches + ledger)

**Goal.** A fresh run's `<NNN>` is unique across everything that has ever allocated one, so it always gets a
new folder AND a new branch.

**Changes.**
- Add a union-aware allocator (e.g. `workspace.next_feature_number` grows optional inputs, or a new
  `workspace.next_run_number(specs_root, *, branch_numbers, ledger_numbers)`), computing `max(union) + 1`
  over:
  - on-disk `specs-src/` (and legacy `specs/`) `NNN-` prefixes (today's source, `workspace.py:189-197`);
  - git branch numbers: parse `<branch_prefix><NNN>-*` from `git for-each-ref refs/heads/` and, when cheap,
    `refs/remotes/<remote>/` — via a new read-only helper in `gitflow.py` on top of `runner._git`
    (`runner.py:583`), returning `[]` on any git error (offline/non-repo safe);
  - ledger `run`/`start` `spec_id`s from `Ledger.entries()` (`ledger.py:98`), the authoritative allocated-id
    record.
- Keep `workspace` pure/deterministic where it is; the git/ledger inputs are **gathered by the caller**
  (`cli/run.py` fresh path, `run.py:2062-2085`) and passed in, so `workspace` stays free of git/ledger
  imports and the function remains unit-testable with plain lists. `gitflow` owns the branch-number scan.
- `allocate_feature_dir` (`workspace.py:206-217`) keeps its `mkdir(exist_ok=False)` fail-fast as the final
  race backstop; the union just makes a same-number collision vanishingly unlikely.

**Acceptance.** With a prior run's folder present only on an unmerged branch (and/or only in the ledger), a
fresh run allocates `max(union)+1`, a new folder, and a new branch — never the prior number.

### Workstream B — `ensure_run_branch` fresh-vs-resume intent + fresh-path guard

**Goal.** Re-entry of an existing branch happens **only** on the resume path; a fresh run that somehow
computes an existing branch REFUSES with an actionable message.

**Changes.**
- Give `ensure_run_branch` (`gitflow.py:149-163`) an explicit intent, e.g.
  `ensure_run_branch(cwd, branch, base, *, mode: "fresh" | "resume")` (or a boolean `allow_reentry`):
  - `resume` → today's behavior: re-enter an existing branch (`gitflow.py:158-160`), else create off base.
  - `fresh` → if the branch already exists, return a **named refusal** (a distinct error string, surfaced
    by the caller as `EXIT_SETUP`) instead of checking it out; otherwise create off base
    (`gitflow.py:161-162`), unchanged.
- Fresh caller (`run.py:2095-2105`): pass `mode="fresh"`. On refusal, print an actionable message pointing
  at `3pwr run --resume --spec-id <NNN>` (mirror the empty-resume guidance style at `run.py:1960-1967`).
- Resume caller (`run.py:2015`): pass `mode="resume"` (no behavior change).
- **Pre-stage hook** (`run.py:1060-1069`): once a run is under way its branch legitimately exists, so the
  per-stage `ensure_run_branch` must re-enter. Pass `mode="resume"` there (or a dedicated `mid_run` intent
  that re-enters) so the hook keeps the run on its branch without tripping the fresh guard.
- Keep every existing safety property: never forced, a refused switch is surfaced not overridden
  (`gitflow.py:159-162`), no history rewrite.

**Acceptance.** A fresh run with a pre-existing computed branch refuses (does not adopt it); a resume
re-enters as before; every mid-run stage stays on the run branch.

### Workstream C — Fetch + `origin/<base>` base resolution + config

**Goal.** A fresh run branches off the latest `origin/<base>` when a remote is available, best-effort and
offline-safe, without mutating the local base.

**Changes.**
- **Config.** Add optional keys to `.3powers/config/git.yaml` (+ its schema `.../schema/git.schema.json`
  + the scaffold copies `engine/src/threepowers/scaffold/config/git.yaml` and
  `.../scaffold/config/schema/git.schema.json`):
  - `fetch_base: true|false` (default `true`, Decision 6) — whether to fetch before branching;
  - `remote: origin` (default `origin`) — the remote name.
  Extend `GitPrefs` (`gitflow.py:67-75`) and `load_prefs` (`gitflow.py:78-105`) tolerantly (same
  missing/malformed posture as the existing keys). Keep the OSS-clean comment style already in the file.
- **Fetch + resolve.** Before branching in `ensure_run_branch` (fresh create path only), when
  `fetch_base` is on: best-effort `git fetch <remote> <base>` (short, non-fatal), then teach `base_tip`
  (or add `base_tip_for_mode`) to prefer `refs/remotes/<remote>/<base>` and fall back to
  `refs/heads/<base>`, then to current HEAD. Thread `remote`/`fetch_base` from `GitPrefs` down to the
  gitflow call (fresh caller `run.py:2102`, and the pre-stage hook must NOT re-fetch — fetch is a fresh-
  create concern only).
- **Best-effort / offline-safe invariants:** no remote, offline, detached HEAD, unborn repo, or a fetch
  failure → silently fall back to local-base / current-HEAD (today's behavior). At most a one-line warning
  (consistent with the `malformed`-warns-once posture). Never force, never fast-forward the local base,
  never block the run on fetch.

**Acceptance.** With a reachable remote, a fresh run's branch points at `origin/<base>`'s tip; the local
`<base>` ref is unchanged. Offline / no-remote / detached / unborn → the run proceeds exactly as today.
`base_branch: develop` works with and without fetch.

### Workstream D — Advisory per-working-tree run lock

**Goal.** A second concurrent `3pwr run` in the SAME working tree fails fast; separate clones/trees are
free; a stale lock self-heals and never wedges a run.

**Changes.**
- A small advisory lock module (or a helper in `workspace`/a new `runlock.py`) taking a lock under the
  per-working-tree engine state (e.g. `.3powers/run.lock`, alongside the existing `ENGINE_STATE_PREFIX`
  `.3powers/` `gitflow.py:53`). The lock file records `{pid, host, started_at}`.
- Acquire at the top of `cmd_run` for BOTH fresh and resume paths (before the clean-start guard / any side
  effect), release in a `finally`. On contention: if the recorded pid is alive on this host → refuse fast
  with an actionable message naming the other run; if the pid is dead or the mtime is older than a
  generous TTL → treat as stale, reclaim, and proceed (self-heal).
- **Scope = the working tree**, not the repo/remote: the lock lives under the checkout's `.3powers/`, so two
  developers in two clones (or two `git worktree` checkouts) each hold their own lock and never contend.
- **Out of the trust spine (Decision 8):** never a gate, verdict, or ledger entry; failure to write the
  lock (read-only FS, etc.) degrades to a warning, never blocks the run — advisory only.

**Acceptance.** Two runs in one checkout: the second refuses with a clear message; a killed run leaves a
lock that the next run reclaims; two runs in two clones both proceed.

### Workstream E — Docs (same unit of work)

- **`docs/cli-reference.md`** — the new `git.yaml` keys (`fetch_base`, `remote`) and the fresh-run isolation
  guarantee (new id + new branch off base; resume is explicit).
- **`docs/getting-started.md` and/or `docs/concepts.md`** — the **big-team story**: many developers + agents
  working only through 3Powers concurrently; the isolation model = each dev on their own clone and/or their
  own dedicated `3pwr/<NNN>-<slug>` branch, every change tracked on that branch and in the signed ledger,
  concurrent runs in one working tree guarded by the run lock.
- **Sandbox clarification** (concepts): `3pwr run`'s isolation is the dedicated branch + per-stage commits +
  signed ledger; the sanitized git worktree is **oracle-dispatch-only**; a worktree-isolated run mode is
  noted as future work (Decision 7).
- **`README.md` (line 75) and `docs/getting-started.md` (lines 23-26, 145-151)** — lead with the uv install
  from PyPI (`uv tool install threepowers`, and the zero-install `uvx threepowers`), keeping the
  install-from-clone (`uv tool install ./engine`) as a secondary "from source" option. Covered in detail by
  Workstream G but authored in the same unit of work.
- OSS-clean: no internal spec/requirement ids in help/docs/error text; `git.yaml` comments stay OSS-clean
  (enforced by `engine/tests/test_oss_readiness.py`).

### Workstream F — Tests

- **Regression (the specific bug), must fail without the fix:** a prior run's branch/folder exists **only on
  an unmerged branch** → a fresh run gets a NEW id + a NEW branch off base, never re-entering the stale one.
  Exercise `next_run_number` (union) + `ensure_run_branch(mode="fresh")` together.
- **Workstream A:** `test_run_workspace.py` / `test_workspace*.py` — union of folders + branch numbers +
  ledger ids yields `max+1`; branch-only and ledger-only prior ids are both respected; `[]`/offline inputs
  degrade to the on-disk-only number (back-compat).
- **Workstream B:** `test_gitflow*.py` — `mode="fresh"` refuses on an existing branch (named error, no
  checkout); `mode="resume"` re-enters; the pre-stage hook keeps a mid-run stage on its branch.
- **Workstream C:** `test_gitflow*.py` — with a fake remote-tracking ref, the fresh branch points at
  `origin/<base>`; fetch failure / no remote / detached / unborn all fall back with no error; local base
  never fast-forwarded; `base_branch: develop` honored. `test_config*.py` — new keys parse and default.
- **Workstream D:** a new `test_runlock.py` — second acquire in one tree refuses; stale (dead pid / old
  mtime) reclaims; separate trees both acquire; a lock-write failure degrades to a warning.
- **Whole engine:** `cd engine && uv run pytest && uv run ruff check . && uv run mypy src`, then
  `3pwr gate run --path engine` green (incl. `test_oss_readiness.py` and the High-risk coverage floors —
  the trust-spine modules must stay untouched by this work).

### Workstream G — First `v1.0.0` release + PyPI Trusted Publishing (uv-installable)

**Goal.** After Workstreams A–F are green and merged, the `threepowers` distribution is published to PyPI as
`1.0.0` via a tag-triggered, tokenless GitHub Actions workflow, and uv is the documented primary install.
This is the **last** workstream — it must not begin until the fix is green so the released artifact and the
`v1.0.0` tag capture the isolation fix.

**Changes.**
- **Version + metadata bump** in `engine/pyproject.toml`: `version` `1.0.0rc1` → `1.0.0`; classifier
  `Development Status :: 4 - Beta` → `Development Status :: 5 - Production/Stable`. Leave `name`
  (`threepowers`), the `3pwr` script entry, deps, and urls unchanged. Sanity-check `[project.urls]` and
  `readme = "README.md"` render correctly on PyPI (the repo README is the long description).
- **Release workflow** — new `.github/workflows/release.yml`, triggered on pushing a tag matching `v*`
  (e.g. `v1.0.0`):
  - a `build` job: checkout, install uv (`astral-sh/setup-uv`), `uv build` in `engine/` producing the sdist +
    wheel under `engine/dist/`;
  - a `publish` job with `permissions: id-token: write` and a GitHub `environment:` (e.g. `pypi`), using PyPI
    Trusted Publishing (OIDC) — either `uv publish` with no token (OIDC) or the official
    `pypa/gh-action-pypi-publish` — to upload `engine/dist/*`. No API token is stored anywhere.
  - Guardrails: the workflow should verify the tag version matches `pyproject.version` before publishing
    (fail fast on a mismatched tag), and only run publish on the upstream repo (not forks).
- **Manual one-time prerequisite (documented, not a code task):** register the Trusted Publisher on PyPI for
  project `threepowers` — repository `VerzCar/3powers`, the `release.yml` workflow filename, and the matching
  environment name — and reserve/own the `threepowers` project name. Capture these exact values in the plan
  hand-off / release notes so the maintainer can complete the PyPI-side setup before the first tag.
- **Install docs (with Workstream E):**
  - `README.md:75` — primary: `uv tool install threepowers` (and `uvx threepowers` for a throwaway run);
    secondary "from source": the existing clone + `uv tool install ./engine`.
  - `docs/getting-started.md:23-26` and `:145-151` — same reordering; keep prerequisites (`uv`, `git`) and
    the `Installed 1 executable: 3pwr` confirmation; note the CLI is `3pwr` even though the package is
    `threepowers`.
  - `docs/STATUS.md` — reflect the `1.0.0` release (milestone/validation line) per the "status lives in one
    place" rule.
  - `CHANGELOG.md` (hand-maintained top-level) — add the `1.0.0` release entry (Keep-a-Changelog), including
    the isolation fix and the uv/PyPI availability.
- **Release procedure (documented in the plan hand-off):** merge the feature branch → bump is already in →
  tag `v1.0.0` on the merge commit → push the tag → workflow builds + publishes → verify
  `uv tool install threepowers` from a clean machine resolves `1.0.0` and `3pwr --version` reports it.

**Acceptance.** Pushing `v1.0.0` builds and publishes `threepowers==1.0.0` to PyPI with no stored token;
`uv tool install threepowers` and `uvx threepowers` work from a clean environment; `3pwr --version` reports
`1.0.0`; README + Getting Started lead with the uv install; STATUS + CHANGELOG record the release.

**Dependencies / ordering.** Strictly last: begins only after A–F (and the Verification phase) are green and
the fix is on the release commit, so the published artifact contains the isolation fix.

---

## Affected files

- `engine/src/threepowers/workspace.py` — union-aware run-number allocation (`next_feature_number`
  `189-197`; `allocate_feature_dir` `206-217`).
- `engine/src/threepowers/gitflow.py` — `ensure_run_branch` fresh-vs-resume intent + fresh guard
  (`149-163`); `base_tip` remote-aware resolution (`143-146`); new fetch + branch-number scan helpers;
  `GitPrefs`/`load_prefs` new keys (`67-105`).
- `engine/src/threepowers/cli/run.py` — fresh path passes `mode="fresh"` + gathers branch/ledger ids +
  refusal message (`2062-2105`); resume path `mode="resume"` (`2015`); pre-stage hook stays on-branch
  (`1060-1069`); acquire/release the run lock in `cmd_run`.
- `engine/src/threepowers/runner.py` — low-level `_git` reused for the new read-only git helpers
  (`583-591`); no behavior change to `_changed_files`.
- New: `engine/src/threepowers/runlock.py` (or a `workspace` helper) — the advisory per-working-tree lock.
- `.3powers/config/git.yaml` + `.3powers/config/schema/git.schema.json` + the scaffold copies under
  `engine/src/threepowers/scaffold/config/` (`git.yaml`, `schema/git.schema.json`) — `fetch_base`,
  `remote`.
- `docs/cli-reference.md`, `docs/getting-started.md`, `docs/concepts.md` — the isolation guarantee, the
  big-team model, the new keys, the sandbox clarification.
- Tests: `test_workspace*`/`test_run_workspace.py`, `test_gitflow*.py`, `test_config*.py`, new
  `test_runlock.py`, plus the cross-cutting regression test.
- **Release (Workstream G):** `engine/pyproject.toml` (version `1.0.0rc1`→`1.0.0`, Development Status
  classifier); new `.github/workflows/release.yml` (tag-triggered OIDC publish); `README.md` (install
  section, line ~75); `docs/getting-started.md` (install, lines ~23-26 & ~145-151); `docs/STATUS.md`
  (1.0.0 milestone); `CHANGELOG.md` (1.0.0 entry).

## Risks & edge cases

- **Detached HEAD / unborn repo** — `current_branch` already returns `""` (`gitflow.py:133-136`); creation
  falls back to current HEAD (`gitflow.py:161`). The union scan and fetch must both no-op cleanly here.
- **Offline / no remote / fetch failure** — best-effort fetch must never fail the run; fall back to
  local-base / current-HEAD with at most a one-line warning (Decision 4).
- **Diverged base** — branching off `origin/<base>` deliberately ignores an out-of-date local base; the
  local base is never fast-forwarded, so no surprise mutation of the developer's checkout.
- **Remote naming** — non-`origin` remotes handled via the `remote` config key; an unknown remote → fetch
  fails → fall back (no crash).
- **Stale lock** — a crashed run must not wedge the next; pid-liveness + mtime-TTL self-heal (Decision 5);
  a lock-write failure degrades to advisory-warning, never blocks.
- **Concurrent id race in one tree** — the union narrows the window; `mkdir(exist_ok=False)`
  (`workspace.py:216`) is the final backstop; the run lock removes the same-tree race entirely.
- **Branch-number scan cost / large repos** — `for-each-ref` is cheap; remote refs consulted only "where
  cheaply available" and never block; any git error → `[]`.
- **Trust-spine boundary** — id allocation, fetch, and the lock must never become a gate/verdict/ledger
  input; keep them notifications-style isolated (verified by the High-risk coverage + `gate_gaming` staying
  green).
- **Release ordering** — Workstream G must not tag/publish until A–F are green on the release commit;
  publishing a `1.0.0` that lacks the fix would be worse than no release. Tag the merge commit, not the
  feature branch mid-flight.
- **PyPI Trusted Publishing prerequisites** — the OIDC publish fails until the maintainer registers the
  trusted publisher on PyPI (project `threepowers`, repo `VerzCar/3powers`, `release.yml`, environment) and
  owns the `threepowers` name; the workflow's tag-vs-`pyproject.version` guard prevents a mismatched-tag
  publish. `1.0.0` cannot be re-uploaded to PyPI (immutable) — get the version/artifact right before tagging.
- **Package-vs-CLI name mismatch** — the distribution is `threepowers` but the command is `3pwr`; docs must
  state both so `uv tool install threepowers` users know to run `3pwr`.

## Definition of done

- A fresh run with a prior run's branch/folder only on an unmerged branch gets a NEW id + NEW branch off
  base; a fresh run never adopts an existing branch (refuses if it somehow computes one); resume is
  unchanged and explicit.
- Fresh runs branch off `origin/<base>` when a remote is reachable (opt-in default), else fall back safely;
  `base_branch: develop` works end to end; the local base is never mutated.
- A second run in the same working tree fails fast; separate clones/trees are unaffected; a stale lock
  self-heals.
- `docs/` updated in the same unit of work (isolation guarantee, big-team model, new keys, sandbox note);
  no internal ids leak (OSS-readiness green).
- Engine green under ruff/mypy/pytest and its own `3pwr gate run --path engine`, including the regression
  test that fails without the fix and the untouched High-risk coverage floors.
- `threepowers 1.0.0` is published to PyPI via the tokenless tag-triggered workflow; `uv tool install
  threepowers` and `uvx threepowers` resolve `1.0.0` from a clean environment and `3pwr --version` reports
  it; README + Getting Started lead with the uv install (from-source kept as secondary); STATUS + CHANGELOG
  record the release; the `v1.0.0` tag sits on the commit that carries the isolation fix.

## Open questions

None — the five substantive forks were chosen by the maintainer (Intent + confirmed design decisions);
the rest are engineering defaults grounded in this session's code read.

## Suggested handover

Next step is the **implementation-plan agent** → `plan/IMPLEMENTATION-009-feature-fresh-run-isolation-and-base-branch.md`
(phased, file-scoped). Suggested phase order: A (union id) → B (fresh-vs-resume intent + guard) →
C (fetch/origin base + config) → D (run lock) → E (docs) → a dedicated Verification phase (regression +
whole-engine gates) → **G (v1.0.0 release + PyPI Trusted Publishing + uv install docs), strictly last** so
the tag and the published artifact capture the fix. All `engine/` changes go through the python-engineer
agent; the release workflow (`.github/workflows/release.yml`) and docs are ordinary changes in the same
unit of work. Note the manual PyPI Trusted-Publisher registration is a maintainer prerequisite the
implementation plan should call out (not a code task). Per AGENTS.md the handover is explicit — say the word
and I'll dispatch it.
