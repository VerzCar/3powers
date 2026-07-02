# 3Powers — Project Status & Handoff

## At a glance

| | |
|---|---|
| **Current milestone** | **v0.5 complete; v1.0 in progress** (spec §17 phasing; plans 001–017 delivered) |
| **Last validated** | **2026-07-02**, against [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (Spec ID `3PWR`) |
| **Delivered** | full judiciary (oracle independence, complete gate suite, signed local trust spine), self-applied at High-risk (NFR-006), brownfield Stage Zero, emergency/deviation paths, observe & feedback loop, one-command orchestration (`3pwr run`), headless read-path-isolated **oracle** dispatch (A3, oracle leg), three reference adapters (TypeScript, Python, Go), the `spec_integrity` gate (spec-lock), trust-spine hardening |
| **Open residuals** | fuller A3 (the **coder** leg also headless, under a second different-family CLI) + a live non-Copilot end-to-end run · live design-oracle scanners + a live Go-toolchain gate run · catalog publishing of the Spec Kit extension · model-driven eval layer (FR-050) · cross-platform validation (NFR-003) · context strategy approximated at command level (FR-060/061) |

**This file is the only home of implementation status.** Every other document (README, AGENTS.md,
CLAUDE.md) carries a durable summary and links here; when status changes, this file — and only this
file — is edited.

> **Read this first if you're picking up 3Powers cold.** It says what the project is, how to run it,
> exactly how far we are **validated against the spec**, whether we're heading the right way, and what
> to do next. The spec — [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) (Spec ID `3PWR`) — is the
> single source of truth; this document is checked against it. It is a maintainer-facing status matrix —
> the requirement IDs below are the point. Last updated after **plan 017**.

---

## 1. What 3Powers is (90 seconds)

When one model writes the spec, the code, the tests, *and* the review, validation goes circular — the
**separation-of-powers collapse**. 3Powers restores three independent branches: **Legislative** (the
spec is law), **Executive** (agents build), **Judicial** (an independent oracle + a deterministic gate
suite + human review judge whether the code matches the spec). It layers on **GitHub Spec Kit**, uses
**Git** as substrate, and is agnostic to model / language / provider / CI-CD. Trust is recovered
**locally and offline** via a signed, hash-chained verdict ledger — no mandatory CI/CD enforcer.

It is **self-applied**: the `3pwr` engine gates its own code.

## 2. How to run it (get going in 5 minutes)

```bash
# install the engine (provides the `3pwr` command; needs uv)
uv tool install ./engine

# one-time: create the independent signer (private key stored OUTSIDE the repo)
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/3powers.key"

# engine dev loop
(cd engine && uv sync --extra dev && uv run pytest)          # 251 tests
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

**The lifecycle runs through GitHub Copilot slash commands** (open the repo in VS Code):
`/speckit.specify → clarify → plan → tasks` → **switch chat model** → `/3pwr.oracle` (Phase-A oracle,
different model family) → **switch back** → `/speckit.implement` → `/3pwr.verify` → `/3pwr.review` →
`/3pwr.signoff` → `/3pwr.advance`. For an **existing/legacy** repo, start with `/3pwr.characterize`
(reconstruct a spec + pin current behavior) before changing a module. The runnable sample is
[`examples/validation-utils/`](../examples/validation-utils/)
(spec id `VUTIL`). Full command list + pinned tool versions are in [`AGENTS.md`](../AGENTS.md).

## 3. Repo map

```
engine/                     # the `3pwr` engine (Python, uv tool) — cli, gates, scanners, gaming, workkind,
                            #   design, mutation, characterize, deviations, conformance, covdiff, scope, lifecycle,
                            #   orchestrate, oracle, observe, deps, provenance, evals, ledger, verify, keys, verdict,
                            #   config, canonical (+ tests/)
.3powers/                   # in-repo trust spine: config/{risk-tiers,roles,design-oracles}.yaml, schemas/*.json,
                            #   adapters/{CONTRACT.md,typescript,python,go}, eval/cases.yaml,
                            #   semgrep-rules.yml, ledger.jsonl, keys/ledger.pub
.specify/ + .github/        # Spec Kit; 3Powers constitution + template overrides + /3pwr.* commands
specs/                      # authoritative specs (the epic + per-feature); 002 = the engine's own
examples/validation-utils/  # runnable TypeScript sample
docs/references/            # compacted Spec Kit + trust-spine tooling references
plan/                       # the continuous plan series 001..015 (015 = work-kind-shaped gates: FR-008/FR-009 + Go adapter)
```

## 4. Status — validated against the spec

**§17 scope phasing:**

| Slice | Status |
|---|---|
| **v0.1 — Trust-spine MVP** | ✅ complete (plans 001–003) |
| **v0.5 — Full judiciary** | ✅ complete (plans 004–005) |
| **v1.0 — Lifecycle & ecosystem** | ◑ in progress (plan 006: **High-risk self-application** + **brownfield Stage Zero**; plan 007: **emergency & deviation paths** §14; plan 008: **structural oracle independence** §7, ledger-anchored; plan 009: **portability & dependency stability** (deps-check + provider-agnostic Spec Kit extension); plan 010: **observe & feedback loop** §13; plan 011: **A3 live headless dispatch** — physical oracle read-path isolation (oracle leg); plan 012: **model diversity recommend-not-force**; plan 013: **orchestration front-end** `3pwr run`; plan 014: **hardening core** (betterleaks, work-kind inference FR-058, tier test-layers FR-064, richer TUI, LICENSE); plan 015: **work-kind-shaped gates** — defect-flow FR-008, design oracles FR-009, a **third (Go) adapter**; plan 016: **spec-integrity gate (spec-lock, SLOCK)** — the approved spec's hash sealed in the signed sign-off, enforced by a `spec_integrity` gate + `advance` + read-only `spec diff`; plan 017: **trust-spine hardening (HARDN)** — threat model, key custody + rotation + opt-in anchoring + external signing, oracle model attestation, conformance ID-binding/assertion checks, gaming flag, opt-in diff mutation; remaining: dual-headless coder leg, catalog publishing) |

**Requirement-level (✅ done · ◑ partial/approximated · ⬜ missing).** Unlisted FRs in a ✅ block are done.

**Legislative (§5):** FR-001 ✅, FR-002 ✅, FR-059 ✅, FR-003 ✅, FR-004 ✅, FR-010 ✅ ·
FR-005 ◑ (Spec Kit `/clarify` exists; "block on unmeasurable" is prompt-level) ·
FR-006 ◑ (sign-off recorded + enforced before *ship*; not hard-gated before *build*) ·
FR-007 ◑ (constitution/plan-template guidance, not a gate) · **FR-058 ✅** (`3pwr classify` + `3pwr run`
infer work kind(s) + a suggested tier, deterministically, shaping the tier/gates + oracle — never the
sign-off; per-kind gate shaping wired into `run_gates` in plan 015) ·
**FR-008 ✅** (a `defect` run adds a **regression gate**: `3pwr gate run --work-kind defect` fails
`missing_regression_test` unless a *regression*/*reproduce* test referencing the requirement is present —
deterministic, no model call) · **FR-009 ✅** (a `design` run unions the **design oracles** —
visual-regression / a11y / structural-contract / component-contract — from `design-oracles.yaml`; each tool
is adapter-supplied, a missing one is **quarantined** not silently passed; live scanners are the residual).

**Executive (§6):** FR-011 ✅ (stages derived from ledger; **`3pwr run` drives the whole loop**, plan 013 — auto mode stops only at the two human gates, composing `specify workflow run`), FR-019 ✅, FR-014 ✅, FR-015 ✅,
FR-016 ◑ (tasks gated by `scope-check`; commit-message tagging not gated), FR-017 ✅, FR-063 ✅ ·
FR-012 ◑ / FR-013 ◑ (**oracle leg now dispatched headlessly** via `3pwr oracle dispatch` + Spec Kit
`workflow run` under a non-coder integration, plan 011; the **coder** leg staying interactive/in-IDE, and
a live end-to-end run under a non-Copilot agent, are the residual) · FR-062 ✅ (Phase-A/B ordering proven
from the ledger seq; enforced at High-risk `advance`), FR-018 ◑ (advisory) · FR-060 ⬜, FR-061 ⬜
(context strategy — harness-limited).

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
(`3pwr deps-check` flags installed-toolchain drift incl. Spec Kit vs `.3powers/config/dependencies.yaml`)
and strengthened FR-044/046/A1 (a **provider-agnostic** Spec Kit extension + substrate-neutral role config,
eval-gated); live multi-integration headless dispatch stays the residual (FR-012/013 ◑).

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
   via Spec Kit `workflow run` under a non-coder integration, inside a **sanitized git worktree** with the
   implementation/plan/tasks/contracts physically absent — attested by a worktree manifest hash in the ledger
   and enforced at a High-risk `advance` (`require_dispatch`). Peeking stays an advisory. The residual is the
   *fuller* proof: the **coder** leg also headless under a different-family CLI, and a live end-to-end run
   under a non-Copilot agent (needs a second CLI integration installed).
2. **A1 packaging — now a real extension; live dispatch is the residual.** Plan 009 packaged 3Powers as a
   **provider-agnostic Spec Kit extension** (`.specify/extensions/3powers/`: the `/3pwr.*` commands + gate
   hooks, `integration: auto`, no hardcoded Copilot) and made the role config + agents substrate-neutral,
   eval-gated; `3pwr deps-check` pins the supported Spec Kit range and flags drift. What remains is the
   *live* cross-integration headless `workflow run` dispatch (running the judiciary isolated under a
   non-Copilot agent) — verifiable only with the Spec Kit runtime, and tied to the A3 read-path isolation in #1.

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
supported third-party versions (incl. Spec Kit) and flags drift; 3Powers ships as a **provider-agnostic
Spec Kit extension** (`.specify/extensions/3powers/`) with substrate-neutral, eval-gated role config. Live
multi-integration headless dispatch stays the residual.

**Plan 010 is done** ([`plan/010-observe-and-feedback.md`](../plan/010-observe-and-feedback.md)):
✅ **observe & feedback loop (§13, FR-054/055)** — `observe signal` routes a production signal to a
new-requirement backlog (not a patch) + moves the spec to the Observe stage; `observe coverage` reports
NFR instrumentation; `observe log-action`/`verify-actions` is a tamper-evident, attributable runtime
agent-action log. The 8th lifecycle stage is now reachable.

**Plan 011 is done** ([`plan/011-a3-live-headless-dispatch.md`](../plan/011-a3-live-headless-dispatch.md)):
✅ **A3 live headless dispatch — physical oracle read-path isolation (FR-021), oracle leg of FR-012/013.**
`3pwr oracle dispatch` builds a **sanitized git worktree** (implementation/plan/tasks/contracts physically
absent), runs the oracle authoring step headlessly via `specify workflow run` under a non-coder integration
(default `claude`), collects the authored tests, and records a signed **dispatch attestation** (integration
+ resolved model + worktree isolation manifest). `independence()`/High-risk `advance` **block** on a
missing-required or non-isolated dispatch (`roles.oracle.require_dispatch`), while the 008 peek/touch signal
stays advisory (NFR-001); dispatch never enters `gate run`. An optional **distinct oracle signer key** is
supported (two-key `verify`, NFR-005). The runtime is present in-repo (`specify` + `claude`), so the minimal
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
stage tracker, composing Spec Kit's `workflow run` (A1; the engine makes no model call, A3). In `auto` mode
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

Next, in priority order (breadth + the remaining hardening track):
- **Fuller A3** — the coder leg also headless under a second, different-family CLI (codex/gemini), and a
  live non-Copilot end-to-end `workflow run` verification (also completes `3pwr run`'s live executive leg).
- **Live design/Go runs** — playwright/axe/schema-diff for a real UI sample (FR-009) and a Go toolchain for
  the Go adapter's live gate run; catalog *publishing* of the `3powers` extension; model-driven eval layer
  (FR-050); cross-platform validation (NFR-003).

## 7. Pointers

- **Spec (law):** [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) · **Constitution:** [`.specify/memory/constitution.md`](../.specify/memory/constitution.md)
- **Plans:** [`plan/`](../plan/) (001→017 done) · **Agent guidance:** [`CLAUDE.md`](../CLAUDE.md), [`AGENTS.md`](../AGENTS.md)
- **References:** [`docs/references/speckit.md`](references/speckit.md), [`docs/references/trust-spine-tooling.md`](references/trust-spine-tooling.md)
- **How to verify the claims here:** run the commands in §2; every plan doc ends with a Verification section.
- **Git:** stacked local branches `plan-001-base-setup` → … → `plan-015-defect-design-go-adapter`
  (015 committed), plus a `docs/open-source-readiness` branch for this documentation pass; none merged to
  `main` yet.
- **External tools used by some gates** (optional; gates quarantine if absent): `gitleaks`, `osv-scanner`,
  `semgrep`; the TS adapter uses `biome`, `tsc`, `vitest`, `stryker`, `fast-check` via `npm`.
