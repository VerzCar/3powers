"""External (hardware-capable) signing via a process boundary (HARDN-FR-006).

Unit layer: with ``$THREEPOWERS_SIGNER_CMD`` configured, signing is delegated to a command
that receives the canonical bytes on stdin and prints a base64 Ed25519 signature — the
private seed is never in a file or environment variable the engine reads. Verification is
unchanged. A misconfigured signer fails loudly, never falling back to a software key.

The tests model the external signer as a script wrapping a keypair the engine never sees.
"""

from __future__ import annotations

import base64
import os
import stat
import sys

import pytest

from threepowers import keys
from threepowers.cli import main
from threepowers.verify import verify_ledger

SIGNER_SCRIPT = """#!{python}
import base64, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
seed = base64.b64decode({seed_b64!r})
sig = Ed25519PrivateKey.from_private_bytes(seed).sign(sys.stdin.buffer.read())
sys.stdout.write(base64.b64encode(sig).decode())
"""


def _external_setup(tmp_path, monkeypatch):
    """A repo whose committed pubkey belongs to an external signer script — no seed on the
    engine's resolution path (no key file, no THREEPOWERS_SIGNING_KEY*)."""
    root = tmp_path / "repo"
    (root / ".3powers" / "keys").mkdir(parents=True)
    sk = keys.generate()  # generated here only to build the fixture script
    script = tmp_path / "hsm-sign"
    script.write_text(
        SIGNER_SCRIPT.format(python=sys.executable, seed_b64=base64.b64encode(sk.seed).decode()),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    keys.write_public(root / ".3powers" / "keys" / "ledger.pub", sk.verify_key)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    monkeypatch.setenv("THREEPOWERS_SIGNER_CMD", str(script))
    return root, sk


def test_external_signer_produces_a_verifiable_ledger(tmp_path, monkeypatch):
    """HARDN-FR-006 + SC-004: signoff under an external signer yields a green, verifiable
    ledger with no ed25519-priv seed on disk or in the environment."""
    root, _sk = _external_setup(tmp_path, monkeypatch)
    assert main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"]) == 0
    res = verify_ledger(
        root / ".3powers" / "ledger.jsonl", root / ".3powers" / "keys" / "ledger.pub"
    )
    assert res.ok, res.problems  # verification code is unchanged — standard Ed25519
    # No seed anywhere the engine resolves keys from: env is clean, repo holds no key file.
    assert "THREEPOWERS_SIGNING_KEY" not in os.environ
    assert "THREEPOWERS_SIGNING_KEY_FILE" not in os.environ
    assert not list(root.rglob("*.key"))


def test_resolve_signer_prefers_external_and_reports_its_key_id(tmp_path, monkeypatch):
    """HARDN-FR-006: with the configuration set, resolve_signer returns the delegating signer."""
    root, sk = _external_setup(tmp_path, monkeypatch)
    signer = keys.resolve_signer(root)
    assert isinstance(signer, keys.CommandSigner)
    assert signer.key_id == sk.key_id  # identity comes from the committed public key


def test_unset_configuration_uses_the_software_chain_unchanged(tmp_path, monkeypatch):
    """HARDN-FR-006 + HARDN-NFR-003: without the env, the existing custody chain applies."""
    root = tmp_path / "repo"
    (root / ".3powers" / "keys").mkdir(parents=True)
    key = tmp_path / "signer.key"
    keys.write_private(key, keys.generate())
    monkeypatch.delenv("THREEPOWERS_SIGNER_CMD", raising=False)
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    signer = keys.resolve_signer(root)
    assert isinstance(signer, keys.SigningKey)


def test_failing_external_signer_raises_and_never_falls_back(tmp_path, monkeypatch):
    """HARDN-FR-006: a broken signer errors loudly even though a software key is available."""
    root, _sk = _external_setup(tmp_path, monkeypatch)
    fallback = tmp_path / "fallback.key"
    keys.write_private(fallback, keys.generate())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(fallback))  # a tempting fallback
    monkeypatch.setenv("THREEPOWERS_SIGNER_CMD", "false")  # exits 1, signs nothing
    signer = keys.resolve_signer(root)
    with pytest.raises(keys.ExternalSignerError, match="refusing to fall back"):
        signer.sign(b"payload")


def test_wrong_key_external_signer_is_caught_at_signing_time(tmp_path, monkeypatch):
    """HARDN-FR-006: a signer whose key does not match the committed pubkey fails loudly."""
    root, _sk = _external_setup(tmp_path, monkeypatch)
    # Swap the committed public key to one the script's seed does not match.
    keys.write_public(root / ".3powers" / "keys" / "ledger.pub", keys.generate().verify_key)
    signer = keys.resolve_signer(root)
    with pytest.raises(keys.ExternalSignerError, match="does not verify"):
        signer.sign(b"payload")


def test_garbage_output_external_signer_fails_loudly(tmp_path, monkeypatch):
    """HARDN-FR-006: non-base64 signer output is a configuration error, not a silent pass."""
    root, _sk = _external_setup(tmp_path, monkeypatch)
    monkeypatch.setenv("THREEPOWERS_SIGNER_CMD", "echo 'not a signature!!'")
    signer = keys.resolve_signer(root)
    with pytest.raises(keys.ExternalSignerError, match="not base64"):
        signer.sign(b"payload")


def test_external_signer_without_committed_pubkey_is_actionable(tmp_path, monkeypatch):
    """HARDN-FR-006: the committed public key is the identity — its absence is named."""
    root = tmp_path / "repo"
    (root / ".3powers" / "keys").mkdir(parents=True)
    monkeypatch.setenv("THREEPOWERS_SIGNER_CMD", "cat")
    with pytest.raises(keys.ExternalSignerError, match="install the external signer's public key"):
        keys.resolve_signer(root)


def test_cli_signoff_with_broken_external_signer_exits_usage(tmp_path, monkeypatch, capsys):
    """HARDN-FR-006: through the CLI, the loud failure is an actionable error exit."""
    root, _sk = _external_setup(tmp_path, monkeypatch)
    monkeypatch.setenv("THREEPOWERS_SIGNER_CMD", "false")
    rc = main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"])
    assert rc == 2
    assert "external signer" in capsys.readouterr().err
    # ... and nothing was appended half-signed.
    ledger_path = root / ".3powers" / "ledger.jsonl"
    assert not ledger_path.exists() or ledger_path.read_text(encoding="utf-8").strip() == ""


def test_oracle_role_external_signer_env(tmp_path, monkeypatch):
    """HARDN-FR-006: the distinct judiciary identity has its own delegation env."""
    root, sk = _external_setup(tmp_path, monkeypatch)
    # Install an oracle pubkey + oracle signer command; the oracle role must pick IT up.
    osk = keys.generate()
    script = tmp_path / "oracle-sign"
    script.write_text(
        SIGNER_SCRIPT.format(python=sys.executable, seed_b64=base64.b64encode(osk.seed).decode()),
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    keys.write_public(root / ".3powers" / "keys" / "oracle.pub", osk.verify_key)
    monkeypatch.setenv("THREEPOWERS_ORACLE_SIGNER_CMD", str(script))
    signer = keys.resolve_signer(root, role="oracle")
    assert isinstance(signer, keys.CommandSigner)
    assert signer.key_id == osk.key_id
    sig = signer.sign(b"data")
    assert osk.verify_key.verify(sig, b"data")
