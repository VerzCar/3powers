# Feature Specification: Open-Source Launch Readiness — Honest Docs, Prerequisites, CI & De-duplication

**Spec ID**: OSSRD

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: most work is documentation (Cosmetic-class by §4 cli_docs), but the spec also adds the
     repository's first CI workflow and release tagging — shared-infrastructure changes that gate
     contributions — so the higher applicable tier (Standard) governs, per the ONBRD precedent. -->

**Status**: Draft

**Input**: External open-source-readiness audit (2026-07-02). Findings: **(1)** `README.md` overclaims
relative to `docs/STATUS.md` — "authored headlessly in a sanitized workspace" holds for the oracle leg
only, and "everything in between runs unattended" hides that `3pwr run` depends entirely on the external
Spec Kit CLI plus a coding-agent integration. **(2)** The Spec Kit pin `0.11.6.dev0` is unsourced in the
entry docs — only `docs/references/speckit.md` reveals it is upstream `github/spec-kit` installed from a
git tag, so a newcomer assumes a private fork and stalls. **(3)** The repository has no `.github/workflows/`
— a project selling merge-blocking gates does not gate its own pull requests. **(4)** Prerequisites are
buried: hard (uv, git), conditional (Spec Kit + a coding-agent integration for the autonomous path),
optional (betterleaks/gitleaks, osv-scanner, semgrep — quarantining gates) are not distinguished up front.
**(5)** Insider jargon ("trust spine", "Phase A/B", "A3", "residual", bare requirement IDs) appears in
entry documents before any definition; "A3" is defined nowhere user-facing. **(6)** Implementation status
is duplicated across `README.md`, `AGENTS.md`, `CLAUDE.md`, and `docs/STATUS.md` and will drift. **(7)**
Assorted polish gaps: gate-name inconsistency (`spec_conformance` vs `spec-conformance`), README gate list
(10) vs architecture doc (16), "Coming soon from PyPI" without a path, single-maintainer governance with no
path to becoming a maintainer, no troubleshooting entry, macOS-only testing unstated, no tagged release.

---

## Non-Goals *(mandatory)*

- Does **not** change engine behavior, any gate, threshold, or trust-spine mechanism — the deterministic
  trust-hardening findings from the same review live in the HARDN spec
  ([`specs/005-trust-hardening/spec.md`](../005-trust-hardening/spec.md)), not here.
- Does **not** make CI/CD a required part of the 3Powers framework for its *users* — local, offline
  enforcement remains the product stance (3PWR-NFR-004); the workflow added here gates only *this
  repository's own* contributions.
- Does **not** rewrite the conceptual or architecture guides' substance; the work is honesty calibration,
  restructuring, de-duplication, and completeness — not new conceptual content.
- Does **not** publish the package to PyPI or a catalog; it makes the install story honest about the
  current clone-and-install path and removes untimed promises.
- Does **not** expand governance beyond documenting the existing model and the path into it — no new
  maintainers, boards, or processes are created by this spec.
- Does **not** localize or translate any document.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A newcomer self-qualifies and reaches first success without insider knowledge (Priority: P1)

A developer who has never seen the repository reads the README, understands exactly what is delivered
versus in progress, sees which prerequisites they need for which path, and reaches a first green verdict
without asking a maintainer anything.

**Acceptance Scenarios**:

1. **Given** a reader with no prior context, **When** they read `README.md` top to bottom, **Then** every
   capability claim matches `docs/STATUS.md` (oracle-leg-only headless isolation is stated as such; the
   Spec Kit + coding-agent dependency of the autonomous path is stated where autonomy is claimed), and
   every term of art is defined at or linked from first use.
2. **Given** the same reader, **When** they follow the getting-started prerequisites section, **Then**
   hard, conditional, and optional prerequisites are distinguished, each optional scanner names its
   quarantine behavior, and the Spec Kit pin names its upstream source and install command.
3. **Given** a reader who only wants the deterministic gates (no autonomy), **When** they follow the
   documented offline path, **Then** they reach a signed verdict without installing Spec Kit or any
   coding-agent integration.

### User Story 2 - A contributor's pull request is checked automatically (Priority: P1)

A first-time contributor opens a pull request and automated checks tell them — without a maintainer —
whether the engine still lints, type-checks, tests green, and verifies its own ledger.

**Acceptance Scenarios**:

1. **Given** an open pull request against `main`, **When** the CI workflow runs, **Then** it executes the
   engine's lint, type, and test suites and the offline ledger verification, and a failure blocks the
   merge as a required check.
2. **Given** a contributor reading `CONTRIBUTING.md`, **When** they prepare a change, **Then** the
   documented local commands match what CI runs, and the platform support statement (tested on macOS,
   Linux best-effort) is present.

### User Story 3 - Status has one home (Priority: P2)

A maintainer updates implementation status in exactly one file; every other document points there and none
contradicts it.

**Acceptance Scenarios**:

1. **Given** a status change (e.g. a residual delivered), **When** `docs/STATUS.md` is updated, **Then**
   no other file requires a matching edit to stay truthful — `README.md`, `AGENTS.md`, and `CLAUDE.md`
   carry only durable summaries plus a link.
2. **Given** `docs/STATUS.md`, **When** a newcomer opens it, **Then** an executive summary at the top
   states the current milestone, the date last validated, and the open residuals in one screen.

## Requirements *(each is referenced by ≥1 test or checklist item)*

### Functional Requirements

- **OSSRD-FR-001**: The README shall claim only what `docs/STATUS.md` validates as delivered, shall scope
  the sanitized-headless claim to the oracle leg, and shall state the external dependencies of the
  autonomous path (Spec Kit CLI + a coding-agent integration) wherever unattended operation is claimed.
  - *Acceptance*: a docs-conformance check finds no README capability claim contradicting STATUS; the
    quickstart names the autonomous path's dependencies before the first `3pwr run` invocation.
