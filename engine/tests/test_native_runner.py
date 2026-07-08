"""The native provider-agnostic executive — EXEC (spec 009).

The engine owns its executive: `3pwr run` dispatches each stage to a headless coding agent directly and
runs the gate suite in-process, with no IDE and no Spec Kit. These tests exercise the whole runner,
manifest, prompt, preflight, and diagnostics flow with a FAKE agent and no network (EXEC-NFR-004), so the
engine makes no model call itself (EXEC-NFR-001).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import agents, hosted, orchestrate, prompts, runner, runpreflight
from threepowers.cli import _make_agent_runner, _resolve_runner_kind, main
from threepowers.config import Settings
from threepowers.runner import CliAgentRunner, DispatchResult, NativeRunner, StageResult


# --------------------------------------------------------------------------- agent manifests (EXEC-FR-002/003/004)
def _settings_with_agents(tmp_path, **manifests) -> Settings:
    adir = tmp_path / ".3powers" / "agents"
    adir.mkdir(parents=True)
    import yaml

    for name, data in manifests.items():
        (adir / f"{name}.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return Settings(root=tmp_path)


def test_load_and_list_agent_manifests(tmp_path):
    """EXEC-FR-002/004: manifests are loaded declaratively; a missing one names its path."""
    s = _settings_with_agents(
        tmp_path,
        claude={"command": "claude", "family": "anthropic", "headless": True},
        codex={"command": "codex", "family": "openai"},
    )
    assert agents.available_agents(s) == ["claude", "codex"]
    m = agents.load_agent(s, "claude")
    assert agents.agent_command(m) == "claude" and agents.agent_family(m) == "anthropic"
    assert agents.is_headless(m) is True
    with pytest.raises(FileNotFoundError):
        agents.load_agent(s, "nope")


def test_build_command_arg_and_flag_and_model():
    """EXEC-FR-003: the invocation is built from the manifest — prompt as flagged arg, model inserted."""
    manifest = {
        "command": "claude",
        "base_args": ["--permission-mode", "acceptEdits"],
        "model_flag": "--model",
        "prompt_flag": "-p",
        "prompt_via": "arg",
    }
    argv, stdin = agents.build_command(manifest, "DO THING", model="anthropic/claude-x")
    assert stdin is None
    assert argv == [
        "claude",
        "--permission-mode",
        "acceptEdits",
        "--model",
        "anthropic/claude-x",
        "-p",
        "DO THING",
    ]


def test_build_command_positional_and_stdin_and_no_command():
    """EXEC-FR-003: positional prompt (no flag), stdin delivery, and the missing-command guard."""
    argv, stdin = agents.build_command({"command": "codex", "base_args": ["exec"]}, "P")
    assert argv == ["codex", "exec", "P"] and stdin is None
    argv2, stdin2 = agents.build_command({"command": "x", "prompt_via": "stdin"}, "P")
    assert argv2 == ["x"] and stdin2 == "P"
    with pytest.raises(ValueError):
        agents.build_command({}, "P")


def test_reference_manifests_ship(tmp_path, monkeypatch):
    """EXEC-FR-004: the repo ships ≥3 reference manifests (claude/codex/copilot/opencode/aider)."""
    import threepowers

    repo_root = __import__("pathlib").Path(threepowers.__file__).resolve().parents[3]
    s = Settings(root=repo_root)
    shipped = set(agents.available_agents(s))
    assert {"claude", "codex", "copilot"} <= shipped
    assert len(shipped) >= 3
    # every shipped *CLI* manifest builds a valid invocation; a hosted backend uses a different contract
    from threepowers import hosted

    for name in shipped:
        manifest = agents.load_agent(s, name)
        if hosted.is_hosted(manifest):
            assert manifest.get("trigger_command")  # hosted manifests declare a trigger instead
            continue
        argv, _ = agents.build_command(manifest, "PROMPT")
        assert argv and isinstance(argv[0], str)


# --------------------------------------------------------------------------- prompt assembly (EXEC-FR-005)
def test_prompt_assembly_is_deterministic_and_scoped():
    """EXEC-FR-005: prompt assembly is a pure function of its non-empty inputs."""
    a = prompts.assemble("specify", intent="add a rate limiter")
    b = prompts.assemble("specify", intent="add a rate limiter")
    assert a == b
    assert "Specify" in a and "add a rate limiter" in a
    # the oracle prompt forbids reading the implementation (Phase A independence)
    orc = prompts.assemble("oracle", intent="x", spec_text="SPEC")
    assert "MUST NOT read the implementation" in orc and "SPEC" in orc
    # an empty block is omitted, so different inputs yield different prompts
    assert prompts.assemble("plan", intent="x") != prompts.assemble("plan", intent="x", context="c")


# --------------------------------------------------------------------------- CliAgentRunner (EXEC-FR-001/016, NFR-001)
def test_cli_agent_runner_dispatches_via_process_not_a_model(tmp_path):
    """EXEC-FR-001 / NFR-001: dispatch goes to an external agent process (injected here), never a model API."""
    s = Settings(root=tmp_path)
    manifest = {"command": "claude", "prompt_flag": "-p", "model_flag": "--model"}
    seen: list[tuple] = []

    def fake_dispatcher(argv, *, cwd, stdin, timeout, stream=False, tee=None):
        seen.append((argv, cwd, stdin, timeout))
        return (0, "changes written", "")

    r = CliAgentRunner(
        s, manifest, model="anthropic/opus", intent="do it", dispatcher=fake_dispatcher
    )
    res = r.dispatch("implement", "Build")
    assert res.ok and res.model == "anthropic/opus"
    argv = seen[0][0]
    assert argv[0] == "claude" and "--model" in argv and argv[-2] == "-p"
    assert "Implement" in argv[-1]  # the assembled stage prompt is the final arg


def test_cli_agent_runner_reports_dispatch_failure(tmp_path):
    """EXEC-FR-016: a non-zero agent exit is a dispatch failure carrying the reason."""
    s = Settings(root=tmp_path)

    def failing(argv, *, cwd, stdin, timeout, stream=False, tee=None):
        return (127, "", "agent command not found: codex")

    r = CliAgentRunner(s, {"command": "codex"}, dispatcher=failing)
    res = r.dispatch("plan", "Plan")
    assert not res.ok and "not found" in res.detail


# --------------------------------------------------------------------------- NativeRunner drive (EXEC-FR-001/006/007/008)
def _fake_runner(verdict="pass", fail_step=""):
    def dispatch(step, stage):
        ok = step != fail_step
        return StageResult(
            step=step,
            stage=stage,
            ok=ok,
            attempts=1,
            outcome="ok" if ok else "dispatch_failed",
            detail=step,
        )

    def run_verdict(stage):
        return verdict

    return NativeRunner(dispatch=dispatch, run_verdict=run_verdict)


def test_native_runner_stops_only_at_mandatory_gates_then_completes():
    """EXEC-FR-001/006/007/008: auto mode drives every stage with a fake agent, stopping at the two gates."""
    r = _fake_runner()
    r1 = orchestrate.drive(r, "auto", lambda e: None)
    assert r1.status == "paused_at_gate" and r1.gate == "review-spec"
    r2 = orchestrate.drive(r, "auto", lambda e: None, resuming=True)
    assert r2.status == "paused_at_gate" and r2.gate == "signoff"
    r3 = orchestrate.drive(r, "auto", lambda e: None, resuming=True)
    assert r3.status == "done"


def test_native_runner_verdict_fail_is_gate_red():
    """EXEC-FR-006: a failing in-process verdict at Verify surfaces as a real gate-red (verdict='fail')."""
    r = _fake_runner(verdict="fail")
    orchestrate.drive(r, "auto", lambda e: None)  # review-spec
    res = orchestrate.drive(r, "auto", lambda e: None, resuming=True)
    assert res.status == "failed" and res.is_gate_red


def test_native_runner_verdict_error_is_not_gate_red():
    """EXEC-FR-016: gates that cannot run (verdict='error') are a setup failure, never a false gate-red."""
    r = _fake_runner(verdict="error")
    orchestrate.drive(r, "auto", lambda e: None)  # review-spec
    res = orchestrate.drive(r, "auto", lambda e: None, resuming=True)
    assert res.status == "failed" and not res.is_gate_red and res.verdict == ""


def test_native_runner_dispatch_failure_is_not_gate_red():
    """EXEC-FR-016: an agent dispatch failure is reported distinctly from a gate verdict."""
    r = _fake_runner(fail_step="specify")
    res = orchestrate.drive(r, "auto", lambda e: None)
    assert res.status == "failed" and not res.is_gate_red and res.verdict == ""


# --------------------------------------------------------------------------- native preflight (EXEC-FR-015)
def _roles(tmp_path, coder, oracle):
    cdir = tmp_path / ".3powers" / "config"
    cdir.mkdir(parents=True, exist_ok=True)
    import yaml

    (cdir / "roles.yaml").write_text(
        yaml.safe_dump(
            {"version": 1, "diversity_level": "family", "roles": {"coder": coder, "oracle": oracle}}
        ),
        encoding="utf-8",
    )


def test_check_native_all_ok_and_each_failure_mode(tmp_path):
    """EXEC-FR-015: native preflight requires a headless coder agent + a different-family oracle agent."""
    s = _settings_with_agents(
        tmp_path,
        claude={"command": "claude", "family": "anthropic", "headless": True},
        codex={"command": "codex", "family": "openai", "headless": True},
    )
    _roles(
        tmp_path,
        {"integration": "claude", "model_family": "anthropic"},
        {"integration": "codex", "model_family": "openai"},
    )
    present = lambda cmd: True  # noqa: E731 — probe stub (EXEC-NFR-004)

    ok = runpreflight.check_native(
        s,
        coder_agent="claude",
        oracle_agent="codex",
        entries=[],
        spec_id="RUN",
        command_present=present,
    )
    assert runpreflight.unmet(ok) == []

    # missing coder agent
    none = runpreflight.check_native(
        s, coder_agent="", oracle_agent="codex", entries=[], spec_id="RUN", command_present=present
    )
    assert any("coder" in p.name for p in runpreflight.unmet(none))

    # coder command absent from PATH
    absent = runpreflight.check_native(
        s,
        coder_agent="claude",
        oracle_agent="codex",
        entries=[],
        spec_id="RUN",
        command_present=lambda cmd: cmd != "claude",
    )
    assert any("coder" in p.name and "claude" in p.fix for p in runpreflight.unmet(absent))

    # same-family oracle without a deviation is refused (diversity)
    _roles(
        tmp_path,
        {"integration": "claude", "model_family": "anthropic"},
        {"integration": "claude", "model_family": "anthropic"},
    )
    same = runpreflight.check_native(
        s,
        coder_agent="claude",
        oracle_agent="claude",
        entries=[],
        spec_id="RUN",
        command_present=present,
    )
    assert any("oracle" in p.name and "deviation" in p.fix for p in runpreflight.unmet(same))


# --------------------------------------------------------------------------- CLI end-to-end (EXEC-FR-013/001/006)
def _git_init(root):
    import subprocess

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)


def _artifact_writer(spec_id="RUN"):
    """A fake agent that, like a real one, writes each stage's declared artifact (RUNLIVE-FR-001).

    Detects the stage from the assembled prompt (the final argv) and produces the file the artifact contract
    expects — flat in the feature folder the prompt names (SRCX-FR-001) — so a native run advances past
    Specify/Oracle/Implement. No model call — the engine issues none (EXEC-NFR-001, RUNLIVE-NFR-001)."""

    def fake(argv, **kw):
        import re

        from pathlib import Path

        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
        d = cwd / (m.group(1) if m else f"specs-src/{spec_id}")
        if "# Discovery agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery: x\n", encoding="utf-8")
        elif "# Specify agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "# Plan agent" in prompt:
            # plan/tasks carry hard artifact contracts (PHASE-FR-002) — the fake writes them
            # flat into the run's feature folder (SRCX-FR-001) like a real agent would.
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in prompt:
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "# Oracle agent" in prompt:
            t = cwd / "tests" / "oracle" / spec_id
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "# Implement agent" in prompt:
            src = cwd / "src"
            src.mkdir(parents=True, exist_ok=True)
            (src / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "changes written", "")

    return fake


@pytest.fixture()
def native_project(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    _setup_native_project(root, tmp_path / "signer.key", monkeypatch)
    return root


def _setup_native_project(root: Path, keyfile: Path, monkeypatch) -> Path:
    """Build one native-run project: agents + roles + signer + git, with the agent process faked
    (no model call — EXEC-NFR-001). Module-level so tests needing more than one independent
    project (e.g. the usage/no-usage verdict byte comparison) reuse the exact fixture setup."""
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    (root / "specs-src" / "009-x").mkdir(parents=True)
    (root / "specs-src" / "009-x" / "spec.md").write_text(
        "# Spec\n**Spec ID**: X\n", encoding="utf-8"
    )
    import yaml

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
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    _git_init(root)  # a real repo so artifact detection + checkpoints work (RUNLIVE-FR-001/010)
    # a headless agent CLI is "present"; the agent process is faked (no model call — EXEC-NFR-001)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", _artifact_writer())
    return root


def test_resolve_runner_kind_defaults_native():
    """EXEC-FR-013: native is the default; --dry-run forces sim; --runner selects explicitly."""
    import argparse

    ns = argparse.Namespace(dry_run=False, runner=None)
    assert _resolve_runner_kind(ns) == "native"
    assert _resolve_runner_kind(argparse.Namespace(dry_run=True, runner="native")) == "sim"
    assert _resolve_runner_kind(argparse.Namespace(dry_run=False, runner="specify")) == "specify"


def test_cli_native_run_dispatches_and_stops_at_spec_gate(native_project, capsys):
    """EXEC-FR-001/013: a native run drives the executive stages with a headless agent (no Spec Kit) and
    stops at the mandatory spec-approval gate."""
    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "add a rate limiter",
            "--no-input",
            "--spec-id",
            "RUN",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 3  # paused at the first mandatory human gate (AUTOX-FR-009)
    assert "review-spec" in out  # paused at the first mandatory human gate (FR-006)


def test_cli_native_run_runs_gates_in_process_at_verify(native_project, monkeypatch, capsys):
    """EXEC-FR-006: resuming reaches Verify, where the deterministic gate suite runs IN-PROCESS."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    calls: list = []

    def fake_gates(settings, target, **kw):
        calls.append(kw.get("tier"))
        return Verdict(spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS)

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(climod, "run_gates", fake_gates)

    assert (
        main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    )
    # resume past the spec gate → auto mode drives plan..implement..verify, stopping at sign-off
    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "carlo",
        ]
    )
    assert rc == 3  # paused at the sign-off gate
    assert calls  # run_gates was invoked in-process at the Verify stage
    assert "signoff" in capsys.readouterr().out


