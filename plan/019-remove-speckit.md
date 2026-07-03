# Plan 019 — Remove the Spec Kit substrate (SLIM, spec 010)

**Spec:** [`specs/010-remove-speckit/spec.md`](../specs/010-remove-speckit/spec.md) (Spec ID `SLIM`,
Standard). Sequenced after EXEC (plan 018). Depends on the epic amendment A1′/A3′ landed by EXEC.

## Why

With the native executive delivered (EXEC), Spec Kit is dead weight: `3pwr run` no longer needs
`specify workflow run`, and the vendored prompts/workflows only served it. SLIM severs the runtime
dependency and prunes the artifacts, so 3Powers stands on its own. The judiciary (gates/ledger/oracle/
verify) is untouched.

## What was done

**Runtime de-coupling (SLIM-FR-001/002/003):**
- Removed `orchestrate.SpecifyRunner` + `_parse_specify_outcome`.
- `cli.py`: dropped `--runner specify` (now `native`|`sim`), the native-only preflight, `--workflow`, and
  the `--with-speckit` init path. `3pwr oracle dispatch` now authors via the native `CliAgentRunner` in the
  sanitized worktree (EXEC-FR-009), not `specify workflow run`.
- `runpreflight.py`: removed the Spec-Kit `check()` (workflow + `specify` CLI prereqs); `check_native` is
  the only preflight. `copilot` moved into the headless set (it has a headless CLI now); `aider` added.
- `scaffold.py`: removed `run_specify_init`, `install_speckit_extension`, `install_speckit_workflows`,
  `has_speckit`, `specify_installed`, the `_SPECKIT_*` dirs. Added `seed_agents` — `3pwr init` seeds
  `.3powers/agents/*.yaml`.
- `oracle.py` / `observe.py`: reframed "Spec Kit integration" → "agent backend" (SLIM-FR-006).

**Artifacts deleted (SLIM-FR-003/005):** `.specify/{workflows,extensions,integrations,scripts,
extensions.yml,*.json}`, the vendored `.github/{prompts,agents}/speckit.*` (22 files), and the bundled
`scaffold/{speckit,workflows}` trees. **Kept:** `.specify/memory/constitution.md`, `.specify/templates/`.

**Dependencies/docs (SLIM-FR-004, NFR-002):** removed the `spec-kit` entry from
`.3powers/config/dependencies.yaml` (+ the scaffold copy) and the `spec-kit` keyword from
`pyproject.toml`; reframed the load-bearing Spec-Kit claims in README/AGENTS/CLAUDE and the scaffold
constitution/roles/agents-template. Added [`docs/migration-remove-speckit.md`](migration-remove-speckit.md)
(SLIM-FR-008).

**Tests:** removed the Spec-Kit-only tests (`install_speckit_*`, `--with-speckit`, `SpecifyRunner`,
`_parse_specify_outcome`); rewrote the RUNX preflight tests to `check_native`; updated the scaffold
default oracle backend from `copilot` → `claude` (a real headless agent) and the affected assertions.

## Verification

- `uv run pytest` → **472 passed**; `uv run ruff check .` clean; `uv run mypy src` clean.
- `grep -rniE "specify workflow|SpecifyRunner|\.specify/workflows|with-speckit"` over `engine/src` returns
  no runtime code path (only historical comments) — SLIM-NFR-001.
- `3pwr run` / `3pwr oracle dispatch` / the suite run with `specify` absent from PATH — SLIM-FR-007.
- **Follow-up (needs the signer key, maintainer):** re-seal the amended epic and sign off EXEC + SLIM via
  `3pwr signoff --stage spec`; run the engine self-application gate (`3pwr gate run --path engine
  --adapter python --tier Standard`) to confirm SLIM-NFR-003 green end-to-end.

---

## Handoff — what's still missing & what the next spec should contain

### State after EXEC (018) + SLIM (019)
3Powers has a **native, provider-agnostic executive** (`3pwr run` drives headless agent CLIs directly,
gates in-process, stops at the two human gates) and **no Spec Kit dependency**. Suite green. The trust
spine, gate suite, and oracle independence are unchanged.

### Residuals (ordered by value)
1. **Live end-to-end run is unproven in CI.** All runner logic is tested with a *fake* agent (EXEC-NFR-004).
   No test drives a real `claude -p` producing a real spec/impl through a real gate run. Needs a gated,
   opt-in live smoke (skipped without an agent CLI + key on PATH).
2. **Prompt assembly + artifact collection are MVP.** `prompts.py` emits short stage instructions; the
   native runner treats "agent exited 0" as success and the whole working-tree diff as the artifact. There
   is no per-stage artifact validation (did `specify` actually write a spec? did `oracle` write tests into
   `oracle-tests/`?), no structured output parsing, no streaming of agent output to the tracker, and no
   retry/timeout policy surfaced to the user.
3. **Shape-(b) async hosted backend (EXEC-FR-011) is specified, not built.** The GitHub Copilot coding
   agent (REST → Actions → PR) — the path for enterprise Copilot shops that can't run a local headless CLI
   — needs a concrete backend: trigger, poll, collect the branch/PR as the stage artifact, then judge it.
4. **Per-stage commit + resume ergonomics.** INITX-FR-006 auto-commit exists as config but the native
   runner doesn't commit each stage; a mid-run failure resumes by re-dispatching the segment, not from a
   committed checkpoint.
5. **Doc sweep + STATUS rewrite.** Headline Spec-Kit claims are fixed, but narrative mentions remain in
   `CLAUDE.md`, `README.md`, and especially `docs/STATUS.md` (the §17 matrix still describes the Spec-Kit
   dispatch as the executive). STATUS should be rewritten to reflect EXEC/SLIM as the current milestone.
6. **Vestigial `agentpins` + kept `.specify/`.** `agentpins` still pins the judiciary model into
   `.github/agents/3pwr.*.agent.md` (kept as manual/IDE prompts); consider retiring it, and relocating the
   constitution + templates from `.specify/` to `.3powers/` so no `.specify/` remains at all.
7. **Spend/observability (NFR-009).** The native runner now controls dispatch, so per-run/per-stage token
   spend and an audit stream are finally implementable in-engine — currently unaddressed.

### What the next spec should contain (proposed `RUNLIVE`, spec 011)
A spec that hardens the native executive from "walks the lifecycle with a fake agent" to "reliably builds
real software," covering:
- **Per-stage artifact contracts** — each action stage declares what artifact it must produce (a spec file,
  oracle tests under `oracle-tests/`, an implementation diff), and the runner *verifies* it before
  advancing; a stage that produced nothing is a dispatch failure, not a silent pass (extends EXEC-FR-004).
- **Robust dispatch** — timeouts, retries, and streamed agent output surfaced in the tracker; a
  machine-readable per-stage result on `--json`.
- **A gated live e2e proof** — an opt-in test that runs one real agent end-to-end and asserts a green
  verdict, closing residual #1.
- **The async hosted backend (EXEC-FR-011 shape-b)** — the Copilot-coding-agent backend, so Copilot-only
  enterprises are covered end-to-end.
- **Per-stage commit checkpoints + resume-from-commit.**

A **separate** small spec (`DOCX`) should do the STATUS/doc rewrite + retire `agentpins`/`.specify` residue
(residuals #5, #6) — pure documentation/cleanup, Cosmetic/Standard tier.
