"""Language-agnostic supply-chain scanners — core gates.

Secret scanning (betterleaks, falling back to gitleaks) and dependency scanning (osv-scanner)
live in the core, not in a language adapter, because they do not depend on the project's language.
When a scanner binary is absent the gate is **quarantined** — reported as ``skip`` with a surfaced
finding — never silently passed.

Each scanner accepts auditable exclusions from the committed ``scan.yaml`` (per-tool ``ignore``
path globs, ``ignore_rules`` for the secret scanner, plus an expiring ``advisories`` allowlist
for the dependency scanner). Security invariants: every applied exclusion or advisory acceptance
is reported in the gate output — never silent; exclusions are deterministic in the config's
committed bytes; an advisory suppresses only with a non-empty reason and only until its optional
expiry (fail-closed); and the core ``ed25519-priv`` private-key check always runs — the globs
only filter its walk, never disable it.
"""

from __future__ import annotations

import fnmatch
import json
import re
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

from .adapters import run_cmd
from .deviations import parse_iso
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult


def _quarantine(gate: str, tool: str) -> GateResult:
    return GateResult(
        gate=gate,
        status=STATUS_SKIP,
        tool=tool,
        findings=[f"quarantined: '{tool}' not installed — gate not enforced"],
    )


def _in_scope(target: Path, file: str, changed: set[str] | None) -> bool:
    """True if a finding's file is in the changed-file scope (brownfield).

    ``changed`` holds absolute paths; ``file`` is whatever the scanner reported
    (absolute, or relative to ``target``). When ``changed`` is None nothing is scoped.
    """
    if changed is None:
        return True
    p = Path(file)
    resolved = str((p if p.is_absolute() else (target / p)).resolve())
    return resolved in changed


def _rel_to_target(target: Path, file: str) -> str:
    """``file`` (absolute, or relative to ``target``) as a /-separated path relative to ``target``.

    A path outside ``target`` comes back as given — an ignore glob never accidentally matches it.
    """
    p = Path(file)
    try:
        rel = (p if p.is_absolute() else (target / p)).resolve().relative_to(target.resolve())
    except (ValueError, OSError):
        return p.as_posix()
    return rel.as_posix()


