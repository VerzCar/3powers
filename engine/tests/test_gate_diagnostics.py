"""Gate failure diagnostics — inline red-gate summaries, `gate run --id <NNN>`, prerequisite
install hints before any gate runs, and hints carrying the real run number (GDIAG, spec 021).

Exercises Track B of plan 030 offline: the structured gate-red rendering fed by the verdict payload
(GDIAG-FR-001), the `--id` spec-resolution shorthand with its exactly-one-match contract
(GDIAG-FR-002) and its mutual exclusion with `--spec` (GDIAG-FR-003), the prerequisite pre-check
that stops on the setup path with per-tool install hints before any gate command executes
(GDIAG-FR-004) while quarantine-safe gates and report-only runs stay untouched (GDIAG-FR-005), and
the Resume/Inspect hints interpolating the resolved spec id (GDIAG-FR-006).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import cli, orchestrate, workspace
from threepowers.cli import EXIT_SETUP, EXIT_USAGE, main
from threepowers.config import Settings
from threepowers.gates import PrerequisiteError, missing_prerequisites, run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_SKIP, Verdict


# --------------------------------------------------------------------------- fixtures
def _repo(tmp_path: Path) -> Path:
    """A minimal rooted repo (`.3powers/` present) with one numbered feature folder."""
    (tmp_path / ".3powers" / "config").mkdir(parents=True)
    feature = tmp_path / "specs" / "030-add-button"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text(
        "**Spec ID**: GD\n\n- **GD-FR-001**: shall.\n", encoding="utf-8"
    )
    return tmp_path


_RISK = "tiers:\n  T: {{ diff_coverage: 0, gates: [{gates}] }}\n"


def _project(
    tmp_path: Path, adapter_yaml: str, tier_gates: str = "format"
) -> tuple[Settings, Path]:
    """A rooted project with a declarative test adapter — mirrors test_gates/_missing_toolchain."""
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(
        _RISK.format(gates=tier_gates), encoding="utf-8"
    )
    (tp / "adapters" / "a" / "adapter.yaml").write_text(adapter_yaml, encoding="utf-8")
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "d").write_text("")
    (proj / "spec.md").write_text("**Spec ID**: GD\n\n- **GD-FR-001**: shall.\n", encoding="utf-8")
    return Settings(root=tmp_path), proj


_MISSING_PROBE = "definitely-not-a-real-tool-xyz --version"
_OK_PROBE = 'python -c "print(1)"'


# --------------------------------------------------------------------------- B2. resolve_feature_dir (GDIAG-FR-002)
def test_resolve_feature_dir_returns_the_single_match(tmp_path):
    """GDIAG-FR-002: exactly one specs/<NNN>-*/ directory resolves to that directory."""
    root = _repo(tmp_path)
    assert workspace.resolve_feature_dir(root, "030") == root / "specs" / "030-add-button"


def test_resolve_feature_dir_errors_on_zero_matches(tmp_path):
    """GDIAG-FR-002: no matching folder is a user-facing error naming the pattern and the fix."""
    root = _repo(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"specs/031-\*/"):
        workspace.resolve_feature_dir(root, "031")


def test_resolve_feature_dir_errors_on_multiple_matches(tmp_path):
    """GDIAG-FR-002: an ambiguous prefix is a user-facing error naming every candidate."""
    root = _repo(tmp_path)
    (root / "specs" / "030-other").mkdir()
    with pytest.raises(LookupError, match="specs/030-add-button.*specs/030-other"):
        workspace.resolve_feature_dir(root, "030")


# --------------------------------------------------------------------------- B2. gate run --id (GDIAG-FR-002/003)
def test_gate_run_id_resolves_the_same_spec_as_spec(tmp_path, monkeypatch, capsys):
    """GDIAG-FR-002: `gate run --id 030` targets exactly the spec path `--spec specs/030-*/spec.md`
    targets — the shorthand and the explicit path are interchangeable."""
    root = _repo(tmp_path)
    captured: list[Path] = []

    def fake_run_gates(s, target, *, tier, spec_path, **kw):
        captured.append(spec_path)
        return Verdict(spec_id="GD", tier=tier, adapter="a").finalize()

    monkeypatch.setattr(cli, "run_gates", fake_run_gates)
    base = ["--root", str(root), "gate", "run", "--adapter", "a", "--no-ledger"]
    assert main([*base, "--id", "030"]) == 0
    assert main([*base, "--spec", str(root / "specs" / "030-add-button" / "spec.md")]) == 0
    capsys.readouterr()
    assert len(captured) == 2 and captured[0] == captured[1]
    assert captured[0].name == "spec.md" and captured[0].parent.name == "030-add-button"


def test_gate_run_id_errors_clearly_on_zero_and_multiple_matches(tmp_path, monkeypatch, capsys):
    """GDIAG-FR-002: `--id` with zero or multiple matching folders errors without running a gate."""
    root = _repo(tmp_path)
    (root / "specs" / "030-other").mkdir()
    ran: list[Path] = []
    monkeypatch.setattr(cli, "run_gates", lambda *a, **kw: ran.append(kw.get("spec_path")))
    base = ["--root", str(root), "gate", "run", "--adapter", "a", "--no-ledger"]
    assert main([*base, "--id", "031"]) == EXIT_USAGE
    assert "specs/031-*/" in capsys.readouterr().err
    assert main([*base, "--id", "030"]) == EXIT_USAGE
    assert "ambiguous" in capsys.readouterr().err
    assert ran == []  # no gate ran in either failure mode


def test_gate_run_rejects_id_combined_with_spec(tmp_path, capsys):
    """GDIAG-FR-003: `--id` and `--spec` are mutually exclusive — a clear error, nonzero exit."""
    root = _repo(tmp_path)
    with pytest.raises(SystemExit) as exc:
        main(
            ["--root", str(root), "gate", "run", "--id", "030", "--spec", "x/spec.md"]
        )
    assert exc.value.code == EXIT_USAGE
    assert "not allowed with" in capsys.readouterr().err


# --------------------------------------------------------------------------- B1. gate-red summary (GDIAG-FR-001/006)
_RED_VERDICT = {
    "spec_id": "030",
    "gates": [
        {"gate": "format", "status": "fail", "tool": "biome", "findings": ["biome found 2 issues"]},
        {"gate": "types", "status": "pass", "tool": "tsc", "findings": []},
        {"gate": "tests", "status": "fail", "tool": "vitest", "findings": ["1 test failed"]},
    ],
}


def test_gate_red_event_renders_each_failed_gate_with_tool_and_first_line():
    """GDIAG-FR-001: the gate-red rendering names the counts and, per failed gate, the gate name,
    its adapter tool, and the first actionable findings line."""
    ev = orchestrate.Event(
        "failed", "gate_red", "Verify", "fail", data={"verdict": _RED_VERDICT, "spec_id": "030"}
    )
    out = orchestrate.format_event(ev, "auto")
    assert "gates failed (2 of 3):" in out
    assert "format · biome" in out and "↳ biome found 2 issues" in out
    assert "· vitest" in out and "↳ 1 test failed" in out
    assert "tsc" not in out  # a passing gate never appears in the failure summary


def test_gate_red_summary_hints_carry_the_real_nnn():
    """GDIAG-FR-006: the Resume:/Inspect: command lines interpolate the resolved spec id — the
    real NNN, never a placeholder."""
    ev = orchestrate.Event(
        "failed", "gate_red", "Verify", "fail", data={"verdict": _RED_VERDICT, "spec_id": "030"}
    )
    out = orchestrate.format_event(ev, "auto")
    assert "Resume:  3pwr run --resume --spec-id 030" in out
    assert "Inspect: 3pwr gate run --id 030" in out
    assert "RUN" not in out


def test_gate_red_event_without_verdict_payload_renders_the_plain_line():
    """GDIAG-FR-001 property: an event with no verdict payload (simulated/legacy emitter) renders
    the pre-existing one-line message unchanged."""
    out = orchestrate.format_event(
        orchestrate.Event("failed", stage="Verify", detail="fail"), "auto"
    )
    assert "gates red" in out and "gates failed" not in out


# --------------------------------------------------------------------------- B3. prerequisites (GDIAG-FR-004/005)
_ADAPTER_MISSING_FMT = (
    'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
    "toolchain:\n"
    f'  fmt: {{ install: "get-fmt now", probe: "{_MISSING_PROBE}" }}\n'
    "gates:\n"
    "  format: { cmd: \"python -c \\\"import pathlib; pathlib.Path('ran.txt').write_text('x')\\\"\","
    " parser: fmt, requires: fmt }\n"
)


def test_missing_required_tool_stops_before_any_gate_runs(tmp_path):
    """GDIAG-FR-004: a required tool failing its probe raises the prerequisite error before any
    gate command executes — the gate's own command never ran."""
    s, proj = _project(tmp_path, _ADAPTER_MISSING_FMT)
    with pytest.raises(PrerequisiteError) as exc:
        run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    assert exc.value.missing == [("fmt", "get-fmt now")]
    assert "prerequisites missing" in str(exc.value) and "get-fmt now" in str(exc.value)
    assert not (proj / "ran.txt").exists()  # the format command was never executed


