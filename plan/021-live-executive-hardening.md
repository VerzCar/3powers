# Plan 021 — Live executive hardening (RUNLIVE, spec 011)

**Spec:** [`specs/011-live-executive-hardening/spec.md`](../specs/011-live-executive-hardening/spec.md)
(Spec ID `RUNLIVE`, Standard). Sequenced after EXEC (plan 018) + SLIM (plan 019). Introduces **no new
trust-spine primitive** — it makes the native executive's dispatch honest, verifiable, resumable, and
provable end-to-end. The thesis invariant *a model never produces or alters the verdict* is preserved: none
of this feature enters the deterministic gate suite or the ledger's verdict.

## Why

After EXEC + SLIM, `3pwr run` drives headless agents directly, but the executive is still an MVP: every
runner path is tested with a *fake* agent, "agent exited 0" counts as success (the whole diff is the
"artifact"), there is no dispatch timeout/retry/streaming, no committed checkpoints between stages, and no
backend for agents that expose only an *asynchronous hosted* run. RUNLIVE closes those gaps so an
unattended `3pwr run` produces trustworthy software.

## What was done

**Per-stage artifact contracts (RUNLIVE-FR-001/002/003) — new [`artifacts.py`](../engine/src/threepowers/artifacts.py).**
Each action stage declares the artifact it must produce; `verify(contract, produced)` is a **pure**
function of the contract and the set of repo-relative paths the stage produced. Three engine-owned hard
contracts — `specify` → a spec file (`specs/<feature>/spec.md`), `oracle` → oracle tests
(`tests/oracle/…` / `oracle-tests/…`), `implement` → a non-empty change — and a **lenient fallback** for
every other stage (`verify(None, …)` never blocks, FR-003). A stage that produced nothing, or only an
off-target change, is a **named artifact failure** (`artifact_missing`), distinct from a gate-red and never
a silent pass. Stage prompts now name where to write the artifact so a real agent hits the contract.

**Robust, observable dispatch (RUNLIVE-FR-004/005/006) — [`runner.py`](../engine/src/threepowers/runner.py).**
`dispatch_agent` gained a `stream` flag (inherit the terminal on a TTY for live progress) and keeps its
timeout → rc 124 termination (FR-004, never a hang). New pure policy helpers `dispatch_with_retry` (a stage
is tried at most `retries + 1` times; a success is never retried — FR-005) and `run_stage` (retry → artifact
verify → a `StageResult` carrying agent, resolved model, attempts, duration, artifact summary, outcome).
`NativeRunner` collects one `StageResult` per dispatched stage; `3pwr run --json` emits them (FR-006).
Timeout/retry are configurable (`--timeout`/`--retries`, else `onboarding.yaml` defaults; `config.py`
`dispatch_timeout()`/`dispatch_retries()`).

**A gated live end-to-end proof (RUNLIVE-FR-007) — [`tests/e2e/test_live_run.py`](../engine/tests/e2e/test_live_run.py).**
An **opt-in** test drives one real headless agent through the whole lifecycle to a green verdict; it is
skipped (never failed) without `THREEPOWERS_LIVE_E2E=1` + an agent CLI on PATH, and makes no network call in
that state. Two deterministic **property** tests assert the engine opens no network/HTTP client (its only
agent seams are the injectable subprocess dispatch + hosted command) and that a native run advances through
the injected seam alone — so the default suite performs zero outbound model calls.

**Async hosted backend (RUNLIVE-FR-008/009) — new [`hosted.py`](../engine/src/threepowers/hosted.py).**
`HostedAgentRunner` satisfies the same `dispatch(step, stage)` contract as `CliAgentRunner` by **triggering**
a hosted run, **polling** it to completion, and **collecting** the produced branch/PR into the working tree
— so the same in-process gate suite judges it identically (FR-008, NFR-003). It is **provider-neutral**
(NFR-005): trigger/poll/collect are *manifest-declared commands* with `{placeholder}` substitution, so a
Copilot shop wires them to `gh api` / `gh pr checkout` with no vendor code in the engine. Reference manifest
[`copilot-hosted.yaml`](../.3powers/agents/copilot-hosted.yaml) (seeded by `3pwr init`). Credentials are
inherited via the child environment and never interpreted, logged, or stored (FR-009). `_make_agent_runner`
in `cli.py` selects the backend from the manifest `mode`.

