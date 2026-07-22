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

import ast
import re
import tomllib
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
def test_readme_scopes_sanitized_workspace_claim_to_the_oracle_leg():
    """OSSRD-FR-001: every README paragraph claiming a *sanitized* workspace names the oracle.

    Read-path isolation (the sanitized worktree) is oracle-specific. "Headless" is no longer
    oracle-only — the native executive (EXEC/SLIM, DOCX truth-up) dispatches every agent headlessly."""
    for para in _read(README).split("\n\n"):
        low = para.lower()
        if "sanitized" in low:
            assert "oracle" in low, f"unscoped sanitized-workspace claim:\n{para}"


def test_readme_names_autonomy_dependency_before_first_run_command():
    """OSSRD-FR-001 (DOCX truth-up): a coding-agent integration — the only autonomy dependency now
    that the executive is native (EXEC/SLIM) — is named before the first `3pwr run`."""
    t = _read(README)
    first_run = t.find("3pwr run")
    assert first_run != -1
    assert 0 <= t.lower().find("coding-agent integration") < first_run


# --------------------------------------------------------------------------- FR-002 (DOCX-FR-002)
def test_entry_docs_carry_no_speckit_dependency_claim():
    """DOCX-FR-002 (truths up OSSRD-FR-002): README, AGENTS, and CLAUDE present Spec Kit as neither a
    dependency nor a required lifecycle step. Any surviving mention is historical/optional interop, so
    only the dependency *phrasings* are forbidden — not the words "Spec Kit" themselves."""
    forbidden = (
        "layers on github spec kit",
        "built on github spec kit",
        "built on spec kit",
        "driven by github spec kit",
        "driven by spec kit",
        "composes github spec kit",
        "composes spec kit",
        "composing spec kit",
        "spec kit's workflow run",
        "specify workflow run",
        "the specify cli",
        "needs the specify",
    )
    for doc in (README, AGENTS, CLAUDE):
        norm = _read(doc).lower().replace("*", "").replace("`", "")
        for phrase in forbidden:
            assert phrase not in norm, f"{doc.name}: residual Spec-Kit dependency claim {phrase!r}"


# --------------------------------------------------------------------------- FR-003
def test_getting_started_opens_with_tiered_prerequisites():
    """OSSRD-FR-003: prerequisites (hard/conditional/optional) precede any install command."""
    t = _read(GETTING_STARTED)
    i_prereq = t.find("## Prerequisites")
    assert i_prereq != -1
    assert i_prereq < t.find("uv tool install ./engine"), (
        "install precedes the prerequisites section"
    )
    section = t[i_prereq : t.find("## 1.")]
    assert "Hard requirements" in section
    assert "Conditional requirements" in section
    assert "Optional scanners" in section
    # each optional scanner names its quarantine behavior
    for tool in ("betterleaks", "osv-scanner", "semgrep"):
        assert tool in section
    assert section.count("quarantined") >= 3


def test_gates_only_path_requires_no_agent_integration():
    """OSSRD-FR-003 (DOCX truth-up): the gates-only path lists no agent-integration requirement (and,
    post-SLIM, no substrate at all)."""
    t = _read(GETTING_STARTED)
    row = next(ln for ln in t.splitlines() if "Gates-only" in ln)
    assert "no agent integration" in row


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
    """OSSRD-FR-008: no 'coming soon' install promise; the quickstart's first command is a real,
    working install of the published engine (`uv tool install 3powers`)."""
    t = _read(README)
    assert "coming soon" not in t.lower()
    first_block = t.split("```bash", 1)[1].split("```", 1)[0]
    first_cmd = next(
        ln for ln in first_block.splitlines() if ln.strip() and not ln.lstrip().startswith("#")
    )
    assert first_cmd.strip().startswith("uv tool install 3powers"), (
        f"quickstart's first command is {first_cmd!r}"
    )


# --------------------------------------------------------------------------- FR-009
def test_platform_policy_and_maintainer_path_are_documented():
    """OSSRD-FR-009: CONTRIBUTING states the platform policy; GOVERNANCE the maintainer path."""
    c = _read(CONTRIBUTING)
    for word in ("macOS", "Linux", "WSL2"):
        assert word in c, f"CONTRIBUTING platform statement is missing {word!r}"
    assert "## Becoming a maintainer" in _read(GOVERNANCE)


