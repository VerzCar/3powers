# Plan 031 — internal-ID inventory (disposable)

Total hits: **280** across 58 files.

## Summary by kind

| kind | count |
|---|---|
| scaffold-asset | 260 |
| format-example | 20 |

## Summary by namespace

| namespace | count |
|---|---|
| 3PWR | 161 |
| EXEC | 22 |
| PHASE | 16 |
| HARDN | 12 |
| (bare/sibling) | 12 |
| GITX | 12 |
| SPECX | 10 |
| DEMO | 10 |
| RUNLIVE | 8 |
| STEER | 6 |
| SPECID | 4 |
| VUTIL | 2 |
| AGENTX | 2 |
| CLIUX | 2 |
| SRCX | 1 |

Engine-source total (sanity check vs raw grep census): **123**

## .3powers/adapters/CONTRACT.md (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 20 | scaffold-asset | 3PWR-FR-034 | `toolchain:                         # optional: the tools this adapter's gates drive (3PWR-FR-034/048)` |
| 86 | scaffold-asset | HARDN-FR-008 | `* **Tests reference requirement IDs by declaration binding** (HARDN-FR-008): an ID traces a` |
| 88 | scaffold-asset | VUTIL-FR-001 | ``describe("VUTIL-FR-001 …")`) or the docstring adjacent to the declaration (e.g. a Python` |
| 96 | scaffold-asset | HARDN-FR-009 | `assertion_patterns:     # ≥1 must match inside every requirement-bound test (HARDN-FR-009)` |
| 102 | scaffold-asset | 3PWR-NFR-015 | `check with a visible quarantine finding — never a failure, never a silent pass (3PWR-NFR-015).` |

## .3powers/adapters/go/adapter.yaml (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | (plan 015) | `# Go reference adapter (plan 015) — the third language, proving the adapter contract is truly` |
| 2 | scaffold-asset | 3PWR-FR-027 | `# language-agnostic (3PWR-FR-027 / 3PWR-NFR-007): adding a language is "add a manifest", no core change.` |
| 2 | scaffold-asset | 3PWR-NFR-007 | `# language-agnostic (3PWR-FR-027 / 3PWR-NFR-007): adding a language is "add a manifest", no core change.` |
| 5 | scaffold-asset | 3PWR-FR-029 | `# (3PWR-FR-029) unchanged — `go test` writes a Go coverprofile, so the tests gate converts it to LCOV` |
| 13 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 45 | scaffold-asset | 3PWR-FR-029 | `# Emit LCOV so the core's diff-coverage (3PWR-FR-029) works unchanged across languages.` |
| 58 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 60 | scaffold-asset | 3PWR-NFR-015 | `# assertion. Absent patterns degrade to a visible quarantine (3PWR-NFR-015).` |

## .3powers/adapters/python/adapter.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | scaffold-asset | 3PWR-NFR-006 | `# 3PWR-A6 / 3PWR-NFR-006). Commands are prefixed with `uv run` so each tool executes` |
| 11 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 13 | scaffold-asset | 3PWR-NFR-007 | `# "<tool> is not installed — run: <install>". Editable data (3PWR-NFR-007).` |
| 57 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 60 | scaffold-asset | 3PWR-NFR-015 | `# never a failure or a silent pass (3PWR-NFR-015).` |

## .3powers/adapters/typescript/adapter.yaml (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 12 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 15 | scaffold-asset | 3PWR-NFR-007 | `# is an optional version check. Editable data, like the rest of the adapter (3PWR-NFR-007).` |
| 59 | scaffold-asset | 3PWR-FR-009 | `# Optional design oracles (3PWR-FR-009) — run ONLY when work-kind inference tags a change `design`` |
| 60 | scaffold-asset | 3PWR-FR-058 | `# (3PWR-FR-058). These are illustrative TS wirings; when the tool isn't installed (or the project` |
| 61 | scaffold-asset | 3PWR-NFR-015 | `# doesn't define the script) the gate is quarantined, never silently passed (3PWR-NFR-015).` |
| 75 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 77 | scaffold-asset | 3PWR-NFR-015 | `# assertion. Absent patterns degrade to a visible quarantine (3PWR-NFR-015).` |

## .3powers/agents/aider.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — Aider, headless (EXEC-FR-004).` |
| 4 | scaffold-asset | EXEC-FR-012 | `# the engine passes the environment through (EXEC-FR-012). 3Powers records provenance/commits itself,` |

## .3powers/agents/claude.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-002 | `# Agent backend manifest — Claude Code, headless (EXEC-FR-002/003/004).` |
| 4 | scaffold-asset | EXEC-NFR-003 | `# fields alone, so adding an agent is "add a manifest" with no engine change (EXEC-NFR-003).` |
| 5 | scaffold-asset | EXEC-NFR-001 | `# The engine makes no model call itself — the dispatched `claude` process does (EXEC-NFR-001).` |
| 8 | scaffold-asset | EXEC-FR-012 | `# (EXEC-FR-012).` |
| 10 | scaffold-asset | 3PWR-FR-022 | `family: anthropic            # model family for the diversity precheck (3PWR-FR-022)` |

## .3powers/agents/codex.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — OpenAI Codex CLI, headless (EXEC-FR-004).` |
| 4 | scaffold-asset | EXEC-FR-012 | `# (the engine passes the environment through — EXEC-FR-012).` |

## .3powers/agents/copilot-hosted.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | RUNLIVE-FR-008 | `# Agent backend manifest — async HOSTED backend (RUNLIVE-FR-008), GitHub Copilot coding agent shape.` |
| 7 | scaffold-asset | RUNLIVE-NFR-003 | `# in-process deterministic gate suite judges the result identically to a local dispatch (RUNLIVE-NFR-003).` |
| 9 | scaffold-asset | RUNLIVE-NFR-005 | `# Provider-neutral by construction (RUNLIVE-NFR-005): the three steps are ordinary commands with` |
| 12 | scaffold-asset | RUNLIVE-FR-009 | `# (RUNLIVE-FR-009); point `gh` at your entitlement via the environment.` |
| 17 | scaffold-asset | 3PWR-FR-022 | `family: openai              # the diversity precheck family (3PWR-FR-022); set to your hosted model's family` |

