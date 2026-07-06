# Plan 032 — Per-adapter e2e notebook projects (and retiring `examples/`)

**Git branch:** authored and delivered on `claude/3powers-e2e-testing-plan-lo46g1` (the branch
designated for this unit of work; it stands in for the usual `feat/032-…` name — same discipline:
dedicated branch, no pull requests).

**Intent (verbatim requirements, condensed):** every language adapter (Go, Python, TypeScript)
gets a small example application for **end-to-end testing of the `3pwr` CLI itself**; the projects
live under a new top-level `e2e/` folder; the current `examples/` folder (one TypeScript sample)
is deleted; each e2e project is driven by a **Jupyter notebook** with a fixed, committed cell
sequence that provisions a **dedicated sandbox** and readies the project *before* any `3pwr`
command runs; the notebooks are built so **an agent can execute real `3pwr` commands** against
them; the **headless CLI integration is configured once** and shared by all projects; there is an
**easy run command** for a complete `3pwr run` per project; the samples carry an
**enterprise-ready baseline** (not too basic, not too detailed); and `AGENTS.md`, `CLAUDE.md`, and
all affected docs are updated to (a) instruct that real-world CLI testing happens in these
projects and (b) reflect that `examples/` is gone.

## Decisions recorded

Authored non-interactively as recommendations; **confirmed by the user on 2026-07-06** with one
change: the default headless integration is **copilot**, not claude (easier access, and model
families can be switched within the one backend). The former open questions and their resolutions
are recorded at the end. The plan is **finalized**.

| # | Decision | Recommendation | Rationale |
|---|---|---|---|
| 1 | Where does a run actually execute? | **Ephemeral sandbox copy.** Each committed project is a plain template tree (`e2e/<name>/project/`, no inner `.git`). The notebook's provisioning cells copy it to a throwaway directory, `git init` + initial commit, `3pwr keygen` with a sandbox-scoped key, `3pwr init --yes --language <lang>`, then seed the shared headless config. | 3Powers uses Git as substrate — a real `3pwr run` creates branches, a ledger, `specs/`, verdicts. Running in-place would either nest git repos inside this repo or pollute it with run artifacts on every e2e execution. A sandbox makes runs repeatable, disposable, and safe to parallelize; it is also literally the "dedicated sandbox" the intent asks for. |
| 2 | Notebook execution + the easy run command | **`./e2e/run.sh <typescript|python|go>`** wrapping **papermill** from a small uv-managed harness (`e2e/harness/`). Parameters cell per notebook: `INTENT`, `INTEGRATION`, `MODE`, `TIER`, `KEEP_SANDBOX`, `DRY_RUN`. The executed notebook (with outputs) is written to the sandbox, never back into the repo; committed notebooks keep cleared outputs. | Papermill gives parameterized, headless, deterministic top-to-bottom execution — exactly "fixed written notebook configuration". A bash wrapper keeps the entry point one memorable command per project; uv pins the notebook toolchain the same way the engine pins its own. |
| 3 | How the two human gates are handled in a "complete run" | The notebook drives `3pwr run "$INTENT" --mode auto --no-input`, expects the documented pause at the spec gate (exit 3), surfaces the spec for inspection, then continues with `3pwr run --resume --approver "$APPROVER"`; same again at sign-off. `run.sh` defaults `APPROVER` to `e2e-harness`. | The gates are **exercised, never bypassed** — the resume path is the CLI's own sanctioned mechanism and the ledger records the approver. When an agent drives the notebook, the agent *is* the reviewing human-stand-in and can genuinely read the spec between cells; when a human drives it, they approve for real. |
| 4 | Shared headless integration | **One config, `e2e/config/`** (`roles.yaml` naming the coder/oracle integrations + model families, optional `models.yaml`), seeded into every sandbox by the shared bootstrap after `3pwr init`. Default integration: **`copilot`** (user decision: easiest access, and one backend that can switch between model families — which also makes coder-vs-oracle family diversity a pure config choice). Any backend listed in the engine's `headless_integrations` works; the parameter cell overrides per run. | "Configured once and used for all the sample projects" — the config lives in exactly one place; projects never carry their own copy. |
| 5 | What "enterprise-ready, not too detailed" means | Per project: layered `src/` (config → domain → service), typed error handling, a small logging abstraction, unit **and** integration tests, strict format/lint/types wired exactly as the adapter manifest expects, LCOV coverage at the adapter's `coverage_path`, the adapter's mutation tool configured, a lockfile, `README.md`, `.gitignore`, `.editorconfig`. **Explicitly excluded:** Dockerfiles, Kubernetes/IaC, CI pipelines, auth, databases, external network calls. | The samples must be rich enough that a `3pwr run` does representative work (real layers to modify, real tests to extend) and every adapter gate has something genuine to chew on — but every extra artifact is surface the e2e kit must keep green forever. |
| 6 | Fate of `specs/001-validation-utils/` | **Keep, untouched.** Only `examples/validation-utils/` is deleted. | The spec artifacts are history bound into the signed ledger; deleting or editing them risks tripping `verify`/`spec_integrity` and erases the traceability record. Dangling references *from docs* to the deleted example are fixed in Track D; the spec folder itself is an internal artifact and may reference the past freely. |
| 7 | CI involvement | Full lifecycle runs are **agent/human-driven only** (they dispatch a live coding agent — cost, credentials, nondeterminism). A cheap deterministic path exists for automation: `./e2e/run.sh <lang> --check` provisions the sandbox and runs baseline gates + `3pwr run --dry-run`, no agent dispatch. Wiring `--check` into CI is a follow-up, not part of this plan. | Keeps the e2e kit honest (the real thing needs a real agent) without leaving zero machine-checkable surface. |

