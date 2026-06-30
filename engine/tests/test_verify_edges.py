"""Verify edge cases (3PWR-FR-040): missing key and malformed signature both fail closed."""

from __future__ import annotations

import json

from threepowers import keys
from threepowers.ledger import Ledger
from threepowers.verify import verify_ledger


def test_missing_public_key_fails(tmp_path):
    sk = keys.generate()
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"r": "pass"}, sk)
    res = verify_ledger(ledger.path, tmp_path / "absent.pub")
    assert not res.ok and any("public key" in p for p in res.problems)


def test_malformed_signature_fails(tmp_path):
    sk = keys.generate()
    pub = tmp_path / "l.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"r": "pass"}, sk)
    line = json.loads(ledger.path.read_text())
    line["signature"] = "%%% not base64 %%%"
    ledger.path.write_text(json.dumps(line) + "\n")
    assert not verify_ledger(ledger.path, pub).ok
