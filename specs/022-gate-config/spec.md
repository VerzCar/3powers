# Feature Specification: Configurable Gates — Per-Project Tool Overrides, Native-Tooling Auto-Detection, Opt-In Auto-Fix, and the Effective-Config View

**Spec ID**: GATECFG
<!-- A short uppercase id unique to this spec. Requirement IDs are namespaced with it (3PWR-FR-059).
     GATECFG makes the gate suite's TOOLING configurable per project without ever touching the gate
     SET: a committed `.3powers/config/gates.yaml` deep-merges per-gate keys over the adapter
     manifest; a lightweight startup probe auto-detects the project's native tools (biome/prettier,
     eslint, tsc/pyright, vitest/jest/playwright, go test/gofmt) for gates the file does not
     override; an opt-in `--auto-fix` flag runs a configured `fix_cmd` for the format/lint gates
     only — fix, announce, re-check — with the fixed paths joining the run's produced set; and
     `3pwr gate config show` renders the effective per-gate configuration with its source, without
     executing anything. Cross-refs: 3PWR-FR-026/032/027, 3PWR-NFR-007, GATEPIPE-FR-003 (the
     fix-hint panel), GITX-FR-008 (produced paths ride the stage commit). Configuration replaces
     TOOLS, never gates: the risk tier alone decides which gates run, and nothing here weakens one
     (recorded decision SEC-002). Auto-fix is opt-in only — agent output is never silently mutated
     mid-run (recorded decision SEC-001). No trust-spine module (canonical/keys/ledger/verify/
     speclock/anchor) is touched. -->

**Risk Tier**: Standard
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Rationale: this
     changes which COMMANDS the adapter gates execute (config merge, detection, fix/re-check), so
     the machine contracts — the verdict schema, the `--json` payload purity, the gate set per tier
     — must hold under test; Cosmetic was rejected for that reason. High-risk was rejected: no
     trust-spine module changes, no gate is added, removed, or weakened (3PWR-FR-032), and every
     new behavior is deterministic given the tree + config. -->

**Status**: Draft

**Input**: Plan 030, Track C (GATECFG): the engine hard-codes each adapter's test runner,
formatter, and type-checker (vitest/biome/tsc for TypeScript, …). Enterprise projects already have
their own tool choices (jest, playwright, prettier, eslint, pyright, go test, gofmt…); adopting
3Powers today means adopting unwanted tools. Teams need to point a gate at their own command —
committed, shared, and visible — while the judiciary's gate set stays exactly what the tier says.

---

## Non-Goals *(mandatory — 3PWR-FR-004)*

- Does **not** change which gates run, their order, any tier threshold, or how pass/fail is
  judged (3PWR-FR-026/032) — configuration replaces the TOOL a gate invokes, never the gate.
- Does **not** run any fix by default: `--auto-fix` is opt-in only, so an agent's produced output
  is never silently mutated mid-run (recorded decision).
- Does **not** make `gates.yaml` a personal override: it is committed, versioned team
  configuration under `.3powers/config/`, seeded by `3pwr init`.
- Does **not** touch the verdict schema, the ledger, signing, exit codes, or the `--json` payload
  purity — the detection line and the auto-fixed line are human output only.
- Does **not** hardcode language assumptions into the core's gate names or gate engine — the
  detection probes are declarative data, in keeping with the adapter contract (3PWR-NFR-007).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The project pins its own tools (Priority: P1)

A team whose test runner is `npm run test:unit` (not the adapter's default) commits a
`.3powers/config/gates.yaml` overriding `tests.cmd`; every subsequent gate run — everyone's,
identically — executes their command, while every other gate keeps the adapter's defaults.

**Acceptance Scenarios**:

1. **Given** a `gates.yaml` overriding only `tests.cmd`, **When** the gate suite runs, **Then**
   the tests gate executes the overridden command and every other gate is unchanged.
2. **Given** an override setting only one key of a gate block, **When** the configuration is
   assembled, **Then** the gate's other keys keep their adapter values (per-key merge, not
   block replacement).

### User Story 2 - The engine meets the project where it is (Priority: P1)

A project that already uses jest (or prettier, eslint, tsc, playwright, or the Go toolchain) gets
those tools picked up automatically: one startup line names what was detected, and the run uses
the project's native tooling without any configuration.