---

## Why now

1. **The CLI has no end-to-end proving ground.** The engine's pytest suite verifies units and the
   gate engine verifies *target* projects, but nothing in the repo exercises the full lifecycle —
   `init` → `keygen` → `run` → gates → ledger → `verify` — against a realistic project per
   adapter. Every "does the whole thing actually work" check today is ad-hoc.
2. **Two of three adapters have no sample at all.** The Go and Python adapters ship as manifests
   with no project to run them against; only TypeScript has `examples/validation-utils`, and that
   sample predates the native executive — it demonstrates `gate run`, not a lifecycle run.
3. **`examples/validation-utils` is a maintenance liability at the wrong altitude.** It is wired
   into docs, README, AGENTS.md, and two `dependencies.yaml` comments, yet tests nothing the e2e
   kit wouldn't test better. Replacing it wholesale is cheaper than upgrading it.
4. **Agent-driven testing needs a fixed script.** An agent asked to "test 3pwr for real" today has
   to improvise setup; a committed notebook makes the procedure deterministic, reviewable, and
   identical across the three languages.

---

## Target layout

```
e2e/
  README.md                     # the kit's public guide: prerequisites, one-command runs, sandbox model
  run.sh                        # easy run command: ./e2e/run.sh <typescript|python|go> [--intent "…"] [--check]
  harness/
    pyproject.toml              # uv project pinning jupyter/papermill/nbclient
    uv.lock
    bootstrap.py                # shared sandbox provisioning used by every notebook
  config/
    roles.yaml                  # the ONE headless-integration config (coder/oracle backends, families)
  typescript-orders/
    run.ipynb                   # fixed notebook (cleared outputs)
    project/                    # order-pricing service: src/{config,domain,service}, tests/{unit,integration},
                                # package.json + package-lock.json, tsconfig (strict), biome.json,
                                # vitest.config.ts (lcov → coverage/lcov.info), stryker.conf.json,
                                # README.md, .gitignore, .editorconfig
  python-inventory/
    run.ipynb
    project/                    # inventory service: pyproject.toml + uv.lock, src-layout package,
                                # tests/{unit,integration}, ruff + mypy(strict) config,
                                # pytest-cov → coverage/lcov.info, mutmut config, README, .gitignore, .editorconfig
  go-ratelimit/
    run.ipynb
    project/                    # rate-limiter service: go.mod/go.sum, idiomatic package layout,
                                # table-driven unit tests + integration tests, gofmt/go vet clean,
                                # go test coverprofile → gcov2lcov → coverage/lcov.info, README, .gitignore, .editorconfig
```

