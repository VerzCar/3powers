"""The deterministic stage-completion gate + the oracle/implement records.

Two run-workspace concerns live here, both pure given injected inputs:

* **Stage records**: the two producing stages whose real outputs live elsewhere in
  the repository — ``oracle`` (authored test files) and ``implement`` (code changes) — each leave a
  short markdown *record* in the run's feature folder that links those outputs at their real paths.
  The record never relocates or duplicates them; a multi-phase implement yields exactly one
  ``changelog.md`` enumerating every phase in deterministic artifact order (the legacy record name
  ``implement.md`` stays read-resolvable; the top-level project ``CHANGELOG.md`` is hand-maintained
  and never touched by a run).

* **The completion gate**: a producing stage is *done* only when BOTH its declared
  markdown artifact exists on disk in the feature folder AND a matching signed ``run``/``stage`` (or
  ``checkpoint``) ledger entry records that path. Either condition missing blocks the run with a named,
  classified failure — ``artifact_absent`` (recorded but gone from disk) or ``artifact_unrecorded``
  (on disk but in no ledger entry) — and the stage must be re-run. The same gate governs ``--resume``:
  a resume re-enters at the earliest recorded producing stage whose artifact is broken,
  never skipping a stage on the strength of a ledger entry alone.

The gate's outcome is a pure function of (feature-folder disk state, ledger entries, step) — no model
call, no network. The ledger entries are read once by the caller and injected; nothing here appends
to or signs the ledger — no new entry type, no signing change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

from .orchestrate import LIFECYCLE_STEPS
from .workspace import PRODUCING_STEPS, find_artifact, stage_artifact_path

# The two named completion-gate failure classes — new VALUES folding through the
# existing run/failure handling; distinct from dispatch-time ``artifact_missing``.
CLASS_ABSENT = "artifact_absent"
CLASS_UNRECORDED = "artifact_unrecorded"

# The producing steps whose feature-folder markdown is an engine-written *record*.
RECORD_STEPS: tuple[str, ...] = ("oracle", "implement")


@dataclass(frozen=True)
class CompletionCheck:
    """One stage's completion-gate verdict — pure given its inputs."""

    ok: bool
    step: str
    path: str = ""  # the declared repo-relative POSIX artifact path
    failure_class: str = ""  # CLASS_ABSENT | CLASS_UNRECORDED | ""

    @property
    def message(self) -> str:
        """The actionable failure line naming the stage and the artifact."""
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
    """Whether ``step`` is gated at all: only the producing steps carry the gate."""
    return step in PRODUCING_STEPS


def recorded_stage_artifacts(entries: list[dict], spec_id: str) -> dict[str, list[str]]:
    """The artifact paths recorded per completed step — one pass over the ledger.

    A matching record is a ``run`` entry of kind ``stage`` or ``checkpoint`` for ``spec_id``;
    its ``artifacts`` list accumulates per step (a re-run's fresh entry adds to the
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
    """The declared artifact's repo-relative POSIX path and whether it exists on disk.

    The flat location wins; the legacy split location is the read fallback for legacy features —
    so an already-written split artifact is checked *at its split path* while a new
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
    """The deterministic completion check for one producing step.

    Passes iff the declared markdown exists on disk AND a matching ledger entry lists that path
    (compared as a repo-relative POSIX path). A non-producing step always passes."""
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
    """Cap a resume's re-entry index by the on-disk completion check.

    Applies the gate to every producing stage recorded complete before ``start_index`` (the
    ledger-derived resume index); the earliest broken stage becomes the re-entry point, so a stage
    whose artifact vanished is re-run — never skipped on the strength of its ledger entry alone.
    Stages the run never recorded are out of the gate's scope. Returns the (possibly
    capped) index and the failing check, when any."""
    if feature_dir is None:
        return start_index, None
    recorded = recorded_stage_artifacts(entries, spec_id)  # one ledger pass
    for i, (sid, kind, _stage) in enumerate(LIFECYCLE_STEPS[: max(0, start_index)]):
        if kind != "action" or not is_producing(sid) or sid not in recorded:
            continue
        chk = check_step(root, feature_dir, sid, recorded)
        if not chk.ok:
            return i, chk
    return start_index, None


# --------------------------------------------------------------------------- stage records
def render_oracle_record(spec_id: str, linked: Sequence[str]) -> str:
    """The ``oracle.md`` record — links the authored oracle tests at their real repo paths."""
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