# --------------------------------------------------------------------------- robust dispatch (RUNLIVE-FR-004/005/006)
def test_dispatch_agent_timeout_is_a_terminated_failure(monkeypatch):
    """RUNLIVE-FR-004: an agent that exceeds its timeout is terminated and reported (rc 124), never a hang."""
    import subprocess as sp

    def raise_timeout(*a, **k):
        raise sp.TimeoutExpired(cmd="claude", timeout=k.get("timeout", 1))

    monkeypatch.setattr(runner.subprocess, "run", raise_timeout)
    rc, out, err = runner.dispatch_agent(["claude", "-p", "x"], cwd=Path("."), timeout=1)
    assert rc == 124 and "timed out" in err


def test_dispatch_with_retry_bounds_attempts_and_stops_on_success():
    """RUNLIVE-FR-005: a stage is tried at most retries+1 times; a success is never retried."""
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return DispatchResult(calls["n"] >= 3, detail=f"try {calls['n']}")

    res, attempts = runner.dispatch_with_retry(flaky, retries=5)
    assert res.ok and attempts == 3  # succeeded on the 3rd of a 6-try budget; stopped there

    # exhausted budget: retries=2 → at most 3 attempts, then reported failed
    always = {"n": 0}

    def failing():
        always["n"] += 1
        return DispatchResult(False, detail="nope")

    res2, attempts2 = runner.dispatch_with_retry(failing, retries=2)
    assert not res2.ok and attempts2 == 3

    # a success is never retried (attempts == 1)
    ok_res, ok_attempts = runner.dispatch_with_retry(lambda: DispatchResult(True), retries=3)
    assert ok_res.ok and ok_attempts == 1


