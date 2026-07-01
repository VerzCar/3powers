# Plan 015 — work-kind-shaped gates: defect-flow (FR-008), design oracles (FR-009), a third (Go) adapter

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md) and [`plan/014-hardening-core.md`](014-hardening-core.md)
> first (this plan builds directly on plan 014's work-kind inference). Spec:
> [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) §5 (FR-008), §7 (FR-009 design oracles), §8/§10
> (adapter contract, FR-027/NFR-007). Use `uv run python -m threepowers.cli` for the CLI — the globally
> installed `3pwr` alias is stale.

## Context

Plan 014 shipped **work-kind inference** (`workkind.classify` → `kinds` + `suggested_tier`, recorded by
`3pwr classify` / `3pwr run`) but deliberately deferred the **per-kind gate shaping** — the part where an
inferred kind actually changes the *gate set*. Plan 015 delivers that shaping for the two kinds the spec
calls out, plus a third reference adapter:

- **FR-008 (defect):** a defect fix must ship a **failing regression test** as an acceptance criterion.
- **FR-009 (design):** design work is judged by **design oracles** — visual-regression, accessibility,
  structural (API/schema contract), component-contract — not by the standard code gates alone.
- **Third adapter (Go):** a third reference language adapter, proving the adapter contract is truly
  language-agnostic (FR-027/NFR-007) beyond TS + Python.

The hinge already exists: `workkind.classify` (plan 014) infers `defect`/`design`; this plan wires that
inference into `gates.run_gates` so the gate set adapts. The inference still only *shapes* gates — the human
sign-off (FR-006/037) is untouched.

## Scope

**In (build + unit-test now):**
1. **Wire work-kind into `run_gates`** — the plumbing plan 014 deferred: `run_gates(..., work_kind=…)`
   augments the tier's gate list per kind; `3pwr gate run --work-kind <k>`; `3pwr run` passes the inferred
   kinds to the verify step. Recorded in the verdict for traceability.
2. **FR-008 defect-flow** — when `work_kind` includes `defect`, require a **regression test** acceptance
   criterion; fail (class `missing_regression_test`) if absent. Author-side guidance in the oracle command.
3. **FR-009 design oracles** — a `design-oracles.yaml` config + optional adapter-declared design gates
   (`visual_regression`, `a11y_scan`, `contract_check`, `component_contract`); `work_kind=design` unions
   them into the gate set; **quarantine** (never silently pass) when the adapter doesn't declare a tool
   (NFR-015); verdict failure classes. The concept + config + selection + quarantine are offline-testable.
4. **Go reference adapter** — a declarative `.3powers/adapters/go/adapter.yaml` + a conformance-suite test.

**Out (→ residual):** live design scanners for a real UI project (playwright/axe/schema-diff are
adapter-supplied — needs those tools + a UI sample); the Go adapter's *live* gate run (needs a Go
toolchain); model-driven eval (FR-050); fuller-A3 dual-headless; catalog publishing; cross-platform CI.

## Decisions (recommended)

| Area | Decision | Why |
|---|---|---|
| Work-kind → gates | `run_gates` unions per-kind gates onto the tier's base gate list; never removes a tier gate; work-kind recorded in the verdict | Inference shapes, never weakens (FR-032); traceable |
| Defect regression | Detect a regression test by convention — a test named/marked `*regression*` (or a spec acceptance criterion tagged `[regression]`) referencing the defect's requirement; missing → `missing_regression_test` | Deterministic, language-agnostic (mirrors the conformance trace); no model call (NFR-001) |
| Design oracles | Adapter-declared optional gates + a `design-oracles.yaml` catalog of kinds→gate names; core selects by work-kind and **quarantines** a missing tool | Keeps the core language-agnostic (NFR-007); design tools are adapter-supplied; quarantine surfaces gaps (NFR-015) |
| Go coverage | The Go adapter's `tests` gate emits **lcov** (e.g. `go test -coverprofile=… && gcov2lcov …`) so the existing `covdiff` diff-coverage works unchanged; declare `gcov2lcov` as an adapter dependency | Reuse `covdiff.parse_lcov` (FR-029) — no core change for a new language |
| Self-application | New pure predicates (regression detection, design-gate selection) hold High-risk coverage; the engine's own spec is not a defect/design change, so its self-application gate set is unchanged | NFR-006 stays green; work-kind shaping only triggers for defect/design runs |

## Implementation (sequenced)

### 0. Work-kind → `run_gates` (the deferred hook)
- `engine/src/threepowers/gates.py::run_gates(...)` — add `work_kind: list[str] | None = None`. After
  `required = list(tcfg.get("gates", []))`, call a new `_augment_gates(required, work_kind, manifest, cfg)`
  that unions per-kind gates (WS2/WS3). Record `work_kind` in the verdict (`Verdict` / details) for trace.
- `engine/src/threepowers/cli.py::cmd_gate_run` — add `--work-kind` (repeatable); pass to `run_gates`.
- `3pwr run` — the verify step should carry the inferred kinds; pass them where the gate suite is invoked
  (record already lands in the `run` ledger entry from plan 014).

