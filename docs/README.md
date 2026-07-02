# 3Powers Documentation

Start here. These guides explain what 3Powers is, how to use it, and how the engine works — pick by what
you're trying to do. The **spec** ([`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md), Spec ID `3PWR`) is
the law; these docs explain and operationalize it.

## Guides

| If you want to… | Read |
|---|---|
| Understand the ideas (the three powers, lifecycle, tiers, oracle, trust spine) | **[Concepts](concepts.md)** |
| Install it and run the whole thing end-to-end | **[Getting Started](getting-started.md)** |
| Know how the engine works inside (gates, verdict, ledger, verify) | **[Engine Architecture](engine-architecture.md)** |
| Look up a command or flag | **[CLI Reference](cli-reference.md)** |
| Adopt 3Powers on an existing / legacy codebase | **[Brownfield Adoption](brownfield.md)** |
| See exactly how far the implementation is, validated against the spec | **[STATUS](STATUS.md)** |

## Reference material

- [`references/speckit.md`](references/speckit.md) — how 3Powers layers on **GitHub Spec Kit** (the `/speckit.*` workflow).
- [`references/trust-spine-tooling.md`](references/trust-spine-tooling.md) — the free/OSS tool choices behind the gates and trust spine.
- [`../.specify/memory/constitution.md`](../.specify/memory/constitution.md) — the supreme, normative law (the principles `concepts.md` explains).
- [`../.3powers/adapters/CONTRACT.md`](../.3powers/adapters/CONTRACT.md) — the language-adapter manifest schema.
- [`../CLAUDE.md`](../CLAUDE.md) · [`../AGENTS.md`](../AGENTS.md) — guidance for agents working in the repo.
- [`../plan/`](../plan/) — the continuous plan series (implementation history, 001 → 015).
- [`../CONTRIBUTING.md`](../CONTRIBUTING.md) — how to set up the dev environment and contribute.

## Coming next

A few docs are planned but not yet written: an **adapter-authoring walkthrough** (add a language,
step-by-step, beyond the `CONTRACT.md` schema) and a **CI/CD integration** guide.
Contributions welcome — see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
