# Plan 031 — internal-ID inventory (disposable)

Total hits: **1658** across 111 files.

## Summary by kind

| kind | count |
|---|---|
| docstring | 892 |
| comment | 379 |
| scaffold-asset | 260 |
| doc-prose | 64 |
| format-example | 61 |
| echoed-message | 2 |

## Summary by namespace

| namespace | count |
|---|---|
| 3PWR | 448 |
| STEER | 136 |
| GITX | 98 |
| (bare/sibling) | 85 |
| RUNLIVE | 85 |
| EXEC | 80 |
| SRCX | 80 |
| PHASE | 79 |
| HARDN | 72 |
| AGENTX | 67 |
| AUTOX | 64 |
| CLIUX | 50 |
| ONBRD | 42 |
| GATECFG | 41 |
| PROGFILE | 40 |
| INITX | 34 |
| SLOCK | 27 |
| GATEPIPE | 26 |
| GDIAG | 18 |
| RUNX | 18 |
| TRIX | 18 |
| SPECX | 10 |
| PHASEPR | 10 |
| RUNID | 9 |
| VUTIL | 8 |
| SPECID | 4 |
| OSSRD | 3 |
| MONEY | 3 |
| DOCX | 2 |
| SLIM | 1 |

Engine-source total (sanity check vs raw grep census): **1445**

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

## .github/workflows/ci.yml (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | doc-prose | OSSRD-FR-004 | `# CI for this repository's own contributions (OSSRD-FR-004).` |
| 4 | doc-prose | 3PWR-NFR-004 | `# locally and offline (3PWR-NFR-004; assumption A4: CI may re-validate, never gatekeep the framework's` |
| 9 | doc-prose | OSSRD-NFR-002 | `# Budget: the whole job must finish well within 10 minutes on the hosted runners (OSSRD-NFR-002).` |
| 26 | doc-prose | OSSRD-NFR-002 | `timeout-minutes: 10 # OSSRD-NFR-002: never the reason contributors bypass checks` |
| 54 | doc-prose | HARDN-FR-002 | `# passes the custody preflight by construction (HARDN-FR-002).` |

## CHANGELOG.md (18)

| line | kind | match | excerpt |
|---|---|---|---|
| 33 | doc-prose | (plan 029) | `plain streamed log escape-free, and teardown always restores the terminal, on Ctrl-C too. (plan 029)` |
| 49 | doc-prose | (plan 028) | `branch + committed stages surfaced by both status commands. (plan 028)` |
| 60 | doc-prose | (plan 018) | `and implementation status lives only in STATUS. (plan 018)` |
| 73 | doc-prose | (plan 017) | `and a per-tier `diff_mutation` knob runs mutation over changed files. (plan 017)` |
| 79 | doc-prose | (plan 016) | `with the recorded hash is caught by the existing `verify` — no new trust primitive. (plan 016)` |
| 83 | doc-prose | (plan 015) | `which are quarantined — surfaced as skipped — when a tool isn't wired up. (plan 015)` |
| 85 | doc-prose | (plan 015) | `contract is language-agnostic. (plan 015)` |
| 87 | doc-prose | (plan 013) | `two human gates (spec approval, sign-off) in `auto` mode. (plan 013)` |
| 90 | doc-prose | (plan 010) | `attributable agent-action log. (plan 010)` |
| 92 | doc-prose | (plan 011) | `sanitized Git worktree where the implementation is physically absent, attested in the ledger. (plan 011)` |
| 95 | doc-prose | (plan 008) | `the High-risk tier. (plan 008)` |
| 97 | doc-prose | (plan 007) | `exceptions that are always recorded and never silently weaken a gate. (plan 007)` |
| 99 | doc-prose | (plan 006) | `spec and pin a legacy module's current behavior. (plan 006)` |
| 101 | doc-prose | (plan 009) | `provider-agnostic Spec Kit extension. (plan 009)` |
| 108 | doc-prose | (plan 014) | `and quarantines when neither is present. (plan 014)` |
| 110 | doc-prose | (plan 012) | `exception rather than being blocked outright, so single-model users are never walled off. (plan 012)` |
| 111 | doc-prose | (plan 014) | `- Per-tier required test layers (unit / integration / e2e) are enforced as a per-change union. (plan 014)` |
| 113 | doc-prose | (plan 006) | `diff-coverage plus mutation), so 3Powers is genuinely built with 3Powers at the strictest tier. (plan 006)` |

## CONTRIBUTING.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 64 | doc-prose | VUTIL-FR-001 | `requirement IDs (e.g. `VUTIL-FR-001`), a declared **risk tier**, and an explicit **non-goals** section.` |

## docs/brownfield.md (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 101 | doc-prose | MONEY-FR-001 | `- **MONEY-FR-001**: The system shall preserve the observed behavior of `canonical_bytes` in `src/money.py`…` |
| 102 | doc-prose | MONEY-FR-002 | `- **MONEY-FR-002**: The system shall preserve the observed behavior of `sha256_hex` …` |
| 103 | doc-prose | MONEY-FR-003 | `- **MONEY-FR-003**: The system shall preserve the observed behavior of `hash_payload` …` |

## docs/cli-reference.md (15)

| line | kind | match | excerpt |
|---|---|---|---|
| 80 | doc-prose | AGENTX-FR-001 | `characterize — AGENTX-FR-001/009). The executive uses a repo-local template as that` |
| 82 | doc-prose | AGENTX-FR-005 | `engine's built-in instruction (AGENTX-FR-005). Seeding is non-clobbering — a hand-edited template is` |
| 84 | doc-prose | AGENTX-FR-011 | `role→model setup** below (AGENTX-FR-011/012).` |
| 88 | doc-prose | AGENTX-FR-014 | `model, without reinitializing (AGENTX-FR-014). Interactive by default: pick the integration you have` |
| 91 | doc-prose | AGENTX-FR-015 | `list is accepted free-form (BYOK), its family derived where the id encodes it (AGENTX-FR-015/016).` |
| 93 | doc-prose | AGENTX-FR-012 | ``3pwr run` needs no manual role editing (AGENTX-FR-012/013). Non-destructive: only the roles you` |
| 105 | doc-prose | 3PWR-FR-021 | `policy (3PWR-FR-021, epic A3): when `true`, a High-risk `advance` refuses unless an isolated` |
| 110 | doc-prose | 3PWR-FR-022 | `forced; proceed with `3pwr deviation --gate model_diversity …` (3PWR-FR-022/057, AGENTX-FR-018).` |
| 110 | doc-prose | AGENTX-FR-018 | `forced; proceed with `3pwr deviation --gate model_diversity …` (3PWR-FR-022/057, AGENTX-FR-018).` |
| 519 | doc-prose | AUTOX-FR-009 | `**The stable machine contract (AUTOX-FR-009).** Each terminal outcome maps to exactly one documented` |
| 539 | doc-prose | AUTOX-FR-008 | `**Transcripts (AUTOX-FR-008, stable).** Every stage attempt's stdout/stderr — streamed or not — is` |
| 546 | doc-prose | GITX-FR-016 | `Gives the command-by-command `/3pwr.*` drive the same git guarantees as `3pwr run` (GITX-FR-016): checks` |
| 582 | doc-prose | GITX-FR-014 | ``git_stage_commit`, `git_run_branch` — GITX-FR-014). Human sign-off and provenance are never deviatable.` |
| 619 | doc-prose | VUTIL-NFR-002 | `3pwr observe signal --spec-id VUTIL --kind incident --nfr VUTIL-NFR-002 --note "p99 latency regressed under load"` |
| 719 | doc-prose | AUTOX-FR-003 | `One honest answer, re-runnable any time (AUTOX-FR-003): performs the auto run's own preflight — a` |

## docs/concepts.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 31 | doc-prose | VUTIL-FR-001 | `[EARS](https://alistairmavin.com/ears/) form, each with a unique ID like `VUTIL-FR-001`. Every spec` |

## docs/engine-architecture.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 109 | doc-prose | VUTIL-FR-001 | `read the requirement IDs declared in the spec (e.g. `VUTIL-FR-001`), scan the test roots for files that` |
| 111 | doc-prose | VUTIL-FR-001 | `simply by including its ID in a name or string — `describe("VUTIL-FR-001: rejects empty input", …)`. It` |

## docs/getting-started.md (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 56 | doc-prose | 3PWR-FR-022 | `family** than the coder (recommended, 3PWR-FR-022):` |
| 89 | doc-prose | 3PWR-FR-006 | `1. **Spec approval** (3PWR-FR-006) — read the generated spec, then` |
| 91 | doc-prose | 3PWR-FR-037 | `2. **Sign-off** (3PWR-FR-037) — review the evidence, then resume the same way.` |

## docs/migration-remove-speckit.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 11 | doc-prose | SLIM-NFR-003 | `changed (SLIM-NFR-003).` |
| 44 | doc-prose | 3PWR-FR-022 | ``coder: { integration: codex }`, `oracle: { integration: claude }` (a different family — 3PWR-FR-022).` |

## docs/references/speckit.md (2)

| line | kind | match | excerpt |
|---|---|---|---|
| 77 | doc-prose | (plan 009) | `(plan 009) — providing the `/3pwr.*` judiciary commands + `after_tasks`/`after_implement` gate hooks,` |
| 88 | doc-prose | (plan 009) | `\| extensions/hooks \| the `3powers` extension auto-runs the oracle (`after_tasks`) + gates (`after_implement`); provider-agnostic packaging (plan 009) \|` |

## docs/threat-model.md (11)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | doc-prose | HARDN-FR-001 | `This document is the versioned, in-repo answer to "what does the ledger prove?" (HARDN-FR-001).` |
| 37 | doc-prose | HARDN-FR-004 | `\| **Key swap** — `.3powers/keys/ledger.pub` replaced without authority \| the committed key does not descend from the genesis key through signed `key_rotation...` |
| 57 | doc-prose | 3PWR-NFR-005 | `repository working tree (3PWR-NFR-005). An agent operating inside the repo must find no key` |
| 60 | doc-prose | HARDN-FR-002 | `Enforced hygiene (HARDN-FR-002/003):` |
| 72 | doc-prose | HARDN-FR-004 | `**Key continuity (HARDN-FR-004).** Replacing the signer is legitimate only through a signed` |
| 78 | doc-prose | HARDN-FR-006 | `**External / hardware-backed signing (HARDN-FR-006).** Where an external signer is configured` |
| 86 | doc-prose | HARDN-FR-005 | `Anchoring (opt-in, HARDN-FR-005) records the current ledger head — sequence number and entry` |
| 118 | doc-prose | HARDN-FR-007 | `failure at a High-risk `advance` (HARDN-FR-007).` |
| 126 | doc-prose | HARDN-FR-008 | `assertion per requirement-bound test (HARDN-FR-008/009); the gate-gaming detector flags newly` |
| 127 | doc-prose | HARDN-FR-010 | `added assertion-free requirement-referencing tests for mandatory human review (HARDN-FR-010).` |
| 130 | doc-prose | HARDN-FR-011 | `HARDN-FR-011) and human review.` |

## docs/troubleshooting.md (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 83 | doc-prose | 3PWR-FR-032 | `never satisfy a gate by weakening it (3PWR-FR-032):` |

## engine/src/threepowers/__init__.py (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 6 | docstring | 3PWR-NFR-001 | `normalized **verdict** (identical shape across languages — 3PWR-NFR-001/033);` |
| 8 | docstring | 3PWR-FR-030 | `3PWR-FR-030);` |
| 10 | docstring | 3PWR-FR-038 | ```verify`` that fails on any tamper, gap, or break (3PWR-FR-038/039/040);` |
| 13 | docstring | 3PWR-FR-041 | `human sign-off is absent (3PWR-FR-041/042).` |
| 16 | docstring | 3PWR-NFR-004 | `(3PWR-NFR-004/010).` |
| 22 | comment | 3PWR-NFR-008 | `# Documented, versioned, and stable (3PWR-NFR-008). 1.1 adds the additive,` |
| 23 | comment | 3PWR-FR-052 | `# backward-compatible ``report_only`` verdict field (brownfield adoption, 3PWR-FR-052).` |

## engine/src/threepowers/adapters.py (25)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-027 | `"""Language adapters — the polyglot plugin contract (3PWR-FR-027, 3PWR-NFR-007).` |
| 1 | docstring | 3PWR-NFR-007 | `"""Language adapters — the polyglot plugin contract (3PWR-FR-027, 3PWR-NFR-007).` |
| 6 | docstring | 3PWR-NFR-007 | `(3PWR-NFR-007). The core never assumes a language beyond what the adapter declares` |
| 7 | docstring | 3PWR-FR-045 | `(3PWR-FR-045).` |
| 41 | comment | GATECFG-FR-006 | `# The only gates a fix command may run for (GATECFG-FR-006): a fix mutates source to satisfy a` |
| 46 | comment | GATECFG-FR-001 | `# Where the per-project gate overrides live (GATECFG-FR-001) — committed team configuration,` |
| 47 | comment | GATECFG-FR-002 | `# versioned with the rest of .3powers/config/, seeded by `3pwr init` (GATECFG-FR-002).` |
| 60 | docstring | GATECFG-FR-001 | `"""The per-gate overrides from ``.3powers/config/gates.yaml`` (GATECFG-FR-001).` |
| 80 | docstring | GATECFG-FR-001 | `One ``dict.update()`` pass per gate block (GATECFG-FR-001): only keys present in the override` |
| 82 | docstring | GATECFG-FR-006 | `non-fixable gate is discarded, never merged (GATECFG-FR-006). Overrides replace TOOLS, never` |
| 83 | docstring | GATECFG-NFR-001 | `gates — the risk tier alone decides which gates run (GATECFG-NFR-001)."""` |
| 102 | docstring | GATECFG-FR-006 | `"""Discard any ``fix_cmd`` declared on a non-fixable gate (GATECFG-FR-006).` |
| 112 | docstring | GATECFG-FR-001 | `"""The adapter manifest with the project's ``gates.yaml`` overrides merged in (GATECFG-FR-001)."""` |
| 180 | docstring | 3PWR-FR-034 | `"""The adapter's declared toolchain map (tool → {install, probe}), or ``{}`` (3PWR-FR-034)."""` |
| 202 | docstring | GDIAG-FR-004 | `"""Whether ``tool`` answers the probe its toolchain entry declares (GDIAG-FR-004).` |
| 220 | docstring | GATECFG-FR-004 | `"""One declarative auto-detection probe (GATECFG-FR-004): data, never core logic (3PWR-NFR-007).` |
| 220 | docstring | 3PWR-NFR-007 | `"""One declarative auto-detection probe (GATECFG-FR-004): data, never core logic (3PWR-NFR-007).` |
| 233 | comment | GATECFG-FR-004 | `# Fixed first-match order per gate (GATECFG-FR-004). The rules are pure data: adding a detectable` |
| 235 | comment | GATECFG-FR-006 | `# (GATECFG-FR-006 holds by construction).` |
| 352 | docstring | GATECFG-FR-004 | `"""Probe ``target`` for project-native gate tooling (GATECFG-FR-004).` |
| 356 | docstring | GATECFG-FR-003 | `the explicit team configuration outranks detection (GATECFG-FR-003). Deterministic given the` |
| 370 | docstring | GATECFG-FR-003 | `"""The assembled gate configuration for one run (GATECFG-FR-003).` |
| 375 | docstring | GATECFG-FR-005 | `gate's tool, for the one startup line (GATECFG-FR-005)."""` |
| 385 | docstring | GATECFG-FR-003 | `Detection runs only for gates ``gates.yaml`` leaves alone (GATECFG-FR-003/004). A detected` |
| 388 | docstring | GATECFG-NFR-001 | `Configuration replaces tools, never gates (GATECFG-NFR-001)."""` |

## engine/src/threepowers/agents.py (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | EXEC-FR-002 | `"""Agent backends — the provider-agnostic executive plugin contract (EXEC-FR-002/003, 3PWR-FR-046).` |
| 1 | docstring | 3PWR-FR-046 | `"""Agent backends — the provider-agnostic executive plugin contract (EXEC-FR-002/003, 3PWR-FR-046).` |
| 6 | docstring | EXEC-NFR-003 | `an agent is "add a manifest" — no change to the engine core (EXEC-NFR-003). This mirrors the language` |
| 9 | docstring | EXEC-NFR-001 | `The engine itself never calls a model API (EXEC-NFR-001, amended 3PWR A3): it constructs an invocation for` |
| 12 | docstring | EXEC-FR-012 | `the environment; the engine passes the environment through and interprets no credential (EXEC-FR-012).` |
| 25 | comment | 3PWR-FR-022 | `#   family       model family for the diversity precheck (3PWR-FR-022); '' when it depends on the model` |
| 68 | docstring | EXEC-FR-003 | `"""Build the agent invocation from a manifest (EXEC-FR-003).` |
| 72 | docstring | EXEC-FR-005 | `same (manifest, prompt, model) always yields the same invocation (supports EXEC-FR-005's property).` |

## engine/src/threepowers/anchor.py (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | HARDN-FR-005 | `"""Opt-in external anchoring of the ledger head (HARDN-FR-005).` |
| 11 | docstring | HARDN-NFR-001 | `no network call (HARDN-NFR-001, 3PWR-NFR-004). Pushing the tag is the only network-capable` |
| 11 | docstring | 3PWR-NFR-004 | `no network call (HARDN-NFR-001, 3PWR-NFR-004). Pushing the tag is the only network-capable` |
| 44 | docstring | HARDN-NFR-001 | `"""The deterministic witness payload recorded in the tag (HARDN-NFR-001)."""` |
| 74 | docstring | HARDN-NFR-001 | `stays offline (HARDN-NFR-001).` |
| 107 | docstring | HARDN-FR-005 | `"""Cross-check the local chain against the latest anchor (HARDN-FR-005, SC-003).` |
| 111 | docstring | HARDN-NFR-001 | `the anchored head passes. Pure and deterministic (HARDN-NFR-001).` |

## engine/src/threepowers/artifacts.py (21)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | RUNLIVE-FR-001 | `"""Per-stage artifact contracts — each executive action stage declares what it must produce (RUNLIVE-FR-001).` |
| 8 | docstring | RUNLIVE-FR-002 | `a gate-red verdict and never a silent pass (RUNLIVE-FR-002).` |
| 11 | docstring | RUNLIVE-NFR-002 | `deterministic and unit-testable with a fake agent and no network (RUNLIVE-NFR-002). The engine-owned` |
| 12 | docstring | RUNLIVE-NFR-005 | `contract table below is provider-, model-, and language-agnostic (RUNLIVE-NFR-005): it names *kinds* of` |
| 14 | docstring | RUNLIVE-FR-003 | `lenient prior behavior so unconfigured stages still run (RUNLIVE-FR-003) — but PHASE-FR-002 extended the` |
| 14 | docstring | PHASE-FR-002 | `lenient prior behavior so unconfigured stages still run (RUNLIVE-FR-003) — but PHASE-FR-002 extended the` |
| 16 | docstring | PHASE-FR-001 | `committed artifact trail in the feature workspace (PHASE-FR-001) is checked at every stage.` |
| 32 | docstring | RUNLIVE-FR-002 | `(RUNLIVE-FR-002), so it must read as *what was expected*, including the location.` |
| 43 | docstring | RUNLIVE-NFR-002 | `"""The result of verifying a stage's produced paths against its contract (pure — RUNLIVE-NFR-002)."""` |
| 54 | docstring | RUNLIVE-FR-006 | `"""A short artifact summary for the per-stage result (RUNLIVE-FR-006)."""` |
| 63 | docstring | RUNLIVE-FR-002 | `"""The failure message naming the stage and the expected artifact (RUNLIVE-FR-002).` |
| 79 | comment | RUNLIVE-FR-001 | `# The engine-owned per-stage contracts (RUNLIVE-FR-001). Every lifecycle *action* stage that produces a` |
| 81 | comment | PHASE-FR-002 | `# PHASE-FR-002 removed from RUNLIVE-FR-003's lenient fallback, so a plan or tasks dispatch that writes no` |
| 81 | comment | RUNLIVE-FR-003 | `# PHASE-FR-002 removed from RUNLIVE-FR-003's lenient fallback, so a plan or tasks dispatch that writes no` |
| 83 | comment | SRCX-FR-001 | `# The spec/plan/tasks patterns accept the canonical FLAT layout (specs/<f>/<step>.md — SRCX-FR-001) and` |
| 84 | comment | SRCX-FR-003 | `# the legacy PHASE split layout (specs/<f>/spec/spec.md, specs/<f>/artifacts/<step>.md — SRCX-FR-003).` |
| 127 | docstring | RUNLIVE-FR-003 | `"""The artifact contract for an action step, or ``None`` when the step declares none (RUNLIVE-FR-003)."""` |
| 137 | docstring | RUNLIVE-NFR-002 | `"""Verify a stage's ``produced`` paths against its ``contract`` — pure and deterministic (RUNLIVE-NFR-002).` |
| 140 | docstring | RUNLIVE-FR-003 | ```None`` the stage declared no artifact, so the check is lenient and always passes (RUNLIVE-FR-003) — an` |
| 144 | docstring | RUNLIVE-FR-002 | `failure message (RUNLIVE-FR-002/006).` |
| 147 | comment | RUNLIVE-FR-003 | `if contract is None:  # RUNLIVE-FR-003: no declared contract → never block` |

## engine/src/threepowers/canonical.py (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 7 | docstring | 3PWR-NFR-001 | `(supports 3PWR-NFR-001/010).` |

## engine/src/threepowers/catalog.py (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | AGENTX-FR-015 | `"""Per-integration model/label catalog for the role setup (AGENTX-FR-015/016).` |
| 10 | docstring | AGENTX-NFR-001 | `Everything here is deterministic and fully offline (AGENTX-NFR-001): the same file bytes always` |
| 24 | comment | AGENTX-FR-015 | `# The bundled fallback — the same file `3pwr init` seeds into .3powers/config/ (AGENTX-FR-015).` |
| 54 | docstring | AGENTX-FR-015 | `"""The resolved model catalog (AGENTX-FR-015).` |
| 58 | docstring | AGENTX-FR-016 | `the shipped defaults plus free-form entry — AGENTX-FR-016)."""` |
| 71 | docstring | AGENTX-FR-015 | `"""The integrations the catalog knows, in file order (AGENTX-FR-015)."""` |
| 108 | docstring | AGENTX-FR-012 | `"""The documented default model entry for ``integration`` (AGENTX-FR-012), or ``None``.` |
| 125 | docstring | AGENTX-FR-012 | `"""Best-effort model *family* from a model id (AGENTX-FR-012 property; pure, offline).` |

## engine/src/threepowers/characterize.py (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-053 | `"""Characterization of a legacy module (3PWR-FR-053, brownfield Stage Zero §12).` |
| 7 | docstring | 3PWR-FR-051 | `only then modify it (3PWR-FR-051).` |
| 14 | docstring | 3PWR-FR-030 | `spec-conformance gate traces them, 3PWR-FR-030) and pins the public surface, with a` |
| 116 | docstring | 3PWR-FR-053 | `Generated by `3pwr characterize` (3PWR-FR-053). Each test references its reconstructed` |
| 140 | docstring | 3PWR-NFR-015 | `except Exception as exc:  # legacy import deps absent → surface as skip (3PWR-NFR-015)` |
| 174 | docstring | 3PWR-FR-053 | `"""Reconstruct a spec stub + characterization tests for one file ``module_path`` (3PWR-FR-053).` |
| 283 | docstring | 3PWR-FR-053 | `"""Characterize a single file OR every source file under a directory (3PWR-FR-053).` |

## engine/src/threepowers/cli.py (374)

