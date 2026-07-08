"""Gate-gaming detection — a language-agnostic core gate.

Scans a change's diff for the moves that make a red gate look green: inline lint
disables, type suppressions, coverage pragmas, deleted assertions — and newly added
**assertion-free tests that reference requirement IDs**, the move that
games the conformance trace. A hit is a **fail surfaced for mandatory human review** —
never a silent pass. Accepting a legitimate suppression is a *deviation*,
recorded explicitly, not absorbed here.
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
# Assertions whose REMOVAL weakens a test — and whose ABSENCE from a newly added
# requirement-referencing test is a gaming signal. Language-agnostic union.
_ASSERT = re.compile(
    r"\b(assert|expect|\.toBe|\.toEqual|self\.assert|pytest\.raises"
    r"|t\.(?:Error|Errorf|Fatal|Fatalf|Fail|FailNow)|require\.\w+)\b"
)
# A test declaration opening, per language (chosen by file suffix so a snippet quoted
# inside another language's test fixture never false-positives — self-application).
_DECL_BY_SUFFIX: list[tuple[tuple[str, ...], re.Pattern]] = [
    ((".py",), re.compile(r"^\s*(?:async\s+)?def\s+test_\w+")),
    (
        (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"),
        re.compile(r"\b(?:describe|it|test)(?:\.\w+)?\s*\("),
    ),
    ((".go",), re.compile(r"^\s*func\s+Test\w+|\bt\.Run\s*\(")),
]
# A namespaced requirement ID (mirrors the conformance matcher, digit-leading spec ids ok).
_REQ = re.compile(r"\b[0-9A-Z]{2,16}-(?:FR|NFR)-\d{3,}\b")


def _decl_re(file: str) -> re.Pattern | None:
    suffix = Path(file.split()[0]).suffix.lower()
    for suffixes, rx in _DECL_BY_SUFFIX:
        if suffix in suffixes:
            return rx
    return None


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
    added_by_file: dict[str, list[str]] = {}
    removed_asserts: dict[str, list[str]] = {}
    current = "?"
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            body = line[1:]
            added_by_file.setdefault(current, []).append(body)
            for rx, label in _SUPPRESSIONS:
                if rx.search(body):
                    findings.append(f"{label} added in {current}: {body.strip()[:80]}")
        elif line.startswith("-") and not line.startswith("---") and _ASSERT.search(line[1:]):
            removed_asserts.setdefault(current, []).append(line[1:])
    # A *net* per-file loss of assertions weakens the suite; a refactor that removes and
    # re-adds an assertion balances out and is not a gaming signal.
    for file, removed in removed_asserts.items():
        re_added = sum(1 for ln in added_by_file.get(file, []) if _ASSERT.search(ln))
        for ln in removed[: max(0, len(removed) - re_added)]:
            findings.append(f"assertion removed in {file}: {ln.strip()[:80]}")
    for file, lines in added_by_file.items():
        findings += _weak_added_tests(file, lines)
    return findings


def _weak_added_tests(file: str, added: list[str]) -> list[str]:
    """Newly added assertion-free tests that reference a requirement ID.

    Works over the *added* lines only, with the declaration pattern chosen by the file's
    language: a block runs from a test declaration to the next one; a block whose opening
    (declaration + adjacent title/docstring) names a requirement ID but whose body contains
    no assertion is a gaming signal, routed to mandatory human review through this gate's
    existing red → deviation path.
    """
    rx = _decl_re(file)
    if rx is None:
        return []
    findings: list[str] = []
    decls = [i for i, ln in enumerate(added) if rx.search(ln)]
    for n, start in enumerate(decls):
        end = decls[n + 1] if n + 1 < len(decls) else len(added)
        head = "\n".join(added[start : min(start + 3, end)])
        if not _REQ.search(head):
            continue
        if not _ASSERT.search("\n".join(added[start:end])):
            findings.append(
                "assertion-free requirement-referencing test added in "
                f"{file}: {added[start].strip()[:80]}"
            )
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
        # An untracked file is all added lines — same weak-test scan.
        findings += _weak_added_tests(f"{rel} (untracked)", text.splitlines())
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
