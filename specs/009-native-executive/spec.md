# Feature Specification: Native Provider-Agnostic Executive — a Self-Hosted `3pwr run` that Drives Headless Coding Agents Directly (No IDE, No Spec Kit)

**Spec ID**: EXEC
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     EXEC is a standalone feature spec that gives 3Powers its own executive: a native, headless,
     provider-agnostic agent runner that dispatches each lifecycle stage to a coding agent directly,
     instead of delegating dispatch to the Spec Kit substrate. It is the successor to RUNX (spec 008)
     and **supersedes RUNX-FR-001/002** (headless-via-Spec-Kit). It **amends the epic law** — the
     top-of-file Substrate line, assumptions A1 and A3, and the §16 non-goals — see the "Epic
     Amendments" section below. Its rationale lives in the epic: §6 (the eight-stage lifecycle &
     one-command orchestration), §7 (oracle independence & model diversity), §9 (the trust spine),
     §10-§11 (agnosticism/adapters/config) of [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md). It
     cites 3PWR-*, RUNX-*, INITX-* ids only as cross-references (the "why"). The physical removal of the
     Spec Kit artifacts is the separate SLIM spec (spec 010), sequenced after EXEC lands. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: this feature is executive orchestration/dispatch. It introduces a new agent-runner
     component but **no new trust-spine primitive** — no new signing, ledger, gate, or verdict logic. It
     composes the already-delivered High-risk primitives (canonical/keys/ledger/verify, oracle
     read-path isolation, the model-diversity refusal, the `advance` enforcement gate) and records only
     additive provenance. The single thesis-critical invariant it must preserve — *a model never
     produces or alters the verdict* — is enforced by the deterministic gate engine and the signed
     ledger, each already governed at High-risk in its own module; this feature never enters that path.
     Per spec §4 orchestration/config work is Standard, so Standard applies. A maintainer may elevate the
     whole spec to High-risk to demand mutation coverage on the new runner/dispatch code; it is declared
     Standard here and is adjustable at spec approval. -->

**Status**: Draft

**Input**: User description: "The whole project runs on the `3pwr` CLI, but `3pwr run` dispatches through
Spec Kit's `workflow run`, and that does not work when I'm inside an IDE like GitHub Copilot — there is no
agent for a terminal command to pilot. I want my own underlying vanilla orchestrator, helpers, and agents
that satisfy the 3Powers solution: a simple `run` command where everything is handled for me — all the
stages, gates, and the provenance — so at the end I have a framework and solution I can rely on when I want
to create software with agents. It must be enterprise-ready and provider-agnostic: teams on a Claude partner
subscription, on GitHub Copilot with their Microsoft policies, or on OpenAI/Azure OpenAI must all be able to
use it, routing through their own model gateway (e.g. an internal proxy, Bedrock, Vertex, or LiteLLM)."

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** make the engine itself call any model or agent API. The engine assembles prompts, dispatches
  an external agent process, records, and attests; the model runtime and every model call stay outside
  3Powers (amended 3PWR A3). This is a hard invariant, not a preference.
- Does **not** let any model or agent produce, alter, or influence the deterministic verdict, the signed
  ledger, an oracle-independence proof, or a human sign-off. The judiciary is unchanged and remains
  deterministic and model-free (3PWR-NFR-001).
- Does **not** implement, host, or proxy a model gateway, a virtual-key store, budgets, RBAC, SSO, or
  provider credentials. Enterprise model-access governance is **inherited** by pointing the dispatched
  agent at the organization's existing gateway; the engine only passes configuration through, opaquely.
- Does **not** hardcode any provider, model, or agent vendor in engine logic. Every provider/agent-specific
  detail lives in a declarative manifest or in pass-through environment/config (3PWR-NFR-007/FR-046).
- Does **not** weaken, remove, or bypass any deterministic gate, any risk-tier threshold, or either
  mandatory human gate — spec approval (3PWR-FR-006) and sign-off (3PWR-FR-037).
- Does **not** replace, retire, or weaken the independent-oracle Phase-A flow or its physical read-path
  isolation (3PWR-FR-020/021/062); it **invokes** that authoritative flow for a run's oracle step, under a
  different model family than the coder (3PWR-FR-022).
