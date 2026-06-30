# `.3powers/` — the in-repo trust spine

Everything 3Powers needs lives here, self-contained in the repository so the whole
record reconstructs **offline** with no external service (3PWR-FR-071, 3PWR-NFR-004/010).

| Path | Committed? | Purpose |
|------|-----------|---------|
| `config/risk-tiers.yaml` | yes | Single source of every gate threshold (3PWR-FR-032/049). |
| `config/roles.yaml` | yes | Role → model-family binding; judicial diversity (3PWR-FR-022/044). |
| `schemas/*.json` | yes | Versioned verdict + ledger-entry schemas (3PWR-NFR-008). |
| `adapters/` | yes | Language-adapter contract + manifests (3PWR-FR-027). |
| `ledger.jsonl` | yes | Append-only, hash-chained, signed verdict ledger (3PWR-FR-038) — the durable record. |
| `keys/ledger.pub` | yes | Public verify key. The **private key lives OUTSIDE the repo** (3PWR-NFR-005). |
| `verdicts/latest.json` | no (gitignored) | Most recent verdict — a convenience cache; the signed copy lives in the ledger. |
| `runs/` | no (gitignored) | Transient run state. |

Verify the spine at any time, offline:

```bash
3pwr verify
```
