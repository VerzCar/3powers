"""Language adapters — the polyglot plugin contract.

An adapter is a *declarative manifest* (``.3powers/adapters/<lang>/adapter.yaml``)
that maps each gate to a tool invocation and the standard format of its output.
Adding a language is therefore "add a manifest" — no change to the gate-engine core.
The core never assumes a language beyond what the adapter declares.
"""

from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from .config import Settings


@dataclass
class CmdResult:
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    def tail(self, n: int = 20) -> list[str]:
        text = (self.stdout + "\n" + self.stderr).strip()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return lines[-n:]


# The only gates a fix command may run for: a fix mutates source to satisfy a
# style check — types/tests/mutation must never be "fixed" into passing. Enforced at configuration
# assembly (a stray fix_cmd is discarded) AND at execution (gates.py refuses to run one).
AUTOFIX_GATES = frozenset({"format", "lint"})

# Where the per-project gate overrides live — committed team configuration,
# versioned with the rest of .3powers/config/, seeded by `3pwr init`.
GATE_OVERRIDES_NAME = "gates.yaml"


def _read_manifest(settings: Settings, name: str) -> dict[str, Any]:
    """Parse the raw adapter manifest, without any override or detection applied."""
    path = settings.adapters_dir / name / "adapter.yaml"
    if not path.exists():
        raise FileNotFoundError(f"adapter manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_gate_overrides(settings: Settings) -> dict[str, dict[str, Any]]:
    """The per-gate overrides from ``.3powers/config/gates.yaml``.

    Returns ``{gate: {key: value}}``; ``{}`` when the file is absent, empty, or fully commented.
    Non-mapping gate blocks are ignored — the file overrides gate KEYS, nothing else."""
    path = settings.dir / "config" / GATE_OVERRIDES_NAME
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return {
        str(gate): dict(block) for gate, block in data.items() if isinstance(block, dict) and block
    }


def merge_gate_overrides(
    manifest: dict[str, Any], overrides: dict[str, dict[str, Any]]
) -> list[str]:
    """Deep-merge ``overrides`` into the manifest's ``gates:`` blocks; returns the overridden gates.

    One ``dict.update()`` pass per gate block: only keys present in the override
    replace the adapter's; absent gates/keys keep the adapter values. A ``fix_cmd`` on a
    non-fixable gate is discarded, never merged. Overrides replace TOOLS, never
    gates — the risk tier alone decides which gates run."""
    if not overrides:
        return []
    gates = manifest.setdefault("gates", {})
    touched: list[str] = []
    for gate, block in overrides.items():
        patch = dict(block)
        if gate not in AUTOFIX_GATES:
            patch.pop("fix_cmd", None)
        if not patch:
            continue
        merged = dict(gates.get(gate) or {})
        merged.update(patch)
        gates[gate] = merged
        touched.append(gate)
    return touched


def _strip_invalid_fix_cmds(manifest: dict[str, Any]) -> None:
    """Discard any ``fix_cmd`` declared on a non-fixable gate.

    The schema admits a fix command for the format/lint gates only — types, tests, and mutation
    must never be "fixed" into passing, whichever file tried to configure one."""
    for gate, spec in (manifest.get("gates") or {}).items():
        if gate not in AUTOFIX_GATES and isinstance(spec, dict):
            spec.pop("fix_cmd", None)


def load_adapter(settings: Settings, name: str) -> dict[str, Any]:
    """The adapter manifest with the project's ``gates.yaml`` overrides merged in."""
    manifest = _read_manifest(settings, name)
    merge_gate_overrides(manifest, load_gate_overrides(settings))
    _strip_invalid_fix_cmds(manifest)
    return manifest


def detect_adapter(settings: Settings, target: Path) -> str:
    """Pick the adapter whose ``detect`` files exist under ``target``."""
    if not settings.adapters_dir.is_dir():
        raise FileNotFoundError("no adapters directory")
    for adir in sorted(p for p in settings.adapters_dir.iterdir() if p.is_dir()):
        manifest = adir / "adapter.yaml"
        if not manifest.exists():
            continue
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        detect = data.get("detect", [])
        if detect and all((target / f).exists() for f in detect):
            return adir.name
    raise LookupError(f"could not detect a language adapter for {target}")


def gate_spec(manifest: dict[str, Any], gate: str) -> Optional[dict[str, Any]]:
    return (manifest.get("gates") or {}).get(gate)


def run_cmd(command: str, cwd: Path, timeout: int = 600, shell: bool = False) -> CmdResult:
    """Run an adapter command and capture its result.

    ``shell=True`` (opt-in per gate via ``shell: true`` in the manifest) runs the command through the
    system shell so a toolchain that needs a pipeline can be declared — e.g. Go's
    ``go test -coverprofile=… && gcov2lcov …`` to emit LCOV for the core's diff-coverage. Commands come
    only from committed, trusted adapter manifests, never from user input, so no injection surface is
    opened. Default stays ``shlex.split`` (no shell) for the reference adapters.
    """
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command if shell else shlex.split(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=shell,
        )
        return CmdResult(
            proc.returncode, proc.stdout, proc.stderr, int((time.monotonic() - start) * 1000)
        )
    except FileNotFoundError as exc:
        return CmdResult(127, "", f"tool not found: {exc}", int((time.monotonic() - start) * 1000))
    except subprocess.TimeoutExpired:
        return CmdResult(
            124, "", f"timed out after {timeout}s", int((time.monotonic() - start) * 1000)
        )


def command_of(spec: dict[str, Any]) -> Optional[str]:
    """Prefer a non-mutating ``check_cmd`` over a mutating ``cmd``."""
    return spec.get("check_cmd") or spec.get("cmd")


def wants_shell(spec: dict[str, Any]) -> bool:
    """Whether this gate's command must run through the shell (opt-in ``shell: true``)."""
    return bool(spec.get("shell"))


def toolchain(manifest: dict[str, Any]) -> dict[str, Any]:
    """The adapter's declared toolchain map (tool → {install, probe}), or ``{}``."""
    tc = manifest.get("toolchain")
    return tc if isinstance(tc, dict) else {}


def gate_requires(spec: Optional[dict[str, Any]]) -> Optional[str]:
    """The toolchain entry a gate needs (its ``requires:``), or ``None``."""
    if not spec:
        return None
    req = spec.get("requires")
    return (str(req).strip() or None) if req else None


def install_hint(manifest: dict[str, Any], tool: str) -> Optional[str]:
    """The declared install command for ``tool`` in this adapter, or ``None``."""
    entry = toolchain(manifest).get(tool)
    if isinstance(entry, dict):
        return str(entry.get("install") or "").strip() or None
    return None


def probe_tool(manifest: dict[str, Any], tool: str, cwd: Path, timeout: int = 120) -> bool:
    """Whether ``tool`` answers the probe its toolchain entry declares.

    Runs the adapter's declarative ``probe:`` command (e.g. a ``--version`` check) in ``cwd`` —
    the target project, so project-local shims (``npx``, ``uv run``) resolve as the gates would.
    A tool with no ``probe:`` declared (or no toolchain entry at all) is assumed present: the
    in-gate missing-tool detection still catches it, so nothing is ever silently passed."""
    entry = toolchain(manifest).get(tool)
    if not isinstance(entry, dict):
        return True
    probe = str(entry.get("probe") or "").strip()
    if not probe:
        return True
    return run_cmd(probe, cwd=cwd, timeout=timeout).ok


# --------------------------------------------------------------------------- native-tooling detection
@dataclass(frozen=True)
class DetectRule:
    """One declarative auto-detection probe: data, never core logic.

    ``globs`` match files directly under the target; ``contains`` (optional) additionally requires
    the matched file's text to contain the marker (e.g. ``[tool.pyright]`` in pyproject.toml).
    ``spec`` is the gate block the detected tool would run with."""

    gate: str
    globs: tuple[str, ...]
    tool: str
    spec: dict[str, str]
    contains: str = ""


# Fixed first-match order per gate. The rules are pure data: adding a detectable
# tool is "add a rule", no gate-engine change. Every fix command sits on a fixable gate only
# (it holds by construction).
DETECT_RULES: tuple[DetectRule, ...] = (
    DetectRule(
        gate="format",
        globs=("biome.json",),
        tool="biome",
        spec={
            "check_cmd": "npx --no-install @biomejs/biome format .",
            "fix_cmd": "npx --no-install @biomejs/biome format --write .",
            "parser": "biome",
        },
    ),
    DetectRule(
        gate="format",
        globs=(".prettierrc", ".prettierrc.*", "prettier.config.*"),
        tool="prettier",
        spec={
            "check_cmd": "npx --no-install prettier --check .",
            "fix_cmd": "npx --no-install prettier --write .",
            "parser": "prettier",
        },
    ),
    DetectRule(
        gate="format",
        globs=("go.mod",),
        tool="gofmt",
        spec={"check_cmd": "gofmt -l .", "parser": "gofmt"},
    ),
    # For `format`, a dedicated formatter (biome.json, prettier) is preferred; a project that
    # formats with ESLint and configures no dedicated formatter uses ESLint for `format` too,
    # rather than having biome imposed. The engine never overrides a project's native tooling —
    # biome is only the adapter's last-resort default when a project configures no formatter at all.
    DetectRule(
        gate="format",
        globs=(".eslintrc*", "eslint.config.*"),
        tool="eslint",
        spec={
            "check_cmd": "npx --no-install eslint .",
            "fix_cmd": "npx --no-install eslint --fix .",
            "parser": "eslint",
        },
    ),
    # For `lint`, a dedicated linter config (ESLint) outranks biome's combined config:
    # a biome-formats-and-ESLint-lints repo gets `lint · eslint` with no double-linting.
    DetectRule(
        gate="lint",
        globs=(".eslintrc*", "eslint.config.*"),
        tool="eslint",
        spec={
            "check_cmd": "npx --no-install eslint .",
            "fix_cmd": "npx --no-install eslint --fix .",
            "parser": "eslint",
        },
    ),
    DetectRule(
        gate="lint",
        globs=("biome.json",),
        tool="biome",
        spec={
            "check_cmd": "npx --no-install @biomejs/biome lint .",
            "fix_cmd": "npx --no-install @biomejs/biome lint --write .",
            "parser": "biome",
        },
    ),
    DetectRule(
        gate="types",
        globs=("tsconfig.json",),
        tool="tsc",
        spec={"cmd": "npx --no-install tsc --noEmit", "parser": "tsc"},
    ),
    DetectRule(
        gate="types",
        globs=("pyproject.toml",),
        tool="pyright",
        spec={"cmd": "pyright", "parser": "pyright"},
        contains="[tool.pyright]",
    ),
    DetectRule(
        gate="tests",
        globs=("vitest.config.*",),
        tool="vitest",
        spec={
            "cmd": "npx --no-install vitest run --coverage",
            "parser": "vitest",
            "coverage_format": "lcov",
            "coverage_path": "coverage/lcov.info",
        },
    ),
    DetectRule(
        gate="tests",
        globs=("jest.config.*",),
        tool="jest",
        spec={
            "cmd": "npx --no-install jest --coverage --coverageReporters=lcov",
            "parser": "jest",
            "coverage_format": "lcov",
            "coverage_path": "coverage/lcov.info",
        },
    ),
    DetectRule(
        gate="tests",
        globs=("playwright.config.*",),
        tool="playwright",
        spec={"cmd": "npx --no-install playwright test", "parser": "playwright"},
    ),
    DetectRule(
        gate="tests",
        globs=("go.mod",),
        tool="gotest",
        spec={"cmd": "go test ./...", "parser": "gotest"},
    ),
)


def _rule_matches(rule: DetectRule, target: Path) -> bool:
    """Whether one detection rule's signal files exist under ``target`` (root-level, non-recursive)."""
    for pattern in rule.globs:
        for hit in target.glob(pattern):
            if not hit.is_file():
                continue
            if not rule.contains:
                return True
            try:
                if rule.contains in hit.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:
                continue
    return False


def detect_native_tools(
    target: Path, skip: set[str] | None = None
) -> dict[str, tuple[str, dict[str, str]]]:
    """Probe ``target`` for project-native gate tooling.

    Returns ``{gate: (tool, gate_spec)}`` — the FIRST matching rule per gate wins, in the
    declared table order. Gates in ``skip`` (those ``gates.yaml`` overrides) are never probed:
    the explicit team configuration outranks detection. Deterministic given the
    tree; reads files, runs nothing."""
    skip = skip or set()
    found: dict[str, tuple[str, dict[str, str]]] = {}
    for rule in DETECT_RULES:
        if rule.gate in skip or rule.gate in found:
            continue
        if _rule_matches(rule, target):
            found[rule.gate] = (rule.tool, dict(rule.spec))
    return found


@dataclass
class EffectiveGates:
    """The assembled gate configuration for one run.

    ``manifest`` is the adapter manifest with ``gates.yaml`` overrides and auto-detection applied,
    in that precedence; ``sources`` tags each gate with where its configuration came from
    (``adapter`` | ``gates.yaml`` | ``auto-detected``); ``detected`` names each auto-detected
    gate's tool, for the one startup line."""

    manifest: dict[str, Any]
    sources: dict[str, str]
    detected: dict[str, str]


def effective_gates(settings: Settings, name: str, target: Path) -> EffectiveGates:
    """Assemble the effective per-gate configuration: adapter < auto-detection < ``gates.yaml``.

    Detection runs only for gates ``gates.yaml`` leaves alone. A detected
    tool the adapter already configures for that gate keeps the adapter's richer command
    (coverage settings, shell guards, ``requires:``) — detection confirms, never degrades.
    Configuration replaces tools, never gates."""
    manifest = _read_manifest(settings, name)
    overridden = set(merge_gate_overrides(manifest, load_gate_overrides(settings)))
    gates: dict[str, Any] = manifest.setdefault("gates", {})
    sources = {gate: "gates.yaml" if gate in overridden else "adapter" for gate in gates}
    detected: dict[str, str] = {}
    for gate, (tool, spec) in detect_native_tools(target, skip=overridden).items():
        existing = gates.get(gate) or {}
        existing_tool = str(existing.get("parser") or command_of(existing) or "").split()
        if not existing_tool or existing_tool[0] != tool:
            gates[gate] = spec
        detected[gate] = tool
        sources[gate] = "auto-detected"
    _strip_invalid_fix_cmds(manifest)
    return EffectiveGates(manifest=manifest, sources=sources, detected=detected)
