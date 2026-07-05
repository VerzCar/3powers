# Changelog

All notable changes to 3Powers are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

3Powers is pre-1.0. Entries are grouped by the development milestones (v0.1 → v0.5 → v1.0) described in
the spec's scope phasing and tracked in detail in [`docs/STATUS.md`](docs/STATUS.md). Each item notes the
plan document under [`plan/`](plan/) that delivered it. Releases are tagged on `main`; the first tagged
release is **v0.5.0**, matching the latest released milestone below.

## [Unreleased] — v1.0 (in progress): lifecycle & ecosystem

### Added

- **Git-integrated run lifecycle (GITX).** Git handling is now a mandatory pre/post-stage hook on every
  live run and the manual `/3pwr.*` drive: a working git repository is a run precondition (reported by
  the shared `ready`/init/preflight check set); every run is isolated to a dedicated branch
  `3pwr/<NNN>-<slug>` — reusing the SRCX run identity, created off the configured base, bound to the run
  as one additive `branch` field on the signed `run`/`start` entry, and re-entered on resume; a run
  refuses to start atop uncommitted changes it did not produce (naming the paths, leaving them
  untouched) and leaves nothing it produced uncommitted after any stage; each producing stage is exactly
  one commit staging only the run's produced paths, with an agent-written `COMMIT:` message
  (deterministic `3pwr(<spec-id>): <step>` fallback) authored per-commit as the configured `3pwr`
  identity — the developer's git config is never mutated and no history is rewritten. The discipline is
  mandatory: `--no-auto-commit` is superseded (warns, no longer disables) and the only relaxations are
  the signed, revocable `git_clean_start`/`git_stage_commit`/`git_run_branch` deviations. New:
  `3pwr git start` (manual-drive branch establishment), git-aware `advance` boundary checks,
  `.3powers/config/git.yaml` (branch prefix / base / 3pwr author, tolerant defaults), and the run
  branch + committed stages surfaced by both status commands. (plan 028)

- **Open-source launch readiness (OSSRD).** A CI workflow gates every pull request to `main` (engine
  lint, types, tests, and offline ledger verification, as required checks); a
  [glossary](docs/glossary.md) defines every term of art (trust spine, oracle, Phase A/B, residual,
  A1–A6, verdict, quarantine, work kind, the requirement-ID scheme); a
  [troubleshooting guide](docs/troubleshooting.md) covers the common failures with exact fixes.
  Entry docs were calibrated to what [STATUS](docs/STATUS.md) validates (the sanitized-headless claim is
  scoped to the oracle leg; the autonomous path's Spec Kit + coding-agent dependency is stated up front),
  the Spec Kit pin is sourced to upstream `github/spec-kit` everywhere it appears, prerequisites are
  split hard / per-path / optional, gate names match the engine's canonical identifiers across all docs,
  and implementation status lives only in STATUS. (plan 018)
- **Trust-spine hardening (HARDN).** A versioned [`docs/threat-model.md`](docs/threat-model.md) states what
  the ledger proves, against whom, under which assumptions. Key custody is enforced (`keygen`/`rotate-key`
  refuse in-repo keys; `verify` fails a `key_custody` violation; the secret gate's core `ed25519-priv` check
  always runs). Key rotation is a signed `key_rotation` entry authored by the outgoing key — `verify` walks
  the succession, so a bare committed-pubkey swap is a named *unrotated key change*. Opt-in `3pwr anchor` +
  `3pwr verify --anchored` record the head with an external git-tag witness and catch wholesale ledger
  regeneration by a key holder. `$THREEPOWERS_SIGNER_CMD` delegates signing to an external (hardware-capable)
  process boundary — no readable seed, loud failure, unchanged verification. The self-reported oracle model
  is cross-checked against the ledger-attested dispatch (contradiction blocks a High-risk advance; without a
  dispatch the claim is labelled self-reported). The `spec_conformance` gate now requires requirement IDs
  **bound to test declarations** (`untraced_requirement` for comment-only mentions) with ≥1 assertion per
  bound test (`weak_test`), `gate_gaming` flags newly added assertion-free requirement-referencing tests,
  and a per-tier `diff_mutation` knob runs mutation over changed files. (plan 017)
- **Spec-lock (SLOCK): the `spec_integrity` gate.** A Spec-stage `3pwr signoff` now seals the approved document's
  raw-bytes SHA-256 inside the signed ledger entry; a new `spec_integrity` gate (cheapest-first, before any
  test, at every tier) and `advance` fail a spec silently modified after approval (`spec_modified`), unless
  a fresh Spec-stage sign-off supersedes it or a signed `spec_integrity` deviation covers it. The read-only
  `3pwr spec diff` reports the mismatch with a textual diff when the sign-off commit is known. Tampering
  with the recorded hash is caught by the existing `verify` — no new trust primitive. (plan 016)
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

- The complete cheapest-first gate suite, including **mutation testing**, **`sast`**, and the
  `dependency_scan`, `secret_scan`, `gate_gaming`, and `spec_conformance` gates.
- **Build provenance + SBOM**, signed by the independent identity and verified at a deploy gate.
- Two-way requirement ↔ task coverage, scope discipline, residual review, and the prompt/constitution eval
  harness. (plans 004–005)

## [0.1.0] — Trust-spine MVP

### Added

- The signed, hash-chained verdict **ledger**, offline `3pwr verify`, the local `3pwr advance` enforcement
  gate, and full reversibility via `3pwr revert`.
- The deterministic gate runner with the format / lint / types / tests / `diff_coverage` floor, emitting one
  normalized verdict.
- Two reference language adapters (TypeScript, Python), self-application of the engine on its own code, and
  supply-chain scanners. (plans 001–003)

[Unreleased]: https://github.com/VerzCar/3powers/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/VerzCar/3powers/releases/tag/v0.5.0
