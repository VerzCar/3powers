"""The per-feature workspace — one versioned folder per feature, one artifact per stage (PHASE-FR-001).

Each feature gets a single workspace folder under ``specs/`` holding a ``spec/`` subfolder for the
legislative artifact and a sibling ``artifacts/`` folder for every other lifecycle stage's output
(plan, tasks, and subsequent stage artifacts), so *all* stages — driven by ``3pwr run`` or manually —
leave a versioned, checkable output that is the context boundary between sessions::

    specs/<feature>/
      spec/spec.md          # the specification (the only file in spec/ for now)
      artifacts/plan.md     # every other action stage's artifact
      artifacts/tasks.md

Features in the **legacy layout** (``specs/<feature>/spec.md`` directly in the feature folder) remain
resolvable and runnable — the layout applies to features created after delivery, and resolution finds
exactly one specification per feature folder whichever layout it uses (PHASE-FR-001's property). All
functions here are pure path logic — no network, no model, no ledger (3PWR-NFR-001).
"""

from __future__ import annotations

from pathlib import Path

# The two workspace subfolders (PHASE-FR-001). Only the spec lives in the spec folder for now.
SPEC_DIR = "spec"
ARTIFACTS_DIR = "artifacts"


def spec_path(feature_dir: Path) -> Path | None:
    """The feature's single specification file, whichever layout (PHASE-FR-001).

    The workspace layout (``<feature>/spec/spec.md``) wins over the legacy layout
    (``<feature>/spec.md``) when both exist, so resolution always yields exactly one spec per
    feature folder; ``None`` when the folder holds no specification at all."""
    new = feature_dir / SPEC_DIR / "spec.md"
    if new.is_file():
        return new
    legacy = feature_dir / "spec.md"
    if legacy.is_file():
        return legacy
    return None


def feature_dir_of(spec: Path) -> Path:
    """The feature workspace folder a resolved spec file belongs to (both layouts)."""
    parent = spec.parent
    return parent.parent if parent.name == SPEC_DIR else parent


def artifacts_dir(feature_dir: Path) -> Path:
    """The sibling folder every non-spec stage artifact lands in (PHASE-FR-001)."""
    return feature_dir / ARTIFACTS_DIR


def stage_artifact_path(feature_dir: Path, step: str) -> Path:
    """Where a lifecycle action step's artifact belongs in the feature workspace (PHASE-FR-001/002).

    The spec goes in ``spec/spec.md``; every other stage's artifact is ``artifacts/<step>.md``."""
    if step == "specify":
        return feature_dir / SPEC_DIR / "spec.md"
    return artifacts_dir(feature_dir) / f"{step}.md"


def find_artifact(feature_dir: Path, step: str) -> Path | None:
    """An existing stage artifact in the workspace or the legacy flat layout, else ``None``.

    Legacy features keep ``plan.md``/``tasks.md`` directly in the feature folder; both locations
    stay readable (PHASE-FR-001) — the workspace location wins when both exist."""
    if step == "specify":
        return spec_path(feature_dir)
    new = artifacts_dir(feature_dir) / f"{step}.md"
    if new.is_file():
        return new
    legacy = feature_dir / f"{step}.md"
    if legacy.is_file():
        return legacy
    return None


def find_specs(root: Path) -> list[Path]:
    """Every feature's resolved specification under ``<root>/specs`` — one per feature folder.

    Deduplicates by feature folder so a feature never yields two specs (the workspace layout wins),
    keeping the exactly-one property across a mixed-layout tree (PHASE-FR-001)."""
    specs_root = root / "specs"
    if not specs_root.is_dir():
        return []
    seen: dict[Path, Path] = {}
    for candidate in sorted(specs_root.glob("**/spec.md")):
        feature = feature_dir_of(candidate)
        resolved = spec_path(feature)
        if resolved is not None:
            seen[feature] = resolved
    return sorted(set(seen.values()))
