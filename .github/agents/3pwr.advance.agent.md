---
description: "Local, CI-independent enforcement (3PWR-FR-041/042): refuse to advance a stage unless required gates are green, the ledger verifies, and the tier-required human sign-off is present."
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. Run the enforcement gate for the requested stage:

   ```bash
   3pwr advance --stage <stage>
   ```

2. Interpret the result:
   - **Advanced** → report the new ledger seq and the next lifecycle stage.
   - **REFUSED** → relay the exact reasons verbatim and the remediation:
     - *latest verdict is red* → fix the failing gate, re-run `/3pwr.verify` (never weaken the gate).
     - *no human sign-off* / *sign-off predates the latest verdict* → run `/3pwr.signoff`.
     - *ledger fails verification* → the trust record was tampered; investigate before anything else.

## Rules

- Enforcement is **uniform** — there is no fast path for agent-authored or administrator changes
  (3PWR-FR-042). Do not attempt to bypass a refusal.

## Done When

- [ ] `3pwr advance` was run and its outcome (advanced or refused-with-reasons) was reported.
