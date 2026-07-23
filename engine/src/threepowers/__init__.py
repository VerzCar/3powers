"""3Powers engine — the native provider-agnostic executive + judicial trust spine.

This package implements the language-agnostic core of 3Powers:

* a cheapest-first **gate runner** that drives per-language adapters and emits one
  normalized **verdict** with an identical shape across languages;
* a deterministic **spec-conformance** trace (every requirement → a linked test);
* an append-only, hash-chained, Ed25519-signed **verdict ledger** with an offline
  ``verify`` that fails on any tamper, gap, or break;
* a local, CI-independent **enforcement** hook (``advance``) that refuses to proceed
  when a required gate is red, the ledger fails verification, or a tier-required
  human sign-off is absent.

Everything is self-contained in the repository and reconstructable offline.
"""

__version__ = "1.1.0"

# Version of the normalized verdict / ledger schemas this engine emits.
# Documented, versioned, and stable. 1.1 adds the additive, backward-compatible
# ``report_only`` verdict field (brownfield adoption).
SCHEMA_VERSION = "1.1"
