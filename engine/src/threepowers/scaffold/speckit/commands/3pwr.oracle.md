---
description: "Phase A judiciary — author the independent oracle from a sealed, spec-only bundle; a different model family than the coder."
model: {{judiciary_model}}
---

## User Input

```text
$ARGUMENTS
```

## Author the oracle (Phase A)

You are the judiciary. Author the answer key from the **spec alone**, using a model from a **different
model family** than the coder. Switch the model in whatever Spec Kit integration you
initialized (copilot, claude, gemini, …) — 3Powers assumes no single provider.

1. `3pwr oracle seal --spec specs/<feature>/spec.md` — write the spec-only bundle you author from
   (`.3powers/oracle/<SPECID>/sealed.json`). Read only that bundle.
2. Author ≥1 test per acceptance criterion, each named with its requirement ID; add a property-based test
   wherever input is parsed/validated/transformed. Route any unmeasurable criterion back
   to `/speckit.clarify`.
3. `3pwr oracle record --spec-id <ID> --model <family>/<model> --tests <paths>` — refused if the family
   matches the coder; records the actual model, signer, and test hashes.
4. `3pwr oracle verify --spec-id <ID>` — confirm **PASS**, then hand off to `/3pwr.verify`.

**If this is a defect fix (work-kind `defect`):** author the **failing regression test first**
— a test named `*regression*`/`*reproduce*` that references the defect's requirement id and *fails before
the fix*. That test is the oracle's acceptance criterion; `/3pwr.verify --work-kind defect` refuses to go
green without it (`missing_regression_test`). Then implement the fix until it passes.

**If this is design work (work-kind `design`):** the code gates alone don't judge it — the
**design oracles** do (visual-regression, accessibility, structural/API contract, component contract).
`/3pwr.verify --work-kind design` runs whichever your language adapter declares and quarantines the rest.

**High-risk (physical read-path isolation):** instead of steps 1–3 by hand, run
`3pwr oracle dispatch --spec-id <ID> --integration <non-coder, e.g. claude>`. It builds a **sanitized git
worktree** (the implementation/plan/tasks/contracts are physically absent), authors the oracle there
headlessly via `specify workflow run` under that integration, and records the seal-bound record **plus** a
signed isolation attestation. One-time setup: `specify integration install claude`. Then
`3pwr oracle verify --spec-id <ID> --require-dispatch`. This is opt-in; the manual model-switch flow above
stays valid for Standard/Cosmetic work.
