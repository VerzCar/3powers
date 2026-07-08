"""Supply-chain scanner gates (3PWR-FR-028), the quarantine path (3PWR-NFR-015), and the
auditable scan.yaml exclusions (plan 033 Track I / SEC-001)."""

from __future__ import annotations

import shlex
from pathlib import Path

import yaml

from threepowers import gates as gates_mod
from threepowers import scaffold, scanners
from threepowers.adapters import CmdResult
from threepowers.config import Settings
from threepowers.gates import run_gates
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult


def test_quarantine_when_tool_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: None)
    for gate in (scanners.secret_scan(tmp_path), scanners.dependency_scan(tmp_path)):
        assert gate.status == STATUS_SKIP
        assert "quarantined" in gate.findings[0]  # surfaced, not silently passed


def test_secret_scan_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: "/bin/gitleaks")
    monkeypatch.setattr(scanners, "run_cmd", lambda cmd, cwd: CmdResult(0, "", "", 3))
    gate = scanners.secret_scan(tmp_path)
    assert gate.status == STATUS_PASS and gate.findings == []


def test_secret_scan_prefers_betterleaks(tmp_path, monkeypatch):
    """3PWR-FR-028: when both are installed, betterleaks (the maintained successor) is used."""
    monkeypatch.setattr(scanners.shutil, "which", lambda t: "/bin/" + t)  # both on PATH
    monkeypatch.setattr(scanners, "run_cmd", lambda cmd, cwd: CmdResult(0, "", "", 3))
    gate = scanners.secret_scan(tmp_path)
    assert gate.tool == "betterleaks" and gate.status == STATUS_PASS


def test_secret_scan_falls_back_to_gitleaks(tmp_path, monkeypatch):
    """gitleaks is the fallback when betterleaks is not installed."""
    monkeypatch.setattr(
        scanners.shutil, "which", lambda t: "/bin/gitleaks" if t == "gitleaks" else None
    )
    monkeypatch.setattr(scanners, "run_cmd", lambda cmd, cwd: CmdResult(0, "", "", 3))
    gate = scanners.secret_scan(tmp_path)
    assert gate.tool == "gitleaks" and gate.status == STATUS_PASS


def test_secret_scan_quarantine_when_neither(tmp_path, monkeypatch):
    """3PWR-NFR-015: neither scanner installed → quarantined, never silently passed."""
    monkeypatch.setattr(scanners.shutil, "which", lambda t: None)
    gate = scanners.secret_scan(tmp_path)
    assert gate.status == STATUS_SKIP and "betterleaks/gitleaks" in gate.tool


def test_secret_scan_betterleaks_null_report_is_clean(tmp_path, monkeypatch):
    """betterleaks writes `null` for an empty report (gitleaks writes `[]`); both mean clean."""
    monkeypatch.setattr(scanners.shutil, "which", lambda t: "/bin/betterleaks")

    def fake_run(cmd, cwd):
        out = Path(shlex.split(cmd)[shlex.split(cmd).index("--report-path") + 1])
        out.write_text("null", encoding="utf-8")  # betterleaks' empty-report form
        return CmdResult(0, "", "", 3)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)
    gate = scanners.secret_scan(tmp_path)
    assert gate.status == STATUS_PASS and gate.findings == []


def test_secret_scan_betterleaks_finds_secret(tmp_path, monkeypatch):
    """betterleaks shares gitleaks' JSON schema (File/RuleID/StartLine)."""
    monkeypatch.setattr(scanners.shutil, "which", lambda t: "/bin/betterleaks")

    def fake_run(cmd, cwd):
        out = Path(shlex.split(cmd)[shlex.split(cmd).index("--report-path") + 1])
        out.write_text('[{"RuleID":"github-pat","File":".env","StartLine":1}]', encoding="utf-8")
        return CmdResult(1, "", "", 4)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)
    gate = scanners.secret_scan(tmp_path)
    assert gate.status == STATUS_FAIL and gate.tool == "betterleaks"
    assert any("github-pat" in f and ".env" in f for f in gate.findings)


