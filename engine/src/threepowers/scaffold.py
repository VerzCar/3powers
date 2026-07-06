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
from pathlib import Path
from typing import Any, Optional

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


_AGENTS_SCAFFOLD_DIR = SCAFFOLD_DIR / "agents"


def bundled_agents() -> list[str]:
    """The agent backends the engine can seed — one per bundled manifest (EXEC-FR-004)."""
    if not _AGENTS_SCAFFOLD_DIR.is_dir():
        return []
    return sorted(p.stem for p in _AGENTS_SCAFFOLD_DIR.glob("*.yaml"))


def seed_agents(settings: Settings) -> dict[str, str]:
    """Copy the bundled agent-backend manifests into ``.3powers/agents/`` (EXEC-FR-004), never clobbering.

    The native executive drives whichever headless coding agent a role points at; seeding the reference
    manifests makes a fresh project runnable with `3pwr run` and no Spec Kit."""
    out: dict[str, str] = {}
    if not _AGENTS_SCAFFOLD_DIR.is_dir():
        return out
    for src in sorted(_AGENTS_SCAFFOLD_DIR.glob("*.yaml")):
        out[src.name] = _copy_if_missing(src, settings.agents_dir / src.name)
    return out


def seed_gitignore(settings: Settings) -> str:
    """Write ``.3powers/.gitignore`` so transient state and stray keys are never committed."""
    return _copy_if_missing(SCAFFOLD_DIR / "gitignore", settings.dir / ".gitignore")


_TEMPLATES_SCAFFOLD_DIR = SCAFFOLD_DIR / "templates" / "agents"


def bundled_stage_templates() -> list[str]:
    """The per-stage agent templates the engine ships — one per dispatched stage (AGENTX-FR-001)."""
    if not _TEMPLATES_SCAFFOLD_DIR.is_dir():
        return []
    return sorted(p.name for p in _TEMPLATES_SCAFFOLD_DIR.glob("*.agent.md"))


def seed_stage_templates(settings: Settings) -> dict[str, str]:
    """Copy the bundled stage agent templates into ``.3powers/templates/agents/`` (AGENTX-FR-009).

    Non-clobbering and idempotent (ONBRD-FR-008/009): a hand-edited template is never overwritten,
    and re-running converges to the same on-disk state. Each template is the editable instruction
    body the executive dispatches for that stage (AGENTX-FR-005)."""
    out: dict[str, str] = {}
    if not _TEMPLATES_SCAFFOLD_DIR.is_dir():
        return out
    for src in sorted(_TEMPLATES_SCAFFOLD_DIR.glob("*.agent.md")):
        out[src.name] = _copy_if_missing(src, settings.stage_templates_dir / src.name)
    return out


def write_onboarding(
    settings: Settings, *, auto_mode: bool, tier: str = "Standard", auto_commit: bool = True
) -> None:
    """Record the autonomy defaults (advisory; ONBRD-FR-005 / INITX-FR-001/006).

    Advisory only: ``auto_mode`` selects the default ``3pwr run`` mode when ``--mode`` is omitted,
    ``tier`` is the tier a *new* spec starts at, and ``auto_commit`` toggles per-stage auto-commit.
    None ever weakens a gate or suppresses a mandatory human gate (ONBRD-NFR-004 / INITX-NFR-002)."""
    path = settings.onboarding_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# 3Powers onboarding preferences.\n"
        "# Advisory only: `auto_mode` selects the default `3pwr run` mode when --mode is omitted,\n"
        "# `tier` is the tier a new spec starts at, and `auto_commit` toggles per-stage auto-commit.\n"
        "# None suppresses a mandatory human gate or weakens a threshold (ONBRD-NFR-004 / INITX-NFR-002).\n"
        "version: 1\n"
        "defaults:\n"
        f"  auto_mode: {str(bool(auto_mode)).lower()}\n"
        f"  tier: {tier}\n"
        f"  auto_commit: {str(bool(auto_commit)).lower()}\n",
        encoding="utf-8",
    )


