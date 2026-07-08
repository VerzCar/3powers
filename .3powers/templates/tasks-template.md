---

description: "Task list template for feature implementation — context-sized phases, delegable handoffs"
---

# Tasks: [FEATURE NAME]

**Input**: `specs/[###-feature-name]/artifacts/plan.md` (required) and
`specs/[###-feature-name]/spec.md` (flat in the feature folder; legacy split features keep `spec/spec.md`)

**Output**: This file, committed to `specs/[###-feature-name]/artifacts/tasks.md` — the Tasks stage's
artifact. A tasks artifact that was not written to the feature workspace fails the stage.

**Organization**: Tasks are grouped into ORDERED PHASES. Each phase is a
self-contained, delegable unit sized so one **fresh agent session** — the approved spec + the
constitution/rules + the phase's tasks + the files in its scope — fits comfortably inside the
configured context budget (`.3powers/config/context.yaml`, default ~110k tokens; estimate ~4 bytes
per token over those artifacts' bytes). The executive dispatches **each phase as a new headless
session** reloading its handoff block; it never carries one long conversation across the feature.
A phase whose estimate exceeds the budget gets an advisory warning — split it.

## Task format: `- [ ] T### [REQ-ID] Description (files: …)`

- **[REQ-ID]**: The requirement ID this task traces to — e.g. `[SPECID]-FR-001`. Every
  task traces to exactly ONE requirement; the spec-conformance gate later checks the reverse too.
- **(files: …)**: The task's **declared file scope** — exact paths. Editing outside this scope is a
  signal to stop and re-spec, not to proceed.

## Phase format

Each `## Phase N: <name>` section carries, in this order:

- `**File scope**:` every file the phase may touch (the union of its tasks' files).
- `**Depends on**:` the phase(s) that must complete first, or `none`.
- `**Estimated context**:` the phase's estimated context size vs the budget.
- `**Parallel**: yes` (or `[P]` in the heading) ONLY for a phase with no dependency whose file scope
  is **disjoint** from its siblings' — the executive may dispatch such phases to parallel subagent
  sessions. Overlapping scopes run sequentially regardless of the marker.
- A **Handoff** block naming what a fresh session must reload — the session starts cold; nothing
  outside the handoff can be assumed.

---

## Phase 1: [Name — a coherent chunk, e.g. "core model + parsing"]

**File scope**: [src/…, tests/…]
**Depends on**: none
**Estimated context**: ~[N]k tokens (budget ~110k)

**Handoff** (what a fresh session reloads): the approved spec
(`specs/[###-feature]/spec.md`), the constitution/rules
(`.3powers/memory/constitution.md`), this phase's tasks below, and the file scope above.

- [ ] T001 [SPECID-FR-001] [Description] (files: src/[file1].py, tests/test_[file1].py)
- [ ] T002 [SPECID-FR-002] [Description] (files: src/[file2].py)

---

## Phase 2: [Name] [P]

**File scope**: [src/other/…] — disjoint from Phase 1
**Depends on**: none
**Estimated context**: ~[N]k tokens (budget ~110k)
**Parallel**: yes

**Handoff** (what a fresh session reloads): the approved spec, the constitution/rules, this phase's
tasks below, and the file scope above.

- [ ] T003 [SPECID-FR-003] [Description] (files: src/other/[file3].py)

---

## Phase 3: [Name — e.g. "integration + docs"]

**File scope**: [files touched — may overlap earlier phases]
**Depends on**: Phase 1, Phase 2
**Estimated context**: ~[N]k tokens (budget ~110k)

**Handoff** (what a fresh session reloads): the approved spec, the constitution/rules, this phase's
tasks below, and the file scope above.

- [ ] T004 [SPECID-FR-004] [Description] (files: …)

---

[Add more phases as needed. Keep every phase under the budget — split, don't stretch.]

## Dependencies & execution order

- Phases execute in artifact order; a phase declaring `**Depends on**:` waits for the named phase(s).
- Phases marked parallel with **disjoint** file scopes and no dependency may be dispatched
  concurrently to subagent sessions; results are recorded in deterministic artifact order.
- An oversize phase proceeds with a warning (advisory, never blocking); an
  irreducible one (a single task over budget) is called out as such.

## Notes

- One requirement per task; exact file paths in every scope declaration.
- Each phase must be independently completable from its handoff block alone.
- Commit after each phase — the committed artifact is the context boundary between sessions.
- Avoid: vague tasks, undeclared file scopes, cross-phase edits, parallel markers on overlapping
  scopes.
