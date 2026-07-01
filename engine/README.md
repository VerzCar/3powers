# The `3pwr` engine

This directory is the **3Powers engine** — the Python package (`threepowers`) that provides the `3pwr`
command: the deterministic gate runner, the oracle-independence checks, and the signed trust spine. It is
distributed as a [`uv`](https://docs.astral.sh/uv/) tool.

New to 3Powers? Start with the top-level [README](../README.md) and [docs](../docs/). This file is for
working *on the engine itself*.

## Install & develop

```bash
# Install the CLI from source (from the repo root)
uv tool install ./engine

# Engine dev environment + the checks it must always pass
cd engine
uv sync --extra dev
uv run pytest                 # test suite
uv run ruff check .           # lint
uv run mypy src               # types
```

Python 3.11+ is required. Entry point: `threepowers.cli:main`, exposed as the `3pwr` console script. Every
command and flag is documented in [docs/cli-reference.md](../docs/cli-reference.md).

## Module map

```
src/threepowers/
  Trust spine (High-risk tier — held to ≥95% diff-coverage + mutation):
    canonical.py     # deterministic hashing
    keys.py          # Ed25519 key generation + loading
    ledger.py        # append-only, hash-chained, signed verdict ledger
    verify.py        # offline recompute of the chain + signatures

  Verdict & gate engine:
    verdict.py       # the normalized verdict + canonical gate order
    gates.py         # the cheapest-first gate runner
    adapters.py      # declarative per-language adapter loading/invocation
    conformance.py   # spec-conformance trace (+ defect regression, tier test-layers)
    covdiff.py       # diff-coverage gate
    mutation.py      # mutation-testing gate
    scanners.py      # SAST / dependency / secret scanners
    gaming.py        # gate-gaming detection
    design.py        # design-oracle gates (visual / a11y / contract)
    scope.py         # task requirement-ID + file-scope discipline

  Oracle independence:
    oracle.py        # seal / record / verify / headless dispatch

  Lifecycle, orchestration & feedback:
    lifecycle.py     # per-spec stage, derived from the ledger
    orchestrate.py   # `3pwr run` — the whole-lifecycle loop
    workkind.py      # deterministic work-kind + tier inference
    characterize.py  # brownfield: reconstruct a spec + characterization tests
    deviations.py    # signed, reversible gate exceptions + emergency path
    observe.py       # production signals, NFR coverage, agent-action log
    provenance.py    # build provenance + SBOM signing, deploy gate
    evals.py         # prompt/constitution eval set
    deps.py          # third-party version drift check

  CLI & config:
    cli.py           # argparse command surface (see docs/cli-reference.md)
    config.py        # settings, risk tiers, roles
```

Tests live in `tests/`, with `tests/integration/` and `tests/e2e/` layers alongside the unit tests.

## Mutation testing (the High-risk proof)

The trust-spine modules are held to the strictest tier. Mutation runs via `mutmut`, scoped to those
modules:

```bash
(cd .. && 3pwr gate run --path engine --adapter python \
   --spec specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths engine/src/threepowers/canonical.py engine/src/threepowers/keys.py \
           engine/src/threepowers/ledger.py engine/src/threepowers/verify.py)
```

## Adding a language adapter

The core assumes no language. To add one, write a declarative `adapter.yaml` under
[`../.3powers/adapters/<lang>/`](../.3powers/adapters/) per
[`../.3powers/adapters/CONTRACT.md`](../.3powers/adapters/CONTRACT.md). The TypeScript, Python, and Go
adapters are working references — no changes to this engine should be needed.

## Self-application

The engine gates its own code. Keep it green under its own gates (`ruff` + `mypy` + `pytest`, plus
`3pwr gate run --path engine`), and hold the trust-spine modules to the High-risk bar. See
[CONTRIBUTING.md](../CONTRIBUTING.md) and [docs/STATUS.md](../docs/STATUS.md).
