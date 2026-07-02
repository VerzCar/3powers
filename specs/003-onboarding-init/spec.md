# Feature Specification: Guided Onboarding — Interactive `3pwr init` + Autonomy-First Documentation

**Spec ID**: ONBRD
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     ONBRD is a standalone feature spec; it cites 3PWR-* ids only as cross-references (the "why").
     Its rationale lives in the epic law: §5 (intake/authoring), §10 (agnosticism/adapters),
     §12 (brownfield adoption) of [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md). -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: the wizard writes signing-key material and seeds config, and orchestrates existing
     trust-spine commands — orchestration/config is Standard per spec §4. It implements no trust-spine
     primitive itself (no new signing, ledger, or gate logic), so High-risk would be disproportionate.
     The documentation requirements (ONBRD-FR-011…014) are Cosmetic-class work by §4 (cli_docs); the
     higher applicable tier governs the whole spec, exactly as the engine spec scopes tiers per capability. -->

**Status**: Draft

**Input**: User description: "3Powers should have an onboarding command that sets everything up — for an existing project or a new one — so I can start creating the spec right away. It asks which directory (default current), which language (show the supported ones, let me pick), where to create the key (a private location, defaulting outside the repo), and whether auto mode is the default. And the README should lead with the autonomous, enterprise-ready story and list the supported languages/stack so I can check it fits my project (e.g. a Next.js TypeScript app)."

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

<!-- Explicitly state what is OUT of scope. A spec without non-goals cannot proceed to planning. -->

- Does **not** replace or reimplement signer generation (`3pwr keygen`); onboarding invokes the existing
  signer creation and its key-custody rules (3PWR-NFR-005), and never introduces a second key format.
- Does **not** replace, weaken, or add a fast path around any gate, `advance`, or a risk-tier threshold
  (3PWR-FR-032/042).
- Does **not** author, clarify, or approve a specification for the user. After onboarding, the next step is
  still to author a spec under a human who approves it (3PWR-FR-006); onboarding stops at "ready to author."
- Does **not** run the lifecycle, dispatch agents, or make any model or network call, and does **not**
  install language toolchains (formatters, test runners, compilers, package managers). It configures
  3Powers; it does not provision the developer's build environment.
- Does **not** author new language adapters. It selects among the adapters that already exist; a stack with
  no matching adapter is surfaced, never fabricated.
- Does **not** add framework- or stack-specific behavior or code generation (no Next.js-, React-, or
  framework-specific setup). Language selection is at the adapter granularity only (e.g. *TypeScript*, not
  "Next.js").
- Does **not** place the private signing key inside the repository under any option, including a user SSH
  directory (3PWR-NFR-005). Every offered location resolves outside the repository working tree.
- Does **not** change the on-disk trust-spine layout, the ledger format, the schemas, or the meaning of any
  existing flag.
- Does **not** rewrite the substance of the conceptual or architecture guides. The documentation work is a
  restructure, a completeness pass, and one new section — not a content rewrite of the technical guides.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Guided onboarding of a new (greenfield) project (Priority: P1)

A developer starting a fresh project wants a single guided step that leaves them ready to write their first
spec — signer created, baseline configuration seeded, a language chosen, and their autonomy preference
recorded — without hunting through separate commands.

**Acceptance Scenarios**:

1. **Given** an empty repository with no trust spine present, **When** the developer runs the guided
   onboarding and accepts every default, **Then** the trust-spine layout exists, a signer key pair is
   created (private key outside the repository, public key committed in-repo), a risk-tier table, a roles
   file, and the selected language adapter are present, and the tool prints a closing "you're ready — next
   run …" line naming the spec-authoring entry point.
2. **Given** the same empty repository, **When** the developer selects a language from the presented list,
   **Then** that language's adapter is the one made available and the closing summary reflects that choice.
3. **Given** onboarding has completed, **When** the developer runs the gate suite or the lifecycle next,
   **Then** no additional manual trust-spine setup is required beyond what onboarding's closing guidance
   stated.

### User Story 2 - Adopting 3Powers on an existing (brownfield) codebase (Priority: P1)

A developer with an existing codebase wants onboarding to recognise that the repository already has code and
steer them onto the gradual-adoption path rather than treating it as a blank slate.

