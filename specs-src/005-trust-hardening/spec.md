# Feature Specification: Trust-Spine Hardening — Key Custody, Continuity, Anchoring & Anti-Gaming

**Spec ID**: HARDN

**Risk Tier**: High-risk
<!-- Cosmetic | Standard | High-risk — declared BEFORE planning (3PWR-FR-003). Drives every gate threshold.
     Rationale: every capability here touches the trust spine (keys, ledger, verify, advance) or the
     judiciary gates that decide a verdict (spec-conformance, gate-gaming). A defect weakens the very
     mechanism the framework asks users to trust, so the whole spec is held to the strictest bar —
     consistent with the SLOCK precedent. -->

**Status**: Draft

**Input**: External architecture review (2026-07-02) challenging 3Powers against its founding playbook
(`tmp/AI-First_SDD_Playbook_v6.md`). Trust-mechanism findings: **(1)** the ledger is tamper-*evident*, not
tamper-*proof* — an agent with shell access on the signing machine can read the private key
(`$THREEPOWERS_SIGNING_KEY_FILE` / `~/.config/3powers/`), forge entries, or regenerate the ledger + key
pair wholesale, and the committed public key (`.3powers/keys/ledger.pub`) can be swapped as an unremarkable
git diff; the custody assumptions this rests on are documented nowhere. **(2)** the oracle's
"different model family" is self-reported via `oracle record --model` — nothing binds the claim to the
process that actually ran. **(3)** the spec-conformance gate is regex ID-matching: a test containing
`// covers X-FR-001` with an empty body counts a requirement as traced, and mutation testing — the
compensating control — runs only at High-risk, so at Standard tier no independent check on test *quality*
exists. This spec closes each gap with deterministic, local mechanisms plus one versioned threat-model
document, without introducing any model call into the verdict path (3PWR-NFR-001).

---

## Clarifications

### Session 2026-07-02 (review approver)

- **Ledger-hardening scope**: everything — threat-model document, custody hygiene enforcement,
  key-continuity rotation rule, opt-in external anchoring, **and** hardware-backed signing support.
  Anchoring and hardware signing remain opt-in capabilities; the offline, software-key default is
  unchanged.
- **Conformance-hardening posture**: the chosen trust-system posture is *deterministic by default,
  human-only-on-exception, heavy machinery opt-in*: ID-binding + assertion-bearing checks run always
  (near-zero cost, no human time); assertion-free requirement-referencing tests are *flagged* for human
  review rather than silently absorbed; diff-scoped mutation at Standard tier is a configuration knob for
  users who want machine assurance instead of human review and accept the runtime cost.

## Non-Goals *(mandatory)*

- Does **not** make the ledger tamper-proof against an adversary who holds the signing key *and* operates
  before any anchor exists — key theft plus no anchoring still permits undetectable forgery of *new*
  entries. The threat model states this residual explicitly; anchoring bounds it, never erases it.
- Does **not** mandate external anchoring or hardware-backed keys; both are opt-in. The default trust
  spine stays fully offline and self-contained (3PWR-NFR-004/010).
- Does **not** cryptographically verify *which model* authored the oracle end-to-end; the mechanism here
  is a deterministic cross-check of the self-reported model against the ledger-attested dispatch
  integration when a dispatch exists, plus honest surfacing when it does not.
- Does **not** add semantic, model-based, or heuristic judgment of test quality to the verdict path — every
  new check is deterministic (3PWR-NFR-001). Judging whether an assertion is *meaningful* stays with
  mutation testing and human review.
- Does **not** change the format, hashing, or signing of existing ledger entry kinds; key rotation and
  anchor receipts are *new* entry kinds appended through the existing signed-append path.
- Does **not** weaken or remove any existing gate or threshold (3PWR-FR-032); every mechanism here only
  adds detection.
- Does **not** implement a specific hardware token, keystore, or signing protocol in this spec's text —
  the requirement is the *capability* (seed never readable by the engine process); the concrete
  integration is a plan-level decision.

## Requirements *(each is referenced by ≥1 engine test)*

### Functional Requirements

#### Threat model & key custody

