# Plan 017 — Trust-spine hardening (HARDN): key custody, continuity, anchoring & anti-gaming

> **Cold start:** read [`docs/STATUS.md`](../docs/STATUS.md) and the governing feature spec
> [`specs/005-trust-hardening/spec.md`](../specs/005-trust-hardening/spec.md) (Spec ID `HARDN`,
> **High-risk**). Epic context: [`3Powers_Spec_v0.2.md`](../specs/3Powers_Spec_v0.2.md) — the ledger
> is the trust spine (§9), the oracle is independent (§7), and no gate is ever satisfied by weakening
> it (3PWR-FR-032). The new [`docs/threat-model.md`](../docs/threat-model.md) is the map of what all
> of this proves. Use `uv run python -m threepowers.cli` — the installed `3pwr` alias may be stale.

## Context

An external architecture review (2026-07-02) checked 3Powers against its founding playbook and found
three honest gaps in the trust mechanisms themselves. **(1)** The ledger is tamper-*evident*, not
tamper-*proof* — an agent with shell access on the signing machine can read the private key, forge
entries, or regenerate ledger + key pair wholesale; the committed public key could be swapped in an
unremarkable git diff; and none of these custody assumptions were documented anywhere. **(2)** The
oracle's "different model family" was self-reported via `oracle record --model` — nothing bound the
claim to the process that ran. **(3)** Spec-conformance was regex ID-matching — a comment containing
`// covers X-FR-001` above an empty test traced a requirement, and mutation (the compensating
control) ran only at High-risk. Plan 017 closes each gap with deterministic, local mechanisms plus
one versioned threat-model document, keeping the verdict path model-free and offline
(3PWR-NFR-001/004).

## Scope

**In (delivered):**

1. **Threat model (HARDN-FR-001)** — [`docs/threat-model.md`](../docs/threat-model.md): what the
   ledger/provenance prove, the five tamper classes `verify` detects (chain break, gap, payload
   edit, signature mismatch, key swap), what it cannot detect (key-holder forgery absent an
   anchor), the custody boundary, and the self-reported nature of the oracle claim outside
   dispatch. Linked from `README.md` + `SECURITY.md`; docs-conformance-tested.
2. **Custody hygiene (HARDN-FR-002)** — `keygen`/`rotate-key` refuse to create a private key inside
   the working tree; `3pwr verify` runs a custody preflight and fails with a `key_custody` finding
   on an in-tree or group/other-readable key file. No deviation path — the remedy is to fix custody.
3. **Core secret check (HARDN-FR-003)** — the secret gate detects committed `ed25519-priv` material
   with a built-in check that ALWAYS runs; only the external betterleaks/gitleaks portion can
   quarantine.
4. **Key continuity (HARDN-FR-004)** — a `key_rotation` ledger entry authored by the *outgoing* key
   and carrying both the previous and the successor public key; `verify` walks the succession
   span-by-span and fails with an *unrotated key change* finding when the committed pubkey does not
   descend from the genesis key (SC-001). New `3pwr rotate-key`. Rotation-free ledgers verify
   byte-identically (HARDN-NFR-003).
5. **Opt-in anchoring (HARDN-FR-005)** — `3pwr anchor` records the head (seq + entry hash) as the
   annotated git tag `3powers/anchor/<seq>` (the reference witness) + a local signed `anchor`
   receipt; `--push` is the only network operation. `3pwr verify --anchored` fails on truncation or
   rewrite behind the anchor — catching wholesale regeneration by a key holder, which plain verify
   cannot see (SC-003). Plain `verify` is untouched and offline.
6. **External signing (HARDN-FR-006)** — a `Signer` protocol + `CommandSigner`: with
   `$THREEPOWERS_SIGNER_CMD` (or `$THREEPOWERS_ORACLE_SIGNER_CMD`) set, signing pipes the canonical
   bytes to the command's stdin and reads a base64 Ed25519 signature from stdout — the seed is never
   readable by the engine (SC-004); a broken signer fails loudly, never falling back. Verification
   is unchanged.
