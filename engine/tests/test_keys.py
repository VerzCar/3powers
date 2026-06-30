"""Signer identity tests (3PWR-FR-039, 3PWR-NFR-005): the private key stays outside the repo."""

from __future__ import annotations

import base64
import stat

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