| line | kind | match | excerpt |
|---|---|---|---|
| 11 | docstring | SLOCK-FR-001 | `approved document's hash into the signed entry — SLOCK-FR-001)` |
| 14 | docstring | SLOCK-FR-005 | `at High-risk + the approved spec unchanged, SLOCK-FR-005)` |
| 20 | docstring | AUTOX-FR-003 | `summary; read-only, offline, the same checks init and the run use (AUTOX-FR-003)` |
| 22 | format-example | FR-006 | `human gates (spec approval FR-006, sign-off FR-037); the native executive` |
| 22 | format-example | FR-037 | `human gates (spec approval FR-006, sign-off FR-037); the native executive` |
| 23 | docstring | EXEC-FR-001 | `dispatches each stage to a headless agent (EXEC-FR-001) and streams progress` |
| 27 | docstring | SLOCK-FR-007 | `hash? (SLOCK-FR-007)` |
| 32 | docstring | AUTOX-FR-009 | `(AUTOX-FR-009): 3 = paused at a human gate, 4 = setup/dispatch failure (never a gate verdict).` |
| 100 | comment | AUTOX-FR-009 | `# The stable `3pwr run` terminal contract (AUTOX-FR-009): one documented (status, exit-code) pair` |
| 119 | comment | PHASE-FR-001 | `# layout (the spec/ workspace subfolder or the legacy flat file — PHASE-FR-001).` |
| 137 | docstring | CLIUX-FR-014 | `the shipped defaults are used. Cached on ``args`` so the file is read at most once (CLIUX-FR-014)."""` |
| 153 | docstring | CLIUX-FR-005 | `ui.yaml ``color_mode`` (CLIUX-FR-005/014). Machine output is never routed through it (CLIUX-FR-007)."""` |
| 153 | docstring | CLIUX-FR-007 | `ui.yaml ``color_mode`` (CLIUX-FR-005/014). Machine output is never routed through it (CLIUX-FR-007)."""` |
| 164 | docstring | CLIUX-FR-013 | `"""The effective verbosity for this command (CLIUX-FR-013): ``quiet`` \| ``normal`` \| ``verbose``."""` |
| 180 | docstring | CLIUX-FR-004 | `"""Assemble a command's human output honoring verbosity (CLIUX-FR-004/006/013).` |
| 184 | docstring | CLIUX-FR-007 | `quiet ⊆ normal ⊆ verbose, and none of this touches the ``--json`` payload (CLIUX-FR-007)."""` |
| 205 | docstring | SLOCK-FR-001 | `"""Best-effort spec-hash fields for a Spec-stage sign-off (SLOCK-FR-001).` |
| 218 | docstring | ONBRD-FR-006 | `"""Onboarding is interactive only with a real TTY and neither --yes nor --json (ONBRD-FR-006)."""` |
| 262 | docstring | ONBRD-FR-006 | `(``--yes``/``--json``/no TTY) prompts for nothing (ONBRD-FR-006), so an init stays byte-stable."""` |
| 304 | docstring | 3PWR-NFR-011 | `"""Human-readable verdict: failing gate, class, and offending item — no transcript needed (3PWR-NFR-011).` |
| 306 | docstring | INITX-FR-013 | ```st`` colorizes the status markers consistently with the rest of the CLI (INITX-FR-013); a disabled` |
| 309 | docstring | GATEPIPE-FR-003 | `own panel after the pipeline view instead (GATEPIPE-FR-003)."""` |
| 377 | docstring | HARDN-FR-004 | `"""Rotate the ledger signer (HARDN-FR-004): the OUTGOING key signs its successor.` |
| 454 | docstring | ONBRD-FR-009 | `"""Create the ``.3powers/`` skeleton idempotently (ONBRD-FR-009). Returns created\|kept."""` |
| 476 | docstring | INITX-FR-009 | `"""Build the first-run readiness checklist (INITX-FR-009/010/011; AUTOX-FR-001/002).` |
| 476 | docstring | AUTOX-FR-001 | `"""Build the first-run readiness checklist (INITX-FR-009/010/011; AUTOX-FR-001/002).` |
| 480 | docstring | INITX-FR-010 | `INITX-FR-010); a 3Powers-generated AGENTS.md starter is an unfinished TODO (INITX-FR-011). No item` |
| 480 | docstring | INITX-FR-011 | `INITX-FR-010); a 3Powers-generated AGENTS.md starter is an unfinished TODO (INITX-FR-011). No item` |
| 481 | docstring | INITX-FR-009 | `is omitted (INITX-FR-009). ``auto_prqs`` — the SAME check set the live run preflight enforces` |
| 483 | docstring | AUTOX-FR-002 | `never drift (AUTOX-FR-002)."""` |
| 526 | comment | AUTOX-FR-001 | `# here means `3pwr run --mode auto` will not refuse to start (AUTOX-FR-001/002).` |
| 535 | docstring | INITX-FR-013 | `"""Render checklist items as colorized ``<mark> <label>: <detail>`` lines (INITX-FR-013)."""` |
| 539 | comment | AGENTX-FR-012 | `# The configurable roles the setup walks, in the order they are asked (AGENTX-FR-012).` |
| 544 | docstring | AGENTX-FR-018 | `"""Warn (stderr) when the oracle or reviewer resolves to the coder's family (AGENTX-FR-018).` |
| 546 | docstring | 3PWR-FR-022 | `Diversity is recommended, never forced (3PWR-FR-022/057): the warning names the signed` |
| 548 | docstring | INITX-FR-014 | `stdout stays byte-identical (INITX-FR-014). Returns the roles warned about."""` |
| 556 | comment | AGENTX-FR-012 | `# whose family the id does not encode (AGENTX-FR-012/015).` |
| 600 | docstring | 3PWR-FR-022 | `box even within a single BYOK integration (3PWR-FR-022)."""` |
| 617 | docstring | AGENTX-FR-011 | `"""The shared headless-CLI + role→model + diversity setup (AGENTX-FR-011/012/014/015).` |
| 619 | docstring | AGENTX-FR-011 | `One pass: multi-select which agent-backend CLIs you use (no provider is forced — AGENTX-FR-011),` |
| 621 | docstring | AGENTX-FR-016 | `selection and a model drawn from its catalog or entered free-form (AGENTX-FR-016), writing a` |
| 623 | docstring | AGENTX-FR-012 | `oracle) so ``3pwr run`` needs no manual role editing (AGENTX-FR-012/013). Finally choose how` |
| 624 | docstring | 3PWR-FR-022 | `diversity is judged — by ``family`` or ``model`` (3PWR-FR-022).` |
| 630 | docstring | AGENTX-NFR-004 | `Non-interactive (AGENTX-NFR-004): prompts for nothing; explicit choices are applied, and a role` |
| 632 | docstring | AGENTX-FR-014 | `(non-destructive, AGENTX-FR-014/NFR-003). Deterministic and offline (AGENTX-NFR-001); diversity` |
| 632 | format-example | NFR-003 | `(non-destructive, AGENTX-FR-014/NFR-003). Deterministic and offline (AGENTX-NFR-001); diversity` |
| 632 | docstring | AGENTX-NFR-001 | `(non-destructive, AGENTX-FR-014/NFR-003). Deterministic and offline (AGENTX-NFR-001); diversity` |
| 633 | docstring | AGENTX-FR-018 | `only ever warns (AGENTX-FR-018)."""` |
| 748 | comment | 3PWR-FR-022 | `# 3) How is diversity judged — family or model? (3PWR-FR-022)` |
| 769 | docstring | AGENTX-FR-014 | `"""(Re)run the headless-CLI + role→model setup without reinitializing (AGENTX-FR-014).` |
| 772 | docstring | AGENTX-NFR-003 | `reconfigured here are rewritten; every other roles.yaml field is preserved (AGENTX-NFR-003).` |
| 774 | docstring | AGENTX-NFR-004 | `defaults (AGENTX-NFR-004). Dispatch configuration only — no gate, verdict, ledger, or human` |
| 775 | docstring | AGENTX-NFR-002 | `gate is touched (AGENTX-NFR-002), and model diversity only ever warns (AGENTX-FR-018)."""` |
| 775 | docstring | AGENTX-FR-018 | `gate is touched (AGENTX-NFR-002), and model diversity only ever warns (AGENTX-FR-018)."""` |
| 821 | docstring | INITX-FR-006 | `"""Auto-commit after a successful lifecycle stage (INITX-FR-006).` |
| 876 | docstring | STEER-FR-010 | `"""Pick one run-notification channel (or none) and write its config (STEER-FR-010).` |
| 878 | docstring | STEER-NFR-002 | `Secrets are never stored (STEER-NFR-002): slack/teams record only the env-var *name* holding the` |
| 936 | docstring | ONBRD-FR-001 | `"""Guided onboarding — make an existing or new project 3Powers-ready in one step (ONBRD-FR-001).` |
| 939 | docstring | ONBRD-FR-006 | `documented default for every choice (ONBRD-FR-006). It creates the signer OUTSIDE the repo` |
| 940 | docstring | ONBRD-NFR-001 | `(ONBRD-NFR-001), seeds the baseline config + the selected language adapter without clobbering` |
| 941 | docstring | ONBRD-FR-008 | `(ONBRD-FR-008), records the autonomy default (ONBRD-FR-005), is idempotent on re-run` |
| 941 | docstring | ONBRD-FR-005 | `(ONBRD-FR-008), records the autonomy default (ONBRD-FR-005), is idempotent on re-run` |
| 942 | docstring | ONBRD-FR-009 | `(ONBRD-FR-009), and prints greenfield-vs-brownfield next steps (ONBRD-FR-010). Fully offline` |
| 942 | docstring | ONBRD-FR-010 | `(ONBRD-FR-009), and prints greenfield-vs-brownfield next steps (ONBRD-FR-010). Fully offline` |
| 943 | docstring | ONBRD-NFR-002 | `(ONBRD-NFR-002)."""` |
| 948 | comment | ONBRD-FR-002 | `# 1) Target directory — default the current directory (ONBRD-FR-002).` |
| 970 | comment | ONBRD-FR-010 | `# 3) Brownfield detection + a suggested default language (ONBRD-FR-010).` |
| 983 | comment | ONBRD-FR-003 | `# 4) Language selection from the supported (adapter-backed) set (ONBRD-FR-003).` |
| 988 | comment | ONBRD-FR-004 | `# 5) Signing key — a private location OUTSIDE the repo (ONBRD-FR-004/007, NFR-001).` |
| 988 | format-example | NFR-001 | `# 5) Signing key — a private location OUTSIDE the repo (ONBRD-FR-004/007, NFR-001).` |
| 1025 | comment | ONBRD-FR-005 | `# 6) Autonomy default (ONBRD-FR-005) — advisory; never bypasses a human gate (NFR-004).` |
| 1025 | format-example | NFR-004 | `# 6) Autonomy default (ONBRD-FR-005) — advisory; never bypasses a human gate (NFR-004).` |
| 1032 | comment | ONBRD-FR-008 | `# 7) Seed baseline config + the selected adapter, never clobbering (ONBRD-FR-008).` |
| 1040 | comment | INITX-FR-001 | `#    (INITX-FR-001/002; AGENTX-FR-011/012). The seeded roles.yaml is the documented default,` |
| 1040 | comment | AGENTX-FR-011 | `#    (INITX-FR-001/002; AGENTX-FR-011/012). The seeded roles.yaml is the documented default,` |
| 1041 | comment | AGENTX-NFR-004 | `#    so a non-interactive init prompts for nothing and stays run-ready (AGENTX-NFR-004).` |
| 1050 | comment | INITX-FR-001 | `# default (INITX-FR-001/002; AGENTX-FR-011/012): risk tier → which agent CLIs → per-role model →` |
| 1050 | comment | AGENTX-FR-011 | `# default (INITX-FR-001/002; AGENTX-FR-011/012): risk tier → which agent CLIs → per-role model →` |
| 1052 | comment | AGENTX-NFR-004 | `# empty notifications are the documented defaults and stay run-ready (AGENTX-NFR-004).` |
| 1068 | comment | 3PWR-FR-022 | `# Diversity is recommended, not forced (3PWR-FR-022/057). Warn to STDERR so a --json` |
| 1069 | comment | INITX-FR-014 | `# run's stdout stays byte-identical (INITX-FR-014); never a silent accept (INITX-FR-002).` |
| 1069 | comment | INITX-FR-002 | `# run's stdout stays byte-identical (INITX-FR-014); never a silent accept (INITX-FR-002).` |
| 1093 | comment | ONBRD-FR-016 | `# 9) AGENTS.md — create a 3Powers starter if the repo has none (ONBRD-FR-016).` |
| 1098 | comment | EXEC-FR-004 | `#     (EXEC-FR-004; SLIM removed the substrate) — and each dispatched stage's editable` |
| 1099 | comment | AGENTX-FR-001 | `#     instructions live in .3powers/templates/agents/ (AGENTX-FR-001/009).` |
| 1106 | comment | INITX-FR-002 | `# different from the coder's (INITX-FR-002 / 3PWR-FR-022). The oracle's explicit model_family` |
| 1106 | comment | 3PWR-FR-022 | `# different from the coder's (INITX-FR-002 / 3PWR-FR-022). The oracle's explicit model_family` |
| 1107 | comment | AGENTX-FR-012 | `# wins over prefix-derivation — catalog bindings may use bare ids (AGENTX-FR-012/015).` |
| 1116 | comment | AUTOX-FR-001 | `# Auto full-mode readiness — the SAME check set the live run preflight enforces (AUTOX-FR-001/002):` |
| 1156 | comment | AUTOX-FR-002 | `# (AUTOX-FR-002/005) — derived from the same checks the run preflight enforces.` |
| 1167 | comment | INITX-FR-013 | `# ---- human, colorized summary (INITX-FR-013) ----` |
| 1202 | comment | INITX-FR-009 | `# Readiness checklist (INITX-FR-009/010/011). The header keeps the phrase the onboarding` |
| 1203 | comment | ONBRD-FR-015 | `# contract documents (ONBRD-FR-015) so existing guidance stays discoverable.` |
| 1213 | comment | AUTOX-FR-005 | `# The remaining auto full-mode steps, as exact fixes in dependency order (AUTOX-FR-005):` |
| 1233 | comment | STEER-NFR-002 | `# in the config — STEER-NFR-002). Shown as a call-to-action alongside the signer export.` |
| 1251 | comment | INITX-FR-012 | `# describe what you want and 3pwr drives the lifecycle (INITX-FR-012).` |
| 1263 | comment | 3PWR-FR-051 | `# Existing code? The now-working brownfield on-ramp, demoted below the primary CTA (3PWR-FR-051/052).` |
| 1278 | docstring | GATECFG-FR-005 | `"""The one auto-detection startup line (GATECFG-FR-005), e.g.` |
| 1289 | docstring | GATECFG-FR-003 | `"""Assemble the effective gate configuration (GATECFG-FR-003), or ``None`` when it cannot be.` |
| 1304 | comment | GDIAG-FR-002 | `# --id <NNN> is the run-number shorthand for --spec (GDIAG-FR-002): resolve the one matching` |
| 1321 | comment | 3PWR-FR-051 | `# Brownfield adoption (3PWR-FR-051/052): report-only / diff-scope is the on-ramp for a repo` |
| 1332 | comment | GATEPIPE-FR-001 | `# The live per-gate pipeline (GATEPIPE-FR-001/002): rows update in place on a capable TTY and` |
| 1337 | comment | GATECFG-FR-003 | `# The effective gate configuration (GATECFG-FR-003): the adapter manifest, the project's` |
| 1339 | comment | GATECFG-FR-004 | `# auto-detected once at startup (GATECFG-FR-004). One line names what was detected, never` |
| 1340 | comment | GATECFG-FR-005 | `# under --json (GATECFG-FR-005). An unassemblable config degrades to None: run_gates loads` |
| 1367 | comment | GDIAG-FR-004 | `# A required tool of a non-optional gate is absent (GDIAG-FR-004): no gate ran; the per-tool` |
| 1392 | comment | GATECFG-FR-008 | `# The auto-fixed announcement (GATECFG-FR-008): one line per gate a fix turned green — human` |
| 1399 | comment | GATEPIPE-FR-003 | `# One panel per failed gate, printed after the live pipeline exits (GATEPIPE-FR-003) — the` |
| 1408 | comment | 3PWR-FR-034 | `# exactly what to install so the next `gate run` / `3pwr run` succeeds (3PWR-FR-034). Human-output` |
| 1437 | comment | 3PWR-FR-052 | `# (optionally diff-scoped via --base/--paths) once the diff is clean (3PWR-FR-052).` |
| 1444 | docstring | GATECFG-FR-010 | `"""Render the effective per-gate configuration — without executing any gate (GATECFG-FR-010).` |
| 1448 | docstring | GATECFG-FR-003 | `committed ``gates.yaml`` override, or startup auto-detection (GATECFG-FR-003/004)."""` |
| 1521 | comment | HARDN-FR-002 | `# Custody preflight (HARDN-FR-002): a private key inside the working tree or readable` |
| 1531 | comment | HARDN-FR-005 | `# Opt-in anchored mode (HARDN-FR-005): cross-check the chain against the latest` |
| 1532 | comment | HARDN-NFR-001 | `# local anchor tag. Plain `verify` never reads an anchor (HARDN-NFR-001).` |
| 1566 | docstring | HARDN-FR-005 | `"""Record the ledger head with an external witness (HARDN-FR-005) — opt-in.` |
| 1570 | docstring | HARDN-NFR-001 | `(the sole network-capable operation, HARDN-NFR-001).` |
| 1640 | comment | SLOCK-FR-001 | `# signed entry so any later silent mutation is caught (SLOCK-FR-001). A fresh` |
| 1641 | comment | SLOCK-FR-006 | `# Spec-stage sign-off supersedes the previous hash (SLOCK-FR-006).` |
| 1666 | docstring | SLOCK-FR-007 | `"""Read-only spec-integrity report (SLOCK-FR-007) — never writes to the ledger.` |
| 1760 | docstring | 3PWR-FR-041 | `"""Local, CI-independent enforcement (3PWR-FR-041/042)."""` |
| 1774 | comment | 3PWR-FR-057 | `#    active, signed deviation (3PWR-FR-057). Report-only verdicts are advisory (3PWR-FR-052)` |
| 1774 | comment | 3PWR-FR-052 | `#    active, signed deviation (3PWR-FR-057). Report-only verdicts are advisory (3PWR-FR-052)` |
| 1804 | comment | 3PWR-FR-056 | `# 2b. An emergency cleanup overdue past one working day blocks the advance (3PWR-FR-056).` |
| 1812 | comment | 3PWR-FR-037 | `# 3. A human sign-off must exist at or after the latest verdict (3PWR-FR-037).` |
| 1819 | comment | 3PWR-FR-020 | `# 4. Oracle independence (3PWR-FR-020/021/022/062). The judiciary must have authored the oracle` |
| 1823 | format-example | FR-021 | `#    At High-risk, physical read-path isolation (FR-021, A3) is also proven when a dispatch` |
| 1854 | comment | SLOCK-FR-005 | `# 5. Spec integrity (SLOCK-FR-005): once a human has approved the spec, its recorded` |
| 1856 | comment | 3PWR-FR-057 | `#    `spec_integrity` deviation (3PWR-FR-057) turns the refusal into a warned,` |
| 1858 | comment | SLOCK-FR-003 | `#    never blocked (SLOCK-FR-003).` |
| 1878 | comment | GITX-FR-016 | `# 6. Git run discipline (GITX-FR-016): when the spec's run records a dedicated branch, a` |
| 1881 | comment | GITX-FR-014 | `#    deviations (GITX-FR-014); a pre-GITX ledger records no branch and is untouched.` |
| 1966 | docstring | 3PWR-FR-057 | `"""Record (or revoke) a signed, reversible gate deviation (3PWR-FR-057)."""` |
| 2047 | docstring | 3PWR-FR-056 | `"""Open the constrained emergency fast path (3PWR-FR-056)."""` |
| 2128 | docstring | 3PWR-FR-022 | `"""Check model diversity between two roles (3PWR-FR-022), at the configured granularity.` |
| 2131 | docstring | 3PWR-FR-057 | `deviation (3PWR-FR-057), which turns the VIOLATION into a warned RELAXED (exit 0)."""` |
| 2173 | docstring | 3PWR-FR-020 | `"""Seal a spec-only oracle bundle the judiciary authors from (3PWR-FR-020)."""` |
| 2229 | docstring | 3PWR-FR-022 | `"""Record oracle authoring; refuse the coder's model family (3PWR-FR-022/062)."""` |
| 2249 | comment | 3PWR-FR-022 | `# Diversity is recommended, not forced (3PWR-FR-022): a same-family/model setup proceeds only under` |
| 2250 | comment | 3PWR-FR-057 | `# a signed model_diversity deviation (3PWR-FR-057) — warned and recorded, never a silent drop.` |
| 2304 | comment | 3PWR-FR-021 | `# Advisory (non-blocking) peek/touch signals for human review (3PWR-FR-021).` |
| 2363 | docstring | 3PWR-FR-020 | `"""Verify oracle independence structurally, from the ledger (3PWR-FR-020/021/022/062)."""` |
| 2430 | docstring | 3PWR-FR-021 | `which the implementation is physically absent (3PWR-FR-021/012/013; A3).` |
| 2433 | docstring | 3PWR-NFR-001 | `gate verdict (3PWR-NFR-001). The blocking isolation check binds at ``advance`` (High-risk)."""` |
| 2444 | comment | 3PWR-FR-022 | `# Resolve the oracle model/family. Diversity is recommended, not forced (3PWR-FR-022): a` |
| 2445 | format-example | FR-057 | `# same-family/model dispatch proceeds only under a signed model_diversity deviation (FR-057).` |
| 2518 | comment | EXEC-FR-009 | `# worktree — no external workflow substrate (EXEC-FR-009; supersedes the Spec Kit dispatch).` |
| 2519 | comment | EXEC-NFR-001 | `# The engine issues no model call itself; the agent process does (EXEC-NFR-001).` |
| 2579 | comment | 3PWR-FR-021 | `# Advisory (non-blocking) peek/touch signals, unchanged from plan 008 (3PWR-FR-021).` |
| 2689 | docstring | 3PWR-FR-054 | `"""Record a production signal and route it to the legislature as new intent (3PWR-FR-054)."""` |
| 2747 | docstring | 3PWR-FR-054 | `"""Report NFR-instrumentation coverage — which NFRs have a live check (3PWR-FR-054)."""` |
| 2785 | docstring | 3PWR-FR-055 | `"""Append a tamper-evident, attributable runtime agent action (3PWR-FR-055)."""` |
| 2824 | docstring | 3PWR-FR-055 | `"""Verify the runtime agent-action log's chain + signatures (3PWR-FR-055/040)."""` |
| 2842 | docstring | 3PWR-FR-011 | `"""Per-spec lifecycle stage, derived from the ledger (3PWR-FR-011/019)."""` |
| 2855 | comment | AUTOX-FR-007 | `# The most recent unresolved run failure, if any (AUTOX-FR-007).` |
| 2881 | comment | AUTOX-FR-007 | `# Distinct from paused-at-gate and from in-progress (AUTOX-FR-007).` |
| 2901 | comment | 3PWR-FR-056 | `# Surface active deviations + overdue emergency cleanups (3PWR-FR-056/057).` |
| 2914 | comment | GITX-FR-009 | `# Surface each run's git lifecycle state (GITX-FR-009): its dedicated branch and the committed` |
| 2927 | comment | 3PWR-FR-020 | `# Surface oracle authoring records + advisory peek/touch findings (3PWR-FR-020/021/062).` |
| 2946 | docstring | GITX-FR-016 | `"""Establish the run's dedicated branch for a MANUAL drive (GITX-FR-016).` |
| 2949 | docstring | GITX-FR-002 | `repository (GITX-FR-002), the clean-start guard (GITX-FR-007), and one dedicated branch named` |
| 2949 | docstring | GITX-FR-007 | `repository (GITX-FR-002), the clean-start guard (GITX-FR-007), and one dedicated branch named` |
| 2950 | docstring | GITX-FR-003 | `from the run's SRCX identity (GITX-FR-003/004) — bound to the run in the signed ledger so a` |
| 2951 | docstring | GITX-FR-005 | `later resume or `advance` recovers it offline (GITX-FR-005). Idempotent: an already-established` |
| 2980 | comment | GITX-FR-007 | `# The clean-start guard (GITX-FR-007) — the run's own recorded paths and its feature folder are` |
| 2981 | comment | GITX-FR-014 | `# tolerated; only unrelated changes refuse, relaxable via the signed deviation (GITX-FR-014).` |
| 3005 | comment | GITX-FR-005 | `# the orchestrated path records (GITX-FR-005, GITX-NFR-002).` |
| 3005 | comment | GITX-NFR-002 | `# the orchestrated path records (GITX-FR-005, GITX-NFR-002).` |
| 3034 | docstring | 3PWR-FR-058 | `"""Infer work kind(s) + a suggested risk tier from free-form intent (3PWR-FR-058).` |
| 3036 | docstring | 3PWR-NFR-001 | `Deterministic (keyword heuristics, no model call — never perturbs the verdict, 3PWR-NFR-001). The` |
| 3037 | docstring | 3PWR-FR-006 | `inference shapes the tier + oracle strategy; it never bypasses the human sign-off (3PWR-FR-006)."""` |
| 3062 | docstring | STEER-FR-009 | `"""Fire ``event`` at the ``--notify`` hook AND every configured channel (STEER-FR-009/011).` |
| 3064 | docstring | STEER-NFR-001 | `Best-effort and fully isolated from the trust path (STEER-NFR-001): the channels are loaded at` |
| 3065 | docstring | STEER-FR-010 | `most once per invocation (a malformed file warns once — STEER-FR-010), delivery never raises,` |
| 3067 | docstring | STEER-NFR-002 | `(STEER-NFR-002). With no ``notifications.yaml`` and no ``--notify``, nothing happens and no` |
| 3069 | docstring | RUNID-FR-003 | `local, so a workspace-derived NNN reaches the notification too (RUNID-FR-003)."""` |
| 3072 | comment | STEER-FR-011 | `)  # the existing command hook keeps working alongside (STEER-FR-011)` |
| 3084 | docstring | SRCX-FR-011 | `"""The run's bound feature folder, read back from the signed ``run``/``start`` entry (SRCX-FR-011).` |
| 3106 | docstring | STEER-FR-006 | `A revise re-dispatches the paused stage WITH the original intent (STEER-FR-006) — recovered from` |
| 3107 | docstring | STEER-FR-004 | `the ledger alone (STEER-FR-004's reproducibility), never re-asked."""` |
| 3120 | docstring | STEER-FR-005 | `review (STEER-FR-005) — one source for the pause screen and the interactive prompt."""` |
| 3140 | docstring | 3PWR-FR-006 | `"""Record the human's gate approval as a signed sign-off (3PWR-FR-006 spec / FR-037 evidence).` |
| 3140 | format-example | FR-037 | `"""Record the human's gate approval as a signed sign-off (3PWR-FR-006 spec / FR-037 evidence).` |
| 3143 | docstring | SLOCK-FR-001 | `signed entry (SLOCK-FR-001) — same capture as a manual `3pwr signoff --stage spec`.` |
| 3168 | docstring | AUTOX-FR-006 | `"""Append the signed run-failure record before exiting (AUTOX-FR-006).` |
| 3171 | docstring | AUTOX-NFR-003 | `the existing append API — additive content only, so ``3pwr verify`` stays green (AUTOX-NFR-003).` |
| 3172 | docstring | AUTOX-FR-008 | `The transcript field carries the persisted path, never the output itself (AUTOX-FR-008)."""` |
| 3187 | docstring | EXEC-FR-013 | `(EXEC-FR-013)."""` |
| 3194 | docstring | EXEC-FR-009 | `"""The coder agent backend: --agent wins, else --integration/roles.coder.integration (EXEC-FR-009)."""` |
| 3204 | docstring | SRCX-FR-011 | `(SRCX-FR-011 — no modification-time scan), else the newest feature spec under specs/ (legacy)."""` |
| 3225 | docstring | EXEC-FR-006 | `"""Run the deterministic gate suite IN-PROCESS for the native verify stage (EXEC-FR-006).` |
| 3228 | docstring | GDIAG-FR-004 | `adapter detected, bad tier, or a missing gate prerequisite — GDIAG-FR-004) so the caller reports a` |
| 3229 | docstring | EXEC-FR-016 | `setup/dispatch problem, never a false gate-red (EXEC-FR-016). The engine computes the verdict itself` |
| 3230 | docstring | 3PWR-NFR-001 | `— no subprocess dispatch, no model (3PWR-NFR-001).` |
| 3234 | docstring | AUTOX-FR-011 | ```verdict`` entry — so an in-run red or green is never invisible to the trust spine (AUTOX-FR-011).` |
| 3235 | docstring | AUTOX-NFR-003 | `The verdict bytes themselves are unchanged (AUTOX-NFR-003). When ``out`` is given, the computed` |
| 3237 | docstring | GDIAG-FR-001 | `gates inline (GDIAG-FR-001)."""` |
| 3243 | comment | GATECFG-FR-003 | `# The same effective configuration as a standalone gate run (GATECFG-FR-003/004): the` |
| 3245 | comment | GATECFG-FR-005 | `# human output only (GATECFG-FR-005). Degrades to None — run_gates loads the adapter.` |
| 3260 | comment | GDIAG-FR-004 | `# No gate ran — say exactly what to install (GDIAG-FR-004), then report the setup failure.` |
| 3281 | docstring | RUNLIVE-FR-004 | `"""The per-stage dispatch timeout (RUNLIVE-FR-004): --timeout wins, else the configured default."""` |
| 3287 | docstring | RUNLIVE-FR-005 | `"""The dispatch retry budget (RUNLIVE-FR-005): --retries wins, else the configured default."""` |
| 3293 | docstring | RUNLIVE-FR-006 | `"""Stream agent output live only on a real TTY and not under --json (RUNLIVE-FR-006)."""` |
| 3310 | docstring | RUNLIVE-FR-008 | `RUNLIVE-FR-008). Both satisfy the same ``dispatch(step, stage) -> DispatchResult`` contract, so the` |
| 3311 | docstring | RUNLIVE-NFR-003 | `verdict is judged identically (RUNLIVE-NFR-003). The transcript sink persists each local attempt's` |
| 3312 | docstring | AUTOX-FR-008 | `output (AUTOX-FR-008); a hosted backend's output lives with its hosting service. ``echo`` routes the` |
| 3313 | docstring | STEER-FR-012 | `streamed agent conversation above the run's live bar instead of raw stdout (STEER-FR-012)."""` |
| 3333 | docstring | PHASE-FR-005 | `"""The approved-spec text a stage's prompt reloads (PHASE-FR-005).` |
| 3338 | docstring | PHASE-NFR-001 | `tree (PHASE-NFR-001)."""` |
| 3350 | docstring | PHASE-FR-005 | `"""A reference to (digest of) an accepted stage artifact for the NEXT stage's prompt (PHASE-FR-005)."""` |
| 3363 | docstring | PHASE-FR-010 | `"""The ordered phases declared by the feature's tasks artifact, or ``[]`` (PHASE-FR-010).` |
| 3382 | docstring | PHASE-FR-008 | `"""Per-phase context estimates + the advisory oversize warnings after the tasks stage (PHASE-FR-008/009).` |
| 3387 | docstring | PHASE-NFR-002 | `(PHASE-NFR-002)."""` |
| 3412 | docstring | PHASEPR-FR-005 | `"""Advisory stall check after one phase session ends (PHASEPR-FR-005).` |
| 3416 | docstring | PHASEPR-NFR-002 | `Strictly advisory (PHASEPR-NFR-002): it never raises, never retries, and never changes a stage` |
| 3450 | docstring | PHASE-FR-010 | `"""Run the implement stage phase by phase (PHASE-FR-010/011/012).` |
| 3454 | docstring | 3PWR-FR-061 | `state carried between phases (3PWR-FR-061). Phases marked parallel with disjoint declared scopes` |
| 3457 | docstring | PHASE-NFR-003 | `touches the trust spine concurrently (PHASE-NFR-003). Any phase failure fails the stage naming the` |
| 3458 | docstring | PHASE-FR-012 | `phase(s); later phases are recorded as explicitly skipped, never as passed (PHASE-FR-012)."""` |
| 3499 | comment | AUTOX-FR-008 | `# phased failure still points at the persisted output (AUTOX-FR-008).` |
| 3530 | docstring | SRCX-FR-001 | `"""The deterministic prompt line naming the run's feature folder (SRCX-FR-001/008).` |
| 3534 | docstring | SRCX-FR-013 | `the completion gate asserts (SRCX-FR-013's property)."""` |
| 3549 | docstring | PROGFILE-NFR-001 | `"""Run one progress-file update, degrading any error to a stderr warning (PROGFILE-NFR-001).` |
| 3578 | docstring | EXEC-FR-001 | `"""Build the native executive runner: dispatch each stage to the role's agent (EXEC-FR-001/009), verify` |
| 3579 | docstring | RUNLIVE-FR-001 | `its declared artifact (RUNLIVE-FR-001/002), retry/timeout-bound the dispatch (RUNLIVE-FR-004/005),` |
| 3579 | docstring | RUNLIVE-FR-004 | `its declared artifact (RUNLIVE-FR-001/002), retry/timeout-bound the dispatch (RUNLIVE-FR-004/005),` |
| 3581 | docstring | GITX-FR-001 | `3pwr-authored stage commit (GITX-FR-001/010/011/012, superseding RUNLIVE-FR-010's opt-out` |
| 3581 | docstring | RUNLIVE-FR-010 | `3pwr-authored stage commit (GITX-FR-001/010/011/012, superseding RUNLIVE-FR-010's opt-out` |
| 3583 | docstring | SRCX-FR-004 | `producing stage (SRCX-FR-004/005/012), and run the gate suite in-process at Verify (EXEC-FR-006)."""` |
| 3583 | docstring | EXEC-FR-006 | `producing stage (SRCX-FR-004/005/012), and run the gate suite in-process at Verify (EXEC-FR-006)."""` |
| 3595 | comment | AUTOX-FR-008 | `# under .3powers/runs/<spec-id>/, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).` |
| 3595 | comment | AUTOX-NFR-002 | `# under .3powers/runs/<spec-id>/, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).` |
| 3623 | comment | PHASE-FR-005 | `# knows the committed context boundary it continues from (PHASE-FR-005).` |
| 3627 | comment | GITX-FR-001 | `# The mandatory PRE-STAGE git hook (GITX-FR-001): every stage of a live run happens on the` |
| 3629 | comment | GITX-NFR-003 | `# before dispatching; a switch git refuses is a named failure, never forced (GITX-NFR-003).` |
| 3641 | comment | 3PWR-FR-022 | `# (3PWR-FR-022). Physical read-path isolation stays with `3pwr oracle dispatch`, which a` |
| 3642 | comment | 3PWR-FR-021 | `# High-risk `advance` enforces (3PWR-FR-021); the run routes the oracle stage to its backend here.` |
| 3653 | comment | RUNLIVE-FR-003 | `# A None contract verifies leniently (RUNLIVE-FR-003), so this always runs.` |
| 3656 | comment | SRCX-FR-017 | `# A completion-gate re-run (SRCX-FR-017) may regenerate a committed artifact` |
| 3660 | comment | 3PWR-FR-032 | `# so nothing is weakened for a first run (3PWR-FR-032).` |
| 3669 | comment | SRCX-FR-001 | `# feature folder (the agent-authored markdown stages — SRCX-FR-001), and the prior stage's` |
| 3670 | comment | PHASE-FR-005 | `# accepted artifact reference — no stage rediscovers its inputs (PHASE-FR-005).` |
| 3679 | comment | STEER-FR-006 | `# (STEER-FR-006) — assembled deterministically upstream (STEER-NFR-003).` |
| 3679 | comment | STEER-NFR-003 | `# (STEER-FR-006) — assembled deterministically upstream (STEER-NFR-003).` |
| 3686 | comment | PHASE-FR-010 | `# scopes are disjoint (PHASE-FR-010/011); a phaseless artifact stays a single dispatch.` |
| 3715 | comment | SRCX-FR-004 | `# their real outputs at their real repo paths (SRCX-FR-004/005). For a phased` |
| 3717 | comment | SRCX-FR-006 | `# in deterministic order (SRCX-FR-006, SRCX-NFR-006).` |
| 3717 | comment | SRCX-NFR-006 | `# in deterministic order (SRCX-FR-006, SRCX-NFR-006).` |
| 3720 | comment | SRCX-FR-005 | `# the record links the full produced change set (SRCX-FR-005's property)` |
| 3742 | comment | PHASE-FR-008 | `# over-budget phase (PHASE-FR-008/009).` |
| 3744 | comment | AUTOX-FR-010 | `# Record the completion itself — lightweight, additive (AUTOX-FR-010, extends` |
| 3745 | comment | RUNLIVE-FR-010 | `# RUNLIVE-FR-010): resume progress lives in the signed ledger, not only in checkpoint` |
| 3752 | comment | PROGFILE-FR-007 | `# The stage-complete trigger (PROGFILE-FR-007), BEFORE the post-stage commit below,` |
| 3753 | comment | PROGFILE-FR-008 | `# so the committed progress.md already shows this stage ✓ done (PROGFILE-FR-008).` |
| 3756 | comment | GITX-FR-001 | `# The mandatory POST-STAGE git hook (GITX-FR-001/010, superseding RUNLIVE-FR-010's` |
| 3756 | comment | RUNLIVE-FR-010 | `# The mandatory POST-STAGE git hook (GITX-FR-001/010, superseding RUNLIVE-FR-010's` |
| 3759 | comment | GITX-FR-011 | `# and spec id (deterministic fallback — GITX-FR-011) and the 3pwr author applied` |
| 3760 | comment | GITX-FR-012 | `# per-commit (GITX-FR-012, GITX-NFR-004). A stage that produced nothing forces no empty` |
| 3760 | comment | GITX-NFR-004 | `# per-commit (GITX-FR-012, GITX-NFR-004). A stage that produced nothing forces no empty` |
| 3762 | comment | GITX-FR-008 | `# author. After it, no run-produced change is left uncommitted (GITX-FR-008).` |
| 3765 | comment | RUNID-FR-005 | `# The engine's ledger rides every producing stage commit (RUNID-FR-005): the` |
| 3773 | comment | PROGFILE-FR-008 | `# The run's progress file rides the same stage commit (PROGFILE-FR-008): committed` |
| 3792 | comment | GITX-FR-008 | `# Clean-stop would be violated (GITX-FR-008) — a named, recorded failure on the` |
| 3815 | comment | PHASE-FR-003 | `# artifact trail is reconstructable from the ledger alone (PHASE-FR-003).` |
| 3819 | comment | SRCX-FR-012 | `# The deterministic completion gate (SRCX-FR-012): the stage's declared markdown must` |
| 3822 | comment | SRCX-FR-014 | `# re-run (SRCX-FR-014/015). Pure given (disk state, ledger entries, step); one ledger` |
| 3823 | comment | SRCX-NFR-001 | `# read serves the check (SRCX-NFR-001/004).` |
| 3843 | comment | AUTOX-FR-011 | `# (AUTOX-FR-011): a red or green at Verify is never invisible to the trust spine. The` |
| 3845 | comment | GDIAG-FR-001 | `# (GDIAG-FR-001).` |
| 3856 | comment | GATECFG-FR-008 | `# An --auto-fix run's fixed paths join the run's produced set (GATECFG-FR-008): they land` |
| 3858 | comment | GITX-FR-008 | `# uncommitted (GITX-FR-008). The signed ledger rides along, as on every stage commit.` |
| 3944 | docstring | STEER-FR-006 | `"""Revise-with-message at a paused human gate (STEER-FR-006..008).` |
| 3966 | comment | STEER-FR-006 | `args.intent = _run_intent_from_ledger(ledger.entries(), spec_id)  # STEER-FR-006` |
| 3986 | comment | STEER-FR-008 | `# The revision is auditable from the ledger alone (STEER-FR-008): feedback + outcome ride the` |
| 4002 | comment | STEER-FR-006 | `# The run returns to the SAME gate (STEER-FR-006): re-record the pause so the ledger-derived` |
| 4070 | docstring | STEER-FR-005 | `"""The three-action interactive choice at a paused human gate (STEER-FR-005): approve / revise /` |
| 4074 | docstring | 3PWR-FR-006 | `approval (3PWR-FR-006). An unrecognized answer re-prompts."""` |
| 4111 | docstring | 3PWR-FR-011 | `"""Drive the whole lifecycle loop (3PWR-FR-011; §6). ``auto`` stops only at the two mandatory human` |
| 4112 | format-example | FR-006 | `gates (FR-006 spec approval, FR-037 sign-off); ``commit`` stops at every gate. By default the` |
| 4112 | format-example | FR-037 | `gates (FR-006 spec approval, FR-037 sign-off); ``commit`` stops at every gate. By default the` |
| 4113 | docstring | EXEC-FR-001 | `**native** executive dispatches each stage to a headless agent directly (EXEC-FR-001) and runs the` |
| 4114 | docstring | EXEC-FR-006 | `gate suite in-process at Verify (EXEC-FR-006); ``--runner sim`` uses the offline simulator (also` |
| 4115 | docstring | EXEC-NFR-001 | `forced by ``--dry-run``). The engine makes no model call itself (EXEC-NFR-001) and never enters the` |
| 4116 | docstring | 3PWR-NFR-001 | `deterministic verdict (3PWR-NFR-001)."""` |
| 4119 | comment | ONBRD-FR-005 | `mode = args.mode or s.default_mode()  # --mode wins; else the `3pwr init` default (ONBRD-FR-005)` |
| 4148 | comment | AUTOX-FR-007 | `# A recorded, unresolved run failure — distinct from paused and in-progress (AUTOX-FR-007).` |
| 4158 | comment | GITX-FR-009 | `# The run's git lifecycle state (GITX-FR-009): its dedicated branch and the per-stage` |
| 4160 | comment | GITX-NFR-001 | `# no model and no network (GITX-NFR-001).` |
| 4191 | comment | STEER-FR-001 | `# File-based intent (STEER-FR-001..003): resolve --file (+ the optional inline instruction)` |
| 4193 | comment | STEER-FR-004 | `# is written; every downstream consumer sees ONLY the resolved intent (STEER-FR-004).` |
| 4208 | comment | EXEC-NFR-003 | `# Resolve the coder + oracle agents from config/flags — provider-agnostic (EXEC-NFR-003).` |
| 4214 | comment | EXEC-FR-015 | `# Preflight — a live run must not dispatch a stage until its prerequisites hold (EXEC-FR-015):` |
| 4216 | comment | AUTOX-FR-002 | `# shared check set init's readiness and `3pwr ready` report (AUTOX-FR-002), so they cannot` |
| 4218 | comment | EXEC-FR-016 | `# (EXEC-FR-016).` |
| 4230 | comment | RUNX-FR-010 | `# alternatives — never "gates red", never the incident path (RUNX-FR-010/012, NFR-004).` |
| 4230 | format-example | NFR-004 | `# alternatives — never "gates red", never the incident path (RUNX-FR-010/012, NFR-004).` |
| 4231 | comment | AUTOX-FR-009 | `# Exits with the setup/dispatch code, distinct from usage and gates-red (AUTOX-FR-009).` |
| 4263 | comment | RUNLIVE-FR-006 | `stream = _run_stream(args)  # stream agent output live on a TTY (RUNLIVE-FR-006)` |
| 4267 | comment | GITX-FR-014 | `# signed deviation as the only relaxation (GITX-FR-014). --dry-run / the simulator dispatch` |
| 4282 | comment | GITX-FR-014 | `# The plain opt-out is SUPERSEDED (GITX-FR-014): the stage commit is mandatory; the only` |
| 4293 | comment | GDIAG-FR-001 | `# event can render each failed gate inline with the run's resolved identity (GDIAG-FR-001/006).` |
| 4295 | comment | PROGFILE-FR-001 | `# The run's progress-file reporter (PROGFILE-FR-001) — bound once the live run's feature folder` |
| 4302 | comment | GDIAG-FR-001 | `# choke point every runner path flows through (GDIAG-FR-001/006).` |
| 4308 | comment | PROGFILE-FR-007 | `# The progress file's lifecycle triggers (PROGFILE-FR-007), at the same choke point:` |
| 4327 | docstring | RUNX-FR-007 | `(RUNX-FR-007/NFR-002); the oracle stage carries the oracle integration/model. No-op for --dry-run` |
| 4327 | format-example | NFR-002 | `(RUNX-FR-007/NFR-002); the oracle stage carries the oracle integration/model. No-op for --dry-run` |
| 4328 | docstring | RUNX-FR-012 | `(it dispatches nothing) so the offline simulation records nothing (RUNX-FR-012). Keyed on the actual` |
| 4330 | docstring | RUNLIVE-FR-010 | `dispatch (RUNLIVE-FR-010)."""` |
| 4361 | comment | STEER-FR-012 | `# (STEER-FR-012); with no bar (off-TTY/degraded) the echo stays the process's stdout.` |
| 4363 | comment | STEER-FR-013 | `# Live event delivery (STEER-FR-013): the bar learns a stage is running the moment its` |
| 4371 | docstring | RUNLIVE-FR-006 | `"""The per-stage machine-readable results of the dispatched stages, for --json (RUNLIVE-FR-006)."""` |
| 4374 | comment | SRCX-FR-008 | `# The run's bound feature folder (SRCX-FR-008/010/011) — resolved per branch below.` |
| 4385 | comment | STEER-FR-006 | `# The third gate action (STEER-FR-006/007): a revise outside a paused gate, or with` |
| 4403 | comment | AUTOX-FR-010 | `# No recorded progress at all — say so honestly and name the fresh start (AUTOX-FR-010).` |
| 4411 | format-example | FR-006 | `# A human gate was awaiting approval — record the sign-off before continuing (FR-006/037).` |
| 4414 | comment | SRCX-FR-010 | `# one (SRCX-FR-010/011); a pre-SRCX run falls back to the resolvable spec's folder.` |
| 4417 | comment | SRCX-NFR-004 | `)  # one read serves resume + the completion checks (SRCX-NFR-004)` |
| 4423 | comment | PROGFILE-FR-001 | `# Rebind the run's progress file to the recorded workspace (PROGFILE-FR-001): the` |
| 4433 | comment | GITX-FR-004 | `# The pre-stage git hook on resume (GITX-FR-004/005/007): recover the run's branch from` |
| 4464 | comment | STEER-FR-006 | `# feedback, then return to the SAME gate (STEER-FR-006..008).` |
| 4480 | format-example | FR-010 | `# failure resumes from the next uncompleted stage without re-dispatching a committed one (FR-010)` |
| 4481 | comment | SRCX-FR-017 | `# — then intersect with the on-disk completion check (SRCX-FR-017): a recorded stage whose` |
| 4490 | comment | RUNX-FR-004 | `_record_dispatch(start_index)  # provenance for the resumed segment only (RUNX-FR-004/007)` |
| 4494 | format-example | FR-058 | `)  # FR-058: shape the tier + oracle, not the sign-off` |
| 4496 | comment | GITX-FR-007 | `# The pre-stage git hook's clean-start guard (GITX-FR-007), BEFORE any side effect: a` |
| 4499 | comment | GITX-NFR-003 | `# (GITX-NFR-003).` |
| 4504 | comment | SRCX-FR-008 | `# Bind the run's feature folder (SRCX-FR-008/011): an explicit --spec names it; otherwise a` |
| 4522 | comment | RUNID-FR-001 | `# The workspace's NNN is the run's real identity (RUNID-FR-001): derived once here,` |
| 4526 | comment | RUNID-FR-003 | `# (RUNID-FR-003). An explicit --spec-id always wins (RUNID-FR-002).` |
| 4526 | comment | RUNID-FR-002 | `# (RUNID-FR-003). An explicit --spec-id always wins (RUNID-FR-002).` |
| 4530 | comment | PROGFILE-FR-001 | `# The run's human-readable progress file (PROGFILE-FR-001): bound to the allocated` |
| 4540 | comment | GITX-FR-003 | `# stage commit (GITX-FR-003/006): the branch name reuses SRCX's <NNN>-<slug> identity` |
| 4558 | comment | GITX-FR-005 | `# The additive branch binding on the existing run/start payload (GITX-FR-005): a later` |
| 4560 | comment | GITX-NFR-002 | `# guessing; no new entry type and no signing change (GITX-NFR-002).` |
| 4563 | comment | SRCX-FR-011 | `# The additive folder binding on the existing run/start payload (SRCX-FR-011): a later` |
| 4564 | comment | SRCX-NFR-002 | `# resume reads it back from the signed ledger alone — no mtime scan (SRCX-NFR-002).` |
| 4581 | format-example | FR-006 | `print("  " + rst.dim("you still approve the spec — FR-006"))` |
| 4589 | comment | STEER-FR-012 | `# shows its heartbeat from the first moment (STEER-FR-012/013). No-op off-TTY/degraded.` |
| 4634 | comment | AUTOX-FR-009 | `# Paused-at-gate is distinguishable from completed by exit code alone (AUTOX-FR-009).` |
| 4640 | comment | STEER-FR-005 | `)  # the three actions, on-screen at the interactive pause too (STEER-FR-005)` |
| 4645 | comment | STEER-FR-005 | `# Revise-with-message, inline (STEER-FR-005/006): take the feedback here, re-run the` |
| 4688 | comment | RUNX-FR-004 | `)  # provenance for the next segment (no re-record — RUNX-FR-004, RUNLIVE-FR-010)` |
| 4688 | comment | RUNLIVE-FR-010 | `)  # provenance for the next segment (no re-record — RUNX-FR-004, RUNLIVE-FR-010)` |
| 4691 | comment | STEER-FR-012 | `# screen immediately (STEER-FR-012/013).` |
| 4699 | comment | STEER-FR-016 | `# restored, on normal exit, interruption, and failure alike (STEER-FR-016, STEER-NFR-004).` |
| 4699 | comment | STEER-NFR-004 | `# restored, on normal exit, interruption, and failure alike (STEER-FR-016, STEER-NFR-004).` |
| 4705 | comment | AUTOX-FR-006 | `# (AUTOX-FR-006), so `--status`/`3pwr status` can say "failed at <stage> (<class>)"` |
| 4706 | comment | AUTOX-FR-007 | `# afterwards (AUTOX-FR-007). Attempts come from the failing stage's dispatch result.` |
| 4725 | comment | RUNX-FR-011 | `# A real deterministic-gate verdict failed at Verify (RUNX-FR-011): report gate-red,` |
| 4751 | comment | EXEC-FR-016 | `# setup problem, never a false gate-red (EXEC-FR-016).` |
| 4779 | comment | RUNLIVE-FR-002 | `# A stage produced no declared artifact (RUNLIVE-FR-002): distinct from a gate-red and from a` |
| 4781 | comment | RUNLIVE-FR-010 | `# resume pick up here without re-running completed stages (RUNLIVE-FR-010).` |
| 4811 | comment | GITX-FR-001 | `# The mandatory git hook could not hold its guarantee (GITX-FR-001/008/010): the stage` |
| 4813 | comment | GITX-NFR-003 | `# GITX-NFR-003). Named, recorded, and exiting on the setup/dispatch path — never a` |
| 4843 | comment | SRCX-FR-012 | `# The deterministic stage-completion gate blocked the run (SRCX-FR-012/014/015): the` |
| 4845 | comment | SRCX-FR-016 | `# named class is recorded (SRCX-FR-016) and surfaced by both status commands; the stage` |
| 4873 | comment | RUNX-FR-010 | `# A dispatch/execution failure — NOT a gate verdict (RUNX-FR-010): name the stage, never say` |
| 4925 | docstring | 3PWR-FR-070 | `"""Reverse to a prior recorded state via a signed reversal entry (3PWR-FR-070)."""` |
| 4969 | docstring | 3PWR-FR-019 | `"""Record an abort for a spec's run (3PWR-FR-019)."""` |
| 4995 | docstring | 3PWR-FR-015 | `"""Two-way requirement<->task coverage before code (3PWR-FR-015)."""` |
| 5023 | docstring | 3PWR-FR-016 | `"""Task requirement-ID + file-scope discipline (3PWR-FR-016/017)."""` |
| 5041 | docstring | 3PWR-FR-066 | `"""Sign build provenance + SBOM for an artifact (3PWR-FR-066/068)."""` |
| 5087 | docstring | 3PWR-FR-067 | `"""Verify an artifact's provenance; refuse if missing or invalid (3PWR-FR-067)."""` |
| 5135 | docstring | 3PWR-FR-036 | `"""Record a signed residual review (3PWR-FR-036/037)."""` |
| 5164 | docstring | 3PWR-FR-053 | `"""Reconstruct a spec + characterization tests for a legacy module (3PWR-FR-053)."""` |
| 5228 | docstring | 3PWR-FR-050 | `"""Run the prompt/constitution eval set; block on regression (3PWR-FR-050)."""` |
| 5254 | docstring | 3PWR-FR-048 | `"""Probe installed third-party versions against the supported ranges (3PWR-FR-048/NFR-014).` |
| 5254 | format-example | NFR-014 | `"""Probe installed third-party versions against the supported ranges (3PWR-FR-048/NFR-014).` |
| 5257 | docstring | 3PWR-NFR-001 | `keeping them out of the verdict preserves determinism (3PWR-NFR-001)."""` |
| 5312 | docstring | AUTOX-FR-003 | `"""Standalone, re-runnable auto-run readiness (AUTOX-FR-003): the full ``3pwr run --mode auto``` |
| 5313 | docstring | AUTOX-FR-002 | `preflight — the SAME shared check set init and the run itself use (AUTOX-FR-002) — plus a` |
| 5314 | docstring | 3PWR-FR-048 | `dependency summary (3PWR-FR-048), with one overall ready/not-ready verdict and a per-item fix.` |
| 5316 | docstring | AUTOX-NFR-001 | `Read-only and fully offline (AUTOX-NFR-001): it probes config, PATH, and the key custody chain,` |
| 5331 | comment | 3PWR-FR-048 | `# Dependency summary (3PWR-FR-048) — informational; never flips the readiness verdict (never a gate).` |

