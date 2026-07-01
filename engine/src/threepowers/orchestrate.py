"""The orchestration front-end — drive the whole lifecycle as one loop (3PWR-FR-011, §6).

`3pwr run` is a **thin driver over Spec Kit's `workflow run`** (A1): it does not dispatch agents or call
model APIs itself (A3). It walks the lifecycle, streaming progress, and — in ``auto`` mode — auto-continues
past the intermediate review gates while **always** stopping at the two spec-mandated human gates:
``review-spec`` (a human approves the spec, 3PWR-FR-006) and ``signoff`` (a human signs off on the evidence
+ residual, 3PWR-FR-037). ``commit`` mode stops at every gate.

The mode/gate/progress logic (``drive``) is pure given a *runner*; the live runner shells out to
``specify workflow run``/``resume`` (best-effort — the live executive dispatch is the A3 residual), and a
``SimulatedRunner`` drives ``--dry-run`` and the tests. Orchestration is provisioning, never part of the
deterministic verdict (3PWR-NFR-001) — the gates still run through ``3pwr gate run``.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Protocol

from .adapters import run_cmd
from .lifecycle import STAGES, canonical_stage

# The two human gates the spec makes mandatory — auto mode NEVER skips these (spec §1).
MANDATORY_GATES: dict[str, str] = {
    "review-spec": "3PWR-FR-006",  # a human approves the spec before implementation begins
    "signoff": "3PWR-FR-037",  # a human signs off on evidence + residual before advance
}

# The lifecycle steps, in order, mapped to their stage — mirrors .specify/workflows/3powers/lifecycle.yml.
# kind: "action" (an executive/judiciary command), "verdict" (the deterministic gate suite), "gate" (human).
LIFECYCLE_STEPS: list[tuple[str, str, str]] = [
    ("specify", "action", "Spec"),
    ("clarify", "action", "Spec"),
    ("review-spec", "gate", "Spec"),
    ("plan", "action", "Plan"),
    ("review-plan", "gate", "Plan"),
    ("tasks", "action", "Plan"),
    ("oracle", "action", "Build"),
    ("implement", "action", "Build"),
    ("verify", "verdict", "Verify"),
    ("review-verify", "gate", "Verify"),
    ("signoff", "gate", "Review"),
    ("advance", "action", "Ship"),
]


@dataclass
class Event:
    """A streamed progress event."""

    kind: str  # step | verdict | gate-auto | gate-stop | done | failed | aborted
    step: str = ""
    stage: str = ""
    detail: str = ""


@dataclass
class Outcome:
    """What a runner returns from ``run()``/``resume()`` — its position + the events since the last call."""

    status: str  # gate | done | failed | aborted
    gate: str = ""
    stage: str = ""
    verdict: str = ""  # pass | fail | ""
    events: list[Event] = field(default_factory=list)


@dataclass
class RunResult:
    """The driver's result after processing up to the next stop / completion."""

    status: str  # paused_at_gate | done | failed | aborted
    gate: str = ""
    gate_fr: str = ""  # the FR id when the pause is a mandatory gate
    stage: str = ""


class Runner(Protocol):
    def run(self) -> Outcome: ...
    def resume(self, decision: str) -> Outcome: ...


def is_mandatory(gate: str) -> bool:
    return gate in MANDATORY_GATES


def resume_index(gate: str) -> int:
    """The step index just AFTER ``gate`` — where a cross-invocation ``--resume`` picks the run back up."""
    for i, (sid, _kind, _stage) in enumerate(LIFECYCLE_STEPS):
        if sid == gate:
            return i + 1
    return 0


def drive(
    runner: Runner, mode: str, on_event: Callable[[Event], None], *, resuming: bool = False
) -> RunResult:
    """Walk the workflow via ``runner``, applying the auto/commit gate policy and streaming events.

    In ``auto`` mode an intermediate gate is auto-approved (the run continues); a mandatory gate always
    stops. In ``commit`` mode every gate stops. Returns when the run pauses at a stop, completes, fails,
    or aborts. ``resuming`` means we are continuing past a gate the human just approved."""
    outcome = runner.resume("approve") if resuming else runner.run()
    while True:
        for ev in outcome.events:
            on_event(ev)
        if outcome.status == "gate":
            if is_mandatory(outcome.gate) or mode == "commit":
                on_event(Event("gate-stop", outcome.gate, outcome.stage))
                return RunResult(
                    "paused_at_gate",
                    gate=outcome.gate,
                    gate_fr=MANDATORY_GATES.get(outcome.gate, ""),
                    stage=outcome.stage,
                )
            on_event(
                Event("gate-auto", outcome.gate, outcome.stage)
            )  # auto mode: intermediate gate
            outcome = runner.resume("approve")
            continue
        on_event(Event(outcome.status, "", outcome.stage, outcome.verdict))
        return RunResult(outcome.status, stage=outcome.stage)


