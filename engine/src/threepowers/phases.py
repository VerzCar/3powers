"""Context-sized phases — parse, estimate, schedule, and dispatch a phased implementation plan.

The tasks stage's artifact (``implementation-plan.md``; legacy ``tasks.md``) decomposes work into
ordered **phases**, each a self-contained delegable unit sized so
one fresh agent session (spec + rules + phase tasks + files in scope) fits inside the configured context
budget. This module owns the deterministic mechanics:

* :func:`parse_phases` reads the phase structure from the tasks artifact's text;
* :func:`estimate_tokens` / :func:`phase_reload_bytes` compute a deterministic context-size estimate from
  artifact **bytes** — no provider tokenizer, no network;
* :func:`oversize_warning` words the strictly-advisory over-budget warning — the budget
  never fails a stage or gate;
* :func:`schedule` batches phases for parallel subagent dispatch — a ``[P]`` phase joins a concurrent
  batch only when its declared dependencies have completed in a prior batch, it declares a file scope,
  and that scope is disjoint from every other batch member — and reports a named reason for every
  serialized ``[P]`` phase;
* :func:`run_phases` executes the schedule — one fresh session per phase, concurrent inside a batch — and
  returns results in deterministic artifact order.

Everything is a pure function of its inputs (identical artifacts and config produce identical estimates,
schedules, and orderings on any machine); the ledger is never touched here, so parallel
completion cannot corrupt the trust spine (the caller appends results *after* collection,
from one thread).
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# The deterministic bytes→tokens heuristic: ~4 bytes per token is a practical estimate
# for source and prose; exactness is a non-goal — this is an indicator, not a meter.
BYTES_PER_TOKEN = 4

# The shipped default context budget in tokens: a practical fill indicator for today's
# common context windows at which model performance is still dependable. Advisory, per-model-configurable.
DEFAULT_BUDGET_TOKENS = 110_000


@dataclass(frozen=True)
class Phase:
    """One phase parsed from the tasks artifact — a self-contained delegable unit.

    ``index`` is the 1-based artifact-order position (the deterministic tie-breaker everywhere);
    ``file_scope`` is the phase's declared scope (its own line plus every task's ``(files: …)``),
    sorted and deduped so scope comparison is order-independent."""

    index: int
    name: str
    tasks: tuple[str, ...] = ()
    file_scope: tuple[str, ...] = ()
    parallel: bool = False
    depends_on: tuple[str, ...] = ()
    body: str = ""


@dataclass
class PhaseResult:
    """The outcome of executing one phase."""

    index: int
    name: str
    ok: bool
    detail: str = ""

    def as_dict(self) -> dict:
        return {"phase": self.index, "name": self.name, "ok": self.ok, "detail": self.detail}


_PHASE_HEADING = re.compile(r"^##\s*Phase\s+([^\s:]+):?\s*(.*)$")
_FILES_IN_TASK = re.compile(r"\(files?:\s*([^)]*)\)")
_SCOPE_LINE = re.compile(r"^\*\*File scope\*\*\s*:\s*(.*)$", re.IGNORECASE)
_DEPENDS_LINE = re.compile(r"^\*\*Depends on\*\*\s*:\s*(.*)$", re.IGNORECASE)
_PARALLEL_LINE = re.compile(r"^\*\*Parallel\*\*\s*:\s*(.*)$", re.IGNORECASE)
_TASK_LINE = re.compile(r"^-\s*\[[ xX]\]\s+")
# A task line's bracketed requirement id, e.g. `[DEMO-FR-001]` — the trace the changelog carries.
_REQ_ID = re.compile(r"\[([0-9A-Z]{2,16}-(?:FR|NFR)-\d{3,})\]")


def requirement_ids(phase: Phase) -> tuple[str, ...]:
    """The requirement ids the phase's task lines trace to — first-appearance order, deduped.

    Pure and deterministic; a phase whose tasks carry no bracketed requirement id yields ``()``,
    so an untraced phase stays visibly untraced in the changelog record."""
    seen: list[str] = []
    for task in phase.tasks:
        for rid in _REQ_ID.findall(task):
            if rid not in seen:
                seen.append(rid)
    return tuple(seen)


def _split_paths(raw: str) -> list[str]:
    return [p.strip() for p in raw.replace(",", " ").split() if p.strip() and p.strip() != "—"]


def parse_phases(text: str) -> list[Phase]:
    """Parse the ordered phases out of a tasks artifact's text — pure and deterministic.

    A phase starts at a ``## Phase N: <name>`` heading. Inside it, ``**File scope**:`` and each task's
    ``(files: …)`` build the declared scope; ``**Depends on**:`` (anything but "none"/"-") declares a
    dependency; ``[P]`` in the heading or ``**Parallel**: yes`` marks the phase parallel-eligible.
    A text with no phase headings yields ``[]`` — the caller treats the whole task set as a single
    phase, preserving the pre-phase behavior as the degenerate case."""
    phases: list[Phase] = []
    current: Optional[dict] = None

    def _flush() -> None:
        nonlocal current
        if current is None:
            return
        phases.append(
            Phase(
                index=len(phases) + 1,
                name=current["name"],
                tasks=tuple(current["tasks"]),
                file_scope=tuple(sorted(set(current["scope"]))),
                parallel=current["parallel"],
                depends_on=tuple(current["depends"]),
                body="\n".join(current["lines"]).strip(),
            )
        )
        current = None

    for line in text.splitlines():
        m = _PHASE_HEADING.match(line.strip())
        if m:
            _flush()
            title = m.group(2).strip()
            parallel = "[P]" in title
            current = {
                "name": title.replace("[P]", "").strip() or f"Phase {m.group(1)}",
                "tasks": [],
                "scope": [],
                "parallel": parallel,
                "depends": [],
                "lines": [line],
            }
            continue
        if current is None:
            continue
        current["lines"].append(line)
        stripped = line.strip()
        sm = _SCOPE_LINE.match(stripped)
        if sm:
            current["scope"].extend(_split_paths(sm.group(1)))
            continue
        dm = _DEPENDS_LINE.match(stripped)
        if dm:
            deps = dm.group(1).strip()
            if deps and deps.lower() not in ("none", "-", "—"):
                current["depends"].extend(d.strip() for d in deps.split(",") if d.strip())
            continue
        pm = _PARALLEL_LINE.match(stripped)
        if pm:
            if pm.group(1).strip().lower() in ("yes", "true", "y"):
                current["parallel"] = True
            continue
        if _TASK_LINE.match(stripped):
            current["tasks"].append(stripped)
            fm = _FILES_IN_TASK.search(stripped)
            if fm:
                current["scope"].extend(_split_paths(fm.group(1)))
    _flush()
    return phases


# --------------------------------------------------------------------------- context-size estimation
def estimate_tokens(total_bytes: int) -> int:
    """The deterministic bytes→tokens estimate (ceiling division) — same bytes, same estimate, any machine."""
    n = max(0, int(total_bytes))
    return -(-n // BYTES_PER_TOKEN)


def _file_bytes(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:
        return 0


def phase_reload_bytes(
    root: Path,
    phase: Phase,
    *,
    spec_path: Optional[Path] = None,
    constitution_path: Optional[Path] = None,
    prompt_text: str = "",
) -> int:
    """The byte size of a phase's reload set: the specification, the constitution/rules,
    the phase's tasks and prompt, and the files in its declared scope. Files absent from the tree count
    zero (they are to be created); no network or tokenizer is involved."""
    total = len(phase.body.encode("utf-8")) + len(prompt_text.encode("utf-8"))
    if spec_path is not None:
        total += _file_bytes(spec_path)
    if constitution_path is not None:
        total += _file_bytes(constitution_path)
    for rel in phase.file_scope:
        total += _file_bytes(root / rel)
    return total


def phase_estimate(
    root: Path,
    phase: Phase,
    *,
    spec_path: Optional[Path] = None,
    constitution_path: Optional[Path] = None,
    prompt_text: str = "",
) -> int:
    """The phase's estimated context size in tokens — deterministic given the reload set."""
    return estimate_tokens(
        phase_reload_bytes(
            root,
            phase,
            spec_path=spec_path,
            constitution_path=constitution_path,
            prompt_text=prompt_text,
        )
    )