## engine/src/threepowers/completion.py (32)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | SRCX-NFR-005 | `Two SRCX concerns live here, both pure given injected inputs (SRCX-NFR-005):` |
| 5 | docstring | SRCX-FR-005 | `* **Stage records** (SRCX-FR-005/006): the two producing stages whose real outputs live elsewhere in` |
| 11 | docstring | SRCX-FR-012 | `* **The completion gate** (SRCX-FR-012..018): a producing stage is *done* only when BOTH its declared` |
| 16 | docstring | SRCX-FR-017 | `(SRCX-FR-017): a resume re-enters at the earliest recorded producing stage whose artifact is broken,` |
| 20 | docstring | SRCX-NFR-001 | `call, no network (SRCX-NFR-001, 3PWR-NFR-001). The ledger entries are read once by the caller and` |
| 20 | docstring | 3PWR-NFR-001 | `call, no network (SRCX-NFR-001, 3PWR-NFR-001). The ledger entries are read once by the caller and` |
| 21 | docstring | SRCX-NFR-004 | `injected (SRCX-NFR-004); nothing here appends to or signs the ledger — no new entry type, no signing` |
| 22 | docstring | SRCX-NFR-002 | `change (SRCX-NFR-002).` |
| 34 | comment | SRCX-FR-014 | `# The two named completion-gate failure classes (SRCX-FR-014/015) — new VALUES folding through the` |
| 39 | comment | SRCX-FR-005 | `# The producing steps whose feature-folder markdown is an engine-written *record* (SRCX-FR-005).` |
| 45 | docstring | SRCX-FR-012 | `"""One stage's completion-gate verdict (SRCX-FR-012) — pure given its inputs (SRCX-NFR-005)."""` |
| 45 | docstring | SRCX-NFR-005 | `"""One stage's completion-gate verdict (SRCX-FR-012) — pure given its inputs (SRCX-NFR-005)."""` |
| 54 | docstring | SRCX-FR-014 | `"""The actionable failure line naming the stage and the artifact (SRCX-FR-014/015)."""` |
| 69 | docstring | SRCX-FR-007 | `"""Whether ``step`` is gated at all (SRCX-FR-007/018): only the producing steps carry the gate."""` |
| 74 | docstring | SRCX-NFR-004 | `"""The artifact paths recorded per completed step — one pass over the ledger (SRCX-NFR-004).` |
| 77 | docstring | SRCX-FR-013 | `(SRCX-FR-013); its ``artifacts`` list accumulates per step (a re-run's fresh entry adds to the` |
| 95 | docstring | SRCX-FR-013 | `"""The declared artifact's repo-relative POSIX path and whether it exists on disk (SRCX-FR-013).` |
| 98 | docstring | SRCX-FR-003 | `(SRCX-FR-003) — so an already-written split artifact is checked *at its split path* while a new` |
| 112 | docstring | SRCX-FR-012 | `"""The deterministic completion check for one producing step (SRCX-FR-012..015).` |
| 115 | docstring | SRCX-FR-007 | `(compared as a repo-relative POSIX path). A non-producing step always passes (SRCX-FR-007)."""` |
| 134 | docstring | SRCX-FR-017 | `"""Cap a resume's re-entry index by the on-disk completion check (SRCX-FR-017).` |
| 139 | docstring | SRCX-FR-018 | `Stages the run never recorded are out of the gate's scope (SRCX-FR-018). Returns the (possibly` |
| 143 | comment | SRCX-NFR-004 | `recorded = recorded_stage_artifacts(entries, spec_id)  # one ledger pass (SRCX-NFR-004)` |
| 153 | comment | SRCX-FR-005 | `# --------------------------------------------------------------------------- stage records (SRCX-FR-005/006)` |
| 155 | docstring | SRCX-FR-005 | `"""The ``oracle.md`` record — links the authored oracle tests at their real repo paths (SRCX-FR-005)."""` |
| 175 | docstring | SRCX-FR-006 | `"""The single ``implement.md`` record — every phase, every change, deterministic order (SRCX-FR-006).` |
| 177 | docstring | PHASE-FR-012 | ```phases`` are the per-phase results in artifact order (as collected — PHASE-FR-012); each phase` |
| 179 | docstring | SRCX-FR-005 | `set is always listed, so the record links a superset of the stage's change set (SRCX-FR-005)."""` |
| 191 | comment | SRCX-FR-006 | `for ph in phases:  # deterministic artifact order, as collected (SRCX-FR-006)` |
| 218 | docstring | SRCX-FR-004 | `"""Write the ``oracle.md`` / ``implement.md`` record flat into the feature folder (SRCX-FR-004/005).` |
| 221 | docstring | SRCX-FR-013 | `the signed ``run``/``stage`` entry records it (SRCX-FR-013) and the completion gate can hold. For a` |
| 223 | docstring | SRCX-NFR-006 | `deterministic order (SRCX-NFR-006)."""` |

