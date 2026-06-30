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


# -- entry-shape invariants (3PWR-FR-038): pin exactly what an entry records ----
def test_append_defaults_spec_id_to_empty(signed_ledger):
    ledger, sk, _pub = signed_ledger
    e = ledger.append("verdict", {"r": "pass"}, sk)  # no spec_id given
    assert e["spec_id"] == ""


def test_append_rejects_unknown_type_with_named_message(signed_ledger):
    ledger, sk, _pub = signed_ledger
    with pytest.raises(ValueError) as exc:
        ledger.append("not-a-real-type", {}, sk)
    assert "not-a-real-type" in str(exc.value)


def test_entry_records_sorted_requirement_ids_under_that_key(signed_ledger):
    ledger, sk, _pub = signed_ledger
    e = ledger.append("verdict", {"r": "pass"}, sk, requirement_ids=["3PWR-FR-002", "3PWR-FR-001"])
    assert "requirement_ids" in e
    assert e["requirement_ids"] == ["3PWR-FR-001", "3PWR-FR-002"]  # sorted


def test_entry_records_signer_key_id(signed_ledger):
    ledger, sk, _pub = signed_ledger
    e = ledger.append("verdict", {"r": "pass"}, sk)
    assert e["signer_key_id"] == sk.key_id
    assert e["signer_key_id"].startswith("ed25519:")


def test_timestamp_is_utc_second_precision(signed_ledger):
    import re

    ledger, sk, _pub = signed_ledger
    e = ledger.append("verdict", {"r": "pass"}, sk)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", e["timestamp"])


def test_latest_of_returns_none_when_type_absent(signed_ledger):
    ledger, sk, _pub = signed_ledger
    ledger.append("verdict", {"r": "pass"}, sk)
    assert ledger.latest_of("signoff") is None  # not "" or a falsy non-None


def test_ledger_file_is_one_json_object_per_line(signed_ledger):
    ledger, sk, _pub = signed_ledger
    ledger.append("verdict", {"a": 1}, sk)
    ledger.append("signoff", {"b": 2}, sk)
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(isinstance(json.loads(ln), dict) for ln in lines)


def test_append_creates_missing_parent_dirs(tmp_path):
    sk = keys.generate()
    ledger = Ledger(tmp_path / "deep" / "nested" / "ledger.jsonl")
    ledger.append("verdict", {"r": "pass"}, sk)
    assert ledger.path.exists()


def test_non_ascii_payload_round_trips_and_verifies(signed_ledger):
    ledger, sk, pub = signed_ledger
    ledger.append("verdict", {"note": "café-λ"}, sk)
    # The raw file keeps UTF-8 (ensure_ascii=False), not an escaped \uXXXX form.
    raw = ledger.path.read_text(encoding="utf-8")
    assert "café-λ" in raw and "\\u" not in raw
    # And the chain/signatures still verify over the non-ASCII content.
    assert verify_ledger(ledger.path, pub).ok
