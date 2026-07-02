"""A3 — live headless dispatch + physical oracle read-path isolation (3PWR-FR-021/012/013).

Pure predicates (worktree manifest, isolation, dispatch attestation, the ``independence`` upgrade,
two-key verify) are exercised directly; the sanitized-worktree build and the ``3pwr oracle dispatch``
command are driven end to end on a real ``git``-initialised repo (``--dry-run`` — no live agent). The
physical-isolation fact is a *blocking* check at High-risk; the 008 peek/touch heuristics stay
advisory (3PWR-NFR-001).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from threepowers import keys as keymod
from threepowers import oracle
from threepowers.cli import main
from threepowers.ledger import Ledger
from threepowers.verify import verify_ledger

ROLES = {"roles": {"coder": {"model_family": "openai"}, "oracle": {"model_family": "anthropic"}}}


# --------------------------------------------------------------------------- git helpers
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


# --------------------------------------------------------------------------- pure: isolation + manifest
def test_is_excluded_and_isolation_violations():
    """3PWR-FR-021: implementation / plan / tasks / contracts are excluded; tests, specs, the
    sealed bundle, and docs are not."""
    manifest = [
        {"path": "src/impl.py", "hash": "h"},
        {"path": "engine/src/threepowers/oracle.py", "hash": "h"},
        {"path": "plan.md", "hash": "h"},
        {"path": "tasks.md", "hash": "h"},
        {"path": "specs/x/contracts/api.yaml", "hash": "h"},
        {"path": "tests/thing.test.py", "hash": "h"},
        {"path": "ORACLE_BUNDLE.json", "hash": "h"},
        {"path": "spec.md", "hash": "h"},
        {"path": "README.md", "hash": "h"},
    ]
    v = oracle.isolation_violations(manifest)
    assert "src/impl.py" in v
    assert "engine/src/threepowers/oracle.py" in v
    assert "plan.md" in v and "tasks.md" in v
    assert "specs/x/contracts/api.yaml" in v  # anything under a contracts/ dir
    assert "tests/thing.test.py" not in v  # a test file is not implementation
    assert "ORACLE_BUNDLE.json" not in v and "spec.md" not in v and "README.md" not in v


def test_worktree_manifest_is_deterministic(tmp_path):
    """The isolation manifest hash is stable for an identical tree, and changes on any edit."""
    d = tmp_path / "w"
    (d / "sub").mkdir(parents=True)
    (d / "a.txt").write_text("A\n", encoding="utf-8")
    (d / "sub" / "b.txt").write_text("B\n", encoding="utf-8")
    h1 = oracle.manifest_hash(oracle.worktree_manifest(d))
    assert h1.startswith("sha256:")
    assert h1 == oracle.manifest_hash(oracle.worktree_manifest(d))
    (d / "a.txt").write_text("A changed\n", encoding="utf-8")
    assert oracle.manifest_hash(oracle.worktree_manifest(d)) != h1


# --------------------------------------------------------------------------- pure: attestation helpers
def test_dispatch_payload_and_active_dispatch():
    p = oracle.dispatch_payload(
        "sha256:b",
        "claude",
        "anthropic/claude-x",
        {"manifest_hash": "sha256:m", "file_count": 5, "excluded_absent": True},
    )
    assert p["kind"] == "dispatch"
    assert p["bundle_hash"] == "sha256:b"
    assert p["integration"] == "claude"
    assert p["model_family"] == "anthropic"
    assert p["isolation"] == {
        "method": "git-worktree",
        "manifest_hash": "sha256:m",
        "file_count": 5,
        "excluded_absent": True,
    }
    entries = [{"seq": 0, "type": "oracle", "spec_id": "ORAC", "payload": p}]
    assert oracle.active_dispatch(entries, "ORAC")["payload"]["integration"] == "claude"
    assert oracle.active_dispatch([], "ORAC") is None


def test_integration_family_and_model_parse():
    """3PWR-FR-022 precheck helpers."""
    assert oracle.integration_family("claude") == "anthropic"
    assert oracle.integration_family("copilot") == ""  # in-IDE picker: family is ambiguous
    assert oracle.integration_family("nope") == ""
    assert (
        oracle.parse_dispatched_model('{"run": {"model": "anthropic/claude-x"}}')
        == "anthropic/claude-x"
    )
    assert oracle.parse_dispatched_model("not json") is None
    assert oracle.parse_dispatched_model('{"model": "no-slash"}') is None


# --------------------------------------------------------------------------- pure: independence upgrade
def _seal(seq, bhash="h", req_ids=("ORAC-FR-001",)):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": "ORAC",
        "payload": {"kind": "seal", "bundle_hash": bhash, "requirement_ids": list(req_ids)},
    }


def _record(seq, bhash="h", family="anthropic"):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": "ORAC",
        "payload": {
            "kind": "record",
            "bundle_hash": bhash,
            "model_family": family,
            "model": f"{family}/m",
            "test_paths": [],
            "advisory_findings": [],
        },
    }


def _dispatch(seq, bhash="h", family="anthropic", *, excluded_absent=True, manifest="sha256:m"):
    return {
        "seq": seq,
        "type": "oracle",
        "spec_id": "ORAC",
        "payload": oracle.dispatch_payload(
            bhash,
            "claude",
            f"{family}/m",
            {"manifest_hash": manifest, "file_count": 3, "excluded_absent": excluded_absent},
        ),
    }


def _covered_tests(tmp_path):
    t = tmp_path / "oracle_orac.py"
    t.write_text("# covers ORAC-FR-001\n", encoding="utf-8")
    return [t]


def test_independence_dispatch_proves_isolation(tmp_path):
    """3PWR-FR-021/A3: a seal-bound, isolated, diverse dispatch makes independence PASS and reports
    read-path isolation."""
    entries = [_seal(0), _record(1), _dispatch(2)]
    ind = oracle.independence(
        entries,
        ROLES,
        "ORAC",
        repo_root=tmp_path,
        test_roots=_covered_tests(tmp_path),
        require_dispatch=True,
    )
    assert ind.ok, ind.reasons
    assert ind.dispatch_ok is True
    assert ind.isolation_method == "git-worktree"


def test_independence_dispatch_not_isolated_blocks(tmp_path):
    """3PWR-FR-021: a dispatch whose manifest did not prove the implementation absent blocks."""
    entries = [_seal(0), _record(1), _dispatch(2, excluded_absent=False)]
    ind = oracle.independence(
        entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=_covered_tests(tmp_path)
    )
    assert not ind.ok
    assert ind.dispatch_ok is False
    assert any("read-path isolation" in r for r in ind.reasons)


def test_independence_require_dispatch_without_dispatch_blocks(tmp_path):
    """3PWR-FR-021/A3: with the policy on, a missing dispatch attestation blocks; with it off, the
    manual path (008) still passes — backward compatible."""
    entries = [_seal(0), _record(1)]
    roots = _covered_tests(tmp_path)
    blocked = oracle.independence(
        entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=roots, require_dispatch=True
    )
    assert not blocked.ok
    assert any("no isolated oracle dispatch" in r for r in blocked.reasons)
    ok = oracle.independence(
        entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=roots, require_dispatch=False
    )
    assert ok.ok, ok.reasons
    assert ok.dispatch_ok is None  # no attestation present


def test_independence_dispatch_family_equals_coder_blocks(tmp_path):
    """3PWR-FR-022: a dispatch that resolved to the coder's family blocks even if the record was
    diverse."""
    entries = [_seal(0), _record(1, family="anthropic"), _dispatch(2, family="openai")]
    ind = oracle.independence(
        entries, ROLES, "ORAC", repo_root=tmp_path, test_roots=_covered_tests(tmp_path)
    )
    assert not ind.ok
    assert any("dispatch model family" in r and "coder" in r for r in ind.reasons)


def test_independence_advisory_never_blocks_even_with_dispatch(tmp_path):
    """User's rule (3PWR-FR-021): advisory peek/touch findings are surfaced, never blocking."""
    rec = _record(1)
    rec["payload"]["advisory_findings"] = ["oracle test imports internal implementation modules: x"]
    entries = [_seal(0), rec, _dispatch(2)]
    ind = oracle.independence(
        entries,
        ROLES,
        "ORAC",
        repo_root=tmp_path,
        test_roots=_covered_tests(tmp_path),
        require_dispatch=True,
    )
    assert ind.ok, ind.reasons
    assert ind.advisory and all("advisory" not in r for r in ind.reasons)


