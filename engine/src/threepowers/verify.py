"""Ledger verification: recompute the hash chain and signatures.

``verify`` is the keystone of the trust spine. It is fully local and offline
and fails on *any* tamper, gap, or break: a mutated payload changes
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


def _payload_key(payload: dict, field: str) -> Optional[VerifyKey]:
    """Decode a raw-32-byte public key carried in a ``key_rotation`` payload; None if malformed."""
    try:
        raw = base64.b64decode(payload.get(field) or "")
    except (ValueError, TypeError):
        return None
    return VerifyKey(raw=raw) if len(raw) == 32 else None


def verify_ledger(
    ledger_path: Path,
    pubkey_path: Path,
    extra_pubkey_paths: Optional[list[Path]] = None,
) -> VerifyResult:
    """Recompute the chain and verify each entry's signature against the *active* signer.

    Key continuity: the active ledger key starts at the genesis key and changes
    only through signed ``key_rotation`` entries — each authored by the outgoing key and naming
    its successor. A rotation-free ledger verifies against the committed public key exactly as
    before; with rotations, the committed key must be the last successor, else
    the swap is an *unrotated key change*, not an unremarkable git diff.

    ``extra_pubkey_paths`` lets a repo carry more than one independent signer — e.g. a distinct
    judiciary (oracle) identity that signs the isolated-dispatch attestation.
    Absent extra keys are simply skipped, so single-key repos verify unchanged."""
    res = VerifyResult(ok=True)
    try:
        entries = Ledger(ledger_path).entries()
    except ValueError as exc:
        # A corrupt (non-JSON) ledger line is a tamper/corruption event, not a crash: the
        # keystone verify fails *closed* with a named, locatable problem
        # so callers get ok=False (and the CLI a red EXIT_FAIL verdict), never an exception.
        return VerifyResult(ok=False, problems=[f"ledger corrupted — {exc}"])
    res.entries = len(entries)

    if not entries:
        return res  # an empty ledger trivially verifies

    primary: Optional[VerifyKey] = load_public(pubkey_path) if pubkey_path.exists() else None
    extras: list[VerifyKey] = []
    for extra in extra_pubkey_paths or []:
        if extra.exists():
            extras.append(load_public(extra))
    if primary is None and not extras:
        return VerifyResult(
            ok=False, entries=len(entries), problems=[f"public key not found at {pubkey_path}"]
        )

    # The genesis key: with rotations recorded, the first rotation carries it; without any,
    # the committed key IS the genesis key and behavior is unchanged.
    rotations = [e for e in entries if e.get("type") == "key_rotation"]
    active: Optional[VerifyKey] = primary
    if rotations:
        active = _payload_key(rotations[0].get("payload") or {}, "previous_public_key")
        if active is None:
            res.problems.append(
                f"entry seq={rotations[0].get('seq', '?')}: malformed key_rotation — "
                "previous_public_key is not a raw-32 Ed25519 key"
            )
            active = primary

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

        # 4. Signature verifies against the active ledger key or a distinct extra signer.
        candidates = ([active] if active else []) + extras
        try:
            sig = base64.b64decode(entry["signature"])
            signed = canonical_bytes(core_of(entry))
            if not any(vk.verify(sig, signed) for vk in candidates):
                skid = entry.get("signer_key_id") or "?"
                known = {vk.key_id for vk in candidates}
                if skid not in known:
                    res.problems.append(
                        f"{loc}: invalid signature — signed by {skid}, not the active key; "
                        "unrotated key change (no key_rotation entry records this succession)"
                    )
                else:
                    res.problems.append(f"{loc}: invalid signature")
        except (KeyError, ValueError):
            res.problems.append(f"{loc}: missing or malformed signature")

        # 5. A key rotation hands over the active key — authored by the OUTGOING key
        #    (its signature was just checked against `active` above), naming the successor.
        if entry.get("type") == "key_rotation":
            payload = entry.get("payload") or {}
            declared_prev = _payload_key(payload, "previous_public_key")
            if active is not None and (declared_prev is None or declared_prev.raw != active.raw):
                res.problems.append(
                    f"{loc}: key rotation does not chain — previous_public_key is not the "
                    "active key"
                )
            successor = _payload_key(payload, "new_public_key")
            if successor is None:
                res.problems.append(
                    f"{loc}: malformed key_rotation — new_public_key is not a raw-32 Ed25519 key"
                )
            else:
                active = successor

        expected_prev = entry.get("entry_hash", expected_prev)

    # 6. Continuity to the committed key: the key the repo *now* trusts must be the final
    #    successor in the rotation chain.
    if rotations and primary is not None and active is not None and active.raw != primary.raw:
        res.problems.append(
            f"unrotated key change — committed public key {primary.key_id} does not descend "
            f"from the genesis key through recorded rotations (chain ends at {active.key_id})"
        )

    res.ok = not res.problems
    return res