def test_run_stage_reports_dispatch_artifact_and_ok_outcomes():
    """RUNLIVE-FR-002/006: run_stage classifies dispatch-failed, artifact-missing, and ok with a summary."""
    from threepowers import artifacts

    ticks = iter([10.0, 10.5, 20.0, 20.25, 30.0, 30.1])

    def clock():
        return next(ticks)

    # dispatch failed after exhausting retries
    df = runner.run_stage(
        "implement",
        "Build",
        attempt=lambda: DispatchResult(False, detail="boom"),
        retries=0,
        agent="claude",
        clock=clock,
    )
    assert not df.ok and df.outcome == "dispatch_failed" and df.attempts == 1 and df.duration_s > 0

    # dispatched ok but produced no declared artifact
    contract = artifacts.contract_for("specify")
    am = runner.run_stage(
        "specify",
        "Spec",
        attempt=lambda: DispatchResult(True),
        retries=0,
        verify_artifact=lambda: artifacts.verify(contract, []),
        agent="claude",
        clock=clock,
    )
    assert not am.ok and am.outcome == "artifact_missing" and "spec file" in am.detail

    # dispatched ok and produced the artifact → ok, with an artifact summary
    good = runner.run_stage(
        "specify",
        "Spec",
        attempt=lambda: DispatchResult(True, model="anthropic/opus"),
        retries=0,
        verify_artifact=lambda: artifacts.verify(contract, ["specs-src/x/spec.md"]),
        agent="claude",
        clock=clock,
    )
    assert good.ok and good.outcome == "ok" and "spec.md" in good.artifact
    assert good.as_dict()["model"] == "anthropic/opus"


