"""The gated live end-to-end proof + the deterministic no-network property (RUNLIVE-FR-007).

Two things live here (both e2e-layer — the path is ``tests/e2e/``):

* an **opt-in** test that drives ONE real headless agent through the whole `3pwr run` lifecycle against a
  trivial sample and asserts the executive really builds software — skipped (never failed) when no agent CLI
  or opt-in is present, and it makes no network call in that skipped state;
* the **property** that the *deterministic* suite performs zero outbound model calls — the engine's only
  agent seams are the injectable subprocess dispatch and the hosted command, and neither module imports a
  network client (RUNLIVE-FR-007 property, RUNLIVE-NFR-001).
"""

from __future__ import annotations

import inspect
import os
import shutil

import pytest

from threepowers import hosted, runner
from threepowers.cli import main

# Opt-in switches for the live proof. The deterministic suite runs with neither set.
LIVE_OPT_IN = os.environ.get("THREEPOWERS_LIVE_E2E") in ("1", "true", "yes")
LIVE_AGENT = os.environ.get("THREEPOWERS_LIVE_AGENT", "claude")
LIVE_AGENT_FAMILY = os.environ.get("THREEPOWERS_LIVE_AGENT_FAMILY", "anthropic")


# --------------------------------------------------------------------------- deterministic property (no network)
def test_engine_opens_no_network_client_for_model_traffic():
    """RUNLIVE-FR-007 property / NFR-001: the engine itself makes no outbound model call.

    Its only agent seams are :func:`runner.dispatch_agent` (a local subprocess) and
    :func:`hosted.run_hosted_command` (a local subprocess); neither the runner nor the hosted module imports
    a network/HTTP client, so all model traffic originates from the *dispatched* process, never the engine."""
    banned = (
        "import requests",
        "import httpx",
        "import aiohttp",
        "import urllib",
        "from urllib",
        "import http.client",
        "import socket",
        "openai",
        "anthropic",
    )
    for mod in (runner, hosted):
        src = inspect.getsource(mod)
        for token in banned:
            assert token not in src, f"{mod.__name__} unexpectedly references {token!r}"


def test_deterministic_run_invokes_only_the_injectable_agent_seam(tmp_path, monkeypatch):
    """RUNLIVE-FR-007 property: a native run reaches a gate through the injectable dispatch seam alone — the
    real subprocess/model is never invoked in the deterministic suite (it is faked)."""
    repo = tmp_path / "repo"
    (repo / ".3powers" / "config").mkdir(parents=True)
    (repo / ".3powers" / "agents").mkdir(parents=True)
    import subprocess

    import yaml

    for name, fam in (("claude", "anthropic"), ("codex", "openai")):
        (repo / ".3powers" / "agents" / f"{name}.yaml").write_text(
            yaml.safe_dump({"command": name, "family": fam, "headless": True, "prompt_flag": "-p"}),
            encoding="utf-8",
        )
    (repo / ".3powers" / "config" / "roles.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "diversity_level": "family",
                "roles": {
                    "coder": {"integration": "claude", "model_family": "anthropic"},
                    "oracle": {"integration": "codex", "model_family": "openai"},
                },
            }
        ),
        encoding="utf-8",
    )
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(repo), "keygen", "--out", str(key)]) == 0
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(repo), check=True, capture_output=True)

    # A faked agent seam that records it was the ONLY model touchpoint, and writes the spec artifact.
    seen: list[str] = []

    def fake_dispatch(argv, **kw):
        seen.append("dispatch")
        import re

        from pathlib import Path

        if argv and "# Specify agent" in argv[-1]:
            m = re.search(r"FEATURE FOLDER: (\S+)", argv[-1])
            d = Path(kw["cwd"]) / (m.group(1) if m else "specs/LIVE")
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text("# Spec\n**Spec ID**: LIVE\n", encoding="utf-8")
        return (0, "ok", "")

    def forbid_hosted(*a, **k):
        raise AssertionError("hosted backend must not run for a CLI-backed role")

    monkeypatch.setattr(runner, "dispatch_agent", fake_dispatch)
    monkeypatch.setattr(hosted, "run_hosted_command", forbid_hosted)
    from threepowers import runpreflight

    monkeypatch.setattr(runpreflight.shutil, "which", lambda c: f"/usr/bin/{c}")

    rc = main(["--root", str(repo), "run", "add x", "--no-input", "--spec-id", "LIVE"])
    assert rc == 3 and seen  # paused at the spec gate via the injectable dispatch seam only