# --------------------------------------------------------------------------- two-key verify (NFR-005)
def test_two_key_verify_accepts_oracle_signed_entries(tmp_path):
    """3PWR-FR-021/039: an entry signed by a distinct oracle key verifies only when that key is
    supplied; the primary key alone cannot verify it."""
    primary = keymod.generate()
    oracle_sk = keymod.generate()
    primary_pub = tmp_path / "ledger.pub"
    oracle_pub = tmp_path / "oracle.pub"
    keymod.write_public(primary_pub, primary.verify_key)
    keymod.write_public(oracle_pub, oracle_sk.verify_key)
    lp = tmp_path / "ledger.jsonl"
    Ledger(lp).append("oracle", {"kind": "dispatch"}, oracle_sk, spec_id="ORAC")
    assert not verify_ledger(
        lp, primary_pub
    ).ok  # primary alone can't verify an oracle-signed entry
    assert verify_ledger(lp, primary_pub, [oracle_pub]).ok  # both keys → verifies


def test_single_key_repo_still_verifies(tmp_path):
    """Backward compatibility: a missing extra oracle key path is simply skipped."""
    primary = keymod.generate()
    primary_pub = tmp_path / "ledger.pub"
    keymod.write_public(primary_pub, primary.verify_key)
    lp = tmp_path / "ledger.jsonl"
    Ledger(lp).append("verdict", {"result": "pass"}, primary, spec_id="X")
    assert verify_ledger(lp, primary_pub, [tmp_path / "does-not-exist.pub"]).ok


