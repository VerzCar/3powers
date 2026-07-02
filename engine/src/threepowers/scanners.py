"""Language-agnostic supply-chain scanners — core gates (3PWR-FR-028).

Secret scanning (betterleaks, falling back to gitleaks) and dependency scanning (osv-scanner)
live in the core, not in a language adapter, because they do not depend on the project's language.
When a scanner binary is absent the gate is **quarantined** — reported as ``skip`` with a surfaced
finding — never silently passed (3PWR-NFR-015).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .adapters import run_cmd
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult


def _quarantine(gate: str, tool: str) -> GateResult:
    return GateResult(
        gate=gate,
        status=STATUS_SKIP,
        tool=tool,
        findings=[f"quarantined: '{tool}' not installed — gate not enforced"],
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


# Secret scanners tried in order of preference. betterleaks is the maintained Gitleaks successor;
# gitleaks is the fallback. Both share the same ``dir`` CLI and JSON schema (File/RuleID/StartLine),
# so one command + one parser serves both — betterleaks writes ``null`` for an empty report where
# gitleaks writes ``[]``, handled below. Neither installed → the gate is quarantined (3PWR-NFR-015).
_SECRET_TOOLS = ("betterleaks", "gitleaks")


def _secret_tool() -> str | None:
    return next((t for t in _SECRET_TOOLS if shutil.which(t)), None)


# The engine's own private-key line format: ``ed25519-priv <base64-raw-seed-32>``. A real seed is
# 44 base64 chars; requiring ≥40 avoids matching the format's *mention* in docs or source literals
# while catching any actual committed key material (HARDN-FR-003).
_PRIVATE_KEY_RE = re.compile(r"^ed25519-priv\s+[A-Za-z0-9+/=]{40,}\s*$")
_MAX_CORE_SCAN_BYTES = 1_000_000


def _scan_candidates(target: Path) -> list[Path]:
    """Files the core secret check reads: git-tracked under ``target``, else a bounded walk."""
    try:
        res = subprocess.run(
            ["git", "ls-files", "-z"], cwd=target, capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            return [target / f for f in res.stdout.split("\0") if f]
    except OSError:
        pass
    skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    return [p for p in target.rglob("*") if p.is_file() and not (skip & set(p.parts))]


def _core_private_key_findings(target: Path, changed: set[str] | None) -> list[str]:
    """Core fallback scan for committed ``ed25519-priv`` material (HARDN-FR-003).

    Runs with or without an external secret scanner installed — the engine's own key format
    is never quarantined away. Deterministic, local, read-only.
    """
    findings: list[str] = []
    for f in _scan_candidates(target):
        if not _in_scope(target, str(f), changed):
            continue
        try:
            if f.stat().st_size > _MAX_CORE_SCAN_BYTES:
                continue
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PRIVATE_KEY_RE.match(line.strip()):
                try:
                    shown = str(f.relative_to(target))
                except ValueError:
                    shown = str(f)
                findings.append(f"ed25519-priv private-key material in {shown}:{lineno}")
                break  # one finding per file names it; no need to enumerate every line
        if len(findings) >= 10:
            break
    return findings


def secret_scan(target: Path, changed: set[str] | None = None) -> GateResult:
    """Scan the working tree for committed secrets (3PWR-FR-026 §8).

    A core check for the engine's own ``ed25519-priv`` key material ALWAYS runs first
    (HARDN-FR-003) — it needs no external binary and is never quarantined away. For the
    broader ruleset the gate prefers betterleaks (the maintained Gitleaks successor), falling
    back to gitleaks — both share the ``dir`` CLI and JSON schema. Only the external portion
    is quarantined when neither binary is installed (3PWR-NFR-015)."""
    core = _core_private_key_findings(target, changed)
    tool = _secret_tool()
    if tool is None:
        if core:
            return GateResult(
                gate="secret_scan",
                status=STATUS_FAIL,
                tool="3pwr-core",
                details={"count": len(core)},
                findings=core,
            )
        q = _quarantine("secret_scan", "betterleaks/gitleaks")
        q.findings.append("core ed25519-priv private-key check ran clean (HARDN-FR-003)")
        return q
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "secrets.json"
        res = run_cmd(
            f"{tool} dir {target} --no-banner --exit-code 1 "
            f"--report-format json --report-path {report}",
            cwd=target,
        )
        findings: list[str] = list(core)
        if report.exists():
            try:
                # betterleaks emits `null` for no findings; gitleaks emits `[]`. Coerce both to [].
                for f in json.loads(report.read_text(encoding="utf-8") or "null") or []:
                    if not _in_scope(target, f.get("File", ""), changed):
                        continue
                    findings.append(
                        f"{f.get('RuleID', 'secret')} in "
                        f"{f.get('File', '?')}:{f.get('StartLine', '?')}"
                    )
                    if len(findings) >= 10:
                        break
            except (ValueError, OSError, TypeError):
                pass
        if res.returncode not in (0, 1):
            # scanner error (not a clean pass/fail) → quarantine the external portion rather
            # than block — but committed key material found by the core check still fails.
            if core:
                return GateResult(
                    gate="secret_scan",
                    status=STATUS_FAIL,
                    tool="3pwr-core",
                    details={"count": len(core)},
                    findings=core,
                )
            return _quarantine("secret_scan", tool)
        # When diff-scoped, only changed-file findings block (3PWR-FR-051).
        in_scope = bool(findings) if changed is not None else (res.returncode == 1 or bool(core))
        status = STATUS_FAIL if in_scope else STATUS_PASS
        return GateResult(
            gate="secret_scan",
            status=status,
            tool=tool,
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
