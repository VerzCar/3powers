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

from threepowers import (
    cli,
    keys,
    notify,
    orchestrate,
    prompts,
    runner,
    runpreflight,
    scaffold,
    workspace,
)
from threepowers.cli import EXIT_FAIL, EXIT_PAUSED, main
from threepowers.conformance import run_conformance
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_FAIL, GateResult, Verdict


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
        m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
        d = cwd / (m.group(1) if m else "specs-src/unknown")
        out = "changes written"
        if "# Discovery agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
            out += "\nCOMMIT: authored the discovery work for the run"
        elif "# Specify agent" in prompt:
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
    # Seed specs-src/029-seed so the run's workspace allocates 030 — committed, so the GITX
    # clean-start guard sees a clean tree.
    seed = root / "specs-src" / "029-seed"
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
    """RUNID-FR-001 + RUNID-FR-003: a fresh run with no --spec-id allocating specs-src/030-add-x/
    derives spec id "030" — every ledger entry of the run and the paused-gate report carry it."""
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_PAUSED
    assert (run_repo / "specs-src" / "030-add-x").is_dir()
    assert obj["status"] == "paused_at_gate" and obj["spec_id"] == "030"
    run_entries = [e for e in _entries(run_repo) if e.get("type") == "run"]
    assert run_entries and all(e["spec_id"] == "030" for e in run_entries)
    kinds = {e["payload"].get("kind") for e in run_entries}
    assert {"start", "stage", "gate"} <= kinds  # start, stage, and gate records all carry the NNN


def test_explicit_spec_id_always_wins(run_repo, capsys):
    """RUNID-FR-002: an explicit --spec-id is the run's identity unchanged — the allocated
    workspace NNN never overrides it."""
    rc = main(["--root", str(run_repo), "run", "add x", "--no-input", "--json", "--spec-id", "PAY"])
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_PAUSED and obj["spec_id"] == "PAY"
    assert (run_repo / "specs-src" / "030-add-x").is_dir()  # the workspace still allocated its NNN
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
    # HEAD at the pause is the engine's own state commit; the producing specify commit carries the
    # NNN in its subject just the same — locate it in the branch log.
    specify_subject = _git(
        run_repo, "log", "-1", "-F", "--grep", "3pwr(030): specify", "--pretty=%s"
    )
    assert specify_subject.startswith("3pwr(030): specify")  # the stage commit carries the NNN


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
    # HEAD at the pause is the engine's own state commit; the producing specify commit is the one
    # that bundles the ledger alongside its artifact — locate and inspect it.
    specify_hash = _git(run_repo, "log", "-1", "-F", "--grep", "3pwr(030): specify", "--pretty=%H")
    subject = _git(run_repo, "show", "-s", "--pretty=%s", specify_hash)
    assert subject.startswith("3pwr(030): specify")
    files = _git(run_repo, "show", "--name-only", "--pretty=format:", specify_hash).split()
    assert ".3powers/ledger.jsonl" in files
    assert "specs-src/030-add-x/spec.md" in files
    # and the pause leaves no uncommitted ledger change behind
    assert ".3powers/ledger.jsonl" not in _git(run_repo, "status", "--porcelain")


# --------------------------------------------------------------------------- A2. oracle destination (RUNID-FR-006)
def test_oracle_instructions_target_the_feature_folder_id():
    """RUNID-FR-006 (as re-keyed by plan 033 Track E): the oracle stage instruction — engine
    built-in and the scaffolded repo template — takes its test destination from the
    $ORACLE_DESTINATION variable (under tests/oracle/, keyed by the run's feature-folder id);
    the retired <spec-id> and <NNN>-<slug> placeholders are gone."""
    body = prompts.resolve_body("oracle", None)
    assert "$ORACLE_DESTINATION" in body
    assert "<spec-id>" not in body and "<NNN>-<slug>" not in body
    template = scaffold.SCAFFOLD_DIR / "templates" / "agents" / "oracle.agent.md"
    text = template.read_text(encoding="utf-8")
    assert "$ORACLE_DESTINATION" in text
    assert "<spec-id>" not in text and "<NNN>-<slug>" not in text


