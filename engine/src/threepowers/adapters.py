"""Language adapters — the polyglot plugin contract (3PWR-FR-027, 3PWR-NFR-007).

An adapter is a *declarative manifest* (``.3powers/adapters/<lang>/adapter.yaml``)
that maps each gate to a tool invocation and the standard format of its output.
Adding a language is therefore "add a manifest" — no change to the gate-engine core
(3PWR-NFR-007). The core never assumes a language beyond what the adapter declares
(3PWR-FR-045).
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


def load_adapter(settings: Settings, name: str) -> dict[str, Any]:
    path = settings.adapters_dir / name / "adapter.yaml"
    if not path.exists():
        raise FileNotFoundError(f"adapter manifest not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


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
