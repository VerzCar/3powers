---
description: "Run the deterministic gate suite (cheapest-first) and verify the signed ledger. Surfaces one normalized verdict; never silently fixes failures."
handoffs:
  - label: Record human sign-off
    agent: 3pwr.signoff
    prompt: Record my sign-off for this feature.
---

## User Input

```text
$ARGUMENTS
```

## Steps

1. **Resolve context**: the feature directory under `specs/`, the target project `--path`, and the
   risk tier from the spec's **Risk Tier** field.
2. **Run the gate suite** (cheapest-first → one normalized verdict):

   ```bash
   3pwr gate run --path <target> --spec specs/<feature>/spec.md --tier <tier>
   ```

   This runs format → lint → types → tests (+ diff-coverage) → spec-conformance, writes
   `.3powers/verdicts/latest.json`, and appends a **signed** entry to the ledger.
3. **Verify the ledger** (offline): `3pwr verify`.

## Reporting

- Report the verdict per gate. For any failure, name the **gate**, the **failure class**, and the
  **offending requirement/file** straight from the verdict — do **not** open agent transcripts.
- If a gate is red, **do not weaken it** and **do not silently fix**. If the gap is an
  intent mismatch, recommend filing a new requirement rather than patching code (mirrors residual review).
- If green, hand off to `/3pwr.signoff`.

## Done When

- [ ] `3pwr gate run` produced a verdict and a signed ledger entry.
- [ ] `3pwr verify` passes.
- [ ] Result reported per gate with actionable detail.
