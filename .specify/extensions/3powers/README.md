# 3Powers — Spec Kit extension

Packages the 3Powers judiciary as a Spec Kit **extension** (constraint 3PWR-A1): the independent oracle,
the deterministic gate suite, and the signed verdict ledger with local enforcement, wired into the
spec-driven lifecycle via hooks.

## Provider-agnostic (3PWR-A3)

No integration is hardcoded. Install into any project Spec Kit can dispatch — copilot, claude, gemini,
codex, … — and Spec Kit renders the `/3pwr.*` commands into that integration's format. 3Powers makes no
direct model-API calls; it reuses Spec Kit's integration registry + headless dispatch, and enforces only
that the oracle and coder resolve to **different model families** (3PWR-FR-022), never a specific vendor.

## Install

```bash
uv tool install ./engine                 # the `3pwr` CLI (the engine these commands drive)
specify extension install 3powers        # register + render the /3pwr.* commands for your integration
```

The supported Spec Kit range is pinned in [`.3powers/config/dependencies.yaml`](../../../.3powers/config/dependencies.yaml)
and checked by `3pwr deps-check` — so a drifting upstream release is flagged for adaptation rather than
breaking silently.

## Provides

| Command | Role |
|---|---|
| `/3pwr.oracle`  | Phase A — author the independent oracle from a sealed, spec-only bundle |
| `/3pwr.verify`  | run the gate suite + verify the signed ledger |
| `/3pwr.advance` | local enforcement of gates + ledger + sign-off before advancing |

Hooks: `after_tasks → 3pwr.oracle` (Phase A precedes Phase B), `after_implement → 3pwr.verify`.

> **Residual (needs the Spec Kit runtime).** Live cross-integration headless dispatch — running the
> judiciary *isolated* under a non-Copilot agent with no read path to the implementation — is exercised by
> Spec Kit's `workflow run` at install/run time; that end-to-end verification is outside this repository
> (see plan 009 "Out"). What ships here is the distributable extension + the provider-agnostic config.
