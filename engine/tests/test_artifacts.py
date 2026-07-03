"""Per-stage artifact contracts — a stage that produced nothing (or the wrong thing) is caught (RUNLIVE-FR-001/002/003).

Verification is a pure function of the contract + the paths a stage produced, so these exercise it with no
agent and no network (RUNLIVE-NFR-002).
"""

from __future__ import annotations

from threepowers import artifacts


def test_specify_contract_requires_a_spec_file():
    """RUNLIVE-FR-001: the Specify stage advances only if it produced a spec file."""
    c = artifacts.contract_for("specify")
    assert c is not None and c.kind == "path"
    ok = artifacts.verify(c, ["specs/013-thing/spec.md", "notes.txt"])
    assert ok.ok and "specs/013-thing/spec.md" in ok.matched
    assert "spec.md" in ok.summary


def test_specify_empty_is_a_named_artifact_failure():
    """RUNLIVE-FR-002: a Specify stage that wrote nothing fails, naming the expected artifact — not silent."""
    c = artifacts.contract_for("specify")
    chk = artifacts.verify(c, [])
    assert not chk.ok
    assert "spec file" in chk.message and "no change" in chk.message


def test_right_artifact_wrong_location_names_expected_and_off_target():
    """Edge case: the right kind of file in the wrong place fails, naming expected + what was produced."""
    c = artifacts.contract_for("specify")
    chk = artifacts.verify(c, ["docs/spec.md", "README.md"])  # not under specs/<feature>/
    assert not chk.ok
    assert "off-target" in chk.message and "docs/spec.md" in chk.message
    assert "specs/<feature>/spec.md" in chk.message


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
    """RUNLIVE-FR-003: a stage with no declared contract returns None (the caller stays lenient)."""
    assert artifacts.contract_for("clarify") is None
    assert artifacts.contract_for("plan") is None
    assert artifacts.contract_for("tasks") is None


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
