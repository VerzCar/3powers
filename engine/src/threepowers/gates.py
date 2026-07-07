"""The deterministic gate engine — runs the suite cheapest-first (3PWR-FR-026).

Order: format → lint → types → tests (+ diff-coverage) → mutation → spec-conformance.
Which gates are *required* (and their thresholds) is read entirely from the
risk-tier table (3PWR-FR-032/049): a gate is never satisfied by weakening it. The
result is one normalized verdict (3PWR-FR-033) whose every failure is actionable
(3PWR-FR-034).
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Protocol

from . import adapters, covdiff, design, gaming, mutation, scanners, speclock
from .adapters import CmdResult
from .conformance import conformance_failures, extract_spec, regression_gate, run_conformance
from .config import Settings, tier_config
from .ledger import Ledger
from .verdict import (
    GATE_ORDER,
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_SKIP,
    GateResult,
    Verdict,
    failure,
)

# Design-oracle gate → its actionable failure class (3PWR-FR-009/034).
_DESIGN_FAILURE_CLASS = {
    "visual_regression": "visual_regression",
    "a11y_scan": "a11y_violation",
    "contract_check": "contract_break",
    "component_contract": "component_contract",
}

# Gates executed by invoking an adapter command vs. computed in the core.
_ADAPTER_GATES = {"format", "lint", "types", "tests", "mutation"}
_CORE_GATES = {
    "spec_integrity",
    "diff_coverage",
    "sast",
    "dependency_scan",
    "secret_scan",
    "gate_gaming",
    "spec_conformance",
}

# Best-effort start-time tool labels for the core-computed gates (GATEPIPE-FR-001). The finish
# event's GateResult.tool stays authoritative — e.g. secret_scan may resolve to gitleaks.
_CORE_TOOL_LABELS = {
    "spec_integrity": "3pwr",
    "diff_coverage": "3pwr-covdiff",
    "sast": "semgrep",
    "dependency_scan": "osv-scanner",
    "secret_scan": "betterleaks",
    "gate_gaming": "3pwr",
    "spec_conformance": "3pwr",
    "defect_regression": "3pwr",
    "mutation": "mutation",
}


class GateObserver(Protocol):
    """The gate engine's start/finish event seam (GATEPIPE-FR-001).

    ``run_gates`` calls ``gate_started`` when a required gate begins and ``gate_finished`` with the
    gate's result when it completes — in execution order, every start before its own finish. A
    renderer (the live pipeline view) consumes these; the observer never enters the verdict
    computation (GATEPIPE-NFR-001, 3PWR-NFR-001)."""

    def gate_started(self, gate: str, tool: str) -> None:
        """A required gate is about to run; ``tool`` is the best-effort tool label."""

    def gate_finished(self, result: GateResult) -> None:
        """The gate completed with ``result`` (pass, fail, or skip)."""


def _gate_tool_label(gate: str, manifest: dict[str, Any]) -> str:
    """The best-effort tool label for a gate's start event (GATEPIPE-FR-001).

    Adapter gates take the manifest's parser/command name; core gates use the static label table.
    Purely presentational — the finish event's ``GateResult.tool`` stays authoritative."""
    if gate in _ADAPTER_GATES:
        spec = adapters.gate_spec(manifest, gate) or {}
        tokens = str(spec.get("parser") or spec.get("cmd") or "").split()
        return tokens[0] if tokens else ""
    return _CORE_TOOL_LABELS.get(gate, "")