- **HARDN-FR-001**: The project shall maintain a versioned threat-model document in-repo stating what each
  trust-spine mechanism proves, the tamper classes `verify` detects (chain break, gap, payload edit,
  signature mismatch, key swap), the classes it cannot detect (forgery by a holder of the signing key
  absent an anchor), the custody boundary (executive agents must never be able to resolve a signing key),
  and the self-reported nature of the oracle model claim outside dispatch.
  - *Acceptance*: the document exists under `docs/`, covers ledger, provenance, key custody, anchoring,
    and oracle-model attestation; it is linked from `README.md` and `SECURITY.md`; a docs-conformance test
    asserts its presence and required sections.
- **HARDN-FR-002**: The engine shall refuse to create a signing key inside the repository working tree,
  and shall report a custody violation when a resolved private-key path lies inside the working tree or is
  readable by other users.
  - *Acceptance*: `3pwr keygen` with an output path inside the repo is refused with an actionable message;
    `3pwr verify` (or its custody preflight) emits a `key_custody` finding when
    `$THREEPOWERS_SIGNING_KEY_FILE` resolves inside the working tree or the key file's mode is broader
    than owner-only; a compliant setup emits nothing.
- **HARDN-FR-003**: The secret-scanning gate shall detect committed private-key material in the
  repository — including the engine's own `ed25519-priv` format — and fail the verdict.
  - *Acceptance*: a tracked file containing an `ed25519-priv` line yields a failing `secret_scan` gate
    with a finding naming the file; the check works with or without an external secret scanner installed
    (core fallback, never quarantined away).

#### Key continuity & anchoring

- **HARDN-FR-004**: The engine shall support key rotation as a signed ledger entry authored by the
  *previous* key and carrying the successor public key, and `verify` shall fail when the committed public
  key does not descend from the ledger's genesis key through recorded rotations.
  - *Acceptance*: a rotation command appends a `key_rotation` entry signed by the outgoing key; entries
    after the rotation verify against the successor key; replacing `.3powers/keys/ledger.pub` with an
    unrelated key and re-signing subsequent entries makes `3pwr verify` fail with an unrotated-key-change
    finding; a ledger with no rotations verifies exactly as today when the committed key is the genesis
    key.
- **HARDN-FR-005**: The engine shall provide an opt-in anchoring command that records the current ledger
  head (sequence number + entry hash) with an external witness, and an opt-in verification mode that
  cross-checks the local chain against the latest anchor and fails on divergence.
  - *Acceptance*: `3pwr anchor` publishes the head to the configured witness (a signed git ref/tag as the
    reference witness) and appends a local anchor receipt; `3pwr verify --anchored` fails when the ledger
    was rewritten or truncated after the anchor and passes when it extends the anchored head; plain
    `3pwr verify` behaves exactly as before, offline, with no network call.

#### Hardware-backed signing

- **HARDN-FR-006**: Where an external signer is configured, the engine shall delegate ledger signing to a
  signer interface whose private-key material is never present in a file or environment variable readable
  by the engine process, while verification remains unchanged (standard Ed25519 signatures against the
  committed public key).
  - *Acceptance*: with the external-signer configuration set, `gate run`/`signoff` produce validly signed
    entries with no `ed25519-priv` seed on disk or in the environment; `3pwr verify` passes on the
    resulting ledger with no verification-code change; with the configuration unset, the existing
    software-key custody chain applies unchanged; a misconfigured external signer fails signing loudly,
    never falling back silently to a software key.

#### Oracle model attestation

- **HARDN-FR-007**: When a ledger-attested oracle dispatch exists for a spec, the engine shall cross-check
  the self-reported model of `oracle record` against the dispatched integration and treat a contradiction
  as a blocking independence failure at High-risk `advance`; when no dispatch exists, oracle verification
  output shall state that the model claim is self-reported.
  - *Acceptance*: an `oracle record --model` naming a family contradicting the recorded dispatch
    integration fails `oracle verify` and blocks a High-risk `advance`; a consistent pair passes; without
    any dispatch entry, `oracle verify` output includes a self-reported advisory note and blocks nothing
    it does not block today.

#### Conformance anti-gaming

- **HARDN-FR-008**: The spec-conformance gate shall count a requirement as traced only when its ID is
  bound to a test declaration (test name or declaration line), not merely mentioned in a comment or
  non-test text.
  - *Acceptance*: a requirement ID appearing only in a comment with no matching test declaration yields an
    `untraced_requirement` failure naming the ID; the same ID in a test name or declaration line yields a
    traced requirement; existing conforming repos (engine, sample) still pass.
