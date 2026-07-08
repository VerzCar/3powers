"""The per-run feature workspace — one FLAT versioned folder per run, one artifact per producing
stage.

Every lifecycle stage's artifact for a run lies flat in that run's feature folder
``specs/<NNN>-<slug>/``::

    specs/<NNN>-<slug>/
      spec.md          # the specification (the Specify stage's artifact)
      plan.md          # every other producing stage's markdown, flat
      tasks.md
      oracle.md        # a *record* linking the authored oracle tests
      implement.md     # a *record* linking the implementation changes

Both legacy layouts stay resolvable and runnable for existing features:
the older flat layout (identical to the new canonical one) and the legacy split layout
(``spec/spec.md`` + ``artifacts/<step>.md``). Resolution prefers the flat location and falls back to
the split one — never yielding two paths for one stage.

The engine auto-allocates the ``<NNN>-<slug>`` run folder: ``<NNN>`` is the maximum
existing ``NNN-`` prefix under ``specs/`` plus one, zero-padded to three digits, and ``<slug>`` is
derived deterministically from the intent. All functions here are deterministic, offline path
logic — no network, no model, no ledger.
"""

from __future__ import annotations

import re
from pathlib import Path

# The legacy split-layout workspace subfolders — still resolvable, never written.
SPEC_DIR = "spec"
ARTIFACTS_DIR = "artifacts"

# The producing lifecycle steps — exactly the steps that declare a flat markdown artifact in the
# feature folder. Pure gate / verdict / sign-off / advance steps stay ledger-only.
PRODUCING_STEPS: tuple[str, ...] = ("specify", "plan", "tasks", "oracle", "implement")

# Slug bounds: a fixed maximum length, and a fixed fallback token when the intent
# slugifies to empty (e.g. all punctuation).
SLUG_MAX_LEN = 48
SLUG_FALLBACK = "feature"


def spec_path(feature_dir: Path) -> Path | None:
    """The feature's single specification file, whichever layout.

    The canonical flat layout (``<feature>/spec.md`` — identical to the older legacy layout) wins
    over the legacy split layout (``<feature>/spec/spec.md``) when both exist, so resolution always
    yields exactly one spec per feature folder; ``None`` when the folder holds no specification."""
    flat = feature_dir / "spec.md"
    if flat.is_file():
        return flat
    split = feature_dir / SPEC_DIR / "spec.md"
    if split.is_file():
        return split
    return None


def feature_dir_of(spec: Path) -> Path:
    """The feature workspace folder a resolved spec file belongs to (both layouts)."""
    parent = spec.parent
    return parent.parent if parent.name == SPEC_DIR else parent


def artifacts_dir(feature_dir: Path) -> Path:
    """The legacy split layout's artifact subfolder — resolvable for legacy features only."""
    return feature_dir / ARTIFACTS_DIR


def stage_artifact_path(feature_dir: Path, step: str) -> Path:
    """Where a producing step's artifact is WRITTEN — flat in the feature folder.

    ``spec.md`` for ``specify``; ``<step>.md`` for every other step. No ``spec/`` or ``artifacts/``
    subfolder is ever part of a write location."""
    if step == "specify":
        return feature_dir / "spec.md"
    return feature_dir / f"{step}.md"


def find_artifact(feature_dir: Path, step: str) -> Path | None:
    """An existing stage artifact — the flat path when it exists, else the split fallback.

    Never returns two paths for one stage: flat (canonical, also the older legacy location) wins;
    the legacy split location (``artifacts/<step>.md``) stays readable for existing features."""
    if step == "specify":
        return spec_path(feature_dir)
    flat = feature_dir / f"{step}.md"
    if flat.is_file():
        return flat
    split = artifacts_dir(feature_dir) / f"{step}.md"
    if split.is_file():
        return split
    return None


def find_specs(root: Path) -> list[Path]:
    """Every feature's resolved specification under ``<root>/specs`` — one per feature folder.

    Deduplicates by feature folder so a feature never yields two specs (the flat layout wins),
    keeping the exactly-one property across a mixed-layout tree."""
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


def resolve_feature_dir(root: Path, nnn: str) -> Path:
    """Resolve a feature workspace folder from its number: ``specs/<nnn>-*/``.

    ``nnn`` is the folder-name prefix before the first ``-`` (usually the zero-padded run number the
    engine allocated, e.g. ``030``). Exactly one directory must match; the two failure modes carry
    user-facing messages naming the fix:

    Raises:
        FileNotFoundError: no ``specs/<nnn>-*/`` directory exists under ``root``.
        LookupError: more than one directory matches — the prefix is ambiguous.
    """
    specs_root = root / "specs"
    matches = sorted(p for p in specs_root.glob(f"{nnn}-*") if p.is_dir())
    if not matches:
        raise FileNotFoundError(
            f"no feature folder matches specs/{nnn}-*/ — check the number, or pass "
            "--spec <path/to/spec.md>"
        )
    if len(matches) > 1:
        names = ", ".join(f"specs/{p.name}" for p in matches)
        raise LookupError(
            f"'{nnn}' is ambiguous — {len(matches)} feature folders match ({names}); pass "
            "--spec <path/to/spec.md>"
        )
    return matches[0]


# --------------------------------------------------------------------------- run-folder allocation
def slugify(text: str, max_len: int = SLUG_MAX_LEN) -> str:
    """Derive the run folder's slug from the intent — deterministic, pure, idempotent.

    Lowercased; runs of non-alphanumeric characters collapse to a single hyphen; leading/trailing
    hyphens are trimmed; the result is bounded to ``max_len`` with no trailing hyphen; an empty
    result falls back to the fixed token ``feature``. ``slug(slug(x)) == slug(x)``."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or SLUG_FALLBACK


def next_feature_number(specs_root: Path) -> int:
    """The next ``<NNN>`` under ``specs/``: the maximum existing ``NNN-`` prefix plus one."""
    nums = [0]
    if specs_root.is_dir():
        for d in specs_root.iterdir():
            m = re.match(r"(\d+)-", d.name)
            if m:
                nums.append(int(m.group(1)))
    return max(nums) + 1


def feature_folder_name(specs_root: Path, intent: str) -> str:
    """The ``<NNN>-<slug>`` folder name a new run allocates — a pure function of the
    ``specs/`` directory listing and the intent string, byte-identical on any machine."""
    return f"{next_feature_number(specs_root):03d}-{slugify(intent)}"


def allocate_feature_dir(root: Path, intent: str) -> Path:
    """Allocate the new run's feature folder ``specs/<NNN>-<slug>/``.

    Creates the folder, failing fast with :class:`FileExistsError` when the target already exists
    (e.g. two concurrent runs picked the same number) — a folder allocated for a different run is
    never overwritten. Cross-process locking is an explicit non-goal."""
    specs_root = root / "specs"
    target = specs_root / feature_folder_name(specs_root, intent)
    specs_root.mkdir(parents=True, exist_ok=True)
    target.mkdir(exist_ok=False)
    return target
