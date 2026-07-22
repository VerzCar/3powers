"""The redo rewind marker rides the trust spine unchanged (spec 039).

A `3pwr run --redo` records the rewind by APPENDING a signed `kind: "redo"` `run` entry — no new
ledger entry type and no signing change (REQ-007). These tests prove the append keeps the
hash-chained, Ed25519-signed ledger green under `verify` (SEC-002), that the marker is signed and
readable offline, and that tampering with a recorded rewind is caught exactly as any other entry.
"""

from __future__ import annotations

import json

import pytest

from threepowers import keys
from threepowers.ledger import Ledger
from threepowers.verify import verify_ledger


@pytest.fixture()
def signed_run(tmp_path):
    """A signed run ledger with a start + a Spec-stage completion, plus its public key."""
    sk = keys.generate()
    pub = tmp_path / "ledger.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    ledger.append("run", {"kind": "start", "intent": "add a rate limiter"}, sk, spec_id="RUN")
    ledger.append(
        "run",
        {"kind": "stage", "step": "specify", "artifacts": ["specs-src/001-run/spec.md"]},
        sk,
        spec_id="RUN",
    )
    return ledger, sk, pub


def test_redo_entry_keeps_verify_green(signed_run):
    """Covers: REQ-007/SEC-002 — appending a signed `kind: "redo"` marker leaves `verify` passing:
    the hash chain stays intact with no gap or break, and the entry count grows by exactly one."""
    ledger, sk, pub = signed_run
    before = verify_ledger(ledger.path, pub)
    assert before.ok, before.problems
    redo = ledger.append(
        "run",
        {
            "kind": "redo",
            "target_step": "specify",
            "reason": "clarify the rate-limit scope",
            "feedback_ref": "tighten the non-goals",
            "approver": "carlo",
        },
        sk,
        spec_id="RUN",
    )
    after = verify_ledger(ledger.path, pub)
    assert after.ok, after.problems
    assert after.entries == before.entries + 1
    assert redo["seq"] == before.entries  # chained onto the tail, next sequence


def test_redo_entry_is_signed_and_readable_offline(signed_run):
    """Covers: REQ-007/SEC-002 — the rewind marker carries a signature + signer key id and its full
    payload reconstructs from the repo alone, no network, no second source of truth."""
    ledger, sk, _pub = signed_run
    ledger.append(
        "run",
        {
            "kind": "redo",
            "target_step": "plan",
            "reason": "revisit the phasing",
            "feedback_ref": "",
            "approver": "reviewer",
        },
        sk,
        spec_id="RUN",
    )
    marker = [e for e in ledger.entries() if e["payload"].get("kind") == "redo"][-1]
    assert marker["signature"] and marker["signer_key_id"]
    assert marker["type"] == "run"  # additive — no new entry type
    payload = marker["payload"]
    assert payload["target_step"] == "plan"
    assert payload["approver"] == "reviewer"
    assert payload["reason"] == "revisit the phasing"


def test_tampered_redo_marker_is_detected(signed_run):
    """Covers: SEC-002 — rewriting a recorded rewind's target without re-signing breaks the chain,
    so `verify` fails closed: the append-only marker cannot be silently altered."""
    ledger, sk, pub = signed_run
    ledger.append(
        "run",
        {
            "kind": "redo",
            "target_step": "specify",
            "reason": "clarify",
            "feedback_ref": "",
            "approver": "carlo",
        },
        sk,
        spec_id="RUN",
    )
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[-1])
    tampered["payload"]["target_step"] = "oracle"  # flip the rewind target, keep the signature
    lines[-1] = json.dumps(tampered)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("tampered" in p or "signature" in p for p in res.problems)
