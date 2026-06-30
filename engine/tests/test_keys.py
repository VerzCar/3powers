"""Signer identity tests (3PWR-FR-039, 3PWR-NFR-005): the private key stays outside the repo."""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

import pytest

from threepowers import keys


def test_sign_verify_roundtrip():
    sk = keys.generate()
    sig = sk.sign(b"hello")
    assert sk.verify_key.verify(sig, b"hello")
    assert not sk.verify_key.verify(sig, b"tampered")


def test_key_id_format():
    sk = keys.generate()
    assert sk.key_id.startswith("ed25519:")
    assert len(sk.key_id.split(":")[1]) == 16


def test_public_line_roundtrip(tmp_path):
    sk = keys.generate()
    p = tmp_path / "k.pub"
    keys.write_public(p, sk.verify_key)
    vk = keys.load_public(p)
    assert vk.raw == sk.verify_key.raw and vk.key_id == sk.key_id


def test_private_line_roundtrip_and_permissions(tmp_path):
    sk = keys.generate()
    p = tmp_path / "k.key"
    keys.write_private(p, sk)
    assert stat.S_IMODE(p.stat().st_mode) == 0o600  # 3PWR-NFR-005: protected on disk
    assert keys.SigningKey.from_line(p.read_text()).seed == sk.seed


def test_resolve_from_env_file(tmp_path, monkeypatch):
    sk = keys.generate()
    p = tmp_path / "k.key"
    keys.write_private(p, sk)
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(p))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    assert keys.resolve_signing_key(tmp_path).seed == sk.seed


def test_resolve_from_env_seed(tmp_path, monkeypatch):
    sk = keys.generate()
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY", base64.b64encode(sk.seed).decode())
    assert keys.resolve_signing_key(tmp_path).seed == sk.seed


def test_resolve_missing_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    with pytest.raises(FileNotFoundError):
        keys.resolve_signing_key(tmp_path)


def test_malformed_lines_rejected():
    with pytest.raises(ValueError):
        keys.VerifyKey.from_line("garbage line")
    with pytest.raises(ValueError):
        keys.SigningKey.from_line("garbage line")


def test_default_private_path_layout(tmp_path):
    """The default key path is ~/.config/3powers/<repo>.key, OUTSIDE the repo (3PWR-NFR-005)."""
    repo = tmp_path / "myrepo"
    p = keys.default_private_path(repo)
    assert p.name == "myrepo.key"
    assert p.parent.name == "3powers"
    assert p.parent.parent.name == ".config"
    # The path is anchored at the user's home, not inside the repo.
    assert str(p).startswith(str(Path(os.path.expanduser("~"))))
    assert str(repo) not in str(p)


def test_resolve_from_default_path(tmp_path, monkeypatch):
    """With no env override, the key is read from the default user path (3PWR-NFR-005)."""
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    sk = keys.generate()
    repo = tmp_path / "repo"
    keys.write_private(keys.default_private_path(repo), sk)
    assert keys.resolve_signing_key(repo).seed == sk.seed


def test_resolve_missing_message_names_keygen_and_outside(tmp_path, monkeypatch):
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "no-home"))
    with pytest.raises(FileNotFoundError) as exc:
        keys.resolve_signing_key(tmp_path)
    msg = str(exc.value)
    assert "keygen" in msg and "OUTSIDE the repository" in msg


def test_write_creates_missing_parent_dirs(tmp_path):
    """write_* must create missing parent directories (parents=True)."""
    sk = keys.generate()
    pub = tmp_path / "deep" / "nested" / "k.pub"
    priv = tmp_path / "other" / "deep" / "k.key"
    keys.write_public(pub, sk.verify_key)
    keys.write_private(priv, sk)
    assert pub.exists() and priv.exists()


def test_public_key_file_is_one_trailing_newline(tmp_path):
    sk = keys.generate()
    p = tmp_path / "k.pub"
    keys.write_public(p, sk.verify_key)
    text = p.read_text(encoding="utf-8")
    assert text == sk.verify_key.to_line() + "\n"
    assert text.count("\n") == 1
