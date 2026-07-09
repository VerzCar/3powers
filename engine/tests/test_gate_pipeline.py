"""Pipeline gate view — live per-gate status rows, per-failure panels, and noise filters
(GATEPIPE, spec 023).

Exercises Track D of plan 030 offline: the gate engine's start/finish event seam and the live
pipeline rows (GATEPIPE-FR-001), the plain-text/`--json` degradation contract (GATEPIPE-FR-002),
the per-failed-gate panels that replace the bottom "failures:" block — trimming, auto-fix hint,
scanner findings (GATEPIPE-FR-003) — the ExperimentalWarning/blank-line noise filter
(GATEPIPE-FR-004), the `–` info glyph on a skipped spec_integrity (GATEPIPE-FR-005), and the
deterministic, presentation-only rendering property (GATEPIPE-NFR-001).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

from threepowers import orchestrate, style
from threepowers.cli import main
from threepowers.config import Settings
from threepowers.gates import run_gates
from threepowers.verdict import GateResult

# Strips every ANSI escape sequence (SGR, cursor moves, mode sets) a rich live region emits —
# a test matcher only, so content assertions survive the live rendering.
_ESC_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _clean(text: str) -> str:
    return _ESC_RE.sub("", text)


# --------------------------------------------------------------------------- fixtures
_RISK = "tiers:\n  T: { diff_coverage: 0, gates: [format, lint] }\n"

_ADAPTER = """\
language: a
detect: ["d"]
test_roots: ["tests"]
gates:
  format:
    cmd: python -c "print('ok')"
    parser: biome
    fix_cmd: biome check --write .
  lint:
    cmd: python -c "import sys; print('err one'); print('err two'); sys.exit(1)"
    parser: eslint
"""

_ADAPTER_FAIL_FMT = """\
language: a
detect: ["d"]
test_roots: ["tests"]
gates:
  format:
    cmd: python -c "import sys; print('drift in a.ts'); sys.exit(1)"
    parser: biome
    fix_cmd: biome check --write .
  lint:
    cmd: python -c "print('ok')"
    parser: eslint
"""


def _project(tmp_path: Path, adapter_yaml: str) -> tuple[Settings, Path]:
    """A rooted project with a declarative test adapter — mirrors test_gate_diagnostics."""
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(_RISK, encoding="utf-8")
    (tp / "adapters" / "a" / "adapter.yaml").write_text(adapter_yaml, encoding="utf-8")
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "d").write_text("")
    (proj / "spec.md").write_text("**Spec ID**: GP\n\n- **GP-FR-001**: shall.\n", encoding="utf-8")
    return Settings(root=tmp_path), proj


class _Recorder:
    """A recording GateObserver capturing the event stream in order."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str, str]] = []

    def gate_started(self, gate: str, tool: str) -> None:
        self.events.append(("start", gate, tool))

    def gate_finished(self, result: GateResult) -> None:
        self.events.append(("finish", result.gate, result.status))


# --------------------------------------------------------------------------- D1. events + live rows
def test_run_gates_emits_start_and_finish_events_in_gate_order(tmp_path):
    """GATEPIPE-FR-001: the gate engine emits a start event before each required gate runs and a
    finish event with its result — every start before its own finish, in execution order."""
    s, proj = _project(tmp_path, _ADAPTER)
    rec = _Recorder()
    run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a", observer=rec)
    assert rec.events == [
        ("start", "format", "biome"),
        ("finish", "format", "pass"),
        ("start", "lint", "eslint"),
        ("finish", "lint", "fail"),
    ]


def test_live_pipeline_rows_show_running_then_final_glyphs_and_summary():
    """GATEPIPE-FR-001: on a live terminal one compact row per gate transitions from the running
    glyph to `✓ gate · tool <elapsed>` / `✗ gate · tool <elapsed>  N errors`, updated in place."""
    buf = io.StringIO()
    st = style.Styler(enabled=True)
    pipe = orchestrate.GatePipeline(buf, st, live=True)
    with pipe:
        pipe.gate_started("format", "biome")
        pipe.gate_finished(GateResult(gate="format", status="pass", tool="biome", duration_ms=400))
        pipe.gate_started("types", "tsc")
        pipe.gate_finished(
            GateResult(
                gate="types",
                status="fail",
                tool="tsc",
                duration_ms=1200,
                findings=["error TS2345", "error TS2411"],
            )
        )
    out = _clean(buf.getvalue())
    assert "(running…)" in out  # the row existed in its running state before the result landed
    assert "✓ format · biome" in out.replace("\n", " ") or "✓" in out and "format · biome" in out
    assert "0.4 s" in out
    assert "✗" in out and "types · tsc" in out
    assert "1.2 s" in out and "2 errors" in out