def oversize_warning(phase: Phase, estimate: int, budget: int) -> Optional[str]:
    """The advisory over-budget warning, or ``None`` when the phase fits.

    Names the phase, its estimate, and the budget, and instructs splitting; an irreducible phase (a
    single task already over budget) is told so. Advisory only — the caller never fails a stage or a
    gate on it."""
    if estimate <= budget:
        return None
    advice = (
        "this phase is irreducible (a single task over budget) — the warning stands and the run proceeds"
        if len(phase.tasks) <= 1
        else "split the phase into smaller phases"
    )
    return (
        f"phase {phase.index} '{phase.name}': estimated ~{estimate} tokens exceeds the context "
        f"budget ({budget}); {advice} (advisory — never blocking)"
    )


# --------------------------------------------------------------------------- scheduling
# The three closed serialization-reason strings a serialized ``[P]`` phase can carry. They are the
# machine-usable vocabulary the CLI renders as pre-batch log lines — kept here as the single source
# so every consumer names a serialization the same way.
REASON_NO_SCOPE = "no file scope declared"


def _reason_depends(index: int) -> str:
    """The named reason for a ``[P]`` phase blocked by a dependency not yet completed."""
    return f"depends on Phase {index} (not yet complete)"


def _reason_overlap(index: int) -> str:
    """The named reason for a ``[P]`` phase blocked by a file-scope overlap with a batch member."""
    return f"file scope overlaps Phase {index}"