def test_cli_json_emits_a_per_stage_result(native_project, capsys):
    """RUNLIVE-FR-006: a --json run carries one structured result per dispatched stage, no ANSI."""
    import json as _json

    rc = main(
        ["--root", str(native_project), "run", "add x", "--no-input", "--json", "--spec-id", "RUN"]
    )
    assert rc == 3
    obj = _json.loads(capsys.readouterr().out)
    assert obj["status"] == "paused_at_gate" and obj["gate"] == "review-spec"
    stages = obj["stages"]
    steps = [st["step"] for st in stages]
    assert "specify" in steps
    spec_stage = next(st for st in stages if st["step"] == "specify")
    assert spec_stage["ok"] and spec_stage["outcome"] == "ok" and spec_stage["agent"] == "claude"
    assert spec_stage["attempts"] == 1 and "spec.md" in spec_stage["artifact"]


# --------------------------------------------------------------------------- discovery work-kind gate (plan 034 phase 5)
def _discovery_ledger_entries(root: Path) -> tuple[list[dict], list[dict]]:
    """The run's discovery ledger entries: (stage completions, dispatch provenance)."""
    from threepowers.ledger import Ledger

    entries = Ledger(root / ".3powers" / "ledger.jsonl").entries()
    runs = [e.get("payload", {}) for e in entries if e.get("type") == "run"]
    stage = [p for p in runs if p.get("kind") == "stage" and p.get("step") == "discovery"]
    dispatch = [p for p in runs if p.get("kind") == "dispatch" and p.get("stage") == "discovery"]
    return stage, dispatch


def test_run_parser_resolves_discovery_override():
    """Plan 034 phase 5: --discovery/--no-discovery resolve to an Optional[bool], default None."""
    import threepowers.cli as climod

    p = climod.build_parser()
    assert p.parse_args(["run", "add x"]).discovery is None
    assert p.parse_args(["run", "add x", "--discovery"]).discovery is True
    assert p.parse_args(["run", "add x", "--no-discovery"]).discovery is False


def test_run_help_lists_the_discovery_flags(capsys):
    """Plan 034 phase 5: `3pwr run --help` lists both flag forms."""
    with pytest.raises(SystemExit):
        main(["run", "--help"])
    out = capsys.readouterr().out
    assert "--discovery" in out and "--no-discovery" in out


def test_defect_intent_skips_discovery_and_proceeds_to_specify(native_project, monkeypatch, capsys):
    """Plan 034 phase 5: a defect-kind intent short-circuits Discovery — outcome 'skipped' in the
    parseable --json stages list, nothing written, no run/stage or dispatch discovery ledger entry
    — and the walk proceeds straight to Specify with the prior-context handoff untouched."""
    import json as _json

    prompts_seen: list[str] = []
    inner = _artifact_writer()

    def recording(argv, **kw):
        prompts_seen.append(argv[-1] if argv else "")
        return inner(argv, **kw)

    monkeypatch.setattr(runner, "dispatch_agent", recording)
    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "fix the crash bug",
            "--no-input",
            "--json",
            "--spec-id",
            "RUN",
        ]
    )
    obj = _json.loads(capsys.readouterr().out)
    assert rc == 3 and obj["gate"] == "review-spec"  # the walk reached Specify and its gate
    disc = next(st for st in obj["stages"] if st["step"] == "discovery")
    assert disc["ok"] and disc["outcome"] == "skipped"
    assert "specify" in [st["step"] for st in obj["stages"]]
    assert not list(native_project.glob("specs-src/**/discovery.md"))  # nothing written
    stage, dispatch = _discovery_ledger_entries(native_project)
    assert stage == [] and dispatch == []  # no ledger trace of a stage that never ran
    # prior_box untouched: the specify prompt (the FIRST dispatched) carries no discovery handoff
    assert "# Specify agent" in prompts_seen[0]
    assert "discovery.md" not in prompts_seen[0]
    # The verdict/gate --json path never consumes StageResult, so the new outcome value
    # cannot perturb its bytes (light source-level guard).
    import inspect

    from threepowers import verdict as verdictmod

    assert "StageResult" not in inspect.getsource(verdictmod)


def test_no_discovery_flag_skips_for_a_feature_intent(native_project, capsys):
    """Plan 034 phase 5: --no-discovery overrides the work-kind gate — a feature intent skips."""
    import json as _json

    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "add x",
            "--no-discovery",
            "--no-input",
            "--json",
            "--spec-id",
            "RUN",
        ]
    )
    obj = _json.loads(capsys.readouterr().out)
    assert rc == 3 and obj["gate"] == "review-spec"
    disc = next(st for st in obj["stages"] if st["step"] == "discovery")
    assert disc["ok"] and disc["outcome"] == "skipped"
    assert not list(native_project.glob("specs-src/**/discovery.md"))
    stage, dispatch = _discovery_ledger_entries(native_project)
    assert stage == [] and dispatch == []


