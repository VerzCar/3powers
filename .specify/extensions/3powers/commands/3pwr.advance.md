---
description: "Local, CI-independent enforcement — advance a stage only when the gates are green, the ledger verifies, and a human sign-off is present (3PWR-FR-041/042)."
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
tier — oracle independence holds (3PWR-FR-041/042/020/062). An overdue emergency cleanup also blocks it
(3PWR-FR-056). On success it appends a signed `stage_advance` entry.
