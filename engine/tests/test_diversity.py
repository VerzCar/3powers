"""Model diversity: recommend, don't force (3PWR-FR-022 via FR-057).

Diversity comparison is configurable (family|model), and a same-family/same-model oracle proceeds
only under a signed ``model_diversity`` deviation — warned and recorded, never a silent drop.
Pure predicates are exercised directly; the record→deviation→advance→revoke flow is driven through
``3pwr``.
"""

from __future__ import annotations

import pytest

from threepowers import deviations, oracle
from threepowers.cli import main
from threepowers.config import model_diversity_ok


# --------------------------------------------------------------------------- pure: diverse()
def test_diverse_family_and_model_levels():
    """3PWR-FR-022: family-level compares families; model-level accepts a different model in one
    family; a family-only side at model-level falls back to a family comparison; empty is never diverse."""
    assert oracle.diverse("openai/gpt", "anthropic/claude", "family")
    assert not oracle.diverse("anthropic/opus", "anthropic/sonnet", "family")  # same family
    assert oracle.diverse("anthropic/opus", "anthropic/sonnet", "model")  # different model
    assert not oracle.diverse("anthropic/opus", "anthropic/opus", "model")  # identical model
    assert not oracle.diverse(
        "anthropic", "anthropic/opus", "model"
    )  # family-only side → family compare
    assert oracle.diverse("openai", "anthropic/opus", "model")  # different families
    assert not oracle.diverse("", "anthropic/opus", "family")
    assert not oracle.diverse("anthropic/opus", "", "model")


def test_model_diversity_ok_levels():
    """3PWR-FR-022: config-level check honours granularity and prefers a declared full model."""
    roles = {
        "roles": {
            "coder": {"model_family": "anthropic", "model": "anthropic/opus"},
            "oracle": {"model_family": "anthropic", "model": "anthropic/sonnet"},
        }
    }
    assert not model_diversity_ok(roles, "oracle", "coder", "family")  # same family
    assert model_diversity_ok(roles, "oracle", "coder", "model")  # different model


# --------------------------------------------------------------------------- pure: deviation helpers
def test_diversity_deviation_helpers():
    """3PWR-FR-057: an active model_diversity deviation is found (spec-scoped or global)."""
    scoped = [{"seq": 3, "spec_id": "ORAC", "gates": ["model_diversity"]}]
    assert deviations.diversity_deviation(scoped, "ORAC") == 3
    assert deviations.covers_model_diversity(scoped, "ORAC")
    assert deviations.diversity_deviation(scoped, "OTHER") is None  # does not leak across specs
    glob = [{"seq": 4, "spec_id": "", "gates": ["model_diversity"]}]
    assert deviations.covers_model_diversity(glob, "ANY")  # a global deviation applies everywhere
    other = [{"seq": 5, "spec_id": "", "gates": ["mutation"]}]
    assert not deviations.covers_model_diversity(other, "X")


# --------------------------------------------------------------------------- pure: independence relaxation
ROLES_SAME = {
    "roles": {"coder": {"model_family": "anthropic"}, "oracle": {"model_family": "anthropic"}}
}


def _seal(seq, bhash="h", req_ids=("ORAC-FR-001",)):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": "ORAC",
        "payload": {"kind": "seal", "bundle_hash": bhash, "requirement_ids": list(req_ids)},
    }


def _record(seq, bhash="h", model="anthropic/claude"):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": "ORAC",
        "payload": {
            "kind": "record",
            "bundle_hash": bhash,
            "model": model,
            "model_family": oracle.family_of(model),
            "test_paths": [],
            "advisory_findings": [],
        },
    }


def _otest(tmp_path):
    t = tmp_path / "oracle_orac.py"
    t.write_text("# covers ORAC-FR-001\n", encoding="utf-8")
    return [t]


def test_independence_same_family_blocks_then_relaxed(tmp_path):
    """3PWR-FR-022/FR-057: a same-family oracle blocks by default; with the deviation it is advisory,
    never blocking, and independence passes."""
    entries = [
        _seal(0),
        _record(1, model="anthropic/claude"),
    ]  # oracle anthropic == coder anthropic
    roots = _otest(tmp_path)
    blocked = oracle.independence(entries, ROLES_SAME, "ORAC", repo_root=tmp_path, test_roots=roots)
    assert not blocked.ok
    assert any("equals the coder family" in r for r in blocked.reasons)
    relaxed = oracle.independence(
        entries, ROLES_SAME, "ORAC", repo_root=tmp_path, test_roots=roots, diversity_relaxed=True
    )
    assert relaxed.ok, relaxed.reasons
    assert any("relaxed by an active model_diversity deviation" in a for a in relaxed.advisory)
    assert all("equals the coder" not in r for r in relaxed.reasons)


def test_independence_model_level_diversity(tmp_path):
    """3PWR-FR-022: at model level a different model in one family passes; the same model blocks."""
    roots = _otest(tmp_path)
    ok = oracle.independence(
        [_seal(0), _record(1, model="anthropic/sonnet")],
        ROLES_SAME,
        "ORAC",
        repo_root=tmp_path,
        test_roots=roots,
        diversity_level="model",
        coder_model="anthropic/opus",
    )
    assert ok.ok, ok.reasons
    blocked = oracle.independence(
        [_seal(0), _record(1, model="anthropic/opus")],
        ROLES_SAME,
        "ORAC",
        repo_root=tmp_path,
        test_roots=roots,
        diversity_level="model",
        coder_model="anthropic/opus",
    )
    assert not blocked.ok
    assert any("equals the coder model" in r for r in blocked.reasons)


