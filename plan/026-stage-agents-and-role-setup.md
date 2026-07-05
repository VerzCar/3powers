# Plan 026 — Per-stage agent templates + the headless-CLI / role→model setup (AGENTX, spec 016)

**Spec:** [`specs/016-stage-agents-and-role-setup/spec.md`](../specs/016-stage-agents-and-role-setup/spec.md)
(Spec ID `AGENTX`, Standard). The authoring-and-configuration counterpart to EXEC (009) — which made
3Powers own its executive with engine-owned stage instructions — and to PHASE (013), which introduced
context-budgeted phases and `[P]` parallel dispatch. **Authoring + dispatch configuration only, no
trust-spine module change** — `canonical`/`keys`/`ledger`/`verify` are untouched; no gate, threshold,
verdict byte, exit code, ledger record, or human gate changed (AGENTX-NFR-002), and model diversity
stays recommended, never forced (3PWR-FR-022/057).

## Why

Two gaps were left after EXEC/PHASE. (1) The per-stage instructions were inline Python in
`prompts.py` — a project could neither see nor tune the prompt each stage's agent runs, and the curated
reference set the user placed under `.3powers/templates/example-templates/` (the Spec-Kit
`speckit.*.agent.md` collection plus the native `planning.agent`/`implementation-plan.agent`) had never
been folded into 3Powers-native templates. (2) Init pinned only the oracle role's model — it never asked
which headless CLI you use, never configured planner/coder/reviewer, had no catalog of selectable
models+labels per integration, and there was no standalone role-setup command — so a user could not go
straight to `3pwr run` after init without hand-editing YAML.

## What was done

- **One editable agent template per dispatched stage** (AGENTX-FR-001..004): nine merged templates in
  [`engine/src/threepowers/scaffold/templates/agents/`](../engine/src/threepowers/scaffold/templates/agents/)
  — discovery, specify, clarify, plan, tasks, oracle, implement, review, characterize — each a readable
  markdown with a `stage`/`artifact`/`role` metadata header and a body that merges the stage-aligned
  parts of the curated reference set (spec-quality checklist + `[NEEDS CLARIFICATION]` discipline,
  the clarify ambiguity taxonomy + max-5-question loop, the task checklist line format and `[P]`
  marker semantics, phase organization, the analyze/review audit dimensions, AI-to-AI plan discipline)
  with the engine's existing instruction for that stage. All substrate machinery is gone — no
  `.specify/` script call, extension-hook block, `$ARGUMENTS` token, or `handoffs:` front matter — and
  every body references the executive's run-context blocks (INTENT / APPROVED SPEC / PRIOR CONTEXT /
  FILE SCOPE) as its only input channel.
- **Template resolution with built-in fallback** (AGENTX-FR-005) in
  [`prompts.py`](../engine/src/threepowers/prompts.py): `TEMPLATE_STEPS`, `template_path`,
  `template_body` (front-matter stripping), `stage_template_body` (absent/empty/unreadable → `""`),
  `resolve_body`, and an additive `assemble(..., body=)` override. Both runners
  ([`runner.py`](../engine/src/threepowers/runner.py) `CliAgentRunner.dispatch` and
  [`hosted.py`](../engine/src/threepowers/hosted.py)) resolve the repo-local template at
  `.3powers/templates/agents/<step>.agent.md` (new `Settings.stage_templates_dir`); a template changes
  only the instruction body, never the context blocks or their order — deterministic, offline
  (EXEC-FR-005 preserved). The phase-estimate report uses the resolved body too.
- **Phase-parallel plan/tasks/implement templates** (AGENTX-FR-006..008): the plan and tasks templates
  demand ordered, context-budgeted phases with file scope, dependencies, and an estimated context
  against the budget (PHASE-FR-007); `[P]` is allowed only for disjoint, dependency-free phases and is
  "never a licence" for overlapping/dependent ones (PHASE-FR-011); the implement template directs
  batch-independent / serialize-dependencies execution within a phase and the file-scope stop-and-re-spec
  condition (3PWR-FR-017).
- **Seeding and retirement** (AGENTX-FR-009/010): `scaffold.seed_stage_templates` seeds the nine
  templates at init, non-clobbering and idempotent (ONBRD-FR-008/009); this repo's own
  `.3powers/templates/agents/` is seeded and the one-time authoring reference
  `.3powers/templates/example-templates/` is **deleted** (nothing in the engine or docs references it).
