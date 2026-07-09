"""Trust-spine tests: the hash-chained, signed ledger and its offline verify.

These exercise 3PWR-FR-038/039/040 and 3PWR-NFR-010 — a tampered, reordered, or
forged ledger must fail verification.
"""

from __future__ import annotations

import base64
import json

import pytest

from threepowers import keys
from threepowers.canonical import hash_payload
from threepowers.ledger import Ledger, LedgerTamperError, core_of, rotation_payload
from threepowers.verify import verify_entry, verify_ledger


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


def test_entries_skips_blank_lines(signed_ledger):
    """Blank lines (e.g. a stray newline from hand-editing) are ignored, not treated as entries.

    Resilience of the offline-reconstructable record (3PWR-NFR-010): a blank line neither parses
    as an entry nor breaks the chain."""
    ledger, sk, pub = signed_ledger
    ledger.append("verdict", {"r": "pass"}, sk)
    ledger.path.write_text(ledger.path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert len(ledger.entries()) == 1  # the trailing blank line is skipped
    assert verify_ledger(ledger.path, pub).ok


def test_entries_raise_on_malformed_json_line_naming_the_line(signed_ledger):
    """A non-JSON line is corruption: surfaced loud and locatable, never silently skipped.

    The line number lets a human find the break; `verify_ledger` turns this into a named
    'ledger corrupted' verdict rather than a crash (3PWR-FR-040/NFR-011)."""
    ledger, sk, _pub = signed_ledger
    ledger.append("verdict", {"r": "pass"}, sk)
    with ledger.path.open("a", encoding="utf-8") as fh:
        fh.write("{ this is not valid json\n")  # a truncated / corrupted second entry
    with pytest.raises(ValueError) as exc:
        ledger.entries()
    assert "line 2" in str(exc.value) and "malformed" in str(exc.value)


# -- pre-append tail-integrity check (3PWR-FR-040/NFR-010): a tampered tail refuses ---
# the next append instead of getting buried under fresh, validly signed history.


@pytest.fixture()
def repo_ledger(tmp_path):
    """A ledger laid out like a real repo: the committed key at keys/ledger.pub beside it."""
    sk = keys.generate()
    pub = tmp_path / "keys" / "ledger.pub"
    keys.write_public(pub, sk.verify_key)
    ledger = Ledger(tmp_path / "ledger.jsonl")
    return ledger, sk, pub


def _rewrite_tail(ledger, mutate):
    """Hand-edit the last JSONL entry via ``mutate(entry_dict)`` and write it back."""
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    tail = json.loads(lines[-1])
    mutate(tail)
    lines[-1] = json.dumps(tail, ensure_ascii=False)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_append_refuses_on_tampered_tail_payload(repo_ledger):
    """A hand-edited tail payload makes the next append raise, naming seq and `3pwr verify`."""
    ledger, sk, _pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    ledger.append("verdict", {"result": "pass"}, sk)
    _rewrite_tail(ledger, lambda e: e["payload"].update(result="fail"))
    with pytest.raises(LedgerTamperError) as exc:
        ledger.append("verdict", {"result": "pass"}, sk)
    assert "seq=1" in str(exc.value) and "3pwr verify" in str(exc.value)
    assert exc.value.seq == 1
    # Nothing was written on top of the damage.
    assert len(ledger.path.read_text(encoding="utf-8").splitlines()) == 2


def test_append_refuses_on_tampered_tail_signature(repo_ledger):
    """A forged tail signature (valid base64, wrong bytes) also refuses the next append."""
    ledger, sk, _pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    forged = base64.b64encode(b"\x00" * 64).decode()
    _rewrite_tail(ledger, lambda e: e.update(signature=forged))
    with pytest.raises(LedgerTamperError) as exc:
        ledger.append("verdict", {"result": "pass"}, sk)
    assert "seq=0" in str(exc.value) and "3pwr verify" in str(exc.value)
    assert len(ledger.path.read_text(encoding="utf-8").splitlines()) == 1


def test_append_on_intact_tail_writes_the_same_entry_shape(repo_ledger):
    """An intact ledger appends normally and the written entry is exactly the signed core

    plus the derived fields — i.e. the tail check changes nothing about what append writes,
    and full verification still passes."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    entry = ledger.append("signoff", {"approver": "x"}, sk)
    assert entry["entry_hash"] == hash_payload(core_of(entry))  # write path unchanged
    assert verify_ledger(ledger.path, pub).ok


def test_genesis_append_on_empty_ledger_is_unchecked(repo_ledger):
    """The very first append has no tail to check and must go through untouched."""
    ledger, sk, pub = repo_ledger
    entry = ledger.append("verdict", {"result": "pass"}, sk)
    assert entry["seq"] == 0
    assert verify_ledger(ledger.path, pub).ok


def test_verify_entry_and_verify_ledger_agree_on_fixtures(repo_ledger):
    """Parity: the shared per-entry helper and the full chain walk see the same tamper."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    tail = ledger.last()
    candidates = [sk.verify_key]
    assert verify_entry(tail, None, candidates) == []  # intact both ways
    assert verify_ledger(ledger.path, pub).ok
    _rewrite_tail(ledger, lambda e: e["payload"].update(result="fail"))
    tampered = ledger.last()
    assert verify_entry(tampered, None, candidates)  # tampered both ways
    assert not verify_ledger(ledger.path, pub).ok


def test_middle_tamper_passes_append_but_fails_verify(repo_ledger):
    """Scope boundary: append checks the tail only; the chain walk is `3pwr verify`'s job."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"a": 1}, sk)
    ledger.append("verdict", {"a": 2}, sk)
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    middle = json.loads(lines[0])
    middle["payload"]["a"] = 99  # tamper the FIRST entry, leave the tail intact
    ledger.path.write_text("\n".join([json.dumps(middle), lines[1]]) + "\n", encoding="utf-8")
    entry = ledger.append("verdict", {"a": 3}, sk)  # tail is intact — append proceeds
    assert entry["seq"] == 2
    assert not verify_ledger(ledger.path, pub).ok  # ...but full verification catches it


def test_append_tail_check_verifies_exactly_one_entry(repo_ledger, monkeypatch):
    """The pre-append check is tail-only — one verify_entry call, never a full-chain walk."""
    from threepowers import verify as verify_mod

    ledger, sk, _pub = repo_ledger
    for i in range(5):
        ledger.append("verdict", {"i": i}, sk)

    calls: list[dict] = []
    real = verify_mod.verify_entry

    def counting(entry, expected_prev, candidates, **kwargs):
        calls.append(entry)
        return real(entry, expected_prev, candidates, **kwargs)

    monkeypatch.setattr(verify_mod, "verify_entry", counting)
    ledger.append("verdict", {"i": 99}, sk)
    assert len(calls) == 1  # only the tail, not the other five entries
    assert calls[0]["seq"] == 4


def test_append_accepts_rotation_tail_signed_by_outgoing_key(repo_ledger):
    """Key rotation must not wedge appends: the tail (the rotation entry) is signed by the

    OUTGOING key while the repo now commits only the successor — the check resolves the old
    key from the rotation payload without a chain walk and does not refuse."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    successor = keys.generate()
    ledger.append("key_rotation", rotation_payload(sk.verify_key, successor.verify_key), sk)
    keys.write_public(pub, successor.verify_key)  # the repo now trusts the successor only
    entry = ledger.append("verdict", {"result": "pass"}, successor)
    assert entry["seq"] == 2
    assert verify_ledger(ledger.path, pub).ok


def test_append_without_registered_keys_still_catches_payload_tamper(signed_ledger):
    """With no key material beside the ledger (legacy layout), the signature check is

    skipped rather than falsely refusing — but the content-hash check still catches a
    hand-edited tail payload."""
    ledger, sk, _pub = signed_ledger  # fixture keeps the pub key AWAY from the ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    _rewrite_tail(ledger, lambda e: e["payload"].update(result="fail"))
    with pytest.raises(LedgerTamperError):
        ledger.append("verdict", {"result": "pass"}, sk)


def test_append_skips_malformed_key_files_without_refusing(repo_ledger):
    """A malformed .pub beside the ledger never blocks an append (fail-open on key files;

    key problems are `3pwr verify`'s to report loudly)."""
    ledger, sk, pub = repo_ledger
    (pub.parent / "broken.pub").write_text("not a key line\n", encoding="utf-8")
    ledger.append("verdict", {"result": "pass"}, sk)
    entry = ledger.append("verdict", {"result": "pass"}, sk)  # tail check ran, no refusal
    assert entry["seq"] == 1


def test_append_skips_malformed_rotation_payload_keys(repo_ledger):
    """Rotation payloads carrying non-base64 or wrong-length key material are skipped

    when gathering signature candidates — never a crash, never a false refusal."""
    ledger, sk, _pub = repo_ledger
    ledger.append(
        "key_rotation",
        {"previous_public_key": "%%% not base64 %%%", "new_public_key": "dG9vc2hvcnQ="},
        sk,
    )
    entry = ledger.append("verdict", {"result": "pass"}, sk)
    assert entry["seq"] == 1


def test_append_succeeds_after_unrotated_committed_key_swap(repo_ledger):
    """Regression: a replaced committed key (no key_rotation entry) must not wedge appends.

    The tail was signed by a key the repo can no longer resolve — a key-succession
    problem, which is `3pwr verify`'s to report, not tail tamper. The append under the
    new key succeeds, and full verification still names the succession problem."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    successor = keys.generate()
    keys.write_public(pub, successor.verify_key)  # regenerated key, no rotation recorded
    entry = ledger.append("verdict", {"result": "pass"}, successor)  # must not refuse
    assert entry["seq"] == 1
    res = verify_ledger(ledger.path, pub)
    assert not res.ok  # the succession problem still surfaces where it belongs
    assert any("unrotated key change" in p for p in res.problems)


def test_append_proceeds_when_tail_signer_is_unknown_but_content_intact(repo_ledger):
    """A tail whose recorded signer is missing/unresolvable gets the content-hash check

    only: without the signing key's public half, a superseded key and a forgery are
    indistinguishable at append time — that judgement is `3pwr verify`'s."""
    ledger, sk, _pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    # signer_key_id is derived (outside the signed core): dropping it leaves the
    # content hash intact but makes the signer unresolvable.
    _rewrite_tail(ledger, lambda e: e.pop("signer_key_id"))
    entry = ledger.append("verdict", {"result": "pass"}, sk)
    assert entry["seq"] == 1


def test_append_refuses_payload_tamper_even_with_unknown_tail_signer(repo_ledger):
    """The content-hash check is unconditional: a hand-edited payload refuses the next

    append even when the tail's signer is unresolvable (so the signature check is
    skipped)."""
    ledger, sk, pub = repo_ledger
    ledger.append("verdict", {"result": "pass"}, sk)
    keys.write_public(pub, keys.generate().verify_key)  # unrotated key swap
    _rewrite_tail(ledger, lambda e: e["payload"].update(result="fail"))
    with pytest.raises(LedgerTamperError) as exc:
        ledger.append("verdict", {"result": "pass"}, sk)
    assert "entry_hash mismatch" in str(exc.value)
