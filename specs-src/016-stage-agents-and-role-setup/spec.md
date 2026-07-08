# Feature Specification: Per-Stage Agent Templates and a Headless-CLI + Role→Model Setup — an Editable, Merged Agent Template for Every Agent-Dispatched Stage (with Phase-Parallel Plan/Tasks), plus an Init/Config Flow that Picks a Headless Integration, Assigns a Model per Role, and Writes a Run-Ready `roles.yaml`

**Spec ID**: AGENTX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     AGENTX is the authoring-and-configuration counterpart to EXEC (009) — which made 3Powers own its
     executive so `3pwr run` dispatches each stage to a headless coding agent — and to PHASE (013),
     which introduced context-budgeted phases and one fresh session per phase with `[P]` parallel
     dispatch. EXEC delivered engine-owned stage *instructions* (hardcoded in prompts.py) and a
     declarative agent-backend manifest per integration; INITX (007) / ONBRD (003) delivered guided
     init, and AUTOX (014) the run preflight. Those left two gaps AGENTX closes: (1) the per-stage
     instructions are inline Python, not editable per-stage agent *templates* a project can see and
     tune — and the curated reference set under .3powers/templates/example-templates/ has never been
     folded into 3Powers-native templates; (2) init only pins the oracle role's model — it never asks
     which headless CLI you use, never configures planner/coder/reviewer, has no catalog of selectable
     models+labels per integration, and there is no standalone role-setup command, so a user cannot go
     straight to `3pwr run` after init. Cross-refs: EXEC-FR-004/005, PHASE-FR-005/007/011,
     ONBRD-FR-008/009, INITX-FR-002/003/014, 3PWR-FR-006/007/017/021/022/030/057/065, 3PWR-NFR-001.
     No trust-spine module change. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this shapes the executive's stage-authoring inputs (the prompt each dispatched agent
     runs) and the onboarding config that binds every role to a model + headless CLI. It touches shared
     orchestration and onboarding seams (prompt assembly, scaffold seeding, the role config) but changes
     NO trust-spine module (canonical/keys/ledger/verify), no gate, threshold, verdict byte, or ledger
     format, and it weakens no gate (3PWR-FR-032). It is more than Cosmetic because a wrong template or a
     mis-written role binding would silently misdirect real runs (wrong instructions, wrong model, wrong
     integration) and because model-diversity guidance (3PWR-FR-022) rides on the role config this
     feature writes. It is not High-risk because it is dispatch configuration and authored prompt text —
     it produces no verdict and signs nothing. The invariant that role/model/template choices are
     dispatch-only and never change verdict/ledger bytes is made an explicit, tested requirement
     (AGENTX-NFR-002), the same latitude CLIUX (015) and AUTOX (014) used to land on Standard. -->

**Status**: Draft

**Input**: User request: "For each stage I want to create a template that is used for the dedicated
agent that runs it — a spec agent, a plan agent, an implementation agent, discovery, clarify, and so on
— as agent markdown templates handed to the headless CLI for execution. Merge the good reference
templates I put in .3powers/templates/example-templates/ (the speckit.*.agent.md set plus the native
planning.agent / implementation-plan.agent) with 3Powers' own stage instructions into one template per
stage, keeping the parts that are mandatory or good-to-have and dropping the rest — especially the
plan/tasks pairing must express parallel execution of tasks inside phases. Delete the example-templates
folder when done. Second: the init phase must set up the headless CLI. Once I pick the integration(s) I
have installed (say copilot), ask me which model I want for each role (or a default), then write
roles.yaml with a full per-role block — model_family, model, integration, label (and require_dispatch
for the oracle) — so I can go straight to `3pwr run`. Because we support many integrations we need a
dictionary of the models and labels per integration to set them correctly, at init or via a
`3pwr config roles setup` command. And explain what require_dispatch means." A codebase review confirmed
the seams: prompts.py holds inline per-stage instruction bodies with a deterministic `assemble`;
orchestrate.py lists the lifecycle steps; runner.py dispatches each step to the role's agent backend;
scaffold.py seeds .3powers/ non-clobbering; cmd_init pins only the oracle; roles.yaml already carries
per-role blocks and a `headless_integrations` list; oracle.py holds a bare integration→family map.