# The explanatory header rewritten role files keep (AGENTX-FR-017): `require_dispatch` and the
# diversity stance stay explained WHERE THE CONFIG LIVES, even after yaml.safe_dump drops the
# scaffold template's comments. Deterministic bytes — the same write always yields the same file.
_ROLES_HEADER = (
    "# 3Powers role \u2192 agent-backend + model binding (written by `3pwr init` /\n"
    "# `3pwr config roles setup`; safe to hand-edit).\n"
    "# Each role block: model_family, model, integration (an agent backend under\n"
    "# .3powers/agents/), label (a human-friendly name).\n"
    "#\n"
    "# oracle.require_dispatch (default false) is the High-risk read-path-isolation policy\n"
    "# (3PWR-FR-021, epic A3): when true, a High-risk `advance` refuses unless an ISOLATED\n"
    "# HEADLESS-DISPATCH attestation (`3pwr oracle dispatch`) proves the oracle was authored with\n"
    "# the implementation/plan/tasks/contracts physically absent from its worktree. Leave it false\n"
    "# while authoring the oracle in-IDE; enable it once the project adopts headless oracle\n"
    "# authoring at High-risk.\n"
    "#\n"
    "# Model diversity (oracle/reviewer vs coder) is RECOMMENDED, never forced (3PWR-FR-022): a\n"
    "# same-family setup proceeds under a signed, reversible deviation \u2014\n"
    '# `3pwr deviation --gate model_diversity --approver <you> --note "single-model dev"`\n'
    "# (3PWR-FR-057).\n"
    "#\n"
    "# `diversity_level` (default `family`) is how \"diverse enough\" is judged (3PWR-FR-022):\n"
    "#   family \u2014 the oracle and coder must be different model *families*.\n"
    "#   model  \u2014 a different *model* in one family qualifies (e.g. opus vs sonnet).\n"
    "# One BYOK integration (e.g. copilot) can serve several families: pick a coder model in one\n"
    "# family and an oracle model in another and `family` diversity holds with a single CLI.\n"
    "#\n"
    "# `headless_integrations` lists the agent-backend CLIs a LIVE `3pwr run` may dispatch headlessly\n"
    "# (EXEC-FR-015/NFR-003) \u2014 set by `3pwr init`'s multi-select to the CLIs you have installed.\n"
)


def set_role_model(
    settings: Settings,
    role: str,
    *,
    model: str,
    integration: str = "",
    label: str = "",
    model_family: str = "",
    require_dispatch: Optional[bool] = None,
) -> None:
    """Record a role's concrete model + integration in ``roles.yaml`` (INITX-FR-002/003, AGENTX-FR-012).

    Merges into the existing roles configuration (seeding it first if absent), preserving every
    other role and unrelated field (AGENTX-NFR-003). ``model_family`` wins when given (a catalog
    entry's family — AGENTX-FR-015); otherwise the family is derived from the model id where it
    encodes one. For the oracle role, ``require_dispatch`` is always present in the written block
    (AGENTX-FR-012): an explicit value wins, an existing value is preserved, else the documented
    default ``false``. The rewritten file keeps an explanatory header (AGENTX-FR-017)."""
    from .catalog import derive_family

    data = _load_roles_doc(settings)
    roles = data.setdefault("roles", {})
    block = dict(roles.get(role) or {})
    block["model"] = model
    fam = (model_family or derive_family(model)).strip()
    if fam:
        block["model_family"] = fam
    if integration:
        block["integration"] = integration
    if label:
        block["label"] = label
    if role == "oracle":
        if require_dispatch is not None:
            block["require_dispatch"] = bool(require_dispatch)
        else:
            block.setdefault("require_dispatch", False)
    elif require_dispatch is not None:
        block["require_dispatch"] = bool(require_dispatch)
    roles[role] = block
    _save_roles_doc(settings, data)