### 1. FR-008 defect-flow — `conformance.py` (or a small `defect.py`) + gates + lifecycle
- A predicate `has_regression_test(test_roots, spec_id) -> bool` — reuse `conformance._iter_test_files` /
  `_iter_req_ids`; a regression test = a test file/name matching `*regression*`/`*reproduc*` that references
  a spec requirement, OR a spec acceptance line tagged `[regression]`.
- In `run_gates`, when `work_kind` includes `defect`, run the check and emit `failure("missing_regression_test", …)`
  + a `defect_regression` GateResult (pass/fail) when absent. Reuse `verdict.failure`.
- `.specify/workflows/3powers/lifecycle.yml` + `.specify/extensions/3powers/commands/3pwr.oracle.md` —
  for a defect, guidance to author the failing regression test **first** (Phase A), so the fix is proven.
- Tests: `test_defect.py` — defect run without a regression test fails (`missing_regression_test`); with one,
  passes; non-defect work is unaffected.

### 2. FR-009 design oracles — config + adapter contract + selection + verdict
- `.3powers/config/design-oracles.yaml` — kinds → gate name + description + threshold, e.g.
  `visual_regression → {gate: visual_regression, min_similarity: 0.98}`, `accessibility → {gate: a11y_scan,
  standard: WCAG-2.1-AA}`, `structural → {gate: contract_check}`, `component_contract → {gate: component_contract}`.
- `.3powers/adapters/CONTRACT.md` + the TS adapter (`.3powers/adapters/typescript/adapter.yaml`) — declare
  the *optional* design gates a language supplies (e.g. TS → `visual_regression: {cmd: "npm run test:visual",
  parser: playwright}`, `a11y_scan: {cmd: "npx axe …", parser: axe}`). Language-agnostic core unchanged.
- `run_gates` (`_augment_gates`) — when `work_kind` includes `design`, union the design gates the adapter
  declares; a selected design gate whose adapter tool is absent → **quarantine** (`scanners._quarantine`
  pattern, NFR-015), never a silent pass. New gate runners dispatch via the adapter (`adapters.run_cmd`).
- `verdict.py` — failure classes `visual_regression`, `a11y_violation`, `contract_break`, `component_contract`
  (via `failure(...)`, FR-034).
- Tests: `test_design_oracles.py` — a fake adapter declaring a design gate → selected on a design run;
  missing tool → quarantined; verdict carries the design failure class. (Live playwright/axe = residual.)

### 3. Go reference adapter — `.3powers/adapters/go/adapter.yaml` + test
- Manifest: `language: go`, `detect: ["go.mod"]`, `test_roots: ["."]`, `property_test_lib: rapid`, gates:
  `format {check_cmd: "gofmt -l ."}`, `lint {cmd: "golangci-lint run ./... || go vet ./..."}`,
  `types {cmd: "go build ./..."}`, `tests {cmd: "go test -coverprofile=cover.out ./... && gcov2lcov -infile
  cover.out -outfile coverage/lcov.info", coverage_path: "coverage/lcov.info"}`, `mutation {cmd: "go-mutesting
  ./...", tier_min: High-risk}`. (Confirm exact flags against installed tools when a Go toolchain is present.)
- `.3powers/config/dependencies.yaml` — add Go toolchain components (`go`, `golangci-lint`, `gcov2lcov`,
  `go-mutesting`) as `on_drift: warn` (optional; quarantine if absent).
- Tests: extend `engine/tests/test_adapters.py` — Go adapter loads + `detect` picks it on a `go.mod` fixture
  (pure YAML; no Go toolchain needed for the load/detect test).
- A tiny `examples/` Go sample is optional (nice for a live end-to-end once Go is installed) → can defer.

## Verification (definition of done)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)          # + test_defect / test_design_oracles / go adapter
# High-risk self-application stays green (NFR-006):
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)

# FR-008: a defect run requires a regression test.
3pwr gate run --path <proj> --work-kind defect --spec <spec> --tier High-risk   # fails without a regression test
# FR-009: a design run selects the design oracles (quarantined if the adapter lacks the tool).
3pwr gate run --path <proj> --work-kind design --spec <spec> --tier Standard
# Go adapter is detected on a go.mod project:
3pwr gate run --path <go-proj> --adapter go --spec <spec> --tier Standard        # needs a Go toolchain (else quarantines)
```

**Done when:** `run_gates` shapes the gate set by inferred work-kind (never weakening a tier gate, recorded
in the verdict); a **defect** run fails without a regression test (`missing_regression_test`) and passes with
one; a **design** run selects the configured design oracles and **quarantines** a missing adapter tool
(never silently passes); the **Go adapter** loads + auto-detects on `go.mod` (a live Go gate run works where
a Go toolchain is installed); the engine self-applies green at High-risk; STATUS flips FR-008/FR-009 ✅ and
notes the third adapter.

## Residual (→ later / external)
- Live design scanners (playwright/axe/schema-diff) for a real UI sample; a runnable Go example for a live
  end-to-end (needs a Go toolchain); model-driven eval (FR-050); fuller-A3 dual-headless (codex/gemini);
  catalog publishing; cross-platform CI (NFR-003).