def test_discovery_flag_forces_dispatch_for_a_defect_intent(native_project, capsys):
    """Plan 034 phase 5: --discovery overrides the work-kind gate — a defect intent dispatches
    Discovery, its note lands and is recorded like any producing stage."""
    import json as _json

    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "fix the crash bug",
            "--discovery",
            "--no-input",
            "--json",
            "--spec-id",
            "RUN",
        ]
    )
    obj = _json.loads(capsys.readouterr().out)
    assert rc == 3 and obj["gate"] == "review-spec"
    disc = next(st for st in obj["stages"] if st["step"] == "discovery")
    assert disc["ok"] and disc["outcome"] == "ok"
    assert list(native_project.glob("specs-src/**/discovery.md"))  # the note landed
    stage, dispatch = _discovery_ledger_entries(native_project)
    assert stage and dispatch  # recorded like any dispatched producing stage


# --------------------------------------------------------------------------- per-stage artifact contract (RUNLIVE-FR-001/002)
def test_cli_specify_producing_nothing_is_artifact_missing(native_project, monkeypatch, capsys):
    """RUNLIVE-FR-002/SC-001: a Specify agent that writes no spec stops the run with a named artifact
    failure — not a silent pass, not a gate-red."""

    def discovery_only(argv, **kw):
        # Discovery (the head step) produces its note; Specify then writes nothing.
        import re

        prompt = argv[-1] if argv else ""
        if "# Discovery agent" in prompt:
            m = re.search(r"feature folder\s+`([^`\s]+)`", prompt)
            d = Path(kw["cwd"]) / (m.group(1) if m else "specs-src/RUN")
            d.mkdir(parents=True, exist_ok=True)
            (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
        return (0, "did nothing", "")

    monkeypatch.setattr(runner, "dispatch_agent", discovery_only)
    rc = main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc == 4  # EXIT_SETUP — a setup/dispatch problem, not a gate verdict (AUTOX-FR-009)
    assert "artifact missing" in out and "Spec" in out
    assert "gates red" not in out  # never mislabeled a gate-red (SC-001)


# --------------------------------------------------------------------------- commit checkpoints + resume (RUNLIVE-FR-010)
def _writer_no_implement():
    def fake(argv, **kw):
        import re

        p = argv[-1] if argv else ""
        cwd = Path(kw["cwd"])
        m = re.search(r"feature folder\s+`([^`\s]+)`", p)
        d = cwd / (m.group(1) if m else "specs-src/RUN")
        # plan/tasks carry hard contracts too (PHASE-FR-002) — write them flat so the run reaches Build
        if "# Plan agent" in p:
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "# Implementation-plan agent" in p:
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text("# Tasks\n- [ ] T001 [RUN-FR-001] x\n", encoding="utf-8")
        elif "# Oracle agent" in p:
            t = cwd / "tests" / "oracle" / "RUN"
            t.mkdir(parents=True, exist_ok=True)
            (t / "test_o.py").write_text("def test_o():\n    assert True\n", encoding="utf-8")
        return (0, "ok", "")  # Implement writes nothing → artifact_missing

    return fake


def _recording_writer(seen):
    def fake(argv, **kw):
        p = argv[-1] if argv else ""
        for key, marker in (
            ("discovery", "# Discovery agent"),
            ("specify", "# Specify agent"),
            ("clarify", "# Clarify agent"),
            ("plan", "# Plan agent"),
            ("tasks", "# Implementation-plan agent"),
            ("oracle", "# Oracle agent"),
            ("implement", "# Implement agent"),
        ):
            if marker in p:
                seen.append(key)
        if "# Implement agent" in p:
            d = Path(kw["cwd"]) / "src"
            d.mkdir(parents=True, exist_ok=True)
            (d / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "ok", "")

    return fake


def test_checkpoint_resume_skips_committed_stages(native_project, monkeypatch, capsys):
    """RUNLIVE-FR-010/SC-005: after committed checkpoints and a mid-run failure, a resume continues from the
    next uncompleted stage without re-dispatching a committed one."""
    import subprocess as sp

    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(
        climod,
        "run_gates",
        lambda *a, **k: Verdict(
            spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS
        ),
    )

    # Run 1: specify (committed as a checkpoint) → stop at review-spec.
    assert (
        main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    )

    # Run 2 (resume): oracle is committed, but implement produces nothing → artifact_missing at Build.
    monkeypatch.setattr(runner, "dispatch_agent", _writer_no_implement())
    rc2 = main(
        [
            "--root",
            str(native_project),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "x",
        ]
    )
    assert rc2 == 4 and "artifact missing" in capsys.readouterr().out

    # specify + oracle are committed checkpoints; implement is not.
    log = sp.run(
        ["git", "log", "--pretty=%s"], cwd=str(native_project), capture_output=True, text=True
    ).stdout
    assert "3pwr(RUN): specify" in log and "3pwr(RUN): oracle" in log
    assert "3pwr(RUN): implement" not in log

    # Run 3 (resume): a fixed agent — ONLY implement is re-dispatched; specify/oracle are not.
    seen: list[str] = []
    monkeypatch.setattr(runner, "dispatch_agent", _recording_writer(seen))
    rc3 = main(
        [
            "--root",
            str(native_project),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "x",
        ]
    )
    assert rc3 == 3 and "signoff" in capsys.readouterr().out
    assert "implement" in seen
    assert "specify" not in seen and "oracle" not in seen and "plan" not in seen
    # the property (RUNLIVE-FR-010): implement succeeded exactly once — its checkpoint now exists
    log2 = sp.run(
        ["git", "log", "--pretty=%s"], cwd=str(native_project), capture_output=True, text=True
    ).stdout
    assert log2.count("3pwr(RUN): implement") == 1


# --------------------------------------------------------------------------- async hosted backend (RUNLIVE-FR-008)
def test_make_agent_runner_selects_hosted_or_cli(tmp_path):
    """RUNLIVE-FR-008/NFR-005: the manifest's `mode` picks the backend — hosted vs local CLI."""
    s = Settings(root=tmp_path)
    cli = _make_agent_runner(
        s, {"command": "claude"}, model="", intent="", timeout=60, stream=False
    )
    assert isinstance(cli, CliAgentRunner)
    hb = _make_agent_runner(
        s,
        {"mode": "async-hosted", "trigger_command": ["gh"]},
        model="",
        intent="",
        timeout=60,
        stream=False,
    )
    assert isinstance(hb, hosted.HostedAgentRunner)


def test_cli_native_run_with_hosted_backend_reaches_spec_gate(native_project, monkeypatch, capsys):
    """RUNLIVE-FR-008/NFR-003/SC-004: an async-hosted coder backend drives a stage end-to-end (trigger →
    poll → collect); its produced artifact is judged by the same path as a local dispatch."""
    import yaml

    (native_project / ".3powers" / "agents" / "claude.yaml").write_text(
        yaml.safe_dump(
            {
                "agent": "claude",
                "family": "anthropic",
                "headless": True,
                "mode": "async-hosted",
                "trigger_command": ["gh", "trigger", "{step}"],
                "poll_command": ["gh", "poll", "{run_id}"],
                "completed_values": ["completed"],
                "collect_command": ["gh", "collect", "{run_id}", "{step}"],
            }
        ),
        encoding="utf-8",
    )
    state = {"step": ""}

    def fake_hosted(argv, cwd):
        if argv[:2] == ["gh", "trigger"]:
            state["step"] = argv[2]
            return (0, "run-1", "")
        if argv[:2] == ["gh", "poll"]:
            return (0, "completed", "")
        if argv[:2] == ["gh", "collect"]:
            # the run deterministically allocated specs-src/010-add-x (SRCX-FR-008: max 009 + 1)
            d = Path(cwd) / "specs-src" / "010-add-x"
            if state["step"] == "discovery":  # the hosted run's branch carries the note
                d.mkdir(parents=True, exist_ok=True)
                (d / "discovery.md").write_text("# Discovery\n", encoding="utf-8")
            if state["step"] == "specify":  # the hosted run's branch carries the produced spec
                d.mkdir(parents=True, exist_ok=True)
                (d / "spec.md").write_text("# Spec\n**Spec ID**: RUN\n", encoding="utf-8")
            return (0, "checked out", "")
        return (1, "", "unexpected")

    monkeypatch.setattr(hosted, "run_hosted_command", fake_hosted)
    rc = main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc == 3 and "review-spec" in out  # the hosted-produced spec advanced the run to the gate


def test_no_auto_commit_is_superseded_and_warns(native_project, capsys):
    """GITX-FR-014 (supersedes RUNLIVE-FR-010's opt-out): `--no-auto-commit` no longer silently
    disables the stage commit — it warns, names the signed deviation, and the commit happens."""
    import subprocess as sp

    before = sp.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(native_project),
        capture_output=True,
        text=True,
    ).stdout.strip()
    rc = main(
        [
            "--root",
            str(native_project),
            "run",
            "add x",
            "--no-input",
            "--no-auto-commit",
            "--spec-id",
            "RUN",
        ]
    )
    err = capsys.readouterr().err
    assert rc == 3  # paused at the spec gate
    assert "superseded" in err and "git_stage_commit" in err  # warned, never silent
    after = sp.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(native_project),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert int(after) > int(before)  # the mandatory stage commit still happened


