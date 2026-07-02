"""Trust-spine hardening end to end through the CLI — e2e layer (HARDN).

Drives the hardened spine the way a user does, via ``main([...])``: custody-refused
keygen (HARDN-FR-002), a signed rotation the ledger verifies across (HARDN-FR-004),
an anchor that catches a wholesale rewrite plain verify cannot see (HARDN-FR-005),
and a committed private key failing the secret gate's core check (HARDN-FR-003) —
dogfooding the tier-required layers on this spec's own change (HARDN-NFR-004).
"""

from __future__ import annotations

import subprocess

from threepowers import keys, scanners
from threepowers.cli import main


def _git(root, *args):
    subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


def test_hardened_spine_lifecycle_e2e(tmp_path, monkeypatch, capsys):
    """HARDN-FR-002/004/005 + HARDN-NFR-001: refuse in-repo key → rotate → anchor →
    catch the regenerated ledger, all offline."""
    repo = tmp_path / "repo"
    (repo / ".3powers" / "config").mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))

    # HARDN-FR-002: an in-repo key is refused; an outside key is minted.
    assert main(["--root", str(repo), "keygen", "--out", str(repo / "k.key")]) == 2
    assert main(["--root", str(repo), "keygen", "--out", str(key)]) == 0

    base = ["--root", str(repo)]
    assert main(base + ["signoff", "--approver", "c", "--stage", "review"]) == 0
    assert main(base + ["verify"]) == 0  # compliant custody, chain intact

    # HARDN-FR-004: rotate; the succession is signed and the ledger still verifies.
    assert main(base + ["rotate-key", "--out", str(key), "--reason", "e2e"]) == 0
    assert main(base + ["signoff", "--approver", "c", "--stage", "review"]) == 0
    assert main(base + ["verify"]) == 0

    # HARDN-FR-005 + SC-003: anchor the head, then let a key holder regenerate the
    # ledger wholesale — plain verify is blind, --anchored is not.
    assert main(base + ["anchor"]) == 0
    (repo / ".3powers" / "ledger.jsonl").write_text("", encoding="utf-8")
    assert main(base + ["signoff", "--approver", "evil", "--stage", "review"]) == 0
    assert main(base + ["verify"]) == 0
    capsys.readouterr()
    assert main(base + ["verify", "--anchored"]) == 1
    out = capsys.readouterr().out
    assert "truncated" in out or "diverges" in out  # the anchor names the divergence class


def test_committed_key_material_fails_the_gate_e2e(tmp_path, monkeypatch):
    """HARDN-FR-003 + SC-002: an ed25519-priv line in the tree fails secret_scan's core check
    even with no external scanner installed."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: None)
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "leaked.key").write_text(keys.generate().to_line() + "\n", encoding="utf-8")
    gr = scanners.secret_scan(proj)
    assert gr.status == "fail"
    assert any("leaked.key" in f for f in gr.findings)


def test_trust_spine_modules_hold_the_high_risk_mutation_scope():
    """HARDN-NFR-004: the modules this spec extends are pinned in the High-risk mutation
    scope (engine/pyproject.toml [tool.mutmut] only_mutate) — the self-application bar."""
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    for mod in ("anchor.py", "canonical.py", "keys.py", "ledger.py", "speclock.py", "verify.py"):
        assert f"src/threepowers/{mod}" in text, f"{mod} missing from the mutation scope"
