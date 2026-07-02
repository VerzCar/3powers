# Plan 018 — Open-source launch readiness (OSSRD): honest docs, prerequisites, CI & de-duplication

> **Cold start:** the governing spec is [`specs/006-oss-readiness/spec.md`](../specs/006-oss-readiness/spec.md)
> (Spec ID `OSSRD`, tier **Standard**); the task breakdown is
> [`specs/006-oss-readiness/tasks.md`](../specs/006-oss-readiness/tasks.md). This plan changes **no engine
> behavior, gate, threshold, or trust-spine mechanism** — the deterministic findings from the same external
> review landed as HARDN ([plan 017](017-trust-hardening.md)). This is the documentation-and-repo-hygiene
> half: what the project *says* must match what [`docs/STATUS.md`](../docs/STATUS.md) validates.

## Context

An external open-source-readiness audit (2026-07-02) found the repo not yet safe to announce: the README
claimed more than STATUS validates ("authored headlessly in a sanitized workspace" without the
oracle-leg-only qualifier; "everything in between runs unattended" hiding the Spec Kit + coding-agent
dependency), the Spec Kit pin looked like a private fork to a newcomer, a project selling merge-blocking
gates had no CI on its own pull requests, prerequisites were undifferentiated, insider jargon ("trust
spine", "Phase A/B", "A3", "residual") appeared before any definition — "A3" was defined nowhere
user-facing — and implementation status was quadruplicated across README/AGENTS/CLAUDE/STATUS, guaranteed
to drift.

## Scope — in (delivered)

- **Honesty calibration (OSSRD-FR-001, NFR-001).** The README scopes the sanitized-headless claim to the
  **oracle leg** and names the autonomous path's dependencies (upstream Spec Kit CLI + a coding-agent
  integration) before the first `3pwr run`. A Mermaid lifecycle diagram shows the eight stages with
  exactly the two amber human gates; its caption carries the same qualification. The honesty invariant is
  now a **repeatable check**: `engine/tests/test_oss_readiness.py` fails on the audited unqualified
  claims, from the repo alone.
