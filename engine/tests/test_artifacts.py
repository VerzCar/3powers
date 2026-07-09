"""Per-stage artifact contracts — a stage that produced nothing (or the wrong thing) is caught (RUNLIVE-FR-001/002/003).

Verification is a pure function of the contract + the paths a stage produced, so these exercise it with no
agent and no network (RUNLIVE-NFR-002).
"""

from __future__ import annotations

from threepowers import artifacts


def test_discovery_contract_requires_a_note_in_the_feature_folder():
    """Plan 034 phase 4: the Discovery stage advances only if it produced its note flat in the
    run's feature folder (specs-src/<feature>/discovery.md; the legacy specs/ base matches too)."""
    c = artifacts.contract_for("discovery")
    assert c is not None and c.kind == "path"
    ok = artifacts.verify(c, ["specs-src/034-thing/discovery.md", "notes.txt"])
    assert ok.ok and "specs-src/034-thing/discovery.md" in ok.matched
    assert artifacts.verify(c, ["specs/034-thing/discovery.md"]).ok


def test_discovery_off_target_note_is_a_named_failure():
    """Plan 034 phase 4: a discovery note outside a feature folder (or no note at all) fails,
    naming the expected artifact and location."""
    c = artifacts.contract_for("discovery")
    chk = artifacts.verify(c, ["docs/discovery.md"])  # not under specs-src/<feature>/
    assert not chk.ok
    assert "off-target" in chk.message and "specs-src/<feature>/discovery.md" in chk.message
    empty = artifacts.verify(c, [])
    assert not empty.ok and "discovery note" in empty.message


def test_specify_contract_requires_a_spec_file():
    """RUNLIVE-FR-001: the Specify stage advances only if it produced a spec file."""
    c = artifacts.contract_for("specify")
    assert c is not None and c.kind == "path"
    ok = artifacts.verify(c, ["specs-src/013-thing/spec.md", "notes.txt"])
    assert ok.ok and "specs-src/013-thing/spec.md" in ok.matched
    assert "spec.md" in ok.summary
    # legacy base back-compat: signed ledger history keeps its recorded specs/… paths
    legacy = artifacts.verify(c, ["specs/013-thing/spec.md"])
    assert legacy.ok and "specs/013-thing/spec.md" in legacy.matched


def test_specify_empty_is_a_named_artifact_failure():
    """RUNLIVE-FR-002: a Specify stage that wrote nothing fails, naming the expected artifact — not silent."""
    c = artifacts.contract_for("specify")
    chk = artifacts.verify(c, [])
    assert not chk.ok
    assert "spec file" in chk.message and "no change" in chk.message


def test_right_artifact_wrong_location_names_expected_and_off_target():
    """Edge case: the right kind of file in the wrong place fails, naming expected + what was produced."""
    c = artifacts.contract_for("specify")
    chk = artifacts.verify(c, ["docs/spec.md", "README.md"])  # not under specs-src/<feature>/
    assert not chk.ok
    assert "off-target" in chk.message and "docs/spec.md" in chk.message
    assert "specs-src/<feature>/spec.md" in chk.message


def test_oracle_contract_matches_common_oracle_locations():
    """RUNLIVE-FR-001: oracle tests are accepted from the collected and worktree locations."""
    c = artifacts.contract_for("oracle")
    for path in (
        "tests/oracle/RUNLIVE/test_contracts.py",
        "oracle-tests/test_x.py",
        "pkg/test_oracle_thing.py",
    ):
        assert artifacts.verify(c, [path]).ok, path
    # an implementation file is not an oracle artifact
    assert not artifacts.verify(c, ["src/thing.py"]).ok


def test_implement_is_a_change_contract():
    """RUNLIVE-FR-001: Implement requires a non-empty change; an empty stage fails at Implement."""
    c = artifacts.contract_for("implement")
    assert c.kind == "change"
    assert artifacts.verify(c, ["src/rate_limiter.py"]).ok
    empty = artifacts.verify(c, [])
    assert not empty.ok and "implementation change" in empty.message


def test_unconfigured_stage_has_no_contract_and_falls_back():
    """RUNLIVE-FR-003: a stage with no declared contract returns None (the caller stays lenient).

    PHASE-FR-002 removed `plan`/`tasks` from this lenient fallback — every artifact-producing action
    stage now declares a contract; only genuinely artifact-less steps (clarify) stay lenient."""
    assert artifacts.contract_for("clarify") is None
    assert artifacts.contract_for("plan") is not None
    assert artifacts.contract_for("tasks") is not None


def test_verify_none_contract_is_lenient():
    """RUNLIVE-FR-003: verifying with no contract never blocks — even an empty produced set passes."""
    assert artifacts.verify(None, []).ok
    ok = artifacts.verify(None, ["anything.txt"])
    assert ok.ok and ok.produced == ["anything.txt"]


def test_verify_is_deterministic_and_order_independent():
    """RUNLIVE-NFR-002: same inputs → same result; produced order does not change the verdict."""
    c = artifacts.contract_for("oracle")
    a = artifacts.verify(c, ["b.py", "tests/oracle/x/test_a.py"])
    b = artifacts.verify(c, ["tests/oracle/x/test_a.py", "b.py", "b.py"])
    assert a.ok == b.ok and a.matched == b.matched