def test_cmd_gate_run_exits_setup_with_the_install_hint(tmp_path, capsys):
    """GDIAG-FR-004: `gate run` surfaces the prerequisites block on stderr and exits with the
    setup exit code — a setup problem, never a gate verdict."""
    s, proj = _project(tmp_path, _ADAPTER_MISSING_FMT)
    rc = main(
        [
            "--root", str(tmp_path), "gate", "run", "--path", str(proj),
            "--tier", "T", "--adapter", "a", "--no-ledger", "--spec", str(proj / "spec.md"),
        ]
    )
    err = capsys.readouterr().err
    assert rc == EXIT_SETUP
    assert "prerequisites missing" in err and "fmt" in err and "get-fmt now" in err
    assert not (proj / "ran.txt").exists()


def test_mutation_stays_quarantine_safe_and_shared_tools_probe_once(tmp_path):
    """GDIAG-FR-005: the pre-check never hard-stops on the opt-in mutation gate — its missing tool
    keeps the existing skip; a tool required by several non-optional gates is probed/listed once."""
    adapter = (
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
        "toolchain:\n"
        f'  ok: {{ install: "get-ok", probe: {_OK_PROBE!r} }}\n'
        f'  mut: {{ install: "get-mut", probe: "{_MISSING_PROBE}" }}\n'
        "gates:\n"
        '  format: { cmd: "python -c pass", parser: ok, requires: ok }\n'
        '  lint: { cmd: "python -c pass", parser: ok, requires: ok }\n'
        '  mutation: { cmd: "python -c pass", parser: mut, requires: mut }\n'
    )
    s, proj = _project(tmp_path, adapter, tier_gates="format, lint, mutation")
    manifest = {"toolchain": {"x": {"install": "i", "probe": _MISSING_PROBE}}}
    dup = missing_prerequisites(
        {
            **manifest,
            "gates": {
                "format": {"cmd": "c", "requires": "x"},
                "lint": {"cmd": "c", "requires": "x"},
            },
        },
        ["format", "lint"],
        proj,
    )
    assert dup == [("x", "i")]  # deduplicated: one probe, one listing
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    mutation = next(g for g in v.gates if g.gate == "mutation")
    assert mutation.status == STATUS_SKIP  # quarantine-safe: skipped, never a hard stop