# --------------------------------------------------------------------------- FR-010
def test_troubleshooting_covers_the_required_failures_with_fixes():
    """OSSRD-FR-010 (DOCX truth-up): each required failure names its symptom, cause, and resolving
    command. The Spec-Kit failures were replaced by the native-executive one (no agent CLI on PATH)."""
    t = _read(TROUBLESHOOTING)
    for heading in (
        "## Signing key not found",
        "## Coding-agent CLI not found",
        "quarantined",  # the missing-scanner entry
    ):
        assert heading in t, f"troubleshooting is missing {heading!r}"
    # every entry follows the symptom / cause / fix structure, each with a resolving command block
    assert t.count("**Symptom**") >= 4
    assert t.count("**Cause**") >= 4
    assert t.count("**Fix**") >= 4
    for cmd in ("3pwr keygen", "3pwr deps-check", "osv-scanner"):
        assert cmd in t


# --------------------------------------------------------------------------- FR-011
def test_changelog_and_readme_agree_on_the_tagged_milestone():
    """OSSRD-FR-011: the CHANGELOG references the release tag; README names the same milestone."""
    ch = _read(CHANGELOG)
    assert "## [1.0.0-rc.1]" in ch
    assert "releases/tag/v1.0.0-rc.1" in ch
    status_section = _read(README).split("## Status", 1)[1]
    assert "v1.0" in status_section


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


# --------------------------------------------------------------- public-text hygiene (PUBTXT)
#
# Internal requirement IDs, epic letters, and plan/spec numbers never appear in end-user-readable
# text — CLI help and messages, engine source docstrings and comments, docs/ prose, or the scaffold
# assets shipped by `3pwr init`. See AGENTS.md, "Open-source readiness". Format teaching uses the
# reserved DEMO- example namespace or bare FR-###/NFR-###.

# The namespaced form only: bare FR-###/NFR-### stays legal (it is how scaffold templates teach end
# users to number their own requirements).
_NAMESPACED_ID = re.compile(r"\b[A-Z0-9][A-Z0-9]{2,}-(?:FR|NFR)-[0-9]{2,3}\b")
_EPIC_REF = re.compile(r"\(epic [A-Z][0-9]\)")

# Frozen allowlist (see the AGENTS.md rule): the reserved DEMO- example namespace, plus explicit
# placeholder namespaces used to teach the ID format. Extending this list is a deliberate,
# reviewed one-line change.
_ALLOWED_NAMESPACES = frozenset({"DEMO", "SPECID"})

_TEXT_SUFFIXES = {".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".cfg", ".ini", ".json"}

ENGINE_SRC = REPO / "engine" / "src" / "threepowers"
DOCS_DIR = REPO / "docs"


def _hygiene_surfaces() -> list[Path]:
    """The end-user-readable surfaces the no-internal-IDs rule scans.

    docs/ minus STATUS.md (the sanctioned traceability document), the root-level public files,
    and the whole engine source tree including the scaffold assets `3pwr init` ships.
    engine/tests/ is excluded by construction (requirement-ID declarations live there for the
    spec-conformance gate).
    """
    files: list[Path] = [README, CONTRIBUTING, GOVERNANCE, CHANGELOG]
    files.extend(
        p
        for p in DOCS_DIR.rglob("*")
        if p.is_file() and p.name != "STATUS.md" and p.suffix in _TEXT_SUFFIXES
    )
    files.extend(
        p
        for p in ENGINE_SRC.rglob("*")
        if p.is_file() and p.suffix in _TEXT_SUFFIXES and "__pycache__" not in p.parts
    )
    return files


def _hygiene_violations(text: str) -> list[str]:
    """Return the forbidden tokens in one document's text (empty when clean)."""
    tokens = [
        m.group(0)
        for m in _NAMESPACED_ID.finditer(text)
        if m.group(0).split("-", 1)[0] not in _ALLOWED_NAMESPACES
    ]
    tokens.extend(m.group(0) for m in _EPIC_REF.finditer(text))
    return tokens


def _hygiene_failure_message(rel: str, lineno: int, token: str) -> str:
    """One actionable failure line: file, line, matched token, and the one-line rule."""
    return (
        f"{rel}:{lineno}: {token!r} — internal requirement IDs never appear in "
        "end-user-readable text (AGENTS.md, 'Open-source readiness'; use DEMO-FR-### "
        "or bare FR-### for format teaching)"
    )


def test_public_text_carries_no_internal_requirement_ids():
    """PUBTXT-FR-001 PUBTXT-FR-002 PUBTXT-FR-003: no namespaced internal requirement ID or epic
    reference on any end-user-readable surface — docs/ (minus STATUS.md), the root public files,
    and the whole engine source tree (docstrings, comments, and the scaffold assets `3pwr init`
    ships) included. Bare FR-###/NFR-### and the DEMO-/placeholder namespaces are allowed (format
    teaching). Rule: AGENTS.md, "Open-source readiness"."""
    failures: list[str] = []
    for path in _hygiene_surfaces():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):  # binary or unreadable: not a text surface
            continue
        for lineno, line in enumerate(lines, 1):
            for token in _hygiene_violations(line):
                rel = str(path.relative_to(REPO))
                failures.append(_hygiene_failure_message(rel, lineno, token))
    assert not failures, "\n".join(failures)


