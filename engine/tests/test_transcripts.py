"""Persisted, credential-redacted agent transcripts (AUTOX-FR-008, AUTOX-NFR-002).

Any stage attempt's stdout/stderr — streamed or captured — lands on disk under
``.3powers/runs/<spec-id>/``; seeded fake secrets never appear in any persisted byte; and every
failure message names the transcript path.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from threepowers import runner, runpreflight, transcripts
from threepowers.cli import main
from threepowers.ledger import Ledger


# --------------------------------------------------------------------------- redaction (unit)
def test_credential_values_are_collected_by_name_shape(monkeypatch):
    """AUTOX-NFR-002: values of credential-shaped env names are collected; short/benign ones not."""
    env = {
        "FAKE_API_TOKEN": "hunter2secret123",
        "PROVIDER_SECRET": "s3cr3t-value-xyz",
        "MY_PASSWORD": "correcthorse",
        "HOME": "/home/u",
        "DEBUG": "1",
        "SHORT_TOKEN": "abc",  # under the length floor — never scrubbed from ordinary text
    }
    vals = transcripts.credential_values(env)
    assert "hunter2secret123" in vals and "s3cr3t-value-xyz" in vals and "correcthorse" in vals
    assert "/home/u" not in vals and "1" not in vals and "abc" not in vals


def test_redact_replaces_longest_first():
    """AUTOX-NFR-002: overlapping values redact longest-first, never leaving a suffix behind."""
    long, short = "abcdefgh12345678", "abcdefgh"
    vals = transcripts.credential_values({"A_TOKEN": short, "B_TOKEN": long})
    out = transcripts.redact(f"x {long} y {short} z", vals)
    assert long not in out and short not in out
    assert out.count(transcripts.REDACTED) == 2


# --------------------------------------------------------------------------- tee (unit, real subprocess)
@pytest.mark.parametrize("stream", [False, True])
def test_dispatch_agent_tees_output_streamed_and_captured(tmp_path, stream):
    """AUTOX-FR-008: both a captured and a STREAMED dispatch persist the attempt's stdout+stderr —
    streaming mode no longer loses output."""
    sink = transcripts.TranscriptSink(tmp_path, "RUN")
    path, writer = sink.open("implement")
    code = "import sys; print('hello-out'); print('hello-err', file=sys.stderr)"
    rc, out, err = runner.dispatch_agent(
        [sys.executable, "-c", code], cwd=tmp_path, stream=stream, tee=writer
    )
    writer.close()
    assert rc == 0 and "hello-out" in out
    text = path.read_text(encoding="utf-8")
    assert "hello-out" in text and "hello-err" in text
    assert path.parent == tmp_path / ".3powers" / "runs" / "RUN"


def test_dispatch_agent_tee_redacts_secrets(tmp_path, monkeypatch):
    """AUTOX-NFR-002: a secret echoed by the agent process is redacted before it is persisted;
    pass-through to the child is untouched (the child still SEES the real value)."""
    monkeypatch.setenv("FAKE_PROVIDER_TOKEN", "supersecretvalue42")
    sink = transcripts.TranscriptSink(tmp_path, "RUN")
    path, writer = sink.open("implement")
    code = "import os; print('token is', os.environ['FAKE_PROVIDER_TOKEN'])"
    rc, out, _ = runner.dispatch_agent(
        [sys.executable, "-c", code], cwd=tmp_path, stream=False, tee=writer
    )
    writer.close()
    assert rc == 0 and "supersecretvalue42" in out  # the child saw the real value (EXEC-FR-012)
    text = path.read_text(encoding="utf-8")
    assert "supersecretvalue42" not in text and transcripts.REDACTED in text


def test_dispatch_agent_timeout_notes_the_transcript(tmp_path):
    """AUTOX-FR-008 + RUNLIVE-FR-004: a timed-out attempt still leaves its partial output and the
    timeout note in the transcript."""
    sink = transcripts.TranscriptSink(tmp_path, "RUN")
    path, writer = sink.open("implement")
    code = "import sys, time; print('started', flush=True); time.sleep(30)"
    rc, out, err = runner.dispatch_agent(
        [sys.executable, "-c", code], cwd=tmp_path, timeout=1, tee=writer
    )
    writer.close()
    assert rc == 124 and "timed out" in err
    text = path.read_text(encoding="utf-8")
    assert "started" in text and "timed out" in text


def test_attempt_paths_are_ordered_and_numbered(tmp_path):
    """AUTOX-FR-008: the layout <NN>-<step>-attempt<K>.log orders files by lifecycle position and
    numbers retries per step."""
    sink = transcripts.TranscriptSink(tmp_path, "RUN")
    p1, w1 = sink.open("specify")
    w1.close()
    p2, w2 = sink.open("specify")
    w2.close()
    p3, w3 = sink.open("implement")
    w3.close()
    assert p1.name.endswith("-specify-attempt1.log")
    assert p2.name.endswith("-specify-attempt2.log")
    assert p1.name.split("-")[0] < p3.name.split("-")[0]  # specify orders before implement


# --------------------------------------------------------------------------- CLI end-to-end
def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    for name, fam in (("claude", "anthropic"), ("codex", "openai")):
        (root / ".3powers" / "agents" / f"{name}.yaml").write_text(
            yaml.safe_dump({"command": name, "family": fam, "headless": True, "prompt_flag": "-p"}),
            encoding="utf-8",
        )
    (root / ".3powers" / "config" / "roles.yaml").write_text(
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
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    _git_init(root)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    return root


def test_cli_failure_names_the_transcript_path(run_repo, monkeypatch, capsys):
    """AUTOX-FR-008: after a failed attempt the transcript file exists with the attempt's output,
    and both the human failure message and --json carry its path."""

    def fake(argv, **kw):
        tee = kw.get("tee")
        if tee is not None:
            tee.write("agent said something long\n")
        return (1, "", "kaput")

    monkeypatch.setattr(runner, "dispatch_agent", fake)
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json", "--spec-id", "RUN"])
    assert rc != 0
    obj = json.loads(capsys.readouterr().out)
    tpath = obj["transcript"]
    assert tpath.startswith(".3powers/runs/RUN/") and tpath.endswith("-discovery-attempt2.log")
    assert "agent said something" in (run_repo / tpath).read_text(encoding="utf-8")
    # ...and the human message names it too
    monkeypatch.setattr(runner, "dispatch_agent", fake)
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc != 0 and "agent transcript: .3powers/runs/RUN/" in out


def test_failure_ledger_record_stores_the_path_not_the_content(run_repo, monkeypatch, capsys):
    """AUTOX-FR-008 + AUTOX-NFR-002: the run-failure ledger record carries the transcript PATH; a
    seeded fake credential appears in no persisted transcript and no ledger detail."""
    monkeypatch.setenv("FAKE_CI_TOKEN", "leakysecret9000")

    def fake(argv, **kw):
        tee = kw.get("tee")
        if tee is not None:
            tee.write("using token leakysecret9000 to call the provider\n")
        return (1, "", "auth failed for token leakysecret9000")

    monkeypatch.setattr(runner, "dispatch_agent", fake)
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--spec-id", "RUN"])
    assert rc != 0
    capsys.readouterr()

    ledger_text = (run_repo / ".3powers" / "ledger.jsonl").read_text(encoding="utf-8")
    assert "leakysecret9000" not in ledger_text
    entries = Ledger(run_repo / ".3powers" / "ledger.jsonl").entries()
    failure = [
        e for e in entries if e.get("type") == "run" and e["payload"].get("kind") == "failure"
    ][-1]
    assert failure["payload"]["transcript"].startswith(".3powers/runs/RUN/")
    for f in (run_repo / ".3powers" / "runs").rglob("*.log"):
        assert "leakysecret9000" not in f.read_text(encoding="utf-8")
