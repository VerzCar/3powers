# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `specs-src/[###-feature-name]/spec.md`
(legacy features keep `specs/[###-feature-name]/spec.md`)

**Output**: This file, committed to `specs-src/[###-feature-name]/plan.md` — the Plan stage's
artifact. A plan that was not written to the feature workspace fails the stage.

## Summary

[Extract from feature spec: primary requirement + technical approach]

## Technical Context

<!--
  Replace with the project's technical details. Keep the spec free of these — implementation
  detail belongs here, not in the law.
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before design. Re-check after the phase decomposition below.*

[Gates determined from `.3powers/memory/constitution.md`]

## Risk tier & gates *(mandatory)*

*GATE: Must be filled before the Tasks stage.*

- **Tier**: [from spec] → thresholds resolved from `.3powers/config/risk-tiers.yaml`.
- **Required gates this tier**: [format, lint, types, tests, diff_coverage, spec_conformance, …].

### Phase-A oracle specification

The oracle is authored from the spec's *Acceptance* criteria ONLY, by `/3pwr.oracle`, without reading
this plan or the implementation. List the oracle test intent per requirement (≥1 per requirement, named
with its ID; property test where input is parsed/validated/transformed):

| Requirement | Oracle test intent | Property? |
|-------------|--------------------|-----------|
| [SPECID]-FR-001 | [what the oracle asserts] | [yes/no] |

### Requirement → task coverage (two-way)

Confirm before tasks: every requirement maps to ≥1 task and every task to a requirement. Flag any spec
text that is actually implementation detail and route it out of the spec.

## Phase Decomposition *(mandatory)*

Split the work into small **ordered phases**, each sized so one *fresh* agent session — the approved
spec + the constitution/rules + the phase's tasks + the files in its scope — fits comfortably inside
the configured context budget (`.3powers/config/context.yaml`, default ~110k tokens; estimate ~4 bytes
per token over those artifacts' bytes). Each committed artifact is a context boundary: the executive
runs **each phase as a new headless session** that reloads its handoff set — never one long
conversation across the whole feature.

Rules:

- Ordered phases; each phase is a coherent, self-contained chunk of the work.
- One requirement per task; every task declares its file scope.
- Each phase declares its **file scope** (the union of its tasks' files) and its **estimated context
  size**; split any phase whose estimate exceeds the budget (the executive warns — advisory, never
  blocking).
- Mark independent phases with **disjoint file scopes** `[P]` — the executive may dispatch them to
  parallel subagent sessions. Phases sharing files, or depending on another phase, run sequentially.
- **Every phase runs the coding gates** — format, lint, types, tests + diff-coverage over its file
  scope (`3pwr gate run --path <scope>`, or the project's own verify commands) — and fixes every
  failure before the phase is done (the executor's own advisory checks; the Verify stage remains
  the sole ledger verdict).
- **The last phase is always a dedicated Verification phase** depending on all prior phases, whose
  goal is a fully green build across the whole change.

| Phase | Name | File scope | Depends on | Est. context | Parallel? |
|-------|------|------------|------------|--------------|-----------|
| 1 | [name] | [files] | none | ~[N]k tokens | no |
| 2 | [name] | [files] | Phase 1 | ~[N]k tokens | no |
| N | Verification | [the whole change] | all prior phases | ~[N]k tokens | no |

## Project Structure

### Documentation (this feature — the workspace)

```text
specs-src/[###-feature]/
├── spec.md                  # the specification (Specify stage's artifact)
├── plan.md                  # this file (Plan stage's artifact)
└── implementation-plan.md   # Tasks stage's artifact (legacy runs: tasks.md)
```

### Source Code (repository root)

```text
[Replace with the concrete layout for this feature — real paths only.]
```

**Structure Decision**: [Document the selected structure and reference the real directories above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why simpler insufficient] |
