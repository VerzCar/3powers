# Feature Specification: Init Experience — Config-Driven Setup, Model-Pinned Judiciary Agents, Workflow Extensions & a First-Run Readiness Gate

**Spec ID**: INITX
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     INITX is a standalone feature spec that extends the guided-onboarding feature (ONBRD); it cites
     3PWR-* and ONBRD-* ids only as cross-references (the "why"). Its rationale lives in the epic law:
     §5 (intake/authoring), §7 (oracle independence & model diversity), §8 (deterministic gates),
     §10 (agnosticism/adapters), §12 (brownfield adoption) of
     [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md). -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this feature orchestrates existing trust-spine commands and seeds/renders configuration
     and agent-context files; it configures and integrates, it implements no trust-spine primitive (no new
     signing, ledger, or gate logic), so Standard is the applicable tier per spec §4 (orchestration/config).
     The colorized-output work is Cosmetic-class by §4 (cli_docs); the higher applicable tier governs the
     whole spec, exactly as the engine spec scopes tiers per capability. -->

**Status**: Draft

**Input**: User description: "After `3pwr init --with-speckit` I still had to wire things up by hand. Init should let me choose (or accept defaults for) the 3Powers configuration — at least which model backs the judiciary — and then write that model into the Spec Kit judiciary agents' frontmatter so the diversity split is real in the IDE. It should install the 3Powers workflow the way we actually want it (author the oracle/tests first after plan, auto-commit after each stage), reusing my sdd-judiciary bundle but rendered from my config, not hardcoded. If I change a config later, the next run should warn me it's stale. The brownfield 'adopt gradually' output is confusing — I want a clearer, explained getting-started. I want colorful output like npm or Homebrew. And init must tell me plainly what's still missing before my first run — flag a missing CI/CD pipeline as mandatory for secure gates, and flag the AGENTS.md it generated as a TODO."

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** replace, retire, or weaken the existing independent-oracle Phase-A flow (`/3pwr.oracle`:
  seal → author → record → verify, with headless dispatch). This feature **augments** it; the existing
  oracle flow remains the authoritative Phase-A path (3PWR-FR-020/021/062).
- Does **not** edit risk-tier thresholds or provide any path to lower a gate threshold or bypass a gate
  (3PWR-FR-032/042). The only risk-tier choice offered is which default tier a new spec starts at; the
  threshold table itself is never made downward-editable through this flow.
- Does **not** select, pin, or override the model for the coder role or any non-judiciary agent; those
  remain on the Spec Kit integration's default model. Only the judiciary roles (oracle, and reviewer where
  applicable) are pinned (3PWR-FR-022/044).
- Does **not** make any model or network call in the default flow. Initializing the Spec Kit workspace,
  installing extensions, and rendering agent files happen only under the explicit opt-in already governed
  by ONBRD-FR-015; the default flow stays offline (ONBRD-NFR-002).
- Does **not** author, clarify, approve, run, or dispatch the lifecycle. After this flow the next step is
  still a human-approved spec (3PWR-FR-006); it stops at "ready to run."
- Does **not** create, provision, or configure a CI/CD pipeline, nor install language toolchains. It
  **detects and flags** the absence of a CI/CD configuration; it never writes one.
- Does **not** reimplement Spec Kit's preset/extension mechanism, its dispatch, or its model registry. It
  renders templates from configuration and registers them through the existing Spec Kit tooling.
- Does **not** persist any secret, token, or model API key. A judiciary model selection records only a
  `<family>/<model>` label and its integration name — never a credential.
- Does **not** auto-apply configuration drift. Drift detection **warns** and points to an explicit
  re-apply command; it never regenerates or edits an agent file as a side effect of another command.
- Does **not** add framework- or stack-specific behavior. CI/CD detection and language selection stay at
  recognized-marker / adapter granularity (e.g. *TypeScript*, not "Next.js").
- Does **not** prompt for the observability (NFR-instrumentation) or design-oracle configuration in the
  wizard. Those are Observe-stage (3PWR-FR-054) and design-work-kind (3PWR-FR-009) concerns, not init-time
  choices; they are seeded with documented defaults and explained, not solicited interactively.
- Does **not** change the on-disk trust-spine layout, the ledger format, the schemas, or the meaning of any
  existing flag; the roles configuration is extended in a backward-compatible way only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Choose the judiciary model once and have it pinned into the Spec Kit agents (Priority: P1)

