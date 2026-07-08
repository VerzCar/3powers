"""Human-readable run progress — ``specs-src/<NNN>-<slug>/progress.md``.

The signed ledger is the run's authoritative, machine-readable record; this module writes the
*operator's* view of it: one markdown file in the run's feature folder that an operator can ``cat``
or share to see where the run is and what to do next. The file tracks stage-level progress (one row
per lifecycle stage with a status glyph and completion timestamp) and, while the
current stage has declared phases, phase-level progress read live from the tasks artifact's
checkboxes. It carries a "Current state" block, the last deterministic-gate
verdict, copy-pasteable helper commands with the run's real identity, and the failed gate names of
the last verify attempt.

Writes are atomic — rendered to ``.progress.md.tmp`` in the same directory, then ``os.replace``d
onto ``progress.md`` — so a concurrent reader never sees a torn file (matching the
ledger's durability posture). Rendering is a pure function of a :class:`Snapshot`; the stateful
:class:`Reporter` folds the run loop's lifecycle triggers (stage start / stage complete / gate
verdict / human-gate pause / run failure) into that snapshot. The module never
touches the ledger and never enters a verdict; a failure writing this file must never fail a run
(the caller degrades errors to a warning).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from . import phases as phasesmod
from . import workspace
from .lifecycle import STAGES
from .orchestrate import LIFECYCLE_STEPS

# The engine-owned progress file and its same-directory atomic-write staging name.
FILENAME = "progress.md"
TMP_NAME = ".progress.md.tmp"

# Row statuses and their glyphs.
STATUS_DONE = "done"
STATUS_RUNNING = "running"
STATUS_PENDING = "pending"
STATUS_PAUSED = "paused"
STATUS_FAILED = "failed"

GLYPHS: dict[str, str] = {
    STATUS_DONE: "✓",
    STATUS_RUNNING: "⏳",
    STATUS_PENDING: "○",
    STATUS_PAUSED: "🔒",
    STATUS_FAILED: "✗",
}

_TIMESTAMP_FMT = "%Y-%m-%d %H:%M"
_CHECKED_TASK = re.compile(r"^-\s*\[[xX]\]")

# Each stage's non-gate lifecycle steps, in walk order — a stage is complete when all of them are
# (a gate belongs to the pause/approval flow, not to the stage's own work).
_STAGE_ACTIONS: dict[str, tuple[str, ...]] = {}
for _sid, _kind, _stage in LIFECYCLE_STEPS:
    if _kind != "gate":
        _STAGE_ACTIONS[_stage] = (*_STAGE_ACTIONS.get(_stage, ()), _sid)


@dataclass
class StageRow:
    """One rendered row of the stage-progress table."""

    stage: str
    status: str = STATUS_PENDING
    completed: str = ""  # the completion timestamp, empty until the stage is done
    label: str = ""  # an override for the status word (e.g. "phase 2/3" on a phased Build)
    tokens: Optional[int] = None  # agent-reported usage; None renders the unknown placeholder


@dataclass
class PhaseRow:
    """One rendered row of the phase-detail table."""

    index: int
    description: str
    status: str  # done | running | pending | failed
    tasks_done: str  # "3/5", or "—" for an untouched pending phase
    tokens: Optional[int] = None  # agent-reported usage; None renders the unknown placeholder


@dataclass
class Snapshot:
    """Everything :func:`render` needs — a pure, self-contained view of the run's progress.

    Built by :class:`Reporter` at each lifecycle trigger; tests may construct one directly to
    assert the rendered schema without a live run."""

    nnn: str  # the workspace number for the title line
    slug: str
    timestamp: str
    spec_id: str  # the run's resolved identity — interpolated into the helper commands
    stages: list[StageRow]
    current_state: str
    since: str = ""
    last_verdict: str = ""  # empty renders the no-verdict placeholder
    failed_gates: list[str] = field(default_factory=list)
    phase_stage: str = ""  # the stage the phase table details (e.g. "Build")
    phases: list[PhaseRow] = field(default_factory=list)
    tier: str = "Standard"


def failed_gate_names(verdict: dict[str, Any]) -> list[str]:
    """The failed gate names of a verdict dict, in verdict order.

    Names only — the actionable error lines stay with the gate-red event rendering; the progress
    file lists what failed, not the raw output."""
    gates = verdict.get("gates") or []
    return [str(g.get("gate", "?")) for g in gates if g.get("status") == "fail"]


def _tokens_cell(tokens: Optional[int]) -> str:
    """The Tokens column cell: the agent-reported count, or the unknown placeholder ``—``."""
    return str(tokens) if tokens is not None else "—"


def render(snap: Snapshot) -> str:
    """Render the progress markdown for ``snap`` — pure and deterministic given the snapshot.

    Layout per the progress-file content schema: the title line, the stage-progress
    table, the phase-detail table only when the snapshot carries phases,
    then the Current state / Last verdict / fenced Helper commands / Gate
    failures sections with the run's real identity interpolated. Both tables carry a Tokens
    column — the agent-reported usage per stage/phase, ``—`` when the backend reports none."""
    lines = [f"# Run {snap.nnn} · {snap.slug} · {snap.timestamp}", ""]
    lines += ["## Stage progress", ""]
    lines += [
        "| Stage | Status | Completed | Tokens |",
        "|-------|--------|-----------|--------|",
    ]
    for row in snap.stages:
        cell = f"{GLYPHS.get(row.status, '·')} {row.label or row.status}"
        lines.append(f"| {row.stage} | {cell} | {row.completed} | {_tokens_cell(row.tokens)} |")
    if snap.phases:
        lines += ["", f"### {snap.phase_stage} — phase detail", ""]
        lines += [
            "| Phase | Description | Status | Tasks done | Tokens |",
            "|-------|-------------|--------|------------|--------|",
        ]
        for ph in snap.phases:
            status_cell = f"{GLYPHS.get(ph.status, '·')} {ph.status}"
            lines.append(
                f"| {ph.index} | {ph.description} | {status_cell} | {ph.tasks_done} | "
                f"{_tokens_cell(ph.tokens)} |"
            )
    lines += ["", "## Current state", "", snap.current_state or "○ not started yet"]
    if snap.since:
        lines.append(f"**Since:** {snap.since}")
    lines += ["", "## Last verdict", "", snap.last_verdict or "— (no verdict yet)"]
    lines += [
        "",
        "## Helper commands",
        "",
        "```bash",
        "# Check current status",
        f"3pwr run --status --spec-id {snap.spec_id}",
        "",
        "# Resume after approval / gate-pause",
        f"3pwr run --resume --spec-id {snap.spec_id} --approver <you>",
        "",
        "# Abort this run",
        f"3pwr abort --spec-id {snap.spec_id}",
        "",
        "# Re-run gates only",
        f"3pwr gate run --id {snap.spec_id} --tier {snap.tier}",
        "```",
    ]
    lines += ["", "## Gate failures (last verify attempt)", ""]
    if snap.failed_gates:
        lines += [f"- {g}" for g in snap.failed_gates]
    else:
        lines.append("(none yet)")
    return "\n".join(lines) + "\n"


def write(snap: Snapshot, feature_dir: Path) -> Path:
    """Atomically write the rendered snapshot as ``<feature_dir>/progress.md``.

    Renders to ``.progress.md.tmp`` in the same directory, then ``os.replace``s it onto the target,
    so a reader never observes a torn file and no ``.tmp`` survives a successful write. Returns the
    written path. Raises ``OSError`` on an IO failure — the caller degrades it to a warning, never
    a run failure."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    tmp = feature_dir / TMP_NAME
    target = feature_dir / FILENAME
    tmp.write_text(render(snap), encoding="utf-8")
    os.replace(tmp, target)
    return target


