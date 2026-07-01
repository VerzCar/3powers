# GitHub Spec Kit — compacted reference

> What 3Powers builds on. Verified against the installed CLI
> (`specify 0.11.6.dev0`, June 2026) and the scaffolding it produced in this repo.

## What it is

An open-source toolkit for **Spec-Driven Development**: specs are executable artifacts that drive
AI-assisted implementation through structured phases, with a project **constitution** as governance.
Vendor-neutral (50+ agents). Repo: `github.com/github/spec-kit`.

## Install & init

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v<X.Y.Z>
specify init . --integration copilot --here   # scaffolds from BUNDLED assets — no network needed
```

Key `init` flags: `--integration <agent>` (e.g. `copilot`, `claude`, `gemini`, `codex`, …),
`--here`, `--force` (merge into non-empty dir), `--script sh|ps`, `--ignore-agent-tools`,
`--preset <id>`. Other CLI: `specify check`, `specify version`.

## Slash-command workflow (all prefixed `/speckit.`)

`constitution → specify → clarify → plan → analyze → tasks → implement → converge`
plus `checklist` and `taskstoissues`. Recommended order: constitution → specify → (clarify) → plan →
(checklist) → tasks → (analyze) → implement → (converge).

| Command | Produces |
|---|---|
| `/speckit.constitution` | `.specify/memory/constitution.md` |
| `/speckit.specify` | `specs/<NNN-feature>/spec.md` (+ `checklists/`) |
| `/speckit.clarify` | resolves ambiguities in the spec |
| `/speckit.plan` | `plan.md` (+ `research.md`, `data-model.md`, `contracts/`) |
| `/speckit.tasks` | `tasks.md` |
| `/speckit.analyze` | cross-artifact consistency report |
| `/speckit.implement` | source code |

## Layout created by `init`

```
.specify/
  memory/constitution.md            # the project's supreme law, loaded by every command
  templates/{spec,plan,tasks,checklist,constitution}-template.md
  scripts/bash/{common,create-new-feature,setup-plan,setup-tasks,check-prerequisites}.sh
  workflows/…  integrations/…  extensions/…  extensions.yml
.github/
  prompts/speckit.<cmd>.prompt.md   # ← the Copilot slash commands
  agents/speckit.<cmd>.agent.md     # the real command logic
  copilot-instructions.md
specs/<NNN-feature>/spec.md         # created on first /speckit.specify
.specify/feature.json               # tracks the active feature dir for downstream commands
```

## Copilot command pattern (how 3Powers adds `/3pwr.*`)

Each command is **two files**:
- `.github/prompts/<name>.prompt.md` — thin; frontmatter `agent: <name>` only.
- `.github/agents/<name>.agent.md` — the instructions; frontmatter `description` + optional `handoffs`
  (suggested next commands); body uses `$ARGUMENTS`.

3Powers mirrors this exactly: see `.github/prompts/3pwr.*.prompt.md` + `.github/agents/3pwr.*.agent.md`.

## Helper scripts (`.specify/scripts/bash/`)

`common.sh` exposes `get_repo_root`, `resolve_template`, `_persist_feature_json`.
`create-new-feature.sh` makes the `specs/<NNN-…>` dir + copies the resolved spec template + writes
`.specify/feature.json`. Templates resolve through a stack: project overrides → presets → extensions →
core defaults.

## Extension / hook system (not used in 001; future catalog packaging)

Agent command files check `.specify/extensions.yml` for `hooks.before_*` / `hooks.after_*` and emit
`EXECUTE_COMMAND:` for mandatory hooks. Extensions (`extension.yml` + `commands/`) and presets
(`preset.yml` + `templates/`) are the catalog-distribution mechanism. **3Powers now ships as a real
extension** — [`.specify/extensions/3powers/extension.yml`](../../.specify/extensions/3powers/extension.yml)
(plan 009) — providing the `/3pwr.*` judiciary commands + `after_tasks`/`after_implement` gate hooks,
**provider-agnostic** (no integration hardcoded; `install` renders per the project's chosen integration).
The engine also pins the supported Spec Kit range in `.3powers/config/dependencies.yaml` (`3pwr deps-check`).

## How 3Powers layers on Spec Kit

| Spec Kit primitive | 3Powers use |
|---|---|
| constitution | encodes separation of powers, EARS, oracle independence, the trust spine |
| spec/plan/tasks templates | spec ID + namespaced IDs, risk tier, non-goals, oracle plan, file-scope |
| custom `/3pwr.*` commands | the judiciary (Phase-A oracle), `verify`, `signoff`, `advance` |
| extensions/hooks | the `3powers` extension auto-runs the oracle (`after_tasks`) + gates (`after_implement`); provider-agnostic packaging (plan 009) |
