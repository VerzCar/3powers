"""Mutation gate — measure the suite's power to catch injected faults (3PWR-FR-031).

Mutation testing is the High-risk oracle's teeth (spec §8): a surviving mutant is an
actionable **missing assertion** (3PWR-FR-034), and the score is checked against the
tier threshold read from the single risk-tier table (3PWR-FR-032). The mutation tool
is **adapter-declared** (3PWR-NFR-007) — the core only interprets a *normalized*
score, so the verdict shape is identical across languages (3PWR-FR-033). The run is
scoped to changed/high-risk files per invocation (3PWR-FR-031); the full sweep is a
scheduled concern (3PWR-NFR-002).

When the mutation tool is unavailable the gate is **quarantined** — surfaced as a
skip with a finding, never silently passed (3PWR-NFR-015).
"""

from __future__ import annotations

import json
import shlex
from pathlib import Path
from typing import Any

from .adapters import CmdResult, command_of, run_cmd
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult

# mutmut/Stryker statuses that count as "the suite caught it".
_KILLED = {"killed", "timeout"}
# ...and as "a fault slipped through" (a missing assertion).
_SURVIVED = {"survived", "suspicious", "no coverage", "nocoverage"}


def _quarantine(reason: str, tool: str) -> GateResult:
    return GateResult(
        gate="mutation",
        status=STATUS_SKIP,
        tool=tool,
        findings=[f"quarantined: {reason} — gate not enforced"],
    )


def _mutmut_filters(paths: list[str] | None) -> list[str]:
    """Translate target-relative file paths into mutmut mutant-name globs.

    A mutmut mutant key looks like ``threepowers.canonical.x_func__mutmut_1``; a glob
    of ``*.<stem>.*`` selects every mutant of that module, scoping the run to the
    requested high-risk files (3PWR-FR-031).
    """
    return [f"*.{Path(p).stem}.*" for p in (paths or [])]


def _parse_mutmut_results(text: str) -> tuple[int, int, list[str]]:
    """Return ``(killed, survived, surviving_names)`` from ``mutmut results`` output."""
    killed = survived = 0
    survivors: list[str] = []
    for raw in text.splitlines():
        name, sep, status = raw.rpartition(":")
        if not sep:
            continue
        status = status.strip().lower()
        name = name.strip()
        if status in _KILLED:
            killed += 1
        elif status in _SURVIVED:
            survived += 1
            survivors.append(name)
    return killed, survived, survivors


def _parse_stryker_report(report_path: Path) -> tuple[int, int, list[str]] | None:
    """Return ``(killed, survived, surviving_locations)`` from a Stryker JSON report."""
    if not report_path.exists():
        return None
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    killed = survived = 0
    survivors: list[str] = []
    for fpath, finfo in (data.get("files") or {}).items():
        for m in finfo.get("mutants", []):
            status = str(m.get("status", "")).strip().lower()
            if status in _KILLED:
                killed += 1
            elif status in _SURVIVED:
                survived += 1
                line = (m.get("location", {}).get("start", {}) or {}).get("line", "?")
                survivors.append(f"{fpath}:{line}")
    return killed, survived, survivors


def mutation_gate(
    target: Path,
    spec: dict[str, Any],
    *,
    threshold: float,
    paths: list[str] | None = None,
) -> GateResult:
    """Run the adapter's mutation tool and grade its score against ``threshold``."""
    parser = str(spec.get("parser") or "").lower()
    cmd = command_of(spec)
    if not cmd:
        return _quarantine("adapter declares no mutation command", parser or "mutation")

    run_res: CmdResult
    if parser == "mutmut":
        run_command = cmd
        for f in _mutmut_filters(paths):
            run_command += " " + shlex.quote(f)
        run_res = run_cmd(run_command, cwd=target)
        if run_res.returncode == 127:
            return _quarantine("mutation tool not found", "mutmut")
        # `--all true` is required: the default `results` omits killed mutants, which
        # would make the score read 0%. We need every status to compute killed/total.
        score_cmd = str(spec.get("score_cmd") or "uv run mutmut results --all true")
        results = run_cmd(score_cmd, cwd=target)
        killed, survived, survivors = _parse_mutmut_results(results.stdout)
        tool = "mutmut"
    elif parser == "stryker":
        run_res = run_cmd(cmd, cwd=target)
        if run_res.returncode == 127:
            return _quarantine("mutation tool not found", "stryker")
        report = target / str(spec.get("report_path") or "reports/mutation/mutation.json")
        parsed = _parse_stryker_report(report)
        if parsed is None:
            return _quarantine(f"no mutation report at {report}", "stryker")
        killed, survived, survivors = parsed
        tool = "stryker"
    else:
        return _quarantine(f"unknown mutation parser {parser!r}", parser or "mutation")

    total = killed + survived
    if total == 0:
        return _quarantine("no mutants were generated", tool)
    score = round(100.0 * killed / total, 2)
    status = STATUS_PASS if score >= threshold else STATUS_FAIL
    findings: list[str] = []
    if status == STATUS_FAIL:
        findings = [f"surviving mutant (missing assertion): {n}" for n in survivors[:15]]
    return GateResult(
        gate="mutation",
        status=status,
        tool=tool,
        duration_ms=run_res.duration_ms,
        details={
            "mutation_score": score,
            "threshold": threshold,
            "killed": killed,
            "survived": survived,
            "total": total,
        },
        findings=findings,
    )
