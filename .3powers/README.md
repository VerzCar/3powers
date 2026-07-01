# `.3powers/` — the in-repo trust spine

Everything 3Powers needs lives here, self-contained in the repository so the whole
record reconstructs **offline** with no external service.

| Path | Committed? | Purpose |
|------|-----------|---------|
| `config/risk-tiers.yaml` | yes | Single source of every gate threshold. |
| `config/roles.yaml` | yes | Role → model-family binding; judicial diversity (a different model family than the coder). |
| `config/design-oracles.yaml` | yes | The design-oracle catalog for `design`-classified changes. |
| `config/dependencies.yaml` | yes | Supported third-party version ranges for `3pwr deps-check`. |
| `schemas/*.json` | yes | Versioned verdict + ledger-entry schemas. |
| `adapters/` | yes | Language-adapter contract + manifests (TypeScript, Python, Go). |
| `ledger.jsonl` | yes | Append-only, hash-chained, signed verdict ledger — the durable record. |
| `keys/ledger.pub` | yes | Public verify key. The **private key lives OUTSIDE the repo**. |
| `verdicts/latest.json` | no (gitignored) | Most recent verdict — a convenience cache; the signed copy lives in the ledger. |
| `runs/` | no (gitignored) | Transient run state. |

Verify the spine at any time, offline:

```bash
3pwr verify
```
