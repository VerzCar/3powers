---
description: "Brownfield Stage Zero: reconstruct a spec for a legacy module and pin its current behavior with characterization tests serving as its oracle. Never changes the module."
handoffs:
  - label: Verify the characterized module
    agent: 3pwr.verify
    prompt: Run the gate suite for the reconstructed characterization spec.
---

## User Input

```text
$ARGUMENTS
```

## Purpose (3PWR-FR-053, §12)

Bring an un-specified **legacy module** under the judiciary *before* it is changed: reconstruct the
spec it implicitly already satisfies, and lock today's behavior with characterization tests that act
as its oracle. This is the safe on-ramp for gradual adoption (3PWR-FR-051) — you do **not** modify
the module here.

## Steps

1. **Identify the module** to characterize from the user input (a single file path).
2. **Reconstruct the spec + scaffold tests** (static analysis only — the module is *not* executed at
   generation time):

   ```bash
   3pwr characterize --module <path/to/legacy_module> [--specs specs] [--tests <tests-dir>]
   ```

   This writes a minimal spec stub under `specs/<NNN>-<module>-characterization/spec.md` (with a
   reconstructed requirement per public symbol, a Risk Tier, and Non-Goals) and a runnable
   characterization test that references those requirement IDs.
3. **Strengthen the golden masters.** The generated tests pin the public *surface*. For each
   reconstructed requirement, call the symbol with representative inputs and assert its **current**
   return value (a golden master). Do not guess intended behavior — capture what the code does today.
4. **Confirm the loop closes**: spec-conformance must trace every reconstructed requirement to a test:

   ```bash
   3pwr conformance --spec specs/<NNN>-<module>-characterization/spec.md --tests <generated-test>
   ```

## Reporting

- List the reconstructed Spec ID, the requirement IDs, and the files written.
- Note any public symbol whose behavior you could not pin (needs representative inputs) as a TODO,
  not a silent gap.

## Done When

- [ ] A spec stub exists under `specs/` with one reconstructed requirement per public symbol.
- [ ] Characterization tests exist, run green, and reference every reconstructed requirement ID.
- [ ] `3pwr conformance` traces the reconstructed spec with no untested requirement.
- [ ] The legacy module itself is **unchanged**.
