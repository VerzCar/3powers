# Threat model — what the 3Powers trust spine proves, against whom, under which assumptions

This document is the versioned, in-repo answer to "what does the ledger prove?" (HARDN-FR-001).
It states precisely what each trust-spine mechanism guarantees, which tamper classes
`3pwr verify` detects, which it **cannot** detect, and the custody assumptions everything rests
on. It exists so an enterprise security review can answer these questions from the repository
alone (HARDN-SC-007). The spec governing this document is
[`specs/005-trust-hardening/spec.md`](../specs/005-trust-hardening/spec.md).

The one-sentence summary: **the ledger is tamper-*evident*, not tamper-*proof*.** Every
mechanism below turns a class of silent manipulation into a loud, locatable failure — none of
them makes manipulation impossible.

## What the ledger proves

The ledger (`.3powers/ledger.jsonl`) is an append-only, hash-chained sequence of entries, each
Ed25519-signed over its canonical content by an identity whose private key lives **outside** the
repository. For any party holding the repository (including the committed public key,
`.3powers/keys/ledger.pub`), a passing `3pwr verify` proves:

- every entry's content is exactly what was signed (payload edits change the recomputed hash);
- the sequence is dense, ordered, and unbroken (no insertion, deletion, or reordering);
- every entry was signed by a holder of a private key descending from the ledger's genesis key
  through recorded rotations (see [Key custody](#key-custody)).

It does **not** prove *who* the key holder was, *when* an entry was really created (timestamps
are claims by the signer), or that the signing machine was uncompromised.

## Tamper classes detected by `3pwr verify`

| Tamper class | How it is caught |
|---|---|
| **Chain break** — an entry inserted, deleted, or reordered | `prev_hash` no longer matches the predecessor's `entry_hash` |
| **Sequence gap** — entries dropped or renumbered | `seq` is required to be dense and monotonic from 0 |
| **Payload edit** — any field of a recorded entry changed | recomputed `entry_hash` over the canonical core mismatches the stored one |
| **Signature mismatch** — an entry forged without the signing key | Ed25519 verification against the committed public key(s) fails |
| **Key swap** — `.3powers/keys/ledger.pub` replaced without authority | the committed key does not descend from the genesis key through signed `key_rotation` entries (HARDN-FR-004) |

## What `verify` cannot detect

- **Forgery by a holder of the signing key, absent an anchor.** An adversary who obtains the
  private key — or who can execute code on the signing machine — can append validly signed
  entries, or regenerate the *entire* ledger and key pair wholesale and re-sign every entry.
  Plain `verify` will pass. Once an external anchor exists, any rewrite or truncation of the
  anchored history is caught by `3pwr verify --anchored` (see [Anchoring](#anchoring)); forgery
  of *new*, post-anchor entries remains possible until the next anchor. Anchoring **bounds**
  this residual; nothing erases it.
- **A compromised signing environment.** The ledger records what the key signed, not whether
  the machine or operator was trustworthy at that moment.
- **Timestamp truthfulness.** Timestamps are asserted by the signer, not proven.

## Key custody

The custody boundary the whole spine rests on: **executive agents must never be able to resolve
a signing key.** The private key is resolved from (in order) `$THREEPOWERS_SIGNING_KEY_FILE`,
`$THREEPOWERS_SIGNING_KEY`, or `~/.config/3powers/<repo>.key` — always **outside** the
repository working tree (3PWR-NFR-005). An agent operating inside the repo must find no key
material there to read, and nothing in-repo may point it at one.

Enforced hygiene (HARDN-FR-002/003):

- `3pwr keygen` **refuses** to create a private key inside the working tree;
- `3pwr verify` runs a custody preflight and fails with a `key_custody` finding when a resolved
  private-key path lies inside the working tree or the key file is readable by other users
  (broader than `0600`);
- the secret-scanning gate detects committed `ed25519-priv` key material with a **core check
  that always runs**, with or without an external scanner installed.

There is no deviation path for a custody violation — the remedy is to fix custody (move the key
outside the tree, `chmod 600` it, rotate if it may have leaked), not to accept it.

**Key continuity (HARDN-FR-004).** Replacing the signer is legitimate only through a signed
`key_rotation` ledger entry: authored by the *outgoing* key, carrying the successor public key.
`verify` walks these rotations and fails when the committed public key does not descend from
the genesis key — turning the "swap the committed pubkey in an unremarkable git diff" attack
into a named finding.

**External / hardware-backed signing (HARDN-FR-006).** Where an external signer is configured
(`$THREEPOWERS_SIGNER_CMD`), the engine delegates signing to a process boundary: the private
seed is never present in a file or environment variable readable by the engine. Verification is
unchanged — standard Ed25519 signatures against the committed public key. A misconfigured
external signer fails loudly; it never silently falls back to a software key.

## Anchoring

Anchoring (opt-in, HARDN-FR-005) records the current ledger head — sequence number and entry
hash — with an **external witness** the key holder does not control unilaterally. The reference
witness is a signed git ref/tag (`3powers/anchor/<seq>`), pushed to a remote. `3pwr verify
--anchored` cross-checks the local chain against the latest anchor and fails when the ledger
was rewritten or truncated behind it.

What anchoring adds: after an anchor, even an adversary holding the current signing key cannot
silently rewrite the anchored history (HARDN-SC-003). What it does not add: protection for
entries appended *after* the last anchor, or against a witness the adversary also controls.
Plain `3pwr verify` remains fully offline and makes no network call; anchoring is the only
network-capable feature and runs only under its explicit opt-in commands.

## Provenance

`3pwr provenance` signs a build artifact's hash + SBOM with the **same independent identity**
as the ledger, and `3pwr deploy-gate` refuses artifacts whose provenance does not verify. This
proves an artifact is byte-identical to one recorded by the signer and links it to the gate
verdicts in the ledger. It inherits every custody assumption above: a stolen signing key forges
provenance exactly as it forges ledger entries.

## Oracle model attestation

The oracle's independence claim ("a different model family authored the oracle tests") has two
evidence classes, and they are **not equal**:

- **Self-reported** — `3pwr oracle record --model <family>/<model>` records what the operator
  *claims* ran. Nothing binds the claim to the process that actually executed. When no dispatch
  attestation exists, `3pwr oracle verify` says so explicitly: the model claim is self-reported.
- **Ledger-attested dispatch** — `3pwr oracle dispatch` runs the oracle headlessly under a named
  integration inside a sanitized worktree, and records the integration + worktree manifest hash
  in the ledger. When a dispatch exists, the engine cross-checks the self-reported model family
  against the dispatched integration and treats a contradiction as a blocking independence
  failure at a High-risk `advance` (HARDN-FR-007).

Even a dispatch attestation is not end-to-end cryptographic proof of *which* model produced the
text; it is a deterministic, local record of which integration was invoked, in which isolation.

## Conformance and gate-gaming residuals

The spec-conformance gate binds requirement IDs to test declarations and requires at least one
assertion per requirement-bound test (HARDN-FR-008/009); the gate-gaming detector flags newly
added assertion-free requirement-referencing tests for mandatory human review (HARDN-FR-010).
These checks are deterministic and cannot judge whether an assertion is *meaningful* — that
remains the job of mutation testing (always at High-risk; opt-in diff-scoped at lower tiers,
HARDN-FR-011) and human review.
