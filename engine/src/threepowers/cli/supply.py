"""Supply-chain commands: ``provenance``, ``deploy-gate``, ``residual``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING


from .. import (
    keys,
    provenance,
)
from ..ledger import Ledger
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


def cmd_provenance(args: argparse.Namespace) -> int:
    """Sign build provenance + SBOM for an artifact."""
    s = _settings(args.root)
    artifact = Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"error: artifact not found: {artifact}", file=sys.stderr)
        return EXIT_USAGE
    target = Path(args.path).resolve() if args.path else s.root
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    signed = provenance.sign_record(provenance.build_record(s.root, target, artifact), sk)
    pdir = s.dir / "provenance"
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"{signed['artifact']['sha256'].split(':')[1]}.json").write_text(
        json.dumps(signed, indent=2) + "\n", encoding="utf-8"
    )
    entry = Ledger(s.ledger_path).append(
        "provenance",
        {"artifact": signed["artifact"], "source_commit": signed["source_commit"]},
        sk,
        spec_id=args.spec_id or "",
    )
    pst = _styler(args)
    _print(
        {"artifact": signed["artifact"], "ledger_seq": entry["seq"]},
        args.json,
        _compose(
            args,
            pst,
            title="provenance",
            subject=artifact.name,
            rows=[
                pst.status_row(
                    "pass",
                    f"provenance signed for {artifact.name} ({signed['artifact']['sha256']})",
                    f"{len(signed['sbom']['components'])} SBOM components; ledger seq={entry['seq']}",
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_deploy_gate(args: argparse.Namespace) -> int:
    """Verify an artifact's provenance; refuse if missing or invalid."""
    s = _settings(args.root)
    artifact = Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"error: artifact not found: {artifact}", file=sys.stderr)
        return EXIT_USAGE
    digest = provenance.sha256_file(artifact)
    pfile = s.dir / "provenance" / f"{digest.split(':')[1]}.json"
    reasons: list[str] = []
    if not pfile.exists():
        reasons.append("no provenance record for this artifact hash")
    else:
        record = json.loads(pfile.read_text(encoding="utf-8"))
        if record.get("artifact", {}).get("sha256") != digest:
            reasons.append("artifact hash does not match provenance")
        if not s.pubkey_path.exists():
            reasons.append("public key not found")
        elif not provenance.verify_record(record, keys.load_public(s.pubkey_path)):
            reasons.append("provenance signature invalid")
    dgt = _styler(args)
    if reasons:
        rows = [dgt.status_row("fail", f"DEPLOY REFUSED for {artifact.name}")]
        rows += [dgt.status_row("fail", r, indent=4) for r in reasons]
        _print(
            {"deployable": False, "reasons": reasons},
            args.json,
            _compose(args, dgt, title="deploy-gate", subject=artifact.name, rows=rows),
        )
        return EXIT_FAIL
    _print(
        {"deployable": True, "artifact": digest},
        args.json,
        _compose(
            args,
            dgt,
            title="deploy-gate",
            subject=artifact.name,
            rows=[
                dgt.status_row(
                    "pass", f"deploy-gate PASS — provenance verified for {artifact.name}"
                )
            ],
        ),
    )
    return EXIT_OK


def cmd_residual(args: argparse.Namespace) -> int:
    """Record a signed residual review."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signer(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"reviewer": args.reviewer, "note": args.note or "", "findings": args.findings or []}
    entry = Ledger(s.ledger_path).append("residual", payload, sk, spec_id=args.spec_id or "")
    rst = _styler(args)
    print(
        _compose(
            args,
            rst,
            title="residual",
            subject=args.spec_id or "",
            rows=[
                rst.status_row(
                    "pass",
                    f"residual review recorded by {args.reviewer}",
                    f"ledger seq={entry['seq']}",
                )
            ],
        )
    )
    return EXIT_OK


def _register_provenance(sub: SubParsers, common: AddCommon) -> None:
    pvp = common(sub.add_parser("provenance", help="sign build provenance + SBOM for an artifact"))
    pvp.add_argument("--artifact", required=True)
    pvp.add_argument("--path", help="project dir for the SBOM (default: repo root)")
    pvp.add_argument("--spec-id", dest="spec_id")
    pvp.set_defaults(func=cmd_provenance)


def _register_deploy_gate(sub: SubParsers, common: AddCommon) -> None:
    dgp = common(
        sub.add_parser("deploy-gate", help="verify an artifact's provenance; refuse if bad")
    )
    dgp.add_argument("--artifact", required=True)
    dgp.set_defaults(func=cmd_deploy_gate)


def _register_residual(sub: SubParsers, common: AddCommon) -> None:
    rsp = common(sub.add_parser("residual", help="record a signed residual review"))
    rsp.add_argument("--reviewer", required=True)
    rsp.add_argument("--note")
    rsp.add_argument("--findings", nargs="*")
    rsp.add_argument("--spec-id", dest="spec_id")
    rsp.set_defaults(func=cmd_residual)
