# Plan 008 — Structural oracle independence (Phase A/B, ledger-anchored, FR-020/021/022/062)

> **Cold-start note.** Read [`docs/STATUS.md`](../docs/STATUS.md) first (spec-validated state) and
> [`docs/concepts.md`](../docs/concepts.md) for the model. The spec
> [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) is the law. Plans 001–007 delivered v0.1, v0.5, and the
> first part of v1.0 (High-risk self-application, brownfield Stage Zero, emergency & deviation). This plan
> continues v1.0 with the spec's central thesis.

## Context — why this is next

[STATUS §5](../docs/STATUS.md) names **structural oracle independence** as **direction risk #1** — the
clearest remaining gap on the spec's thesis ("tests written by a different mind than the code"). Today the
oracle's independence is only **procedural**: the `/3pwr.oracle` prompt, `roles-check` (refuses same family
from `roles.yaml`), authoring order, and ledger records. Nothing about *which model actually authored the
oracle*, *whether it came before the implementation*, or *whether it was authored from the spec alone* is
proven from the record — a determined coder or agent can peek.

This plan moves oracle independence from *documentary* to **structurally attested, tracked, and enforced**,
entirely at the engine level and self-applicable. It is honest about the residual: **physically preventing
the oracle author from *reading* the implementation (the full letter of FR-021) needs Spec Kit headless
dispatch (A3)**, which is harness-limited in a Copilot-only setting and is deferred to plan 009. Here we
(a) narrow the read path with a spec-only sealed bundle, (b) prove the independence facts from the signed
ledger, and (c) surface — never block on — signals that the author touched the implementation.

**Enforcement shape (deliberate):**
- The **deterministic, ledger-anchored independence facts block `advance`, but only at the High-risk tier**
  (oracle separation *is* High-risk, spec §4). Standard/Cosmetic work is unaffected — no dev slowdown.
- Detecting that the oracle author (human **or any agent**) **read/touched the implementation is ADVISORY:
  flag + comment, never a blocker.** Blocking on a fuzzy, input-dependent signal would both slow development
  and break determinism (NFR-001). It is recorded and surfaced, never added to `advance` reasons.
- **Everything is tracked, traced, and run against the spec:** the ledger records the seal, the authoring,
  the *actual* model used, the signer identity, and any advisory findings.

Two correctness constraints shape the whole approach: (1) oracle independence is a function of *the ledger +
which identity signed what*, not of the code, so it binds at the **`advance` boundary**, never as a blocking
*verdict* gate (that would make the verdict non-deterministic — NFR-001); this mirrors `deviations.py`.
(2) Phase-A-before-Phase-B ordering is proven from the ledger's monotonic signed **`seq`**, *not* git
timestamps (no remote + one-window commits make git time simultaneous and spoofable).

## Scope

**In:**
- **FR-020 — author the oracle from the spec's acceptance criteria only.** `3pwr oracle seal` extracts a
  content-addressed, **spec-only** bundle (requirement IDs + acceptance-criterion text; excludes impl / plan /
  tasks / contracts) to `.3powers/oracle/<spec-id>/sealed.json`, hashed with `canonical.hash_payload`
  (stable across re-seals), and records a signed `oracle` seal entry. The judiciary authors *from the bundle*.
- **FR-062 — Phase A precedes Phase B, coder does not author the oracle.** `3pwr oracle record` captures the
  authoring event (bundle hash authored against, model actually used, oracle test paths + content hashes,
  signer identity). `advance` (High-risk) proves the oracle record's `seq` precedes the implementation
  verdict's `seq`.