def scope_overlap(a: Phase, b: Phase) -> list[str]:
    """The declared file paths two phases share (sorted) — the disjointness check's evidence."""
    return sorted(set(a.file_scope) & set(b.file_scope))


_PHASE_REF = re.compile(r"\d+")


def _dependency_indices(phase: Phase) -> set[int]:
    """The 1-based phase indices a phase declares it depends on — parsed from its ``depends_on`` refs.

    Each declared dependency (e.g. ``"Phase 1"`` or ``"1"``) contributes its leading integer; a ref
    carrying no integer is ignored. Pure and deterministic."""
    indices: set[int] = set()
    for dep in phase.depends_on:
        m = _PHASE_REF.search(dep)
        if m:
            indices.add(int(m.group()))
    return indices


def _serialization_reason(
    phase: Phase, current_batch: list[Phase], completed: set[int]
) -> Optional[str]:
    """Why a ``[P]`` phase cannot join the batch being formed, or ``None`` when it can.

    Checked in a fixed order so the outcome is deterministic and every serialization is named by
    exactly one cause: an undeclared file scope, then a dependency not yet completed in a *prior*
    (already-closed) batch, then a file-scope overlap with a member of the batch being formed."""
    if not phase.file_scope:
        return REASON_NO_SCOPE
    unmet = sorted(d for d in _dependency_indices(phase) if d not in completed)
    if unmet:
        return _reason_depends(unmet[0])
    for member in current_batch:
        if scope_overlap(phase, member):
            return _reason_overlap(member.index)
    return None


@dataclass(frozen=True)
class PhaseDecision:
    """One phase's scheduling decision — its batch, whether it runs concurrently, and, for a
    serialized ``[P]`` phase, the named reason it did not parallelize.

    ``batch_index`` is the 0-based position of the phase's batch in run order. ``parallel`` is
    ``True`` only when the phase's batch holds more than one member (it actually runs concurrently).
    ``serialization_reason`` is exactly one of the three closed strings — :data:`REASON_NO_SCOPE`,
    ``"depends on Phase N (not yet complete)"``, or ``"file scope overlaps Phase N"`` — when a
    ``[P]`` phase was blocked from a sibling batch, and ``None`` when the phase runs in parallel or
    was never a ``[P]`` candidate blocked by a concrete cause. Machine-usable: downstream rendering
    (CLI pre-batch logs, ``progress.md`` markers) consumes these fields directly."""

    index: int
    name: str
    batch_index: int
    parallel: bool
    serialization_reason: Optional[str] = None


@dataclass(frozen=True)
class Schedule:
    """The scheduler's verdict: ordered batches plus per-phase decision metadata.

    ``batches[i]`` runs concurrently; batches run in order. ``decisions`` holds one
    :class:`PhaseDecision` per phase, stably ordered by phase index. Pure and deterministic, and —
    like the rest of this module — free of any trust-spine state; the caller appends run results
    from one thread *after* collection."""

    batches: list[list[Phase]]
    decisions: list[PhaseDecision]

    @property
    def notes(self) -> list[str]:
        """Human-readable serialization notes — one line per serialized ``[P]`` phase naming its reason.

        Derived from :attr:`decisions`; preserves the phase-order, reason-bearing summary the CLI
        prints today while richer per-batch rendering consumes the structured decisions directly."""
        return [
            f"phase {d.index} ({d.name}) runs sequentially — {d.serialization_reason}"
            for d in self.decisions
            if d.serialization_reason is not None
        ]


