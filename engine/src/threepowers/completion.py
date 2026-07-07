"""The deterministic stage-completion gate + the oracle/implement records (SRCX, spec 017).

Two SRCX concerns live here, both pure given injected inputs (SRCX-NFR-005):

* **Stage records** (SRCX-FR-005/006): the two producing stages whose real outputs live elsewhere in
  the repository — ``oracle`` (authored test files) and ``implement`` (code changes) — each leave a
  short markdown *record* in the run's feature folder that links those outputs at their real paths.
  The record never relocates or duplicates them; a multi-phase implement yields exactly one
  ``implement.md`` enumerating every phase in deterministic artifact order.

* **The completion gate** (SRCX-FR-012..018): a producing stage is *done* only when BOTH its declared
  markdown artifact exists on disk in the feature folder AND a matching signed ``run``/``stage`` (or
  ``checkpoint``) ledger entry records that path. Either condition missing blocks the run with a named,
  classified failure — ``artifact_absent`` (recorded but gone from disk) or ``artifact_unrecorded``
  (on disk but in no ledger entry) — and the stage must be re-run. The same gate governs ``--resume``
  (SRCX-FR-017): a resume re-enters at the earliest recorded producing stage whose artifact is broken,
  never skipping a stage on the strength of a ledger entry alone.

The gate's outcome is a pure function of (feature-folder disk state, ledger entries, step) — no model
call, no network (SRCX-NFR-001, 3PWR-NFR-001). The ledger entries are read once by the caller and
injected (SRCX-NFR-004); nothing here appends to or signs the ledger — no new entry type, no signing
change (SRCX-NFR-002).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from .orchestrate import LIFECYCLE_STEPS
from .workspace import PRODUCING_STEPS, find_artifact, stage_artifact_path

# The two named completion-gate failure classes (SRCX-FR-014/015) — new VALUES folding through the
# existing run/failure handling; distinct from RUNLIVE's dispatch-time ``artifact_missing``.
CLASS_ABSENT = "artifact_absent"
CLASS_UNRECORDED = "artifact_unrecorded"

# The producing steps whose feature-folder markdown is an engine-written *record* (SRCX-FR-005).
RECORD_STEPS: tuple[str, ...] = ("oracle", "implement")


@dataclass(frozen=True)
class CompletionCheck:
    """One stage's completion-gate verdict (SRCX-FR-012) — pure given its inputs (SRCX-NFR-005)."""

    ok: bool
    step: str
    path: str = ""  # the declared repo-relative POSIX artifact path
    failure_class: str = ""  # CLASS_ABSENT | CLASS_UNRECORDED | ""

    @property
    def message(self) -> str:
        """The actionable failure line naming the stage and the artifact (SRCX-FR-014/015)."""
        if self.ok:
            return ""
        if self.failure_class == CLASS_ABSENT:
            return (
                f"stage '{self.step}' has no artifact on disk — expected {self.path}; "
                f"the stage must be re-run"
            )
        return (
            f"stage '{self.step}' produced {self.path}, but no ledger entry records it; "
            f"the stage must be re-run"
        )


def is_producing(step: str) -> bool:
    """Whether ``step`` is gated at all (SRCX-FR-007/018): only the producing steps carry the gate."""
    return step in PRODUCING_STEPS


def recorded_stage_artifacts(entries: list[dict], spec_id: str) -> dict[str, list[str]]:
    """The artifact paths recorded per completed step — one pass over the ledger (SRCX-NFR-004).

    A matching record is a ``run`` entry of kind ``stage`` or ``checkpoint`` for ``spec_id``
    (SRCX-FR-013); its ``artifacts`` list accumulates per step (a re-run's fresh entry adds to the
    append-only history — the union is what "is recorded" means)."""
    recorded: dict[str, list[str]] = {}
    for e in entries:
        if e.get("spec_id") != spec_id or e.get("type") != "run":
            continue
        payload = e.get("payload", {})
        if payload.get("kind") not in ("stage", "checkpoint") or not payload.get("step"):
            continue
        step = str(payload["step"])
        paths = recorded.setdefault(step, [])
        for p in payload.get("artifacts", []) or []:
            if p not in paths:
                paths.append(str(p))
    return recorded


def declared_artifact_rel(root: Path, feature_dir: Path, step: str) -> tuple[str, bool]:
    """The declared artifact's repo-relative POSIX path and whether it exists on disk (SRCX-FR-013).

    The flat location wins; the PHASE split location is the read fallback for legacy features
    (SRCX-FR-003) — so an already-written split artifact is checked *at its split path* while a new
    stage lands flat. When neither exists, the canonical flat write location names the missing path."""
    located = find_artifact(feature_dir, step)
    path = located if located is not None else stage_artifact_path(feature_dir, step)
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = path.as_posix()
    return rel, located is not None