- Does **not** physically remove the Spec Kit files, the vendored agent prompts, or the workflow
  descriptors — that severance is the SLIM spec (spec 010). EXEC makes the native runner the default and
  may retain the old substrate runner temporarily behind an explicit selector.
- Does **not** ship a retiring or deprecated agent backend as a reference (a backend scheduled for
  end-of-life is excluded), and does **not** guarantee an autonomous, in-IDE-only assistant that exposes no
  headless or programmatic entry point (such a surface is served only through its provider's async/hosted
  agent path — see EXEC-FR-011).
- Does **not** change the on-disk trust-spine layout, the ledger format, the schemas, or the meaning of any
  existing flag, beyond **additively** recording per-stage executive-dispatch provenance.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command builds software headlessly, no IDE (Priority: P1)

A developer wants `3pwr run "<intent>" --mode auto` to carry the intent through the whole lifecycle — with
real coding agents doing the spec, plan, and implementation work directly in the repository — without any
IDE or editor session, pausing only where a human must decide.

**Acceptance Scenarios**:

1. **Given** a project with a headless coding agent available on the machine, **When** the developer runs
   auto mode, **Then** each executive stage (specify, clarify, plan, tasks, oracle, implement) is dispatched
   to that agent with no interactive IDE, the agent's produced changes are captured as that stage's
   artifact, the deterministic gate suite runs at the Verify stage, and the stage tracker advances,
   pausing only at spec approval (3PWR-FR-006) and sign-off (3PWR-FR-037).
2. **Given** a headless run paused at a human gate, **When** the developer records the decision (resume with
   an approver identity), **Then** dispatch continues from the next stage and no already-completed stage is
   re-dispatched.
3. **Given** commit mode, **When** each stage completes, **Then** the run stops for review at every gate.
4. **Given** no Spec Kit CLI is installed anywhere, **When** the developer runs auto mode, **Then** the run
   still proceeds end-to-end — Spec Kit is not required.

### User Story 2 - Choose the agent by configuration, change nothing in code (Priority: P1)

A developer or platform team wants to point the executive at whichever headless coding agent their
organization has standardized on, and to add a new one, without modifying engine code.

**Acceptance Scenarios**:

1. **Given** a declarative agent manifest for a headless coding agent, **When** the developer selects that
   agent (by flag or role configuration), **Then** the run dispatches each stage to that agent, and no
   engine source change is needed to support it.
2. **Given** a new agent described only by a new manifest added to configuration, **When** a run selects it,
   **Then** it is driven correctly, proving the runner is manifest-driven, not vendor-coded.

### User Story 3 - Enterprise entitlement & gateway, within policy (Priority: P1)

An enterprise wants to use its existing entitlement and route all model traffic through its own governed
gateway (internal proxy, cloud model service, or an OpenAI-compatible LLM gateway), keeping keys, budgets,
and audit under its control — while 3Powers adds no model traffic of its own.

**Acceptance Scenarios**:

1. **Given** an organization whose agent runtime is reachable only through a governed gateway configured via
   environment/config, **When** a run dispatches a stage, **Then** all model traffic originates from the
   dispatched agent and flows through that gateway; the engine performs no model call and stores no model
   credential.
2. **Given** a team whose only programmatic entry to its agent runtime is an asynchronous, hosted agent run
   (rather than a local headless CLI), **When** the executive dispatches a stage to that backend, **Then**
   the hosted run is triggered, awaited to completion, and its produced changes are collected as the stage
   artifact and judged by the same deterministic gate suite (see EXEC-FR-011).

### User Story 4 - The oracle is genuinely independent during a run (Priority: P1)

A developer wants the oracle authored during a run to be a different model family than the coder and unable
to read the implementation, so the separation of powers holds in a live headless run.

**Acceptance Scenarios**:

1. **Given** a run that reaches Phase A, **When** the oracle stage executes, **Then** it is authored through
   the read-path-isolated dispatch (3PWR-FR-021) under an agent whose model family differs from the
   coder's (3PWR-FR-022), and the isolation attestation is recorded in the signed ledger.
2. **Given** the coder and oracle resolve to the same model family, **When** the run reaches the oracle
   stage or preflight, **Then** the tool refuses by default or proceeds only under a signed, reversible
   deviation with a warning (3PWR-FR-022 via 3PWR-FR-057) — never a silent accept.
