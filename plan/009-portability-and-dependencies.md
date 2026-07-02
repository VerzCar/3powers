# Plan 009 — Portability & dependency stability (A1/A3, FR-044/046/048, NFR-014)

> **Cold-start note.** Read [`docs/STATUS.md`](../docs/STATUS.md) first, then the spec
> [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (the law). Plans 001–008 delivered v0.1, v0.5, and most
> of v1.0's judiciary (through **structural oracle independence**, plan 008). This plan advances the
> **agnosticism/ecosystem** side of v1.0: run everywhere Spec Kit runs, and stay stable across third-party
> releases.

## Context — why this is next

Two owner-driven requirements shape this plan:

1. **3Powers must run everywhere Spec Kit runs — not Copilot-only.** The spec's promise (A1, A3,
   FR-044/046, NFR-014) is that 3Powers ships as Spec Kit **extensions/presets/workflows via catalogs** and
   reuses Spec Kit's **integration registry + headless `workflow run` dispatch** — never a Copilot-specific
   harness. Today the *engine* is already provider-agnostic (no LLM API calls; roles bind to model
   *families* in config), but the *dispatch + packaging* layer is interactive-Copilot-shaped (STATUS marks
   FR-012/013 ◑). Spec Kit's own model is `integration: "auto"` with an advisory `any: [...]` hint (see
   `.specify/workflows/speckit/workflow.yml`) — the workflow runs against *any* integration providing the
   core commands. We package to that model.
2. **Third-party dependencies must be pinnable and drift-detectable.** Today pins live only in lockfiles
   (`engine/uv.lock`, `package-lock.json`) and an *advisory* AGENTS.md table (Spec Kit `0.11.6.dev0`, etc.).
   Nothing detects the *installed* Spec Kit / adapter-tool / scanner versions and flags drift from a
   known-good range. A new Spec Kit release could silently break 3Powers. We add a configurable
   supported-versions manifest + a check that flags drift (fix to a stable version; surface when an
   upstream release needs adaptation).

Sequenced: **(A) dependency compatibility** is the stability foundation; **(B) provider-agnostic packaging**
builds on it. The *live* cross-integration headless dispatch (running the judiciary under a non-Copilot
agent, isolated) still needs the Spec Kit runtime + a configured non-Copilot integration to verify
end-to-end — that verification is the documented residual; everything built here is unit-testable now.

## Scope

**In — (A) Dependency compatibility & pinning (FR-048, NFR-014, NFR-015 pattern):**
- `.3powers/config/dependencies.yaml` — supported version ranges + known-good pins + a per-component
  `on_drift: warn|block|ignore` policy for Spec Kit, the scanners, and the adapter toolchains.
- `engine/src/threepowers/deps.py` — a dependency-free version comparator + a probe/check that reports
  each component as `ok | drift | missing | unknown`.
- `3pwr deps-check` — probes installed versions, prints a table, exits non-zero only on a `block`-policy
  drift/absence. A **preflight command**, deliberately *not* a verdict gate (its result is
  environment-dependent, so keeping it out of the verdict preserves determinism — NFR-001).

**In — (B) Provider-agnostic packaging (A1, A3, FR-044/046):**
- `.specify/extensions/3powers/extension.yml` (+ registry + `extensions.yml` hooks) — a real Spec Kit
  extension that provides the `/3pwr.*` judiciary commands and wires the gates via `after_*` hooks,
  distributable through Spec Kit catalogs. Uses the `integration: auto` / advisory-`any` model — never
  hardcodes an integration.