def test_run_oracle_stage_prompt_names_the_concrete_destination(tmp_path):
    """Track E (plan 033): the assembled oracle-stage prompt on the run path substitutes the
    concrete keyed destination tests/oracle/<NNN>-<slug>/ and the run's feature folder — both
    computed from the run's bound feature folder — into the template body, and ships no
    placeholder token to the agent."""
    from threepowers.cli.run import _feature_folder_value, _oracle_destination_value
    from threepowers.config import Settings

    root = tmp_path / "repo"
    fdir = root / "specs-src" / "030-add-x"
    fdir.mkdir(parents=True)
    s = Settings(root=root)
    assert _oracle_destination_value(fdir) == "tests/oracle/030-add-x/"
    assert _feature_folder_value(s, fdir) == "specs-src/030-add-x"
    assembled = prompts.assemble(
        "oracle",
        intent="add x",
        spec_text="S",
        variables={
            "FEATURE_FOLDER": _feature_folder_value(s, fdir),
            "ORACLE_DESTINATION": _oracle_destination_value(fdir),
        },
    )
    assert "tests/oracle/030-add-x/" in assembled
    assert "specs-src/030-add-x" in assembled  # oracle.md lands flat in the feature folder
    for token in ("<spec-id>", "<NNN>-<slug>", "<feature>", "$ORACLE_DESTINATION"):
        assert token not in assembled
    # a run without a bound folder substitutes nothing rather than a placeholder
    assert _oracle_destination_value(None) == ""
    assert _feature_folder_value(s, None) == ""


# ----------------------------------------------------- Track A (plan 036): the numeric id in every hint
_CMD_ID_RE = re.compile(r"3pwr\b[^\n]*?--(?:spec-id|id)[= ]+(\S+)")


def _emitted_command_ids(text: str) -> list[str]:
    """Every ``--spec-id`` / ``--id`` argument of a rendered ``3pwr …`` command in ``text``."""
    return [m.strip("`\"'").rstrip(".,)") for m in _CMD_ID_RE.findall(text)]


def _assert_emitted_command_ids_numeric(text: str) -> None:
    """Guard: every ``--spec-id`` / ``--id`` argument of a rendered ``3pwr`` command is the numeric
    feature-folder id (or a documentation placeholder) — never a non-numeric front-matter prefix a
    resume/inspect/re-dispatch command cannot resolve via ``resolve_feature_dir``."""
    for val in _emitted_command_ids(text):
        if val.startswith("<") or val in {"SPEC_ID", "NNN", "ID"}:
            continue  # an argparse metavar / documentation token, not an emitted value
        assert val.isdigit(), f"non-numeric id emitted in a 3pwr command: {val!r}"


def _gate_repo(tmp_path: Path) -> Path:
    """A rooted repo with one numbered feature folder whose spec front-matter prefix (FEAT) is
    deliberately NOT the numeric id — so a leaked prefix in any hint is caught."""
    (tmp_path / ".3powers" / "config").mkdir(parents=True)
    feature = tmp_path / "specs-src" / "042-widget"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text(
        "**Spec ID**: FEAT\n\n- **FEAT-FR-001**: shall.\n", encoding="utf-8"
    )
    return tmp_path


def _failing_verdict() -> Verdict:
    """A finalized red verdict whose ``spec_id`` is the front-matter prefix FEAT (never the id)."""
    v = Verdict(spec_id="FEAT", tier="Standard", adapter="a")
    v.add(
        GateResult(
            gate="tests",
            status=STATUS_FAIL,
            tool="pytest",
            findings=["1 test failed"],
            details={"class": "test_failed"},
        )
    )
    return v.finalize()