## engine/src/threepowers/config.py (35)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | docstring | 3PWR-FR-032 | `spend) is read from one risk-tier table (3PWR-FR-032/049). Roles are bound to model` |
| 6 | docstring | 3PWR-FR-022 | `(3PWR-FR-022/044).` |
| 38 | docstring | 3PWR-FR-021 | `"""The distinct judiciary (oracle) public key, if one was minted (3PWR-FR-021/039)."""` |
| 63 | docstring | EXEC-FR-002 | `"""Declarative agent-backend manifests for the native executive (EXEC-FR-002)."""` |
| 68 | docstring | ONBRD-FR-005 | `"""Advisory onboarding preferences written by ``3pwr init`` (3PWR-ONBRD-FR-005)."""` |
| 73 | docstring | PHASE-FR-007 | `"""The advisory per-model context-budget configuration (PHASE-FR-007)."""` |
| 78 | docstring | CLIUX-FR-014 | `"""Optional human-output preferences — color mode, verbosity, layout (CLIUX-FR-014).` |
| 81 | docstring | CLIUX-FR-015 | `back to the shipped defaults, so its absence changes nothing (CLIUX-FR-015)."""` |
| 86 | docstring | GITX-FR-015 | `"""The git-integration preferences — branch prefix, base branch, 3pwr author (GITX-FR-015).` |
| 94 | docstring | STEER-FR-010 | `"""The opt-in notification channels for a paused/failed/completed run (STEER-FR-010).` |
| 96 | docstring | STEER-NFR-001 | `Convenience only — never a trust or enforcement channel (STEER-NFR-001): a missing file` |
| 98 | docstring | STEER-NFR-002 | `:mod:`threepowers.notify`). Secrets are referenced from the environment (STEER-NFR-002)."""` |
| 103 | docstring | PHASE-FR-008 | `"""The project constitution — part of every phase's reload set (PHASE-FR-008)."""` |
| 108 | docstring | AGENTX-FR-001 | `"""The per-stage agent templates — one editable markdown per dispatched stage (AGENTX-FR-001).` |
| 112 | docstring | AGENTX-FR-005 | `the engine's built-in instruction (AGENTX-FR-005)."""` |
| 117 | docstring | AGENTX-FR-015 | `"""The per-integration model/label catalog — editable data, not code (AGENTX-FR-015/016).` |
| 124 | docstring | PHASE-FR-007 | `"""The advisory context budget in tokens for ``model`` (PHASE-FR-007).` |
| 129 | docstring | PHASE-FR-009 | `split, never a failed gate (PHASE-FR-009, PHASE-NFR-002)."""` |
| 129 | docstring | PHASE-NFR-002 | `split, never a failed gate (PHASE-FR-009, PHASE-NFR-002)."""` |
| 146 | docstring | ONBRD-FR-005 | `"""The recorded ``3pwr run`` autonomy default (advisory — ONBRD-FR-005): ``auto`` \| ``commit``.` |
| 149 | docstring | ONBRD-NFR-004 | `mode when ``--mode`` is omitted and never suppresses a mandatory human gate (ONBRD-NFR-004)."""` |
| 156 | docstring | INITX-FR-006 | `"""Whether per-stage auto-commit is enabled (INITX-FR-006). Defaults to True (the wanted workflow).` |
| 163 | docstring | RUNLIVE-FR-004 | `"""The per-stage dispatch timeout in seconds (RUNLIVE-FR-004). Defaults to 1800 (30 min).` |
| 177 | docstring | RUNLIVE-FR-005 | `"""How many times a *failed* dispatch is retried before the stage is reported failed (RUNLIVE-FR-005).` |
| 191 | docstring | INITX-FR-001 | `"""The recorded default risk tier a new spec starts at (advisory — INITX-FR-001).` |
| 194 | docstring | INITX-NFR-002 | `threshold or removes a gate (INITX-NFR-002); it seeds the tier a fresh spec is authored at."""` |
| 201 | docstring | CLIUX-FR-014 | `"""Resolved UI preferences from ``ui.yaml`` + whether the file was malformed (CLIUX-FR-014/015).` |
| 206 | docstring | CLIUX-FR-015 | `(CLIUX-FR-015). Deterministic and pure in the file bytes. Only recognized keys/values are` |
| 237 | docstring | CLIUX-FR-014 | `"""The resolved UI preferences (CLIUX-FR-014); shorthand for ``load_ui()[0]``."""` |
| 247 | docstring | 3PWR-FR-021 | `"""Policy: require an isolated headless-dispatch attestation at High-risk (3PWR-FR-021/A3).` |
| 256 | docstring | 3PWR-FR-022 | `"""How strictly model diversity is compared (3PWR-FR-022): ``family`` (default) or ``model``.` |
| 275 | docstring | AGENTX-FR-012 | `does not encode (AGENTX-FR-012/015)."""` |
| 282 | docstring | INITX-FR-003 | `"""The concrete model pin for a role — ``{model, integration, label}`` — or ``None`` (INITX-FR-003).` |
| 286 | docstring | INITX-FR-004 | `falls back to the model id, so a pin always renders as ``<label> (<integration>)`` (INITX-FR-004)."""` |
| 325 | docstring | 3PWR-FR-022 | `"""True iff two roles are *diverse enough* at ``level`` (3PWR-FR-022).` |

## engine/src/threepowers/conformance.py (33)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-030 | `"""Spec-conformance gate — every requirement must have a linked test (3PWR-FR-030).` |
| 3 | docstring | 3PWR-FR-028 | `This is a deterministic, language-agnostic trace (3PWR-FR-028): we read the` |
| 5 | docstring | 3PWR-FR-064 | `test, across the unit / integration / e2e layers (3PWR-FR-064/065). A requirement` |
| 7 | docstring | 3PWR-FR-034 | `(3PWR-FR-034).` |
| 9 | docstring | HARDN-FR-008 | `Anti-gaming (HARDN-FR-008/009): a requirement counts as *traced* only when its ID is` |
| 14 | docstring | 3PWR-NFR-015 | `failure or a silent pass (3PWR-NFR-015, HARDN-NFR-003). One read per file — the binding` |
| 14 | docstring | HARDN-NFR-003 | `failure or a silent pass (3PWR-NFR-015, HARDN-NFR-003). One read per file — the binding` |
| 15 | docstring | HARDN-NFR-002 | `and assertion checks ride the same scan pass (HARDN-NFR-002).` |
| 27 | comment | 3PWR-FR-059 | `# Canonical requirement ID, namespaced by spec ID (3PWR-FR-059): e.g. VUTIL-FR-001 or` |
| 27 | comment | VUTIL-FR-001 | `# Canonical requirement ID, namespaced by spec ID (3PWR-FR-059): e.g. VUTIL-FR-001 or` |
| 28 | comment | 3PWR-FR-038 | `# 3PWR-FR-038. The spec ID may start with a digit (the 3Powers epic id is "3PWR"). The` |
| 36 | docstring | 3PWR-FR-038 | `slash-runs such as ``3PWR-FR-038/039/040`` into 038, 039, 040."""` |
| 54 | docstring | 3PWR-FR-052 | `Tolerates ``None`` (a brownfield report-only run with no spec yet, 3PWR-FR-052): yields` |
| 109 | comment | HARDN-FR-008 | `# ------------------------------------------------------------- declaration binding (HARDN-FR-008/009)` |
| 116 | docstring | HARDN-NFR-002 | `"""What one scan pass over the test files found (one read per file, HARDN-NFR-002)."""` |
| 139 | docstring | HARDN-FR-008 | `"""The exclusive end of a declaration's *binding region* (HARDN-FR-008).` |
| 171 | docstring | HARDN-FR-008 | `"""Parse one test file into declaration blocks (HARDN-FR-008/009).` |
| 253 | docstring | HARDN-FR-008 | `# Anti-gaming path (HARDN-FR-008/009): only declaration-bound IDs trace; a comment` |
| 264 | docstring | 3PWR-NFR-015 | `"is not enforced (3PWR-NFR-015)"` |
| 268 | docstring | HARDN-NFR-003 | `# degraded, never silently strict or silently passing (HARDN-NFR-003).` |
| 273 | docstring | 3PWR-NFR-015 | `"binding is not enforced (3PWR-NFR-015)"` |
| 277 | docstring | 3PWR-FR-064 | `# Per tier, the CHANGE must exercise all required test layers (3PWR-FR-064/065). We check the` |
| 291 | docstring | HARDN-FR-008 | `"a comment does not trace it (HARDN-FR-008)"` |
| 295 | docstring | HARDN-FR-009 | `f"requirement {rid} is bound to an assertion-free test in {f} (HARDN-FR-009)"` |
| 313 | docstring | RUNID-FR-004 | `# exercised (RUNID-FR-004). Empty exactly when nothing is referenced.` |
| 329 | docstring | 3PWR-FR-008 | `# A regression test names itself: a *regression* / *reproduce* file or body marker (3PWR-FR-008).` |
| 334 | docstring | 3PWR-FR-008 | `"""Detect a failing-regression test guarding a defect fix (3PWR-FR-008), deterministically.` |
| 338 | docstring | 3PWR-NFR-001 | `is traceable to the defect it guards (mirrors the conformance trace; no model call, 3PWR-NFR-001).` |
| 361 | docstring | 3PWR-FR-008 | `"""The defect-flow gate (3PWR-FR-008): a defect fix must ship a failing regression test."""` |
| 395 | docstring | HARDN-FR-008 | `"name/declaration line (HARDN-FR-008)",` |
| 404 | docstring | HARDN-FR-009 | `detail="requirement-bound test contains no assertion (HARDN-FR-009)",` |
| 418 | docstring | 3PWR-FR-016 | `# A task line in tasks.md carries a task id like T001 (3PWR-FR-016).` |
| 423 | docstring | 3PWR-FR-015 | `"""Verify two-way requirement↔task coverage before code (3PWR-FR-015).` |

## engine/src/threepowers/covdiff.py (3)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-029 | `"""Diff coverage — measure coverage on *changed* lines only (3PWR-FR-029).` |
| 3 | docstring | 3PWR-FR-028 | `This lives in the language-agnostic core (3PWR-FR-028): adapters merely emit a` |
| 84 | docstring | 3PWR-FR-051 | `capability area's files at its tier (spec §4) or to a brownfield diff (3PWR-FR-051).` |

## engine/src/threepowers/deps.py (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-048 | `"""Third-party dependency compatibility (3PWR-FR-048, 3PWR-NFR-014).` |
| 1 | docstring | 3PWR-NFR-014 | `"""Third-party dependency compatibility (3PWR-FR-048, 3PWR-NFR-014).` |
| 11 | docstring | 3PWR-NFR-001 | `so keeping them out of the verdict preserves determinism (3PWR-NFR-001) — the same reason the oracle's` |
| 12 | docstring | 3PWR-NFR-015 | `peek/touch signal is advisory. An absent tool is reported, like the scanner quarantine (3PWR-NFR-015),` |

## engine/src/threepowers/design.py (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-009 | `"""Design oracles — how *design* work is judged, beyond the code gates (3PWR-FR-009).` |
| 3 | docstring | 3PWR-FR-058 | `When work-kind inference (3PWR-FR-058) tags a change ``design``, the engine unions a set of` |
| 6 | docstring | 3PWR-NFR-007 | `core language-agnostic (3PWR-NFR-007). A selected oracle the adapter doesn't declare — or whose tool` |
| 8 | docstring | 3PWR-NFR-015 | `passed (3PWR-NFR-015).` |
| 27 | comment | 3PWR-NFR-015 | `# every oracle dimension (quarantined if unwired) rather than silently passing (3PWR-NFR-015).` |

## engine/src/threepowers/deviations.py (18)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-056 | `"""Emergency & deviation paths — bending the process without breaking it (3PWR-FR-056/057).` |
| 7 | docstring | 3PWR-NFR-001 | `run honestly, so the verdict stays deterministic (3PWR-NFR-001). A ``deviation`` is a` |
| 10 | docstring | 3PWR-FR-035 | `(3PWR-FR-035): a legitimate suppression is a recorded deviation, not an absorbed one.` |
| 12 | docstring | 3PWR-FR-057 | `* **Deviation (3PWR-FR-057):** relaxes named gates with a reason, a human approver, and a` |
| 14 | docstring | 3PWR-FR-056 | `* **Emergency (3PWR-FR-056):** a constrained profile that may defer only **mutation** and` |
| 19 | docstring | 3PWR-FR-056 | `that ``advance`` / ``deploy-gate`` always require (3PWR-FR-056).` |
| 27 | comment | 3PWR-FR-057 | `# A named non-gate requirement a deviation MAY relax (3PWR-FR-057): model diversity (FR-022) is` |
| 27 | format-example | FR-022 | `# A named non-gate requirement a deviation MAY relax (3PWR-FR-057): model diversity (FR-022) is` |
| 29 | comment | GITX-FR-014 | `# The GITX git-discipline guards (GITX-FR-014) relax the same way: the clean-start guard, the` |
| 43 | comment | 3PWR-FR-056 | `# Gates an emergency fast path MAY defer (3PWR-FR-056).` |
| 47 | comment | 3PWR-FR-056 | `# Default cleanup window for an emergency: one working day (3PWR-FR-056).` |
| 70 | docstring | 3PWR-FR-056 | `"""Build the constrained emergency-deviation payload (3PWR-FR-056)."""` |
| 85 | docstring | 3PWR-FR-057 | `"""Build a general deviation payload (3PWR-FR-057)."""` |
| 100 | docstring | 3PWR-FR-057 | `"""Currently-active deviations: not expired and not revoked by a later entry (3PWR-FR-057)."""` |
| 137 | docstring | 3PWR-FR-022 | `None. Model diversity (3PWR-FR-022) is recommended; a same-family setup needs a signed deviation."""` |
| 148 | docstring | 3PWR-FR-022 | `"""True iff an active deviation relaxes model diversity (3PWR-FR-022 via FR-057)."""` |
| 148 | format-example | FR-057 | `"""True iff an active deviation relaxes model diversity (3PWR-FR-022 via FR-057)."""` |
| 155 | docstring | 3PWR-FR-056 | `"""Active emergency deviations whose one-day cleanup deadline has passed (3PWR-FR-056)."""` |

## engine/src/threepowers/evals.py (1)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-050 | `"""Prompt/constitution evaluation harness (3PWR-FR-050).` |

## engine/src/threepowers/frame.py (50)

| line | kind | match | excerpt |
|---|---|---|---|
| 6 | docstring | STEER-FR-012 | `(STEER-FR-012): the eight lifecycle stages with done / current / upcoming marks, the active step, a` |
| 7 | docstring | STEER-FR-013 | `heartbeat spinner with the elapsed time (STEER-FR-013), and the gate guidance stay painted on the` |
| 11 | docstring | TRIX-FR-003 | `The rendering engine is ``rich`` (TRIX-FR-003/004): :class:`LiveFrame` wraps a non-highlighting` |
| 14 | docstring | TRIX-FR-008 | `(TRIX-FR-008) — and **no alternate screen buffer and no scroll region** are ever used, preserving` |
| 16 | docstring | STEER-NFR-003 | `and the styler (STEER-NFR-003): identical inputs yield identical text; the heartbeat is a` |
| 19 | docstring | STEER-FR-015 | `Degradation is total and safe (STEER-FR-015, STEER-NFR-004, TRIX-FR-007): off a TTY, under` |
| 19 | docstring | STEER-NFR-004 | `Degradation is total and safe (STEER-FR-015, STEER-NFR-004, TRIX-FR-007): off a TTY, under` |
| 19 | docstring | TRIX-FR-007 | `Degradation is total and safe (STEER-FR-015, STEER-NFR-004, TRIX-FR-007): off a TTY, under` |
| 22 | docstring | STEER-FR-016 | `always restores the cursor and leaves the bar's last state as ordinary lines (STEER-FR-016).` |
| 45 | comment | STEER-FR-015 | `# Below this the terminal "cannot support the live bar" and the plain log applies (STEER-FR-015).` |
| 60 | docstring | STEER-FR-013 | `"""The heartbeat spinner's frame for ``index`` — pure and cyclic (STEER-FR-013)."""` |
| 75 | comment | TRIX-FR-008 | `# matchers only — never used to construct output (TRIX-FR-008).` |
| 82 | docstring | STEER-NFR-003 | `:func:`sanitize_line` applies between the SGR runs it preserves (STEER-NFR-003)."""` |
| 92 | docstring | STEER-FR-012 | `(STEER-FR-012/016, TRIX-FR-005). Pure (STEER-NFR-003)."""` |
| 92 | docstring | TRIX-FR-005 | `(STEER-FR-012/016, TRIX-FR-005). Pure (STEER-NFR-003)."""` |
| 92 | docstring | STEER-NFR-003 | `(STEER-FR-012/016, TRIX-FR-005). Pure (STEER-NFR-003)."""` |
| 106 | docstring | STEER-NFR-003 | `"""What the pinned frame shows — a pure value the renderer maps to bytes (STEER-NFR-003)."""` |
| 116 | docstring | STEER-FR-012 | `(STEER-FR-012's property): stages before it are done, the reached one current, the rest upcoming."""` |
| 127 | docstring | STEER-FR-013 | `"""Fold one streamed run event into the frame state (pure — STEER-FR-013).` |
| 146 | comment | STEER-FR-005 | `# (STEER-FR-005); the frame names the three actions at a glance (STEER-FR-013).` |
| 146 | comment | STEER-FR-013 | `# (STEER-FR-005); the frame names the three actions at a glance (STEER-FR-013).` |
| 208 | docstring | STEER-NFR-003 | `"""Render the live bar — exactly ``BAR_HEIGHT`` lines, pure in its inputs (STEER-NFR-003).` |
| 210 | docstring | STEER-FR-013 | ```spinner``/``elapsed`` decorate the running status line (the heartbeat, STEER-FR-013); left` |
| 262 | docstring | STEER-FR-015 | `"""Whether ``stream``'s terminal can carry the live bar (STEER-FR-015).` |
| 266 | docstring | STEER-NFR-004 | `(STEER-NFR-004)."""` |
| 284 | docstring | STEER-FR-012 | `"""The bottom-anchored live bar on one terminal stream (STEER-FR-012..016, TRIX-FR-003/004).` |
| 284 | docstring | TRIX-FR-003 | `"""The bottom-anchored live bar on one terminal stream (STEER-FR-012..016, TRIX-FR-003/004).` |
| 294 | docstring | STEER-NFR-004 | `so exception paths and normal exits converge (STEER-NFR-004). One re-entrant lock serializes` |
| 297 | docstring | STEER-FR-012 | `out of a partial region, which is exactly the history loss this design replaces (STEER-FR-012).` |
| 298 | docstring | STEER-FR-016 | `A ``SIGWINCH`` re-lays the bar out (STEER-FR-016)."""` |
| 330 | docstring | TRIX-FR-004 | `"""Start the live display — the bar appears at the bottom, cursor hidden (TRIX-FR-004)."""` |
| 342 | comment | TRIX-FR-005 | `# through unmodified (TRIX-FR-005), and rich owns every escape byte (TRIX-FR-008).` |
| 342 | comment | TRIX-FR-008 | `# through unmodified (TRIX-FR-005), and rich owns every escape byte (TRIX-FR-008).` |
| 351 | comment | STEER-FR-013 | `# the frame's own ticker drives the heartbeat cadence (STEER-FR-013).` |
| 357 | comment | STEER-NFR-004 | `pass  # never let the bar take the run down (STEER-NFR-004)` |
| 363 | docstring | STEER-FR-016 | `always safe to call twice (STEER-FR-016, STEER-NFR-004)."""` |
| 363 | docstring | STEER-NFR-004 | `always safe to call twice (STEER-FR-016, STEER-NFR-004)."""` |
| 372 | comment | STEER-NFR-004 | `pass  # a vanished stream must not raise on teardown (STEER-NFR-004)` |
| 382 | docstring | STEER-FR-013 | `"""Fold one streamed event into the frame and repaint (STEER-FR-013). Opens lazily."""` |
| 403 | docstring | STEER-FR-012 | `"""Print content ABOVE the bar, into the terminal's ordinary flow (STEER-FR-012).` |
| 407 | docstring | TRIX-FR-004 | `(TRIX-FR-004/005). Thread-safe: the runner's pump threads and the event thread share the` |
| 415 | comment | TRIX-FR-005 | `# never reformats the content (TRIX-FR-005); the explicit refresh flushes the` |
| 423 | comment | STEER-NFR-004 | `pass  # never let output routing take the run down (STEER-NFR-004)` |
| 426 | docstring | STEER-FR-013 | `"""Advance the running spinner one frame and repaint (STEER-FR-013) — driven by the` |
| 435 | docstring | RUNID-FR-003 | `"""Adopt a late-resolved run identity as the bar's title subject (RUNID-FR-003).` |
| 466 | comment | STEER-NFR-004 | `pass  # never let a repaint take the run down (STEER-NFR-004)` |
| 469 | docstring | STEER-FR-016 | `"""Re-lay the bar out after a terminal resize (STEER-FR-016)."""` |
| 530 | docstring | STEER-FR-015 | `"""A :class:`LiveFrame` when the terminal supports the live bar, else ``None`` (STEER-FR-015).` |
| 532 | docstring | STEER-FR-013 | `The production path gets the heartbeat ticker (STEER-FR-013); tests constructing` |
| 533 | docstring | STEER-NFR-003 | `:class:`LiveFrame` directly stay tick-free and deterministic (STEER-NFR-003)."""` |