- **HARDN-FR-009**: The spec-conformance gate shall require at least one assertion inside each
  requirement-bound test, with assertion patterns declared per language adapter, and shall quarantine —
  never silently pass — when an adapter declares no assertion patterns.
  - *Acceptance*: an empty or assertion-free test body bound to a requirement ID yields a failing finding
    of class `weak_test` naming the requirement and file; an adapter manifest without assertion patterns
    yields a quarantined finding (3PWR-NFR-015); the check adds no file reads beyond the existing
    conformance scan pass.
- **HARDN-FR-010**: The gate-gaming detector shall flag newly introduced assertion-free tests that
  reference requirement IDs as gaming signals routed to mandatory human review, sanctionable only through
  the existing signed-deviation path.
  - *Acceptance*: a diff adding an assertion-free requirement-referencing test yields a `gate_gaming`
    finding; a signed `3pwr deviation --gate gate_gaming` records the sanctioned acceptance exactly as for
    existing gaming classes; revocation re-blocks.
- **HARDN-FR-011**: Where diff-scoped mutation is enabled for a tier in the risk-tier configuration, the
  engine shall run mutation testing scoped to the changed files against that tier's mutation threshold,
  quarantining when the mutation tool is unavailable.
  - *Acceptance*: with the Standard tier configured for diff mutation and a `--base` given, `gate run`
    executes mutation over changed files only and grades against the configured Standard threshold; with
    the knob unset, Standard-tier behavior is unchanged; a missing mutation tool yields a quarantined
    finding, never a silent pass.

### Non-Functional Requirements

- **HARDN-NFR-001**: Every check in this spec shall be deterministic — no model call and, in the default
  verdict path, no network access; anchoring is the only network-capable feature and runs only under its
  explicit opt-in commands/flags.
  - *Acceptance*: two runs over identical inputs produce identical findings; `gate run` and plain `verify`
    complete with networking disabled.
- **HARDN-NFR-002**: The always-on additions (custody checks, ID-binding, assertion checks, gaming flags)
  shall impose no measurable verdict-latency cost — bounded by a single additional pass over files the
  gates already read.
  - *Acceptance*: conformance-gate wall time over the engine's own repo stays within noise of the
    pre-HARDN baseline in the test suite's timing assertion.
- **HARDN-NFR-003**: Backward compatibility — every ledger, key pair, and adapter valid before this spec
  shall remain valid: rotation-free ledgers verify, software-key custody works unchanged, and adapters
  without assertion patterns degrade to quarantine (visible), never to failure or silent pass.
  - *Acceptance*: the pre-HARDN fixture ledgers and both reference adapters pass their existing tests
    unmodified except for newly visible quarantine findings.
- **HARDN-NFR-004**: Self-application — the engine's own repository shall pass the hardened gate suite at
  its declared tiers, and the trust-spine modules extended here shall hold the High-risk bar
  (diff-coverage ≥ 95%, mutation ≥ 70%).
  - *Acceptance*: `3pwr gate run --path engine --tier High-risk` (trust-spine scope) is green
    post-implementation.

## Success Criteria

- **HARDN-SC-001**: A swapped committed public key without a signed rotation entry is caught by
  `3pwr verify` — the key-regeneration attack becomes visible instead of an unremarkable git diff.
- **HARDN-SC-002**: A private key inside the repo, a world-readable key file, or committed `ed25519-priv`
  material each produce a named, actionable finding.
- **HARDN-SC-003**: After `3pwr anchor`, rewriting or truncating the ledger is detected by
  `verify --anchored`, even by an adversary holding the current signing key.
- **HARDN-SC-004**: With an external signer configured, a green, verifiable ledger is produced with no
  private-key material readable by the engine process.
- **HARDN-SC-005**: A test that mentions a requirement ID in a comment, or binds it with no assertion,
  no longer counts as tracing that requirement — and the assertion-free case is surfaced to a human.
- **HARDN-SC-006**: A user who enables Standard-tier diff mutation gets machine-graded test quality on
  every change without reading a single test; a user who does not enables nothing and pays nothing.
- **HARDN-SC-007**: The threat-model document lets an enterprise security review answer "what does the
  ledger prove, against whom, under which assumptions" from the repo alone.

## Sign-off

| Approver | Date | Decision |
|----------|------|----------|
| _(record via `3pwr signoff --approver <you> --spec-id HARDN --stage spec --spec specs/005-trust-hardening/spec.md`)_ | | |
