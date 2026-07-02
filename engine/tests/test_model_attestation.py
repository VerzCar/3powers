"""Oracle model attestation — self-report vs. ledger-attested dispatch (HARDN-FR-007).

Unit layer: when a dispatch attestation exists, the self-reported ``oracle record`` model
family must not contradict the dispatched integration; a contradiction is a blocking
independence failure. Without a dispatch, the model claim is honestly labelled
self-reported — advisory, never blocking.
"""

from __future__ import annotations

from threepowers import oracle

ROLES = {"roles": {"coder": {"model_family": "openai"}, "oracle": {"model_family": "anthropic"}}}


def _seal(seq, spec_id="ORAC", bhash="h", req_ids=()):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": spec_id,
        "payload": {"kind": "seal", "bundle_hash": bhash, "requirement_ids": list(req_ids)},
    }


def _record(seq, family, spec_id="ORAC", bhash="h"):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": spec_id,
        "payload": {
            "kind": "record",
            "bundle_hash": bhash,
            "model_family": family,
            "model": f"{family}/m",
            "test_paths": [],
            "advisory_findings": [],
        },
    }


def _dispatch(seq, integration, family, spec_id="ORAC", bhash="h"):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": spec_id,
        "payload": {
            "kind": "dispatch",
            "bundle_hash": bhash,
            "integration": integration,
            "model": f"{family}/m" if family else "",
            "model_family": family,
            "isolation": {
                "method": "git-worktree",
                "manifest_hash": "sha256:abc",
                "file_count": 3,
                "excluded_absent": True,
            },
        },
    }


def _ind(entries, tmp_path, **kw):
    return oracle.independence(entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=[], **kw)


def test_contradicting_self_report_blocks(tmp_path):
    """HARDN-FR-007: record says google, the attested dispatch ran claude (anthropic) — blocking."""
    entries = [_seal(0), _record(1, "google"), _dispatch(2, "claude", "anthropic")]
    ind = _ind(entries, tmp_path)
    assert not ind.ok
    assert any("contradicts the ledger-attested dispatch" in r for r in ind.reasons)
    assert ind.dispatch_ok is False


def test_consistent_self_report_and_dispatch_pass(tmp_path):
    """HARDN-FR-007: a consistent record/dispatch pair passes with no attestation finding."""
    entries = [_seal(0), _record(1, "anthropic"), _dispatch(2, "claude", "anthropic")]
    ind = _ind(entries, tmp_path)
    assert ind.ok, ind.reasons
    assert ind.dispatch_ok is True
    assert not any("self-reported" in a for a in ind.advisory)


def test_no_dispatch_yields_self_reported_advisory_never_blocking(tmp_path):
    """HARDN-FR-007: without a dispatch the claim is labelled self-reported — advisory only."""
    entries = [_seal(0), _record(1, "anthropic")]
    ind = _ind(entries, tmp_path)
    assert ind.ok, ind.reasons  # blocks nothing it does not block today
    assert any("self-reported" in a for a in ind.advisory)
    assert ind.dispatch_ok is None


def test_ambiguous_integration_cannot_contradict(tmp_path):
    """HARDN-FR-007: an integration with no declared family ('' — e.g. copilot) never contradicts."""
    entries = [_seal(0), _record(1, "anthropic"), _dispatch(2, "copilot", "")]
    ind = _ind(entries, tmp_path)
    assert not any("contradicts" in r for r in ind.reasons)


def test_resolved_family_of_ambiguous_integration_still_cross_checks(tmp_path):
    """HARDN-FR-007: when copilot's dispatch resolved an actual family, a contradiction counts."""
    entries = [_seal(0), _record(1, "google"), _dispatch(2, "copilot", "anthropic")]
    ind = _ind(entries, tmp_path)
    assert any("contradicts the ledger-attested dispatch" in r for r in ind.reasons)


def test_attestation_check_is_deterministic(tmp_path):
    """HARDN-NFR-001: identical inputs → identical reasons/advisory, twice."""
    entries = [_seal(0), _record(1, "google"), _dispatch(2, "claude", "anthropic")]
    a, b = _ind(entries, tmp_path), _ind(entries, tmp_path)
    assert a.reasons == b.reasons and a.advisory == b.advisory
