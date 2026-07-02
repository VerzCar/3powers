"""Spec-lock end to end through the CLI — e2e layer (SLOCK).

Seal → mutate → detect → re-approve, all via ``main([...])``: the full SLOCK loop as a
user drives it (SLOCK-FR-001/006/007, SC-006 self-application — the same commands guard
this repo's own specs).
"""

from __future__ import annotations

from threepowers.cli import main

SPEC = "**Spec ID**: E2E\n\n- **E2E-FR-001**: The law shall hold.\n"


def test_speclock_seal_mutate_detect_reapprove_e2e(tmp_path, monkeypatch):
    """SLOCK-FR-001/003/006/007: seal at sign-off, catch the mutation, re-approve to recover."""
    (tmp_path / ".3powers" / "config").mkdir(parents=True)
    spec = tmp_path / "specs" / "spec.md"
    spec.parent.mkdir()
    spec.write_text(SPEC, encoding="utf-8")
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(tmp_path), "keygen", "--out", str(key)]) == 0

    base = ["--root", str(tmp_path)]
    signoff = base + [
        "signoff",
        "--approver",
        "carlo",
        "--stage",
        "spec",
        "--spec-id",
        "E2E",
        "--spec",
        str(spec),
    ]
    diff = base + ["spec", "diff", "--spec-id", "E2E"]

    assert main(signoff) == 0  # SLOCK-FR-001: hash sealed into the signed sign-off
    assert main(diff) == 0  # matches its approval hash (SLOCK-FR-007)

    spec.write_text(SPEC + "- **E2E-FR-666**: silently injected.\n", encoding="utf-8")
    assert main(diff) == 1  # the mutation is surfaced (SLOCK-FR-007)

    assert main(signoff) == 0  # a fresh Spec-stage sign-off supersedes (SLOCK-FR-006)
    assert main(diff) == 0  # green again against the new hash
    assert main(base + ["verify"]) == 0  # the ledger still verifies (SLOCK-NFR-002)
