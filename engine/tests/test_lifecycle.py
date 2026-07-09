"""Lifecycle derivation (3PWR-FR-011/019) and reversal (3PWR-FR-070)."""

from __future__ import annotations

from threepowers import keys
from threepowers.ledger import Ledger
from threepowers.lifecycle import canonical_stage, derive


def _ledger(tmp_path):
    return Ledger(tmp_path / "l.jsonl"), keys.generate()


def test_canonical_stage_is_case_insensitive():
    assert canonical_stage("ship") == "Ship"
    assert canonical_stage("BUILD") == "Build"
    assert canonical_stage("nope") is None


def test_spec_state_defaults_to_discovery(tmp_path):
    """Plan 034 phase 4: a spec with no stage-bearing record starts at Discovery — the lifecycle's
    first stage — and a run/stage record naming discovery folds to the canonical stage."""
    ledger, sk = _ledger(tmp_path)
    ledger.append("verdict", {"result": "none"}, sk, spec_id="NEW")
    assert derive(ledger.entries())["NEW"].stage == "Discovery"
    ledger.append(
        "run", {"kind": "stage", "step": "discovery", "stage": "discovery"}, sk, spec_id="D"
    )
    assert derive(ledger.entries())["D"].stage == "Discovery"


def test_derive_tracks_stage_verdict_and_signoff(tmp_path):
    """3PWR-FR-011 stage + 3PWR-FR-019 resumable state, derived from the ledger."""
    ledger, sk = _ledger(tmp_path)
    ledger.append("verdict", {"result": "pass"}, sk, spec_id="3PWR")
    ledger.append("signoff", {"approver": "carlo"}, sk, spec_id="3PWR")
    ledger.append("stage_advance", {"stage": "ship"}, sk, spec_id="3PWR")
    st = derive(ledger.entries())["3PWR"]
    assert st.stage == "Ship"
    assert st.last_verdict == "pass"
    assert st.signed_off


def test_reversal_returns_to_prior_stage(tmp_path):
    """3PWR-FR-070: reverse to a prior recorded state, history stays append-only."""
    ledger, sk = _ledger(tmp_path)
    ledger.append("stage_advance", {"stage": "Build"}, sk, spec_id="3PWR")
    ledger.append("stage_advance", {"stage": "Ship"}, sk, spec_id="3PWR")
    ledger.append("reversal", {"to_seq": 0, "to_stage": "Build"}, sk, spec_id="3PWR")
    assert derive(ledger.entries())["3PWR"].stage == "Build"
    assert len(ledger.entries()) == 3  # nothing deleted


def test_abort_is_recorded(tmp_path):
    """3PWR-FR-019: a run can be aborted."""
    ledger, sk = _ledger(tmp_path)
    ledger.append("stage_advance", {"stage": "Build"}, sk, spec_id="3PWR")
    ledger.append("abort", {"reason": "superseded"}, sk, spec_id="3PWR")
    assert derive(ledger.entries())["3PWR"].aborted