def _changelog_section(work_kinds: Sequence[str]) -> str:
    """The Keep-a-Changelog section heading the run's inferred work kind(s) map to.

    ``defect`` → ``Fixed`` (a bug fix outranks anything it rode in with), ``feature`` → ``Added``,
    anything else (design, refactor, docs, chore, unknown) → ``Changed``. Deterministic."""
    kinds = set(work_kinds)
    if "defect" in kinds:
        return "Fixed"
    if "feature" in kinds:
        return "Added"
    return "Changed"


def _requirement_rows(
    requirement_ids: Sequence[str], files: Sequence[str], summary: str
) -> list[str]:
    """The machine-parseable table rows for one phase: one row per requirement id.

    Each row carries the requirement id, the phase's changed files, and the one-line what/why.
    A phase tracing to no id gets a single ``(untraced)`` row so the gap stays visible."""
    listed = ", ".join(files) if files else "(no scoped change linked)"
    ids = list(requirement_ids) or ["(untraced)"]
    return [f"| {rid} | {listed} | {summary} |" for rid in ids]


def render_changelog(
    spec_id: str,
    produced: Sequence[str],
    phases: Sequence[dict] | None = None,
    phase_scopes: Mapping[int, Sequence[str]] | None = None,
    *,
    phase_requirements: Mapping[int, Sequence[str]] | None = None,
    work_kinds: Sequence[str] = (),
    report: str = "",
) -> str:
    """The single engine-generated ``changelog.md`` record — grouped by phase, requirement-traced.

    Keep-a-Changelog flavored: the run's changes land under one ``Added``/``Changed``/``Fixed``
    section chosen by the inferred work kind(s). Inside it, one subsection per phase (deterministic
    artifact order, as collected) carries a machine-parseable table — a ``Requirement`` id column,
    the phase's changed files, and a one-line what/why. The changed files live at their real
    repository paths; nothing is relocated or duplicated, and the top-level project ``CHANGELOG.md``
    is never touched. ``report`` — the implement agent's completion report — is folded in verbatim
    when present. Byte-deterministic: identical inputs always render identical bytes."""
    all_changes = sorted(set(produced))
    section = _changelog_section(work_kinds)
    reqs = phase_requirements or {}
    lines = [
        f"# Changelog — {spec_id}",
        "",
        "Engine-generated record of the Implement stage's changes, grouped by phase. Each entry",
        "traces to a requirement id; the changed files live at their real repository paths — this",
        "record neither relocates nor duplicates them. The project's top-level CHANGELOG.md is",
        "hand-maintained and untouched by runs.",
        "",
        f"## {section}",
        "",
    ]
    header = ["| Requirement | Files changed | Summary |", "|---|---|---|"]
    if phases:
        scopes = phase_scopes or {}
        for ph in phases:  # deterministic artifact order, as collected
            idx = int(ph.get("phase", 0))
            status = (
                "completed" if ph.get("ok") else f"failed — {ph.get('detail', '')}".rstrip(" —")
            )
            name = str(ph.get("name", ""))
            lines.append(f"### Phase {idx}: {name} — {status}")
            lines.append("")
            scope = set(scopes.get(idx, ()))
            scoped = [p for p in all_changes if p in scope]
            summary = f"Phase {idx} ({name}) {status}"
            lines += header
            lines += _requirement_rows(list(reqs.get(idx, ())), scoped, summary)
            lines.append("")
    else:
        lines += [
            "### Session",
            "",
            "A single implement session (no phased implementation plan).",
            "",
        ]
        lines += header
        lines += _requirement_rows(list(reqs.get(0, ())), all_changes, "single implement session")
        lines.append("")
    lines += ["## All changes", ""]
    lines += [f"- {p}" for p in all_changes] or ["- (none linked)"]
    if report.strip():
        lines += ["", "## Implement agent report", "", report.strip()]
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
    phase_requirements: Mapping[int, Sequence[str]] | None = None,
    work_kinds: Sequence[str] = (),
    report: str = "",
) -> str:
    """Write the ``oracle.md`` / ``changelog.md`` record flat into the feature folder.

    Returns the record's repo-relative POSIX path — the caller adds it to the stage's artifact paths
    so the signed ``run``/``stage`` entry records it and the completion gate can hold. For a
    phased implement the caller invokes this from the collecting thread AFTER all phases complete,
    in deterministic order. The implement record's legacy name (``implement.md``) is never written;
    it stays read-resolvable through :func:`threepowers.workspace.find_artifact`."""
    if step == "oracle":
        text = render_oracle_record(spec_id, linked)
    else:
        text = render_changelog(
            spec_id,
            linked,
            phases=phases,
            phase_scopes=phase_scopes,
            phase_requirements=phase_requirements,
            work_kinds=work_kinds,
            report=report,
        )
    target = stage_artifact_path(feature_dir, step)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()
