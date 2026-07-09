"""End-to-end CLI tests — drive `3pwr` through a temporary 3Powers project.

These exercise the gate suite ordering (3PWR-FR-026), the normalized verdict
(3PWR-FR-033), local enforcement (3PWR-FR-041/042), and model diversity
(3PWR-FR-022) the same way a real run does.
"""

from __future__ import annotations

import json

import pytest

from threepowers.cli import main

RISK_TIERS = """
tiers:
  Cosmetic: { diff_coverage: 0, gates: [format, lint, types] }
  Standard: { diff_coverage: 80, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
"""

ROLES = """
roles:
  coder: { model_family: openai }
  oracle: { model_family: anthropic }
"""

ADAPTER = """
language: fake
detect: ["detect.txt"]
test_roots: ["tests"]
gates:
  format: { check_cmd: "python -c pass", parser: fake }
  lint:   { cmd: "python -c pass", parser: fake }
  types:  { cmd: "python -c pass", parser: fake }
  tests:  { cmd: "python -c pass", parser: fake, coverage_path: "coverage/lcov.info" }
"""

SPEC = "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: The system shall work.\n"


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "repo"  # the key lives OUTSIDE this root (HARDN-FR-002)
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "fake").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK_TIERS, encoding="utf-8")
    (tp / "config" / "roles.yaml").write_text(ROLES, encoding="utf-8")
    (tp / "adapters" / "fake" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")

    proj = root / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "src").mkdir()
    (proj / "detect.txt").write_text("x", encoding="utf-8")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "demo.test.py").write_text("# covers DEMO-FR-001\n", encoding="utf-8")
    # Pre-seed a coverage report (a non-git tmp dir => diff falls back to all measured lines).
    (proj / "coverage").mkdir()
    (proj / "coverage" / "lcov.info").write_text(
        "SF:src/x.py\nDA:1,1\nDA:2,1\nend_of_record\n", encoding="utf-8"
    )

    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root, proj


def _gate_run(root, proj, tier="Standard"):
    return main(
        [
            "--root",
            str(root),
            "gate",
            "run",
            "--path",
            str(proj),
            "--adapter",
            "fake",
            "--spec",
            str(proj / "spec.md"),
            "--tier",
            tier,
        ]
    )


def test_gate_run_green_and_ordered(project, capsys):
    root, proj = project
    assert _gate_run(root, proj) == 0
    verdict = json.loads((root / ".3powers" / "verdicts" / "latest.json").read_text())
    assert verdict["result"] == "pass"
    order = ["format", "lint", "types", "tests", "diff_coverage", "mutation", "spec_conformance"]
    positions = [order.index(g["gate"]) for g in verdict["gates"]]
    assert positions == sorted(positions)  # cheapest-first (3PWR-FR-026)