def _load_roles_doc(settings: Settings) -> dict[str, Any]:
    """The current roles.yaml document, or ``{}`` when absent/empty."""
    path = settings.roles_path
    return (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}) or {}


def _save_roles_doc(settings: Settings, data: dict[str, Any]) -> None:
    """Write roles.yaml with the explanatory header, preserving field order (AGENTX-FR-017)."""
    path = settings.roles_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _ROLES_HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def set_headless_integrations(settings: Settings, names: list[str]) -> None:
    """Record which agent-backend CLIs a live ``3pwr run`` may dispatch (EXEC-FR-015/NFR-003).

    Written to ``roles.yaml`` ``headless_integrations`` (deduped, first-seen order), preserving every
    other field. An empty selection is a no-op — it never wipes the seeded default (AGENTX-NFR-003)."""
    cleaned: list[str] = []
    for n in names:
        v = str(n).strip()
        if v and v not in cleaned:
            cleaned.append(v)
    if not cleaned:
        return
    data = _load_roles_doc(settings)
    data["headless_integrations"] = cleaned
    _save_roles_doc(settings, data)


def set_diversity_level(settings: Settings, level: str) -> None:
    """Record how model diversity is judged — ``family`` or ``model`` (3PWR-FR-022).

    An unrecognized value is ignored (the file keeps its current, valid level)."""
    lvl = str(level or "").strip().lower()
    if lvl not in ("family", "model"):
        return
    data = _load_roles_doc(settings)
    data["diversity_level"] = lvl
    _save_roles_doc(settings, data)


# Notifications config keeps its own short header: yaml.safe_dump drops the scaffold template's
# comments on the first rewrite, and the secret-safety rule (STEER-NFR-002) is worth keeping WHERE
# THE CONFIG LIVES.
_NOTIFY_HEADER = (
    "# 3Powers run notifications (STEER-FR-010). `3pwr run` fires on gate pauses, failures, and\n"
    "# completion. Channels: slack | teams | email | desktop.\n"
    "# SECRETS ARE NEVER STORED HERE (STEER-NFR-002): a slack/teams block names an env var\n"
    "# (`webhook_env`) holding the webhook URL; email reads its password from `password_env`.\n"
    "# Export those before `3pwr run`. An empty `channels:` list means notifications are off.\n"
)


