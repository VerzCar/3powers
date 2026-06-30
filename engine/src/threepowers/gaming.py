"""Gate-gaming detection — a language-agnostic core gate (3PWR-FR-035).

Scans a change's diff for the moves that make a red gate look green: inline lint
disables, type suppressions, coverage pragmas, and deleted assertions. A hit is a
**fail surfaced for mandatory human review** — never a silent pass. Accepting a
legitimate suppression is a *deviation* (FR-057), recorded explicitly, not absorbed
here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .verdict import STATUS_FAIL, STATUS_PASS, GateResult

# Patterns that suppress a gate, matched on ADDED lines. The bracketed character
# class is deliberate: it matches a real hyphenated suppression token but NOT this
# detector's own source line, so 3Powers can gate itself (self-application).
_SUPPRESSIONS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"biome[-]ignore"), "biome lint/format suppression"),
    (re.compile(r"eslint[-]disable"), "eslint suppression"),
    (re.compile(r"#\s*noqa"), "ruff/flake8 suppression"),
    (re.compile(r"#\s*type:\s*ignore"), "mypy type suppression"),
    (re.compile(r"@ts[-](ignore|nocheck)"), "typescript suppression"),
    (re.compile(r"(pragma:\s*no cover|istanbul[ ]ignore|c8[ ]ignore)"), "coverage pragma"),
]
# Assertions whose REMOVAL weakens a test.
_ASSERT = re.compile(r"\b(assert|expect|\.toBe|\.toEqual|self\.assert)\b")


def detect_gaming(repo_root: Path, target: Path, base: str | None) -> GateResult:
    findings: list[str] = []
    diff = _diff(repo_root, target, base)
    if diff is not None:
        findings += _scan_diff(diff)
    findings += _scan_untracked(repo_root, target)  # a suppression in a new file must not evade

    status = STATUS_FAIL if findings else STATUS_PASS
    return GateResult(
        gate="gate_gaming",
        status=status,
        tool="3pwr-gaming",
        details={"count": len(findings)},
        findings=findings[:20],
    )


def _scan_diff(diff: str) -> list[str]:
    findings: list[str] = []
    current = "?"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            body = line[1:]
            for rx, label in _SUPPRESSIONS:
                if rx.search(body):
                    findings.append(f"{label} added in {current}: {body.strip()[:80]}")
        elif line.startswith("-") and not line.startswith("---") and _ASSERT.search(line[1:]):
            findings.append(f"assertion removed in {current}: {line[1:].strip()[:80]}")
    return findings


def _scan_untracked(repo_root: Path, target: Path) -> list[str]:
    findings: list[str] = []
    others = _git(repo_root, ["ls-files", "--others", "--exclude-standard", "--", str(target)])
    for rel in others.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        try:
            text = (repo_root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for ln in text.splitlines():
            for rx, label in _SUPPRESSIONS:
                if rx.search(ln):
                    findings.append(f"{label} in {rel} (untracked): {ln.strip()[:80]}")
    return findings


def _diff(repo_root: Path, target: Path, base: str | None) -> str | None:
    ref = _resolve_base(repo_root, base)
    if ref is None:
        return None
    return _git(repo_root, ["diff", "--unified=0", "--no-color", ref, "--", str(target)])


def _git(repo_root: Path, args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return ""


def _resolve_base(repo_root: Path, base: str | None) -> str | None:
    for ref in [base] if base else ["origin/main", "main", "HEAD~1", "HEAD"]:
        if ref and _git(repo_root, ["rev-parse", "--verify", "--quiet", ref]).strip():
            return ref
    return None