7. **Oracle model attestation (HARDN-FR-007)** — `independence()` cross-checks the self-reported
   record family against the ledger-attested dispatch integration; a contradiction blocks a
   High-risk `advance`. Without a dispatch, `oracle verify` states the claim is self-reported
   (advisory).
8. **Conformance ID-binding (HARDN-FR-008)** — a requirement traces only when its ID is bound to a
   test **declaration** (name/title line or the adjacent docstring); a comment-only mention fails as
   the new `untraced_requirement` class (SC-005). Both existing binding styles keep passing.
9. **Assertion-bearing tests (HARDN-FR-009)** — every requirement-bound test needs ≥1 assertion,
   with patterns declared per adapter (`conformance:` block in all three manifests + scaffold
   copies + CONTRACT.md); assertion-free bound tests fail as `weak_test`; pattern-less adapters
   quarantine visibly (3PWR-NFR-015). One read per file (HARDN-NFR-002, proven by test).
10. **Gaming flag (HARDN-FR-010)** — `gate_gaming` flags newly added assertion-free
    requirement-referencing tests (diff + untracked, suffix-aware declaration patterns), routed to
    mandatory human review; sanctioned only via `3pwr deviation --gate gate_gaming`. The
    removed-assertion signal is now *net per file*, so refactors don't false-positive.
11. **Diff-scoped mutation knob (HARDN-FR-011)** — per-tier `diff_mutation: true` + `--base` runs
    mutation over the changed source files against the tier's `mutation_score` (SC-006); only ever
    *adds* a gate; missing tool quarantines.

