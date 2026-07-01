# Changelog

All notable changes to 3Powers are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

3Powers is pre-1.0. Until the first tagged release, entries are grouped by the development milestones
(v0.1 → v0.5 → v1.0) described in the spec's scope phasing and tracked in detail in
[`docs/STATUS.md`](docs/STATUS.md). Each item notes the plan document under [`plan/`](plan/) that delivered
it.

## [Unreleased] — v1.0 (in progress): lifecycle & ecosystem

### Added

- **Work-kind-shaped gates.** `3pwr classify` infers the kind of change (defect, design, feature, …) and a
  suggested risk tier, and the gate suite adapts. A **defect** fix must ship a failing regression test; a
  **design** change is judged by design oracles (visual-regression, accessibility, and contract checks),
  which are quarantined — surfaced as skipped — when a tool isn't wired up. (plan 015)
- **Go language adapter** — a third reference adapter alongside TypeScript and Python, proving the adapter
  contract is language-agnostic. (plan 015)
- **One-command lifecycle** — `3pwr run` drives all eight stages with a live tracker, stopping only at the
  two human gates (spec approval, sign-off) in `auto` mode. (plan 013)
- **Observe & feedback loop** — `3pwr observe signal | coverage | log-action | verify-actions`: route a
  production signal to a new requirement, report which NFRs have a live check, and keep a tamper-evident,
  attributable agent-action log. (plan 010)
- **Headless, read-path-isolated oracle authoring** — `3pwr oracle dispatch` authors the oracle inside a
  sanitized Git worktree where the implementation is physically absent, attested in the ledger. (plan 011)
- **Structural oracle independence** — `3pwr oracle seal | record | verify`: a spec-only sealed bundle, a
  recorded authoring model that must differ from the coder's, and ledger-proven independence enforced at
  the High-risk tier. (plan 008)
- **Emergency & deviation paths** — `3pwr emergency` and `3pwr deviation`: signed, reversible, time-bound
  exceptions that are always recorded and never silently weaken a gate. (plan 007)
- **Brownfield adoption** — report-only runs, diff-scoped gating, and `3pwr characterize` to reconstruct a
  spec and pin a legacy module's current behavior. (plan 006)
- **Portability tooling** — `3pwr deps-check` (drift against supported versions, including Spec Kit) and a
  provider-agnostic Spec Kit extension. (plan 009)
- Root `LICENSE` (Apache-2.0) and this open-source documentation set (README, CONTRIBUTING, SECURITY,
  GOVERNANCE, Code of Conduct, per-component READMEs).

### Changed

- The secret gate now prefers **betterleaks** (a maintained Gitleaks successor), falling back to gitleaks,
  and quarantines when neither is present. (plan 014)
- Model diversity is now **recommend-not-force**: a same-family oracle proceeds under a signed, reversible
  exception rather than being blocked outright, so single-model users are never walled off. (plan 012)
- Per-tier required test layers (unit / integration / e2e) are enforced as a per-change union. (plan 014)
- **Self-application at High-risk:** the trust-spine modules pass their own High-risk bar (≥95%
  diff-coverage plus mutation), so 3Powers is genuinely built with 3Powers at the strictest tier. (plan 006)

## [0.5.0] — Full judiciary

### Added

- The complete cheapest-first gate suite, including **mutation testing**, **SAST**, and the dependency,
  secret, anti-gaming, and spec-conformance gates.
- **Build provenance + SBOM**, signed by the independent identity and verified at a deploy gate.
- Two-way requirement ↔ task coverage, scope discipline, residual review, and the prompt/constitution eval
  harness. (plans 004–005)

## [0.1.0] — Trust-spine MVP

### Added

- The signed, hash-chained verdict **ledger**, offline `3pwr verify`, the local `3pwr advance` enforcement
  gate, and full reversibility via `3pwr revert`.
- The deterministic gate runner with the format / lint / types / tests / diff-coverage floor, emitting one
  normalized verdict.
- Two reference language adapters (TypeScript, Python), self-application of the engine on its own code, and
  supply-chain scanners. (plans 001–003)

[Unreleased]: https://github.com/your-org/3powers