# --------------------------------------------------------------------------- simulated runner (--dry-run / tests)
class SimulatedRunner:
    """A scripted runner — no live agents. Walks ``steps``, emitting a step/verdict event per action and
    returning at each gate. Drives ``3pwr run --dry-run`` (so the UX is visible offline) and the tests."""

    def __init__(
        self,
        steps: Optional[list[tuple[str, str, str]]] = None,
        verdict: str = "pass",
        start_index: int = 0,
    ) -> None:
        self._steps = steps if steps is not None else LIFECYCLE_STEPS
        self._i = start_index
        self._verdict = verdict

    def _walk(self) -> Outcome:
        events: list[Event] = []
        while self._i < len(self._steps):
            sid, kind, stage = self._steps[self._i]
            self._i += 1
            if kind == "gate":
                return Outcome("gate", gate=sid, stage=stage, events=events)
            if kind == "verdict":
                events.append(Event("verdict", sid, stage, self._verdict))
                if self._verdict != "pass":
                    return Outcome("failed", stage=stage, verdict=self._verdict, events=events)
            else:
                events.append(Event("step", sid, stage))
        return Outcome("done", events=events)

    def run(self) -> Outcome:
        return self._walk()

    def resume(self, decision: str) -> Outcome:
        if decision == "reject":
            return Outcome("aborted", events=[Event("aborted")])
        return self._walk()


# --------------------------------------------------------------------------- live runner (Spec Kit; A3 residual)
class SpecifyRunner:
    """Drive the real lifecycle via ``specify workflow run``/``resume`` (A1). Best-effort JSON parsing —
    the fully-live executive dispatch is the A3 residual; guarded by ``shutil.which('specify')``."""

    def __init__(self, root: Path, workflow: str, inputs: dict[str, str]) -> None:
        self.root = root
        self.workflow = workflow
        self.inputs = inputs

    def _invoke(self, args: list[str]) -> Outcome:
        if shutil.which("specify") is None:
            raise FileNotFoundError(
                "`specify` (Spec Kit) not found — install it to run the live lifecycle, or use --dry-run"
            )
        cmd = "specify " + " ".join(args) + " --json"
        res = run_cmd(cmd, cwd=self.root)
        return _parse_specify_outcome(res.stdout, res.returncode)

    def run(self) -> Outcome:
        args = ["workflow", "run", self.workflow]
        for k, v in self.inputs.items():
            args += ["-i", f"{k}={v}"]
        return self._invoke(args)

    def resume(self, decision: str) -> Outcome:
        return self._invoke(["workflow", "resume", "--decision", decision])


def _parse_specify_outcome(stdout: str, returncode: int) -> Outcome:
    """Best-effort read of a ``specify … --json`` result into an Outcome (schema-tolerant)."""
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return Outcome("failed" if returncode != 0 else "done")
    status = str(data.get("status") or data.get("state") or "").lower()
    gate = data.get("gate") or data.get("paused_at") or ""
    stage = canonical_stage(data.get("stage")) or ""
    verdict = str(data.get("verdict") or "")
    if "gate" in status or gate:
        return Outcome("gate", gate=str(gate), stage=stage or "", verdict=verdict)
    if status in ("done", "complete", "completed", "succeeded"):
        return Outcome("done", stage=stage or "", verdict=verdict)
    if status in ("failed", "error", "aborted"):
        return Outcome(
            "failed" if status != "aborted" else "aborted", stage=stage or "", verdict=verdict
        )
    return Outcome("done" if returncode == 0 else "failed", stage=stage or "", verdict=verdict)


# --------------------------------------------------------------------------- progress rendering (pure)
_MARK = {"done": "✓", "current": "▶", "todo": "·"}


def render_tracker(reached_stage: str) -> str:
    """A one-line stage tracker: stages up to ``reached_stage`` are ✓, the reached one ▶, the rest ·."""
    reached = canonical_stage(reached_stage)
    idx = STAGES.index(reached) if reached in STAGES else -1
    cells = []
    for i, s in enumerate(STAGES):
        mark = _MARK["done"] if i < idx else (_MARK["current"] if i == idx else _MARK["todo"])
        cells.append(f"{mark} {s}")
    return "  ".join(cells)


def format_event(ev: Event, mode: str) -> str:
    """Human-readable one-liner for a streamed event."""
    if ev.kind == "step":
        return f"  ▶ {ev.stage:<8} {ev.step}"
    if ev.kind == "verdict":
        sym = "✓" if ev.detail == "pass" else "✗"
        return f"  {sym} {ev.stage:<8} {ev.step} → verdict {ev.detail.upper()}"
    if ev.kind == "gate-auto":
        return f"  ⏩ {ev.stage:<8} {ev.step} — intermediate gate auto-approved ({mode} mode)"
    if ev.kind == "gate-stop":
        fr = MANDATORY_GATES.get(ev.step)
        tag = f" — HUMAN GATE ({fr})" if fr else " — review gate (commit mode)"
        return f"  ⏸ {ev.stage:<8} {ev.step}{tag}: awaiting your commitment"
    if ev.kind == "failed":
        return "  ✗ gates red — stopped for your decision"
    if ev.kind == "aborted":
        return "  ⊘ aborted"
    if ev.kind == "done":
        return "  ✓ lifecycle complete"
    return f"  · {ev.kind}"