def check_step(
    root: Path, feature_dir: Path, step: str, recorded: dict[str, list[str]]
) -> CompletionCheck:
    """The deterministic completion check for one producing step (SRCX-FR-012..015).

    Passes iff the declared markdown exists on disk AND a matching ledger entry lists that path
    (compared as a repo-relative POSIX path). A non-producing step always passes (SRCX-FR-007)."""
    if not is_producing(step):
        return CompletionCheck(ok=True, step=step)
    rel, on_disk = declared_artifact_rel(root, feature_dir, step)
    if not on_disk:
        return CompletionCheck(ok=False, step=step, path=rel, failure_class=CLASS_ABSENT)
    if rel not in recorded.get(step, []):
        return CompletionCheck(ok=False, step=step, path=rel, failure_class=CLASS_UNRECORDED)
    return CompletionCheck(ok=True, step=step, path=rel)


def resume_entry_index(
    entries: list[dict],
    spec_id: str,
    start_index: int,
    *,
    root: Path,
    feature_dir: Optional[Path],
) -> tuple[int, Optional[CompletionCheck]]:
    """Cap a resume's re-entry index by the on-disk completion check (SRCX-FR-017).

    Applies the gate to every producing stage recorded complete before ``start_index`` (the
    ledger-derived resume index); the earliest broken stage becomes the re-entry point, so a stage
    whose artifact vanished is re-run — never skipped on the strength of its ledger entry alone.
    Stages the run never recorded are out of the gate's scope (SRCX-FR-018). Returns the (possibly
    capped) index and the failing check, when any."""
    if feature_dir is None:
        return start_index, None
    recorded = recorded_stage_artifacts(entries, spec_id)  # one ledger pass (SRCX-NFR-004)
    for i, (sid, kind, _stage) in enumerate(LIFECYCLE_STEPS[: max(0, start_index)]):
        if kind != "action" or not is_producing(sid) or sid not in recorded:
            continue
        chk = check_step(root, feature_dir, sid, recorded)
        if not chk.ok:
            return i, chk
    return start_index, None


# --------------------------------------------------------------------------- stage records (SRCX-FR-005/006)
def render_oracle_record(spec_id: str, linked: Sequence[str]) -> str:
    """The ``oracle.md`` record — links the authored oracle tests at their real repo paths (SRCX-FR-005)."""
    lines = [
        f"# Oracle record — {spec_id}",
        "",
        "Phase-A oracle tests authored from the spec's acceptance criteria. The tests live at their",
        "real repository paths (linked below) — this record neither relocates nor duplicates them.",
        "",
        "## Authored oracle tests",
        "",
    ]
    lines += [f"- {p}" for p in sorted(set(linked))] or ["- (none linked)"]
    return "\n".join(lines) + "\n"


def render_implement_record(
    spec_id: str,
    produced: Sequence[str],
    phases: Sequence[dict] | None = None,
    phase_scopes: Mapping[int, Sequence[str]] | None = None,
) -> str:
    """The single ``implement.md`` record — every phase, every change, deterministic order (SRCX-FR-006).

    ``phases`` are the per-phase results in artifact order (as collected — PHASE-FR-012); each phase
    section links the produced paths inside that phase's declared file scope. The full produced change
    set is always listed, so the record links a superset of the stage's change set (SRCX-FR-005)."""
    all_changes = sorted(set(produced))
    lines = [
        f"# Implement record — {spec_id}",
        "",
        "The implementation changes live at their real repository paths (linked below) — this record",
        "neither relocates nor duplicates them.",
        "",
    ]
    if phases:
        scopes = phase_scopes or {}
        lines += [f"## Phases ({len(phases)})", ""]
        for ph in phases:  # deterministic artifact order, as collected (SRCX-FR-006)
            idx = int(ph.get("phase", 0))
            status = (
                "completed" if ph.get("ok") else f"failed — {ph.get('detail', '')}".rstrip(" —")
            )
            lines.append(f"### Phase {idx}: {ph.get('name', '')} — {status}")
            scope = set(scopes.get(idx, ()))
            scoped = [p for p in all_changes if p in scope]
            lines += [f"- {p}" for p in scoped] or ["- (no scoped change linked)"]
            lines.append("")
    else:
        lines += ["## Session", "", "A single implement session (no phased tasks artifact).", ""]
    lines += ["## Changes", ""]
    lines += [f"- {p}" for p in all_changes] or ["- (none linked)"]
    return "\n".join(lines) + "\n"


def write_record(
    root: Path,
    feature_dir: Path,
    step: str,
    *,
    spec_id: str,
    linked: Sequence[str],
    phases: Sequence[dict] | None = None,
    phase_scopes: Mapping[int, Sequence[str]] | None = None,
) -> str:
    """Write the ``oracle.md`` / ``implement.md`` record flat into the feature folder (SRCX-FR-004/005).

    Returns the record's repo-relative POSIX path — the caller adds it to the stage's artifact paths so
    the signed ``run``/``stage`` entry records it (SRCX-FR-013) and the completion gate can hold. For a
    phased implement the caller invokes this from the collecting thread AFTER all phases complete, in
    deterministic order (SRCX-NFR-006)."""
    if step == "oracle":
        text = render_oracle_record(spec_id, linked)
    else:
        text = render_implement_record(spec_id, linked, phases=phases, phase_scopes=phase_scopes)
    target = stage_artifact_path(feature_dir, step)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()
