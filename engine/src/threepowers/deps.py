"""Third-party dependency compatibility (3PWR-FR-048, 3PWR-NFR-014).

3Powers drives headless agent backends, per-language adapter toolchains, and supply-chain scanners.
A new upstream release of any of these can change behaviour, so the **supported** versions are an
explicit, versioned config (``.3powers/config/dependencies.yaml``) and ``3pwr deps-check`` probes the
INSTALLED versions against it: `ok` (within range), `drift` (installed but outside), `missing` (not
probeable), or `unknown` (installed, no range declared). A per-component policy governs blocking —
`block` fails the check, `warn` surfaces it, `ignore` skips.

This is a **preflight** check, never a verdict gate: installed-tool versions are environment-dependent,
so keeping them out of the verdict preserves determinism (3PWR-NFR-001) — the same reason the oracle's
peek/touch signal is advisory. An absent tool is reported, like the scanner quarantine (3PWR-NFR-015),
never silently passed.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .adapters import run_cmd

OK = "ok"
DRIFT = "drift"  # installed, but outside the supported range
MISSING = "missing"  # not installed / not probeable
UNKNOWN = "unknown"  # installed, but no supported range declared (informational)

_VERSION_RE = re.compile(r"\d+(?:\.\d+)*")
_CLAUSE_RE = re.compile(r"^\s*(>=|<=|==|!=|~=|>|<)?\s*(.+?)\s*$")


def parse_release(text: str) -> tuple[int, ...]:
    """Leading dotted-integer release from a version string, ignoring any prefix (``v``) and
    suffix (``.dev0``, ``-rc1``). ``"v0.11.6.dev0"`` → ``(0, 11, 6)``."""
    m = _VERSION_RE.search(text or "")
    return tuple(int(p) for p in m.group(0).split(".")) if m else ()


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return (a > b) - (a < b)


def _clause_ok(installed: tuple[int, ...], op: str, want: tuple[int, ...]) -> bool:
    c = _cmp(installed, want)
    if op == ">=":
        return c >= 0
    if op == "<=":
        return c <= 0
    if op == ">":
        return c > 0
    if op == "<":
        return c < 0
    if op == "!=":
        return c != 0
    if op == "~=":  # compatible release: >= want AND same leading component(s)
        keep = max(len(want) - 1, 1)
        return c >= 0 and installed[:keep] == want[:keep]
    return c == 0  # "==" or bare


def satisfies(version: str, spec: str) -> bool:
    """True iff ``version`` satisfies every comma-separated clause in ``spec`` (e.g. ``>=0.11,<0.12``)."""
    installed = parse_release(version)
    if not installed or not spec.strip():
        return False
    for clause in spec.split(","):
        m = _CLAUSE_RE.match(clause)
        if not m:
            return False
        want = parse_release(m.group(2))
        if not want or not _clause_ok(installed, m.group(1) or "==", want):
            return False
    return True


@dataclass
class DepCheck:
    name: str
    installed: Optional[str]
    supported: str
    status: str
    policy: str  # warn | block | ignore

    @property
    def blocking(self) -> bool:
        return self.policy == "block" and self.status in (DRIFT, MISSING)


@dataclass
class DepsReport:
    checks: list[DepCheck] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(c.blocking for c in self.checks)

    @property
    def drifted(self) -> list[DepCheck]:
        return [c for c in self.checks if c.status in (DRIFT, MISSING)]


def run_probe(cmd: str, repo_root: Path) -> Optional[str]:
    """Run a probe command and return the version string it prints, or None if the tool's
    executable is absent (mirrors the scanner quarantine) or it prints no version."""
    parts = cmd.split()
    if not parts or shutil.which(parts[0]) is None:
        return None
    res = run_cmd(cmd, cwd=repo_root)
    m = _VERSION_RE.search((res.stdout + "\n" + res.stderr).strip())
    return m.group(0) if m else None


def check_dependencies(manifest: dict, probe: Callable[[str], Optional[str]]) -> DepsReport:
    """Classify each declared component against its supported range. ``probe`` maps a probe
    command → an installed version string (or None); injectable so tests stay deterministic."""
    report = DepsReport()
    for comp in manifest.get("components", []):
        supported = comp.get("supported", "")
        installed = probe(comp.get("probe", ""))
        if installed is None:
            status = MISSING
        elif not supported:
            status = UNKNOWN
        elif satisfies(installed, supported):
            status = OK
        else:
            status = DRIFT
        report.checks.append(
            DepCheck(
                name=comp.get("name", "?"),
                installed=installed,
                supported=supported,
                status=status,
                policy=comp.get("on_drift", "warn"),
            )
        )
    return report
