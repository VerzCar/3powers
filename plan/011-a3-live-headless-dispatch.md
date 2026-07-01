# Plan 011 — A3 live headless dispatch + physical oracle read-path isolation

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md) then the spec
> [`3Powers_Spec_v0.2.md`](../3Powers_Spec_v0.2.md) §3 (A1–A3), §6–§7 (oracle), §10–§11 (dispatch/agnosticism).
> Builds on plan 008 (structural oracle independence) and plan 009 (provider-agnostic Spec Kit extension).

## Context

Plan 008 made oracle independence *structural and ledger-anchored* but deferred the **physical** letter of
**3PWR-FR-021** — preventing the oracle author from *reading* `src/`/`plan.md`/`tasks.md`/`contracts/` —
because in a Copilot-only, interactive setting nothing on disk stops a peek. Plan 009 packaged 3Powers as a
provider-agnostic extension but left the *live* multi-integration `workflow run` dispatch (FR-012/013) as a
residual tied to it.

The blockers 008/009 cited are gone in this environment: `specify` 0.11.6.dev0 provides
`specify workflow run <yaml> -i k=v --json` with **per-step `integration:` binding**, and the `claude` CLI
(a headless, anthropic-family, non-coder agent) is installed and one `specify integration install claude`
away from being registered. What Spec Kit does **not** provide is filesystem isolation — `workflow run`
executes the agent in the repo working directory. So 3Powers provides isolation itself.

**Positioning:** 3Powers is not CLI-only for agent work — the `/speckit.*` and `/3pwr.*` commands run in the
IDE agent window (Copilot/Claude Code/…), watchable like Spec Kit; only the deterministic judiciary
(`3pwr` gates/ledger/`advance`) is a CLI. `oracle dispatch` is **opt-in, High-risk only** and does not
replace the in-IDE flow or impose a second CLI/model on normal users.

## What shipped

- **`3pwr oracle dispatch --spec-id <ID> --integration <claude> [--dry-run]`** (`oracle.py`, `cli.py`):
  builds a **sanitized ephemeral git worktree** from `HEAD` pruned of implementation/plan/tasks/contracts
  (FR-021's exact scope), copies in the sealed bundle (`ORACLE_BUNDLE.json`) + an empty `oracle-tests/`,
  runs the oracle authoring step headlessly via `specify workflow run .specify/workflows/3powers/oracle.yml`
  under a non-coder integration, collects the authored tests back into `tests/oracle/<ID>/`, and records
  **two** signed `oracle` ledger entries: the existing `record` (so `independence()` still finds authoring
  + coverage) and a new `dispatch` attestation (integration + resolved model + `isolation` block:
  `{method: git-worktree, manifest_hash, file_count, excluded_absent}`). Tears the worktree down in a
  `finally`. `--dry-run`/`--tests` build+attest isolation offline (no live agent).
- **Isolation proof** (`oracle.py`): `worktree_manifest`/`manifest_hash` (deterministic filetree hash) +
  `isolation_violations` (no implementation/plan/contracts path may remain) — the evidence recorded in the
  ledger and re-checked at `advance`.
- **`independence()` upgrade** (`oracle.py`): a new `require_dispatch` flag; when a dispatch attestation is
  present (or required), physical isolation becomes **blocking** — seal-bound, `excluded_absent` true with a
  `manifest_hash`, dispatched family ≠ coder family. The 008 peek/touch heuristics stay **advisory**
  (3PWR-NFR-001); dispatch never enters `gate run`. High-risk `advance` reads the policy from
  `roles.oracle.require_dispatch` (default false).
- **`.specify/workflows/3powers/oracle.yml`**: the per-step-integration authoring workflow (default
  `claude`), the FR-012/013 substrate-dispatch surface. Prerequisite: `specify integration install claude`.
- **Optional distinct oracle signer key (NFR-005)**: `keys.resolve_signing_key(root, role="oracle")` +
  `keygen --role oracle` (pub at `.3powers/keys/oracle.pub`), falling back to the primary signer when unset;
  `verify_ledger` accepts an entry signed by the primary **or** oracle key (single-key repos unchanged).

## Decisions

| Area | Decision |
|---|---|
| Isolation | Ephemeral `git worktree` at `HEAD`, pruned of implementation/plan/tasks/contracts; the dispatched agent's cwd is that worktree. Fits A2 (Git is the substrate); the implementation is *physically absent*. |
| Isolation proof | A worktree manifest hash recorded in the ledger; verified by asserting no excluded path remains. |
| Blocking boundary | At `advance`, High-risk only; dispatch is Phase-A provisioning, never in the deterministic verdict (NFR-001). |
| Opt-in | `require_dispatch` defaults **false** — the in-IDE model-switch flow stays valid and watchable; single-model users are unaffected. |
| Oracle key | Optional distinct Ed25519 identity with fallback to the primary; two-key `verify`. |
| Scope | **Oracle leg only.** The fuller dual-headless proof (coder also headless under a second, different-family CLI) is the residual (needs codex/gemini installed). Network egress is out of scope — **read-path** isolation only. |

## Verification

```bash
(cd engine && uv run ruff check . && uv run mypy src && uv run pytest)   # 191 tests green

# High-risk self-application stays green (NFR-006):
(cd engine && uv run python -m threepowers.cli --root .. gate run --path . --adapter python \
   --spec ../specs/002-engine-trust-spine/spec.md --tier High-risk --mutation --no-ledger \
   --paths src/threepowers/canonical.py src/threepowers/keys.py \
           src/threepowers/ledger.py src/threepowers/verify.py)

# Offline dispatch path (no live agent) — worktree isolation + attestation + blocking advance:
3pwr oracle seal --spec specs/<feature>/spec.md --spec-id <ID>
3pwr oracle dispatch --spec-id <ID> --dry-run --tests <authored-oracle-test-paths>
3pwr oracle verify --spec-id <ID> --require-dispatch
3pwr verify

# Minimal live proof (specify + claude present in this repo):
specify integration install claude
3pwr oracle dispatch --spec-id <ID> --integration claude
```

## Residual (→ plan 012+)

- **Plan 012 — model diversity: recommend, not force.** Relax the High-risk same-family refusal via the
  existing signed `deviation` (§14) + a warning, so single-model users (e.g. only Claude Code) are never
  walled off; keep FR-022 as the law. Standard/Cosmetic already don't force it.
- **Fuller A3**: the coder leg also headless under a second, different-family CLI; a live non-Copilot
  end-to-end `workflow run` verification.
- Catalog publishing; a third adapter; defect-flow (FR-008); design oracles (FR-009); root `LICENSE`
  (NFR-012); cross-platform (NFR-003).