# --------------------------------------------------------------------------- the opt-in live proof (skipped by default)
@pytest.mark.skipif(
    not LIVE_OPT_IN,
    reason="live e2e is opt-in: set THREEPOWERS_LIVE_E2E=1 (and have an agent CLI + credentials)",
)
def test_live_end_to_end_drives_a_real_agent(tmp_path, monkeypatch):
    """RUNLIVE-FR-007/SC-003: with a real headless agent CLI + credentials, `3pwr run` drives a trivial
    intent through the executive to a deterministic verdict — proving the executive really builds software.

    Skipped (never failed) when the agent CLI is absent, so the default suite makes no network call."""
    if shutil.which(LIVE_AGENT) is None:
        pytest.skip(f"no '{LIVE_AGENT}' CLI on PATH")

    repo = tmp_path / "repo"
    (repo / ".3powers" / "config").mkdir(parents=True)
    (repo / ".3powers" / "agents").mkdir(parents=True)
    import subprocess

    import yaml

    # The coder is the real agent; the oracle uses a different family (diversity), relaxed by a deviation
    # so a single-agent maintainer can still run the proof.
    (repo / ".3powers" / "agents" / f"{LIVE_AGENT}.yaml").write_text(
        yaml.safe_dump(
            {
                "command": LIVE_AGENT,
                "family": LIVE_AGENT_FAMILY,
                "headless": True,
                "prompt_flag": "-p",
                "base_args": ["--permission-mode", "acceptEdits"] if LIVE_AGENT == "claude" else [],
            }
        ),
        encoding="utf-8",
    )
    (repo / ".3powers" / "config" / "roles.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "diversity_level": "family",
                "roles": {
                    "coder": {"integration": LIVE_AGENT, "model_family": LIVE_AGENT_FAMILY},
                    "oracle": {"integration": LIVE_AGENT, "model_family": LIVE_AGENT_FAMILY},
                },
            }
        ),
        encoding="utf-8",
    )
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(repo), "keygen", "--out", str(key)]) == 0
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(repo), check=True, capture_output=True)
    # single-agent proof: relax the model-diversity precheck via a signed deviation (FR-022 via FR-057)
    assert (
        main(
            [
                "--root",
                str(repo),
                "deviation",
                "--gate",
                "model_diversity",
                "--approver",
                "live",
                "--note",
                "single-agent live e2e",
            ]
        )
        == 0
    )

    intent = (
        "Create hello.py with a function add(a, b) that returns a + b, and a passing test for it."
    )
    # Drive the whole loop, auto-approving the two human gates as the maintainer.
    rc = main(
        [
            "--root",
            str(repo),
            "run",
            intent,
            "--no-input",
            "--tier",
            "Cosmetic",
            "--spec-id",
            "LIVE",
        ]
    )
    assert rc == 3, "the first segment (Specify→spec gate) should pause cleanly, not dispatch-fail"
    # Resume through the remaining gates until the run completes (0) or stops on a failure code.
    for _ in range(4):
        rc = main(
            [
                "--root",
                str(repo),
                "run",
                "--resume",
                "--no-input",
                "--spec-id",
                "LIVE",
                "--approver",
                "live",
            ]
        )
        if rc != 3:  # 3 = paused at the next human gate (AUTOX-FR-009) — keep resuming
            break
        status = main(["--root", str(repo), "run", "--status", "--spec-id", "LIVE"])
        assert status == 0
    # The executive must never have dispatch-failed or produced a false gate-red on a real run.
    assert rc == 0, "a real agent drove the lifecycle without a dispatch/artifact failure"
