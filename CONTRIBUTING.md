# Contributing to 3Powers

Thanks for your interest in 3Powers! This is a spec-driven project with an unusual—but simple—premise:
**the spec is the law, and every change is judged against it by an independent judiciary.** 3Powers is
built using 3Powers, so contributing means playing by the same rules the tool enforces. This guide gets
you set up and explains the workflow.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md). Contributions are accepted under
the project's [Apache-2.0](LICENSE) license.

## Ways to contribute

- **Report a bug** or **request a feature** — open an issue (templates guide you).
- **Improve the docs** — clarity fixes, examples, and guides are always welcome.
- **Add a language adapter** — teach 3Powers a new language declaratively (see below).
- **Fix or extend the engine** — pick up an open issue or a residual noted in [STATUS](docs/STATUS.md).

For anything larger than a small fix, please open an issue first so we can agree on the shape of the
change before you invest time.

## Development setup

You need [`uv`](https://docs.astral.sh/uv/) (Python tooling) and `git`. The TypeScript sample also needs
`npm`. Some gates shell out to optional tools (`betterleaks`/`gitleaks`, `osv-scanner`, `semgrep`); when
one is absent its gate is *quarantined* (surfaced as skipped), never silently passed.

```bash
git clone https://github.com/VerzCar/3powers.git
cd 3powers

# Install the CLI so you can dogfood it
uv tool install ./engine

# Set up the engine dev environment and run the checks it must always pass
cd engine
uv sync --extra dev
uv run pytest                       # the test suite
uv run ruff check .                 # lint
uv run mypy src                     # types
```

Create an independent signer once (its private key is written **outside** the repo; only the public key is
committed):

```bash
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/3powers.key"
```

## The workflow: spec first, then code

3Powers separates the powers on purpose. A code change follows the lifecycle
(**Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe**):

1. **Write or extend a spec.** Requirements live versioned under [`specs/`](specs/), in
   [EARS](https://alistairmavin.com/ears/) form. Each spec has a unique **Spec ID** and namespaced
   requirement IDs (e.g. `VUTIL-FR-001`), a declared **risk tier**, and an explicit **non-goals** section.
   Keep implementation detail (a specific database, framework, or library) *out* of the spec.
2. **Plan and implement** against the spec. Every task, commit, and test should trace to a requirement ID.
3. **Author the oracle independently.** For anything beyond a cosmetic change, the acceptance tests are
   written from the spec — by a *different model family* than the coder, and without reading the
   implementation. The engine records and checks this.
4. **Run the gates and read the verdict:**
   ```bash
   3pwr gate run --path <target> --spec specs/<feature>/spec.md --tier <tier>
   3pwr verify        # recompute the signed ledger chain, offline
   ```
5. **Sign off and advance.** A human approves the evidence; `advance` refuses to proceed without green
   gates *and* a sign-off.

The whole sequence can be driven with a single command — `3pwr run "<intent>"` — or step by step with the
GitHub Copilot slash commands. See **[Getting Started](docs/getting-started.md)** and the
**[CLI Reference](docs/cli-reference.md)**.

## Conventions

- **Trace to a requirement.** Tasks, commits, and tests each map to exactly one requirement ID. Add tests
  that reference the requirement they exercise.
- **Match the surrounding code.** Follow the naming, comment density, and idioms already in the file.
- **Never satisfy a gate by weakening it.** Don't disable a lint rule, add a broad `# type: ignore`, delete
  an assertion, or lower a threshold to get green. If a gate genuinely needs an exception, record a signed,
  reversible **deviation** (`3pwr deviation`) — it's logged and reviewable, never silent.
- **Keep the engine green under its own gates.** Engine changes must pass `ruff`, `mypy`, and `pytest`, and
  the trust-spine modules (`canonical`, `keys`, `ledger`, `verify`) are held to the **High-risk** tier —
  keep their diff-coverage ≥95%.
- **Respect task file-scope.** Editing outside a task's declared file scope is a signal to stop and
  re-spec, not to push through.

## Adding a language adapter

Language support is a **declarative manifest** — the core assumes no language. To add one, write an
`adapter.yaml` under [`.3powers/adapters/<lang>/`](.3powers/adapters/) following
[`.3powers/adapters/CONTRACT.md`](.3powers/adapters/CONTRACT.md). The TypeScript, Python, and Go adapters
are working references. No core code changes should be necessary.

## Submitting a pull request

1. Branch off `main` (or the current working branch if directed on the issue).
2. Make your change, keeping the engine green (`ruff` + `mypy` + `pytest`) and running the relevant gates.
3. Write a clear PR description: what changed, why, and the requirement ID(s) it traces to. Reference the
   issue it closes.
4. Be ready to iterate on review — a residual review may flag intent gaps as *new requirements* rather than
   quiet code fixes; that's the process working.

Not sure about something? Open an issue or a draft PR and ask. See [GOVERNANCE.md](GOVERNANCE.md) for how
decisions are made.
