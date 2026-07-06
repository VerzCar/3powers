"""Run identity — the workspace `NNN` flows through the ledger, hints, commits, and gate details
(RUNID, spec 020).

Exercises Track A of plan 030 with fake agents and no network: the spec id derived from the run
workspace's `NNN` when no ``--spec-id`` is given (RUNID-FR-001), the explicit flag always winning
(RUNID-FR-002), the derived identity reaching every downstream consumer — ledger entries, pause
output, resume hints, notifications, the stage commit message (RUNID-FR-003) — the referenced
requirement ids riding the spec-conformance verdict details into the ledger (RUNID-FR-004), the
ledger file bundled into every producing stage commit (RUNID-FR-005), and the oracle destination
named by spec id, never a slug (RUNID-FR-006).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from threepowers import keys, notify, prompts, runner, runpreflight, scaffold
from threepowers.cli import EXIT_PAUSED, main
from threepowers.conformance import run_conformance
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_FAIL, Verdict


# --------------------------------------------------------------------------- fixtures (fake agent, no network)
def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(root), capture_output=True, text=True, check=False
    )
    return proc.stdout.strip()


def _git_init(root: Path) -> None:
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "config", "user.email", "human@e.st"],
        ["git", "config", "user.name", "human"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _writer():
    """A fake agent writing the specify stage's artifact into the folder the prompt names, ending
    its output with the requested ``COMMIT:`` line (the first run segment ends at spec approval)."""

    def fake(argv, **kw):
        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        m = re.search(r"FEATURE FOLDER: (\S+)", prompt)
        d = cwd / (m.group(1) if m else "specs/unknown")
        out = "changes written"
        if "STAGE: Specify" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text("# Spec\n**Spec ID**: FEAT\n", encoding="utf-8")
            out += "\nCOMMIT: authored the specify work for the run"
        tee = kw.get("tee")
        if tee is not None:  # a real dispatch tees stdout into the persisted transcript
            tee.write(out + "\n")
            tee.flush()
        return (0, out, "")

    return fake


@pytest.fixture()
def run_repo(tmp_path, monkeypatch):
    """A git repo with agents/roles/signer configured and a fake headless coder — no network."""
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
    # Seed specs/029-seed so the run's workspace allocates 030 — committed, so the GITX
    # clean-start guard sees a clean tree.
    seed = root / "specs" / "029-seed"
    seed.mkdir(parents=True)
    (seed / "spec.md").write_text("# seed\n", encoding="utf-8")
    _git_init(root)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", _writer())
    return root


def _entries(root: Path) -> list[dict]:
    return Ledger(root / ".3powers" / "ledger.jsonl").entries()


# --------------------------------------------------------------------------- A1. derivation (RUNID-FR-001/002)
def test_spec_id_derives_from_workspace_nnn(run_repo, capsys):
    """RUNID-FR-001 + RUNID-FR-003: a fresh run with no --spec-id allocating specs/030-add-x/
    derives spec id "030" — every ledger entry of the run and the paused-gate report carry it."""
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_PAUSED
    assert (run_repo / "specs" / "030-add-x").is_dir()
    assert obj["status"] == "paused_at_gate" and obj["spec_id"] == "030"
    run_entries = [e for e in _entries(run_repo) if e.get("type") == "run"]
    assert run_entries and all(e["spec_id"] == "030" for e in run_entries)
    kinds = {e["payload"].get("kind") for e in run_entries}
    assert {"start", "stage", "gate"} <= kinds  # start, stage, and gate records all carry the NNN


def test_explicit_spec_id_always_wins(run_repo, capsys):
    """RUNID-FR-002: an explicit --spec-id is the run's identity unchanged — the allocated
    workspace NNN never overrides it."""
    rc = main(
        ["--root", str(run_repo), "run", "add x", "--no-input", "--json", "--spec-id", "PAY"]
    )
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_PAUSED and obj["spec_id"] == "PAY"
    assert (run_repo / "specs" / "030-add-x").is_dir()  # the workspace still allocated its NNN
    run_entries = [e for e in _entries(run_repo) if e.get("type") == "run"]
    assert run_entries and all(e["spec_id"] == "PAY" for e in run_entries)


# --------------------------------------------------------------------------- A1. consumers (RUNID-FR-003)
def test_derived_id_reaches_hints_commits_and_notifications(run_repo, monkeypatch, capsys):
    """RUNID-FR-003: the derived NNN reaches the resume-hint commands of the pause screen, the
    stage commit message, and the notification subject — no consumer falls back to "RUN"."""
    subjects: list[str] = []

    def record_dispatch(channels, event, subject, message):
        subjects.append(subject)
        return []

    monkeypatch.setattr(notify, "dispatch", record_dispatch)
    assert main(["--root", str(run_repo), "run", "add x", "--no-input"]) == EXIT_PAUSED
    out = capsys.readouterr().out
    assert "3pwr run --resume --spec-id 030" in out  # the copy-pasteable resume hint
    assert "--spec-id RUN" not in out
    assert subjects and all(s == "3pwr run 030" for s in subjects)  # notification subject
    head_subject = _git(run_repo, "log", "-1", "--pretty=%s")
    assert head_subject.startswith("3pwr(030): specify")  # the stage commit carries the NNN


# --------------------------------------------------------------------------- A3. requirement ids (RUNID-FR-004)
def test_conformance_details_carry_the_referenced_ids(tmp_path):
    """RUNID-FR-004: the spec-conformance gate exposes the requirement ids the scanned tests
    actually reference under details["requirement_ids"], sorted; the declared set rides a
    separate key and the verdict aggregates a non-empty requirement_ids()."""
    spec = tmp_path / "spec.md"
    spec.write_text(
        "**Spec ID**: VUTIL\n\n- **VUTIL-FR-001**: a\n- **VUTIL-FR-002**: b\n", encoding="utf-8"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "t.test.ts").write_text('it("VUTIL-FR-001 ok", () => {});\n', encoding="utf-8")
    gate = run_conformance(spec, [tests])
    assert gate.status == STATUS_FAIL  # FR-002 untested — the gate still names what IS referenced
    assert gate.details["requirement_ids"] == ["VUTIL-FR-001"]
    assert gate.details["declared_requirements"] == ["VUTIL-FR-001", "VUTIL-FR-002"]
    v = Verdict(spec_id="VUTIL", tier="Standard", adapter="typescript")
    v.add(gate)
    assert v.requirement_ids() == ["VUTIL-FR-001"]  # non-empty on the ledger append path


def test_referenced_ids_reach_the_signed_ledger_entry(tmp_path, monkeypatch):
    """RUNID-FR-004: a verdict appended to the ledger carries the conformance-referenced ids in
    the entry's requirement_ids field — populated, not always empty."""
    root = tmp_path / "repo"
    (root / ".3powers").mkdir(parents=True)
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    spec = tmp_path / "spec.md"
    spec.write_text("**Spec ID**: VUTIL\n\n- **VUTIL-FR-001**: a\n", encoding="utf-8")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "t.test.ts").write_text('it("VUTIL-FR-001 ok", () => {});\n', encoding="utf-8")
    v = Verdict(spec_id="VUTIL", tier="Standard", adapter="typescript")
    v.add(run_conformance(spec, [tests]))
    sk = keys.resolve_signer(root)
    entry = Ledger(root / ".3powers" / "ledger.jsonl").append(
        "verdict", v.to_dict(), sk, spec_id=v.spec_id, requirement_ids=v.requirement_ids()
    )
    assert entry["requirement_ids"] == ["VUTIL-FR-001"]


