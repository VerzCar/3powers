# Plan 005 — SAST Gate & Prompt/Constitution Eval Harness (complete v0.5)

**Status**: Implemented & verified — **completes v0.5**. SAST runs (semgrep + local ruleset; green on
the engine, ruleset catches a planted `shell=True`); `3pwr eval` passes 4/4 on the real
constitution/commands and blocks on a planted regression. Self-application green at Standard (SAST
included; 26 requirements traced; 79 engine tests; ruff+mypy clean). Builds on plans 001–004; v1.0 next.

## Context — why

Per §17, v0.5 is "Full judiciary": remaining gates (SAST, dependency, secret — the latter two shipped
in plan 002), build provenance + deploy gate + residual review (plan 004), the full risk-tier config
(present since plan 001), and the **prompt/constitution evaluation harness (FR-050)**. Two items remain:
**SAST** and the **eval harness**. Implementing both completes v0.5.

## Scope

**In:** a **SAST** core gate (semgrep against a local, offline ruleset; quarantine when absent) ·
the **eval harness** (FR-050) — treat the constitution, commands, and role config as versioned
software with an eval set, and block on a regression.

**Out → v1.0 (plan 006+):** brownfield Stage Zero (§12), observe/feedback loop (§13),
emergency/deviation paths (§14), catalog distribution, a third reference adapter, the mutmut
src-layout runner, and the harness-limited items (work-kind inference FR-058, context strategy
FR-060/061).

## Decisions

| Area | Decision | Rationale |
|---|---|---|
| **SAST tool** | **semgrep** against a **local, committed ruleset** (`.3powers/config/semgrep-rules.yml`); **quarantine** (skip + surfaced finding) when semgrep is absent | A local ruleset keeps SAST deterministic and offline (NFR-004); quarantine keeps the suite runnable without the tool (NFR-015), like the other scanners. `--config auto` is avoided (needs network/login). |
| **Eval harness** | A **deterministic** eval set (`.3powers/eval/cases.yaml`) of content assertions over the constitution/commands/roles; `3pwr eval` fails on any regression | FR-050's intent — prompts/constitution are versioned software that must not silently lose a non-negotiable. Model-driven eval is a richer future layer; the deterministic set is offline, fast, and self-applicable. |

## Workstreams

1. **SAST gate (FR-026 / §8).** `scanners.sast_scan(target, rules)` runs
   `semgrep scan --json --config <local rules> <target>`; findings (rule, file, line) → `fail`;
   semgrep absent or erroring → quarantine. Ship a small offline ruleset
   (`.3powers/config/semgrep-rules.yml`) covering generic dangerous patterns (e.g. `eval`,
   `subprocess(..., shell=True)`). Wire into `GATE_ORDER` (after mutation, per §8), the Standard +
   High-risk tiers, the verdict schema enum, and `gates.py` (dispatch + a `sast_finding` failure class).
2. **Eval harness (FR-050).** `evals.py` loads `.3powers/eval/cases.yaml` (each case: `file`,
   `must_contain`, `must_not_contain`) and checks the constitution, the `/3pwr.*` command/agent files,
   and `roles.yaml`. `3pwr eval` runs the set and exits non-zero on any failure — so a change that drops
   a non-negotiable (e.g. the oracle's "different model family" rule) is blocked. Self-applicable.
3. **Tests + self-application + docs.** Unit/CLI tests (each citing its FR id); keep
   `3pwr gate run --path engine` green (SAST quarantines or passes on the clean engine); run `3pwr eval`
   on 3Powers' own prompts/constitution; update schemas, `AGENTS.md`, `CLAUDE.md`, and the scoped engine
   spec. Commit on `plan-005-*`.

## New `3pwr` surface

```
3pwr eval [--cases <cases.yaml>]      # prompt/constitution eval set; blocks on regression (FR-050)
# `sast` runs inside `3pwr gate run` at Standard+ (semgrep; quarantines if absent)
```

## Verification

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # engine green
3pwr eval                                                                 # constitution/commands intact
3pwr gate run --path engine --adapter python --spec specs/002-engine-trust-spine/spec.md \
              --tier Standard --base 3e20aad --no-ledger                   # self-application green
# Negative: a planted eval/shell=True in a scanned dir -> sast FAIL (if semgrep present);
#           deleting "different model family" from the oracle command -> `3pwr eval` FAIL.
```

## Out of scope (→ v1.0)

Brownfield (§12), observe (§13), emergency/deviation (§14), catalog packaging as a Spec Kit
extension/preset, a third adapter, and the model-driven layer of the eval harness.
