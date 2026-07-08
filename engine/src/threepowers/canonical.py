"""Canonical JSON encoding and hashing.

A single canonical byte representation is the foundation of the hash chain: the
ledger's integrity depends on every actor computing *exactly* the same bytes for a
given payload. We therefore serialize with sorted keys, no insignificant
whitespace, and UTF-8 — deterministic regardless of who or what produced the object.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_PREV_HASH = "sha256:" + ("0" * 64)


def canonical_bytes(obj: Any) -> bytes:
    """Return the canonical UTF-8 JSON encoding of ``obj``."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return ``sha256:<hex>`` for ``data``."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_payload(obj: Any) -> str:
    """Canonicalize ``obj`` and return its ``sha256:<hex>`` digest."""
    return sha256_hex(canonical_bytes(obj))
