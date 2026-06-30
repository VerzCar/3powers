"""The normalized verdict — one machine-readable shape, identical across languages.

Same code → same verdict regardless of which model authored it (3PWR-NFR-001), and
the shape does not vary by language (3PWR-FR-033). Every failure is actionable: it
names a class and the offending requirement/file/branch (3PWR-FR-034). A human can
read it and find the failing gate without opening any agent transcript
(3PWR-NFR-011).
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION

# Cheapest-first canonical gate order (3PWR-FR-026).
GATE_ORDER = [
    "format",
    "lint",
    "types",
    "tests",
    "diff_coverage",
    "mutation",
    "spec_conformance",
]

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"


@dataclass
class GateResult:
    gate: str
    status: str
    tool: str = ""
    duration_ms: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)


@dataclass
class Verdict:
    spec_id: str
    tier: str
    adapter: str
    commit: str = ""
    schema_version: str = SCHEMA_VERSION
    verdict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    result: str = STATUS_PASS
    gates: list[GateResult] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)

    def add(self, gate: GateResult) -> None:
        self.gates.append(gate)

    def finalize(self) -> "Verdict":
        """Order gates cheapest-first and derive overall result + failures."""
        self.gates.sort(key=lambda g: GATE_ORDER.index(g.gate) if g.gate in GATE_ORDER else 99)
        self.result = STATUS_PASS
        for g in self.gates:
            if g.status == STATUS_FAIL:
                self.result = STATUS_FAIL
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def write(self, path: Path) -> None:
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    def requirement_ids(self) -> list[str]:
        ids: set[str] = set()
        for g in self.gates:
            for rid in g.details.get("requirement_ids", []) or []:
                ids.add(rid)
        return sorted(ids)


def failure(failure_class: str, **fields: Any) -> dict[str, Any]:
    """Build an actionable failure record (3PWR-FR-034).

    Examples of ``failure_class``:
      * ``untested_requirement`` (+ ``requirement_id``)
      * ``coverage_drop``       (+ ``file``, ``uncovered_lines``)
      * ``gate_failed``         (+ ``gate``, ``tool``)
    """
    rec = {"class": failure_class}
    rec.update(fields)
    return rec
