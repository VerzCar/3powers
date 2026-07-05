# 3Powers — Project Status & Handoff

## At a glance

| | |
|---|---|
| **Current milestone** | **v0.5 complete; v1.0 in progress** (spec §17 phasing; plans 001–028 delivered) |
| **Architecture (plans 018–022, current)** | **3Powers owns its executive** — `3pwr run` drives headless coding agents *directly* via a native, provider-agnostic runner (**EXEC**, spec 009), and **GitHub Spec Kit is removed** (**SLIM**, spec 010; epic A1′/A3′/§16 amended). The judiciary is unchanged. The solution + roadmap are documented in the epic ([§17 native-executive track](../specs/3Powers_Spec_v0.2.md)) and in §6 below. **RUNLIVE** (spec 011, plan 021) hardened the executive — per-stage artifact contracts, retry/timeout/streamed dispatch + `--json` per-stage results, a gated live end-to-end proof, an async hosted backend, and commit checkpoints. **DOCX** (spec 012, plan 022) then truthed-up this document and the guides to the native executive, and retired the last Spec-Kit residue (the `agentpins` model-pin module + its `config apply`/config-drift feature; the `.specify/` tree — constitution + templates relocated to `.3powers/`). Migration: [`docs/migration-remove-speckit.md`](migration-remove-speckit.md). |
| **Last validated** | **2026-07-05**, against [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (Spec ID `3PWR`) |
| **Delivered** | full judiciary (oracle independence, complete gate suite, signed local trust spine), self-applied at High-risk (NFR-006), brownfield Stage Zero, emergency/deviation paths, observe & feedback loop, one-command **native** orchestration (`3pwr run`), headless read-path-isolated **oracle** dispatch (A3, oracle leg), three reference adapters (TypeScript, Python, Go), the `spec_integrity` gate (spec-lock), trust-spine hardening, a hardened native executive (RUNLIVE), and **phased execution** (PHASE, spec 013): a per-feature artifact workspace, hard plan/tasks artifact contracts, context-budgeted phases, one fresh headless session per phase, and parallel subagent dispatch for disjoint phases; and **auto full-mode readiness + the run error contract** (AUTOX, spec 014): one shared readiness/preflight check set (`3pwr ready`, init, and the run can never disagree), signed run-failure ledger records surfaced by both status commands, persisted credential-redacted per-attempt transcripts, a stable exit-code/JSON status contract (0 done · 1 gates-red · 2 usage · 3 paused · 4 setup/dispatch), checkpoint-independent resume, and an end-user getting-started path; and **a first-class CLI experience** (CLIUX, spec 015): a zero-dependency structured-output toolkit (headers, key/value blocks, aligned tables, status rows, dividers) that every `3pwr` command renders through, a consistent color + status-glyph vocabulary, a persistent colorized auto-mode stage header showing the current lifecycle stage and its running / paused / failed state, `--quiet`/`--verbose` and an opt-in `.3powers/config/ui.yaml` (color mode / verbosity / layout) — all human-output-only, with `--json`, exit codes, and verdict bytes byte-for-byte unchanged; and **per-stage agent templates + the headless-CLI / role→model setup** (AGENTX, spec 016): one editable, merged agent template per dispatched stage (`.3powers/templates/agents/<stage>.agent.md` — discovery, specify, clarify, plan, tasks, oracle, implement, review, characterize) that the executive uses as the stage's instruction body when present (built-in fallback otherwise), a per-integration model/label catalog (`.3powers/config/models.yaml`, editable data with free-form BYOK fallback), and an init + `3pwr config roles setup` flow that binds every role — planner, coder, oracle, reviewer — to a complete `roles.yaml` block (`model_family`/`model`/`integration`/`label`, oracle `require_dispatch`) so `3pwr run` needs no manual role editing; and **the run artifact workspace** (SRCX, spec 017): every `3pwr run` auto-allocates one FLAT feature folder `specs/<NNN>-<slug>/` (deterministic max-plus-one numbering + intent slug), every producing stage leaves a ledger-tracked markdown flat in it (`spec.md`, `plan.md`, `tasks.md`, plus `oracle.md`/`implement.md` *records* linking the real outputs at their real repo paths), and a deterministic artifact-∧-ledger stage-completion gate blocks a run — and re-enters a `--resume` — at any producing stage whose markdown is missing on disk or unrecorded in the signed ledger (two named failure classes, `artifact_absent`/`artifact_unrecorded`), superseding PHASE-FR-001's folder split while both legacy layouts stay readable; and **the git-integrated run lifecycle** (GITX, spec 018): mandatory pre/post-stage git hooks on every live run and the manual drive — a working git repo is a run precondition, every run is isolated to a dedicated branch `3pwr/<NNN>-<slug>` (reusing the SRCX identity, bound in the signed `run`/`start` entry, re-entered on resume), a run refuses to start atop unrelated uncommitted changes and leaves nothing it produced uncommitted after any stage, each producing stage is exactly one commit staging only the run's produced paths with an agent-written message (deterministic fallback) authored as the configured `3pwr` identity per-commit — superseding RUNLIVE's opt-out checkpoint, relaxable only via the signed `git_clean_start`/`git_stage_commit`/`git_run_branch` deviations |
| **Open residuals** | fuller A3 (the **coder** leg also headless, under a second different-family CLI) + a live non-Copilot end-to-end run · live design-oracle scanners + a live Go-toolchain gate run · catalog publishing of the agent-backend manifests · model-driven eval layer (FR-050) · cross-platform validation (NFR-003) |

**This file is the only home of implementation status.** Every other document (README, AGENTS.md,
CLAUDE.md) carries a durable summary and links here; when status changes, this file — and only this
file — is edited.

> **Read this first if you're picking up 3Powers cold.** It says what the project is, how to run it,
> exactly how far we are **validated against the spec**, whether we're heading the right way, and what
> to do next. The spec — [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (Spec ID `3PWR`) — is the
> single source of truth; this document is checked against it. It is a maintainer-facing status matrix —
> the requirement IDs below are the point. Last updated after **plan 028 (GITX)**.

---

## 1. What 3Powers is (90 seconds)

When one model writes the spec, the code, the tests, *and* the review, validation goes circular — the
**separation-of-powers collapse**. 3Powers restores three independent branches: **Legislative** (the
spec is law), **Executive** (agents build), **Judicial** (an independent oracle + a deterministic gate
suite + human review judge whether the code matches the spec). It **owns its executive** — a native,
provider-agnostic agent runner (`3pwr run`) drives headless coding agents directly — uses **Git** as
substrate, and is agnostic to model / language / provider / CI-CD. Trust is recovered **locally and
offline** via a signed, hash-chained verdict ledger — no mandatory CI/CD enforcer.

It is **self-applied**: the `3pwr` engine gates its own code.

## 2. How to run it (get going in 5 minutes)

```bash
# install the engine (provides the `3pwr` command; needs uv)
uv tool install ./engine

# one-time: create the independent signer (private key stored OUTSIDE the repo)
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/3powers.key"

# engine dev loop
(cd engine && uv sync --extra dev && uv run pytest)          # 670 tests
(cd engine && uv run ruff check . && uv run mypy src)        # lint + types

# self-application at STANDARD (fast — whole engine)
3pwr gate run --path engine --adapter python \
     --spec specs/002-engine-trust-spine/spec.md --tier Standard --base 3e20aad --no-ledger

# self-application at HIGH-RISK (the NFR-006 proof: trust-spine modules incl. mutation ≥70)
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
     --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
     --paths src/threepowers/canonical.py src/threepowers/keys.py \
             src/threepowers/ledger.py src/threepowers/verify.py)   # mutation_score ≈ 89%

3pwr eval                 # prompt/constitution eval set (FR-050)
3pwr verify               # recompute the ledger chain + signatures, offline
```

**One command drives the whole lifecycle:** `3pwr run "<intent>" --mode auto` dispatches each stage to a
headless coding agent via the **native executive**, runs the gate suite in-process, and stops only at the
two human gates (spec approval, sign-off). For a hands-on drive, run the stages yourself with the `3pwr`
CLI and the judiciary `/3pwr.*` prompts: `/3pwr.oracle` authors the Phase-A oracle under a different model
family, then `/3pwr.verify` → `/3pwr.review` → `/3pwr.signoff` → `/3pwr.advance`. For an **existing/legacy**
repo, start with `/3pwr.characterize` (reconstruct a spec + pin current behavior) before changing a module.
The runnable sample is [`examples/validation-utils/`](../examples/validation-utils/)
(spec id `VUTIL`). Full command list + pinned tool versions are in [`AGENTS.md`](../AGENTS.md).

## 3. Repo map

```
engine/                     # the `3pwr` engine (Python, uv tool) — cli, gates, scanners, gaming, workkind,
                            #   design, mutation, characterize, deviations, conformance, covdiff, scope, lifecycle,
                            #   orchestrate, runner, agents, prompts, artifacts, phases, workspace, hosted, oracle,
                            #   observe, deps, provenance, evals, ledger, verify, anchor, keys, verdict, speclock,
                            #   config, canonical (+ tests/)
.3powers/                   # in-repo trust spine: config/{risk-tiers,roles,design-oracles,context}.yaml, schemas/*.json,
                            #   adapters/{CONTRACT.md,typescript,python,go}, agents/*.yaml (native backends), eval/cases.yaml,
                            #   memory/constitution.md, templates/, semgrep-rules.yml, ledger.jsonl, keys/ledger.pub
.github/                    # /3pwr.* judiciary command prompts for a hands-on manual drive (no Spec Kit)
specs/                      # authoritative specs (the epic + per-feature); 002 = the engine's own
examples/validation-utils/  # runnable TypeScript sample
docs/references/            # trust-spine tooling reference + the historical Spec Kit reference (removed by SLIM)
plan/                       # the continuous plan series 001..028 (028 = GITX: the git-integrated run lifecycle)
```

## 4. Status — validated against the spec

**§17 scope phasing:**

| Slice | Status |
|---|---|
| **v0.1 — Trust-spine MVP** | ✅ complete (plans 001–003) |
| **v0.5 — Full judiciary** | ✅ complete (plans 004–005) |
| **v1.0 — Lifecycle & ecosystem** | ◑ in progress (plan 006: **High-risk self-application** + **brownfield Stage Zero**; plan 007: **emergency & deviation paths** §14; plan 008: **structural oracle independence** §7, ledger-anchored; plan 009: **portability & dependency stability** (deps-check + provider-agnostic Spec Kit extension); plan 010: **observe & feedback loop** §13; plan 011: **A3 live headless dispatch** — physical oracle read-path isolation (oracle leg); plan 012: **model diversity recommend-not-force**; plan 013: **orchestration front-end** `3pwr run`; plan 014: **hardening core** (betterleaks, work-kind inference FR-058, tier test-layers FR-064, richer TUI, LICENSE); plan 015: **work-kind-shaped gates** — defect-flow FR-008, design oracles FR-009, a **third (Go) adapter**; plan 016: **spec-integrity gate (spec-lock, SLOCK)** — the approved spec's hash sealed in the signed sign-off, enforced by a `spec_integrity` gate + `advance` + read-only `spec diff`; plan 017: **trust-spine hardening (HARDN)** — threat model, key custody + rotation + opt-in anchoring + external signing, oracle model attestation, conformance ID-binding/assertion checks, gaming flag, opt-in diff mutation; **plan 018: native executive (EXEC, spec 009)** — `3pwr run` drives headless agents directly via a provider-agnostic agent-runner; **plan 019: remove Spec Kit (SLIM, spec 010)** — substrate severed, `3pwr init` seeds agent manifests; **plan 021: live-executive hardening (RUNLIVE, spec 011)** — per-stage artifact contracts, robust dispatch (timeout/retry/streaming + `--json`), a gated live e2e proof, an async hosted backend, commit checkpoints; **plan 022: docs & de-cruft (DOCX, spec 012)** — STATUS/guides truthed-up to the native executive, `agentpins`/config-drift retired, `.specify/` relocated to `.3powers/`; **plan 023: phased execution (PHASE, spec 013)** — per-feature artifact workspace, hard plan/tasks artifact contracts, context-budgeted phases (FR-060/061), fresh session per phase, parallel subagent dispatch; **plan 024: auto full-mode readiness & the run error contract (AUTOX, spec 014)** — unified readiness/preflight (`3pwr ready`, AUTOX-FR-001..005), signed run-failure records + status surfacing + in-run verdict parity (AUTOX-FR-006/007/011), persisted redacted transcripts (AUTOX-FR-008), the stable exit-code/JSON contract + ledger-based resume (AUTOX-FR-009/010), end-user docs + the Spec-Kit config sweep (AUTOX-FR-012..015); **plan 025: a first-class CLI experience (CLIUX, spec 015)** — a zero-dependency structured-output toolkit rolled across every command (CLIUX-FR-001..006), byte-identical `--json` (CLIUX-FR-007), a persistent colorized auto-mode stage header with prominent human gates (CLIUX-FR-008..012), and `--quiet`/`--verbose` + an opt-in `ui.yaml` (CLIUX-FR-013..015); **plan 026: stage agent templates + role setup (AGENTX, spec 016)** — one editable, merged agent template per dispatched stage with built-in fallback (AGENTX-FR-001..005), phase-parallel plan/tasks/implement templates (AGENTX-FR-006..008), init seeding + example-templates retirement (AGENTX-FR-009/010), and the headless-CLI + role→model setup with a per-integration model catalog and `3pwr config roles setup` (AGENTX-FR-011..018); **plan 027: run artifact workspace (SRCX, spec 017)** — flat per-run feature folders with deterministic `<NNN>-<slug>` allocation (SRCX-FR-001/008/009), a ledger-tracked markdown per producing stage incl. the oracle/implement records (SRCX-FR-004/005/006), and the artifact-∧-ledger stage-completion gate governing advance and `--resume` (SRCX-FR-012..018); **plan 028: git-integrated run lifecycle (GITX, spec 018)** — the git precondition + mandatory pre/post-stage hooks (GITX-FR-001/002), the dedicated per-run branch reusing SRCX's identity with its additive ledger binding (GITX-FR-003..006), clean start / clean stop (GITX-FR-007/008), the single agentically-messaged 3pwr-authored stage commit superseding the `--no-auto-commit` opt-out (GITX-FR-010..014), `git.yaml` (GITX-FR-015), and the manual-drive `3pwr git start` + `advance` boundary checks (GITX-FR-016); remaining: catalog publishing) |

**Requirement-level (✅ done · ◑ partial/approximated · ⬜ missing).** Unlisted FRs in a ✅ block are done.

**Legislative (§5):** FR-001 ✅, FR-002 ✅, FR-059 ✅, FR-003 ✅, FR-004 ✅, FR-010 ✅ ·
FR-005 ◑ (a clarify stage exists in the lifecycle; "block on unmeasurable" is prompt-level) ·
FR-006 ◑ (sign-off recorded + enforced before *ship*; not hard-gated before *build*) ·
FR-007 ◑ (constitution/plan-template guidance, not a gate) · **FR-058 ✅** (`3pwr classify` + `3pwr run`
infer work kind(s) + a suggested tier, deterministically, shaping the tier/gates + oracle — never the
sign-off; per-kind gate shaping wired into `run_gates` in plan 015) ·
**FR-008 ✅** (a `defect` run adds a **regression gate**: `3pwr gate run --work-kind defect` fails
`missing_regression_test` unless a *regression*/*reproduce* test referencing the requirement is present —
deterministic, no model call) · **FR-009 ✅** (a `design` run unions the **design oracles** —
visual-regression / a11y / structural-contract / component-contract — from `design-oracles.yaml`; each tool
is adapter-supplied, a missing one is **quarantined** not silently passed; live scanners are the residual).

**Executive (§6):** FR-011 ✅ (stages derived from ledger; **`3pwr run` drives the whole loop** via the **native executive**, plans 018/019 — auto mode stops only at the two human gates; dispatches headless agents directly, no Spec Kit), FR-019 ✅, FR-014 ✅, FR-015 ✅,
FR-016 ◑ (tasks gated by `scope-check`; commit-message tagging not gated), FR-017 ✅, FR-063 ✅ ·
FR-012 ✅ / FR-013 ◑ (**both legs now dispatched headlessly by the native runner** — `3pwr run` drives the
coder leg (EXEC/SLIM, plans 018/019) and `3pwr oracle dispatch` the oracle leg under a non-coder
integration (plan 011); the residual is the *fuller* A3 — the coder leg under a **second, different-family**
CLI + a live non-Copilot end-to-end run) · FR-062 ✅ (Phase-A/B ordering proven
from the ledger seq; enforced at High-risk `advance`), FR-018 ◑ (advisory) · **FR-060 ✅ / FR-061 ✅**
(context strategy — delivered by **PHASE**, spec 013 / plan 023: the tasks artifact decomposes work into
**context-budgeted phases** (deterministic byte-based estimate vs a configurable per-model budget,
default ~110k tokens, `.3powers/config/context.yaml` — advisory-only), and the implement stage runs
**one fresh headless session per phase**, reloading each phase's handoff set (spec + constitution +
phase tasks + file scope) with no carried conversation; disjoint parallel-marked phases dispatch to
**parallel subagent sessions**, with deterministic result ordering and the ledger verifying green).
**Live executive hardening (RUNLIVE, spec 011 / plan 021) ✅:** the native executive is hardened —
**per-stage artifact contracts** catch a stage that produced nothing/off-target as a named artifact failure,
never a silent pass (RUNLIVE-FR-001/002/003); dispatch is **timeout-bounded, retried, streamed, and reported
per-stage on `--json`** (RUNLIVE-FR-004/005/006); a **gated live end-to-end proof** drives a real agent to a
green verdict while the default suite makes zero model calls (RUNLIVE-FR-007); an **async hosted backend**
(provider-neutral trigger→poll→collect) covers Copilot-only shops with no local CLI, judged identically and
leaking no credential (RUNLIVE-FR-008/009); and **commit checkpoints** let a resume skip completed stages
(RUNLIVE-FR-010 — the opt-out checkpoint itself is now superseded by GITX's mandatory, branch-scoped,
3pwr-authored stage commit, plan 028). No new trust primitive; the verdict never sees it (RUNLIVE-NFR-001/003).
**Auto full-mode readiness & the run error contract (AUTOX, spec 014 / plan 024) ✅:** readiness and the
run preflight are ONE shared check set — `3pwr init`'s checklist, the standalone read-only `3pwr ready`,
and the run's refusal consume the same checks (env-supplied signing keys validated, agent-CLI presence
reported with the honest "authentication not verified" caveat) so they can never drift
(AUTOX-FR-001..005); every terminal run failure appends a signed `run`/`failure` ledger record and both
`3pwr run --status` and `3pwr status` say "failed at <stage> (<class>)" until a later record passes that
stage (AUTOX-FR-006/007); every stage attempt's output — streamed included — persists,
credential-redacted, under `.3powers/runs/<spec-id>/` with the path in every failure message
(AUTOX-FR-008, NFR-002); the in-run Verify records its verdict exactly as a standalone gate run
(AUTOX-FR-011); the terminal contract is stable and tested — 0 done · 1 gates-red · 2 usage · 3
paused-at-gate · 4 setup/dispatch — and resume works from ledger stage records with auto-commit off
(AUTOX-FR-009/010); the docs lead with an end-user path to a green auto run, troubleshooting keys on the
exact failure phrases, and the last Spec-Kit-era config language is swept (AUTOX-FR-012..015).
All ledger additions are additive; `3pwr verify` stays green (AUTOX-NFR-003).

**A first-class CLI experience (CLIUX, spec 015 / plan 025) ✅:** the engine's home-grown, zero-dependency
styling layer (`style.py`) grew a **structured-output toolkit** — section headers, key/value blocks,
aligned tables, status rows, dividers, wrapped bullet lists — that **every** `3pwr` command now renders
through, so no command emits a run-on one-line dump and a given status shows the same glyph + color
everywhere (CLIUX-FR-001/004/005/006). With color off (non-TTY, `NO_COLOR`, `--json`, `--yes`) each
primitive degrades to plain, alignment-preserving text equal to the colored output with the ANSI stripped
(CLIUX-FR-002); no third-party rendering library is added — ANSI SGR only (CLIUX-FR-003/NFR-003) — and an
ASCII glyph set is used when the stream can't encode the Unicode marks (CLIUX-NFR-004). `3pwr run` shows a
**persistent, colorized "you are here" stage header** over the eight stages that updates as the run
advances and distinguishes running / paused-at-human-gate (with the exact resume command) / failed
(CLIUX-FR-008/009/010), degrading to the plain streamed log off a TTY — always escape-free, even under
`THREEPOWERS_FORCE_COLOR` (CLIUX-FR-011); `3pwr run --status` and `3pwr status` render the same snapshot
(CLIUX-FR-012). Output density and theming are tunable via `--quiet`/`--verbose` and an opt-in
`.3powers/config/ui.yaml` (color mode / verbosity / layout) with deterministic precedence — flag > env >
file > default — and safe defaults that reproduce prior behavior (CLIUX-FR-013/014/015). It is a
human-output-only layer: `--json` payloads, exit codes, verdict bytes, and the ledger are byte-for-byte
unchanged (CLIUX-FR-007/NFR-002), proven by tests that keep `--json` ANSI-free even when color is forced.

**Per-stage agent templates + the headless-CLI / role→model setup (AGENTX, spec 016 / plan 026) ✅:**
every agent-dispatched stage — discovery, specify, clarify, plan, tasks, oracle, implement, review,
characterize — has a dedicated, editable agent template at `.3powers/templates/agents/<stage>.agent.md`
(AGENTX-FR-001), each a merge of the curated reference structure with the engine's stage instruction,
with all substrate machinery (external scripts, extension hooks, `$ARGUMENTS`, tool-specific handoffs)
removed and the 3Powers discipline + a stage/artifact/role metadata header preserved (AGENTX-FR-002/003/
004); the executive uses the repo-local template as a stage's instruction body when present and falls
back to the built-in instruction when it is absent, empty, or unreadable — deterministically, changing
only the body, never the context blocks (AGENTX-FR-005). The plan/tasks/implement templates make
phase-parallel execution explicit — context-budgeted ordered phases, `[P]` only for disjoint
dependency-free phases, batch-independent tasks with the file-scope stop condition (AGENTX-FR-006/007/
008). Templates seed at init, non-clobbering; the one-time `example-templates/` reference set is retired
(AGENTX-FR-009/010). Init lets the user declare their installed headless CLI and walks every configurable
role — planner, coder, oracle, reviewer — against a per-integration **model/label catalog**
(`.3powers/config/models.yaml`, editable data with free-form BYOK fallback), writing complete
`roles.yaml` blocks (`model_family`/`model`/`integration`/`label`, oracle `require_dispatch` present) so
`3pwr run` needs no manual role editing; the same flow re-runs any time via `3pwr config roles setup`,
non-destructively (AGENTX-FR-011..016). `require_dispatch` is explained where the config lives (shipped
comments, the rewritten file's header, and the CLI reference), and a same-family judiciary only ever
warns, naming the signed deviation path (AGENTX-FR-017/018). An authoring-and-configuration layer only:
no gate, threshold, verdict byte, exit code, ledger record, or human gate changed (AGENTX-NFR-002).
Follow-up (template hardening): each agent template now carries a model-agnostic front-matter
`description` (+ `name`) and a **defined output** — an explicit artifact skeleton plus a fixed
"Completion report" — so a stage's result reads the same regardless of which backend model ran it; the
three orphaned outer document templates (`spec/checklist/constitution-template.md`) were removed, while
`plan/tasks-template.md` stay (the PHASE-FR-006 conformance test binds them as the document skeletons).

**The run artifact workspace (SRCX, spec 017 / plan 027) ✅:** every lifecycle stage's artifact for a
run lies FLAT in that run's feature folder — `specs/<NNN>-<slug>/{spec,plan,tasks,oracle,implement}.md`,
no `spec/` or `artifacts/` subfolder — superseding PHASE-FR-001's split for new runs while all three
layouts keep resolving to exactly one spec per feature (SRCX-FR-001/002/003, SRCX-NFR-003). The two
stages whose real outputs live elsewhere leave *records*: `oracle.md` links the authored oracle tests
and `implement.md` links the code changes at their real repo paths — one record even for an N-phase
parallel implement, written from the collecting thread in deterministic artifact order (SRCX-FR-004/005/
006, SRCX-NFR-006); pure gate/verdict/sign-off stages stay ledger-only (SRCX-FR-007). A fresh `3pwr run`
deterministically allocates `specs/<NNN>-<slug>/` (max existing `NNN-` prefix + 1; a pure, idempotent,
bounded slugify with a fixed fallback token), binds it into the `run`/`start` ledger payload (one
additive field), never overwrites an existing folder, and a resume reads the folder back from the signed
ledger alone — no mtime scan (SRCX-FR-008..011). The **deterministic stage-completion gate** then makes
every producing stage provable: the run advances only when the stage's declared markdown EXISTS ON DISK
and a matching signed `run`/`stage` (or `checkpoint`) entry lists that path — two distinct, recorded
failure classes (`artifact_absent`, `artifact_unrecorded`) surface via both status commands on the
non-gate-red exit path, and `--resume` applies the same gate to every recorded stage, re-entering at the
earliest broken one instead of trusting the ledger record alone — the confirmed resume gap, closed
(SRCX-FR-012..018, SRCX-SC-003). Strictly additive ledger content (new failure-class values + one
`run`/`start` field; no new entry type, no signing change): `3pwr verify` stays green over old and new
ledgers (SRCX-NFR-002); everything is offline, pure given injected inputs, and served by a single ledger
read per check set (SRCX-NFR-001/004/005). Two real executive seams were fixed en route: a re-run stage
regenerating a deleted artifact byte-identical to HEAD no longer fails its dispatch contract on the
empty diff, and `produced_paths` counts a path restored to committed content.

**The git-integrated run lifecycle (GITX, spec 018 / plan 028) ✅:** git handling is now a mandatory
pre-stage and post-stage hook on every live run and the manual `/3pwr.*` drive (GITX-FR-001/016), with
a working git repository as a run **precondition** in the shared readiness/preflight check set
(GITX-FR-002 — `3pwr ready`, init, and the run cannot disagree). Every run is isolated to a dedicated
branch `<prefix><NNN>-<slug>` reusing SRCX's already-allocated run identity — created off the configured
base before any commit, bound to the run as one additive `branch` field on the existing `run`/`start`
payload, and re-entered (never recreated) on resume, so the base branch's tip is never moved by a run
(GITX-FR-003..006). The clean-start guard refuses a run atop uncommitted changes the run did not produce
— naming the paths and the `git_clean_start` deviation, leaving the edits byte-identical (GITX-FR-007,
GITX-NFR-003) — and after every producing stage nothing the run produced is left uncommitted
(GITX-FR-008), surfaced with the run branch by both status commands (GITX-FR-009). Each producing stage
lands as exactly one commit staging only the run's produced paths, whose message is the agent's
`COMMIT:` description (a fixed prompt block; deterministic `3pwr(<spec-id>): <step>` fallback) and whose
author is the configured `3pwr` identity applied per-invocation — the developer's git config is never
mutated, nothing is force-pushed or rewritten (GITX-FR-010..013, GITX-NFR-004). The discipline is
mandatory: `--no-auto-commit` is superseded (warns, no longer disables), and the only relaxations are
the signed, revocable `git_clean_start`/`git_stage_commit`/`git_run_branch` deviations (GITX-FR-014);
`.3powers/config/git.yaml` tunes prefix/base/author with tolerant defaults (GITX-FR-015). The manual
drive gets `3pwr git start` (clean-start-guarded branch establishment + ledger binding) and a
stage-boundary `advance` that refuses off-branch or with the completed stage uncommitted (GITX-FR-016).
All git mechanics are deterministic and offline — the agent-written message is the only model-touched
output, captured as commit data, never a gate or ledger input (GITX-NFR-001/002/005).

**Judiciary — oracle (§7):** **FR-020 ✅** (`oracle seal` writes a spec-only bundle the judiciary authors
from; the authoring record binds to its content hash), **FR-022 ✅** (checked on the *actual* recorded model
at a configurable granularity — `family` default or `model`, plan 012; **recommend-not-force**: a same-model
setup proceeds only under a signed `model_diversity` deviation, FR-057, warned + recorded), FR-023 ✅,
**FR-062 ✅** ·
**FR-021 ✅** (**physical read-path isolation delivered**, plan 011 — `3pwr oracle dispatch` authors the
oracle headlessly in a sanitized git worktree with the implementation/plan/tasks/contracts physically
absent, attested by a worktree manifest hash in the ledger; a High-risk `advance` with `require_dispatch`
blocks a missing/non-isolated dispatch; the 008 peek/touch signal stays advisory. Network egress is out
of scope — read-path isolation only), FR-024 ◑ (required by prompt/sample, not enforced), FR-025 ◑.

**Judiciary — gate engine (§8):** FR-026 ✅, FR-027 ✅ (TypeScript + Python + **Go**, plan 015 — the Go
adapter reuses the core LCOV diff-coverage via `gcov2lcov`; a live Go gate run needs a Go toolchain),
FR-028 ✅, FR-029 ✅,
FR-030 ✅, FR-031 ✅ (**mutation now executes** on the trust spine via the fixed mutmut src-layout
runner; score graded vs the tier threshold; survivors reported as missing assertions), FR-032 ✅,
FR-033 ✅, FR-034 ✅, FR-035 ✅, FR-065 ✅ · **FR-064 ✅** (per-tier `required_layers` in risk-tiers.yaml,
enforced by spec-conformance as a per-change union: High-risk requires unit+integration+e2e). Secret gate
now runs **betterleaks** (maintained Gitleaks successor), gitleaks fallback, quarantine if neither.

**Judiciary — trust spine (§9):** FR-036 ✅, FR-037 ✅, FR-038 ✅, FR-039 ✅, FR-040 ✅, FR-041 ✅,
FR-042 ✅, FR-066 ✅, FR-067 ✅, FR-068 ✅, FR-069 ✅, FR-070 ✅, FR-071 ✅ ·
FR-043 ⬜ (CI re-validation — optional per A4). **Spec-integrity (SLOCK, plan 016) ✅:** a Spec-stage
sign-off seals the full document's SHA-256 inside the signed ledger entry (SLOCK-FR-001/002); the
`spec_integrity` gate fails a post-approval mutation before any test at every tier (SLOCK-FR-003/004),
`advance` refuses `spec_modified` unless a signed `spec_integrity` deviation covers it (SLOCK-FR-005),
a fresh Spec-stage sign-off supersedes (SLOCK-FR-006), and `3pwr spec diff` reports read-only
(SLOCK-FR-007); tampering with the recorded hash is caught by the existing `verify` (SLOCK-NFR-002).
The new `speclock` module holds the High-risk bar (diff-coverage 97% ≥ 95, mutation ≈80% ≥ 70).
**Trust-spine hardening (HARDN, plan 017) ✅:** a versioned [threat model](threat-model.md) states what the
ledger proves and cannot prove (HARDN-FR-001); `keygen`/`rotate-key` refuse in-repo keys and `verify` runs a
custody preflight (`key_custody`, HARDN-FR-002); the secret gate's core `ed25519-priv` check always runs
(HARDN-FR-003); key rotation is a signed `key_rotation` entry authored by the outgoing key, and `verify`
fails an *unrotated key change* (HARDN-FR-004); opt-in `3pwr anchor` + `verify --anchored` catch wholesale
ledger regeneration by a key holder (HARDN-FR-005); `$THREEPOWERS_SIGNER_CMD` delegates signing to an
external process boundary with no readable seed and no silent fallback (HARDN-FR-006); the self-reported
oracle model is cross-checked against the attested dispatch, and labelled self-reported without one
(HARDN-FR-007).

**Agnosticism / config (§10–11):** FR-044 ✅, FR-045 ✅, FR-046 ✅, FR-047 ✅, FR-048 ✅, FR-049 ✅,
FR-050 ✅ (deterministic eval set; model-driven layer is future). · **Plan 009** operationalized FR-048
(`3pwr deps-check` flags installed-toolchain drift vs `.3powers/config/dependencies.yaml`)
and strengthened FR-044/046/A1 (substrate-neutral, eval-gated role config); plan 009's provider-agnostic
Spec Kit extension was later **superseded by the native executive** (EXEC/SLIM, plans 018/019).

**v1.0 (§12–14):** **FR-051 ✅** (diff-scoped gating — `--paths`/`--diff-scope` hold only changed files;
scanners + diff-coverage honor the scope), **FR-052 ✅** (`gate run --report-only` emits but does not
block; `advance` ignores advisory verdicts), **FR-053 ✅** (`3pwr characterize` reconstructs a spec stub
+ runnable characterization tests pinning a legacy module's behavior as its oracle),
**FR-056 ✅** (`3pwr emergency` — a fast path that defers only mutation + coverage, never the
security/secret gates, sign-off, or provenance, and whose overdue one-day cleanup blocks `advance`),
**FR-057 ✅** (`3pwr deviation` — a signed, reversible relaxation of named gates with a reason + a way back;
`advance` accepts a red gate only when an active deviation covers it; also the sanctioned acceptance of a
`gate_gaming` flag) · **FR-054 ✅** (observe: `observe signal` routes a production signal to a
new-requirement backlog + moves the spec to the Observe stage; `observe coverage` reports NFR
instrumentation), **FR-055 ✅** (`observe log-action`/`verify-actions` — a tamper-evident, attributable
runtime agent-action log). The engine records signals + instrumentation *declarations* (it is offline; it
does not run the target's live production system).

**NFRs:** NFR-001 ✅, NFR-004 ✅, NFR-005 ✅ (plan 011 adds an optional **distinct oracle signer key**;
`verify` accepts the primary *or* oracle key, single-key repos unchanged), NFR-007 ✅, NFR-008 ✅,
NFR-010 ✅, NFR-011 ✅,
NFR-013 ✅, NFR-014 ✅ ·
**NFR-006 ✅ — now met:** the trust-spine modules (`canonical`, `keys`, `ledger`, `verify`) pass their own
**High-risk** bar — ≥95% diff-coverage **and** mutation (score ≈89% ≥ the 70% threshold) — via the fixed
mutmut src-layout runner and per-path tier scoping. "3Powers is built with 3Powers at High-risk" is now
true for its trust spine ·
NFR-002 ◑ (perf budgets not measured), NFR-003 ◑ (built/tested on macOS only), NFR-009 ◑ (spend config
exists, not orchestrated), **NFR-012 ✅** (root `LICENSE`, Apache-2.0),
NFR-015 ◑ (scanners quarantine when absent; no general flaky-quarantine), NFR-016 ◑ (provenance/deploy-gate
exist; the engine's own install path doesn't self-verify yet).

## 5. Are we going the right way? (honest direction check)

**Yes — the core is sound and on-spec.** We built the **High-risk trust spine first** (correct per §4),
followed §17 phasing exactly (v0.1 then v0.5), and the engine **self-applies** (gates its own code green).
The deterministic, offline, signed trust spine — the spec's distinctive promise — is real and verifiable.

**Plan 006 closed the biggest unmet stated requirement (NFR-006): the trust spine now passes its own
High-risk bar, mutation included.** Two approximations remain, and they touch the spec's central thesis.
Harden these before adding breadth:

1. **Oracle independence — now *physical* (FR-021 delivered for the oracle leg, A3).** Plan 008 made it
   structural (spec-only sealed bundle, ledger-proven Phase-A/B ordering, actual-model family refusal).
   **Plan 011 made the read-path isolation physical:** `3pwr oracle dispatch` authors the oracle headlessly
   under a non-coder integration (via the native runner since SLIM), inside a **sanitized git worktree** with
   the implementation/plan/tasks/contracts physically absent — attested by a worktree manifest hash in the
   ledger and enforced at a High-risk `advance` (`require_dispatch`). Peeking stays an advisory. The residual
   is the *fuller* proof: the **coder** leg headless under a **second, different-family** CLI, and a live
   end-to-end run under a non-Copilot agent (needs a second CLI integration installed).
2. **A1 — now a native executive (A1′).** Plan 009 first packaged 3Powers as a provider-agnostic Spec Kit
   extension; **EXEC (plan 018) then brought the executive in-house** and **SLIM (plan 019) removed Spec Kit
   entirely** — `3pwr run` now dispatches headless agents directly from substrate-neutral, eval-gated role
   config (no `.specify/`, no external orchestration runtime). What remains is the *live* cross-integration
   proof (running the judiciary isolated under a second, non-Copilot agent CLI), tied to the A3 read-path
   isolation in #1.

**Recommendation:** with plan 011 the thesis-level judiciary delivers **physical** oracle read-path
isolation (FR-021) and the first real cross-integration dispatch (FR-012/013, oracle leg), and plan 012
made model diversity **recommend-not-force** (a same-model setup proceeds via a signed `model_diversity`
deviation, so single-model users are never walled off) with configurable granularity — the spec-level
*headlines* are closed to the limit of this repo. Plans 014–015 then took the hardening track: betterleaks,
work-kind inference (FR-058) now **shaping the gate set** — defect-flow (FR-008) and design oracles (FR-009) —
and a **third (Go) reference adapter** (FR-027). What remains is breadth: the *fuller* A3 proof (the coder
leg also headless under a second, different-family CLI; a live non-Copilot end-to-end run), live design
scanners + a Go toolchain for those adapters' live runs, catalog publishing, and cross-platform (NFR-003).

## 6. What's next (roadmap)

**Plan 006 is done** (see [`plan/006-v1.0-and-hardening.md`](../plan/006-v1.0-and-hardening.md)):
✅ **A — NFR-006** (mutmut src-layout runner fixed; mutation graded vs the tier; per-path High-risk
scoping; the engine runs green at `--tier High-risk`), and ✅ **B — Brownfield Stage Zero** (report-only
mode FR-052, diff-scoped gating FR-051, `3pwr characterize` FR-053).

**Plan 007 is done** ([`plan/007-emergency-and-deviation.md`](../plan/007-emergency-and-deviation.md)):
✅ **emergency & deviation paths (§14, FR-056/057)** — `3pwr deviation` (signed, reversible, named-gate
relaxation; the sanctioned acceptance of a `gate_gaming` flag) and `3pwr emergency` (defer only
mutation+coverage, never security/secret/sign-off/provenance, overdue cleanup blocks `advance`).

**Plan 008 is done** ([`plan/008-oracle-independence.md`](../plan/008-oracle-independence.md)):
✅ **structural oracle independence (§7, FR-020/021/022/062)** — `3pwr oracle seal` (spec-only sealed bundle),
`oracle record` (actual model + signer + test hashes; refuses the coder's family), and `oracle verify`; a
High-risk `advance` now proves oracle independence from the ledger seq, while peeking/touching the
implementation is an **advisory** flag, never a blocker.

**Plan 009 is done** ([`plan/009-portability-and-dependencies.md`](../plan/009-portability-and-dependencies.md)):
✅ **portability & dependency stability (A1/A3, FR-044/046/048, NFR-014)** — `3pwr deps-check` pins the
supported third-party versions and flags drift; the role config is substrate-neutral and eval-gated.
(Plan 009 originally shipped a provider-agnostic Spec Kit extension; it was **superseded by the native
executive** — EXEC/SLIM, plans 018/019.)

**Plan 010 is done** ([`plan/010-observe-and-feedback.md`](../plan/010-observe-and-feedback.md)):
✅ **observe & feedback loop (§13, FR-054/055)** — `observe signal` routes a production signal to a
new-requirement backlog (not a patch) + moves the spec to the Observe stage; `observe coverage` reports
NFR instrumentation; `observe log-action`/`verify-actions` is a tamper-evident, attributable runtime
agent-action log. The 8th lifecycle stage is now reachable.

**Plan 011 is done** ([`plan/011-a3-live-headless-dispatch.md`](../plan/011-a3-live-headless-dispatch.md)):
✅ **A3 live headless dispatch — physical oracle read-path isolation (FR-021), oracle leg of FR-012/013.**
`3pwr oracle dispatch` builds a **sanitized git worktree** (implementation/plan/tasks/contracts physically
absent), runs the oracle authoring step headlessly under a non-coder agent
(default `claude`) — via the old Spec Kit dispatch originally, **now the native runner since SLIM (plan 019)** —
collects the authored tests, and records a signed **dispatch attestation** (agent
+ resolved model + worktree isolation manifest). `independence()`/High-risk `advance` **block** on a
missing-required or non-isolated dispatch (`roles.oracle.require_dispatch`), while the 008 peek/touch signal
stays advisory (NFR-001); dispatch never enters `gate run`. An optional **distinct oracle signer key** is
supported (two-key `verify`, NFR-005). A headless agent CLI (`claude`) is present in-repo, so the minimal
live proof runs here; the *fuller* dual-headless proof is the residual.

**Plan 012 is done** ([`plan/012-diversity-recommend-not-force.md`](../plan/012-diversity-recommend-not-force.md)):
✅ **model diversity — recommend, not force (FR-022 via FR-057).** Comparison granularity is configurable
(`diversity_level: family|model`, default family); a same-family/model oracle is refused by default but
proceeds under a signed, warned, reversible `model_diversity` deviation (`3pwr deviation --gate
model_diversity`), recorded in the ledger and undone by `--revoke`. `oracle record`/`dispatch`/`advance`/
`roles-check` all honour it; `independence()` moves a covered mismatch to advisory (never blocking, NFR-001).
Single-model users (e.g. only Claude Code) are warned, never walled off; FR-022 stays the law.

**Plan 013 is done** ([`plan/013-orchestration-loop.md`](../plan/013-orchestration-loop.md)):
✅ **orchestration front-end `3pwr run` (§6, FR-011).** One command drives the whole lifecycle with a live
stage tracker via the **native executive** (A1′; the engine makes no model call, A3 — plan 013 originally
composed the old Spec Kit dispatch, made native by EXEC/SLIM). In `auto` mode
it auto-approves the intermediate review gates and **stops only at the two mandatory human gates** —
`review-spec` (FR-006 spec approval) and `signoff` (FR-037 evidence sign-off); `commit` mode stops at every
gate. Sign-offs + progress are recorded in the ledger (resumable, FR-011/019 — `--resume`/`--status`), a red
verdict stops + `--notify`s + suggests `observe signal` (FR-054), and orchestration never enters the
deterministic verdict (NFR-001). Fully-headless execution of the executive stages rides on the A3 dispatch
leg (residual); interactive under Copilot.

**Plan 014 is done** ([`plan/014-hardening-core.md`](../plan/014-hardening-core.md)):
✅ **hardening core.** The secret gate now runs **betterleaks** (maintained Gitleaks successor; gitleaks
fallback, quarantine if neither) — verified live. **Work-kind inference (FR-058):** `3pwr classify` + `3pwr
run` infer kind(s) + a suggested tier deterministically, shaping the tier/gates + oracle, never the sign-off.
**Tier test-layers (FR-064):** `required_layers` per tier, enforced by spec-conformance as a per-change union
(High-risk needs unit+integration+e2e; the engine dogfoods it). **Richer TUI:** a dependency-free in-place
`3pwr run` tracker (plain fallback off a TTY). **Root `LICENSE`** (Apache-2.0, NFR-012). Self-applies green
at High-risk (secret_scan · betterleaks, 39 requirements traced across all layers).

**Plan 015 is done** ([`plan/015-defect-design-go-adapter.md`](../plan/015-defect-design-go-adapter.md)):
✅ **work-kind-shaped gates.** Work-kind inference now *shapes the gate set* via `run_gates(work_kind=…)` /
`3pwr gate run --work-kind` (never weakening a tier gate — FR-032). **FR-008 defect-flow:** a `defect` run
adds a **regression gate** that fails `missing_regression_test` unless a *regression*/*reproduce* test
referencing the requirement is present (deterministic, no model call). **FR-009 design oracles:** a `design`
run unions the oracle gates from `design-oracles.yaml` (visual-regression / a11y / structural-contract /
component-contract); each tool is adapter-supplied and a missing one is **quarantined**, never silently
passed (NFR-015). **Third (Go) adapter:** a declarative `.3powers/adapters/go/adapter.yaml` proving the
contract is language-agnostic (FR-027/NFR-007) — it reuses the core LCOV diff-coverage via `gcov2lcov` (a
new opt-in `shell: true` on an adapter gate enables the two-step pipeline). Self-applies green at High-risk
(mutation on the trust spine) and Standard (whole engine, diff-coverage 88% ≥ 80%).

**Plan 016 is done** ([`plan/016-spec-integrity.md`](../plan/016-spec-integrity.md)):
✅ **spec-integrity gate (spec-lock, SLOCK — High-risk).** A Spec-stage `3pwr signoff` (manual or via the
`3pwr run` review-spec gate) seals the approved document's raw-bytes SHA-256 + root-relative path + sign-off
commit **inside the signed ledger entry** (SLOCK-FR-001/002 — no new entry kind, no new trust primitive).
A new `spec_integrity` gate runs cheapest-first (after types, before any test) at **every tier** and fails a
post-approval mutation with class `spec_modified` naming the approving seq; a never-approved spec skips in
O(1), never blocked (SLOCK-FR-003/004, NFR-003). `advance` re-executes the check and refuses `spec_modified`
unless a signed, reversible `spec_integrity` deviation covers it (SLOCK-FR-005); a fresh Spec-stage sign-off
supersedes (SLOCK-FR-006); read-only `3pwr spec diff` reports both hashes + a textual diff when the sign-off
commit is known (SLOCK-FR-007). Tampering with the recorded hash breaks the entry's signature — caught by the
existing `verify` with zero new verification code (SLOCK-NFR-002). Self-applies at **High-risk** scoped to
the new `speclock` module: diff-coverage 97.18% ≥ 95, mutation 79.56% ≥ 70, all SLOCK requirements traced
across unit+integration+e2e.

**Plan 017 is done** ([`plan/017-trust-hardening.md`](../plan/017-trust-hardening.md)):
✅ **trust-spine hardening (HARDN — High-risk).** Closes the external review's three trust-mechanism gaps
with deterministic, local mechanisms: **(custody & continuity)** a versioned
[`docs/threat-model.md`](threat-model.md) linked from README/SECURITY (HARDN-FR-001, SC-007); in-repo
private keys refused at `keygen`/`rotate-key`, custody preflight in `verify` (`key_custody` on an in-tree or
group-readable key, HARDN-FR-002); an always-on core `ed25519-priv` secret check (HARDN-FR-003); signed
`key_rotation` succession walked by `verify` — a bare committed-pubkey swap is an *unrotated key change*
(HARDN-FR-004, SC-001); opt-in `3pwr anchor` (git-tag witness + local receipt; `--push` is the only network
op) with `verify --anchored` catching truncation/rewrite behind the anchor even by a key holder
(HARDN-FR-005, SC-003); external signing via `$THREEPOWERS_SIGNER_CMD` — seed never readable by the engine,
loud failure, verification unchanged (HARDN-FR-006, SC-004). **(oracle)** the self-reported record model is
cross-checked against the ledger-attested dispatch integration — a contradiction blocks a High-risk advance;
without a dispatch the claim is labelled self-reported (HARDN-FR-007). **(anti-gaming)** conformance now
binds requirement IDs to test *declarations* (`untraced_requirement` for comment-only mentions, SC-005) and
requires ≥1 assertion per bound test with adapter-declared patterns (`weak_test`; pattern-less adapters
quarantine visibly — HARDN-FR-008/009, NFR-015); `gate_gaming` flags newly added assertion-free
requirement-referencing tests (HARDN-FR-010); a per-tier `diff_mutation` knob runs mutation over changed
files against the tier threshold (HARDN-FR-011, SC-006). Self-applies at **High-risk** scoped to the
extended trust-spine modules (`keys`, `ledger`, `verify`, new `anchor`): diff-coverage 95.7% ≥ 95,
mutation 79.61% ≥ 70, all HARDN requirements traced across unit+integration+e2e.

**Native-executive track (plans 018–019 delivered; the current direction — see epic §17).** Plan 018
(**EXEC**, spec 009) brought the executive in-house: `3pwr run` drives headless coding agents *directly*
via a native, provider-agnostic agent-runner (manifests under `.3powers/agents/`), runs the gate suite
in-process, and stops only at the two human gates; the engine calls no model API and a model never produces
the verdict. Plan 019 (**SLIM**, spec 010) removed GitHub Spec Kit entirely. This closed the old "fuller
A3 / live executive" residual — the coder leg is now natively headless with no substrate.

**Plan 021 is done** ([`plan/021-live-executive-hardening.md`](../plan/021-live-executive-hardening.md)):
✅ **live executive hardening (RUNLIVE, spec 011).** The native executive is hardened from "walks the
lifecycle with a fake agent" to "reliably builds real software": **per-stage artifact contracts** (a stage
that produced nothing — or only an off-target change — is a *named artifact failure*, distinct from a
gate-red, never a silent pass; unconfigured stages stay lenient — RUNLIVE-FR-001/002/003, new `artifacts`
module); **robust dispatch** — a configurable per-stage timeout + retry policy, streamed agent output on a
TTY, and a machine-readable per-stage result on `--json` (RUNLIVE-FR-004/005/006); a **gated live
end-to-end proof** — an opt-in test drives one real agent to a green verdict while the default suite makes
zero outbound model calls (RUNLIVE-FR-007); an **async hosted backend** — a provider-neutral,
manifest-driven trigger→poll→collect backend for Copilot-only shops without a local headless CLI, judged
identically to a local dispatch and never logging a credential (RUNLIVE-FR-008/009, new `hosted` module +
`copilot-hosted.yaml`); and **commit checkpoints** — each successful stage is committed and a resume
continues from the last checkpoint without re-dispatching a completed stage (RUNLIVE-FR-010). No new
trust-spine primitive; the deterministic verdict never sees any of it (RUNLIVE-NFR-001/003). Self-applies
clean on the gates it owns (diff-coverage 91.68% ≥ 80, gate_gaming green, no new suppressions).

**Plan 022 is done** ([`plan/022-docs-and-decruft.md`](../plan/022-docs-and-decruft.md)):
✅ **docs truth-up & de-cruft (DOCX, spec 012).** This document and the guides (README, AGENTS, CLAUDE,
getting-started, troubleshooting, concepts, glossary, cli-reference) were rewritten to describe the
**native executive** and the **absence of Spec Kit** as the current state — no forward-looking doc presents
Spec Kit as a dependency or a required step (DOCX-FR-001/002; the OSS-readiness doc-structure tests that
had encoded the old Spec-Kit-dependency prose were truthed-up to match). The last Spec-Kit-shaped residue
was retired (DOCX-FR-003): the `agentpins` model-pin module **and** the `config apply` + config-drift
feature it drove (INITX-FR-015/016, now moot — nothing dispatches the `.github/agents/3pwr.*` frontmatter).
The `.specify/` tree is gone (DOCX-FR-004/005): the constitution and the spec/plan/tasks templates were
relocated to `.3powers/memory/constitution.md` + `.3powers/templates/`, every reader points there, and
`3pwr init` seeds the constitution at the new path non-destructively. No gate, verdict, ledger, or signing
behavior changed (DOCX-NFR-001); no engine runtime path references `.specify/` or a Spec-Kit CLI
(DOCX-NFR-002). Also folded in the plan-021 self-gate residue (`ruff format` on three stale files).

**Plan 023 is done** ([`plan/023-phased-execution.md`](../plan/023-phased-execution.md)):
✅ **phased execution (PHASE, spec 013)** — delivers the epic's context strategy (3PWR-FR-060/061) and the
playbook's session LAWs at the engine level. **Feature workspace** (PHASE-FR-001): each new feature is one
versioned folder — `specs/<f>/spec/spec.md` + a sibling `specs/<f>/artifacts/` for every other stage's
output; legacy flat layouts stay resolvable (exactly one spec per feature, whichever layout). *(The folder
split was later superseded by SRCX, spec 017 / plan 027 — new runs write FLAT — while the split stays
readable; the rest of PHASE is unchanged.)* **Hard
plan/tasks artifact contracts** (PHASE-FR-002): a plan/tasks dispatch that writes nothing is a named
artifact failure — the lenient fallback now covers only genuinely artifact-less steps; checkpoint ledger
entries carry the accepted artifact paths (PHASE-FR-003). **Prompt/context injection** (PHASE-FR-004/005):
the plan/tasks stage prompts name their artifact, required sections, decomposition rules, and the sizing
heuristic; every post-approval stage's prompt reloads the approved spec text + a prior-artifact digest
reference — deterministically. **Templates** (PHASE-FR-006): phases as self-contained delegable units with
per-phase handoff blocks, size estimates, `[P]` markers; zero `/speckit.*` residue. **Advisory context
budget** (PHASE-FR-007/008/009): configurable per-model (`context.yaml`, default ~110k tokens), a
deterministic bytes→tokens estimate per phase, an oversize warning that advises a split and never blocks.
**Fresh session per phase + parallel subagents** (PHASE-FR-010/011/012): implement dispatches one new
headless session per phase (the phaseless artifact = one session); parallel-marked, dependency-free,
scope-disjoint phases run concurrently; results are ledger-recorded in deterministic artifact order after
collection (verify stays green — PHASE-NFR-003); a phase failure names the phase and later phases are
explicitly skipped, never silently passed. No trust-spine change; engine self-green (530 tests, ruff, mypy).

Next, in priority order:
- **Breadth (unchanged):** live design/Go runs (playwright/axe/schema-diff + a Go toolchain), model-driven
  eval layer (FR-050), cross-platform validation (NFR-003).
- **Maintainer follow-up:** re-seal + re-approve the epic spec — its post-EXEC/SLIM amendments, plus this
  pass's §17 status-column truth-up, trip `spec_integrity` until a fresh Spec-stage sign-off reseals it.

## 7. Pointers

- **Spec (law):** [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) · **Constitution:** [`.3powers/memory/constitution.md`](../.3powers/memory/constitution.md)
- **Plans:** [`plan/`](../plan/) (001→027 done) · **Agent guidance:** [`CLAUDE.md`](../CLAUDE.md), [`AGENTS.md`](../AGENTS.md)
- **References:** [`docs/references/trust-spine-tooling.md`](references/trust-spine-tooling.md); [`docs/references/speckit.md`](references/speckit.md) (historical — Spec Kit was removed by SLIM)
- **How to verify the claims here:** run the commands in §2; every plan doc ends with a Verification section.
- **Git:** feature branches per spec — recent: `feature/016-stage-agents-and-role-setup`,
  `feature/017-run-artifact-workspace` (this pass — SRCX).
- **External tools used by some gates** (optional; gates quarantine if absent): `gitleaks`, `osv-scanner`,
  `semgrep`; the TS adapter uses `biome`, `tsc`, `vitest`, `stryker`, `fast-check` via `npm`.