**Acceptance Scenarios**:

1. **Given** a repository that already contains source code (and possibly a recognisable stack marker),
   **When** the developer runs onboarding, **Then** existing code is detected, the detected language is
   offered as the default choice, and the closing guidance points to the brownfield adoption sequence
   (report-only → characterize → diff-scoped enforcement) rather than "start a fresh spec."
2. **Given** a repository that is already onboarded, **When** the developer re-runs onboarding, **Then** it
   is idempotent: the existing ledger, keys, and hand-edited configuration are preserved, the tool reports
   what already existed versus what it added, and it exits successfully.
3. **Given** a repository whose stack has no matching adapter, **When** onboarding runs, **Then** it clearly
   reports that the language is unsupported, points to the adapter contract, and completes the remaining
   onboarding steps without fabricating an adapter.

### User Story 3 - Autonomy-first documentation a reader can self-qualify against (Priority: P2)

A prospective adopter reading the README wants to immediately grasp the autonomous, enterprise-ready value
proposition and confirm whether their stack (for example a Next.js TypeScript app) is supported — before
installing anything.

**Acceptance Scenarios**:

1. **Given** the README, **When** a new reader scans it top to bottom, **Then** the autonomous one-command
   flow is presented before the manual/step-by-step flow, and the enterprise, high-autonomy positioning
   statement appears above the deep-dive sections.
2. **Given** the README, **When** a reader looks for language support, **Then** a supported-languages and
   technology-stack table lets them confirm whether a given stack is supported and what tooling backs it,
   without reading the engine source.
3. **Given** the documented autonomous flow, **When** the reader follows it, **Then** it names the guided
   onboarding step first and stays consistent with the getting-started and CLI-reference guides (no
   contradicting commands).

### User Story 4 - Non-interactive / CI onboarding (Priority: P3)

An automation or CI context with no interactive terminal needs onboarding to run deterministically, without
blocking on prompts.

**Acceptance Scenarios**:

1. **Given** a non-interactive shell (no attached terminal) or an explicit non-interactive request, **When**
   onboarding runs, **Then** it prompts for nothing, applies the documented default for every choice, emits
   a machine-readable summary on request, and exits successfully.
2. **Given** machine-readable output is requested, **When** onboarding runs, **Then** no interactive prompt
   is emitted and the summary reports the resolved choices.

### Edge Cases

- **Re-run on an initialized repository (idempotency).** Only the missing pieces are created; the ledger is
  never truncated or rewritten.
- **Key file already exists.** The existing key is left intact and reported; regeneration happens only under
  an explicit force option — the key is never silently overwritten.
- **Signing key already resolvable via the environment.** If a signing key is already configured via the
  environment, onboarding detects it and does not mint a competing key.
- **No interactive terminal / CI.** Onboarding degrades to documented defaults and prompts for nothing.
- **Alternative key location outside the repo.** Every offered location is validated to be outside the
  repository; owner-only file permissions are applied regardless of which location is chosen.
- **Greenfield vs brownfield.** Presence of existing source drives the closing next-step guidance.
- **Version control not initialized.** Onboarding warns that the diff-scoped brownfield features need a
  version-controlled repository, then continues (greenfield onboarding is valid before any commit).
- **Chosen directory missing or not writable.** Rejected as a usage error before any change is made.
- **Configuration already hand-edited.** Pre-existing configuration is preserved and reported as "kept";
  seeding only fills gaps.
- **Interrupted run.** A re-run converges to the same state — no half-written key, no corrupt ledger.

## Requirements *(mandatory)*

<!--
  EARS form (3PWR-FR-002); IDs namespaced by Spec ID (3PWR-FR-059). Each requirement is measurable and
  carries an *Acceptance* line — the oracle (Phase A) is authored from these alone. A **Property** is added
  where input is parsed/validated/transformed (3PWR-FR-024). No implementation detail here (3PWR-FR-007):
  no named prompt library, config filename, or storage mechanism — those are decided at plan time.
-->

### Functional Requirements

#### The onboarding wizard