3. **Given** a High-risk run, **When** it reaches the ship advance, **Then** advance refuses unless the
   oracle isolation is attested and model diversity holds — exactly as today.

### User Story 5 - Honest diagnostics; dispatch failure is never "gates red" (Priority: P2)

A developer whose environment is missing a prerequisite (no headless agent available, or no different-family
oracle agent) wants a plain message naming the missing piece and the fix, and a mid-run dispatch failure
that is reported as a dispatch failure — never mislabeled as a gate verdict.

**Acceptance Scenarios**:

1. **Given** a project missing a run prerequisite, **When** `3pwr run` starts, **Then** it fails fast before
   dispatching any stage, naming the specific missing prerequisite and the exact fix (and the offline
   `--dry-run` alternative), and exits with a setup/usage status distinct from the gate-failure status.
2. **Given** a stage's agent dispatch fails mid-run, **When** the run stops, **Then** the output names the
   stage at which dispatch failed and states the failure was in dispatch/execution — not in the verdict —
   and does not print "gates red".
3. **Given** the deterministic gate suite actually returns fail at Verify, **When** the run stops, **Then**
   (and only then) the output reports a gate-red verdict and lists the failing gates.

### Edge Cases

- **No agent available.** Preflight names it as a setup failure with the fix and the `--dry-run`
  alternative — not "gates red".
- **Selected agent is IDE-/editor-bound with no headless entry point.** It is detected as not
  headless-dispatchable; the tool explains this and names a headless or hosted-async alternative rather than
  shelling out and failing opaquely.
- **Only one model family available.** Diversity is recommended, not forced: the tool warns and names the
  signed, reversible deviation path (3PWR-FR-057/022); the oracle still runs read-path-isolated under the
  same family, with a recorded deviation. Never a silent drop, never a wall.
- **Agent exits non-zero or times out.** Reported as a dispatch failure at the named stage; partial progress
  and attestations are preserved in the ledger; a subsequent run resumes from the last completed stage.
- **Human rejects at a gate.** The run aborts cleanly; no ship, no advance.
- **`--dry-run`.** The simulated path dispatches nothing, requires no agent and no network, and is always
  available offline.
- **Non-interactive / CI.** Prompts degrade to documented defaults; run status and failures are emitted in
  machine-readable form.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable and
  carries an *Acceptance* line — the oracle (Phase A) is authored from these alone. A **Property** is added
  where input is parsed/validated/transformed (3PWR-FR-024). No implementation detail here (3PWR-FR-007): no
  named vendor, filename, config key, or subprocess flag in the normative text — those are decided at plan
  time. Reference-backend names appear only as illustrative examples, exactly as the epic names its
  reference language adapters.
-->

### Functional Requirements

#### The native executive runner

- **EXEC-FR-001**: The system shall drive the full lifecycle with a native executive runner that dispatches
  each stage to a headless coding agent directly, requiring neither an interactive IDE nor any external
  workflow-dispatch substrate.
  - *Acceptance*: on a machine with a headless coding agent but no Spec Kit CLI, a live auto run advances
    through every executive stage and produces each stage's artifact.
  - *Property*: for any project, the set of external tools a live run requires never includes a
    workflow-dispatch substrate; it requires only a configured headless agent (or the offline dry-run).
- **EXEC-FR-002**: The system shall itself make no model or agent API call; all agent work shall be
  performed by the dispatched external agent process, and no model credential shall be interpreted or
  stored by the engine.
  - *Acceptance*: with the engine process's own outbound network disabled and the agent dispatch stubbed,
    a run performs zero model calls originating from the engine.
  - *Property*: no engine code path issues an outbound model/agent API request; all such traffic originates
    from the dispatched agent.
- **EXEC-FR-003**: The system shall describe each supported agent by a declarative manifest — how the agent
  is invoked headlessly, how a stage prompt is passed, the permitted tools, the model selector, and how its
  result is collected — such that adding an agent requires only a new manifest and no engine code change.
  - *Acceptance*: an agent added solely by a new manifest is driven correctly by a run; removing all vendor
    names from engine source does not reduce the set of drivable agents.
  - *Property*: every agent-specific string a run uses is sourced from a manifest or environment, never from
    engine logic.
