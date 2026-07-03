# Plan 018 — Native provider-agnostic executive (EXEC, spec 009)

**Spec:** [`specs/009-native-executive/spec.md`](../specs/009-native-executive/spec.md) (Spec ID `EXEC`,
Standard tier). **Supersedes** RUNX-FR-001/002; **amends** the epic (A1′/A2/A3′/§16 + Substrate line).

## Why

`3pwr run` dispatched through Spec Kit's `specify workflow run`, which cannot pilot an agent inside an IDE
(GitHub Copilot) — a terminal command has no agent to drive there. The epic's A1/A3 forced that coupling.
3Powers now **owns its executive**: a native, headless, provider-agnostic agent runner drives each stage
directly, runs the deterministic gate suite in-process, and stops only at the two human gates — no IDE,
no Spec Kit. The judiciary (gates/ledger/oracle/verify) is untouched; the engine still makes no model call.

## What was built

- **`.3powers/agents/{claude,codex,copilot,opencode,aider}.yaml`** — declarative agent-backend manifests
  (EXEC-FR-002/003/004), mirroring the language-adapter pattern. Enterprise model access is pass-through
  via env (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK/_VERTEX`, `HTTPS_PROXY`, …).
- **`engine/src/threepowers/agents.py`** — manifest loader + `build_command` (invocation from manifest
  alone; arg/stdin prompt delivery; model-flag insertion).
- **`engine/src/threepowers/prompts.py`** — engine-owned, deterministic stage-prompt assembly
  (EXEC-FR-005); the oracle prompt forbids reading the implementation (Phase-A independence).
- **`engine/src/threepowers/runner.py`** — `dispatch_agent` (monkeypatchable subprocess seam),
  `CliAgentRunner` (dispatches a stage to a headless agent; EXEC-FR-001/016), and `NativeRunner`
  (implements the `orchestrate.Runner` protocol; walks `LIFECYCLE_STEPS`; runs the gate suite in-process
  at the verdict step; EXEC-FR-006/007/008). Pure given injected callables (EXEC-NFR-004).
- **`engine/src/threepowers/config.py`** — `Settings.agents_dir`.
- **`engine/src/threepowers/runpreflight.py`** — `check_native` (a native run requires a headless coder
  agent + a different-family oracle agent, not Spec Kit; EXEC-FR-015).
- **`engine/src/threepowers/cli.py`** — `--runner {native,specify,sim}` (native is the default for a live
  run; `--dry-run` forces sim; EXEC-FR-013), `--agent`, `--spec`, `--tier`; `_native_runner` builds the
  dispatch + in-process-verdict closures; the preflight branches native vs. specify. The legacy
  `SpecifyRunner` stays behind `--runner specify` (SLIM/spec 010 removes it later).
- **Epic amendment** in `specs/3Powers_Spec_v0.2.md`: A1′, A3′, A2 reaffirmed, §16, and the Substrate line.
- **Tests** — `engine/tests/test_native_runner.py` (15 tests tracing `EXEC-FR-*`); the 4 RUNX Spec-Kit
  tests now select `--runner specify`.

## Non-goals delivered as residual (per spec)

Shape-(b) async hosted backend (EXEC-FR-011, e.g. Copilot coding agent via REST→Actions→PR) is *specified*
so it fits the contract, but only the synchronous local CLI backend is built here. Physical oracle
read-path isolation still runs through `3pwr oracle dispatch` (High-risk `advance` enforces it); the native
oracle stage routes to the oracle agent/model. A live end-to-end run needs a real agent CLI on PATH.

## Verification

- `uv run pytest` → **481 passed**; `uv run ruff check .` clean; `uv run mypy src` clean.
- `test_native_runner.py`: manifests load + build invocations (EXEC-FR-002/003/004); prompt assembly is
  deterministic (EXEC-FR-005); `NativeRunner` drives a full lifecycle with a **fake agent**, stopping at
  the two mandatory gates and completing (EXEC-FR-001/006/007/008, NFR-004); a dispatch failure and a
  "verdict cannot run" are reported distinctly from a real gate-red (EXEC-FR-016); native preflight covers
  each failure mode (EXEC-FR-015); end-to-end `3pwr run` (default native) dispatches with a headless agent
  and stops at the spec gate, then resumes to run the gate suite in-process at Verify (EXEC-FR-013/001/006).
- **Follow-up (needs the signer key, done by the maintainer):** re-seal the amended epic —
  `3pwr signoff --stage spec --spec-id 3PWR --spec specs/3Powers_Spec_v0.2.md` (SLOCK) — and sign off EXEC:
  `3pwr signoff --stage spec --spec-id EXEC --spec specs/009-native-executive/spec.md`.
