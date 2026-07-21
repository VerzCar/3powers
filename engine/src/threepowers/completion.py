"""The deterministic stage-completion gate + the oracle/implement records.

Two run-workspace concerns live here, both pure given injected inputs:

* **Stage records**: the two producing stages whose real outputs live elsewhere in
  the repository — ``oracle`` (the authored Tests Specification + test files) and ``implement``
  (code changes) — each leave a markdown record in the run's feature folder. Both follow the same
  author-then-validate-then-place shape. The implement record is the **agent-authored**
  ``changelog.md``: the implement agent writes a business-readable account of what the run changed
  and why it matters (grouped Added/Changed/Fixed, traced to requirement ids), and the engine
  *validates* it — every requirement the run addressed is covered, no foreign/internal requirement
  id leaks, and the Added/Changed/Fixed structure is present — then places it as the changelog's
  prose body, appending a clearly-separated, additive machine-readable requirement→files trace so
  nothing that consumed the old table loses data. A validation miss fails the step
  (:class:`ChangelogValidationError`) — a bad changelog is never silently emitted (the legacy record
  name ``implement.md`` stays read-resolvable; the top-level project ``CHANGELOG.md`` is
  hand-maintained and never touched by a run). The oracle record is the **implementation-agnostic**
  ``oracle.md`` Tests Specification: when the oracle agent authored it, the engine *validates* it
  (every spec requirement id named; no leaked file path or test framework token) and leaves it in
  place; when it is absent, the engine writes a structural stub from the spec's acceptance criteria
  with every section marked "not authored" so the gap stays visible. ``oracle.md`` itself stays
  path-free — the machine record of the actual oracle test paths lives in the signed ledger entries
  (the run/stage artifacts and the ``oracle record`` ``test_paths``), never in the document.

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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Optional, Sequence

from .conformance import _iter_req_ids, requirement_namespaces
from .oracle import extract_criteria
from .orchestrate import LIFECYCLE_STEPS
from .workspace import PRODUCING_STEPS, find_artifact, stage_artifact_path

# The two named completion-gate failure classes — new VALUES folding through the
# existing run/failure handling; distinct from dispatch-time ``artifact_missing``.
CLASS_ABSENT = "artifact_absent"
CLASS_UNRECORDED = "artifact_unrecorded"
# The implement stage's business changelog failed validation (missing requirement coverage, a
# leaked foreign requirement id, or no Added/Changed/Fixed section). The step fails with this
# class rather than silently emitting a bad changelog — distinct from the completion-gate classes.
CLASS_CHANGELOG_INVALID = "changelog_invalid"

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
# The sentinel line marking an engine-written oracle.md stub. Its presence means "not authored":
# a re-run regenerates the stub; its absence means the oracle agent authored the document, which
# is validated and left in place, never overwritten.
ORACLE_STUB_MARKER = "> Engine-generated structural stub"

# The Tests Specification must stay implementation-agnostic: a leaked repository path or a named
# test framework means the author bound the law to one implementation. Heuristics, surfaced as
# advisory findings — never a gate.
_ORACLE_PATH_PREFIX_RE = re.compile(
    r"(?:^|[\s`\"'(\[])"
    r"((?:\./|\.\./|src/|tests?/|lib/|app/|pkg/|cmd/|internal/|specs(?:-src)?/|oracle-tests/)"
    r"[\w./-]*)"
)
_ORACLE_FILE_EXT_RE = re.compile(
    r"(?:^|[\s`\"'(\[])"
    r"([\w./-]*[\w-]\.(?:py|ts|tsx|js|jsx|mjs|cjs|go|rs|java|rb|kt|swift|php|c|cc|cpp|h|hpp"
    r"|cs|sql|sh|ya?ml|toml|ini|cfg|lock))\b"
)
_ORACLE_FRAMEWORK_TOKENS = (
    "pytest",
    "unittest",
    "hypothesis",
    "jest",
    "vitest",
    "mocha",
    "jasmine",
    "cypress",
    "playwright",
    "selenium",
    "junit",
    "testng",
    "rspec",
    "minitest",
    "xunit",
    "nunit",
    "testify",
)


def validate_oracle_spec(text: str, requirement_ids: Sequence[str]) -> list[str]:
    """Validate an agent-authored ``oracle.md`` Tests Specification — pure, deterministic.

    Two checks: coverage — the document names every requirement id declared by the spec — and
    implementation-agnosticism — no leaked file path (a slashed repository path or a source-file
    name) and no named test framework appears anywhere in the document. Returns the sorted,
    actionable findings; an empty list means the document holds as law. The findings are advisory
    surface for review, never a verdict input."""
    findings = [
        f"oracle.md does not name requirement {rid}"
        for rid in sorted(set(requirement_ids))
        if rid not in text
    ]
    leaked: set[str] = set()
    for rx in (_ORACLE_PATH_PREFIX_RE, _ORACLE_FILE_EXT_RE):
        leaked.update(m.group(1) for m in rx.finditer(text))
    findings += [f"oracle.md leaks a file path: {tok}" for tok in sorted(leaked)]
    lower = text.lower()
    findings += [
        f"oracle.md names a test framework: {tok}"
        for tok in _ORACLE_FRAMEWORK_TOKENS
        if re.search(rf"\b{re.escape(tok)}\b", lower)
    ]
    return findings


def render_oracle_stub(key: str, criteria: Mapping[str, str]) -> str:
    """The structural ``oracle.md`` stub when the oracle agent authored none — byte-deterministic.

    One section per spec requirement id, carrying the criterion line from the sealed law and
    marked "not authored", so every gap is visible — never silently passed. ``key`` is the run's
    storage key (the ``<NNN>-<slug>`` feature-folder id). Path-free by construction: the machine
    record of the actual oracle test paths lives in the signed ledger entries."""
    lines = [
        f"# Tests Specification — {key}",
        "",
        ORACLE_STUB_MARKER + " — the oracle agent authored no Tests Specification for this run.",
        "> Derived from the approved spec's acceptance criteria only. Each section below is marked",
        '> "not authored" so the gap stays visible until the judiciary authors it.',
        "",
        "## Coverage Summary",
        "",
        f"- Requirements in spec: {len(criteria)}",
        "- Authored here: 0 (structural stub)",
        "",
        "## Acceptance Tests",
        "",
    ]
    for rid in sorted(criteria):
        lines += [
            f"### Test for {rid} — not authored",
            "",
            f"- **Source AC:** {criteria[rid]}",
            "- **Criterion (Given / When / Then):** not authored",
            "",
        ]
    if not criteria:
        lines += ["(the spec declares no requirement ids)", ""]
    return "\n".join(lines) + "\n"


def _spec_criteria(feature_dir: Path) -> dict[str, str]:
    """The feature spec's ``requirement_id → acceptance-criterion line`` map, or ``{}``.

    Read-tolerant: a feature without a resolvable spec, or an unreadable one, yields an empty
    map — the oracle record then degrades to an empty stub rather than failing the stage."""
    spec = find_artifact(feature_dir, "specify")
    if spec is None:
        return {}
    try:
        return extract_criteria(spec)[1]
    except (OSError, UnicodeDecodeError):
        return {}


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


# The three Keep-a-Changelog sections a business changelog groups its entries under. The validator
# requires at least one to head an entry so the record reads as a changelog, not a raw report.
_CHANGELOG_SECTIONS: tuple[str, ...] = ("Added", "Changed", "Fixed")


class ChangelogValidationError(ValueError):
    """Raised when the implement agent's authored business changelog fails validation.

    Carries the sorted, actionable ``findings`` — a missing requirement coverage entry, a leaked
    foreign/internal requirement id, or a missing Added/Changed/Fixed section. The run turns these
    into a named stage failure (:data:`CLASS_CHANGELOG_INVALID`) so a bad changelog is never
    silently emitted."""

    def __init__(self, findings: Sequence[str]) -> None:
        self.findings: list[str] = list(findings)
        super().__init__("; ".join(self.findings))


def validate_changelog(text: str, requirement_ids: Sequence[str]) -> list[str]:
    """Validate an implement-agent-authored business changelog — pure, deterministic.

    Mirrors :func:`validate_oracle_spec`'s author-then-validate shape with three checks:

    * **coverage** — the prose names every requirement id the run addressed;
    * **OSS-readiness** — no requirement id from a *foreign* namespace leaks (an internal 3Powers
      id, or any id whose namespace is not one this run's requirements use); the changelog traces
      only to this spec's own requirements;
    * **structure** — at least one Keep-a-Changelog section (Added/Changed/Fixed) heads an entry,
      so the record reads as a business changelog rather than a raw report.

    Returns the sorted, actionable findings; an empty list means the changelog holds. Unlike the
    advisory oracle findings, the caller treats a non-empty result as a hard step failure."""
    findings = [
        f"changelog.md does not name requirement {rid}"
        for rid in sorted(set(requirement_ids))
        if rid not in text
    ]
    allowed = requirement_namespaces(set(requirement_ids))
    leaked = sorted(
        {f"{sid}-{kind}-{num}" for sid, kind, num in _iter_req_ids(text) if sid not in allowed}
    )
    findings += [f"changelog.md leaks a foreign requirement id: {tok}" for tok in leaked]
    if not any(re.search(rf"(?im)^#{{1,6}}\s+{sec}\b", text) for sec in _CHANGELOG_SECTIONS):
        findings.append(
            "changelog.md has no Added/Changed/Fixed section — the business changelog is required"
        )
    return sorted(findings)


def _requirement_rows(
    requirement_ids: Sequence[str], files: Sequence[str], summary: str
) -> list[str]:
    """The machine-parseable trace rows for one phase: one row per requirement id.

    Each row carries the requirement id, the phase's changed files, and the phase label.
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
    """Assemble the run's ``changelog.md`` — an agent-authored prose body + a machine-trace appendix.

    The **body** is the implement agent's authored business changelog (``report``): plain-language
    Added/Changed/Fixed entries a non-engineer can read, each tracing to a requirement id. The
    engine neither writes nor rewrites that prose — it validates it (see :func:`validate_changelog`)
    and places it here. A clearly-separated, **additive** machine-readable appendix carries the
    deterministic requirement→files trace (one row per requirement id, grouped by phase in
    deterministic artifact order) so nothing that consumed the old table loses data. The changed
    files live at their real repository paths; nothing is relocated or duplicated, and the project's
    top-level ``CHANGELOG.md`` is hand-maintained and untouched. When no prose was authored the body
    degrades to a visible "not authored" note under the work-kind's section. Byte-deterministic:
    identical inputs always render identical bytes."""
    all_changes = sorted(set(produced))
    section = _changelog_section(work_kinds)
    reqs = phase_requirements or {}
    lines = [
        f"# Changelog — {spec_id}",
        "",
        "Business-readable record of what this run changed and why it matters — authored by the",
        "implement agent and validated by the engine for requirement coverage. The changed files",
        "live at their real repository paths; the project's top-level CHANGELOG.md is",
        "hand-maintained and untouched by runs.",
        "",
    ]
    body = report.strip()
    if body:
        lines += [body, ""]
    else:
        lines += [
            f"## {section}",
            "",
            "> The implement agent authored no business changelog for this run.",
            "",
        ]
    # The additive, clearly-separated machine-readable appendix — the deterministic
    # requirement→files trace that consumers of the old table still read.
    lines += [
        "<!-- machine-readable trace: requirement → files (additive appendix; the body above is the"
        " authored business changelog) -->",
        "## Requirement trace (machine-readable)",
        "",
        "| Requirement | Files changed | Phase |",
        "|---|---|---|",
    ]
    if phases:
        scopes = phase_scopes or {}
        for ph in phases:  # deterministic artifact order, as collected
            idx = int(ph.get("phase", 0))
            status = (
                "completed" if ph.get("ok") else f"failed — {ph.get('detail', '')}".rstrip(" —")
            )
            name = str(ph.get("name", ""))
            scope = set(scopes.get(idx, ()))
            scoped = [p for p in all_changes if p in scope]
            label = f"Phase {idx}: {name} — {status}"
            lines += _requirement_rows(list(reqs.get(idx, ())), scoped, label)
    else:
        lines += _requirement_rows(list(reqs.get(0, ())), all_changes, "single implement session")
    lines += ["", "## All changes", ""]
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
    phase_requirements: Mapping[int, Sequence[str]] | None = None,
    work_kinds: Sequence[str] = (),
    report: str = "",
    on_finding: Callable[[str], None] | None = None,
) -> str:
    """Write (or validate) the ``oracle.md`` / ``changelog.md`` record flat in the feature folder.

    Returns the record's repo-relative POSIX path — the caller adds it to the stage's artifact paths
    so the signed ``run``/``stage`` entry records it and the completion gate can hold. For a
    phased implement the caller invokes this from the collecting thread AFTER all phases complete,
    in deterministic order. The implement record's legacy name (``implement.md``) is never written;
    it stays read-resolvable through :func:`threepowers.workspace.find_artifact`.

    The oracle step validates rather than authors: an agent-written ``oracle.md`` (no stub marker)
    is checked against the spec's requirement ids and the path/framework leak heuristics — each
    finding goes to ``on_finding`` (advisory, never a blocker) — and the authored file is left in
    place byte-for-byte. An absent (or engine-stubbed) ``oracle.md`` is (re)written as the
    structural stub keyed by the feature-folder id. ``linked`` — the actual oracle test paths —
    is recorded by the caller's signed ledger entry only, keeping ``oracle.md`` path-free.

    The implement step likewise follows author-then-validate-then-place: ``report`` is the implement
    agent's authored business changelog prose. When the run addressed any requirement (or the agent
    authored prose), it is validated by :func:`validate_changelog` against the spec's requirement
    ids reachable from ``feature_dir``; a non-empty finding set raises
    :class:`ChangelogValidationError` so the caller fails the step rather than emit a bad changelog.
    The validated prose becomes the changelog's body, followed by the additive machine-readable
    requirement→files trace."""
    target = stage_artifact_path(feature_dir, step)
    if step == "oracle":
        criteria = _spec_criteria(feature_dir)
        existing = ""
        if target.is_file():
            try:
                existing = target.read_text(encoding="utf-8")
            except OSError:
                existing = ""
        if existing and ORACLE_STUB_MARKER not in existing:
            # Agent-authored Tests Specification: validate, flag, leave in place.
            if on_finding is not None:
                for finding in validate_oracle_spec(existing, sorted(criteria)):
                    on_finding(finding)
            try:
                return target.relative_to(root).as_posix()
            except ValueError:
                return target.as_posix()
        text = render_oracle_stub(feature_dir.name, criteria)
    else:
        # Implement: validate the agent-authored business changelog before placing it. Coverage is
        # judged against the spec's requirement ids (extract_criteria, reachable from feature_dir),
        # mirroring the oracle branch. A miss is a hard step failure, not an advisory note.
        requirement_ids = sorted(_spec_criteria(feature_dir))
        prose = report.strip()
        if requirement_ids or prose:
            findings = validate_changelog(prose, requirement_ids)
            if on_finding is not None:
                for finding in findings:
                    on_finding(finding)
            if findings:
                raise ChangelogValidationError(findings)
        text = render_changelog(
            spec_id,
            linked,
            phases=phases,
            phase_scopes=phase_scopes,
            phase_requirements=phase_requirements,
            work_kinds=work_kinds,
            report=report,
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    try:
        return target.relative_to(root).as_posix()
    except ValueError:
        return target.as_posix()
