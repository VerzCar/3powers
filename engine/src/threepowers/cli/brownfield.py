"""Brownfield and readiness commands: ``characterize``, ``eval``,
``deps-check``, ``ready``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import yaml

from .. import (
    config,
    deps,
    runpreflight,
    workspace,
)
from ..ledger import Ledger
from ..verdict import STATUS_PASS
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    _compose,
    _print,
    _settings,
    _styler,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_characterize(args: argparse.Namespace) -> int:
    """Reconstruct a spec + characterization tests for a legacy module."""
    from .. import characterize

    # Brownfield Stage Zero runs *before* a repo has adopted 3Powers, so a `.3powers/`
    # trust spine may not exist yet — fall back to --root or cwd rather than requiring it.
    base = Path(args.root).resolve() if args.root else None
    try:
        root = config.find_root(base)
    except FileNotFoundError:
        root = base or Path.cwd()
    module_path = Path(args.module).resolve()
    specs_dir = Path(args.specs).resolve() if args.specs else root / workspace.SPECS_DIR
    # A directory walk defaults each file's tests alongside it; an explicit --tests pins them all.
    tests_dir = Path(args.tests).resolve() if args.tests else None
    try:
        results = characterize.characterize_path(
            root, module_path, specs_dir=specs_dir, tests_dir=tests_dir
        )
    except (FileNotFoundError, SyntaxError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    cst = _styler(args)
    rows = []
    for res in results:
        try:
            rel = str(res.spec_path.parent.relative_to(root)) if root else res.spec_id
        except ValueError:
            rel = res.spec_id
        rows.append(
            cst.status_row(
                "pass",
                f"characterized → spec {res.spec_id} ({rel})",
                f"{len(res.symbols)} symbol(s), {len(res.requirement_ids)} requirement(s)",
            )
        )
    if len(results) > 1:
        rows.insert(0, cst.status_row("info", f"characterized {len(results)} source file(s)"))
    _print(
        {
            "count": len(results),
            "results": [
                {
                    "spec_id": r.spec_id,
                    "spec_path": str(r.spec_path),
                    "test_path": str(r.test_path),
                    "symbols": r.symbols,
                    "requirement_ids": r.requirement_ids,
                }
                for r in results
            ],
        },
        args.json,
        _compose(
            args,
            cst,
            title="characterize",
            subject=module_path.name,
            rows=rows,
        ),
    )
    return EXIT_OK


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the prompt/constitution eval set; block on regression."""
    from ..evals import run_evals

    s = _settings(args.root)
    cases = Path(args.cases).resolve() if args.cases else (s.dir / "eval" / "cases.yaml")
    gate = run_evals(s.root, cases)
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"eval {gate.status.upper()}",
            f"{gate.details.get('passed')}/{gate.details.get('cases')} cases",
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(args, cst, title="eval", rows=rows),
    )
    return EXIT_OK if passed else EXIT_FAIL


def cmd_deps_check(args: argparse.Namespace) -> int:
    """Probe installed third-party versions against the supported ranges.

    A preflight command, not a verdict gate — installed versions are environment-dependent, so
    keeping them out of the verdict preserves determinism."""
    s = _settings(args.root)
    manifest_path = (
        Path(args.manifest).resolve() if args.manifest else s.dir / "config" / "dependencies.yaml"
    )
    if not manifest_path.exists():
        print(f"error: no dependencies manifest at {manifest_path}", file=sys.stderr)
        return EXIT_USAGE
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    report = deps.check_dependencies(manifest, probe=lambda cmd: deps.run_probe(cmd, s.root))

    dst = _styler(args)
    strict_block = bool(args.strict and report.drifted)
    ok = report.ok and not strict_block
    table_rows = []
    for c in report.checks:
        state = (
            "pass"
            if c.status == deps.OK
            else (
                "info" if c.status == deps.UNKNOWN else ("fail" if c.policy == "block" else "warn")
            )
        )
        note = "" if c.status == deps.OK else f"{c.status} [{c.policy}]"
        table_rows.append(
            [dst.mark(state), c.name, c.installed or "—", c.supported or "(any)", note]
        )
    rows = [dst.table(table_rows, headers=["", "dependency", "installed", "supported", "status"])]
    if not ok:
        rows.append(
            dst.status_row(
                "fail", "deps-check FAILED: a blocking dependency is out of range or absent"
            )
        )
    _print(
        {
            "ok": ok,
            "checks": [
                {
                    "name": c.name,
                    "installed": c.installed,
                    "supported": c.supported,
                    "status": c.status,
                    "policy": c.policy,
                }
                for c in report.checks
            ],
        },
        args.json,
        _compose(args, dst, title="deps-check", subject=str(manifest_path), rows=rows),
    )
    return EXIT_OK if ok else EXIT_FAIL


