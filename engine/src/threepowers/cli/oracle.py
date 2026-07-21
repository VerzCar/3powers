"""Oracle-independence commands: ``roles-check`` plus ``oracle``
seal / record / verify / dispatch."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional


from .. import (
    agents,
    canonical,
    covdiff,
    deviations,
    keys,
    oracle,
    workspace,
)
from ..config import model_diversity_ok
from ..ledger import Ledger
from ..runner import CliAgentRunner
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
    from ..config import Settings
    from ._common import AddCommon, SubParsers


def _feature_key(s: Settings, spec: Optional[str]) -> str:
    """The run/feature-context oracle key: the ``<NNN>-<slug>`` feature-folder name, or ``""``.

    Resolves the governing spec (an explicit path, else the newest feature spec) and, when it
    lives in a feature workspace folder (under ``specs-src/`` or the legacy ``specs/``), yields
    that folder's name — the one id the run's ledger records, the oracle test destination
    ``tests/oracle/<NNN>-<slug>/``, and the ``oracle.md`` record all share. A spec outside a
    feature workspace yields ``""`` so the caller falls back to its own default (the spec
    document's Spec ID, or an explicit ``--spec-id``). Deterministic and offline."""
    try:
        spec_path = _resolve_spec(s, spec)
    except FileNotFoundError:
        return ""
    fdir = workspace.feature_dir_of(spec_path)
    if fdir.parent.name in (workspace.SPECS_DIR, workspace.LEGACY_SPECS_DIR):
        return fdir.name
    return ""


def _require_oracle_key(s: Settings, args: argparse.Namespace) -> str:
    """The oracle key a keyed subcommand runs under: ``--spec-id``, else the feature-folder id.

    An explicit ``--spec-id`` always wins unchanged (old records keyed by other tokens keep
    verifying); otherwise the run/feature context supplies the ``<NNN>-<slug>`` folder name.
    Returns ``""`` when neither resolves — the caller reports the usage error."""
    return str(args.spec_id or "") or _feature_key(s, None)


_KEY_ERROR = (
    "error: could not resolve the oracle key from a feature workspace — pass "
    "--spec-id <NNN>-<slug> (the run's feature-folder name)"
)


def cmd_roles_check(args: argparse.Namespace) -> int:
    """Check model diversity between two roles, at the configured granularity.

    Recommended, not forced: a same-family setup passes only under a signed ``model_diversity``
    deviation, which turns the VIOLATION into a warned RELAXED (exit 0)."""
    s = _settings(args.root)
    level = s.diversity_level()
    ok = model_diversity_ok(s.load_roles(), args.role_a, args.role_b, level)
    dev_seq = None
    if not ok:
        active = deviations.active_deviations(Ledger(s.ledger_path).entries())
        dev_seq = deviations.diversity_deviation(active)  # global scope for a config-level check
    verdict = "OK" if ok else ("RELAXED" if dev_seq is not None else "VIOLATION")
    rct = _styler(args)
    state = "pass" if ok else ("warn" if dev_seq is not None else "fail")
    rows = [
        rct.status_row(
            state, f"model diversity ({level}) {args.role_a} vs {args.role_b}: {verdict}"
        )
    ]
    if dev_seq is not None:
        rows.append(
            rct.status_row(
                "warn",
                f"relaxed by model_diversity deviation #{dev_seq} — "
                f"a different {level} is recommended, not required",
                indent=4,
            )
        )
    _print(
        {
            "diverse": ok,
            "level": level,
            "relaxed_by_deviation": dev_seq,
            "role_a": args.role_a,
            "role_b": args.role_b,
        },
        args.json,
        _compose(
            args, rct, title="roles-check", subject=f"{args.role_a} vs {args.role_b}", rows=rows
        ),
    )
    return EXIT_OK if (ok or dev_seq is not None) else EXIT_FAIL


def cmd_oracle_seal(args: argparse.Namespace) -> int:
    """Seal a spec-only oracle bundle the judiciary authors from."""
    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    doc_spec_id, criteria = oracle.extract_criteria(spec_path)
    # The seal's storage key: an explicit --spec-id wins; a spec inside a feature workspace keys
    # by its <NNN>-<slug> folder name (the same id the run's ledger and the oracle test
    # destination use); otherwise the spec document's own Spec ID is the fallback. The sealed
    # requirement ids keep their document namespace regardless of the key.
    spec_id = args.spec_id or _feature_key(s, args.spec) or doc_spec_id
    if not spec_id:
        print("error: could not determine the spec id; pass --spec-id", file=sys.stderr)
        return EXIT_USAGE
    if not criteria:
        print("error: no requirement ids / acceptance criteria found in the spec", file=sys.stderr)
        return EXIT_USAGE
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    source = os.path.relpath(spec_path, s.root)
    bundle = oracle.build_bundle(spec_id, source, criteria, deviations.iso(deviations.now_utc()))
    out = s.dir / "oracle" / spec_id / "sealed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(bundle, indent=2) + "\n", encoding="utf-8")
    entry = Ledger(s.ledger_path).append(
        "oracle",
        oracle.seal_payload(spec_id, source, criteria),
        sk,
        spec_id=spec_id,
        requirement_ids=sorted(criteria),
    )
    ost = _styler(args)
    _print(
        {
            "sealed": str(out),
            "bundle_hash": bundle["bundle_hash"],
            "requirement_ids": bundle["requirement_ids"],
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(
            args,
            ost,
            title="oracle seal",
            subject=spec_id,
            rows=[
                ost.status_row(
                    "pass",
                    f"sealed oracle bundle for {spec_id}: {len(criteria)} acceptance criteria",
                    str(out),
                ),
                ost.kv([("bundle hash", bundle["bundle_hash"]), ("ledger", f"seq={entry['seq']}")]),
            ],
        ),
    )
    return EXIT_OK


def cmd_oracle_record(args: argparse.Namespace) -> int:
    """Record oracle authoring; refuse the coder's model family."""
    s = _settings(args.root)
    args.spec_id = _require_oracle_key(s, args)
    if not args.spec_id:
        print(_KEY_ERROR, file=sys.stderr)
        return EXIT_USAGE
    entries = Ledger(s.ledger_path).entries()
    seal = oracle.active_seal(entries, args.spec_id)
    if seal is None:
        print(
            f"error: no sealed bundle for {args.spec_id} — run `3pwr oracle seal` first",
            file=sys.stderr,
        )
        return EXIT_USAGE
    fam = oracle.family_of(args.model)
    coder = oracle.coder_family(s.load_roles())
    level = s.diversity_level()
    coder_side = s.coder_model() or coder
    if not fam:
        print("error: --model must be <family/model> (e.g. anthropic/claude-...)", file=sys.stderr)
        return EXIT_USAGE
    if not coder:
        print("error: coder model family is unset in roles.yaml", file=sys.stderr)
        return EXIT_USAGE
    # Diversity is recommended, not forced: a same-family/model setup proceeds only under
    # a signed model_diversity deviation — warned and recorded, never a silent drop.
    diversity_dev: Optional[int] = None
    if not oracle.diverse(coder_side, args.model, level):
        diversity_dev = deviations.diversity_deviation(
            deviations.active_deviations(entries), args.spec_id
        )
        if diversity_dev is None:
            ort = _styler(args)
            _print(
                {
                    "recorded": False,
                    "reason": "same_model_family",
                    "oracle_family": fam,
                    "coder_family": coder,
                    "level": level,
                },
                args.json,
                _compose(
                    args,
                    ort,
                    title="oracle record",
                    subject=args.spec_id,
                    rows=[
                        ort.status_row(
                            "fail",
                            f"REFUSED: oracle model '{args.model}' is not diverse from the coder "
                            f"at {level} level",
                        ),
                        ort.status_row(
                            "info",
                            "the judiciary must differ. Diversity is recommended, not forced: "
                            "record a `3pwr deviation --gate model_diversity --approver <you> "
                            "--note ...` to proceed anyway",
                            indent=4,
                        ),
                    ],
                ),
            )
            return EXIT_FAIL

    test_paths: list[str] = []
    test_hashes: dict[str, str] = {}
    test_texts: dict[str, str] = {}
    for t in args.tests:
        tp = Path(t).resolve()
        if not tp.exists():
            print(f"error: oracle test not found: {tp}", file=sys.stderr)
            return EXIT_USAGE
        rel = os.path.relpath(tp, s.root)
        text = tp.read_text(encoding="utf-8")
        test_paths.append(rel)
        test_hashes[rel] = canonical.sha256_hex(text.encode("utf-8"))
        test_texts[rel] = text

    # Advisory (non-blocking) peek/touch signals for human review.
    bundle_file = s.dir / "oracle" / args.spec_id / "sealed.json"
    criteria_text = ""
    if bundle_file.exists():
        data = json.loads(bundle_file.read_text(encoding="utf-8"))
        criteria_text = " ".join(c.get("text", "") for c in data.get("criteria", []))
    advisory = oracle.scan_touched_impl(
        covdiff.changed_files(s.root, args.base), set(test_paths)
    ) + oracle.scan_symbol_leakage(test_texts, criteria_text)

    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = oracle.record_payload(
        seal["payload"]["bundle_hash"], args.model, test_paths, test_hashes, advisory, diversity_dev
    )
    entry = Ledger(s.ledger_path).append(
        "oracle",
        payload,
        sk,
        spec_id=args.spec_id,
        requirement_ids=seal["payload"].get("requirement_ids", []),
    )
    ort = _styler(args)
    rows = [
        ort.status_row(
            "pass",
            f"recorded oracle authoring for {args.spec_id} by {args.model}",
            f"family={fam}; {len(test_paths)} test file(s); ledger seq={entry['seq']}",
        )
    ]
    if diversity_dev is not None:
        rows.append(
            ort.status_row(
                "warn",
                f"model diversity RELAXED by deviation #{diversity_dev} — "
                f"same {level} as the coder; not the recommended posture",
                indent=4,
            )
        )
    rows += [ort.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in advisory]
    _print(
        {
            "recorded": True,
            "model_family": fam,
            "test_paths": test_paths,
            "advisory_findings": advisory,
            "diversity_deviation": diversity_dev,
            "ledger_seq": entry["seq"],
        },
        args.json,
        _compose(args, ort, title="oracle record", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK


def cmd_oracle_verify(args: argparse.Namespace) -> int:
    """Verify oracle independence structurally, from the ledger."""
    s = _settings(args.root)
    args.spec_id = _require_oracle_key(s, args)
    if not args.spec_id:
        print(_KEY_ERROR, file=sys.stderr)
        return EXIT_USAGE
    entries = Ledger(s.ledger_path).entries()
    rec = oracle.authoring_record(entries, args.spec_id)
    if args.tests:
        test_roots = [Path(t).resolve() for t in args.tests]
    elif rec:
        test_roots = [s.root / p for p in rec["payload"].get("test_paths", [])]
    else:
        test_roots = []
    ind = oracle.independence(
        entries,
        s.load_roles(),
        args.spec_id,
        repo_root=s.root,
        test_roots=test_roots,
        require_dispatch=args.require_dispatch,
        diversity_relaxed=deviations.covers_model_diversity(
            deviations.active_deviations(entries), args.spec_id
        ),
        diversity_level=s.diversity_level(),
        coder_model=s.coder_model(),
    )
    ovt = _styler(args)
    rows = [
        ovt.status_row(
            "pass" if ind.ok else "fail",
            f"oracle independence for {args.spec_id}: {'PASS' if ind.ok else 'FAIL'}",
        )
    ]
    kv_pairs = []
    if ind.model_family:
        kv_pairs.append(("oracle model family", ind.model_family))
    if ind.covered:
        kv_pairs.append(("covered", ", ".join(ind.covered)))
    if kv_pairs:
        rows.append(ovt.kv(kv_pairs))
    if ind.isolation_method:
        rows.append(
            ovt.status_row(
                "pass" if ind.dispatch_ok else "fail",
                f"read-path isolation: {ind.isolation_method}",
                indent=4,
            )
        )
    for r in ind.reasons:
        rows.append(ovt.status_row("fail", r, indent=4))
    for a in ind.advisory:
        rows.append(ovt.status_row("warn", f"advisory (not a blocker): {a}", indent=4))
    _print(
        {
            "ok": ind.ok,
            "reasons": ind.reasons,
            "advisory": ind.advisory,
            "covered": ind.covered,
            "model_family": ind.model_family,
            "dispatch_ok": ind.dispatch_ok,
            "isolation_method": ind.isolation_method,
        },
        args.json,
        _compose(args, ovt, title="oracle verify", subject=args.spec_id, rows=rows),
    )
    return EXIT_OK if ind.ok else EXIT_FAIL


def cmd_oracle_dispatch(args: argparse.Namespace) -> int:
    """Author the oracle headlessly under a non-coder integration, in a sanitized worktree from
    which the implementation is physically absent.

    Dispatch is Phase-A provisioning, recorded in the ledger — it never enters the deterministic
    gate verdict. The blocking isolation check binds at ``advance`` (High-risk)."""
    s = _settings(args.root)
    args.spec_id = _require_oracle_key(s, args)
    if not args.spec_id:
        print(_KEY_ERROR, file=sys.stderr)
        return EXIT_USAGE
    ledger = Ledger(s.ledger_path)
    seal = oracle.active_seal(ledger.entries(), args.spec_id)
    if seal is None:
        print(
            f"error: no sealed bundle for {args.spec_id} — run `3pwr oracle seal` first",
            file=sys.stderr,
        )
        return EXIT_USAGE

    # Resolve the oracle model/family. Diversity is recommended, not forced: a
    # same-family/model dispatch proceeds only under a signed model_diversity deviation.
    coder = oracle.coder_family(s.load_roles())
    coder_side = s.coder_model() or coder
    level = s.diversity_level()
    intg_family = oracle.integration_family(args.integration)
    model = args.model or (f"{intg_family}/{args.integration}" if intg_family else "")
    if not model:
        print(
            f"error: cannot resolve a model family for integration '{args.integration}'; "
            "pass --model <family/model>",
            file=sys.stderr,
        )
        return EXIT_USAGE
    fam = oracle.family_of(model)
    diversity_dev: Optional[int] = None
    if coder and not oracle.diverse(coder_side, model, level):
        diversity_dev = deviations.diversity_deviation(
            deviations.active_deviations(ledger.entries()), args.spec_id
        )
        if diversity_dev is None:
            odt = _styler(args)
            _print(
                {
                    "dispatched": False,
                    "reason": "same_model_family",
                    "oracle_family": fam,
                    "coder_family": coder,
                    "level": level,
                },
                args.json,
                _compose(
                    args,
                    odt,
                    title="oracle dispatch",
                    subject=args.spec_id,
                    rows=[
                        odt.status_row(
                            "fail",
                            f"REFUSED: dispatch integration '{args.integration}' (model '{model}') "
                            f"is not diverse from the coder at {level} level",
                        ),
                        odt.status_row(
                            "info",
                            "the judiciary must differ. Record a `3pwr deviation --gate "
                            "model_diversity --approver <you> --note ...` to proceed anyway",
                            indent=4,
                        ),
                    ],
                ),
            )
            return EXIT_FAIL

    sealed_bundle = s.dir / "oracle" / args.spec_id / "sealed.json"
    worktree_dir = s.dir / "worktrees" / args.spec_id
    advisory: list[str] = []
    try:
        try:
            info = oracle.build_sanitized_worktree(
                s.root, worktree_dir, sealed_bundle, base_ref=args.base
            )
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_FAIL
        violations = oracle.isolation_violations(info.manifest)
        if violations:
            print(
                "error: worktree isolation failed — implementation still present: "
                + ", ".join(violations[:5]),
                file=sys.stderr,
            )
            return EXIT_FAIL

        # Dispatch the authoring step to the oracle agent directly, headless, inside the sanitized
        # worktree — no external workflow substrate (supersedes the Spec Kit dispatch).
        # The engine issues no model call itself; the agent process does.
        dispatched_model = model
        if not args.dry_run:
            try:
                oracle_manifest = agents.load_agent(s, args.integration)
            except FileNotFoundError as exc:
                print(f"error: {exc} — add the manifest or use --dry-run", file=sys.stderr)
                return EXIT_USAGE
            if not agents.is_headless(oracle_manifest):
                print(
                    f"error: agent '{args.integration}' is not headless-dispatchable",
                    file=sys.stderr,
                )
                return EXIT_USAGE
            criteria = ""
            if sealed_bundle.exists():
                data = json.loads(sealed_bundle.read_text(encoding="utf-8"))
                criteria = " ".join(c.get("text", "") for c in data.get("criteria", []))
            orc = CliAgentRunner(
                s,
                oracle_manifest,
                model=model,
                cwd=info.path,
                intent=(
                    f"Author oracle tests into ./oracle-tests/ for spec {args.spec_id}, from the "
                    "sealed acceptance criteria ONLY — do not read any implementation."
                ),
                spec_text=criteria,
            )
            res = orc.dispatch("oracle", "Build")
            if not res.ok:
                print("error: oracle dispatch failed:\n  " + res.detail, file=sys.stderr)
                return EXIT_FAIL
            dispatched_model = res.model or model

        # Collect authored oracle tests (from the worktree, or --tests for --dry-run / manual).
        # The destination is keyed by the oracle key — inside a run/feature context the
        # <NNN>-<slug> feature-folder id — so the collected files, the record, and the run's
        # ledger entries all resolve under one id.
        dest_root = s.root / "tests" / "oracle" / args.spec_id
        if args.tests:
            sources = [Path(t).resolve() for t in args.tests]
        else:
            out_dir = info.path / "oracle-tests"
            sources = (
                sorted(f for f in out_dir.rglob("*") if f.is_file()) if out_dir.is_dir() else []
            )
        test_paths: list[str] = []
        test_hashes: dict[str, str] = {}
        test_texts: dict[str, str] = {}
        for src in sources:
            if not src.exists():
                print(f"error: oracle test not found: {src}", file=sys.stderr)
                return EXIT_USAGE
            text = src.read_text(encoding="utf-8")
            dest = dest_root / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")
            rel = os.path.relpath(dest, s.root)
            test_paths.append(rel)
            test_hashes[rel] = canonical.sha256_hex(text.encode("utf-8"))
            test_texts[rel] = text

        # Advisory (non-blocking) peek/touch signals, unchanged from the standalone oracle path.
        criteria_text = ""
        if sealed_bundle.exists():
            data = json.loads(sealed_bundle.read_text(encoding="utf-8"))
            criteria_text = " ".join(c.get("text", "") for c in data.get("criteria", []))
        advisory = oracle.scan_touched_impl(
            covdiff.changed_files(s.root, args.base), set(test_paths)
        ) + oracle.scan_symbol_leakage(test_texts, criteria_text)

        # Sign the record + dispatch attestation with the (optional) distinct oracle identity.
        try:
            osk = keys.resolve_signer(s.root, role="oracle")
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_USAGE
        seal_hash = seal["payload"]["bundle_hash"]
        req_ids = seal["payload"].get("requirement_ids", [])
        rec_entry = ledger.append(
            "oracle",
            oracle.record_payload(
                seal_hash, dispatched_model, test_paths, test_hashes, advisory, diversity_dev
            ),
            osk,
            spec_id=args.spec_id,
            requirement_ids=req_ids,
        )
        disp_entry = ledger.append(
            "oracle",
            oracle.dispatch_payload(
                seal_hash,
                args.integration,
                dispatched_model,
                {
                    "method": "git-worktree",
                    "manifest_hash": info.manifest_hash,
                    "file_count": info.file_count,
                    "excluded_absent": True,
                },
            ),
            osk,
            spec_id=args.spec_id,
            requirement_ids=req_ids,
        )

        odt = _styler(args)
        rows = [
            odt.status_row(
                "pass",
                f"dispatched oracle authoring for {args.spec_id} under '{args.integration}'",
                f"family={fam}; {len(test_paths)} test file(s)",
            ),
            odt.status_row(
                "pass",
                f"read-path isolation via git-worktree ({info.file_count} files, "
                "implementation absent)",
                indent=4,
            ),
            odt.kv(
                [
                    ("record", f"seq={rec_entry['seq']}"),
                    ("dispatch", f"seq={disp_entry['seq']}"),
                    ("manifest", info.manifest_hash),
                ]
            ),
        ]
        if diversity_dev is not None:
            rows.append(
                odt.status_row(
                    "warn",
                    f"model diversity RELAXED by deviation #{diversity_dev} — "
                    f"same {level} as the coder; not the recommended posture",
                    indent=4,
                )
            )
        if args.dry_run:
            rows.append(
                odt.status_row(
                    "info",
                    "dry-run: worktree isolation built + attested; no live agent dispatched",
                    indent=4,
                )
            )
        rows += [
            odt.status_row("warn", f"advisory (not a blocker): {a}", indent=4) for a in advisory
        ]
        _print(
            {
                "dispatched": True,
                "integration": args.integration,
                "model": dispatched_model,
                "model_family": fam,
                "test_paths": test_paths,
                "manifest_hash": info.manifest_hash,
                "file_count": info.file_count,
                "excluded_absent": True,
                "advisory_findings": advisory,
                "diversity_deviation": diversity_dev,
                "record_seq": rec_entry["seq"],
                "dispatch_seq": disp_entry["seq"],
            },
            args.json,
            _compose(args, odt, title="oracle dispatch", subject=args.spec_id, rows=rows),
        )
        return EXIT_OK
    finally:
        if not args.keep_worktree:
            oracle.teardown_worktree(s.root, worktree_dir)


def _register_roles_check(sub: SubParsers, common: AddCommon) -> None:
    rp = common(
        sub.add_parser("roles-check", help="check model-family diversity between two roles")
    )
    rp.add_argument("--role-a", dest="role_a", default="oracle")
    rp.add_argument("--role-b", dest="role_b", default="coder")
    rp.set_defaults(func=cmd_roles_check)


def _register_oracle(sub: SubParsers, common: AddCommon) -> None:
    orp = sub.add_parser(
        "oracle",
        help="oracle independence: seal / record / dispatch / verify",
    )
    osub = orp.add_subparsers(dest="oracle_cmd", required=True)
    # One key threads seal → record → dispatch → verify: the run's <NNN>-<slug> feature-folder
    # name, defaulted from the feature workspace so the oracle files, records, and the run's
    # ledger all resolve under the id the user browses; an explicit --spec-id always wins.
    key_help = (
        "the oracle key — the run's feature-folder name <NNN>-<slug> (the folder the numeric run "
        "id names); default: resolved from the feature workspace"
    )
    osl = common(osub.add_parser("seal", help="seal a spec-only oracle bundle"))
    osl.add_argument("--spec", help="path to the governing spec.md")
    osl.add_argument("--spec-id", dest="spec_id", help=key_help)
    osl.set_defaults(func=cmd_oracle_seal)
    orc = common(
        osub.add_parser("record", help="record oracle authoring; refuse the coder's model family")
    )
    orc.add_argument("--spec-id", dest="spec_id", help=key_help)
    orc.add_argument("--model", required=True, help="oracle model as <family/model>")
    orc.add_argument("--tests", nargs="+", required=True, help="oracle test file(s)")
    orc.add_argument("--base", help="git ref for the touched-implementation advisory scan")
    orc.set_defaults(func=cmd_oracle_record)
    ovf = common(osub.add_parser("verify", help="verify oracle independence"))
    ovf.add_argument("--spec-id", dest="spec_id", help=key_help)
    ovf.add_argument("--tests", nargs="*", help="oracle test roots (default: from the record)")
    ovf.add_argument(
        "--require-dispatch",
        dest="require_dispatch",
        action="store_true",
        help="require an isolated headless-dispatch attestation",
    )
    ovf.set_defaults(func=cmd_oracle_verify)
    odp = common(
        osub.add_parser("dispatch", help="author the oracle headlessly, read-path isolated")
    )
    odp.add_argument("--spec-id", dest="spec_id", help=key_help)
    odp.add_argument(
        "--integration",
        default="claude",
        help="headless agent backend for the oracle step (a non-coder family; default: claude)",
    )
    odp.add_argument("--model", help="override the resolved oracle model as <family/model>")
    odp.add_argument("--base", help="clean git ref for the sanitized worktree (default: HEAD)")
    odp.add_argument(
        "--tests",
        nargs="*",
        help="treat these as the authored oracle tests (for --dry-run / manual authoring)",
    )
    odp.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="build + attest worktree isolation without a live agent dispatch",
    )
    odp.add_argument(
        "--keep-worktree",
        dest="keep_worktree",
        action="store_true",
        help="do not tear down the worktree (debugging)",
    )
    odp.set_defaults(func=cmd_oracle_dispatch)