## engine/src/threepowers/gaming.py (6)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-035 | `"""Gate-gaming detection — a language-agnostic core gate (3PWR-FR-035).` |
| 5 | docstring | HARDN-FR-010 | `**assertion-free tests that reference requirement IDs** (HARDN-FR-010), the move that` |
| 7 | format-example | FR-057 | `never a silent pass. Accepting a legitimate suppression is a *deviation* (FR-057),` |
| 31 | comment | HARDN-FR-010 | `# requirement-referencing test is a gaming signal (HARDN-FR-010). Language-agnostic union.` |
| 103 | docstring | HARDN-FR-010 | `"""Newly added assertion-free tests that reference a requirement ID (HARDN-FR-010).` |
| 144 | comment | HARDN-FR-010 | `# An untracked file is all added lines — same weak-test scan (HARDN-FR-010).` |

## engine/src/threepowers/gates.py (60)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-026 | `"""The deterministic gate engine — runs the suite cheapest-first (3PWR-FR-026).` |
| 5 | docstring | 3PWR-FR-032 | `risk-tier table (3PWR-FR-032/049): a gate is never satisfied by weakening it. The` |
| 6 | docstring | 3PWR-FR-033 | `result is one normalized verdict (3PWR-FR-033) whose every failure is actionable` |
| 7 | docstring | 3PWR-FR-034 | `(3PWR-FR-034).` |
| 32 | comment | 3PWR-FR-009 | `# Design-oracle gate → its actionable failure class (3PWR-FR-009/034).` |
| 52 | comment | GATEPIPE-FR-001 | `# Best-effort start-time tool labels for the core-computed gates (GATEPIPE-FR-001). The finish` |
| 68 | docstring | GATEPIPE-FR-001 | `"""The gate engine's start/finish event seam (GATEPIPE-FR-001).` |
| 73 | docstring | GATEPIPE-NFR-001 | `computation (GATEPIPE-NFR-001, 3PWR-NFR-001)."""` |
| 73 | docstring | 3PWR-NFR-001 | `computation (GATEPIPE-NFR-001, 3PWR-NFR-001)."""` |
| 83 | docstring | GATEPIPE-FR-001 | `"""The best-effort tool label for a gate's start event (GATEPIPE-FR-001).` |
| 134 | docstring | 3PWR-FR-034 | `Turns raw toolchain noise into a fix the user can act on (3PWR-FR-034); only fires for a gate that` |
| 159 | comment | GATEPIPE-FR-003 | `# Surface the configured manual fix in the failure panel (GATEPIPE-FR-003).` |
| 181 | docstring | GATECFG-FR-008 | `"""A ``{path: sha256}`` snapshot of the modified/untracked files under ``cwd`` (GATECFG-FR-008).` |
| 184 | docstring | GITX-FR-008 | `join the run's produced set and ride the stage commit (ref GITX-FR-008). Degrades to ``{}``` |
| 223 | docstring | GATECFG-FR-008 | `"""Run the gate's configured ``fix_cmd`` and re-check, opt-in only (GATECFG-FR-008).` |
| 225 | docstring | GATECFG-FR-006 | `Only a fixable gate (format/lint — GATECFG-FR-006) with a failing check and a configured fix` |
| 244 | docstring | GATECFG-FR-008 | `"""Every path an ``--auto-fix`` run fixed, from a verdict dict (GATECFG-FR-008).` |
| 247 | docstring | GITX-FR-008 | `to the run's produced set so the stage commit picks them up (ref GITX-FR-008)."""` |
| 272 | docstring | HARDN-FR-011 | `"""Changed *source* files to mutate under diff-scoped mutation (HARDN-FR-011).` |
| 285 | docstring | 3PWR-FR-058 | `"""Union the gates an inferred work-kind pulls in onto the tier's list (3PWR-FR-058).` |
| 287 | docstring | 3PWR-FR-008 | `Only ever *adds* — a defect adds the regression gate (3PWR-FR-008), design work adds the` |
| 288 | docstring | 3PWR-FR-009 | `catalog's design oracles (3PWR-FR-009). A tier gate is never removed (3PWR-FR-032).` |
| 288 | docstring | 3PWR-FR-032 | `catalog's design oracles (3PWR-FR-009). A tier gate is never removed (3PWR-FR-032).` |
| 304 | docstring | 3PWR-FR-051 | `(3PWR-FR-051/052). Reported as skipped, never silently passed (3PWR-FR-032)."""` |
| 304 | docstring | 3PWR-FR-032 | `(3PWR-FR-051/052). Reported as skipped, never silently passed (3PWR-FR-032)."""` |
| 313 | docstring | GDIAG-FR-004 | `"""A required tool of a non-optional gate is absent — raised BEFORE any gate runs (GDIAG-FR-004).` |
| 317 | docstring | GDIAG-NFR-002 | `declarative ``toolchain:`` section — the core never invents a hint (GDIAG-NFR-002). The caller` |
| 334 | docstring | GDIAG-FR-004 | `"""The ``(tool, install_hint)`` pairs missing for the run's NON-OPTIONAL gates (GDIAG-FR-004/005).` |
| 339 | docstring | 3PWR-NFR-015 | `and the design oracles (quarantined when their tool is absent — 3PWR-NFR-015). ``tests`` is` |
| 377 | docstring | 3PWR-FR-026 | `"""Run the tier's gate suite cheapest-first and return the one normalized verdict (3PWR-FR-026/033).` |
| 381 | docstring | GATEPIPE-FR-001 | `(GATEPIPE-FR-001). It is presentation-only and never enters the verdict (GATEPIPE-NFR-001).` |
| 381 | docstring | GATEPIPE-NFR-001 | `(GATEPIPE-FR-001). It is presentation-only and never enters the verdict (GATEPIPE-NFR-001).` |
| 382 | docstring | GATECFG-FR-007 | ```auto_fix`` (opt-in only — GATECFG-FR-007) lets a failing format/lint check run its` |
| 383 | docstring | GATECFG-FR-008 | `configured ``fix_cmd`` and re-check (GATECFG-FR-008); no other gate ever runs a fix` |
| 384 | docstring | GATECFG-FR-006 | `(GATECFG-FR-006). ``manifest``, when given, is the caller-assembled effective gate` |
| 385 | docstring | GATECFG-FR-003 | `configuration (``gates.yaml`` overrides + auto-detection — GATECFG-FR-003, via` |
| 387 | docstring | GATECFG-FR-001 | ```gates.yaml`` merged (GATECFG-FR-001). Raises :class:`PrerequisiteError` before any gate runs` |
| 388 | docstring | GDIAG-FR-004 | `when a required tool of a non-optional gate is absent (GDIAG-FR-004); a ``report_only`` run` |
| 393 | comment | 3PWR-FR-058 | `# Work-kind shaping (3PWR-FR-058): an inferred kind can *add* gates — a regression gate for a` |
| 394 | comment | 3PWR-FR-008 | `# defect (3PWR-FR-008), the design oracles for design work (3PWR-FR-009) — but never removes a` |
| 394 | comment | 3PWR-FR-009 | `# defect (3PWR-FR-008), the design oracles for design work (3PWR-FR-009) — but never removes a` |
| 395 | comment | 3PWR-FR-032 | `# tier gate (inference shapes, never weakens; 3PWR-FR-032).` |
| 399 | comment | HARDN-FR-011 | `# Opt-in diff-scoped mutation (HARDN-FR-011): a tier configured with `diff_mutation: true`` |
| 402 | comment | 3PWR-FR-032 | `# (3PWR-FR-032); with the knob unset, behavior is unchanged.` |
| 407 | comment | 3PWR-FR-051 | `# Brownfield diff-scope: block only on new/changed files (3PWR-FR-051). When set,` |
| 420 | comment | GDIAG-FR-004 | `# Prerequisites pre-check (GDIAG-FR-004/005): every required tool of a non-optional gate is` |
| 430 | comment | 3PWR-FR-051 | `# Brownfield adoption (3PWR-FR-051/052): report-only / diff-scope runs before a repo has any` |
| 443 | docstring | GATEPIPE-FR-001 | `"""Record ``gr`` on the verdict and fire the observer's finish event (GATEPIPE-FR-001)."""` |
| 456 | comment | GATEPIPE-FR-001 | `# The start event precedes the gate's own execution (GATEPIPE-FR-001) — the live pipeline` |
| 475 | comment | 3PWR-NFR-002 | `# (3PWR-NFR-002). Reported as skipped, never silently passed.` |
| 487 | comment | HARDN-FR-011 | `# Scope to the changed source files (HARDN-FR-011); the tier's` |
| 488 | comment | 3PWR-FR-032 | `# mutation_score stays the single source of the threshold (3PWR-FR-032).` |
| 522 | comment | GATECFG-FR-008 | `# Opt-in auto-fix (GATECFG-FR-008): fix, re-check; a green re-check passes the` |
| 524 | comment | GATECFG-FR-006 | `# (GATECFG-FR-006) and never without --auto-fix (GATECFG-FR-007/009).` |
| 524 | comment | GATECFG-FR-007 | `# (GATECFG-FR-006) and never without --auto-fix (GATECFG-FR-007/009).` |
| 535 | comment | SLOCK-FR-003 | `# (SLOCK-FR-003/004). Skips (never blocks) a not-yet-approved spec.` |
| 580 | comment | 3PWR-FR-008 | `# Work-kind: defect — a fix must ship a failing regression test (3PWR-FR-008).` |
| 587 | comment | 3PWR-FR-009 | `# Work-kind: design — adapter-supplied design oracle, quarantined if unwired (3PWR-FR-009).` |
| 600 | comment | 3PWR-FR-034 | `# Actionable failures for any failed gate (3PWR-FR-034).` |
| 716 | comment | 3PWR-FR-051 | `# When --paths is given, scope coverage to those files only (spec §4 / 3PWR-FR-051).` |

## engine/src/threepowers/gitflow.py (46)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | RUNLIVE-FR-010 | `GITX turns the executive from committing *opportunistically* (RUNLIVE-FR-010's opt-out checkpoint)` |
| 5 | docstring | GITX-FR-003 | `already-allocated ``<NNN>-<slug>`` run identity (GITX-FR-003 — the identity is consumed, never` |
| 7 | docstring | GITX-FR-007 | `the run's own (GITX-FR-007); each producing stage lands as **exactly one commit** staging only the` |
| 9 | docstring | GITX-FR-010 | `author identity** applied per-commit (GITX-FR-010/011/012).` |
| 12 | docstring | GITX-NFR-001 | `(GITX-NFR-001). The agent-written commit *message* is the only model-touched output and it is` |
| 14 | docstring | GITX-NFR-003 | `(GITX-NFR-003/004): branch switches and commits are **refused, never forced**; the user's git` |
| 17 | docstring | GITX-FR-014 | `relaxable only via a recorded signed deviation on a named guard (GITX-FR-014, 3PWR-FR-057).` |
| 17 | docstring | 3PWR-FR-057 | `relaxable only via a recorded signed deviation on a named guard (GITX-FR-014, 3PWR-FR-057).` |
| 32 | comment | GITX-FR-014 | `# The named guards a signed deviation may relax (GITX-FR-014): each relaxable guard maps to exactly` |
| 44 | comment | GITX-FR-015 | `# The documented `git.yaml` defaults (GITX-FR-015): a missing or malformed file falls back to these.` |
| 52 | comment | GITX-FR-007 | `# ignores the whole prefix (GITX-FR-007's property scopes the guard to work outside the run).` |
| 55 | comment | PROGFILE-FR-001 | `# The engine-written run progress file inside a feature workspace (PROGFILE-FR-001). A paused or` |
| 58 | comment | PROGFILE-NFR-002 | `# (PROGFILE-NFR-002).` |
| 61 | comment | GITX-FR-011 | `# Bound for the agent-written description folded into a commit subject (GITX-FR-011).` |
| 66 | comment | GITX-FR-015 | `# --------------------------------------------------------------------------- preferences (GITX-FR-015)` |
| 79 | docstring | GITX-FR-015 | `"""Resolve ``.3powers/config/git.yaml`` tolerantly (GITX-FR-015; mirrors ``ui.yaml``).` |
| 83 | docstring | GITX-NFR-001 | `identical inputs resolve identical branch names and author attribution (GITX-NFR-001)."""` |
| 108 | comment | GITX-FR-002 | `# --------------------------------------------------------------------------- precondition (GITX-FR-002)` |
| 112 | docstring | GITX-FR-002 | `A pure function of the environment/repository state (GITX-FR-002's property): git must be on` |
| 114 | docstring | GITX-NFR-001 | `worktree — on the path upward). No network, no model (GITX-NFR-001)."""` |
| 123 | comment | GITX-FR-003 | `# --------------------------------------------------------------------------- branch (GITX-FR-003/004/006)` |
| 125 | docstring | GITX-FR-003 | `"""The run's dedicated branch name — ``<prefix><NNN>-<slug>`` (GITX-FR-003).` |
| 128 | docstring | GITX-NFR-001 | `(GITX-NFR-001); GITX neither allocates the number nor derives the slug — that is SRCX's."""` |
| 151 | docstring | GITX-FR-004 | `An existing branch is re-entered (a resume never creates a second one — GITX-FR-004); a missing` |
| 154 | docstring | GITX-NFR-003 | `clobber changes) is surfaced, not overridden (GITX-NFR-003), and no history is rewritten` |
| 155 | docstring | GITX-NFR-004 | `(GITX-NFR-004)."""` |
| 167 | docstring | GITX-FR-005 | `"""The run's recorded branch, read back from the signed ``run``/``start`` entry (GITX-FR-005).` |
| 171 | docstring | GITX-FR-003 | `SRCX identity instead — the same deterministic function, GITX-FR-003)."""` |
| 182 | comment | GITX-FR-007 | `# --------------------------------------------------------------------------- clean start / stop (GITX-FR-007/008)` |
| 191 | docstring | GITX-FR-007 | `"""The uncommitted paths NOT produced by the run — the clean-start guard's subjects (GITX-FR-007).` |
| 193 | docstring | GITX-NFR-001 | `Pure and deterministic given its inputs (GITX-NFR-001). "Produced by the run" is the run's` |
| 196 | docstring | PROGFILE-NFR-002 | `and any feature workspace's engine-written ``progress.md`` (PROGFILE-NFR-002) are never a` |
| 212 | docstring | GITX-FR-007 | `The offline-recoverable run-produced set (GITX-FR-007's property): a prior stage that crashed` |
| 228 | docstring | GITX-FR-008 | `(GITX-FR-008's property: produced ∩ uncommitted == ∅) and at every stage boundary` |
| 229 | docstring | GITX-FR-016 | `(GITX-FR-016)."""` |
| 235 | docstring | GITX-FR-007 | `"""The refusal message naming the offending paths and the signed deviation (GITX-FR-007).` |
| 238 | docstring | GITX-NFR-003 | `(GITX-NFR-003); the only way through is the recorded, revocable relaxation (GITX-FR-014)."""` |
| 238 | docstring | GITX-FR-014 | `(GITX-NFR-003); the only way through is the recorded, revocable relaxation (GITX-FR-014)."""` |
| 248 | comment | GITX-FR-010 | `# --------------------------------------------------------------------------- stage commit (GITX-FR-010/011/012)` |
| 262 | docstring | GITX-FR-011 | `"""The agent-written stage description, extracted from the persisted transcript (GITX-FR-011).` |
| 285 | docstring | GITX-FR-011 | `"""The stage commit's subject (GITX-FR-011's property): ALWAYS carries the stage identifier and` |
| 300 | docstring | GITX-FR-010 | `"""Commit one producing stage's ``paths`` as exactly one commit, authored as 3pwr (GITX-FR-010/012).` |
| 304 | docstring | GITX-NFR-004 | `so the developer's configured git identity is never mutated (GITX-NFR-004). Paths a human` |
| 306 | docstring | GITX-FR-012 | `author (GITX-FR-012). Only an actual git failure is an error; it is surfaced, never forced."""` |
| 334 | docstring | GITX-FR-009 | `"""The producing steps with a recorded stage commit, in ledger order (GITX-FR-009/013).` |
| 337 | docstring | GITX-NFR-001 | `(GITX-NFR-001) — so the status view's per-stage committed indication needs no git scan."""` |

## engine/src/threepowers/hosted.py (14)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | RUNLIVE-FR-008 | `"""The asynchronous hosted agent backend — dispatch a role's stage to a *hosted* agent run (RUNLIVE-FR-008).` |
| 9 | docstring | RUNLIVE-NFR-003 | `identically to a locally-dispatched stage (RUNLIVE-NFR-003).` |
| 11 | docstring | RUNLIVE-NFR-005 | `It is **provider-neutral** (RUNLIVE-NFR-005): the trigger/poll/collect steps are *manifest-declared` |
| 14 | docstring | RUNLIVE-FR-009 | `environment and are never interpreted, logged, or stored by the engine (RUNLIVE-FR-009). The engine issues` |
| 15 | docstring | RUNLIVE-NFR-001 | `no model/agent API call itself — the hosted run does (RUNLIVE-NFR-001). All timing seams (the command` |
| 17 | docstring | RUNLIVE-NFR-002 | `fake and no network (RUNLIVE-NFR-002).` |
| 39 | docstring | RUNLIVE-FR-009 | `"""Run one manifest-declared hosted command (no shell), inheriting the environment (RUNLIVE-FR-009).` |
| 41 | docstring | RUNLIVE-NFR-001 | `Module-level so tests monkeypatch it — the engine issues no model call itself (RUNLIVE-NFR-001). The` |
| 74 | docstring | RUNLIVE-FR-008 | `"""Drive one stage through a hosted, asynchronous agent run (RUNLIVE-FR-008).` |
| 147 | docstring | RUNLIVE-FR-008 | `stage (RUNLIVE-FR-008), never a gate verdict. No credential is read or logged (RUNLIVE-FR-009).` |
| 147 | docstring | RUNLIVE-FR-009 | `stage (RUNLIVE-FR-008), never a gate verdict. No credential is read or logged (RUNLIVE-FR-009).` |
| 149 | docstring | RUNLIVE-NFR-003 | `and contextualized identically to a local one (RUNLIVE-NFR-003, PHASE-FR-005)."""` |
| 149 | docstring | PHASE-FR-005 | `and contextualized identically to a local one (RUNLIVE-NFR-003, PHASE-FR-005)."""` |
| 156 | comment | AGENTX-FR-005 | `# The same repo-local stage-template resolution as the local runner (AGENTX-FR-005).` |

## engine/src/threepowers/keys.py (12)

| line | kind | match | excerpt |
|---|---|---|---|
| 4 | docstring | 3PWR-FR-039 | `never stored in the repository and never appears in the ledger (3PWR-FR-039,` |
| 5 | docstring | 3PWR-NFR-005 | `3PWR-NFR-005). Only the *public* key is committed (``.3powers/keys/ledger.pub``) so` |
| 6 | docstring | 3PWR-NFR-004 | `that ``verify`` is fully local and offline (3PWR-NFR-004).` |
| 58 | docstring | HARDN-FR-006 | `"""Anything that can sign ledger bytes: a software key or an external signer (HARDN-FR-006)."""` |
| 67 | docstring | HARDN-FR-006 | `"""A configured external signer failed — loudly, never falling back (HARDN-FR-006)."""` |
| 148 | docstring | HARDN-FR-006 | `"""Delegate signing to an external process boundary (HARDN-FR-006).` |
| 219 | docstring | 3PWR-NFR-005 | `"""The distinct judiciary (oracle) signer's default path — also OUTSIDE the repo (3PWR-NFR-005)."""` |
| 238 | docstring | HARDN-FR-002 | `"""True iff ``path`` resolves inside the repository working tree (HARDN-FR-002)."""` |
| 255 | docstring | HARDN-FR-002 | `"""Deterministic key-custody preflight (HARDN-FR-002).` |
| 289 | docstring | 3PWR-NFR-005 | `"""Load the private signing key from outside the repository (3PWR-NFR-005).` |
| 294 | docstring | 3PWR-FR-039 | `a distinct oracle key is optional and fully backward-compatible (3PWR-FR-039)."""` |
| 322 | docstring | HARDN-FR-006 | `private seed is never readable by the engine (HARDN-FR-006). A configured-but-broken` |

## engine/src/threepowers/ledger.py (8)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-038 | `"""Append-only, hash-chained, signed verdict ledger (3PWR-FR-038/039).` |
| 10 | docstring | 3PWR-FR-071 | `self-contained and offline-reconstructable (3PWR-FR-071, 3PWR-NFR-010).` |
| 10 | docstring | 3PWR-NFR-010 | `self-contained and offline-reconstructable (3PWR-FR-071, 3PWR-NFR-010).` |
| 55 | docstring | HARDN-FR-004 | `"""The ``key_rotation`` payload: the outgoing key names its successor (HARDN-FR-004).` |
| 58 | docstring | 3PWR-NFR-004 | `the ledger + the committed current key alone — no external state (3PWR-NFR-004/010).` |
| 88 | comment | 3PWR-FR-040 | `# (3PWR-FR-040/FR-034/NFR-011); the CLI catch-all covers other callers.` |
| 88 | format-example | FR-034 | `# (3PWR-FR-040/FR-034/NFR-011); the CLI catch-all covers other callers.` |
| 88 | format-example | NFR-011 | `# (3PWR-FR-040/FR-034/NFR-011); the CLI catch-all covers other callers.` |

## engine/src/threepowers/lifecycle.py (11)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-011 | `"""The eight-stage lifecycle, derived from the ledger (3PWR-FR-011/019).` |
| 5 | docstring | 3PWR-FR-019 | `repository alone (3PWR-FR-019/071) with no second source of truth to drift.` |
| 13 | comment | 3PWR-FR-011 | `# The eight stages (spec §6 / 3PWR-FR-011).` |
| 43 | comment | AUTOX-FR-006 | `# The most recent UNRESOLVED run failure (AUTOX-FR-006/007): set by a `run`/`failure` ledger` |
| 53 | docstring | AUTOX-FR-007 | `"""True while the most recent run event for this spec is an unresolved failure (AUTOX-FR-007)."""` |
| 58 | comment | 3PWR-FR-037 | `# A sign-off counts only if it is at or after the most recent verdict (3PWR-FR-037).` |
| 95 | comment | 3PWR-FR-011 | `# `3pwr run` orchestration records (3PWR-FR-011/019, AUTOX-FR-006/007): start /` |
| 95 | comment | AUTOX-FR-006 | `# `3pwr run` orchestration records (3PWR-FR-011/019, AUTOX-FR-006/007): start /` |
| 99 | comment | AUTOX-FR-006 | `# A recorded terminal run failure (AUTOX-FR-006). The stage here is the lifecycle` |
| 110 | comment | AUTOX-FR-007 | `clear_failure(st)  # any later run progress resolves the recorded failure (AUTOX-FR-007)` |
| 119 | comment | 3PWR-FR-054 | `# A production signal means the spec reached the Observe stage (§13, 3PWR-FR-054).` |

## engine/src/threepowers/mutation.py (9)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-031 | `"""Mutation gate — measure the suite's power to catch injected faults (3PWR-FR-031).` |
| 4 | docstring | 3PWR-FR-034 | `actionable **missing assertion** (3PWR-FR-034), and the score is checked against the` |
| 5 | docstring | 3PWR-FR-032 | `tier threshold read from the single risk-tier table (3PWR-FR-032). The mutation tool` |
| 6 | docstring | 3PWR-NFR-007 | `is **adapter-declared** (3PWR-NFR-007) — the core only interprets a *normalized*` |
| 7 | docstring | 3PWR-FR-033 | `score, so the verdict shape is identical across languages (3PWR-FR-033). The run is` |
| 8 | docstring | 3PWR-FR-031 | `scoped to changed/high-risk files per invocation (3PWR-FR-031); the full sweep is a` |
| 9 | docstring | 3PWR-NFR-002 | `scheduled concern (3PWR-NFR-002).` |
| 12 | docstring | 3PWR-NFR-015 | `skip with a finding, never silently passed (3PWR-NFR-015).` |
| 45 | docstring | 3PWR-FR-031 | `requested high-risk files (3PWR-FR-031).` |

## engine/src/threepowers/notify.py (17)