- **Headless-CLI + role→model setup** (AGENTX-FR-011..014): a shared `_roles_setup_flow` in
  [`cli.py`](../engine/src/threepowers/cli.py) drives both init's customize branch and the new
  **`3pwr config roles setup`** command — declare the installed integration (no provider forced), then
  walk planner/coder/oracle/reviewer against the catalog, writing complete `roles.yaml` blocks
  (`model_family`/`model`/`integration`/`label`, `require_dispatch` always present on the oracle) via
  the extended `scaffold.set_role_model` — non-destructive (only reconfigured roles are rewritten;
  unrelated fields preserved), and immediately run-ready (`3pwr run` needs no manual role editing).
  Non-interactive (`--yes`/`--json`/no TTY) prompts for nothing: explicit flags apply, unbound roles get
  the catalog's documented default, bound roles are kept; `--json` stdout is byte-stable.
- **Model/label catalog** (AGENTX-FR-015/016): a new
  [`catalog.py`](../engine/src/threepowers/catalog.py) reads
  `.3powers/config/models.yaml` (seeded from
  [`scaffold/config/models.yaml`](../engine/src/threepowers/scaffold/config/models.yaml)) — per
  integration: selectable `{model, family, label}` entries plus a documented default. Editable data,
  not code; a malformed/missing file falls back to the shipped copy; a model not listed stays
  selectable free-form (BYOK) with `derive_family` (prefix, else leading-token heuristics) filling the
  family where the id encodes it.
- **`require_dispatch` explained where it lives + diversity guidance** (AGENTX-FR-017/018): the shipped
  `roles.yaml` comments stay; `set_role_model` now writes a deterministic explanatory header into every
  rewritten roles file (meaning, default `false`, when to enable — 3PWR-FR-021/A3); the CLI reference
  documents the command and the flag. `_warn_diversity` warns (stderr, never stdout) when the oracle or
  reviewer resolves to the coder's family, naming `3pwr deviation --gate model_diversity …` — and never
  blocks.
- **A real seam fixed along the way:** bare, integration-native model ids (e.g. Copilot's
  `claude-opus-4.8`) defeat prefix-derivation, so the explicit `model_family` field now wins over
  `family_of(model)` in `Settings.coder_family()`, init's readiness check, and the diversity warning —
  exactly the AGENTX-FR-012 property (a catalog selection's written fields are the entry's fields).

## Verification

- Engine green under its own dev tooling: `ruff check`, `ruff format --check`, `mypy src`, and
  `pytest` — **623 passed, 1 skipped** (25 new).
- New suite [`tests/test_stage_agents.py`](../engine/tests/test_stage_agents.py) names every
  `AGENTX-FR-001..018` and `AGENTX-NFR-001..005`: the per-stage template set, the merged structure +
  no-substrate-machinery sweep, the discipline + header/context-block contract, template-wins /
  built-in-fallback / determinism / body-only properties, the phase + `[P]` + implement-discipline
  content, idempotent non-clobbering seeding, example-templates retirement, full role blocks in the
  US4 shape (copilot + Claude/GPT), run-readiness, non-destructive re-setup, catalog lookup/editing/
  free-form/malformed-fallback, `require_dispatch` explained in the shipped file + the rewritten header
  + the docs, the same-family warning naming the deviation path (exit 0), byte-stable `--json`,
  verdict-bytes invariance + no trust-spine import of the authoring layer, and the unchanged
  runtime-dependency set.
- Self-application (NFR-006), `3pwr gate run --path engine --tier Standard --base main`: format ✓,
  lint ✓, types ✓, tests ✓, diff_coverage ✓, sast ✓, dependency_scan ✓, secret_scan ✓, gate_gaming ✓
  (see the Handoff for the two pre-existing lines).

## Handoff — notes

- Spec 016 still needs the human spec-approval sign-off before it is formally advanced:
  `3pwr signoff --approver <you> --spec-id AGENTX --stage spec --spec specs/016-stage-agents-and-role-setup/spec.md`.
- The `spec_integrity` line on a local gate run keeps its standing pre-existing seal-drift result for
  spec 002 (see plans 022/025) — untouched by this change.
- Non-goals held: no hosted model gateway or raw LLM API call (the executive still drives agent CLIs);
  no lifecycle stage added/removed/reordered; no artifact contract or write location changed; no
  network-synced model registry (the catalog is local, editable, may lag providers); diversity stays a
  warned recommendation with the signed-deviation escape hatch.
- The catalog ships with a small curated set per integration — growing it is a data edit
  (`.3powers/config/models.yaml`), no engine change (AGENTX-FR-016).
