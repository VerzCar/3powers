# 3Powers — Project Status & Handoff

> **Read this first if you're picking up 3Powers cold.** It says what the project is, how to run it,
> exactly how far we are **validated against the spec**, whether we're heading the right way, and what
> to do next. The spec — [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) (Spec ID `3PWR`) — is the
> single source of truth; this document is checked against it. Last updated after **plan 005**.

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
(cd engine && uv sync --extra dev && uv run pytest)          # 79 tests
(cd engine && uv run ruff check . && uv run mypy src)        # lint + types

# self-application: 3Powers gating its own engine (the proof it works)
3pwr gate run --path engine --adapter python \
     --spec specs/002-engine-trust-spine/spec.md --tier Standard --base 3e20aad --no-ledger
3pwr eval                 # prompt/constitution eval set (FR-050)
3pwr verify               # recompute the ledger chain + signatures, offline
```

**The lifecycle runs through GitHub Copilot slash commands** (open the repo in VS Code):
`/speckit.specify → clarify → plan → tasks` → **switch chat model** → `/3pwr.oracle` (Phase-A oracle,
different model family) → **switch back** → `/speckit.implement` → `/3pwr.verify` → `/3pwr.review` →
`/3pwr.signoff` → `/3pwr.advance`. The runnable sample is [`examples/validation-utils/`](../examples/validation-utils/)
(spec id `VUTIL`). Full command list + pinned tool versions are in [`AGENTS.md`](../AGENTS.md).

## 3. Repo map

```
engine/                     # the `3pwr` engine (Python, uv tool) — cli, gates, scanners, gaming,
                            #   conformance, covdiff, scope, lifecycle, provenance, evals,
                            #   ledger, verify, keys, verdict, config, canonical (+ tests/)
.3powers/                   # in-repo trust spine: config/{risk-tiers,roles}.yaml, schemas/*.json,
                            #   adapters/{CONTRACT.md,typescript,python}, eval/cases.yaml,
                            #   semgrep-rules.yml, ledger.jsonl, keys/ledger.pub
