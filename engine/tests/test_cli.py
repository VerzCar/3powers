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
    root = tmp_path
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

    keyfile = root / "signer.key"
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
