"""Task scope discipline (3PWR-FR-016/017).

Two executive boundaries, checked deterministically:

* **FR-016** — every task traces to a requirement: each task line in ``tasks.md`` must
  carry a spec-namespaced requirement ID.
* **FR-017** — a task declares the files it will touch (``(files: …)``); a change that
  edits files outside the union of declared scopes is flagged, because an out-of-scope
  edit is a signal to stop and re-spec, not to proceed.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import covdiff
from .conformance import _TASK_RE, _iter_req_ids
from .verdict import STATUS_FAIL, STATUS_PASS, GateResult

_FILES_RE = re.compile(r"\(files:\s*([^)]*)\)", re.IGNORECASE)


def _in_scope(path: str, declared: set[str]) -> bool:
    for d in declared:
        d = d.rstrip("/")
        if path == d or path.startswith(d + "/"):
            return True
    return False


def scope_check(
    tasks_path: Path,
    repo_root: Path,
    *,
    base: str | None = None,
    target: Path | None = None,
) -> GateResult:
    text = tasks_path.read_text(encoding="utf-8")
    declared: set[str] = set()
    tasks_without_req: list[str] = []

    for line in text.splitlines():
        if not _TASK_RE.search(line):
            continue
        if not any(True for _ in _iter_req_ids(line)):
            tasks_without_req.append(line.strip()[:80])  # FR-016
        m = _FILES_RE.search(line)
        if m:
            for f in m.group(1).split(","):
                f = f.strip()
                if f:
                    declared.add(f)

    changed = covdiff.changed_files(repo_root, base, target)
    out_of_scope = sorted(f for f in changed if not _in_scope(f, declared))

    findings = [f"task without requirement id: {t}" for t in tasks_without_req]
    findings += [f"out-of-scope edit (not in any task's declared files): {f}" for f in out_of_scope]
    status = STATUS_FAIL if findings else STATUS_PASS
    return GateResult(
        gate="scope",
        status=status,
        tool="3pwr-scope",
        details={
            "declared_scope": sorted(declared),
            "out_of_scope": out_of_scope,
            "tasks_without_requirement": tasks_without_req,
        },
        findings=findings,
    )