def test_dependency_scan_reports_vulns(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: "/bin/osv-scanner")

    def fake_run(cmd, cwd):
        parts = shlex.split(cmd)
        out = Path(parts[parts.index("--output-file") + 1])
        out.write_text(
            '{"results":[{"packages":[{"package":{"name":"glob"},'
            '"vulnerabilities":[{"id":"GHSA-xxxx"}]}]}]}',
            encoding="utf-8",
        )
        return CmdResult(1, "", "", 7)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)
    gate = scanners.dependency_scan(tmp_path)
    assert gate.status == STATUS_FAIL
    assert any("GHSA-xxxx" in f and "glob" in f for f in gate.findings)


def test_sast_quarantine_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: None)
    gate = scanners.sast_scan(tmp_path, tmp_path / "rules.yml")
    assert gate.status == STATUS_SKIP and "quarantined" in gate.findings[0]


def test_sast_reports_findings(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: "/bin/semgrep")
    rules = tmp_path / "rules.yml"
    rules.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setattr(
        scanners,
        "run_cmd",
        lambda cmd, cwd: CmdResult(
            1, '{"results":[{"check_id":"dangerous-eval","path":"a.py","start":{"line":3}}]}', "", 5
        ),
    )
    gate = scanners.sast_scan(tmp_path, rules)
    assert gate.status == STATUS_FAIL
    assert any("dangerous-eval" in f for f in gate.findings)


def _sast_with_finding(tmp_path, monkeypatch, path="a.py"):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: "/bin/semgrep")
    rules = tmp_path / "rules.yml"
    rules.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setattr(
        scanners,
        "run_cmd",
        lambda cmd, cwd: CmdResult(
            1,
            '{"results":[{"check_id":"dangerous-eval","path":"%s","start":{"line":3}}]}' % path,
            "",
            5,
        ),
    )
    return rules


def test_sast_diff_scope_ignores_unchanged_files(tmp_path, monkeypatch):
    """A legacy finding outside the diff does not block (brownfield, 3PWR-FR-051)."""
    rules = _sast_with_finding(tmp_path, monkeypatch, path="legacy.py")
    changed = {str((tmp_path / "feature.py").resolve())}  # legacy.py not in the diff
    gate = scanners.sast_scan(tmp_path, rules, changed)
    assert gate.status == STATUS_PASS and gate.findings == []


def test_sast_diff_scope_blocks_changed_files(tmp_path, monkeypatch):
    rules = _sast_with_finding(tmp_path, monkeypatch, path="feature.py")
    changed = {str((tmp_path / "feature.py").resolve())}
    gate = scanners.sast_scan(tmp_path, rules, changed)
    assert gate.status == STATUS_FAIL
    assert any("dangerous-eval" in f for f in gate.findings)


def test_secret_scan_diff_scope_ignores_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(scanners.shutil, "which", lambda _tool: "/bin/gitleaks")

    def fake_run(cmd, cwd):
        out = Path(shlex.split(cmd)[shlex.split(cmd).index("--report-path") + 1])
        out.write_text('[{"RuleID":"aws-key","File":"legacy.py","StartLine":1}]', encoding="utf-8")
        return CmdResult(1, "", "", 4)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)
    changed = {str((tmp_path / "feature.py").resolve())}
    gate = scanners.secret_scan(tmp_path, changed)
    assert gate.status == STATUS_PASS and gate.findings == []


# ------------------------------------------------------------- scan.yaml exclusions (SEC-001)

_KEY_LINE = "ed25519-priv " + "A" * 44 + "\n"  # matches the core private-key format