def test_gate_run_id_output_uses_numeric_id_never_front_matter_prefix(
    tmp_path, monkeypatch, capsys
):
    """Track A: a standalone `gate run --id 042` on a spec whose front-matter prefix is FEAT shows
    the numeric id as the copy-pasteable identity everywhere — header `id=042`, the panel subject,
    and the coder hand-back `re-dispatch: … --spec-id 042` — with FEAT surfacing only as a clearly
    labelled secondary `spec=FEAT`. No `--spec-id FEAT` / `--id FEAT` command is ever emitted, and
    every emitted id resolves back to the feature folder via ``resolve_feature_dir``."""
    root = _gate_repo(tmp_path)
    monkeypatch.setattr(cli, "run_gates", lambda *a, **kw: _failing_verdict())
    rc = main(["--root", str(root), "gate", "run", "--adapter", "a", "--no-ledger", "--id", "042"])
    out = capsys.readouterr().out
    assert rc == EXIT_FAIL
    assert "id=042" in out  # the numeric id is the primary, copy-pasteable identity
    assert "spec=FEAT" in out  # the front-matter prefix appears only as a labelled secondary
    assert "re-dispatch: 3pwr run --resume --spec-id 042" in out
    assert "042 ·" in out  # the panel subject leads with the numeric id
    assert "--spec-id FEAT" not in out and "--id FEAT" not in out
    _assert_emitted_command_ids_numeric(out)
    for val in _emitted_command_ids(out):
        assert workspace.resolve_feature_dir(root, val).name == "042-widget"


def test_gate_run_id_json_payload_has_no_new_required_id_field(tmp_path, monkeypatch, capsys):
    """Track A byte-stability: the `--json` machine payload is unchanged — exactly the top-level
    keys ``{"verdict", "ledger_seq"}`` with no run-id field grafted onto the payload or the
    verdict; the numeric-id remediation is human output only."""
    root = _gate_repo(tmp_path)
    monkeypatch.setattr(cli, "run_gates", lambda *a, **kw: _failing_verdict())
    rc = main(
        [
            "--root",
            str(root),
            "gate",
            "run",
            "--adapter",
            "a",
            "--no-ledger",
            "--id",
            "042",
            "--json",
        ]
    )
    obj = json.loads(capsys.readouterr().out)
    assert rc == EXIT_FAIL
    assert set(obj.keys()) == {"verdict", "ledger_seq"}
    assert "run_id" not in obj and "id" not in obj
    assert obj["verdict"]["spec_id"] == "FEAT"  # the verdict field is untouched
    assert "run_id" not in obj["verdict"]  # no new id field grafted onto the verdict


def test_failure_panels_omit_redispatch_when_no_resolvable_id():
    """Track A: with neither a run id nor a verdict spec id, the coder hand-back omits the
    re-dispatch line entirely rather than printing a non-resolving `<spec-id>` placeholder."""
    v = Verdict(spec_id="", tier="Standard", adapter="a")
    v.add(GateResult(gate="tests", status=STATUS_FAIL, tool="pytest", findings=["x"]))
    out = orchestrate.failure_panels(v.finalize().to_dict(), run_id="")
    assert "hand back to your coding agent" in out  # the prompt still renders
    assert "re-dispatch:" not in out  # but no non-resolving command is printed


def test_run_pause_hints_never_leak_the_front_matter_prefix(run_repo, capsys):
    """Track A: the run-path pause screen resume hint carries the numeric NNN and never the spec's
    `**Spec ID**: FEAT` front-matter prefix, which a resume command cannot resolve."""
    assert main(["--root", str(run_repo), "run", "add x", "--no-input"]) == EXIT_PAUSED
    out = capsys.readouterr().out
    assert "3pwr run --resume --spec-id 030" in out
    assert "--spec-id FEAT" not in out and "--id FEAT" not in out
    _assert_emitted_command_ids_numeric(out)
