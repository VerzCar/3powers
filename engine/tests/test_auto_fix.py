"""The bounded, code-only auto-fix loop (Track C).

Two layers of coverage:

* the pure :func:`threepowers.autofix.run_loop` orchestration — every stop reason (green, budget,
  no-progress, dispatch-failed, ``gate_gaming`` backstop, nothing-to-fix) driven with fakes, plus the
  give-up remediation summary; and
* the wired command surface — ``3pwr gate fix`` running the real deterministic gate suite against a
  real project with a fake coder, proving the SAFETY invariants: every re-check records an honest
  signed verdict, the loop records NO deviation/advisory and mutates no verdict, an unfixable red
  exhausts the budget and prints the step-by-step human summary, and a missing coder integration is
  refused actionably.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from threepowers import autofix, runner
from threepowers.cli import EXIT_FAIL, EXIT_OK, EXIT_SETUP, main
from threepowers.ledger import Ledger
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, GateResult, Verdict

# --------------------------------------------------------------------------- pure run_loop helpers


def _red(*gates: str) -> dict[str, Any]:
    """A red verdict dict (``Verdict.to_dict()`` shape) whose named gates failed."""
    return Verdict(
        spec_id="ZED",
        tier="T",
        adapter="a",
        result=STATUS_FAIL,
        gates=[GateResult(gate=g, status=STATUS_FAIL) for g in gates],
    ).to_dict()


def _green() -> dict[str, Any]:
    return Verdict(spec_id="ZED", tier="T", adapter="a", result=STATUS_PASS).to_dict()


class _Recompute:
    """A scripted recompute: yields the next (outcome, verdict) each call."""

    def __init__(self, *results: tuple[str, dict[str, Any]]) -> None:
        self._results = list(results)
        self.calls = 0

    def __call__(self) -> tuple[str, dict[str, Any]]:
        self.calls += 1
        return self._results.pop(0)


# --------------------------------------------------------------------------- run_loop: stop reasons


def test_run_loop_reaches_green_records_each_attempt():
    """A fixable red turns green: the loop dispatches, re-checks green, and reports ``fixed`` with
    one recorded attempt."""
    changed = iter([{"x": "1"}, {"x": "2"}])  # pre then post → one changed file
    snaps = [{"x": "1"}, {"x": "2"}]

    res = autofix.run_loop(
        verdict=_red("format"),
        max_attempts=3,
        dispatch=lambda prompt, scope: True,
        recompute=_Recompute(("pass", _green())),
        snapshot=lambda: snaps.pop(0),
    )
    assert res.fixed is True
    assert res.reason == autofix.REASON_GREEN
    assert len(res.attempts) == 1
    assert res.attempts[0].changed_files == ["x"]
    _ = changed  # snapshots drive the change detection


def test_run_loop_exhausts_budget_when_never_fixed():
    """A red that never clears exhausts the attempt budget and gives up (not green)."""
    n = 0

    def snap() -> dict[str, str]:
        nonlocal n
        n += 1
        return {"scratch": str(n)}  # each dispatch changes a file → never 'no progress'

    res = autofix.run_loop(
        verdict=_red("format"),
        max_attempts=2,
        dispatch=lambda p, s: True,
        recompute=_Recompute(("fail", _red("format")), ("fail", _red("format"))),
        snapshot=snap,
    )
    assert res.fixed is False
    assert res.reason == autofix.REASON_BUDGET
    assert len(res.attempts) == 2


def test_run_loop_stops_on_no_progress():
    """When the coder changes nothing and the same gates stay red, the loop bails immediately."""
    res = autofix.run_loop(
        verdict=_red("format"),
        max_attempts=5,
        dispatch=lambda p, s: True,
        recompute=_Recompute(("fail", _red("format"))),
        snapshot=lambda: {"x": "same"},  # identical pre/post → no change
    )
    assert res.reason == autofix.REASON_NO_PROGRESS
    assert len(res.attempts) == 1


def test_run_loop_stops_on_dispatch_failure():
    """A failed coder dispatch ends the loop without a re-check."""
    rc = _Recompute()
    res = autofix.run_loop(
        verdict=_red("format"),
        max_attempts=3,
        dispatch=lambda p, s: False,
        recompute=rc,
        snapshot=lambda: {},
    )
    assert res.reason == autofix.REASON_DISPATCH_FAILED
    assert rc.calls == 0  # never recomputed after a failed dispatch


def test_run_loop_gate_gaming_backstop_stops_immediately():
    """A ``gate_gaming`` trip on a re-check stops the loop at once — the coder is never re-dispatched
    after trying to weaken a check."""
    res = autofix.run_loop(
        verdict=_red("tests"),
        max_attempts=5,
        dispatch=lambda p, s: True,
        recompute=_Recompute(("fail", _red("tests", autofix.GAMING_GATE))),
        snapshot=iter([{"a": "1"}, {"a": "2"}]).__next__,
    )
    assert res.reason == autofix.REASON_GAMING
    assert len(res.attempts) == 1


def test_run_loop_nothing_to_fix_when_no_named_gate():
    """A red verdict with no per-gate failure names nothing to hand back: the loop stays honestly
    red and never dispatches the coder."""
    rc = _Recompute()
    res = autofix.run_loop(
        verdict=_green() | {"result": STATUS_FAIL},  # red result, empty gates
        max_attempts=3,
        dispatch=lambda p, s: (_ for _ in ()).throw(AssertionError("must not dispatch")),
        recompute=rc,
        snapshot=lambda: {},
    )
    assert res.fixed is False
    assert res.reason == autofix.REASON_NOTHING_TO_FIX
    assert res.attempts == []
    assert rc.calls == 0


# --------------------------------------------------------------------------- give-up summary


def test_give_up_summary_has_tried_and_left_blocks():
    """The give-up summary composes the per-gate panels with a 'what I tried / what's left for you'
    block, and names a signed deviation only as the labelled last resort."""
    res = autofix.AutoFixResult(
        "fail",
        autofix.REASON_BUDGET,
        [autofix.AttemptRecord(1, ["format"], ["a.py"])],
    )
    out = autofix.give_up_summary(res, _red("format"), run_id="007")
    assert "what I tried" in out
    assert "what's left for you" in out
    assert "attempt 1" in out
    assert "format" in out
    assert "last resort" in out
    assert "deviation" in out


def test_give_up_summary_gaming_points_at_manual_review():
    """A ``gate_gaming`` give-up steers the human to review the weakened check by hand."""
    res = autofix.AutoFixResult(
        "fail", autofix.REASON_GAMING, [autofix.AttemptRecord(1, ["tests"], [])]
    )
    out = autofix.give_up_summary(res, _red("tests", autofix.GAMING_GATE))
    assert "gate_gaming" in out
    assert "review" in out


# --------------------------------------------------------------------------- `gate fix` command


RISK = "tiers:\n  T: { diff_coverage: 0, gates: [format] }\n"
ADAPTER = (
    'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
    "gates:\n"
    '  format: { check_cmd: "python check.py", parser: fmt }\n'
)
CHECK = "import pathlib, sys\nsys.exit(0 if pathlib.Path('f.txt').read_text() == 'ok' else 1)\n"


def _fix_project(tmp_path, monkeypatch, *, with_coder: bool, max_attempts: int = 2):
    """A real git repo whose ``format`` gate is red until ``f.txt`` becomes 'ok'.

    Wires a signer, an adapter with a marker-file gate, and (optionally) a coder integration + agent
    manifest so ``3pwr gate fix`` can dispatch. Returns ``(root, spec_path)``."""
    root = tmp_path / "repo"
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "agents").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK, encoding="utf-8")
    (tp / "config" / "auto-fix.yaml").write_text(
        yaml.safe_dump({"enabled": True, "max_attempts": max_attempts, "scope_to_failed": False}),
        encoding="utf-8",
    )
    (tp / "adapters" / "a" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")
    roles: dict[str, Any] = {"version": 1, "roles": {"oracle": {"integration": "codex"}}}
    if with_coder:
        roles["roles"]["coder"] = {"integration": "claude", "model_family": "anthropic"}
        (tp / "agents" / "claude.yaml").write_text(
            yaml.safe_dump(
                {"command": "claude", "family": "anthropic", "headless": True, "prompt_flag": "-p"}
            ),
            encoding="utf-8",
        )
    (tp / "config" / "roles.yaml").write_text(yaml.safe_dump(roles), encoding="utf-8")

    (root / "tests").mkdir(parents=True)
    (root / "d").write_text("", encoding="utf-8")
    (root / "check.py").write_text(CHECK, encoding="utf-8")
    (root / "f.txt").write_text("bad", encoding="utf-8")
    spec = root / "spec.md"
    spec.write_text("**Spec ID**: ZED\n\n- **ZED-FR-001**: shall.\n", encoding="utf-8")

    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@e.st"],
        ["git", "config", "user.name", "t"],
    ):
        subprocess.run(cmd, cwd=str(root), check=True, capture_output=True)
    return root, spec


def _verdict_entries(root: Path) -> list[dict]:
    return [
        e for e in Ledger(root / ".3powers" / "ledger.jsonl").entries() if e["type"] == "verdict"
    ]


def _deviation_entries(root: Path) -> list[dict]:
    return [
        e for e in Ledger(root / ".3powers" / "ledger.jsonl").entries() if e["type"] == "deviation"
    ]


def test_gate_fix_reaches_green_and_records_only_verdicts(tmp_path, monkeypatch, capsys):
    """A red ``format`` gate the coder fixes: ``gate fix`` reaches green (exit 0), records an honest
    signed verdict for the initial run AND each re-check, and records NO deviation/advisory."""
    root, spec = _fix_project(tmp_path, monkeypatch, with_coder=True)

    def fake_coder(argv, **kw):
        # The coder edits code — here, flips the marker so the real gate goes green on re-check.
        (root / "f.txt").write_text("ok", encoding="utf-8")
        return (0, "fixed the marker", "")

    monkeypatch.setattr(runner, "dispatch_agent", fake_coder)

    rc = main(
        ["--root", str(root), "gate", "fix", "--spec", str(spec), "--tier", "T", "--adapter", "a"]
    )
    assert rc == EXIT_OK
    # initial red verdict + one green re-check = 2 honest signed verdicts.
    assert len(_verdict_entries(root)) == 2
    # SAFETY: the loop never records a deviation or advisory.
    assert _deviation_entries(root) == []


def test_gate_fix_unfixable_exhausts_budget_and_prints_summary(tmp_path, monkeypatch, capsys):
    """An unfixable red exhausts the attempt budget: ``gate fix`` exits gate-red (1), prints the
    step-by-step human remediation summary, records an honest verdict per pass, and records NO
    deviation."""
    root, spec = _fix_project(tmp_path, monkeypatch, with_coder=True, max_attempts=2)
    n = 0

    def fake_coder(argv, **kw):
        # Touches an unrelated scratch file each attempt (so the loop never trips 'no progress') but
        # never fixes the gate — the budget must run out.
        nonlocal n
        n += 1
        (root / f"scratch{n}.txt").write_text("x", encoding="utf-8")
        return (0, "did not fix it", "")

    monkeypatch.setattr(runner, "dispatch_agent", fake_coder)

    rc = main(
        ["--root", str(root), "gate", "fix", "--spec", str(spec), "--tier", "T", "--adapter", "a"]
    )
    out = capsys.readouterr().out
    assert rc == EXIT_FAIL
    assert "what I tried" in out and "what's left for you" in out
    # initial red + 2 red re-checks (budget=2) = 3 honest signed verdicts, still no deviation.
    assert len(_verdict_entries(root)) == 3
    assert _deviation_entries(root) == []


def test_gate_fix_refuses_when_no_coder_configured(tmp_path, monkeypatch, capsys):
    """A red verdict with no coder integration configured is refused with an actionable setup
    message (exit 4) — the loop never runs."""
    root, spec = _fix_project(tmp_path, monkeypatch, with_coder=False)

    rc = main(
        ["--root", str(root), "gate", "fix", "--spec", str(spec), "--tier", "T", "--adapter", "a"]
    )
    err = capsys.readouterr().err
    assert rc == EXIT_SETUP
    assert "no coder integration configured" in err
    assert "roles.coder.integration" in err
    # only the initial verdict was recorded; the loop never ran.
    assert len(_verdict_entries(root)) == 1
    assert _deviation_entries(root) == []


def test_gate_fix_green_project_is_nothing_to_fix(tmp_path, monkeypatch, capsys):
    """A green project reports 'nothing to fix' and exits 0 without dispatching a coder."""
    root, spec = _fix_project(tmp_path, monkeypatch, with_coder=True)
    (root / "f.txt").write_text("ok", encoding="utf-8")  # already green

    def must_not_dispatch(argv, **kw):
        raise AssertionError("a green project must not dispatch the coder")

    monkeypatch.setattr(runner, "dispatch_agent", must_not_dispatch)

    rc = main(
        ["--root", str(root), "gate", "fix", "--spec", str(spec), "--tier", "T", "--adapter", "a"]
    )
    out = capsys.readouterr().out
    assert rc == EXIT_OK
    assert "nothing to fix" in out
    assert len(_verdict_entries(root)) == 1