- **ONBRD-FR-001**: The system shall provide a guided onboarding flow, invoked through the existing
  initialization entry point, that prepares an existing or new project for use without further manual
  trust-spine setup.
  - *Acceptance*: after the flow completes on a repository with no trust spine, the trust-spine layout, a
    signer key pair, a seeded risk-tier table, a roles file, and one selected language adapter are all
    present; a subsequent gate or lifecycle invocation requires no additional setup step.
- **ONBRD-FR-002**: When run interactively, the system shall prompt for the target directory and default to
  the current directory.
  - *Acceptance*: accepting the default selects the current directory; supplying a path targets that path; a
    non-existent or non-writable path is rejected with a usage error before any change is made.
- **ONBRD-FR-003**: When run interactively, the system shall present the set of supported languages — those
  for which an adapter is discoverable — and let the user select exactly one.
  - *Acceptance*: the presented list matches the discoverable adapters and is derived, not hard-coded, so
    adding an adapter changes the offered list without changing this behaviour; selecting one records that
    language.
- **ONBRD-FR-004**: When run interactively, the system shall prompt for the signing-key location, offering a
  private location outside the repository as the default and at least one alternative location outside the
  repository.
  - *Acceptance*: every offered location resolves outside the repository working tree; the default matches
    the established outside-repository default; the private key file is created with owner-only permissions;
    the closing guidance prints the correct key-file environment-variable export for the chosen location.
- **ONBRD-FR-005**: When run interactively, the system shall ask whether autonomous mode should be the
  project default and record the answer.
  - *Acceptance*: the recorded preference is readable after the flow and, when autonomous is chosen, is
    reflected in the closing guidance's suggested command; the preference never removes or bypasses either
    mandatory human gate (3PWR-FR-006/037).
- **ONBRD-FR-006**: When run without an interactive terminal, or when a non-interactive request is supplied,
  the system shall prompt for nothing and apply the documented default for every choice.
  - *Acceptance*: with no attached terminal, or with the non-interactive request, the flow emits no prompt,
    completes with defaults, and exits successfully; machine-readable output, when requested, contains the
    resolved choices and never blocks on input.
- **ONBRD-FR-007**: The system shall create the signer identity honouring the established private-key
  custody rules, and shall refuse to overwrite an existing key unless overwrite is explicitly requested.
  - *Acceptance*: the private key is written outside the repository and only the public key is committed
    in-repo; when a key already exists at the resolved location, it is left intact and reported, and
    regeneration occurs only under an explicit force option.
  - *Property*: for any offered or selected key location, the resolved absolute path is never inside the
    repository working tree.
- **ONBRD-FR-008**: The system shall seed the baseline configuration (a risk-tier table and a roles
  definition) and make the selected language adapter available, without overwriting configuration that
  already exists.
  - *Acceptance*: on a fresh repository the seeded risk-tier and roles configuration exist with valid
    content and the selected adapter is available; where such configuration already exists, its content is
    preserved and reported as "kept."
- **ONBRD-FR-009**: The system shall be idempotent: re-running it on an already-initialized repository shall
  preserve the existing ledger, keys, and configuration, report what already existed versus what was added,
  and exit successfully.
  - *Acceptance*: a second run over a completed onboarding neither truncates nor rewrites the ledger and does
    not regenerate an existing key; it reports created-versus-existing and exits successfully.
  - *Property*: running the flow N times produces the same on-disk trust-spine state as running it once
    (apart from report text).
- **ONBRD-FR-010**: When onboarding completes, the system shall detect whether the repository already
  contains source code and print next-step guidance accordingly — a spec-authoring entry point for an empty
  repository, and the brownfield adoption sequence for a repository with existing code.
  - *Acceptance*: on an empty repository the closing guidance names the spec-authoring/lifecycle entry
    point; on a repository with existing source it names the brownfield sequence (report-only → characterize
    → diff-scoped enforcement); when the stack has no matching adapter, the guidance says so and points to
    the adapter contract.
  - *Property*: when a recognisable stack marker is present, the detected default language matches the
    adapter whose detection rules match that marker.

#### The documentation

- **ONBRD-FR-011**: The README shall present the autonomous lifecycle flow before the manual/step-by-step
  flow.
  - *Acceptance*: in the README, the section describing the one-command autonomous run appears above the
    section describing the manual, stage-by-stage flow.