- **FR-022 — model-family diversity on the actual model.** `record` refuses when the recorded oracle family
  equals the coder family in `roles.yaml` (strengthens today's config-only check to the *actual* family).
- **FR-023 — one oracle test per acceptance criterion.** `oracle verify` / `advance` reuse the `conformance`
  matcher over the recorded oracle test paths.
- **FR-021 (structural attestation) + advisory peek/touch detection.** The sealed bundle narrows the read
  path; two **advisory, non-blocking** signals flag likely peeking for human/agent review: (a) the author's
  changeset also modified implementation files; (b) oracle tests reference implementation-internal symbols
  absent from the sealed spec.
- Wire the deterministic check into `advance` **High-risk only**; surface advisory findings in `status` and
  `oracle verify`.

**Out (→ plan 009+):** the **distinct/enforced oracle signer key** (a second Ed25519 identity + `verify.py`
key routing — NFR-005 custody surface); **true structural read-path isolation via Spec Kit headless dispatch
(A3)** — the physical FR-021; machine-enforcement of **FR-024** (property tests) and **FR-025** (route
unmeasurable criteria back to clarify) — these stay prompt-level; observe/feedback (§13, FR-054/055);
catalog distribution (A1) + a third adapter.

## Decisions (proposed — revisit if you find better)

| Area | Proposal | Rationale |
|---|---|---|
| **Where the check binds** | At the **`advance` boundary**, High-risk only — never a blocking verdict gate; advisory findings never enter `advance` reasons. | Independence is `f(ledger + signer)`, not `f(code)`; a verdict gate would be non-deterministic (NFR-001). Oracle separation is High-risk per §4, so lower tiers are unaffected. |
| **Ordering proof** | From the ledger's monotonic signed **`seq`** (oracle record before the impl verdict), not git time. | No remote + one-window commits make git timestamps simultaneous/spoofable; `seq` is signed and append-only. |
| **Sealed bundle** | Spec-only (req ids + criterion text), repo-relative `source`, sorted ids; `bundle_hash` excludes the timestamp so **re-seal → identical hash**. Lives under `.3powers/`. | Deterministic binding (FR-020); self-contained & offline-reconstructable (FR-069/071). |
| **Peek/touch detection** | **Advisory** `advisory_findings` on the record + printed by `verify`/`status` with a "⚑ advisory (not a blocker)" marker; human **or** agent authors. | User steer: flag + comment, never block, to avoid slowing development; the signal is heuristic/input-dependent, unfit for a deterministic gate. |
| **Diversity source** | Check the **recorded** `model_family` against `roles.yaml`'s coder family, refusing at `record` time. | FR-022 becomes structural, not just declared intent. |
| **Oracle signer identity** | Record the `signer_key_id` the ledger already stamps; do **not** ship a separate key yet. | Non-authorship is already attributable; a second key adds NFR-005 custody surface and only pays off once A3 isolates dispatch (plan 009). |

## Workstreams

1. **`oracle.py` module + `oracle` ledger type.** `extract_criteria(spec)` (reuse `conformance.extract_spec`
   + `_iter_req_ids`); `bundle_hash` / `build_bundle` / `seal_payload` (stable hash); `family_of` /
   `coder_family` / `record_payload`; ledger-derived `active_seal` / `authoring_record`; `independence(entries,
   roles, spec_id, repo_root, test_roots) -> Independence(ok, reasons, advisory, covered, ...)` checking
   **seal-binding** (FR-020/021), **diversity** (FR-022), **ordering** by `seq` (FR-062), **coverage** via
   `conformance.referenced_ids` (FR-023). Pure advisory scanners `scan_touched_impl(changed, oracle_paths)`
   and `scan_symbol_leakage(test_texts, criteria_text)` (modelled on `gaming.py`). Add `"oracle"` to
   `ledger.ENTRY_TYPES`.
2. **CLI.** `cmd_oracle_seal` (writes the bundle + signed seal entry), `cmd_oracle_record` (refuses on family
   collision — FR-022; records model + test hashes + advisory), `cmd_oracle_verify` (runs `independence`,
   prints structural pass/fail **and** advisory, exit on the *structural* result). Register an `oracle`
   subparser with a `seal|record|verify` group (like `gate run` / `ledger show`).
3. **Enforce at `advance` (High-risk only) + surface in `status`.** `cmd_advance` reads the spec's tier from
   the latest enforced verdict; iff High-risk, requires `oracle.independence(...)` and adds structural
   failures to `reasons` (records `oracle_ok`). Advisory findings are **never** in `reasons`. `cmd_status`
   lists oracle records + advisory findings under a "⚑ advisory (not a blocker)" marker.
4. **Rewrite `/3pwr.oracle` prompt.** Author **only** from the sealed bundle, name each test with its req id
   (FR-023), add a property test where input is parsed/validated/transformed (FR-024), refuse and route any
   unmeasurable criterion back to `/speckit.clarify` (FR-025), then run `3pwr oracle record`.
5. **Tests (per-FR) + self-application + docs.** `test_oracle.py`: bundle-hash stability; seal-binding;
   diversity refusal (FR-022); ordering — record-after-verdict fails, before passes (FR-062); coverage
   (FR-023); advisory recorded but High-risk `advance` still proceeds; Standard advance unaffected. Keep the
   engine green (ruff/mypy/pytest) and High-risk self-application green; **do not** add `oracle.py` to the
   mutation `--paths` set. Add FR-020/021/024/025/062/063 acceptance to `specs/002-engine-trust-spine/spec.md`;
   flip `docs/STATUS.md`; update `CLAUDE.md`, `AGENTS.md`, the CLI reference.

## New `3pwr` surface (proposed)

```
3pwr oracle seal   --spec specs/<feature>/spec.md [--spec-id <ID>]                 # FR-020
3pwr oracle record --spec-id <ID> --model <family/model> --tests <paths>... [--base <ref>]  # FR-022/062
3pwr oracle verify --spec-id <ID> [--tests <roots>...]                             # structural + advisory
3pwr advance --stage <s> --spec-id <ID>   # at High-risk: refuses unless oracle independence holds
3pwr status                                # also lists oracle records + ⚑ advisory peek/touch findings
```

## Verification (definition of done)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)     # engine green (new oracle tests pass)

# High-risk self-application stays green (NFR-006):
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)
```
Done when: `oracle seal/record/verify` work and are ledgered; a High-risk `advance` blocks on any broken
structural independence fact (seal-binding, diversity, ordering, coverage) and proceeds when they hold;
peek/touch detection is recorded and surfaced but **never blocks**; a Standard-tier `advance` is unchanged;
the engine self-applies green; and `docs/STATUS.md` flips FR-020/062 to ✅ (FR-022 strengthened, FR-021 noted
as structural attestation with the physical read-path prevention deferred to A3/plan 009).

## How to work here

- **The spec is the law.** Validate against `3Powers_Spec_v0.2.md` §6–§7; respect §17 phasing (this is v1.0).
  Do **not** over-claim FR-021 — physical read-path prevention is deferred to A3/plan 009.
- **Determinism first (NFR-001).** The oracle check binds at `advance`, never in the verdict; ordering is from
  ledger `seq`, not git time; the sealed-bundle hash is stable across re-seals.
- **No inline gate suppressions** in the engine — `gate_gaming` will flag them; fix the underlying issue.
- Each new test references the FR id it exercises; add implemented requirements to `specs/002-*/spec.md`.
- Commit on the `plan-008-oracle-independence` branch.
