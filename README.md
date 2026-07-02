# 3Powers

> **The spec is the law. Agents execute. An independent judiciary decides whether the code obeys.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](engine/pyproject.toml)
[![Built on Spec Kit](https://img.shields.io/badge/built%20on-GitHub%20Spec%20Kit-black.svg)](docs/references/speckit.md)
[![Self-applied](https://img.shields.io/badge/self--applied-gates%20its%20own%20code-brightgreen.svg)](docs/STATUS.md)

**3Powers is an open, portable judiciary for agentic software delivery.** You write the spec and make the
final call; agents do the building; and an *independent* oracle, a deterministic gate suite, and a human
sign-off decide whether what was built actually matches what you asked — recorded in a signed,
tamper-evident ledger, entirely on your machine. No CI/CD platform required, and no lock-in to any model
family, language, or LLM provider.

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

## Quickstart

```bash
# Install the engine (provides the `3pwr` command). Needs `uv` (https://docs.astral.sh/uv/).
#   Coming soon from PyPI:   uv tool install 3pwr
# For now, install from source:
git clone https://github.com/VerzCar/3powers.git
cd 3powers
uv tool install ./engine

# Create the independent signer (private key is written OUTSIDE the repo; only the public key is committed)
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/3powers.key"

# Run the whole gate suite on the bundled sample, then verify the signed ledger offline
(cd examples/validation-utils && npm install)
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
3pwr verify

# Sign off and advance — advance refuses without a green verdict AND a human sign-off
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
3pwr advance --stage ship
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

New here? Follow the hands-on **[Getting Started](docs/getting-started.md)** guide — every command and its
output is real and reproducible.

## The whole lifecycle in one command

3Powers drives an eight-stage lifecycle — **Discovery → Spec → Plan → Build → Verify → Review → Ship →
Observe** — with explicit human gates. You can run it stage by stage, or let one command drive it:

```bash
3pwr classify "add rate limiting to the login endpoint"   # infer the kind of change + a suggested tier
3pwr run "add rate limiting to the login endpoint" --mode auto
```

`3pwr run` composes GitHub Spec Kit's workflow and the judiciary gates, streams a live stage tracker, and
in `auto` mode **stops only at the two moments that need a human** — approving the spec, and the final
sign-off. It records progress in the signed ledger, so a run is resumable and auditable.

Prefer a hands-on flow? Open the repo in VS Code with GitHub Copilot and drive it with slash commands:
`/speckit.specify → clarify → plan → tasks` → **switch the chat model** → `/3pwr.oracle` (the independent
answer key) → **switch back** → `/speckit.implement` → `/3pwr.verify` → `/3pwr.review` → `/3pwr.signoff` →
`/3pwr.advance`. On an *existing* codebase, start with `/3pwr.characterize`.

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

- 📜 Specification — [`3Powers_Spec_v0.2.md`](3Powers_Spec_v0.2.md)
- 🏛️ Constitution — [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
