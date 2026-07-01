---
description: "Run the 3Powers deterministic gate suite and verify the signed verdict ledger for the active feature (3PWR-FR-026/040)."
---

## User Input

```text
$ARGUMENTS
```

## Verify against the gates (judiciary)

Run the 3Powers engine — provider-agnostic, no direct model calls (3PWR-A3):

1. `3pwr gate run --spec specs/<feature>/spec.md --tier <tier>` — the deterministic suite cheapest-first
   (format → lint → types → tests + diff-coverage → mutation → SAST → dependency → secret → gate-gaming →
   spec-conformance), emitting one normalized verdict and a signed ledger entry (3PWR-FR-026/033).
2. `3pwr verify` — recompute the ledger hash chain + signatures offline; fails on any tamper, gap, or
   break (3PWR-FR-040).

Report the failing gate(s) with the offending item, then hand off to `/3pwr.review` (or `/3pwr.signoff`
once green).