# --------------------------------------------------------------------------- A4. ledger in the commit (RUNID-FR-005)
def test_stage_commit_bundles_the_ledger_file(run_repo):
    """RUNID-FR-005: a producing stage's commit contains .3powers/ledger.jsonl alongside the
    stage's artifact, and the working tree keeps no uncommitted ledger change at the pause."""
    assert main(["--root", str(run_repo), "run", "add x", "--no-input"]) == EXIT_PAUSED
    subject = _git(run_repo, "log", "-1", "--pretty=%s")
    assert subject.startswith("3pwr(030): specify")
    files = _git(run_repo, "show", "--name-only", "--pretty=format:", "HEAD").split()
    assert ".3powers/ledger.jsonl" in files
    assert "specs/030-add-x/spec.md" in files


# --------------------------------------------------------------------------- A2. oracle destination (RUNID-FR-006)
def test_oracle_instructions_target_the_spec_id_folder():
    """RUNID-FR-006: the oracle stage instruction — engine built-in and the scaffolded repo
    template — names tests/oracle/<spec-id>/ as the destination, never a slug-based folder."""
    body = prompts.stage_prompt_body("oracle")
    assert "tests/oracle/<spec-id>/" in body
    assert "slug" not in body.lower()
    template = scaffold.SCAFFOLD_DIR / "templates" / "agents" / "oracle.agent.md"
    text = template.read_text(encoding="utf-8")
    assert "tests/oracle/<spec-id>/" in text
    assert "<slug>" not in text and "{slug}" not in text
