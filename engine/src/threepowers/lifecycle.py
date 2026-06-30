"""The eight-stage lifecycle, derived from the ledger (3PWR-FR-011/019).

Per-spec lifecycle state is *computed from the committed ledger* rather than stored in a
separate mutable file, so it persists across sessions and reconstructs offline from the
repository alone (3PWR-FR-019/071) with no second source of truth to drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# The eight stages (spec §6 / 3PWR-FR-011).
STAGES = ["Discovery", "Spec", "Plan", "Build", "Verify", "Review", "Ship", "Observe"]
_BY_LOWER = {s.lower(): s for s in STAGES}


def canonical_stage(name: str | None) -> Optional[str]:
    """Return the canonically-cased stage (so `ship` → `Ship`), or None if unknown."""
    return _BY_LOWER.get((name or "").lower())


def is_stage(name: str | None) -> bool:
    return canonical_stage(name) is not None


def next_stage(name: str) -> Optional[str]:
    if name in STAGES and STAGES.index(name) + 1 < len(STAGES):
        return STAGES[STAGES.index(name) + 1]
    return None


@dataclass
class SpecState:
    spec_id: str
    stage: str = "Spec"
    last_verdict: str = "none"  # pass | fail | none
    signed_off_seq: int = -1
    last_verdict_seq: int = -1
    aborted: bool = False
    last_seq: int = -1

    @property
    def signed_off(self) -> bool:
        # A sign-off counts only if it is at or after the most recent verdict (3PWR-FR-037).
        return self.signed_off_seq >= self.last_verdict_seq and self.signed_off_seq >= 0


def derive(entries: list[dict]) -> dict[str, SpecState]:
    """Fold the ledger into per-spec lifecycle state."""
    states: dict[str, SpecState] = {}

    def state_for(spec_id: str) -> SpecState:
        return states.setdefault(spec_id, SpecState(spec_id=spec_id))

    for e in entries:
        spec_id = e.get("spec_id") or ""
        if not spec_id:
            continue
        st = state_for(spec_id)
        st.last_seq = e["seq"]
        etype = e.get("type")
        payload = e.get("payload", {})
        if etype == "stage_advance":
            stage = canonical_stage(payload.get("stage"))
            if stage:
                st.stage = stage
        elif etype == "verdict":
            st.last_verdict = payload.get("result", "none")
            st.last_verdict_seq = e["seq"]
        elif etype == "signoff":
            st.signed_off_seq = e["seq"]
        elif etype == "reversal":
            to_stage = canonical_stage(payload.get("to_stage"))
            if to_stage:
                st.stage = to_stage
            st.aborted = False
        elif etype == "abort":
            st.aborted = True
    return states
