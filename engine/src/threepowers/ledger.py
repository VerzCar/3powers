"""Append-only, hash-chained, signed verdict ledger (3PWR-FR-038/039).

Each line of ``.3powers/ledger.jsonl`` is one entry recording a gate verdict, a
residual review, a human sign-off, or a stage advance. Entries are chained: every
entry stores the ``entry_hash`` of its predecessor in ``prev_hash``. The signed and
chained bytes are the canonical encoding of the entry *core* (everything except the
hash/signature fields), so the chain and the signatures both bind the same content.

The ledger is committed to the repository, which keeps the whole trust record
self-contained and offline-reconstructable (3PWR-FR-071, 3PWR-NFR-010).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .canonical import GENESIS_PREV_HASH, hash_payload
from .keys import SigningKey

# Fields that are derived (hash/signature) and therefore excluded from the signed core.
_DERIVED_FIELDS = ("entry_hash", "signer_key_id", "signature")

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
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def core_of(entry: dict) -> dict:
    """The signed/chained subset of an entry (excludes derived hash/sig fields)."""
    return {k: v for k, v in entry.items() if k not in _DERIVED_FIELDS}


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
                # corrupted" problem so the keystone verify fails *closed* rather than raising
                # (3PWR-FR-040/FR-034/NFR-011); the CLI catch-all covers other callers.
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
        signer: SigningKey,
        *,
        spec_id: str = "",
        requirement_ids: Optional[list[str]] = None,
    ) -> dict:
        if entry_type not in ENTRY_TYPES:
            raise ValueError(f"unknown ledger entry type: {entry_type!r}")
        prev = self.last()
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

    # -- queries used by enforcement --------------------------------------
    def latest_of(self, entry_type: str) -> Optional[dict]:
        result = None
        for e in self.entries():
            if e.get("type") == entry_type:
                result = e
        return result
