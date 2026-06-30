---
description: "Record a human sign-off into the hash-chained, signed ledger (3PWR-FR-006/037). The approver is a person, not the agent."
handoffs:
  - label: Advance the stage
    agent: 3pwr.advance
    prompt: Advance this feature to the next stage.
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. **Confirm the approver is a person** — not you, the agent, and not merely the prompter acting
   automatically. Ask for their identity if not provided in `$ARGUMENTS`.
2. **Precondition**: the latest verdict must be green (`3pwr verify` passes and `/3pwr.verify` was run).
   If not, stop and send the user back to `/3pwr.verify`.
3. **Record the sign-off** (appended to the signed ledger):

   ```bash
   3pwr signoff --approver "<person>" --stage <stage> --spec-id <SPECID> --note "<what was reviewed>"
   ```

4. Explain that this entry is hash-chained and signed; tampering will be caught by `3pwr verify`.

## Done When

- [ ] A human approver was identified.
- [ ] A `signoff` entry was appended (report the ledger seq).