A developer setting up 3Powers wants to pick (or accept a default for) which model backs the judiciary and
have that choice actually take effect in the IDE — written into the judiciary agents' frontmatter — so the
oracle really runs on a different model family than the coder, without hand-editing agent files.

**Acceptance Scenarios**:

1. **Given** an interactive setup on a project with the Spec Kit workspace present, **When** the developer
   accepts the recommended defaults, **Then** the seeded configuration is unchanged and the judiciary
   agent commands (the oracle and review agents) carry an explicit model selector matching the configured
   judiciary model, while the coder-side commands carry no injected model field.
2. **Given** an interactive setup, **When** the developer chooses to customize and selects an oracle model
   in the **same family** as the configured coder, **Then** the tool emits a model-diversity warning and
   names the recorded-deviation path, and never silently accepts the collision.
3. **Given** a completed setup, **When** the developer inspects the roles configuration, **Then** each
   judiciary role's chosen model is stored as a concrete `<family>/<model>` plus its integration label, and
   an older family-only roles configuration still loads unchanged.

### User Story 2 - Install the 3Powers workflow the way it is meant to run (Priority: P1)

A developer wants setup to leave the wanted workflow in place: after the plan, the oracle/tests are
authored first (Phase A before Phase B), and each successful stage is committed automatically — without
copying a bundle by hand or editing hardcoded model names.

**Acceptance Scenarios**:

1. **Given** setup completes with the Spec Kit workspace, **When** the developer reaches plan completion in
   the lifecycle, **Then** an oracle/test-authoring step is offered before implementation, and the existing
   independent-oracle flow remains the authoritative Phase-A path (not replaced).
2. **Given** auto-commit is enabled, **When** each lifecycle stage completes successfully, **Then** exactly
   one commit is produced per stage with a message naming the spec id and the stage, and a failed stage
   produces no commit.
3. **Given** the shipped workflow templates, **When** they are installed, **Then** every model,
   integration, and organization value in them is rendered from the active configuration — no installed
   file contains a hardcoded model label or an unresolved placeholder.
4. **Given** a spec with a requirement that has no linked test, **When** the developer runs the
   spec-conformance dry-run ("test gaps") check, **Then** it names that requirement id and exits non-zero;
   on full coverage it exits zero; it is safe to run read-only in CI.

### User Story 3 - Know exactly what is still missing before the first run (Priority: P1)

A developer finishing setup wants a plain, honest checklist of what remains before it is safe to run the
lifecycle — especially whether CI/CD exists (so gates run automatically) and whether the generated
AGENTS.md still needs filling in — instead of guessing.

**Acceptance Scenarios**:

1. **Given** setup completes, **When** the summary is printed, **Then** a readiness checklist lists CI/CD
   presence, the agent-guidance file, the Spec Kit workspace and constitution, the signer, and judiciary
   model diversity, each marked satisfied or pending with the exact command to satisfy a pending item; no
   item is silently omitted.
2. **Given** a repository with no recognized CI/CD configuration, **When** setup completes, **Then** the
   checklist flags CI/CD as a **mandatory prerequisite for secure gate enforcement**, states why (gates
   must run automatically on every change), and points to how to add one.
3. **Given** the agent-guidance file was written by 3Powers as a starter with unfilled placeholders,
   **When** setup completes, **Then** the checklist flags it as an unfinished TODO prominently (not a soft
   aside); a filled-in or user-authored file is reported as satisfied.
4. **Given** the next-step guidance, **When** the developer reads it, **Then** the greenfield
   (spec-authoring) and brownfield (report-only → characterize → diff-scoped enforcement) paths are each
   shown with a one-line explanation of what the step does and the order to run it — not a bare command
   list.

### User Story 4 - Modern, colorful command output (Priority: P2)

A developer wants 3Powers' terminal output to be as clear and colorful as a modern package manager, while
staying safe to pipe, parse, and reproduce.

**Acceptance Scenarios**:

1. **Given** an interactive, color-capable terminal, **When** any 3pwr command prints human output,
   **Then** status markers (pass/fail/warn), headings, and sections are colorized consistently.
2. **Given** machine-readable output is requested, or output is not a terminal, or the non-interactive flag
   is set, or the environment requests no color, **When** a command runs, **Then** the output contains no
   color escape codes.
3. **Given** the same command run with and without color, **When** the machine-readable output or a verdict
   is compared, **Then** the machine-readable payload and the verdict bytes are byte-for-byte identical
   (determinism preserved).

### User Story 5 - Be told when configuration has gone stale (Priority: P2)

