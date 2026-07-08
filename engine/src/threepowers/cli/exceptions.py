"""Recorded-exception commands: ``deviation`` and ``emergency``."""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING


from .. import (
    deviations,
    keys,
)
from ..ledger import Ledger
from ..verdict import GATE_ORDER
from ._common import (
    EXIT_OK,
    EXIT_USAGE,
    _compose,
    _print,
    _settings,
    _styler,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_deviation(args: argparse.Namespace) -> int:
    """Record (or revoke) a signed, reversible gate deviation."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE

    if args.revoke is not None:
        target = next((e for e in ledger.entries() if e["seq"] == args.revoke), None)
        if target is None or target.get("type") != "deviation":
            print(f"error: no deviation at ledger seq={args.revoke}", file=sys.stderr)
            return EXIT_USAGE
        entry = ledger.append(
            "deviation", {"revokes": args.revoke, "reason": args.note or ""}, sk, spec_id=""
        )
        dvt = _styler(args)
        _print(
            {"revoked": args.revoke, "ledger_seq": entry["seq"]},
            args.json,
            _compose(
                args,
                dvt,
                title="deviation",
                subject=f"revoke seq={args.revoke}",
                rows=[
                    dvt.status_row(
                        "pass",
                        f"deviation at seq={args.revoke} revoked",
                        f"ledger seq={entry['seq']}",
                    )
                ],
            ),
        )
        return EXIT_OK

    if not args.gate:
        print("error: --gate is required (or use --revoke <seq>)", file=sys.stderr)
        return EXIT_USAGE
    if not args.approver:
        print("error: --approver is required — a human accepts the deviation", file=sys.stderr)
        return EXIT_USAGE
    allowed = set(GATE_ORDER) | set(deviations.DEVIATABLE_REQUIREMENTS)
    unknown = sorted(set(args.gate) - allowed)
    if unknown:
        print(
            f"error: unknown gate/requirement(s): {', '.join(unknown)}; known gates: "
            f"{', '.join(GATE_ORDER)}; requirements: {', '.join(deviations.DEVIATABLE_REQUIREMENTS)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if args.until and deviations.parse_iso(args.until) is None:
        print("error: --until must be ISO-8601 (e.g. 2026-07-01T00:00:00Z)", file=sys.stderr)
        return EXIT_USAGE

    payload = deviations.deviation_payload(args.gate, args.note or "", args.approver, args.until)
    entry = ledger.append("deviation", payload, sk, spec_id=args.spec_id or "")
    way_back = f"until {args.until}" if args.until else "revoke to end"
    dvt = _styler(args)
    _print(
        {"gates": payload["gates"], "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            dvt,
            title="deviation",
            subject=", ".join(payload["gates"]),
            rows=[
                dvt.status_row(
                    "warn",
                    f"deviation recorded by {args.approver} for gate(s) {', '.join(payload['gates'])}",
                    f"{way_back}; ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_emergency(args: argparse.Namespace) -> int:
    """Open the constrained emergency fast path."""
    s = _settings(args.root)
    if not args.approver:
        print("error: --approver is required — a human opens the emergency path", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    hours = (
        args.cleanup_hours if args.cleanup_hours is not None else deviations.DEFAULT_CLEANUP_HOURS
    )
    payload = deviations.emergency_payload(args.note or "", args.approver, hours)
    entry = Ledger(s.ledger_path).append("deviation", payload, sk, spec_id=args.spec_id or "")
    est = _styler(args)
    _print(
        {
            "emergency": True,
            "deferring": payload["gates"],
            "cleanup_due": payload["cleanup_due"],
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            est,
            title="emergency",
            subject=args.approver,
            rows=[
                est.status_row(
                    "warn",
                    f"EMERGENCY fast path opened by {args.approver}: deferring "
                    f"{', '.join(deviations.EMERGENCY_DEFERRABLE)}",
                    f"until cleanup by {payload['cleanup_due']}",
                ),
                est.status_row(
                    "info", "the security/secret gates, human sign-off, and provenance still apply"
                ),
                est.status_row(
                    "warn",
                    f"clean up within {hours}h (file a requirement + "
                    f"`3pwr deviation --revoke {entry['seq']}`) or advance will block",
                ),
            ],
        ),
    )
    return EXIT_OK


def _register_deviation(sub: SubParsers, common: AddCommon) -> None:
    dvp = common(
        sub.add_parser("deviation", help="record/revoke a signed, reversible gate exception")
    )
    dvp.add_argument(
        "--gate",
        action="append",
        help="gate or requirement to relax (repeatable), e.g. a gate name or `model_diversity`; "
        "required unless --revoke",
    )
    dvp.add_argument("--approver", help="human who accepts the deviation (required to record)")
    dvp.add_argument("--note", help="recorded reason")
    dvp.add_argument("--until", help="auto-expiry, ISO-8601 (the way back); else use --revoke")
    dvp.add_argument("--revoke", type=int, help="revoke the deviation at this ledger seq")
    dvp.add_argument("--spec-id", dest="spec_id", help="scope to a spec (default: global)")
    dvp.set_defaults(func=cmd_deviation)


def _register_emergency(sub: SubParsers, common: AddCommon) -> None:
    emp = common(sub.add_parser("emergency", help="open the constrained emergency fast path"))
    emp.add_argument("--approver", help="human who opens the emergency path")
    emp.add_argument("--note", help="recorded reason")
    emp.add_argument("--cleanup-hours", dest="cleanup_hours", type=int, help="cleanup window (24)")
    emp.add_argument("--spec-id", dest="spec_id")
    emp.set_defaults(func=cmd_emergency)
