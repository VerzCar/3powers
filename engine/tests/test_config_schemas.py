"""JSON Schemas for the user-adaptable config + agent-manifest YAMLs.

Every adaptable YAML under ``.3powers/config/`` and ``.3powers/agents/`` carries a
``# yaml-language-server: $schema=…`` header so a user's editor validates and autocompletes it.
These tests assert the schemas exist (in both the live repo tree and the bundled scaffold that
``3pwr init`` ships), are valid JSON, are pointed at by the right YAML header, and — the point of
the feature — that every shipped config actually validates against its own schema.

The engine's runtime deps are only ``cryptography`` + ``PyYAML``; there is no ``jsonschema``
dependency, so validation uses a small self-contained checker covering the JSON Schema subset the
schemas actually use (type/enum/required/properties/items/additionalProperties/oneOf/$ref/$defs).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
LIVE = REPO / ".3powers"
SCAFFOLD = REPO / "engine" / "src" / "threepowers" / "scaffold"

# Guard: skip cleanly under a packaged engine or mutmut's copied layout where the repo tree is absent.
pytestmark = pytest.mark.skipif(
    not (LIVE / "config").is_dir() or not (SCAFFOLD / "config").is_dir(),
    reason="repo .3powers/ + scaffold tree not present (packaged engine or copied layout)",
)

# The adaptable config YAMLs in scope. `semgrep-rules.yml` is intentionally excluded — it is a
# semgrep ruleset, not 3Powers config.
CONFIG_NAMES = [
    "context",
    "dependencies",
    "design-oracles",
    "gates",
    "git",
    "models",
    "notifications",
    "observability",
    "risk-tiers",
    "roles",
    "scan",
    "ui",
    "auto-fix",
]
AGENT_NAMES = ["claude", "codex", "copilot", "copilot-hosted", "opencode", "aider"]

_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _bases() -> list[Path]:
    return [LIVE, SCAFFOLD]


def _yaml_files() -> list[tuple[Path, str]]:
    """(yaml path, expected schema basename) for every in-scope YAML in both trees."""
    out: list[tuple[Path, str]] = []
    for base in _bases():
        for n in CONFIG_NAMES:
            out.append((base / "config" / f"{n}.yaml", f"{n}.schema.json"))
        for n in AGENT_NAMES:
            out.append((base / "agents" / f"{n}.yaml", f"{n}.schema.json"))
    return out


def _schema_files() -> list[Path]:
    out: list[Path] = []
    for base in _bases():
        out += [base / "config" / "schema" / f"{n}.schema.json" for n in CONFIG_NAMES]
        out += [base / "agents" / "schema" / f"{n}.schema.json" for n in AGENT_NAMES]
    return out


# --------------------------------------------------------------------------- (a) files exist


@pytest.mark.parametrize("yaml_path,schema_name", _yaml_files())
def test_every_config_yaml_has_a_schema_file(yaml_path: Path, schema_name: str) -> None:
    """(a) Every in-scope config/agent YAML has a sibling ``schema/<name>.schema.json``."""
    assert yaml_path.exists(), f"missing config: {yaml_path}"
    schema = yaml_path.parent / "schema" / schema_name
    assert schema.exists(), f"missing schema for {yaml_path.name}: {schema}"


# --------------------------------------------------------------------------- (b) schemas parse


@pytest.mark.parametrize("schema_path", _schema_files())
def test_each_schema_is_valid_json_draft_2020_12(schema_path: Path) -> None:
    """(b) Each schema is parseable JSON declaring the draft 2020-12 ``$schema``."""
    data = json.loads(schema_path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert data.get("$schema") == _DRAFT, f"{schema_path} must declare draft 2020-12"
    assert data.get("type") == "object"


# --------------------------------------------------------------------------- (c) header points at schema


@pytest.mark.parametrize("yaml_path,schema_name", _yaml_files())
def test_yaml_header_points_at_existing_schema(yaml_path: Path, schema_name: str) -> None:
    """(c) The YAML's first line is a yaml-language-server ``$schema`` pointing at an existing file."""
    first = yaml_path.read_text(encoding="utf-8").splitlines()[0]
    expected = f"# yaml-language-server: $schema=./schema/{schema_name}"
    assert first.strip() == expected, f"{yaml_path}: header is {first!r}, expected {expected!r}"
    assert (yaml_path.parent / "schema" / schema_name).exists()