| line | kind | match | excerpt |
|---|---|---|---|
| 5 | docstring | STEER-FR-009 | ```.3powers/config/notifications.yaml`` (STEER-FR-009/010/011): reference senders for **Slack**,` |
| 7 | docstring | STEER-FR-014 | `no SDK, no new dependency (STEER-FR-014's stance).` |
| 9 | docstring | STEER-NFR-001 | `The trust isolation is absolute (STEER-NFR-001): notifications are **disabled by default** and are a` |
| 14 | docstring | STEER-NFR-002 | `ledger, transcripts, or warnings (STEER-NFR-002; mirrors 3PWR-NFR-005). With no channel configured,` |
| 14 | docstring | 3PWR-NFR-005 | `ledger, transcripts, or warnings (STEER-NFR-002; mirrors 3PWR-NFR-005). With no channel configured,` |
| 32 | comment | STEER-FR-009 | `# The notifiable event kinds (STEER-FR-009) and the default routing (STEER-FR-011).` |
| 32 | comment | STEER-FR-011 | `# The notifiable event kinds (STEER-FR-009) and the default routing (STEER-FR-011).` |
| 38 | comment | STEER-FR-010 | `# The reference channel types (STEER-FR-010).` |
| 41 | comment | STEER-NFR-002 | `# Default environment variables the webhook channels read their URL from (STEER-NFR-002).` |
| 45 | comment | STEER-FR-010 | `# Keys the loader recognizes on a channel entry — anything else warns once (STEER-FR-010).` |
| 81 | docstring | STEER-FR-010 | `"""The configured channels + at most one warning per problem, tolerantly (STEER-FR-010).` |
| 190 | docstring | STEER-NFR-002 | `Warnings NAME a missing environment variable but never leak its value (STEER-NFR-002)."""` |
| 251 | docstring | STEER-NFR-001 | `"""Fire ``event`` at every channel routed to it — best-effort, never raising (STEER-NFR-001).` |
| 268 | comment | STEER-NFR-001 | `except Exception as exc:  # delivery must NEVER take the run down (STEER-NFR-001)` |
| 284 | docstring | STEER-FR-009 | `"""The actionable gate-pause message (STEER-FR-009): spec id, stage/gate, the artifact to review,` |
| 295 | docstring | STEER-FR-009 | `"""The actionable failure message: the failure class, where, and how to resume (STEER-FR-009)."""` |
| 304 | docstring | STEER-FR-009 | `"""The completion notice (STEER-FR-009)."""` |

## engine/src/threepowers/observe.py (7)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-054 | `"""Observe & feedback — closing the loop back to the spec (3PWR-FR-054/055, §13).` |
| 8 | docstring | 3PWR-FR-054 | `never an in-place patch (3PWR-FR-054);` |
| 12 | docstring | 3PWR-FR-055 | `(3PWR-FR-055) by reusing the append-only signed hash chain (`Ledger` on a separate file), so` |
| 31 | format-example | FR-054 | `# --------------------------------------------------------------------------- signal + routing (FR-054)` |
| 52 | docstring | 3PWR-FR-054 | `This is the *route to new intent* (3PWR-FR-054): a production lesson becomes a fresh requirement` |
| 66 | format-example | FR-054 | `# --------------------------------------------------------------------------- NFR instrumentation (FR-054)` |
| 105 | format-example | FR-055 | `# --------------------------------------------------------------------------- agentic action log (FR-055)` |

## engine/src/threepowers/oracle.py (43)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | 3PWR-FR-020 | `The oracle is the answer key the coder never authored (3PWR-FR-020, §7). This module makes` |
| 8 | docstring | 3PWR-FR-020 | `ledger. The judiciary authors the oracle *from this bundle* (3PWR-FR-020).` |
| 12 | docstring | 3PWR-FR-022 | `(3PWR-FR-022, on the *actual* model — not just the declared config).` |
| 15 | docstring | 3PWR-FR-021 | `and contracts are physically **absent** — the full letter of 3PWR-FR-021. It attests the isolation` |
| 18 | docstring | 3PWR-FR-062 | `timestamps), that Phase A preceded Phase B (3PWR-FR-062), the oracle was bound to the active` |
| 19 | docstring | 3PWR-FR-020 | `seal (3PWR-FR-020/021), the families diverge (3PWR-FR-022), and every acceptance criterion has` |
| 19 | docstring | 3PWR-FR-022 | `seal (3PWR-FR-020/021), the families diverge (3PWR-FR-022), and every acceptance criterion has` |
| 20 | docstring | 3PWR-FR-023 | `an oracle test (3PWR-FR-023). When a dispatch attestation is present (or required by the tier` |
| 21 | docstring | 3PWR-FR-021 | `policy) it also proves **physical read-path isolation** (3PWR-FR-021). These bind at ``advance``` |
| 26 | docstring | 3PWR-NFR-001 | `(that heuristic is input-dependent and must not perturb the deterministic verdict, 3PWR-NFR-001);` |
| 47 | format-example | FR-020 | `# --------------------------------------------------------------------------- sealed bundle (FR-020)` |
| 52 | docstring | 3PWR-FR-020 | `judiciary is meant to author against (3PWR-FR-020). Reuses the conformance spec parser so` |
| 66 | docstring | 3PWR-FR-020 | `re-sealing an unchanged spec yields an identical hash (deterministic binding, 3PWR-FR-020)."""` |
| 98 | format-example | FR-022 | `# --------------------------------------------------------------------------- authoring record (FR-022/062)` |
| 109 | docstring | 3PWR-FR-022 | `"""True iff ``coder`` and ``oracle`` are diverse enough at ``level`` (3PWR-FR-022).` |
| 142 | format-example | FR-057 | `):  # same-family authoring sanctioned by a signed deviation (FR-057)` |
| 182 | comment | 3PWR-FR-021 | `# coarse guess is fine — this never blocks (3PWR-FR-021 is enforced structurally, not here).` |
| 214 | docstring | 3PWR-FR-021 | `"""Advisory: implementation files the oracle author also modified (3PWR-FR-021, non-blocking)."""` |
| 269 | format-example | FR-020 | `(FR-020/021); the recorded oracle is diverse from the coder at ``diversity_level`` (FR-022); the` |
| 269 | format-example | FR-022 | `(FR-020/021); the recorded oracle is diverse from the coder at ``diversity_level`` (FR-022); the` |
| 270 | format-example | FR-062 | `record precedes the implementation verdict by ledger ``seq`` (FR-062); every sealed acceptance` |
| 271 | format-example | FR-023 | `criterion has an oracle test (FR-023). When a dispatch attestation is present — or when` |
| 273 | format-example | FR-021 | `proven (FR-021/A3). A same-family/same-model finding is blocking **unless** ``diversity_relaxed``` |
| 274 | format-example | FR-057 | `(a signed ``model_diversity`` deviation, FR-057), in which case it is advisory — never a silent` |
| 275 | docstring | 3PWR-NFR-001 | `drop. Advisory findings never enter ``reasons`` (3PWR-NFR-001).` |
| 298 | format-example | FR-020 | `# seal-binding (FR-020/021): the oracle was authored against the active spec-only bundle.` |
| 304 | format-example | FR-022 | `# diversity on the ACTUAL model used, at the configured granularity (FR-022). A same` |
| 305 | format-example | FR-057 | `# family/model is blocking unless a signed model_diversity deviation relaxes it (FR-057).` |
| 323 | format-example | FR-062 | `# ordering (FR-062): Phase A must precede Phase B, proven by ledger seq (not git time).` |
| 331 | format-example | FR-023 | `# coverage (FR-023): each sealed acceptance criterion has ≥1 oracle test.` |
| 339 | comment | 3PWR-FR-021 | `# physical read-path isolation via headless dispatch (3PWR-FR-021, A3). Advisory→blocking when a` |
| 341 | comment | 3PWR-NFR-001 | `# is ledger-derived, so this stays deterministic (3PWR-NFR-001).` |
| 379 | comment | HARDN-FR-007 | `# model attestation (HARDN-FR-007): the self-reported record model must not contradict` |
| 392 | comment | HARDN-FR-007 | `# nothing binds it to the process that ran (HARDN-FR-007). Advisory, never blocking.` |
| 410 | format-example | FR-021 | `# --------------------------------------------------------------------------- headless dispatch (FR-021/012/013, A3)` |
| 417 | format-example | FR-022 | `# Best-effort model *family* for an agent-backend key — the fast-fail FR-022 precheck only.` |
| 453 | format-example | FR-021 | `# What the oracle author must never see — FR-021's exact scope: "the implementation, the plan,` |
| 459 | docstring | 3PWR-FR-021 | `"""True iff a repo-relative path is implementation / plan / contracts / source (3PWR-FR-021)."""` |
| 481 | docstring | 3PWR-FR-021 | `Deterministic — the evidence the implementation was absent at authoring time (3PWR-FR-021)."""` |
| 500 | format-example | FR-021 | `"""Excluded (implementation/plan/contracts/source) paths still present — must be empty (FR-021)."""` |
| 530 | docstring | 3PWR-FR-021 | `"""Create an ephemeral git worktree pruned of implementation/plan/contracts/source (3PWR-FR-021).` |
| 543 | comment | 3PWR-FR-021 | `# Prune the implementation / plan / contracts / source (3PWR-FR-021).` |
| 559 | docstring | 3PWR-FR-021 | `"""The ledger attestation for an isolated headless oracle dispatch (3PWR-FR-021/012/013, A3)."""` |

## engine/src/threepowers/orchestrate.py (67)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-011 | `"""The orchestration front-end — drive the whole lifecycle as one loop (3PWR-FR-011, §6).` |
| 5 | docstring | 3PWR-FR-006 | `(a human approves the spec, 3PWR-FR-006) and ``signoff`` (a human signs off on the evidence + residual,` |
| 6 | docstring | 3PWR-FR-037 | `3PWR-FR-037). ``commit`` mode stops at every gate.` |
| 9 | docstring | EXEC-FR-001 | `:class:`threepowers.runner.NativeRunner` (EXEC-FR-001) — it dispatches each stage to a headless agent` |
| 11 | docstring | 3PWR-NFR-001 | `Orchestration never enters the deterministic verdict (3PWR-NFR-001).` |
| 33 | echoed-message | 3PWR-FR-006 | `"review-spec": "3PWR-FR-006",  # a human approves the spec before implementation begins` |
| 34 | echoed-message | 3PWR-FR-037 | `"signoff": "3PWR-FR-037",  # a human signs off on evidence + residual before advance` |
| 64 | comment | GDIAG-FR-001 | `# carries the failed verdict dict + the run's resolved spec id (GDIAG-FR-001/006). Rendering` |
| 95 | comment | RUNX-FR-010 | `# "" = a dispatch/execution failure (not a gate verdict) — the honest-diagnostics split (RUNX-FR-010/011)` |
| 103 | docstring | RUNX-FR-010 | `"""True only when a failure carries a real deterministic-gate ``fail`` verdict (RUNX-FR-010)."""` |
| 108 | docstring | RUNLIVE-FR-002 | `"""True when the failure was a stage producing no declared artifact (RUNLIVE-FR-002)."""` |
| 138 | docstring | RUNLIVE-FR-010 | `"""The last action step committed as a checkpoint for ``spec_id`` (RUNLIVE-FR-010), else ''.` |
| 153 | docstring | AUTOX-FR-010 | `"""The last action step recorded COMPLETE for ``spec_id``, else '' (AUTOX-FR-010).` |
| 156 | docstring | RUNLIVE-FR-010 | `(RUNLIVE-FR-010) or the lightweight ``stage`` completion record written at stage success even with` |
| 170 | docstring | RUNLIVE-FR-010 | `"""Where a ``--resume`` should re-enter the lifecycle (RUNLIVE-FR-010, AUTOX-FR-010).` |
| 170 | docstring | AUTOX-FR-010 | `"""Where a ``--resume`` should re-enter the lifecycle (RUNLIVE-FR-010, AUTOX-FR-010).` |
| 186 | docstring | RUNX-FR-007 | `including) the next gate. Used to record one per-stage dispatch provenance entry (RUNX-FR-007), so a` |
| 188 | docstring | RUNX-FR-004 | `segment (no already-completed stage is re-recorded, mirroring RUNX-FR-004)."""` |
| 193 | docstring | RUNX-FR-007 | `"""The action steps from ``start_index`` up to (not including) the next gate (RUNX-FR-007, RUNLIVE-FR-010).` |
| 193 | docstring | RUNLIVE-FR-010 | `"""The action steps from ``start_index`` up to (not including) the next gate (RUNX-FR-007, RUNLIVE-FR-010).` |
| 216 | comment | STEER-FR-013 | `# moment it happened (STEER-FR-013) — replaying the batched history here would report it twice.` |
| 237 | comment | RUNLIVE-FR-002 | `# (gate-red vs a dispatch/artifact failure — RUNLIVE-FR-002, RUNX-FR-010/011).` |
| 237 | comment | RUNX-FR-010 | `# (gate-red vs a dispatch/artifact failure — RUNLIVE-FR-002, RUNX-FR-010/011).` |
| 293 | comment | CLIUX-NFR-004 | `# Event glyphs, with an ASCII fallback for a stream that cannot encode the Unicode marks (CLIUX-NFR-004).` |
| 322 | docstring | CLIUX-FR-008 | `so the same "you are here" view reads consistently live and in ``--status`` (CLIUX-FR-008/012).` |
| 340 | docstring | GDIAG-FR-001 | `"""The first non-empty findings line of a failed gate — the line the user acts on (GDIAG-FR-001).` |
| 352 | docstring | GDIAG-FR-001 | `"""The structured gates-failed summary for a gate-red event (GDIAG-FR-001/006).` |
| 383 | docstring | CLIUX-FR-009 | `"""Human-readable one-liner for a streamed event (CLIUX-FR-009).` |
| 386 | docstring | CLIUX-FR-009 | `verdict, a prominent paused gate, a red failure — distinct at a glance (CLIUX-FR-009). With no` |
| 403 | comment | RUNX-FR-010 | `# failure is reported distinctly and names the stage reached (RUNX-FR-010/011, RUNLIVE-FR-002).` |
| 403 | comment | RUNLIVE-FR-002 | `# failure is reported distinctly and names the stage reached (RUNX-FR-010/011, RUNLIVE-FR-002).` |
| 415 | comment | SRCX-FR-014 | `# The SRCX completion gate blocked the stage (SRCX-FR-014/015) — named, actionable.` |
| 437 | docstring | CLIUX-FR-008 | `with the running step alongside it (CLIUX-FR-008/009)."""` |
| 445 | docstring | STEER-FR-012 | `dispatched agent's stdout print ABOVE it into ordinary, fully scrollable history (STEER-FR-012/013,` |
| 446 | docstring | CLIUX-FR-008 | `advancing CLIUX-FR-008/009's single in-place line). Off a TTY (pipe / ``--json``), under` |
| 448 | docstring | STEER-FR-015 | ```format_event`` log with no ``\\r`` in-place redraws and no ANSI/control codes (STEER-FR-015,` |
| 449 | docstring | CLIUX-FR-011 | `CLIUX-FR-011). The bar is rendered by ``rich`` behind the frame API (TRIX-FR-003/004; the` |
| 449 | docstring | TRIX-FR-003 | `CLIUX-FR-011). The bar is rendered by ``rich`` behind the frame API (TRIX-FR-003/004; the` |
| 452 | docstring | CLIUX-FR-011 | ```THREEPOWERS_FORCE_COLOR``, so a captured/piped run never carries escapes (CLIUX-FR-011)."""` |
| 470 | comment | CLIUX-FR-011 | `# run never carries escapes (CLIUX-FR-011).` |
| 473 | comment | STEER-FR-012 | `# The live bar (STEER-FR-012) — only when the terminal can carry it (STEER-FR-015);` |
| 473 | comment | STEER-FR-015 | `# The live bar (STEER-FR-012) — only when the terminal can carry it (STEER-FR-015);` |
| 482 | docstring | STEER-FR-016 | `"""Tear the live bar down — last state left on screen, cursor restored (STEER-FR-016).` |
| 489 | docstring | RUNID-FR-003 | `"""Adopt the run's resolved identity after construction (RUNID-FR-003).` |
| 492 | docstring | RUNID-FR-001 | `(the folder's NNN, RUNID-FR-001) arrives late; the live bar's title and its pause/resume` |
| 500 | docstring | STEER-FR-012 | `dispatch produces an event, so the run never looks frozen (STEER-FR-012/013). A no-op off a` |
| 512 | docstring | STEER-FR-012 | `open (scrollback keeps the whole conversation, STEER-FR-012), plain otherwise."""` |
| 522 | docstring | STEER-FR-012 | `above the live bar in real time instead of clobbering it (STEER-FR-012/013)."""` |
| 530 | comment | STEER-FR-012 | `# reflects the current state (STEER-FR-012/013).` |
| 542 | comment | STEER-FR-016 | `# lines so the follow-up guidance prints in normal flow (STEER-FR-016).` |
| 545 | comment | STEER-FR-015 | `# The plain streamed event log — off a TTY, and the degraded TTY path (STEER-FR-015):` |
| 553 | docstring | STEER-FR-012 | `through the tracker (STEER-FR-012) — above the live bar on a capable TTY, plain otherwise.` |
| 576 | comment | GATEPIPE-FR-004 | `# Tool-output noise the rendered gate view suppresses unless verbose (GATEPIPE-FR-004).` |
| 580 | comment | GATEPIPE-FR-003 | `# A failed gate's panel shows at most this many meaningful error lines (GATEPIPE-FR-003).` |
| 585 | docstring | GATEPIPE-FR-004 | `"""Flatten gate findings into rendered lines, filtering noise unless ``verbose`` (GATEPIPE-FR-004).` |
| 589 | docstring | GATEPIPE-NFR-001 | `only — the machine-readable verdict is never filtered (GATEPIPE-NFR-001)."""` |
| 606 | docstring | GATEPIPE-FR-001 | `"""One gate's pipeline row state — running until its finish event lands (GATEPIPE-FR-001)."""` |
| 616 | docstring | GATEPIPE-FR-001 | `"""The per-gate pipeline view of a gate run (GATEPIPE-FR-001/002).` |
| 623 | docstring | GATEPIPE-FR-002 | `line per *finished* gate, no in-place updates (GATEPIPE-FR-002). A ``--json`` run never` |
| 625 | docstring | GATEPIPE-NFR-001 | `enters the verdict (GATEPIPE-NFR-001)."""` |
| 690 | docstring | GATEPIPE-FR-002 | `"""Show ``gate`` as running (live mode); plain mode waits for the finish (GATEPIPE-FR-002)."""` |
| 723 | comment | GATEPIPE-FR-005 | `# (GATEPIPE-FR-005); pass/fail keep the shared status vocabulary (CLIUX-FR-005).` |
| 723 | comment | CLIUX-FR-005 | `# (GATEPIPE-FR-005); pass/fail keep the shared status vocabulary (CLIUX-FR-005).` |
| 737 | docstring | GATEPIPE-FR-001 | `"""The live region's renderable: one three-column grid row per gate (GATEPIPE-FR-001)."""` |
| 757 | docstring | GATEPIPE-FR-003 | `with a truncation note, then the configured auto-fix hint when present (GATEPIPE-FR-003/004).` |
| 779 | docstring | GATEPIPE-FR-003 | `plain indented text otherwise (GATEPIPE-FR-003)."""` |
| 814 | docstring | GATEPIPE-FR-003 | `"""The post-run failure surface: one panel per FAILED gate of ``verdict`` (GATEPIPE-FR-003).` |

## engine/src/threepowers/phases.py (39)

| line | kind | match | excerpt |
|---|---|---|---|
| 5 | docstring | 3PWR-FR-060 | `budget (delivers 3PWR-FR-060/061 at the engine level). This module owns the deterministic mechanics:` |
| 7 | docstring | PHASE-FR-010 | `* :func:`parse_phases` reads the phase structure from the tasks artifact's text (PHASE-FR-010);` |
| 9 | docstring | PHASE-FR-008 | `artifact **bytes** — no provider tokenizer, no network (PHASE-FR-008);` |
| 10 | docstring | PHASE-FR-009 | `* :func:`oversize_warning` words the strictly-advisory over-budget warning (PHASE-FR-009) — the budget` |
| 11 | docstring | PHASE-NFR-002 | `never fails a stage or gate (PHASE-NFR-002);` |
| 13 | docstring | PHASE-FR-011 | `declare no dependency, and have disjoint declared file scopes (PHASE-FR-011);` |
| 15 | docstring | PHASE-FR-010 | `returns results in deterministic artifact order (PHASE-FR-010/012).` |
| 18 | docstring | PHASE-NFR-001 | `schedules, and orderings on any machine — PHASE-NFR-001); the ledger is never touched here, so parallel` |
| 19 | docstring | PHASE-NFR-003 | `completion cannot corrupt the trust spine (PHASE-NFR-003 — the caller appends results *after* collection,` |
| 31 | comment | PHASE-FR-008 | `# The deterministic bytes→tokens heuristic (PHASE-FR-008): ~4 bytes per token is a practical estimate` |
| 35 | comment | PHASE-FR-007 | `# The shipped default context budget in tokens (PHASE-FR-007): a practical fill indicator for today's` |
| 42 | docstring | PHASE-FR-010 | `"""One phase parsed from the tasks artifact — a self-contained delegable unit (PHASE-FR-010).` |
| 59 | docstring | PHASE-FR-012 | `"""The outcome of executing one phase (PHASE-FR-012)."""` |
| 83 | docstring | PHASE-FR-010 | `"""Parse the ordered phases out of a tasks artifact's text (PHASE-FR-010) — pure and deterministic.` |
| 153 | comment | PHASE-FR-008 | `# --------------------------------------------------------------------------- context-size estimation (PHASE-FR-008)` |
| 175 | docstring | PHASE-FR-008 | `"""The byte size of a phase's reload set (PHASE-FR-008): the specification, the constitution/rules,` |
| 196 | docstring | PHASE-FR-008 | `"""The phase's estimated context size in tokens (PHASE-FR-008) — deterministic given the reload set."""` |
| 209 | docstring | PHASE-FR-009 | `"""The advisory over-budget warning (PHASE-FR-009), or ``None`` when the phase fits.` |
| 213 | docstring | PHASE-NFR-002 | `gate on it (PHASE-NFR-002)."""` |
| 227 | comment | PHASE-FR-011 | `# --------------------------------------------------------------------------- scheduling (PHASE-FR-011)` |
| 236 | comment | PHASE-FR-011 | `# concurrently (the conservative reading of PHASE-FR-011's property).` |
| 241 | docstring | PHASE-FR-011 | `"""Batch phases for dispatch (PHASE-FR-011): each batch runs concurrently, batches run in order.` |
| 246 | docstring | PHASE-NFR-001 | `reported overlap). Pure and deterministic (PHASE-NFR-001): two phases end up in the same batch only` |
| 271 | comment | PHASE-FR-010 | `# --------------------------------------------------------------------------- execution (PHASE-FR-010/012)` |
| 274 | docstring | PHASE-FR-012 | `"""The full result of running a phased implement stage (PHASE-FR-012)."""` |
| 285 | docstring | 3PWR-FR-034 | `"""An actionable message naming the failing phase(s) (3PWR-FR-034, PHASE-FR-012)."""` |
| 285 | docstring | PHASE-FR-012 | `"""An actionable message naming the failing phase(s) (3PWR-FR-034, PHASE-FR-012)."""` |
| 299 | docstring | PHASE-FR-010 | `"""Execute the schedule: each batch's phases run concurrently, batches sequentially (PHASE-FR-010/011).` |
| 303 | docstring | PHASE-FR-012 | `the threads interleave (PHASE-FR-012, PHASE-NFR-001/003). After a batch containing a failure, later` |
| 303 | docstring | PHASE-NFR-001 | `the threads interleave (PHASE-FR-012, PHASE-NFR-001/003). After a batch containing a failure, later` |
| 305 | docstring | PHASE-FR-012 | `"skipped" result, so a partially-implemented stage can never read as green (PHASE-FR-012)."""` |
| 332 | docstring | PHASEPR-FR-004 | `"""The one-line "phases already completed" summary for the phase prompt (PHASEPR-FR-004).` |
| 337 | docstring | PHASEPR-NFR-001 | `deterministic function of the parsed phase list and the index (PHASEPR-NFR-001)."""` |
| 352 | docstring | PHASE-FR-010 | `"""The per-phase handoff block a fresh session's prompt reloads (PHASE-FR-010).` |
| 354 | docstring | PHASEPR-FR-001 | `Carries the PHASE INSTRUCTION contract (PHASEPR-FR-001/002/003): scope limited to the declared` |
| 357 | docstring | PHASEPR-FR-004 | `plus the completed-phases summary (PHASEPR-FR-004), the phase's tasks, and the` |
| 360 | docstring | 3PWR-FR-061 | `conversation state (3PWR-FR-061). Deterministic given the inputs (PHASE-NFR-001,` |
| 360 | docstring | PHASE-NFR-001 | `conversation state (3PWR-FR-061). Deterministic given the inputs (PHASE-NFR-001,` |
| 361 | docstring | PHASEPR-NFR-001 | `PHASEPR-NFR-001)."""` |

## engine/src/threepowers/progress.py (29)