## .3powers/agents/copilot.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — GitHub Copilot CLI, headless (EXEC-FR-004; enterprise Copilot shops).` |
| 6 | scaffold-asset | EXEC-FR-011 | `# (EXEC-FR-011) and is a future manifest, not this one.` |

## .3powers/agents/opencode.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — OpenCode, headless (EXEC-FR-004).` |
| 3 | scaffold-asset | EXEC-FR-012 | `# OpenCode's own config or via `--model`; the engine passes the environment through (EXEC-FR-012).` |

## .3powers/config/context.yaml (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | PHASE-FR-007 | `# Context budget for phase sizing (PHASE-FR-007) — ADVISORY ONLY.` |
| 5 | scaffold-asset | PHASE-FR-008 | `# deterministic estimate (~4 bytes/token over the reload set's bytes — PHASE-FR-008) exceeds` |
| 7 | scaffold-asset | PHASE-FR-009 | `# advance decision ever depends on this file (PHASE-FR-009, PHASE-NFR-002).` |
| 7 | scaffold-asset | PHASE-NFR-002 | `# advance decision ever depends on this file (PHASE-FR-009, PHASE-NFR-002).` |

## .3powers/config/dependencies.yaml (6)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-048 | `# Supported third-party versions 3Powers is known-good against (3PWR-FR-048, 3PWR-NFR-014).` |
| 1 | scaffold-asset | 3PWR-NFR-014 | `# Supported third-party versions 3Powers is known-good against (3PWR-FR-048, 3PWR-NFR-014).` |
| 9 | scaffold-asset | 3PWR-NFR-001 | `# so keeping them out of the verdict preserves determinism (3PWR-NFR-001). Absent tools are` |
| 10 | scaffold-asset | 3PWR-NFR-015 | `# reported (like the scanner quarantine, 3PWR-NFR-015), never silently passed. Pin to a stable` |
| 35 | scaffold-asset | 3PWR-NFR-015 | `# absent — 3PWR-NFR-015 — so these stay `warn` here).` |
| 80 | scaffold-asset | (plan 015) | `# Go reference adapter toolchain (plan 015). `go` covers format/lint/types/tests; `gcov2lcov`` |

## .3powers/config/design-oracles.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-009 | `# Design oracles (3PWR-FR-009) — how *design* work is judged, beyond the code gates.` |
| 3 | scaffold-asset | 3PWR-FR-058 | `# When work-kind inference (3PWR-FR-058) tags a change `design`, the gate engine unions these` |
| 4 | scaffold-asset | 3PWR-FR-032 | `# oracle gates onto the tier's gate set (it never removes a tier gate — 3PWR-FR-032). Each oracle's` |
| 5 | scaffold-asset | 3PWR-NFR-007 | `# *tool* is ADAPTER-supplied, keeping the core language-agnostic (3PWR-NFR-007): a language declares` |
| 8 | scaffold-asset | 3PWR-NFR-015 | `# silently passed (3PWR-NFR-015). Trim this catalog to change which oracles a design change must face` |

## .3powers/config/git.yaml (6)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | GITX-FR-015 | `# 3Powers git-integration preferences (GITX-FR-015).` |
| 7 | scaffold-asset | GITX-FR-014 | `# The discipline itself is mandatory (GITX-FR-014): this file tunes names and identity — it cannot` |
| 15 | scaffold-asset | GITX-FR-003 | `# SRCX's already-allocated run identity (GITX-FR-003 — never a new run number).` |
| 20 | scaffold-asset | GITX-NFR-003 | `# current commit instead — never forced, never clobbering (GITX-NFR-003).` |
| 23 | scaffold-asset | GITX-FR-012 | `# The author identity for commits 3pwr itself creates (GITX-FR-012). Applied PER COMMIT via` |
| 25 | scaffold-asset | GITX-NFR-004 | `# (GITX-NFR-004); a commit a human makes by hand keeps the human's own author.` |

## .3powers/config/models.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | AGENTX-FR-015 | `# 3Powers per-integration model/label catalog (AGENTX-FR-015/016).` |
| 26 | scaffold-asset | 3PWR-FR-022 | `# Copilot is BYOK — the model, not the backend, decides the family (3PWR-FR-022 precheck).` |

## .3powers/config/notifications.yaml (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | STEER-FR-009 | `# 3Powers run notifications (STEER-FR-009/010/011).` |
| 4 | scaffold-asset | STEER-NFR-001 | `# a convenience signal, NEVER a trust or enforcement channel (STEER-NFR-001): a channel error,` |
| 11 | scaffold-asset | STEER-NFR-002 | `# (STEER-NFR-002). Each channel routes the events it names via `events:` (default: all three of` |

## .3powers/config/observability.yaml (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-054 | `# NFR instrumentation registry (3PWR-FR-054, §13): which non-functional requirements have a LIVE` |
| 11 | scaffold-asset | 3PWR-NFR-001 | `- nfr: 3PWR-NFR-001` |
| 13 | scaffold-asset | 3PWR-NFR-005 | `- nfr: 3PWR-NFR-005` |
| 15 | scaffold-asset | 3PWR-NFR-010 | `- nfr: 3PWR-NFR-010` |