A developer who edits a 3Powers config file after setup wants the next run to notice and warn that derived
artifacts (such as the judiciary agent pins) may be stale — and to tell them how to re-apply — rather than
silently drifting or silently overwriting their work.

**Acceptance Scenarios**:

1. **Given** setup recorded a configuration fingerprint, **When** a tracked config file is later edited and
   the developer runs any 3pwr command, **Then** the tool warns which file changed and what is affected
   (e.g. judiciary agent pins may be stale) and points to the explicit command to re-apply the
   configuration.
2. **Given** drift has been detected, **When** the warning is shown, **Then** no agent file or other
   tracked file is modified as a side effect; re-rendering happens only when the developer runs the
   explicit re-apply command.
3. **Given** no tracked config file has changed since the fingerprint, **When** a 3pwr command runs,
   **Then** no drift warning is emitted.

### Edge Cases

- **Spec Kit workspace absent.** Judiciary-agent pinning and extension installation are reported as pending
  in the readiness checklist with the command to complete them; the default flow does not initialize Spec
  Kit or make a network call (ONBRD-FR-015 / ONBRD-NFR-002).
- **Only one model family available.** Diversity is recommended, not forced: the tool warns and names the
  signed, reversible deviation path (3PWR-FR-057/022); it never walls the developer off and never silently
  drops the requirement.
- **Hand-edited judiciary agent file.** Re-rendering never clobbers a user-edited agent file without an
  explicit force; drift detection warns rather than overwrites.
- **Non-interactive / CI.** All prompts degrade to documented defaults, color is disabled, and the readiness
  checklist is emitted in machine-readable form (ONBRD-FR-006 / ONBRD-NFR-003).
- **`NO_COLOR` set / piped output.** Color is disabled; machine-readable output is unaffected.
- **Backward-compatible roles config.** A pre-existing family-only roles configuration loads and runs; the
  concrete-model fields are additive.
- **Re-run (idempotency).** Re-running setup preserves hand-edited configuration and agent files, reports
  created-versus-kept, and converges to the same state (ONBRD-FR-009).
- **CI/CD present but partial.** Presence is detected by a recognized CI/CD configuration; the checklist
  reflects present-vs-absent without asserting the pipeline is complete or correct.
- **Auto-commit with a dirty or unrelated working tree.** Auto-commit scopes its commit to the stage's
  outputs and does not sweep unrelated changes; if it cannot commit safely it reports rather than forces.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable and
  carries an *Acceptance* line — the oracle (Phase A) is authored from these alone. A **Property** is added
  where input is parsed/validated/transformed (3PWR-FR-024). No implementation detail here (3PWR-FR-007):
  no named color library, config filename, hook filename, or CI platform — those are decided at plan time.
-->

### Functional Requirements

#### Config selection & judiciary model pinning

- **INITX-FR-001**: When run interactively, the system shall let the user either accept the recommended
  default configuration or customize it, where customization is limited to choices that cannot weaken a
  gate — the model backing each judiciary role and the project's default risk tier.
  - *Acceptance*: accepting defaults leaves the seeded configuration unchanged; customizing lets the user
    set the judiciary model(s) and the default tier; no offered choice lowers a risk-tier threshold or
    removes a gate (3PWR-FR-032).
- **INITX-FR-002**: When run interactively, the system shall prompt for the model that backs each judiciary
  role (oracle, and reviewer where applicable), present the configured coder model, and warn when a chosen
  judiciary model shares the coder's model family (3PWR-FR-022).
  - *Acceptance*: choosing a judiciary model in the coder's family emits a diversity warning and names the
    recorded-deviation path (3PWR-FR-057), never a silent accept; a different family passes clean.
  - *Property*: a recorded judiciary model is always stored as a concrete `<family>/<model>` label together
    with its integration name.
- **INITX-FR-003**: The system shall record each judiciary role's chosen model and integration in the roles
  configuration, extending it without breaking the existing family-only form.
  - *Acceptance*: after setup the roles configuration carries the concrete model + integration for the
    judiciary role(s); a pre-existing family-only roles configuration still loads and runs unchanged.
  - *Property*: reading a roles configuration that predates this feature never fails and yields the same
    diversity decision it did before.
- **INITX-FR-004**: When the Spec Kit workspace is present, the system shall render the chosen judiciary
  model into the frontmatter of the judiciary agent commands (the oracle and review agents) as an explicit
  model selector, and shall leave every non-judiciary agent on the integration's default model.
  - *Acceptance*: after setup, the oracle and review agent files carry an explicit `model` selector of the
    form `<label> (<integration>)` matching the roles configuration; coder-side and other agents carry no
    injected model field.
  - *Property*: the model label written into a judiciary agent file always equals the model recorded for
    that role in the roles configuration.

