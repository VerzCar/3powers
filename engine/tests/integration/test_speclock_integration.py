"""Spec-integrity (spec-lock) through the CLI — integration layer (SLOCK).

Drives `3pwr signoff / gate run / advance / deviation / verify / spec diff` against a
temporary project, proving the pillars end to end: seal at sign-off (SLOCK-FR-001),
fail-fast gate (SLOCK-FR-003/004), advance enforcement + deviation relief
(SLOCK-FR-005), supersede (SLOCK-FR-006), read-only diff (SLOCK-FR-007), and
tamper-evidence via the existing signed ledger (SLOCK-NFR-002).
"""

from __future__ import annotations

import json
import subprocess

import pytest

from threepowers.cli import main

RISK_TIERS = """
tiers:
  Standard:
    diff_coverage: 80
    gates: [format, lint, types, spec_integrity, tests, diff_coverage, spec_conformance]
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
    root = tmp_path / "repo"
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "fake").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK_TIERS, encoding="utf-8")
    (tp / "config" / "roles.yaml").write_text(ROLES, encoding="utf-8")
    (tp / "adapters" / "fake" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")

    proj = root / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "detect.txt").write_text("x", encoding="utf-8")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "demo.test.py").write_text("# covers DEMO-FR-001\n", encoding="utf-8")
    (proj / "coverage").mkdir()
    (proj / "coverage" / "lcov.info").write_text(
        "SF:src/x.py\nDA:1,1\nDA:2,1\nend_of_record\n", encoding="utf-8"
    )

    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root, proj


def _gate_run(root, proj):
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
            "Standard",
        ]
    )


def _spec_signoff(root, proj):
    return main(
        [
            "--root",
            str(root),
            "signoff",
            "--approver",
            "carlo",
            "--stage",
            "spec",
            "--spec-id",
            "DEMO",
            "--spec",
            str(proj / "spec.md"),
        ]
    )


def _latest_verdict(root):
    return json.loads((root / ".3powers" / "verdicts" / "latest.json").read_text())


def _ledger_entries(root):
    text = (root / ".3powers" / "ledger.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_spec_signoff_seals_hash_and_review_does_not(project):
    """SLOCK-FR-001: a Spec-stage sign-off carries spec_hash + spec_path; review carries neither."""
    root, proj = project
    assert _spec_signoff(root, proj) == 0
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
    signoffs = [e for e in _ledger_entries(root) if e["type"] == "signoff"]
    spec_so, review_so = signoffs[0], signoffs[1]
    assert spec_so["payload"]["spec_hash"].startswith("sha256:")
    assert spec_so["payload"]["spec_path"] == "proj/spec.md"
    assert "spec_hash" not in review_so["payload"]
    assert "spec_path" not in review_so["payload"]


def test_gate_skips_before_approval_and_blocks_mutation_after(project):
    """SLOCK-FR-003/004 + SC-001/005: skip pre-approval; a mutated spec fails before tests."""
    root, proj = project
    assert _gate_run(root, proj) == 0  # never signed off → spec_integrity skips (SC-005)
    v = _latest_verdict(root)
    gate = next(g for g in v["gates"] if g["gate"] == "spec_integrity")
    assert gate["status"] == "skip"

    assert _spec_signoff(root, proj) == 0
    assert _gate_run(root, proj) == 0  # unmodified → pass
    v = _latest_verdict(root)
    assert next(g for g in v["gates"] if g["gate"] == "spec_integrity")["status"] == "pass"

    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-666**: injected.\n", encoding="utf-8")
    assert _gate_run(root, proj) == 1  # SC-001: fails at spec_integrity
    v = _latest_verdict(root)
    names = [g["gate"] for g in v["gates"]]
    assert names.index("spec_integrity") < names.index("tests")  # SLOCK-FR-004: before any test
    gate = next(g for g in v["gates"] if g["gate"] == "spec_integrity")
    assert gate["status"] == "fail"
    fail = next(f for f in v["failures"] if f["class"] == "spec_modified")  # SLOCK-FR-003
    assert fail["approving_seq"] == gate["details"]["approval_seq"]


def test_advance_refuses_mutation_unless_deviated_and_reblocks_on_revoke(project, capsys):
    """SLOCK-FR-005 + SC-002: advance refuses spec_modified; a signed spec_integrity
    deviation turns it into a warned pass; revoking re-blocks."""
    root, proj = project
    assert _gate_run(root, proj) == 0  # verdict #0 (green; pre-approval skip)
    assert _spec_signoff(root, proj) == 0  # sign-off #1 seals the hash
    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-666**: injected.\n", encoding="utf-8")

    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "DEMO"]) == 1
    assert "spec_modified" in capsys.readouterr().out

    assert (
        main(
            [
                "--root",
                str(root),
                "deviation",
                "--gate",
                "spec_integrity",
                "--approver",
                "carlo",
                "--note",
                "amendment under review",
                "--spec-id",
                "DEMO",
            ]
        )
        == 0
    )  # entry #2
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "DEMO"]) == 0
    advance = [e for e in _ledger_entries(root) if e["type"] == "stage_advance"][-1]
    assert advance["payload"]["spec_integrity_deviated"] is True
    assert 2 in advance["payload"]["deviations_applied"]

    assert main(["--root", str(root), "deviation", "--revoke", "2"]) == 0
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "DEMO"]) == 1


def test_fresh_spec_signoff_supersedes_and_everything_passes_again(project):
    """SLOCK-FR-006: re-approving the amended spec makes gate run and advance green again."""
    root, proj = project
    assert _spec_signoff(root, proj) == 0
    (proj / "spec.md").write_text(
        SPEC + "- **DEMO-FR-002**: amended, and tested.\n", encoding="utf-8"
    )
    (proj / "tests" / "demo.test.py").write_text(
        "# covers DEMO-FR-001\n# covers DEMO-FR-002\n", encoding="utf-8"
    )
    assert _spec_signoff(root, proj) == 0  # fresh approval over the amendment
    assert _gate_run(root, proj) == 0  # passes against the NEW hash
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
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "DEMO"]) == 0


def test_verify_catches_tampering_with_the_recorded_hash(project):
    """SLOCK-NFR-002 + SC-003: altering spec_hash in the signed entry breaks its signature."""
    root, proj = project
    assert _spec_signoff(root, proj) == 0
    assert main(["--root", str(root), "verify"]) == 0

    ledger_path = root / ".3powers" / "ledger.jsonl"
    entries = _ledger_entries(root)
    for e in entries:
        if e["type"] == "signoff":
            e["payload"]["spec_hash"] = "sha256:" + "f" * 64
    ledger_path.write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n", encoding="utf-8"
    )
    assert main(["--root", str(root), "verify"]) == 1  # no new verification code needed


def test_spec_diff_is_read_only_and_reports_match_then_mismatch(project):
    """SLOCK-FR-007 + SC-004: exit 0 on match, non-zero + report on mismatch; ledger untouched."""
    root, proj = project
    ledger_path = root / ".3powers" / "ledger.jsonl"

    assert main(["--root", str(root), "spec", "diff", "--spec-id", "DEMO"]) == 0  # no approval yet
    assert not ledger_path.exists() or "signoff" not in ledger_path.read_text(encoding="utf-8")

    assert _spec_signoff(root, proj) == 0
    before = ledger_path.read_bytes()
    assert main(["--root", str(root), "spec", "diff", "--spec-id", "DEMO"]) == 0  # match
    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-666**: injected.\n", encoding="utf-8")
    assert main(["--root", str(root), "spec", "diff", "--spec-id", "DEMO"]) == 1  # mismatch
    assert ledger_path.read_bytes() == before  # never writes to the ledger


def test_spec_diff_shows_textual_diff_when_signoff_commit_is_known(project, capsys):
    """SLOCK-FR-007: with the sign-off commit in git, the change is shown as a unified diff."""
    root, proj = project

    def git(*args):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=root,
            check=True,
            capture_output=True,
        )

    git("init", "-q")
    git("add", "-A")
    git("commit", "-q", "-m", "approved spec")

    assert _spec_signoff(root, proj) == 0  # records the sign-off commit
    (proj / "spec.md").write_text(SPEC + "- **DEMO-FR-666**: injected.\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["--root", str(root), "spec", "diff", "--spec-id", "DEMO", "--json"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "mismatch"
    assert "+- **DEMO-FR-666**: injected." in out["diff"]  # SC-004: surfaces the change
