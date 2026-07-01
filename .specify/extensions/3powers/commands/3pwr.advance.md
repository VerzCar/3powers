---
description: "Local, CI-independent enforcement — advance a stage only when the gates are green, the ledger verifies, and a human sign-off is present."
---

## User Input

```text
$ARGUMENTS
```

## Enforce + advance

Trust is recovered **locally**, with no CI/CD platform as the enforcer:

```bash
3pwr advance --stage <stage> --spec-id <SPECID>
```

`advance` refuses unless the ledger verifies, the latest *enforced* verdict is green (or a signed
deviation covers each red gate), a human sign-off exists at/after that verdict, and — at the **High-risk**
tier — oracle independence holds. An overdue emergency cleanup also blocks it. On success it appends a
signed `stage_advance` entry.
