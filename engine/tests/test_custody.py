"""Key custody, the threat-model document, and the core private-key scan (HARDN-FR-001/002/003).

Unit layer for the trust-spine hardening spec (`specs-src/005-trust-hardening/spec.md`): the custody
preflight, the keygen refusal, and the always-on ``ed25519-priv`` secret check are exercised
directly; the threat-model document is asserted structurally, docs-conformance style.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from threepowers import keys, scanners
from threepowers.cli import main
from threepowers.verdict import STATUS_FAIL, STATUS_SKIP

REPO = Path(__file__).resolve().parents[2]
THREAT_MODEL = REPO / "docs" / "threat-model.md"

_DOCS = [REPO / "README.md", REPO / "SECURITY.md", THREAT_MODEL]
docs_present = pytest.mark.skipif(
    not all(p.exists() for p in _DOCS),
    reason="repo docs tree not present (packaged engine or copied layout)",
)


# --------------------------------------------------------------------------- HARDN-FR-001
@docs_present
def test_threat_model_document_exists_with_required_sections():
    """HARDN-FR-001: the threat model covers ledger, provenance, custody, anchoring, oracle attestation."""
    text = THREAT_MODEL.read_text(encoding="utf-8")
    for section in (
        "## What the ledger proves",
        "## Tamper classes detected by `3pwr verify`",
        "## What `verify` cannot detect",
        "## Key custody",
        "## Anchoring",
        "## Provenance",
        "## Oracle model attestation",
    ):
        assert section in text, f"missing section: {section}"
    # The detected tamper classes are all named (HARDN-FR-001).
    for tamper in ("Chain break", "Sequence gap", "Payload edit", "Signature mismatch", "Key swap"):
        assert tamper in text
    # ... and so are the residual, the custody boundary, and the self-reported oracle claim.
    assert "holder of the signing key" in text
    assert "executive agents must never be able to resolve" in text
    assert "self-reported" in text


@docs_present
def test_threat_model_linked_from_readme_and_security():
    """HARDN-FR-001: the threat model is reachable from README.md and SECURITY.md."""
    assert "docs/threat-model.md" in (REPO / "README.md").read_text(encoding="utf-8")
    assert "docs/threat-model.md" in (REPO / "SECURITY.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- HARDN-FR-002
def _mk_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    return root


def test_keygen_refuses_a_private_key_inside_the_working_tree(tmp_path, monkeypatch, capsys):
    """HARDN-FR-002: `3pwr keygen` with an in-repo output path is refused, actionably."""
    root = _mk_repo(tmp_path)
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    rc = main(["--root", str(root), "keygen", "--out", str(root / "signer.key")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "INSIDE the repository working tree" in err
    assert "--out" in err  # the message says how to fix it
    assert not (root / "signer.key").exists()


def test_keygen_outside_the_working_tree_is_unaffected(tmp_path, monkeypatch):
    """HARDN-FR-002 (compliant setup): an outside-repo key is created exactly as before."""
    root = _mk_repo(tmp_path)
    out = tmp_path / "signer.key"
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    assert main(["--root", str(root), "keygen", "--out", str(out)]) == 0
    assert out.exists()
    assert (out.stat().st_mode & 0o777) == 0o600


def test_custody_findings_flag_key_inside_working_tree(tmp_path, monkeypatch):
    """HARDN-FR-002: a resolved private-key path inside the working tree is a key_custody finding."""
    root = _mk_repo(tmp_path)
    inside = root / "leaked.key"
    keys.write_private(inside, keys.generate())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(inside))
    findings = keys.custody_findings(root)
    assert any("key_custody" in f and "INSIDE the working tree" in f for f in findings)


def test_custody_findings_flag_world_readable_key(tmp_path, monkeypatch):
    """HARDN-FR-002: a key file readable by other users is a key_custody finding."""
    root = _mk_repo(tmp_path)
    key = tmp_path / "signer.key"
    keys.write_private(key, keys.generate())
    os.chmod(key, 0o644)
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    findings = keys.custody_findings(root)
    assert any("readable by other users" in f and "chmod 600" in f for f in findings)


def test_custody_findings_empty_for_compliant_setup(tmp_path, monkeypatch):
    """HARDN-FR-002 + HARDN-NFR-001: owner-only key outside the tree → nothing; deterministic."""
    root = _mk_repo(tmp_path)
    key = tmp_path / "signer.key"
    keys.write_private(key, keys.generate())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    monkeypatch.delenv("THREEPOWERS_ORACLE_SIGNING_KEY_FILE", raising=False)
    assert keys.custody_findings(root) == []
    # HARDN-NFR-001: identical inputs → identical findings, run twice.
    assert keys.custody_findings(root) == keys.custody_findings(root)


def test_verify_fails_on_custody_violation(tmp_path, monkeypatch, capsys):
    """HARDN-FR-002: `3pwr verify` emits the key_custody finding and fails on a violation."""
    root = _mk_repo(tmp_path)
    outside = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(outside))
    assert main(["--root", str(root), "keygen", "--out", str(outside)]) == 0
    assert main(["--root", str(root), "verify"]) == 0  # compliant setup emits nothing

    inside = root / "oops.key"
    inside.write_bytes(outside.read_bytes())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(inside))
    capsys.readouterr()
    assert main(["--root", str(root), "verify"]) == 1
    assert "key_custody" in capsys.readouterr().out


# --------------------------------------------------------------------------- HARDN-FR-003
def _no_external_scanner(monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: None)


def test_secret_scan_fails_on_committed_private_key_without_external_tool(tmp_path, monkeypatch):
    """HARDN-FR-003: a tracked ed25519-priv line fails the gate even with no scanner installed."""
    _no_external_scanner(monkeypatch)
    (tmp_path / "oops.key").write_text(keys.generate().to_line() + "\n", encoding="utf-8")
    gr = scanners.secret_scan(tmp_path)
    assert gr.status == STATUS_FAIL
    assert any("ed25519-priv" in f and "oops.key" in f for f in gr.findings)


def test_secret_scan_core_check_never_quarantined_away(tmp_path, monkeypatch):
    """HARDN-FR-003: with no scanner and no key material, the quarantine names the core check as run."""
    _no_external_scanner(monkeypatch)
    (tmp_path / "src.py").write_text('PRIVATE_PREFIX = "ed25519-priv"\n', encoding="utf-8")
    gr = scanners.secret_scan(tmp_path)
    assert gr.status == STATUS_SKIP  # external portion quarantined (3PWR-NFR-015)
    assert any("core ed25519-priv" in f and "clean" in f for f in gr.findings)


def test_secret_scan_source_mention_of_format_is_not_flagged(tmp_path, monkeypatch):
    """HARDN-FR-003: the format's *mention* (a short literal, docs) is not key material."""
    _no_external_scanner(monkeypatch)
    (tmp_path / "keys.py").write_text(
        'PRIVATE_PREFIX = "ed25519-priv"\n# format: ed25519-priv <base64-raw-seed-32>\n',
        encoding="utf-8",
    )
    gr = scanners.secret_scan(tmp_path)
    assert not any("keys.py" in f for f in gr.findings if "ed25519-priv private-key" in f)


def test_secret_scan_core_findings_are_deterministic(tmp_path, monkeypatch):
    """HARDN-NFR-001: two runs over identical inputs produce identical findings."""
    _no_external_scanner(monkeypatch)
    (tmp_path / "oops.key").write_text(keys.generate().to_line() + "\n", encoding="utf-8")
    a = scanners.secret_scan(tmp_path)
    b = scanners.secret_scan(tmp_path)
    assert a.findings == b.findings and a.status == b.status
