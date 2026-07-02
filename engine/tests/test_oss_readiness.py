"""Open-source launch-readiness requirements (OSSRD-FR-001…011, NFR-001…003).

3Powers self-applies (3PWR-NFR-006): these tests verify the OSSRD documentation/CI requirements the way
a gate would — by asserting structural properties of the repo's user-facing docs and workflow. They
locate the repo root relative to the engine and skip cleanly when the docs tree is absent (packaged
engine, or mutmut's copied layout).

OSSRD-NFR-001 (honesty invariant): the repeatable check is THIS suite — any contributor re-runs it from
the repo alone (`uv run pytest tests/test_oss_readiness.py`). What it cannot mechanize (a full
claim-by-claim read of README against STATUS) remains the documented human review step of the spec.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from threepowers.verdict import GATE_ORDER

REPO = Path(__file__).resolve().parents[2]
README = REPO / "README.md"
STATUS = REPO / "docs" / "STATUS.md"
GETTING_STARTED = REPO / "docs" / "getting-started.md"
CONCEPTS = REPO / "docs" / "concepts.md"
GLOSSARY = REPO / "docs" / "glossary.md"
TROUBLESHOOTING = REPO / "docs" / "troubleshooting.md"
AGENTS = REPO / "AGENTS.md"
CLAUDE = REPO / "CLAUDE.md"
CONTRIBUTING = REPO / "CONTRIBUTING.md"
GOVERNANCE = REPO / "GOVERNANCE.md"
CHANGELOG = REPO / "CHANGELOG.md"
WORKFLOW = REPO / ".github" / "workflows" / "ci.yml"

# The entry documents a newcomer meets first (OSSRD-FR-005), plus the agent-guidance docs this spec
# de-duplicated — the set the gate-name and status-link checks run against.
_ENTRY_DOCS = [README, GETTING_STARTED, CONCEPTS]
_DOC_SET = [
    README,
    STATUS,
    GETTING_STARTED,
    CONCEPTS,
    GLOSSARY,
    TROUBLESHOOTING,
    AGENTS,
    CLAUDE,
    CONTRIBUTING,
    GOVERNANCE,
    CHANGELOG,
    WORKFLOW,
]

# Same guard rationale as test_docs_onboarding.py: under a copied layout (mutmut) a different repo root
# resolves; requiring the whole doc set distinguishes the true root from a stray README.
pytestmark = pytest.mark.skipif(
    not all(p.exists() for p in _DOC_SET),
    reason="repo docs tree not present (packaged engine or copied layout)",
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- FR-001
def test_readme_scopes_sanitized_headless_claim_to_the_oracle_leg():
    """OSSRD-FR-001: every README paragraph claiming a sanitized/headless workspace names the oracle."""
    for para in _read(README).split("\n\n"):
        low = para.lower()
        if "sanitized" in low or "headless" in low:
            assert "oracle" in low, f"unscoped sanitized/headless claim:\n{para}"


def test_readme_names_autonomy_dependencies_before_first_run_command():
    """OSSRD-FR-001: Spec Kit + a coding-agent integration are named before the first `3pwr run`."""
    t = _read(README)
    first_run = t.find("3pwr run")
    assert first_run != -1
    assert 0 <= t.find("github/spec-kit") < first_run
    assert 0 <= t.lower().find("coding-agent integration") < first_run


# --------------------------------------------------------------------------- FR-002
def test_entry_documents_source_the_spec_kit_pin_upstream():
    """OSSRD-FR-002: README, AGENTS.md, and getting-started each source the pin to github/spec-kit."""
    for doc in (README, AGENTS, GETTING_STARTED):
        assert "github/spec-kit" in _read(doc), f"{doc.name}: Spec Kit pin left unsourced"
    # the reference doc carries the tagged-install command they point at
    assert "uv tool install specify-cli --from git+https://github.com/github/spec-kit.git" in _read(
        REPO / "docs" / "references" / "speckit.md"
    )


# --------------------------------------------------------------------------- FR-003
def test_getting_started_opens_with_tiered_prerequisites():
    """OSSRD-FR-003: prerequisites (hard/conditional/optional) precede any install command."""
    t = _read(GETTING_STARTED)
    i_prereq = t.find("## Prerequisites")
    assert i_prereq != -1
    assert i_prereq < t.find("uv tool install ./engine"), "install precedes the prerequisites section"
    section = t[i_prereq : t.find("## 1.")]
    assert "Hard requirements" in section
    assert "Conditional requirements" in section
    assert "Optional scanners" in section
    # each optional scanner names its quarantine behavior
    for tool in ("betterleaks", "osv-scanner", "semgrep"):
        assert tool in section
    assert section.count("quarantined") >= 3


def test_gates_only_path_requires_no_speckit_or_agent():
    """OSSRD-FR-003: the gates-only path lists no Spec Kit or agent-integration requirement."""
    t = _read(GETTING_STARTED)
    row = next(ln for ln in t.splitlines() if "Gates-only" in ln)
    assert "no Spec Kit" in row and "no agent integration" in row


# --------------------------------------------------------------------------- FR-004
def test_ci_workflow_runs_lint_types_tests_and_ledger_verify_on_prs():
    """OSSRD-FR-004: the CI workflow gates PRs to main with the engine suites + offline verify."""
    w = _read(WORKFLOW)
    assert "pull_request" in w
    for step in ("ruff check", "mypy src", "pytest", "verify"):
        assert step in w, f"CI workflow is missing the {step!r} step"


def test_contributing_documents_the_identical_local_commands():
    """OSSRD-FR-004: CONTRIBUTING documents the same commands CI runs."""
    c = _read(CONTRIBUTING)
    for cmd in ("uv run ruff check .", "uv run mypy src", "uv run pytest", "3pwr verify"):
        assert cmd in c, f"CONTRIBUTING is missing the {cmd!r} command"


# --------------------------------------------------------------------------- FR-005
def test_glossary_defines_the_required_terms_of_art():
    """OSSRD-FR-005: a glossary exists defining at minimum the spec's listed terms."""
    g = _read(GLOSSARY)
    for heading in (
        "## Trust spine",
        "## Oracle",
        "## Phase A / Phase B",
        "## Residual",
        "## Assumptions (A1–A6)",
        "## Verdict",
        "## Quarantine",
        "## Work kind",
        "## Requirement-ID scheme",
    ):
        assert heading in g, f"glossary is missing {heading!r}"
    assert "**A3" in g  # A3 has an explicit definition, not just a mention