**Acceptance Scenarios**:

1. **Given** a project with only `jest.config.ts`, **When** the gate run starts, **Then** the
   tests gate runs jest; **Given** `vitest.config.ts` instead, **Then** it runs vitest.
2. **Given** a `gates.yaml` override for a gate AND a detectable native tool for the same gate,
   **When** the configuration is assembled, **Then** the `gates.yaml` command wins.
3. **Given** `--json`, **When** the run completes, **Then** no detection line enters the output.

### User Story 3 - Opt-in auto-fix keeps the run green (Priority: P2)

An operator running with `--auto-fix` lets a failing format/lint check apply its configured fix
command, announce it, and re-check — a clean re-check turns the gate green and the fixed files
join the run's produced set; without the flag, the failure stands and the fix is only a hint.

**Acceptance Scenarios**:

1. **Given** `--auto-fix` and a failing format check with a configured `fix_cmd`, **When** the
   gate runs, **Then** the fix runs, the auto-fixed line prints, the check re-runs, and a passing
   re-check yields a green gate whose fixed paths are recorded for the run's produced set.
2. **Given** no `--auto-fix`, **When** the same check fails, **Then** the gate fails on the first
   check and the fix command surfaces only as the failure panel's hint.
3. **Given** a `fix_cmd` configured on a non-fixable gate (types/tests/mutation), **When** the
   configuration is assembled and the suite runs, **Then** that fix command is never executed.

### Edge Cases

- `gates.yaml` absent, empty, or fully commented → the adapter manifest applies unchanged.
- A detected tool that is already the adapter's tool for that gate → the adapter's richer command
  (coverage settings, shell guards, `requires:`) is kept; detection confirms, never degrades.
- The fix command fails or fixes nothing → the re-check fails and the gate reports normally.
- A target that is not a git repository → auto-fix still fixes and re-checks; the produced-paths
  record degrades to empty, never crashes.
- `gate config show` on a project with no `gates.yaml` and nothing detectable → every row is
  tagged with the adapter source.

## Requirements *(mandatory)*

### Functional Requirements

- **GATECFG-FR-001**: The engine shall read `.3powers/config/gates.yaml` — committed, versioned
  team configuration — when loading an adapter manifest and deep-merge its per-gate keys over the
  manifest's `gates:` blocks: one per-key update per gate block, where only keys present in the
  file override and absent gates/keys keep the adapter values.
  - *Acceptance*: overriding `tests.cmd` changes exactly that key; the tests gate's other keys and
    every other gate are byte-identical to the adapter manifest.
- **GATECFG-FR-002**: `3pwr init` shall seed `.3powers/config/gates.yaml` with commented-out
  example overrides (format/lint check+fix commands, the types command, the tests command with its
  coverage format and path), never clobbering an existing file.
  - *Acceptance*: a fresh init produces the seed file; re-running init leaves a hand-edited one
    untouched; the seed, unedited, changes no gate behavior.
- **GATECFG-FR-003**: The effective gate configuration shall be assembled with the fixed
  precedence `gates.yaml` > auto-detection > adapter manifest.
  - *Acceptance*: with all three sources configuring the same gate, the `gates.yaml` command runs;
    with only detection and the manifest, the detected tool wins.
- **GATECFG-FR-004**: At gate-run startup — once per run, and only for gates `gates.yaml` does not
  override — the engine shall probe the target for native tooling via a declarative first-match
  table: format → `biome.json` ⇒ biome, `.prettierrc`/`prettier.config.*` ⇒ prettier; lint →
  `biome.json` ⇒ biome, `.eslintrc*`/`eslint.config.*` ⇒ eslint; types → `tsconfig.json` ⇒ tsc,
  `pyproject.toml` containing `[tool.pyright]` ⇒ pyright; tests → `vitest.config.*` ⇒ vitest,
  `jest.config.*` ⇒ jest, `playwright.config.*` ⇒ playwright; and `go.mod` ⇒ `go test ./...`
  (tests) and `gofmt -l .` (format). A detected tool the adapter already configures for that gate
  keeps the adapter's richer command — detection confirms, never degrades a configured gate.
  - *Acceptance*: a project with only `jest.config.ts` runs jest for tests; one with
    `vitest.config.ts` runs vitest; a Go adapter target keeps its coverage-emitting test command.