- **EXEC-FR-004**: The system shall ship reference agent manifests for at least three widely-used headless
  coding agents (e.g. Claude Code, an OpenAI Codex-class CLI, and the GitHub Copilot CLI), proving the
  manifest contract across vendors.
  - *Acceptance*: the repository contains at least three reference manifests, and each can drive a stage in
    a simulated or live test without an engine change.
- **EXEC-FR-005**: For each executive (action) stage the system shall assemble the stage prompt from
  engine-owned prompt templates together with the approved spec, the prior stages' artifacts, and the
  stage's declared file scope; dispatch it to the role's configured agent; and collect the agent's produced
  changes as that stage's artifact.
  - *Acceptance*: a run produces, per stage, the expected artifact derived from engine-owned templates
    without any external template package installed.
  - *Property*: prompt assembly is a deterministic function of (template, spec, prior artifacts, file
    scope); the same inputs yield the same assembled prompt.
- **EXEC-FR-006**: At each verdict stage the system shall run the deterministic gate suite in-process and
  record the normalized verdict to the signed ledger — never through a subprocess dispatch and never through
  a model.
  - *Acceptance*: the Verify stage of a run produces a verdict via the in-process gate suite; disabling all
    agent dispatch does not prevent the verdict from being computed over existing code.
- **EXEC-FR-007**: In auto mode the system shall auto-continue past intermediate review gates and shall
  always stop at the two mandatory human gates — spec approval (3PWR-FR-006) and sign-off (3PWR-FR-037); in
  commit mode it shall stop at every gate.
  - *Acceptance*: an auto run stops exactly at review-spec and sign-off; a commit run stops at every gate.
  - *Property*: for any mode, the set of stops always includes both mandatory human gates.
- **EXEC-FR-008**: After a human gate decision is recorded, the system shall resume dispatch from the paused
  stage without re-executing any already-completed stage.
  - *Acceptance*: resuming after spec approval continues at the plan stage; no completed stage is dispatched
    twice.
  - *Property*: the count of successful dispatches for any stage across a run and its resumes never exceeds
    one per stage.

#### Roles, diversity, and oracle independence

- **EXEC-FR-009**: The system shall resolve each role (coder, oracle, and any other) to its configured agent
  and model from role configuration, and shall author the oracle role headless inside the existing
  read-path-isolated sanitized worktree, recording the same isolation attestation the delivered oracle
  dispatch records (3PWR-FR-021).
  - *Acceptance*: a run's oracle stage executes in a sanitized worktree with the implementation, plan,
    tasks, and contracts absent, and its isolation manifest hash is recorded in the ledger.
  - *Property*: the recorded oracle model family never equals the coder's family unless a signed diversity
    deviation is present in the ledger.
- **EXEC-FR-010**: When the coder and oracle resolve to the same model family, the system shall apply the
  diversity policy — refuse by default, or proceed under a signed, reversible deviation with a warning —
  never silently proceeding (3PWR-FR-022/057); and at the High-risk tier the ship advance shall continue to
  refuse unless the oracle isolation is attested and diversity holds (3PWR-FR-020/021/022/062).
  - *Acceptance*: same-family resolution without a deviation stops the run and names the deviation path; a
    High-risk run whose oracle isolation is not attested is refused at advance.

#### Enterprise model-access pass-through

- **EXEC-FR-011**: The agent-runner contract shall support two backend shapes without a contract change:
  (a) a synchronous local backend that dispatches a headless agent in the working tree and collects the
  produced changes; and (b) an asynchronous hosted backend that triggers a hosted agent run, awaits its
  completion, and collects the produced changes (e.g. a branch or pull request) as the stage artifact. Both
  shapes shall feed the same in-process deterministic gate suite and ledger.
  - *Acceptance*: a simulated hosted-async backend and a simulated local backend both drive a stage to a
    collected artifact that the verdict stage then judges identically.
- **EXEC-FR-012**: The system shall pass provider and gateway configuration through to the dispatched agent
  via environment/config, opaquely, without interpreting, transforming, logging, or storing any model
  credential, so an organization may route all model traffic through its own governed gateway.
  - *Acceptance*: with gateway configuration present in the environment, a dispatched agent receives it
    unaltered and the engine records no credential value in any log or ledger entry.
  - *Property*: no credential-shaped configuration value ever appears in engine output, logs, or ledger
    entries.

