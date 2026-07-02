# Plan 016 — spec-integrity gate (spec-lock, SLOCK): the approved spec cannot silently mutate

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md) and the governing feature spec
> [`specs/004-spec-integrity/spec.md`](../specs/004-spec-integrity/spec.md) (Spec ID `SLOCK`,
> **High-risk**). Epic context: [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) — the spec is
> the law (3PWR-FR-010), the human approves it (3PWR-FR-006), and the ledger is the trust spine (§9).
> Use `uv run python -m threepowers.cli` for the CLI — the globally installed `3pwr` alias may be stale.

## Context

Through plan 015 the spec was *not* protected against modification after a human approved it:
`signoff --stage spec` recorded only `{approver, stage, note}` — no fingerprint of the approved
document — and neither `gate run` nor `advance` ever re-read the spec. An agent could alter, add, or
delete requirements during Build → Ship and nothing would detect it. The only existing spec-level
fingerprint (`oracle seal`'s criteria-slice `bundle_hash`) is High-risk-only and checked solely in the
oracle-independence flow.

Plan 016 closes that hole with **no new trust primitive and no new ledger entry kind**: the full
document's raw-bytes SHA-256 is sealed *inside the signed `signoff` entry* at the approval moment, and
enforced thereafter — at all tiers — by a new cheapest-first `spec_integrity` gate and by `advance`.

## Scope

**In (delivered):**
1. **Seal at sign-off (SLOCK-FR-001)** — a Spec-stage sign-off (manual `3pwr signoff --stage spec
   [--spec …]` *and* the `3pwr run` review-spec gate) records `spec_hash` (raw-bytes SHA-256),
   a root-relative `spec_path`, and the sign-off `commit` (when in git) in the signed payload.
2. **Ledger-only approval query (SLOCK-FR-002)** — `speclock.spec_approval(entries, spec_id)`:
   latest Spec-stage sign-off carrying a `spec_hash`; later wins; no file I/O.
3. **The `spec_integrity` gate (SLOCK-FR-003/004)** — after `types`, before `tests` in
   `GATE_ORDER` and in every tier's gate list (all three tiers); fails with class `spec_modified`
   naming the approving seq; skips (never blocks) a never-approved spec, in O(1) (SLOCK-NFR-003).
4. **`advance` enforcement (SLOCK-FR-005)** — re-executes the check from the recorded path; refuses
   `spec_modified` unless an active, signed `spec_integrity` deviation covers it (3PWR-FR-057);
   revoke/expiry re-blocks; the applied deviation seq is recorded in the `stage_advance` payload.
5. **Supersede (SLOCK-FR-006)** — a fresh Spec-stage sign-off over the amended document is the
   sanctioned way back; gate and advance then judge against the new hash.
6. **`3pwr spec diff` (SLOCK-FR-007)** — read-only: exit 0 on match, non-zero + both hashes +
   approving seq/approver on mismatch, with a `git show <signoff-commit>:<path>` unified diff when
   the commit is known. Never writes to the ledger.
7. **Tamper-evidence for free (SLOCK-NFR-002)** — the hash lives inside the signed entry, so `verify`
   catches tampering with zero new verification code (proven by test).

**Out (per the spec's non-goals):** protecting the spec *before* first sign-off; preventing legitimate
amendment; whitespace normalization; any change to `oracle seal`/`verify`; a new ledger entry kind; CI/CD.

## Decisions

| Area | Decision | Why |
|---|---|---|
| Where the hash lives | Inside the existing signed `signoff` payload | Reuses the ledger's signature — tamper-evident with no new primitive (SLOCK-NFR-002) |
| Hashing | Raw file bytes, `canonical.sha256_hex` | Byte-for-byte per the non-goals; deterministic (SLOCK-NFR-001) |
| Module | New `engine/src/threepowers/speclock.py`, pure (no subprocess/network) | One shared implementation for gate + advance + diff; added to the High-risk mutation scope (`[tool.mutmut] only_mutate`) |
| Gate placement | `GATE_ORDER` index 3 — after `types`, before `tests`; enabled at **all** tiers | Fail-fast (SLOCK-FR-004); the spec's motivation says "at all tiers" |
| Stage matching | Case-insensitive (`spec`/`Spec`) | The CLI uses lowercase, the orchestration gate `"Spec"` |
| Old sign-offs | Entries without `spec_hash` = no approval → gate skips | Backward compatible; pre-approval authoring is never blocked (SLOCK-FR-003) |
| `advance` relief | Named-gate deviation `--gate spec_integrity` (validated automatically via `GATE_ORDER`) | The §14 sanctioned path (3PWR-FR-057); reversible via `--revoke` |
| Textual diff | Record the sign-off commit in the payload; `spec diff` falls back to `git show` + difflib | "When the sign-off commit is known" (SLOCK-FR-007); best-effort, never blocking |

## What landed (files)

- `engine/src/threepowers/speclock.py` — new: `spec_file_hash`, `approval_fields`, `spec_approval`,
  `check`, `integrity_gate` (trust-spine bar; in the mutmut High-risk scope).
- `engine/src/threepowers/verdict.py` — `spec_integrity` in `GATE_ORDER` (after `types`).
- `engine/src/threepowers/gates.py` — core-gate branch + `spec_modified` failure mapping.
- `engine/src/threepowers/cli.py` — sign-off sealing (manual + orchestration), `advance` check 5
  (+ deviation relief), the `spec diff` command group, `--spec` on `signoff`.
- `.3powers/config/risk-tiers.yaml` + scaffold copy — gate in all three tiers' lists.
- `.3powers/schemas/verdict.schema.json` — gate enum.
- `engine/pyproject.toml` — `speclock.py` in `[tool.mutmut] only_mutate`.
- Tests: `engine/tests/test_speclock.py` (unit), `tests/integration/test_speclock_integration.py`,
  `tests/e2e/test_speclock_e2e.py` — every SLOCK FR/NFR referenced across the three layers
  (3PWR-FR-064); `specs/004-spec-integrity/tasks.md` (two-way coverage green).

## Verification (as run)

- `uv run pytest` — 311 passed; `ruff check` + `ruff format --check` + `mypy src` clean.
- Self-application at **High-risk**, scoped to the capability (spec §4):
  `gate run --path . --adapter python --spec ../specs/004-spec-integrity/spec.md --tier High-risk
  --mutation --no-ledger --paths src/threepowers/speclock.py` → **pass**
  (diff-coverage **97.18% ≥ 95**, mutation **79.56% ≥ 70**, conformance layers unit+integration+e2e
  for every SLOCK requirement).
- SC-001…SC-006 each proven by a named test (see `tests/integration/test_speclock_integration.py`
  and `tests/e2e/test_speclock_e2e.py`); SLOCK-NFR-002 shown with *no new verification code*.

## Residual

- The engine's *own* epic specs are not yet sealed — run `3pwr signoff --stage spec --spec …` on them
  once this merges (SC-006 is proven by test; sealing the live repo specs is an operational step).
- `spec diff`'s textual view needs the sign-off commit; sign-offs made outside git show hashes only.
