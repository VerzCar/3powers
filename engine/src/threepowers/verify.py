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


def verify_entry(
    entry: dict,
    expected_prev: Optional[str],
    candidates: list[VerifyKey],
    *,
    expected_seq: Optional[int] = None,
    loc: Optional[str] = None,
) -> list[str]:
    """Run the per-entry integrity checks on a single ledger entry.

    This is the one implementation of the entry-level checks: ``verify_ledger`` calls it
    for every entry of the chain, and ``Ledger.append`` calls it on the current tail
    before writing, so the two can never drift apart.

    Args:
        entry: the parsed ledger entry to check.
        expected_prev: the predecessor's ``entry_hash``; pass ``None`` to skip the
            chain-linkage check (e.g. for a single-entry check without the predecessor).
        candidates: public keys the signature may verify against. An empty list skips
            the signature check entirely — callers without any key material still get
            the content-hash check, and a valid entry is never refused for lack of keys.
        expected_seq: the sequence number this entry must carry; ``None`` skips the check.
        loc: label used to prefix problem messages; defaults to ``entry seq=<seq>``.

    Returns:
        A list of human-readable problems, empty when every applicable check passes.
    """
    problems: list[str] = []
    where = loc if loc is not None else f"entry seq={entry.get('seq', '?')}"

    # 1. Sequence is dense and monotonic from 0.
    if expected_seq is not None and entry.get("seq") != expected_seq:
        problems.append(f"{where}: sequence gap/break — expected seq={expected_seq}")

    # 2. Chain linkage.
    if expected_prev is not None and entry.get("prev_hash") != expected_prev:
        problems.append(f"{where}: broken chain — prev_hash does not match predecessor")

    # 3. Recomputed content hash matches the stored hash (detects tamper).
    recomputed = hash_payload(core_of(entry))
    if recomputed != entry.get("entry_hash"):
        problems.append(f"{where}: content tampered — entry_hash mismatch")

    # 4. Signature verifies against one of the candidate keys.
    if candidates:
        try:
            sig = base64.b64decode(entry["signature"])
            signed = canonical_bytes(core_of(entry))
            if not any(vk.verify(sig, signed) for vk in candidates):
                skid = entry.get("signer_key_id") or "?"
                known = {vk.key_id for vk in candidates}
                if skid not in known:
                    problems.append(
                        f"{where}: invalid signature — signed by {skid}, not the active key; "
                        "unrotated key change (no key_rotation entry records this succession)"
                    )
                else:
                    problems.append(f"{where}: invalid signature")
        except (KeyError, ValueError):
            problems.append(f"{where}: missing or malformed signature")

    return problems


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

        # Checks 1-4 (sequence, chain linkage, content hash, signature) live in
        # verify_entry — shared with the pre-append tail check in Ledger.append.
        candidates = ([active] if active else []) + extras
        res.problems.extend(
            verify_entry(entry, expected_prev, candidates, expected_seq=idx, loc=loc)
        )

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
