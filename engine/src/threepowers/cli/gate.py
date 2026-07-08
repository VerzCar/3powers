"""Gate-engine commands: ``gate run``, ``gate config show``, ``conformance``,
``classify``, ``coverage-check``, ``scope-check``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional


import threepowers.cli as _cli
from .. import (
    keys,
    orchestrate,
    scope,
    workkind,
    workspace,
)
from ..adapters import command_of, effective_gates
from ..gates import PrerequisiteError
from ..ledger import Ledger
from ..verdict import GATE_ORDER, STATUS_PASS
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_SETUP,
    EXIT_USAGE,
    _compose,
    _detection_line,
    _effective_gates_or_none,
    _format_verdict,
    _print,
    _resolve_spec,
    _settings,
    _styler,
    _verbosity,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_gate_run(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else s.root
    # --id <NNN> is the run-number shorthand for --spec: resolve the one matching
    # feature folder and its spec; zero or multiple matches are clear, actionable errors.
    if getattr(args, "id", None):
        try:
            feature = workspace.resolve_feature_dir(s.root, args.id)
        except (FileNotFoundError, LookupError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_USAGE
        resolved = workspace.spec_path(feature)
        if resolved is None:
            print(
                f"error: specs/{feature.name} contains no spec.md — pass --spec <path/to/spec.md>",
                file=sys.stderr,
            )
            return EXIT_USAGE
        spec_path: Path | None = resolved
    else:
        # Brownfield adoption: report-only / diff-scope is the on-ramp for a repo
        # that has no 3Powers spec yet, so a missing spec is not an error there — the two spec-bound
        # gates SKIP.
        try:
            spec_path = _resolve_spec(s, args.spec)
        except FileNotFoundError:
            if args.report_only or args.diff_scope:
                spec_path = None
            else:
                raise

    # The live per-gate pipeline: rows update in place on a capable TTY and
    # degrade to sequential plain rows off it. Never constructed under --json — the machine payload
    # is never routed through the rendering layer — and quiet keeps the result-only output.
    gst = _styler(args)
    v_level = _verbosity(args)
    # The effective gate configuration: the adapter manifest, the project's
    # committed gates.yaml overrides, and — for gates the file leaves alone — the native tooling
    # auto-detected once at startup. One line names what was detected, never
    # under --json. An unassemblable config degrades to None: run_gates loads
    # the adapter itself and surfaces the real error on its own path.
    eff = _effective_gates_or_none(s, args.adapter, target)
    if eff is not None and eff.detected and not args.json and v_level != "quiet":
        print(_detection_line(eff.detected))
    pipeline: Optional[orchestrate.GatePipeline] = None
    if not args.json and v_level != "quiet":
        pipeline = orchestrate.GatePipeline(sys.stdout, gst, verbose=v_level == "verbose")
        pipeline.open()
    try:
        verdict = _cli.run_gates(
            s,
            target,
            tier=args.tier,
            spec_path=spec_path,
            adapter_name=args.adapter,
            base=args.base,
            allow_mutation=args.mutation,
            paths=args.paths,
            report_only=args.report_only,
            diff_scope=args.diff_scope,
            work_kind=args.work_kind,
            observer=pipeline,
            auto_fix=args.auto_fix,
            manifest=eff.manifest if eff is not None else None,
        )
    except PrerequisiteError as exc:
        # A required tool of a non-optional gate is absent: no gate ran; the per-tool
        # install hints come from the adapter's toolchain data. A setup problem, never a gate verdict.
        print(str(exc), file=sys.stderr)
        return EXIT_SETUP
    finally:
        if pipeline is not None:
            pipeline.close()
    s.verdicts_dir.mkdir(parents=True, exist_ok=True)
    verdict.write(s.verdicts_dir / "latest.json")

    appended = None
    if not args.no_ledger:
        try:
            sk = keys.resolve_signer(s.root)
            appended = Ledger(s.ledger_path).append(
                "verdict",
                verdict.to_dict(),
                sk,
                spec_id=verdict.spec_id,
                requirement_ids=verdict.requirement_ids(),
            )
        except FileNotFoundError as exc:
            print(f"⚠️  ledger entry skipped: {exc}", file=sys.stderr)

    human = _format_verdict(verdict, appended, gst)
    # The auto-fixed announcement: one line per gate a fix turned green — human
    # output only, so the --json payload stays pure machine data.
    if not args.json:
        for g in verdict.gates:
            fixer = (g.details or {}).get("auto_fixed")
            if fixer:
                human += f"\n  ↳ auto-fixed by {fixer}"
    # One panel per failed gate, printed after the live pipeline exits — the
    # structured replacement for the former bottom "failures:" block. Human output only.
    if not args.json:
        panels = orchestrate.failure_panels(verdict.to_dict(), gst, verbose=v_level == "verbose")
        if panels:
            human += "\n" + panels
    if args.report_only and verdict.result != STATUS_PASS:
        human += "\n  " + gst.mark("info") + " report-only: verdict emitted but not enforced"
    # Consolidated install call-to-action: if gates couldn't run because their tools are absent, say
    # exactly what to install so the next `gate run` / `3pwr run` succeeds. Human-output
    # only — the per-gate `missing_tool`/`install_hint` already ride the JSON verdict.
    missing: list[tuple[str, str]] = []
    seen: set[str] = set()
    for g in verdict.gates:
        tool = (g.details or {}).get("missing_tool")
        if tool and tool not in seen:
            seen.add(tool)
            missing.append((tool, (g.details or {}).get("install_hint", "")))
    if missing:
        human += "\n\n" + gst.warn(
            "⚠ missing toolchain — some gates could not run. Install, then re-run:"
        )
        for tool, inst in missing:
            human += "\n    " + (
                f"{tool}  →  {inst}" if inst else f"{tool}  (install it and re-run)"
            )
    _print(
        {"verdict": verdict.to_dict(), "ledger_seq": (appended or {}).get("seq")},
        args.json,
        _compose(
            args,
            gst,
            title="gate run",
            subject=f"{verdict.spec_id or '?'} · {verdict.tier} · {verdict.adapter}",
            rows=[human],
        ),
    )
    # Report-only never blocks the developer's flow; ratchet to a blocking run
    # (optionally diff-scoped via --base/--paths) once the diff is clean.
    if args.report_only:
        return EXIT_OK
    return EXIT_OK if verdict.result == STATUS_PASS else EXIT_FAIL


def cmd_gate_config_show(args: argparse.Namespace) -> int:
    """Render the effective per-gate configuration — without executing any gate.

    One row per gate: the gate, its tool, its check command, its fix command (— when none), and a
    source tag naming where the configuration came from — the adapter manifest, the project's
    committed ``gates.yaml`` override, or startup auto-detection."""
    s = _settings(args.root)
    try:
        adapter_name = args.adapter or _cli.detect_adapter(s, s.root)
        eff = effective_gates(s, adapter_name, s.root)
    except (FileNotFoundError, LookupError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    gates_cfg: dict[str, Any] = eff.manifest.get("gates") or {}
    order = [g for g in GATE_ORDER if g in gates_cfg]
    order += sorted(g for g in gates_cfg if g not in GATE_ORDER)
    header = ("gate", "tool", "check_cmd", "fix_cmd", "source")
    data: list[tuple[str, str, str, str, str]] = []
    obj: dict[str, Any] = {"adapter": adapter_name, "gates": {}}
    for gate in order:
        spec = gates_cfg.get(gate) or {}
        cmd = str(command_of(spec) or "")
        tool_tokens = str(spec.get("parser") or cmd).split()
        tool = tool_tokens[0] if tool_tokens else "—"
        fix = str(spec.get("fix_cmd") or "")
        source = eff.sources.get(gate, "adapter")
        data.append((gate, tool, cmd or "—", fix or "—", f"[{source}]"))
        obj["gates"][gate] = {
            "tool": tool if tool != "—" else "",
            "check_cmd": cmd,
            "fix_cmd": fix,
            "source": source,
        }
    widths = [max(len(h), *(len(row[i]) for row in data), 0) for i, h in enumerate(header[:4])]
    lines = ["  ".join(header[i].ljust(widths[i]) for i in range(4)) + "  " + header[4]]
    for row in data:
        lines.append("  ".join(row[i].ljust(widths[i]) for i in range(4)) + "  " + row[4])
    cst = _styler(args)
    _print(
        obj,
        args.json,
        _compose(args, cst, title="gate config", subject=adapter_name, rows=lines),
    )
    return EXIT_OK


def cmd_conformance(args: argparse.Namespace) -> int:
    from ..conformance import run_conformance

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    roots = [Path(t).resolve() for t in args.tests] if args.tests else [s.root]
    gate = run_conformance(spec_path, roots)
    obj = {"gate": gate.gate, "status": gate.status, **gate.details}
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"spec-conformance {gate.status.upper()}",
            gate.details.get("spec_id", "?"),
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        obj,
        args.json,
        _compose(
            args, cst, title="conformance", subject=gate.details.get("spec_id", ""), rows=rows
        ),
    )
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


def cmd_classify(args: argparse.Namespace) -> int:
    """Infer work kind(s) + a suggested risk tier from free-form intent.

    Deterministic (keyword heuristics, no model call — never perturbs the verdict). The
    inference shapes the tier + oracle strategy; it never bypasses the human sign-off."""
    wk = workkind.classify(args.intent)
    cst = _styler(args)
    rows = [
        cst.kv([("work kinds", ", ".join(wk.kinds) or "—"), ("suggested tier", wk.suggested_tier)])
    ]
    if wk.signals:
        rows.append(cst.status_row("info", "signals", ", ".join(wk.signals)))
    _print(
        {"kinds": wk.kinds, "suggested_tier": wk.suggested_tier, "signals": wk.signals},
        args.json,
        _compose(args, cst, title="classify", rows=rows),
    )
    return EXIT_OK


def cmd_coverage_check(args: argparse.Namespace) -> int:
    """Two-way requirement<->task coverage before code."""
    from ..conformance import two_way_coverage

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    gate = two_way_coverage(spec_path, Path(args.tasks).resolve())
    cst = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [
        cst.status_row(
            "pass" if passed else "fail",
            f"coverage-map {gate.status.upper()}",
            gate.details.get("spec_id", "?"),
        )
    ]
    if gate.findings:
        rows.append(cst.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(
            args, cst, title="coverage-check", subject=gate.details.get("spec_id", ""), rows=rows
        ),
    )
    return EXIT_OK if passed else EXIT_FAIL


def cmd_scope_check(args: argparse.Namespace) -> int:
    """Task requirement-ID + file-scope discipline."""
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else None
    gate = scope.scope_check(Path(args.tasks).resolve(), s.root, base=args.base, target=target)
    sct = _styler(args)
    passed = gate.status == STATUS_PASS
    rows = [sct.status_row("pass" if passed else "fail", f"scope-check {gate.status.upper()}")]
    if gate.findings:
        rows.append(sct.bullet(gate.findings))
    _print(
        {"status": gate.status, **gate.details},
        args.json,
        _compose(args, sct, title="scope-check", rows=rows),
    )
    return EXIT_OK if passed else EXIT_FAIL


def _register_gate(sub: SubParsers, common: AddCommon) -> None:
    gp = sub.add_parser("gate", help="gate engine")
    gsub = gp.add_subparsers(dest="gate_cmd", required=True)
    gr = common(gsub.add_parser("run", help="run the gate suite and emit a verdict"))
    gr.add_argument("--path", help="target project path (default: repo root)")
    gr.add_argument("--tier", default="Standard", help="risk tier (default: Standard)")
    gr.add_argument("--adapter", help="language adapter (default: auto-detect)")
    spec_src = gr.add_mutually_exclusive_group()
    spec_src.add_argument("--spec", help="path to the governing spec.md")
    spec_src.add_argument(
        "--id",
        metavar="NNN",
        help="feature folder number — resolves the spec of specs/<NNN>-*/ (exactly one must match)",
    )
    gr.add_argument("--base", help="git ref for diff-coverage base")
    gr.add_argument("--mutation", action="store_true", help="run the mutation gate")
    gr.add_argument(
        "--paths",
        nargs="*",
        help="scope diff-coverage + mutation to these files",
    )
    gr.add_argument(
        "--report-only",
        action="store_true",
        help="emit the verdict but do not block (for adopting 3Powers in an existing repo)",
    )
    gr.add_argument(
        "--diff-scope",
        action="store_true",
        help="block only on files changed vs --base (for adopting 3Powers in an existing repo)",
    )
    gr.add_argument(
        "--work-kind",
        action="append",
        choices=list(workkind.KINDS),
        help="shape the gate set for an inferred kind (repeatable): defect adds a regression gate, "
        "design adds the design oracles; never weakens a tier gate",
    )
    gr.add_argument("--no-ledger", action="store_true", help="do not append to the ledger")
    gr.add_argument(
        "--auto-fix",
        dest="auto_fix",
        action="store_true",
        help="when a format/lint check fails and a fix command is configured, run the fix and "
        "re-check (opt-in; never the default)",
    )
    gr.set_defaults(func=cmd_gate_run)

    gcp = gsub.add_parser("config", help="gate configuration")
    gcsub = gcp.add_subparsers(dest="gate_config_cmd", required=True)
    gcs = common(
        gcsub.add_parser(
            "show",
            help="show the effective per-gate configuration — adapter defaults, gates.yaml "
            "overrides, and auto-detected tooling — without running any gate",
        )
    )
    gcs.add_argument("--adapter", help="language adapter (default: auto-detect)")
    gcs.set_defaults(func=cmd_gate_config_show)


def _register_conformance(sub: SubParsers, common: AddCommon) -> None:
    cp = common(sub.add_parser("conformance", help="spec-conformance trace only"))
    cp.add_argument("--spec", help="path to the governing spec.md")
    cp.add_argument("--tests", nargs="*", help="test roots to scan")
    cp.set_defaults(func=cmd_conformance)


def _register_classify(sub: SubParsers, common: AddCommon) -> None:
    clp = common(
        sub.add_parser(
            "classify", help="infer the kind(s) of change + a suggested risk tier from your intent"
        )
    )
    clp.add_argument("intent", help="the free-form intent to classify")
    clp.set_defaults(func=cmd_classify)


def _register_coverage_check(sub: SubParsers, common: AddCommon) -> None:
    ccp = common(sub.add_parser("coverage-check", help="two-way requirement<->task coverage"))
    ccp.add_argument("--spec", help="path to the governing spec.md")
    ccp.add_argument("--tasks", required=True, help="path to tasks.md")
    ccp.set_defaults(func=cmd_coverage_check)


def _register_scope_check(sub: SubParsers, common: AddCommon) -> None:
    scp = common(sub.add_parser("scope-check", help="task req-id + file-scope discipline"))
    scp.add_argument("--tasks", required=True, help="path to tasks.md")
    scp.add_argument("--base", help="git ref for the changed-file base")
    scp.add_argument("--path", help="restrict the changed-file scan to this dir")
    scp.set_defaults(func=cmd_scope_check)
