---
name: Bug report
about: Report something that isn't working as intended
title: "[bug] "
labels: bug
---

## What happened

A clear description of the bug.

## Expected behavior

What you expected to happen instead.

## Steps to reproduce

1. …
2. …
3. …

If it involves a gate verdict, please paste the relevant `3pwr` output (add `--json` for the
machine-readable form). Redact anything sensitive.

```
<verdict / error output>
```

## Environment

- 3Powers version / commit: <e.g. `3pwr --version`, or the commit SHA>
- OS:
- Python / `uv` version:
- Language adapter involved (if any): <typescript | python | go | other>
- Optional tools present (if relevant): <betterleaks/gitleaks, osv-scanner, semgrep, …>

## Anything else

Logs, screenshots, or context that might help. If you suspect a **security** issue, please do **not** file
a public issue — see [SECURITY.md](../../SECURITY.md).
