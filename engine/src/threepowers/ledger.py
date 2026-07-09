"""Append-only, hash-chained, signed verdict ledger.

Each line of ``.3powers/ledger.jsonl`` is one entry recording a gate verdict, a
residual review, a human sign-off, or a stage advance. Entries are chained: every
entry stores the ``entry_hash`` of its predecessor in ``prev_hash``. The signed and
chained bytes are the canonical encoding of the entry *core* (everything except the
hash/signature fields), so the chain and the signatures both bind the same content.

The ledger is committed to the repository, which keeps the whole trust record
self-contained and offline-reconstructable. Every append first re-verifies the current
tail entry (recomputed hash + signature, O(1)) and refuses to write on top of a tampered
tail; full-chain verification stays with ``verify``.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .canonical import GENESIS_PREV_HASH, hash_payload
from .keys import Signer, VerifyKey, load_public

# Fields that are derived (hash/signature) and therefore excluded from the signed core.
_DERIVED_FIELDS = ("entry_hash", "signer_key_id", "signature")


class LedgerTamperError(ValueError):
    """An append was refused because the ledger's last entry failed integrity checks.

    Raised by :meth:`Ledger.append` *before* writing anything: appending on top of a
    tampered tail would bury the damage under fresh, validly signed history. The message
    names the offending entry and points at ``3pwr verify``, which locates damage anywhere
    in the chain (the pre-append check covers the tail only).
    """

    def __init__(self, seq: Any, problems: list[str]):
        self.seq = seq
        self.problems = problems
        detail = "; ".join(problems)
        super().__init__(
            f"refusing to append: the ledger's last entry (seq={seq}) failed integrity "
            f"verification — {detail}. Nothing was written; run `3pwr verify` to locate "
            "the damage"
        )


ENTRY_TYPES = (
    "verdict",
    "residual",
    "signoff",
    "stage_advance",
    "reversal",
    "abort",
    "provenance",
    "deviation",
    "oracle",
    "observe",
    "agent_action",
    "run",
    "key_rotation",  # signer succession, authored by the OUTGOING key
    "anchor",  # local receipt of an external ledger-head anchor
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def core_of(entry: dict) -> dict:
    """The signed/chained subset of an entry (excludes derived hash/sig fields)."""
    return {k: v for k, v in entry.items() if k not in _DERIVED_FIELDS}


def rotation_payload(outgoing: VerifyKey, successor: VerifyKey, reason: str = "") -> dict:
    """The ``key_rotation`` payload: the outgoing key names its successor.

    Carrying the *previous* public key too makes every span of the ledger verifiable from
    the ledger + the committed current key alone — no external state.
    """
    return {
        "previous_public_key": base64.b64encode(outgoing.raw).decode(),
        "previous_key_id": outgoing.key_id,
        "new_public_key": base64.b64encode(successor.raw).decode(),
        "new_key_id": successor.key_id,
        "reason": reason,
    }


class Ledger:
    def __init__(self, path: Path):
        self.path = path

    # -- reading -----------------------------------------------------------
    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        for lineno, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                # A line that is not valid JSON is corruption, not a parse quirk to swallow:
                # fail loud and locatable. `verify_ledger` turns this into a named "ledger
                # corrupted" problem so the keystone verify fails *closed* rather than raising;
                # the CLI catch-all covers other callers.
                raise ValueError(f"malformed ledger entry at line {lineno}: {exc}") from exc
        return out

    def last(self) -> Optional[dict]:
        entries = self.entries()
        return entries[-1] if entries else None

    # -- writing -----------------------------------------------------------
    def append(
        self,
        entry_type: str,
        payload: dict[str, Any],
        signer: Signer,
        *,
        spec_id: str = "",
        requirement_ids: Optional[list[str]] = None,
    ) -> dict:
        if entry_type not in ENTRY_TYPES:
            raise ValueError(f"unknown ledger entry type: {entry_type!r}")
        entries = self.entries()
        prev = entries[-1] if entries else None
        if prev is not None:
            self._check_tail(prev, entries)
        seq = (prev["seq"] + 1) if prev else 0
        prev_hash = prev["entry_hash"] if prev else GENESIS_PREV_HASH

        core = {
            "seq": seq,
            "prev_hash": prev_hash,
            "timestamp": _now_iso(),
            "type": entry_type,
            "spec_id": spec_id,
            "requirement_ids": sorted(requirement_ids or []),
            "payload": payload,
        }
        signed_bytes = json.dumps(  # canonical: matches canonical_bytes()
            core, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        entry = dict(core)
        entry["entry_hash"] = hash_payload(core)
        entry["signer_key_id"] = signer.key_id
        entry["signature"] = base64.b64encode(signer.sign(signed_bytes)).decode()

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry

    def _check_tail(self, tail: dict, entries: list[dict]) -> None:
        """Eagerly verify the current last entry before appending on top of it.

        O(1) in verification work: one recomputed content hash plus (at most a handful
        of) Ed25519 signature checks against the registered keys — never a chain walk.
        Deeper tamper detection (middle entries, sequence gaps, chain linkage) stays
        with ``3pwr verify``; this check only stops the tail's damage from being buried
        under fresh, validly signed history.

        Raises:
            LedgerTamperError: the tail's recomputed hash or signature does not check
                out. Nothing is written.
        """
        # Local import: verify.py imports this module at load time, so the shared
        # verify_entry helper must be resolved lazily here to avoid a circular import.
        from .verify import verify_entry

        problems = verify_entry(tail, None, self._registered_keys(entries))
        if problems:
            raise LedgerTamperError(tail.get("seq", "?"), problems)

    def _registered_keys(self, entries: list[dict]) -> list[VerifyKey]:
        """Every public key this repository has registered, resolved without a chain walk.

        Candidates are the committed ``*.pub`` files beside the ledger (the current
        ledger key plus any extra signer, e.g. a distinct oracle identity) and every key
        carried in a ``key_rotation`` payload (``entries`` is already parsed, so the scan
        costs no extra I/O or crypto).

        Design note: this is deliberately a *superset* of the single active-at-the-tail
        key that ``verify_ledger`` resolves by walking the rotation chain — any tail that
        full verification accepts is signed by the committed key, an extra signer, or a
        rotation-chain key, all of which are in this set, so a valid append is never
        refused (the full chain walk stays with ``3pwr verify``). When no key material is
        resolvable at all, the list is empty and the signature check is skipped rather
        than refusing valid appends; the content-hash check still applies.
        """
        candidates: list[VerifyKey] = []
        keys_dir = self.path.parent / "keys"
        if keys_dir.is_dir():
            for pub in sorted(keys_dir.glob("*.pub")):
                try:
                    candidates.append(load_public(pub))
                except (OSError, ValueError):
                    # An unreadable or malformed key file must never block an append;
                    # `3pwr verify` reports key problems loudly.
                    continue
        for entry in entries:
            if entry.get("type") != "key_rotation":
                continue
            payload = entry.get("payload") or {}
            for field in ("previous_public_key", "new_public_key"):
                try:
                    raw = base64.b64decode(payload.get(field) or "")
                except (ValueError, TypeError):
                    continue
                if len(raw) == 32:
                    candidates.append(VerifyKey(raw=raw))
        return candidates

    # -- queries used by enforcement --------------------------------------
    def latest_of(self, entry_type: str) -> Optional[dict]:
        result = None
        for e in self.entries():
            if e.get("type") == entry_type:
                result = e
        return result
