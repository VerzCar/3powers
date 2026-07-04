"""Auto full-mode readiness — one shared source of checks (AUTOX-FR-001…005, AUTOX-NFR-001).

Init's readiness, the standalone ``3pwr ready``, and the live run's preflight all consume
``runpreflight.check_auto``, so their verdicts cannot drift (AUTOX-FR-002 property). These tests drive
the shared checks directly and through the CLI with fake agents/PATH — fully offline (AUTOX-NFR-001).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from threepowers import runpreflight
from threepowers.cli import main
from threepowers.config import Settings

_DIVERSE_ROLES = {
    "version": 1,
    "diversity_level": "family",
    "roles": {
        "coder": {"integration": "claude", "model_family": "anthropic"},
        "oracle": {"integration": "codex", "model_family": "openai"},
    },
}


def _project(tmp_path: Path, *, roles: dict | None = None, agents: dict | None = None) -> Path:
    root = tmp_path / "proj"
    (root / ".3powers" / "config").mkdir(parents=True, exist_ok=True)
    (root / ".3powers" / "config" / "roles.yaml").write_text(
        yaml.safe_dump(roles or _DIVERSE_ROLES), encoding="utf-8"
    )
    adir = root / ".3powers" / "agents"
    adir.mkdir(parents=True, exist_ok=True)
    default_agents = {
        "claude": {"command": "claude", "family": "anthropic", "headless": True},
        "codex": {"command": "codex", "family": "openai", "headless": True},
    }
    for name, data in (agents if agents is not None else default_agents).items():
        (adir / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return root


@pytest.fixture()
def signer_key(tmp_path, monkeypatch):
    # Generate the key directly — a root-less `3pwr keygen` would resolve the REAL repo root from
    # the cwd and overwrite its committed public key.
    from threepowers import keys as keysmod

    keyfile = tmp_path / "signer.key"
    keysmod.write_private(keyfile, keysmod.generate())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    return keyfile


# --------------------------------------------------------------------------- AUTOX-FR-001 (env key validated)
def test_signer_prereq_reports_missing_env_key_file(tmp_path, monkeypatch):
    """AUTOX-FR-001: an env-supplied key file that does not exist is reported not-ready with the
    exact fix — never trusted silently."""
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(tmp_path / "nope.key"))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    p = runpreflight.signer_prereq(tmp_path)
    assert not p.ok and "THREEPOWERS_SIGNING_KEY_FILE" in p.fix and "keygen" in p.fix


def test_signer_prereq_reports_invalid_env_key_content(tmp_path, monkeypatch):
    """AUTOX-FR-001: an env-supplied key file with garbage content is reported as unusable."""
    bad = tmp_path / "bad.key"
    bad.write_text("not a key\n", encoding="utf-8")
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(bad))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    p = runpreflight.signer_prereq(tmp_path)
    assert not p.ok and "not usable" in p.fix


def test_signer_prereq_reports_invalid_env_seed(tmp_path, monkeypatch):
    """AUTOX-FR-001: a malformed inline env seed (base64 of the wrong size) is caught here,
    not at first signing."""
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY_FILE", raising=False)
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY", "AAAA")  # decodes to 3 bytes, not a 32-byte seed
    p = runpreflight.signer_prereq(tmp_path)
    assert not p.ok and "THREEPOWERS_SIGNING_KEY" in p.fix


def test_signer_prereq_ok_for_valid_env_key(tmp_path, monkeypatch, signer_key):
    """AUTOX-FR-001: a valid env-supplied key reports ready, naming the signer identity."""
    p = runpreflight.signer_prereq(tmp_path)
    assert p.ok and p.label.startswith("signer ed25519:")


def test_init_readiness_reports_unresolved_env_key(tmp_path, monkeypatch, capsys):
    """AUTOX-FR-001 (through init): `3pwr init` with a broken env key shows the signer as a
    not-ready auto-run item with its fix, instead of trusting the environment."""
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(tmp_path / "missing.key"))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    rc = main(["--root", str(root), "init", "--yes", "--json", "--language", "python"])
    assert rc == 0  # init itself still completes — seeding is independent (spec edge case)
    report = json.loads(capsys.readouterr().out)
    assert report["auto_ready"] is False
    signer = next(c for c in report["auto_run"] if c["prerequisite"] == "resolvable signing key")
    assert not signer["ok"] and "THREEPOWERS_SIGNING_KEY_FILE" in signer["fix"]


# --------------------------------------------------------------------------- AUTOX-FR-002 (one source, no drift)
def test_ready_and_run_refusal_name_the_same_items(tmp_path, monkeypatch, signer_key, capsys):
    """AUTOX-FR-002: any condition that makes `3pwr run --mode auto` refuse appears in `3pwr ready`
    as not-ready with the same named fix."""
    root = _project(tmp_path)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: None)  # no agent CLI on PATH

    assert main(["--root", str(root), "ready", "--json"]) == 1
    ready_out = json.loads(capsys.readouterr().out)
    ready_missing = {(c["prerequisite"], c["fix"]) for c in ready_out["checks"] if not c["ok"]}
    assert ready_out["ready"] is False and ready_missing

    rc = main(["--root", str(root), "run", "x", "--no-input", "--json", "--spec-id", "P"])
    assert rc != 0
    run_out = json.loads(capsys.readouterr().out)
    run_missing = {(m["prerequisite"], m["fix"]) for m in run_out["missing"]}
    assert run_missing == ready_missing


def test_run_starts_when_ready_says_ready(tmp_path, monkeypatch, signer_key, capsys):
    """AUTOX-FR-002 / AUTOX-SC-001: when every prerequisite is met, `ready` says ready and the run's
    preflight agrees (the run proceeds past preflight rather than refusing)."""
    root = _project(tmp_path)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")
    assert main(["--root", str(root), "ready"]) == 0
    capsys.readouterr()
    from threepowers import runner as runnermod

    monkeypatch.setattr(runnermod, "dispatch_agent", lambda argv, **kw: (1, "", "boom"))
    main(["--root", str(root), "run", "x", "--no-input", "--json", "--spec-id", "P"])
    out = capsys.readouterr().out
    assert "preflight_failed" not in out  # preflight agreed; the failure (if any) came later


# --------------------------------------------------------------------------- AUTOX-FR-003 (`3pwr ready`)
def test_ready_exits_distinctly_and_changes_nothing_on_disk(
    tmp_path, monkeypatch, signer_key, capsys
):
    """AUTOX-FR-003: `3pwr ready` exits distinctly for ready vs not-ready, lists each unmet item
    with its fix, supports --json, and changes nothing on disk."""
    root = _project(tmp_path)

    def snapshot() -> dict[str, float]:
        return {str(p): p.stat().st_mtime for p in root.rglob("*") if p.is_file()}

    before = snapshot()
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: None)
    assert main(["--root", str(root), "ready", "--json"]) == 1  # not ready
    not_ready = json.loads(capsys.readouterr().out)
    assert all(c["fix"] for c in not_ready["checks"] if not c["ok"])

    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")
    assert main(["--root", str(root), "ready", "--json"]) == 0  # ready — a distinct exit
    ready = json.loads(capsys.readouterr().out)
    assert ready["ready"] is True
    assert snapshot() == before  # read-only: nothing on disk changed


def test_ready_outside_a_project_names_init(tmp_path, capsys):
    """AUTOX-FR-003 (edge): outside an initialized repo the check says to run `3pwr init` first —
    an actionable message, never a stack trace (EXEC-NFR-005)."""
    rc = main(["--root", str(tmp_path), "ready"])
    err = capsys.readouterr().err
    assert rc == 2 and "3pwr init" in err


# --------------------------------------------------------------------------- AUTOX-FR-004 (honest labels)
def test_present_cli_reports_authentication_caveat(tmp_path, monkeypatch, signer_key):
    """AUTOX-FR-004: a present agent CLI is reported as present WITH the authentication caveat —
    readiness never claims a prerequisite it did not probe."""
    root = _project(tmp_path)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")
    s = Settings(root=root)
    prqs = runpreflight.check_auto(
        s, coder_agent="claude", oracle_agent="codex", entries=[], spec_id=None
    )
    agent_items = [p for p in prqs if "agent" in p.name]
    assert agent_items and all(p.ok for p in agent_items)
    assert all("authentication not verified" in p.label for p in agent_items)


# --------------------------------------------------------------------------- AUTOX-FR-005 (next steps)
def test_init_next_steps_are_exactly_the_unmet_fixes_in_order(tmp_path, monkeypatch, capsys):
    """AUTOX-FR-005: after an init with N unmet auto-run items, the next-steps list contains exactly
    those N fixes, in dependency order (key → coder agent → oracle agent)."""
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(tmp_path / "missing.key"))
    monkeypatch.delenv("THREEPOWERS_SIGNING_KEY", raising=False)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: None)
    rc = main(["--root", str(root), "init", "--yes", "--json", "--language", "python"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    unmet = [c for c in report["auto_run"] if not c["ok"]]
    assert report["next_steps"] == [c["fix"] for c in unmet]
    # dependency order: the signing key comes first when unmet
    assert "keygen" in report["next_steps"][0]


def test_init_all_met_reports_auto_ready(tmp_path, monkeypatch, signer_key, capsys):
    """AUTOX-FR-005 (converse) / AUTOX-SC-001: with every prerequisite met, init reports auto_ready
    and an empty next-steps list."""
    root = _project(tmp_path)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")
    rc = main(["--root", str(root), "init", "--yes", "--json", "--language", "python"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["auto_ready"] is True and report["next_steps"] == []


# --------------------------------------------------------------------------- AUTOX-NFR-001
def test_readiness_is_deterministic_and_fully_offline(tmp_path, monkeypatch, signer_key, capsys):
    """AUTOX-NFR-001: the readiness checks run with networking disabled, and identical state yields
    identical output — no network or model call anywhere in the feature."""
    import socket

    def _no_network(*_a, **_k):
        raise RuntimeError("readiness attempted a network call")

    monkeypatch.setattr(socket, "socket", _no_network)
    root = _project(tmp_path)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")
    assert main(["--root", str(root), "ready", "--json"]) == 0  # ran with sockets blocked
    first = json.loads(capsys.readouterr().out)
    assert main(["--root", str(root), "ready", "--json"]) == 0
    second = json.loads(capsys.readouterr().out)
    assert first == second  # identical state → identical output