- **ONBRD-FR-012**: The README shall state the enterprise, high-autonomy value proposition prominently near
  the top.
  - *Acceptance*: a positioning statement conveying a secure, trustworthy, enterprise-ready framework for
    building software with high autonomy in agentic mode appears above the deep-dive sections.
- **ONBRD-FR-013**: The README shall include a supported-languages and technology-stack section that lets a
  reader determine fit without reading source.
  - *Acceptance*: a table lists each supported language with its format, lint, type-check, test (and
    coverage), and mutation tooling, its design-oracle support, and a status; the entries match the
    reference adapters; a reader with a TypeScript stack can confirm support from the table alone.
- **ONBRD-FR-014**: The user-facing documentation set shall be reviewed for readability, completeness, and
  absence of unresolved open questions, and gaps found shall be corrected.
  - *Acceptance*: a completeness review is recorded; the guided-onboarding flow and its next-step guidance
    are documented consistently across the README, the getting-started guide, and the CLI reference; no
    unresolved "to-do"/"to-be-decided"/open-question marker remains in the reviewed user-facing docs, and any
    newly identified gap is either closed or explicitly tracked.

### Non-Functional Requirements

- **ONBRD-NFR-001**: The onboarding flow shall never store the private signing key inside the repository
  (ref 3PWR-NFR-005).
  - *Acceptance*: after any onboarding run, no private-key file exists within the repository working tree;
    only the public key is present in-repo.
- **ONBRD-NFR-002**: The onboarding flow shall complete fully offline, making no network or model call.
  - *Acceptance*: the flow succeeds with networking disabled and issues no outbound request.
- **ONBRD-NFR-003**: The onboarding flow shall degrade gracefully from interactive to non-interactive,
  producing an equivalent result via defaults when no interactive terminal is available.
  - *Acceptance*: an interactive run that accepts all defaults and a non-interactive run over the same fresh
    repository produce equivalent trust-spine state.
- **ONBRD-NFR-004**: The onboarding flow shall not weaken, remove, or bypass any gate or gate threshold, nor
  suppress a mandatory human gate (ref 3PWR-FR-032/042/006/037).
  - *Acceptance*: no risk-tier threshold is lowered by the flow; the recorded autonomy preference still
    causes the lifecycle to stop at the two mandatory human gates.
- **ONBRD-NFR-005**: The onboarding flow shall not introduce a new *required* runtime third-party dependency
  for interactive prompting.
  - *Acceptance*: the feature runs with the engine's existing dependency set; no new mandatory package is
    added for prompting.
- **ONBRD-NFR-006**: The user-facing documentation shall meet baseline readability and accessibility
  practices — descriptive link text, tables with header rows, and language labels on fenced code blocks.
  - *Acceptance*: reviewed docs use meaningful link text (no bare "click here"), the supported-languages
    table has a header row, and new or edited code fences carry a language hint.

## Success Criteria *(mandatory)*

- **ONBRD-SC-001**: A brand-new empty repository is taken from "no trust spine" to "ready to author a spec"
  by a single guided onboarding run, with no further manual trust-spine setup required.
- **ONBRD-SC-002**: Re-running onboarding on an already-onboarded repository makes no destructive change (the
  ledger, keys, and hand-edited configuration are preserved) and exits successfully.
- **ONBRD-SC-003**: In every offered key-placement option, the resulting private key resides outside the
  repository working tree.
- **ONBRD-SC-004**: A reader can determine, from the README's supported-languages table alone, whether a
  given stack (for example TypeScript) is supported and what tooling backs it.
- **ONBRD-SC-005**: The README presents the autonomous flow before the manual flow and carries the
  enterprise, high-autonomy positioning statement above the deep-dive sections.
- **ONBRD-SC-006**: The documentation completeness review is recorded and the reviewed user-facing docs
  contain no unresolved open-question markers.
- **ONBRD-SC-007**: Every functional requirement has ≥1 linked verification across the appropriate layers
  (3PWR-FR-030/065) — a test for wizard behaviour (unit/integration/e2e), or a recorded documentation
  review plus a structural lint check for the documentation requirements.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id ONBRD --stage spec`; appended to the signed ledger)_ | | |
