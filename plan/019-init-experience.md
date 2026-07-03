# Plan 019 — Init experience (INITX): config-driven setup, model-pinned judiciary agents, workflow extensions, a first-run readiness gate & colorized output

> **Cold start:** the governing spec is [`specs/007-init-experience/spec.md`](../specs/007-init-experience/spec.md)
> (Spec ID `INITX`, tier **Standard**); the task breakdown is
> [`specs/007-init-experience/tasks.md`](../specs/007-init-experience/tasks.md). Use
> `uv run python -m threepowers.cli` — the installed `3pwr` alias may be stale.

## Context

`3pwr init --with-speckit` left an end user still wiring things by hand: no config choice, no model
selector in the Spec Kit judiciary agents, no test-first / auto-commit workflow, no drift warning when
config changed, a confusing brownfield block, monochrome output, and no honest "what's missing before
the first run" gate. INITX closes those gaps as an extension of the ONBRD onboarding wizard.

## Scope — in (delivered)

1. **Config selection + judiciary model pinning** (INITX-FR-001/002/003/004). The wizard accepts the
   recommended defaults or customizes the two choices that can never weaken a gate — the judiciary model
   and the default risk tier. `roles.yaml` gains an additive concrete `model` + `integration` + `label`
   for the judiciary roles (a family-only file still loads). The configured model is rendered into the
   `/3pwr.oracle` + `/3pwr.review` agent frontmatter only (`agentpins.py`), deterministically and without
   clobbering a hand-edited pin.
2. **The wanted workflow** (INITX-FR-005/006/007/008). The Spec Kit judiciary extension is rendered from
   config and installed (`scaffold/speckit/`) with an **after-plan test-first hook** and a read-only
   `3pwr.tests-gaps` conformance dry-run; `/3pwr.oracle` stays authoritative. `3pwr commit-stage` gives
   **per-stage auto-commit** (`3pwr(<spec-id>): <stage>`), scoped to staged outputs, no commit on a
   no-op/failed stage. Every installed template is rendered from config — no hardcoded model literal or
   unresolved placeholder survives.
3. **First-run readiness gate** (INITX-FR-009/010/011/012). Init ends with an explicit checklist (CI/CD,
   Spec Kit, constitution, AGENTS.md, judiciary diversity), omitting nothing, in human + JSON. A **missing
   CI/CD config is flagged mandatory** for secure gates; a generated **AGENTS.md starter is a TODO**. Next
   steps are explained per-step (greenfield vs brownfield), not a bare command list.
4. **Colorized CLI** (INITX-FR-013/014). A zero-dependency ANSI styler (`style.py`) colorizes markers,
   headings, and sections; color auto-disables for non-TTY / `--json` / `--yes` / `NO_COLOR` and never
   alters machine-readable output or verdict bytes.
5. **Config-drift warning** (INITX-FR-015/016). A fingerprint of tracked config is recorded at
   init/apply; a later edit makes the next `3pwr` run **warn to stderr** (naming the file + pointing to
   `3pwr config apply`) without touching any agent file. `3pwr config apply` re-renders the pins and
   clears the warning.

## Scope — out

- Writing the CI pipeline itself (INITX detects and flags its absence; it never authors one).
- Wiring `commit-stage` into `orchestrate.drive` (the primitive + hook are delivered; the live-runner
  call is a follow-up, kept out of the pure driver + its tests).
- Live-dispatch model diversity enforcement beyond the existing `oracle record`/`advance` checks.

## Decisions

| Area | Decision | Why |
|---|---|---|
| Model pins | Judiciary agents only (`/3pwr.oracle`, `/3pwr.review`) | The diversity-critical agents; coder stays on the IDE default (INITX-FR-004 / non-goal) |
| Auto-commit | One commit per successful stage | Matches the wanted workflow; scoped to staged outputs, no commit on a no-op (INITX-FR-006) |
| Oracle/tests | Augment, keep `/3pwr.oracle` authoritative | Reuse the bundle's model-pin pattern + a `tests-gaps` dry-run; avoid two competing oracle flows |
| Config drift | Warn only, manual `config apply` | Never regenerate agents silently (INITX-FR-016) |
| Color | Stdlib ANSI, no new dependency | Honors ONBRD-NFR-005 (no new runtime dep) + INITX-NFR-004 |

## What landed (files)

- **New:** `engine/src/threepowers/style.py`, `engine/src/threepowers/agentpins.py`,
  `engine/src/threepowers/configdrift.py`; `engine/src/threepowers/scaffold/speckit/` (extension +
  command templates); `engine/tests/test_init_experience.py`; `specs/007-init-experience/{spec,tasks}.md`.
- **Restructured:** `engine/src/threepowers/cli.py` (reworked `cmd_init`, new `config apply` +
  `commit-stage`, `main()` drift hook, colorized `_format_verdict`),
  `engine/src/threepowers/scaffold.py` (CI + AGENTS.md-starter detection, `set_role_model`, extension
  install, tier/auto-commit prefs), `engine/src/threepowers/config.py` (`role_model_pin`, `coder_family`,
  `default_tier`, `auto_commit`), `engine/src/threepowers/scaffold/config/roles.yaml` (additive judiciary
  model fields).

## Verification (as run)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # all green; 439 tests (28 new INITX)
3pwr coverage-check --spec specs/007-init-experience/spec.md --tasks specs/007-init-experience/tasks.md   # PASS (INITX)
# Self-application at the spec's tier (A6): the engine passes its own gate suite for INITX.
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/007-init-experience/spec.md --tier Standard --base main --no-ledger)
#   verdict PASS · diff_coverage 91.4% ≥ 80% · spec_conformance 22 requirements traced (all linked)
```

## Residual

- `spec_integrity` is (correctly) skipped until a human seals the spec:
  `3pwr signoff --stage spec --spec-id INITX --spec specs/007-init-experience/spec.md`.
- Auto-commit is available as the `3pwr commit-stage` primitive + Spec Kit hook; wiring it into
  `3pwr run`'s live loop is the next increment.
