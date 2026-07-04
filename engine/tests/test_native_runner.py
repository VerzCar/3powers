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
    expects, so a native run advances past Specify/Oracle/Implement. No model call — the engine issues none
    (EXEC-NFR-001, RUNLIVE-NFR-001)."""

    def fake(argv, **kw):
        from pathlib import Path

        cwd = Path(kw.get("cwd", "."))
        prompt = argv[-1] if argv else ""
        if "STAGE: Specify" in prompt:
            d = cwd / "specs" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "spec.md").write_text(f"# Spec\n**Spec ID**: {spec_id}\n", encoding="utf-8")
        elif "STAGE: Plan" in prompt:
            # plan/tasks now carry hard artifact contracts (PHASE-FR-002) — the fake writes them
            # into the feature workspace's artifacts folder (PHASE-FR-001) like a real agent would.
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "STAGE: Tasks" in prompt:
            d = cwd / "specs" / spec_id / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text(
                f"# Tasks\n- [ ] T001 [{spec_id}-FR-001] do it (files: src/impl.py)\n",
                encoding="utf-8",
            )
        elif "STAGE: Oracle" in prompt:
            d = cwd / "tests" / "oracle" / spec_id
            d.mkdir(parents=True, exist_ok=True)
            (d / "test_oracle.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        elif "STAGE: Implement" in prompt:
            d = cwd / "src"
            d.mkdir(parents=True, exist_ok=True)
            (d / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")
        return (0, "changes written", "")

    return fake


@pytest.fixture()
def native_project(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    (root / ".3powers" / "agents").mkdir(parents=True)
    (root / "specs" / "009-x").mkdir(parents=True)
    (root / "specs" / "009-x" / "spec.md").write_text("# Spec\n**Spec ID**: X\n", encoding="utf-8")
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
    keyfile = tmp_path / "signer.key"
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
    assert rc == 0
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
        main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 0
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
    assert rc == 0
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
        verify_artifact=lambda: artifacts.verify(contract, ["specs/x/spec.md"]),
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
    assert rc == 0
    obj = _json.loads(capsys.readouterr().out)
    assert obj["status"] == "paused_at_gate" and obj["gate"] == "review-spec"
    stages = obj["stages"]
    steps = [st["step"] for st in stages]
    assert "specify" in steps
    spec_stage = next(st for st in stages if st["step"] == "specify")
    assert spec_stage["ok"] and spec_stage["outcome"] == "ok" and spec_stage["agent"] == "claude"
    assert spec_stage["attempts"] == 1 and "spec.md" in spec_stage["artifact"]


# --------------------------------------------------------------------------- per-stage artifact contract (RUNLIVE-FR-001/002)
def test_cli_specify_producing_nothing_is_artifact_missing(native_project, monkeypatch, capsys):
    """RUNLIVE-FR-002/SC-001: a Specify agent that writes no spec stops the run with a named artifact
    failure — not a silent pass, not a gate-red."""
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (0, "did nothing", ""))
    rc = main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc == 2  # EXIT_USAGE — a setup/dispatch problem, not a gate verdict
    assert "artifact missing" in out and "Spec" in out
    assert "gates red" not in out  # never mislabeled a gate-red (SC-001)


# --------------------------------------------------------------------------- commit checkpoints + resume (RUNLIVE-FR-010)
def _writer_no_implement():
    def fake(argv, **kw):
        p = argv[-1] if argv else ""
        # plan/tasks now carry hard contracts too (PHASE-FR-002) — write them so the run reaches Build
        if "STAGE: Plan" in p:
            d = Path(kw["cwd"]) / "specs" / "RUN" / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "plan.md").write_text("# Plan\n", encoding="utf-8")
        elif "STAGE: Tasks" in p:
            d = Path(kw["cwd"]) / "specs" / "RUN" / "artifacts"
            d.mkdir(parents=True, exist_ok=True)
            (d / "tasks.md").write_text("# Tasks\n- [ ] T001 [RUN-FR-001] x\n", encoding="utf-8")
        elif "STAGE: Oracle" in p:
            d = Path(kw["cwd"]) / "tests" / "oracle" / "RUN"
            d.mkdir(parents=True, exist_ok=True)
            (d / "test_o.py").write_text("def test_o():\n    assert True\n", encoding="utf-8")
        return (0, "ok", "")  # Implement writes nothing → artifact_missing

    return fake


def _recording_writer(seen):
    def fake(argv, **kw):
        p = argv[-1] if argv else ""
        for key in ("Specify", "Clarify", "Plan", "Tasks", "Oracle", "Implement"):
            if f"STAGE: {key}" in p:
                seen.append(key.lower())
        if "STAGE: Implement" in p:
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
        lambda *a, **k: Verdict(spec_id="RUN", tier="Standard", adapter="python", result=STATUS_PASS),
    )

    # Run 1: specify (committed as a checkpoint) → stop at review-spec.
    assert (
        main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"]) == 0
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
    assert rc2 == 2 and "artifact missing" in capsys.readouterr().out

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
    assert rc3 == 0 and "signoff" in capsys.readouterr().out
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
            if state["step"] == "specify":  # the hosted run's branch carries the produced spec
                d = Path(cwd) / "specs" / "RUN"
                d.mkdir(parents=True, exist_ok=True)
                (d / "spec.md").write_text("# Spec\n**Spec ID**: RUN\n", encoding="utf-8")
            return (0, "checked out", "")
        return (1, "", "unexpected")

    monkeypatch.setattr(hosted, "run_hosted_command", fake_hosted)
    rc = main(["--root", str(native_project), "run", "add x", "--no-input", "--spec-id", "RUN"])
    out = capsys.readouterr().out
    assert rc == 0 and "review-spec" in out  # the hosted-produced spec advanced the run to the gate


def test_no_auto_commit_makes_no_checkpoint(native_project, capsys):
    """RUNLIVE-FR-010 (edge): with auto-commit disabled the runner commits nothing."""
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
    assert rc == 0
    after = sp.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(native_project),
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert before == after  # no checkpoint commit was made