**Out (per the spec's non-goals):** tamper-*proofing* against a key holder before any anchor;
mandatory anchoring or hardware keys; end-to-end cryptographic model verification; semantic test
judgment in the verdict path; changes to existing entry-kind formats; any gate weakening; a concrete
hardware-token integration (the capability is the command protocol).

## Decisions

| Area | Decision | Why |
|---|---|---|
| Custody violations | Fail `3pwr verify`; **no deviation relief** | The fix (move key / `chmod 600` / rotate) is trivial; SC-002 wants a named, actionable finding |
| Rotation chain state | The rotation payload carries the *previous* public key too | Every span verifies from ledger + committed key alone — no external state (3PWR-NFR-004/010) |
| Anchoring witness | Annotated git tag `3powers/anchor/<seq>`; `--push` explicit | The spec names a signed git ref/tag as reference witness; keeps plain verify offline (HARDN-NFR-001) |
| External signer protocol | Subprocess: canonical bytes → stdin, base64 sig → stdout, self-checked against the committed pubkey at signing time | Provider-agnostic (wraps ssh-agent/HSM/enclave scripts); a wrong key fails immediately, never silently |
| `rotate-key` signer | Software-key chain only | The rotation must *author* with the outgoing key's material; hardware-key rotation is an operator act |
| Binding definition | Declaration line + adjacent docstring/title string; block = declaration → next declaration at ≤ indentation | Keeps the engine's `def` + docstring idiom and the sample's `describe("ID: …")` both passing (FR-008 acceptance); nesting-safe for `describe/it` |
| Untraced vs untested | Two classes: `untested_requirement` (never mentioned) and `untraced_requirement` (mentioned, not bound) | More actionable than collapsing them; matches the acceptance wording |
| Legacy adapters | No `test_declarations` → mention-based trace + visible quarantine; no `assertion_patterns` → weak-test check skipped + visible quarantine | HARDN-NFR-003: degrade to quarantine, never failure or silent pass |
| Gaming declarations | Per-suffix patterns (py/ts/go) | A TS snippet quoted inside a Python test fixture must not false-positive (self-application) |
| `diff_mutation` grading | Against the tier's existing `mutation_score` | The tier table stays the single source of thresholds (3PWR-FR-032) |
| FR-007 ambiguity | `integration_family("")` (e.g. copilot) cannot contradict | The in-IDE picker's family is unknown; deterministic means no guessing |

## What landed (files)

- `engine/src/threepowers/keys.py` — custody findings, `inside_working_tree`, `Signer` protocol,
  `CommandSigner`, `resolve_signer` (High-risk mutation scope).
- `engine/src/threepowers/ledger.py` — `key_rotation` + `anchor` entry kinds, `rotation_payload`,
  `append` accepts any `Signer`.
- `engine/src/threepowers/verify.py` — span-based succession verification + unrotated-key-change.
- `engine/src/threepowers/anchor.py` — new: head/tag/receipt/latest-anchor/`check_anchored`
  (in the mutation scope).
- `engine/src/threepowers/scanners.py` — core `ed25519-priv` scan, always on.
- `engine/src/threepowers/oracle.py` — FR-007 cross-check + self-reported advisory.
- `engine/src/threepowers/conformance.py` — single-pass declaration binding, `untraced_requirement`,
  `weak_test`, quarantine paths; `run_conformance(conformance_cfg=…)`.
- `engine/src/threepowers/gaming.py` — weak-added-test flag, suffix-aware declarations,
  net-per-file removed-assertion signal.
- `engine/src/threepowers/gates.py` — conformance cfg pass-through, `diff_mutation` trigger +
  changed-source scoping; `engine/src/threepowers/provenance.py` — `Signer` type.
- `engine/src/threepowers/cli.py` — keygen refusal, verify custody preflight + `--anchored`,
  `rotate-key`, `anchor`, `resolve_signer` at every signing site.
- Config/schema: both `risk-tiers.yaml` copies (`diff_mutation` knob), all six adapter manifests
  (`conformance:` block), `.3powers/adapters/CONTRACT.md`, `.3powers/schemas/ledger-entry.schema.json`.
- Docs: `docs/threat-model.md` (new), `README.md`, `SECURITY.md`, `docs/cli-reference.md`,
  `docs/STATUS.md`, `AGENTS.md`, `CLAUDE.md`, `CHANGELOG.md`.
- Tests: `test_custody.py`, `test_rotation.py`, `test_anchor.py`, `test_external_signer.py`,
  `test_model_attestation.py`, `test_conformance_binding.py`, `test_antigaming.py` (unit),
  `integration/test_diff_mutation_integration.py`, `e2e/test_hardening_e2e.py` — every HARDN FR/NFR
  bound across unit+integration+e2e (3PWR-FR-064); `specs/005-trust-hardening/tasks.md`
  (two-way coverage green).

## Verification (as run)

- `uv run pytest` — 389 passed; `ruff check` + `ruff format --check` + `mypy src` clean.
- Self-application at **High-risk**, scoped to the changed trust-spine modules (spec §4):
  `gate run --path . --adapter python --spec ../specs/005-trust-hardening/spec.md --tier High-risk
  --mutation --no-ledger --base main --paths src/threepowers/{keys,ledger,verify,anchor}.py`
  → **pass** (diff-coverage **95.7% ≥ 95**, mutation **79.61% ≥ 70** — 578/726 killed, conformance
  layers unit+integration+e2e for every HARDN requirement, gate_gaming + sast + secret_scan clean
  on this branch's own diff).
- `3pwr coverage-check --spec specs/005-trust-hardening/spec.md --tasks …/tasks.md` → PASS.
- SC-001…SC-007 each proven by a named test (see `test_rotation.py`, `test_custody.py`,
  `test_anchor.py`, `test_external_signer.py`, `test_conformance_binding.py`,
  `integration/test_diff_mutation_integration.py`, `e2e/test_hardening_e2e.py`).

## Residual

- **Anchoring is only as strong as the witness**: the reference witness is a git tag; pushing it
  (and fetching before `verify --anchored`) is the operator's act. A second, independent witness
  class (e.g. a transparency log) is future work; the threat model states the bound.
- **Hardware signing is a protocol, not an integration**: `CommandSigner` is proven with a scripted
  signer; a packaged YubiKey/ssh-agent/enclave wrapper script is an ecosystem item.
- **`rotate-key` requires the software chain** — rotating an external signer's key is documented as
  an operator act (author the rotation with the outgoing signer, install the new pubkey).
- The engine's own epic specs still await live sealing/anchoring on `main` (operational step, as
  with plan 016).