def schedule(phase_list: list[Phase]) -> Schedule:
    """Batch phases for dispatch and record why each ``[P]`` phase did or did not parallelize.

    A ``[P]`` phase joins the batch currently being formed when (1) every phase it declares a
    dependency on has completed in a *prior* (already-closed) batch, (2) it declares a non-empty
    file scope, and (3) its scope is disjoint from every other member of that batch. Otherwise it is
    serialized into its own batch and its :class:`PhaseDecision` carries exactly one named reason —
    :data:`REASON_NO_SCOPE`, ``"depends on Phase N (not yet complete)"``, or ``"file scope overlaps
    Phase N"`` (checked in that order). A non-``[P]`` phase always runs alone.

    Returns a :class:`Schedule` carrying the ordered ``batches`` (each runs concurrently; batches run
    in order) and one ``decisions`` record per phase in stable phase-index order. Pure and
    deterministic: identical input always yields identical batches, decisions, and ordering on any
    machine, and the module never touches the trust spine."""
    batches: list[list[Phase]] = []
    reasons: dict[int, str] = {}
    completed: set[int] = set()  # indices in already-closed (prior) batches
    current: list[Phase] = []

    def _close() -> None:
        nonlocal current
        if current:
            batches.append(current)
            for member in current:
                completed.add(member.index)
            current = []

    for ph in phase_list:
        if not ph.parallel:
            # A non-parallel phase always runs alone, in its own batch, in artifact order.
            _close()
            current = [ph]
            _close()
            continue
        reason = _serialization_reason(ph, current, completed)
        if reason is None:
            current.append(ph)
            continue
        # Blocked from the batch being formed: close it (its members complete) and start this phase
        # in a fresh batch, where a later disjoint sibling may still join it.
        _close()
        current = [ph]
        reasons[ph.index] = reason
    _close()

    batch_of: dict[int, int] = {}
    size_of: dict[int, int] = {}
    for bi, batch in enumerate(batches):
        for member in batch:
            batch_of[member.index] = bi
            size_of[member.index] = len(batch)

    decisions: list[PhaseDecision] = []
    for ph in sorted(phase_list, key=lambda p: p.index):
        parallel = size_of.get(ph.index, 1) > 1
        # A phase that ends up sharing its batch actually parallelized: its earlier blocker (if any)
        # no longer applies, so no reason is reported.
        reason = None if parallel else reasons.get(ph.index)
        decisions.append(
            PhaseDecision(
                index=ph.index,
                name=ph.name,
                batch_index=batch_of.get(ph.index, 0),
                parallel=parallel,
                serialization_reason=reason,
            )
        )
    return Schedule(batches=batches, decisions=decisions)


# --------------------------------------------------------------------------- execution
@dataclass
class PhaseRun:
    """The full result of running a phased implement stage."""

    results: list[PhaseResult] = field(default_factory=list)  # deterministic artifact order
    ok: bool = True

    @property
    def failed(self) -> list[PhaseResult]:
        return [r for r in self.results if not r.ok]

    @property
    def failure_detail(self) -> str:
        """An actionable message naming the failing phase(s)."""
        parts = []
        for r in self.failed:
            why = f": {r.detail}" if r.detail else ""
            parts.append(f"phase {r.index} '{r.name}' failed{why}")
        return "; ".join(parts)


def run_phases(
    batches: list[list[Phase]],
    run_one: Callable[[Phase], tuple[bool, str]],
    *,
    max_workers: int = 4,
) -> PhaseRun:
    """Execute the schedule: each batch's phases run concurrently, batches sequentially.

    ``run_one`` dispatches one phase as a fresh headless session and returns ``(ok, detail)``. Results are
    collected and ordered by phase index, so reruns of the same outcome set record the same order however
    the threads interleave. After a batch containing a failure, later
    phases are **not dispatched and not reported as passed** — each is recorded as an explicit failed
    "skipped" result, so a partially-implemented stage can never read as green."""
    run = PhaseRun()
    failed = False
    for batch in batches:
        if failed:
            for ph in batch:
                run.results.append(
                    PhaseResult(ph.index, ph.name, False, "skipped: an earlier phase failed")
                )
            continue
        if len(batch) == 1:
            ph = batch[0]
            ok, detail = run_one(ph)
            run.results.append(PhaseResult(ph.index, ph.name, ok, detail))
        else:
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as pool:
                outcomes = list(pool.map(run_one, batch))
            for ph, (ok, detail) in zip(batch, outcomes):
                run.results.append(PhaseResult(ph.index, ph.name, ok, detail))
        if any(not r.ok for r in run.results):
            failed = True
    run.results.sort(key=lambda r: r.index)
    run.ok = all(r.ok for r in run.results)
    return run


