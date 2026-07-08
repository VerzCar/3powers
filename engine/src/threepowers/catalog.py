"""Per-integration model/label catalog for the role setup.

The catalog is *editable data, not code*: ``.3powers/config/models.yaml`` maps each supported
headless integration to its selectable models — each entry carrying the model id, its model
*family*, and a human-friendly label — plus a documented default. Init and ``3pwr config roles
setup`` read it to present per-role model choices and to fill ``model_family``/``model``/``label``
consistently. A model absent from the catalog (a new or BYOK model) stays selectable via free-form
entry, its family derived where the value encodes it.

Everything here is deterministic and fully offline: the same file bytes always
yield the same catalog, a missing or malformed repo file falls back to the shipped scaffold copy,
and no network or model call is made anywhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml

from .config import Settings

# The bundled fallback — the same file `3pwr init` seeds into .3powers/config/.
_BUNDLED = Path(__file__).resolve().parent / "scaffold" / "config" / "models.yaml"

# Leading-token → family heuristics for free-form entries whose id does not carry a
# "<family>/" prefix (e.g. Copilot's BYOK ids: "claude-opus-4.8", "gpt-5.5").
_TOKEN_FAMILY = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "codex": "openai",
    "gemini": "google",
    "qwen": "qwen",
    "llama": "meta",
    "mistral": "mistral",
    "deepseek": "deepseek",
    "grok": "xai",
}


def _parse(text: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def load_catalog(settings: Optional[Settings] = None) -> dict[str, Any]:
    """The resolved model catalog.

    The repo-local ``.3powers/config/models.yaml`` wins when present and well-formed; otherwise the
    shipped scaffold copy applies, so the catalog never fails a setup (a malformed file degrades to
    the shipped defaults plus free-form entry)."""
    for path in ([settings.models_catalog_path] if settings is not None else []) + [_BUNDLED]:
        try:
            if path.exists():
                data = _parse(path.read_text(encoding="utf-8"))
                if isinstance(data.get("integrations"), dict):
                    return data
        except OSError:
            continue
    return {"integrations": {}}


def integrations(catalog: dict[str, Any]) -> list[str]:
    """The integrations the catalog knows, in file order."""
    intg = catalog.get("integrations")
    return [str(k) for k in intg.keys()] if isinstance(intg, dict) else []


def models_for(catalog: dict[str, Any], integration: str) -> list[dict[str, str]]:
    """The selectable model entries for ``integration`` — each ``{model, family, label}``.

    Tolerant of hand-edits: entries missing a model id are dropped; a missing family is derived
    from the model id where possible; a missing label falls back to the model id."""
    block = (catalog.get("integrations") or {}).get(integration) or {}
    out: list[dict[str, str]] = []
    for raw in block.get("models") or []:
        if not isinstance(raw, dict):
            continue
        model = str(raw.get("model") or "").strip()
        if not model:
            continue
        out.append(
            {
                "model": model,
                "family": str(raw.get("family") or "").strip() or derive_family(model),
                "label": str(raw.get("label") or "").strip() or model,
            }
        )
    return out


def entry_for(catalog: dict[str, Any], integration: str, model: str) -> Optional[dict[str, str]]:
    """The catalog entry for one model under one integration, or ``None`` (free-form fallback)."""
    for entry in models_for(catalog, integration):
        if entry["model"] == model:
            return entry
    return None


def default_for(catalog: dict[str, Any], integration: str) -> Optional[dict[str, str]]:
    """The documented default model entry for ``integration``, or ``None``.

    The block's ``default:`` id is resolved through :func:`entry_for` when listed; an unlisted
    default still yields a usable entry with a derived family."""
    block = (catalog.get("integrations") or {}).get(integration) or {}
    model = str(block.get("default") or "").strip()
    if not model:
        entries = models_for(catalog, integration)
        return entries[0] if entries else None
    return entry_for(catalog, integration, model) or {
        "model": model,
        "family": derive_family(model),
        "label": model,
    }


def derive_family(model: str) -> str:
    """Best-effort model *family* from a model id (pure, offline).

    A ``<family>/<model>`` id yields its prefix; a bare id is mapped by its leading token
    (``claude-…`` → anthropic, ``gpt-…`` → openai, …); anything else yields ``""`` (unknown)."""
    m = (model or "").strip()
    if not m:
        return ""
    if "/" in m:
        return m.split("/", 1)[0].strip()
    token = m.split("-", 1)[0].split(".", 1)[0].strip().lower()
    return _TOKEN_FAMILY.get(token, "")