# --------------------------------------------------------------------------- CLI end-to-end
RISK_TIERS = """
tiers:
  Standard:  { diff_coverage: 80, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
  High-risk: { diff_coverage: 95, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
"""
ROLES_YAML = """
diversity_level: family
roles:
  coder: { model_family: anthropic }
  oracle: { model_family: anthropic }
"""
ADAPTER = """
language: fake
detect: ["detect.txt"]
test_roots: ["tests"]
gates:
  format: { check_cmd: "python -c pass", parser: fake }
  lint:   { cmd: "python -c pass", parser: fake }
  types:  { cmd: "python -c pass", parser: fake }
  tests:  { cmd: "python -c pass", parser: fake, coverage_path: "coverage/lcov.info" }
"""
SPEC = "**Spec ID**: ORAC\n\n- **ORAC-FR-001**: The system shall work.\n"


@pytest.fixture()
def diversity_project(tmp_path, monkeypatch):
    """A repo whose coder and oracle are the SAME family — so diversity relief is exercised."""
    root = tmp_path
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "fake").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK_TIERS, encoding="utf-8")
    (tp / "config" / "roles.yaml").write_text(ROLES_YAML, encoding="utf-8")
    (tp / "adapters" / "fake" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")
    proj = root / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "detect.txt").write_text("x", encoding="utf-8")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "orac.test.py").write_text("# covers ORAC-FR-001\n", encoding="utf-8")
    (proj / "coverage").mkdir()
    (proj / "coverage" / "lcov.info").write_text(
        "SF:src/x.py\nDA:1,1\nDA:2,1\nend_of_record\n", encoding="utf-8"
    )
    keyfile = root / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root, proj


def _R(root, *args):
    return main(["--root", str(root), *args])


def _seal_cli(root, proj):
    return _R(root, "oracle", "seal", "--spec", str(proj / "spec.md"), "--spec-id", "ORAC")


def _record_cli(root, proj):
    return _R(
        root,
        "oracle",
        "record",
        "--spec-id",
        "ORAC",
        "--model",
        "anthropic/claude",  # same family as the coder
        "--tests",
        str(proj / "tests" / "orac.test.py"),
    )


def test_cli_roles_check_relaxed_by_deviation(diversity_project):
    """3PWR-FR-022/FR-057: roles-check is a VIOLATION for same-family, but RELAXED (exit 0) under a
    global model_diversity deviation."""
    root, _ = diversity_project
    assert _R(root, "roles-check") == 1  # oracle & coder both anthropic → violation
    assert (
        _R(root, "deviation", "--gate", "model_diversity", "--approver", "carlo", "--note", "solo")
        == 0
    )
    assert _R(root, "roles-check") == 0  # relaxed by the deviation


def test_cli_record_refused_then_relaxed(diversity_project):
    """3PWR-FR-022/FR-057: same-family `oracle record` is refused; a signed model_diversity deviation
    lets it proceed (warned), and `oracle verify` then PASSes."""
    root, proj = diversity_project
    assert _seal_cli(root, proj) == 0
    assert _record_cli(root, proj) == 1  # refused — same family, no deviation
    assert (
        _R(root, "deviation", "--gate", "model_diversity", "--approver", "carlo", "--note", "solo")
        == 0
    )
    assert _record_cli(root, proj) == 0  # now proceeds, warned + recorded
    assert _R(root, "oracle", "verify", "--spec-id", "ORAC") == 0


def test_cli_deviation_rejects_unknown_target(diversity_project):
    """A deviation target must be a known gate or requirement."""
    root, _ = diversity_project
    assert _R(root, "deviation", "--gate", "not_a_thing", "--approver", "carlo", "--note", "x") == 2


def test_cli_high_risk_advance_relaxed_then_revoked(diversity_project):
    """3PWR-FR-057: a High-risk advance proceeds under the model_diversity deviation, and refuses
    again once it is revoked — the recorded way back."""
    root, proj = diversity_project
    assert _seal_cli(root, proj) == 0  # #0
    assert (
        _R(root, "deviation", "--gate", "model_diversity", "--approver", "carlo", "--note", "solo")
        == 0
    )  # #1
    assert _record_cli(root, proj) == 0  # #2 Phase A (relaxed)
    assert (
        _R(
            root,
            "gate",
            "run",
            "--path",
            str(proj),
            "--adapter",
            "fake",
            "--spec",
            str(proj / "spec.md"),
            "--tier",
            "High-risk",
        )
        == 0
    )  # #3 verdict
    assert _R(root, "signoff", "--approver", "carlo", "--spec-id", "ORAC") == 0  # #4
    assert (
        _R(root, "advance", "--stage", "ship", "--spec-id", "ORAC") == 0
    )  # proceeds under deviation
    # Revoke the deviation (seq 1) → the way back → advance blocks again.
    assert _R(root, "deviation", "--revoke", "1") == 0
    assert _R(root, "advance", "--stage", "ship", "--spec-id", "ORAC") == 1
