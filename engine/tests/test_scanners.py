"""Supply-chain scanner gates (3PWR-FR-028) and the quarantine path (3PWR-NFR-015)."""

from __future__ import annotations

import shlex
from pathlib import Path

from threepowers import scanners
from threepowers.adapters import CmdResult
from threepowers.verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP


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