def test_entry_documents_link_the_glossary_and_a3_resolves():
    """OSSRD-FR-005: entry docs link the glossary; every user-facing "A3" resolves to a definition."""
    for doc in _ENTRY_DOCS:
        assert "glossary.md" in _read(doc), f"{doc.name} does not link the glossary"
    a3 = re.compile(r"\bA3\b")
    for doc in _ENTRY_DOCS:
        for ln in _read(doc).splitlines():
            if a3.search(ln):
                assert "glossary.md" in ln, f"{doc.name}: bare 'A3' without a definition link: {ln}"


# --------------------------------------------------------------------------- FR-006
def test_status_has_one_home_and_the_other_docs_only_link():
    """OSSRD-FR-006: per-plan status lives only in docs/STATUS.md; README/AGENTS/CLAUDE link to it."""
    per_plan = re.compile(r"\*\*Plan 0\d\d")
    for doc in (README, AGENTS, CLAUDE):
        t = _read(doc)
        assert "docs/STATUS.md" in t, f"{doc.name} does not link docs/STATUS.md"
        assert not per_plan.search(t), f"{doc.name} still carries a per-plan status narrative"


def test_status_opens_with_milestone_date_and_residual_summary():
    """OSSRD-FR-006: STATUS opens with the milestone, validation date, and open residuals."""
    head = "\n".join(_read(STATUS).splitlines()[:30])
    assert "Current milestone" in head
    assert "Last validated" in head
    assert "Open residuals" in head
    assert re.search(r"\b20\d\d-\d\d-\d\d\b", head), "no ISO validation date in the summary"


# --------------------------------------------------------------------------- FR-007
def test_gate_names_match_the_verdicts_canonical_identifiers():
    """OSSRD-FR-007: one spelling per gate — no hyphenated variant of a canonical gate name remains."""
    docs = [*_ENTRY_DOCS, AGENTS, CLAUDE]
    variants = {g.replace("_", "-") for g in GATE_ORDER if "_" in g}
    for doc in docs:
        low = _read(doc).lower()
        for bad in variants:
            assert bad not in low, f"{doc.name} uses non-canonical gate spelling {bad!r}"
    # and the canonical suite is actually named in the README
    assert "spec_conformance" in _read(README)


