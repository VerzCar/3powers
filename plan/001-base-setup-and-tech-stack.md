# Plan 001 — Base Setup & Technology Stack

**Status**: Implemented & verified (walking skeleton green end-to-end). This is plan **001** of a
continuous series; 002+ are previewed at the end.

## Context — why

The repo was pre-implementation: only the epic spec ([`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md))
plus `CLAUDE.md`/`AGENTS.md`. 3Powers is a "judiciary kit" for spec-driven agentic delivery that
restores separation of powers (Legislative spec / Executive build / Judicial verification), **layered
on GitHub Spec Kit** (A1) over Git (A2), and agnostic to model, language, and CI/CD.

Plan 001 establishes the **foundation + technology stack** and a **walking skeleton**: a thin but
*runnable* slice of the v0.1 trust-spine MVP (spec §17), exercisable end-to-end on a small sample
project through **GitHub Copilot**. Heavier gates and provenance are deferred to later plans.

## Decisions (locked)

| Area | Decision | Rationale |
|---|---|---|
| **Core engine** | **Python**, shipped as a `uv` tool named `3pwr` | Spec Kit already requires Python+`uv` (A1) → zero new runtime for end users; "fast enough" as a subprocess orchestrator; mature self-application toolchain (3PWR-NFR-006). Go was runner-up but adds a per-OS binary and has immature mutation tooling. |
| **Spec Kit integration** | `specify init --integration copilot`; layer 3Powers via **confirmed primitives** — constitution + template overrides + custom `/3pwr.*` prompt+agent commands | Avoids depending on the less-certain extension/preset packaging API; catalog packaging is later (v1.0). |
| **Reference adapters** | **TypeScript** (built + run in 001) + **Python** (scaffold; self-application, completed in 002). Declarative manifests. | Two biggest ecosystems; manifest ⇒ "add a language = add a manifest, no core change" (3PWR-NFR-007). |
| **Sample** | **TypeScript input-validation utils** (`examples/validation-utils/`) | Pure functions + input parsing/validation → ideal for an independent oracle and property tests (3PWR-FR-024). |
| **Trust spine** | Append-only **hash-chained JSONL ledger**, **Ed25519** signatures (engine built-in), private key **outside the repo**; offline `3pwr verify` | Local, offline, self-contained (3PWR-FR-038/040/071, 3PWR-NFR-004/005/010). |
| **Layout** | Single hidden **`.3powers/`** root (config + schemas + adapters + ledger + keys), mirroring `.specify/` | Cleaner for end users than the originally-sketched split `3powers/` + `.3powers/`. |
| **Provenance** | Chosen, implemented later: **syft** (SBOM) + **cosign** + **GitHub Artifact Attestations** as optional CI re-validation only (A4) | Spec mandates a local signer, no hosted CI (3PWR-FR-068, 3PWR-NFR-004). |

## As-built repository layout

```
.specify/                      # Spec Kit; constitution + templates OVERRIDDEN with 3Powers law
  memory/constitution.md       #   separation of powers, EARS, oracle independence, trust spine
  templates/{spec,plan,tasks}-template.md
.github/
  prompts/  speckit.*.prompt.md + 3pwr.{oracle,verify,signoff,advance}.prompt.md
  agents/   speckit.*.agent.md  + 3pwr.{oracle,verify,signoff,advance}.agent.md
specs/001-validation-utils/spec.md      # sample feature spec (Spec ID VUTIL), EARS + risk tier + non-goals
engine/                        # the `3pwr` Python engine (uv tool)
  src/threepowers/{cli,gates,conformance,covdiff,adapters,ledger,verify,keys,verdict,config,canonical}.py
  tests/test_{ledger,conformance,covdiff}.py
.3powers/
  config/{risk-tiers,roles}.yaml         # single threshold source + role→model-family diversity
  schemas/{verdict,ledger-entry}.schema.json
  adapters/CONTRACT.md + {typescript,python}/adapter.yaml
  ledger.jsonl  keys/ledger.pub  verdicts/  runs/
examples/validation-utils/     # the runnable TS sample (src + tests/{unit,integration,e2e})
docs/references/{speckit,trust-spine-tooling}.md
plan/001-base-setup-and-tech-stack.md    # this file
AGENTS.md  CLAUDE.md  README.md
```

## The `3pwr` engine (what it does)

| Command | Requirement | Behaviour |
|---|---|---|
| `keygen` | FR-039, NFR-005 | Generate the independent Ed25519 signer; **private key written outside the repo**, public key committed. |
| `gate run` | FR-026/028/029/033/034 | Cheapest-first: format→lint→types→tests→diff-coverage→spec-conformance; one normalized verdict; signed ledger entry appended. |
| `conformance` | FR-030/064/065 | Deterministic trace: every requirement ID referenced by ≥1 test, with unit/integration/e2e layers. |
| `verify` | FR-040, NFR-010 | Recompute hash chain + Ed25519 signatures, offline; non-zero on any tamper/gap/break. |
| `signoff` | FR-006/037 | Append a signed human sign-off entry. |
| `advance` | FR-041/042 | Refuse to proceed unless gate green + ledger verifies + sign-off present; uniform for all actors. |
| `roles-check` | FR-022 | Fail if two roles share a model family (judicial diversity). |

Diff-coverage and spec-conformance are computed in the **language-agnostic core** (FR-028); only
format/lint/types/tests/mutation come from the adapter manifest.

## Verification (performed this iteration — all green)

- Engine unit tests: **13 passed** (ledger sign/verify, tamper/reorder/delete/forgery detection,
  conformance, diff-coverage).
- `uv tool install ./engine` → real `3pwr` command on PATH.
- `keygen` → private key at `~/.config/3powers/*.key` (outside repo), public key committed.
- `gate run` on the sample → **format ✓ lint ✓ types ✓ tests ✓ diff-coverage 100% ✓ spec-conformance (5 traced) ✓**, signed ledger entry.
- `advance` **refused** before sign-off → `signoff` → `advance` **succeeded**; `verify` OK (3 entries).
- Negative: tampering a ledger entry made `verify` fail (named the entry, hash + signature); same-family `roles-check` → VIOLATION.

### End-to-end in GitHub Copilot (for the user to run)

Open the repo in VS Code with Copilot; `/speckit.*` and `/3pwr.*` appear as chat slash commands.
On the sample feature: `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` →
**switch model** → `/3pwr.oracle` (Phase A) → **switch back** → `/speckit.implement` → `/3pwr.verify`
→ `/3pwr.signoff` → `/3pwr.advance`. (Quickstart in [`README.md`](../README.md).)

## Known limitations (honest)

- **Oracle independence is approximated, not structural** in a Copilot-only setting: enforced via the
  judiciary prompt (no implementation reads), `roles.yaml` + `roles-check` (engine refuses same
  family), authoring order, and recording the model in the ledger. True process isolation is a later
  hardening target.
- **Self-application** of the engine's own (Python) code lands in 002 once the Python adapter is
  completed; 001 demonstrates the framework on the TS sample.
- **Mutation** gate is wired (Stryker) but non-blocking in 001 (spec §17).
- **Diff-coverage** parses LCOV ∩ `git diff`; rename/edge cases are a follow-up.

## Continuous plan (next)

- **002** — complete the **Python adapter**, turn on **self-application** at High-risk, enable
  **mutation enforcement**, add **secret + dependency scans** (gitleaks, trivy/osv-scanner).
- **003** — **SAST** (semgrep), **automated residual review** (FR-036, different family), **build
  provenance + SBOM** (syft+cosign) and the **deploy gate** (FR-066–068); optional GH Attestations.
- **004** — prompt/constitution **eval harness** (FR-050), **brownfield** Stage Zero, **observe** loop,
  **catalog distribution** (package 3Powers as a Spec Kit extension/preset).
