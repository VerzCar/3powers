"""Build provenance + deploy gate (3PWR-FR-066/067/068)."""

from __future__ import annotations

import hashlib

from threepowers import keys, provenance


def test_sha256_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"abc")
    assert provenance.sha256_file(p) == "sha256:" + hashlib.sha256(b"abc").hexdigest()


def test_sbom_from_package_lock(tmp_path):
    (tmp_path / "package-lock.json").write_text(
        '{"packages":{"":{"version":"1.0.0"},"node_modules/left-pad":{"version":"2.3.4"}}}',
        encoding="utf-8",
    )
    components = provenance.sbom(tmp_path)["components"]
    assert any(c["name"] == "left-pad" and c["version"] == "2.3.4" for c in components)


def test_sign_and_verify_record(tmp_path):
    """3PWR-FR-068: provenance is signed with the independent Ed25519 identity."""
    sk = keys.generate()
    (tmp_path / "art.bin").write_bytes(b"shipme")
    record = provenance.build_record(tmp_path, tmp_path, tmp_path / "art.bin")
    signed = provenance.sign_record(record, sk)
    assert provenance.verify_record(signed, sk.verify_key)  # FR-066
    signed["artifact"]["sha256"] = "sha256:" + ("0" * 64)  # tamper
    assert not provenance.verify_record(signed, sk.verify_key)  # FR-067