#### The wanted workflow (Spec Kit extensions)

- **INITX-FR-005**: Under the explicit Spec Kit opt-in, the system shall install and register the 3Powers
  workflow extensions that cause the oracle/tests to be authored immediately after the plan (Phase A before
  Phase B), keeping the existing independent-oracle flow as the authoritative oracle.
  - *Acceptance*: after setup with Spec Kit, plan completion offers an oracle/test-authoring step before
    implementation; the existing `/3pwr.oracle` flow remains authoritative and is not replaced (3PWR-FR-062).
- **INITX-FR-006**: The system shall install an auto-commit workflow extension that, when enabled, commits
  after each successful lifecycle stage with a message naming the spec id and the stage.
  - *Acceptance*: with auto-commit enabled, completing each of spec, plan, tests/oracle, implement, and
    verify yields exactly one commit whose message names the spec id and stage; a failed stage yields no
    commit.
  - *Property*: the number of stage commits produced never exceeds the number of stages that completed
    successfully.
- **INITX-FR-007**: The system shall provide a spec-conformance dry-run ("test gaps") check that lists spec
  requirements with no linked test, mirroring the spec-conformance gate, and is safe to run read-only.
  - *Acceptance*: on a spec with an untested requirement the check names that requirement id and exits
    non-zero; on full coverage it exits zero; it produces only a report and modifies no tracked source.
- **INITX-FR-008**: The system shall render every installed extension and agent template from the active
  configuration before installing it, so no installed template carries a hardcoded model, integration, or
  organization value, nor an unresolved placeholder.
  - *Acceptance*: an installed judiciary agent's model equals the configured judiciary model (not a bundled
    literal); no installed file contains an unresolved placeholder token.
  - *Property*: rendering the same template against the same configuration yields byte-identical output.

#### First-run readiness

- **INITX-FR-009**: When setup completes, the system shall print an explicit readiness checklist covering
  CI/CD presence, the agent-guidance file, the Spec Kit workspace and constitution, the signer, and
  judiciary model diversity — marking each item satisfied or pending with the exact command to satisfy a
  pending item — omitting no item.
  - *Acceptance*: on a repository missing each item, the checklist lists it as pending with a fix command;
    on a fully-ready repository every item is satisfied; the checklist is emitted in both human and
    machine-readable output.
- **INITX-FR-010**: When no recognized CI/CD configuration is detected, the system shall flag CI/CD as a
  mandatory prerequisite for secure gate enforcement, state why, and point to how to add one.
  - *Acceptance*: a repository with no recognized CI/CD configuration yields a prominent "CI/CD missing —
    required for secure gates" item; a repository with one yields a satisfied item.
  - *Property*: CI/CD presence is decided by the presence of a recognized CI/CD configuration and is
    independent of the chosen language adapter or hosting platform.
- **INITX-FR-011**: When the agent-guidance file was generated by 3Powers as a starter (not user-authored),
  the system shall flag it as an unfinished TODO in the readiness checklist until its placeholder content
  is filled.
  - *Acceptance*: a starter agent-guidance file with unfilled placeholders is reported as a pending TODO
    prominently; a filled or user-authored file is reported satisfied.
- **INITX-FR-012**: When setup completes, the system shall present the next-step guidance — greenfield
  spec-authoring versus brownfield gradual adoption — with a short explanation of what each step does and
  the order to run it, not a bare command list.
  - *Acceptance*: the brownfield sequence (report-only → characterize → diff-scoped enforcement) is shown
    with a one-line purpose for each command and the order; the greenfield path names the authoring entry
    point with its explanation.

#### Colorized CLI

- **INITX-FR-013**: The system shall render human-facing CLI output with color and visual styling — status
  colors, emphasis, and structured sections — comparable to modern package managers.
  - *Acceptance*: on an interactive, color-capable terminal, pass/fail/warn markers and section headings are
    colorized consistently across commands.
- **INITX-FR-014**: The system shall automatically disable all color and styling when output is not an
  interactive terminal, when machine-readable output is requested, when the non-interactive flag is set, or
  when the environment requests no color; and styling shall never alter machine-readable output or any
  verdict bytes (3PWR-NFR-001).
  - *Acceptance*: with machine-readable output, a non-terminal pipe, the non-interactive flag, or a
    no-color environment request, output contains no color escape codes.
  - *Property*: for any command, the machine-readable output is byte-for-byte independent of the color
    setting.

