"""The deterministic gate engine — runs the suite cheapest-first (3PWR-FR-026).

Order: format → lint → types → tests (+ diff-coverage) → mutation → spec-conformance.
Which gates are *required* (and their thresholds) is read entirely from the
risk-tier table (3PWR-FR-032/049): a gate is never satisfied by weakening it. The
result is one normalized verdict (3PWR-FR-033) whose every failure is actionable
(3PWR-FR-034).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from . import adapters, covdiff, scanners
from .adapters import CmdResult
from .conformance import conformance_failures, extract_spec, run_conformance
from .config import Settings, tier_config
from .verdict import (
    GATE_ORDER,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIP,
    GateResult,
    Verdict,
    failure,
)

# Gates executed by invoking an adapter command vs. computed in the core.
_ADAPTER_GATES = {"format", "lint", "types", "tests", "mutation"}
_CORE_GATES = {"diff_coverage", "dependency_scan", "secret_scan", "spec_conformance"}


def _git_commit(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        return out
    except OSError:
        return ""


def _result_from_cmd(gate: str, spec: dict[str, Any], res: CmdResult) -> GateResult:
    status = STATUS_PASS if res.ok else STATUS_FAIL
    return GateResult(
        gate=gate,
        status=status,
        tool=str(spec.get("parser") or spec.get("cmd", "")).split()[0] if spec else "",
        duration_ms=res.duration_ms,
        details={"returncode": res.returncode},
        findings=[] if res.ok else res.tail(),
    )


def run_gates(
    settings: Settings,
    target: Path,
    *,
    tier: str,
    spec_path: Path,
    adapter_name: str | None = None,
    base: str | None = None,
    allow_mutation: bool = False,
) -> Verdict:
    tiers = settings.load_risk_tiers()
    tcfg = tier_config(tiers, tier)
    required: list[str] = list(tcfg.get("gates", []))

    adapter_name = adapter_name or adapters.detect_adapter(settings, target)
    manifest = adapters.load_adapter(settings, adapter_name)

    spec_id, _ = extract_spec(spec_path)
    verdict = Verdict(
        spec_id=spec_id,
        tier=tier,
        adapter=adapter_name,
        commit=_git_commit(settings.root),
    )

    # Run tests (with coverage) if either the tests or diff_coverage gate is required.
    coverage_path: Path | None = None
    need_tests = "tests" in required or "diff_coverage" in required

    for gate in GATE_ORDER:
        if gate not in required:
            continue

        if gate in _ADAPTER_GATES:
            spec = adapters.gate_spec(manifest, gate)
            if not spec:
                verdict.add(
                    GateResult(
                        gate=gate,
                        status=STATUS_SKIP,
                        findings=[f"adapter '{adapter_name}' declares no '{gate}' gate"],
                    )
                )
                continue
            if gate == "mutation" and not allow_mutation:
                # Wired but non-blocking in v0.1 (3PWR §17): report as skipped.
                verdict.add(
                    GateResult(
                        gate=gate,
                        status=STATUS_SKIP,
                        tool="mutation",
                        findings=["mutation wired but not enforced in this run"],
                    )
                )
                continue
            cmd = adapters.command_of(spec)
            if not cmd:
                verdict.add(
                    GateResult(
                        gate=gate,
                        status=STATUS_SKIP,
                        findings=[f"adapter declares no command for '{gate}'"],
                    )
                )
                continue
            res = adapters.run_cmd(cmd, cwd=target)
            gr = _result_from_cmd(gate, spec, res)
            if gate == "tests" and spec.get("coverage_path"):
                coverage_path = target / spec["coverage_path"]
            verdict.add(gr)

        elif gate == "diff_coverage":
            verdict.add(_diff_coverage_gate(settings, target, manifest, tcfg, coverage_path, base))

        elif gate == "dependency_scan":
            verdict.add(scanners.dependency_scan(target))

        elif gate == "secret_scan":
            verdict.add(scanners.secret_scan(target))

        elif gate == "spec_conformance":
            roots = _test_roots(manifest, target)
            gr = run_conformance(spec_path, roots)
            verdict.add(gr)
            verdict.failures.extend(conformance_failures(gr))

    # Make sure tests actually ran when required even if listed only via diff_coverage.
    if need_tests and not any(g.gate == "tests" for g in verdict.gates):
        spec = adapters.gate_spec(manifest, "tests")
        cmd = adapters.command_of(spec) if spec else None
        if spec and cmd:
            res = adapters.run_cmd(cmd, cwd=target)
            verdict.add(_result_from_cmd("tests", spec, res))

    # Actionable failures for any failed gate (3PWR-FR-034).
    for g in verdict.gates:
        if g.status != STATUS_FAIL:
            continue
        if g.gate in _ADAPTER_GATES:
            verdict.failures.append(
                failure(
                    "gate_failed",
                    gate=g.gate,
                    tool=g.tool,
                    detail="; ".join(g.findings[-3:]) or "non-zero exit",
                )
            )
        elif g.gate == "secret_scan":
            verdict.failures.append(
                failure(
                    "secret_exposed",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3]) or "secret detected",
                )
            )
        elif g.gate == "dependency_scan":
            verdict.failures.append(
                failure(
                    "vulnerable_dependency",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3]) or "vulnerable dependency",
                )
            )
    return verdict.finalize()


def _test_roots(manifest: dict[str, Any], target: Path) -> list[Path]:
    roots = manifest.get("test_roots") or ["tests", "src", "."]
    out = [target / r for r in roots]
    return [p for p in out if p.exists()] or [target]


def _diff_coverage_gate(
    settings: Settings,
    target: Path,
    manifest: dict[str, Any],
    tcfg: dict[str, Any],
    coverage_path: Path | None,
    base: str | None,
) -> GateResult:
    threshold = float(tcfg.get("diff_coverage", 0))
    if coverage_path is None:
        spec = adapters.gate_spec(manifest, "tests") or {}
        if spec.get("coverage_path"):
            coverage_path = target / spec["coverage_path"]
    if coverage_path is None or not coverage_path.exists():
        return GateResult(
            gate="diff_coverage",
            status=STATUS_FAIL,
            tool="3pwr-covdiff",
            findings=[f"no coverage report found at {coverage_path}"],
        )
    lcov = covdiff.parse_lcov(coverage_path, root=target)
    changed = covdiff.changed_lines(settings.root, target, base)
    pct, uncovered = covdiff.diff_coverage(lcov, changed)
    status = STATUS_PASS if pct >= threshold else STATUS_FAIL
    findings = []
    if status == STATUS_FAIL:
        findings = [f"{u['file']}:{u['line']} not covered" for u in uncovered[:10]]
    return GateResult(
        gate="diff_coverage",
        status=status,
        tool="3pwr-covdiff",
        details={"covered_pct": pct, "threshold": threshold, "uncovered_count": len(uncovered)},
        findings=findings,
    )
