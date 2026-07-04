# 3Powers — Framework Specification (Epic)

> **Spec is the law. Agents execute. Gates judge.**
> A spec-driven framework that turns intent into trusted software, where execution is done by agents and trust is recovered by an independent, deterministic judiciary — without depending on any single model, language, LLM provider, or CI/CD platform.

| | |
|---|---|
| **Working name** | 3Powers (alternatives: *Trias*, *Trias Politica*, *TriBranch*) |
| **Spec ID** | `3PWR` |
| **Author** | Carlo Verzeri |
| **Document type** | Epic-level specification (the *what* and *why*; the *how* is deferred to a separate implementation plan) |
| **Version** | 0.2 · Draft |
| **Status** | Awaiting clarify pass and sign-off |
| **Substrate** | A native, provider-agnostic executive (an agent-runner contract + engine-owned lifecycle prompts + the judiciary plugins) over **Git**, with optional external model gateways (internal proxy / cloud model service / OpenAI-compatible gateway) as pass-through model access — see §3 Constraints. *(Amended by EXEC, spec 009; was "Layered on GitHub Spec Kit".)* |
| **Source of method** | *The AI-First SDD Playbook*, Season 1 v1.0 (Verzeri, June 2026) |

> **Revision note (v0.2).** Incorporates author feedback: work type is now *inferred*, not declared (FR-001, FR-058); requirement IDs are project-unique and namespaced by spec ID (FR-059, identifier scheme below); explicit context and session management to preserve model performance (FR-013, FR-060, FR-061); the Phase A / Phase B testing model with the oracle as the binding check and all three test layers required (FR-062–FR-065); build provenance and the deploy gate made first-class (FR-066–FR-068); and full versioning, reversibility, and self-containment of the record (FR-069–FR-071).

---

## 1. Why (problem and users)

### 1.1 The problem

Generative models broke the old bundle where working code was itself proof that someone understood the problem. A passing build no longer proves intent was met. The scarce thing is no longer the code; it is the confidence that the code does what was meant. Reviewing every generated line by hand does not scale, and letting the same model write the spec, the code, the tests, and the first review fuses the legislative, executive, and judicial powers into a single mind — the **separation-of-powers collapse**, where everything agrees with everything because it all came from one source.

Existing agentic scaffolds (GitHub Spec Kit among them) solve the *legislative scaffolding* and a large part of the *executive orchestration* (multi-agent dispatch, workflow runs with human gate steps, presets, extensions). What they deliberately leave out is the **judiciary**: an independent oracle the executing agent cannot author, a deterministic gate suite that returns the same verdict regardless of which model wrote the code, and an enforcement layer that makes a red gate actually block. They also offload blocking to a CI/CD platform, which couples trust to one vendor and one always-online pipeline.

3Powers supplies that missing judiciary and makes it portable — model-agnostic, language-agnostic, provider-agnostic, and free of any mandatory CI/CD platform. It also owns its **executive**: a native, provider-agnostic agent-runner drives headless coding agents directly (A1′/A3′; see §3 and §6), so a single developer or a large team can specify a unit of work, let agents build it, and read a trustworthy verdict on whether it matches the spec — with no dependency on an external orchestration substrate or an IDE. *(v0.2 originally layered the executive on GitHub Spec Kit; it was brought in-house by EXEC/SLIM — see §17.)*

### 1.2 Who it is for

- **The human lead / solo builder** who wants to author intent, sign off on the law, and read evidence — not re-read diffs. Holds final judicial authority.
- **Engineering teams** adopting agentic delivery who need the executive's work checked by something independent before it merges.
- **Regulated and high-risk teams** that must produce traceable evidence (spec → task → commit → test → verdict → sign-off → provenance) on demand.
- **Tool authors** who want to add language adapters, gate plugins, presets, or extensions to a shared, open ecosystem.

### 1.3 What success looks like in the world

A user states a unit of work as plain-language intent. 3Powers infers what kind of work it is, drives it through the eight-stage lifecycle using whichever agents and models the user configured, authors an oracle the coder never touched, runs a deterministic gate suite across whatever languages the change spans, and writes a signed, tamper-evident verdict. Every step is versioned and reversible, and the whole record is self-contained in the repository. The user spends judgment on the spec and on the residual the gates cannot express — and trusts the green verdict because an independent branch produced it.

---

## 2. Vision in one paragraph

3Powers is an open, portable **judiciary kit** for spec-driven, agentic software delivery. It enforces the separation of powers — the spec as law, agents as executive, gates and human review as judiciary — across any model family, any language toolchain, any LLM provider, and with no required CI/CD platform. Its deterministic gate engine, its signed verdict ledger, and its signed build provenance give a human and the agents themselves a single, machine-readable answer to one question: *does this code do what the spec said, checked by something the executive could not fake — and can I prove what shipped and roll it back?*

