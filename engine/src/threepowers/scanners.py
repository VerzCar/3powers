"""Language-agnostic supply-chain scanners — core gates (3PWR-FR-028).

Secret scanning (gitleaks) and dependency scanning (osv-scanner) live in the core,
not in a language adapter, because they do not depend on the project's language. When
a scanner binary is absent the gate is **quarantined** — reported as ``skip`` with a
surfaced finding — never silently passed (3PWR-NFR-015).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .adapters import run_cmd
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult


def _quarantine(gate: str, tool: str) -> GateResult:
    return GateResult(
        gate=gate,
        status=STATUS_SKIP,
        tool=tool,
        findings=[f"quarantined: '{tool}' not installed — gate not enforced (3PWR-NFR-015)"],
    )


def secret_scan(target: Path) -> GateResult:
    """Scan the working tree for committed secrets with gitleaks."""
    if not shutil.which("gitleaks"):
        return _quarantine("secret_scan", "gitleaks")
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "gitleaks.json"
        res = run_cmd(
            f"gitleaks dir {target} --no-banner --exit-code 1 "
            f"--report-format json --report-path {report}",
            cwd=target,
        )
        findings: list[str] = []
        if report.exists():
            try:
                for f in json.loads(report.read_text(encoding="utf-8") or "[]")[:10]:
                    findings.append(
                        f"{f.get('RuleID', 'secret')} in "
                        f"{f.get('File', '?')}:{f.get('StartLine', '?')}"
                    )
            except (ValueError, OSError):
                pass
        if res.returncode == 0:
            status = STATUS_PASS
        elif res.returncode == 1:
            status = STATUS_FAIL
        else:  # scanner error (not a clean pass/fail) → quarantine rather than block
            return _quarantine("secret_scan", "gitleaks")
        return GateResult(
            gate="secret_scan",
            status=status,
            tool="gitleaks",
            duration_ms=res.duration_ms,
            details={"count": len(findings)},
            findings=findings,
        )


def dependency_scan(target: Path) -> GateResult:
    """Scan dependency manifests/lockfiles for known vulnerabilities with osv-scanner."""
    if not shutil.which("osv-scanner"):
        return _quarantine("dependency_scan", "osv-scanner")
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "osv.json"
        res = run_cmd(f"osv-scanner --format json --output-file {report} -r {target}", cwd=target)
        findings: list[str] = []
        if report.exists():
            try:
                data = json.loads(report.read_text(encoding="utf-8") or "{}")
                for r in data.get("results", []):
                    for pkg in r.get("packages", []):
                        name = pkg.get("package", {}).get("name", "?")
                        for v in pkg.get("vulnerabilities", [])[:10]:
                            findings.append(f"{v.get('id', 'VULN')} in {name}")
            except (ValueError, OSError):
                pass
        if res.returncode == 0:
            status = STATUS_PASS
        elif res.returncode == 1:
            status = STATUS_FAIL
        else:  # e.g. nothing to scan / scanner error → quarantine, do not false-fail
            return _quarantine("dependency_scan", "osv-scanner")
        return GateResult(
            gate="dependency_scan",
            status=status,
            tool="osv-scanner",
            duration_ms=res.duration_ms,
            details={"count": len(findings)},
            findings=findings[:10],
        )
