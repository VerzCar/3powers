# Migration — Spec Kit removed (SLIM, spec 010)

3Powers now owns its executive (EXEC, spec 009): `3pwr run` drives headless coding agents **directly** and
GitHub Spec Kit is no longer a dependency. This note is for a repository initialized under the old
`3pwr init --with-speckit` path.

## Nothing in the trust spine is affected

The judiciary is untouched. Your **signed ledger, sealed specs, verdicts, and provenance remain valid and
verifiable** — `3pwr verify` behaves exactly as before. No gate, threshold, ledger format, or signing
changed (SLIM-NFR-003).

## What changed

- `3pwr run` no longer shells out to the old Spec Kit workflow runner. It uses the **native executive**: it
  dispatches each stage to the headless agent named by each role's `integration` in
  `.3powers/config/roles.yaml`, described by a manifest in `.3powers/agents/<name>.yaml`.
- `3pwr init` no longer has `--with-speckit`; it seeds `.3powers/agents/` manifests instead.
- `3pwr oracle dispatch` authors the oracle via the native runner in the sanitized worktree (no `specify`).
- `--runner specify` is gone; the runner is `native` (default) or `sim` (offline).
- The `spec-kit` entry was removed from `.3powers/config/dependencies.yaml`; `3pwr deps-check` no longer
  probes `specify`.

## What is safe to delete from an old workspace

These were Spec Kit runtime artifacts and are no longer read by the engine:

- `.specify/workflows/`, `.specify/extensions/`, `.specify/integrations/`, `.specify/scripts/`,
  `.specify/extensions.yml`, `.specify/*.json` (integration/init options), the extensions `.registry`.
- The vendored `speckit.*` prompt/agent files under `.github/prompts/` and `.github/agents/`.

**Keep**: your 3Powers constitution, the plan/tasks authoring templates, and the per-stage agent
templates (`.3powers/templates/agents/*.agent.md`, AGENTX) — these are engine-owned and still used.

> **Update (DOCX, spec 012).** A later change **relocated** those engine-owned files out of `.specify/`:
> the constitution now lives at `.3powers/memory/constitution.md` and the authoring templates at
> `.3powers/templates/`. **No `.specify/` directory remains** in the engine — the whole directory is now
> safe to delete. If you migrated before DOCX, move `.specify/memory/constitution.md` and
> `.specify/templates/` to their `.3powers/` locations, then remove `.specify/` entirely.

## What to do

1. Point each role at an agent backend you have installed, e.g. in `.3powers/config/roles.yaml`:
   `coder: { integration: codex }`, `oracle: { integration: claude }` (a different family — 3PWR-FR-022).
2. Ensure that agent's CLI is on PATH (e.g. `claude`, `codex`, `copilot`). Route model access through your
   own gateway via the environment (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `CLAUDE_CODE_USE_BEDROCK`,
   `HTTPS_PROXY`, …) — the engine passes it through and calls no model itself.
3. Run `3pwr run "<intent>" --mode auto` — no Spec Kit, no IDE required.