| line | kind | match | excerpt |
|---|---|---|---|
| 6 | docstring | PROGFILE-FR-004 | `per lifecycle stage with a status glyph and completion timestamp — PROGFILE-FR-004) and, while the` |
| 8 | docstring | PROGFILE-FR-005 | `checkboxes (PROGFILE-FR-005). It carries a "Current state" block, the last deterministic-gate` |
| 10 | docstring | PROGFILE-FR-006 | `the last verify attempt (PROGFILE-FR-006).` |
| 13 | docstring | PROGFILE-FR-002 | `onto ``progress.md`` — so a concurrent reader never sees a torn file (PROGFILE-FR-002, matching the` |
| 16 | docstring | PROGFILE-FR-007 | `verdict / human-gate pause / run failure — PROGFILE-FR-007) into that snapshot. The module never` |
| 18 | docstring | PROGFILE-NFR-001 | `(PROGFILE-NFR-001 — the caller degrades errors to a warning).` |
| 35 | comment | PROGFILE-FR-002 | `# The engine-owned progress file and its same-directory atomic-write staging name (PROGFILE-FR-002).` |
| 39 | comment | PROGFILE-FR-004 | `# Row statuses and their glyphs (PROGFILE-FR-004).` |
| 67 | docstring | PROGFILE-FR-004 | `"""One rendered row of the stage-progress table (PROGFILE-FR-004)."""` |
| 77 | docstring | PROGFILE-FR-005 | `"""One rendered row of the phase-detail table (PROGFILE-FR-005)."""` |
| 92 | comment | PROGFILE-FR-003 | `nnn: str  # the workspace number for the title line (PROGFILE-FR-003)` |
| 107 | docstring | PROGFILE-FR-006 | `"""The failed gate names of a verdict dict, in verdict order (PROGFILE-FR-006).` |
| 118 | docstring | PROGFILE-FR-003 | `Layout per the PROGFILE content schema: the title line (PROGFILE-FR-003), the stage-progress` |
| 119 | docstring | PROGFILE-FR-004 | `table (PROGFILE-FR-004), the phase-detail table only when the snapshot carries phases` |
| 120 | docstring | PROGFILE-FR-005 | `(PROGFILE-FR-005), then the Current state / Last verdict / fenced Helper commands / Gate` |
| 121 | docstring | PROGFILE-FR-006 | `failures sections with the run's real identity interpolated (PROGFILE-FR-006)."""` |
| 168 | docstring | PROGFILE-FR-001 | `"""Atomically write the rendered snapshot as ``<feature_dir>/progress.md`` (PROGFILE-FR-001/002).` |
| 173 | docstring | PROGFILE-NFR-001 | `a run failure (PROGFILE-NFR-001)."""` |
| 192 | docstring | PROGFILE-FR-007 | `rewrites the file (PROGFILE-FR-007). Stage completion is per-step: a stage's row turns ``done``` |
| 196 | docstring | PROGFILE-FR-005 | `tasks ``[x]`` is reflected on the next trigger (PROGFILE-FR-005). ``now`` is injectable for` |
| 197 | docstring | PROGFILE-NFR-001 | `deterministic tests; IO errors propagate for the caller to degrade (PROGFILE-NFR-001)."""` |
| 230 | docstring | PROGFILE-FR-007 | `"""Stage start (PROGFILE-FR-007): the stage's row turns ``⏳ running`` and the current-state` |
| 243 | docstring | PROGFILE-FR-007 | `"""Stage complete (PROGFILE-FR-007): record the step; when it was the stage's last non-gate` |
| 244 | docstring | PROGFILE-FR-004 | `step the row turns ``✓ done`` with a completion timestamp (PROGFILE-FR-004)."""` |
| 250 | docstring | PROGFILE-FR-007 | `"""Gate verdict PASS/FAIL (PROGFILE-FR-007): update the last-verdict block; a red verdict` |
| 268 | docstring | PROGFILE-FR-007 | `"""Human-gate pause (PROGFILE-FR-007): the gate's stage shows ``🔒 paused`` and the` |
| 280 | docstring | PROGFILE-FR-007 | `"""Run failure (PROGFILE-FR-007): the failing stage shows ``✗ failed`` and the current-state` |
| 329 | docstring | PROGFILE-FR-001 | `"""Atomically (re)write ``progress.md`` from the current state (PROGFILE-FR-001/002)."""` |
| 349 | comment | PROGFILE-FR-005 | `# Phase detail applies only while the phased stage is current (PROGFILE-FR-005): the` |

## engine/src/threepowers/prompts.py (17)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | EXEC-FR-005 | `"""Engine-owned lifecycle stage prompts (EXEC-FR-005) + per-stage agent templates (AGENTX-FR-001/005).` |
| 1 | docstring | AGENTX-FR-001 | `"""Engine-owned lifecycle stage prompts (EXEC-FR-005) + per-stage agent templates (AGENTX-FR-001/005).` |
| 7 | docstring | EXEC-FR-005 | `run-to-run variance (supports EXEC-FR-005's property and 3PWR-NFR-001).` |
| 7 | docstring | 3PWR-NFR-001 | `run-to-run variance (supports EXEC-FR-005's property and 3PWR-NFR-001).` |
| 9 | docstring | AGENTX-FR-001 | `A project can SEE and TUNE each stage's instructions (AGENTX-FR-001): a repo-local stage template at` |
| 14 | docstring | AGENTX-FR-005 | `(AGENTX-FR-005). Template resolution is deterministic and offline: identical template bytes and` |
| 97 | comment | GITX-FR-011 | `# The producing stages whose prompt asks the agent for a commit description (GITX-FR-011): the` |
| 113 | comment | AGENTX-FR-001 | `# The lifecycle stages that carry a dedicated agent template (AGENTX-FR-001): every stage that` |
| 134 | docstring | AGENTX-FR-001 | `"""The agent-template filename for a step (AGENTX-FR-001)."""` |
| 139 | docstring | AGENTX-FR-001 | `"""The well-known repo-local template location for a step (AGENTX-FR-001)."""` |
| 147 | docstring | AGENTX-FR-004 | `artifact, and the role (AGENTX-FR-004); it orients readers and is not part of the dispatched` |
| 158 | docstring | AGENTX-FR-005 | `"""The repo-local template's instruction body for ``step``, or ``""`` (AGENTX-FR-005).` |
| 162 | docstring | AGENTX-NFR-001 | `crashes on a malformed template. Deterministic and fully offline (AGENTX-NFR-001)."""` |
| 180 | docstring | AGENTX-FR-005 | `"""The instruction body the executive dispatches for ``step`` (AGENTX-FR-005).` |
| 196 | docstring | EXEC-FR-005 | `"""Compose the full stage prompt deterministically (EXEC-FR-005).` |
| 201 | docstring | AGENTX-FR-005 | `repo-local stage template's (AGENTX-FR-005); it changes only the instruction body, never the` |
| 205 | comment | GITX-FR-011 | `# A fixed block outside the tunable instruction body (GITX-FR-011): a repo-local stage` |

## engine/src/threepowers/provenance.py (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-066 | `"""Build provenance + SBOM + deploy-gate verification (3PWR-FR-066/067/068).` |
| 5 | docstring | 3PWR-FR-068 | `Ed25519 identity as the verdict ledger** (3PWR-FR-068) — so provenance is produced and` |
| 6 | docstring | 3PWR-NFR-004 | `verified with no hosted CI/CD pipeline, fully offline (3PWR-NFR-004). The deploy gate` |
| 7 | docstring | 3PWR-FR-067 | `refuses any artifact whose provenance is missing or fails verification (3PWR-FR-067).` |

## engine/src/threepowers/runner.py (66)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | EXEC-FR-001 | `This is the executive leg 3Powers now owns (EXEC-FR-001; amends 3PWR A1/A3). :class:`NativeRunner`` |
| 9 | docstring | EXEC-FR-004 | `the invocation from a declarative manifest and runs the agent as an external process (EXEC-FR-004/005);` |
| 11 | docstring | EXEC-FR-006 | `callable — never through a subprocess and never through a model (EXEC-FR-006);` |
| 15 | docstring | RUNLIVE-FR-004 | `per policy (RUNLIVE-FR-004/005), the stage's declared **artifact contract** is verified before advancing` |
| 16 | docstring | RUNLIVE-FR-001 | `(RUNLIVE-FR-001/002), and a machine-readable **per-stage result** (agent, model, attempts, duration,` |
| 17 | docstring | RUNLIVE-FR-006 | `artifact, outcome) is recorded for ``--json`` (RUNLIVE-FR-006). None of this enters the deterministic` |
| 21 | docstring | EXEC-NFR-001 | `process (EXEC-NFR-001, RUNLIVE-NFR-001). ``NativeRunner`` is pure given its injected callables, so the whole` |
| 21 | docstring | RUNLIVE-NFR-001 | `process (EXEC-NFR-001, RUNLIVE-NFR-001). ``NativeRunner`` is pure given its injected callables, so the whole` |
| 23 | docstring | EXEC-NFR-004 | `(EXEC-NFR-004, RUNLIVE-NFR-002). A dispatch failure, an exhausted retry, or a missing artifact returns` |
| 23 | docstring | RUNLIVE-NFR-002 | `(EXEC-NFR-004, RUNLIVE-NFR-002). A dispatch failure, an exhausted retry, or a missing artifact returns` |
| 25 | docstring | EXEC-FR-016 | `(EXEC-FR-016, RUNLIVE-FR-002).` |
| 25 | docstring | RUNLIVE-FR-002 | `(EXEC-FR-016, RUNLIVE-FR-002).` |
| 47 | comment | EXEC-NFR-004 | `# Injected seams (EXEC-NFR-004): dispatch one action stage, or produce a verdict for one verify stage.` |
| 53 | docstring | AUTOX-FR-008 | `"""Anything transcript lines can be teed into (a file, a redacting writer — AUTOX-FR-008)."""` |
| 66 | comment | AUTOX-FR-008 | `# The persisted transcript path for this attempt, when one was written (AUTOX-FR-008).` |
| 72 | docstring | RUNLIVE-FR-006 | `"""The machine-readable result of running one action stage end-to-end (RUNLIVE-FR-006).` |
| 76 | docstring | RUNLIVE-FR-002 | `machine; ``outcome`` classifies a failure for an actionable message (RUNLIVE-FR-002/NFR-004):` |
| 76 | format-example | NFR-004 | `machine; ``outcome`` classifies a failure for an actionable message (RUNLIVE-FR-002/NFR-004):` |
| 90 | comment | AUTOX-FR-008 | `# The persisted transcript path of the stage's LAST attempt (AUTOX-FR-008): a failure message` |
| 94 | comment | PHASE-FR-003 | `# committed artifact trail is reconstructable from the signed ledger alone (PHASE-FR-003).` |
| 96 | comment | PHASE-FR-009 | `# Advisory notes (e.g. the context-budget oversize warnings, PHASE-FR-009) — never a failure.` |
| 98 | comment | PHASE-FR-010 | `# Per-phase results when the stage ran as context-sized phases (PHASE-FR-010/012), artifact order.` |
| 139 | docstring | EXEC-NFR-001 | `(EXEC-NFR-001). ``argv`` comes only from a committed agent manifest via :func:`agents.build_command`,` |
| 142 | docstring | RUNLIVE-FR-004 | ```timeout`` bounds the attempt (RUNLIVE-FR-004): an over-long agent is terminated and reported as a` |
| 144 | docstring | AUTOX-FR-008 | `the persisted transcript sink (AUTOX-FR-008). With ``stream`` set the lines are ALSO echoed live` |
| 145 | docstring | RUNLIVE-FR-006 | `(RUNLIVE-FR-006) — to ``echo_out``/``echo_err`` when given (the run's live bar routes the` |
| 146 | docstring | STEER-FR-012 | `conversation above itself through these, STEER-FR-012), else straight to the process's own` |
| 169 | comment | AUTOX-FR-008 | `# buffers, the transcript sink, and — when streaming — the terminal (AUTOX-FR-008).` |
| 239 | docstring | EXEC-FR-001 | `"""Dispatch a lifecycle stage to a headless coding-agent CLI described by a manifest (EXEC-FR-001/003).` |
| 241 | docstring | EXEC-FR-005 | `Assembles the engine-owned stage prompt (EXEC-FR-005), builds the invocation from the manifest, runs the` |
| 243 | docstring | EXEC-FR-016 | `a dispatch failure (EXEC-FR-016). The provider/gateway environment is inherited by the child process, so` |
| 244 | docstring | EXEC-FR-012 | `an org routes model traffic through its own gateway with no engine change (EXEC-FR-012).` |
| 247 | docstring | RUNLIVE-NFR-002 | `pure and unit-testable (RUNLIVE-NFR-002).` |
| 274 | comment | STEER-FR-012 | `# Where a streamed attempt's live echo goes (STEER-FR-012): the run's live bar routes the` |
| 278 | comment | AUTOX-FR-008 | `# The per-run transcript sink (AUTOX-FR-008): every attempt's output is persisted,` |
| 279 | comment | AUTOX-NFR-002 | `# credential-redacted (AUTOX-NFR-002). None = no persistence (programmatic callers).` |
| 282 | comment | EXEC-NFR-001 | `# (tests / a fake agent) is honored — the engine still issues no model call (EXEC-NFR-001).` |
| 294 | docstring | EXEC-FR-001 | `"""Run one fresh headless session for ``step`` (EXEC-FR-001; PHASE-FR-005/010).` |
| 294 | docstring | PHASE-FR-005 | `"""Run one fresh headless session for ``step`` (EXEC-FR-001; PHASE-FR-005/010).` |
| 298 | docstring | PHASE-FR-005 | `file scope, so no stage depends on the agent rediscovering its inputs (PHASE-FR-005). Each` |
| 307 | comment | AGENTX-FR-005 | `# unreadable falls back to the built-in instruction (AGENTX-FR-005). Only the body` |
| 308 | comment | EXEC-FR-005 | `# changes — the context blocks and their order stay fixed (EXEC-FR-005).` |
| 312 | comment | AUTOX-FR-008 | `# Persist this attempt's output to the run's transcript location (AUTOX-FR-008): teed even` |
| 314 | comment | AUTOX-NFR-002 | `# credential-shaped env values before any byte lands on disk (AUTOX-NFR-002).` |
| 349 | comment | AUTOX-NFR-002 | `# transcript itself; nothing persisted may carry a credential (AUTOX-NFR-002).` |
| 362 | docstring | RUNLIVE-FR-005 | `"""Run ``attempt`` until it succeeds or the retry budget is exhausted (RUNLIVE-FR-005).` |
| 366 | docstring | RUNLIVE-NFR-002 | `unit-tested with a fake (RUNLIVE-NFR-002)."""` |
| 392 | docstring | RUNLIVE-FR-001 | `"""Dispatch one action stage under the retry/timeout policy, then verify its artifact (RUNLIVE-FR-001..006).` |
| 396 | docstring | RUNLIVE-FR-003 | `contract, or ``None`` when the stage declares none (RUNLIVE-FR-003). Returns a :class:`StageResult` that` |
| 398 | docstring | RUNLIVE-NFR-002 | `model, no network (RUNLIVE-NFR-002)."""` |
| 441 | comment | PHASE-FR-003 | `artifact_paths=list(check.matched),  # recorded with the ledger entry (PHASE-FR-003)` |
| 458 | docstring | RUNLIVE-NFR-002 | `"""Run a git command in ``cwd`` (module-level so tests can monkeypatch it — RUNLIVE-NFR-002)."""` |
| 471 | docstring | AUTOX-FR-008 | `Engine-written transcripts (``.3powers/runs/``, AUTOX-FR-008) are excluded even when the` |
| 490 | docstring | RUNLIVE-NFR-002 | `"""A content snapshot of the changed/untracked files — ``{path: sha256}`` (RUNLIVE-NFR-002).` |
| 509 | docstring | SRCX-FR-017 | `re-run — SRCX-FR-017) — the dispatch really did produce it even though the working tree ends` |
| 517 | docstring | EXEC-FR-001 | `"""Drive the lifecycle headlessly via injected dispatch + verdict callables (EXEC-FR-001/006).` |
| 520 | docstring | RUNLIVE-FR-006 | ```--json`` per-stage report (RUNLIVE-FR-006). A failing action stage carries its outcome + detail into` |
| 522 | docstring | RUNLIVE-FR-002 | `(RUNLIVE-FR-002)."""` |
| 538 | comment | STEER-FR-013 | `# Live event delivery (STEER-FR-013): each event is surfaced the moment it happens — a` |
| 546 | docstring | STEER-FR-013 | `"""Whether events reach the caller the moment they happen (STEER-FR-013) — ``drive`` then` |
| 562 | comment | STEER-FR-013 | `# Announce the suite BEFORE it runs (STEER-FR-013) — a long gate run shows live too.` |
| 567 | comment | EXEC-FR-016 | `# NOT a gate-red verdict (EXEC-FR-016). verdict="" signals the non-verdict failure.` |
| 584 | comment | STEER-FR-013 | `# Announce the stage BEFORE dispatching it (STEER-FR-013): the live bar names the` |
| 591 | comment | EXEC-FR-016 | `# (EXEC-FR-016, RUNLIVE-FR-002), carrying the outcome + named detail.` |
| 591 | comment | RUNLIVE-FR-002 | `# (EXEC-FR-016, RUNLIVE-FR-002), carrying the outcome + named detail.` |
| 612 | docstring | STEER-FR-006 | `"""Dispatch exactly ONE action stage outside the walk — the revise re-run (STEER-FR-006).` |

## engine/src/threepowers/runpreflight.py (23)

| line | kind | match | excerpt |
|---|---|---|---|
| 2 | docstring | EXEC-FR-015 | `(EXEC-FR-015).` |
| 5 | docstring | EXEC-FR-016 | `names the fully-offline ``--dry-run`` alternative — it is never mislabeled "gates red" (EXEC-FR-016).` |
| 7 | docstring | EXEC-NFR-003 | `and no vendor name is embedded in run logic (EXEC-NFR-003). This module only *reads* configuration and the` |
| 24 | comment | EXEC-NFR-003 | `# (roles.yaml `headless_integrations`) so the accepted set is data, not code (EXEC-NFR-003).` |
| 40 | comment | EXEC-FR-016 | `# The always-available offline paths named in every preflight-failure message (EXEC-FR-016).` |
| 49 | docstring | RUNX-FR-009 | `"""One run prerequisite and, when unmet, the exact next step to resolve it (RUNX-FR-009).` |
| 51 | docstring | AUTOX-FR-004 | ```label`` is the honest status detail for a MET prerequisite (AUTOX-FR-004): it states exactly what` |
| 62 | docstring | RUNX-NFR-005 | `"""The configured headless-capable integrations, else the built-in default (RUNX-NFR-005)."""` |
| 89 | docstring | RUNX-FR-006 | `deviation is active (RUNX-FR-006 / 3PWR-FR-022 via FR-057)."""` |
| 89 | docstring | 3PWR-FR-022 | `deviation is active (RUNX-FR-006 / 3PWR-FR-022 via FR-057)."""` |
| 89 | format-example | FR-057 | `deviation is active (RUNX-FR-006 / 3PWR-FR-022 via FR-057)."""` |
| 105 | docstring | EXEC-FR-015 | `CLI is present. Native counterpart to the coder/oracle checks in :func:`check` (EXEC-FR-015)."""` |
| 127 | comment | AUTOX-FR-004 | `# The honest offline caveat (AUTOX-FR-004): PATH presence is probeable; provider authentication` |
| 145 | docstring | EXEC-FR-015 | `"""Verify the prerequisites for a LIVE **native** run (EXEC-FR-015): a headless coder agent and a` |
| 171 | docstring | EXEC-NFR-004 | `"""The default PATH probe for :func:`git_prereq` (injected in tests — EXEC-NFR-004)."""` |
| 176 | docstring | GITX-FR-002 | `"""A working git repository — a PRECONDITION for starting a run (GITX-FR-002).` |
| 180 | docstring | GITX-NFR-001 | `deterministic, no subprocess needed for the work-tree test (GITX-NFR-001)."""` |
| 194 | docstring | AUTOX-FR-001 | `well-formed), never trusted silently (AUTOX-FR-001)."""` |
| 241 | docstring | AUTOX-FR-002 | `check set (AUTOX-FR-002): ``3pwr init``'s readiness, the standalone ``3pwr ready``, and the run's` |
| 245 | docstring | AUTOX-FR-005 | `(AUTOX-FR-005): signing key → working git repository (GITX-FR-002) → coder agent (roles + CLI)` |
| 245 | docstring | GITX-FR-002 | `(AUTOX-FR-005): signing key → working git repository (GITX-FR-002) → coder agent (roles + CLI)` |
| 266 | docstring | RUNX-FR-007 | `"""The additive executive-dispatch provenance recorded per dispatched stage (RUNX-FR-007).` |
| 269 | format-example | NFR-002 | `hash-chained ledger as the run's verdict, so altering one is detectable by ``3pwr verify`` (NFR-002)."""` |

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

## engine/src/threepowers/scaffold.py (48)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | ONBRD-FR-001 | `"""Onboarding scaffold — bundled baseline config + reference adapters (ONBRD-FR-001/003/008).` |
| 5 | docstring | ONBRD-NFR-002 | `(ONBRD-NFR-002). Nothing here writes a private key into the repository (ONBRD-NFR-001):` |
| 5 | docstring | ONBRD-NFR-001 | `(ONBRD-NFR-002). Nothing here writes a private key into the repository (ONBRD-NFR-001):` |
| 9 | docstring | ONBRD-FR-008 | `Seeding never clobbers hand-edited files (ONBRD-FR-008) and is therefore idempotent: re-running` |
| 10 | docstring | ONBRD-FR-009 | `converges to the same on-disk state (ONBRD-FR-009).` |
| 47 | docstring | ONBRD-FR-003 | `"""The languages the engine can scaffold — one per bundled adapter manifest (ONBRD-FR-003)."""` |
| 61 | docstring | ONBRD-FR-010 | `"""The bundled language whose detect files ALL exist under ``target`` (ONBRD-FR-010).` |
| 73 | docstring | ONBRD-FR-010 | `"""Brownfield heuristic — does ``target`` already hold a project? (ONBRD-FR-010)` |
| 96 | docstring | ONBRD-FR-008 | `"""Copy the baseline config into ``.3powers/config/``, never clobbering (ONBRD-FR-008)."""` |
| 105 | docstring | ONBRD-FR-008 | `"""Make the selected adapter available under ``.3powers/adapters/<lang>/`` (ONBRD-FR-008)."""` |
| 123 | docstring | EXEC-FR-004 | `"""The agent backends the engine can seed — one per bundled manifest (EXEC-FR-004)."""` |
| 130 | docstring | EXEC-FR-004 | `"""Copy the bundled agent-backend manifests into ``.3powers/agents/`` (EXEC-FR-004), never clobbering.` |
| 151 | docstring | AGENTX-FR-001 | `"""The per-stage agent templates the engine ships — one per dispatched stage (AGENTX-FR-001)."""` |
| 158 | docstring | AGENTX-FR-009 | `"""Copy the bundled stage agent templates into ``.3powers/templates/agents/`` (AGENTX-FR-009).` |
| 160 | docstring | ONBRD-FR-008 | `Non-clobbering and idempotent (ONBRD-FR-008/009): a hand-edited template is never overwritten,` |
| 162 | docstring | AGENTX-FR-005 | `body the executive dispatches for that stage (AGENTX-FR-005)."""` |
| 174 | docstring | ONBRD-FR-005 | `"""Record the autonomy defaults (advisory; ONBRD-FR-005 / INITX-FR-001/006).` |
| 174 | docstring | INITX-FR-001 | `"""Record the autonomy defaults (advisory; ONBRD-FR-005 / INITX-FR-001/006).` |
| 178 | docstring | ONBRD-NFR-004 | `None ever weakens a gate or suppresses a mandatory human gate (ONBRD-NFR-004 / INITX-NFR-002)."""` |
| 178 | docstring | INITX-NFR-002 | `None ever weakens a gate or suppresses a mandatory human gate (ONBRD-NFR-004 / INITX-NFR-002)."""` |
| 195 | comment | AGENTX-FR-017 | `# The explanatory header rewritten role files keep (AGENTX-FR-017): `require_dispatch` and the` |
| 236 | docstring | INITX-FR-002 | `"""Record a role's concrete model + integration in ``roles.yaml`` (INITX-FR-002/003, AGENTX-FR-012).` |
| 236 | docstring | AGENTX-FR-012 | `"""Record a role's concrete model + integration in ``roles.yaml`` (INITX-FR-002/003, AGENTX-FR-012).` |
| 239 | docstring | AGENTX-NFR-003 | `other role and unrelated field (AGENTX-NFR-003). ``model_family`` wins when given (a catalog` |
| 240 | docstring | AGENTX-FR-015 | `entry's family — AGENTX-FR-015); otherwise the family is derived from the model id where it` |
| 242 | docstring | AGENTX-FR-012 | `(AGENTX-FR-012): an explicit value wins, an existing value is preserved, else the documented` |
| 243 | docstring | AGENTX-FR-017 | `default ``false``. The rewritten file keeps an explanatory header (AGENTX-FR-017)."""` |
| 275 | docstring | AGENTX-FR-017 | `"""Write roles.yaml with the explanatory header, preserving field order (AGENTX-FR-017)."""` |
| 285 | docstring | EXEC-FR-015 | `"""Record which agent-backend CLIs a live ``3pwr run`` may dispatch (EXEC-FR-015/NFR-003).` |
| 285 | format-example | NFR-003 | `"""Record which agent-backend CLIs a live ``3pwr run`` may dispatch (EXEC-FR-015/NFR-003).` |
| 288 | docstring | AGENTX-NFR-003 | `other field. An empty selection is a no-op — it never wipes the seeded default (AGENTX-NFR-003)."""` |
| 302 | docstring | 3PWR-FR-022 | `"""Record how model diversity is judged — ``family`` or ``model`` (3PWR-FR-022).` |
| 314 | comment | STEER-NFR-002 | `# comments on the first rewrite, and the secret-safety rule (STEER-NFR-002) is worth keeping WHERE` |
| 326 | docstring | STEER-FR-010 | `"""Record one run-notification channel in ``notifications.yaml`` (STEER-FR-010).` |
| 330 | docstring | STEER-NFR-002 | `value: slack/teams carry ``webhook_env`` and email ``password_env`` (STEER-NFR-002)."""` |
| 353 | docstring | ONBRD-NFR-001 | `"""True iff ``path`` resolves OUTSIDE the repository working tree (ONBRD-NFR-001 / SC-003)."""` |
| 354 | comment | HARDN-FR-002 | `from .keys import inside_working_tree  # single custody source of truth (HARDN-FR-002)` |
| 363 | docstring | ONBRD-FR-016 | `"""Write a 3Powers-flavoured AGENTS.md starter if the repo has none (ONBRD-FR-016).` |
| 371 | comment | DOCX-FR-004 | `# 3Powers-owned path (DOCX-FR-004; relocated out of the former Spec-Kit tree).` |
| 388 | docstring | ONBRD-FR-015 | `(ONBRD-FR-015) — a user-authored one is left alone."""` |
| 397 | docstring | ONBRD-FR-015 | `"""Lay the 3Powers constitution at ``.3powers/memory/constitution.md`` (ONBRD-FR-015, DOCX-FR-005).` |
| 397 | docstring | DOCX-FR-005 | `"""Lay the 3Powers constitution at ``.3powers/memory/constitution.md`` (ONBRD-FR-015, DOCX-FR-005).` |
| 413 | docstring | INITX-FR-010 | `"""True iff a recognized CI/CD configuration is present (INITX-FR-010).` |
| 416 | docstring | INITX-FR-010 | `It asserts *presence* only — never that the pipeline is complete or correct (INITX-FR-010)."""` |
| 447 | docstring | INITX-FR-011 | `"""True iff AGENTS.md exists and is still the unfilled 3Powers starter (INITX-FR-011).` |
| 459 | docstring | ONBRD-FR-015 | `"""A checklist of what a project needs to run the full agentic workflow (ONBRD-FR-015/016).` |
| 461 | docstring | INITX-FR-009 | `Extended for INITX-FR-009/010/011 with CI/CD presence and whether AGENTS.md is still an unfilled` |
| 474 | docstring | ONBRD-FR-007 | `"""Create the Ed25519 signer, refusing to overwrite an existing key unless forced (ONBRD-FR-007).` |

