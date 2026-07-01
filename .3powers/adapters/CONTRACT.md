# 3Powers Language-Adapter Contract

> Polyglot from day one. Language support is a **plugin contract, not hard-coded**.
> Adding a language requires only a manifest + a conformance run — **no change to
> the gate-engine core** (language-agnostic / adapter-supplied). The core never
> assumes a language beyond what the adapter declares.

An adapter is a single declarative file: `.3powers/adapters/<language>/adapter.yaml`.
The engine reads it, runs the declared commands cheapest-first, and folds their
results into the one normalized verdict.

## Manifest schema

```yaml
language: <string>                 # adapter id, e.g. "typescript"
detect: ["<file>", ...]            # files whose presence selects this adapter
test_roots: ["<dir>", ...]         # where spec-conformance scans for requirement IDs
property_test_lib: <string>        # property-based testing library
gates:
  format:   { check_cmd: "<cmd>", parser: <name> }
  lint:     { cmd: "<cmd>",       parser: <name> }
  types:    { cmd: "<cmd>",       parser: <name> }
  tests:    { cmd: "<cmd>",       parser: <name>,
              coverage_format: lcov, coverage_path: "<relative path>" }
  mutation: { cmd: "<cmd>",       parser: <name>, tier_min: "High-risk" }

  # Optional design oracles — run only when the kind of change is inferred as `design`.
  visual_regression:  { cmd: "<cmd>", parser: <name> }
  a11y_scan:          { cmd: "<cmd>", parser: <name> }
  contract_check:     { cmd: "<cmd>", parser: <name> }
  component_contract: { cmd: "<cmd>", parser: <name> }
```

### Design oracles (optional, work-kind-shaped)

Design work is judged by **design oracles**, not the code gates alone. When the kind of change is inferred
as `design`, the engine unions the oracle gates listed in `.3powers/config/design-oracles.yaml` onto the
tier's gate set. Each oracle's *tool* is adapter-supplied (`visual_regression`, `a11y_scan`,
`contract_check`, `component_contract`); a selected oracle the adapter doesn't declare — or whose tool
isn't installed — is **quarantined**, never silently passed. An adapter for a non-UI language may declare
none; design runs then quarantine every oracle (surfaced).

### Defect regression (work-kind-shaped)

When the kind of change is inferred as `defect`, the engine adds the core `defect_regression` gate: a
defect fix must ship a **failing regression test** — one marked `*regression*`/`*reproduce*` (by file name
or body) that references the defect's requirement id. This is a deterministic trace, so it needs no
adapter tool.

### Gate responsibilities

| Gate              | Owner   | Contract |
|-------------------|---------|----------|
| `format`          | adapter | `check_cmd` exits non-zero if code is not formatted (no writes). |
| `lint`            | adapter | `cmd` exits non-zero on a lint error. |
| `types`           | adapter | `cmd` exits non-zero on a type error. |
| `tests`           | adapter | `cmd` runs unit+integration+e2e and writes an **LCOV** report to `coverage_path`. |
| `diff_coverage`   | **core**| Computed from the LCOV report ∩ `git diff` changed lines. |
| `mutation`        | adapter | `cmd` runs the language mutation tool; opt-in via `--mutation`. |
| `spec_conformance`| **core**| Deterministic trace: every requirement ID in the spec is referenced by ≥1 test. |

The **language-agnostic gates** (`diff_coverage`, `spec_conformance`, the defect regression gate, and the
supply-chain scanners — secret/dependency/SAST — plus provenance) live in the core; only the
language-specific gates come from the adapter.

### Conventions

* **Command exit code is the contract.** `0` = pass, non-zero = fail. The engine
  captures stdout/stderr tails as actionable findings.
* **Coverage is LCOV.** Every adapter's test command must emit LCOV so the core's
  diff-coverage works identically across languages.
* **Tests reference requirement IDs by mention** — e.g. `describe("VUTIL-FR-001 …")`.
  The conformance trace is a deterministic text match, so it is language-neutral.
* **`shell: true` opts a gate into a shell.** A gate command normally runs argv-style;
  set `shell: true` on the gate to allow shell features like a pipe or `$(…)` (e.g. Go
  converts its coverprofile to LCOV with a `go test … && gcov2lcov …` pipeline).

## Reference adapters

* `typescript/` — built and exercised end-to-end (runs the sample).
* `python/` — also the adapter that lets 3Powers gate its own engine code at the
  strictest tier (the engine gates its own code).
* `go/` — the third reference adapter, proving the contract is truly language-agnostic:
  adding a language is "add a manifest", with no change to the core.