def _secret_report(monkeypatch, body: str, returncode: int = 1):
    """Fake a secret-scanner run that writes ``body`` as its JSON report."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: "/bin/betterleaks")

    def fake_run(cmd, cwd):
        out = Path(shlex.split(cmd)[shlex.split(cmd).index("--report-path") + 1])
        out.write_text(body, encoding="utf-8")
        return CmdResult(returncode, "", "", 4)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)


def test_secret_scan_ignore_glob_excludes_and_reports(tmp_path, monkeypatch):
    """SEC-001: an ignored path is excluded AND the exclusion is reported, never silent."""
    _secret_report(monkeypatch, '[{"RuleID":"github-pat","File":"dist/app.js","StartLine":1}]')
    gate = scanners.secret_scan(tmp_path, ignore=["**/dist/**"])
    assert gate.status == STATUS_PASS
    assert gate.details["ignored_globs"] == ["**/dist/**"]
    assert gate.details["excluded_count"] == 1
    assert any("scan.yaml exclusions applied" in f for f in gate.findings)


def test_secret_scan_ignore_rule_suppresses_but_others_still_fail(tmp_path, monkeypatch):
    """SEC-001: a suppressed rule id is excluded; a non-suppressed finding still fails."""
    _secret_report(
        monkeypatch,
        '[{"RuleID":"generic-api-key","File":"a.txt","StartLine":1},'
        '{"RuleID":"github-pat","File":"b.txt","StartLine":2}]',
    )
    gate = scanners.secret_scan(tmp_path, ignore_rules=["generic-api-key"])
    assert gate.status == STATUS_FAIL
    assert any("github-pat" in f for f in gate.findings)
    assert not any("generic-api-key in" in f for f in gate.findings)
    assert gate.details["excluded_count"] == 1
    assert gate.details["ignored_rules"] == ["generic-api-key"]


def test_secret_scan_non_ignored_finding_still_fails(tmp_path, monkeypatch):
    """SEC-001: an ignore glob never blankets the scan — findings outside it still fail."""
    _secret_report(monkeypatch, '[{"RuleID":"github-pat","File":"src/.env","StartLine":1}]')
    gate = scanners.secret_scan(tmp_path, ignore=["**/dist/**"])
    assert gate.status == STATUS_FAIL
    assert any("src/.env" in f for f in gate.findings)


def test_core_ed25519_walk_skips_ignored_globs_but_still_fires_outside(tmp_path, monkeypatch):
    """SEC-001: the core private-key check honors globs only as a walk filter — key material
    outside an ignored tree still fails, with no external scanner installed."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: None)
    (tmp_path / ".next").mkdir()
    (tmp_path / ".next" / "cache.txt").write_text(_KEY_LINE, encoding="utf-8")
    (tmp_path / "oops.key").write_text(_KEY_LINE, encoding="utf-8")
    gate = scanners.secret_scan(tmp_path, ignore=["**/.next/**"])
    assert gate.status == STATUS_FAIL
    assert any("oops.key" in f for f in gate.findings)
    assert not any(".next" in f for f in gate.findings if "private-key" in f)


def test_core_ed25519_walk_ignored_only_key_is_excluded_and_reported(tmp_path, monkeypatch):
    """SEC-001: key material only inside an ignored tree is skipped by the walk — and the
    exclusion still shows up on the (quarantined) result."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: None)
    (tmp_path / ".next").mkdir()
    (tmp_path / ".next" / "cache.txt").write_text(_KEY_LINE, encoding="utf-8")
    gate = scanners.secret_scan(tmp_path, ignore=["**/.next/**"])
    assert gate.status == STATUS_SKIP  # external portion quarantined; filtered core walk clean
    assert gate.details["ignored_globs"] == ["**/.next/**"]
    assert any("scan.yaml exclusions applied" in f for f in gate.findings)


def test_sast_ignore_glob_excludes_reports_and_passes(tmp_path, monkeypatch):
    """SEC-001: sast ignore globs become semgrep --exclude flags, filter the parsed results,
    and are reported on the gate output."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: "/bin/semgrep")
    rules = tmp_path / "rules.yml"
    rules.write_text("rules: []\n", encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_run(cmd, cwd):
        captured["cmd"] = cmd
        return CmdResult(
            1,
            '{"results":[{"check_id":"dangerous-eval","path":"dist/x.js","start":{"line":3}}]}',
            "",
            5,
        )

    monkeypatch.setattr(scanners, "run_cmd", fake_run)
    gate = scanners.sast_scan(tmp_path, rules, ignore=["**/dist/**"])
    assert gate.status == STATUS_PASS
    assert "--exclude '**/dist/**'" in captured["cmd"]
    assert gate.details["ignored_globs"] == ["**/dist/**"]
    assert gate.details["excluded_count"] == 1
    assert any("scan.yaml exclusions applied" in f for f in gate.findings)


def test_sast_non_ignored_finding_still_fails(tmp_path, monkeypatch):
    """SEC-001: a sast finding outside the ignore globs still fails the gate."""
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: "/bin/semgrep")
    rules = tmp_path / "rules.yml"
    rules.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setattr(
        scanners,
        "run_cmd",
        lambda cmd, cwd: CmdResult(
            1,
            '{"results":[{"check_id":"dangerous-eval","path":"src/a.py","start":{"line":3}}]}',
            "",
            5,
        ),
    )
    gate = scanners.sast_scan(tmp_path, rules, ignore=["**/dist/**"])
    assert gate.status == STATUS_FAIL
    assert any("dangerous-eval" in f and "src/a.py" in f for f in gate.findings)


