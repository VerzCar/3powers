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
    pending_gate: str = ""  # a `3pwr run` orchestration paused at this human gate (3PWR-FR-011/019)
    # The most recent UNRESOLVED run failure (AUTOX-FR-006/007): set by a `run`/`failure` ledger
    # record, cleared by any later progress (a stage completing, a gate, a verdict, a sign-off…).
    # The latest failure wins; earlier ones remain in the append-only ledger as history.
    failed_stage: str = ""
    failed_class: str = ""  # dispatch_failed | artifact_missing | gates_red | verdict_error
    failed_at: str = ""  # the failure entry's timestamp
    failed_transcript: str = ""  # the persisted transcript path, when one was recorded

    @property
    def failed(self) -> bool:
        """True while the most recent run event for this spec is an unresolved failure (AUTOX-FR-007)."""
        return bool(self.failed_class)

    @property
    def signed_off(self) -> bool:
        # A sign-off counts only if it is at or after the most recent verdict (3PWR-FR-037).
        return self.signed_off_seq >= self.last_verdict_seq and self.signed_off_seq >= 0


def derive(entries: list[dict]) -> dict[str, SpecState]:
    """Fold the ledger into per-spec lifecycle state."""
    states: dict[str, SpecState] = {}

    def state_for(spec_id: str) -> SpecState:
        return states.setdefault(spec_id, SpecState(spec_id=spec_id))

    def clear_failure(st: SpecState) -> None:
        st.failed_stage = st.failed_class = st.failed_at = st.failed_transcript = ""

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
            st.pending_gate = ""  # advancing clears any paused-at-gate run marker
            clear_failure(st)
        elif etype == "verdict":
            st.last_verdict = payload.get("result", "none")
            st.last_verdict_seq = e["seq"]
            clear_failure(st)  # the run progressed to a verdict — past any earlier failure
        elif etype == "signoff":
            st.signed_off_seq = e["seq"]
            st.pending_gate = ""  # the human acted on the gate
            clear_failure(st)
        elif etype == "run":
            # `3pwr run` orchestration records (3PWR-FR-011/019, AUTOX-FR-006/007): start /
            # paused-at-gate / stage completions / complete — and terminal failures.
            kind = payload.get("kind")
            if kind == "failure":
                # A recorded terminal run failure (AUTOX-FR-006). The stage here is the lifecycle
                # stage the failure names; it does not advance progress. Latest failure wins.
                st.failed_stage = str(payload.get("stage") or "")
                st.failed_class = str(payload.get("class") or "")
                st.failed_at = str(e.get("timestamp") or "")
                st.failed_transcript = str(payload.get("transcript") or "")
                continue
            stage = canonical_stage(payload.get("stage"))
            if stage:
                st.stage = stage
            st.pending_gate = payload.get("gate", "") if kind == "gate" else ""
            clear_failure(st)  # any later run progress resolves the recorded failure (AUTOX-FR-007)
        elif etype == "reversal":
            to_stage = canonical_stage(payload.get("to_stage"))
            if to_stage:
                st.stage = to_stage
            st.aborted = False
        elif etype == "abort":
            st.aborted = True
        elif etype == "observe":
            # A production signal means the spec reached the Observe stage (§13, 3PWR-FR-054).
            st.stage = "Observe"
    return states
