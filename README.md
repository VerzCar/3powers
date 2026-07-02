# 3Powers

> **The spec is the law. Agents execute. An independent judiciary decides whether the code obeys.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](engine/pyproject.toml)
[![Built on Spec Kit](https://img.shields.io/badge/built%20on-GitHub%20Spec%20Kit-black.svg)](docs/references/speckit.md)
[![Self-applied](https://img.shields.io/badge/self--applied-gates%20its%20own%20code-brightgreen.svg)](docs/STATUS.md)

**3Powers is a secure, trustworthy, enterprise-ready framework for building software with high autonomy in
agentic mode.** Agents do the building; an *independent* judiciary — an oracle that never saw the code, a
deterministic gate suite, and a signed, tamper-evident ledger — proves that what shipped matches the spec
you approved. You stay in the loop at exactly two moments: **approving the spec, and the final sign-off.**
Everything in between runs unattended. It all happens on your machine — no CI/CD platform required, and no
lock-in to any model family, language, or LLM provider.

Open, portable, and auditable by construction: every verdict and sign-off is hash-chained and
Ed25519-signed in a ledger you can verify offline — so "the agents said it passed" becomes "here is the
signed, independent proof."

## The problem: when one model does everything, validation is a mirror

Hand a capable agent a feature and it will happily write the spec, the code, the tests, *and* the review.
They all agree — because they all came from the same mind. A passing build no longer proves the code does
what you *meant*; it only proves the model agreed with itself. Nothing independent ever checked the work.

3Powers calls this the **separation-of-powers collapse**, and it is the exact thing standing between
"agents can write my code" and "I can trust what they wrote." The scarce thing is no longer code — it's
**confidence that the code does what was intended.**

## The fix: restore the separation of powers

3Powers splits every change across three branches that hold each other accountable — and makes that
separation *mechanical*, not a matter of good intentions:

- ⚖️ **Legislative — the spec is the law.** Versioned, testable requirements are the single source of
  truth every later stage answers to.
- 🛠️ **Executive — agents build against it.** Coding agents turn the spec into a plan, tasks, and code.
  They may write their own tests, but those can never *replace* the independent check.
- 👩‍⚖️ **Judicial — an independent judiciary decides.** An **oracle** (acceptance tests written from the
  spec by a *different model family* than the coder, blocked from reading the implementation), a
  **deterministic gate suite** (same verdict no matter who wrote the code), and a **human sign-off**.

You stay where your judgement actually matters — **the spec and the final review**. The judiciary does the
tireless, independent validation in between. Execution is the agents' job; *trust* is the framework's.

## What you get

- **An independent oracle.** Acceptance tests authored *from the spec alone*, by a different model family
  than the coder, and — at the strictest tier — authored headlessly in a sanitized workspace where the
  implementation is physically absent. The coder never grades its own exam.
- **A deterministic verdict.** One cheapest-first gate suite — format → lint → types → tests + coverage →
  mutation → SAST (static security scan) → dependency → secret → anti-gaming → spec-conformance — that
  returns the *same* result
  regardless of which model wrote the code, and names exactly what failed and where.
- **A local trust spine.** Every verdict and sign-off is hash-chained and Ed25519-signed in an append-only
  ledger you can verify **offline**. A local `advance` gate refuses to ship without green gates *and* a
  human sign-off. Tamper-evident, reconstructable from the repo alone — no CI/CD gatekeeper needed.
- **Risk-tiered rigor.** `Cosmetic` / `Standard` / `High-risk` set every threshold from one knob. The
  golden rule: **you never satisfy a gate by weakening it** — attempts to game a gate are flagged for human
  review, not silently absorbed.
- **Polyglot & provider-agnostic.** Languages plug in through a declarative adapter (TypeScript, Python,
  and Go today) with zero changes to the core; swap model vendors freely. It layers on **GitHub Spec Kit**
  and uses **Git** as its substrate.
- **Proven on itself.** The `3pwr` engine gates its own code — its trust-spine modules at the **High-risk**
  tier, mutation testing included. If it couldn't survive its own gates, why would you trust it on yours?

## Quickstart — the autonomous path

Install the engine, let the guided setup make your project 3Powers-ready, then let one command drive the
whole lifecycle.

```bash
# 1. Install once (provides the `3pwr` command). Needs `uv` (https://docs.astral.sh/uv/).
#    Coming soon from PyPI:   uv tool install 3pwr
git clone https://github.com/VerzCar/3powers.git && cd 3powers && uv tool install ./engine

# 2. In YOUR project (new or existing), run guided onboarding. It asks for the directory, the
#    language, where to keep the signing key (always OUTSIDE the repo), and whether autonomous
#    mode is your default — then it's ready. Add --yes to accept every default (e.g. in CI).
cd /path/to/your/project
3pwr init

# 3. Describe what you want built, and let the lifecycle run:
3pwr run "add rate limiting to the login endpoint" --mode auto
```

`3pwr run` composes GitHub Spec Kit's workflow and the judiciary gates, streams a live stage tracker, and
in `auto` mode **stops only at the two moments that need a human** — approving the spec, and the final
sign-off. Planning, the independent oracle, and the whole deterministic gate suite run unattended in
between, and every step is recorded in a signed, offline-verifiable ledger, so a run is fully resumable and
auditable.

> The autonomous lifecycle uses **GitHub Spec Kit** (the `specify` CLI) and a coding-agent integration
> (e.g. GitHub Copilot in VS Code) for the build/oracle steps; the deterministic gates, ledger, and
> enforcement are pure `3pwr` and need neither. New here? The hands-on
> **[Getting Started](docs/getting-started.md)** guide walks every command with real, reproducible output.

## Prefer to drive it yourself? Manual mode

Every stage is also a command you can run by hand. Open the repo in VS Code with GitHub Copilot and drive
it with slash commands: `/speckit.specify → clarify → plan → tasks` → **switch the chat model** →
`/3pwr.oracle` (the independent answer key) → **switch back** → `/speckit.implement` → `/3pwr.verify` →
`/3pwr.review` → `/3pwr.signoff` → `/3pwr.advance`. On an *existing* codebase, start with
`/3pwr.characterize`.

Or drive the gates directly — here on the bundled TypeScript sample (after `3pwr init` has created your
signer):

```bash
(cd examples/validation-utils && npm install)
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
3pwr verify                                                    # recompute the signed ledger, offline
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
3pwr advance --stage ship          # refuses without a green verdict AND a human sign-off
```

Every run emits one normalized verdict a human can read without opening a single agent transcript:

```
verdict FAIL  spec=VUTIL tier=Standard adapter=typescript
  ✓ format · biome          ✓ lint · biome        ✓ types · tsc
  ✓ tests · vitest          ✓ diff_coverage · 3pwr-covdiff  (100.0% ≥ 80.0%)
  ✗ dependency_scan · osv-scanner
      - GHSA-4x5r-pxfx-6jf8 in @babel/core
  ✓ secret_scan             ✓ gate_gaming         ✓ spec_conformance  (5 requirements traced)
  failures:
    • vulnerable_dependency: GHSA-4x5r-pxfx-6jf8 in @babel/core
  ↳ ledger entry #0 signed by ed25519:4fd71c543b0f499c
```

## Supported languages & technology stack

Check whether 3Powers fits your project. A language plugs in through a declarative **adapter**
(`.3powers/adapters/<lang>/adapter.yaml`) with zero changes to the core — and a framework like **Next.js is
covered by its language adapter (TypeScript); there is no framework-specific setup.** `3pwr init` sets up
the adapter for your chosen language automatically.

| Language | Detected by | Format | Lint | Types | Test (coverage) | Mutation | Design oracles | Status |
|---|---|---|---|---|---|---|---|---|
| **TypeScript** | `package.json` + `tsconfig.json` | Biome | Biome | tsc | Vitest (LCOV) | Stryker | Playwright · Axe · oasdiff · Pact | Reference — exercised end-to-end |
| **Python** | `pyproject.toml` | Ruff | Ruff | mypy | pytest (LCOV) | mutmut | — | Reference — gates the engine itself |
| **Go** | `go.mod` | gofmt | go vet | go build | go test → gcov2lcov (LCOV) | go-mutesting | — | Reference — wired |

The language-agnostic gates — diff-coverage, spec-conformance, dependency, secret, and SAST — run the same
way for every adapter. Don't see your language? Adding one is "write a manifest," not a core change — see
the adapter contract at [`.3powers/adapters/CONTRACT.md`](.3powers/adapters/CONTRACT.md).

## Who it's for

- **Teams who've handed execution to agents and now need to trust the output** — without reading every
  transcript or hoping the tests mean something.
- **Regulated or high-assurance work** that needs an auditable, signed trail from spec → verdict →
  sign-off → build provenance.
- **Anyone adopting GitHub Spec Kit** who wants the missing judiciary layer: independent validation and
  local, enforceable trust.

## Documentation

Full guides live in **[`docs/`](docs/)**:

- **[Concepts](docs/concepts.md)** — the three powers, the lifecycle, risk tiers, oracle independence, the trust spine.
- **[Getting Started](docs/getting-started.md)** — install and run the whole thing end-to-end.
- **[Engine Architecture](docs/engine-architecture.md)** — how the gates, the verdict, and the ledger work inside.
- **[CLI Reference](docs/cli-reference.md)** — every `3pwr` command and flag.
- **[Brownfield Adoption](docs/brownfield.md)** — bring 3Powers to an existing codebase.
- **[STATUS](docs/STATUS.md)** — implementation status, validated against the spec (maintainer-facing).

Contributing? See **[CONTRIBUTING.md](CONTRIBUTING.md)**, **[GOVERNANCE.md](GOVERNANCE.md)**, and the
**[Code of Conduct](CODE_OF_CONDUCT.md)**. To report a vulnerability, see **[SECURITY.md](SECURITY.md)**.

## Layout

| Path | What |
|---|---|
| [`engine/`](engine/) | the `3pwr` Python engine (gate runner, oracle, ledger, verify) |
| [`.3powers/`](.3powers/) | in-repo trust spine: config, schemas, language adapters, signed ledger, public key |
| [`.specify/`](.specify/), [`.github/`](.github/) | Spec Kit + the 3Powers constitution, templates, and `/3pwr.*` commands |
| [`examples/validation-utils/`](examples/validation-utils/) | a small, runnable TypeScript sample |
| [`specs/`](specs/) | authoritative specs (the law) |
| [`docs/`](docs/) | guides (concepts, getting-started, architecture, CLI, brownfield) + references |
| [`plan/`](plan/) | the continuous plan series (implementation history, 001 → 015) |

## Status

**v0.5 complete; v1.0 in progress.** The full judiciary is built and self-applied at the strictest tier:
an independent oracle, the complete cheapest-first gate suite, the signed local trust spine (ledger,
offline verify, enforcement, reversibility, build provenance), brownfield adoption, the observe-and-feedback
loop, one-command orchestration, and three reference language adapters (TypeScript, Python, Go). See
**[STATUS](docs/STATUS.md)** for the honest, spec-validated breakdown and what's next.

## License

[Apache-2.0](LICENSE).

---

- 📜 Specification — [`3Powers_Spec_v0.2.md`](specs/3Powers_Spec_v0.2.md)
- 🏛️ Constitution — [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
