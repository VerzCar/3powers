# Plan 014 — hardening core: betterleaks, work-kind inference, tier test-layers, richer TUI, LICENSE

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md), then the spec
> [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) §4 (tiers), §5 (FR-058), §8 (FR-064/065), NFR-012.

## Context

The core of "the missing rest" after plans 001–013. Delivered here; FR-008 (defect-flow), FR-009 (design
oracles), and a third (Go) adapter build on work-kind and are **deferred to plan 015**; the genuinely
external residuals (fuller-A3 dual-headless, catalog publishing, cross-platform CI) stay documented.

## What shipped

- **Pluggable secret scanner — betterleaks default, gitleaks fallback** (`scanners.py`). betterleaks is the
  maintained Gitleaks successor (v1.6.1); confirmed live that its `dir` CLI + JSON schema are identical to
  gitleaks (`File/RuleID/StartLine`), differing only in the empty-report form (`null` vs `[]`, handled). The
  gate uses whichever binary is on PATH — betterleaks first — records which ran (`tool=`), and quarantines
  if neither (3PWR-NFR-015). `dependencies.yaml` gains a `betterleaks` component (kept gitleaks).
- **Work-kind inference (3PWR-FR-058)** — `workkind.py::classify(intent)` deterministically infers
  kind(s) `⊆ {defect,feature,design,refactor,chore,docs}` + a `suggested_tier` (auth/payment/checkout/…
  → High-risk; docs/chore-only → Cosmetic; else Standard). `3pwr classify "<intent>"` surfaces it; `3pwr run`
  records `inferred_kinds` + `suggested_tier` in the ledger and shows them in the header. It shapes the tier
  (→ the applicable gate set) but **never** bypasses the human sign-off (FR-006). Deterministic → no
  NFR-001 risk. Per-kind gate shaping (defect/design) is plan 015.
- **FR-064 tier-required test layers** — `required_layers` per tier in `risk-tiers.yaml`
  (`Cosmetic: []`, `Standard: [unit]`, `High-risk: [unit, integration, e2e]`). `run_conformance` enforces it
  as a **per-change union**: the change's tests must cover the tier's required layers (not every requirement
  in every layer). The engine dogfoods it — new `tests/integration/` + `tests/e2e/` tests give its own
  High-risk self-application all three layers.
- **Richer TUI progress** for `3pwr run` — a dependency-free `Tracker` that redraws the stage line in place
  on a TTY (ANSI `\r` + clear) and falls back to plain streamed lines off a TTY / under `--json`. No new
  runtime dependency (NFR-014).
- **Root `LICENSE`** (Apache-2.0) — closes NFR-012.

## Decisions

| Area | Decision |
|---|---|
| Secret scanner | One command + parser for both (they're CLI/schema-identical); prefer betterleaks, fall back to gitleaks; handle betterleaks' `null` empty report; record `tool=`. |
| Work-kind | Deterministic keyword classifier; shapes the tier (hence gates) + records a signal for the oracle; never the sign-off. |
| FR-064 | Per-change **union** enforcement (the sensible reading of "all three layers for a change"); only the repo's real tier config sets `required_layers`, so existing fake-project tests (own inline tiers) are unaffected. |
| TUI | Dependency-free ANSI in-place tracker; plain fallback. |

## Verification (as-run)

- `brew install betterleaks` (1.6.1); `betterleaks dir … --report-format json --report-path …` confirmed
  (identical schema to gitleaks; empty = `null`).
- `ruff` + `mypy` clean; **231 tests** pass (new: scanner registry + null handling, `test_workkind.py`,
  `test_conformance_layers.py`, tracker tests, + the integration/e2e dogfood tests).
- **High-risk self-application PASS** — all 11 gates, with `secret_scan · betterleaks` running live and
  `spec_conformance` satisfying `required_layers` (39 requirements traced), mutation + 100% diff-coverage,
  gate_gaming clean.
- `3pwr classify "fix the null-pointer bug in checkout"` → defect / High-risk; `"update the README
  documentation"` → docs / Cosmetic. `3pwr deps-check` shows betterleaks 1.6.1 ✓ + gitleaks 8.30.1 ✓.

## Residual (→ plan 015 / external)
- **Plan 015:** FR-008 defect→regression-test flow + FR-009 design oracles (both consume work-kind to shape
  gates) + a third (Go) reference adapter.
- **External-only:** fuller-A3 dual-headless (codex/gemini), catalog publishing (registry), cross-platform CI,
  model-driven eval (FR-050). Also: fuller test-layer labelling of the existing engine suite (only the
  dogfood markers are added here).