def test_resolve_signing_key_role_and_seed(tmp_path, monkeypatch):
    """3PWR-NFR-005: the oracle role prefers its own key (here via the seed env), and falls back to
    the primary when unset; the ledger role always resolves the primary."""
    import base64 as _b64

    primary = keymod.generate()
    oracle_sk = keymod.generate()
    monkeypatch.setenv("THREEPOWERS_ORACLE_SIGNING_KEY", _b64.b64encode(oracle_sk.seed).decode())
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY", _b64.b64encode(primary.seed).decode())
    assert keymod.resolve_signing_key(tmp_path, role="oracle").key_id == oracle_sk.key_id
    assert keymod.resolve_signing_key(tmp_path).key_id == primary.key_id  # ledger role → primary
    monkeypatch.delenv("THREEPOWERS_ORACLE_SIGNING_KEY", raising=False)
    assert keymod.resolve_signing_key(tmp_path, role="oracle").key_id == primary.key_id  # fallback
    assert keymod.default_oracle_private_path(tmp_path).name.endswith(".oracle.key")


# --------------------------------------------------------------------------- worktree build (git)
def test_build_sanitized_worktree_prunes_implementation(tmp_path):
    """3PWR-FR-021: implementation / plan / tasks / contracts are physically absent from the
    worktree; the sealed bundle is copied in; teardown removes it."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "impl.py").write_text("x = 1\n", encoding="utf-8")
    (root / "plan.md").write_text("the plan\n", encoding="utf-8")
    (root / "tasks.md").write_text("the tasks\n", encoding="utf-8")
    (root / "contracts").mkdir()
    (root / "contracts" / "api.yaml").write_text("openapi\n", encoding="utf-8")
    (root / "spec.md").write_text(
        "**Spec ID**: ORAC\n- **ORAC-FR-001**: shall.\n", encoding="utf-8"
    )
    (root / "tests").mkdir()
    (root / "tests" / "t.test.py").write_text("# test\n", encoding="utf-8")
    _init_repo(root)
    sealed = root / "sealed.json"
    sealed.write_text(
        '{"spec_id": "ORAC"}\n', encoding="utf-8"
    )  # created AFTER commit (uncommitted)

    wt = root / ".3powers" / "worktrees" / "ORAC"
    info = oracle.build_sanitized_worktree(root, wt, sealed, base_ref="HEAD")
    try:
        paths = {m["path"] for m in info.manifest}
        assert "src/impl.py" not in paths
        assert "plan.md" not in paths and "tasks.md" not in paths
        assert "contracts/api.yaml" not in paths
        assert oracle.isolation_violations(info.manifest) == []
        assert "ORACLE_BUNDLE.json" in paths  # sealed bundle copied in (was uncommitted)
        assert "tests/t.test.py" in paths and "spec.md" in paths  # legislative content survives
        assert info.file_count == len(info.manifest)
    finally:
        oracle.teardown_worktree(root, wt)
    assert not wt.exists()


# --------------------------------------------------------------------------- CLI end-to-end (--dry-run)
RISK_TIERS = """
tiers:
  Standard:  { diff_coverage: 80, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
  High-risk: { diff_coverage: 95, gates: [format, lint, types, tests, diff_coverage, spec_conformance] }
"""
ROLES_YAML = """
roles:
  coder: { model_family: openai }
  oracle: { model_family: anthropic, require_dispatch: true }
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
def dispatch_project(tmp_path, monkeypatch):
    root = tmp_path / "dispatch-repo"
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
    (proj / "impl.py").write_text(
        "def f():\n    return 1\n", encoding="utf-8"
    )  # pruned in worktree
    (proj / "tests" / "orac.test.py").write_text("# covers ORAC-FR-001\n", encoding="utf-8")
    (proj / "coverage").mkdir()
    (proj / "coverage" / "lcov.info").write_text(
        "SF:src/x.py\nDA:1,1\nDA:2,1\nend_of_record\n", encoding="utf-8"
    )
    # The oracle test the "dispatch" authors (simulated via --tests under --dry-run).
    otest = root / "authored_oracle_orac.py"
    otest.write_text("# oracle covers ORAC-FR-001\n", encoding="utf-8")

    keyfile = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(keyfile))
    assert main(["--root", str(root), "keygen", "--out", str(keyfile)]) == 0
    _init_repo(root)  # so `git worktree add` works
    return root, proj, otest


