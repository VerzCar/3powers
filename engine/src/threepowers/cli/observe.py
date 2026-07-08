"""Observe & feedback commands: ``observe`` signal / coverage /
log-action / verify-actions."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .. import (
    keys,
    observe,
)
from ..config import Settings
from ..ledger import Ledger
from ..verify import verify_ledger
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    _compose,
    _print,
    _resolve_spec,
    _settings,
    _styler,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_observe_signal(args: argparse.Namespace) -> int:
    """Record a production signal and route it to the legislature as new intent."""
    s = _settings(args.root)
    if args.kind not in observe.SIGNAL_KINDS:
        print(f"error: --kind must be one of {', '.join(observe.SIGNAL_KINDS)}", file=sys.stderr)
        return EXIT_USAGE
    if not args.note:
        print("error: --note is required — describe the production lesson", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    backlog = s.dir / "feedback" / f"{args.spec_id}.md"
    fb_id = observe.route_to_backlog(backlog, args.spec_id, args.kind, args.nfr or "", args.note)
    entry = Ledger(s.ledger_path).append(
        "observe",
        observe.signal_payload(args.kind, args.note, args.nfr, fb_id),
        sk,
        spec_id=args.spec_id,
        requirement_ids=[args.nfr] if args.nfr else [],
    )
    ost = _styler(args)
    _print(
        {
            "kind": args.kind,
            "routed_to": fb_id,
            "backlog": str(backlog),
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            ost,
            title="observe signal",
            subject=f"{args.kind} · {args.spec_id}",
            rows=[
                ost.status_row(
                    "pass",
                    f"observed [{args.kind}] for {args.spec_id} → routed to the legislature "
                    f"as new intent {fb_id}",
                ),
                ost.kv(
                    [
                        ("backlog", str(backlog)),
                        ("next", "take it into a new `3pwr run` spec — not an in-place patch"),
                    ]
                ),
                ost.status_row(
                    "info", "spec now at the Observe stage", f"ledger seq={entry['seq']}"
                ),
            ],
        ),
    )
    return EXIT_OK


def cmd_observe_coverage(args: argparse.Namespace) -> int:
    """Report NFR-instrumentation coverage — which NFRs have a live check."""
    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    reg_path = (
        Path(args.registry).resolve() if args.registry else s.dir / "config" / "observability.yaml"
    )
    observability: dict = {}
    if reg_path.exists():
        observability = yaml.safe_load(reg_path.read_text(encoding="utf-8")) or {}
    cov = observe.nfr_coverage(spec_path, observability)
    ost = _styler(args)
    rows = [
        ost.status_row(
            "pass" if cov.ok else "warn",
            f"NFR instrumentation: {len(cov.instrumented)}/{len(cov.nfrs)} NFR(s) have a live check",
            cov.spec_id,
        )
    ]
    for m in cov.missing:
        rows.append(ost.status_row("fail", f"{m}: no live production check registered", indent=4))
    _print(
        {
            "spec_id": cov.spec_id,
            "nfrs": cov.nfrs,
            "instrumented": cov.instrumented,
            "missing": cov.missing,
        },
        args.json,
        _compose(args, ost, title="observe coverage", subject=cov.spec_id, rows=rows),
    )
    return EXIT_OK if cov.ok else EXIT_FAIL


def _actions_path(s: Settings) -> Path:
    return s.dir / "runtime" / "actions.jsonl"


def cmd_observe_log_action(args: argparse.Namespace) -> int:
    """Append a tamper-evident, attributable runtime agent action."""
    s = _settings(args.root)
    if not args.agent or not args.action:
        print("error: --agent and --action are required", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = Ledger(_actions_path(s)).append(
        "agent_action",
        observe.action_payload(args.agent, args.action),
        sk,
        spec_id=args.spec_id or "",
    )
    ost = _styler(args)
    _print(
        {"agent": args.agent, "seq": entry["seq"]},
        args.json,
        _compose(
            args,
            ost,
            title="observe log-action",
            subject=args.agent,
            rows=[
                ost.status_row(
                    "pass",
                    f"logged runtime action by {args.agent}",
                    f"runtime log seq={entry['seq']}; tamper-evident — "
                    "check with `3pwr observe verify-actions`",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_observe_verify_actions(args: argparse.Namespace) -> int:
    """Verify the runtime agent-action log's chain + signatures."""
    s = _settings(args.root)
    res = verify_ledger(_actions_path(s), s.pubkey_path)
    ost = _styler(args)
    _print(
        {"ok": res.ok, "entries": res.entries, "problems": res.problems},
        args.json,
        _compose(
            args,
            ost,
            title="observe verify-actions",
            rows=[ost.status_row("pass" if res.ok else "fail", res.summary())],
        ),
    )
    return EXIT_OK if res.ok else EXIT_FAIL


def _register_observe(sub: SubParsers, common: AddCommon) -> None:
    obp = sub.add_parser(
        "observe", help="observe & feedback: signal / coverage / log-action / verify-actions"
    )
    obsub = obp.add_subparsers(dest="observe_cmd", required=True)
    osig = common(
        obsub.add_parser("signal", help="record a production signal → route to new intent")
    )
    osig.add_argument("--spec-id", dest="spec_id", required=True)
    osig.add_argument("--kind", required=True, help="incident | missed-nfr | usage")
    osig.add_argument("--nfr", help="the NFR id the signal relates to (optional)")
    osig.add_argument("--note", help="the production lesson (required)")
    osig.set_defaults(func=cmd_observe_signal)
    ocov = common(
        obsub.add_parser("coverage", help="report which NFRs have a live production check")
    )
    ocov.add_argument("--spec", help="path to the governing spec.md")
    ocov.add_argument(
        "--registry", help="observability.yaml (default: .3powers/config/observability.yaml)"
    )
    ocov.set_defaults(func=cmd_observe_coverage)
    olog = common(
        obsub.add_parser("log-action", help="log a tamper-evident, attributable agent action")
    )
    olog.add_argument("--agent", required=True, help="the acting agent's identity")
    olog.add_argument("--action", required=True, help="the action taken")
    olog.add_argument("--spec-id", dest="spec_id")
    olog.set_defaults(func=cmd_observe_log_action)
    over = common(obsub.add_parser("verify-actions", help="verify the runtime agent-action log"))
    over.set_defaults(func=cmd_observe_verify_actions)