def set_notification_channel(settings: Settings, channel: dict[str, Any]) -> None:
    """Record one run-notification channel in ``notifications.yaml`` (STEER-FR-010).

    Replaces any existing block of the same ``type`` (idempotent re-init), else appends — so a
    second `3pwr init` reconfiguring the same channel never duplicates it. Never writes a secret
    value: slack/teams carry ``webhook_env`` and email ``password_env`` (STEER-NFR-002)."""
    ctype = str(channel.get("type") or "").strip()
    if not ctype:
        return
    path = settings.notifications_config_path
    data = (yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}) or {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("version", 1)
    chans = data.get("channels")
    if not isinstance(chans, list):
        chans = []
    chans = [c for c in chans if not (isinstance(c, dict) and str(c.get("type")) == ctype)]
    chans.append(channel)
    data["channels"] = chans
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _NOTIFY_HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def is_outside_repo(path: Path, root: Path) -> bool:
    """True iff ``path`` resolves OUTSIDE the repository working tree (ONBRD-NFR-001 / SC-003)."""
    from .keys import inside_working_tree  # single custody source of truth (HARDN-FR-002)

    return not inside_working_tree(root, path.expanduser())


# --------------------------------------------------------------------------- agent + Spec Kit readiness


def seed_agents_md(root: Path) -> str:
    """Write a 3Powers-flavoured AGENTS.md starter if the repo has none (ONBRD-FR-016).

    Returns ``'created'`` (a starter was written) or ``'kept'`` (an AGENTS.md already exists — left
    untouched; the caller recommends updating it). The starter names ``3pwr`` as the main command."""
    return _copy_if_missing(SCAFFOLD_DIR / "agents-template.md", root / "AGENTS.md")


def constitution_path(root: Path) -> Path:
    # 3Powers-owned path (DOCX-FR-004; relocated out of the former Spec-Kit tree).
    return root / ".3powers" / "memory" / "constitution.md"


def is_threepowers_constitution(root: Path) -> bool:
    """True iff a constitution exists and looks like the 3Powers separation-of-powers one."""
    path = constitution_path(root)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").lower()
    return "3powers constitution" in text or "separation of powers" in text


def constitution_is_placeholder(root: Path) -> bool:
    """True iff the constitution is an unfilled template (contains ``[PROJECT_NAME]`` etc.).

    A scaffolded-but-unedited constitution is not a *real* one, so a ``force`` overlay may replace it
    (ONBRD-FR-015) — a user-authored one is left alone."""
    path = constitution_path(root)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return "[PROJECT_NAME]" in text or "[PRINCIPLE_" in text


def seed_constitution(root: Path, *, force: bool = False) -> str:
    """Lay the 3Powers constitution at ``.3powers/memory/constitution.md`` (ONBRD-FR-015, DOCX-FR-005).

    Offline and local. By default it writes only when the constitution is absent, never overwriting an
    existing one. With ``force=True`` it also replaces an unfilled *placeholder* constitution — but still
    never a user-authored one. Returns ``'created'``, ``'overlaid'`` (a placeholder was replaced), or
    ``'kept'``."""
    path = constitution_path(root)
    if not path.exists():
        return _copy_if_missing(SCAFFOLD_DIR / "constitution.md", path)
    if force and constitution_is_placeholder(root):
        shutil.copyfile(SCAFFOLD_DIR / "constitution.md", path)
        return "overlaid"
    return "kept"


def detect_ci(root: Path) -> bool:
    """True iff a recognized CI/CD configuration is present (INITX-FR-010).

    Platform-agnostic: a non-empty GitHub Actions workflows directory, or any known CI config file.
    It asserts *presence* only — never that the pipeline is complete or correct (INITX-FR-010)."""
    wf = root / ".github" / "workflows"
    if wf.is_dir() and any(p.is_file() and p.suffix in (".yml", ".yaml") for p in wf.iterdir()):
        return True
    return any(
        (root / m).exists()
        for m in (
            ".gitlab-ci.yml",
            ".circleci/config.yml",
            "Jenkinsfile",
            "azure-pipelines.yml",
            "azure-pipelines.yaml",
            ".drone.yml",
            "bitbucket-pipelines.yml",
            ".travis.yml",
        )
    )


# Placeholder tokens that only the 3Powers AGENTS.md starter carries (agents-template.md).
_AGENTS_STARTER_TOKENS = (
    "[Brief description",
    "[package manager]",
    "[command]",
    "[test command]",
    "[lint command]",
    "[bracketed]",
)


def agents_md_is_starter(root: Path) -> bool:
    """True iff AGENTS.md exists and is still the unfilled 3Powers starter (INITX-FR-011).

    The starter carries bracketed placeholders; any remaining one means it is an unfinished TODO. A
    filled-in or user-authored file has none of them."""
    path = root / "AGENTS.md"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    return any(tok in text for tok in _AGENTS_STARTER_TOKENS)


def readiness(root: Path) -> dict[str, object]:
    """A checklist of what a project needs to run the full agentic workflow (ONBRD-FR-015/016).

    Extended for INITX-FR-009/010/011 with CI/CD presence and whether AGENTS.md is still an unfilled
    starter (a TODO). Model-diversity readiness is computed by the caller (it needs config)."""
    return {
        "agents_md": (root / "AGENTS.md").exists(),
        "agents_md_todo": agents_md_is_starter(root),
        "constitution": is_threepowers_constitution(root),
        "ci": detect_ci(root),
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
