# Implementation Plan — AUTOX (spec 014): Auto Full-Mode Readiness & the Run Error Contract

**Spec:** [`specs/014-auto-mode-readiness/spec.md`](spec.md) (Spec ID `AUTOX`, Standard, Draft).
Sequenced after PHASE (spec 013, draft — complementary, no shared files except docs). Trust-spine
impact: additive ledger content via existing append APIs; no change to `canonical`/`keys`/`ledger`/
`verify`.

> **Shape.** This plan dogfoods the PHASE methodology (PHASE-FR-004/006): ordered phases, each an
> independently executable one-session unit with a requirement trace, a declared file scope, an
> estimated context size against the ~110k-token advisory budget, and a handoff block naming what a
> fresh session must reload. Phases marked **[P]** have disjoint file scopes and no mutual dependency
> and may be delegated to parallel subagent sessions. Every phase ends with the engine green under its
> own gates (`uv run ruff check . && uv run mypy src && uv run pytest` in `engine/`).

**Standing handoff set (reload at the start of EVERY phase's fresh session):**
`specs/014-auto-mode-readiness/spec.md` · `.3powers/memory/constitution.md` · this plan (the phase
being executed) · the phase's declared file scope. Nothing else is assumed in context.

---

## Phase 1 — One readiness truth: unify init readiness with the run preflight

**Trace:** AUTOX-FR-001, FR-002, FR-003, FR-004, FR-005 · AUTOX-NFR-001
**Files:** `engine/src/threepowers/runpreflight.py`, `engine/src/threepowers/scaffold.py`,
`engine/src/threepowers/cli.py` (cmd_init readiness section ~423–691 + one new subcommand),
`engine/tests/test_runpreflight*.py`, `engine/tests/` onboarding/readiness tests
**Est. context:** ~55k tokens (cli.py is the heavy file; load only the init + preflight regions)

1. Extract the auto-run prerequisite checks into one shared, pure function set in `runpreflight.py`
   (signer resolvable — including validating an env-supplied key file: exists/readable/valid; coder
   integration configured + manifest exists + headless + CLI on PATH; oracle different-family or
   recorded `model_diversity` deviation). Each check returns `(id, ok, honest_label, fix)`; the
   authentication caveat ("present, authentication not verified") is part of the label (FR-004).
2. Make `3pwr run`'s existing preflight consume exactly this set (behavior preserved: same refusal, same
   fixes, EXIT_USAGE) and make init's readiness checklist append these items to its current five facts
   (FR-001/002). Drift is now impossible by construction — one source (FR-002 *Property*).
3. Add the standalone re-runnable command (suggest `3pwr ready`; `--json` supported) = shared checks +
   a `deps-check` summary + one overall verdict; read-only, offline, distinct exit codes for
   ready/not-ready (FR-003). Never a gate.
4. Init's closing next-steps: emit the unmet items' fixes as exact commands in dependency order (key →
   roles → CLI install) derived from the same results (FR-005).
5. Tests name the FR ids (conformance): env-key-invalid at init; readiness↔preflight agreement property
   (same fake state → same verdict); `ready` exits/JSON; next-steps ordering.

**Done when:** a repo missing any auto prerequisite shows it at init, in `3pwr ready`, and in the run
refusal with identical fixes; gates green.

---

## Phase 2 — Failures become facts: ledger records, status surfacing, verdict parity

**Trace:** AUTOX-FR-006, FR-007, FR-011 · AUTOX-NFR-003
**Files:** `engine/src/threepowers/cli.py` (cmd_run failure branches ~2317–2375, `_native_verdict`
~1918–1939, `cmd_status`/`_run_status`), `engine/src/threepowers/orchestrate.py` (lifecycle derive),
`engine/tests/test_run*.py`, `engine/tests/test_orchestrate*.py`
**Est. context:** ~50k tokens

1. On every terminal failure branch (`dispatch_failed`, `artifact_missing`, `gates_red`,
   `verdict_error`), append a `run`/`failure` ledger entry — stage, class, attempts, bounded detail —
   via the existing append API before exiting (FR-006). Mirror the existing `run`/`gate` append style.
2. Teach `lifecycle.derive`/status rendering to surface the newest failure record: `3pwr run --status`
   and `3pwr status` show "failed at <stage> (<class>)", cleared once a later record passes that stage
   (FR-007). Distinct from `⏸ paused`.
3. Verdict parity: make the in-run Verify path append the verdict entry exactly as standalone
   `cmd_gate_run` does (FR-011) — same content, no byte changes to the verdict itself (NFR-003).
4. Tests: per failure class, ledger tail asserts stage+class and `3pwr verify` green; status shows and
   then clears the failure; in-run vs standalone verdict entries are equivalent.

**Done when:** no failure mode exits without a signed trace, and both status commands can say "failed
at X"; existing ledgers still verify.

---

## Phase 3 — Nothing is lost: persisted transcripts with redaction

**Trace:** AUTOX-FR-008 · AUTOX-NFR-002
**Files:** `engine/src/threepowers/runner.py` (`dispatch_agent` ~113–127, `CliAgentRunner.dispatch`,
streaming path), a small new `engine/src/threepowers/transcripts.py` (path layout + redaction),
`engine/tests/test_runner*.py`
**Est. context:** ~40k tokens