Every `project/` tree must be green under its adapter's full gate set (Standard tier) from a fresh
sandbox — that is the kit's standing invariant, checked by the notebooks' baseline-gate cell.

## The fixed notebook skeleton (identical shape in all three)

1. **Parameters** (papermill-tagged): `INTENT` (per-project canned default, see Track B),
   `INTEGRATION` (default from `e2e/config/roles.yaml`), `MODE` (`auto`), `TIER` (`Standard`),
   `APPROVER` (`e2e-harness`), `KEEP_SANDBOX` (`false`), `DRY_RUN` (`false`).
2. **Preflight** — probe the adapter's declared toolchain (the manifest's `probe` commands), the
   `3pwr` install, and (unless `DRY_RUN`) the selected agent CLI; fail fast with the exact install
   hint on any miss.
3. **Sandbox provisioning** (via `harness/bootstrap.py`) — copy `project/` to a fresh temp dir,
   `git init`, initial commit; install project dependencies from the lockfile.
4. **Trust setup** — sandbox-scoped `3pwr keygen`, export `THREEPOWERS_SIGNING_KEY_FILE`,
   `3pwr init --yes --language <lang>`, overlay `e2e/config/roles.yaml`.
5. **Baseline gates** — `3pwr gate run` must be green *before* the lifecycle run; this is the
   "project runs and is ready before executing the CLI" requirement made executable, and doubles
   as the kit's regression check against adapter changes.
6. **Lifecycle run** — `3pwr run "$INTENT" --mode auto --no-input` (with `--dry-run` when
   `DRY_RUN`); assert the documented pause at the spec gate.
7. **Spec approval** — render the generated spec for the driving agent/human to read, then
   `3pwr run --resume --approver "$APPROVER"`.
8. **Sign-off** — same resume mechanics at the second human gate.
9. **Post-run assertions** — `3pwr verify` exits 0; `3pwr status` shows the completed run; the
   feature folder `specs/<NNN>-<slug>/` contains the stage artifacts; the intent's acceptance
   behavior is present (one cheap smoke assertion per project).
10. **Teardown** — remove the sandbox unless `KEEP_SANDBOX`; always print the sandbox path first.

---

## Track A — Shared harness and headless config

- `e2e/harness/` uv project (papermill + jupyter pinned; lockfile committed) and
  `harness/bootstrap.py`: sandbox copy, git init, dependency install per language, key + init +
  config overlay. One implementation, three thin per-notebook call sites.
- `e2e/config/roles.yaml`: the single headless-integration config (decision 4) — coder
  integration **`copilot`**, oracle integration also `copilot` but pinned to a **different model
  family** (honoring the diversity recommendation; copilot makes the family switch a config-only
  change), `require_dispatch` left at default.
- `e2e/run.sh`: maps `<lang>` → notebook, forwards `--intent/--integration/--check/--keep`,
  executes via `uv run --project e2e/harness papermill …`, writes the executed notebook + run log
  to the sandbox's artifact dir, and propagates the notebook's exit status.

**Tests:** `run.sh --check` for each language must pass end-to-end on a machine with the
toolchains installed (deterministic: no agent dispatch). Harness code lives under `e2e/`, not
`engine/`, so no engine gates apply; keep `bootstrap.py` stdlib-only so the harness venv stays
papermill-only.

## Track B — The three sample projects

One small, layered service per adapter, each with a canned default `INTENT` that produces
representative work for a lifecycle run:

| Project | Domain (deliberately boring, no I/O) | Canned intent |
|---|---|---|
| `typescript-orders` | Order pricing: line items, tax rules, currency rounding, an order service over a pricing domain | "add a percentage-based bulk discount rule to order pricing" |
| `python-inventory` | Inventory tracking: stock levels, reservations, reorder thresholds, a service layer over typed domain models | "add a low-stock reorder suggestion to the inventory service" |
| `go-ratelimit` | Rate limiting: token bucket + sliding window strategies behind one interface, a limiter registry | "add a fixed-window rate-limiting strategy" |

