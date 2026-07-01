"""Third-party dependency compatibility (3PWR-FR-048, 3PWR-NFR-014).

The version comparator and the classifier are pure and pinned directly; the `deps-check` CLI is
driven end to end with an injected probe (no real tools), so the tests are deterministic.
"""

from __future__ import annotations

import pytest

from threepowers import deps
from threepowers.cli import main


# --------------------------------------------------------------------------- comparator
def test_parse_release_ignores_prefix_and_suffix():
    assert deps.parse_release("v0.11.6.dev0") == (0, 11, 6)
    assert deps.parse_release("Version 5.6.3") == (5, 6, 3)
    assert deps.parse_release("no digits here") == ()


@pytest.mark.parametrize(
    "version,spec,ok",
    [
        ("0.11.6.dev0", ">=0.11,<0.12", True),  # prerelease within range (3PWR-FR-048)
        ("0.12.0", ">=0.11,<0.12", False),
        ("0.10.9", ">=0.11,<0.12", False),
        ("8.30.1", ">=8,<9", True),
        ("9.0.0", ">=8,<9", False),
        ("1.10.0", ">=1.10", True),
        ("1.9.0", ">=1.10", False),
        ("2.4", "==2.4", True),
        ("2.4.1", "==2.4", False),
        ("2.4.1", "!=2.5", True),
        ("0.12", "~=0.11", True),
        ("1.0", "~=0.11", False),
    ],
)
def test_satisfies(version, spec, ok):
    assert deps.satisfies(version, spec) is ok


def test_satisfies_rejects_unparseable():
    assert deps.satisfies("", ">=1") is False
    assert deps.satisfies("1.0", "") is False


# --------------------------------------------------------------------------- classifier
def _probe_map(mapping):
    return lambda cmd: mapping.get(cmd)


def test_check_classifies_ok_drift_missing_unknown():
    manifest = {
        "components": [
            {
                "name": "spec-kit",
                "probe": "specify version",
                "supported": ">=0.11,<0.12",
                "on_drift": "block",
            },
            {
                "name": "ruff",
                "probe": "ruff --version",
                "supported": ">=0.6,<0.7",
                "on_drift": "warn",
            },
            {"name": "gone", "probe": "gone --version", "supported": ">=1", "on_drift": "block"},
            {"name": "loose", "probe": "loose --version", "supported": "", "on_drift": "warn"},
        ]
    }
    probe = _probe_map(
        {"specify version": "0.11.6", "ruff --version": "0.9.0", "loose --version": "3.3.3"}
    )
    by = {c.name: c for c in deps.check_dependencies(manifest, probe).checks}
    assert by["spec-kit"].status == deps.OK
    assert by["ruff"].status == deps.DRIFT and not by["ruff"].blocking  # warn never blocks
    assert by["gone"].status == deps.MISSING and by["gone"].blocking  # block + absent
    assert by["loose"].status == deps.UNKNOWN


def test_report_ok_only_when_no_block_policy_failure():
    warn = {
        "components": [
            {"name": "ruff", "probe": "r", "supported": ">=0.6,<0.7", "on_drift": "warn"}
        ]
    }
    assert deps.check_dependencies(warn, _probe_map({"r": "9.9"})).ok is True  # drift, but warn
    block = {
        "components": [
            {"name": "ruff", "probe": "r", "supported": ">=0.6,<0.7", "on_drift": "block"}
        ]
    }
    assert deps.check_dependencies(block, _probe_map({"r": "9.9"})).ok is False


# --------------------------------------------------------------------------- CLI
MANIFEST = """
components:
  - { name: spec-kit, probe: "specify version", supported: ">=0.11,<0.12", on_drift: block }
  - { name: ruff, probe: "ruff --version", supported: ">=0.6,<0.7", on_drift: warn }
"""


@pytest.fixture()
def proj(tmp_path):
    (tmp_path / ".3powers" / "config").mkdir(parents=True)
    (tmp_path / ".3powers" / "config" / "dependencies.yaml").write_text(MANIFEST, encoding="utf-8")
    return tmp_path


def _patch_probe(monkeypatch, mapping):
    monkeypatch.setattr(deps, "run_probe", lambda cmd, root: mapping.get(cmd))


def test_deps_check_passes_known_good(proj, monkeypatch):
    _patch_probe(monkeypatch, {"specify version": "0.11.6", "ruff --version": "0.6.9"})
    assert main(["--root", str(proj), "deps-check"]) == 0


def test_deps_check_blocks_on_block_policy_drift(proj, monkeypatch):
    """3PWR-FR-048: a Spec Kit version outside the supported range fails a `block` policy."""
    _patch_probe(monkeypatch, {"specify version": "0.13.0", "ruff --version": "0.6.9"})
    assert main(["--root", str(proj), "deps-check"]) == 1


def test_deps_check_warn_drift_blocks_only_with_strict(proj, monkeypatch):
    _patch_probe(monkeypatch, {"specify version": "0.11.6", "ruff --version": "9.9.9"})
    assert main(["--root", str(proj), "deps-check"]) == 0  # ruff drift is warn
    assert main(["--root", str(proj), "deps-check", "--strict"]) == 1  # strict escalates warn


def test_deps_check_missing_manifest_is_usage_error(tmp_path):
    (tmp_path / ".3powers").mkdir()
    rc = main(["--root", str(tmp_path), "deps-check", "--manifest", str(tmp_path / "nope.yaml")])
    assert rc == 2
