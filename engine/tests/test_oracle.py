"""Structural oracle independence — Phase A/B, ledger-anchored (3PWR-FR-020/021/022/062) — plus
the Tests Specification (plan 033 Track F): the validated, implementation-agnostic ``oracle.md``.

Pure predicates are pinned with hand-built ledger entries (ordering proven by ``seq``, never git
time); the CLI wiring — seal/record/verify and the High-risk ``advance`` gate — is driven end to
end through ``3pwr``. The peek/touch signals are asserted to be **advisory, never blocking**.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from threepowers import completion, oracle, prompts, scaffold
from threepowers.cli import main

ROLES = {"roles": {"coder": {"model_family": "openai"}, "oracle": {"model_family": "anthropic"}}}


# --------------------------------------------------------------------------- pure logic
def _write_spec(p: Path, spec_id: str = "ORAC", reqs: tuple[str, ...] = ("ORAC-FR-001",)) -> Path:
    lines = [f"**Spec ID**: {spec_id}", ""]
    for r in reqs:
        lines += [f"- **{r}**: The system shall handle {r}.", f"  - *Acceptance*: {r} holds."]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_bundle_hash_stable_across_reseals(tmp_path):
    """3PWR-FR-020: re-sealing an unchanged spec yields an identical hash (no timestamp inside)."""
    spec = _write_spec(tmp_path / "spec.md")
    sid, crit = oracle.extract_criteria(spec)
    assert sid == "ORAC" and set(crit) == {"ORAC-FR-001"}
    h1 = oracle.bundle_hash(sid, "spec.md", crit)
    assert h1 == oracle.bundle_hash(sid, "spec.md", crit) and h1.startswith("sha256:")
    changed = dict(crit, **{"ORAC-FR-001": "different text"})
    assert oracle.bundle_hash(sid, "spec.md", changed) != h1


def test_family_helpers():
    """3PWR-FR-022 building blocks."""
    assert oracle.family_of("anthropic/claude-x") == "anthropic"
    assert oracle.family_of("") == ""
    assert oracle.coder_family({"roles": {"coder": {"model_family": "openai"}}}) == "openai"
    assert oracle.coder_family({}) == ""


def test_scan_touched_impl_flags_source_not_tests():
    """3PWR-FR-021 (advisory): implementation files touched are flagged; tests/docs/oracle are not."""
    changed = {"src/thing.py", "tests/thing.test.py", "README.md", "src/oracle_x.py"}
    joined = " ".join(oracle.scan_touched_impl(changed, oracle_paths={"src/oracle_x.py"}))
    assert "src/thing.py" in joined
    assert "tests/thing.test.py" not in joined  # a test file is not "implementation"
    assert "README.md" not in joined  # not a source file
    assert "src/oracle_x.py" not in joined  # the declared oracle file itself


def test_scan_symbol_leakage_flags_internals():
    """3PWR-FR-021 (advisory): private symbols / internal imports absent from the spec are flagged."""
    texts = {
        "t_clean.py": "def test_orac(): assert do_thing('ORAC-FR-001')",
        "t_peek.py": "from .engine import _secret_helper\n_secret_helper()",
    }
    blob = " ".join(oracle.scan_symbol_leakage(texts, criteria_text="ORAC-FR-001 the system shall"))
    assert "t_peek.py" in blob
    assert "t_clean.py" not in blob


def _seal_entry(seq, spec_id, bhash, req_ids):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": spec_id,
        "payload": {"kind": "seal", "bundle_hash": bhash, "requirement_ids": req_ids},
    }


def _record_entry(seq, spec_id, bhash, family):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": spec_id,
        "payload": {
            "kind": "record",
            "bundle_hash": bhash,
            "model_family": family,
            "model": f"{family}/m",
            "test_paths": [],
            "advisory_findings": [],
        },
    }


def _verdict_entry(seq, spec_id):
    return {
        "seq": seq,
        "type": "verdict",
        "spec_id": spec_id,
        "payload": {"result": "pass", "tier": "High-risk"},
    }


def test_independence_missing_seal_and_record(tmp_path):
    ind = oracle.independence([], ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert not ind.ok
    assert any("no sealed oracle bundle" in r for r in ind.reasons)
    assert any("no oracle authoring record" in r for r in ind.reasons)


def test_independence_seal_binding(tmp_path):
    """3PWR-FR-020/021: a record bound to a stale bundle hash fails."""
    entries = [
        _seal_entry(0, "ORAC", "sha256:aaa", ["ORAC-FR-001"]),
        _record_entry(1, "ORAC", "sha256:bbb", "anthropic"),
    ]
    ind = oracle.independence(entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert any("stale/mismatched bundle" in r for r in ind.reasons)


def test_independence_diversity(tmp_path):
    """3PWR-FR-022: an oracle in the coder's family fails."""
    entries = [
        _seal_entry(0, "ORAC", "h", ["ORAC-FR-001"]),
        _record_entry(1, "ORAC", "h", "openai"),
    ]
    ind = oracle.independence(entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert any("equals the coder family" in r for r in ind.reasons)


def test_independence_ordering_by_ledger_seq(tmp_path):
    """3PWR-FR-062: Phase A must precede Phase B, proven by ledger seq (not git time)."""
    ok_order = [
        _seal_entry(0, "ORAC", "h", []),
        _record_entry(1, "ORAC", "h", "anthropic"),
        _verdict_entry(2, "ORAC"),
    ]
    ind_ok = oracle.independence(ok_order, ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert not any("Phase A must precede Phase B" in r for r in ind_ok.reasons)
    bad_order = [
        _verdict_entry(0, "ORAC"),
        _seal_entry(1, "ORAC", "h", []),
        _record_entry(2, "ORAC", "h", "anthropic"),
    ]
    ind_bad = oracle.independence(bad_order, ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert any("Phase A must precede Phase B" in r for r in ind_bad.reasons)


def test_independence_coverage_and_pass(tmp_path):
    """3PWR-FR-023: each sealed criterion needs an oracle test; a bound, diverse, ordered, covered
    record with no implementation verdict yet is independent (PASS)."""
    otest = tmp_path / "oracle_orac.py"
    otest.write_text("# oracle for ORAC-FR-001\n", encoding="utf-8")
    entries = [
        _seal_entry(0, "ORAC", "h", ["ORAC-FR-001"]),
        _record_entry(1, "ORAC", "h", "anthropic"),
    ]
    ind_missing = oracle.independence(entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=[])
    assert any("without an oracle test" in r for r in ind_missing.reasons)
    ind_ok = oracle.independence(entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=[otest])
    assert ind_ok.ok, ind_ok.reasons
    assert ind_ok.covered == ["ORAC-FR-001"]


# --------------------------------------------------------------------------- CLI end-to-end
RISK_TIERS = """
tiers:
  Standard:  { diff_coverage: 80, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
  High-risk: { diff_coverage: 95, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
"""
ROLES_YAML = """
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
SPEC = "**Spec ID**: ORAC\n\n- **ORAC-FR-001**: The system shall work.\n"


@pytest.fixture()
def project(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    tp = root / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "fake").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(RISK_TIERS, encoding="utf-8")
    (tp / "config" / "roles.yaml").write_text(ROLES_YAML, encoding="utf-8")
    (tp / "adapters" / "fake" / "adapter.yaml").write_text(ADAPTER, encoding="utf-8")

    proj = root / "proj"
    (proj / "tests").mkdir(parents=True)
    (proj / "detect.txt").write_text("x", encoding="utf-8")
    (proj / "spec.md").write_text(SPEC, encoding="utf-8")
    (proj / "tests" / "orac.test.py").write_text("# covers ORAC-FR-001\n", encoding="utf-8")
    (proj / "coverage").mkdir()
    (proj / "coverage" / "lcov.info").write_text(
        "SF:src/x.py\nDA:1,1\nDA:2,1\nend_of_record\n", encoding="utf-8"
    )
    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    return root, proj


def _seal(root, proj):
    return main(
        [
            "--root",
            str(root),
            "oracle",
            "seal",
            "--spec",
            str(proj / "spec.md"),
            "--spec-id",
            "ORAC",
        ]
    )


def _record(root, proj, model="anthropic/claude", tests=None):
    tests = tests or [str(proj / "tests" / "orac.test.py")]
    return main(
        [
            "--root",
            str(root),
            "oracle",
            "record",
            "--spec-id",
            "ORAC",
            "--model",
            model,
            "--tests",
            *tests,
        ]
    )


def _verify(root):
    return main(["--root", str(root), "oracle", "verify", "--spec-id", "ORAC"])


def _gate(root, proj, tier="High-risk"):
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


def _signoff(root):
    return main(["--root", str(root), "signoff", "--approver", "carlo", "--spec-id", "ORAC"])


def _advance(root):
    return main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "ORAC"])


def test_seal_record_verify_flow(project):
    """3PWR-FR-020/062: seal → record → verify PASS (Phase A, before any implementation verdict)."""
    root, proj = project
    assert _seal(root, proj) == 0
    assert (root / ".3powers" / "oracle" / "ORAC" / "sealed.json").exists()
    assert _record(root, proj) == 0
    assert _verify(root) == 0


def test_record_refuses_same_family(project):
    """3PWR-FR-022: the engine refuses to record an oracle in the coder's model family."""
    root, proj = project
    assert _seal(root, proj) == 0
    assert _record(root, proj, model="openai/gpt") == 1  # same as coder → refused
    assert _verify(root) == 1  # no valid record → not independent


def test_high_risk_advance_requires_oracle(project):
    """3PWR-FR-020/062: a High-risk advance blocks without an independent, correctly-ordered oracle."""
    root, proj = project
    assert _gate(root, proj) == 0  # green High-risk verdict (Phase B)
    assert _signoff(root) == 0
    assert _advance(root) == 1  # refused: no sealed oracle / record
    # Provide the oracle AFTER the implementation verdict → ordering violation still blocks.
    assert _seal(root, proj) == 0
    assert _record(root, proj) == 0
    assert _advance(root) == 1  # refused: oracle authored after the impl verdict (FR-062)


def test_high_risk_advance_passes_when_oracle_precedes(project):
    """3PWR-FR-062: with Phase A recorded BEFORE the implementation verdict, advance proceeds."""
    root, proj = project
    assert _seal(root, proj) == 0  # #0
    assert _record(root, proj) == 0  # #1 Phase A
    assert _gate(root, proj) == 0  # #2 verdict, Phase B
    assert _signoff(root) == 0  # #3
    assert _advance(root) == 0  # proceeds: independent oracle, ordered
    assert main(["--root", str(root), "verify"]) == 0


def test_standard_advance_unaffected_by_oracle(project):
    """A Standard-tier advance does not require the oracle (High-risk-only enforcement, spec §4)."""
    root, proj = project
    assert _gate(root, proj, tier="Standard") == 0
    assert _signoff(root) == 0
    assert _advance(root) == 0  # no oracle needed at Standard


def test_advisory_touch_is_flagged_but_not_blocking(project, capsys):
    """User's rule (3PWR-FR-021): touching/peeking is flagged + commented, never a blocker."""
    root, proj = project
    peek = proj / "tests" / "peek.test.py"
    peek.write_text(
        "# covers ORAC-FR-001\nfrom .impl import _secret\n_secret()\n", encoding="utf-8"
    )
    assert _seal(root, proj) == 0  # #0
    assert _record(root, proj, tests=[str(peek)]) == 0  # #1 — advisory recorded, still succeeds
    assert _gate(root, proj) == 0  # #2
    assert _signoff(root) == 0  # #3
    assert _advance(root) == 0  # #4 — proceeds DESPITE the advisory finding
    capsys.readouterr()  # drain
    assert main(["--root", str(root), "status", "--spec-id", "ORAC"]) == 0
    assert "advisory (not a blocker)" in capsys.readouterr().out


# --------------------------------------------------------------------------- Track F: oracle.md (plan 033)
ORACLE_MD_OK = """# Tests Specification — 030-demo

## Coverage Summary

| Requirements in spec | Covered here | Open questions |
|---|---|---|
| 2 | 2 | 0 |

## Acceptance Tests

### Test for DEMO-FR-001

- **Source AC:** spec §DEMO-FR-001
- **Type:** acceptance
- **Criterion (Given / When / Then):** Given a valid input / When submitted / Then it is accepted
- **Notes for executor:** must not assume any storage layout or entry-point naming.

### Test for DEMO-NFR-001

- **Source AC:** spec §DEMO-NFR-001
- **Type:** performance
- **Metric / Threshold / Boundary:** p95 latency ≤ 200 ms at 100 requests per second
- **Measurement protocol:** measured over 5 minutes against the reference dataset.
"""


def test_validate_oracle_spec_passes_a_clean_specification():
    """Track F (plan 033): a per-requirement, path-free Tests Specification — Given/When/Then per
    criterion, metric/protocol for the NFR — yields no findings."""
    assert completion.validate_oracle_spec(ORACLE_MD_OK, ["DEMO-FR-001", "DEMO-NFR-001"]) == []


def test_validate_oracle_spec_flags_missing_id_and_leaks():
    """Track F (plan 033): a missing requirement id, a leaked file path, and a named test
    framework are each flagged — the Tests Specification must stay implementation-agnostic."""
    text = ORACLE_MD_OK + "\nSee src/service.py and reuse the pytest fixtures in tests/unit/.\n"
    findings = completion.validate_oracle_spec(text, ["DEMO-FR-001", "DEMO-NFR-001", "DEMO-FR-002"])
    assert any("does not name requirement DEMO-FR-002" in f for f in findings)
    assert any("leaks a file path" in f and "src/service.py" in f for f in findings)
    assert any("names a test framework: pytest" in f for f in findings)


def test_absent_oracle_md_yields_the_visible_stub(tmp_path):
    """Track F (plan 033): when the oracle agent authored no oracle.md, the engine writes a
    structural stub from the spec's criteria — one section per requirement id, marked
    "not authored", keyed by the feature-folder id, and path-free."""
    f = tmp_path / "specs-src" / "030-demo"
    f.mkdir(parents=True)
    (f / "spec.md").write_text(
        "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: shall work.\n- **DEMO-NFR-001**: ≤ 200 ms.\n",
        encoding="utf-8",
    )
    rel = completion.write_record(
        tmp_path, f, "oracle", spec_id="030", linked=["tests/oracle/030-demo/test_x.py"]
    )
    assert rel == "specs-src/030-demo/oracle.md"
    text = (f / "oracle.md").read_text(encoding="utf-8")
    assert completion.ORACLE_STUB_MARKER in text  # visibly a stub, never silently passed
    assert "Tests Specification — 030-demo" in text  # keyed by the folder id
    for rid in ("DEMO-FR-001", "DEMO-NFR-001"):
        assert f"### Test for {rid} — not authored" in text
    assert "tests/oracle/030-demo/test_x.py" not in text  # path-free (the ledger holds the paths)
    # byte-deterministic given the same inputs
    _, criteria = oracle.extract_criteria(f / "spec.md")
    assert completion.render_oracle_stub("030-demo", criteria) == text


def test_authored_oracle_md_is_validated_and_left_in_place(tmp_path):
    """Track F (plan 033): an agent-authored oracle.md is validated — a leaked path or missing id
    is flagged through on_finding — and left in place byte-for-byte, never overwritten."""
    f = tmp_path / "specs-src" / "030-demo"
    f.mkdir(parents=True)
    (f / "spec.md").write_text(
        "**Spec ID**: DEMO\n\n- **DEMO-FR-001**: shall work.\n- **DEMO-FR-002**: shall also.\n",
        encoding="utf-8",
    )
    authored = ORACLE_MD_OK + "\nImplemented in src/service.py.\n"  # covers FR-001, leaks a path
    (f / "oracle.md").write_text(authored, encoding="utf-8")
    findings: list[str] = []
    rel = completion.write_record(
        tmp_path, f, "oracle", spec_id="030", linked=[], on_finding=findings.append
    )
    assert rel == "specs-src/030-demo/oracle.md"
    assert (f / "oracle.md").read_text(encoding="utf-8") == authored  # left in place
    assert any("does not name requirement DEMO-FR-002" in x for x in findings)
    assert any("leaks a file path" in x and "src/service.py" in x for x in findings)


def _oracle_template_texts() -> list[str]:
    """Both shipped oracle.agent.md copies — the engine scaffold plus, when present, this repo's
    own .3powers copy (absent in a packaged engine)."""
    texts = [
        (scaffold.SCAFFOLD_DIR / "templates" / "agents" / "oracle.agent.md").read_text(
            encoding="utf-8"
        )
    ]
    repo_copy = Path(__file__).resolve().parents[2] / ".3powers" / "templates" / "agents"
    if (repo_copy / "oracle.agent.md").is_file():
        texts.append((repo_copy / "oracle.agent.md").read_text(encoding="utf-8"))
    return texts


def test_oracle_template_carries_the_tests_specification_instruction():
    """Track F (plan 033): the merged oracle.agent.md instructs — in order — loading the sealed
    bundle, the hard stop on unmeasurable criteria ("Open Questions for the Legislature", routed
    to clarify, no invented thresholds), authoring the implementation-agnostic oracle.md (type
    marker, property invariant, NFR metric/threshold/protocol, executor notes, mutation flag,
    Coverage Summary), then the runnable tests at the engine-given $ORACLE_DESTINATION (under
    tests/oracle/, keyed by the run's feature-folder id); thresholds come
    from the constitution + risk-tiers config; no substrate residue survives."""
    for text in _oracle_template_texts():
        for token in (
            "Open Questions for the Legislature",
            "STOP",
            "clarify",
            "Invent no thresholds",
            "acceptance | property | performance",
            "Property invariant",
            "Metric / Threshold / Boundary",
            "Measurement protocol",
            "Notes for executor",
            "High-risk mutation flag",
            "Coverage Summary",
            "$ORACLE_DESTINATION",
            "tests/oracle/",
            ".3powers/memory/constitution.md",
            ".3powers/config/risk-tiers.yaml",
        ):
            assert token in text, f"oracle.agent.md lost the merged instruction {token!r}"
        for residue in (".specify", "$ARGUMENTS", "tests.md", "<spec-id>", "<NNN>-<slug>"):
            assert residue not in text, f"oracle.agent.md carries residue {residue!r}"


def test_oracle_isolation_rules_are_preserved():
    """Track F (plan 033): the isolation rules survive the merge — the template and the built-in
    oracle instruction both author only from the sealed spec and forbid reading the
    implementation/plan/tasks/contracts."""
    for text in _oracle_template_texts():
        assert "MUST NOT read the implementation" in text
        assert "sealed spec" in text
    body = prompts.resolve_body("oracle", None)
    assert "MUST NOT read the implementation" in body
    assert "sealed spec" in body
    assert "oracle.md" in body  # the Tests Specification is authored first, from the spec alone