def _ignore_match(rel_posix: str, ignore: Sequence[str]) -> bool:
    """True when a target-relative path matches any configured ignore glob.

    Globs use ``fnmatch`` semantics, where ``*`` crosses ``/`` (so ``**`` and ``*`` behave alike);
    a leading ``**/`` also matches at the tree root, so ``**/dist/**`` excludes both ``dist/x``
    and ``pkg/dist/x``. Deterministic in the configured globs — no environment input."""
    for raw in ignore:
        pat = str(raw).strip().lstrip("/")
        if not pat:
            continue
        if fnmatch.fnmatch(rel_posix, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(rel_posix, pat[3:]):
            return True
    return False


def _with_exclusion_report(
    gr: GateResult,
    ignore: Sequence[str],
    ignore_rules: Sequence[str] = (),
    excluded: int = 0,
    advisories: Sequence[tuple[str, str, int]] = (),
) -> GateResult:
    """Surface every configured scanner exclusion on the gate result — never silent.

    Security invariant: an exclusion from the committed ``scan.yaml`` always appears in the gate
    output — the configured globs/rules land in ``details`` and one informational findings line
    counts what they excluded. ``advisories`` holds the *accepted* dependency advisories as
    ``(id, reason, count)`` triples; each acceptance is named with its reason and count.
    Applied only after the gate's status is computed, so the report itself never changes a
    verdict."""
    if not ignore and not ignore_rules and not advisories:
        return gr
    gr.details["excluded_count"] = excluded
    parts: list[str] = []
    if ignore:
        gr.details["ignored_globs"] = list(ignore)
        parts.append("globs " + ", ".join(ignore))
    if ignore_rules:
        gr.details["ignored_rules"] = list(ignore_rules)
        parts.append("rules " + ", ".join(ignore_rules))
    if advisories:
        gr.details["accepted_advisories"] = [
            {"id": vid, "reason": reason, "count": count} for vid, reason, count in advisories
        ]
        parts.append(
            "advisories "
            + ", ".join(
                f"{vid} ({count} finding(s) accepted — {reason})"
                for vid, reason, count in advisories
            )
        )
    gr.findings.append(
        f"scan.yaml exclusions applied ({excluded} finding(s) excluded): " + "; ".join(parts)
    )
    return gr


# Secret scanners tried in order of preference. betterleaks is the maintained Gitleaks successor;
# gitleaks is the fallback. Both share the same ``dir`` CLI and JSON schema (File/RuleID/StartLine),
# so one command + one parser serves both — betterleaks writes ``null`` for an empty report where
# gitleaks writes ``[]``, handled below. Neither installed → the gate is quarantined.
_SECRET_TOOLS = ("betterleaks", "gitleaks")


def _secret_tool() -> str | None:
    return next((t for t in _SECRET_TOOLS if shutil.which(t)), None)


# The engine's own private-key line format: ``ed25519-priv <base64-raw-seed-32>``. A real seed is
# 44 base64 chars; requiring ≥40 avoids matching the format's *mention* in docs or source literals
# while catching any actual committed key material.
_PRIVATE_KEY_RE = re.compile(r"^ed25519-priv\s+[A-Za-z0-9+/=]{40,}\s*$")
_MAX_CORE_SCAN_BYTES = 1_000_000


def _scan_candidates(target: Path, ignore: Sequence[str] = ()) -> list[Path]:
    """Files the core secret check reads: git-tracked under ``target``, else a bounded walk.

    Configured ``ignore`` globs (the committed ``scan.yaml``) are honored as a walk filter in
    both branches — the check itself still runs on every non-ignored file and can never be
    disabled by configuration."""

    def keep(p: Path) -> bool:
        if not ignore:
            return True
        try:
            rel = p.relative_to(target).as_posix()
        except ValueError:
            rel = p.as_posix()
        return not _ignore_match(rel, ignore)

    try:
        res = subprocess.run(
            ["git", "ls-files", "-z"], cwd=target, capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            return [target / f for f in res.stdout.split("\0") if f and keep(target / f)]
    except OSError:
        pass
    skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}
    return [p for p in target.rglob("*") if p.is_file() and not (skip & set(p.parts)) and keep(p)]


def _core_private_key_findings(
    target: Path, changed: set[str] | None, ignore: Sequence[str] = ()
) -> list[str]:
    """Core fallback scan for committed ``ed25519-priv`` material.

    Runs with or without an external secret scanner installed — the engine's own key format
    is never quarantined away. ``ignore`` globs only filter which files the walk reads; the
    check still fires on key material anywhere outside them. Deterministic, local, read-only.
    """
    findings: list[str] = []
    for f in _scan_candidates(target, ignore):
        if not _in_scope(target, str(f), changed):
            continue
        try:
            if f.stat().st_size > _MAX_CORE_SCAN_BYTES:
                continue
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _PRIVATE_KEY_RE.match(line.strip()):
                try:
                    shown = str(f.relative_to(target))
                except ValueError:
                    shown = str(f)
                findings.append(f"ed25519-priv private-key material in {shown}:{lineno}")
                break  # one finding per file names it; no need to enumerate every line
        if len(findings) >= 10:
            break
    return findings


def secret_scan(
    target: Path,
    changed: set[str] | None = None,
    ignore: Sequence[str] = (),
    ignore_rules: Sequence[str] = (),
) -> GateResult:
    """Scan the working tree for committed secrets.

    A core check for the engine's own ``ed25519-priv`` key material ALWAYS runs first
    — it needs no external binary and is never quarantined or configured away. For the
    broader ruleset the gate prefers betterleaks (the maintained Gitleaks successor), falling
    back to gitleaks — both share the ``dir`` CLI and JSON schema. Only the external portion
    is quarantined when neither binary is installed.

    ``ignore`` (path globs) and ``ignore_rules`` (scanner rule ids) come from the committed
    ``scan.yaml``; every applied exclusion is surfaced on the result — never silent. The core
    private-key check honors ``ignore`` only as a walk filter and still fires on key material
    anywhere outside the ignored trees."""
    excluded = 0
    core = _core_private_key_findings(target, changed, ignore)
    tool = _secret_tool()
    if tool is None:
        if core:
            gr = GateResult(
                gate="secret_scan",
                status=STATUS_FAIL,
                tool="3pwr-core",
                details={"count": len(core)},
                findings=core,
            )
            return _with_exclusion_report(gr, ignore, ignore_rules, excluded)
        q = _quarantine("secret_scan", "betterleaks/gitleaks")
        q.findings.append("core ed25519-priv private-key check ran clean")
        return _with_exclusion_report(q, ignore, ignore_rules, excluded)
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "secrets.json"
        res = run_cmd(
            f"{tool} dir {target} --no-banner --exit-code 1 "
            f"--report-format json --report-path {report}",
            cwd=target,
        )
        external: list[str] = []
        if report.exists():
            try:
                suppressed_rules = set(ignore_rules)
                # betterleaks emits `null` for no findings; gitleaks emits `[]`. Coerce both to [].
                for f in json.loads(report.read_text(encoding="utf-8") or "null") or []:
                    file, rule = f.get("File", ""), f.get("RuleID", "secret")
                    if rule in suppressed_rules or _ignore_match(
                        _rel_to_target(target, file), ignore
                    ):
                        excluded += 1
                        continue
                    if not _in_scope(target, file, changed):
                        continue
                    external.append(f"{rule} in {file or '?'}:{f.get('StartLine', '?')}")
                    if len(core) + len(external) >= 10:
                        break
            except (ValueError, OSError, TypeError):
                pass
        findings: list[str] = list(core) + external
        if res.returncode not in (0, 1):
            # scanner error (not a clean pass/fail) → quarantine the external portion rather
            # than block — but committed key material found by the core check still fails.
            if core:
                gr = GateResult(
                    gate="secret_scan",
                    status=STATUS_FAIL,
                    tool="3pwr-core",
                    details={"count": len(core)},
                    findings=core,
                )
                return _with_exclusion_report(gr, ignore, ignore_rules, excluded)
            return _with_exclusion_report(
                _quarantine("secret_scan", tool), ignore, ignore_rules, excluded
            )
        rc_fail = res.returncode == 1
        if rc_fail and excluded and not external:
            # Every scanner finding was excluded by the committed scan.yaml (reported below);
            # the tool's exit code alone no longer blocks.
            rc_fail = False
        # When diff-scoped, only changed-file findings block (brownfield).
        in_scope = bool(findings) if changed is not None else (rc_fail or bool(core))
        status = STATUS_FAIL if in_scope else STATUS_PASS
        gr = GateResult(
            gate="secret_scan",
            status=status,
            tool=tool,
            duration_ms=res.duration_ms,
            details={"count": len(findings)},
            findings=findings,
        )
        return _with_exclusion_report(gr, ignore, ignore_rules, excluded)


def _accepted_advisories(advisories: Sequence[Mapping[str, object]]) -> dict[str, str]:
    """Advisory ids currently eligible to suppress a dependency finding, mapped to their reasons.

    Fail-closed: an entry suppresses only when it carries a non-empty (non-whitespace) reason
    and has not expired — a missing/blank reason, a past ``until``, or an unparseable ``until``
    suppresses nothing. ``until`` accepts an ISO-8601 date or timestamp; a date-only value is
    treated as UTC midnight (the acceptance lapses at the start of that day)."""
    accepted: dict[str, str] = {}
    now = datetime.now(timezone.utc)
    for adv in advisories:
        vid = str(adv.get("id") or "").strip()
        reason = str(adv.get("reason") or "").strip()
        if not vid or not reason:
            continue
        until_raw = str(adv.get("until") or "").strip()
        if until_raw:
            until = parse_iso(until_raw)
            if until is None:
                continue  # unparseable expiry never suppresses (fail-closed)
            if until.tzinfo is None:
                # parse_iso yields a naive datetime for date-only values; compare in UTC so
                # the expiry check is stable regardless of the machine's local zone.
                until = until.replace(tzinfo=timezone.utc)
            if until < now:
                continue
        accepted[vid] = reason
    return accepted


def dependency_scan(
    target: Path,
    ignore: Sequence[str] = (),
    advisories: Sequence[Mapping[str, object]] = (),
) -> GateResult:
    """Scan dependency manifests/lockfiles for known vulnerabilities with osv-scanner.

    ``ignore`` globs (the committed ``scan.yaml``) drop findings whose *source manifest* path
    matches. ``advisories`` is the committed allowlist of accepted vulnerability ids
    (``{id, reason, until}``): a matching finding is suppressed only while the entry carries a
    non-empty reason and has not passed its optional ``until`` expiry — expired or reason-less
    entries suppress nothing. Every applied exclusion and every accepted advisory (id, reason,
    count) is surfaced on the result — never silent."""
    accepted = _accepted_advisories(advisories)
    if not shutil.which("osv-scanner"):
        return _with_exclusion_report(_quarantine("dependency_scan", "osv-scanner"), ignore)
    with tempfile.TemporaryDirectory() as td:
        report = Path(td) / "osv.json"
        res = run_cmd(f"osv-scanner --format json --output-file {report} -r {target}", cwd=target)
        findings: list[str] = []
        excluded = 0
        accepted_hits: dict[str, int] = {}
        if report.exists():
            try:
                data = json.loads(report.read_text(encoding="utf-8") or "{}")
                for r in data.get("results", []):
                    src = (r.get("source") or {}).get("path", "") or ""
                    drop = bool(src) and _ignore_match(_rel_to_target(target, src), ignore)
                    for pkg in r.get("packages", []):
                        name = pkg.get("package", {}).get("name", "?")
                        for v in pkg.get("vulnerabilities", [])[:10]:
                            if drop:
                                excluded += 1
                                continue
                            vid = str(v.get("id") or "VULN")
                            if vid in accepted:
                                excluded += 1
                                accepted_hits[vid] = accepted_hits.get(vid, 0) + 1
                                continue
                            findings.append(f"{vid} in {name}")
            except (ValueError, OSError):
                pass
        if res.returncode == 0:
            status = STATUS_PASS
        elif res.returncode == 1:
            # Every vulnerable source was excluded/accepted by the committed scan.yaml (reported
            # below) → not blocking; an unparsed red exit without exclusions stays a
            # conservative fail.
            status = STATUS_PASS if (excluded and not findings) else STATUS_FAIL
        else:  # e.g. nothing to scan / scanner error → quarantine, do not false-fail
            return _with_exclusion_report(_quarantine("dependency_scan", "osv-scanner"), ignore)
        gr = GateResult(
            gate="dependency_scan",
            status=status,
            tool="osv-scanner",
            duration_ms=res.duration_ms,
            details={"count": len(findings)},
            findings=findings[:10],
        )
        return _with_exclusion_report(
            gr,
            ignore,
            excluded=excluded,
            advisories=[(vid, accepted[vid], n) for vid, n in accepted_hits.items()],
        )


def sast_scan(
    target: Path,
    rules_path: Path,
    changed: set[str] | None = None,
    ignore: Sequence[str] = (),
) -> GateResult:
    """Static analysis with semgrep against a local, offline ruleset.

    ``ignore`` globs (the committed ``scan.yaml``) become repeatable semgrep ``--exclude``
    flags AND are applied to the parsed results — deterministic across semgrep versions.
    Every applied exclusion is surfaced on the result — never silent."""
    if not shutil.which("semgrep") or not rules_path.exists():
        return _with_exclusion_report(_quarantine("sast", "semgrep"), ignore)
    excludes = "".join(f"--exclude {shlex.quote(str(g))} " for g in ignore)
    res = run_cmd(
        f"semgrep scan --quiet --json {excludes}--config {rules_path} {target}", cwd=target
    )
    findings: list[str] = []
    raw_count = 0
    excluded = 0
    try:
        for r in json.loads(res.stdout or "{}").get("results") or []:
            raw_count += 1
            path = r.get("path", "")
            if _ignore_match(_rel_to_target(target, path), ignore):
                excluded += 1
                continue
            if not _in_scope(target, path, changed):
                continue  # brownfield: only changed-file findings block
            line = r.get("start", {}).get("line", "?")
            findings.append(f"{r.get('check_id', 'rule')} at {path or '?'}:{line}")
            if len(findings) >= 20:
                break
    except ValueError:
        pass
    if res.returncode >= 2 and raw_count == 0:  # semgrep itself errored
        return _with_exclusion_report(_quarantine("sast", "semgrep"), ignore)
    status = STATUS_FAIL if findings else STATUS_PASS
    gr = GateResult(
        gate="sast",
        status=status,
        tool="semgrep",
        duration_ms=res.duration_ms,
        details={"count": len(findings)},
        findings=findings,
    )
    return _with_exclusion_report(gr, ignore, excluded=excluded)
