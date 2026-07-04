# Plan 024 — Auto full-mode readiness & the run error contract (AUTOX, spec 014)

**Spec:** [`specs/014-auto-mode-readiness/spec.md`](../specs/014-auto-mode-readiness/spec.md) (Spec ID
`AUTOX`, Standard). The end-user-experience counterpart to EXEC (009) / RUNLIVE (011) and the
onboarding pair ONBRD (003) / INITX (007). **No trust-spine module change** — `canonical`/`keys`/
`ledger`/`verify` are untouched; all new ledger content is additive through the existing append APIs,
and `3pwr verify` stays green over old and new ledgers (AUTOX-NFR-003). Executed phase-by-phase from
the spec's own plan ([`specs/014-auto-mode-readiness/plan.md`](../specs/014-auto-mode-readiness/plan.md)),
one commit per phase.

## Why

Readiness at init and preflight at run were two disjoint mechanisms that could disagree (init could say
"ready" while `3pwr run --mode auto` still refused to start); an env-supplied signing key was trusted
unverified at init; no run failure was recorded anywhere, so no status command could say "failed at
stage X"; agent output was not persisted (≤400 chars in the message, nothing at all when streaming);
exit code 2 conflated usage with every dispatch/timeout/artifact/verdict-error failure and a paused
human gate exited 0; failure-resume worked only when auto-commit checkpoints existed; and the docs
walked the maintainer's gates-only path rather than an end user to a green auto run.

## What was done

**Phase 1 — one readiness truth (AUTOX-FR-001..005, NFR-001).**
[`runpreflight.py`](../engine/src/threepowers/runpreflight.py) gained `signer_prereq` (a resolvable,
*usable* signer — an env key that is missing/unreadable/malformed is reported with its exact fix, never
trusted silently) and `check_auto` — the ONE shared check set (signer → headless coder agent →
different-family oracle) that `3pwr init`'s readiness checklist, the new standalone **`3pwr ready`**
command (read-only, offline, `--json`, exits 0/1, plus a deps-check summary — never a gate), and the
live run's own preflight all consume. Drift is impossible by construction (the FR-002 property). A
present agent CLI carries the honest label "present; authentication not verified (offline check)"
(FR-004). Init closes with the unmet items' fixes as exact commands in dependency order (FR-005).

**Phase 2 — failures become facts (AUTOX-FR-006/007/011, NFR-003).** Every terminal failure branch of
`cmd_run` (`dispatch_failed`, `artifact_missing`, `gates_red`, and `verdict_error` — now reported
distinctly) appends a signed `run`/`failure` ledger record — stage, class, attempts, bounded detail,
transcript path — before exiting. `lifecycle.derive` surfaces the newest unresolved failure
(`failed_stage`/`failed_class`/`failed_at`), cleared by any later progress record, so `3pwr run
--status` and `3pwr status` show `failed at <stage> (<class>)` with its timestamp — distinct from
paused and in-progress; the latest failure wins, earlier ones remain as append-only history. The in-run
Verify (`_native_verdict`) now records its verdict exactly as a standalone `3pwr gate run` —
`verdicts/latest.json` + a signed `verdict` entry with requirement IDs — so a run's red or green is
never invisible to the trust spine.

**Phase 3 — nothing is lost (AUTOX-FR-008, NFR-002).** New
[`transcripts.py`](../engine/src/threepowers/transcripts.py): a per-run `TranscriptSink` (shared by the
coder and oracle backends) tees every stage attempt's stdout/stderr to
`.3powers/runs/<spec-id>/<NN>-<step>-attempt<K>.log` — the streaming path included, via a piped
line-pump in `dispatch_agent` that captures, persists, and echoes live, so a streamed run no longer
loses output. Credential-shaped environment values are redacted before any byte is persisted
(transcripts AND the 400-char excerpt that rides in failure records); pass-through to the child agent
process is untouched. Failure messages and `--json` name the transcript path; the ledger record stores
the path, never the content. Transcript files are excluded from produced-path detection so they can
never satisfy an artifact contract or be swept into a checkpoint commit.