.specify/ + .github/        # Spec Kit; 3Powers constitution + template overrides + /3pwr.* commands
specs/                      # authoritative specs (the epic + per-feature); 002 = the engine's own
examples/validation-utils/  # runnable TypeScript sample
docs/references/            # compacted Spec Kit + trust-spine tooling references
plan/                       # the continuous plan series 001..005 (006 = next, see plan/006-*.md)
```

## 4. Status — validated against the spec

**§17 scope phasing:**

| Slice | Status |
|---|---|
| **v0.1 — Trust-spine MVP** | ✅ complete (plans 001–003) |
| **v0.5 — Full judiciary** | ✅ complete (plans 004–005) |
| **v1.0 — Lifecycle & ecosystem** | ⬜ not started (this is next) |

**Requirement-level (✅ done · ◑ partial/approximated · ⬜ missing).** Unlisted FRs in a ✅ block are done.

**Legislative (§5):** FR-001 ✅, FR-002 ✅, FR-059 ✅, FR-003 ✅, FR-004 ✅, FR-010 ✅ ·
FR-005 ◑ (Spec Kit `/clarify` exists; "block on unmeasurable" is prompt-level) ·
FR-006 ◑ (sign-off recorded + enforced before *ship*; not hard-gated before *build*) ·
FR-007 ◑ (constitution/plan-template guidance, not a gate) · FR-058 ⬜ (work-kind inference) ·
FR-008 ⬜ (defect→regression-test flow) · FR-009 ⬜ (design oracles).

**Executive (§6):** FR-011 ✅ (stages derived from ledger), FR-019 ✅, FR-014 ✅, FR-015 ✅,
FR-016 ◑ (tasks gated by `scope-check`; commit-message tagging not gated), FR-017 ✅, FR-063 ✅ ·
FR-012 ◑ / FR-013 ◑ (roles bind to model *families* in config; dispatch is interactive Copilot, not
Spec Kit headless `workflow run`) · FR-062 ◑, FR-018 ◑ (advisory) · FR-060 ⬜, FR-061 ⬜ (context
strategy — harness-limited).

**Judiciary — oracle (§7):** FR-022 ✅ (engine refuses same family), FR-023 ✅ ·
FR-020 ◑, FR-021 ◑ (judiciary prompt forbids reads, but **isolation is procedural, not structural** in a
Copilot-only setting), FR-024 ◑ (required by prompt/sample, not enforced), FR-025 ◑.

**Judiciary — gate engine (§8):** FR-026 ✅, FR-027 ✅ (TypeScript + Python), FR-028 ✅, FR-029 ✅,
FR-030 ✅, FR-032 ✅, FR-033 ✅, FR-034 ✅, FR-035 ✅, FR-065 ✅ ·
FR-031 ◑ (mutation wired + scoped; the **mutmut src-layout runner doesn't execute per-change yet**) ·
FR-064 ◑ (layers tracked, not tier-required).

**Judiciary — trust spine (§9):** FR-036 ✅, FR-037 ✅, FR-038 ✅, FR-039 ✅, FR-040 ✅, FR-041 ✅,
FR-042 ✅, FR-066 ✅, FR-067 ✅, FR-068 ✅, FR-069 ✅, FR-070 ✅, FR-071 ✅ ·
FR-043 ⬜ (CI re-validation — optional per A4).

**Agnosticism / config (§10–11):** FR-044 ✅, FR-045 ✅, FR-046 ✅, FR-047 ✅, FR-048 ✅, FR-049 ✅,
FR-050 ✅ (deterministic eval set; model-driven layer is future).

**v1.0 (§12–14):** FR-051/052/053 ⬜ (brownfield), FR-054/055 ⬜ (observe), FR-056/057 ⬜ (emergency/deviation).

**NFRs:** NFR-001 ✅, NFR-004 ✅, NFR-005 ✅, NFR-007 ✅, NFR-008 ✅, NFR-010 ✅, NFR-011 ✅,
NFR-013 ✅, NFR-014 ✅ ·
**NFR-006 ◑ — important:** the engine self-gates green at **Standard**; the spec requires the trust-spine
components to pass at **High-risk** (mutation), which is **not yet met** (blocked on the mutmut runner) ·
NFR-002 ◑ (perf budgets not measured), NFR-003 ◑ (built/tested on macOS only), NFR-009 ◑ (spend config
exists, not orchestrated), NFR-012 ◑ (Apache-2.0 declared in pyproject; **no root `LICENSE` file yet**),
NFR-015 ◑ (scanners quarantine when absent; no general flaky-quarantine), NFR-016 ◑ (provenance/deploy-gate
exist; the engine's own install path doesn't self-verify yet).

## 5. Are we going the right way? (honest direction check)

**Yes — the core is sound and on-spec.** We built the **High-risk trust spine first** (correct per §4),
followed §17 phasing exactly (v0.1 then v0.5), and the engine **self-applies** (gates its own code green).
The deterministic, offline, signed trust spine — the spec's distinctive promise — is real and verifiable.

**But three approximations are the real risk, and they touch the spec's central thesis. Harden these
before adding breadth:**

1. **Oracle independence is procedural, not structural (FR-021/022, FR-062).** This *is* the thesis —
   "tests written by a different mind than the code." Today we enforce it with the `/3pwr.oracle` prompt,
   `roles-check` (engine refuses same family), authoring order, and ledger records. A determined coder
   could still peek. Closing this likely means using **Spec Kit's headless dispatch (A3)** to run the
   judiciary as an isolated step with a different model and no read path to the implementation.
2. **Self-application is only at Standard, not High-risk (NFR-006).** The spec explicitly requires the
   trust-spine modules to pass their own **High-risk** bar (mutation). Blocked on the mutmut↔src-layout
   runner. Until closed, "3Powers is built with 3Powers at High-risk" is not fully true.
3. **A1 packaging drift.** The spec says 3Powers ships as Spec Kit **preset(s)/extension(s)/workflow(s)**
   via catalogs and reuses Spec Kit's `workflow run` dispatch. We layered via confirmed primitives
   (templates + custom commands + a standalone `3pwr` engine) and drive it interactively in Copilot.
   That was the right call to get a working spine fast, but catalog/workflow packaging (and the headless
   dispatch in #1) remain to make it truly portable and to enable structural oracle isolation.

None of these block use today; they are the difference between "works and self-applies" and "fully
delivers the spec's guarantees." **Recommendation:** treat them as a *hardening track* and do the
highest-value one (NFR-006, High-risk self-application) at the front of the next phase — it's the
clearest unmet, stated requirement and it validates everything else.

## 6. What's next (roadmap)

Recommended next plan is written up in [`plan/006-v1.0-and-hardening.md`](../plan/006-v1.0-and-hardening.md).
Its shape:

- **A — Close NFR-006 (self-application at High-risk):** finish the mutmut src-layout runner; raise the
  trust-spine modules to the High-risk mutation bar; run the engine green at `--tier High-risk`.
- **B — Brownfield Stage Zero (§12, FR-051/052/053):** report-only mode, ratchet-to-blocking on changed
  code only, characterization-test reconstruction — the highest-value adoption feature for existing repos.

Then, in priority order, the rest of v1.0 and the hardening track:
- Emergency & deviation paths (§14, FR-056/057) — small; the deviation mechanism is also the sanctioned
  way to accept a `gate_gaming`-flagged suppression.
- Observe / feedback loop (§13, FR-054/055).
- **Structural oracle independence** via Spec Kit headless dispatch (FR-021/062; direction risk #1).
- Catalog distribution as a Spec Kit extension/preset (A1; direction risk #3) + a **third adapter** (e.g. Go/Rust/Java).
- Loose ends: defect-flow (FR-008) & design oracles (FR-009); tier-required test layers (FR-064);
  a root `LICENSE` file (NFR-012); model-driven eval layer (FR-050); cross-platform validation (NFR-003).

## 7. Pointers

- **Spec (law):** [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) · **Constitution:** [`.specify/memory/constitution.md`](../.specify/memory/constitution.md)
- **Plans:** [`plan/`](../plan/) (001→005 done; 006 = next) · **Agent guidance:** [`CLAUDE.md`](../CLAUDE.md), [`AGENTS.md`](../AGENTS.md)
- **References:** [`docs/references/speckit.md`](references/speckit.md), [`docs/references/trust-spine-tooling.md`](references/trust-spine-tooling.md)
- **How to verify the claims here:** run the commands in §2; every plan doc ends with a Verification section.
- **Git:** five stacked local branches `plan-001-base-setup` → … → `plan-005-sast-and-eval`
  (`9f65ccb`), none merged to `main`, no remote configured (PRs need a GitHub repo + push first).
- **External tools used by some gates** (optional; gates quarantine if absent): `gitleaks`, `osv-scanner`,
  `semgrep`; the TS adapter uses `biome`, `tsc`, `vitest`, `stryker`, `fast-check` via `npm`.