def _osv_report(monkeypatch, body: str, returncode: int = 1):
    monkeypatch.setattr(scanners.shutil, "which", lambda _t: "/bin/osv-scanner")

    def fake_run(cmd, cwd):
        parts = shlex.split(cmd)
        out = Path(parts[parts.index("--output-file") + 1])
        out.write_text(body, encoding="utf-8")
        return CmdResult(returncode, "", "", 7)

    monkeypatch.setattr(scanners, "run_cmd", fake_run)


def test_dependency_scan_ignore_source_excludes_and_reports(tmp_path, monkeypatch):
    """SEC-001: a vulnerable dependency whose source manifest lies under an ignored tree is
    excluded — and reported."""
    _osv_report(
        monkeypatch,
        '{"results":[{"source":{"path":"vendor/node_modules/x/package-lock.json"},'
        '"packages":[{"package":{"name":"glob"},"vulnerabilities":[{"id":"GHSA-xxxx"}]}]}]}',
    )
    gate = scanners.dependency_scan(tmp_path, ignore=["**/node_modules/**"])
    assert gate.status == STATUS_PASS and gate.findings != []
    assert gate.details["excluded_count"] == 1
    assert gate.details["ignored_globs"] == ["**/node_modules/**"]
    assert any("scan.yaml exclusions applied" in f for f in gate.findings)


def test_dependency_scan_non_ignored_source_still_fails(tmp_path, monkeypatch):
    """SEC-001: a vulnerability from a non-ignored manifest still fails the gate."""
    _osv_report(
        monkeypatch,
        '{"results":[{"source":{"path":"package-lock.json"},'
        '"packages":[{"package":{"name":"glob"},"vulnerabilities":[{"id":"GHSA-xxxx"}]}]}]}',
    )
    gate = scanners.dependency_scan(tmp_path, ignore=["**/node_modules/**"])
    assert gate.status == STATUS_FAIL
    assert any("GHSA-xxxx" in f for f in gate.findings)


def test_scanner_exclusions_are_deterministic(tmp_path, monkeypatch):
    """SEC-001: same inputs + same committed config → byte-identical results across runs."""
    _secret_report(monkeypatch, '[{"RuleID":"github-pat","File":"dist/app.js","StartLine":1}]')
    a = scanners.secret_scan(tmp_path, ignore=["**/dist/**"])
    b = scanners.secret_scan(tmp_path, ignore=["**/dist/**"])
    assert (a.status, a.findings, a.details) == (b.status, b.findings, b.details)


# --------------------------------------------------------- scan.yaml loading, seeding, dispatch


_EMPTY_IGNORES = {
    tool: {"ignore": [], "ignore_rules": []} for tool in ("secret_scan", "dependency_scan", "sast")
}


def test_scan_config_loader_missing_and_malformed_fall_back(tmp_path):
    """A missing or malformed scan.yaml yields NO exclusions — the scanners run unrestricted."""
    s = Settings(root=tmp_path)
    assert s.load_scan_ignores() == _EMPTY_IGNORES  # absent file
    p = s.scan_config_path
    p.parent.mkdir(parents=True)
    p.write_text("just a scalar", encoding="utf-8")
    assert s.load_scan_ignores() == _EMPTY_IGNORES  # not a mapping
    p.write_text("version: 1\nsecret_scan: [not, a, mapping]\n", encoding="utf-8")
    assert s.load_scan_ignores() == _EMPTY_IGNORES  # malformed section
    p.write_text("{invalid yaml: [", encoding="utf-8")
    assert s.load_scan_ignores() == _EMPTY_IGNORES  # unparseable