def _git_commit(repo_root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()
        return out
    except OSError:
        return ""


# Output signatures of "the tool isn't installed" — distinct from a genuine gate failure. Covers
# `npx --no-install`, uv/npm shims, POSIX/Windows shells, and our own run_cmd FileNotFoundError.
_MISSING_TOOL_SIGNS = (
    "canceled due to missing packages",  # npx --no-install
    "could not determine executable",  # npx
    "command not found",
    "not recognized as an internal or external command",  # windows
    "no such file or directory",
    "tool not found",  # adapters.run_cmd FileNotFoundError → returncode 127
    ": not found",  # sh: <tool>: not found
)


def _looks_missing_tool(res: CmdResult) -> bool:
    """Heuristic: did this command fail because its executable is absent (not a real gate failure)?"""
    if res.returncode == 127:
        return True
    blob = (res.stdout + "\n" + res.stderr).lower()
    return any(sig in blob for sig in _MISSING_TOOL_SIGNS)


def _missing_tool_finding(
    manifest: dict[str, Any] | None, spec: dict[str, Any], res: CmdResult
) -> tuple[str, str, str] | None:
    """``(tool, actionable finding, install-cmd)`` when a gate failed because its tool is missing.

    Turns raw toolchain noise into a fix the user can act on (3PWR-FR-034); only fires for a gate that
    declares ``requires:`` AND whose failure output signals an absent tool, so a genuine gate failure
    is never mislabeled. ``install-cmd`` is ``""`` when the adapter declares none."""
    if manifest is None:
        return None
    tool = adapters.gate_requires(spec)
    if not tool or not _looks_missing_tool(res):
        return None
    install = adapters.install_hint(manifest, tool) or ""
    msg = (
        f"{tool} is not installed — run: {install}"
        if install
        else f"{tool} is not installed or not on PATH — install it and re-run"
    )
    return tool, msg, install


def _result_from_cmd(
    gate: str, spec: dict[str, Any], res: CmdResult, manifest: dict[str, Any] | None = None
) -> GateResult:
    status = STATUS_PASS if res.ok else STATUS_FAIL
    details: dict[str, Any] = {"returncode": res.returncode}
    findings = [] if res.ok else res.tail()
    if not res.ok:
        if spec and spec.get("fix_cmd"):
            # Surface the configured manual fix in the failure panel (GATEPIPE-FR-003).
            # Rendering only — the engine never runs it here.
            details["fix_cmd"] = str(spec["fix_cmd"])
        hit = _missing_tool_finding(manifest, spec, res)
        if hit:
            tool, msg, install = hit
            details["missing_tool"] = tool
            if install:
                details["install_hint"] = install
            findings = [msg, *findings]  # lead with the actionable fix
    return GateResult(
        gate=gate,
        status=status,
        tool=str(spec.get("parser") or spec.get("cmd", "")).split()[0] if spec else "",
        duration_ms=res.duration_ms,
        details=details,
        findings=findings,
    )


# --------------------------------------------------------------------------- opt-in auto-fix (GATECFG)
def _worktree_snapshot(cwd: Path) -> dict[str, str]:
    """A ``{path: sha256}`` snapshot of the modified/untracked files under ``cwd`` (GATECFG-FR-008).

    Diffing a pre-/post-fix snapshot yields exactly the paths a ``fix_cmd`` touched, so they can
    join the run's produced set and ride the stage commit (ref GITX-FR-008). Degrades to ``{}``
    outside a git repository — auto-fix still fixes and re-checks; only the produced-paths record
    is empty. Design note: local by intention — the judiciary never imports the executive's
    runner module for this."""
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return {}
    if proc.returncode != 0:
        return {}
    state: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        rel = line[3:].strip().strip('"')
        if " -> " in rel:  # a rename: XY old -> new
            rel = rel.split(" -> ", 1)[1].strip().strip('"')
        fp = cwd / rel
        try:
            state[rel] = hashlib.sha256(fp.read_bytes()).hexdigest() if fp.is_file() else ""
        except OSError:
            state[rel] = ""
    return state


def _paths_changed(pre: dict[str, str], post: dict[str, str]) -> list[str]:
    """The paths whose content changed between two snapshots (sorted; either direction counts)."""
    changed = {p for p, h in post.items() if pre.get(p) != h}
    changed |= {p for p in pre if p not in post}
    return sorted(changed)


def _try_auto_fix(spec: dict[str, Any], cmd: str, target: Path) -> tuple[CmdResult, dict[str, Any]]:
    """Run the gate's configured ``fix_cmd`` and re-check, opt-in only (GATECFG-FR-008).

    Only a fixable gate (format/lint — GATECFG-FR-006) with a failing check and a configured fix
    reaches this. Returns the re-check's :class:`CmdResult` plus the extra details for the gate's
    result: on a passing re-check, ``auto_fixed`` (the tool that fixed) and ``fixed_paths`` (what
    it touched, for the run's produced set); on a failing one, nothing extra — the failure reports
    normally."""
    fix_cmd = str(spec["fix_cmd"])
    pre = _worktree_snapshot(target)
    adapters.run_cmd(fix_cmd, cwd=target, shell=adapters.wants_shell(spec))
    recheck = adapters.run_cmd(cmd, cwd=target, shell=adapters.wants_shell(spec))
    if not recheck.ok:
        return recheck, {}
    tool = str(spec.get("parser") or fix_cmd).split()[0]
    return recheck, {
        "auto_fixed": tool,
        "fixed_paths": _paths_changed(pre, _worktree_snapshot(target)),
    }


def fixed_paths(verdict: dict[str, Any]) -> list[str]:
    """Every path an ``--auto-fix`` run fixed, from a verdict dict (GATECFG-FR-008).

    The paths ride each green auto-fixed gate's ``details.fixed_paths``; the caller appends them
    to the run's produced set so the stage commit picks them up (ref GITX-FR-008)."""
    out: list[str] = []
    for g in verdict.get("gates") or []:
        for p in (g.get("details") or {}).get("fixed_paths") or []:
            if p not in out:
                out.append(p)
    return sorted(out)


_MUTABLE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go"}


def _is_test_file(rel: str) -> bool:
    p = "/" + rel.replace("\\", "/")
    name = Path(rel).name
    return (
        name.startswith("test_")
        or Path(rel).stem.endswith("_test")
        or ".test." in name
        or ".spec." in name
        or any(h in p for h in ("/tests/", "/e2e/", "/integration/"))
    )


def _diff_mutation_paths(settings: Settings, base: str | None, target: Path) -> list[str]:
    """Changed *source* files to mutate under diff-scoped mutation (HARDN-FR-011).

    Repo-relative changed files vs ``base``, kept when they are mutatable source (by
    suffix) and not test files — mutating the tests themselves grades nothing.
    """
    return [
        rel
        for rel in sorted(covdiff.changed_files(settings.root, base, target))
        if Path(rel).suffix in _MUTABLE_SUFFIXES and not _is_test_file(rel)
    ]


def _augment_gates(required: list[str], work_kind: list[str], settings: Settings) -> list[str]:
    """Union the gates an inferred work-kind pulls in onto the tier's list (3PWR-FR-058).

    Only ever *adds* — a defect adds the regression gate (3PWR-FR-008), design work adds the
    catalog's design oracles (3PWR-FR-009). A tier gate is never removed (3PWR-FR-032).
    """
    if not work_kind:
        return required
    out = list(required)
    if "defect" in work_kind and "defect_regression" not in out:
        out.append("defect_regression")
    if "design" in work_kind:
        for gate in design.selected_gates(settings):
            if gate not in out:
                out.append(gate)
    return out


def _no_spec_skip(gate: str) -> GateResult:
    """A SKIP for a spec-bound gate when a brownfield report-only/diff-scope run has no spec yet
    (3PWR-FR-051/052). Reported as skipped, never silently passed (3PWR-FR-032)."""
    return GateResult(
        gate=gate,
        status=STATUS_SKIP,
        findings=["no spec resolved — brownfield report-only/diff-scope (3PWR-FR-052)"],
    )


class PrerequisiteError(RuntimeError):
    """A required tool of a non-optional gate is absent — raised BEFORE any gate runs (GDIAG-FR-004).

    Carries ``missing`` as ``(tool, install_hint)`` pairs; ``str(exc)`` is the ready-to-print
    prerequisites block with one install hint per missing tool, taken from the adapter manifest's
    declarative ``toolchain:`` section — the core never invents a hint (GDIAG-NFR-002). The caller
    exits on the setup path (never a gate verdict)."""

    def __init__(self, missing: list[tuple[str, str]]) -> None:
        self.missing = missing
        width = max((len(t) for t, _ in missing), default=0)
        lines = ["⚠ prerequisites missing — install before re-running:"]
        for tool, hint in missing:
            lines.append(
                f"  {tool:<{width}}  {hint or '(no install hint declared — install it and re-run)'}"
            )
        super().__init__("\n".join(lines))


def missing_prerequisites(
    manifest: dict[str, Any], required: list[str], target: Path
) -> list[tuple[str, str]]:
    """The ``(tool, install_hint)`` pairs missing for the run's NON-OPTIONAL gates (GDIAG-FR-004/005).

    Probes each distinct tool a required adapter gate declares via ``requires:``, using the
    manifest's declarative ``toolchain:`` probe (adapters.probe_tool). Quarantine-safe gates keep
    their existing behavior and are never probed here: ``mutation`` (opt-in, skips when unwired)
    and the design oracles (quarantined when their tool is absent — 3PWR-NFR-015). ``tests`` is
    probed whenever ``diff_coverage`` is required, since diff-coverage forces the test run.
    Deterministic given the manifest + the local toolchain; hints come only from manifest data."""
    probe_gates = [g for g in required if g in _ADAPTER_GATES and g != "mutation"]
    if "diff_coverage" in required and "tests" not in probe_gates:
        probe_gates.append("tests")
    missing: list[tuple[str, str]] = []
    seen: set[str] = set()
    for gate in probe_gates:
        spec = adapters.gate_spec(manifest, gate)
        if not spec or not adapters.command_of(spec):
            continue  # the gate skips anyway — nothing to require
        tool = adapters.gate_requires(spec)
        if not tool or tool in seen:
            continue
        seen.add(tool)
        if not adapters.probe_tool(manifest, tool, cwd=target):
            missing.append((tool, adapters.install_hint(manifest, tool) or ""))
    return missing


def run_gates(
    settings: Settings,
    target: Path,
    *,
    tier: str,
    spec_path: Path | None,
    adapter_name: str | None = None,
    base: str | None = None,
    allow_mutation: bool = False,
    paths: list[str] | None = None,
    report_only: bool = False,
    diff_scope: bool = False,
    work_kind: list[str] | None = None,
    observer: GateObserver | None = None,
    auto_fix: bool = False,
    manifest: dict[str, Any] | None = None,
) -> Verdict:
    """Run the tier's gate suite cheapest-first and return the one normalized verdict (3PWR-FR-026/033).

    ``observer``, when given, receives a start event before each required gate runs and a finish
    event with its :class:`GateResult` — the seam the live pipeline view renders from
    (GATEPIPE-FR-001). It is presentation-only and never enters the verdict (GATEPIPE-NFR-001).
    ``auto_fix`` (opt-in only — GATECFG-FR-007) lets a failing format/lint check run its
    configured ``fix_cmd`` and re-check (GATECFG-FR-008); no other gate ever runs a fix
    (GATECFG-FR-006). ``manifest``, when given, is the caller-assembled effective gate
    configuration (``gates.yaml`` overrides + auto-detection — GATECFG-FR-003, via
    :func:`adapters.effective_gates`); absent, the adapter manifest is loaded with the project's
    ``gates.yaml`` merged (GATECFG-FR-001). Raises :class:`PrerequisiteError` before any gate runs
    when a required tool of a non-optional gate is absent (GDIAG-FR-004); a ``report_only`` run
    never hard-stops."""
    tiers = settings.load_risk_tiers()
    tcfg = tier_config(tiers, tier)
    required: list[str] = list(tcfg.get("gates", []))
    # Work-kind shaping (3PWR-FR-058): an inferred kind can *add* gates — a regression gate for a
    # defect (3PWR-FR-008), the design oracles for design work (3PWR-FR-009) — but never removes a
    # tier gate (inference shapes, never weakens; 3PWR-FR-032).
    kinds = list(work_kind or [])
    required = _augment_gates(required, kinds, settings)

    # Opt-in diff-scoped mutation (HARDN-FR-011): a tier configured with `diff_mutation: true`
    # runs the mutation gate over the CHANGED files whenever a --base is given — machine-graded
    # test quality on every change, without the full-sweep cost. Only ever ADDS a gate
    # (3PWR-FR-032); with the knob unset, behavior is unchanged.
    diff_mutation = bool(tcfg.get("diff_mutation")) and base is not None
    if diff_mutation and "mutation" not in required:
        required.append("mutation")

    # Brownfield diff-scope: block only on new/changed files (3PWR-FR-051). When set,
    # the file-based scanners count only findings in files changed vs. ``base``.
    changed_scope: set[str] | None = None
    if diff_scope:
        changed_scope = {
            str((settings.root / rel).resolve())
            for rel in covdiff.changed_files(settings.root, base, target)
        }

    adapter_name = adapter_name or adapters.detect_adapter(settings, target)
    if manifest is None:
        manifest = adapters.load_adapter(settings, adapter_name)

    # Prerequisites pre-check (GDIAG-FR-004/005): every required tool of a non-optional gate is
    # probed BEFORE any gate command runs — a missing one stops the run on the setup path with
    # per-tool install hints, never a misleading gate-red. Quarantine-safe gates (mutation, the
    # design oracles) keep their skip/quarantine behavior; a report-only run is the brownfield
    # on-ramp and never hard-stops — its gates surface missing tools per-gate as before.
    if not report_only:
        absent = missing_prerequisites(manifest, required, target)
        if absent:
            raise PrerequisiteError(absent)

    # Brownfield adoption (3PWR-FR-051/052): report-only / diff-scope runs before a repo has any
    # 3Powers spec, so `spec_path` may be None — the two spec-bound gates then SKIP (below).
    spec_id, _ = extract_spec(spec_path) if spec_path is not None else ("", set())
    verdict = Verdict(
        spec_id=spec_id,
        tier=tier,
        adapter=adapter_name,
        commit=_git_commit(settings.root),
        report_only=report_only,
        work_kind=kinds,
    )

    def _add(gr: GateResult) -> None:
        """Record ``gr`` on the verdict and fire the observer's finish event (GATEPIPE-FR-001)."""
        verdict.add(gr)
        if observer is not None:
            observer.gate_finished(gr)

    # Run tests (with coverage) if either the tests or diff_coverage gate is required.
    coverage_path: Path | None = None
    need_tests = "tests" in required or "diff_coverage" in required

    for gate in GATE_ORDER:
        if gate not in required:
            continue

        # The start event precedes the gate's own execution (GATEPIPE-FR-001) — the live pipeline
        # shows the row as running before the (possibly long) command produces a result.
        if observer is not None:
            observer.gate_started(gate, _gate_tool_label(gate, manifest))

        if gate in _ADAPTER_GATES:
            spec = adapters.gate_spec(manifest, gate)
            if not spec:
                _add(
                    GateResult(
                        gate=gate,
                        status=STATUS_SKIP,
                        findings=[f"adapter '{adapter_name}' declares no '{gate}' gate"],
                    )
                )
                continue
            if gate == "mutation":
                if not allow_mutation and not diff_mutation:
                    # Expensive gate — opt in with --mutation; full sweep is scheduled
                    # (3PWR-NFR-002). Reported as skipped, never silently passed.
                    _add(
                        GateResult(
                            gate="mutation",
                            status=STATUS_SKIP,
                            tool="mutation",
                            findings=["mutation wired; pass --mutation to enforce"],
                        )
                    )
                    continue
                mut_paths = paths
                if diff_mutation and not paths:
                    # Scope to the changed source files (HARDN-FR-011); the tier's
                    # mutation_score stays the single source of the threshold (3PWR-FR-032).
                    mut_paths = _diff_mutation_paths(settings, base, target)
                    if not mut_paths:
                        _add(
                            GateResult(
                                gate="mutation",
                                status=STATUS_SKIP,
                                tool="mutation",
                                findings=["diff mutation: no changed source files to mutate"],
                            )
                        )
                        continue
                _add(
                    mutation.mutation_gate(
                        target,
                        spec,
                        threshold=float(tcfg.get("mutation_score", 0)),
                        paths=mut_paths,
                    )
                )
                continue
            cmd = adapters.command_of(spec)
            if not cmd:
                _add(
                    GateResult(
                        gate=gate,
                        status=STATUS_SKIP,
                        findings=[f"adapter declares no command for '{gate}'"],
                    )
                )
                continue
            res = adapters.run_cmd(cmd, cwd=target, shell=adapters.wants_shell(spec))
            fix_details: dict[str, Any] = {}
            if not res.ok and auto_fix and gate in adapters.AUTOFIX_GATES and spec.get("fix_cmd"):
                # Opt-in auto-fix (GATECFG-FR-008): fix, re-check; a green re-check passes the
                # gate and records what the fix touched. Never fires for any other gate
                # (GATECFG-FR-006) and never without --auto-fix (GATECFG-FR-007/009).
                res, fix_details = _try_auto_fix(spec, cmd, target)
            gr = _result_from_cmd(gate, spec, res, manifest)
            gr.details.update(fix_details)
            if gate == "tests" and spec.get("coverage_path"):
                coverage_path = target / spec["coverage_path"]
            _add(gr)

        elif gate == "spec_integrity":
            # The spec is the law — after human approval its full-document hash is frozen in
            # the signed ledger; a silent mutation fails fast, before any test runs
            # (SLOCK-FR-003/004). Skips (never blocks) a not-yet-approved spec.
            if spec_path is None:
                _add(_no_spec_skip("spec_integrity"))
            else:
                _add(
                    speclock.integrity_gate(
                        Ledger(settings.ledger_path).entries(), spec_id, settings.root, spec_path
                    )
                )

        elif gate == "diff_coverage":
            _add(_diff_coverage_gate(settings, target, manifest, tcfg, coverage_path, base, paths))

        elif gate == "sast":
            _add(
                scanners.sast_scan(
                    target, settings.dir / "config" / "semgrep-rules.yml", changed_scope
                )
            )

        elif gate == "dependency_scan":
            # Dependency vulnerabilities are not file-local; never diff-scoped.
            _add(scanners.dependency_scan(target))

        elif gate == "secret_scan":
            _add(scanners.secret_scan(target, changed_scope))

        elif gate == "gate_gaming":
            _add(gaming.detect_gaming(settings.root, target, base))

        elif gate == "spec_conformance":
            if spec_path is None:
                _add(_no_spec_skip("spec_conformance"))
            else:
                roots = _test_roots(manifest, target)
                gr = run_conformance(
                    spec_path,
                    roots,
                    required_layers=tcfg.get("required_layers"),
                    conformance_cfg=manifest.get("conformance"),
                )
                _add(gr)
                verdict.failures.extend(conformance_failures(gr))

        elif gate == "defect_regression":
            # Work-kind: defect — a fix must ship a failing regression test (3PWR-FR-008).
            if spec_path is None:
                _add(_no_spec_skip("defect_regression"))
            else:
                _add(regression_gate(spec_path, _test_roots(manifest, target)))

        elif gate in design.DESIGN_GATES:
            # Work-kind: design — adapter-supplied design oracle, quarantined if unwired (3PWR-FR-009).
            _add(design.design_gate(gate, manifest, adapter_name, target))

    # Make sure tests actually ran when required even if listed only via diff_coverage.
    if need_tests and not any(g.gate == "tests" for g in verdict.gates):
        spec = adapters.gate_spec(manifest, "tests")
        cmd = adapters.command_of(spec) if spec else None
        if spec and cmd:
            if observer is not None:
                observer.gate_started("tests", _gate_tool_label("tests", manifest))
            res = adapters.run_cmd(cmd, cwd=target, shell=adapters.wants_shell(spec))
            _add(_result_from_cmd("tests", spec, res, manifest))

    # Actionable failures for any failed gate (3PWR-FR-034).
    for g in verdict.gates:
        if g.status != STATUS_FAIL:
            continue
        if g.gate == "mutation":
            verdict.failures.append(
                failure(
                    "surviving_mutant",
                    gate=g.gate,
                    detail=f"{g.details.get('survived')} mutant(s) survived — "
                    f"score {g.details.get('mutation_score')}% < {g.details.get('threshold')}% "
                    "(each surviving mutant is a missing assertion)",
                )
            )
        elif g.gate in _ADAPTER_GATES:
            verdict.failures.append(
                failure(
                    "gate_failed",
                    gate=g.gate,
                    tool=g.tool,
                    detail="; ".join(g.findings[-3:]) or "non-zero exit",
                )
            )
        elif g.gate == "sast":
            verdict.failures.append(
                failure(
                    "sast_finding",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3]) or "static-analysis finding",
                )
            )
        elif g.gate == "secret_scan":
            verdict.failures.append(
                failure(
                    "secret_exposed",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3]) or "secret detected",
                )
            )
        elif g.gate == "dependency_scan":
            verdict.failures.append(
                failure(
                    "vulnerable_dependency",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3]) or "vulnerable dependency",
                )
            )
        elif g.gate == "gate_gaming":
            verdict.failures.append(
                failure(
                    "gate_gaming",
                    gate=g.gate,
                    detail="; ".join(g.findings[:3])
                    or "suppression detected — human review required",
                )
            )
        elif g.gate == "defect_regression":
            verdict.failures.append(
                failure(
                    "missing_regression_test",
                    gate=g.gate,
                    detail="; ".join(g.findings[:1])
                    or "a defect fix requires a failing regression test",
                )
            )
        elif g.gate == "spec_integrity":
            verdict.failures.append(
                failure(
                    "spec_modified",
                    gate=g.gate,
                    approving_seq=g.details.get("approval_seq"),
                    detail="; ".join(g.findings[:1])
                    or "spec changed after approval — review with `3pwr spec diff`",
                )
            )
        elif g.gate in _DESIGN_FAILURE_CLASS:
            verdict.failures.append(
                failure(
                    _DESIGN_FAILURE_CLASS[g.gate],
                    gate=g.gate,
                    tool=g.tool,
                    detail="; ".join(g.findings[:3]) or f"{g.gate} oracle failed",
                )
            )
    return verdict.finalize()


