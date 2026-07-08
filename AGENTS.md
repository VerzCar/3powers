# AGENTS.md

Guidance for AI coding agents working in this repository. This file complements [`README.md`](README.md): the README is for humans, this file carries the workflow rules and commands an agent needs to contribute effectively. See [`CLAUDE.md`](CLAUDE.md) for the architecture deep-dive and [`docs/`](docs/) for the public guides.

## Project overview

3Powers is a **trustworthy agent harness for spec-driven, agentic software delivery**. It drives your coding agents through the whole lifecycle, then restores the separation of powers when AI writes software: the spec is the law (legislative), agents build (executive), and an independent oracle plus a deterministic gate suite plus human review judge the result (judicial). In short, it is a harness with a judiciary.

**Implementation status lives in exactly one place: [docs/STATUS.md](docs/STATUS.md)** — the current milestone, the validation date, and the open residuals. Do not infer scope or progress from this file; read STATUS.

Key technologies: Python ≥ 3.10 in `engine/` (a uv-managed, src-layout package shipping the `3pwr` CLI; runtime deps only `cryptography` and `PyYAML`), declarative language adapters (TypeScript, Python, Go), and a per-adapter end-to-end notebook kit in `e2e/` for real-world CLI testing.

Repository layout:

```
engine/                     # the 3pwr engine — Python, shipped as a uv tool (src/threepowers/, tests/)
docs/                       # public documentation — kept current with every change
plan/                       # plans and implementation plans (see the mandatory workflow below)
specs-src/                  # spec artifacts produced by 3pwr runs
e2e/                        # per-adapter notebook kit — real-world CLI testing in throwaway sandboxes
.3powers/                   # this repo's own trust spine (config, templates, ledger)
.github/agents/             # the agent roles used by the mandatory workflow
```

## Mandatory workflow: intent → plan → implementation plan → implementation

**No change lands without a plan.** Every unit of work follows this chain, in order:

1. **Intent.** A request arrives (feature, refactor, fix).
2. **Plan.** Created by the **planning agent** ([.github/agents/planning.agent.md](.github/agents/planning.agent.md)). If you receive an intent without an existing plan, do **not** start changing code — create the plan first by dispatching the planning agent as a subagent. Plans live in `plan/` and follow the strict naming convention `PLAN-[iteration number]-description-of-the-topic-of-the-plan.md` (iteration number zero-padded to three digits; check `plan/` for the next available number).
3. **Implementation plan.** Created by the **implementation-plan agent** ([.github/agents/implementation-plan.agent.md](.github/agents/implementation-plan.agent.md)), always derived from a finalized `PLAN-*` file — never invented from scratch. Saved in `plan/` as `IMPLEMENTATION-[continuous count]-[purpose]-[component]-[version].md`.
4. **Implementation.** An implementing agent executes the implementation plan phase by phase. Code changes are always instructed by an implementation plan, never directly from an intent.
   - **All Python code changes** (anything under `engine/`) must be done by the **python-engineer agent** ([.github/agents/python-engineer.agent.md](.github/agents/python-engineer.agent.md)), which takes the implementation plan's phases as input.

## Setup commands

- Install the engine as a CLI: `uv tool install ./engine` (provides `3pwr`; after engine changes reinstall with `uv tool install --force ./engine` — the installed tool can go stale against the source)
- Engine dev environment: `cd engine && uv sync --extra dev`
- End-to-end kit prerequisites: `uv`, plus the toolchains for the languages you drive — Node.js + npm (TypeScript), Go + `gcov2lcov` (Go); a smoke of the whole kit is `./e2e/run.sh <typescript|python|go> --check` (deterministic, no agent). See [e2e/README.md](e2e/README.md).
- One-time signer setup for gate/ledger commands: `3pwr keygen`, then `export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"` (the private key lives **outside** the repo)

## Development workflow