- **OSSRD-FR-002**: Every entry document that references the Spec Kit pin shall name its upstream source
  (`github/spec-kit`) and the tagged-install command; no entry document shall leave the pin unsourced.
  - *Acceptance*: `README.md`, `AGENTS.md`, and `docs/getting-started.md` each source the pin or link the
    sourcing section of `docs/references/speckit.md`.
- **OSSRD-FR-003**: The getting-started guide shall open with a prerequisites section distinguishing hard
  requirements, conditional requirements (per path: autonomous vs slash-command vs gates-only), and
  optional scanners with their quarantine behavior.
  - *Acceptance*: the section exists before any install command; the gates-only path lists no Spec Kit or
    agent-integration requirement.
- **OSSRD-FR-004**: The repository shall carry a CI workflow that runs the engine's format/lint, type, and
  test suites and offline ledger verification on every pull request to `main`, configured as required
  checks.
  - *Acceptance*: `.github/workflows/` contains the workflow; it runs
    `ruff check`, `mypy src`, `pytest`, and `3pwr verify` (or their uv-invoked equivalents) and fails the
    run on any failure; `CONTRIBUTING.md` documents the identical local commands.
- **OSSRD-FR-005**: Every term of art in an entry document shall be defined at first use or link to its
  definition, and a glossary shall define at minimum: trust spine, oracle, Phase A/Phase B, residual, A3
  (and the other lettered assumptions), verdict, quarantine, work kind, and the requirement-ID scheme.
  - *Acceptance*: a glossary exists under `docs/`; entry documents (`README.md`,
    `docs/getting-started.md`, `docs/concepts.md`) contain no undefined first-use of a glossary term;
    "A3" resolves to a definition from every user-facing occurrence.
- **OSSRD-FR-006**: Implementation status shall live only in `docs/STATUS.md`, carrying a validation date
  and a one-screen executive summary; `README.md`, `AGENTS.md`, and `CLAUDE.md` shall link to it instead
  of duplicating per-plan status detail.
  - *Acceptance*: per-plan/residual status narratives appear in exactly one file; the other three link;
    STATUS opens with milestone, date, and open-residual summary.
- **OSSRD-FR-007**: Gate naming, gate lists, and command examples shall be consistent across all
  documents, matching the engine's canonical identifiers.
  - *Acceptance*: one spelling per gate everywhere (matching the verdict's identifiers); the README gate
    list either matches the architecture doc or explicitly defers to it for work-kind-shaped gates;
    a docs check greps entry docs against the canonical gate-name list.
- **OSSRD-FR-008**: The install story shall document only currently working paths; any future distribution
  channel shall be listed as planned in STATUS, not promised in the README.
  - *Acceptance*: no "coming soon" install command remains in `README.md`; the clone-and-install path is
    the quickstart's first command.
- **OSSRD-FR-009**: Contributor and governance documents shall state the platform support policy (tested
  on macOS; Linux best-effort; Windows unsupported/WSL2) and a documented path to becoming a maintainer.
  - *Acceptance*: `CONTRIBUTING.md` carries the platform statement; `GOVERNANCE.md` carries the
    maintainer path.
- **OSSRD-FR-010**: The documentation shall include a troubleshooting entry covering at minimum: signing
  key not found, Spec Kit version mismatch, quarantined gates (missing scanner), and `specify` not
  installed for `3pwr run`.
  - *Acceptance*: each listed failure names its symptom, cause, and the exact resolving command.
- **OSSRD-FR-011**: The repository shall carry a version tag matching the honest milestone before public
  announcement, and `CHANGELOG.md` shall reference it.
  - *Acceptance*: a tag exists on `main` whose name matches the CHANGELOG's latest milestone entry; the
    README status section names the same milestone.

### Non-Functional Requirements

- **OSSRD-NFR-001**: Honesty invariant — no user-facing document may state a capability that
  `docs/STATUS.md` marks residual or partial without carrying that qualification inline.
  - *Acceptance*: a repo-wide docs review against STATUS's residual list finds zero unqualified claims;
    the check is repeatable by a contributor from the repo alone.
- **OSSRD-NFR-002**: The CI workflow shall complete on a pull request within 10 minutes on the hosted
  default runners, so it never becomes the reason contributors bypass checks.
  - *Acceptance*: a representative PR run finishes under the bound.
- **OSSRD-NFR-003**: Entry-document brevity — the README shall carry the pitch, one quickstart, and links;
  reference tables (language matrix, full gate list) live in `docs/`.
  - *Acceptance*: README body stays ≤ 120 lines of prose/tables excluding badges and license footer;
    the language matrix resides under `docs/`.

## Success Criteria

- **OSSRD-SC-001**: A newcomer reaches a first signed green verdict on the bundled sample using only the
  README + getting-started, with no maintainer contact and no undocumented prerequisite.
- **OSSRD-SC-002**: A reader comparing `README.md` against `docs/STATUS.md` finds zero contradictions.
- **OSSRD-SC-003**: A pull request that breaks the engine's lint, types, tests, or ledger verification is
  blocked automatically.
- **OSSRD-SC-004**: The Spec Kit pin question ("is this a fork? where do I get it?") is answerable from
  every entry document.
- **OSSRD-SC-005**: Status is updated in one file and nowhere else; the other documents remain truthful
  without edits.
- **OSSRD-SC-006**: The repository carries a tagged release whose name matches the documented milestone.

## Sign-off

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id OSSRD --stage spec --spec specs/006-oss-readiness/spec.md`)_ | | |
