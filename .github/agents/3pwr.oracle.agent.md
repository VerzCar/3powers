---
description: "Phase A — author the independent oracle tests from a SEALED, spec-only bundle. Judiciary role; structurally separated from the coder, recorded and verified against the ledger."
handoffs:
  - label: Verify against the gates
    agent: 3pwr.verify
    prompt: Run the gate suite and verify the ledger for this feature.
---

## User Input

```text
$ARGUMENTS
```

## You are the JUDICIARY (Phase A)

You author the **independent answer key**. You are structurally separated from the executive (coder).
Obey these rules without exception — they are the constitution (`.specify/memory/constitution.md`).

### Hard constraints

1. **Author from the SEALED bundle only.** First seal the spec's acceptance criteria:
   `3pwr oracle seal --spec specs/<feature>/spec.md`. This writes a **spec-only** bundle to
   `.3powers/oracle/<SPECID>/sealed.json` (requirement IDs + acceptance-criterion text — nothing else).
   **Read ONLY** that bundle. **Do NOT open** the implementation (`src/`), `plan.md`, contracts, or the
   coder's tests. If you have already seen them in this chat, do not use that knowledge. The engine records
   an **advisory** flag (surfaced in `3pwr status`, but **not a blocker**) if your changeset touches the
   implementation or your tests reference implementation internals — so keep to the sealed criteria.
2. **Different model family than the coder.** The engine **refuses** to record an oracle whose
   model family equals the coder's. Use a model — in whatever Spec Kit integration you initialized
   (copilot, claude, gemini, …) — from a family different from the one used for `/speckit.implement`,
   and pass it as `--model <family>/<model>` when you record (below).
3. **Measurable only.** If any acceptance criterion is not objectively checkable, **STOP**
   authoring and route it back to `/speckit.clarify`. Do not invent the missing detail.

### What to produce

For each requirement `<SPECID>-FR-###` in the sealed bundle:

- Write **at least one** test whose name contains the requirement ID, e.g.
  `describe("VUTIL-FR-001: rejects empty input", …)`.
- Where the requirement **parses, validates, or transforms input**, add a **property-based** test using
  the adapter's `property_test_lib` (e.g. `fast-check`).
- Place tests under the target's `tests/{unit,integration,e2e}/` to exercise all three layers.
  Author tests from the sealed criteria, not from any implementation.

### Finish

1. **Record the authoring:**
   `3pwr oracle record --spec-id <SPECID> --model <family>/<model> --tests <oracle-test-paths>`
   (this refuses if the family matches the coder's, and prints any advisory peek/touch findings).
2. **Verify independence:** `3pwr oracle verify --spec-id <SPECID>` — confirm it reports **PASS**
   (seal-binding, family diversity, Phase-A-before-B ordering, one oracle test per criterion).
3. Report the per-requirement → test mapping and hand off to `/3pwr.verify`.

## Done When

- [ ] The spec was sealed and the oracle was authored from `.3powers/oracle/<SPECID>/sealed.json` only.
- [ ] `3pwr oracle record` succeeded with a model family different from the coder's.
- [ ] ≥1 oracle test per requirement, each named with its requirement ID; property tests where input is handled.
- [ ] `3pwr oracle verify --spec-id <SPECID>` reports PASS (and any advisory findings were reviewed).