#### Runner selection, provenance, and honest diagnostics

- **EXEC-FR-013**: The system shall select the executive runner explicitly, defaulting to the native runner,
  with the offline simulated runner selectable for `--dry-run` and tests; the native runner shall be the
  default for a live run.
  - *Acceptance*: a live run with no selector uses the native runner; `--dry-run` uses the simulated runner
    and dispatches nothing.
- **EXEC-FR-014**: The system shall record, for each dispatched stage, a provenance entry in the signed
  ledger naming the stage, the agent, and the resolved model (and, for the oracle stage, the isolation
  attestation); and a headless run shall be offline-reconstructable and tamper-evident.
  - *Acceptance*: after a run the ledger carries one provenance entry per dispatched stage plus the oracle
    isolation attestation, and offline ledger verification validates the chain and fails if any run entry is
    altered, reordered, or removed.
- **EXEC-FR-015**: Before dispatching any stage the system shall verify run prerequisites — a headless coder
  agent available and a different-family oracle agent available — and, when any is missing, fail fast with a
  message naming the missing prerequisite and the exact fix, before any stage is dispatched.
  - *Acceptance*: each missing prerequisite yields a distinct, named error carrying a fix, emitted before any
    dispatch; a satisfied project passes preflight without a spurious warning.
- **EXEC-FR-016**: When the lifecycle cannot start, or a stage's agent dispatch fails, the system shall
  report it as a setup/dispatch failure naming the stage — distinct from a deterministic gate verdict — and
  shall neither print "gates red" nor route the user to the incident/observe-signal path; a gate-red verdict
  shall be reported only when the deterministic gate suite actually returned fail at Verify.
  - *Acceptance*: a dispatch failure names the failing stage and exits with a status distinct from the
    gate-failure status; "gates red" appears only for a real gate failure.
  - *Property*: the "gates red" message is emitted if and only if the deterministic gate suite returned fail.

### Non-Functional Requirements

- **EXEC-NFR-001 (thesis invariant)**: The engine shall make no model or agent API call itself; all model
  traffic shall originate from the dispatched agent process (ref 3PWR A3, amended).
  - *Acceptance*: an engine-network-disabled test confirms a run performs zero model calls from the engine
    while still orchestrating (with agent dispatch stubbed).
- **EXEC-NFR-002**: The deterministic verdict bytes and any machine-readable run output shall be identical
  whether a stage was produced natively, by any agent backend, or step-by-step — dispatch is a delivery
  mechanism, not a source of verdict variance (ref 3PWR-NFR-001).
  - *Acceptance*: the verdict produced by a native run and a step-by-step run of the same approved spec over
    the same code is byte-for-byte identical.
- **EXEC-NFR-003**: The runner shall be model-, provider-, and agent-agnostic: no vendor is referenced in
  core engine logic; every vendor-specific detail lives in a manifest or in pass-through env/config (ref
  3PWR-NFR-007/FR-046).
  - *Acceptance*: a source scan finds no provider/agent vendor name embedded in the runner's control logic;
    changing manifests changes which agents are drivable with no code change.
- **EXEC-NFR-004**: The runner shall be unit-testable with a fake agent — no live model — so the whole
  orchestration, preflight, provenance, and diagnostics logic is exercised deterministically in the suite.
  - *Acceptance*: the suite drives a full lifecycle with a fake agent, asserting the two mandatory stops and
    completion, with no network access.
- **EXEC-NFR-005**: Preflight and dispatch shall degrade gracefully — an unavailable agent, a missing
  prerequisite, or a failed dispatch shall never surface as an unhandled crash; each yields an actionable
  message and a clean non-zero exit (ref 3PWR-FR-034).
  - *Acceptance*: inducing each failure mode produces a readable, actionable message and a clean non-zero
    exit, never a stack trace as the primary output.
