<p align="center">
  <img src="https://raw.githubusercontent.com/VerzCar/3powers/main/docs/assets/3powers-logo.png" alt="3Powers" width="140" />
</p>

# 3Powers

> **The spec is the law. Agents execute. An independent judiciary determines whether the implementation complies with the spec.**

**3Powers is a portable, open agent harness with a judiciary** — it drives your coding agents through the whole agentic lifecycle at high autonomy, then does the one thing a bare harness never does: it refuses to take their word for it. Agents do the building. An *independent* judiciary — an oracle that never saw the code, a deterministic gate suite, and a signed, tamper-evident ledger — proves that what shipped matches the spec you approved.

This package (`3powers` on PyPI) provides the **`3pwr` command**: the native provider-agnostic executive, the deterministic gate runner, the oracle-independence checks, and the hash-chained, Ed25519-signed verdict ledger you can verify offline. It is model-, language-, and provider-agnostic, uses Git as its substrate, and needs no CI/CD platform.

## Install

Install with [uv](https://docs.astral.sh/uv/) — the package is published as **`3powers`**, and the command it installs is **`3pwr`**:

```bash
uv tool install 3powers        # installs the `3pwr` command
```

Or run it once without installing:

```bash
uvx 3powers --help
```

Python 3.11+ is required.

## Quickstart: the autonomous path

```bash
# 1. In YOUR project (new or existing), run the guided onboarding. It asks for the language,
#    where to keep the signing key (always OUTSIDE the repo), and your default autonomy mode.
cd /path/to/your/project && 3pwr init

# 2. Describe what you want built, and let the lifecycle run:
3pwr run "add rate limiting to the login endpoint" --mode auto
```

`3pwr run` streams a live stage tracker and in `auto` mode **stops only at the two human gates**: approving the spec, and the final sign-off. Every step lands in the signed, offline-verifiable ledger, so a run is resumable and auditable.

The deterministic gates, ledger, and enforcement are pure `3pwr` and need no agent at all — the gates-only path works fully offline. Every run emits one normalized verdict a human can read without opening a single agent transcript:

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

## Why: when one model does everything, validation is a mirror

Hand a capable agent a feature and it will happily write the spec, the code, the tests, *and* the review. They all agree, because they all came from the same mind. A passing build only proves the model agreed with itself. 3Powers calls this the **separation-of-powers collapse**, and restores three independent branches:

- ⚖️ **Legislative — the spec is the law.** Versioned, testable requirements every later stage answers to.
- 🛠️ **Executive — agents build against it.** They may write their own tests, but those never *replace* the independent check.
- 👩‍⚖️ **Judicial — an independent judiciary decides.** An oracle authored from the spec by a *different model family*, a deterministic gate suite, and a human sign-off.

The lifecycle runs in eight stages — Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe — with a signed, hash-chained ledger recording every verdict and sign-off so the whole run is verifiable offline.

## Documentation

Full guides live in the repository:

- **[Getting Started](https://github.com/VerzCar/3powers/blob/main/docs/getting-started.md)** — prerequisites, install, and the whole thing end-to-end.
- **[Concepts](https://github.com/VerzCar/3powers/blob/main/docs/concepts.md)** — the three powers, the lifecycle, risk tiers, oracle independence, the trust spine.
- **[CLI Reference](https://github.com/VerzCar/3powers/blob/main/docs/cli-reference.md)** — every `3pwr` command and flag.
- **[Engine Architecture](https://github.com/VerzCar/3powers/blob/main/docs/engine-architecture.md)** — the gates, the verdict, and the ledger.
- **[Glossary](https://github.com/VerzCar/3powers/blob/main/docs/glossary.md)** — every term of art, defined once.
- **[STATUS](https://github.com/VerzCar/3powers/blob/main/docs/STATUS.md)** — implementation status, validated against the spec.

Repository: **https://github.com/VerzCar/3powers**

## Contributing

Working *on* the engine itself? See **[CONTRIBUTING.md](https://github.com/VerzCar/3powers/blob/main/CONTRIBUTING.md)** for the dev environment and the checks it must always pass (`ruff` + `mypy` + `pytest`, plus the engine gating its own code at the strictest tier).

## License

[Apache-2.0](https://github.com/VerzCar/3powers/blob/main/LICENSE).
