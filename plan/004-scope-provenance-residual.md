# Plan 004 — Scope Discipline, Build Provenance & Residual Review

**Status**: Implemented & verified. `scope-check`, `provenance`/`deploy-gate`, and `residual` all work;
the deploy gate refuses a tampered artifact; self-application is green at Standard (25 requirements
traced; 72 engine tests; ruff+mypy clean). Builds on plans 001–003. SAST + eval harness → plan 005.

## Context — why

Plan 003 closed most of v0.1. Two v0.1 executive-boundary requirements remain (FR-016 commit/task
requirement-ID tagging, FR-017 task file-scope), and v0.5's first pillars are due: the **build
provenance + deploy gate** (FR-066–068) — which the spec calls first-class — and **automated residual
review** (FR-036/037). The spec stays the source of truth (§9, §6).

## Scope

**In:** `3pwr scope-check` (FR-016/017) · build provenance + SBOM + deploy gate (FR-066–068) ·
residual review command + signed `residual` ledger entry (FR-036/037).

**Out → plan 005:** SAST (semgrep) gate · prompt/constitution eval harness (FR-050) · work-kind
inference (FR-058) · brownfield/observe/emergency paths (v1.0) · the mutmut src-layout runner.

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| **Provenance signing** | Reuse the engine's **own Ed25519 ledger identity** to sign the provenance record — no cosign, no hosted CI | FR-068 mandates "the same independent signer identity used by the verdict ledger"; keeps it offline (NFR-004) and makes the 3Powers run the issuing authority. |
| **SBOM** | Generate a minimal SBOM from lockfiles in-core (`package-lock.json`, `uv.lock`); use **syft** if present for a richer one | Works offline with zero external tools (NFR-004); syft is an optional enrichment. |
| **Deploy gate** | `3pwr deploy-gate` recomputes the artifact hash, finds its provenance, verifies the signature + hash; refuses on any miss | FR-067 — protection lands at verification, not generation. |
| **Scope check** | Parse each task's declared `(files: …)` scope; diff (incl. untracked) must stay within the union of declared scopes | FR-017 — an out-of-scope edit is a signal to stop and re-spec. |
| **Residual** | A `residual` ledger entry (type already exists) recorded by `3pwr residual`; `/3pwr.review` drives it on a different model family | FR-036/037; the human signs off on evidence **and** residual. |

## Workstreams

1. **Scope discipline (FR-016/017).** `3pwr scope-check --spec <s> --tasks <t> [--base <ref>]`:
   - every task carries a requirement ID (FR-016; reuses the tasks parser);
   - each task declares a file scope `(files: a, b)`; the changed set (git diff vs base **+ untracked**)
     must be a subset of the union of declared scopes — any file outside is flagged (FR-017).
   Deterministic; returns a `GateResult`-style result; self-applicable.

2. **Build provenance + SBOM + deploy gate (FR-066–068).** New `provenance.py`:
   - `sbom(target)` — components from lockfiles (or syft if installed);
   - `3pwr provenance --artifact <path>` — record `{schema, artifact{path,sha256}, source_commit,
     repo, built_at, sbom}`, **signed with the ledger Ed25519 key**, written to
     `.3powers/provenance/<sha>.json` + a signed `provenance` ledger entry;
   - `3pwr deploy-gate --artifact <path>` — recompute hash, locate provenance, verify signature + hash;
     refuse (exit 1) if missing/mismatched/invalid.
   Versioned `provenance.schema.json`.

3. **Residual review (FR-036/037).** `.github/{prompts,agents}/3pwr.review.*` — automated residual on a
   **different model family** than the coder, scoped to intent fit / architecture / business-logic /
   security, citing requirement IDs and flagging intent gaps as *new requirements*. `3pwr residual
   --reviewer <id> --note <…> [--spec-id <ID>]` appends a signed `residual` entry. `/3pwr.signoff` then
   covers evidence **and** residual; `/3pwr.review` hands off to `/3pwr.signoff`.

4. **Tests + self-application + docs.** Unit/CLI tests (each citing its FR id, feeding conformance);
   keep `3pwr gate run --path engine` green; add the new FRs to the scoped engine spec; update schemas,
   `AGENTS.md`, `CLAUDE.md`, and this plan. Commit on `plan-004-*`.

## New `3pwr` surface

```
3pwr scope-check --spec <s> --tasks <t> [--base <ref>]   # FR-016/017
3pwr provenance  --artifact <path>                        # signed provenance + SBOM (FR-066/068)
3pwr deploy-gate --artifact <path>                        # verify provenance, refuse if bad (FR-067)
3pwr residual    --reviewer <id> --note <…> [--spec-id]   # signed residual entry (FR-036)
```

## Verification

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)     # engine green
3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md \
              --tier Standard --base 3e20aad --no-ledger                    # self-application green
# provenance round-trip on a built artifact:
python -m build  # or any artifact
3pwr provenance --artifact dist/<wheel>        # signs + records
3pwr deploy-gate --artifact dist/<wheel>       # PASS
# tamper the artifact -> deploy-gate REFUSES (FR-067)
# scope-check: a changed file outside all task scopes -> FAIL (FR-017)
```

## Out of scope (→ plan 005, completing v0.5)

SAST (semgrep) as a core gate; the prompt/constitution **eval harness** (FR-050); then v1.0 (brownfield,
observe, emergency/deviation paths, catalog distribution, third adapter).
