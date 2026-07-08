"""Spec-integrity (spec-lock) — unit layer (SLOCK).

Every test names the SLOCK requirement it exercises (3PWR-FR-059); the integration and
e2e layers live under ``tests/integration`` / ``tests/e2e`` (3PWR-FR-064).
"""

from __future__ import annotations

from threepowers import canonical, keys, speclock
from threepowers.ledger import Ledger
from threepowers.verdict import GATE_ORDER, STATUS_FAIL, STATUS_PASS, STATUS_SKIP


def _ledger(tmp_path):
    return Ledger(tmp_path / "ledger.jsonl"), keys.generate()


def _spec(tmp_path, text="# Spec\n\n- **SLK-FR-001**: shall hold.\n"):
    p = tmp_path / "specs-src" / "spec.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _approve(ledger, sk, root, spec_path, spec_id="SLK", stage="spec", commit=""):
    payload = {"approver": "carlo", "stage": stage, "note": ""}
    payload.update(speclock.approval_fields(root, spec_path, commit=commit))
    return ledger.append("signoff", payload, sk, spec_id=spec_id)


# --------------------------------------------------------------- hashing (FR-001)
def test_spec_file_hash_is_raw_bytes_sha256(tmp_path):
    """SLOCK-FR-001: the recorded hash is a raw-bytes SHA-256 of the full document."""
    spec = _spec(tmp_path)
    assert speclock.spec_file_hash(spec) == canonical.sha256_hex(spec.read_bytes())


