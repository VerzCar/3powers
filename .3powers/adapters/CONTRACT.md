# 3Powers Language-Adapter Contract

> Polyglot from day one (3PWR-A5). Language support is a **plugin contract, not
> hard-coded** (3PWR-FR-027). Adding a language requires only a manifest + a
> conformance run — **no change to the gate-engine core** (3PWR-NFR-007). The core
> never assumes a language beyond what the adapter declares (3PWR-FR-045).

An adapter is a single declarative file: `.3powers/adapters/<language>/adapter.yaml`.
The engine reads it, runs the declared commands cheapest-first, and folds their
results into the one normalized verdict (3PWR-FR-033).

## Manifest schema

```yaml
language: <string>                 # adapter id, e.g. "typescript"
detect: ["<file>", ...]            # files whose presence selects this adapter
test_roots: ["<dir>", ...]         # where spec-conformance scans for requirement IDs
property_test_lib: <string>        # property-based testing library (3PWR-FR-024)
gates:
  format:   { check_cmd: "<cmd>", parser: <name> }
  lint:     { cmd: "<cmd>",       parser: <name> }
  types:    { cmd: "<cmd>",       parser: <name> }
  tests:    { cmd: "<cmd>",       parser: <name>,
              coverage_format: lcov, coverage_path: "<relative path>" }
  mutation: { cmd: "<cmd>",       parser: <name>, tier_min: "High-risk" }

  # Optional design oracles (3PWR-FR-009) — run only when work-kind inference tags a change `design`.
  visual_regression:  { cmd: "<cmd>", parser: <name> }
  a11y_scan:          { cmd: "<cmd>", parser: <name> }
  contract_check:     { cmd: "<cmd>", parser: <name> }
  component_contract: { cmd: "<cmd>", parser: <name> }
```

### Design oracles (optional, work-kind-shaped)

Design work is judged by **design oracles**, not the code gates alone (3PWR-FR-009). When work-kind
inference (3PWR-FR-058) tags a change `design`, the engine unions the oracle gates listed in
`.3powers/config/design-oracles.yaml` onto the tier's gate set. Each oracle's *tool* is adapter-supplied
(`visual_regression`, `a11y_scan`, `contract_check`, `component_contract`); a selected oracle the adapter
doesn't declare — or whose tool isn't installed — is **quarantined**, never silently passed (3PWR-NFR-015).
An adapter for a non-UI language may declare none; design runs then quarantine every oracle (surfaced).

### Gate responsibilities

| Gate              | Owner   | Contract |
|-------------------|---------|----------|
| `format`          | adapter | `check_cmd` exits non-zero if code is not formatted (no writes). |
| `lint`            | adapter | `cmd` exits non-zero on a lint error. |
| `types`           | adapter | `cmd` exits non-zero on a type error. |
| `tests`           | adapter | `cmd` runs unit+integration+e2e (3PWR-FR-064) and writes an **LCOV** report to `coverage_path`. |
| `diff_coverage`   | **core**| Computed from the LCOV report ∩ `git diff` changed lines (3PWR-FR-028/029). |
| `mutation`        | adapter | `cmd` runs the language mutation tool. Wired but non-blocking in v0.1. |
| `spec_conformance`| **core**| Deterministic trace: every requirement ID in the spec is referenced by ≥1 test (3PWR-FR-030). |

The **language-agnostic gates** (`diff_coverage`, `spec_conformance`, and — in later
plans — secret/dependency/provenance) live in the core (3PWR-FR-028); only the
language-specific gates come from the adapter.

### Conventions

* **Command exit code is the contract.** `0` = pass, non-zero = fail. The engine
  captures stdout/stderr tails as actionable findings (3PWR-FR-034).
* **Coverage is LCOV.** Every adapter's test command must emit LCOV so the core's
  diff-coverage works identically across languages.
* **Tests reference requirement IDs by mention** — e.g. `describe("VUTIL-FR-001 …")`.
  The conformance trace is a deterministic text match, so it is language-neutral.

## Reference adapters

* `typescript/` — built and exercised end-to-end in plan 001 (runs the sample).
* `python/` — scaffold for plan 002; also the adapter that lets 3Powers gate its
  own engine code at the High-risk tier (self-application, 3PWR-A6 / 3PWR-NFR-006).