def test_scaffolded_format_teaching_uses_the_reserved_namespace():
    """PUBTXT-FR-004: the hygiene scan's own allowlist admits the DEMO- namespace, so scaffold
    templates and docs can still teach the full namespaced requirement-ID format."""
    assert not _hygiene_violations("Number requirements DEMO-FR-001, DEMO-FR-002, ...")
    assert _hygiene_violations("cross-check the chain (HARDN-FR-005)") == ["HARDN-FR-005"]
    assert _hygiene_violations("delivered in (epic A3)") == ["(epic A3)"]
    assert not _hygiene_violations("write FR-001, FR-002 for your own requirements")


def test_engine_source_modules_keep_their_docstrings():
    """PUBTXT-FR-002: citations were rewritten, never resolved by deleting documentation — every
    module under engine/src/threepowers/ still carries a module docstring. (The citation-free
    half of the requirement is the surface scan above.)"""
    modules = [p for p in ENGINE_SRC.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts]
    assert modules, "engine source tree is empty — wrong repo root?"
    undocumented = [
        str(p.relative_to(REPO))
        for p in modules
        if not ast.get_docstring(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert not undocumented, f"modules without a docstring: {undocumented}"


def test_hygiene_convention_is_written_down_in_the_agent_guides():
    """PUBTXT-FR-005: AGENTS.md carries the convention (internal IDs never in end-user-readable
    text; DEMO- is the reserved teaching namespace) and CLAUDE.md mirrors it."""
    agents = _read(AGENTS)
    assert "Open-source readiness" in agents
    assert "Internal requirement IDs stay out of end-user-readable text" in agents
    assert "DEMO-FR-###" in agents
    claude = _read(CLAUDE)
    assert "Open-source readiness" in claude
    assert "DEMO-FR-###" in claude


def test_hygiene_allowlist_is_frozen_and_failures_are_actionable():
    """PUBTXT-FR-006: the allowlist is a frozen, deliberate set (DEMO + the placeholder
    namespace), and a violation's failure message names file, line, matched token, and the
    one-line rule."""
    assert isinstance(_ALLOWED_NAMESPACES, frozenset)
    assert _ALLOWED_NAMESPACES == {"DEMO", "SPECID"}
    msg = _hygiene_failure_message("docs/example.md", 7, "HARDN-FR-005")
    assert "docs/example.md:7" in msg  # file and line
    assert "HARDN-FR-005" in msg  # the matched token
    assert "AGENTS.md" in msg and "end-user-readable text" in msg  # the rule, actionably
    assert "DEMO-FR-###" in msg  # the sanctioned alternative


def test_no_disposable_scanner_ships():
    """PUBTXT-FR-007: the temporary inventory scanner is gone — its regex and surface list live
    only inside this permanent test module."""
    assert not list((REPO / "plan").rglob("scan_public_ids.py")), (
        "the disposable scanner must not ship; the enforcement lives in this test"
    )
    # The permanent home of the pattern and surfaces is this module.
    assert _NAMESPACED_ID.pattern and callable(_hygiene_surfaces)


def test_hygiene_scan_is_file_based_and_offline(tmp_path):
    """PUBTXT-NFR-001: the hygiene checks run inside the ordinary engine test suite on plain
    file reads — no network, no subprocess — and detect a seeded violation from a bare file."""
    seeded = tmp_path / "leaky.md"
    seeded.write_text("traces to HARDN-FR-005 (epic A3)", encoding="utf-8")
    assert _hygiene_violations(seeded.read_text(encoding="utf-8")) == [
        "HARDN-FR-005",
        "(epic A3)",
    ]
    surfaces = _hygiene_surfaces()
    assert surfaces and all(p.is_absolute() and REPO in p.parents for p in surfaces)


def test_mutation_scope_is_pinned_to_the_trust_spine():
    """PUBTXT-NFR-002: the hygiene work left the mutation-testing scope untouched —
    [tool.mutmut] only_mutate still names exactly the six trust-spine modules."""
    cfg = tomllib.loads((REPO / "engine" / "pyproject.toml").read_text(encoding="utf-8"))
    mutmut = cfg["tool"]["mutmut"]
    assert mutmut["source_paths"] == ["src/threepowers"]
    assert sorted(mutmut["only_mutate"]) == [
        "src/threepowers/anchor.py",
        "src/threepowers/canonical.py",
        "src/threepowers/keys.py",
        "src/threepowers/ledger.py",
        "src/threepowers/speclock.py",
        "src/threepowers/verify.py",
    ]
