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

# Canonical requirement ID, namespaced by spec ID (3PWR-FR-059): e.g. VUTIL-FR-001.
_REQ_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,15})-(FR|NFR)-(\d{3,})\b")
_SPEC_ID_RE = re.compile(r"(?im)^\*{0,2}Spec ID\*{0,2}\s*[:=]\s*`?([A-Z][A-Z0-9]{1,15})`?")

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
    for spec_id, kind, num in _REQ_RE.findall(text):
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
        except OSError:
            continue
        layer = _layer_of(f)
        for sid, kind, num in _REQ_RE.findall(text):
            if spec_id and sid != spec_id:
                continue
            refs.setdefault(f"{sid}-{kind}-{num}", set()).add(layer)
    return refs


def run_conformance(spec_path: Path, test_roots: list[Path]) -> GateResult:
    spec_id, declared = extract_spec(spec_path)
    refs = referenced_ids(test_roots, spec_id)
    untested = sorted(declared - set(refs))

    findings = [f"requirement {rid} has no linked test" for rid in untested]
    status = STATUS_FAIL if untested else STATUS_PASS
    return GateResult(
        gate="spec_conformance",
        status=status,
        tool="3pwr-conformance",
        details={
            "spec_id": spec_id,
            "requirement_ids": sorted(declared),
            "untested_requirements": untested,
            "layers": {rid: sorted(layers) for rid, layers in sorted(refs.items())},
        },
        findings=findings,
    )


def conformance_failures(gate: GateResult) -> list[dict]:
    return [
        failure("untested_requirement", requirement_id=rid,
                detail="no test references this requirement ID")
        for rid in gate.details.get("untested_requirements", [])
    ]