- Engine work happens inside `engine/` — source in `engine/src/threepowers/`, tests in `engine/tests/`.
- A `3pwr` run's stage artifacts lie flat in the run's auto-allocated feature folder `specs-src/<NNN>-<slug>/` — `spec.md`, `plan.md`, `tasks.md`, `oracle.md`, `implement.md`, plus the engine-maintained `progress.md`. The legacy base folder `specs/` and the legacy split layout (`specs/<feature>/spec/spec.md` + the sibling `specs/<feature>/artifacts/` folder) stay readable.
- Tasks artifacts group work into ordered phases sized to the context budget (`.3powers/config/context.yaml`); phases marked `[P]` with disjoint file scopes are dispatched in parallel as fresh sessions. The budget is advisory — an oversize phase warns, never blocks.
- The full `3pwr` command surface (gate runs, ledger verification, lifecycle runs, oracle, brownfield, deviations, …) is documented in [docs/cli-reference.md](docs/cli-reference.md). Consult it there; it is not duplicated in this file.
- The engine gates its own code (self-application): keep any engine change green under ruff, mypy, and pytest before declaring it done.

## Testing instructions

- All engine tests: `cd engine && uv run pytest`
- A single test file: `uv run pytest tests/test_<module>.py`
- Lint: `uv run ruff check .` · Types: `uv run mypy src`
- **Real-world testing of the `3pwr` CLI happens in the `e2e/` notebook projects** — drive them with `./e2e/run.sh <lang>` (a full lifecycle run needs a headless agent CLI) or `./e2e/run.sh <lang> --check` (deterministic, no agent). Each run works in a throwaway sandbox and never writes into this repo; the sample templates carry committed source + lockfiles only. There is no longer a top-level `examples/` folder.
- Tests mirror the source layout (`engine/tests/test_<module>.py`). New or changed code ships with tests in the same change; a bug fix ships with a regression test that fails without the fix.
- Trust-spine modules (`canonical`, `keys`, `ledger`, `verify`, `speclock`, `anchor`) are High-risk: keep their coverage ≥ 95%. Mutation testing is scoped to them via `[tool.mutmut]` in `engine/pyproject.toml` — do not widen or narrow that scope.

## Code style

- Python: ruff (line length 100), full type annotations on all public signatures, and a clean `mypy src` (`warn_unused_ignores` is on — a stale `# type: ignore` fails).
- Never satisfy a check by weakening it: no inline lint-disables, type suppressions, deleted assertions, or loosened gate/tool config.
- Every public module, class, and function gets a docstring stating what it does and its contract.
- TypeScript sample: Biome for lint/format, strict TypeScript, Vitest for tests.

## Engine CLI reference

The `3pwr` engine's commands are documented once, publicly, in [docs/cli-reference.md](docs/cli-reference.md). Use that reference for gate runs, ledger verification, lifecycle runs, and every other engine command instead of relying on tables in this file.

## Branch and commit discipline

- All work happens on a **dedicated feature branch**, never directly on `main`. The branch is created by the planning agent from the plan's purpose (`feat/[NNN]-<topic>` or `fix/[NNN]-<topic>`).
- Commit when the unit of work is done — everything green (tests, lint, types) and the docs updated — not as a stream of broken intermediate states.
- **Do not open pull requests.** Delivery ends with the completed, committed feature branch.
- Never force-push shared history and never push to `main` directly.

## Open-source readiness

This is an open-source project. Everything in this repository is public, so all outward-facing content — `docs/`, the README, CLI help text and error messages — must be open-source ready at all times:

- **No internal references in public surfaces.** Do not reference internal plan files, spec artifacts, or internal requirement IDs in `docs/` or in CLI help descriptions. Internal working artifacts belong in `plan/` and `specs-src/` only.
- **Internal requirement IDs stay out of end-user-readable text.** Internal requirement IDs (`3PWR-FR-###` and friends), epic letters, and plan/spec numbers live in `specs-src/`, `plan/`, engine tests (`Covers:` declarations — the requirement IDs in test docstrings that the conformance gate parses), commit messages, `docs/STATUS.md`, and this file — **never** in end-user-readable text: CLI help and messages, engine source docstrings and comments, `docs/` prose, or the scaffold assets shipped by `3pwr init`. Text that teaches the requirement-ID format uses the reserved example namespace (`DEMO-FR-###`) or bare `FR-###`. This composes with the de-jargon rule above: the *user's own* IDs stay in their artifacts; *3Powers'* IDs stay out of everything user-facing. Enforced by `engine/tests/test_oss_readiness.py`. The `Covers:` declarations are the requirement IDs in test docstrings that the `spec_conformance` gate parses.
- **Docs stay current.** Every change and every new feature must be described in `docs/` (or referenced from there) as part of the same unit of work. A change that alters behavior without a matching docs update is incomplete.
