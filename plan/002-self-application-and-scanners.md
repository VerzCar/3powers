# Plan 002 — Self-Application, Python Adapter & Supply-Chain Scanners

**Status**: Largely implemented. Self-application is green at Standard (engine gated by its own
Python adapter), and secret + dependency scanners are wired as core gates. Mutation is scoped to the
trust-spine modules and wired, but the mutmut 3.x + src-layout runner needs follow-up setup, so the
full sweep runs on schedule (3PWR-NFR-002). Builds on plan [`001`](001-base-setup-and-tech-stack.md).

## Context — why

Plan 001 proved the framework works on an *external* sample (TypeScript). The spec's deepest
constraint is that **3Powers is built and maintained using 3Powers** (3PWR-A6 / 3PWR-NFR-006): its own
trust-spine code must pass its own gates at the **High-risk** tier. Plan 002 makes the engine eat its
own dog food, completes the second reference adapter (Python — which is also what gates the engine),
and adds the first language-agnostic supply-chain scanners.

## Scope

**In:** complete the **Python adapter** · a scoped **engine spec** so conformance can run on the engine
· raise engine test coverage and fix lint/types so the engine passes its own gates · **tiered
self-application** (trust-spine modules at High-risk, orchestration at Standard) · turn on **mutation
enforcement** (mutmut) for High-risk · add **secret** (gitleaks) and **dependency** (osv-scanner) scans
as language-agnostic core gates.

**Out (→ 003+):** SAST (semgrep), automated residual review (FR-036), build provenance + SBOM + deploy
gate (FR-066–068), eval harness (FR-050), brownfield/observe, catalog packaging.

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| **Self-application scoping** | Trust-spine modules (`ledger`, `verify`, `canonical`, `keys`) → **High-risk**; orchestration (`gates`, `adapters`, `config`, `verdict`, `conformance`, `covdiff`, `cli`) → **Standard** | Matches the capability→tier map in `risk-tiers.yaml` (spec §4): the trust spine *is* the trust. |
| **Engine spec** | `specs/002-engine-trust-spine/spec.md`, Spec ID **3PWR**, listing only the FR subset the v0.1 engine implements | Conformance checks the *declared* requirements; a scoped slice keeps it honest without claiming the whole 71-FR epic. Engine tests reference these real epic IDs. |
| **Secret scan** | **gitleaks** | Fully offline, fast, language-agnostic; core gate (3PWR-FR-028). |
| **Dependency scan** | **osv-scanner** (Trivy as fallback) | Precise per-ecosystem advisories from OSV; language-agnostic core gate. |
| **Scanner availability** | Gates degrade to `skip` (not `fail`) when the tool is absent, and are surfaced as quarantined (3PWR-NFR-015) | Keeps the suite runnable on machines without every tool installed, without silently passing. |

## Workstreams

1. **Scoped engine spec** — `specs/002-engine-trust-spine/spec.md` (Spec ID 3PWR): EARS + acceptance for
   the implemented subset — e.g. FR-022, FR-029, FR-030, FR-033, FR-034, FR-038, FR-039, FR-040,
   FR-041, FR-042 (+ NFR-001/010). Record a sign-off.
2. **Python adapter completion** — confirm `ruff format --check`, `ruff check`, `mypy src`, and
   `pytest --cov --cov-report=lcov` run clean; ensure the LCOV path matches the manifest. Make
   `3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md` work.
3. **Coverage + hygiene** — add engine tests (gates, cli, keys, config, verdict, adapters) so:
   diff-coverage ≥ 80 (Standard) overall, and the four trust-spine modules reach the High-risk bar;
   fix all ruff/mypy findings. Each new test references the FR ID it exercises (feeds conformance).
4. **Mutation enforcement** — add mutmut config scoped to the trust-spine modules; run
   `3pwr gate run … --tier High-risk --mutation`; report surviving mutants as missing assertions
   (3PWR-FR-031/034) and close the gaps to clear the tier's `mutation_score`.
5. **Secret + dependency core gates** — extend the engine with `secret_scan` (gitleaks) and
   `dependency_scan` (osv-scanner) as core, language-agnostic gates; add them to the appropriate tiers;
   fold normalized findings (vulnerability class, file/line) into the verdict (3PWR-FR-034). Add a
   `quarantine` concept so an absent tool is surfaced, never silently green (3PWR-NFR-015).
6. **Verify & document** — self-application gate run green at the intended tiers; update
   `docs/references/trust-spine-tooling.md` and `AGENTS.md` with the new gates and pinned scanner
   versions.

## Engine module → tier map

| Module | Tier | Implements |
|---|---|---|
| `canonical.py`, `keys.py`, `ledger.py`, `verify.py` | **High-risk** | FR-038/039/040, NFR-001/005/010 |
| `conformance.py`, `covdiff.py` | Standard | FR-029/030/064/065 |
| `gates.py`, `adapters.py`, `verdict.py`, `config.py`, `cli.py` | Standard | FR-026/027/032/033/034/041/042 |

## Verification (target)

```bash
# Self-application: 3Powers gating its own engine
3pwr gate run --path engine --adapter python \
    --spec specs/002-engine-trust-spine/spec.md --tier Standard
3pwr gate run --path engine --adapter python \
    --spec specs/002-engine-trust-spine/spec.md --tier High-risk --mutation   # trust-spine modules
3pwr verify
```
Expected: floor + tests + diff-coverage + spec-conformance green; mutation ≥ tier threshold on
trust-spine modules; secret/dependency scans green (or cleanly quarantined if a tool is absent); signed
verdict in the ledger.

## Known risks

- Reaching the High-risk **mutation** bar on `verify.py`/`ledger.py` may surface real assertion gaps —
  that is the gate doing its job; close them rather than lower the threshold (3PWR-FR-032).
- `mypy --strict`-level cleanliness across the engine may need type refinements.
- Scanner tools (gitleaks/osv-scanner) aren't installed in every environment; the quarantine path keeps
  the suite usable while flagging the gap.
