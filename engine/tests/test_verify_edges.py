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
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    # The failure must NAME its class, not just be a non-empty list (3PWR-FR-034/NFR-011).
    assert any(p and "malformed" in p for p in res.problems)


def test_missing_pubkey_result_fields(tmp_path):
    """The missing-key branch fails closed with ok=False and the real entry count."""
    sk = keys.generate()
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"r": "pass"}, sk)
    res = verify_ledger(ledger.path, tmp_path / "absent.pub")
    assert res.ok is False  # not None / not falsy-by-accident
    assert res.entries == 1


def test_sequence_gap_names_the_failure(tmp_path):
    """A deleted middle entry must produce an actionable, named problem (3PWR-FR-034)."""
    sk = keys.generate()
    pub = tmp_path / "l.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"a": 1}, sk)
    ledger.append("verdict", {"a": 2}, sk)
    ledger.append("verdict", {"a": 3}, sk)
    lines = ledger.path.read_text().splitlines()
    ledger.path.write_text("\n".join([lines[0], lines[2]]) + "\n")  # drop seq=1
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    seq_problems = [p for p in res.problems if p and "sequence" in p]
    assert seq_problems
    # The exact offending entry + line must be named so a human can find it (3PWR-NFR-011).
    assert any("entry seq=2" in p and "line 2" in p for p in seq_problems)


def test_corrupt_ledger_line_fails_closed(tmp_path):
    """A corrupt (non-JSON) ledger line makes verify fail CLOSED, not crash (3PWR-FR-040).

    The keystone verify must classify corruption as tamper: it RETURNS ok=False with a named,
    human-readable problem (3PWR-FR-034/NFR-011) — never raising — so the CLI reports a red
    verdict (EXIT_FAIL) instead of a usage error on a tampered ledger."""
    sk = keys.generate()
    pub = tmp_path / "l.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"r": "pass"}, sk)
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write("}} truncated — not json\n")
    res = verify_ledger(ledger.path, pub)  # must return, must not raise
    assert res.ok is False
    assert any(p and "corrupt" in p for p in res.problems)


def test_broken_chain_names_the_failure(tmp_path):
    sk = keys.generate()
    pub = tmp_path / "l.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "l.jsonl")
    ledger.append("verdict", {"a": 1}, sk)
    ledger.append("verdict", {"a": 2}, sk)
    # Corrupt the first entry's recorded prev_hash so linkage breaks at seq=0.
    lines = ledger.path.read_text().splitlines()
    first = json.loads(lines[0])
    first["prev_hash"] = "sha256:" + "f" * 64
    ledger.path.write_text("\n".join([json.dumps(first), lines[1]]) + "\n")
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any(p and "chain" in p for p in res.problems)
