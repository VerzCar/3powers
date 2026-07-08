"""DOCX (spec 012) — docs truth-up & de-cruft: truth/absence verifications (DOCX-FR-001…005, NFR-002).

3Powers self-applies (3PWR-NFR-006): these bind each DOCX functional requirement to a deterministic
truth/absence check (DOCX-SC-005). They locate the repo root relative to the engine and skip cleanly when
the repo tree is absent (packaged engine, or mutmut's copied `mutants/` layout — same guard rationale as
test_oss_readiness.py: under the copied layout `parents[2]` resolves to `engine/`).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from threepowers import scaffold
from threepowers.cli import build_parser, main

REPO = Path(__file__).resolve().parents[2]
ENGINE_SRC = REPO / "engine" / "src" / "threepowers"
_MARKERS = [REPO / "README.md", REPO / "docs" / "STATUS.md", ENGINE_SRC / "cli" / "__init__.py"]

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _MARKERS),
    reason="repo tree not present (packaged engine or copied layout)",
)


def _init(root: Path, key: Path) -> int:
    return main(
        ["--root", str(root), "init", "--yes", "--language", "python", "--key-path", str(key)]
    )


# --------------------------------------------------------------------------- DOCX-FR-001
def test_docx_fr001_status_describes_native_executive_not_speckit_dependency():
    """DOCX-FR-001: STATUS describes the native executive + Spec Kit as removed, with no dependency claim."""
    t = (REPO / "docs" / "STATUS.md").read_text(encoding="utf-8")
    assert "native executive" in t.lower()
    assert "removed" in t.lower() and "SLIM" in t
    norm = t.lower().replace("*", "").replace("`", "")
    assert "layers on github spec kit" not in norm


# --------------------------------------------------------------------------- DOCX-FR-003
def test_docx_fr003_agentpins_and_configdrift_are_removed():
    """DOCX-FR-003: the retired modules cannot be imported (removed with their callers/tests)."""
    assert importlib.util.find_spec("threepowers.agentpins") is None
    assert importlib.util.find_spec("threepowers.configdrift") is None


def test_docx_fr003_config_apply_command_is_gone():
    """DOCX-FR-003: the `3pwr config apply` command (the pin-render/drift caller) no longer exists."""
    with pytest.raises(SystemExit):  # argparse rejects an unknown subcommand
        build_parser().parse_args(["config", "apply"])


# --------------------------------------------------------------------------- DOCX-FR-004 / NFR-002
def test_docx_fr004_no_specify_tree_and_constitution_relocated():
    """DOCX-FR-004: no `.specify/` tree remains; the constitution lives under the 3Powers-owned path."""
    assert not (REPO / ".specify").exists()
    assert (REPO / ".3powers" / "memory" / "constitution.md").exists()
    # the single engine reader points at the new location
    assert scaffold.constitution_path(REPO) == REPO / ".3powers" / "memory" / "constitution.md"


def test_docx_nfr002_no_specify_path_in_engine_runtime():
    """DOCX-NFR-002 (property): no engine runtime code path references a `.specify/` path or a Spec-Kit CLI."""
    for py in ENGINE_SRC.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert ".specify" not in text, f"{py.name} references .specify"
        assert "specify workflow" not in text, f"{py.name} references the Spec Kit CLI"


# --------------------------------------------------------------------------- DOCX-FR-005
def test_docx_fr005_init_seeds_constitution_at_new_path(tmp_path):
    """DOCX-FR-005: a fresh `3pwr init` seeds the constitution at `.3powers/memory/`, creating no `.specify/`."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, key=tmp_path / "k.key") == 0
    assert (root / ".3powers" / "memory" / "constitution.md").exists()
    assert not (root / ".specify").exists()
    assert scaffold.is_threepowers_constitution(root)


def test_docx_fr005_init_is_non_destructive(tmp_path):
    """DOCX-FR-005: a re-run never clobbers a hand-edited constitution (ONBRD-FR-008/015)."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, key=tmp_path / "k.key") == 0
    cpath = root / ".3powers" / "memory" / "constitution.md"
    cpath.write_text("# Custom Constitution SENTINEL\n", encoding="utf-8")
    assert _init(root, key=tmp_path / "k.key") == 0
    assert "SENTINEL" in cpath.read_text(encoding="utf-8")