## .3powers/config/risk-tiers.yaml (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | scaffold-asset | 3PWR-FR-032 | `# diversity, and verification spend (3PWR-FR-032 / 3PWR-FR-049). A gate is NEVER` |
| 4 | scaffold-asset | 3PWR-FR-049 | `# diversity, and verification spend (3PWR-FR-032 / 3PWR-FR-049). A gate is NEVER` |
| 18 | scaffold-asset | 3PWR-FR-064 | `required_layers: []                       # test layers required per requirement (3PWR-FR-064)` |
| 25 | scaffold-asset | HARDN-FR-011 | `# Opt-in machine-graded test quality (HARDN-FR-011): set `diff_mutation: true` (and a` |
| 29 | scaffold-asset | 3PWR-FR-064 | `required_layers: [unit]                   # every requirement needs ≥1 unit test (3PWR-FR-064)` |
| 36 | scaffold-asset | 3PWR-FR-064 | `required_layers: [unit, integration, e2e] # all three layers required per requirement (3PWR-FR-064)` |
| 41 | scaffold-asset | 3PWR-NFR-006 | `# Cosmetic. 3Powers applies these tiers to its own code (3PWR-A6 / 3PWR-NFR-006).` |

## .3powers/config/roles.yaml (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 5 | scaffold-asset | 3PWR-FR-044 | `# (3PWR-FR-044/022): the judiciary (oracle) SHOULD resolve to a different family than the coder.` |
| 11 | scaffold-asset | 3PWR-FR-057 | `# `3pwr deviation --gate model_diversity --approver <you> --note "single-model dev"` (3PWR-FR-057).` |
| 14 | scaffold-asset | 3PWR-FR-022 | `# `diversity_level` (default `family`) sets how "diverse enough" is judged (3PWR-FR-022):` |
| 18 | scaffold-asset | 3PWR-FR-021 | `# `oracle.require_dispatch` (default false) is the High-risk policy for 3PWR-FR-021/A3: when true, a` |
| 27 | scaffold-asset | 3PWR-FR-022 | `diversity_level: family                     # family \| model (3PWR-FR-022)` |
| 29 | scaffold-asset | EXEC-FR-015 | `# Agent backends a LIVE `3pwr run` can dispatch HEADLESSLY (no interactive IDE) — EXEC-FR-015/NFR-003.` |
| 29 | format-example | NFR-003 | `# Agent backends a LIVE `3pwr run` can dispatch HEADLESSLY (no interactive IDE) — EXEC-FR-015/NFR-003.` |
| 38 | scaffold-asset | 3PWR-FR-036 | `reviewer: { model_family: "google" }      # residual review (3PWR-FR-036, arrives v0.5)` |

## .3powers/config/semgrep-rules.yml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-026 | `# Local, offline SAST ruleset for the 3Powers `sast` gate (3PWR-FR-026, §8).` |
| 4 | scaffold-asset | 3PWR-NFR-004 | `# deterministic and offline (3PWR-NFR-004). Teams extend this per project.` |

## .3powers/config/ui.yaml (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | CLIUX-FR-014 | `# 3Powers CLI output preferences (CLIUX-FR-014/015).` |

## .3powers/memory/constitution.md (28)

| line | kind | match | excerpt |
|---|---|---|---|
| 17 | scaffold-asset | 3PWR-FR-010 | `Authoritative specifications live, versioned, in `specs/` (3PWR-FR-010) — never in an external tracker.` |
| 19 | scaffold-asset | 3PWR-FR-003 | `**Non-Goals** section *before* planning may begin (3PWR-FR-003/004). Implementation detail (a named` |
| 21 | scaffold-asset | 3PWR-FR-007 | `routed to planning (3PWR-FR-007). Specs carry a **Spec ID**; requirements are namespaced` |
| 22 | format-example | 3PWR-FR-059 | ``<SPECID>-FR-###` / `<SPECID>-NFR-###` so they are globally unique (3PWR-FR-059).` |
| 27 | scaffold-asset | 3PWR-FR-020 | `source (3PWR-FR-020/021), and is pinned to a **different model family** than the coder` |
| 28 | scaffold-asset | 3PWR-FR-022 | `(3PWR-FR-022) — the engine refuses when they match. There is at least one oracle test per acceptance` |
| 30 | scaffold-asset | 3PWR-FR-023 | `validated, or transformed (3PWR-FR-023/024). The coder's own tests (Phase B) may self-verify but never` |
| 31 | scaffold-asset | 3PWR-FR-062 | `replace the oracle (3PWR-FR-062/063).` |
| 34 | scaffold-asset | 3PWR-FR-016 | `Every task, commit, test, and verdict traces to exactly one requirement ID (3PWR-FR-016). Before code is` |
| 36 | scaffold-asset | 3PWR-FR-015 | `(3PWR-FR-015). The **spec-conformance** gate fails if any requirement lacks a linked test across the` |
| 37 | scaffold-asset | 3PWR-FR-030 | `unit / integration / e2e layers (3PWR-FR-030/064/065). Artifacts — never chat summaries — are handed` |
| 38 | scaffold-asset | 3PWR-FR-014 | `between stages (3PWR-FR-014).` |
| 43 | scaffold-asset | 3PWR-FR-032 | `(`.3powers/config/risk-tiers.yaml`, 3PWR-FR-032/049). **A gate is never satisfied by weakening it** —` |
| 45 | scaffold-asset | 3PWR-FR-035 | `weakened config) is routed to mandatory human review, not a silent pass (3PWR-FR-035).` |
| 49 | scaffold-asset | 3PWR-FR-038 | `signed verdict ledger** (3PWR-FR-038/039); a local `verify` that fails on any tamper, gap, or break` |
| 50 | scaffold-asset | 3PWR-FR-040 | `(3PWR-FR-040); and a local enforcement gate that refuses to advance when a required gate is red, the` |
| 51 | scaffold-asset | 3PWR-FR-037 | `ledger fails verification, or a tier-required **human sign-off** is absent (3PWR-FR-037/041). The` |
| 52 | scaffold-asset | 3PWR-NFR-005 | `signer identity is independent of the executive agents and never stored in the repo (3PWR-NFR-005).` |
| 53 | scaffold-asset | 3PWR-FR-042 | `Enforcement is uniform — no fast path for agent-authored or administrator changes (3PWR-FR-042). The` |
| 54 | scaffold-asset | 3PWR-FR-071 | `whole record is self-contained and reconstructable offline (3PWR-FR-071, 3PWR-NFR-004/010).` |
| 54 | scaffold-asset | 3PWR-NFR-004 | `whole record is self-contained and reconstructable offline (3PWR-FR-071, 3PWR-NFR-004/010).` |
| 58 | scaffold-asset | 3PWR-NFR-014 | `(3PWR-NFR-014). Language support is a declarative **adapter contract**; adding a language changes no` |
| 59 | scaffold-asset | 3PWR-FR-027 | `core code (3PWR-FR-027/045, 3PWR-NFR-007). Executive agents may not touch credentials, access control,` |
| 59 | scaffold-asset | 3PWR-NFR-007 | `core code (3PWR-FR-027/045, 3PWR-NFR-007). Executive agents may not touch credentials, access control,` |
| 60 | scaffold-asset | 3PWR-FR-018 | `hard-deletes, or security configuration without human approval (3PWR-FR-018), and editing outside a` |
| 61 | scaffold-asset | 3PWR-FR-017 | `task's declared file scope is a signal to stop and re-spec (3PWR-FR-017).` |
| 65 | scaffold-asset | 3PWR-NFR-006 | `3Powers is built and maintained using 3Powers (3PWR-A6 / 3PWR-NFR-006). Its own trust-spine code is` |
| 73 | scaffold-asset | 3PWR-FR-047 | ``AGENTS.md` complements but never replaces gate enforcement (3PWR-FR-047/048).` |

