"""Detect when the seeded 3Powers configuration has changed since the last apply (INITX-FR-015/016).

``3pwr init`` (and ``3pwr config apply``) records a fingerprint of the tracked config files. On a later
run, any ``3pwr`` command compares the current config against that fingerprint and WARNS — to stderr, so
stdout / ``--json`` / verdict bytes stay byte-identical (INITX-FR-014) — naming which file changed and
pointing to ``3pwr config apply``. Detection never regenerates an agent file or acts on the change
automatically (INITX-FR-016); re-rendering happens only when the user runs the explicit command.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .config import Settings

# The config files whose drift matters. Editing any of these may make derived artifacts
# (e.g. the judiciary agent model pins) stale.
TRACKED: tuple[str, ...] = (
    "risk-tiers.yaml",
    "roles.yaml",
    "design-oracles.yaml",
    "observability.yaml",
    "onboarding.yaml",
)


def _manifest_path(settings: Settings) -> Path:
    return settings.dir / "config" / ".fingerprint.json"


def fingerprint(settings: Settings) -> dict[str, str]:
    """A content hash per existing tracked config file (absent files are omitted)."""
    out: dict[str, str] = {}
    cfg = settings.dir / "config"
    for name in TRACKED:
        p = cfg / name
        if p.exists():
            out[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def record(settings: Settings) -> None:
    """Persist the current config fingerprint (called by ``init`` and ``config apply``)."""
    path = _manifest_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 1, "files": fingerprint(settings)}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _recorded(settings: Settings) -> dict[str, str] | None:
    path = _manifest_path(settings)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    files = data.get("files")
    return files if isinstance(files, dict) else None


def detect(settings: Settings) -> list[str]:
    """The tracked config files that changed since the recorded fingerprint (INITX-FR-015).

    Covers modified, added, and removed files. Empty when nothing changed, or when no fingerprint has
    been recorded yet (there is nothing to compare against — the first run never warns)."""
    recorded = _recorded(settings)
    if recorded is None:
        return []
    current = fingerprint(settings)
    return sorted(name for name in TRACKED if recorded.get(name) != current.get(name))


def warn_lines(changed: list[str]) -> list[str]:
    """Human warning lines for detected drift (INITX-FR-016) — printed to stderr by the caller."""
    lines = [f"⚠ 3Powers config changed since last apply: {', '.join(changed)}"]
    if "roles.yaml" in changed:
        lines.append("    the judiciary agent model pins (/3pwr.oracle, /3pwr.review) may be stale")
    lines.append("    re-apply with:  3pwr config apply")
    return lines