# --------------------------------------------------------------------------- session freshness (plan 033 Track G / RUNVIS)
# Tokens that would reuse or resume a prior conversation/session — the engine must never emit one.
_SESSION_REUSE_TOKENS = {
    "--resume",
    "--continue",
    "-c",
    "-r",
    "--session",
    "--session-id",
    "resume",
    "continue",
}


def test_build_command_emits_new_session_args_and_round_trips(tmp_path):
    """Plan 033 Track G (RUNVIS): a manifest's `new_session_args` rides every invocation — after
    the base args, before the model/prompt — and round-trips through a YAML manifest on disk."""
    manifest = {
        "command": "aider",
        "base_args": ["--yes-always"],
        "new_session_args": ["--no-restore-chat-history"],
        "prompt_flag": "--message",
    }
    argv, stdin = agents.build_command(manifest, "DO", model="")
    assert stdin is None
    assert argv == ["aider", "--yes-always", "--no-restore-chat-history", "--message", "DO"]
    # round-trip: the field survives the YAML manifest load and still shapes the invocation
    s = _settings_with_agents(tmp_path, aider=manifest)
    loaded = agents.load_agent(s, "aider")
    assert loaded.get("new_session_args") == ["--no-restore-chat-history"]
    argv2, _ = agents.build_command(loaded, "DO", model="")
    assert "--no-restore-chat-history" in argv2