1. Tee every stage attempt's stdout/stderr to `.3powers/runs/<spec-id>/<NNN>-<stage>-attempt<k>.log`
   (the `runs/` dir already exists from init) — including the streaming path, which today captures
   nothing (`capture_output=not stream`). Keep the 400-char detail excerpt behavior on top.
2. Redact before write: collect credential-shaped env values (the pass-through allowlist the runner
   already knows about) and replace their occurrences with `«redacted»` (NFR-002). Pass-through to the
   child process is untouched.
3. Failure messages and `--json` gain the transcript path (ties into Phase 2's detail field — the
   ledger record stores the path, not the content).
4. Tests: streamed + captured runs both leave transcripts; seeded fake secrets never appear in any
   persisted byte; path printed on failure.

**Done when:** any attempt's output is on disk, secrets never are, and every failure names the file.

---

## Phase 4 — The contract: exit codes, JSON statuses, and checkpoint-independent resume

**Trace:** AUTOX-FR-009, FR-010
**Depends on:** Phase 2 (resumes read the run-progress/failure records it introduced).
**Files:** `engine/src/threepowers/cli.py` (exit constants + cmd_run terminal branches + `--resume`
~2217–2230), `engine/src/threepowers/orchestrate.py` (`resume_start_index` ~142–153,
`last_checkpoint_step`), `engine/tests/test_run*.py`
**Est. context:** ~45k tokens

1. Define the terminal contract: `0` completed · new distinct code for paused-at-human-gate · `1`
   gates-red · dedicated code for setup/dispatch failure · `2` stays usage. One documented (status,
   exit-code) pair per outcome (FR-009 *Property*); JSON `status` strings frozen as named in the spec.
2. Record per-stage completion in the ledger at stage success (lightweight `run`/`stage` entry, additive)
   so `resume_start_index` = max(gate-approved, committed checkpoint, **recorded completion**) — resume
   now works with auto-commit off, given an intact working tree (FR-010). Completed stages never
   re-dispatch; the no-progress case gets the honest "nothing to resume — start fresh with …" message.
3. Tests: exit-code table exhaustively asserted per branch; `--no-auto-commit` failure at stage k
   resumes at k; nothing-to-resume message.

**Done when:** a script can branch on exit codes alone and a failed `--no-auto-commit` run resumes.

---

## Phase 5 **[P]** — Docs & config sweep for the end user

**Trace:** AUTOX-FR-012, FR-013, FR-014, FR-015 · AUTOX-NFR-004
**Depends on:** Phases 1–4 behaviorally (documents what they built); no shared source files → may run
as a parallel session against their merged result.
**Files:** `docs/getting-started.md`, `docs/troubleshooting.md`, `docs/cli-reference.md`,
`.3powers/config/roles.yaml` + its scaffold copy under `engine/src/threepowers/scaffold/`,
`docs/STATUS.md` (single status touch at delivery)
**Est. context:** ~35k tokens

1. Getting-started: lead with the linear end-user path — install → `3pwr init` (own repo) → key export
   → roles + agent CLI (auth belongs to the provider's CLI) → `3pwr ready` → `3pwr run --mode auto` →
   what success and the two human gates look like; keep the maintainer/gates-only walkthrough after it;
   fix the stale version string (FR-012).
2. Troubleshooting: one entry per failure class keyed to the exact CLI phrases ("dispatch failed at",
   "artifact missing at", "gates red", timeout detail, "no paused run to resume") with cause, fix, and
   the resume command (FR-013).
3. CLI reference: the exit-code/JSON-status table and the transcript location, marked stable (FR-014).
4. Sweep Spec-Kit-era language from shipped `roles.yaml` (both copies) and any template stragglers
   (FR-015, extends DOCX). Update STATUS once, at delivery (NFR-004).

**Done when:** a newcomer path exists end-to-end, every printable failure phrase has an entry, and no
shipped config presents Spec Kit as current.

---

## Verification (whole feature)

- **Gates:** `(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)` green after every
  phase; self-application `3pwr gate run --path engine --adapter python --spec
  specs/014-auto-mode-readiness/spec.md --tier Standard` green at delivery; trust-spine module coverage
  stays ≥95% (they should be untouched — assert no diff under `canonical|keys|ledger|verify`).
- **Conformance:** every AUTOX-FR id appears in ≥1 test name or the recorded doc review (AUTOX-SC-007);
  two-way requirement↔task coverage once the tasks artifact is authored from this plan.
- **End-to-end:** with the sim runner, drive each failure class and assert ledger record + status +
  transcript + exit code; run the readiness↔preflight agreement property under a fake PATH/config.
- **Ledger compatibility:** `3pwr verify` over a pre-AUTOX ledger and over a new-format ledger both
  green (AUTOX-NFR-003).
- **Docs:** follow the getting-started path verbatim in a scratch repo (dry-run where a real agent CLI
  is absent); grep troubleshooting for each CLI failure phrase.

## Handoff — residuals

1. Agent-CLI *authentication* probing (needs a provider call) — out of scope by AUTOX Non-Goals; would
   need a per-manifest optional `auth_probe` command if ever wanted.
2. Model-driven repair of failed runs — separate concern, separate spec.
3. PHASE (013) integration: when phased dispatch lands, per-phase transcripts and per-phase completion
   records slot into the same `runs/` layout and `run`/`stage` entries — noted so the two specs converge.