- Make role/dispatch config + the oracle/review agents **substrate-neutral** (Spec Kit integration of the
  user's choice; Copilot demoted to *an example*), keeping the model-family diversity law intact.
- Eval cases (FR-050, via the existing `must_contain`/`must_not_contain`) that gate substrate-neutrality
  and the extension manifest — so a regression to a Copilot-only assumption fails `3pwr eval`.

**Out (→ plan 010+):** the *live* multi-integration headless `workflow run` dispatch verification (needs the
Spec Kit runtime + a non-Copilot integration configured); A3 physical oracle read-path isolation (still the
FR-021 residual); observe/feedback (§13); a third adapter; catalog *publishing* (as opposed to the in-repo
extension). Machine-enforcing exact lockfile version equality is out — we check *ranges*, not lock bytes.

## Decisions (proposed — revisit if you find better)

| Area | Proposal | Rationale |
|---|---|---|
| **deps-check placement** | A standalone **preflight command** (like `verify`), not a verdict gate; may be surfaced advisorily. | Installed-tool versions are environment-dependent; putting them in the verdict would break determinism (NFR-001), same reasoning as the oracle advisory. |
| **Version comparator** | A small, **dependency-free** parser: leading dotted-int release, suffixes (`.dev0`, `-rc1`) ignored for range compares; clauses `>=,<=,>,<,==,!=` AND-ed. | Keep the engine's runtime deps to `cryptography`+`PyYAML` (NFR); PEP 440 in full is overkill for "is X within a supported range". |
| **Probe model** | Each component declares a full `probe` command (e.g. `specify version`, `uv run ruff --version`); the engine runs it and extracts the first version token. Absent tool → `missing`. | Mirrors the adapter/scanner pattern (`run_cmd` + `shutil.which`); the manifest author controls how each tool is probed (global vs project-local). |
| **Extension packaging** | Author a **real** `.specify/extensions/3powers/extension.yml` modelled on the in-repo `agent-context` extension; wire the existing `/3pwr.*` commands as `after_*` hooks. | The format is present and copyable; reuses confirmed Spec Kit primitives (A1) rather than inventing packaging. |
| **Provider-agnosticism** | Rely on Spec Kit's `integration: "auto"` + advisory `any: [...]`; keep `roles.yaml` about model *families* (the diversity law) and make prose substrate-neutral. | Matches Spec Kit's own workflow model; the engine already makes no provider calls (A3). |

## Workstreams

1. **`deps.py` + comparator + `dependencies.yaml`.** `parse_release`, `satisfies(version, spec)`
   (comma-AND of `>=,<=,>,<,==,!=`); `run_probe(cmd, root)` (reuses `adapters.run_cmd` + `shutil.which`);
   `check_dependencies(manifest, probe) -> DepsReport` (injectable probe → deterministic tests) classifying
   each component `ok|drift|missing|unknown` and computing an overall block/ok per policy. Ship
   `.3powers/config/dependencies.yaml` covering Spec Kit + gitleaks/osv-scanner/semgrep + the python & TS
   adapter toolchains.
2. **CLI `deps-check`.** `cmd_deps_check` (loads the manifest or `--manifest`; `--strict` treats warn as
   block; `--json`), a table of `component: installed vs supported → status`, exit 1 only on a block-policy
   failure. Register the subparser.
3. **Spec Kit extension packaging.** `.specify/extensions/3powers/extension.yml` (provides the `/3pwr.*`
   commands; `after_tasks → 3pwr.oracle`, `after_implement → 3pwr.verify` hooks), a `commands/` shim,
   register in `.specify/extensions/.registry` + `.specify/extensions.yml`. Provider-agnostic
   (`integration: auto`).
4. **Substrate-neutral config + eval gates.** Rewrite the Copilot-specific comment in
   `.3powers/config/roles.yaml` and the "switch the Copilot chat model" lines in the oracle/review agents to
   name the *chosen Spec Kit integration* (Copilot as one example). Add `.3powers/eval/cases.yaml` cases
   asserting the extension manifest provides the commands and that role config states the provider-agnostic
   (A3) promise — regressions fail `3pwr eval`.
5. **Tests + self-application + docs.** `test_deps.py` (comparator edge cases; check with an injected probe
   for ok/drift/missing × warn/block; CLI exit codes with a temp manifest). Keep the engine green and the
   High-risk self-application green; run `3pwr eval` green. Add FR-044/046/048 acceptance to
   `specs/002-engine-trust-spine/spec.md`; update `docs/STATUS.md`, `CLAUDE.md`, `AGENTS.md`, the CLI
   reference, and `docs/references/speckit.md` (extension now real).

## New `3pwr` surface (proposed)

```
3pwr deps-check [--manifest .3powers/config/dependencies.yaml] [--strict] [--json]   # FR-048/NFR-014
```

## Verification (definition of done)

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)      # engine green (+ test_deps.py)
3pwr deps-check                       # probes Spec Kit + scanners + adapter tools; warns/blocks on drift
3pwr eval                             # substrate-neutrality + extension cases pass (FR-050)
# self-application stays green at Standard AND High-risk (NFR-006).
```
Done when: `deps-check` flags a drifted/absent dependency per its policy and passes a known-good environment;
the 3Powers Spec Kit extension is registered and provider-agnostic (`integration: auto`, no hardcoded
Copilot); `3pwr eval` gates substrate-neutrality; the engine self-applies green; `docs/STATUS.md` records
plan 009 (FR-044/046/048 ✅ at the config/packaging level; live multi-integration dispatch noted as the
residual).

## How to work here

- **The spec is the law.** Validate against §3 (constraints A1–A3), §10–§11 (agnosticism/config); respect
  §17 phasing (v1.0). Don't over-claim: the *live* cross-integration dispatch stays a documented residual.
- **Determinism (NFR-001).** `deps-check` is a preflight command, never a verdict gate.
- **No inline gate suppressions**; keep the engine green under its own gates.
- Each new test cites its FR id; add implemented requirements to `specs/002-*/spec.md`.
- Commit on the `plan-009-portability-and-dependencies` branch.
