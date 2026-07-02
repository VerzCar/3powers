"""Onboarding scaffold — bundled baseline config + reference adapters (ONBRD-FR-001/003/008).

The engine ships a canonical ``.3powers/`` starter set as package data under ``scaffold/`` so
``3pwr init`` can make an *existing or new* project gate-ready with no network access
(ONBRD-NFR-002). Nothing here writes a private key into the repository (ONBRD-NFR-001):
``create_signer`` always writes the private key to a path the caller has already checked is
OUTSIDE the working tree, and only the public key is committed.

Seeding never clobbers hand-edited files (ONBRD-FR-008) and is therefore idempotent: re-running
converges to the same on-disk state (ONBRD-FR-009).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import yaml

from . import keys
from .config import Settings

SCAFFOLD_DIR = Path(__file__).resolve().parent / "scaffold"
_ADAPTERS_DIR = SCAFFOLD_DIR / "adapters"
_CONFIG_DIR = SCAFFOLD_DIR / "config"

# Stack markers that make a repository read as "already a project" (brownfield). Kept broader than
# the adapter detect-globs so a repo in an unsupported language still reads as brownfield.
_SOURCE_MARKERS = (
    "package.json",
    "tsconfig.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    "composer.json",
)
_SOURCE_DIRS = ("src", "app", "lib", "pkg", "cmd", "internal")


def bundled_languages() -> list[str]:
    """The languages the engine can scaffold — one per bundled adapter manifest (ONBRD-FR-003)."""
    if not _ADAPTERS_DIR.is_dir():
        return []
    return sorted(
        p.name for p in _ADAPTERS_DIR.iterdir() if p.is_dir() and (p / "adapter.yaml").exists()
    )


def _detect_globs(lang: str) -> list[str]:
    data = yaml.safe_load((_ADAPTERS_DIR / lang / "adapter.yaml").read_text(encoding="utf-8")) or {}
    return list(data.get("detect", []))


def detect_language(target: Path) -> Optional[str]:
    """The bundled language whose detect files ALL exist under ``target`` (ONBRD-FR-010).

    Mirrors ``adapters.detect_adapter`` so onboarding's suggested default matches what the gate
    engine will later auto-detect. ``None`` when nothing matches."""
    for lang in bundled_languages():
        globs = _detect_globs(lang)
        if globs and all((target / f).exists() for f in globs):
            return lang
    return None


def has_source(target: Path) -> bool:
    """Brownfield heuristic — does ``target`` already hold a project? (ONBRD-FR-010)

    True if a recognised stack marker is present, or a conventional source directory has content.
    The trust spine and VCS metadata are ignored, so an otherwise-empty repo reads as greenfield."""
    if any((target / m).exists() for m in _SOURCE_MARKERS):
        return True
    for d in _SOURCE_DIRS:
        p = target / d
        if p.is_dir() and any(p.iterdir()):
            return True
    return False


def _copy_if_missing(src: Path, dst: Path) -> str:
    """Copy ``src`` → ``dst`` only when ``dst`` is absent. Returns ``'created'`` or ``'kept'``."""
    if dst.exists():
        return "kept"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    return "created"


def seed_config(settings: Settings) -> dict[str, str]:
    """Copy the baseline config into ``.3powers/config/``, never clobbering (ONBRD-FR-008)."""
    out: dict[str, str] = {}
    for src in sorted(_CONFIG_DIR.glob("*")):
        if src.is_file():
            out[src.name] = _copy_if_missing(src, settings.dir / "config" / src.name)
    return out


def materialize_adapter(settings: Settings, lang: str) -> str:
    """Make the selected adapter available under ``.3powers/adapters/<lang>/`` (ONBRD-FR-008)."""
    src = _ADAPTERS_DIR / lang / "adapter.yaml"
    if not src.exists():
        raise LookupError(
            f"no bundled adapter for language {lang!r}; supported: {bundled_languages()}"
        )
    return _copy_if_missing(src, settings.adapters_dir / lang / "adapter.yaml")


def seed_contract(settings: Settings) -> str:
    """Drop the adapter-authoring contract next to the adapters (points users to adding languages)."""
    return _copy_if_missing(_ADAPTERS_DIR / "CONTRACT.md", settings.adapters_dir / "CONTRACT.md")


def seed_gitignore(settings: Settings) -> str:
    """Write ``.3powers/.gitignore`` so transient state and stray keys are never committed."""
    return _copy_if_missing(SCAFFOLD_DIR / "gitignore", settings.dir / ".gitignore")


def write_onboarding(settings: Settings, *, auto_mode: bool) -> None:
    """Record the autonomy default (advisory only — never bypasses a human gate; ONBRD-FR-005)."""
    path = settings.onboarding_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# 3Powers onboarding preferences.\n"
        "# Advisory only: selects the default `3pwr run` mode when --mode is omitted; it NEVER\n"
        "# suppresses a mandatory human gate (spec approval, sign-off) — ONBRD-NFR-004.\n"
        "version: 1\n"
        "defaults:\n"
        f"  auto_mode: {str(bool(auto_mode)).lower()}\n",
        encoding="utf-8",
    )


def is_outside_repo(path: Path, root: Path) -> bool:
    """True iff ``path`` resolves OUTSIDE the repository working tree (ONBRD-NFR-001 / SC-003)."""
    rp = path.expanduser().resolve()
    rr = root.resolve()
    return rr != rp and rr not in rp.parents


# --------------------------------------------------------------------------- agent + Spec Kit readiness


def seed_agents_md(root: Path) -> str:
    """Write a 3Powers-flavoured AGENTS.md starter if the repo has none (ONBRD-FR-016).

    Returns ``'created'`` (a starter was written) or ``'kept'`` (an AGENTS.md already exists — left
    untouched; the caller recommends updating it). The starter names ``3pwr`` as the main command."""
    return _copy_if_missing(SCAFFOLD_DIR / "agents-template.md", root / "AGENTS.md")


def has_speckit(root: Path) -> bool:
    """Whether Spec Kit is initialised in ``root`` (the ``.specify/`` tree exists)."""
    return (root / ".specify").is_dir()


def specify_installed() -> bool:
    """Whether the Spec Kit ``specify`` CLI is on PATH (needed for the live autonomous lifecycle)."""
    return shutil.which("specify") is not None


def constitution_path(root: Path) -> Path:
    return root / ".specify" / "memory" / "constitution.md"


def is_threepowers_constitution(root: Path) -> bool:
    """True iff a constitution exists and looks like the 3Powers separation-of-powers one."""
    path = constitution_path(root)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").lower()
    return "3powers constitution" in text or "separation of powers" in text


def constitution_is_placeholder(root: Path) -> bool:
    """True iff the constitution is Spec Kit's unfilled template (contains ``[PROJECT_NAME]`` etc.).

    `specify init` writes a placeholder constitution; that is not a *real* constitution, so the explicit
    ``--with-speckit`` overlay may replace it (ONBRD-FR-015) — a user-authored one is left alone."""
    path = constitution_path(root)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return "[PROJECT_NAME]" in text or "[PRINCIPLE_" in text


def seed_constitution(root: Path, *, force: bool = False) -> str:
    """Lay the 3Powers constitution overlay at ``.specify/memory/constitution.md`` (ONBRD-FR-015).

    Offline and local. By default it writes only when the constitution is absent, never overwriting an
    existing one. With ``force=True`` (the explicit ``--with-speckit`` path) it also replaces Spec Kit's
    unfilled *placeholder* constitution — but still never a user-authored one. Returns ``'created'``,
    ``'overlaid'`` (a placeholder was replaced), or ``'kept'``."""
    path = constitution_path(root)
    if not path.exists():
        return _copy_if_missing(SCAFFOLD_DIR / "constitution.md", path)
    if force and constitution_is_placeholder(root):
        shutil.copyfile(SCAFFOLD_DIR / "constitution.md", path)
        return "overlaid"
    return "kept"


def run_specify_init(root: Path, integration: Optional[str] = None) -> int:
    """Run Spec Kit's ``specify init`` in ``root`` for the opt-in ``--with-speckit`` path (ONBRD-FR-015).

    ``specify init`` scaffolds from assets bundled in the specify CLI (no network). stdio is inherited so
    the user can pick an integration interactively when one is not supplied. Returns its exit code."""
    args = ["specify", "init", "--here", "--force"]
    if integration:
        args += ["--integration", integration]
    return subprocess.run(args, cwd=root, check=False).returncode


def readiness(root: Path) -> dict[str, object]:
    """A checklist of what a project needs to run the full agentic workflow (ONBRD-FR-015/016)."""
    return {
        "agents_md": (root / "AGENTS.md").exists(),
        "speckit_dir": has_speckit(root),
        "specify_cli": specify_installed(),
        "constitution": is_threepowers_constitution(root),
    }


def create_signer(
    out: Path, pub: Path, *, force: bool = False
) -> tuple[Optional[keys.SigningKey], str]:
    """Create the Ed25519 signer, refusing to overwrite an existing key unless forced (ONBRD-FR-007).

    Returns ``(key, status)`` with status ``'created'`` (a fresh key was written) or ``'kept'`` (an
    existing key was left intact). The private key is written with owner-only permissions
    (``keys.write_private``); only the public key is committed. The caller MUST have verified that
    ``out`` is outside the repository (``is_outside_repo``) — this never checks the location."""
    out = out.expanduser()
    if out.exists() and not force:
        return None, "kept"
    sk = keys.generate()
    keys.write_private(out, sk)
    keys.write_public(pub, sk.verify_key)
    return sk, "created"
