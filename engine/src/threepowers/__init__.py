"""3Powers engine — the native provider-agnostic executive + judicial trust spine.

This package implements the language-agnostic core of 3Powers:

* a cheapest-first **gate runner** that drives per-language adapters and emits one
  normalized **verdict** (identical shape across languages — 3PWR-NFR-001/033);
* a deterministic **spec-conformance** trace (every requirement → a linked test —
  3PWR-FR-030);
* an append-only, hash-chained, Ed25519-signed **verdict ledger** with an offline
  ``verify`` that fails on any tamper, gap, or break (3PWR-FR-038/039/040);
* a local, CI-independent **enforcement** hook (``advance``) that refuses to proceed
  when a required gate is red, the ledger fails verification, or a tier-required
  human sign-off is absent (3PWR-FR-041/042).

Everything is self-contained in the repository and reconstructable offline
(3PWR-NFR-004/010).
"""

__version__ = "0.1.0"

# Version of the normalized verdict / ledger schemas this engine emits.
# Documented, versioned, and stable (3PWR-NFR-008). 1.1 adds the additive,
# backward-compatible ``report_only`` verdict field (brownfield adoption, 3PWR-FR-052).
SCHEMA_VERSION = "1.1"
