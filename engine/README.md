# `threepowers` — the 3Powers engine (`3pwr`)

The language-agnostic judicial core of [3Powers](../README.md): a cheapest-first
**gate runner**, a deterministic **spec-conformance** trace, an append-only
hash-chained **Ed25519-signed ledger**, and a fully offline **`verify`** — plus a
local `advance` enforcement gate. Layered on GitHub Spec Kit; ships as the `3pwr`
command.

## Install

```bash
uv tool install ./engine        # provides the `3pwr` command
# or, for development:
uv sync --extra dev
```

## Commands

```bash
3pwr keygen                       # create the independent signer (key kept outside the repo)
3pwr gate run --path examples/validation-utils \
              --spec specs/<feature>/spec.md --tier Standard
3pwr conformance --spec <spec.md> --tests <dir>...
3pwr verify                       # recompute chain + signatures, offline
3pwr signoff --approver <you> --stage review
3pwr advance  --stage ship        # refuses unless gate green + ledger verifies + sign-off present
3pwr ledger show
```

See [`.3powers/adapters/CONTRACT.md`](../.3powers/adapters/CONTRACT.md) to add a language.
