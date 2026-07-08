"""Documentation + shipped-config requirements for auto full mode (AUTOX-FR-012…015, NFR-004).

The recorded documentation review, asserted structurally (3PWR-NFR-006 self-application): the
getting-started leads with a complete end-user path, troubleshooting keys on the exact failure phrases
the CLI prints, the CLI reference documents the stable run contract, and no shipped config presents
Spec Kit as current. Skips cleanly when run against a packaged engine without the docs tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

_DOCS = [
    REPO / "docs" / "getting-started.md",
    REPO / "docs" / "troubleshooting.md",
    REPO / "docs" / "cli-reference.md",
    REPO / "docs" / "STATUS.md",
    REPO / ".3powers" / "config" / "roles.yaml",
]

pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _DOCS),
    reason="repo docs tree not present (packaged engine or copied layout)",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- AUTOX-FR-012
def test_getting_started_leads_with_the_end_user_path_in_order():
    """AUTOX-FR-012: the end-user path is present, complete, and in order — install, init in the
    user's own repo, key export, roles + agent CLI (auth belongs to the provider), readiness check,
    run, what success and the two human gates look like — before the maintainer walkthrough."""
    text = _read(REPO / "docs" / "getting-started.md")
    markers = [
        "uv tool install",
        "3pwr init",
        "export THREEPOWERS_SIGNING_KEY_FILE",
        "roles.yaml",
        "authentication belongs to the provider",
        "3pwr ready",
        '3pwr run "<what you want built>" --mode auto',
        "Spec approval",
        "Sign-off",
        "maintainer walkthrough",
    ]
    pos = 0
    for m in markers:
        nxt = text.find(m, pos)
        assert nxt >= 0, f"getting-started is missing the end-user step {m!r} (in order)"
        pos = nxt + len(m)


def test_getting_started_version_string_is_not_stale():
    """AUTOX-FR-012 (acceptance): no hardcoded engine version can drift — the doc shows
    `3pwr --version` without pinning a stale literal output."""
    text = _read(REPO / "docs" / "getting-started.md")
    assert "3pwr --version" in text
    assert not re.search(r"3pwr \d+\.\d+\.\d+", text)  # no pinned literal version can go stale


# --------------------------------------------------------------------------- AUTOX-FR-013
def test_troubleshooting_has_an_entry_per_failure_phrase():
    """AUTOX-FR-013: every failure phrase the CLI can print has a troubleshooting entry with the
    resume command."""
    text = _read(REPO / "docs" / "troubleshooting.md")
    phrases = [
        "unmet prerequisites",  # preflight refusal
        "dispatch failed at",
        "agent timed out after",
        "artifact missing at",
        "gates red",
        "verdict error at",
        "nothing to resume",
    ]
    for phrase in phrases:
        assert phrase in text, f"troubleshooting has no entry keyed to {phrase!r}"
    assert text.count("3pwr run --resume") >= 4  # the resume command rides with the fixes


# --------------------------------------------------------------------------- AUTOX-FR-014
def test_cli_reference_documents_the_stable_run_contract():
    """AUTOX-FR-014: the CLI reference carries the exit-code/JSON-status table (AUTOX-FR-009) and
    the transcript location (AUTOX-FR-008) as stable interfaces — matching the tested behavior."""
    text = _read(REPO / "docs" / "cli-reference.md")
    from threepowers.cli import EXIT_FAIL, EXIT_OK, EXIT_PAUSED, EXIT_SETUP, EXIT_USAGE

    for status, code in [
        ("`done`", EXIT_OK),
        ("`gates_red`", EXIT_FAIL),
        ("`paused_at_gate`", EXIT_PAUSED),
        ("`preflight_failed`", EXIT_SETUP),
        ("`dispatch_failed`", EXIT_SETUP),
        ("`artifact_missing`", EXIT_SETUP),
        ("`verdict_error`", EXIT_SETUP),
    ]:
        assert f"| {status} | `{code}` |" in text, f"contract row for {status} missing/mismatched"
    assert f"| — | `{EXIT_USAGE}` |" in text  # usage keeps its own code
    assert ".3powers/runs/<spec-id>/" in text  # the transcript location, marked stable
    assert "### `ready`" in text  # the standalone readiness command is documented


# --------------------------------------------------------------------------- AUTOX-FR-015
def test_shipped_config_and_templates_carry_no_current_speckit_language():
    """AUTOX-FR-015: a search of shipped .3powers/ config/templates — and the engine's bundled
    scaffold — finds no Spec-Kit reference presented as current (extends the DOCX sweep)."""
    roots = [
        REPO / ".3powers" / "config",
        REPO / ".3powers" / "templates",
        REPO / ".3powers" / "eval",
        REPO / ".3powers" / "memory",
        REPO / "engine" / "src" / "threepowers" / "scaffold",
    ]
    for root in roots:
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix not in (".yaml", ".yml", ".md"):
                continue
            text = _read(f)
            for token in ("Spec Kit", "speckit", "/speckit."):
                assert token not in text, f"{f.relative_to(REPO)} still references {token!r}"


def test_status_is_updated_once_for_autox():
    """AUTOX-NFR-004: docs/STATUS.md remains the single home of implementation status and records
    the AUTOX delivery."""
    text = _read(REPO / "docs" / "STATUS.md")
    assert "AUTOX" in text and "spec 014" in text
