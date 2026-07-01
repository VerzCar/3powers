"""Spec-conformance gate — every requirement must have a linked test (3PWR-FR-030).

This is a deterministic, language-agnostic trace (3PWR-FR-028): we read the
requirement IDs declared in a spec and confirm each is referenced by at least one
test, across the unit / integration / e2e layers (3PWR-FR-064/065). A requirement
with no linked test is an actionable failure naming the requirement ID
(3PWR-FR-034). Tests reference a requirement simply by mentioning its ID — e.g.
``describe("VUTIL-FR-001: rejects empty input", ...)``.
"""

from __future__ import annotations

import re
from pathlib import Path

from .verdict import STATUS_FAIL, STATUS_PASS, GateResult, failure

# Canonical requirement ID, namespaced by spec ID (3PWR-FR-059): e.g. VUTIL-FR-001 or
# 3PWR-FR-038. The spec ID may start with a digit (the 3Powers epic id is "3PWR"). The
# number group also captures slash-runs like "038/039/040", expanded by _iter_req_ids.
_REQ_RE = re.compile(r"\b([0-9A-Z]{2,16})-(FR|NFR)-(\d{3,}(?:/\d{3,})*)\b")
_SPEC_ID_RE = re.compile(r"(?im)^\*{0,2}Spec ID\*{0,2}\s*[:=]\s*`?([0-9A-Z]{2,16})`?")


def _iter_req_ids(text: str):
    """Yield ``(spec_id, kind, num)`` for every requirement ID in ``text``, expanding
    slash-runs such as ``3PWR-FR-038/039/040`` into 038, 039, 040."""
    for sid, kind, nums in _REQ_RE.findall(text):
        for num in nums.split("/"):
            yield sid, kind, num


_LAYER_HINTS = {
    "unit": ("/unit/", ".unit.", "tests/unit"),
    "integration": ("/integration/", ".int.", ".integration.", "tests/integration"),
    "e2e": ("/e2e/", ".e2e.", "tests/e2e"),
}

_TEST_GLOBS = ("*.test.*", "*.spec.*", "test_*.py", "*_test.py")


def extract_spec(spec_path: Path) -> tuple[str, set[str]]:
    """Return ``(spec_id, {requirement_ids})`` declared in a spec file."""
    text = spec_path.read_text(encoding="utf-8")
    m = _SPEC_ID_RE.search(text)
    declared_spec = m.group(1) if m else ""
    ids: set[str] = set()
    for spec_id, kind, num in _iter_req_ids(text):
        if declared_spec and spec_id != declared_spec:
            continue
        ids.add(f"{spec_id}-{kind}-{num}")
    if not declared_spec and ids:
        # Infer the spec ID from the requirements themselves.
        declared_spec = next(iter(ids)).split("-")[0]
    return declared_spec, ids


def _layer_of(path: Path) -> str:
    p = str(path).replace("\\", "/")
    for layer, hints in _LAYER_HINTS.items():
        if any(h in p for h in hints):
            return layer
    return "unit"


def _iter_test_files(roots: list[Path]):
    for root in roots:
        if root.is_file():
            yield root
            continue
        for pattern in _TEST_GLOBS:
            yield from root.rglob(pattern)


def referenced_ids(test_roots: list[Path], spec_id: str) -> dict[str, set[str]]:
    """Map each referenced requirement ID → the set of layers that reference it."""
    refs: dict[str, set[str]] = {}
    seen: set[Path] = set()
    for f in _iter_test_files(test_roots):
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # skip binary / unreadable files
        layer = _layer_of(f)
        for sid, kind, num in _iter_req_ids(text):
            if spec_id and sid != spec_id:
                continue
            refs.setdefault(f"{sid}-{kind}-{num}", set()).add(layer)
    return refs


def run_conformance(
    spec_path: Path, test_roots: list[Path], required_layers: list[str] | None = None
) -> GateResult:
    spec_id, declared = extract_spec(spec_path)
    refs = referenced_ids(test_roots, spec_id)
    untested = sorted(declared - set(refs))
    required = list(required_layers or [])

    # Per tier, the CHANGE must exercise all required test layers (3PWR-FR-064/065). We check the
    # UNION of layers across the spec's tested requirements — a High-risk change needs unit +
    # integration + e2e tests *somewhere* for this spec, not every requirement in every layer. When
    # there are no tests at all, the untested-requirement failures already cover it (skip layers).
    covered_layers: set[str] = set()
    for layers in refs.values():
        covered_layers |= layers
    missing_layers = (
        [layer for layer in required if layer not in covered_layers] if (required and refs) else []
    )

    findings = [f"requirement {rid} has no linked test" for rid in untested]
    if missing_layers:
        findings.append(
            f"this change is missing tier-required test layer(s): {', '.join(missing_layers)} "
            "(3PWR-FR-064)"
        )
    status = STATUS_FAIL if (untested or missing_layers) else STATUS_PASS
    return GateResult(
        gate="spec_conformance",
        status=status,
        tool="3pwr-conformance",
        details={
            "spec_id": spec_id,
            "requirement_ids": sorted(declared),
            "untested_requirements": untested,
            "required_layers": required,
            "covered_layers": sorted(covered_layers),
            "missing_layers": missing_layers,
            "layers": {rid: sorted(layers) for rid, layers in sorted(refs.items())},
        },
        findings=findings,
    )


def conformance_failures(gate: GateResult) -> list[dict]:
    out = [
        failure(
            "untested_requirement",
            requirement_id=rid,
            detail="no test references this requirement ID",
        )
        for rid in gate.details.get("untested_requirements", [])
    ]
    out += [
        failure(
            "untested_layer",
            detail=f"the change lacks a '{layer}' test layer required at this tier (3PWR-FR-064)",
        )
        for layer in gate.details.get("missing_layers", [])
    ]
    return out


# A task line in tasks.md carries a task id like T001 (3PWR-FR-016).
_TASK_RE = re.compile(r"\bT\d{2,}\b")


def two_way_coverage(spec_path: Path, tasks_path: Path) -> GateResult:
    """Verify two-way requirement↔task coverage before code (3PWR-FR-015).

    Every requirement must map to ≥1 task and every task must trace to a requirement;
    a gap in either direction fails.
    """
    spec_id, declared = extract_spec(spec_path)
    text = tasks_path.read_text(encoding="utf-8")

    reqs_in_tasks: set[str] = set()
    tasks_without_req: list[str] = []
    for line in text.splitlines():
        if not _TASK_RE.search(line):
            continue
        ids = {f"{s}-{k}-{n}" for s, k, n in _iter_req_ids(line) if (not spec_id or s == spec_id)}
        if ids:
            reqs_in_tasks |= ids
        else:
            tasks_without_req.append(line.strip()[:80])

    reqs_without_task = sorted(declared - reqs_in_tasks)
    findings = [f"requirement {r} has no task" for r in reqs_without_task]
    findings += [f"task has no requirement id: {t}" for t in tasks_without_req]
    status = STATUS_FAIL if findings else STATUS_PASS
    return GateResult(
        gate="coverage_map",
        status=status,
        tool="3pwr-coverage-map",
        details={
            "spec_id": spec_id,
            "requirements_without_task": reqs_without_task,
            "tasks_without_requirement": tasks_without_req,
        },
        findings=findings,
    )
