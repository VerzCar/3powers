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