def test_shipped_manifests_never_emit_a_session_reuse_flag():
    """Plan 033 Track G (RUNVIS): no shipped CLI manifest builds an invocation carrying a
    resume/continue/session-reuse token — every dispatch is a clean session by construction."""
    import threepowers

    repo_root = Path(threepowers.__file__).resolve().parents[3]
    s = Settings(root=repo_root)
    checked = 0
    for name in agents.available_agents(s):
        manifest = agents.load_agent(s, name)
        if hosted.is_hosted(manifest):
            continue  # a hosted backend triggers a NEW hosted run per dispatch — no session flag
        argv, _ = agents.build_command(manifest, "PROMPT", model="some/model")
        # exclude the prompt itself (the final token when passed as an argument)
        flags = argv[:-1] if argv[-1] == "PROMPT" else argv
        assert not (_SESSION_REUSE_TOKENS & set(flags)), f"{name}: session reuse flag in {flags}"
        checked += 1
    assert checked >= 3


def test_each_dispatch_is_an_independent_process_with_no_carried_session(tmp_path):
    """Plan 033 Track G (RUNVIS): two dispatches through one runner are two independent agent
    processes with identical, session-free invocations — no state token is injected or carried
    between them."""
    s = Settings(root=tmp_path)
    manifest = {"command": "claude", "prompt_flag": "-p"}
    seen: list[list[str]] = []

    def recording(argv, *, cwd, stdin, timeout, stream=False, tee=None):
        seen.append(list(argv))
        return (0, "done", "")

    r = CliAgentRunner(s, manifest, intent="do it", dispatcher=recording)
    assert r.dispatch("plan", "Plan").ok
    assert r.dispatch("plan", "Plan").ok
    assert len(seen) == 2  # one process per dispatch — never a shared session
    assert seen[0] == seen[1]  # the second invocation carries nothing from the first
    assert not (_SESSION_REUSE_TOKENS & set(seen[0][:-1]))


# --------------------------------------------------------------------------- usage capture (plan 033 Track H / RUNVIS)
def test_extract_usage_json_strategy_reads_a_dotted_field():
    """Plan 033 Track H (RUNVIS): a `usage: {strategy: json}` manifest reads the token count from
    the last JSON line of the agent output via a dotted field path."""
    m = {"usage": {"strategy": "json", "field": "usage.total_tokens"}}
    out = 'progress text\n{"usage": {"total_tokens": 1234}, "result": "ok"}\n'
    assert agents.extract_usage(m, out) == 1234
    # a flat field works too, and a whole-output JSON document is read as a fallback
    flat = {"usage": {"strategy": "json", "field": "total_tokens"}}
    assert agents.extract_usage(flat, '{"total_tokens": 42}') == 42


def test_extract_usage_regex_strategy_takes_the_last_match():
    """Plan 033 Track H (RUNVIS): a `usage: {strategy: regex}` manifest extracts group 1 of the
    last pattern match, tolerating thousands separators."""
    m = {"usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9][0-9,]*)"}}
    out = "step one\ntokens used: 1,000\nmore work\ntokens used: 12,345\n"
    assert agents.extract_usage(m, out) == 12345


def test_extract_usage_unknown_reads_as_none_never_an_error():
    """Plan 033 Track H (RUNVIS): an unreporting backend reads as None — no hint, an unmatched
    hint, a malformed hint, or a broken pattern never raises and never fabricates a count."""
    assert agents.extract_usage({}, "no usage here") is None  # backend declares no hint
    m_regex = {"usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9,]+)"}}
    assert agents.extract_usage(m_regex, "the agent printed no summary") is None
    m_json = {"usage": {"strategy": "json", "field": "usage.total_tokens"}}
    assert agents.extract_usage(m_json, "not json at all") is None
    assert agents.extract_usage({"usage": {"strategy": "carrier-pigeon"}}, "x") is None
    assert agents.extract_usage({"usage": {"strategy": "regex", "pattern": "(["}}, "x") is None
    assert agents.extract_usage({"usage": "not-a-dict"}, "tokens used: 5") is None


def test_cli_agent_runner_captures_manifest_declared_usage(tmp_path):
    """Plan 033 Track H (RUNVIS): dispatch extracts the agent-reported token count per the
    manifest's usage hint; a manifest without one reads as None."""
    s = Settings(root=tmp_path)
    reporting = {
        "command": "codex",
        "usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9,]+)"},
    }

    def fake(argv, *, cwd, stdin, timeout, stream=False, tee=None):
        return (0, "changes written\ntokens used: 777", "")

    res = CliAgentRunner(s, reporting, dispatcher=fake).dispatch("implement", "Build")
    assert res.ok and res.tokens == 777
    silent = CliAgentRunner(s, {"command": "codex"}, dispatcher=fake).dispatch("implement", "Build")
    assert silent.ok and silent.tokens is None


def test_run_stage_threads_tokens_into_the_stage_result_additively():
    """Plan 033 Track H (RUNVIS): the dispatch's token count reaches StageResult and its
    as_dict() — present only when reported, and always a superset of the prior keys (the e2e
    notebooks' defensive parsing contract)."""
    with_usage = runner.run_stage(
        "implement",
        "Build",
        attempt=lambda: DispatchResult(True, tokens=55),
        retries=0,
        agent="codex",
    )
    without_usage = runner.run_stage(
        "implement", "Build", attempt=lambda: DispatchResult(True), retries=0, agent="codex"
    )
    assert with_usage.tokens == 55 and without_usage.tokens is None
    d_with, d_without = with_usage.as_dict(), without_usage.as_dict()
    assert d_with["tokens"] == 55 and "tokens" not in d_without
    prior_keys = {
        "step",
        "stage",
        "ok",
        "agent",
        "model",
        "attempts",
        "duration_s",
        "artifact",
        "outcome",
        "detail",
    }
    assert prior_keys <= set(d_without) <= set(d_with)  # strictly additive (PAT-002)


