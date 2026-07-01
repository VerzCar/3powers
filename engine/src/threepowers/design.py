"""Design oracles — how *design* work is judged, beyond the code gates (3PWR-FR-009).

When work-kind inference (3PWR-FR-058) tags a change ``design``, the engine unions a set of
**design-oracle gates** onto the tier's gate set. Which oracles apply is a config catalog
(``.3powers/config/design-oracles.yaml``); the *tool* for each is **adapter-supplied**, keeping the
core language-agnostic (3PWR-NFR-007). A selected oracle the adapter doesn't declare — or whose tool
isn't installed — is **quarantined** (reported ``skip`` with a surfaced finding), never silently
passed (3PWR-NFR-015).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from . import adapters
from .config import Settings
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult

# The canonical design-oracle gate names the engine knows how to place in the cheapest-first order
# (see verdict.GATE_ORDER). The catalog maps oracle *kinds* onto these gate names.
DESIGN_GATES = ("contract_check", "component_contract", "a11y_scan", "visual_regression")

# Built-in catalog used when the repo ships no design-oracles.yaml, so a design change always surfaces
# every oracle dimension (quarantined if unwired) rather than silently passing (3PWR-NFR-015).
_DEFAULT_ORACLES: dict[str, dict[str, Any]] = {
    "structural": {"gate": "contract_check"},
    "component_contract": {"gate": "component_contract"},
    "accessibility": {"gate": "a11y_scan"},
    "visual_regression": {"gate": "visual_regression"},
}


def load_oracles(settings: Settings) -> dict[str, dict[str, Any]]:
    """The design-oracle catalog (oracle kind → {gate, thresholds…}); the built-in default if absent."""
    path = settings.design_oracles_path
    if not path.exists():
        return dict(_DEFAULT_ORACLES)
    data = _safe_load(path)
    oracles = data.get("oracles") if isinstance(data, dict) else None
    return oracles if isinstance(oracles, dict) and oracles else dict(_DEFAULT_ORACLES)


def _safe_load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def selected_gates(settings: Settings) -> list[str]:
    """Design-oracle gate names to run for a design change, in cheapest-first (GATE_ORDER) order."""
    wanted = {
        str(entry.get("gate"))
        for entry in load_oracles(settings).values()
        if isinstance(entry, dict) and entry.get("gate") in DESIGN_GATES
    }
    return [g for g in DESIGN_GATES if g in wanted]


def _quarantine(gate: str, tool: str, why: str) -> GateResult:
    return GateResult(
        gate=gate,
        status=STATUS_SKIP,
        tool=tool,
        findings=[f"quarantined: {why} — design oracle not enforced"],
    )


def design_gate(gate: str, manifest: dict[str, Any], adapter_name: str, target: Path) -> GateResult:
    """Run one design-oracle gate via the adapter's declared command; quarantine if unwired/absent."""
    spec = adapters.gate_spec(manifest, gate)
    if not spec:
        return _quarantine(gate, "", f"adapter '{adapter_name}' declares no '{gate}'")
    cmd = adapters.command_of(spec)
    if not cmd:
        return _quarantine(gate, "", f"adapter '{adapter_name}' declares no command for '{gate}'")
    res = adapters.run_cmd(cmd, cwd=target, shell=adapters.wants_shell(spec))
    tool = str(spec.get("parser") or cmd.split()[0])
    if res.returncode == 127:  # the tool itself isn't installed
        return _quarantine(gate, tool, f"'{tool}' not installed")
    return GateResult(
        gate=gate,
        status=STATUS_PASS if res.ok else STATUS_FAIL,
        tool=tool,
        duration_ms=res.duration_ms,
        details={"returncode": res.returncode},
        findings=[] if res.ok else res.tail(),
    )
