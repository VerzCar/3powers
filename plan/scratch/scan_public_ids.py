#!/usr/bin/env python3
"""Disposable inventory scanner for plan 031 (Track A).

Walks the public surfaces of the repo, matches internal requirement-ID citations
and their sibling forms, classifies each hit heuristically, and emits
plan/scratch/031-id-inventory.md as the authoritative Track B worklist.

Stdlib only. Read-only. Deleted in the closing commit of delivery unit 1.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# Namespace may start with a digit (the repo's own 3PWR- namespace), so the
# leading class is [A-Z0-9] with a lookbehind standing in for \b.
ID_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9][A-Z0-9]{2,}-)?(FR|NFR)-[0-9]{2,3}\b")
EPIC_RE = re.compile(r"\(epic [A-Z][0-9]\)")
PLANSPEC_RE = re.compile(r"\((plan|spec) [0-9]{3}\)")

# Placeholder / teaching forms that are always format-example.
PLACEHOLDER_RE = re.compile(r"<[A-Za-z]+>-(FR|NFR)-|\bDEMO-(FR|NFR)-")

HELP_CONTEXT_RE = re.compile(r"\b(help|description)\s*=")
ECHO_CONTEXT_RE = re.compile(
    r"\b(print|_print|echo|styler|_styler|notify|_notify|checklist|_checklist|"
    r"warn|error|hint|panel|console|write|raise \w*Error|SystemExit|log)\b"
)


def surfaces() -> list[Path]:
    """Collect every file on the scanned surface, minus the exemptions."""
    files: list[Path] = []

    # engine source incl. scaffold assets (all file types under the package)
    eng = REPO / "engine" / "src" / "threepowers"
    files.extend(p for p in eng.rglob("*") if p.is_file() and not p.name.endswith(".pyc"))

    # docs minus STATUS.md
    docs = REPO / "docs"
    files.extend(
        p
        for p in docs.rglob("*")
        if p.is_file() and p.name != "STATUS.md" and p.suffix in {".md", ".txt", ".html"}
    )

    # root-level public files
    for name in ("README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "CHANGELOG.md"):
        p = REPO / name
        if p.exists():
            files.append(p)

    # .3powers seeded copies (never ledger/verdicts/runs)
    tp = REPO / ".3powers"
    for rel in ("README.md", "memory/constitution.md"):
        p = tp / rel
        if p.exists():
            files.append(p)
    for sub in ("templates", "agents", "config", "adapters"):
        d = tp / sub
        if d.is_dir():
            files.extend(p for p in d.rglob("*") if p.is_file())

    # .github non-agent files
    gh = REPO / ".github"
    if gh.is_dir():
        files.extend(
            p
            for p in gh.rglob("*")
            if p.is_file() and "agents" not in p.relative_to(gh).parts
        )

    return sorted(set(files))


def classify(path: Path, line: str, match_text: str, in_docstring: bool) -> str:
    """Heuristic kind classification for one hit."""
    rel = path.relative_to(REPO)
    parts = rel.parts
    bare = "-FR-" not in match_text and "-NFR-" not in match_text and match_text.startswith(
        ("FR-", "NFR-")
    )
    if bare or PLACEHOLDER_RE.search(line):
        return "format-example"
    if "scaffold" in parts or parts[0] == ".3powers":
        return "scaffold-asset"
    if path.suffix == ".py":
        stripped = line.lstrip()
        if in_docstring:
            return "docstring"
        if stripped.startswith("#"):
            return "comment"
        if HELP_CONTEXT_RE.search(line):
            return "help-string"
        if ECHO_CONTEXT_RE.search(line):
            return "echoed-message"
        # string literal in code that isn't clearly help/echo: treat as echoed
        if '"' in line or "'" in line:
            return "echoed-message"
        return "comment"
    return "doc-prose"


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    """Return (lineno, kind, match, excerpt) hits for one file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    hits: list[tuple[int, str, str, str]] = []
    in_doc = False
    doc_delim = ""
    for lineno, line in enumerate(text.splitlines(), 1):
        # crude python docstring tracking
        if path.suffix == ".py":
            stripped = line.strip()
            i = 0
            while i < len(stripped):
                if in_doc:
                    j = stripped.find(doc_delim, i)
                    if j == -1:
                        break
                    in_doc = False
                    i = j + 3
                else:
                    j3 = stripped.find('"""', i)
                    k3 = stripped.find("'''", i)
                    if j3 == -1 and k3 == -1:
                        break
                    if k3 == -1 or (j3 != -1 and j3 < k3):
                        doc_delim, j = '"""', j3
                    else:
                        doc_delim, j = "'''", k3
                    end = stripped.find(doc_delim, j + 3)
                    if end == -1:
                        in_doc = True
                        break
                    i = end + 3
            line_in_doc = in_doc or stripped.startswith(('"""', "'''")) or (
                doc_delim and stripped.endswith(doc_delim) and not stripped.startswith("#")
            )
        else:
            line_in_doc = False
        matches = [m.group(0) for m in ID_RE.finditer(line)]
        matches += [m.group(0) for m in EPIC_RE.finditer(line)]
        matches += [m.group(0) for m in PLANSPEC_RE.finditer(line)]
        for mt in matches:
            kind = classify(path, line, mt, bool(line_in_doc))
            excerpt = line.strip()
            if len(excerpt) > 160:
                excerpt = excerpt[:157] + "..."
            hits.append((lineno, kind, mt, excerpt))
    return hits


def main() -> int:
    out = Path(__file__).with_name("031-id-inventory.md")
    per_file: dict[Path, list[tuple[int, str, str, str]]] = {}
    kind_counts: Counter[str] = Counter()
    ns_counts: Counter[str] = Counter()
    for path in surfaces():
        hits = scan_file(path)
        if not hits:
            continue
        per_file[path] = hits
        for _, kind, mt, _ in hits:
            kind_counts[kind] += 1
            m = re.match(r"([A-Z0-9][A-Z0-9]{2,})-(?:FR|NFR)-", mt)
            ns_counts[m.group(1) if m else "(bare/sibling)"] += 1

    lines = ["# Plan 031 — internal-ID inventory (disposable)", ""]
    total = sum(kind_counts.values())
    lines.append(f"Total hits: **{total}** across {len(per_file)} files.")
    lines.append("")
    lines.append("## Summary by kind")
    lines.append("")
    lines.append("| kind | count |")
    lines.append("|---|---|")
    for kind, n in kind_counts.most_common():
        lines.append(f"| {kind} | {n} |")
    lines.append("")
    lines.append("## Summary by namespace")
    lines.append("")
    lines.append("| namespace | count |")
    lines.append("|---|---|")
    for ns, n in ns_counts.most_common():
        lines.append(f"| {ns} | {n} |")
    lines.append("")
    engine_total = sum(
        len(h)
        for p, h in per_file.items()
        if "engine" in p.relative_to(REPO).parts
    )
    lines.append(f"Engine-source total (sanity check vs raw grep census): **{engine_total}**")
    lines.append("")
    for path in sorted(per_file):
        rel = path.relative_to(REPO)
        hits = per_file[path]
        lines.append(f"## {rel} ({len(hits)})")
        lines.append("")
        lines.append("| line | kind | match | excerpt |")
        lines.append("|---|---|---|---|")
        for lineno, kind, mt, excerpt in hits:
            safe = excerpt.replace("|", "\\|")
            lines.append(f"| {lineno} | {kind} | {mt} | `{safe}` |")
        lines.append("")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {out} — {total} hits, engine total {engine_total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
