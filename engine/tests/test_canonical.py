"""Canonical-encoding tests — the foundation of the hash chain (3PWR-NFR-001/010).

Every actor must compute *exactly* the same bytes for a payload, so these pin the
canonical form precisely: sorted keys, no insignificant whitespace, UTF-8 with
non-ASCII preserved (not \\u-escaped), and a stable ``sha256:`` digest. These
assertions exist to kill mutations of the canonical form that would otherwise pass
unnoticed and silently fork the chain (3PWR-FR-031).
"""

from __future__ import annotations

from threepowers import canonical


def test_canonical_bytes_sorts_keys_and_omits_whitespace():
    # Insertion order differs but the canonical bytes must not.
    a = canonical.canonical_bytes({"b": 1, "a": 2})
    b = canonical.canonical_bytes({"a": 2, "b": 1})
    assert a == b == b'{"a":2,"b":1}'  # sorted keys, no spaces after , or :


def test_canonical_bytes_preserves_non_ascii_as_utf8():
    # ensure_ascii=False: a non-ASCII char is emitted as raw UTF-8, not "\uXXXX".
    out = canonical.canonical_bytes({"name": "café-λ"})
    assert "café-λ".encode("utf-8") in out
    assert b"\\u" not in out


def test_sha256_hex_has_prefix_and_64_hex_digits():
    digest = canonical.sha256_hex(b"hello")
    assert digest.startswith("sha256:")
    hexpart = digest.split(":", 1)[1]
    assert len(hexpart) == 64 and int(hexpart, 16) >= 0  # valid lowercase hex


def test_hash_payload_is_content_addressed():
    # Different content → different digest. Kills a mutant that hashes a constant.
    assert canonical.hash_payload({"x": 1}) != canonical.hash_payload({"x": 2})
    # Same content (any key order) → identical digest.
    assert canonical.hash_payload({"x": 1, "y": 2}) == canonical.hash_payload({"y": 2, "x": 1})


def test_hash_payload_matches_manual_composition():
    obj = {"k": "v"}
    assert canonical.hash_payload(obj) == canonical.sha256_hex(canonical.canonical_bytes(obj))


def test_genesis_prev_hash_is_zeroed_sha256():
    assert canonical.GENESIS_PREV_HASH == "sha256:" + "0" * 64