def _test_roots(manifest: dict[str, Any], target: Path) -> list[Path]:
    roots = manifest.get("test_roots") or ["tests", "src", "."]
    out = [target / r for r in roots]
    return [p for p in out if p.exists()] or [target]


def _diff_coverage_gate(
    settings: Settings,
    target: Path,
    manifest: dict[str, Any],
    tcfg: dict[str, Any],
    coverage_path: Path | None,
    base: str | None,
    paths: list[str] | None = None,
) -> GateResult:
    threshold = float(tcfg.get("diff_coverage", 0))
    if coverage_path is None:
        spec = adapters.gate_spec(manifest, "tests") or {}
        if spec.get("coverage_path"):
            coverage_path = target / spec["coverage_path"]
    if coverage_path is None or not coverage_path.exists():
        return GateResult(
            gate="diff_coverage",
            status=STATUS_FAIL,
            tool="3pwr-covdiff",
            findings=[f"no coverage report found at {coverage_path}"],
        )
    lcov = covdiff.parse_lcov(coverage_path, root=target)
    changed = covdiff.changed_lines(settings.root, target, base)
    # When --paths is given, scope coverage to those files only (spec §4 / 3PWR-FR-051).
    allow = {str((target / p).resolve()) for p in paths} if paths else None
    pct, uncovered = covdiff.diff_coverage(lcov, changed, allow)
    status = STATUS_PASS if pct >= threshold else STATUS_FAIL
    findings = []
    if status == STATUS_FAIL:
        findings = [f"{u['file']}:{u['line']} not covered" for u in uncovered[:10]]
    return GateResult(
        gate="diff_coverage",
        status=status,
        tool="3pwr-covdiff",
        details={
            "covered_pct": pct,
            "threshold": threshold,
            "uncovered_count": len(uncovered),
            "scoped_paths": list(paths) if paths else [],
        },
        findings=findings,
    )