Each is built to the enterprise baseline of decision 5, wired **exactly** to its adapter manifest:
Biome/tsc/Vitest(+lcov)/Stryker for TypeScript; ruff/mypy/pytest-cov(+lcov)/mutmut under uv for
Python; gofmt/go vet/go build/`go test -coverprofile` + gcov2lcov for Go. Test files follow the
adapter's conformance patterns (describe/it + expect; `def test_*` + assert; `func TestX` +
`t.Errorf`/testify) so `spec_conformance` binding works on runs that add requirements.

**Tests:** for each project, from a fresh sandbox: dependency install from lockfile succeeds;
the full adapter gate set is green at Standard tier; the notebook's baseline-gate cell (Track C)
encodes this permanently.

## Track C — Notebooks and the complete-run path

- Three `run.ipynb` files implementing the fixed skeleton above; committed with cleared outputs;
  all `3pwr` invocations in plain `%%bash`-style cells so the transcript reads as a CLI session an
  agent can mimic or a human can replay line by line.
- The complete-run path (`./e2e/run.sh typescript`, etc.) executes the whole notebook including
  both resume gates; `--check` stops after cell 5 plus a `--dry-run` lifecycle cell.
- `e2e/README.md`: prerequisites (uv, node, go, gcov2lcov, an agent CLI), the sandbox model, the
  one-command runs, how an agent should drive a notebook (read the spec at the pause, then
  resume), and the invariant that committed notebooks are the fixed configuration — edits to the
  procedure happen in the notebook, nowhere else. Open-source ready: no internal requirement IDs.

**Tests:** one full agent-driven run per language executed during implementation and its outcome
recorded in the delivery commit message; `--check` green for all three on the implementer's
machine.

## Track D — Retire `examples/` and update every instruction surface

Delete `examples/` (the whole folder — `validation-utils` is its only content) **in the same unit
of work** as the doc updates, so no commit leaves dangling references:

| Surface | Change |
|---|---|
| `AGENTS.md` | Repository-layout block: drop `examples/validation-utils/`, add `e2e/` with a one-line description. Key-technologies line: replace the sample mention with the e2e kit. Setup commands: replace the `npm install` sample line with the e2e prerequisites + `./e2e/run.sh <lang> --check`. Testing instructions: replace the validation-utils commands with the e2e run commands, and add the instruction: **real-world testing of the `3pwr` CLI happens in the `e2e/` notebook projects — drive them via `./e2e/run.sh`; the former `examples/` folder is deleted.** |
| `CLAUDE.md` | Lockfile line (`examples/validation-utils/package-lock.json` → the e2e lockfiles); add the same real-world-testing instruction to "Working in this repo". |
| `README.md` | Quickstart's gate-run demo re-targeted at an e2e project path (or the engine itself). |
| `docs/getting-started.md` | "Try it on the sample" section rewritten around `e2e/` + `run.sh`, linking `e2e/README.md`. |
| `docs/cli-reference.md` | The four example blocks using `examples/validation-utils`/`specs/001-validation-utils` paths get neutral e2e-based or placeholder paths (behavior text unchanged). |
| `docs/STATUS.md` | Sample references updated; the e2e kit recorded as the runnable sample surface (STATUS remains the single status source). |
| `.3powers/config/dependencies.yaml` + `engine/src/threepowers/scaffold/config/dependencies.yaml` | The two comments pinning "supported ranges vs. lockfile" now cite `e2e/typescript-orders/project/package-lock.json`; both copies edited in the same commit (seeded-copy parity). |
| `specs/001-validation-utils/` | Untouched (decision 6). |

**Tests:** `grep -r "examples/validation-utils"` over the repo (minus `specs/`, `plan/`,
`.3powers/ledger.jsonl`, `.3powers/verdicts/`) returns nothing; the engine's oss-readiness test
still passes; `(cd engine && uv run pytest)` green (no engine code changes expected — if any test
fixture references the examples path, it is re-pointed in the same commit).

---

## Delivery order and dependencies

| Track | Depends on | Risk | Effort |
|---|---|---|---|
| A — harness + shared config | — | Low | Small |
| B — three sample projects | A (baseline-gate check uses the bootstrap) | Medium (breadth) | Medium |
| C — notebooks + run command | A, B | Medium (live-agent moving parts) | Medium |
| D — examples removal + docs | C (docs point at a working kit) | Low | Small |