# --------------------------------------------------------------------------- FR-008
def test_install_story_documents_only_working_paths():
    """OSSRD-FR-008: no 'coming soon' install promise; clone-and-install is the first command."""
    t = _read(README)
    assert "coming soon" not in t.lower()
    first_block = t.split("```bash", 1)[1].split("```", 1)[0]
    first_cmd = next(ln for ln in first_block.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    assert first_cmd.strip().startswith("git clone"), f"quickstart's first command is {first_cmd!r}"


# --------------------------------------------------------------------------- FR-009
def test_platform_policy_and_maintainer_path_are_documented():
    """OSSRD-FR-009: CONTRIBUTING states the platform policy; GOVERNANCE the maintainer path."""
    c = _read(CONTRIBUTING)
    for word in ("macOS", "Linux", "WSL2"):
        assert word in c, f"CONTRIBUTING platform statement is missing {word!r}"
    assert "## Becoming a maintainer" in _read(GOVERNANCE)


# --------------------------------------------------------------------------- FR-010
def test_troubleshooting_covers_the_required_failures_with_fixes():
    """OSSRD-FR-010: each required failure names its symptom, cause, and resolving command."""
    t = _read(TROUBLESHOOTING)
    for heading in (
        "## Signing key not found",
        "## Spec Kit version mismatch",
        "quarantined",  # the missing-scanner entry
        "`specify` not installed",
    ):
        assert heading in t, f"troubleshooting is missing {heading!r}"
    # every entry follows the symptom / cause / fix structure, each with a resolving command block
    assert t.count("**Symptom**") >= 4
    assert t.count("**Cause**") >= 4
    assert t.count("**Fix**") >= 4
    for cmd in ("3pwr keygen", "3pwr deps-check", "uv tool install specify-cli", "osv-scanner"):
        assert cmd in t


# --------------------------------------------------------------------------- FR-011
def test_changelog_and_readme_agree_on_the_tagged_milestone():
    """OSSRD-FR-011: the CHANGELOG references the release tag; README names the same milestone."""
    ch = _read(CHANGELOG)
    assert "## [0.5.0]" in ch
    assert "releases/tag/v0.5.0" in ch
    status_section = _read(README).split("## Status", 1)[1]
    assert "v0.5" in status_section


# --------------------------------------------------------------------------- NFR-001
def test_entry_docs_carry_no_unqualified_residual_capability_claims():
    """OSSRD-NFR-001: no doc claims a residual capability without inline qualification.

    The phrases below are exactly the audited overclaims: capabilities docs/STATUS.md marks residual
    (full unattended execution, a fully headless coder leg) stated as delivered. The scoped versions
    ("stops only at the two human gates", oracle-leg headless) remain legitimate.
    """
    assert "Open residuals" in _read(STATUS)  # the residual list this invariant is checked against
    forbidden = (
        "everything in between runs unattended",
        "fully autonomous",
        "fully headless",
        "no human involvement",
    )
    for doc in (*_ENTRY_DOCS, AGENTS, CLAUDE):
        low = _read(doc).lower()
        for phrase in forbidden:
            assert phrase not in low, f"{doc.name}: unqualified residual claim {phrase!r}"


# --------------------------------------------------------------------------- NFR-002
def test_ci_workflow_carries_the_ten_minute_budget():
    """OSSRD-NFR-002: the workflow enforces the 10-minute bound on hosted runners."""
    assert "timeout-minutes: 10" in _read(WORKFLOW)


# --------------------------------------------------------------------------- NFR-003
def test_readme_body_stays_within_the_prose_budget():
    """OSSRD-NFR-003: ≤120 lines of prose/tables, excluding badges, fenced blocks, license footer."""
    lines = _read(README).splitlines()
    count, fenced = 0, False
    for ln in lines:
        s = ln.strip()
        if s.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not s:
            continue
        if s.startswith("[!["):  # badges
            continue
        if s == "## License":
            break
        count += 1
    assert count <= 120, f"README carries {count} prose/table lines (budget: 120)"


def test_full_language_matrix_lives_under_docs():
    """OSSRD-NFR-003: the full per-language tooling matrix resides under docs/, linked from README."""
    gs = _read(GETTING_STARTED)
    assert "## Supported languages & tooling matrix" in gs
    assert "| Format | Lint | Types |" in gs.replace("**", "")
    assert "supported-languages--tooling-matrix" in _read(README)