def test_scan_config_loader_parses_per_tool_and_drops_non_strings(tmp_path):
    s = Settings(root=tmp_path)
    s.scan_config_path.parent.mkdir(parents=True)
    s.scan_config_path.write_text(
        "version: 1\n"
        "secret_scan:\n  ignore: ['**/dist/**', 3, '']\n  ignore_rules: [generic-api-key]\n"
        "sast:\n  ignore: ['**/.next/**']\n",
        encoding="utf-8",
    )
    cfg = s.load_scan_ignores()
    assert cfg["secret_scan"] == {"ignore": ["**/dist/**"], "ignore_rules": ["generic-api-key"]}
    assert cfg["sast"] == {"ignore": ["**/.next/**"], "ignore_rules": []}
    assert cfg["dependency_scan"] == {"ignore": [], "ignore_rules": []}


def test_init_seeds_scan_yaml_and_never_clobbers(tmp_path):
    """`3pwr init` seeds scan.yaml with the default ignore set and keeps a hand-edited one."""
    s = Settings(root=tmp_path)
    scaffold.seed_config(s)
    seed = s.scan_config_path
    assert seed.is_file()
    data = yaml.safe_load(seed.read_text(encoding="utf-8"))
    assert data["version"] == 1
    for tool in ("secret_scan", "dependency_scan", "sast"):
        assert "**/.next/**" in data[tool]["ignore"]
    seed.write_text("version: 1\nsast: {ignore: ['mine/**']}\n", encoding="utf-8")
    scaffold.seed_config(s)
    assert "mine" in seed.read_text(encoding="utf-8")


def test_gate_dispatch_threads_scan_ignores_into_each_scanner(tmp_path, monkeypatch):
    """run_gates passes the per-tool scan.yaml ignore lists into each scanner call."""
    tp = tmp_path / ".3powers"
    (tp / "config").mkdir(parents=True)
    (tp / "adapters" / "a").mkdir(parents=True)
    (tp / "config" / "risk-tiers.yaml").write_text(
        "tiers:\n  T: { diff_coverage: 0, gates: [sast, dependency_scan, secret_scan] }\n",
        encoding="utf-8",
    )
    (tp / "config" / "scan.yaml").write_text(
        "version: 1\n"
        "secret_scan:\n  ignore: ['**/dist/**']\n  ignore_rules: [generic-api-key]\n"
        "dependency_scan:\n  ignore: ['**/node_modules/**']\n"
        "sast:\n  ignore: ['**/.next/**']\n",
        encoding="utf-8",
    )
    (tp / "adapters" / "a" / "adapter.yaml").write_text(
        'language: a\ndetect: ["d"]\ntest_roots: ["tests"]\ngates: {}\n', encoding="utf-8"
    )
    proj = tmp_path / "p"
    proj.mkdir()
    (proj / "d").write_text("")
    seen: dict[str, object] = {}

    def fake_sast(target, rules_path, changed=None, ignore=()):
        seen["sast"] = list(ignore)
        return GateResult(gate="sast", status=STATUS_PASS)

    def fake_dep(target, ignore=()):
        seen["dependency_scan"] = list(ignore)
        return GateResult(gate="dependency_scan", status=STATUS_PASS)

    def fake_secret(target, changed=None, ignore=(), ignore_rules=()):
        seen["secret_scan"] = (list(ignore), list(ignore_rules))
        return GateResult(gate="secret_scan", status=STATUS_PASS)

    monkeypatch.setattr(gates_mod.scanners, "sast_scan", fake_sast)
    monkeypatch.setattr(gates_mod.scanners, "dependency_scan", fake_dep)
    monkeypatch.setattr(gates_mod.scanners, "secret_scan", fake_secret)
    v = run_gates(Settings(root=tmp_path), proj, tier="T", spec_path=None, adapter_name="a")
    assert v.result == STATUS_PASS
    assert seen["sast"] == ["**/.next/**"]
    assert seen["dependency_scan"] == ["**/node_modules/**"]
    assert seen["secret_scan"] == (["**/dist/**"], ["generic-api-key"])