- **GATECFG-FR-005**: When detection selected at least one tool, the gate run shall print exactly
  one startup line naming each detected gate=tool pair (e.g.
  `auto-detected gates:  format=biome  tests=vitest  types=tsc`); nothing prints when nothing was
  detected, and the line never enters the `--json` output.
  - *Acceptance*: a run detecting biome+vitest prints one line naming both; a `--json` run's
    stdout parses as the unchanged machine payload with no detection line.
- **GATECFG-FR-006**: The adapter `gates:` schema shall accept a `fix_cmd` key for the format and
  lint gates only; a `fix_cmd` configured on any other gate (types, tests, mutation, …) shall be
  discarded at configuration assembly and never executed.
  - *Acceptance*: a `gates.yaml` putting `fix_cmd` under `tests` yields an effective config
    without it, and no fix ever runs for that gate.
- **GATECFG-FR-007**: `3pwr gate run` and `3pwr run` shall accept an `--auto-fix` flag; auto-fix
  shall be opt-in only and never the default, so produced output is never silently mutated
  (recorded security decision).
  - *Acceptance*: both commands parse the flag; omitting it yields byte-identical gate behavior to
    the pre-GATECFG engine.
- **GATECFG-FR-008**: With `--auto-fix` active, a format/lint gate whose check command fails and
  whose configuration carries a `fix_cmd` shall: run the fix command, announce
  `↳ auto-fixed by <tool>` in the human output, and re-run the check command; a passing re-check
  makes the gate green and records the fixed paths on the gate's result so they join the run's
  produced set (and thus the stage commit — ref GITX-FR-008); a failing re-check reports the
  failure normally.
  - *Acceptance*: a fixable format failure under `--auto-fix` ends green with the fixed file
    recorded in the gate's details and the auto-fixed line in the human output; an unfixable one
    ends red with the standard failure surface.
- **GATECFG-FR-009**: Without `--auto-fix`, a failing format/lint gate shall fail on its first
  check; the configured `fix_cmd` shall surface only as the failure panel's suggested manual fix
  (ref GATEPIPE-FR-003), never execute.
  - *Acceptance*: the same fixable failure without the flag is red, its panel carries the
    `↳ auto-fix:` hint, and the working tree is untouched by the engine.
- **GATECFG-FR-010**: `3pwr gate config show [--adapter <name>]` shall render the effective
  per-gate configuration — gate, tool, check command, fix command, and a source tag naming where
  each gate's configuration came from (the adapter manifest, `gates.yaml`, or auto-detection) —
  without executing any gate command.
  - *Acceptance*: a project with a `gates.yaml` tests override and a detectable formatter shows
    the tests row tagged as the override, the format row tagged as detected, and the rest tagged
    as the adapter; no gate command runs.

### Non-Functional Requirements

- **GATECFG-NFR-001**: Configuration shall replace tools, never gates: the risk tier alone decides
  which gates run, no override/detection/fix path can remove or weaken a tier gate, and the
  assembled configuration is deterministic given the tree + config files (ref 3PWR-FR-032,
  3PWR-NFR-001).
  - *Acceptance*: the required gate set for a tier is identical with and without `gates.yaml` and
    detection; two assemblies over identical inputs are equal.

## Success Criteria *(mandatory)*

- **GATECFG-SC-001**: A project overriding `tests.cmd` to `npm run test:unit` passes its gate run
  using that command.
- **GATECFG-SC-002**: Auto-detection selects jest when `jest.config.ts` is present and no
  `vitest.config.*` exists.
- **GATECFG-SC-003**: `--auto-fix` on a fixable formatting failure runs the fix, re-checks, and
  turns the gate green; without the flag the same failure is red with a hint.
- **GATECFG-SC-004**: `gate config show` reveals the effective configuration with correct source
  tags, executing nothing.
- **GATECFG-SC-005**: Every functional requirement has ≥1 linked verification (3PWR-FR-030/065) —
  a test naming the GATECFG-FR id.

## Sign-off *(3PWR-FR-006 — recorded human approver before implementation begins)*

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id GATECFG --stage spec --spec specs/022-gate-config/spec.md`; appended to the signed ledger)_ | | |