def test_spec_file_hash_is_byte_for_byte(tmp_path):
    """SLOCK-FR-001 + non-goal: no normalization — a whitespace edit changes the hash."""
    spec = _spec(tmp_path)
    before = speclock.spec_file_hash(spec)
    spec.write_text(spec.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert speclock.spec_file_hash(spec) != before


def test_approval_fields_are_root_relative_with_optional_commit(tmp_path):
    """SLOCK-FR-001: the payload carries spec_hash + a root-relative spec_path (+ commit)."""
    spec = _spec(tmp_path)
    fields = speclock.approval_fields(tmp_path, spec, commit="abc1234")
    assert fields["spec_hash"] == speclock.spec_file_hash(spec)
    assert fields["spec_path"] == "specs-src/spec.md"
    assert fields["commit"] == "abc1234"
    assert "commit" not in speclock.approval_fields(tmp_path, spec)


# --------------------------------------------------- approval query (FR-002/006)
def test_spec_approval_none_when_no_signoff(tmp_path):
    """SLOCK-FR-002: no Spec-stage sign-off → no approval hash."""
    assert speclock.spec_approval([], "SLK") is None


def test_spec_approval_ignores_other_stages_and_hashless_signoffs(tmp_path):
    """SLOCK-FR-002: review sign-offs and pre-SLOCK spec sign-offs (no hash) never match."""
    ledger, sk = _ledger(tmp_path)
    ledger.append("signoff", {"approver": "c", "stage": "review"}, sk, spec_id="SLK")
    ledger.append("signoff", {"approver": "c", "stage": "spec"}, sk, spec_id="SLK")  # pre-SLOCK
    assert speclock.spec_approval(ledger.entries(), "SLK") is None


def test_spec_approval_latest_wins(tmp_path):
    """SLOCK-FR-002/FR-006: when several approvals exist, the later one supersedes."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec)
    spec.write_text("amended\n", encoding="utf-8")
    second = _approve(ledger, sk, tmp_path, spec)
    got = speclock.spec_approval(ledger.entries(), "SLK")
    assert got is not None and got["seq"] == second["seq"]
    assert got["payload"]["spec_hash"] == speclock.spec_file_hash(spec)


def test_spec_approval_is_scoped_to_the_spec_id(tmp_path):
    """SLOCK-FR-002: an approval for another spec never leaks across."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec, spec_id="OTHER")
    assert speclock.spec_approval(ledger.entries(), "SLK") is None


def test_spec_approval_stage_match_is_case_insensitive(tmp_path):
    """SLOCK-FR-001: manual (`--stage spec`) and orchestration (`Spec`) both count."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec, stage="Spec")
    assert speclock.spec_approval(ledger.entries(), "SLK") is not None


# ------------------------------------------------------------- check (FR-003/005)
def test_check_match_then_mismatch_after_edit(tmp_path):
    """SLOCK-FR-003: unmodified spec matches; a post-approval edit is a mismatch."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    entry = _approve(ledger, sk, tmp_path, spec)
    res = speclock.check(ledger.entries(), "SLK", tmp_path)
    assert res.status == speclock.MATCH and res.ok
    spec.write_text("mutated\n", encoding="utf-8")
    res = speclock.check(ledger.entries(), "SLK", tmp_path)
    assert res.status == speclock.MISMATCH and not res.ok
    assert res.approval_seq == entry["seq"]
    assert res.approver == "carlo"


def test_check_resolves_recorded_path_without_spec_arg(tmp_path):
    """SLOCK-FR-005: `advance` re-executes the check from the recorded root-relative path."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec)
    res = speclock.check(ledger.entries(), "SLK", tmp_path)  # no spec_path passed
    assert res.status == speclock.MATCH
    spec.unlink()
    res = speclock.check(ledger.entries(), "SLK", tmp_path)
    assert res.status == speclock.MISSING_FILE and not res.ok


def test_check_is_deterministic(tmp_path):
    """SLOCK-NFR-001: identical inputs → identical result (no clock, model, or network)."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec)
    assert speclock.check(ledger.entries(), "SLK", tmp_path) == speclock.check(
        ledger.entries(), "SLK", tmp_path
    )


# ----------------------------------------------------------------- gate (FR-003/004)
def test_gate_skips_without_approval_and_never_reads_the_file(tmp_path, monkeypatch):
    """SLOCK-FR-003 + SLOCK-NFR-003: no approval → skip in O(1), the spec file is never hashed."""

    def _boom(_path):
        raise AssertionError("spec file must not be read when no approval exists")

    monkeypatch.setattr(speclock, "spec_file_hash", _boom)
    gate = speclock.integrity_gate([], "SLK", tmp_path, tmp_path / "missing.md")
    assert gate.status == STATUS_SKIP
    assert "never blocked" in " ".join(gate.findings)


def test_gate_passes_on_unmodified_spec(tmp_path):
    """SLOCK-FR-003: an unmodified spec yields a passing gate."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    entry = _approve(ledger, sk, tmp_path, spec)
    gate = speclock.integrity_gate(ledger.entries(), "SLK", tmp_path, spec)
    assert gate.status == STATUS_PASS
    assert gate.details["approval_seq"] == entry["seq"]


def test_gate_fails_naming_the_approving_seq_after_mutation(tmp_path):
    """SLOCK-FR-003: a post-approval mutation fails, naming the approving ledger seq."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    entry = _approve(ledger, sk, tmp_path, spec)
    spec.write_text("mutated\n", encoding="utf-8")
    gate = speclock.integrity_gate(ledger.entries(), "SLK", tmp_path, spec)
    assert gate.status == STATUS_FAIL
    assert gate.details["approval_seq"] == entry["seq"]
    assert any("modified after approval" in f for f in gate.findings)


def test_gate_orders_after_types_before_tests():
    """SLOCK-FR-004: cheapest-first — spec_integrity sits after types, before tests."""
    assert GATE_ORDER.index("types") < GATE_ORDER.index("spec_integrity")
    assert GATE_ORDER.index("spec_integrity") < GATE_ORDER.index("tests")


def test_gate_result_is_deterministic(tmp_path):
    """SLOCK-NFR-001: two gate runs over identical inputs produce an identical result."""
    ledger, sk = _ledger(tmp_path)
    spec = _spec(tmp_path)
    _approve(ledger, sk, tmp_path, spec)
    a = speclock.integrity_gate(ledger.entries(), "SLK", tmp_path, spec)
    b = speclock.integrity_gate(ledger.entries(), "SLK", tmp_path, spec)
    assert a == b