## .3powers/templates/agents/implementation-plan.agent.md (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 72 | scaffold-asset | SPECX-FR-003 | `- `[REQ-ID]` — exactly ONE requirement id the task traces to (e.g. `SPECX-FR-003`); every task` |
| 104 | scaffold-asset | SPECX-FR-001 | `- [ ] T001 [SPECX-FR-001] <exact, atomic step> (files: src/one.py, tests/test_one.py)` |
| 105 | scaffold-asset | SPECX-FR-002 | `- [ ] T002 [SPECX-FR-002] <exact, atomic step> (files: src/two.py)` |
| 116 | scaffold-asset | SPECX-FR-003 | `- [ ] T003 [SPECX-FR-003] <exact, atomic step> (files: src/other/three.py)` |

## .3powers/templates/agents/oracle.agent.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 31 | scaffold-asset | SPECX-FR-004 | ``SPECX-FR-004`), so per-criterion coverage is provable.` |

## .3powers/templates/agents/specify.agent.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 100 | format-example | FR-001 | `- **<SPECID>-FR-001**: The system shall <capability>.` |
| 104 | format-example | NFR-001 | `- **<SPECID>-NFR-001**: The system shall <measurable quality attribute>.` |

## .3powers/templates/plan-template.md (10)

| line | kind | match | excerpt |
|---|---|---|---|
| 9 | scaffold-asset | PHASE-FR-002 | `artifact. A plan that was not written to the feature workspace fails the stage (PHASE-FR-002).` |
| 19 | scaffold-asset | 3PWR-FR-007 | `detail belongs here, not in the law (3PWR-FR-007).` |
| 52 | scaffold-asset | 3PWR-FR-032 | `- **Tier**: [from spec] → thresholds resolved from `.3powers/config/risk-tiers.yaml` (3PWR-FR-032/049).` |
| 55 | scaffold-asset | 3PWR-FR-022 | `### Role → model-family assignment (3PWR-FR-022/044)` |
| 63 | scaffold-asset | 3PWR-FR-020 | `### Phase-A oracle specification (3PWR-FR-020/062)` |
| 71 | format-example | FR-001 | `\| [SPECID]-FR-001 \| [what the oracle asserts] \| [yes/no] \|` |
| 73 | scaffold-asset | 3PWR-FR-015 | `### Requirement → task coverage (two-way — 3PWR-FR-015)` |
| 76 | scaffold-asset | 3PWR-FR-007 | `text that is actually implementation detail and route it out of the spec (3PWR-FR-007).` |
| 78 | scaffold-asset | PHASE-FR-004 | `## Phase Decomposition *(mandatory — PHASE-FR-004/006)*` |
| 104 | scaffold-asset | PHASE-FR-001 | `### Documentation (this feature — the workspace, PHASE-FR-001)` |

## .3powers/templates/tasks-template.md (13)

