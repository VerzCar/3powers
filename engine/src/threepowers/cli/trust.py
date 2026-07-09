"""Trust-spine commands: ``verify``, ``anchor``, ``signoff``, ``advance``,
``spec diff``, ``ledger show``, ``revert``."""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional


from .. import (
    anchor,
    deviations,
    gitflow,
    keys,
    lifecycle,
    oracle,
    speclock,
)
from ..ledger import Ledger
from ..verdict import STATUS_PASS
from ..verify import verify_ledger
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_USAGE,
    _compose,
    _git_out,
    _print,
    _resolve_spec,
    _settings,
    _spec_approval_payload,
    _styler,
    _verbosity,
)

if TYPE_CHECKING:
    from ._common import AddCommon, SubParsers


def cmd_verify(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    res = verify_ledger(s.ledger_path, s.pubkey_path, [s.oracle_pubkey_path])
    # Custody preflight: a private key inside the working tree or readable
    # by other users is a custody violation — surfaced here, where trust is re-derived.
    custody = keys.custody_findings(s.root)
    ok = res.ok and not custody
    vst = _styler(args)
    rows = [vst.status_row("pass" if res.ok else "fail", res.summary())]
    for c in custody:
        rows.append(vst.status_row("fail", c))
    anchored: Optional[dict] = None
    if getattr(args, "anchored", False):
        # Opt-in anchored mode: cross-check the chain against the latest
        # local anchor tag. Plain `verify` never reads an anchor.
        chk = anchor.check_anchored(Ledger(s.ledger_path).entries(), anchor.latest_anchor(s.root))
        anchored = {"ok": chk.ok, "anchor_seq": chk.anchor_seq, "problems": chk.problems}
        ok = ok and chk.ok
        if chk.ok:
            rows.append(
                vst.status_row(
                    "pass", f"anchor OK — chain extends the witnessed head (seq={chk.anchor_seq})"
                )
            )
        for p in chk.problems:
            rows.append(vst.status_row("fail", p))
    _print(
        {
            "ok": ok,
            "entries": res.entries,
            "problems": res.problems,
            "key_custody": custody,
            **({"anchored": anchored} if anchored is not None else {}),
        },
        args.json,
        _compose(
            args,
            vst,
            title="verify",
            subject="ledger chain + signatures",
            rows=rows,
            extra=[vst.dim(f"{res.entries} entries checked")],
        ),
    )
    return EXIT_OK if ok else EXIT_FAIL


def cmd_anchor(args: argparse.Namespace) -> int:
    """Record the ledger head with an external witness — opt-in.

    Creates the annotated git tag ``3powers/anchor/<seq>`` carrying the head's entry hash,
    appends a local ``anchor`` receipt entry, and — only under ``--push`` — pushes the tag
    (the sole network-capable operation).
    """
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    head = anchor.head_of(ledger.entries())
    if head is None:
        print("error: the ledger is empty — nothing to anchor", file=sys.stderr)
        return EXIT_USAGE
    seq, entry_hash = head
    ok, msg = anchor.create_anchor(s.root, seq, entry_hash, push=args.push, remote=args.remote)
    if not ok:
        print(f"error: {msg}", file=sys.stderr)
        return EXIT_FAIL
    try:
        sk = keys.resolve_signer(s.root)
        receipt = ledger.append(
            "anchor",
            {
                "anchored_seq": seq,
                "anchored_hash": entry_hash,
                "witness": "git-tag",
                "ref": msg,
                "pushed": bool(args.push),
            },
            sk,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    ast = _styler(args)
    _print(
        {
            "anchored_seq": seq,
            "anchored_hash": entry_hash,
            "ref": msg,
            "pushed": bool(args.push),
            "ledger_seq": receipt["seq"],
        },
        args.json,
        _compose(
            args,
            ast,
            title="anchor",
            subject=f"seq={seq}",
            rows=[
                ast.status_row(
                    "pass",
                    f"anchored ledger head seq={seq} ({entry_hash}) as tag {msg}"
                    + (
                        " — pushed"
                        if args.push
                        else " — local only; push it to complete the witness"
                    ),
                ),
                ast.kv([("receipt", f"ledger seq={receipt['seq']}")]),
            ],
        ),
    )
    return EXIT_OK


def cmd_signoff(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"approver": args.approver, "stage": args.stage, "note": args.note or ""}
    # A Spec-stage sign-off freezes the law: seal the full document's hash inside the
    # signed entry so any later silent mutation is caught. A fresh
    # Spec-stage sign-off supersedes the previous hash.
    if args.stage.lower() == "spec":
        payload.update(_spec_approval_payload(s, getattr(args, "spec", None)))
    entry = Ledger(s.ledger_path).append("signoff", payload, sk, spec_id=args.spec_id or "")
    sealed = f"; spec hash sealed ({payload['spec_hash']})" if payload.get("spec_hash") else ""
    sst = _styler(args)
    print(
        _compose(
            args,
            sst,
            title="signoff",
            subject=f"{args.spec_id or ''} · {args.stage}".strip(" ·"),
            rows=[
                sst.status_row(
                    "pass",
                    f"sign-off recorded by {args.approver} for stage '{args.stage}'",
                    f"ledger seq={entry['seq']}{sealed}",
                )
            ],
        )
    )
    return EXIT_OK


def cmd_spec_diff(args: argparse.Namespace) -> int:
    """Read-only spec-integrity report — never writes to the ledger.

    Exit 0 when the spec matches its approval hash (or none is recorded); exit 1 on a
    mismatch, with a textual diff when the sign-off commit is known.
    """
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    spec_path: Optional[Path]
    try:
        spec_path = _resolve_spec(s, args.spec)
    except FileNotFoundError:
        spec_path = None  # fall back to the path recorded at approval
    lock = speclock.check(entries, args.spec_id or "", s.root, spec_path=spec_path)

    if lock.status == speclock.NO_APPROVAL:
        _print(
            {"spec_id": args.spec_id, "status": lock.status},
            args.json,
            f"no Spec-stage approval hash recorded for '{args.spec_id}' — nothing to compare "
            "(seal one via `3pwr signoff --stage spec`)",
        )
        return EXIT_OK

    obj = {
        "spec_id": args.spec_id,
        "status": lock.status,
        "approval_seq": lock.approval_seq,
        "approver": lock.approver,
        "approved_hash": lock.approved_hash,
        "current_hash": lock.current_hash,
        "spec_path": lock.spec_path,
    }
    dst = _styler(args)
    if lock.status == speclock.MATCH:
        _print(
            obj,
            args.json,
            _compose(
                args,
                dst,
                title="spec diff",
                subject=args.spec_id or "",
                rows=[
                    dst.status_row(
                        "pass",
                        "spec matches its approval hash",
                        f"ledger seq={lock.approval_seq}, approver={lock.approver}",
                    ),
                    "  " + dst.dim(lock.approved_hash or ""),
                ],
            ),
        )
        return EXIT_OK

    headline = (
        "spec MODIFIED after approval"
        if lock.status == speclock.MISMATCH
        else f"approved spec file is MISSING: {lock.spec_path}"
    )
    lines = [
        dst.status_row("fail", headline),
        f"  approved: {lock.approved_hash} (ledger seq={lock.approval_seq}, "
        f"approver={lock.approver})",
        f"  current:  {lock.current_hash or '(missing file)'}",
    ]
    # Textual diff (best-effort): the version at the sign-off commit vs. the file now.
    target = spec_path or speclock.resolve_target(s.root, lock)
    diff_text = ""
    if lock.commit and lock.spec_path and target is not None and target.exists():
        before = _git_out(s.root, ["show", f"{lock.commit}:{lock.spec_path}"])
        if before:
            diff_text = "\n".join(
                difflib.unified_diff(
                    before.splitlines(),
                    target.read_text(encoding="utf-8").splitlines(),
                    fromfile=f"{lock.spec_path} @ {lock.commit} (approved)",
                    tofile=f"{lock.spec_path} (current)",
                    lineterm="",
                )
            )
    if diff_text:
        obj["diff"] = diff_text
        lines.append(diff_text)
    else:
        lines.append("  (no textual diff available — sign-off commit unknown or file missing)")
    _print(
        obj,
        args.json,
        _compose(args, dst, title="spec diff", subject=args.spec_id or "", rows=lines),
    )
    return EXIT_FAIL


def cmd_advance(args: argparse.Namespace) -> int:
    """Local, CI-independent enforcement."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    active = deviations.active_deviations(entries)
    reasons: list[str] = []
    deviations_applied: list[int] = []

    # 1. Ledger must verify (accepting the primary or a distinct oracle signer).
    vres = verify_ledger(s.ledger_path, s.pubkey_path, [s.oracle_pubkey_path])
    if not vres.ok:
        reasons.append("ledger fails verification")

    # 2. Latest *enforced* verdict must be green — OR every red gate must be covered by an
    #    active, signed deviation. Report-only verdicts are advisory
    #    and never satisfy an advance.
    enforced = [
        e
        for e in entries
        if e.get("type") == "verdict" and not e.get("payload", {}).get("report_only")
    ]
    last_verdict = enforced[-1] if enforced else None
    if not last_verdict:
        reasons.append("no enforced verdict recorded")
    elif last_verdict.get("payload", {}).get("result") != STATUS_PASS:
        # The shared coverage decision: `run` consults the same helper at Verify, so the
        # two enforcement points cannot drift.
        verdict_payload = last_verdict.get("payload", {})
        red_gates = deviations.red_gates(verdict_payload)
        uncovered = sorted(
            deviations.uncovered_red_gates(verdict_payload, active, last_verdict.get("spec_id"))
        )
        if uncovered:
            reasons.append(f"latest verdict is red on un-deviated gate(s): {', '.join(uncovered)}")
        else:
            deviations_applied = sorted(
                int(d["seq"])
                for d in active
                if red_gates & set(d.get("gates", []))
                and (
                    not (d.get("spec_id") or "") or d.get("spec_id") == last_verdict.get("spec_id")
                )
            )

    # 2b. An emergency cleanup overdue past one working day blocks the advance.
    overdue = deviations.overdue_emergencies(entries)
    if overdue:
        reasons.append(
            f"emergency cleanup overdue ({len(overdue)}) — file the follow-up requirement and "
            "`3pwr deviation --revoke <seq>`"
        )

    # 3. A human sign-off must exist at or after the latest verdict.
    last_signoff = ledger.latest_of("signoff")
    if not last_signoff:
        reasons.append("no human sign-off recorded")
    elif last_verdict and last_signoff.get("seq", -1) < last_verdict.get("seq", 0):
        reasons.append("sign-off predates the latest verdict")

    # 4. Oracle independence. The judiciary must have authored the oracle
    #    from the spec, with a different model family, before the implementation. This binds at the
    #    High-risk tier only (oracle separation IS High-risk, spec §4); lower tiers stay advisory.
    #    Detection that the author *touched* the implementation is advisory — surfaced, never blocking.
    #    At High-risk, physical read-path isolation is also proven when a dispatch
    #    attestation is present — and *required* when the repo opts in (roles.oracle.require_dispatch).
    oracle_ok: Optional[bool] = None
    oracle_advisory: list[str] = []
    oracle_dispatch_ok: Optional[bool] = None
    oracle_isolation: Optional[str] = None
    oracle_diversity_relaxed = False
    spec_for_oracle = args.spec_id or (last_verdict.get("spec_id") if last_verdict else "") or ""
    tier = (last_verdict.get("payload", {}) if last_verdict else {}).get("tier")
    if tier == "High-risk":
        rec = oracle.authoring_record(entries, spec_for_oracle)
        test_roots = [s.root / p for p in rec["payload"].get("test_paths", [])] if rec else []
        oracle_diversity_relaxed = deviations.covers_model_diversity(active, spec_for_oracle)
        ind = oracle.independence(
            entries,
            s.load_roles(),
            spec_for_oracle,
            repo_root=s.root,
            test_roots=test_roots,
            require_dispatch=s.oracle_require_dispatch(),
            diversity_relaxed=oracle_diversity_relaxed,
            diversity_level=s.diversity_level(),
            coder_model=s.coder_model(),
        )
        oracle_ok = ind.ok
        oracle_advisory = ind.advisory
        oracle_dispatch_ok = ind.dispatch_ok
        oracle_isolation = ind.isolation_method
        if not ind.ok:
            reasons += [f"oracle independence — {r}" for r in ind.reasons]

    # 5. Spec integrity: once a human has approved the spec, its recorded
    #    hash must still match the document on disk — at every tier. A signed, active
    #    `spec_integrity` deviation turns the refusal into a warned,
    #    recorded pass; revoking or expiring it re-blocks. A never-approved spec is
    #    never blocked.
    lock = speclock.check(entries, spec_for_oracle, s.root)
    spec_integrity_deviated = False
    if not lock.ok:
        if speclock.GATE_NAME in deviations.covered_gates(active, spec_for_oracle):
            spec_integrity_deviated = True
            dev_seqs = [
                int(d["seq"])
                for d in active
                if speclock.GATE_NAME in d.get("gates", [])
                and (not (d.get("spec_id") or "") or d.get("spec_id") == spec_for_oracle)
            ]
            deviations_applied = sorted(set(deviations_applied) | set(dev_seqs))
        else:
            reasons.append(
                f"spec_modified — spec changed after approval (ledger seq={lock.approval_seq}); "
                "review with `3pwr spec diff`, re-approve via `3pwr signoff --stage spec`, or "
                "record a `3pwr deviation --gate spec_integrity`"
            )

    # 6. Git run discipline: when the spec's run records a dedicated branch, a
    #    stage-boundary advance refuses off the run branch or with the completed stage's work
    #    uncommitted — naming the condition and the fix. Relaxable only via the named signed
    #    deviations; a ledger predating branch binding records no branch and is untouched.
    git_branch = gitflow.branch_from_ledger(entries, spec_for_oracle)
    if git_branch:
        covered_git = deviations.covered_gates(active, spec_for_oracle)
        git_cond = gitflow.precondition(s.root)
        if git_cond:
            reasons.append(f"git — {git_cond}")
        else:
            cur_branch = gitflow.current_branch(s.root)
            if cur_branch != git_branch and deviations.GIT_RUN_BRANCH not in covered_git:
                reasons.append(
                    f"git — not on the run's dedicated branch '{git_branch}' (currently "
                    f"'{cur_branch or 'detached HEAD'}'); `git checkout {git_branch}`, or record "
                    f"`3pwr deviation --gate {deviations.GIT_RUN_BRANCH}`"
                )
            dirty = gitflow.uncommitted_run_paths(s.root, entries, spec_for_oracle)
            if dirty and deviations.GIT_STAGE_COMMIT not in covered_git:
                shown = ", ".join(dirty[:5]) + (" …" if len(dirty) > 5 else "")
                reasons.append(
                    f"git — the completed stage's work is not committed: {shown}; commit it on "
                    f"'{git_branch}', or record `3pwr deviation --gate {deviations.GIT_STAGE_COMMIT}`"
                )

    if reasons:
        cst = _styler(args)
        rows = [cst.status_row("fail", f"REFUSED to advance to '{args.stage}'")]
        rows += [cst.status_row("fail", r, indent=4) for r in reasons]
        rows += [
            cst.status_row("warn", f"advisory (not a blocker): {a}", indent=4)
            for a in oracle_advisory
        ]
        _print(
            {
                "advanced": False,
                "stage": args.stage,
                "reasons": reasons,
                "oracle_advisory": oracle_advisory,
            },
            args.json,
            _compose(args, cst, title="advance", subject=args.spec_id or args.stage, rows=rows),
        )
        return EXIT_FAIL

    payload: dict = {"stage": args.stage}
    if deviations_applied:
        payload["deviations_applied"] = deviations_applied
    if spec_integrity_deviated:
        payload["spec_integrity_deviated"] = True
    if oracle_ok is not None:
        payload["oracle_ok"] = oracle_ok
    if oracle_dispatch_ok is not None:
        payload["dispatch_ok"] = oracle_dispatch_ok
    if oracle_isolation:
        payload["isolation_method"] = oracle_isolation
    if oracle_diversity_relaxed:
        payload["diversity_relaxed"] = True
    try:
        sk = keys.resolve_signer(s.root)
        entry = ledger.append("stage_advance", payload, sk, spec_id=args.spec_id or "")
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    note = f" under deviation {deviations_applied}" if deviations_applied else ""
    cst = _styler(args)
    rows = [
        cst.status_row("pass", f"advanced to '{args.stage}'{note}", f"ledger seq={entry['seq']}")
    ]
    rows += [
        cst.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in oracle_advisory
    ]
    _print(
        {
            "advanced": True,
            "stage": args.stage,
            "ledger_seq": entry["seq"],
            "oracle_advisory": oracle_advisory,
            **payload,
        },
        args.json,
        _compose(args, cst, title="advance", subject=args.spec_id or args.stage, rows=rows),
    )
    return EXIT_OK


def cmd_ledger_show(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    if args.json:
        print(json.dumps(entries, indent=2))
        return EXIT_OK
    lst = _styler(args)
    if not entries:
        print(_compose(args, lst, title="ledger", rows=[lst.status_row("info", "empty ledger")]))
        return EXIT_OK
    table_rows = [
        [
            f"#{e['seq']}",
            e["type"],
            e["timestamp"],
            e.get("spec_id", "") or "—",
            e["signer_key_id"],
        ]
        for e in entries
    ]
    out = []
    if _verbosity(args) != "quiet":
        out.append(
            lst.header("ledger", f"{len(entries)} entr{'y' if len(entries) == 1 else 'ies'}")
        )
    out.append(lst.table(table_rows, headers=["seq", "type", "timestamp", "spec", "signer"]))
    print("\n".join(out))
    return EXIT_OK


def cmd_revert(args: argparse.Namespace) -> int:
    """Reverse to a prior recorded state via a signed reversal entry."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    entries = ledger.entries()
    target = next((e for e in entries if e["seq"] == args.to), None)
    if target is None:
        print(f"error: no ledger entry with seq={args.to}", file=sys.stderr)
        return EXIT_USAGE
    spec_id = target.get("spec_id") or ""
    state_at = lifecycle.derive([e for e in entries if e["seq"] <= args.to])
    to_stage = state_at[spec_id].stage if spec_id in state_at else lifecycle.STAGES[1]
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = ledger.append(
        "reversal",
        {"to_seq": args.to, "to_stage": to_stage, "reason": args.reason or ""},
        sk,
        spec_id=spec_id,
    )
    rvt = _styler(args)
    _print(
        {"reverted_to_seq": args.to, "to_stage": to_stage, "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            rvt,
            title="revert",
            subject=spec_id or "(global)",
            rows=[
                rvt.status_row(
                    "pass",
                    f"reverted {spec_id or '(global)'} to stage '{to_stage}' (state @seq={args.to})",
                    f"ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def _register_verify(sub: SubParsers, common: AddCommon) -> None:
    vp = common(sub.add_parser("verify", help="verify the ledger (offline)"))
    vp.add_argument(
        "--anchored",
        action="store_true",
        help="also cross-check the chain against the latest local anchor tag",
    )
    vp.set_defaults(func=cmd_verify)


def _register_anchor(sub: SubParsers, common: AddCommon) -> None:
    anp = common(
        sub.add_parser("anchor", help="record the ledger head with an external witness (opt-in)")
    )
    anp.add_argument(
        "--push", action="store_true", help="push the anchor tag to the remote (network)"
    )
    anp.add_argument("--remote", default="origin", help="git remote for --push (default: origin)")
    anp.set_defaults(func=cmd_anchor)


def _register_signoff(sub: SubParsers, common: AddCommon) -> None:
    sp = common(sub.add_parser("signoff", help="record a signed human sign-off"))
    sp.add_argument("--approver", required=True, help="approver identity (a person)")
    sp.add_argument("--stage", default="review")
    sp.add_argument("--note")
    sp.add_argument("--spec-id", dest="spec_id")
    sp.add_argument(
        "--spec",
        help="path to the approved spec.md — its hash is sealed into a Spec-stage sign-off "
        "(default: the newest spec under specs-src/)",
    )
    sp.set_defaults(func=cmd_signoff)


def _register_advance(sub: SubParsers, common: AddCommon) -> None:
    ap = common(sub.add_parser("advance", help="enforce gate+ledger+sign-off before advancing"))
    ap.add_argument("--stage", required=True)
    ap.add_argument("--spec-id", dest="spec_id")
    ap.set_defaults(func=cmd_advance)


def _register_revert(sub: SubParsers, common: AddCommon) -> None:
    rvp = common(sub.add_parser("revert", help="reverse to a prior recorded state (signed)"))
    rvp.add_argument("--to", type=int, required=True, help="ledger seq to revert to")
    rvp.add_argument("--reason")
    rvp.set_defaults(func=cmd_revert)


def _register_ledger(sub: SubParsers, common: AddCommon) -> None:
    lp = sub.add_parser("ledger", help="ledger operations")
    lsub = lp.add_subparsers(dest="ledger_cmd", required=True)
    ls = common(lsub.add_parser("show", help="print the ledger"))
    ls.set_defaults(func=cmd_ledger_show)


def _register_spec(sub: SubParsers, common: AddCommon) -> None:
    spp = sub.add_parser("spec", help="spec operations: integrity diff")
    spsub = spp.add_subparsers(dest="spec_cmd", required=True)
    spd = common(
        spsub.add_parser(
            "diff",
            help="read-only: does the spec still match its approval hash? (never writes)",
        )
    )
    spd.add_argument("--spec-id", dest="spec_id", required=True)
    spd.add_argument("--spec", help="path to the spec.md (default: the path recorded at approval)")
    spd.set_defaults(func=cmd_spec_diff)
