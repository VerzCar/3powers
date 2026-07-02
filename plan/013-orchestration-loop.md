# Plan 013 — Orchestration front-end (`3pwr run`): the automated lifecycle loop

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md), then the spec
> [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) §6 (lifecycle), §3 (A1/A3), and FR-006/037 (the two
> mandatory human gates). Builds on the judiciary from plans 008/011/012 and Spec Kit's `workflow run`.

## Context

The eight-stage lifecycle existed only as parts: Spec Kit drove the executive stages (`/speckit.*` or
`specify workflow run`) and the 3powers extension wired the judiciary in as hooks + `3pwr` commands. There
was **no single automated front-end** that chains all stages, pauses for human commitment, streams
progress, and toggles auto/commit — the playbook §26 "Orchestration Loop", automated.

Plan 013 adds `3pwr run`: one command drives the whole loop with a **live progress tracker**, delegating the
agent work to Spec Kit's `workflow run` (A1 — no new harness, no model calls from the engine, A3). In
**auto** mode it auto-continues past the intermediate review gates but **always** stops at the two
spec-mandated human gates — `review-spec` (a human approves the spec, **FR-006**) and `signoff` (a human
signs off on the evidence + residual, **FR-037**); **commit** mode stops at every gate. Nothing ships
unreviewed — the separation-of-powers thesis (§1) is preserved.

## What shipped

- **`.specify/workflows/3powers/lifecycle.yml`** — the full-cycle workflow: `specify → clarify →
  review-spec(gate) → plan → review-plan(gate) → tasks → oracle → implement → verify → review-verify(gate)
  → signoff(gate) → advance`, with per-step `integration:` and the two mandatory gates.
- **`engine/src/threepowers/orchestrate.py`** — the driver: `drive(runner, mode, on_event)` applies the
  auto/commit gate policy (pure, testable), `SimulatedRunner` (drives `--dry-run` + tests), `SpecifyRunner`
  (thin `specify workflow run`/`resume` wrapper, best-effort — the live executive dispatch is the A3
  residual), a stage-tracker renderer, and `MANDATORY_GATES = {review-spec: FR-006, signoff: FR-037}`.
- **`3pwr run`** (`cli.py`) — `3pwr run "<intent>" [--mode auto|commit] [--integration <x>] [--notify <cmd>]
  [--resume] [--status] [--dry-run] [--json]`. Streams progress; at a mandatory gate it pauses (interactive:
  prompts; else prints the `--resume` command), records the sign-off in the ledger, and continues; on a red
  verdict it stops + `--notify`s + suggests `3pwr observe signal` (FR-054). Resumable across invocations.
- **Ledger/lifecycle** — a `run` entry type (start / gate / complete) + `SpecState.pending_gate`, so
  `3pwr status` and `3pwr run --status` show where a run is paused and `--resume` knows where to continue
  (FR-011/019). Orchestration never enters the deterministic verdict (NFR-001).

## Decisions

| Area | Decision |
|---|---|
| Runner | Thin driver over `specify workflow run`/`resume`/`status` (A1); the engine makes no model call (A3). |
| Human gates | `review-spec` (FR-006) and `signoff` (FR-037) always stop; auto mode auto-approves only the intermediate gates; commit mode stops at all. |
| Sign-off | Recorded at each human gate via the existing `signoff` ledger entry, keeping the trust record intact. |
| Progress | A streamed stage tracker + a `--notify <cmd>` hook on gate/failure/completion; `--json` for machines; resumable via the ledger. |
| Failure | A red verdict stops for the human and suggests routing the lesson to a new spec round (`observe signal`, FR-054) — not an in-place patch. |
| Determinism | `3pwr run` is provisioning; the gates still run through `3pwr gate run` (NFR-001). |

## Verification

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)          # 211 tests incl. test_orchestrate.py
# High-risk self-application stays green (NFR-006): (trust-spine --paths, mutation + 100% diff-coverage)

# Offline demo (no live agents) — auto mode stops only at the two human gates:
3pwr run "add a rate limiter" --dry-run --no-input --spec-id DEMO      # ▶ streams; ⏸ review-spec (FR-006)
3pwr run --resume --dry-run --no-input --spec-id DEMO --approver you   # auto-approves review-plan/verify; ⏸ signoff (FR-037)
3pwr run --resume --dry-run --no-input --spec-id DEMO --approver you   # ✓ lifecycle complete
3pwr run --status --spec-id DEMO                                       # stage tracker from the ledger
```

**Done:** `3pwr run` drives the lifecycle with a live tracker, auto mode stops only at FR-006 + FR-037,
records resumable progress + sign-offs in the ledger, routes red verdicts to the human, and composes
`specify workflow run` without the engine calling a model or touching the deterministic verdict; 211 tests
green; the engine self-applies green at High-risk.

## Residual (→ later)
- **Fully-headless execution of the executive stages** (real agents doing spec/plan/implement) rides on the
  A3 dispatch leg (plan 011); interactive under Copilot (an IDE agent). The orchestration layer is complete
  and tested; the live executive dispatch is the documented residual.
- Notification transports (Slack/desktop) beyond the `--notify <cmd>` hook; a richer TUI; work-kind
  inference (FR-058) to auto-shape the oracle/gates per intent.
