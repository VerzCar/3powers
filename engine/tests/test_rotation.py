"""Key continuity — rotation as a signed ledger entry (HARDN-FR-004).

Unit layer: the ``key_rotation`` entry kind, the span-based verification that walks
recorded successions, the unrotated-key-change finding, and the ``3pwr rotate-key``
command. Backward compatibility (HARDN-NFR-003): rotation-free ledgers verify exactly
as before.
"""

from __future__ import annotations

import json

from threepowers import keys
from threepowers.cli import main
from threepowers.ledger import Ledger, rotation_payload
from threepowers.verify import verify_ledger


def _setup(tmp_path):
    root = tmp_path / "repo"
    (root / ".3powers" / "keys").mkdir(parents=True)
    ledger_path = root / ".3powers" / "ledger.jsonl"
    pub = root / ".3powers" / "keys" / "ledger.pub"
    return root, Ledger(ledger_path), pub


def test_rotation_entry_signed_by_outgoing_key_verifies(tmp_path):
    """HARDN-FR-004: a rotation authored by the previous key hands over to the successor."""
    root, ledger, pub = _setup(tmp_path)
    genesis, successor = keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, genesis)
    ledger.append(
        "key_rotation", rotation_payload(genesis.verify_key, successor.verify_key), genesis
    )
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, successor)
    keys.write_public(pub, successor.verify_key)  # the committed key is the successor
    res = verify_ledger(ledger.path, pub)
    assert res.ok, res.problems


def test_unrotated_committed_key_swap_fails_verify(tmp_path):
    """HARDN-FR-004 + SC-001: swapping the committed pubkey without a rotation is a named finding."""
    root, ledger, pub = _setup(tmp_path)
    genesis, attacker = keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, genesis)
    # The attacker swaps the committed key, then appends entries signed with their own key.
    # (The pre-append tail check does not block this: the genesis tail's signer is no
    # longer resolvable, which is a key-succession question for `verify`, not tamper.)
    keys.write_public(pub, attacker.verify_key)
    ledger.append("signoff", {"approver": "x", "stage": "review", "note": ""}, attacker)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("unrotated key change" in p for p in res.problems)


def test_rotation_free_ledger_verifies_exactly_as_before(tmp_path):
    """HARDN-NFR-003: no rotations → the committed genesis key verifies everything, unchanged."""
    root, ledger, pub = _setup(tmp_path)
    sk = keys.generate()
    for _ in range(3):
        ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, sk)
    keys.write_public(pub, sk.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert res.ok and res.entries == 3 and res.problems == []


def test_rotation_not_signed_by_outgoing_key_fails(tmp_path):
    """HARDN-FR-004: a rotation the active key did not author breaks the succession."""
    root, ledger, pub = _setup(tmp_path)
    genesis, rogue, successor = keys.generate(), keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, genesis)
    # A rogue key claims genesis as predecessor but signs the rotation itself.
    ledger.append("key_rotation", rotation_payload(genesis.verify_key, successor.verify_key), rogue)
    keys.write_public(pub, successor.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("invalid signature" in p for p in res.problems)


def test_rotation_chain_must_link_previous_to_active(tmp_path):
    """HARDN-FR-004: a rotation whose previous_public_key is not the active key is flagged."""
    root, ledger, pub = _setup(tmp_path)
    k1, k2, k3, unrelated = keys.generate(), keys.generate(), keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, k1)
    ledger.append("key_rotation", rotation_payload(k1.verify_key, k2.verify_key), k1)
    # The second rotation mis-declares its predecessor (signed correctly by the active k2).
    ledger.append("key_rotation", rotation_payload(unrelated.verify_key, k3.verify_key), k2)
    keys.write_public(pub, k3.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("does not chain" in p for p in res.problems)


def test_first_rotation_misdeclaring_genesis_fails_the_genesis_span(tmp_path):
    """HARDN-FR-004: declaring a foreign genesis key makes every pre-rotation entry fail."""
    root, ledger, pub = _setup(tmp_path)
    genesis, unrelated, successor = keys.generate(), keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, genesis)
    bad = rotation_payload(unrelated.verify_key, successor.verify_key)
    ledger.append("key_rotation", bad, genesis)  # declares `unrelated` as the genesis key
    keys.write_public(pub, successor.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("invalid signature" in p for p in res.problems)


def test_malformed_rotation_payload_is_a_named_problem(tmp_path):
    """HARDN-FR-004: a rotation without a decodable successor key fails loudly, never silently."""
    root, ledger, pub = _setup(tmp_path)
    genesis = keys.generate()
    payload = rotation_payload(genesis.verify_key, genesis.verify_key)
    payload["new_public_key"] = "not-base64!!"
    ledger.append("key_rotation", payload, genesis)
    keys.write_public(pub, genesis.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("malformed key_rotation" in p for p in res.problems)


def test_two_rotations_chain_through_to_the_committed_key(tmp_path):
    """HARDN-FR-004: successive rotations each hand over; the committed key is the last successor."""
    root, ledger, pub = _setup(tmp_path)
    k1, k2, k3 = keys.generate(), keys.generate(), keys.generate()
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, k1)
    ledger.append("key_rotation", rotation_payload(k1.verify_key, k2.verify_key), k1)
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, k2)
    ledger.append("key_rotation", rotation_payload(k2.verify_key, k3.verify_key), k2)
    ledger.append("signoff", {"approver": "a", "stage": "review", "note": ""}, k3)
    keys.write_public(pub, k3.verify_key)
    assert verify_ledger(ledger.path, pub).ok
    # ... and a committed key stuck at an intermediate stage is an unrotated change.
    keys.write_public(pub, k2.verify_key)
    res = verify_ledger(ledger.path, pub)
    assert not res.ok
    assert any("unrotated key change" in p for p in res.problems)


# --------------------------------------------------------------------------- CLI
def test_rotate_key_command_end_to_end(tmp_path, monkeypatch, capsys):
    """HARDN-FR-004: `3pwr rotate-key` appends the signed rotation and installs the successor."""
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(root), "keygen", "--out", str(key)]) == 0
    assert main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"]) == 0

    assert main(["--root", str(root), "rotate-key", "--out", str(key), "--reason", "test"]) == 0
    out = capsys.readouterr().out
    assert "key rotated" in out

    # Entries signed with the successor verify; the ledger records the rotation.
    assert main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"]) == 0
    assert main(["--root", str(root), "verify"]) == 0
    entries = Ledger(root / ".3powers" / "ledger.jsonl").entries()
    rot = [e for e in entries if e["type"] == "key_rotation"]
    assert len(rot) == 1
    assert rot[0]["payload"]["new_key_id"] != rot[0]["payload"]["previous_key_id"]


def test_rotate_key_refuses_in_repo_output(tmp_path, monkeypatch, capsys):
    """HARDN-FR-002 applies to rotation too: the successor key must live outside the tree."""
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(root), "keygen", "--out", str(key)]) == 0
    rc = main(["--root", str(root), "rotate-key", "--out", str(root / "new.key")])
    assert rc == 2
    assert "INSIDE the repository working tree" in capsys.readouterr().err


def test_rotation_payload_is_json_serializable_and_deterministic():
    """HARDN-NFR-001: the payload is a pure function of the two keys."""
    a, b = keys.generate(), keys.generate()
    p1 = rotation_payload(a.verify_key, b.verify_key, "r")
    p2 = rotation_payload(a.verify_key, b.verify_key, "r")
    assert p1 == p2
    json.dumps(p1)
