"""The native provider-agnostic executive — EXEC (spec 009).

The engine owns its executive: `3pwr run` dispatches each stage to a headless coding agent directly and
runs the gate suite in-process, with no IDE and no Spec Kit. These tests exercise the whole runner,
manifest, prompt, preflight, and diagnostics flow with a FAKE agent and no network (EXEC-NFR-004), so the
engine makes no model call itself (EXEC-NFR-001).
"""

from __future__ import annotations

import pytest

from threepowers import agents, orchestrate, prompts, runner, runpreflight
from threepowers.cli import _resolve_runner_kind, main
from threepowers.config import Settings
from threepowers.runner import CliAgentRunner, DispatchResult, NativeRunner


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
    # every shipped manifest builds a valid invocation
    for name in shipped:
        argv, _ = agents.build_command(agents.load_agent(s, name), "PROMPT")
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

    def fake_dispatcher(argv, *, cwd, stdin, timeout):
        seen.append((argv, cwd, stdin, timeout))
        return (0, "changes written", "")

    r = CliAgentRunner(s, manifest, model="anthropic/opus", intent="do it", dispatcher=fake_dispatcher)
    res = r.dispatch("implement", "Build")
    assert res.ok and res.model == "anthropic/opus"
    argv = seen[0][0]
    assert argv[0] == "claude" and "--model" in argv and argv[-2] == "-p"
    assert "Implement" in argv[-1]  # the assembled stage prompt is the final arg


def test_cli_agent_runner_reports_dispatch_failure(tmp_path):
    """EXEC-FR-016: a non-zero agent exit is a dispatch failure carrying the reason."""
    s = Settings(root=tmp_path)

    def failing(argv, *, cwd, stdin, timeout):
        return (127, "", "agent command not found: codex")

    r = CliAgentRunner(s, {"command": "codex"}, dispatcher=failing)
    res = r.dispatch("plan", "Plan")
    assert not res.ok and "not found" in res.detail


# --------------------------------------------------------------------------- NativeRunner drive (EXEC-FR-001/006/007/008)
def _fake_runner(verdict="pass", fail_step=""):
    def dispatch(step, stage):
        return DispatchResult(step != fail_step, detail=step)

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
        yaml.safe_dump({"version": 1, "diversity_level": "family", "roles": {"coder": coder, "oracle": oracle}}),
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
        s, coder_agent="claude", oracle_agent="codex", entries=[], spec_id="RUN", command_present=present
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
        s, coder_agent="claude", oracle_agent="claude", entries=[], spec_id="RUN", command_present=present
    )
    assert any("oracle" in p.name and "deviation" in p.fix for p in runpreflight.unmet(same))


# --------------------------------------------------------------------------- CLI end-to-end (EXEC-FR-013/001/006)
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
    # a headless agent CLI is "present"; the agent process is faked (no model call — EXEC-NFR-001)
    monkeypatch.setattr(runpreflight.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")
    monkeypatch.setattr(runner, "dispatch_agent", lambda argv, **kw: (0, "ok", ""))
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
        ["--root", str(native_project), "run", "add a rate limiter", "--no-input", "--spec-id", "RUN"]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "review-spec" in out  # paused at the first mandatory human gate (FR-006)


def test_cli_native_run_runs_gates_in_process_at_verify(native_project, monkeypatch, capsys):
    """EXEC-FR-006: resuming reaches Verify, where the deterministic gate suite runs IN-PROCESS."""
    import threepowers.cli as climod
    from threepowers.verdict import STATUS_PASS

    calls: list = []

    def fake_gates(settings, target, **kw):
        calls.append(kw.get("tier"))
        import types

        return types.SimpleNamespace(result=STATUS_PASS)

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