def _fixed_verdict_gates(monkeypatch, calls):
    """Patch the in-process gate suite to a FIXED verdict (stable id + timestamp) so two runs'
    verdict payload bytes are comparable; records every run_gates call's kwargs."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS, Verdict

    def fake_gates(settings, target, **kw):
        calls.append(kw)
        return Verdict(
            spec_id="RUN",
            tier="Standard",
            adapter="python",
            result=STATUS_PASS,
            verdict_id="fixed-verdict-id",
            created_at="2026-01-01T00:00:00Z",
        )

    monkeypatch.setattr(climod, "detect_adapter", lambda s, t: "python")
    monkeypatch.setattr(climod, "run_gates", fake_gates)


def _drive_to_signoff(root: Path) -> None:
    assert main(["--root", str(root), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 3
    rc = main(
        [
            "--root",
            str(root),
            "run",
            "--resume",
            "--no-input",
            "--spec-id",
            "RUN",
            "--approver",
            "carlo",
        ]
    )
    assert rc == 3  # paused at sign-off — Verify's in-process gate suite already ran


def test_verdict_bytes_identical_with_and_without_usage_capture(tmp_path, monkeypatch, capsys):
    """Plan 033 Track H / CON-003 (RUNVIS): the deterministic verdict payload is byte-identical
    whether or not usage is captured — tokens ride ONLY the additive run-entry fields, never
    run_gates, the verdict, or the verdict bytes; `3pwr verify` stays green over the new
    payloads."""
    import yaml

    from threepowers.canonical import canonical_bytes
    from threepowers.ledger import Ledger

    calls: list[dict] = []
    _fixed_verdict_gates(monkeypatch, calls)

    # Project A: no usage hint, no usage output — the pre-Track-H behavior.
    root_a = tmp_path / "repo_a"
    _setup_native_project(root_a, tmp_path / "a.key", monkeypatch)
    _drive_to_signoff(root_a)

    # Project B: the coder manifest declares a usage hint and the agent reports a token count.
    root_b = tmp_path / "repo_b"
    _setup_native_project(root_b, tmp_path / "b.key", monkeypatch)
    (root_b / ".3powers" / "agents" / "claude.yaml").write_text(
        yaml.safe_dump(
            {
                "command": "claude",
                "family": "anthropic",
                "headless": True,
                "prompt_flag": "-p",
                "usage": {"strategy": "regex", "pattern": r"tokens used[:\s]+([0-9,]+)"},
            }
        ),
        encoding="utf-8",
    )
    base = _artifact_writer()

    def with_usage(argv, **kw):
        rc, out, err = base(argv, **kw)
        return rc, out + "\ntokens used: 4,321", err

    monkeypatch.setattr(runner, "dispatch_agent", with_usage)
    _drive_to_signoff(root_b)
    capsys.readouterr()

    def entries(root: Path) -> list[dict]:
        return Ledger(root / ".3powers" / "ledger.jsonl").entries()

    verdicts_a = [e["payload"] for e in entries(root_a) if e.get("type") == "verdict"]
    verdicts_b = [e["payload"] for e in entries(root_b) if e.get("type") == "verdict"]
    assert len(verdicts_a) == 1 and len(verdicts_b) == 1
    # CON-003: the verdict bytes are identical with and without usage capture, and token-free.
    assert canonical_bytes(verdicts_a[0]) == canonical_bytes(verdicts_b[0])
    assert b"tokens" not in canonical_bytes(verdicts_b[0])
    # run_gates itself received no token-shaped input on either run.
    assert calls and all("token" not in k.lower() for kw in calls for k in kw)

    # The additive fields landed where they belong: B's stage + checkpoint entries carry tokens…
    def stage_payloads(root: Path, kind: str) -> list[dict]:
        return [
            e["payload"]
            for e in entries(root)
            if e.get("type") == "run" and e["payload"].get("kind") == kind
        ]

    b_stages = stage_payloads(root_b, "stage")
    coder_stages = [p for p in b_stages if p["step"] != "oracle"]
    assert coder_stages and all(p.get("tokens") == 4321 for p in coder_stages)
    # the oracle role runs under the codex manifest, which declares no usage hint → unknown
    assert all("tokens" not in p for p in b_stages if p["step"] == "oracle")
    assert any(p.get("tokens") == 4321 for p in stage_payloads(root_b, "checkpoint"))
    # …while A's payloads are untouched (the field appears only when usage was captured).
    assert all("tokens" not in p for p in stage_payloads(root_a, "stage"))
    assert all("tokens" not in p for p in stage_payloads(root_a, "checkpoint"))

    # The run's progress.md shows the Tokens column with the accumulated per-stage counts
    # (Spec = specify + clarify = 2 × 4321), and — (unknown) where nothing was reported.
    prog = (root_b / "specs-src" / "010-add-x" / "progress.md").read_text(encoding="utf-8")
    assert "| Tokens |" in prog and "8642" in prog

    # Ledger verification stays green over the new additive payloads.
    assert main(["--root", str(root_b), "verify"]) == 0
    capsys.readouterr()


def test_json_status_payload_keys_stay_a_superset_for_e2e_parsers(native_project, capsys):
    """Plan 033 Track H / PAT-002 (RUNVIS): the --json pause payload keeps every prior key — the
    e2e notebooks' defensive `.get()` parsing of status/stage results must keep working."""
    import json as _json

    rc = main(
        ["--root", str(native_project), "run", "add x", "--no-input", "--json", "--spec-id", "RUN"]
    )
    assert rc == 3
    obj = _json.loads(capsys.readouterr().out)
    assert {"status", "gate", "stage", "spec_id", "stages"} <= set(obj)
    prior_stage_keys = {
        "step",
        "stage",
        "ok",
        "agent",
        "model",
        "attempts",
        "duration_s",
        "artifact",
        "outcome",
        "detail",
    }
    for st in obj["stages"]:
        assert prior_stage_keys <= set(st)