#### Configuration drift

- **INITX-FR-015**: The system shall record a fingerprint of the seeded configuration at setup and, on a
  subsequent run, detect when a tracked configuration file has changed since that fingerprint.
  - *Acceptance*: editing a tracked config file causes the next run to detect drift naming the changed file;
    an unchanged configuration produces no drift signal.
  - *Property*: the drift decision depends only on the tracked configuration content, not on unrelated
    repository changes.
- **INITX-FR-016**: When configuration drift is detected, the system shall warn which file changed and what
  is affected, and point to an explicit command to re-apply the configuration; it shall not regenerate or
  edit any agent file, nor act on the change, automatically.
  - *Acceptance*: after a roles-configuration edit, the next run warns naming that file and the possibly
    stale judiciary agent pins, and prints the re-apply command; no agent file is modified until the user
    runs that command.
  - *Property*: drift detection modifies no tracked file outside recording its own fingerprint.

### Non-Functional Requirements

- **INITX-NFR-001**: The default flow shall complete fully offline, making no model or network call; only
  the explicit Spec Kit opt-in may reach the Spec Kit tooling (ref ONBRD-NFR-002).
  - *Acceptance*: the default flow succeeds with networking disabled and issues no outbound request.
- **INITX-NFR-002**: The flow shall not weaken, remove, or bypass any gate, threshold, or mandatory human
  gate (ref 3PWR-FR-032/042/006/037).
  - *Acceptance*: no risk-tier threshold is lowered by the flow; pinning a judiciary model and installing
    extensions never removes the two mandatory human gates.
- **INITX-NFR-003**: Interactive config selection and colorized output shall degrade gracefully to
  non-interactive defaults with no attached terminal, producing an equivalent result (ref ONBRD-NFR-003).
  - *Acceptance*: an interactive run accepting all defaults and a non-interactive run over the same fresh
    repository produce equivalent configuration and agent state.
- **INITX-NFR-004**: Colorized output shall require no network access and shall honor standard no-color
  conventions; color support shall be optional at runtime and its absence shall never fail a command.
  - *Acceptance*: with color support unavailable or disabled, commands still run and print readable
    uncolored output.
- **INITX-NFR-005**: Rendering agent and extension templates from configuration shall be deterministic —
  the same configuration yields byte-identical output (ref 3PWR-NFR-001).
  - *Acceptance*: rendering twice from an unchanged configuration produces identical files.
- **INITX-NFR-006**: The flow shall be idempotent and non-destructive: re-running it preserves user-authored
  configuration and hand-edited agent files, reporting created-versus-kept, and never overwrites a
  hand-edited file without an explicit force (ref ONBRD-FR-009).
  - *Acceptance*: a second run over a completed setup neither clobbers a hand-edited agent file nor an
    edited config; it reports what it kept and exits successfully.

## Success Criteria *(mandatory)*

- **INITX-SC-001**: After setup on a repository with the Spec Kit workspace, the judiciary agent files
  carry an explicit model selector matching the configured judiciary model, and non-judiciary agents carry
  none.
- **INITX-SC-002**: A single setup run leaves the wanted workflow installed — oracle/tests authored after
  plan (Phase A first) and auto-commit-after-each-stage available — with every template rendered from
  configuration and no hardcoded model, integration, or organization value remaining.
- **INITX-SC-003**: A fresh setup prints a readiness checklist in which a missing CI/CD configuration is
  flagged as a mandatory prerequisite and a 3Powers-generated agent-guidance starter is flagged as an
  unfinished TODO; no checklist item is silently omitted.
- **INITX-SC-004**: With machine-readable output, a non-terminal pipe, the non-interactive flag, or a
  no-color environment request, 3pwr output contains no color escape codes and the machine-readable payload
  is byte-identical to the colorized run's data.
- **INITX-SC-005**: After a tracked configuration file is edited, the next 3pwr run warns which file changed
  and points to the re-apply command, without modifying any agent file.
- **INITX-SC-006**: A new adopter can tell, from the setup output alone, what to do first on both a
  greenfield and a brownfield repository, because each next step carries a short explanation.
- **INITX-SC-007**: Every functional requirement has ≥1 linked verification across the appropriate layers
  (3PWR-FR-030/065) — a behavioral test for wizard/rendering/detection logic, or a recorded review plus a
  structural check for the presentation requirements.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id INITX --stage spec`; appended to the signed ledger)_ | | |