Single delivery unit on the designated branch, committed per track (A → B [three commits, one per
project — parallelizable] → C → D), everything green at each commit. **No engine source changes
are anticipated**, so the python-engineer gate for `engine/` work is not triggered; if
implementation reveals an engine bug (this is an e2e kit — it may), that fix is its own plan/fix
unit, not smuggled into this one.

## Spec files to create

Self-application: `specs/<NNN>-e2e-notebook-kit/spec.md`, spec ID `E2EKIT` — the kit's invariants
(per-adapter project green under its full gate set from a fresh sandbox; fixed notebook skeleton;
single shared headless config; one-command complete run; no `examples/` references outside
history). `<NNN>` = next free workspace number at implementation time.

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| **Live runs need a real agent CLI + credentials.** A full lifecycle run dispatches a headless coder; on a machine without one, the kit looks broken. | Preflight cell fails fast with the exact backend + install hint; `--check` / `DRY_RUN=true` gives a zero-credential deterministic path; `e2e/README.md` states the split plainly. |
| **Nondeterminism and cost of live runs.** An agent-authored spec/implementation differs run to run. | Post-run assertions check *invariants* (verify green, artifacts exist, gates passed, one behavioral smoke), never exact content; full runs are agent/human-driven, not CI (decision 7). |
| **Sample projects drift red as adapters evolve.** An adapter command change can silently break a `project/` tree. | The baseline-gate cell fails the notebook before any agent is dispatched; `--check` makes that a one-command regression test; AGENTS.md's testing instructions tell agents to run it. |
| **Sandbox/gitignore interference.** A `project/.gitignore` (e.g. `coverage/`, `node_modules/`) must not hide template files from the *outer* repo; template trees must never contain an inner `.git` or installed dependencies. | Bootstrap installs dependencies only in the sandbox; template trees are committed source + lockfiles only; an explicit check in Track B's review: `git status` clean and complete after authoring each template. |
| **Notebook output churn.** Executed outputs committed by accident make every run a diff. | Committed notebooks keep cleared outputs (kit invariant, stated in `e2e/README.md`); `run.sh` writes executed copies to the sandbox only. |
| **Go toolchain breadth.** `gcov2lcov` (and optionally `go-mutesting`) are extra installs beyond `go`. | Probes in preflight with the adapter's own install hints; `e2e/README.md` prerequisites list them; mutation stays opt-in exactly as the adapter declares (`tier_min: High-risk`). |
| **Docs/instruction misses.** A stray `examples/` reference survives. | Track D closes with the repo-wide grep gate (exemptions: `specs/`, `plan/`, ledger/verdicts) run as part of the delivery checklist. |

## Verification (post-delivery)

```bash
./e2e/run.sh typescript --check && ./e2e/run.sh python --check && ./e2e/run.sh go --check
./e2e/run.sh typescript      # one full agent-driven lifecycle run (repeat per language once)
(cd engine && uv run pytest && uv run ruff check . && uv run mypy src)
grep -rn "examples/validation-utils" --exclude-dir=specs --exclude-dir=plan \
  --exclude-dir=.git --exclude=ledger.jsonl -r . && echo STALE || echo clean
test ! -d examples && echo examples-gone
```

---

## Open questions — resolved 2026-07-06

All resolved by the user; the plan is **finalized**.

1. **Default headless integration (decision 4):** **`copilot`** is the seeded default in
   `e2e/config/roles.yaml` — chosen for easiest access and because a single copilot backend can
   switch model families, which also makes the coder-vs-oracle family diversity a config-only
   choice. (Was: `claude`.)
2. **`specs/001-validation-utils/` (decision 6):** **confirmed** — stays untouched as history while
   its subject project (`examples/validation-utils/`) is deleted.
3. **CI (decision 7):** **confirmed** — full lifecycle runs stay out of CI; the `--check` smoke
   wiring into CI is a separate follow-up, not part of this plan.
4. **Approver identity (decision 3):** **confirmed** — `e2e-harness` is acceptable as the recorded
   approver for e2e runs' human gates (`run.sh` default; overridable per run).
5. **Project domains/names (Track B):** accepted as proposed — `typescript-orders` /
   `python-inventory` / `go-ratelimit`.