# --------------------------------------------------------------------------- D1. degradation
def test_non_tty_pipeline_degrades_to_sequential_plain_rows_without_ansi():
    """GATEPIPE-FR-002: off a TTY the pipeline prints one plain-text row per FINISHED gate — no
    running rows, no in-place updates, and no ANSI escape anywhere."""
    buf = io.StringIO()
    pipe = orchestrate.GatePipeline(buf, style.Styler())  # StringIO is not a TTY → plain mode
    with pipe:
        pipe.gate_started("format", "biome")
        assert buf.getvalue() == ""  # a running gate prints nothing in plain mode
        pipe.gate_finished(GateResult(gate="format", status="pass", tool="biome", duration_ms=400))
        pipe.gate_started("types", "tsc")
        pipe.gate_finished(
            GateResult(gate="types", status="fail", tool="tsc", duration_ms=1200, findings=["e"])
        )
    out = buf.getvalue()
    lines = out.splitlines()
    assert "\x1b" not in out and "(running" not in out
    assert len(lines) == 2
    assert "✓ format · biome" in lines[0] and "0.4 s" in lines[0]
    assert "✗ types · tsc" in lines[1] and "1 error" in lines[1]


def test_json_gate_run_payload_is_pure_json_with_no_pipeline_rows(tmp_path, capsys):
    """GATEPIPE-FR-002: a --json gate run's stdout is exactly the machine payload — the pipeline
    never routes a byte through it, so the output parses and re-serializes byte-identically."""
    s, proj = _project(tmp_path, _ADAPTER)
    rc = main(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--adapter",
            "a",
            "--no-ledger",
            "--spec",
            str(proj / "spec.md"),
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1  # lint fails
    payload = json.loads(out)
    assert out == json.dumps(payload, indent=2) + "\n"  # nothing but the payload was printed
    assert payload["verdict"]["result"] == "fail"


# --------------------------------------------------------------------------- D2. failure panels
def test_failed_gate_panel_trims_to_30_meaningful_lines_and_shows_the_fix_hint():
    """GATEPIPE-FR-003: a failed gate's panel shows at most the first 30 meaningful lines with a
    `… N more lines` note and ends with the `↳ auto-fix:` hint when a fix_cmd is configured."""
    findings = [f"error line {i}" for i in range(40)] + ["", "   "]
    gate = {
        "gate": "format",
        "status": "fail",
        "tool": "biome",
        "duration_ms": 1200,
        "findings": findings,
        "details": {"fix_cmd": "biome check --write ."},
    }
    out = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    panel = out.split("hand back to your coding agent")[0]  # the panel region, before the prompt
    shown = [ln for ln in panel.splitlines() if "error line" in ln]
    assert len(shown) == 30 and "error line 29" in shown[-1]
    assert "… 10 more lines" in panel
    assert "↳ auto-fix: biome check --write ." in panel
    assert "format · biome" in panel and "1.2 s" in panel


def test_failure_panels_replace_the_bottom_failures_block(tmp_path, capsys):
    """GATEPIPE-FR-003: a red gate run prints one panel per failed gate and no bottom "failures:"
    block — the panels are the failure surface."""
    s, proj = _project(tmp_path, _ADAPTER_FAIL_FMT)
    rc = main(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--adapter",
            "a",
            "--no-ledger",
            "--spec",
            str(proj / "spec.md"),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert "failures:" not in out
    assert "format · biome" in out and "drift in a.ts" in out
    assert "↳ auto-fix: biome check --write ." in out


def test_scanner_failure_panel_renders_one_line_per_finding():
    """GATEPIPE-FR-003: dependency/secret scan panels render one line per finding — the finding ID
    and the package/file each on its own row."""
    gate = {
        "gate": "dependency_scan",
        "status": "fail",
        "tool": "osv-scanner",
        "duration_ms": 900,
        "findings": ["GHSA-qx2v-qp2m-jg93 in postcss", "GHSA-q8mj-m7cp-5q26 in qs"],
        "details": {"count": 2},
    }
    out = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    panel = out.split("hand back to your coding agent")[0]  # the panel region, before the prompt
    lines = panel.splitlines()
    assert any("GHSA-qx2v-qp2m-jg93 in postcss" in ln for ln in lines)
    assert any("GHSA-q8mj-m7cp-5q26 in qs" in ln for ln in lines)
    ghsa = [ln for ln in lines if "GHSA-" in ln]
    assert len(ghsa) == 2  # one line per finding


def test_failed_gate_panel_annotates_a_waived_gate_only_when_covered():
    """Covers: 3PWR-FR-057 — a failed gate covered by an active deviation carries the waiver
    annotation in its panel; an uncovered one renders exactly as before, and the annotation
    never mutates the verdict dict."""
    gate = {
        "gate": "dependency_scan",
        "status": "fail",
        "tool": "osv-scanner",
        "duration_ms": 900,
        "findings": ["GHSA-qx2v-qp2m-jg93 in postcss"],
        "details": {},
    }
    verdict = {"gates": [gate]}
    waiver = "↳ waived by active deviation seq=7 (approver: ann)"
    annotated = orchestrate.failure_panels(
        verdict, style.Styler(), waivers={"dependency_scan": waiver}
    )
    assert waiver in annotated
    bare = orchestrate.failure_panels(verdict, style.Styler())
    assert "waived" not in bare
    # read-only: the annotation never entered the verdict dict itself
    assert "waived" not in str(verdict)


def test_failed_format_gate_carries_the_configured_fix_cmd_in_its_details(tmp_path):
    """GATEPIPE-FR-003: a failing adapter gate whose manifest declares fix_cmd surfaces it in the
    gate's details so the panel can render the manual-fix hint (the engine never runs it)."""
    s, proj = _project(tmp_path, _ADAPTER_FAIL_FMT)
    v = run_gates(s, proj, tier="T", spec_path=proj / "spec.md", adapter_name="a")
    fmt = next(g for g in v.gates if g.gate == "format")
    assert fmt.status == "fail"
    assert fmt.details.get("fix_cmd") == "biome check --write ."
    ok = next(g for g in v.gates if g.gate == "lint")
    assert "fix_cmd" not in ok.details  # a passing gate never carries the hint


# --------------------------------------------------------------------------- D3. noise filters
def test_experimental_warning_and_blank_lines_are_suppressed_unless_verbose():
    """GATEPIPE-FR-004: Node.js ExperimentalWarning lines and blank lines are excluded from the
    rendered gate output by default and shown under verbose."""
    lines = [
        "(node:123) ExperimentalWarning: VM Modules is an experimental feature",
        "",
        "real error",
        "   ",
    ]
    assert orchestrate.meaningful_lines(lines) == ["real error"]
    verbose = orchestrate.meaningful_lines(lines, verbose=True)
    assert "real error" in verbose and len(verbose) == 4


def test_failure_panel_excludes_noise_by_default_and_keeps_it_verbose():
    """GATEPIPE-FR-004: a failed gate's panel drops ExperimentalWarning noise by default and keeps
    it when rendered verbose — the machine verdict is never filtered."""
    gate = {
        "gate": "tests",
        "status": "fail",
        "tool": "vitest",
        "duration_ms": 100,
        "findings": ["(node:1) ExperimentalWarning: foo", "1 test failed"],
        "details": {},
    }
    quiet = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    assert "ExperimentalWarning" not in quiet and "1 test failed" in quiet
    loud = orchestrate.failure_panels({"gates": [gate]}, style.Styler(), verbose=True)
    assert "ExperimentalWarning" in loud


def test_spec_integrity_skip_renders_the_info_glyph_not_the_failure_glyph():
    """GATEPIPE-FR-005: a skipped spec_integrity row renders with the `–` info glyph, never `✗` —
    a not-yet-approved spec reads as informational."""
    buf = io.StringIO()
    pipe = orchestrate.GatePipeline(buf, style.Styler())
    with pipe:
        pipe.gate_started("spec_integrity", "3pwr")
        pipe.gate_finished(
            GateResult(gate="spec_integrity", status="skip", findings=["no approval recorded"])
        )
    out = buf.getvalue()
    (row,) = out.splitlines()
    assert "– spec_integrity" in row and "skipped" in row
    assert "✗" not in row


# --------------------------------------------------------------------------- determinism
def test_plain_pipeline_and_panels_render_identically_for_identical_inputs():
    """GATEPIPE-NFR-001: the plain-mode rows and the failure panels are pure functions of the gate
    results — identical inputs render byte-identical output, with no network and no model."""
    result = GateResult(
        gate="lint", status="fail", tool="eslint", duration_ms=250, findings=["e1", "e2"]
    )

    def render() -> str:
        buf = io.StringIO()
        with orchestrate.GatePipeline(buf, style.Styler()) as pipe:
            pipe.gate_started("lint", "eslint")
            pipe.gate_finished(result)
        return buf.getvalue()

    assert render() == render()
    gate = {
        "gate": "lint",
        "status": "fail",
        "tool": "eslint",
        "duration_ms": 250,
        "findings": ["e1"],
        "details": {},
    }
    one = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    two = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    assert one == two and one != ""


# --------------------------------------------------------------------------- D4. remediation block
def _failed(gate: str, tool: str = "t", findings: list[str] | None = None, **details) -> dict:
    """A failed-gate dict in the Verdict.to_dict() shape the panel renderer consumes."""
    return {
        "gate": gate,
        "status": "fail",
        "tool": tool,
        "duration_ms": 100,
        "findings": findings if findings is not None else ["finding one"],
        "details": details,
    }


def test_passing_run_renders_no_remediation_block():
    """Covers: 3PWR-FR-034 — with no failed gate there is no panel, no guidance, no hand-back
    prompt, and no deviation hint: failure_panels and coder_handback are both empty."""
    verdict = {"spec_id": "030", "gates": [{"gate": "format", "status": "pass", "tool": "biome"}]}
    assert orchestrate.failure_panels(verdict, style.Styler()) == ""
    assert orchestrate.coder_handback(verdict) == ""


def test_format_and_lint_panels_keep_the_auto_fix_line_and_add_guidance():
    """Covers: 3PWR-FR-034 — format/lint panels still carry the `↳ auto-fix:` command and now end
    with the what-it-means/fix guidance."""
    gates = [
        _failed("format", "biome", fix_cmd="biome format --write ."),
        _failed("lint", "eslint", fix_cmd="eslint --fix ."),
    ]
    out = orchestrate.failure_panels({"gates": gates}, style.Styler())
    assert "↳ auto-fix: biome format --write ." in out
    assert "↳ auto-fix: eslint --fix ." in out
    assert "↳ what it means: the code's formatting drifts from the configured style" in out
    assert "↳ what it means: the linter found rule violations in the code" in out


def test_code_gates_show_guidance_handback_and_labelled_deviation_last_resort():
    """Covers: 3PWR-FR-034 — types/tests/gate_gaming/dependency_scan panels show honest code-fix
    guidance, the coder hand-back prompt follows the panels, and the pre-filled `3pwr deviation`
    command renders under the explicit last-resort label."""
    names = ["types", "tests", "gate_gaming", "dependency_scan"]
    out = orchestrate.failure_panels(
        {"spec_id": "030", "gates": [_failed(n) for n in names]}, style.Styler()
    )
    for name in names:
        assert f"3pwr deviation --gate {name} " in out
    assert '--approver <you> --note "<why>" [--until <date>]' in out
    assert out.count("↳ last resort — only if this is a deliberate, justified exception:") == 4
    assert "make the code satisfy its declared types" in out  # types: fix the code, not the check
    assert "never weaken a test" in out  # tests
    assert "restore the weakened check and make the code satisfy it" in out  # gate_gaming
    assert "hand back to your coding agent — copy-paste:" in out
    assert "re-dispatch: 3pwr run --resume --spec-id 030" in out


def test_dependency_scan_guidance_names_the_advisories_allowlist_and_deviation_honour():
    """Covers: 3PWR-FR-034 — the dependency_scan guidance names the auditable scan.yaml
    `advisories:` allowlist (id + reason, optional expiry, always reported) and truthfully states
    a recorded deviation is honoured by both `3pwr run` and `3pwr advance`."""
    out = orchestrate.failure_panels(
        {"gates": [_failed("dependency_scan", "osv-scanner")]}, style.Styler()
    )
    assert ".3powers/config/scan.yaml" in out and "advisories:" in out
    assert "id + reason" in out and "until" in out
    assert "every acceptance is reported" in out
    assert "3pwr run and 3pwr advance" in out
    gaming = orchestrate.failure_panels({"gates": [_failed("gate_gaming")]}, style.Styler())
    assert "3pwr run and 3pwr advance" in gaming


def test_unknown_gate_gets_the_generic_default_guidance():
    """Covers: 3PWR-FR-034 — a gate with no static guidance entry still renders the honest
    generic default, never a KeyError and never an empty block."""
    out = orchestrate.failure_panels({"gates": [_failed("a11y_scan", "axe")]}, style.Styler())
    assert "↳ what it means: this gate's check failed" in out
    assert "↳ fix: make the code satisfy the check; never weaken the check itself" in out
    assert "3pwr deviation --gate a11y_scan " in out


def test_finding_specific_remediation_hint_overrides_the_static_guidance():
    """Covers: 3PWR-FR-034 — a gate that supplies details["remediation"] (e.g. the fixed version a
    vulnerability scanner reports) sees that hint on the fix line instead of the static table."""
    gate = _failed("dependency_scan", "osv-scanner", remediation="upgrade postcss to 8.4.31")
    out = orchestrate.failure_panels({"gates": [gate]}, style.Styler())
    assert "↳ fix: upgrade postcss to 8.4.31" in out
    assert "↳ fix: upgrade the dependency to a fixed version" not in out
    assert "↳ what it means: a dependency carries a known vulnerability" in out  # meaning stays


def test_coder_handback_prompt_text_is_stable_and_oss_ready():
    """Covers: 3PWR-FR-034 — the coder hand-back prompt is a deterministic snapshot: it names the
    failed gates and findings, instructs an honest fix consistent with the implement-stage rules
    ("never weaken a gate"), and caps the findings per gate."""
    verdict = {
        "spec_id": "030",
        "gates": [
            _failed("types", "tsc", findings=["error TS2345 in a.ts"]),
            _failed("tests", "vitest", findings=[f"test {i} failed" for i in range(7)]),
        ],
    }
    expected = "\n".join(
        [
            "The deterministic gate suite rejected this change. Make the code satisfy the spec",
            "and every failed check below. Never weaken a gate: fix the code, not the check —",
            "keep every existing test, assertion, and check configuration intact.",
            "",
            "Failed gates:",
            "- types · tsc",
            "    error TS2345 in a.ts",
            "- tests · vitest",
            "    test 0 failed",
            "    test 1 failed",
            "    test 2 failed",
            "    test 3 failed",
            "    test 4 failed",
            "    … plus 2 more findings",
            "",
            "For each finding, correct the underlying code so it genuinely satisfies the",
            "check, keep the change minimal and traceable to the spec, then re-run the",
            "failed checks and report the honest result.",
        ]
    )
    assert orchestrate.coder_handback(verdict) == expected
    assert orchestrate.coder_handback(verdict) == orchestrate.coder_handback(verdict)


def test_coder_handback_never_instructs_weakening_a_check():
    """Covers: 3PWR-FR-034 — the hand-back prompt's own instruction text contains no
    suppress/delete/disable/skip instruction for any failed-gate mix; the honest-fix framing
    ("fix the code, not the check") is always present."""
    names = ["format", "lint", "types", "tests", "gate_gaming", "dependency_scan", "a11y_scan"]
    prompt = orchestrate.coder_handback(
        {"gates": [_failed(n, findings=["a finding"]) for n in names]}
    )
    for banned in ("suppress", "delete", "disable", "skip", "ignore", "silence"):
        assert banned not in prompt.lower()
    assert "fix the code, not the check" in prompt
    assert "Never weaken a gate" in prompt


def test_json_gate_run_payload_is_byte_stable_with_no_remediation_leak(tmp_path, capsys):
    """Covers: 3PWR-FR-034 3PWR-NFR-001 — the --json payload of a failing gate run is pure machine
    data, byte-identical under re-serialization, and carries none of the human remediation
    surface (guidance, hand-back prompt, or deviation hint)."""
    s, proj = _project(tmp_path, _ADAPTER)
    rc = main(
        [
            "--root",
            str(tmp_path),
            "gate",
            "run",
            "--path",
            str(proj),
            "--tier",
            "T",
            "--adapter",
            "a",
            "--no-ledger",
            "--spec",
            str(proj / "spec.md"),
            "--json",
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1  # lint fails
    payload = json.loads(out)
    assert out == json.dumps(payload, indent=2) + "\n"  # byte-stable: exactly the payload
    for phrase in (
        "what it means",
        "hand back to your coding agent",
        "last resort",
        "3pwr deviation",
        "re-dispatch",
    ):
        assert phrase not in out
    assert set(payload) == {"verdict", "ledger_seq"}  # no additive remediation key
    for g in payload["verdict"]["gates"]:
        assert "remediation" not in (g.get("details") or {})