## engine/src/threepowers/scanners.py (12)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-028 | `"""Language-agnostic supply-chain scanners — core gates (3PWR-FR-028).` |
| 6 | docstring | 3PWR-NFR-015 | `finding — never silently passed (3PWR-NFR-015).` |
| 32 | docstring | 3PWR-FR-051 | `"""True if a finding's file is in the changed-file scope (brownfield, 3PWR-FR-051).` |
| 47 | comment | 3PWR-NFR-015 | `# gitleaks writes ``[]``, handled below. Neither installed → the gate is quarantined (3PWR-NFR-015).` |
| 57 | comment | HARDN-FR-003 | `# while catching any actual committed key material (HARDN-FR-003).` |
| 77 | docstring | HARDN-FR-003 | `"""Core fallback scan for committed ``ed25519-priv`` material (HARDN-FR-003).` |
| 106 | docstring | 3PWR-FR-026 | `"""Scan the working tree for committed secrets (3PWR-FR-026 §8).` |
| 109 | docstring | HARDN-FR-003 | `(HARDN-FR-003) — it needs no external binary and is never quarantined away. For the` |
| 112 | docstring | 3PWR-NFR-015 | `is quarantined when neither binary is installed (3PWR-NFR-015)."""` |
| 161 | comment | 3PWR-FR-051 | `# When diff-scoped, only changed-file findings block (3PWR-FR-051).` |
| 209 | docstring | 3PWR-FR-026 | `"""Static analysis with semgrep against a local, offline ruleset (3PWR-FR-026 §8)."""` |
| 219 | comment | 3PWR-FR-051 | `continue  # brownfield: only changed-file findings block (3PWR-FR-051)` |

## engine/src/threepowers/scope.py (4)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-016 | `"""Task scope discipline (3PWR-FR-016/017).` |
| 5 | format-example | FR-016 | `* **FR-016** — every task traces to a requirement: each task line in ``tasks.md`` must` |
| 7 | format-example | FR-017 | `* **FR-017** — a task declares the files it will touch (``(files: …)``); a change that` |
| 47 | format-example | FR-016 | `tasks_without_req.append(line.strip()[:80])  # FR-016` |

## engine/src/threepowers/speclock.py (18)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | 3PWR-FR-010 | `The spec is the law (3PWR-FR-010). After a human approves it (``signoff --stage spec``,` |
| 4 | docstring | 3PWR-FR-006 | `3PWR-FR-006) nothing should be able to alter, add, or delete requirements unnoticed. At` |
| 6 | docstring | SLOCK-FR-001 | `sign-off ledger entry* (SLOCK-FR-001) — so tampering with the recorded hash is caught by` |
| 7 | docstring | SLOCK-NFR-002 | `the existing ``verify`` with no new trust primitive or entry kind (SLOCK-NFR-002).` |
| 8 | docstring | SLOCK-FR-003 | `Thereafter the ``spec_integrity`` gate (SLOCK-FR-003/004) and ``advance`` (SLOCK-FR-005)` |
| 8 | docstring | SLOCK-FR-005 | `Thereafter the ``spec_integrity`` gate (SLOCK-FR-003/004) and ``advance`` (SLOCK-FR-005)` |
| 10 | docstring | SLOCK-FR-006 | `hash (SLOCK-FR-006). Everything here is deterministic — bytes on disk plus committed` |
| 11 | docstring | SLOCK-NFR-001 | `ledger state, no model call, no network (SLOCK-NFR-001).` |
| 33 | docstring | SLOCK-FR-001 | `"""Raw-bytes SHA-256 of the full spec document (SLOCK-FR-001).` |
| 42 | docstring | SLOCK-FR-001 | `"""The extra payload recorded on a Spec-stage sign-off (SLOCK-FR-001).` |
| 45 | docstring | SLOCK-FR-007 | ```commit`` (when known) lets ``3pwr spec diff`` show a textual diff (SLOCK-FR-007).` |
| 58 | docstring | SLOCK-FR-002 | `"""The latest Spec-stage sign-off carrying a spec hash for ``spec_id`` (SLOCK-FR-002).` |
| 61 | docstring | SLOCK-FR-006 | `(SLOCK-FR-006). Sign-offs for other stages, for other specs, or without a` |
| 63 | docstring | SLOCK-FR-003 | ```None`` and the gate skips rather than blocks (SLOCK-FR-003).` |
| 106 | docstring | SLOCK-NFR-003 | `check is O(1) (SLOCK-NFR-003). When ``spec_path`` is not given, the path recorded` |
| 108 | docstring | SLOCK-FR-005 | `re-executes the check with no ``--spec`` argument (SLOCK-FR-005).` |
| 139 | docstring | SLOCK-FR-003 | `"""The ``spec_integrity`` gate (SLOCK-FR-003) — pass / fail(spec_modified) / skip.` |
| 142 | docstring | SLOCK-FR-004 | `any test executes (SLOCK-FR-004) — when the document changed after approval.` |

## engine/src/threepowers/steering.py (21)

| line | kind | match | excerpt |
|---|---|---|---|
| 5 | docstring | STEER-FR-001 | `* **File-based intent** (STEER-FR-001..004): the run's intent can come from a text file` |
| 9 | docstring | STEER-FR-002 | `the identical resolved intent (STEER-FR-002's property), and only the *resolved* text is recorded in` |
| 10 | docstring | STEER-FR-004 | `the ledger ``start`` entry (STEER-FR-004).` |
| 11 | docstring | STEER-FR-005 | `* **The three gate actions** (STEER-FR-005..008): at a human-gate pause the operator approves, rejects,` |
| 14 | docstring | STEER-NFR-003 | `revise-context block injected into the re-dispatched stage's prompt (STEER-NFR-003). Revise feedback` |
| 15 | docstring | STEER-FR-007 | `is resolved from inline-or-file by the SAME rule as the intent source (STEER-FR-007's property).` |
| 18 | docstring | STEER-NFR-003 | `and ledger format are untouched (STEER-NFR-003, 3PWR-NFR-001).` |
| 18 | docstring | 3PWR-NFR-001 | `and ledger format are untouched (STEER-NFR-003, 3PWR-NFR-001).` |
| 27 | comment | STEER-FR-006 | `# The step a revise re-dispatches per human gate (STEER-FR-006): the action step that OWNS the artifact` |
| 36 | comment | 3PWR-FR-037 | `),  # the evidence gate re-works the implementation (3PWR-FR-037)` |
| 41 | docstring | STEER-FR-003 | `"""Read a UTF-8 intent/feedback file; ``(text, "")`` or ``("", error)`` (STEER-FR-003).` |
| 63 | docstring | STEER-FR-002 | `(STEER-FR-002's property, reused verbatim for revise feedback per STEER-FR-007).` |
| 63 | docstring | STEER-FR-007 | `(STEER-FR-002's property, reused verbatim for revise feedback per STEER-FR-007).` |
| 74 | docstring | STEER-FR-001 | `"""The run's resolved intent from ``--file`` and/or the inline argument (STEER-FR-001/002).` |
| 76 | docstring | STEER-FR-003 | `Returns ``(resolved, "")`` or ``("", error)`` when the file is unusable (STEER-FR-003). The` |
| 88 | docstring | STEER-FR-007 | `"""Revise feedback resolved from inline-or-file by the SAME rule as the intent (STEER-FR-007).` |
| 100 | docstring | STEER-FR-006 | `"""The ``(step, stage)`` a revise at ``gate`` re-dispatches, or ``("", "")`` (STEER-FR-006)."""` |
| 105 | docstring | STEER-FR-005 | `"""The repo-relative path of the artifact under review at ``gate`` (STEER-FR-005), or ``""``.` |
| 126 | docstring | STEER-FR-005 | `"""The three human-gate actions, each with its copy-pasteable command (STEER-FR-005)."""` |
| 135 | docstring | STEER-FR-006 | `"""The deterministic prompt block a revise injects into the re-dispatched stage (STEER-FR-006).` |
| 138 | docstring | STEER-NFR-003 | `inputs so a revision reproduces byte-identically from the recorded feedback (STEER-NFR-003)."""` |

## engine/src/threepowers/style.py (40)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | INITX-FR-013 | `"""Colorized, package-manager-style CLI output + a structured-output toolkit (INITX-FR-013/014, CLIUX, TRIX).` |
| 6 | docstring | 3PWR-NFR-001 | `(3PWR-NFR-001, INITX-FR-014). Every ANSI escape this module emits is generated by ``rich`` style` |
| 6 | docstring | INITX-FR-014 | `(3PWR-NFR-001, INITX-FR-014). Every ANSI escape this module emits is generated by ``rich`` style` |
| 7 | docstring | TRIX-FR-002 | `primitives (TRIX-FR-002/008; CLIUX-FR-003 as amended) — no hand-rolled SGR construction — and the` |
| 7 | docstring | CLIUX-FR-003 | `primitives (TRIX-FR-002/008; CLIUX-FR-003 as amended) — no hand-rolled SGR construction — and the` |
| 8 | docstring | INITX-NFR-004 | `styler degrades to a no-op when color is off (INITX-NFR-004 — its absence never fails a command).` |
| 9 | docstring | CLIUX-NFR-003 | `No network is ever touched (CLIUX-NFR-003, TRIX-NFR-001).` |
| 9 | docstring | TRIX-NFR-001 | `No network is ever touched (CLIUX-NFR-003, TRIX-NFR-001).` |
| 12 | docstring | CLIUX-FR-001 | `(CLIUX-FR-001): section headers, key/value blocks, aligned tables, status rows, dividers, and wrapped` |
| 15 | docstring | CLIUX-FR-002 | `(CLIUX-FR-002). Meaning is never carried by color alone: a glyph or word always accompanies it, and an` |
| 16 | docstring | CLIUX-NFR-004 | `ASCII glyph set is used when the stream cannot encode the Unicode marks (CLIUX-NFR-004).` |
| 31 | comment | TRIX-FR-002 | `# The semantic style vocabulary, each name a rich Style (TRIX-FR-002). rich renders the standard` |
| 55 | comment | CLIUX-NFR-004 | `# ASCII fallbacks for a stream whose encoding cannot represent the Unicode marks (CLIUX-NFR-004).` |
| 70 | docstring | CLIUX-FR-002 | `"""The text with every ANSI SGR sequence removed (CLIUX-FR-002)."""` |
| 75 | docstring | CLIUX-FR-002 | `"""The printable width of ``text`` — its length ignoring ANSI color sequences (CLIUX-FR-002)."""` |
| 93 | docstring | CLIUX-NFR-004 | `"""Whether ``stream``'s encoding can represent the Unicode status/progress marks (CLIUX-NFR-004)."""` |
| 109 | docstring | INITX-FR-014 | `"""Whether to emit ANSI color for human output (INITX-FR-014, CLIUX-FR-014).` |
| 109 | docstring | CLIUX-FR-014 | `"""Whether to emit ANSI color for human output (INITX-FR-014, CLIUX-FR-014).` |
| 113 | docstring | INITX-FR-014 | `(INITX-FR-014). The resolution order then follows the CLIUX-FR-014 precedence — environment over` |
| 113 | docstring | CLIUX-FR-014 | `(INITX-FR-014). The resolution order then follows the CLIUX-FR-014 precedence — environment over` |
| 116 | docstring | CLIUX-FR-003 | `environment-layer fallback (TRIX, CLIUX-FR-003 as amended); then ``color_mode``` |
| 141 | docstring | CLIUX-FR-001 | `structured-output toolkit (CLIUX-FR-001). Every escape byte is generated by ``rich``` |
| 142 | docstring | TRIX-FR-002 | `(TRIX-FR-002/008) — this class holds no SGR knowledge of its own.` |
| 145 | docstring | INITX-FR-014 | `styler — that keeps the ``--json`` payload byte-identical with and without color (INITX-FR-014,` |
| 146 | docstring | TRIX-FR-006 | `TRIX-FR-006). ``ascii_only`` swaps the Unicode glyphs for an ASCII set when the stream cannot` |
| 147 | docstring | CLIUX-NFR-004 | `encode them (CLIUX-NFR-004); it defaults off, so a directly-constructed ``Styler`` still uses` |
| 155 | docstring | TRIX-FR-002 | `returned unchanged otherwise or when no name maps (TRIX-FR-002)."""` |
| 202 | comment | CLIUX-FR-001 | `# ----------------------------------------------------------- structured-output toolkit (CLIUX-FR-001)` |
| 204 | docstring | CLIUX-FR-006 | `"""A self-identifying section header (CLIUX-FR-006): an emphasized title + optional dim subject."""` |
| 212 | docstring | CLIUX-FR-001 | `"""A horizontal divider (CLIUX-FR-001)."""` |
| 219 | docstring | CLIUX-FR-005 | `uses, so a given status reads the same everywhere (CLIUX-FR-005). Color is never the sole` |
| 220 | docstring | CLIUX-NFR-004 | `signal: the glyph (or its ASCII fallback) and the text always carry the meaning (CLIUX-NFR-004)."""` |
| 227 | docstring | CLIUX-FR-001 | `"""An aligned key/value block (CLIUX-FR-001/004): dim labels padded to a common width, then the` |
| 228 | docstring | CLIUX-FR-004 | `value. Multi-field results render here instead of as one run-on line (CLIUX-FR-004)."""` |
| 242 | docstring | CLIUX-FR-001 | `"""Aligned columns (CLIUX-FR-001/004). Column widths use the *visible* cell width, so colored` |
| 244 | docstring | CLIUX-FR-002 | `stripped (CLIUX-FR-002)."""` |
| 269 | docstring | CLIUX-FR-004 | `"""A wrapped bullet list (CLIUX-FR-004): long items wrap to the terminal width, never one line."""` |
| 288 | docstring | CLIUX-NFR-004 | `matches what ``stream`` can encode (CLIUX-NFR-004)."""` |
| 303 | docstring | CLIUX-FR-013 | `"""The effective human-output verbosity (CLIUX-FR-013/014): ``quiet`` \| ``normal`` \| ``verbose``.` |
| 307 | docstring | CLIUX-FR-014 | `the more-informative ``verbose`` wins. A pure function of its inputs (CLIUX-FR-014 property)."""` |

## engine/src/threepowers/transcripts.py (11)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | AUTOX-FR-008 | `"""Persisted per-attempt agent transcripts, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).` |
| 1 | docstring | AUTOX-NFR-002 | `"""Persisted per-attempt agent transcripts, credential-redacted (AUTOX-FR-008, AUTOX-NFR-002).` |
| 7 | docstring | EXEC-FR-012 | `environment passed through to the child agent process is untouched (EXEC-FR-012 / RUNLIVE-FR-009).` |
| 7 | docstring | RUNLIVE-FR-009 | `environment passed through to the child agent process is untouched (EXEC-FR-012 / RUNLIVE-FR-009).` |
| 22 | comment | AUTOX-NFR-002 | `# Environment-variable NAMES whose values are treated as credentials (AUTOX-NFR-002). Deliberately` |
| 31 | docstring | AUTOX-NFR-002 | `"""The environment values that look like credentials, longest first (AUTOX-NFR-002).` |
| 54 | docstring | PHASEPR-FR-005 | `"""The last ``limit`` bytes of a transcript, decoded leniently (PHASEPR-FR-005).` |
| 67 | comment | PHASEPR-FR-005 | `# The clarify phrases the stall scan matches case-insensitively (PHASEPR-FR-005). Deliberately few` |
| 75 | docstring | PHASEPR-FR-005 | `(PHASEPR-FR-005) — a pure, deterministic predicate.` |
| 95 | docstring | AUTOX-NFR-002 | `"""A minimal text sink that redacts credential values before every write (AUTOX-NFR-002).` |
| 115 | docstring | AUTOX-FR-008 | `"""Allocates the per-attempt transcript files for one run (AUTOX-FR-008).` |

## engine/src/threepowers/verdict.py (11)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | 3PWR-NFR-001 | `Same code → same verdict regardless of which model authored it (3PWR-NFR-001), and` |
| 4 | docstring | 3PWR-FR-033 | `the shape does not vary by language (3PWR-FR-033). Every failure is actionable: it` |
| 5 | docstring | 3PWR-FR-034 | `names a class and the offending requirement/file/branch (3PWR-FR-034). A human can` |
| 7 | docstring | 3PWR-NFR-011 | `(3PWR-NFR-011).` |
| 20 | comment | 3PWR-FR-026 | `# Cheapest-first canonical gate order (3PWR-FR-026, spec §8). The trailing gates are` |
| 21 | comment | 3PWR-FR-058 | `# work-kind-shaped (3PWR-FR-058): they join the suite only when the inferred kind pulls` |
| 22 | comment | 3PWR-FR-008 | `# them in — ``defect_regression`` for a defect (3PWR-FR-008), the design oracles for design` |
| 23 | comment | 3PWR-FR-009 | `# work (3PWR-FR-009) — and never replace a tier gate.` |
| 71 | comment | 3PWR-FR-052 | `report_only: bool = False  # advisory run: emit but do not block (3PWR-FR-052)` |
| 74 | comment | 3PWR-FR-058 | `)  # inferred kinds shaping the suite (3PWR-FR-058)` |
| 108 | docstring | 3PWR-FR-034 | `"""Build an actionable failure record (3PWR-FR-034).` |

## engine/src/threepowers/verify.py (10)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-040 | `"""Ledger verification: recompute the hash chain and signatures (3PWR-FR-040).` |
| 4 | docstring | 3PWR-NFR-004 | `(3PWR-NFR-004) and fails on *any* tamper, gap, or break: a mutated payload changes` |
| 52 | docstring | HARDN-FR-004 | `Key continuity (HARDN-FR-004): the active ledger key starts at the genesis key and changes` |
| 55 | docstring | HARDN-NFR-003 | `before (HARDN-NFR-003); with rotations, the committed key must be the last successor, else` |
| 59 | docstring | 3PWR-FR-021 | `judiciary (oracle) identity that signs the isolated-dispatch attestation (3PWR-FR-021/039).` |
| 60 | docstring | 3PWR-NFR-004 | `Absent extra keys are simply skipped, so single-key repos verify unchanged (3PWR-NFR-004)."""` |
| 66 | comment | 3PWR-FR-040 | `# keystone verify fails *closed* with a named, locatable problem (3PWR-FR-040/NFR-011)` |
| 66 | format-example | NFR-011 | `# keystone verify fails *closed* with a named, locatable problem (3PWR-FR-040/NFR-011)` |
| 85 | comment | HARDN-NFR-003 | `# the committed key IS the genesis key and behavior is unchanged (HARDN-NFR-003).` |
| 153 | comment | HARDN-FR-004 | `#    successor in the rotation chain (HARDN-FR-004, SC-001).` |

## engine/src/threepowers/workkind.py (5)

| line | kind | match | excerpt |
|---|---|---|---|
| 1 | docstring | 3PWR-FR-058 | `"""Work-kind inference (3PWR-FR-058) — shape the tier + oracle strategy, never the sign-off.` |
| 4 | docstring | 3PWR-NFR-001 | `(keyword heuristics — no model call, so it never perturbs the deterministic verdict, 3PWR-NFR-001). A` |
| 6 | docstring | 3PWR-FR-006 | `approves the spec (3PWR-FR-006) and signs off on the evidence (3PWR-FR-037). Per-kind gate shaping` |
| 6 | docstring | 3PWR-FR-037 | `approves the spec (3PWR-FR-006) and signs off on the evidence (3PWR-FR-037). Per-kind gate shaping` |
| 88 | docstring | 3PWR-FR-058 | `"""Infer work kind(s) + a suggested risk tier from free-form intent (deterministic, 3PWR-FR-058)."""` |

## engine/src/threepowers/workspace.py (27)

| line | kind | match | excerpt |
|---|---|---|---|
| 3 | docstring | PHASE-FR-001 | `SRCX (spec 017) supersedes PHASE-FR-001's folder split: every lifecycle stage's artifact for a run lies` |
| 3 | docstring | (spec 017) | `SRCX (spec 017) supersedes PHASE-FR-001's folder split: every lifecycle stage's artifact for a run lies` |
| 4 | docstring | SRCX-FR-001 | `flat in that run's feature folder ``specs/<NNN>-<slug>/`` (SRCX-FR-001)::` |
| 10 | docstring | SRCX-FR-005 | `oracle.md        # a *record* linking the authored oracle tests (SRCX-FR-005)` |
| 11 | docstring | SRCX-FR-005 | `implement.md     # a *record* linking the implementation changes (SRCX-FR-005)` |
| 13 | docstring | SRCX-FR-002 | `Both legacy layouts stay resolvable and runnable for existing features (SRCX-FR-002/003, SRCX-NFR-003):` |
| 13 | docstring | SRCX-NFR-003 | `Both legacy layouts stay resolvable and runnable for existing features (SRCX-FR-002/003, SRCX-NFR-003):` |
| 18 | docstring | SRCX-FR-008 | `The engine auto-allocates the ``<NNN>-<slug>`` run folder (SRCX-FR-008/009): ``<NNN>`` is the maximum` |
| 21 | docstring | 3PWR-NFR-001 | `no network, no model, no ledger (3PWR-NFR-001, SRCX-NFR-001).` |
| 21 | docstring | SRCX-NFR-001 | `no network, no model, no ledger (3PWR-NFR-001, SRCX-NFR-001).` |
| 29 | comment | SRCX-FR-001 | `# The legacy PHASE (spec 013) workspace subfolders — still resolvable, never written (SRCX-FR-001/002).` |
| 29 | comment | (spec 013) | `# The legacy PHASE (spec 013) workspace subfolders — still resolvable, never written (SRCX-FR-001/002).` |
| 34 | comment | SRCX-FR-004 | `# feature folder (SRCX-FR-004). Pure gate / verdict / sign-off / advance steps stay ledger-only` |
| 35 | comment | SRCX-FR-007 | `# (SRCX-FR-007).` |
| 38 | comment | SRCX-FR-009 | `# Slug bounds (SRCX-FR-009): a fixed maximum length, and a fixed fallback token when the intent` |
| 45 | docstring | SRCX-FR-002 | `"""The feature's single specification file, whichever layout (SRCX-FR-002).` |
| 66 | docstring | SRCX-FR-003 | `"""The PHASE split layout's artifact subfolder — resolvable for legacy features only (SRCX-FR-003)."""` |
| 71 | docstring | SRCX-FR-001 | `"""Where a producing step's artifact is WRITTEN — flat in the feature folder (SRCX-FR-001).` |
| 81 | docstring | SRCX-FR-003 | `"""An existing stage artifact — the flat path when it exists, else the split fallback (SRCX-FR-003).` |
| 100 | docstring | SRCX-FR-002 | `keeping the exactly-one property across a mixed-layout tree (SRCX-FR-002)."""` |
| 114 | docstring | GDIAG-FR-002 | `"""Resolve a feature workspace folder from its number: ``specs/<nnn>-*/`` (GDIAG-FR-002).` |
| 140 | comment | SRCX-FR-008 | `# --------------------------------------------------------------------------- run-folder allocation (SRCX-FR-008/009)` |
| 142 | docstring | SRCX-FR-009 | `"""Derive the run folder's slug from the intent — deterministic, pure, idempotent (SRCX-FR-009).` |
| 154 | docstring | SRCX-FR-008 | `"""The next ``<NNN>`` under ``specs/``: the maximum existing ``NNN-`` prefix plus one (SRCX-FR-008)."""` |
| 165 | docstring | SRCX-FR-008 | `"""The ``<NNN>-<slug>`` folder name a new run allocates (SRCX-FR-008) — a pure function of the` |
| 166 | docstring | SRCX-NFR-001 | ```specs/`` directory listing and the intent string, byte-identical on any machine (SRCX-NFR-001)."""` |
| 171 | docstring | SRCX-FR-008 | `"""Allocate the new run's feature folder ``specs/<NNN>-<slug>/`` (SRCX-FR-008).` |

