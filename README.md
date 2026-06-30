# 3Powers

> **Spec is the law. Agents execute. Gates judge.**

An open, portable **judiciary kit** for spec-driven, agentic software delivery. It enforces a separation
of powers — the spec as legislature, agents as executive, an independent oracle and deterministic gates
as judiciary — across any model family, language toolchain, or LLM provider, with no required CI/CD
platform. It layers on **GitHub Spec Kit** over Git.

**Status:** **v0.5 complete; v1.0 in progress** — the full judiciary, self-applied **at High-risk**
(NFR-006 met), with **brownfield Stage Zero** landed ([`plan/006`](plan/006-v1.0-and-hardening.md)). New
here? Start with the **[documentation](docs/)** below, or **[`docs/STATUS.md`](docs/STATUS.md)** for the
spec-validated status and what's next.

## How it works

The eight-stage lifecycle (Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe) runs
through GitHub Copilot slash commands. Spec Kit drives the legislative/executive stages
(`/speckit.*`); 3Powers adds the judiciary (`/3pwr.*`) and a local trust spine:

- an independent **oracle** authored from the spec alone, by a *different model family* than the coder;
- a cheapest-first **gate suite** (format → lint → types → tests → diff-coverage → mutation → SAST →
  dependency → secret → gate-gaming → spec-conformance) that emits one normalized verdict;
- an append-only, **hash-chained, Ed25519-signed ledger** with an offline `3pwr verify` and a local
  `advance` gate that refuses to proceed without green gates + a human sign-off.

## Quickstart

```bash
# 1. Install the engine (provides the `3pwr` command)
uv tool install ./engine

# 2. Create the independent signer (private key is written OUTSIDE the repo)
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/3powers.key"

# 3. Run the gate suite on the sample, then verify the signed ledger
cd examples/validation-utils && npm install && cd -
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
3pwr verify

# 4. Sign off and advance (advance refuses without a sign-off)
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id VUTIL
3pwr advance --stage ship
```

### Driving the full lifecycle in GitHub Copilot

Open the repo in VS Code with Copilot — `/speckit.*` and `/3pwr.*` appear as chat slash commands. On a
feature:

`/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → **switch the chat model**
→ `/3pwr.oracle` (Phase A, independent tests) → **switch back** → `/speckit.implement` →
`/3pwr.verify` → `/3pwr.signoff` → `/3pwr.advance`.

## Documentation

Full guides live in **[`docs/`](docs/)**:

- **[Concepts](docs/concepts.md)** — the three powers, lifecycle, risk tiers, oracle independence, trust spine.
- **[Getting Started](docs/getting-started.md)** — install and run the whole thing end-to-end.
- **[Engine Architecture](docs/engine-architecture.md)** — how the gates, verdict, and ledger work inside.
- **[CLI Reference](docs/cli-reference.md)** — every `3pwr` command and flag.
- **[Brownfield Adoption](docs/brownfield.md)** — bring 3Powers to an existing codebase.
- **[STATUS](docs/STATUS.md)** — implementation status, validated against the spec.

## Layout

| Path | What |
|---|---|
| [`engine/`](engine/) | the `3pwr` Python engine (gate runner, ledger, verify) |
| [`.3powers/`](.3powers/) | in-repo trust spine: config, schemas, adapters, signed ledger, public key |
| [`.specify/`](.specify/), `.github/` | Spec Kit + 3Powers constitution, templates, and `/3pwr.*` commands |
| [`examples/validation-utils/`](examples/validation-utils/) | the runnable TypeScript sample |
| [`specs/`](specs/) | authoritative specs (the law) |
| [`plan/`](plan/) | the continuous plan series (001 → 006) |
| [`docs/`](docs/) | guides (concepts, getting-started, architecture, CLI, brownfield) + references |

- 📜 Specification — [`3Powers_Spec_v0.2.md`](3Powers_Spec_v0.2.md) (Spec ID `3PWR`)
- 🏛️ Constitution — [`.specify/memory/constitution.md`](.specify/memory/constitution.md)
- 🤖 Agent guidance — [`CLAUDE.md`](CLAUDE.md) · [`AGENTS.md`](AGENTS.md)