**Phase 4 — the contract (AUTOX-FR-009/010).** The terminal machine contract is stable and documented:
`0` done · `1` gates_red (also rejected/aborted) · `2` usage · `3` paused-at-human-gate · `4`
setup/dispatch failure (`preflight_failed` / `dispatch_failed` / `artifact_missing` / `verdict_error`)
— paused is distinguishable from completed by exit code alone, one (status, exit-code) pair per
outcome, every branch asserted under test. Each successful stage now appends a lightweight
`run`/`stage` completion record, and `orchestrate.resume_start_index` reads the later of gate approval,
committed checkpoint, and recorded completion — so a failed `--no-auto-commit` run resumes at the
failed stage without re-dispatching a completed one; with no recorded progress the resume says
"nothing to resume" and names the fresh-start command.

**Phase 5 — docs & config sweep (AUTOX-FR-012..015, NFR-004).**
[`getting-started.md`](../docs/getting-started.md) now leads with the linear end-user path (install →
`3pwr init` in the user's own repo → key export → roles + agent CLI, with authentication named as the
provider's business → `3pwr ready` → `3pwr run --mode auto` → what success and the two human gates look
like), the maintainer walkthrough following; the pinned version literal is gone.
[`troubleshooting.md`](../docs/troubleshooting.md) carries one entry per failure class keyed to the
exact CLI phrases ("unmet prerequisites", "dispatch failed at", "agent timed out after", "artifact
missing at", "gates red", "verdict error at", "nothing to resume"), each with cause, fix, and the
resume command. [`cli-reference.md`](../docs/cli-reference.md) documents the exit-code/JSON-status
table and the transcript location as stable interfaces, plus the `ready` command. The Spec-Kit-era
language the DOCX sweep missed is gone: the repo's `roles.yaml` header rewritten to the native
agent-backend wording (+ `headless_integrations`), the constitution's header names the native lifecycle
stages, the eval set's two stale `.specify/` cases fixed (the eval set is green again: 5/5), and the
two "Spec Kit integration" CLI help strings corrected. `docs/STATUS.md` updated once, at delivery.

## Verification

- **Engine gates:** `uv run ruff check .` + `ruff format --check` ✅ · `uv run mypy src` ✅ (40
  files) · `uv run pytest` ✅ (577 passed, 1 skipped — the opt-in live e2e) — after every phase.
- **Conformance (AUTOX-SC-007):** every AUTOX-FR/NFR id appears in test docstrings across
  `test_auto_readiness.py` (FR-001..005), `test_run_errors.py` (FR-006/007/011),
  `test_transcripts.py` (FR-008, NFR-002), `test_run_contract.py` (FR-009/010), and
  `test_auto_docs.py` (FR-012..015, NFR-004 — the recorded documentation review, asserted
  structurally).
- **End-to-end:** each failure class driven with a fake agent asserts ledger record + status +
  transcript + exit code; the readiness↔preflight agreement property runs under a fake PATH/config;
  the `--no-auto-commit` resume proof re-dispatches only the failed stage.
- **Ledger compatibility (AUTOX-NFR-003):** `3pwr verify` green over ledgers with and without the new
  `run`/`failure` + `run`/`stage` records; verdict-bytes tests untouched.
- **Trust spine untouched:** no diff under `canonical.py` / `keys.py` / `ledger.py` / `verify.py`.
- **Self-application:** `3pwr gate run --path engine --adapter python --spec
  specs/014-auto-mode-readiness/spec.md --tier Standard` — **verdict PASS** (format/lint/types/tests
  green, diff_coverage 92.12% ≥ 80%, gate_gaming + spec_conformance green, 19 requirements traced);
  `3pwr eval` 5/5 (the eval set had been failing 4/6 on two stale `.specify/` paths — fixed by the
  FR-015 sweep).

## Handoff — residuals

1. Agent-CLI *authentication* probing (needs a provider call) — out of scope by the AUTOX non-goals;
   would need a per-manifest optional `auth_probe` command if ever wanted.
2. Model-driven repair of failed runs — a separate concern, separate spec.
3. PHASE (013) convergence: per-phase transcripts already share the `runs/` sink; a per-phase
   completion record (finer than the stage-level `run`/`stage`) can slot in when phased resume wants
   phase granularity.
