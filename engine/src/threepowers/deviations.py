"""Emergency & deviation paths — bending the process without breaking it (3PWR-FR-056/057).

A process that cannot bend under fire gets abandoned; one that bends without discipline
rots. Both paths here are **pre-agreed, signed, and reversible** (spec §14).

Design: deviations live at the **enforcement boundary**, not in the verdict. Gates always
run honestly, so the verdict stays deterministic (3PWR-NFR-001). A ``deviation`` is a
signed ledger entry that lets ``advance`` accept *specific named red gates* — recorded and
surfaced, never silent. It is also the **sanctioned way to accept a ``gate_gaming`` flag**
(3PWR-FR-035): a legitimate suppression is a recorded deviation, not an absorbed one.

* **Deviation (3PWR-FR-057):** relaxes named gates with a reason, a human approver, and a
  way back (an ``expires_at`` or an explicit revoke).
* **Emergency (3PWR-FR-056):** a constrained profile that may defer only **mutation** and
  **diff-coverage**, never the security/secret gates, and requires a **cleanup within one
  working day** — ``advance`` refuses while that cleanup is overdue.

Human sign-off and provenance are *not* deviatable: they are separate enforcement checks
that ``advance`` / ``deploy-gate`` always require (3PWR-FR-056).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

# Gates an emergency fast path MAY defer (3PWR-FR-056).
EMERGENCY_DEFERRABLE: tuple[str, ...] = ("mutation", "diff_coverage")
# Gates an emergency fast path shall NEVER relax — the deterministic security + secret gates.
EMERGENCY_FORBIDDEN: tuple[str, ...] = ("sast", "secret_scan", "dependency_scan")
# Default cleanup window for an emergency: one working day (3PWR-FR-056).
DEFAULT_CLEANUP_HOURS = 24


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (``...Z`` or with offset); None if absent/malformed."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def emergency_payload(reason: str, approver: str, cleanup_hours: int) -> dict[str, Any]:
    """Build the constrained emergency-deviation payload (3PWR-FR-056)."""
    return {
        "gates": list(EMERGENCY_DEFERRABLE),
        "reason": reason,
        "approver": approver,
        "emergency": True,
        "expires_at": None,
        "cleanup_due": iso(now_utc() + timedelta(hours=cleanup_hours)),
        "revokes": None,
    }


def deviation_payload(
    gates: list[str], reason: str, approver: str, expires_at: str | None
) -> dict[str, Any]:
    """Build a general deviation payload (3PWR-FR-057)."""
    return {
        "gates": sorted(set(gates)),
        "reason": reason,
        "approver": approver,
        "emergency": False,
        "expires_at": expires_at,
        "cleanup_due": None,
        "revokes": None,
    }


def active_deviations(
    entries: list[dict[str, Any]], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Currently-active deviations: not expired and not revoked by a later entry (3PWR-FR-057)."""
    now = now or now_utc()
    revoked: set[int] = set()
    candidates: list[dict[str, Any]] = []
    for e in entries:
        if e.get("type") != "deviation":
            continue
        payload = e.get("payload", {})
        revokes = payload.get("revokes")
        if revokes is not None:
            revoked.add(int(revokes))
            continue
        candidates.append({**payload, "seq": e.get("seq"), "spec_id": e.get("spec_id", "")})
    active: list[dict[str, Any]] = []
    for dev in candidates:
        if dev.get("seq") in revoked:
            continue
        expires = parse_iso(dev.get("expires_at"))
        if expires is not None and now >= expires:
            continue
        active.append(dev)
    return active


def covered_gates(active: list[dict[str, Any]], spec_id: str | None = None) -> set[str]:
    """Gates covered by the active deviations, scoped to ``spec_id`` (empty = global)."""
    gates: set[str] = set()
    for dev in active:
        dev_spec = dev.get("spec_id") or ""
        if spec_id and dev_spec and dev_spec != spec_id:
            continue  # a spec-scoped deviation does not leak to another spec
        gates.update(dev.get("gates", []))
    return gates


def overdue_emergencies(
    entries: list[dict[str, Any]], now: datetime | None = None
) -> list[dict[str, Any]]:
    """Active emergency deviations whose one-day cleanup deadline has passed (3PWR-FR-056)."""
    now = now or now_utc()
    out: list[dict[str, Any]] = []
    for dev in active_deviations(entries, now):
        if not dev.get("emergency"):
            continue
        due = parse_iso(dev.get("cleanup_due"))
        if due is not None and now >= due:
            out.append(dev)
    return out