# --------------------------------------------------------------------------- minimal validator


def _validate(instance: Any, sch: dict[str, Any], root: dict[str, Any], path: str) -> list[str]:
    """Validate ``instance`` against the JSON Schema subset the config schemas use.

    Supports: ``$ref`` (local ``#/...`` pointers), ``type`` (incl. a list of types and null),
    ``enum``, ``properties``, ``required``, ``items``, ``additionalProperties`` (bool or schema),
    ``oneOf``. Returns a list of human-readable error strings (empty when valid).
    """
    errors: list[str] = []

    if "$ref" in sch:
        ref = sch["$ref"]
        assert ref.startswith("#/"), f"only local refs supported, got {ref}"
        target: Any = root
        for part in ref[2:].split("/"):
            target = target[part]
        return _validate(instance, target, root, path)

    if "oneOf" in sch:
        matches = sum(1 for sub in sch["oneOf"] if not _validate(instance, sub, root, path))
        if matches != 1:
            errors.append(f"{path}: matched {matches} of oneOf schemas (expected exactly 1)")
        return errors

    t = sch.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_type_ok(instance, one) for one in types):
            errors.append(f"{path}: expected type {t}, got {type(instance).__name__}")
            return errors

    if "enum" in sch and instance not in sch["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {sch['enum']}")

    if isinstance(instance, dict) and (t == "object" or "properties" in sch):
        props = sch.get("properties", {})
        for req in sch.get("required", []):
            if req not in instance:
                errors.append(f"{path}: missing required key {req!r}")
        addl = sch.get("additionalProperties", True)
        for key, val in instance.items():
            if key in props:
                errors += _validate(val, props[key], root, f"{path}.{key}")
            elif isinstance(addl, dict):
                errors += _validate(val, addl, root, f"{path}.{key}")
            elif addl is False:
                errors.append(f"{path}: unexpected key {key!r}")

    if isinstance(instance, list) and "items" in sch:
        for i, item in enumerate(instance):
            errors += _validate(item, sch["items"], root, f"{path}[{i}]")

    return errors


def _type_ok(instance: Any, jtype: str) -> bool:
    if jtype == "null":
        return instance is None
    if jtype == "boolean":
        return isinstance(instance, bool)
    if jtype == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if jtype == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if jtype == "string":
        return isinstance(instance, str)
    if jtype == "array":
        return isinstance(instance, list)
    if jtype == "object":
        return isinstance(instance, dict)
    return True


def test_the_minimal_validator_rejects_a_known_bad_instance() -> None:
    """A self-check so the validator's negative path is exercised (it must catch real violations)."""
    sch = json.loads((LIVE / "config" / "schema" / "ui.schema.json").read_text(encoding="utf-8"))
    bad = {"color_mode": "rainbow"}  # not in the enum
    assert _validate(bad, sch, sch, "ui.yaml"), "validator failed to reject an out-of-enum value"


# --------------------------------------------------------------------------- (d) shipped config validates


@pytest.mark.parametrize("yaml_path,schema_name", _yaml_files())
def test_shipped_config_validates_against_its_schema(yaml_path: Path, schema_name: str) -> None:
    """(d) Every shipped config validates against its schema (a schema must never reject a config
    the engine accepts)."""
    schema = json.loads((yaml_path.parent / "schema" / schema_name).read_text(encoding="utf-8"))
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if data is None:  # an all-comments file (e.g. gates.yaml) is a valid empty config
        return
    errors = _validate(data, schema, schema, yaml_path.name)
    assert not errors, "\n".join(errors)
