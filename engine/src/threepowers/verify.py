"""Ledger verification: recompute the hash chain and signatures (3PWR-FR-040).

``verify`` is the keystone of the trust spine. It is fully local and offline
(3PWR-NFR-004) and fails on *any* tamper, gap, or break: a mutated payload changes
the recomputed ``entry_hash``; a reordered/inserted/deleted entry breaks the
``prev_hash`` linkage or the ``seq`` sequence; a forged entry fails Ed25519
verification against the committed public key.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .canonical import GENESIS_PREV_HASH, canonical_bytes, hash_payload
from .keys import VerifyKey, load_public
from .ledger import Ledger, core_of


@dataclass
class VerifyResult:
    ok: bool
    entries: int = 0
    problems: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return f"ledger OK — {self.entries} entr{'y' if self.entries == 1 else 'ies'}, chain and signatures intact"
        return f"ledger TAMPERED — {len(self.problems)} problem(s):\n  - " + "\n  - ".join(
            self.problems
        )


def verify_ledger(
    ledger_path: Path,
    pubkey_path: Path,
    extra_pubkey_paths: Optional[list[Path]] = None,
) -> VerifyResult:
    """Recompute the chain and verify each entry's signature against *any* committed public key.

    ``extra_pubkey_paths`` lets a repo carry more than one independent signer — e.g. a distinct
    judiciary (oracle) identity that signs the isolated-dispatch attestation (3PWR-FR-021/039).
    Absent extra keys are simply skipped, so single-key repos verify unchanged (3PWR-NFR-004)."""
    res = VerifyResult(ok=True)
    entries = Ledger(ledger_path).entries()
    res.entries = len(entries)

    if not entries:
        return res  # an empty ledger trivially verifies

    vks: list[VerifyKey] = []
    if pubkey_path.exists():
        vks.append(load_public(pubkey_path))
    for extra in extra_pubkey_paths or []:
        if extra.exists():
            vks.append(load_public(extra))
    if not vks:
        return VerifyResult(
            ok=False, entries=len(entries), problems=[f"public key not found at {pubkey_path}"]
        )

    expected_prev = GENESIS_PREV_HASH
    for idx, entry in enumerate(entries):
        loc = f"entry seq={entry.get('seq', '?')} (line {idx + 1})"

        # 1. Sequence is dense and monotonic from 0.
        if entry.get("seq") != idx:
            res.problems.append(f"{loc}: sequence gap/break — expected seq={idx}")

        # 2. Chain linkage.
        if entry.get("prev_hash") != expected_prev:
            res.problems.append(f"{loc}: broken chain — prev_hash does not match predecessor")

        # 3. Recomputed content hash matches the stored hash (detects tamper).
        recomputed = hash_payload(core_of(entry))
        if recomputed != entry.get("entry_hash"):
            res.problems.append(f"{loc}: content tampered — entry_hash mismatch")

        # 4. Signature verifies against any committed public key (primary or a distinct oracle key).
        try:
            sig = base64.b64decode(entry["signature"])
            signed = canonical_bytes(core_of(entry))
            if not any(vk.verify(sig, signed) for vk in vks):
                res.problems.append(f"{loc}: invalid signature")
        except (KeyError, ValueError):
            res.problems.append(f"{loc}: missing or malformed signature")

        expected_prev = entry.get("entry_hash", expected_prev)

    res.ok = not res.problems
    return res