---

## 3. Architectural constraints & assumptions (givens, not implementation)

These are decided inputs to the design, not internal *how*:

- **A1′ — 3Powers owns its executive.** *(Amended by EXEC, spec 009; was "Built on Spec Kit (Path A)".)* 3Powers ships its own executive: a declarative **agent-runner** contract, engine-owned lifecycle prompts, and the gate/judiciary plugins. It dispatches each role to a headless coding agent (Claude Code, an OpenAI Codex-class CLI, the GitHub Copilot CLI, OpenCode, Aider, …) described by a manifest. GitHub Spec Kit is no longer the dispatch substrate or a runtime dependency; interop export remains possible but is not required.
- **A2 — Git is the substrate.** The repository (and, for the read-path-isolated oracle, a sanitized worktree) is the agent's working environment, the home of the authoritative spec, and the home of the versioned history. Git is assumed; a specific Git host is not.
- **A3′ — Provider-agnosticism via a pluggable agent runner.** *(Amended by EXEC, spec 009; was "Provider-agnosticism via [Spec Kit] dispatch".)* Any headless coding agent described by a manifest is eligible to fill a role, and model access is routed through the organization's own gateway via pass-through environment/config. The engine **dispatches agents and passes gateway config through but calls no model API itself**, and — the invariant that carries the thesis — **a model never produces or alters the verdict** (the judiciary stays deterministic and model-free, 3PWR-NFR-001).
- **A4 — CI is optional, never the source of trust.** Where a CI/CD platform exists, 3Powers may re-validate in it, but the guarantee — verdicts, provenance, and reversibility — must hold locally and offline.
- **A5 — Polyglot from day one.** Language support is a plugin contract, not a hard-coded assumption; v1 ships the contract plus at least two reference adapters.
- **A6 — Self-application.** 3Powers is built and maintained using 3Powers.

---

## 4. Risk tiers (per capability area)

The framework declares its own tiers because its failure modes differ in blast radius. A weakness in the trust spine lets bad code through *everywhere*; a weakness in a CLI banner does not.

| Capability area | Tier | Rationale |
|---|---|---|
| Oracle separation (§7), deterministic gate engine (§8), verdict ledger, provenance & reversibility (§9) | **High-risk** | These *are* the trust. A defect here silently re-opens circular validation or lets a tampered artifact ship. |
| Executive orchestration (§6), legislative authoring (§5), agnosticism (§10), config & constitution (§11) | **Standard** | Important to correctness, but their failures are visible and recoverable. |
| CLI ergonomics, human-readable formatting, docs, catalog metadata | **Cosmetic** | Lint and types only; no mutation, no ceremony. |

High-risk areas carry the full gate set at their strictest thresholds, including mutation testing and model diversity. 3Powers must apply these tiers to *its own* development (NFR-006).

---

## 5. Legislative — Intake & spec authoring

**Why.** The spec is the law every later stage answers to. A misframed requirement here becomes a defect paid for in every stage after it, and it is the cheapest place to fix a mistake. This area makes the playbook's soft expectations mandatory. The human gives intent in plain language; the framework does the structuring; the human always approves the result.

### Identifier scheme

