# Getting Started

A hands-on tour: install the engine, run the full gate suite on the bundled sample, read the verdict,
and watch the local trust spine enforce a green-gate-plus-sign-off rule before anything "ships". Every
command and its output below is real — you can reproduce it. New to the ideas? Skim
[Concepts](concepts.md) first; terms of art are defined in the [glossary](glossary.md).

## Prerequisites

What you need depends on the path you take. **Hard requirements**, every path:

- [`uv`](https://docs.astral.sh/uv/) — installs and runs the Python engine.
- `git` — the substrate the trust spine records against.

**Conditional requirements — per path:**

| Path | What you get | Additionally needs |
|---|---|---|
| **Gates-only (offline)** | the deterministic gate suite, signed ledger, `verify`, and `advance` — a signed verdict, no autonomy | nothing extra — no Spec Kit, no agent integration (the bundled TypeScript sample uses `npm`) |
| **Slash commands (in-IDE)** | drive each lifecycle stage by hand | VS Code with GitHub Copilot |
| **Autonomous (`3pwr run`)** | one command drives the whole lifecycle | GitHub Spec Kit (the `specify` CLI) **and** a coding-agent integration (e.g. Copilot) |

Spec Kit is upstream [`github/spec-kit`](https://github.com/github/spec-kit) — not a fork — installed
from a pinned tag:

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@<pinned-tag>
```

The currently supported pin lives in [`.3powers/config/dependencies.yaml`](../.3powers/config/dependencies.yaml)
(check yours with `3pwr deps-check`); see the [Spec Kit reference](references/speckit.md#install--init).

**Optional scanners.** Three gates shell out to external scanners. Each is **quarantined** when its tool
is absent — surfaced as *skipped* in the verdict, never silently passed — so you can start without them:

| Tool | Gate | When absent |
|---|---|---|
| `betterleaks` (or `gitleaks`) | `secret_scan` | gate quarantined — reported as skipped |
| `osv-scanner` | `dependency_scan` | gate quarantined — reported as skipped |
| `semgrep` | `sast` | gate quarantined — reported as skipped |

Everything below through §7 is the **gates-only path**: it reaches a signed green verdict with none of
the conditional or optional tools installed.

## 1. Install the engine

```bash
uv tool install ./engine
```
```
Installed 1 executable: 3pwr
```

`3pwr` is now on your PATH. Check it:

```bash
3pwr --version        # 3pwr 0.1.0
```

## 2. Create the independent signer

The trust spine signs every ledger entry with an identity that is **independent of the coding agents**.
Its private key is written **outside** the repo; only the public key is committed.

```bash
3pwr keygen
```
```
signer identity created: ed25519:ae1efc06d9e4e02e
  private key (keep OUTSIDE the repo): /Users/you/.config/3powers/3powers.key
  public key  (committed):             /Users/you/projects/3powers/.3powers/keys/ledger.pub

Point the engine at the private key with:
  export THREEPOWERS_SIGNING_KEY_FILE="/Users/you/.config/3powers/3powers.key"
```

The engine looks for the key via `$THREEPOWERS_SIGNING_KEY_FILE`, then `$THREEPOWERS_SIGNING_KEY` (a
base64 seed, handy for CI), then the default path above. Export the variable or rely on the default.

> This tutorial runs inside the already-initialized 3Powers repo, so `keygen` is all you need here. In
> **your own** project (new or existing), run **`3pwr init`** instead — the guided onboarding creates the
> signer, the baseline config, and your language adapter in one step. See the
> [CLI reference](cli-reference.md#init--guided-onboarding-new-or-existing-project).

## 3. Run the gate suite on the sample

The repo ships a small TypeScript sample, [`examples/validation-utils/`](../examples/validation-utils/)
(Spec ID `VUTIL`). Install its dev tools once, then run every gate against it at the **Standard** tier:

```bash
(cd examples/validation-utils && npm install)
3pwr gate run --path examples/validation-utils \
              --spec specs/001-validation-utils/spec.md --tier Standard
```
```
verdict FAIL  spec=VUTIL tier=Standard adapter=typescript
  ✓ format · biome
  ✓ lint · biome
  ✓ types · tsc
  ✓ tests · vitest
  ✓ diff_coverage · 3pwr-covdiff  (100.0% ≥ 80.0%)
  ✗ dependency_scan · osv-scanner
      - GHSA-4x5r-pxfx-6jf8 in @babel/core
      - GHSA-2g4f-4pwh-qvx6 in ajv
      - GHSA-67mh-4wv8-2f99 in esbuild
      - GHSA-52f5-9888-hmc6 in tmp
      - GHSA-ph9p-34f9-6g65 in tmp
  ✓ secret_scan · gitleaks
  ✓ gate_gaming · 3pwr-gaming
  ✓ spec_conformance · 3pwr-conformance  (5 requirements traced)
  failures:
    • vulnerable_dependency: GHSA-4x5r-pxfx-6jf8 in @babel/core; GHSA-2g4f-4pwh-qvx6 in ajv; ...
  ↳ ledger entry #0 signed by ed25519:4fd71c543b0f499c
```

**Read the verdict** (this is the whole point — a human identifies the problem
without opening any agent transcript):

- Gates ran **cheapest-first**: the format/lint/type floor, then tests + `diff_coverage`,
  then the scanners and conformance.
- The code itself is clean — **diff_coverage is 100%** on changed lines, and all five
  `VUTIL` requirements trace to a test (**spec_conformance**).
- But `dependency_scan` is **red**: `osv-scanner` found real, current advisories in the sample's
  transitive dev dependencies. The failure is **actionable** — it names the class
  (`vulnerable_dependency`) and the exact advisory + package. That's the gate suite doing its job, not a
  bug in the sample.
- The run appended **one signed entry** to the ledger (`#0`). One run → one normalized verdict,
  written to `.3powers/verdicts/latest.json` and recorded in the ledger.

> Pass `--json` for the machine-readable verdict (the same artifact agents consume).
> Pass `--no-ledger` to run the gates without recording an entry.

## 4. Inspect the trust spine

Every verdict is signed and chained. Verify the chain **offline**:

```bash
3pwr verify
```
```
ledger OK — 1 entry, chain and signatures intact
```

See the ledger and the lifecycle stage it implies (the stage is *derived from the ledger*, not stored
elsewhere):

```bash
3pwr ledger show
```
```
#  0 verdict       2026-06-30T20:48:16Z VUTIL    sig=ed25519:4fd71c543b0f499c
```
```bash
3pwr status
```
```
VUTIL      stage=Spec       verdict=fail
```

## 5. Enforcement: a red gate blocks the advance

`advance` is the local gate that recovers what a CI branch-protection rule would normally give you — but
offline and signed. Try to ship while the verdict is red and there's no sign-off:

```bash
3pwr advance --stage ship --spec-id VUTIL
```
```
REFUSED to advance to 'ship':
  - latest verdict is red
  - no human sign-off recorded
```

It refuses for **both** reasons: the gates aren't green, and no human has signed off.
Enforcement is uniform — there's no fast path for an agent or an admin.

To get to green here you'd remediate the advisory (update the dependency), or — if it's a dev-only
false positive — record an explicit, reversible **deviation** (a signed, time-bound exception). You never
reach green by deleting the gate.

## 6. The green happy path

Here's the successful flow, demonstrated on the engine's own format/lint/type floor (which is green).
A passing verdict, a human sign-off recorded *after* it, then a clean advance:

```bash
# a green verdict (Cosmetic tier = the deterministic floor only)
3pwr gate run --path engine --adapter python \
              --spec specs/002-engine-trust-spine/spec.md --tier Cosmetic
```
```
verdict PASS  spec=3PWR tier=Cosmetic adapter=python
  ✓ format · ruff
  ✓ lint · ruff
  ✓ types · mypy
  ↳ ledger entry #1 signed by ed25519:4fd71c543b0f499c
```
```bash
3pwr signoff --approver "$(git config user.name)" --stage review --spec-id 3PWR
3pwr advance --stage ship --spec-id 3PWR
```
```
sign-off recorded by carlo.verzeri for stage 'review' (ledger seq=2)
advanced to 'ship' (ledger seq=3)
```

Now the ledger holds the full, signed audit trail — spec → verdict → sign-off → advance — and it still
verifies end to end:

```bash
3pwr verify        # ledger OK — 4 entries, chain and signatures intact
3pwr ledger show
```
```
#  0 verdict       2026-06-30T20:48:16Z VUTIL    sig=ed25519:4fd71c543b0f499c
#  1 verdict       2026-06-30T20:49:51Z 3PWR     sig=ed25519:4fd71c543b0f499c
#  2 signoff       2026-06-30T20:49:51Z 3PWR     sig=ed25519:4fd71c543b0f499c
#  3 stage_advance 2026-06-30T20:49:51Z 3PWR     sig=ed25519:4fd71c543b0f499c
```

If anyone edits a recorded entry, `3pwr verify` fails — the chain and signatures no longer line up. That
is tamper-**evidence**: you can't quietly rewrite history.

## 7. Self-application at High-risk

3Powers gates its own trust-spine code at the strictest tier — the proof that it eats its own dog food.
This run includes **mutation testing** scoped to the four trust-spine modules:

```bash
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)
```
```
verdict PASS  spec=3PWR tier=High-risk adapter=python
  ✓ format ✓ lint ✓ types ✓ tests
  ✓ diff_coverage · 3pwr-covdiff  (100.0% ≥ 95.0%)
  ✓ mutation · mutmut
  ✓ sast ✓ dependency_scan ✓ secret_scan ✓ gate_gaming
  ✓ spec_conformance · 3pwr-conformance  (31 requirements traced)
```

Mutation testing injects faults into the trust-spine code and checks the tests catch them; a surviving
mutant is reported as a missing assertion. The score (~89%) clears the High-risk
threshold (70%). See [Engine Architecture](engine-architecture.md#mutation) for how it works.

## Driving the full lifecycle

The eight stages (Discovery → Spec → Plan → Build → Verify → Review → Ship → Observe) run through GitHub
Copilot slash commands. Open the repo in VS Code with Copilot; `/speckit.*` and `/3pwr.*` appear as chat
commands. On a feature:

```
/speckit.specify → /speckit.clarify → /speckit.plan → /speckit.tasks
   → switch the chat model →  /3pwr.oracle      (Phase A: independent tests, different family)
   → switch back →            /speckit.implement
   → /3pwr.verify → /3pwr.review → /3pwr.signoff → /3pwr.advance
```

The **model switch** is what makes the oracle independent: the judiciary authors the answer key
([Phase A](glossary.md#phase-a--phase-b)) with a different model family than the coder, from the spec
alone. On an *existing* repo, start with `/3pwr.characterize` — see [Brownfield Adoption](brownfield.md).

## The whole lifecycle in one command

You don't have to run the stages by hand. `3pwr run` drives the eight-stage lifecycle end to end — it
composes the Spec Kit workflow and the judiciary gates, streams a live stage tracker, and in `auto` mode
**stops only at the two human gates** (approving the spec, and the final sign-off):

```bash
# A quick, offline read on what you're about to build: the kind(s) of change + a suggested risk tier.
3pwr classify "add rate limiting to the login endpoint"

# Drive the lifecycle; it pauses for you at the spec-approval and sign-off gates.
3pwr run "add rate limiting to the login endpoint" --mode auto
3pwr run --status --spec-id RUN     # the live stage tracker, derived from the ledger
```

`3pwr classify` only *suggests* the kind and tier (it shapes which gates and oracle strategy apply); the
human sign-off is always yours. The step-by-step slash-command flow above stays valid for a hands-on run.

> `3pwr run` needs the **autonomous path** prerequisites — the `specify` CLI plus a coding-agent
> integration (see [Prerequisites](#prerequisites)). Without them it fails fast naming the missing tool;
> `--dry-run` simulates the loop offline. See [Troubleshooting](troubleshooting.md) if a run won't start.

## Supported languages & tooling matrix

A language plugs in through a declarative **adapter** (`.3powers/adapters/<lang>/adapter.yaml`) with zero
changes to the core. A framework like **Next.js is covered by its language adapter (TypeScript)** — there
is no framework-specific setup. `3pwr init` sets up the adapter for your chosen language (guided).

| Language | Detected by | Format | Lint | Types | Test (coverage) | Mutation | Design oracles | Status |
|---|---|---|---|---|---|---|---|---|
| **TypeScript** | `package.json` + `tsconfig.json` | Biome | Biome | tsc | Vitest (LCOV) | Stryker | Playwright · Axe · oasdiff · Pact | Reference — exercised end-to-end |
| **Python** | `pyproject.toml` | Ruff | Ruff | mypy | pytest (LCOV) | mutmut | — | Reference — gates the engine itself |
| **Go** | `go.mod` | gofmt | go vet | go build | go test → gcov2lcov (LCOV) | go-mutesting | — | Reference — wired |

The language-agnostic gates — `diff_coverage`, `spec_conformance`, `dependency_scan`, `secret_scan`, and
`sast` — run the same way for every adapter. Adding a language is "write a manifest," not a core change —
see the adapter contract at [`.3powers/adapters/CONTRACT.md`](../.3powers/adapters/CONTRACT.md).

## Next

- **[CLI Reference](cli-reference.md)** — every command and flag.
- **[Engine Architecture](engine-architecture.md)** — what each gate does and how the ledger works.
- **[Concepts](concepts.md)** — the why behind the workflow.
- **[Troubleshooting](troubleshooting.md)** — the common failures with their exact fixes.
- **[Glossary](glossary.md)** — every term of art, defined once.
