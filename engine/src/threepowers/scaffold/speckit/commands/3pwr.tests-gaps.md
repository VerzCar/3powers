---
description: "Read-only judiciary dry-run — list spec requirements with no linked test, mirroring the spec_conformance gate (INITX-FR-007). Safe to run in CI; changes nothing."
model: {{judiciary_model}}
handoffs:
  - label: Author the oracle
    agent: 3pwr.oracle
    prompt: Author the independent oracle for the requirements that have no linked test.
    send: false
  - label: Implement
    agent: speckit.implement
    prompt: Start implementation now that every requirement has a linked test.
    send: false
---

## User Input

```text
$ARGUMENTS
```

## Judiciary dry-run (test gaps)

This mirrors the deterministic `spec_conformance` gate, read-only. Run it before implementation to
confirm every requirement in the spec has at least one linked test (3PWR-FR-030 / INITX-FR-007).

Run:

```bash
3pwr conformance --spec specs/<feature>/spec.md
```

- It **names every requirement id with no linked test** and exits non-zero when any gap remains.
- On full coverage it exits zero.
- It reads the spec + tests and writes nothing — safe to run in CI.

If it reports gaps, hand off to `/3pwr.oracle` to author the missing oracle tests (Phase A, on a model
family different from the coder), then re-run this check. Do **not** proceed to `/speckit.implement`
while critical (High-risk) requirements are untested.

## Done When

- [ ] `3pwr conformance` reports PASS (no requirement without a linked test), or the remaining gaps are
      explicitly accepted for a lower tier.
