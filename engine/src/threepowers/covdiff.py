"""Diff coverage — measure coverage on *changed* lines only (3PWR-FR-029).

This lives in the language-agnostic core (3PWR-FR-028): adapters merely emit a
standard LCOV report; the core intersects it with the lines a change touched. We use
LCOV because every reference adapter's coverage tool can produce it (Vitest/v8,
coverage.py, JaCoCo, …), so the same core code serves all languages.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def parse_lcov(lcov_path: Path, root: Path | None = None) -> dict[str, dict[int, int]]:
    """Return ``{absolute_file_path: {line_number: hit_count}}`` from an LCOV file.

    Relative ``SF:`` paths are resolved against ``root`` (the project root the coverage
    tool ran in — e.g. coverage.py emits paths relative to cwd), falling back to the
    LCOV file's own directory when ``root`` is not given.
    """
    result: dict[str, dict[int, int]] = {}
    if not lcov_path.exists():
        return result
    base = root or lcov_path.parent
    current: str | None = None
    for line in lcov_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("SF:"):
            raw = line[3:].strip()
            p = Path(raw)
            current = str((p if p.is_absolute() else (base / p)).resolve())
            result.setdefault(current, {})
        elif line.startswith("DA:") and current is not None:
            num, _, count = line[3:].partition(",")
            try:
                result[current][int(num)] = int(count)
            except ValueError:
                continue
        elif line.startswith("end_of_record"):
            current = None
    return result


def changed_lines(repo_root: Path, target: Path, base: str | None) -> dict[str, set[int]]:
    """Lines added/modified under ``target`` relative to ``base``.

    New (untracked) files count fully. If ``base`` cannot be resolved we return an
    empty mapping, and the caller treats every measured line as in-scope (so a
    brand-new project still gets a meaningful diff-coverage number).
    """
    changed: dict[str, set[int]] = {}
    base_ref = _resolve_base(repo_root, base)
    if base_ref is not None:
        diff = _git(repo_root, ["diff", "--unified=0", "--no-color", base_ref, "--", str(target)])
        changed.update(_parse_diff_added(diff, repo_root))
    # Untracked files: count every line as changed.
    others = _git(repo_root, ["ls-files", "--others", "--exclude-standard", "--", str(target)])
    for rel in others.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        fpath = (repo_root / rel).resolve()
        try:
            n = len(fpath.read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeDecodeError):
            continue  # skip binary / unreadable files
        changed[str(fpath)] = set(range(1, n + 1))
    return changed


def diff_coverage(
    lcov: dict[str, dict[int, int]],
    changed: dict[str, set[int]],
) -> tuple[float, list[dict]]:
    """Return ``(percent_covered, uncovered)`` over changed *executable* lines.

    When ``changed`` is empty (no resolvable base) we fall back to all measured lines
    so the metric is still meaningful on a fresh tree.
    """
    covered = 0
    total = 0
    uncovered: list[dict] = []
    for file, line_hits in lcov.items():
        scope = changed.get(file)
        for line, hits in sorted(line_hits.items()):
            if scope is not None and line not in scope:
                continue
            total += 1
            if hits > 0:
                covered += 1
            else:
                uncovered.append({"file": file, "line": line})
    if total == 0:
        return 100.0, []
    return round(100.0 * covered / total, 2), uncovered


# -- helpers ---------------------------------------------------------------
def _git(repo_root: Path, args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return ""


def _resolve_base(repo_root: Path, base: str | None) -> str | None:
    candidates = [base] if base else ["origin/main", "main", "HEAD~1", "HEAD"]
    for ref in candidates:
        if ref and _git(repo_root, ["rev-parse", "--verify", "--quiet", ref]).strip():
            return ref
    return None


def _parse_diff_added(diff: str, repo_root: Path) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    current: str | None = None
    cursor = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = str((repo_root / line[6:].strip()).resolve())
            out.setdefault(current, set())
        elif line.startswith("@@"):
            m = _HUNK_RE.match(line)
            if m:
                cursor = int(m.group(1))
        elif line.startswith("+") and not line.startswith("+++") and current is not None:
            out[current].add(cursor)
            cursor += 1
        elif not line.startswith("-") and current is not None and not line.startswith("\\"):
            cursor += 1
    return out
