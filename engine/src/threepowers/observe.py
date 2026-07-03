"""Observe & feedback — closing the loop back to the spec (3PWR-FR-054/055, §13).

Production is where software is graded, and what is learned must return to the **spec as new intent**,
not as ad-hoc patches. This module:

* records a production signal (incident, missed objective, real usage) and **routes it to the
  legislature as a new requirement** — a feedback backlog the human takes into a new `3pwr run` spec —
  never an in-place patch (3PWR-FR-054);
* reports **NFR-instrumentation coverage** — which of a spec's non-functional requirements have a
  declared live production check (§13 acceptance: "a specified NFR has a live check");
* supports a **tamper-evident, attributable** log of a target system's runtime agent actions
  (3PWR-FR-055) by reusing the append-only signed hash chain (`Ledger` on a separate file), so
  `verify` catches any tamper and each action names the agent that took it.

The engine is offline (Git substrate); it does not run the target's production system. It therefore
records externally-supplied signals and instrumentation *declarations*, and enforces the discipline
that lessons re-enter Stage 1–2 as new requirements.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .conformance import _iter_req_ids, extract_spec

SIGNAL_KINDS = ("incident", "missed-nfr", "usage")


# --------------------------------------------------------------------------- signal + routing (FR-054)
def signal_payload(kind: str, note: str, nfr: str, routed_to: str) -> dict:
    return {"kind": kind, "note": note, "nfr": nfr or "", "routed_to": routed_to}


_FB_HEADER = (
    "# Feedback intents — production lessons routed back to the legislature (3PWR-FR-054)\n\n"
    "> Each entry is a **new requirement candidate**. Take it into a new `3pwr run` spec — do NOT patch "
    "in place. The loop returns to the spec, not to ad-hoc fixes.\n\n"
)


def next_fb_id(text: str, spec_id: str) -> str:
    """Next `<SPEC>-FB-###` id, one past the highest already recorded in the backlog."""
    nums = [int(m) for m in re.findall(rf"{re.escape(spec_id)}-FB-(\d+)", text)]
    return f"{spec_id}-FB-{(max(nums) + 1) if nums else 1:03d}"


def route_to_backlog(backlog_path: Path, spec_id: str, kind: str, nfr: str, note: str) -> str:
    """Append a new-requirement candidate to the spec's feedback backlog and return its id.

    This is the *route to new intent* (3PWR-FR-054): a production lesson becomes a fresh requirement
    to re-enter the lifecycle, never an in-place patch."""
    text = backlog_path.read_text(encoding="utf-8") if backlog_path.exists() else _FB_HEADER
    fb_id = next_fb_id(text, spec_id)
    ref = f" (re: {nfr})" if nfr else ""
    entry = (
        f"- **{fb_id}** [{kind}]{ref}: {note}\n"
        "  - *Route*: re-enter via a new `3pwr run` spec as a new requirement (not an in-place patch).\n"
    )
    backlog_path.parent.mkdir(parents=True, exist_ok=True)
    backlog_path.write_text(text + entry, encoding="utf-8")
    return fb_id


# --------------------------------------------------------------------------- NFR instrumentation (FR-054)
def spec_nfrs(spec_path: Path) -> tuple[str, set[str]]:
    """Return ``(spec_id, {NFR ids})`` declared in a spec."""
    spec_id, _ = extract_spec(spec_path)
    ids: set[str] = set()
    for sid, kind, num in _iter_req_ids(spec_path.read_text(encoding="utf-8")):
        if kind == "NFR" and (not spec_id or sid == spec_id):
            ids.add(f"{sid}-{kind}-{num}")
    return spec_id, ids


def instrumented_nfrs(observability: dict) -> set[str]:
    return {c.get("nfr") for c in observability.get("checks", []) if c.get("nfr")}


@dataclass
class NfrCoverage:
    spec_id: str
    nfrs: list[str] = field(default_factory=list)
    instrumented: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing


def nfr_coverage(spec_path: Path, observability: dict) -> NfrCoverage:
    """Which of a spec's NFRs have a declared live production check (§13 acceptance signal)."""
    spec_id, nfrs = spec_nfrs(spec_path)
    inst = instrumented_nfrs(observability)
    return NfrCoverage(
        spec_id=spec_id,
        nfrs=sorted(nfrs),
        instrumented=sorted(n for n in nfrs if n in inst),
        missing=sorted(n for n in nfrs if n not in inst),
    )


# --------------------------------------------------------------------------- agentic action log (FR-055)
def action_payload(agent: str, action: str) -> dict:
    """A single runtime action, attributed to the agent that took it. Tamper-evidence comes from the
    signed hash chain the entry is appended to (verified by `3pwr verify`)."""
    return {"agent": agent, "action": action}