def _seal_cli(root, proj):
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


def _dispatch_cli(root, otest, extra=()):
    return main(
        [
            "--root",
            str(root),
            "oracle",
            "dispatch",
            "--spec-id",
            "ORAC",
            "--integration",
            "claude",
            "--dry-run",
            "--tests",
            str(otest),
            *extra,
        ]
    )


def _gate_cli(root, proj, tier="High-risk"):
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


def test_cli_dispatch_dry_run_isolates_and_attests(dispatch_project):
    """3PWR-FR-021/A3: `oracle dispatch --dry-run` builds an isolated worktree, records the
    record + dispatch attestation, and `oracle verify --require-dispatch` PASSes; the ledger
    verifies and the worktree is cleaned up."""
    root, proj, otest = dispatch_project
    assert _seal_cli(root, proj) == 0
    assert _dispatch_cli(root, otest) == 0
    assert (
        main(["--root", str(root), "oracle", "verify", "--spec-id", "ORAC", "--require-dispatch"])
        == 0
    )
    assert main(["--root", str(root), "verify"]) == 0
    assert not (root / ".3powers" / "worktrees" / "ORAC").exists()


def test_cli_dispatch_refuses_coder_family(dispatch_project):
    """3PWR-FR-022: dispatching under an integration in the coder's family is refused up front."""
    root, proj, otest = dispatch_project
    assert _seal_cli(root, proj) == 0
    rc = main(
        [
            "--root",
            str(root),
            "oracle",
            "dispatch",
            "--spec-id",
            "ORAC",
            "--integration",
            "codex",  # openai family == coder
            "--dry-run",
            "--tests",
            str(otest),
        ]
    )
    assert rc == 1


def test_cli_high_risk_advance_with_dispatch(dispatch_project):
    """3PWR-FR-021/062: Phase-A isolated dispatch before the Phase-B verdict lets a High-risk
    advance proceed (roles.oracle.require_dispatch is on)."""
    root, proj, otest = dispatch_project
    assert _seal_cli(root, proj) == 0  # #0 seal
    assert _dispatch_cli(root, otest) == 0  # #1 record, #2 dispatch (Phase A)
    assert _gate_cli(root, proj) == 0  # #3 verdict (Phase B)
    assert main(["--root", str(root), "signoff", "--approver", "carlo", "--spec-id", "ORAC"]) == 0
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "ORAC"]) == 0


def test_cli_high_risk_advance_requires_dispatch_when_policy_on(dispatch_project):
    """3PWR-FR-021/A3: with the policy on, a manual record WITHOUT an isolated dispatch blocks the
    High-risk advance."""
    root, proj, otest = dispatch_project
    assert _seal_cli(root, proj) == 0
    assert (
        main(
            [
                "--root",
                str(root),
                "oracle",
                "record",
                "--spec-id",
                "ORAC",
                "--model",
                "anthropic/claude",
                "--tests",
                str(otest),
            ]
        )
        == 0
    )
    assert _gate_cli(root, proj) == 0
    assert main(["--root", str(root), "signoff", "--approver", "carlo", "--spec-id", "ORAC"]) == 0
    assert main(["--root", str(root), "advance", "--stage", "ship", "--spec-id", "ORAC"]) == 1