Every specification carries a unique spec ID (this document's is `3PWR`). Within a project, every requirement ID is globally unique by being **namespaced with its spec ID** — the canonical form of each requirement below is `3PWR-FR-###` / `3PWR-NFR-###`. The short forms `FR-###` / `NFR-###` are used in this document for readability and resolve to their namespaced form. This makes any task, commit, test, or verdict trace to exactly one spec, and removes the per-feature ID collision noted in the playbook's Appendix K. (Mandated by FR-059.)

**Functional requirements**

- **FR-001** The system shall accept a free-form statement of intent describing the *what* and the *why*, and shall not require the human to pre-classify the kind of work.
- **FR-058** When intent is submitted, the system shall infer the kind(s) of work it represents — and a single intent may resolve to more than one kind (for example, a styling change *and* a behavior fix in the same request) — using that inference only to shape the oracle strategy and the applicable gates, never to bypass the human sign-off on the resulting spec (FR-006).
- **FR-002** When intent is submitted, the system shall scaffold a specification expressed in EARS form, with every requirement carrying a project-unique, spec-namespaced identifier.
- **FR-059** The system shall assign every specification a unique spec ID and shall namespace every requirement ID with that spec ID, so requirement IDs are globally unique within the project and every requirement traces to exactly one spec.
- **FR-003** The system shall require a declared risk tier (`Cosmetic`, `Standard`, or `High-risk`) on every specification before planning may begin.
- **FR-004** The system shall require an explicit non-goals section on every specification.
- **FR-005** When a specification is authored, the system shall run a clarify pass that surfaces unstated scope, missing edge cases, undefined terms, and unmeasurable criteria, write the resolved answers back into the specification, and block advancement while any acceptance criterion remains unmeasurable.
- **FR-006** The system shall require a recorded human sign-off (approver identity and timestamp) on the specification — checked against the written FRs and NFRs — before any implementation artifact is produced.
- **FR-007** If a specification contains implementation detail (a named database, framework, schema, or stack choice), then the system shall flag it as out of place in the law and route it to planning.
- **FR-008** Where the inferred work involves a defect, the system shall require a failing regression test that reproduces the incident, authored as the acceptance criterion, before any fix is implemented.
- **FR-009** Where the inferred work involves a design change, the system shall accept design oracles (for example visual-regression, structural, accessibility, or component-contract checks) as the acceptance criteria and map them to the applicable subset of gates.
- **FR-010** The system shall store the authoritative specification in a versioned `specs/` directory inside the repository, never in an external ticketing or wiki tool, while permitting optional one-way connection to such tools.

**Acceptance signals.** Free-form intent produces an EARS spec with project-unique IDs and a correctly inferred work kind; the clarify pass raises nothing new; a person has signed off against the FRs/NFRs; the spec is committed under `specs/`.

---

## 6. Executive — Orchestration

**Why.** The hard part of agentic work is not knowing what to do; it is making a squad of agents do it well without their context decaying or their powers fusing. This area runs the eight stages as a resumable loop with the model switches, context discipline, and build-time testing the playbook requires.

**The loop, roles & resumability**

- **FR-011** The system shall drive the eight-stage lifecycle (Discovery, Spec, Plan, Build, Verify, Review, Ship, Observe) as a resumable workflow with explicit human gate steps between branches.
- **FR-012** The system shall dispatch each role (spec author, clarifier, planner, coder, oracle author, reviewer) to a separately configurable agent and model, without depending on any single provider.
- **FR-019** The system shall support resuming or aborting a run from any gate or failure point, persisting run state across sessions.

**Sessions & context (preserving model performance)**

- **FR-013** When work crosses a branch handoff, the system shall start a fresh agent session and reload the constitution, the relevant `AGENTS.md`, and the committed artifact being acted on; and the policy for *when* each model's session is reset shall be configurable, so model performance is preserved as context fills.
- **FR-060** The system shall apply a deliberate context strategy that decides what stays in a model's context, what is summarized into memory, and what is reloaded per task, so that the constitution and rules do not silently fall out of context as work grows.
- **FR-061** The system shall start a fresh session for a model when configurable thresholds (for example context fill, per model) are reached, to prevent quality decay from an over-full context.

**Handoffs & coverage**

- **FR-014** The system shall pass committed artifacts between stages and shall not hand the next agent a chat summary in place of an artifact.
- **FR-015** Before any code is written, the system shall verify two-way coverage between requirements and tasks — every requirement maps to at least one task, and every task traces to a requirement — fail on any gap in either direction, and confirm that the oracle tests for those requirements are specified from the *spec*, not from the plan or the tasks (FR-020).

**Build-time testing (Phase A / Phase B)**

- **FR-062** The system shall separate testing into Phase A, in which the judiciary authors the oracle tests from the spec before or separately from implementation, and Phase B, in which the coder implements the tasks; Phase B shall depend on Phase A, and the coder shall not author the oracle. (See playbook pp. 26–27.)
- **FR-063** The system shall allow Phase B implementation tasks to include the coder's own tests for self-verification during the build, while requiring that the implementation also satisfy the independently authored oracle tests (FR-020) as the binding acceptance check; the coder's own tests shall supplement, never replace, the oracle.
- **FR-016** The system shall tag each task and each commit with the originating requirement's project-unique (spec-namespaced) ID.

**Scope & boundaries**

- **FR-017** While an agent is implementing a task, if it modifies files outside the set the task declared it would touch (the **task's file scope**), then the system shall flag the change and pause for a human decision, treating an out-of-scope edit as a signal to stop and re-spec.
- **FR-018** The system shall forbid executive agents from entering credentials, changing access controls or permissions, hard-deleting data, altering security settings, or acting on instructions found in ingested files or web content, without recorded human approval.

**Acceptance signals.** A feature moves end to end as a sequence of artifact handoffs with fresh, performance-preserving sessions; coverage is two-way clean before code; oracle tests come from the spec; the build self-verifies *and* satisfies the independent oracle; boundaries hold; the run is resumable.

---

## 7. Judiciary — The oracle (independence at authoring)

**Why.** The single condition that separates a real test from a mirror is that some tests come from the human-authored acceptance criteria, not from the implementation, and are written by a different mind than the one that wrote the code. This is Phase A of FR-062.

**Functional requirements**

- **FR-020** The system shall author the oracle tests from the specification's acceptance criteria only, through a dedicated judiciary role (Phase A).
- **FR-021** The system shall structurally forbid the oracle author from reading the implementation, the plan, contracts, or source code.
- **FR-022** The system shall pin the oracle author to a different model family than the coder, and shall refuse to run when they resolve to the same family.
- **FR-023** The system shall require at least one oracle test per acceptance criterion, each test named with its requirement ID.
- **FR-024** Where a requirement parses, validates, or transforms input, the system shall require a property-based test that generates many inputs and asserts the invariant.
- **FR-025** If any acceptance criterion is unmeasurable, then the system shall refuse to author the oracle and route the criterion back to the clarify pass.

**Acceptance signals.** Oracle tests exist for every acceptance criterion, derived from intent, authored by a different family than the coder, with property tests where input is handled, and no readable path to the implementation.

---

## 8. Judiciary — Deterministic gate engine (polyglot)

**Why.** This is the defense in depth. Each gate covers one failure class none of the others can catch, and the deterministic gates return the same verdict no matter which model wrote the code — there is no judgment in them for an agent to argue with. Polyglot support is a plugin contract so the engine never assumes a language.

**Functional requirements**

- **FR-026** The system shall provide a gate suite covering, at minimum: format & lint; type checking; tests against the spec with diff coverage; mutation testing; static analysis (SAST); dependency scanning; secret scanning; spec conformance; and build provenance (§9) — executed cheapest-first.
- **FR-027** The system shall expose a language-adapter contract through which each language supplies its own format, lint, type, test, coverage, and mutation tooling behind a normalized interface, and shall ship at least two reference adapters and an adapter conformance suite at v1.
- **FR-028** The system shall run language-agnostic gates (secret scanning, dependency policy, spec conformance, build provenance) in its core, independent of any language adapter.
- **FR-029** The system shall measure test coverage on the changed lines of a change, not on the whole repository.
- **FR-030** The system shall fail the spec-conformance gate when any requirement in the specification has no linked test, using a deterministic trace.
- **FR-064** The system shall support and, per risk tier, require all three test layers — **unit, integration, and end-to-end** — for a change.
- **FR-065** The system shall make every test, at every layer, traceable to a requirement ID, and the spec-conformance gate shall account for all three layers.
- **FR-031** The system shall scope mutation testing to changed or high-risk files on a per-change run and run the full sweep on a schedule, reporting each surviving mutant as an actionable missing assertion.
- **FR-032** The system shall read every gate threshold (coverage, mutation score, model diversity, verification spend) from a single risk-tier configuration, and shall never satisfy a gate by dropping or weakening it.
- **FR-033** When a gate run completes, the system shall emit one normalized, machine-readable verdict whose schema is identical across languages, together with a human-readable summary.
- **FR-034** The system shall make each failure in the verdict actionable by naming its class — a surviving mutant names a missing assertion, a coverage drop names an untested branch, a scanner finding names a vulnerability class, an untested requirement names its ID.
- **FR-035** If a change introduces gate-gaming — an inline lint disable, a new type suppression, a deleted assertion, or a weakened pipeline or gate configuration — then the system shall flag it for mandatory human review rather than letting it pass.

**Acceptance signals.** All gate classes run, cheapest-first; unit, integration, and e2e all run and trace to the spec; thresholds follow the tier; a change spanning two languages produces one unified verdict; gaming attempts are surfaced, not silently absorbed.

---

## 9. Judiciary — The trust spine: review, ledger, provenance & reversibility

**Why.** Branch protection is where every preceding gate becomes real; until a red gate stops an advance, the whole judiciary is advice. Because 3Powers removes the CI/CD platform as the enforcer, it must recover that property locally through independent, tamper-evident records — of the *process* (the verdict ledger), of the *artifact* (build provenance), and of the *history* (versioning and reversibility). This is the area that *gives trust back*.

### Residual review

- **FR-036** When the deterministic gates are green, the system shall run an automated residual review on a different model family than the coder, scoped to what gates cannot catch — intent fit, architecture, subtle business-logic errors, and security design — citing requirement IDs and flagging any intent gap as a new requirement rather than a code fix.
- **FR-037** The system shall require a human approver, who is a person and not the agent's prompter, to sign off on the evidence and the residual before a change may advance.

### Verdict ledger

- **FR-038** The system shall maintain an append-only, hash-chained ledger recording, per change, every gate verdict, the residual review, and the human sign-off.
- **FR-039** The system shall sign each ledger entry with a key that the executive agents do not hold (an **independent signer identity**).
- **FR-040** The system shall provide a verify operation that recomputes the ledger's hash chain and signatures and fails on any tampering, gap, or break in the chain.
- **FR-041** The system shall provide a local, CI-independent enforcement hook that refuses to advance a change when a required gate is red, when the ledger fails to verify, or when the tier-required human sign-off is absent.
- **FR-042** The system shall apply enforcement uniformly to every actor, including administrators and agents, and shall provide no fast path that skips review for agent-authored changes.
- **FR-043** Where a CI/CD platform is present, the system shall be able to re-validate the same verdicts within it, without depending on that platform for the guarantee.

### Build provenance & the deploy gate

A signed, verifiable record of where a build came from — *this exact artifact, identified by its hash, was built by this run, from this commit, in this repository, with this list of dependencies* — so you can prove that what runs in production is what you built, read a vulnerable build's contents off the artifact during an incident, fail a tampered artifact at the deploy gate during a supply-chain attack, and answer "where did this come from and what is in it" on demand when most of the code was generated.

- **FR-066** For every released artifact, the system shall produce a signed, verifiable provenance record binding the artifact (identified by its hash) to the source commit, the repository, the producing run, and the complete list of dependencies (a software bill of materials).
- **FR-067** The system shall verify provenance at the deploy gate and refuse any artifact whose provenance is missing or fails verification, because the protection lands at verification, not at generation.
- **FR-068** The system shall sign provenance with the same independent signer identity used by the verdict ledger (FR-039), so that provenance can be produced and verified without a hosted CI/CD pipeline; the 3Powers run that built the artifact shall be the issuing authority.

> *Suitable practices (non-binding): keyless signing such as Sigstore, a SLSA-style provenance record, and an SBOM tool such as `syft`. The mechanic — a signed record verified at deploy — is the law; the tool is swappable.*

### Versioning, history & reversibility (self-contained record)

- **FR-069** The system shall version every artifact (spec, plan, tasks, oracle tests, code, verdict, sign-off, provenance) and every stage transition, preserving an ordered, complete history.
- **FR-070** The system shall allow any recorded change or stage advance to be reversed to a prior recorded state.
- **FR-071** The system shall keep the complete record — specs, plans, tasks, tests, code, verdicts, the ledger, run state, and provenance — self-contained within the repository, reconstructable with no external service.

**Acceptance signals.** A change cannot advance with a red required gate, an unverifiable ledger, or a missing sign-off; tampering with a past verdict is caught by `verify`; a tampered release artifact fails provenance verification at the deploy gate; every step is versioned and any state is reversible; the entire history reconstructs from the repository alone, with the network and any CI platform switched off.

---

## 10. Agnosticism (model · language · provider · CI/CD)

**Why.** These are the hard portability promises that distinguish 3Powers from a single-stack tool. They are stated as requirements, not aspirations.

- **FR-044** The system shall bind roles to models and providers through configuration, and shall allow a model or provider to be swapped without changing the workflow definition.
- **FR-045** The system shall behave language-agnostically: no gate's behavior shall assume a specific language beyond what its adapter declares.
- **FR-046** The system shall operate without any specific LLM provider; any agent dispatchable through the chosen substrate may fill any role, subject to the model-diversity rule.

---

## 11. Configuration, constitution & evaluation

**Why.** The rulebook keeps agents inside the system, and the prompts and constitution are themselves software that needs its own regression tests.

- **FR-047** The system shall load a versioned constitution of non-negotiable principles and apply it at every stage.
- **FR-048** The system shall load per-component `AGENTS.md` (commands, pinned versions, boundaries), treat it as advisory guidance, and rely on the gates for enforcement.
- **FR-049** The system shall treat the risk-tier-to-threshold table as the single source governing coverage, mutation, model-diversity, and verification-spend decisions.
- **FR-050** The system shall treat prompts, skills, and the constitution as versioned software with an associated evaluation set, run that evaluation set whenever any of them changes, and block on a regression.

**Acceptance signals.** Changing a prompt or constitution rule triggers the eval set; a regression blocks; the tier table is the only place thresholds live.

---

## 12. Brownfield adoption (Stage Zero)

**Why.** Most teams do not start clean. The framework must spread service by service without forcing a stop-the-world migration.

- **FR-051** The system shall support gradual adoption by holding only new and changed code to the full process, leaving existing code untouched until it is modified.
- **FR-052** The system shall support running gates in report-only mode and then ratcheting them to blocking on changed code only, so legacy debt does not wall off every merge at adoption.
- **FR-053** The system shall reconstruct a specification for a legacy module on request and pin that module's current behavior with characterization tests serving as its oracle.

**Acceptance signals.** A first feature ships with a real spec and spec-derived tests in an existing repo; legacy paths are pinned by characterization tests before they are changed; gates block only the diff.

---

## 13. Observe & feedback (closing the loop)

**Why.** Production is where software is graded, and the loop must return what is learned to the spec rather than to ad-hoc patches.

- **FR-054** The system shall support instrumenting the target software against the specification's non-functional requirements and routing production signal — incidents, missed objectives, real usage — back into the legislature as new intent rather than as patches applied in place.
- **FR-055** Where the target system itself contains agents taking actions at runtime, the system shall require tamper-evident, attributable logging of every such action.

**Acceptance signals.** A specified NFR has a live check in production; a production lesson re-enters Stage 1–2 as a new requirement; agentic runtime logs are attributable and tamper-evident.

---

## 14. Off the happy path (emergencies & deviations)

**Why.** A process that cannot bend under fire gets abandoned; one that bends without discipline rots. Both paths are pre-agreed and recorded.

- **FR-056** The system shall provide an emergency fast path that may defer mutation testing and full coverage but shall never skip the deterministic security and secret gates, the human sign-off, or provenance, and shall require a recorded cleanup (a written requirement and restored thresholds) within one working day.
- **FR-057** The system shall provide a reversible, documented deviation mechanism that relaxes named gates with a recorded reason and a defined way back, and shall pull cosmetic-tier code that reaches production back up to its real tier.

**Acceptance signals.** An emergency fix carries a reproducing regression test, a sign-off, provenance, and a one-day cleanup; a deviation is recorded with its reason and its reversal path.

---

## 15. Non-functional requirements (cross-cutting)

- **NFR-001** Given identical inputs, the deterministic gates shall produce identical verdicts regardless of which model produced the code under test.
- **NFR-002** The deterministic floor (format, lint, type) shall return within seconds; the oracle gate (tests + diff coverage) within roughly one to three minutes on changed files; mutation on high-risk changed files within roughly two to five minutes; with the full sweep deferred to a schedule.
- **NFR-003** The system shall run on Linux, macOS, and Windows.
- **NFR-004** The system shall operate fully offline and air-gapped once its dependencies are present, with no mandatory cloud service or CI/CD platform — including verdicts, provenance, and reversibility.
- **NFR-005** The independent signer key shall never be exposed to executive agents and shall never be stored in plaintext in the repository or the ledger.
- **NFR-006** 3Powers shall be built and maintained using 3Powers, and its own repository shall pass its own gates at the High-risk tier for the trust-spine components.
- **NFR-007** Adding support for a new language shall require only implementing the adapter contract and passing the adapter conformance suite, with no change to the gate-engine core.
- **NFR-008** The verdict schema shall be documented, versioned, and stable, and shall be the single artifact consumed by both agents and humans.
- **NFR-009** Verification spend (number and strength of models touching a change) shall scale by risk tier from the same configuration, defaulting to the strongest model only on hard planning, hard implementation, and judiciary work.
- **NFR-010** Every advance shall be auditable: an unbroken chain of spec → task → commit → test → verdict → sign-off → provenance shall be reconstructable from the repository and the ledger alone.
- **NFR-011** A human shall be able to read a failed verdict and identify the failing gate, the failure class, and the offending requirement or file without opening any agent transcript.
- **NFR-012** The framework shall be open-source and license-clean, and third parties shall be able to author language adapters, gate plugins, presets, and extensions.
- **NFR-013** The system shall guarantee tamper-*evidence*, not tamper-*proofing*: evasion of local enforcement shall be detectable through the ledger and the provenance records, and the system shall document that it cannot guarantee tamper-proof local blocking (see Non-goals).
- **NFR-014** The system shall have no required runtime dependency on any single LLM provider, model vendor, language toolchain, or CI/CD platform.
- **NFR-015** A flaky gate shall be quarantinable out of the blocking set and surfaced as broken, and shall never be silently ignored or used as a reason to bypass the process.
- **NFR-016** Released 3Powers artifacts shall carry build provenance and a software bill of materials (FR-066), and the install path shall verify them before use.

---

## 16. Non-goals

3Powers is **not**:

- **A model runtime or a model gateway.** *(Amended by EXEC, spec 009; the former non-goals "a new agent harness" and "a replacement for Spec Kit" are retired — the native executive is now in scope, A1′/A3′.)* 3Powers owns a thin agent-runner that dispatches external coding agents; it does not run models itself and does not implement the gateway/keys/budgets/RBAC/SSO/audit layer — those are inherited by pointing the agent at the organization's gateway.
- **A CI/CD platform.** CI is optional re-validation, never the source of trust (A4). Provenance is produced and verified without a hosted pipeline (FR-068).
- **An IDE, editor, or language runtime.** It orchestrates existing per-language tools through adapters; it does not build or run code itself beyond invoking those tools.
- **An author of intent.** A human writes the intent and signs off on the law; the framework infers the *kind* of work but never approves its own spec.
- **A guarantee of correctness.** It provides risk-proportioned assurance with independent layers behind it, not proof.
- **A guarantee of tamper-proof local enforcement.** Without an independent always-on runner, local blocking can be bypassed by a sufficiently privileged actor; 3Powers makes such evasion *evident*, not impossible (NFR-013).
- **A universal language pack at v1.** v1 ships the adapter contract plus at least two reference adapters; broader coverage accrues through the ecosystem.
- **A project-management tool.** External trackers may connect read-only; the repository owns the authoritative spec.

---

## 17. Scope phasing (v0.1 → v1.0)

This is scope definition, not an implementation plan.

| Slice | In scope |
|---|---|
| **v0.1 — Trust spine (MVP)** | Free-form intake with inferred work typing and project-unique IDs (§5); legislative authoring with mandatory tier, EARS, non-goals, sign-off; oracle separation with forbidden reads and model pinning (§7); the deterministic floor + the three oracle-bearing gates (tests/diff-coverage, mutation on high-risk, spec-conformance) with unit + integration + e2e support (§8 subset); the adapter contract + **two** reference adapters; one end-to-end workflow with human gates and context/session management (§6); a signed, hash-chained verdict ledger + local enforcement (§9); and **versioning, history & reversibility of all artifacts and steps** (FR-069–FR-071). |
| **v0.5 — Full judiciary** | Remaining gates (SAST, dependency, secret); **build provenance with deploy-gate verification, signed by the shared independent identity** (FR-066–FR-068); automated residual review; the full risk-tier threshold config; the prompt/constitution evaluation harness (§11). |
| **v1.0 — Lifecycle & ecosystem** | Brownfield Stage Zero (§12); observe/feedback loop (§13); emergency and deviation paths (§14); catalog distribution; a third reference adapter; hardened ledger + `verify` UX; full documentation; complete self-application (NFR-006). |

**Native-executive track (post-v1.0 amendment — the new solution + roadmap).** The v0.1–v1.0 slices above
were built on the GitHub Spec Kit substrate (original A1). Practice showed that substrate could not drive
agents headlessly from outside an IDE (a terminal `3pwr run` had no agent to pilot inside e.g. GitHub
Copilot), so the executive was brought in-house — A1′/A3′ (§3):

| Spec | Status | Scope |
|---|---|---|
| **EXEC** (spec 009) | delivered | A native, **provider-agnostic agent-runner**: `3pwr run` dispatches each stage to a headless coding agent (Claude Code / Codex CLI / GitHub Copilot CLI / OpenCode / Aider) described by a declarative manifest, runs the deterministic gate suite in-process, and stops only at the two human gates. Enterprise model access (Bedrock/Vertex/Azure/LiteLLM/internal proxy) is inherited via env pass-through; the engine calls no model API and a model never produces the verdict. |
| **SLIM** (spec 010) | delivered | Removes GitHub Spec Kit entirely (runner, vendored prompts/workflows, `--with-speckit`, the dependency pin); `3pwr init` seeds the agent manifests instead. |
| **RUNLIVE** (spec 011) | delivered | Hardens the executive: per-stage **artifact contracts**, robust dispatch (timeout/retry/streaming), a **gated live end-to-end proof**, the **async hosted backend** (e.g. the GitHub Copilot coding agent for shops without a local headless CLI), and per-stage commit checkpoints. |
| **DOCX** (spec 012) | delivered | Truth-up STATUS + docs to the native executive and retire the last Spec-Kit residue (the `agentpins` model-pin module + its config-drift feature; the `.specify/` tree, relocated to `.3powers/`). |
| **PHASE** (spec 013) | draft | Phased execution: real `plan`/`tasks` stage prompts + hard artifact contracts in a per-feature workspace (`spec/` + artifacts folder, every stage leaving a checked, versioned artifact); an advisory per-model **context budget** (default ≈110k tokens) sizing plan phases; **one fresh session per phase** with the handoff set reloaded (delivers FR-060/061 at engine level); **parallel subagent dispatch** for disjoint-file-scope phases with deterministic ledger ordering. |

The **judiciary** (§7–§9) — oracle independence, the gate suite, the signed trust spine — is unchanged by
this track; only the executive substrate changed.

---

## 18. Definition of Done (epic acceptance for v1.0)

The epic is done when:

- A user can take free-form intent (a feature, a bug, or a mixed design-plus-behavior change) from words to a signed verdict end to end, on at least three languages, with no CI/CD platform involved, and the work kind is inferred, not declared.
- The oracle is provably authored by a different model family than the coder, has no readable path to the implementation, and the implementation both self-verifies and satisfies that oracle across unit, integration, and e2e layers.
- A change spanning two languages produces one normalized verdict that both an agent and a human can act on.
- A required red gate, an unverifiable ledger, or a missing sign-off each independently blocks advancement; tampering with a prior verdict is caught by `verify`; and a tampered release artifact fails provenance verification at the deploy gate.
- Every step is versioned, any recorded state is reversible, and the full history reconstructs from the repository alone.
- Adding a fourth language requires only a new adapter passing the conformance suite.
- 3Powers' own repository is delivered through 3Powers at the High-risk tier for its trust-spine components.

---

## 19. Open questions (for the clarify pass)

Sharp questions whose answers would most change the build:

1. **Signer custody (now also underpins provenance and history integrity).** How is the independent signer identity provisioned for a solo developer with no server, while keeping the key out of the executive agents' reach (FR-039, FR-068, NFR-005)? This one key roots the ledger, the provenance, and the credibility of the versioned history.
2. **Model-family taxonomy.** What defines "a different model family," and who maintains that map as providers and models proliferate (FR-022, FR-036)?
3. **Design oracles.** For inferred design work, what is the canonical, mostly-deterministic oracle set (visual regression, accessibility, token conformance, contract checks), and which parts are inherently judgmental (FR-009)?
4. **Shared ledger & history.** How do the local verdict ledger and the versioned history behave with multiple developers pushing concurrently — how are chains and reversals merged and conflicts resolved (FR-038, FR-069–FR-071)?
5. **Provenance trust root without a CI runner.** The producing 3Powers run is the issuing authority (FR-068); what minimum attestation and key-custody arrangement makes that credible to an external third party, given there is no hosted pipeline as a trust root?
6. **Diff coverage in polyglot changes.** How is changed-line coverage attributed when a single change spans multiple languages and toolchains (FR-029)?
7. **Substrate coupling — resolved by EXEC/SLIM (§17).** Formerly: how are Spec Kit breaking changes insulated (A1)? The executive is now native (A1′), so the coupling moved to the agent-runner manifest contract: the open question is now how to keep the reference agent-backend manifests current as the underlying agent CLIs (Claude Code, Codex, Copilot, …) change their flags/headless entry points.
8. **Inference confidence.** When the model infers the wrong work kind, or misses one of several kinds in a mixed intent, how does the human catch it before sign-off, and what is the cost of a wrong inference (FR-058)?
9. **Reversal semantics.** Does "reverse to a prior recorded state" (FR-070) mean a git-level revert, a logical undo of a stage transition, or both — and how does a reversal itself get recorded in the ledger so history stays honest?

---

## 20. Glossary

| Term | Meaning |
|---|---|
| **Oracle** | The independent answer key the work is checked against — here, the human-authored spec and its acceptance criteria, authored by a different mind than the coder. |
| **The three branches** | Legislative (the spec), executive (the agents), judicial (verification and review). |
| **Separation-of-powers collapse** | One agent writing the spec, code, tests, and review, so nothing independent can catch an error. |
| **Circular validation** | Tests that check code against the same interpretation that produced the code. |
| **Phase A / Phase B** | Phase A authors the oracle tests from the spec (judiciary, different model, before/separately from implementation); Phase B implements the tasks (executive) and may add self-verification tests, but must satisfy Phase A's oracle. Phase B depends on Phase A. |
| **Task file scope (blast radius)** | The set of files or modules a task declares it will touch; edits beyond it signal scope creep or a task that needs re-speccing (FR-017). |
| **Gate** | A deterministic or oracle-bearing check that contributes to the verdict; a LAW whose tool is swappable. |
| **Verdict** | The normalized, machine- and human-readable result of a gate run for a change. |
| **Verdict ledger** | The signed, append-only, hash-chained record of verdicts and sign-offs that substitutes for branch protection. |
| **Provenance** | A signed, verifiable record binding an artifact (by hash) to its commit, repository, producing run, and dependencies. |
| **SBOM** | Software bill of materials — the list of components and dependencies in an artifact. |
| **Risk tier** | Cosmetic / Standard / High-risk; sets every downstream threshold. |
| **Model-diversity tax** | The extra inference cost of verifying with a different model than the one that wrote the code. |
| **Deviation** | A conscious, documented departure from the process with a defined way back. |
| **Adapter** | A language plugin that supplies that language's tools behind the normalized gate interface. |
| **Spec ID** | A unique identifier per specification (this document: `3PWR`); requirement IDs are namespaced with it to be project-unique (FR-059). |

---

## 21. Sign-off

| Role | Name | Date | Decision |
|---|---|---|---|
| Author | Carlo Verzeri | | drafted |
| Human approver | | | _pending_ |

> *Required before implementation begins (FR-006). Principles stay stable; their application evolves — version this document the way you version the constitution.*
