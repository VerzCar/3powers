"""Context-sized phases — parse, estimate, schedule, and dispatch a phased tasks artifact (PHASE spec 013).

The tasks artifact decomposes work into ordered **phases**, each a self-contained delegable unit sized so
one fresh agent session (spec + rules + phase tasks + files in scope) fits inside the configured context
budget (delivers 3PWR-FR-060/061 at the engine level). This module owns the deterministic mechanics:

* :func:`parse_phases` reads the phase structure from the tasks artifact's text (PHASE-FR-010);
* :func:`estimate_tokens` / :func:`phase_reload_bytes` compute a deterministic context-size estimate from
  artifact **bytes** — no provider tokenizer, no network (PHASE-FR-008);
* :func:`oversize_warning` words the strictly-advisory over-budget warning (PHASE-FR-009) — the budget
  never fails a stage or gate (PHASE-NFR-002);
* :func:`schedule` batches phases for parallel subagent dispatch **only** when they are marked parallel,
  declare no dependency, and have disjoint declared file scopes (PHASE-FR-011);
* :func:`run_phases` executes the schedule — one fresh session per phase, concurrent inside a batch — and
  returns results in deterministic artifact order (PHASE-FR-010/012).

Everything is a pure function of its inputs (identical artifacts and config produce identical estimates,
schedules, and orderings on any machine — PHASE-NFR-001); the ledger is never touched here, so parallel
completion cannot corrupt the trust spine (PHASE-NFR-003 — the caller appends results *after* collection,
from one thread).
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

# The deterministic bytes→tokens heuristic (PHASE-FR-008): ~4 bytes per token is a practical estimate
# for source and prose; exactness is a non-goal — this is an indicator, not a meter.
BYTES_PER_TOKEN = 4

# The shipped default context budget in tokens (PHASE-FR-007): a practical fill indicator for today's
# common context windows at which model performance is still dependable. Advisory, per-model-configurable.
DEFAULT_BUDGET_TOKENS = 110_000


@dataclass(frozen=True)
class Phase:
    """One phase parsed from the tasks artifact — a self-contained delegable unit (PHASE-FR-010).

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
    """The outcome of executing one phase (PHASE-FR-012)."""

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


def _split_paths(raw: str) -> list[str]:
    return [p.strip() for p in raw.replace(",", " ").split() if p.strip() and p.strip() != "—"]


def parse_phases(text: str) -> list[Phase]:
    """Parse the ordered phases out of a tasks artifact's text (PHASE-FR-010) — pure and deterministic.

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


# --------------------------------------------------------------------------- context-size estimation (PHASE-FR-008)
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
    """The byte size of a phase's reload set (PHASE-FR-008): the specification, the constitution/rules,
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
    """The phase's estimated context size in tokens (PHASE-FR-008) — deterministic given the reload set."""
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
    """The advisory over-budget warning (PHASE-FR-009), or ``None`` when the phase fits.

    Names the phase, its estimate, and the budget, and instructs splitting; an irreducible phase (a
    single task already over budget) is told so. Advisory only — the caller never fails a stage or a
    gate on it (PHASE-NFR-002)."""
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


# --------------------------------------------------------------------------- scheduling (PHASE-FR-011)
def scope_overlap(a: Phase, b: Phase) -> list[str]:
    """The declared file paths two phases share (sorted) — the disjointness check's evidence."""
    return sorted(set(a.file_scope) & set(b.file_scope))


def _parallel_eligible(phase: Phase) -> bool:
    # A phase joins a concurrent batch only when it is marked parallel, declares no dependency, and
    # declares a non-empty file scope — an undeclared scope could touch anything, so it never runs
    # concurrently (the conservative reading of PHASE-FR-011's property).
    return phase.parallel and not phase.depends_on and bool(phase.file_scope)


def schedule(phases: list[Phase]) -> tuple[list[list[Phase]], list[str]]:
    """Batch phases for dispatch (PHASE-FR-011): each batch runs concurrently, batches run in order.

    Consecutive phases join one batch only when every member is parallel-marked, dependency-free, and
    pairwise disjoint in declared file scope; any other phase runs alone, in artifact order. Returns the
    batches plus human-readable notes for each pair that was serialized *despite* parallel markers (the
    reported overlap). Pure and deterministic (PHASE-NFR-001): two phases end up in the same batch only
    if their declared file-scope sets do not intersect."""
    batches: list[list[Phase]] = []
    notes: list[str] = []
    current: list[Phase] = []
    for ph in phases:
        if _parallel_eligible(ph) and current and all(_parallel_eligible(p) for p in current):
            overlaps = [(p, scope_overlap(ph, p)) for p in current]
            clash = [(p, o) for p, o in overlaps if o]
            if not clash:
                current.append(ph)
                continue
            for p, o in clash:
                notes.append(
                    f"phases {p.index} and {ph.index} share files ({', '.join(o[:3])}"
                    f"{', …' if len(o) > 3 else ''}) — running sequentially despite parallel markers"
                )
        if current:
            batches.append(current)
        current = [ph]
    if current:
        batches.append(current)
    return batches, notes


# --------------------------------------------------------------------------- execution (PHASE-FR-010/012)
@dataclass
class PhaseRun:
    """The full result of running a phased implement stage (PHASE-FR-012)."""

    results: list[PhaseResult] = field(default_factory=list)  # deterministic artifact order
    ok: bool = True

    @property
    def failed(self) -> list[PhaseResult]:
        return [r for r in self.results if not r.ok]

    @property
    def failure_detail(self) -> str:
        """An actionable message naming the failing phase(s) (3PWR-FR-034, PHASE-FR-012)."""
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
    """Execute the schedule: each batch's phases run concurrently, batches sequentially (PHASE-FR-010/011).

    ``run_one`` dispatches one phase as a fresh headless session and returns ``(ok, detail)``. Results are
    collected and ordered by phase index, so reruns of the same outcome set record the same order however
    the threads interleave (PHASE-FR-012, PHASE-NFR-001/003). After a batch containing a failure, later
    phases are **not dispatched and not reported as passed** — each is recorded as an explicit failed
    "skipped" result, so a partially-implemented stage can never read as green (PHASE-FR-012)."""
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


def handoff_context(phase: Phase, total: int, *, constitution_text: str = "") -> str:
    """The per-phase handoff block a fresh session's prompt reloads (PHASE-FR-010).

    Carries the phase position, its tasks, and the constitution/rules text; the approved spec and the
    file scope travel in their own prompt blocks (:func:`threepowers.prompts.assemble`), so the whole
    handoff set is reloaded with no carried conversation state (3PWR-FR-061). Deterministic given the
    inputs (PHASE-NFR-001)."""
    parts = [
        f"PHASE {phase.index}/{total}: {phase.name}",
        "This session is fresh: reload everything from this handoff — the approved spec (above), the "
        "constitution/rules (below), this phase's tasks, and the declared file scope. Implement ONLY "
        "this phase's tasks; do not touch files outside the declared scope.",
    ]
    if phase.body:
        parts += ["", "PHASE TASKS:", phase.body]
    if constitution_text.strip():
        parts += ["", "CONSTITUTION / RULES:", constitution_text.strip()]
    return "\n".join(parts)
