"""Spec-conformance gate — every requirement must have a linked test (3PWR-FR-030).

This is a deterministic, language-agnostic trace (3PWR-FR-028): we read the
requirement IDs declared in a spec and confirm each is referenced by at least one
test, across the unit / integration / e2e layers (3PWR-FR-064/065). A requirement
with no linked test is an actionable failure naming the requirement ID
(3PWR-FR-034).

Anti-gaming (HARDN-FR-008/009): a requirement counts as *traced* only when its ID is
bound to a test **declaration** — the test's name/title line or its adjacent docstring —
not merely mentioned in a comment; and every requirement-bound test must contain at
least one assertion, with the declaration and assertion patterns supplied per language
adapter. An adapter that declares no patterns degrades to a visible quarantine, never a
failure or a silent pass (3PWR-NFR-015, HARDN-NFR-003). One read per file — the binding
and assertion checks ride the same scan pass (HARDN-NFR-002).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

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


# ------------------------------------------------------------- declaration binding (HARDN-FR-008/009)
_DOCSTRING_OPEN_RE = re.compile(r"^[rbuRBU]{0,2}(\"\"\"|''')")
_TITLE_QUOTE = ('"', "'", "`")


@dataclass
class FileTrace:
    """What one scan pass over the test files found (one read per file, HARDN-NFR-002)."""

    mentioned: dict[str, set[str]] = field(default_factory=dict)  # rid → layers (any mention)
    bound: dict[str, set[str]] = field(default_factory=dict)  # rid → layers (declaration-bound)
    weak: list[tuple[str, str]] = field(default_factory=list)  # (rid, file) assertion-free


def _compile_patterns(patterns: list[str]) -> tuple[list[re.Pattern[str]], list[str]]:
    compiled: list[re.Pattern[str]] = []
    bad: list[str] = []
    for p in patterns:
        try:
            compiled.append(re.compile(p))
        except re.error:
            bad.append(p)
    return compiled, bad


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip())


def _binding_end(lines: list[str], start: int, end: int) -> int:
    """The exclusive end of a declaration's *binding region* (HARDN-FR-008).

    The region is the declaration line itself plus, when the next non-blank line opens a
    docstring (Python idiom) or is a bare title string (a wrapped ``describe(``/``it(``
    argument), that adjacent title text — a test's *name*. Body comments never bind.
    """
    k = start + 1
    while k < end and not lines[k].strip():
        k += 1
    if k >= end:
        return start + 1
    stripped = lines[k].strip()
    m = _DOCSTRING_OPEN_RE.match(stripped)
    if m:
        quote = m.group(1)
        if quote in stripped[m.end() :]:
            return k + 1  # one-line docstring
        k2 = k + 1
        while k2 < end and quote not in lines[k2]:
            k2 += 1
        return min(k2 + 1, end)
    if stripped.startswith(_TITLE_QUOTE):
        return k + 1  # a wrapped declaration title string
    return start + 1


def _scan_blocks(
    text: str,
    spec_id: str,
    decl_res: list[re.Pattern[str]],
    assert_res: list[re.Pattern[str]],
) -> tuple[dict[str, bool], set[str]]:
    """Parse one test file into declaration blocks (HARDN-FR-008/009).

    A block runs from a declaration line to the next declaration at the same or lower
    indentation — so a ``describe(`` binding spans its nested ``it(`` bodies. Returns
    ``({bound_rid: all_binding_blocks_have_an_assertion}, {mentioned_rids})``. With no
    assertion patterns supplied, assertions are not judged (the caller quarantines).
    """
    mentioned = {f"{s}-{k}-{n}" for s, k, n in _iter_req_ids(text) if not spec_id or s == spec_id}
    lines = text.splitlines()
    decls = [
        (i, _indent_of(line))
        for i, line in enumerate(lines)
        if any(r.search(line) for r in decl_res)
    ]
    bound: dict[str, bool] = {}
    for n, (start, indent) in enumerate(decls):
        end = len(lines)
        for j, j_indent in decls[n + 1 :]:
            if j_indent <= indent:
                end = j
                break
        bind_text = "\n".join(lines[start : _binding_end(lines, start, end)])
        ids = {
            f"{s}-{k}-{num}"
            for s, k, num in _iter_req_ids(bind_text)
            if not spec_id or s == spec_id
        }
        if not ids:
            continue
        body = "\n".join(lines[start:end])
        has_assertion = any(r.search(body) for r in assert_res) if assert_res else True
        for rid in ids:
            bound[rid] = bound.get(rid, True) and has_assertion
    return bound, mentioned


def scan_trace(
    test_roots: list[Path],
    spec_id: str,
    decl_res: list[re.Pattern[str]],
    assert_res: list[re.Pattern[str]],
) -> FileTrace:
    """One pass over the test files: mentions, declaration-bound IDs, and weak tests."""
    trace = FileTrace()
    seen: set[Path] = set()
    for f in _iter_test_files(test_roots):
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        layer = _layer_of(f)
        bound, mentioned = _scan_blocks(text, spec_id, decl_res, assert_res)
        for rid in mentioned:
            trace.mentioned.setdefault(rid, set()).add(layer)
        for rid, ok in bound.items():
            trace.bound.setdefault(rid, set()).add(layer)
            if not ok:
                trace.weak.append((rid, str(f)))
    trace.weak.sort()
    return trace


def run_conformance(
    spec_path: Path,
    test_roots: list[Path],
    required_layers: list[str] | None = None,
    conformance_cfg: Optional[dict[str, Any]] = None,
) -> GateResult:
    spec_id, declared = extract_spec(spec_path)
    cfg = conformance_cfg or {}
    decl_res, bad_decl = _compile_patterns(list(cfg.get("test_declarations") or []))
    assert_res, bad_assert = _compile_patterns(list(cfg.get("assertion_patterns") or []))
    quarantined: list[str] = []
    for bad in bad_decl + bad_assert:
        quarantined.append(f"quarantined: invalid conformance pattern {bad!r} — ignored")

    untraced: list[str] = []
    weak: list[tuple[str, str]] = []
    if decl_res:
        # Anti-gaming path (HARDN-FR-008/009): only declaration-bound IDs trace; a comment
        # mention alone is an *untraced* requirement, and every binding block needs ≥1 assertion.
        trace = scan_trace(test_roots, spec_id, decl_res, assert_res)
        refs = trace.bound
        untraced = sorted((declared & set(trace.mentioned)) - set(trace.bound))
        untested = sorted(declared - set(trace.mentioned))
        if assert_res:
            weak = [(rid, f) for rid, f in trace.weak if rid in declared]
        else:
            quarantined.append(
                "quarantined: adapter declares no assertion patterns — the weak-test check "
                "is not enforced (3PWR-NFR-015)"
            )
    else:
        # No declaration patterns (legacy adapter): mention-based tracing, visibly quarantined —
        # degraded, never silently strict or silently passing (HARDN-NFR-003).
        refs = referenced_ids(test_roots, spec_id)
        untested = sorted(declared - set(refs))
        quarantined.append(
            "quarantined: adapter declares no test-declaration patterns — requirement-ID "
            "binding is not enforced (3PWR-NFR-015)"
        )
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
    findings += [
        f"requirement {rid} is mentioned but not bound to any test declaration — "
        "a comment does not trace it (HARDN-FR-008)"
        for rid in untraced
    ]
    findings += [
        f"requirement {rid} is bound to an assertion-free test in {f} (HARDN-FR-009)"
        for rid, f in weak
    ]
    if missing_layers:
        findings.append(
            f"this change is missing tier-required test layer(s): {', '.join(missing_layers)}"
        )
    findings += quarantined
    status = STATUS_FAIL if (untested or untraced or weak or missing_layers) else STATUS_PASS
    return GateResult(
        gate="spec_conformance",
        status=status,
        tool="3pwr-conformance",
        details={
            "spec_id": spec_id,
            "requirement_ids": sorted(declared),
            "untested_requirements": untested,
            "untraced_requirements": untraced,
            "weak_tests": [[rid, f] for rid, f in weak],
            "quarantined": quarantined,
            "required_layers": required,
            "covered_layers": sorted(covered_layers),
            "missing_layers": missing_layers,
            "layers": {rid: sorted(layers) for rid, layers in sorted(refs.items())},
        },
        findings=findings,
    )


# A regression test names itself: a *regression* / *reproduce* file or body marker (3PWR-FR-008).
_REGRESSION_RE = re.compile(r"(?i)regress|reproduc")


def has_regression_test(test_roots: list[Path], spec_id: str) -> tuple[bool, list[str]]:
    """Detect a failing-regression test guarding a defect fix (3PWR-FR-008), deterministically.

    A regression test is one that is *marked* as such — by file name (``*regression*`` /
    ``*reproduce*``) or an inline mention — **and** references a requirement id of this spec, so it
    is traceable to the defect it guards (mirrors the conformance trace; no model call, 3PWR-NFR-001).
    Returns ``(present, [requirement ids the regression tests reference])``.
    """
    hits: set[str] = set()
    seen: set[Path] = set()
    for f in _iter_test_files(test_roots):
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not (_REGRESSION_RE.search(f.name) or _REGRESSION_RE.search(text)):
            continue
        for sid, kind, num in _iter_req_ids(text):
            if spec_id and sid != spec_id:
                continue
            hits.add(f"{sid}-{kind}-{num}")
    return (bool(hits), sorted(hits))


def regression_gate(spec_path: Path, test_roots: list[Path]) -> GateResult:
    """The defect-flow gate (3PWR-FR-008): a defect fix must ship a failing regression test."""
    spec_id, _ = extract_spec(spec_path)
    present, refs = has_regression_test(test_roots, spec_id)
    findings = (
        []
        if present
        else [
            "defect fix has no regression test: add a test named *regression*/*reproduce* that "
            f"references a {spec_id or 'spec'} requirement id and fails before the fix"
        ]
    )
    return GateResult(
        gate="defect_regression",
        status=STATUS_PASS if present else STATUS_FAIL,
        tool="3pwr-conformance",
        details={"regression_refs": refs},
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
            "untraced_requirement",
            requirement_id=rid,
            detail="the ID appears only outside a test declaration — bind it to a test "
            "name/declaration line (HARDN-FR-008)",
        )
        for rid in gate.details.get("untraced_requirements", [])
    ]
    out += [
        failure(
            "weak_test",
            requirement_id=rid,
            file=f,
            detail="requirement-bound test contains no assertion (HARDN-FR-009)",
        )
        for rid, f in gate.details.get("weak_tests", [])
    ]
    out += [
        failure(
            "untested_layer",
            detail=f"the change lacks a '{layer}' test layer required at this tier",
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