def cmd_ready(args: argparse.Namespace) -> int:
    """Standalone, re-runnable auto-run readiness: the full ``3pwr run --mode auto``
    preflight — the SAME shared check set init and the run itself use — plus a
    dependency summary, with one overall ready/not-ready verdict and a per-item fix.

    Read-only and fully offline: it probes config, PATH, and the key custody chain,
    changes nothing on disk, and is never a gate. Exits 0 when ready, 1 when not."""
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    coder_int = runpreflight.resolve_coder_integration(s, getattr(args, "integration", None))
    oracle_int = runpreflight.resolve_oracle_integration(s)
    prqs = runpreflight.check_auto(
        s,
        coder_agent=coder_int,
        oracle_agent=oracle_int,
        entries=entries,
        spec_id=getattr(args, "spec_id", None),
    )
    missing = runpreflight.unmet(prqs)

    # Dependency summary — informational; never flips the readiness verdict (never a gate).
    deps_summary: Optional[dict[str, Any]] = None
    manifest_path = s.dir / "config" / "dependencies.yaml"
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        report = deps.check_dependencies(manifest, probe=lambda cmd: deps.run_probe(cmd, s.root))
        deps_summary = {
            "ok": report.ok,
            "total": len(report.checks),
            "drifted_or_missing": [
                {"name": c.name, "status": c.status, "policy": c.policy} for c in report.drifted
            ],
        }

    obj = {
        "ready": not missing,
        "checks": [
            {"prerequisite": p.name, "ok": p.ok, "label": p.label, "fix": p.fix} for p in prqs
        ],
        "deps": deps_summary,
    }
    rst = _styler(args)
    rows = []
    if missing:
        rows.append(
            rst.status_row("fail", "not ready for `3pwr run --mode auto` — remaining steps:")
        )
    else:
        rows.append(rst.status_row("pass", "ready for `3pwr run --mode auto`"))
    for p in prqs:
        rows.append(
            rst.status_row(
                "pass" if p.ok else "fail", rst.bold(p.name), p.label if p.ok else p.fix, indent=4
            )
        )
    if missing:
        rows.append("  " + rst.dim("always available offline:"))
        rows.append(rst.bullet(runpreflight.OFFLINE_ALTERNATIVES, indent=4))
    if deps_summary is not None:
        drift = deps_summary["drifted_or_missing"]
        if drift:
            named = ", ".join(f"{d['name']} ({d['status']})" for d in drift)
            rows.append(
                rst.status_row("warn", f"dependency summary: {named}", "details: 3pwr deps-check")
            )
        else:
            rows.append(
                rst.status_row(
                    "pass", f"dependency summary: {deps_summary['total']} component(s) within range"
                )
            )
    _print(
        obj,
        getattr(args, "json", False),
        _compose(args, rst, title="ready", subject="auto-run preflight", rows=rows),
    )
    return EXIT_OK if not missing else EXIT_FAIL


def _register_characterize(sub: SubParsers, common: AddCommon) -> None:
    chp = common(
        sub.add_parser("characterize", help="reconstruct a spec + pin a legacy module's behavior")
    )
    chp.add_argument(
        "--module",
        required=True,
        help="a legacy source file (e.g. src/foo.py) or a directory to walk and characterize",
    )
    chp.add_argument("--specs", help="spec-stub directory (default: <root>/specs-src)")
    chp.add_argument("--tests", help="tests output dir (default: alongside the module)")
    chp.set_defaults(func=cmd_characterize)


def _register_eval(sub: SubParsers, common: AddCommon) -> None:
    evp = common(sub.add_parser("eval", help="run the prompt/constitution eval set"))
    evp.add_argument("--cases", help="eval cases.yaml (default: .3powers/eval/cases.yaml)")
    evp.set_defaults(func=cmd_eval)


def _register_deps_check(sub: SubParsers, common: AddCommon) -> None:
    dcp = common(
        sub.add_parser(
            "deps-check", help="check installed third-party versions vs supported ranges"
        )
    )
    dcp.add_argument(
        "--manifest", help="dependencies.yaml (default: .3powers/config/dependencies.yaml)"
    )
    dcp.add_argument("--strict", action="store_true", help="treat warn-policy drift as blocking")
    dcp.set_defaults(func=cmd_deps_check)


def _register_ready(sub: SubParsers, common: AddCommon) -> None:
    rdy = common(
        sub.add_parser(
            "ready",
            help="am I ready for `3pwr run --mode auto`? — the full run preflight + a dependency "
            "summary; read-only, offline, never a gate",
        )
    )
    rdy.add_argument(
        "--integration",
        default=None,
        help="check against this coder agent backend instead of roles.coder.integration",
    )
    rdy.add_argument(
        "--spec-id",
        dest="spec_id",
        help="consider deviations recorded for this spec id (e.g. a model-diversity deviation)",
    )
    rdy.set_defaults(func=cmd_ready)
