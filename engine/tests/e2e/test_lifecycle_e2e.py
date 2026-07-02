"""End-to-end layer: the `3pwr run` lifecycle loop through the CLI (3PWR-FR-011).

An **e2e-layer** test (its path is ``tests/e2e/``, recognised by the conformance layer detector). It
drives the whole `3pwr run` command via ``main([...])`` — orchestrator + ledger + lifecycle end to end
— so the engine's own change is exercised at the e2e layer, dogfooding tier-required layers
(3PWR-FR-064/065).
"""

from __future__ import annotations

from threepowers.cli import main


def test_run_dry_run_lifecycle_e2e(tmp_path, monkeypatch):
    """3PWR-FR-011: `3pwr run --dry-run` drives the lifecycle end to end and pauses at the spec gate."""
    repo = tmp_path / "repo"
    (repo / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(repo), "keygen", "--out", str(key)]) == 0
    assert (
        main(
            [
                "--root",
                str(repo),
                "run",
                "ship a feature",
                "--dry-run",
                "--no-input",
                "--spec-id",
                "E2E",
            ]
        )
        == 0
    )
    # Resumable from the ledger (3PWR-FR-011/019): status reflects the paused human gate.
    assert main(["--root", str(repo), "run", "--status", "--spec-id", "E2E"]) == 0
