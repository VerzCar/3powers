# Plan 020 — Headless executive dispatch (RUNX): honest `3pwr run` preflight, diagnostics, oracle diversity & per-stage provenance

> **Cold start:** the governing spec is [`specs/008-headless-run/spec.md`](../specs/008-headless-run/spec.md)
> (Spec ID `RUNX`, tier **Standard**); the task breakdown is
> [`specs/008-headless-run/tasks.md`](../specs/008-headless-run/tasks.md). Use
> `uv run python -m threepowers.cli` — the installed `3pwr` alias may be stale.

## Context

Running `3pwr run` in a fresh project failed immediately with `✗ gates red — stopped for your decision`
and an all-dots stage tracker — but no gate had run, and the message pointed at
`observe signal --kind incident`, the wrong remedy. RUNX makes `3pwr run` honest: a run that cannot start
says exactly what is missing and how to fix it, the oracle really resolves to a different family, and a
setup/dispatch failure is never mislabeled as a gate-red. It is the execution half of the init story whose
setup half is INITX (spec 007).

## Scope — in (delivered)

1. **Preflight before any dispatch** (RUNX-FR-009/012, NFR-004/005). A live run first verifies its
   prerequisites — the lifecycle workflow present, the Spec Kit CLI available, a headless coder
   integration, and a different-family oracle integration — and fails fast with a **named prerequisite +
   exact fix**, always naming the offline `--dry-run` and step-by-step alternatives. The accepted headless
   set is **configuration-driven** (`roles.yaml headless_integrations`); an IDE-only integration (copilot)
   is detected and a headless alternative named. `--dry-run` needs none of this.
2. **Honest diagnostics** (RUNX-FR-010/011). A dispatch/setup failure names the stage it failed at, exits
   with a status **distinct** from the gate-failure status (setup/usage `2` vs gate-red `1`), and never
   prints "gates red" nor routes to the incident/observe path. "Gates red" appears **only** when the
   deterministic gate suite actually returned `fail` at Verify; the tracker shows the stages reached.
3. **Oracle diversity within a run** (RUNX-FR-005/006). Same-family coder/oracle is refused by default and
   proceeds only under a signed, active model-diversity deviation — never silently; the oracle segment
   carries the oracle integration, and physical read-path isolation stays delegated to the delivered
   `oracle dispatch`.
4. **Per-stage provenance** (RUNX-FR-007, NFR-002). Each dispatched stage records a signed
   `run`/`dispatch` provenance entry (stage, integration, resolved model) bound into the hash-chained
   ledger; a resume records only its own segment (no re-dispatch — RUNX-FR-004). The ledger re-verifies
   offline.
5. **Non-regression guarantees** (RUNX-FR-003/008, NFR-001). Auto/commit gate policy and the High-risk
   require-dispatch + diversity enforcement at advance are unchanged; `drive` passes the runner's verdict
   through unchanged (dispatch is delivery only).

## Scope — out

- The fully-live headless dispatch of real agents remains the A3 residual — the live runner
  (`SpecifyRunner`) composes `specify workflow run`, but does not yet stream per-stage events; provenance
  is recorded per driven segment. This spec makes the *engine-side* orchestration, preflight, diagnostics,
  and attestation honest and complete; the live agent execution is exercised structurally + via the
  stubbed-live CLI path (RUNX-SC-007).
- Provisioning (workflow/agent/extension scaffolding, model pins) stays with INITX; RUNX consumes it.

## Decisions

| Area | Decision | Why |
|---|---|---|
| Failure exit codes | preflight/dispatch → `2` (setup/usage); gate-red → `1` | RUNX-FR-010 demands a status distinct from the gate-failure status |
| "gates red" text | emitted only on a real `fail` verdict at Verify | RUNX-FR-010/011 — never for a non-verdict failure |
| Headless set | config-driven `roles.yaml headless_integrations`, IDE-only list advisory | RUNX-NFR-005 — no integration hardcoded in run logic |
| Diversity | refuse same-family by default; signed deviation to proceed | RUNX-FR-006 (3PWR-FR-022 via FR-057) |
| Drift warning | preflight guides; init defaults (copilot) intentionally flagged | honest behavior — the user must configure headless integrations |

## What landed (files)

- **New:** `engine/src/threepowers/runpreflight.py`; `engine/tests/test_headless_run.py`;
  `specs/008-headless-run/tasks.md`.
- **Restructured:** `engine/src/threepowers/orchestrate.py` (`RunResult.verdict`/`is_gate_red`,
  `segment_actions`, dispatch-vs-gate-red `format_event`), `engine/src/threepowers/cli.py` (`cmd_run`
  preflight, provenance recording, gate-red/dispatch-fail split),
  `engine/src/threepowers/scaffold/config/roles.yaml` (`headless_integrations`).

## Verification (as run)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # all green; 462 tests (23 new RUNX)
3pwr coverage-check --spec specs/008-headless-run/spec.md --tasks specs/008-headless-run/tasks.md   # PASS (RUNX)
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/008-headless-run/spec.md --tier Standard --base main --no-ledger)
#   verdict PASS · diff_coverage 91.7% ≥ 80% · spec_conformance 17 requirements traced (all linked)
# Smoke: a live run with no headless integration now names the unmet prerequisites + fixes + offline
# alternatives and exits 2 — never "gates red", never the incident path.
```

## Residual

- `spec_integrity` is (correctly) skipped until a human seals the spec:
  `3pwr signoff --stage spec --spec-id RUNX --spec specs/008-headless-run/spec.md`.
- Full per-stage event streaming from the live `SpecifyRunner` (so provenance reflects confirmed, not
  segment-planned, dispatch) is the remaining A3 increment.