def _default_now() -> str:
    return datetime.now().strftime(_TIMESTAMP_FMT)


class Reporter:
    """Fold the run loop's lifecycle triggers into a :class:`Snapshot` and rewrite ``progress.md``.

    One instance per run invocation, bound to the run's feature folder and resolved identity. Each
    trigger method — :meth:`stage_started`, :meth:`stage_completed`, :meth:`verdict`,
    :meth:`paused`, :meth:`failed`, :meth:`completed` — updates the tracked state and atomically
    rewrites the file. Stage completion is per-step: a stage's row turns ``done``
    when its last non-gate lifecycle step completes; starting a later stage marks every earlier
    stage done (a resume reconstructs past sessions' rows without replaying their events). Phase
    detail is re-read from the tasks artifact's checkboxes at every write, so an agent marking
    tasks ``[x]`` is reflected on the next trigger. ``now`` is injectable for
    deterministic tests; IO errors propagate for the caller to degrade."""

    def __init__(
        self,
        feature_dir: Path,
        *,
        spec_id: str = "",
        tier: str = "Standard",
        now: Optional[Callable[[], str]] = None,
    ) -> None:
        """Bind the reporter to a run: ``feature_dir`` names the workspace (its ``NNN-slug`` name
        feeds the title line), ``spec_id`` is the run's resolved identity for the helper commands
        (defaults to the folder's ``NNN``), ``tier`` fills the gate-run hint."""
        self._feature_dir = feature_dir
        nnn, _, slug = feature_dir.name.partition("-")
        self._nnn = nnn
        self._slug = slug or feature_dir.name
        self._spec_id = spec_id or nnn
        self._tier = tier
        self._now = now or _default_now
        self._started = self._now()
        self._status: dict[str, str] = {s: STATUS_PENDING for s in STAGES}
        self._completed_at: dict[str, str] = {}
        self._steps_done: set[str] = set()
        self._current_step = ""
        self._current_stage = ""
        self._current_state = ""
        self._since = ""
        self._last_verdict = ""
        self._failed_gates: list[str] = []
        # Advisory agent-reported usage: per-stage totals (accumulated over the stage's steps)
        # and per-phase counts for the phase-detail table. Unknown stays absent — rendered —.
        self._stage_tokens: dict[str, int] = {}
        self._phase_tokens: dict[int, int] = {}

    # ------------------------------------------------------------------ the lifecycle triggers
    def stage_started(self, step: str, stage: str) -> Path:
        """Stage start: the stage's row turns ``⏳ running`` and the current-state
        block names the running step; every earlier stage is marked done (their events may belong
        to a prior session on a resume)."""
        self._complete_before(stage)
        if self._status.get(stage) != STATUS_DONE:
            self._status[stage] = STATUS_RUNNING
        self._current_step = step
        self._current_stage = stage
        self._since = self._now()
        self._current_state = f"**Stage:** {stage} — running '{step}'"
        return self.write()

    def stage_completed(self, step: str, stage: str, tokens: Optional[int] = None) -> Path:
        """Stage complete: record the step; when it was the stage's last non-gate
        step the row turns ``✓ done`` with a completion timestamp. ``tokens`` — the step's
        agent-reported usage — accumulates into the stage's Tokens cell (additive; ``None``
        leaves the cell unknown)."""
        if tokens is not None and stage in self._status:
            self._stage_tokens[stage] = self._stage_tokens.get(stage, 0) + int(tokens)
        self._mark_step_done(step, stage)
        self._current_state = f"**Stage:** {stage} — '{step}' complete"
        return self.write()

    def phase_tokens(self, tokens_by_index: dict[int, int]) -> None:
        """Record the agent-reported usage of a phased build's phases, keyed by phase index.

        Feeds the phase-detail table's Tokens column; phases absent from the mapping stay
        unknown. No write is triggered — the next lifecycle trigger renders the counts."""
        self._phase_tokens.update({int(k): int(v) for k, v in tokens_by_index.items()})

    def verdict(self, result: str, failed_gates: list[str]) -> Path:
        """Gate verdict PASS/FAIL: update the last-verdict block; a red verdict
        lists the failed gate names in the gate-failures section and marks Verify ``✗ failed``, a
        green one clears the section and completes Verify."""
        ts = self._now()
        if result == "pass":
            self._last_verdict = f"✓ pass ({ts})"
            self._failed_gates = []
            self._mark_step_done("verify", "Verify")
            self._current_state = "**Stage:** Verify — gates passed"
        else:
            names = ", ".join(failed_gates) if failed_gates else "see the run output"
            self._last_verdict = f"✗ fail ({ts}) — failed gates: {names}"
            self._failed_gates = list(failed_gates)
            self._status["Verify"] = STATUS_FAILED
            self._current_state = "**Stage:** Verify — ✗ gates red (see gate failures below)"
        return self.write()

    def paused(self, gate: str, stage: str) -> Path:
        """Human-gate pause: the gate's stage shows ``🔒 paused`` and the
        current-state block names the awaited gate with the resume command."""
        self._complete_before(stage)
        if stage in self._status:
            self._status[stage] = STATUS_PAUSED
        self._current_state = (
            f"🔒 paused at '{gate}' ({stage}) — resume with "
            f"`3pwr run --resume --spec-id {self._spec_id} --approver <you>`"
        )
        return self.write()

    def failed(self, failure_class: str, stage: str, detail: str = "") -> Path:
        """Run failure: the failing stage shows ``✗ failed`` and the current-state
        block carries the recorded failure class."""
        self._complete_before(stage)
        if stage in self._status:
            self._status[stage] = STATUS_FAILED
        where = f" at {stage}" if stage else ""
        extra = f" — {detail}" if detail and detail != "fail" else ""
        self._current_state = f"✗ failed — {failure_class}{where}{extra}"
        return self.write()

    def completed(self) -> Path:
        """Lifecycle complete: every stage row turns done and the current state says so."""
        for stage in STAGES:
            self._status[stage] = STATUS_DONE
        self._current_state = "✓ lifecycle complete — advanced to Ship; observe feeds new intent"
        return self.write()

    # ------------------------------------------------------------------ snapshot + write
    def snapshot(self) -> Snapshot:
        """The current :class:`Snapshot` — the pure input :func:`render` consumes."""
        phase_rows, running_label = self._phases_view()
        rows: list[StageRow] = []
        for stage in STAGES:
            status = self._status.get(stage, STATUS_PENDING)
            label = running_label if (stage == "Build" and status == STATUS_RUNNING) else ""
            rows.append(
                StageRow(
                    stage=stage,
                    status=status,
                    completed=self._completed_at.get(stage, ""),
                    label=label,
                    tokens=self._stage_tokens.get(stage),
                )
            )
        return Snapshot(
            nnn=self._nnn,
            slug=self._slug,
            timestamp=self._started,
            spec_id=self._spec_id,
            stages=rows,
            current_state=self._current_state,
            since=self._since,
            last_verdict=self._last_verdict,
            failed_gates=list(self._failed_gates),
            phase_stage="Build" if phase_rows else "",
            phases=phase_rows,
            tier=self._tier,
        )

    def write(self) -> Path:
        """Atomically (re)write ``progress.md`` from the current state."""
        return write(self.snapshot(), self._feature_dir)

    # ------------------------------------------------------------------ internals
    def _complete_before(self, stage: str) -> None:
        # Starting a stage means everything before it is done — the resume-safe inference: rows for
        # stages completed in a prior session turn done without replaying that session's events.
        if stage not in STAGES:
            return
        for earlier in STAGES[: STAGES.index(stage)]:
            self._status[earlier] = STATUS_DONE

    def _mark_step_done(self, step: str, stage: str) -> None:
        self._steps_done.add(step)
        needed = _STAGE_ACTIONS.get(stage, ())
        if needed and all(sid in self._steps_done for sid in needed):
            self._status[stage] = STATUS_DONE
            self._completed_at.setdefault(stage, self._now())

    def _phases_view(self) -> tuple[list[PhaseRow], str]:
        # Phase detail applies only while the phased stage is current: the
        # implement step, with a tasks artifact that declares phases. Checkbox state is re-read at
        # every write, so agents marking tasks [x] surface on the next trigger.
        if self._current_step != "implement":
            return [], ""
        artifact = workspace.find_artifact(self._feature_dir, "tasks")
        if artifact is None:
            return [], ""
        try:
            text = artifact.read_text(encoding="utf-8")
        except OSError:
            return [], ""
        parsed = phasesmod.parse_phases(text)
        if not parsed:
            return [], ""
        build_failed = self._status.get("Build") == STATUS_FAILED
        rows: list[PhaseRow] = []
        running_label = ""
        active_seen = False
        for ph in parsed:
            total = len(ph.tasks)
            done = sum(1 for t in ph.tasks if _CHECKED_TASK.match(t))
            if total and done == total:
                status = STATUS_DONE
            elif not active_seen:
                status = STATUS_FAILED if build_failed else STATUS_RUNNING
                active_seen = True
                running_label = f"phase {ph.index}/{len(parsed)}"
            else:
                status = STATUS_PENDING
            tasks_done = "—" if (status == STATUS_PENDING and done == 0) else f"{done}/{total}"
            rows.append(
                PhaseRow(
                    index=ph.index,
                    description=ph.name,
                    status=status,
                    tasks_done=tasks_done,
                    tokens=self._phase_tokens.get(ph.index),
                )
            )
        return rows, running_label