---

## Context (non-normative — for a fresh reader)

Read this before planning; none of it is a requirement.

- **What already exists (don't duplicate):** The native executive owns its stage instructions
  (EXEC-FR-005): `prompts.py` holds a per-step instruction body for `specify`, `clarify`, `plan`,
  `tasks`, `oracle`, `implement` (a generic fallback for the rest) and a pure `assemble(step, intent,
  spec_text, context, file_scope)` that prepends a standing discipline preamble and appends whatever
  run-context blocks are present — deterministically, so the same inputs yield the same prompt bytes.
  `orchestrate.py` walks the twelve `LIFECYCLE_STEPS` (specify → clarify → review-spec → plan →
  review-plan → tasks → oracle → implement → verify → review-verify → signoff → advance); the
  agent-dispatched *action* steps are specify/clarify/plan/tasks/oracle/implement (plus the residual
  reviewer, and the brownfield `characterize`, and a Discovery stage), while verify is the in-process
  gate suite and review-spec/signoff are the two human gates. `runner.py`'s `CliAgentRunner.dispatch`
  builds each step's prompt via `assemble`, then runs the role's backend headlessly; PHASE-FR-005/010
  give it per-phase blocks (the approved spec, the prior artifact, the phase's tasks + file scope), and
  the implement stage runs one fresh session per phase, concurrently for `[P]` phases with disjoint file
  scopes. `scaffold.py` seeds `.3powers/` from bundled package data (config/, agents/, adapters/,
  constitution) non-clobbering and idempotent, and `set_role_model` writes a role's concrete
  model/integration/label into `roles.yaml`.
- **The curated reference set:** the user placed a reference collection under
  `.3powers/templates/example-templates/` — the Spec-Kit `speckit.{specify,clarify,plan,tasks,implement,
  analyze,checklist,converge,constitution,…}.agent.md` set plus the 3Powers-native `planning.agent.md`
  and `implementation-plan.agent.md`. These carry battle-tested structure (task checklist format, the
  `[P]` parallel marker, phase organization, AI-to-AI plan discipline) but also substrate machinery that
  does not belong in a 3Powers-native template: external `.specify/scripts/bash/*.sh` calls, an
  extension-hook protocol (`.specify/extensions.yml`, before/after hooks), `$ARGUMENTS` placeholders, and
  tool-specific `handoffs:` front matter. github/awesome-copilot's `agents/` collection is a further
  reference for the stages the curated set does not cover well (discovery/research, a critic/reviewer,
  characterization).
- **Where the seams are:** stage instructions are inline Python — a project can neither see nor tune the
  prompt each stage's agent runs, and the curated reference structure is not applied. On the config side,
  `cmd_init` asks only (in its customize branch) for the oracle model/integration/label; planner, coder,
  and reviewer are never set up interactively; there is no per-integration catalog of selectable
  models+labels (only `oracle.py:INTEGRATION_FAMILY`, an integration→family map, e.g. claude→anthropic,
  codex→openai, copilot→"" because Copilot is BYOK); and there is no `3pwr config roles` command, so
  re-doing the role setup means hand-editing YAML.
- **`require_dispatch`, in plain terms:** it is the High-risk oracle policy for physical read-path
  isolation (3PWR-FR-021, epic A3). Default `false`: the oracle may be authored in-IDE and recorded
  (`3pwr oracle record`). Set `true`: a High-risk `advance` refuses unless there is an *isolated
  headless-dispatch attestation* (`3pwr oracle dispatch`) proving the oracle was authored with the
  implementation/plan/tasks/contracts physically absent from its worktree. It is per-project, opt-in, and
  independent of which model or integration a role uses.
- **Guardrail:** authored prompt text and dispatch configuration only. No gate, threshold, verdict bytes,
  ledger chain/signing, exit code, or `--json` schema changes; model diversity stays recommended, never
  forced (3PWR-FR-022/057); the two mandatory human gates are untouched.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** add a hosted model gateway or make any raw model/LLM API call from the engine — the
  executive drives headless *agent CLIs*, not model endpoints; this feature configures which CLI + model a
  role uses, it does not become a model client (preserves EXEC's agent-runner boundary, 3PWR-NFR-001).
- Does **not** change the gate suite, any threshold, verdict bytes, the ledger chain/signing format, exit
  codes, or the two mandatory human gates (3PWR-FR-006/037, 3PWR-FR-032); role/model/template choices are
  dispatch and authoring inputs only.
- Does **not** force model diversity or mandate any specific provider, model, or integration; diversity
  stays a warned recommendation with the signed-deviation escape hatch (3PWR-FR-022/057), and any single
  installed integration is a valid setup.
- Does **not** maintain an authoritative, network-synced model registry; the model/label catalog is local,
  editable, offline data that may lag real provider availability, and a free-form / BYOK model entry always
  remains valid.
- Does **not** rewrite the core structure of the spec/plan/tasks *document* templates
  (`.3powers/templates/{spec,plan,tasks}-template.md`) beyond what the per-stage *agent* templates need;
  the phase, `[P]`, and file-scope conventions those documents already carry are reused, not redesigned.
- Does **not** implement the coder-leg full headless dispatch or change oracle read-path isolation; the A3
  coder-leg residual and the `oracle dispatch` mechanism are unchanged (only `require_dispatch` is
  *documented* and surfaced by setup).
- Does **not** add, remove, or reorder lifecycle stages, and does **not** change what any stage's artifact
  contract is or where it is written (`specs/<f>/spec/spec.md`, `.../artifacts/{plan,tasks}.md`, etc.).
- Does **not** localize/translate template text or add a template theming/plugin system beyond a plain
  markdown file per stage plus the built-in fallback.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One editable agent template per stage (Priority: P1)

A user setting up 3Powers wants each lifecycle stage that dispatches an agent — discovery, spec, clarify,
plan, tasks, oracle, implement, review — to run from a dedicated, readable agent template they can open and
tune, rather than instructions buried in the engine, so they can see and adjust exactly what each stage's
agent is told to do.

**Acceptance Scenarios**:

1. **Given** a fresh, initialized project, **When** the user lists the templates location, **Then** there is
   one agent template file per agent-dispatched stage (discovery, spec/specify, clarify, plan, tasks,
   oracle, implement, review, characterize), each a readable markdown file carrying that stage's
   instructions.
2. **Given** a project with a repo-local stage template, **When** the executive dispatches that stage,
   **Then** the agent's instructions come from the repo-local template, not the engine's built-in default.
3. **Given** a project with no repo-local template for a stage (or the file removed), **When** that stage is
   dispatched, **Then** the executive falls back to the engine's built-in instruction for that stage and the
   run proceeds unchanged.

### User Story 2 - Templates carry the merged, 3Powers-native structure (Priority: P1)

A user wants each template to combine the best of the curated reference set with 3Powers' own discipline —
keeping the mandatory and useful parts (EARS specs, phase decomposition, task checklist format, artifact
contracts) and dropping substrate machinery (external scripts, extension hooks, `$ARGUMENTS`, tool-specific
handoffs) — so the templates read as first-class 3Powers artifacts, not ports of another tool.

**Acceptance Scenarios**:

1. **Given** the plan agent template, **When** it is read, **Then** it reflects a merge of the reference
   plan agent and the native planning agent (context-budgeted ordered phases, judicial plan, role→model
   table) and contains no `.specify/…` script call, extension-hook block, `$ARGUMENTS` token, or
   tool-specific `handoffs:` front matter.
2. **Given** the tasks agent template, **When** it is read, **Then** it reflects a merge of the reference
   tasks agent and the implementation-plan agent (the checklist task format and phase organization) with the
   same substrate machinery removed.
3. **Given** any stage template, **When** it is read, **Then** it preserves the 3Powers discipline (the spec
   is the law, no scope invention, no gate weakening, stay within declared file scope, trace every artifact
   to a requirement id) and names the artifact it must produce.

### User Story 3 - Plan and tasks templates make phase-parallel execution explicit (Priority: P1)

A user wants the plan and tasks templates to decompose work into context-budgeted phases and to clearly mark
which phases can run in parallel, so that independent phases with disjoint file scopes are dispatched
concurrently while dependent or overlapping ones stay sequential — and so tasks inside a phase run with the
same discipline.

**Acceptance Scenarios**:

1. **Given** the plan agent template, **When** a plan is authored from it, **Then** the plan decomposes work
   into ordered phases, each declaring its file scope, its dependencies, and an estimated context size
   against the configured budget.
2. **Given** the tasks agent template, **When** tasks are authored from it, **Then** phases whose file
   scopes are disjoint and which have no unmet dependency are marked parallelizable (`[P]` / an explicit
   parallel marker), and phases that share files or depend on another phase carry no such marker.
3. **Given** two phases marked parallelizable with disjoint scopes, **When** the executive reaches them,
   **Then** it may dispatch them as concurrent fresh sessions; **and Given** two phases that overlap in file
   scope or declare a dependency, **Then** they run sequentially regardless of any marker.
4. **Given** the implement template and a single phase, **When** the agent executes that phase's tasks,
   **Then** independent tasks (disjoint files, no dependency) proceed together and only true dependencies are
   serialized, and no task edits a file outside its declared scope.

### User Story 4 - Init sets up my headless CLI and every role in one pass (Priority: P1)

A user who has one or more headless coding-CLI agents installed wants init to let them declare which
integration(s) they use, then be asked which model to assign to each role (or accept a documented default),
and have a complete `roles.yaml` written — so that immediately after init they can run `3pwr run` with no
manual config editing.

**Acceptance Scenarios**:

1. **Given** an interactive init, **When** the user declares the integration(s) they have installed (e.g.
   copilot), **Then** init does not force any other provider and uses the declared integration for the role
   bindings it writes.
2. **Given** the chosen integration, **When** init walks the configurable roles (planner, coder, oracle,
   reviewer), **Then** for each role it offers the models available for that integration plus a documented
   default, records the user's choice, and writes a full per-role block — `model_family`, `model`,
   `integration`, `label` — with `require_dispatch` present for the oracle.
3. **Given** the user selected copilot with a Claude model for planner/oracle and a GPT model for
   coder/reviewer, **When** init finishes, **Then** `roles.yaml` contains blocks equivalent to:
   `planner: {model_family: anthropic, model: claude-opus-4.8, integration: copilot, label: Claude Opus
   4.8}`, `coder: {model_family: openai, model: gpt-5.5, integration: copilot, label: GPT 5.5}`,
   `oracle: {model_family: anthropic, model: claude-opus-4.8, integration: copilot, label: Claude Opus 4.8,
   require_dispatch: false}`, `reviewer: {model_family: openai, model: gpt-5.5, integration: copilot,
   label: GPT 5.5}`.
4. **Given** setup has completed, **When** the user runs `3pwr run`, **Then** it starts using the configured
   integration and per-role models without any further role editing.

### User Story 5 - Re-run role setup any time, without reinitializing (Priority: P2)

A user who wants to change integration or the model for a role later wants a dedicated command to re-run the
same role setup, non-destructively, without reinitializing the whole project.

**Acceptance Scenarios**:

1. **Given** an initialized project, **When** the user runs the role-setup command (`3pwr config roles
   setup` or the equivalent config-roles surface), **Then** it performs the same integration + per-role
   model selection as init and writes the same shape of `roles.yaml`.
2. **Given** an existing `roles.yaml` with hand-edited fields outside the roles it changes, **When** the
   setup command runs, **Then** it preserves those other fields (non-clobbering) and updates only the roles
   the user reconfigures.

### User Story 6 - A model/label catalog offers the right choices per integration (Priority: P2)

A user selecting a model for a role wants to be offered a curated list of models with human-friendly labels
appropriate to the chosen integration — and still be able to type in a model the catalog doesn't list — so
the role block's `model_family`, `model`, and `label` are filled correctly and consistently.

**Acceptance Scenarios**:

1. **Given** the chosen integration, **When** the setup offers models, **Then** the offered options come
   from a catalog keyed by integration, each carrying a model family and a friendly label, and choosing one
   fills the role block's `model_family`, `model`, and `label` consistently.
2. **Given** a model the catalog does not list (a new or BYOK model), **When** the user enters it free-form,
   **Then** setup accepts it and records it, deriving the family where possible.
3. **Given** a new model or integration becomes available, **When** the user edits the catalog data,
   **Then** the new entry is offered by subsequent setups with no engine code change.

### User Story 7 - `require_dispatch` is explained where it lives (Priority: P2)

A user reading the role config wants to understand what `require_dispatch` does before deciding whether to
enable it, without hunting through source.

**Acceptance Scenarios**:

1. **Given** the role config (and its documentation), **When** the user reads about the oracle role,
   **Then** `require_dispatch` is explained: what it enforces (an isolated headless-dispatch attestation
   proving physical read-path isolation at High-risk, 3PWR-FR-021/A3), its default (`false`), and when to
   turn it on.

### Edge Cases

- A named integration is not installed / not on PATH → setup still writes the requested role binding but the
  run-readiness check reports the missing CLI as an unmet step (consistent with the existing preflight),
  never silently claiming readiness.
- The oracle (or reviewer) ends up in the same model family as the coder → setup warns that diversity is
  recommended and names the signed-deviation path, but never blocks (3PWR-FR-022/057).
- Non-interactive setup (`--yes` / `--json` / no TTY) → setup prompts for nothing and applies documented
  defaults for integration and per-role models, keeping any `--json` stdout byte-stable (INITX-FR-014).
- A stage template file is malformed or empty → the executive falls back to the built-in instruction for
  that stage rather than dispatching an empty or broken prompt, and does not crash.
- A repo-local template exists for a stage that has no built-in default (e.g. discovery) → the repo-local
  template is used; if it is absent, the generic stage instruction applies.
- The model/label catalog is missing or malformed → setup falls back to shipped catalog defaults (and to
  free-form entry) rather than failing.
- Re-running init or the setup command → idempotent and non-clobbering: it converges to the same on-disk
  state and never overwrites a hand-edited template or unrelated config (ONBRD-FR-008/009).

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement carries an
  *Acceptance* line; a *Property* where a value is derived or parsed (3PWR-FR-024). Config field names
  and the roles.yaml block shape appear where they ARE the contract under specification (the role
  binding the user must get), not as implementation detail (3PWR-FR-007) — the same latitude CLIUX took
  for `ui.yaml` and `--json`. Named modules/functions/paths are context in the non-normative sections only.
-->

### Functional Requirements

#### Per-stage agent templates — the set and its contract

- **AGENTX-FR-001**: The system shall provide a dedicated agent template for each lifecycle stage that
  dispatches a headless agent — at minimum discovery, spec (specify), clarify, plan, tasks, oracle,
  implement, review (residual), and characterize — each stored as a readable markdown file at a well-known,
  versioned templates location.
  - *Acceptance*: after init, one agent template file exists per named stage; each is valid markdown
    carrying that stage's agent instructions.
- **AGENTX-FR-002**: Each stage template shall be a merge of the stage-aligned, reusable parts of the
  curated reference templates with the engine's existing instruction for that stage, keeping the parts that
  are mandatory or valuable to a 3Powers stage and discarding substrate machinery — external script
  invocations, extension-hook protocols, `$ARGUMENTS` placeholders, and tool-specific handoff front matter.
  - *Acceptance*: the plan template merges the reference plan agent with the native planning agent, and the
    tasks template merges the reference tasks agent with the implementation-plan agent; no shipped template
    contains a `.specify/…` script call, an extension-hook block, a `$ARGUMENTS` token, or a `handoffs:`
    front-matter key.
- **AGENTX-FR-003**: Each stage template shall preserve the 3Powers discipline: the spec is the law, no
  scope beyond the spec's requirements and non-goals, no gate weakening, every change stays within its
  declared file scope, and every artifact traces to a requirement id.
  - *Acceptance*: each template states these constraints (directly or by carrying the standing discipline
    preamble); a review finds none that invites out-of-scope work or gate relaxation.
- **AGENTX-FR-004**: Each stage template shall declare, in a small metadata header, the stage it serves, the
  artifact it must produce, and the role that runs it; and its instruction body shall reference the
  run-context blocks the executive supplies (the intent, the approved spec, the prior stage's artifact, and
  the declared file scope) rather than any external input mechanism.
  - *Acceptance*: each template's header names its stage, artifact, and role; its body refers to the
    supplied context blocks and contains no reference to an external argument/script input channel.
- **AGENTX-FR-005**: When the executive assembles a stage's agent prompt, the system shall use the
  repo-local stage template as the source of that stage's instruction body when present, and shall fall back
  to the engine's built-in instruction for that stage when the template is absent, empty, or unreadable.
  - *Acceptance*: with a repo-local template present, the assembled prompt's instruction body is that
    template's body; with it absent/empty, the assembled prompt equals the current built-in instruction for
    that stage.
  - *Property*: template resolution is deterministic and offline — identical template bytes and identical
    run context yield identical assembled-prompt bytes (preserve EXEC-FR-005 / 3PWR-NFR-001); presence of a
    valid repo-local template changes only the instruction body, never the surrounding context blocks or
    their order.

#### Plan/tasks/implement templates — phase-parallel execution

- **AGENTX-FR-006**: The plan and tasks agent templates shall decompose implementation work into ordered,
  context-budgeted phases, each declaring its file scope, its dependencies, and an estimated context size
  against the configured budget.
  - *Acceptance*: a plan/tasks authored from the templates contains ordered phases, each with a file-scope
    declaration, a dependency declaration (or "none"), and an estimated-context line referencing the budget
    (PHASE-FR-007).
- **AGENTX-FR-007**: The tasks agent template shall require that a phase be marked parallelizable only when
  its file scope is disjoint from its sibling phases' and it has no unmet dependency, so the executive may
  dispatch such phases as concurrent fresh sessions; phases that share files or depend on another phase
  shall carry no parallel marker.
  - *Acceptance*: authored tasks mark disjoint, dependency-free phases with `[P]` (or an explicit parallel
    marker) and leave overlapping or dependent phases unmarked, consistent with PHASE-FR-011.
  - *Property*: the parallel marker's presence implies disjoint file scopes and no unmet dependency; it is
    never a licence to run overlapping or dependent phases concurrently.
- **AGENTX-FR-008**: The implement agent template shall direct that, within a phase, independent tasks
  (disjoint files, no dependency) be executed together and only true dependencies be serialized, and that no
  task edit a file outside its declared scope (editing outside scope is a signal to stop and re-spec,
  3PWR-FR-017).
  - *Acceptance*: the implement template states the batch-independent / serialize-dependencies discipline
    and the file-scope stop condition.

#### Seeding and retirement

- **AGENTX-FR-009**: The system shall seed the stage templates into a project on init, non-clobbering and
  idempotently, so a freshly initialized project runs the lifecycle with the templates present and re-running
  init preserves any hand-edited template.
  - *Acceptance*: init writes the stage templates when absent, leaves hand-edited templates untouched, and
    re-running init converges to the same on-disk state (ONBRD-FR-008/009).
- **AGENTX-FR-010**: Once the merged stage templates exist, the curated reference set
  (`.3powers/templates/example-templates/`) shall be removed, as it is a one-time authoring reference and
  not a shipped artifact.
  - *Acceptance*: after delivery, the example-templates directory is absent from the repository and nothing
    in the engine or docs references it as a runtime input.

#### Headless-CLI + role→model setup

- **AGENTX-FR-011**: During init, the system shall let the user declare which headless CLI integration(s)
  they use and have installed, and shall not force any specific provider or integration.
  - *Acceptance*: interactive init offers the supported integrations for selection and proceeds with the
    user's choice; no code path requires a particular integration.
- **AGENTX-FR-012**: For each configurable role — planner, coder, oracle, reviewer — the setup shall prompt
  the user to select a model (or accept a documented default) drawn from the models available for the chosen
  integration, and shall write a complete per-role binding to the role config: `model_family`, `model`,
  `integration`, and `label`, with `require_dispatch` present for the oracle role.
  - *Acceptance*: after selecting an integration and per-role models, the role config contains a full block
    per role in the shape shown in User Story 4 scenario 3 — e.g. selecting copilot yields
    `coder: {model_family: openai, model: gpt-5.5, integration: copilot, label: GPT 5.5}` and an `oracle`
    block additionally carrying `require_dispatch`.
  - *Property*: for a catalog-listed selection, the written `model_family`, `model`, and `label` are exactly
    the catalog entry's fields for that integration; for a free-form entry, `model` is the entered value and
    `model_family` is derived where the value encodes it.
- **AGENTX-FR-013**: After the setup completes, the project shall be immediately runnable with `3pwr run`
  using the configured integration and per-role models, requiring no manual editing of the role config.
  - *Acceptance*: following an init that configures the roles, `3pwr run` dispatches to the configured
    integration with the configured models and reports no role-config gap (subject only to the existing
    run-readiness checks, e.g. the CLI being installed).
- **AGENTX-FR-014**: The system shall provide a command to (re)run the role setup after init — a
  `3pwr config roles setup` (or equivalent config-roles) surface — that performs the same integration and
  per-role model selection and writes the same role-config shape, non-destructively, without reinitializing
  the project.
  - *Acceptance*: the command exists, runs the same selection flow as init, updates only the roles the user
    reconfigures, and preserves unrelated fields in the role config.

#### Model/label catalog

- **AGENTX-FR-015**: The system shall maintain, for each supported headless integration, a catalog of
  selectable models, each with its model family and a human-friendly label, and shall use it to present the
  per-role model choices and to fill `model_family`/`model`/`label` consistently during init and the config
  setup.
  - *Acceptance*: for a given integration the setup offers the catalog's models with their labels; selecting
    one populates the role block's three fields from the catalog entry.
- **AGENTX-FR-016**: The model/label catalog shall be editable data, not code, so that new models or
  integrations can be added without an engine change; and a model absent from the catalog (a new or BYOK
  model) shall remain selectable via free-form entry.
  - *Acceptance*: editing the catalog data makes a new model appear in the next setup with no code change; a
    free-form model not in the catalog is accepted and recorded.

#### `require_dispatch` documentation and diversity guidance

- **AGENTX-FR-017**: The role config and its documentation shall explain `require_dispatch`: that it is the
  High-risk oracle policy requiring an isolated headless-dispatch attestation proving physical read-path
  isolation (3PWR-FR-021/A3), that its default is `false`, and when to enable it.
  - *Acceptance*: the role config (comments and/or accompanying docs) states `require_dispatch`'s meaning,
    default, and when to turn it on, in terms a reader can act on without reading source.
- **AGENTX-FR-018**: When the setup writes a role config in which the oracle or reviewer resolves to the
  coder's model family, the system shall warn that model diversity is recommended and name the signed
  deviation path, and shall never block on this basis.
  - *Acceptance*: choosing same-family judiciary and coder produces a warning naming
    `3pwr deviation --gate model_diversity …` (3PWR-FR-022/057) and setup still completes.

### Non-Functional Requirements

- **AGENTX-NFR-001**: All template resolution, catalog lookup, and role-config writes shall be deterministic
  and fully offline — identical inputs, environment, and files yield identical output; no network or model
  call anywhere in this feature (ref 3PWR-NFR-001).
  - *Acceptance*: the feature's tests run with networking disabled; identical state yields identical
    assembled prompts and identical written role config.
- **AGENTX-NFR-002**: This shall be an authoring-and-configuration layer only: it shall never alter the gate
  suite, any threshold, verdict bytes, exit codes, or the ledger, and it shall never suppress a mandatory
  human gate (preserve 3PWR-FR-006/037, 3PWR-FR-032/NFR-001).
  - *Acceptance*: existing gate, verdict-bytes, exit-code, and ledger tests are untouched and green; a test
    proves a role-config or template change produces no change in any verdict or ledger record.
- **AGENTX-NFR-003**: Seeding and config writes shall be idempotent and non-clobbering — re-running init or
  the setup command converges to the same on-disk state and never overwrites a hand-edited template or an
  unrelated config field (ref ONBRD-FR-008/009).
  - *Acceptance*: a re-run after hand-editing a template and an unrelated role field leaves both intact.
- **AGENTX-NFR-004**: In non-interactive mode (`--yes` / `--json` / no TTY), the setup shall prompt for
  nothing and apply the documented default for every choice (integration and per-role model), keeping any
  `--json` stdout byte-stable (ref INITX-FR-014, ONBRD-FR-006).
  - *Acceptance*: a `--json` init/setup emits no prompt and a stable payload; the same non-interactive run
    twice yields byte-identical stdout.
- **AGENTX-NFR-005**: No third-party runtime dependency shall be introduced, and the engine shall stay green
  under its own gates across this change, with `docs/STATUS.md` remaining the single home of implementation
  status (ref 3PWR-NFR-004/006, DOCX-NFR-003).
  - *Acceptance*: the dependency manifest is unchanged; the self-application gate run plus ruff/mypy/pytest
    are green; STATUS is updated once at delivery.

## Success Criteria *(mandatory)*

- **AGENTX-SC-001**: Every agent-dispatched stage (discovery, spec, clarify, plan, tasks, oracle, implement,
  review, characterize) has a dedicated agent template that the executive uses when present and that carries
  the 3Powers discipline and its artifact contract.
- **AGENTX-SC-002**: Each stage template is a merge of the curated reference structure with 3Powers' own
  stage instruction, with all substrate machinery (external scripts, extension hooks, `$ARGUMENTS`,
  tool-specific handoffs) removed; the curated `example-templates/` reference set is gone.
- **AGENTX-SC-003**: The plan and tasks templates decompose work into context-budgeted phases and mark
  disjoint, dependency-free phases as parallelizable such that the executive can dispatch them concurrently,
  while overlapping/dependent phases run sequentially.
- **AGENTX-SC-004**: A user who runs init, declares an installed integration, and picks (or defaults) a
  model per role obtains a complete, run-ready `roles.yaml` (per-role `model_family`/`model`/`integration`/
  `label`, oracle `require_dispatch`) and can run `3pwr run` with no manual role editing.
- **AGENTX-SC-005**: The same role setup is available after init via a dedicated config-roles command, and
  a per-integration model/label catalog — editable data with free-form fallback — drives the choices.
- **AGENTX-SC-006**: `require_dispatch` is explained where the role config lives; model diversity remains a
  warned recommendation, never a block; and no verdict, threshold, ledger byte, exit code, or human gate is
  changed by this feature.
- **AGENTX-SC-007**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) — a test
  naming the AGENTX-FR id, or a recorded output/template review where the rendered artifact is what is
  asserted.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id AGENTX --stage spec --spec specs/016-stage-agents-and-role-setup/spec.md`; appended to the signed ledger)_ | | |
