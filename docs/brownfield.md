# Brownfield Adoption (Stage Zero)

Most teams don't start from a clean repo. 3Powers is designed to **spread through an existing codebase
service by service** — no stop-the-world migration. This guide is the adoption path for a legacy project.
Commands and output below are real.

> **The core idea:** hold only **new and changed** code to the full process, leave existing code untouched
> until you modify it, and **pin** the behavior of any legacy module *before* you change it.

## The five steps

```
1. init        →  2. report-only   →  3. characterize   →  4. diff-scope   →  5. enforce
   adopt           see the debt        pin legacy            block the diff     full gates on new code
```

## 1. Adopt the trust spine

In the existing repo, lay down the `.3powers/` skeleton and create the independent signer:

```bash
3pwr init
3pwr keygen
export THREEPOWERS_SIGNING_KEY_FILE="$HOME/.config/3powers/<repo>.key"
```

You'll also need a language **adapter** manifest for your stack (see
[`CONTRACT.md`](../.3powers/adapters/CONTRACT.md); the Python, TypeScript, and Go reference adapters are
good templates) and a `risk-tiers.yaml` (copy the one in this repo).

## 2. See the debt without blocking anyone (`--report-only`)

Run the full suite in **report-only** mode. It emits a complete verdict and records it, but **never
blocks** — so legacy debt doesn't wall off every merge on day one:

```bash
3pwr gate run --path . --tier Standard --report-only
```
```
  ✓ secret_scan · betterleaks
  ✓ gate_gaming · 3pwr-gaming
  ✓ spec_conformance · 3pwr-conformance  (5 requirements traced)
  failures:
    • vulnerable_dependency: GHSA-4x5r-pxfx-6jf8 in @babel/core; ...
  ⓘ report-only: verdict emitted but not enforced
```
```bash
echo $?      # → 0  (report-only never fails the run)
```

Now you have an honest baseline of where the codebase stands — coverage, scanner findings, untested
requirements — without forcing anyone to fix it all at once. A report-only verdict is **advisory**: it's
recorded in the ledger but `advance` ignores it, so it can't be used to ship.

## 3. Pin a legacy module before you touch it (`characterize`)

Before you change an un-specified module, **reconstruct the spec it implicitly satisfies** and lock its
current behavior with characterization tests that serve as its oracle. The module is parsed statically —
never executed at generation time — so this is safe on untrusted legacy code:

```bash
3pwr characterize --module src/legacy/money.py
```
```
characterized money.py → spec MONEY (3 symbol(s), 3 requirement(s))
  spec:  specs/001-money-characterization/spec.md
  tests: src/legacy/characterization/test_money_characterization.py
```

It writes two artifacts. A **spec stub** with one reconstructed requirement per public symbol, a risk
tier, and a non-goals section that's honest about what it is:

```markdown
# Characterization Specification: src/money.py
**Spec ID**: MONEY
**Risk Tier**: Standard
**Status**: Reconstructed

## Non-Goals
- This spec does **not** define *desired* behavior; it freezes the module's **observed** behavior
  as an oracle so the code can be safely changed later.

### Functional Requirements
- **MONEY-FR-001**: The system shall preserve the observed behavior of `canonical_bytes` in `src/money.py`…
- **MONEY-FR-002**: The system shall preserve the observed behavior of `sha256_hex` …
- **MONEY-FR-003**: The system shall preserve the observed behavior of `hash_payload` …
```

…and a **runnable characterization test** that references each reconstructed requirement ID (so
spec-conformance traces it) and pins the module's public surface:

```bash
(cd <project> && pytest src/legacy/characterization/)      # → 3 passed
```

The generated tests pin the public *surface* (the symbols exist and are callable). Your next step is to
strengthen them into **golden masters**: call each symbol with representative inputs and assert today's
return value. Now any change that alters behavior is caught — you can refactor `money.py` with a safety net.

> When the module re-enters the legislature for real work, replace the reconstructed placeholders with
> genuine EARS intent (the stub says so in its non-goals).

## 4. Block only the diff (`--diff-scope`)

Once you're ready to *enforce* on changed code, ratchet from report-only to **blocking, but scoped to the
diff**. With `--base` and `--diff-scope`, diff-coverage measures only changed lines and the file-based
scanners (SAST, secret) only count findings in changed files — pre-existing legacy issues don't block your
merge:

```bash
3pwr gate run --path . --tier Standard --base main --diff-scope
```

This is the heart of gradual adoption: a developer touching one file is held to the full bar **on that
file**, while the untouched legacy is left alone until someone modifies it.

## 5. Enforce — and raise the bar on the trust-critical parts

For genuinely new code, run the full suite blocking (no `--report-only`). For the most trust-critical
capability areas, scope a **High-risk** run (mutation included) to just those files, exactly as 3Powers
does to its own trust spine (risk-tier scoping per capability):

```bash
3pwr gate run --path . --tier High-risk --mutation \
              --paths src/payments/ledger.py src/payments/signing.py
```

Then the normal lifecycle applies — sign-off, `advance`, provenance at the deploy gate. See
[Getting Started](getting-started.md) for the full flow.

## Driving it in Copilot

The brownfield entry point has its own command: open the repo in VS Code with Copilot and run
**`/3pwr.characterize`** on a legacy module. It reconstructs the spec, scaffolds the tests, helps you fill
in the golden masters, and confirms spec-conformance traces the reconstructed requirements — all without
changing the module itself.

## Summary

| Goal | Command |
|---|---|
| Adopt the spine | `3pwr init` + `3pwr keygen` |
| See the debt, block nothing | `3pwr gate run … --report-only` |
| Pin a legacy module | `3pwr characterize --module <path>` |
| Enforce on the diff only | `3pwr gate run … --base <ref> --diff-scope` |
| Harden the trust-critical files | `3pwr gate run … --tier High-risk --mutation --paths <files>` |

See also: [Concepts](concepts.md) · [Getting Started](getting-started.md) · [CLI Reference](cli-reference.md).
