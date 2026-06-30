"""Prompt/constitution evaluation harness (3PWR-FR-050).

The constitution, the ``/3pwr.*`` commands, and the role config are versioned software.
This runs an eval set of content assertions over them and **fails on any regression**, so
a change that drops a non-negotiable (e.g. the oracle's different-model-family rule) is
blocked rather than silently shipped. A model-driven eval layer is a future addition; the
deterministic set is offline, fast, and self-applicable.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .verdict import STATUS_FAIL, STATUS_PASS, GateResult


def run_evals(repo_root: Path, cases_path: Path) -> GateResult:
    cases: list[dict] = []
    if cases_path.exists():
        cases = (yaml.safe_load(cases_path.read_text(encoding="utf-8")) or {}).get("cases", [])

    findings: list[str] = []
    passed = 0
    for case in cases:
        name = case.get("name", "?")
        rel = case.get("file", "")
        target = repo_root / rel
        if not target.exists():
            findings.append(f"{name}: missing file {rel}")
            continue
        text = target.read_text(encoding="utf-8").lower()  # presence checks are case-insensitive
        ok = True
        for needle in case.get("must_contain", []):
            if needle.lower() not in text:
                findings.append(f"{name}: {rel} must contain {needle!r}")
                ok = False
        for needle in case.get("must_not_contain", []):
            if needle.lower() in text:
                findings.append(f"{name}: {rel} must NOT contain {needle!r}")
                ok = False
        if ok:
            passed += 1

    status = STATUS_FAIL if findings else STATUS_PASS
    return GateResult(
        gate="eval",
        status=status,
        tool="3pwr-eval",
        details={"cases": len(cases), "passed": passed},
        findings=findings,
    )