- **EXEC-NFR-006**: Enterprise model-access governance (keys, budgets, RBAC, SSO, audit) shall be
  inheritable, not reimplemented: pointing the dispatched agent at an organization's gateway shall require
  no engine code change and add no engine-originated model traffic (ref 3PWR-FR-046).
  - *Acceptance*: a run configured against a governed gateway dispatches through it with no engine change and
    no engine-originated model call.

## Epic Amendments (3PWR) *(normative — applied as part of this feature)*

This feature amends the epic law [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md). The amendments are
part of EXEC's scope and the epic must be re-sealed at Spec-stage sign-off after they land (SLOCK):

- **Substrate line (epic header).** Replace "Layered on GitHub Spec Kit …" with: a **native,
  provider-agnostic executive** over **Git as substrate**, with **optional external model gateways**
  (internal proxy / cloud model service / OpenAI-compatible LLM gateway) as pass-through model access.
- **A1′ (was "Built on Spec Kit").** 3Powers ships **its own executive** — a declarative agent-runner
  contract, engine-owned lifecycle prompts, and the gate/judiciary plugins. Spec Kit is **no longer** the
  dispatch substrate or a runtime dependency. (Interop export remains possible but is not required.)
- **A2 (Git is the substrate).** Unchanged and reaffirmed: the repository/worktree is the agent's working
  environment, the home of the authoritative spec, and the home of versioned history; a specific Git host
  is not assumed.
- **A3′ (was "Provider-agnosticism via [Spec Kit] dispatch").** Provider-agnosticism is achieved via a
  **pluggable, manifest-driven agent runner** the engine owns. The engine **dispatches agents and passes
  model-gateway config through** but **calls no model API itself**, and — the invariant that carries the
  thesis — **a model never produces or alters the verdict.**
- **§16 non-goals.** Retire "A new agent harness or model runtime" and "A replacement for Spec Kit" as
  non-goals (the native executive is now in scope). Add: 3Powers is **not a model runtime and not a model
  gateway** — those remain outside its boundary and are inherited/passed-through.
- **Supersession.** RUNX-FR-001/002 (headless dispatch *through the Spec Kit substrate*) are superseded by
  EXEC-FR-001/002 (headless dispatch by the **native** runner). The remaining RUNX requirements
  (diagnostics, provenance, diversity, verdict-parity) are preserved and re-expressed here against the
  native runner.

## Success Criteria *(mandatory)*

- **EXEC-SC-001**: On a machine with a headless coding agent and **no Spec Kit CLI**, a single `3pwr run
  "<intent>" --mode auto` drives every executive stage via real agents, runs the deterministic gates, and
  stops only at the two human gates — no IDE required.
- **EXEC-SC-002**: A new headless agent is made drivable by adding a manifest alone, with no engine source
  change (agnosticism proven across ≥3 reference backends).
- **EXEC-SC-003**: An enterprise routes all model traffic through its own governed gateway (proxy / cloud
  model service / OpenAI-compatible gateway) with no engine change and no engine-originated model call;
  GitHub Copilot, Claude-partner, and OpenAI/Azure-OpenAI shops can each run the executive within their
  policy boundary.
- **EXEC-SC-004**: A run's oracle stage is authored under a different model family than the coder,
  read-path-isolated, with the isolation attested in the signed ledger; a same-family resolution is refused
  or proceeds only under a recorded deviation; a High-risk run cannot advance unless isolation and diversity
  hold.
- **EXEC-SC-005**: The verdict bytes are identical whether a stage was produced by the native runner or
  step-by-step; the engine makes zero model calls under an engine-network-disabled test.
- **EXEC-SC-006**: A dispatch or setup failure is reported distinctly and names the stage reached — never
  "gates red" and never an incident-signal suggestion; "gates red" appears only for a real gate failure.
- **EXEC-SC-007**: A completed or paused native run is fully reconstructable offline (run status and ledger
  verification), with per-stage provenance for which agent/model did what.
- **EXEC-SC-008**: Every functional requirement has ≥1 linked verification across the appropriate layers
  (3PWR-FR-030/065) — a behavioral test for the runner/preflight/diagnostics/prompt-assembly logic driven by
  a fake agent, or a recorded review plus a structural check where a live end-to-end dispatch cannot be
  exercised deterministically in the suite.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id EXEC --stage spec --spec specs/009-native-executive/spec.md`; appended to the signed ledger)_ | | |