def test_report_only_run_never_hard_stops_on_prerequisites(tmp_path):
    """GDIAG-FR-005: a report-only (brownfield on-ramp) run proceeds despite a failing probe and
    surfaces the per-gate missing-tool finding as before."""
    adapter = (
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\n'
        "toolchain:\n"
        f'  fmt: {{ install: "get-fmt now", probe: "{_MISSING_PROBE}" }}\n'
        "gates:\n"
        '  format: { cmd: "definitely-not-a-real-tool-xyz ci .", parser: fmt, requires: fmt }\n'
    )
    s, proj = _project(tmp_path, adapter)
    v = run_gates(s, proj, tier="T", spec_path=None, adapter_name="a", report_only=True)
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == STATUS_FAIL and fmt.details.get("missing_tool") == "fmt"


def test_unprobed_tools_are_assumed_present(tmp_path):
    """GDIAG-FR-004 edge: a tool with no probe declared (or no toolchain entry) is never flagged —
    the in-gate missing-tool detection still applies, so nothing is silently passed."""
    manifest = {
        "toolchain": {"fmt": {"install": "get-fmt"}},  # install hint but no probe
        "gates": {
            "format": {"cmd": "c", "requires": "fmt"},
            "lint": {"cmd": "c", "requires": "unlisted"},  # no toolchain entry at all
        },
    }
    assert missing_prerequisites(manifest, ["format", "lint"], tmp_path) == []