**Commit checkpoints + resume-from-checkpoint (RUNLIVE-FR-010) — `runner.py` + `orchestrate.py` + `cli.py`.**
With auto-commit enabled, each successful stage's produced paths are committed as
`3pwr(<spec-id>): <step>` (`commit_checkpoint`, scoped to the produced paths — never a blanket `add`), and a
signed `run`/`checkpoint` entry records it in the ledger. A `--resume` re-enters at
`resume_start_index = max(after the approved gate, after the last committed checkpoint)`, so a mid-run
failure continues from the next uncompleted stage **without re-dispatching a committed one** (the property:
a stage succeeds at most once across a run and its resumes). `--resume` now also works after a non-gate
(dispatch/artifact) failure. `--no-auto-commit` opts out (resume falls back to the segment).

**Diagnostics.** `Outcome`/`RunResult` carry a finer `outcome` + `detail`; `3pwr run` reports
`artifact_missing` distinctly from a bare `dispatch_failed` and from a real `gates_red`, each with the named
stage and an actionable next step; all terminal `--json` payloads carry the per-stage `stages` array.

## Verification

- `uv run pytest` → **498 passed, 1 skipped** (the skipped one is the opt-in live proof). New/extended
  tests: `tests/test_artifacts.py` (FR-001/002/003), `tests/test_hosted.py` (FR-008/009),
  `tests/test_native_runner.py` (FR-004/005/006/010 + hosted wiring), `tests/e2e/test_live_run.py`
  (FR-007). Every RUNLIVE FR has ≥1 linked verification (SC-006).
- `uv run ruff check .` clean; `uv run ruff format --check` clean on all RUNLIVE files; `uv run mypy src`
  clean.
- The opt-in live proof skips cleanly with no agent (`THREEPOWERS_LIVE_E2E=1 THREEPOWERS_LIVE_AGENT=absent`
  → skipped, never failed) — SC-003's "no agent → skipped, no network".
- **Self-application (engine gates its own change), Standard:**
  `uv run python -m threepowers.cli --root .. gate run --path . --adapter python --spec
  ../specs/002-engine-trust-spine/spec.md --tier Standard --base HEAD --no-ledger` → the RUNLIVE change is
  clean on the gates it owns: **`diff_coverage` 91.68% ≥ 80**, **`gate_gaming` ✓** (no new
  suppressions — the `# type: ignore`/`# noqa` were designed out), tests/lint/types ✓, sast/dependency/secret
  ✓. `format` (3 pre-existing unformatted files: `runpreflight.py`, `test_headless_run.py`,
  `test_init_experience.py`), `spec_integrity` (the epic was edited after its seq-4 approval), and
  `spec_conformance` (5 epic FRs untraced) fail **identically on a clean HEAD** with the change stashed —
  i.e. they are pre-existing repo state, not introduced here. A follow-up (a DOCX-adjacent cleanup) should
  `ruff format` those three files and re-seal + re-approve the epic spec.

## Handoff — residuals

1. **The live proof is opt-in, not run in CI.** RUNLIVE-FR-007's real end-to-end run needs an agent CLI +
   credentials on the runner; the deterministic suite proves the mechanism (fake agent, no network) but a
   scheduled live smoke is still the fuller proof.
2. **The hosted backend's reference commands are illustrative.** `copilot-hosted.yaml` uses `gh api` paths
   that a deployment must adapt; a first real hosted run against a live Copilot coding-agent tenant is
   unproven here (offline by design).
3. **Streaming is child-stdio pass-through on a TTY**, not a parsed structured stream folded into the
   in-place tracker; the `--json` per-stage result is the machine-readable path.
4. **Per-stage spend telemetry (NFR-009)** is now implementable in the runner (it owns dispatch) but is not
   yet surfaced — the `StageResult` is the natural carrier.
5. **Pre-existing self-gate residue** (see Verification): format 3 files + re-seal the epic spec.