def completed_phases_summary(phase_list: list[Phase], current_index: int) -> str:
    """The one-line "phases already completed" summary for the phase prompt.

    Names every phase preceding ``current_index`` in artifact order — e.g.
    ``Phase 1 (HeaderComponent styles), Phase 2 (ButtonComponent)`` — so a fresh session never
    redoes earlier work; returns ``"none"`` for the first phase (nothing is invented). A pure,
    deterministic function of the parsed phase list and the index."""
    done = [p for p in phase_list if p.index < current_index]
    if not done:
        return "none"
    return ", ".join(f"Phase {p.index} ({p.name})" for p in done)


def _scope_gate_target(phase: Phase) -> str:
    """The concrete ``--path`` target for the phase's coding-gate command — deterministic.

    The first declared scope path's top-level directory when every scope path shares it, else the
    repository root (``.``); an undeclared scope also yields the root, so the command is always
    concrete and runnable."""
    tops = {p.split("/", 1)[0] for p in phase.file_scope if p}
    if len(tops) == 1:
        return tops.pop()
    return "."


def handoff_context(
    phase: Phase,
    total: int,
    *,
    constitution_text: str = "",
    spec_id: str = "",
    completed_summary: str = "none",
) -> str:
    """The per-phase handoff block a fresh session's prompt reloads.

    Carries the PHASE INSTRUCTION contract: scope limited to the declared
    phase's tasks and file scope, ``[P]`` tasks dispatched concurrently via subagents, completion
    markers (``[x]`` done / ``[!]`` + reason) written back to the implementation plan
    (``implementation-plan.md``; legacy ``tasks.md``), the per-phase coding-gate command, no
    operator questions — plus the completed-phases summary, the phase's tasks, and the
    constitution/rules text. The approved spec and the file scope travel in their own prompt blocks
    (:func:`threepowers.prompts.assemble`), so the whole handoff set is reloaded with no carried
    conversation state. Deterministic given the inputs."""
    run_label = f" for run {spec_id}" if spec_id else ""
    gate_target = _scope_gate_target(phase)
    parts = [
        "═══════════════════ PHASE INSTRUCTION ════════════════════════",
        f"PHASE {phase.index}/{total}: {phase.name}",
        f"You are implementing Phase {phase.index} of {total}{run_label}.",
        "",
        f'SCOPE: implement only the tasks explicitly listed under "## Phase {phase.index}" in the '
        "tasks below.",
        "Do NOT modify files outside the declared file scope for this phase.",
        "Do NOT implement tasks from other phases.",
        "",
        "PARALLEL TASKS: tasks marked [P] in this phase MUST be executed via your own sub-agents "
        "— dispatch one sub-agent per [P] task, run them concurrently, and collect their results "
        "before proceeding.",
        "Do not serialize [P] tasks in your own session; sub-agent dispatch is the required "
        "execution mode for them.",
        "(Whole phases marked [P] with disjoint file scopes are already dispatched concurrently "
        "by the engine as separate fresh sessions — that engine-level parallelism is not yours "
        "to manage.)",
        "",
        "CODING GATE: after finishing this phase's tasks, run the coding gates over this phase's "
        "file scope —",
        f"`3pwr gate run --path {gate_target}` (or the project's own format/lint/type/test verify "
        "commands) —",
        "and fix every failure before reporting the phase done. A phase with a red coding gate is "
        "not complete.",
        "These per-phase runs are the coder's own advisory checks; the Verify stage remains the "
        "sole signed verdict.",
        "",
        "COMPLETION: when you have finished every task in this phase, update the implementation "
        "plan (implementation-plan.md; legacy tasks.md):",
        "mark each completed task with `[x]` in its checkbox. If a task cannot be completed,",
        "mark it `[!]` and append a one-line reason.",
        "",
        "CLARIFICATIONS: do not ask the operator for input. If something is unclear, make the most",
        "reasonable decision and document your assumption in a comment in the code (not in the "
        "implementation plan).",
        "",
        "This session is fresh: reload everything from this handoff — the approved spec (above), "
        "the constitution/rules (below), this phase's tasks, and the declared file scope.",
        "",
        f"Phases already completed: {completed_summary or 'none'}",
    ]
    if phase.body:
        parts += ["", "PHASE TASKS:", phase.body]
    if constitution_text.strip():
        parts += ["", "CONSTITUTION / RULES:", constitution_text.strip()]
    return "\n".join(parts)
