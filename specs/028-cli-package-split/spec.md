# Feature Specification: CLI Package Split — cli.py Becomes the threepowers/cli/ Package

**Spec ID**: CLIPKG
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     CLIPKG converts the single ~5,700-line engine/src/threepowers/cli.py into the package
     engine/src/threepowers/cli/ — one module per command group, each owning its cmd_* functions and
     registering its own subparsers via a register(sub, common) hook — as a pure refactor with
     identical behavior, help text, exit codes, and --json payloads, and zero pyproject.toml change.
     Source plan: plan/031 Track D. -->

**Risk Tier**: Standard
<!-- Pure code motion — no behavior change, no trust-spine module touched, no gate altered
     (3PWR-FR-032). Standard rather than Cosmetic because the entry point and the whole command
     surface depend on the moved code, so behavior-identity must hold under test. -->

**Status**: Draft

**Input**: Plan 031, Track D: `cli.py` is ~9× the next-largest module, holds ~45 command functions
plus a monolithic parser assembly, and is the single biggest merge-conflict and review-cost driver
in the repository.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change any behavior: help text, exit codes, `--json` payloads, and subcommand order
  are byte-identical before and after the split.
- Does **not** split any module other than `cli.py` — `runner.py`, `gates.py`, `oracle.py`, and
  `orchestrate.py` are future candidates only.
- Does **not** split `cli/run.py` further; it may remain ~1,900 lines (one coherent domain: the
  lifecycle loop).
- Does **not** edit `engine/pyproject.toml` — the `[project.scripts]` target `threepowers.cli:main`
  resolves to the package unchanged, and the mutation-testing scope stays as-is.

## Requirements *(mandatory)*

### Functional Requirements

- **CLIPKG-FR-001**: `engine/src/threepowers/cli.py` MUST become the package
  `engine/src/threepowers/cli/` with this module map: `__init__.py` (assembly + re-exports),
  `_common.py` (shared helpers and exit codes), `keys.py` (keygen, rotate-key), `bootstrap.py`
  (init, config roles setup, commit-stage), `gate.py` (gate run/config, conformance,
  coverage-check, scope-check, classify), `trust.py` (verify, anchor, signoff, spec diff, advance,
  ledger show, revert), `exceptions.py` (deviation, emergency), `oracle.py` (roles-check, oracle
  seal/record/verify/dispatch), `observe.py` (observe subcommands), `run.py` (run, status, git
  start, abort), `supply.py` (provenance, deploy-gate, residual), `brownfield.py` (characterize,
  eval, deps-check, ready).
- **CLIPKG-FR-002**: Each command module MUST own its `cmd_*` functions and private helpers and
  MUST register its own subparsers via per-command registrar hooks with the `(sub, common)`
  signature (the `_register_*` functions) that bind every leaf subcommand to its handler with
  `set_defaults(func=…)`; help text lives in the module that owns the implementation.
- **CLIPKG-FR-003**: `cli/__init__.py` MUST assemble the parser as a loop over an ordered
  registrar table that fixes the subcommand registration order (the pre-split `3pwr --help`
  command order), so the help output's command order equals the table's order, and MUST
  re-export the public surface (`main`, `build_parser`, the exit-code constants, and every name
  that `engine/tests/` imports from `threepowers.cli`).
- **CLIPKG-FR-004**: The split MUST be a pure refactor presenting one uniform command surface:
  every subcommand resolves to a `cmd_*` handler in its owning module via `set_defaults(func=…)`,
  `--help` composes from the modules' registrars and names every subcommand, the exit-code
  constants keep their documented values (0 ok, 1 fail, 2 usage, 3 paused, 4 setup), `--json`
  payloads are unchanged, and the unmodified test suite passes. (One-time validation: per-command
  `--help` output captured before the split diffed byte-identical after it.)
- **CLIPKG-FR-005**: `cli.py` MUST be deleted in the same commit that lands the package, and
  `engine/pyproject.toml` MUST NOT change (`threepowers.cli:main` keeps resolving).

### Non-Functional Requirements

- **CLIPKG-NFR-001**: The package MUST import cleanly with no circular imports — every submodule
  is importable on its own — and `ruff check`, `mypy src`, and the full pytest suite stay green
  across the new package boundaries; any type looseness mypy newly reveals is fixed minimally,
  not refactored.

## Success Criteria *(mandatory)*

1. `uv tool install --force ./engine && 3pwr --version && 3pwr --help` works with zero
   `pyproject.toml` change.
2. Diffing every captured pre-split `--help` output against the post-split output yields no
   difference.
3. The full engine test suite passes with zero-or-mechanical (import-path-only) test edits.
