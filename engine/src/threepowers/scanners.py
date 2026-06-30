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


def _in_scope(target: Path, file: str, changed: set[str] | None) -> bool:
    """True if a finding's file is in the changed-file scope (brownfield, 3PWR-FR-051).

    ``changed`` holds absolute paths; ``file`` is whatever the scanner reported
    (absolute, or relative to ``target``). When ``changed`` is None nothing is scoped.
    """
    if changed is None:
        return True
    p = Path(file)
    resolved = str((p if p.is_absolute() else (target / p)).resolve())
    return resolved in changed


def secret_scan(target: Path, changed: set[str] | None = None) -> GateResult:
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
        in_scope = True
        if report.exists():
            try:
                for f in json.loads(report.read_text(encoding="utf-8") or "[]"):
                    if not _in_scope(target, f.get("File", ""), changed):
                        continue
                    findings.append(
                        f"{f.get('RuleID', 'secret')} in "
                        f"{f.get('File', '?')}:{f.get('StartLine', '?')}"
                    )
                    if len(findings) >= 10:
                        break
            except (ValueError, OSError):
                pass
        if res.returncode not in (0, 1):
            # scanner error (not a clean pass/fail) → quarantine rather than block
            return _quarantine("secret_scan", "gitleaks")
        # When diff-scoped, only changed-file findings block (3PWR-FR-051).
        in_scope = bool(findings) if changed is not None else res.returncode == 1
        status = STATUS_FAIL if in_scope else STATUS_PASS
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


def sast_scan(target: Path, rules_path: Path, changed: set[str] | None = None) -> GateResult:
    """Static analysis with semgrep against a local, offline ruleset (3PWR-FR-026 §8)."""
    if not shutil.which("semgrep") or not rules_path.exists():
        return _quarantine("sast", "semgrep")
    res = run_cmd(f"semgrep scan --quiet --json --config {rules_path} {target}", cwd=target)
    findings: list[str] = []
    raw_count = 0
    try:
        for r in json.loads(res.stdout or "{}").get("results") or []:
            raw_count += 1
            if not _in_scope(target, r.get("path", ""), changed):
                continue  # brownfield: only changed-file findings block (3PWR-FR-051)
            line = r.get("start", {}).get("line", "?")
            findings.append(f"{r.get('check_id', 'rule')} at {r.get('path', '?')}:{line}")
            if len(findings) >= 20:
                break
    except ValueError:
        pass
    if res.returncode >= 2 and raw_count == 0:  # semgrep itself errored
        return _quarantine("sast", "semgrep")
    status = STATUS_FAIL if findings else STATUS_PASS
    return GateResult(
        gate="sast",
        status=status,
        tool="semgrep",
        duration_ms=res.duration_ms,
        details={"count": len(findings)},
        findings=findings,
    )