def test_full_enforcement_flow(project):
    """gate → refuse → sign-off → advance → verify (3PWR-FR-041/042)."""
    root, proj = project
    assert _gate_run(root, proj) == 0
    assert main(["--root", str(root), "advance", "--stage", "ship"]) == 1  # no sign-off yet
    assert (
        main(
            [
                "--root",
                str(root),
                "signoff",
                "--approver",
                "carlo",
                "--stage",
                "review",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )
    assert main(["--root", str(root), "advance", "--stage", "ship"]) == 0
    assert main(["--root", str(root), "verify"]) == 0


def _signoff(root, spec="DEMO"):
    return main(["--root", str(root), "signoff", "--approver", "carlo", "--spec-id", spec])


def _advance(root, spec="DEMO"):
    return main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", spec])


def _make_conformance_red(proj):
    # add an untested requirement → spec-conformance fails → verdict red on that gate
    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-002**: shall also work.\n", encoding="utf-8")


def test_deviation_lets_advance_pass_a_red_gate(project):
    """3PWR-FR-057: a recorded, signed deviation lets advance accept a named red gate."""
    root, proj = project
    _make_conformance_red(proj)
    assert _gate_run(root, proj) == 1  # red on spec_conformance
    assert _signoff(root) == 0
    assert _advance(root) == 1  # refused: red on un-deviated spec_conformance
    assert (
        main(
            [
                "--root",
                str(root),
                "deviation",
                "--gate",
                "spec_conformance",
                "--approver",
                "carlo",
                "--note",
                "DEMO-FR-002 tracked as follow-up",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )
    assert _advance(root) == 0  # proceeds under the deviation
    assert main(["--root", str(root), "verify"]) == 0  # ledger still verifies


def test_uncovered_red_gate_still_blocks(project):
    """3PWR-FR-057: a deviation for a different gate does not unblock the failing one."""
    root, proj = project
    _make_conformance_red(proj)
    assert _gate_run(root, proj) == 1
    assert _signoff(root) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "deviation",
                "--gate",
                "lint",
                "--approver",
                "carlo",
                "--note",
                "n/a",
            ]
        )
        == 0
    )
    assert _advance(root) == 1  # still red on un-deviated spec_conformance


def test_deviation_revoke_reblocks_advance(project):
    """3PWR-FR-057: revoking the deviation (the way back) re-blocks the advance."""
    root, proj = project
    _make_conformance_red(proj)
    assert _gate_run(root, proj) == 1  # #0
    assert _signoff(root) == 0  # #1
    assert (
        main(
            [
                "--root",
                str(root),
                "deviation",
                "--gate",
                "spec_conformance",
                "--approver",
                "carlo",
                "--note",
                "tracked follow-up",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )  # #2
    assert _advance(root) == 0  # #3 — proceeds under deviation
    assert main(["--root", str(root), "deviation", "--revoke", "2"]) == 0  # #4 — way back
    assert _advance(root) == 1  # re-blocked


def test_deviation_without_a_reason_is_rejected(project, capsys):
    """3PWR-FR-057: a deviation must state a reason — an empty/whitespace --note is refused with
    an actionable message; a non-empty one records; a revoke needs no note."""
    root, _proj = project
    base = ["--root", str(root), "deviation", "--gate", "lint", "--approver", "carlo"]
    assert main(base) == 2  # no --note at all
    assert 'a deviation must state a reason — pass --note "<why>"' in capsys.readouterr().err
    assert main([*base, "--note", "   "]) == 2  # whitespace-only
    assert main([*base, "--note", "tracked follow-up"]) == 0  # non-empty records
    assert main(["--root", str(root), "deviation", "--revoke", "0"]) == 0  # revoke unaffected


def test_gate_run_annotates_a_waived_red_gate(project, capsys):
    """3PWR-FR-057: a red gate covered by an active deviation is annotated in the gate run output;
    the recorded verdict stays honestly red and the --json payload never carries the annotation."""
    root, proj = project
    _make_conformance_red(proj)
    assert (
        main(
            [
                "--root",
                str(root),
                "deviation",
                "--gate",
                "spec_conformance",
                "--approver",
                "carlo",
                "--note",
                "tracked follow-up",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert _gate_run(root, proj) == 1  # still red — deviations never touch the verdict
    out = capsys.readouterr().out
    assert "waived by active deviation seq=0 (approver: carlo)" in out
    verdict = json.loads((root / ".3powers" / "verdicts" / "latest.json").read_text())
    assert verdict["result"] == "fail"
    assert "waived" not in json.dumps(verdict)  # the recorded verdict is untouched
    # --json: pure machine payload — the annotation is human rendering only
    rc = main(
        [
            "--root",
            str(root),
            "gate",
            "run",
            "--path",
            str(proj),
            "--adapter",
            "fake",
            "--spec",
            str(proj / "spec.md"),
            "--tier",
            "Standard",
            "--json",
        ]
    )
    assert rc == 1
    json_out = capsys.readouterr().out
    payload = json.loads(json_out)
    assert json_out == json.dumps(payload, indent=2) + "\n"  # nothing but the payload
    assert "waived" not in json_out


def test_emergency_overdue_cleanup_blocks_advance(project):
    """3PWR-FR-056: an emergency past its one-day cleanup blocks advance until revoked."""
    root, proj = project
    assert _gate_run(root, proj) == 0  # green verdict #0
    assert _signoff(root) == 0  # #1
    assert (
        main(
            [
                "--root",
                str(root),
                "emergency",
                "--approver",
                "carlo",
                "--note",
                "prod down",
                "--cleanup-hours",
                "0",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )  # #2 — cleanup_due = now → immediately overdue
    assert _advance(root) == 1  # blocked: emergency cleanup overdue
    assert main(["--root", str(root), "deviation", "--revoke", "2"]) == 0  # #3 — cleaned up
    assert _advance(root) == 0  # now proceeds
    assert main(["--root", str(root), "status"]) == 0


def test_tamper_makes_verify_fail(project):
    """3PWR-FR-040: a mutated ledger entry fails verification."""
    root, proj = project
    assert _gate_run(root, proj) == 0
    ledger = root / ".3powers" / "ledger.jsonl"
    ledger.write_text(ledger.read_text().replace('"pass"', '"fail"'))
    assert main(["--root", str(root), "verify"]) == 1


def test_roles_check_same_family_refused(project):
    """3PWR-FR-022: same model family is a violation."""
    root, _ = project
    assert main(["--root", str(root), "roles-check", "--role-a", "coder", "--role-b", "coder"]) == 1
    assert (
        main(["--root", str(root), "roles-check", "--role-a", "oracle", "--role-b", "coder"]) == 0
    )


def test_conformance_flags_untested(project):
    """3PWR-FR-030/034: an untested requirement fails conformance."""
    root, proj = project
    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-002**: shall also work.\n", encoding="utf-8")
    rc = main(
        [
            "--root",
            str(root),
            "conformance",
            "--spec",
            str(proj / "spec.md"),
            "--tests",
            str(proj / "tests"),
        ]
    )
    assert rc == 1


def test_ledger_show_and_json(project, capsys):
    root, proj = project
    assert _gate_run(root, proj) == 0
    assert main(["--root", str(root), "ledger", "show"]) == 0
    out = capsys.readouterr().out
    assert "verdict" in out


def test_lifecycle_status_revert_abort(project):
    """Lifecycle status (3PWR-FR-011/019) and reversal (3PWR-FR-070) via the CLI."""
    root, proj = project
    assert _gate_run(root, proj) == 0  # verdict #0 (spec DEMO)
    assert (
        main(
            [
                "--root",
                str(root),
                "signoff",
                "--approver",
                "x",
                "--stage",
                "review",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )  # #1
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "DEMO"]) == 0  # #2
    assert main(["--root", str(root), "status", "--spec-id", "DEMO"]) == 0
    assert main(["--root", str(root), "revert", "--to", "0", "--reason", "rollback"]) == 0  # #3
    assert main(["--root", str(root), "abort", "--spec-id", "DEMO", "--reason", "done"]) == 0  # #4
    assert main(["--root", str(root), "verify"]) == 0  # chain still intact


def test_coverage_check_cli(project):
    """Two-way requirement<->task coverage via the CLI (3PWR-FR-015)."""
    root, proj = project
    tasks = proj / "tasks.md"
    tasks.write_text("- [ ] T001 [DEMO-FR-001] implement\n", encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(root),
                "coverage-check",
                "--spec",
                str(proj / "spec.md"),
                "--tasks",
                str(tasks),
            ]
        )
        == 0
    )
    tasks.write_text("- [ ] T001 orphan task with no requirement\n", encoding="utf-8")
    assert (
        main(
            [
                "--root",
                str(root),
                "coverage-check",
                "--spec",
                str(proj / "spec.md"),
                "--tasks",
                str(tasks),
            ]
        )
        == 1
    )


def test_scope_check_cli(project):
    """Task req-id discipline via the CLI (3PWR-FR-016)."""
    root, proj = project
    tasks = proj / "tasks.md"
    tasks.write_text("- [ ] T001 [DEMO-FR-001] do (files: src/x.ts)\n", encoding="utf-8")
    assert main(["--root", str(root), "scope-check", "--tasks", str(tasks)]) == 0
    tasks.write_text("- [ ] T001 orphan (files: src/x.ts)\n", encoding="utf-8")
    assert main(["--root", str(root), "scope-check", "--tasks", str(tasks)]) == 1


def test_provenance_and_deploy_gate(project):
    """Signed provenance (3PWR-FR-066/068) verified at the deploy gate (3PWR-FR-067)."""
    root, proj = project
    artifact = root / "artifact.bin"
    artifact.write_bytes(b"shipme-v1")
    assert (
        main(["--root", str(root), "provenance", "--artifact", str(artifact), "--path", str(proj)])
        == 0
    )
    assert main(["--root", str(root), "deploy-gate", "--artifact", str(artifact)]) == 0
    artifact.write_bytes(b"tampered")  # supply-chain tamper
    assert main(["--root", str(root), "deploy-gate", "--artifact", str(artifact)]) == 1


def test_residual_recorded(project):
    """A residual review is recorded as a signed ledger entry (3PWR-FR-036)."""
    root, _ = project
    assert (
        main(
            [
                "--root",
                str(root),
                "residual",
                "--reviewer",
                "anthropic",
                "--spec-id",
                "DEMO",
                "--note",
                "looks good",
            ]
        )
        == 0
    )
    assert main(["--root", str(root), "verify"]) == 0


def test_eval_cli(project):
    """Prompt/constitution eval set blocks on regression (3PWR-FR-050)."""
    root, _ = project
    (root / "doc.md").write_text("we keep the different model family rule\n", encoding="utf-8")
    cases = root / "cases.yaml"
    cases.write_text(
        'cases:\n  - name: c\n    file: doc.md\n    must_contain: ["different model family"]\n',
        encoding="utf-8",
    )
    assert main(["--root", str(root), "eval", "--cases", str(cases)]) == 0
    (root / "doc.md").write_text("the rule was quietly weakened\n", encoding="utf-8")  # regression
    assert main(["--root", str(root), "eval", "--cases", str(cases)]) == 1