- **Pin sourcing (OSSRD-FR-002).** README, AGENTS.md, and getting-started each source the pin to upstream
  [`github/spec-kit`](https://github.com/github/spec-kit) and link the tagged-install command in
  [`docs/references/speckit.md`](../docs/references/speckit.md) — the "is this a fork?" question is
  answerable from every entry document.
- **Tiered prerequisites (OSSRD-FR-003).** Getting-started opens, before any install command, with hard
  requirements (`uv`, `git`), conditional requirements per path (autonomous vs slash-command vs
  gates-only — the gates-only path needs no Spec Kit and no agent integration), and the optional scanners
  each naming their quarantine behavior.
- **CI on this repo's own PRs (OSSRD-FR-004, NFR-002).** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)
  runs `ruff check` / `mypy src` / `pytest` / offline `3pwr verify` on every pull request to `main` (and
  pushes to `main`), inside `timeout-minutes: 10` with a locked `uv sync`. CONTRIBUTING documents the
  identical local commands. Framework stance unchanged: CI re-validates *this repo's contributions*; it is
  never the source of trust (A4, 3PWR-NFR-004). The keyless runner passes the custody preflight by
  construction (HARDN-FR-002).
- **Glossary + troubleshooting (OSSRD-FR-005/010).** [`docs/glossary.md`](../docs/glossary.md) defines
  trust spine, oracle, Phase A/B, residual, the **A1–A6 assumptions** (finally giving "A3" a user-facing
  definition), verdict, quarantine, work kind, and the requirement-ID scheme; entry docs link it at first
  use. [`docs/troubleshooting.md`](../docs/troubleshooting.md) covers signing-key-not-found, Spec Kit
  version mismatch, quarantined gates, and `specify`-missing-for-`3pwr run` — symptom / cause / exact
  resolving command each.
- **Status has one home (OSSRD-FR-006).** `docs/STATUS.md` opens with a one-screen executive summary
  (milestone, validation date, open residuals) and is the *only* file carrying per-plan status; README,
  AGENTS.md, and CLAUDE.md now hold durable summaries plus a link — a status change edits one file.
- **Canonical gate naming (OSSRD-FR-007).** One spelling per gate across the user-facing docs, matching
  `GATE_ORDER` in `verdict.py` (underscores); the README gate list defers to
  [Engine Architecture](../docs/engine-architecture.md) for the work-kind-shaped set; the docs test greps
  entry docs against the canonical list, so a regression fails the suite.
- **Honest install story + release linkage (OSSRD-FR-008/011).** No "coming soon from PyPI";
  clone-and-install is the quickstart's first command. CHANGELOG references the `v0.5.0` tag matching its
  latest released milestone, and the README status section names the same milestone.
- **Contributor clarity (OSSRD-FR-009).** CONTRIBUTING states the platform policy (tested on macOS; Linux
  best-effort — CI runs on Linux; Windows unsupported → WSL2); GOVERNANCE already documented the
  maintainer path (verified, unchanged).
- **Entry-document brevity (OSSRD-NFR-003).** The README stays ≤120 prose/table lines (excluding badges,
  fenced blocks, license footer) — enforced by test; the full per-language tooling matrix moved to
  getting-started, with a compact language/status table remaining in the README.

## Decisions

| Area | Decision |
|---|---|
| ONBRD-FR-013 (full language table in README) vs OSSRD-NFR-003 (reference tables in docs/) | **Compact table in README + full matrix in docs** — the ONBRD docs test now checks the split; self-qualification (incl. the Next.js answer) still works from the README alone |
| Gate-name canon | The **verdict's identifiers** (underscores), per OSSRD-FR-007's own acceptance; feature names like "spec-lock" stay prose |
| FR-007 enforcement scope | The automated check greps the **entry docs + AGENTS + CLAUDE** (per the spec's acceptance); the wider doc set was fixed in the same pass, but sealed specs and the immutable plan series keep their historical spellings |
| CI triggers | `pull_request` → `main` **and** `push` → `main` (catches direct pushes; keeps the badge meaningful) |
| Required-check wiring | Branch protection is a GitHub setting, not a repo file — a **maintainer step** after merge: mark the `engine` job as a required check |
| Release tag | **`v0.5.0`** on `main` after merge (matches the CHANGELOG's latest released milestone) — a maintainer step; the docs test verifies the documented linkage |
| NFR-001 mechanization limit | Claim-by-claim README-vs-STATUS reading cannot be fully automated; the test suite pins the audited overclaims and structure, and the remainder is the human review this spec's sign-off records |

## What landed (files)

- **New:** `docs/glossary.md`, `docs/troubleshooting.md`, `.github/workflows/ci.yml`,
  `engine/tests/test_oss_readiness.py`, `specs/006-oss-readiness/tasks.md`, this plan.
- **Restructured:** `README.md` (honesty, diagram, brevity, compact table), `docs/getting-started.md`
  (prerequisites, matrix), `docs/STATUS.md` (executive summary), `AGENTS.md` + `CLAUDE.md` (status
  de-dup), `CONTRIBUTING.md` (CI commands, platform policy), `CHANGELOG.md` (tag links, OSSRD entry).
- **Naming pass:** `docs/concepts.md`, `docs/engine-architecture.md`, `docs/cli-reference.md`,
  `docs/brownfield.md`, `docs/README.md`, `engine/README.md`,
  `engine/tests/test_docs_onboarding.py` (ONBRD-FR-013 split).

## Verification (as run)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # all green; 26 OSSRD/ONBRD docs tests
3pwr coverage-check --spec specs/006-oss-readiness/spec.md --tasks specs/006-oss-readiness/tasks.md
3pwr scope-check --tasks specs/006-oss-readiness/tasks.md --base feat/trust-hardening
3pwr gate run --path engine --adapter python --spec specs/006-oss-readiness/spec.md \
              --tier Standard --base feat/trust-hardening
3pwr verify
```

Residuals: the live CI run under 10 minutes is confirmed on the first real pull request (OSSRD-NFR-002);
the `v0.5.0` tag and the required-check branch protection are maintainer steps after merge
(OSSRD-FR-011/004).