| line | kind | match | excerpt |
|---|---|---|---|
| 9 | scaffold-asset | SRCX-FR-001 | ``specs/[###-feature-name]/spec.md` (flat in the feature folder — SRCX-FR-001; legacy split features keep `spec/spec.md`)` |
| 12 | scaffold-asset | PHASE-FR-002 | `artifact. A tasks artifact that was not written to the feature workspace fails the stage (PHASE-FR-002).` |
| 14 | scaffold-asset | PHASE-FR-004 | `**Organization**: Tasks are grouped into ORDERED PHASES (PHASE-FR-004/006). Each phase is a` |
| 24 | format-example | FR-001 | `- **[REQ-ID]**: The requirement ID this task traces to — e.g. `[SPECID]-FR-001` (3PWR-FR-016). Every` |
| 24 | scaffold-asset | 3PWR-FR-016 | `- **[REQ-ID]**: The requirement ID this task traces to — e.g. `[SPECID]-FR-001` (3PWR-FR-016). Every` |
| 27 | scaffold-asset | 3PWR-FR-017 | `signal to stop and re-spec, not to proceed (3PWR-FR-017).` |
| 38 | scaffold-asset | PHASE-FR-011 | `sessions (PHASE-FR-011). Overlapping scopes run sequentially regardless of the marker.` |
| 54 | scaffold-asset | SPECID-FR-001 | `- [ ] T001 [SPECID-FR-001] [Description] (files: src/[file1].py, tests/test_[file1].py)` |
| 55 | scaffold-asset | SPECID-FR-002 | `- [ ] T002 [SPECID-FR-002] [Description] (files: src/[file2].py)` |
| 69 | scaffold-asset | SPECID-FR-003 | `- [ ] T003 [SPECID-FR-003] [Description] (files: src/other/[file3].py)` |
| 82 | scaffold-asset | SPECID-FR-004 | `- [ ] T004 [SPECID-FR-004] [Description] (files: …)` |
| 93 | scaffold-asset | PHASE-FR-011 | `(PHASE-FR-011/012).` |
| 94 | scaffold-asset | PHASE-FR-009 | `- An oversize phase proceeds with a warning (advisory, never blocking — PHASE-FR-009); an` |

## CONTRIBUTING.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 64 | format-example | DEMO-FR-001 | `requirement IDs (e.g. `DEMO-FR-001`), a declared **risk tier**, and an explicit **non-goals** section.` |

## docs/brownfield.md (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 101 | format-example | DEMO-FR-001 | `- **DEMO-FR-001**: The system shall preserve the observed behavior of `canonical_bytes` in `src/demo.py`…` |
| 102 | format-example | DEMO-FR-002 | `- **DEMO-FR-002**: The system shall preserve the observed behavior of `sha256_hex` …` |
| 103 | format-example | DEMO-FR-003 | `- **DEMO-FR-003**: The system shall preserve the observed behavior of `hash_payload` …` |

## docs/cli-reference.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 619 | format-example | DEMO-NFR-002 | `3pwr observe signal --spec-id DEMO --kind incident --nfr DEMO-NFR-002 --note "p99 latency regressed under load"` |

## docs/concepts.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 31 | format-example | DEMO-FR-001 | `[EARS](https://alistairmavin.com/ears/) form, each with a unique ID like `DEMO-FR-001`. Every spec` |

## docs/engine-architecture.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 109 | format-example | DEMO-FR-001 | `read the requirement IDs declared in the spec (e.g. `DEMO-FR-001`), scan the test roots for files that` |
| 111 | format-example | DEMO-FR-001 | `simply by including its ID in a name or string — `describe("DEMO-FR-001: rejects empty input", …)`. It` |

## engine/src/threepowers/conformance.py (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 26 | format-example | DEMO-FR-001 | `# Canonical requirement ID, namespaced by spec ID: e.g. DEMO-FR-001. The spec ID may` |
| 35 | format-example | DEMO-FR-038 | `slash-runs such as ``DEMO-FR-038/039/040`` into 038, 039, 040."""` |

## engine/src/threepowers/scaffold/adapters/CONTRACT.md (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 20 | scaffold-asset | 3PWR-FR-034 | `toolchain:                         # optional: the tools this adapter's gates drive (3PWR-FR-034/048)` |
| 86 | scaffold-asset | HARDN-FR-008 | `* **Tests reference requirement IDs by declaration binding** (HARDN-FR-008): an ID traces a` |
| 88 | scaffold-asset | VUTIL-FR-001 | ``describe("VUTIL-FR-001 …")`) or the docstring adjacent to the declaration (e.g. a Python` |
| 96 | scaffold-asset | HARDN-FR-009 | `assertion_patterns:     # ≥1 must match inside every requirement-bound test (HARDN-FR-009)` |
| 102 | scaffold-asset | 3PWR-NFR-015 | `check with a visible quarantine finding — never a failure, never a silent pass (3PWR-NFR-015).` |

## engine/src/threepowers/scaffold/adapters/go/adapter.yaml (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | (plan 015) | `# Go reference adapter (plan 015) — the third language, proving the adapter contract is truly` |
| 2 | scaffold-asset | 3PWR-FR-027 | `# language-agnostic (3PWR-FR-027 / 3PWR-NFR-007): adding a language is "add a manifest", no core change.` |
| 2 | scaffold-asset | 3PWR-NFR-007 | `# language-agnostic (3PWR-FR-027 / 3PWR-NFR-007): adding a language is "add a manifest", no core change.` |
| 5 | scaffold-asset | 3PWR-FR-029 | `# (3PWR-FR-029) unchanged — `go test` writes a Go coverprofile, so the tests gate converts it to LCOV` |
| 13 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 45 | scaffold-asset | 3PWR-FR-029 | `# Emit LCOV so the core's diff-coverage (3PWR-FR-029) works unchanged across languages.` |
| 58 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 60 | scaffold-asset | 3PWR-NFR-015 | `# assertion. Absent patterns degrade to a visible quarantine (3PWR-NFR-015).` |

## engine/src/threepowers/scaffold/adapters/python/adapter.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | scaffold-asset | 3PWR-NFR-006 | `# 3PWR-A6 / 3PWR-NFR-006). Commands are prefixed with `uv run` so each tool executes` |
| 11 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 13 | scaffold-asset | 3PWR-NFR-007 | `# "<tool> is not installed — run: <install>". Editable data (3PWR-NFR-007).` |
| 57 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 60 | scaffold-asset | 3PWR-NFR-015 | `# never a failure or a silent pass (3PWR-NFR-015).` |

## engine/src/threepowers/scaffold/adapters/typescript/adapter.yaml (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 12 | scaffold-asset | 3PWR-FR-034 | `# Toolchain 3Powers drives (3PWR-FR-034/048): a gate's `requires:` names one of these; when the tool` |
| 15 | scaffold-asset | 3PWR-NFR-007 | `# is an optional version check. Editable data, like the rest of the adapter (3PWR-NFR-007).` |
| 59 | scaffold-asset | 3PWR-FR-009 | `# Optional design oracles (3PWR-FR-009) — run ONLY when work-kind inference tags a change `design`` |
| 60 | scaffold-asset | 3PWR-FR-058 | `# (3PWR-FR-058). These are illustrative TS wirings; when the tool isn't installed (or the project` |
| 61 | scaffold-asset | 3PWR-NFR-015 | `# doesn't define the script) the gate is quarantined, never silently passed (3PWR-NFR-015).` |
| 75 | scaffold-asset | HARDN-FR-008 | `# Anti-gaming conformance patterns (HARDN-FR-008/009): a requirement ID traces only when bound` |
| 77 | scaffold-asset | 3PWR-NFR-015 | `# assertion. Absent patterns degrade to a visible quarantine (3PWR-NFR-015).` |

## engine/src/threepowers/scaffold/agents/aider.yaml (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — Aider, headless (EXEC-FR-004). Seeded by `3pwr init`.` |

## engine/src/threepowers/scaffold/agents/claude.yaml (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — Claude Code, headless (EXEC-FR-004). Seeded by `3pwr init`.` |
| 2 | scaffold-asset | EXEC-NFR-001 | `# The engine makes no model call itself; the dispatched `claude` process does (EXEC-NFR-001). Point it at` |
| 4 | scaffold-asset | EXEC-FR-012 | `# engine passes the environment through untouched (EXEC-FR-012).` |

## engine/src/threepowers/scaffold/agents/codex.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — OpenAI Codex CLI, headless (EXEC-FR-004). Seeded by `3pwr init`.` |
| 2 | scaffold-asset | EXEC-FR-012 | `# Route model access via OPENAI_BASE_URL / OPENAI_API_KEY or an OpenAI-compatible gateway (EXEC-FR-012).` |

## engine/src/threepowers/scaffold/agents/copilot-hosted.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | RUNLIVE-FR-008 | `# Agent backend manifest — async HOSTED backend (RUNLIVE-FR-008), GitHub Copilot coding agent shape.` |
| 7 | scaffold-asset | RUNLIVE-NFR-003 | `# in-process deterministic gate suite judges the result identically to a local dispatch (RUNLIVE-NFR-003).` |
| 9 | scaffold-asset | RUNLIVE-NFR-005 | `# Provider-neutral by construction (RUNLIVE-NFR-005): the three steps are ordinary commands with` |
| 12 | scaffold-asset | RUNLIVE-FR-009 | `# (RUNLIVE-FR-009); point `gh` at your entitlement via the environment.` |
| 17 | scaffold-asset | 3PWR-FR-022 | `family: openai              # the diversity precheck family (3PWR-FR-022); set to your hosted model's family` |

## engine/src/threepowers/scaffold/agents/copilot.yaml (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — GitHub Copilot CLI, headless (EXEC-FR-004). Seeded by `3pwr init`.` |

## engine/src/threepowers/scaffold/agents/opencode.yaml (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | EXEC-FR-004 | `# Agent backend manifest — OpenCode, headless (EXEC-FR-004). Seeded by `3pwr init`.` |

## engine/src/threepowers/scaffold/config/context.yaml (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | PHASE-FR-007 | `# Context budget for phase sizing (PHASE-FR-007) — ADVISORY ONLY.` |
| 5 | scaffold-asset | PHASE-FR-008 | `# deterministic estimate (~4 bytes/token over the reload set's bytes — PHASE-FR-008) exceeds` |
| 7 | scaffold-asset | PHASE-FR-009 | `# advance decision ever depends on this file (PHASE-FR-009, PHASE-NFR-002).` |
| 7 | scaffold-asset | PHASE-NFR-002 | `# advance decision ever depends on this file (PHASE-FR-009, PHASE-NFR-002).` |

## engine/src/threepowers/scaffold/config/dependencies.yaml (6)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-048 | `# Supported third-party versions 3Powers is known-good against (3PWR-FR-048, 3PWR-NFR-014).` |
| 1 | scaffold-asset | 3PWR-NFR-014 | `# Supported third-party versions 3Powers is known-good against (3PWR-FR-048, 3PWR-NFR-014).` |
| 9 | scaffold-asset | 3PWR-NFR-001 | `# so keeping them out of the verdict preserves determinism (3PWR-NFR-001). Absent tools are` |
| 10 | scaffold-asset | 3PWR-NFR-015 | `# reported (like the scanner quarantine, 3PWR-NFR-015), never silently passed. Pin to a stable` |
| 35 | scaffold-asset | 3PWR-NFR-015 | `# absent — 3PWR-NFR-015 — so these stay `warn` here).` |
| 80 | scaffold-asset | (plan 015) | `# Go reference adapter toolchain (plan 015). `go` covers format/lint/types/tests; `gcov2lcov`` |

## engine/src/threepowers/scaffold/config/design-oracles.yaml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-009 | `# Design oracles (3PWR-FR-009) — how *design* work is judged, beyond the code gates.` |
| 3 | scaffold-asset | 3PWR-FR-058 | `# When work-kind inference (3PWR-FR-058) tags a change `design`, the gate engine unions these` |
| 4 | scaffold-asset | 3PWR-FR-032 | `# oracle gates onto the tier's gate set (it never removes a tier gate — 3PWR-FR-032). Each oracle's` |
| 5 | scaffold-asset | 3PWR-NFR-007 | `# *tool* is ADAPTER-supplied, keeping the core language-agnostic (3PWR-NFR-007): a language declares` |
| 8 | scaffold-asset | 3PWR-NFR-015 | `# silently passed (3PWR-NFR-015). Trim this catalog to change which oracles a design change must face` |

## engine/src/threepowers/scaffold/config/git.yaml (6)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | GITX-FR-015 | `# 3Powers git-integration preferences (GITX-FR-015).` |
| 7 | scaffold-asset | GITX-FR-014 | `# The discipline itself is mandatory (GITX-FR-014): this file tunes names and identity — it cannot` |
| 15 | scaffold-asset | GITX-FR-003 | `# SRCX's already-allocated run identity (GITX-FR-003 — never a new run number).` |
| 20 | scaffold-asset | GITX-NFR-003 | `# current commit instead — never forced, never clobbering (GITX-NFR-003).` |
| 23 | scaffold-asset | GITX-FR-012 | `# The author identity for commits 3pwr itself creates (GITX-FR-012). Applied PER COMMIT via` |
| 25 | scaffold-asset | GITX-NFR-004 | `# (GITX-NFR-004); a commit a human makes by hand keeps the human's own author.` |

## engine/src/threepowers/scaffold/config/models.yaml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | AGENTX-FR-015 | `# 3Powers per-integration model/label catalog (AGENTX-FR-015/016).` |
| 26 | scaffold-asset | 3PWR-FR-022 | `# Copilot is BYOK — the model, not the backend, decides the family (3PWR-FR-022 precheck).` |

## engine/src/threepowers/scaffold/config/notifications.yaml (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | STEER-FR-009 | `# 3Powers run notifications (STEER-FR-009/010/011).` |
| 4 | scaffold-asset | STEER-NFR-001 | `# a convenience signal, NEVER a trust or enforcement channel (STEER-NFR-001): a channel error,` |
| 11 | scaffold-asset | STEER-NFR-002 | `# (STEER-NFR-002). Each channel routes the events it names via `events:` (default: all three of` |

## engine/src/threepowers/scaffold/config/observability.yaml (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-054 | `# NFR instrumentation registry (3PWR-FR-054, §13): which non-functional requirements have a LIVE` |
| 11 | scaffold-asset | 3PWR-NFR-001 | `- nfr: 3PWR-NFR-001` |
| 13 | scaffold-asset | 3PWR-NFR-005 | `- nfr: 3PWR-NFR-005` |
| 15 | scaffold-asset | 3PWR-NFR-010 | `- nfr: 3PWR-NFR-010` |

## engine/src/threepowers/scaffold/config/risk-tiers.yaml (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | scaffold-asset | 3PWR-FR-032 | `# diversity, and verification spend (3PWR-FR-032 / 3PWR-FR-049). A gate is NEVER` |
| 4 | scaffold-asset | 3PWR-FR-049 | `# diversity, and verification spend (3PWR-FR-032 / 3PWR-FR-049). A gate is NEVER` |
| 18 | scaffold-asset | 3PWR-FR-064 | `required_layers: []                       # test layers required per requirement (3PWR-FR-064)` |
| 25 | scaffold-asset | HARDN-FR-011 | `# Opt-in machine-graded test quality (HARDN-FR-011): set `diff_mutation: true` (and a` |
| 29 | scaffold-asset | 3PWR-FR-064 | `required_layers: [unit]                   # every requirement needs ≥1 unit test (3PWR-FR-064)` |
| 36 | scaffold-asset | 3PWR-FR-064 | `required_layers: [unit, integration, e2e] # all three layers required per requirement (3PWR-FR-064)` |
| 41 | scaffold-asset | 3PWR-NFR-006 | `# Cosmetic. 3Powers applies these tiers to its own code (3PWR-A6 / 3PWR-NFR-006).` |

## engine/src/threepowers/scaffold/config/roles.yaml (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 5 | scaffold-asset | 3PWR-FR-044 | `# (3PWR-FR-044/022): the judiciary (oracle) SHOULD resolve to a different family than the coder.` |
| 11 | scaffold-asset | 3PWR-FR-057 | `# `3pwr deviation --gate model_diversity --approver <you> --note "single-model dev"` (3PWR-FR-057).` |
| 13 | scaffold-asset | 3PWR-FR-022 | `# `diversity_level` (default `family`) sets how "diverse enough" is judged (3PWR-FR-022):` |
| 17 | scaffold-asset | 3PWR-FR-021 | `# `oracle.require_dispatch` (default false) is the High-risk policy for 3PWR-FR-021: when true, a` |
| 24 | scaffold-asset | 3PWR-FR-022 | `diversity_level: family                     # family \| model (3PWR-FR-022)` |
| 26 | scaffold-asset | EXEC-FR-015 | `# Agent backends a LIVE `3pwr run` can dispatch HEADLESSLY (no interactive IDE) — EXEC-FR-015/NFR-003.` |
| 26 | format-example | NFR-003 | `# Agent backends a LIVE `3pwr run` can dispatch HEADLESSLY (no interactive IDE) — EXEC-FR-015/NFR-003.` |
| 41 | scaffold-asset | 3PWR-FR-036 | `# residual review (3PWR-FR-036):` |

## engine/src/threepowers/scaffold/config/semgrep-rules.yml (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | 3PWR-FR-026 | `# Local, offline SAST ruleset for the 3Powers `sast` gate (3PWR-FR-026, §8).` |
| 4 | scaffold-asset | 3PWR-NFR-004 | `# deterministic and offline (3PWR-NFR-004). Teams extend this per project.` |

## engine/src/threepowers/scaffold/config/ui.yaml (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | scaffold-asset | CLIUX-FR-014 | `# 3Powers CLI output preferences (CLIUX-FR-014/015).` |

## engine/src/threepowers/scaffold/constitution.md (28)

| line | kind | match | excerpt |
|---|---|---|---|
| 17 | scaffold-asset | 3PWR-FR-010 | `Authoritative specifications live, versioned, in `specs/` (3PWR-FR-010) — never in an external tracker.` |
| 19 | scaffold-asset | 3PWR-FR-003 | `**Non-Goals** section *before* planning may begin (3PWR-FR-003/004). Implementation detail (a named` |
| 21 | scaffold-asset | 3PWR-FR-007 | `routed to planning (3PWR-FR-007). Specs carry a **Spec ID**; requirements are namespaced` |
| 22 | format-example | 3PWR-FR-059 | ``<SPECID>-FR-###` / `<SPECID>-NFR-###` so they are globally unique (3PWR-FR-059).` |
| 27 | scaffold-asset | 3PWR-FR-020 | `source (3PWR-FR-020/021), and is pinned to a **different model family** than the coder` |
| 28 | scaffold-asset | 3PWR-FR-022 | `(3PWR-FR-022) — the engine refuses when they match. There is at least one oracle test per acceptance` |
| 30 | scaffold-asset | 3PWR-FR-023 | `validated, or transformed (3PWR-FR-023/024). The coder's own tests (Phase B) may self-verify but never` |
| 31 | scaffold-asset | 3PWR-FR-062 | `replace the oracle (3PWR-FR-062/063).` |
| 34 | scaffold-asset | 3PWR-FR-016 | `Every task, commit, test, and verdict traces to exactly one requirement ID (3PWR-FR-016). Before code is` |
| 36 | scaffold-asset | 3PWR-FR-015 | `(3PWR-FR-015). The **spec-conformance** gate fails if any requirement lacks a linked test across the` |
| 37 | scaffold-asset | 3PWR-FR-030 | `unit / integration / e2e layers (3PWR-FR-030/064/065). Artifacts — never chat summaries — are handed` |
| 38 | scaffold-asset | 3PWR-FR-014 | `between stages (3PWR-FR-014).` |
| 43 | scaffold-asset | 3PWR-FR-032 | `(`.3powers/config/risk-tiers.yaml`, 3PWR-FR-032/049). **A gate is never satisfied by weakening it** —` |
| 45 | scaffold-asset | 3PWR-FR-035 | `weakened config) is routed to mandatory human review, not a silent pass (3PWR-FR-035).` |
| 49 | scaffold-asset | 3PWR-FR-038 | `signed verdict ledger** (3PWR-FR-038/039); a local `verify` that fails on any tamper, gap, or break` |
| 50 | scaffold-asset | 3PWR-FR-040 | `(3PWR-FR-040); and a local enforcement gate that refuses to advance when a required gate is red, the` |
| 51 | scaffold-asset | 3PWR-FR-037 | `ledger fails verification, or a tier-required **human sign-off** is absent (3PWR-FR-037/041). The` |
| 52 | scaffold-asset | 3PWR-NFR-005 | `signer identity is independent of the executive agents and never stored in the repo (3PWR-NFR-005).` |
| 53 | scaffold-asset | 3PWR-FR-042 | `Enforcement is uniform — no fast path for agent-authored or administrator changes (3PWR-FR-042). The` |
| 54 | scaffold-asset | 3PWR-FR-071 | `whole record is self-contained and reconstructable offline (3PWR-FR-071, 3PWR-NFR-004/010).` |
| 54 | scaffold-asset | 3PWR-NFR-004 | `whole record is self-contained and reconstructable offline (3PWR-FR-071, 3PWR-NFR-004/010).` |
| 58 | scaffold-asset | 3PWR-NFR-014 | `(3PWR-NFR-014). Language support is a declarative **adapter contract**; adding a language changes no` |
| 59 | scaffold-asset | 3PWR-FR-027 | `core code (3PWR-FR-027/045, 3PWR-NFR-007). Executive agents may not touch credentials, access control,` |
| 59 | scaffold-asset | 3PWR-NFR-007 | `core code (3PWR-FR-027/045, 3PWR-NFR-007). Executive agents may not touch credentials, access control,` |
| 60 | scaffold-asset | 3PWR-FR-018 | `hard-deletes, or security configuration without human approval (3PWR-FR-018), and editing outside a` |
| 61 | scaffold-asset | 3PWR-FR-017 | `task's declared file scope is a signal to stop and re-spec (3PWR-FR-017).` |
| 65 | scaffold-asset | 3PWR-NFR-006 | `3Powers is built and maintained using 3Powers (3PWR-A6 / 3PWR-NFR-006). Its own trust-spine code is` |
| 73 | scaffold-asset | 3PWR-FR-047 | ``AGENTS.md` complements but never replaces gate enforcement (3PWR-FR-047/048).` |

## engine/src/threepowers/scaffold/templates/agents/implementation-plan.agent.md (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 72 | scaffold-asset | SPECX-FR-003 | `- `[REQ-ID]` — exactly ONE requirement id the task traces to (e.g. `SPECX-FR-003`); every task` |
| 104 | scaffold-asset | SPECX-FR-001 | `- [ ] T001 [SPECX-FR-001] <exact, atomic step> (files: src/one.py, tests/test_one.py)` |
| 105 | scaffold-asset | SPECX-FR-002 | `- [ ] T002 [SPECX-FR-002] <exact, atomic step> (files: src/two.py)` |
| 116 | scaffold-asset | SPECX-FR-003 | `- [ ] T003 [SPECX-FR-003] <exact, atomic step> (files: src/other/three.py)` |

## engine/src/threepowers/scaffold/templates/agents/oracle.agent.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 31 | scaffold-asset | SPECX-FR-004 | ``SPECX-FR-004`), so per-criterion coverage is provable.` |

## engine/src/threepowers/scaffold/templates/agents/specify.agent.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 100 | format-example | FR-001 | `- **<SPECID>-FR-001**: The system shall <capability>.` |
| 104 | format-example | NFR-001 | `- **<SPECID>-NFR-001**: The system shall <measurable quality attribute>.` |

