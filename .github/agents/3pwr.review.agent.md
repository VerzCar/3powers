---
description: "Automated residual review on a different model family than the coder — scoped to what the deterministic gates cannot catch. Records a signed residual entry."
handoffs:
  - label: Record human sign-off
    agent: 3pwr.signoff
    prompt: Record my sign-off on the evidence and the residual for this feature.
---

## User Input

```text
$ARGUMENTS
```

## When to run

Only **after the deterministic gates are green** (`/3pwr.verify` passed). The residual review judges
what the gates structurally cannot.

## Constraints

- **Different model family than the coder.** Run
  `3pwr roles-check --role-a reviewer --role-b coder`; if it reports VIOLATION, switch the model (in
  whatever Spec Kit integration you initialized) to a family different from the one that implemented the
  change, then continue.

## What to review (cite requirement IDs)

Scope the review to what gates miss:

1. **Intent fit** — does the change actually satisfy the spec's intent, not just its literal tests?
2. **Architecture** — boundaries, coupling, and whether the design will hold.
3. **Subtle business-logic errors** the tests did not encode.
4. **Security design** — authz, input trust, secret handling, unsafe defaults.

For each finding, cite the requirement ID. **Flag any intent gap as a *new requirement*** routed back to
`/speckit.specify` — not as a quiet code fix.

## Record it

Append a signed residual entry to the ledger:

```bash
3pwr residual --reviewer "<model-family/id>" --spec-id <SPECID> \
              --note "<summary>" --findings "<id: finding>" "<id: finding>"
```

Then hand off to `/3pwr.signoff` — the human approver signs off on the **evidence and the residual**
together.

## Done When

- [ ] Reviewer model family confirmed different from the coder.
- [ ] Findings recorded (or "no residual findings"), each citing a requirement ID; intent gaps filed as new requirements.
- [ ] A signed `residual` entry is in the ledger.
