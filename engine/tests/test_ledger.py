"""Trust-spine tests: the hash-chained, signed ledger and its offline verify.

These exercise 3PWR-FR-038/039/040 and 3PWR-NFR-010 — a tampered, reordered, or
forged ledger must fail verification.
"""

from __future__ import annotations

import json

import pytest

from threepowers import keys
from threepowers.ledger import Ledger
from threepowers.verify import verify_ledger


@pytest.fixture()
def signed_ledger(tmp_path):
    sk = keys.generate()
    pub = tmp_path / "ledger.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    return ledger, sk, pub


def test_append_chains_and_verifies(signed_ledger):
    ledger, sk, pub = signed_ledger
    e0 = ledger.append("verdict", {"result": "pass"}, sk, spec_id="VUTIL")
    e1 = ledger.append("signoff", {"approver": "carlo"}, sk)
    assert e0["seq"] == 0 and e1["seq"] == 1
    assert e1["prev_hash"] == e0["entry_hash"]  # chain linkage
    res = verify_ledger(ledger.path, pub)
    assert res.ok, res.problems
    assert res.entries == 2


def test_empty_ledger_verifies(signed_ledger):
    ledger, _sk, pub = signed_ledger
    assert verify_ledger(ledger.path, pub).ok


def test_tampered_payload_is_detected(signed_ledger):
    ledger, sk, pub = signed_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    # Flip the recorded result without re-signing.
    line = json.loads(ledger.path.read_text().splitlines()[0])
    line["payload"]["result"] = "fail"
    ledger.path.write_text(json.dumps(line) + "\n")
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("tampered" in p or "signature" in p for p in res.problems)


def test_reordered_entries_break_the_chain(signed_ledger):
    ledger, sk, pub = signed_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    ledger.append("signoff", {"approver": "x"}, sk)
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("\n".join([lines[1], lines[0]]) + "\n")
    assert not verify_ledger(ledger.path, pub).ok


def test_deleted_entry_breaks_sequence(signed_ledger):
    ledger, sk, pub = signed_ledger
    ledger.append("verdict", {"a": 1}, sk)
    ledger.append("verdict", {"a": 2}, sk)
    ledger.append("verdict", {"a": 3}, sk)
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert not verify_ledger(ledger.path, pub).ok


def test_foreign_key_fails_verification(signed_ledger, tmp_path):
    ledger, sk, _pub = signed_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    other = keys.generate()
    wrong_pub = tmp_path / "wrong.pub"
    keys.write_public(wrong_pub, other.verify_key)
    assert not verify_ledger(ledger.path, wrong_pub).ok
