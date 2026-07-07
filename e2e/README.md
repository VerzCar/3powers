# End-to-end testing kit

Real-world tests of the `3pwr` CLI itself. Each sample project here is a small,
enterprise-shaped codebase wired to one language adapter; a fixed Jupyter
notebook drives the **whole `3pwr` lifecycle** against it inside a throwaway
sandbox, proving the CLI works end to end on that language.

```
e2e/
├── run.sh                 # one-command runner: ./e2e/run.sh <lang> [--check]
├── config/roles.yaml      # the single shared headless-integration config
├── harness/               # papermill-pinned runner + bootstrap.py (sandbox provisioning)
├── typescript-orders/     # order-pricing sample  → TypeScript adapter
│   ├── project/           #   the committed template (source + lockfile only)
│   └── run.ipynb          #   the fixed lifecycle notebook
├── python-inventory/      # inventory sample       → Python adapter
└── go-ratelimit/          # rate-limiter sample    → Go adapter
```

## Prerequisites

- **`3pwr`** — install the CLI: `uv tool install ./engine` (from the repo root).
- **[uv](https://docs.astral.sh/uv/)** — runs the papermill harness and the Python sample.
- Per language you want to drive:
  - TypeScript → **Node.js 20+** and **npm**
  - Python → **uv** (above)
  - Go → the **Go toolchain** and **`gcov2lcov`**
    (`go install github.com/jandelgado/gcov2lcov@latest`)
- For a **full run** only: a working headless agent CLI (**`copilot`** by
  default) and its credentials. The `--check` path needs none of these.

Each notebook's preflight cell probes exactly the tools its run needs and fails
fast with the install hint when one is missing — you never get a misleading
failure deep into a run.

## The ephemeral sandbox model

A real `3pwr run` creates a branch, a signed ledger, `specs/` artifacts, and
verdicts. To keep all of that out of this repository, every run works on a
**throwaway sandbox**: `bootstrap.py` copies a project template to a temp
directory, turns it into its own git repository, installs its dependencies,
mints a sandbox-scoped signing key **outside** the repo, runs `3pwr init`, and
seeds the shared headless config. The executed notebook and run logs are written
beside that sandbox — never back into this tree — and the sandbox is removed at
teardown (keep it with `--keep`).

The committed templates therefore contain **source and lockfiles only** — no
inner `.git`, no `node_modules`/`.venv`/module cache, no coverage output.
Dependencies are installed only inside the sandbox.

## Running

```bash
# Full lifecycle run — dispatches the configured headless agent (needs its CLI):
./e2e/run.sh typescript
./e2e/run.sh python
./e2e/run.sh go

# Check / dry run — deterministic, zero-credential; the sim runner, no agent:
./e2e/run.sh go --check
```

Options: `--intent "<text>"` overrides the canned intent · `--integration NAME`
picks the agent backend · `--approver NAME` records the approver at the two human
gates (default `e2e-harness`) · `--keep` leaves the sandbox in place · `--check`
takes the deterministic no-agent path.

**`--check` is the standing regression test for the kit** — it provisions a
sandbox, proves the baseline gate suite is green, and drives `3pwr run` through
both human gates on the offline sim runner. Run it whenever you change an adapter
or a sample project to catch drift before any agent is dispatched.

## How an agent drives a notebook

The notebook is a plain CLI session an agent (or a person) can follow by hand:

1. Run the cells top to bottom. Provisioning, the trust-setup check, and the
   **baseline gate suite must be green before any lifecycle run**.
2. `3pwr run` stops at the **spec-approval** gate. **Read the rendered spec**,
   decide whether it captures the intent, then approve with
   `3pwr run --resume --approver <you>`.
3. The run advances through plan, build, and verify, then stops at the
   **sign-off** gate. Review the verdict and approve the same way.
4. The post-run cell checks **invariants only** — the ledger verifies, the run
   shows as completed, the feature folder holds the stage artifacts, and one
   cheap behavioral smoke passes. It never asserts exact agent-authored content,
   which differs every run.

Both human gates are genuinely exercised through the CLI's own `--resume` path;
nothing is auto-approved.

## Invariants

- **The notebook is the fixed configuration.** To change how a project is
  exercised, edit its `run.ipynb` — nowhere else. The three notebooks share one
  identical skeleton; only the parameters cell (language + intent) and the single
  behavioral-smoke line differ.
- **Committed notebooks keep cleared outputs.** `run.sh` writes the executed copy
  (with outputs) to the sandbox artifact directory, so re-running never churns a
  committed notebook. If you open a notebook in Jupyter, clear its outputs before
  committing.
- **Each sample stays green under its full adapter gate set** at Standard tier
  from a fresh sandbox. That check is the notebook's baseline cell, so a red gate
  fails the run before any agent is dispatched.
