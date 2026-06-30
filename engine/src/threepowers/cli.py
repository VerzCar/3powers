"""``3pwr`` — the 3Powers command line.

Subcommands:
  keygen        generate the independent Ed25519 signer identity (key kept outside repo)
  init          ensure the in-repo ``.3powers/`` trust-spine layout exists
  gate run      run the deterministic gate suite, emit a verdict, append it to the ledger
  conformance   run only the spec-conformance trace
  verify        recompute the ledger hash chain + signatures (offline)
  signoff       append a signed human sign-off entry
  advance       local enforcement gate: refuse to proceed unless gate green + ledger
                verifies + the tier-required sign-off is present
  ledger show   print the ledger

Exit codes: 0 = ok/green, 1 = gate failed / verification failed / advance refused,
2 = usage or environment error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import __version__, config, keys, lifecycle, provenance, scope
from .config import Settings, model_diversity_ok
from .gates import run_gates
from .ledger import Ledger
from .verdict import STATUS_PASS
from .verify import verify_ledger

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_USAGE = 2


# --------------------------------------------------------------------------- helpers
def _settings(root: Optional[str]) -> Settings:
    base = Path(root).resolve() if root else None
    return Settings(root=config.find_root(base))


def _resolve_spec(s: Settings, spec: Optional[str]) -> Path:
    if spec:
        return Path(spec).resolve()
    feat = s.root / ".specify" / "feature.json"
    if feat.exists():
        data = json.loads(feat.read_text(encoding="utf-8"))
        d = data.get("feature_directory")
        if d:
            cand = s.root / d / "spec.md"
            if cand.exists():
                return cand
    raise FileNotFoundError("could not resolve a spec; pass --spec <path/to/spec.md>")


def _print(obj: dict, as_json: bool, human: str) -> None:
    if as_json:
        print(json.dumps(obj, indent=2))
    else:
        print(human)


def _format_verdict(verdict, appended: Optional[dict]) -> str:
    """Human-readable verdict: failing gate, class, and offending item — no transcript needed (3PWR-NFR-011)."""
    mark = {"pass": "✓", "fail": "✗", "skip": "–"}
    lines = [
        f"verdict {verdict.result.upper()}  "
        f"spec={verdict.spec_id or '?'} tier={verdict.tier} adapter={verdict.adapter}"
    ]
    for g in verdict.gates:
        extra = ""
        if g.gate == "diff_coverage" and g.details:
            extra = f"  ({g.details.get('covered_pct')}% ≥ {g.details.get('threshold')}%)"
        elif g.gate == "spec_conformance" and g.details:
            extra = f"  ({len(g.details.get('requirement_ids', []))} requirements traced)"
        lines.append(
            f"  {mark.get(g.status, '?')} {g.gate}{(' · ' + g.tool) if g.tool else ''}{extra}"
        )
        for finding in g.findings[:5]:
            lines.append(f"      - {finding}")
    if verdict.failures:
        lines.append("  failures:")
        for fl in verdict.failures:
            detail = fl.get("detail") or fl.get("requirement_id") or fl.get("file") or ""
            lines.append(f"    • {fl['class']}: {detail}")
    if appended:
        lines.append(f"  ↳ ledger entry #{appended['seq']} signed by {appended['signer_key_id']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- commands
def cmd_keygen(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    out = Path(args.out).resolve() if args.out else keys.default_private_path(s.root)
    if out.exists() and not args.force:
        print(f"refusing to overwrite existing key at {out} (use --force)", file=sys.stderr)
        return EXIT_USAGE
    sk = keys.generate()
    keys.write_private(out, sk)
    keys.write_public(s.pubkey_path, sk.verify_key)
    print(f"signer identity created: {sk.key_id}")
    print(f"  private key (keep OUTSIDE the repo): {out}")
    print(f"  public key  (committed):             {s.pubkey_path}")
    print()
    print("Point the engine at the private key with:")
    print(f'  export THREEPOWERS_SIGNING_KEY_FILE="{out}"')
    return EXIT_OK


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd()
    s = Settings(root=root)
    for d in (
        s.dir / "config",
        s.dir / "schemas",
        s.dir / "adapters",
        s.dir / "keys",
        s.dir / "runs",
        s.dir / "verdicts",
    ):
        d.mkdir(parents=True, exist_ok=True)
    if not s.ledger_path.exists():
        s.ledger_path.touch()
    print(f"initialized 3Powers trust-spine layout under {s.dir}")
    return EXIT_OK


def cmd_gate_run(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else s.root
    spec_path = _resolve_spec(s, args.spec)

    verdict = run_gates(
        s,
        target,
        tier=args.tier,
        spec_path=spec_path,
        adapter_name=args.adapter,
        base=args.base,
        allow_mutation=args.mutation,
    )
    s.verdicts_dir.mkdir(parents=True, exist_ok=True)
    verdict.write(s.verdicts_dir / "latest.json")

    appended = None
    if not args.no_ledger:
        try:
            sk = keys.resolve_signing_key(s.root)
            appended = Ledger(s.ledger_path).append(
                "verdict",
                verdict.to_dict(),
                sk,
                spec_id=verdict.spec_id,
                requirement_ids=verdict.requirement_ids(),
            )
        except FileNotFoundError as exc:
            print(f"⚠️  ledger entry skipped: {exc}", file=sys.stderr)

    human = _format_verdict(verdict, appended)
    _print(
        {"verdict": verdict.to_dict(), "ledger_seq": (appended or {}).get("seq")}, args.json, human
    )
    return EXIT_OK if verdict.result == STATUS_PASS else EXIT_FAIL


def cmd_conformance(args: argparse.Namespace) -> int:
    from .conformance import run_conformance

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    roots = [Path(t).resolve() for t in args.tests] if args.tests else [s.root]
    gate = run_conformance(spec_path, roots)
    obj = {"gate": gate.gate, "status": gate.status, **gate.details}
    human = f"spec-conformance: {gate.status.upper()} ({gate.details.get('spec_id', '?')})"
    if gate.findings:
        human += "\n  - " + "\n  - ".join(gate.findings)
    _print(obj, args.json, human)
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


def cmd_verify(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    res = verify_ledger(s.ledger_path, s.pubkey_path)
    _print(
        {"ok": res.ok, "entries": res.entries, "problems": res.problems}, args.json, res.summary()
    )
    return EXIT_OK if res.ok else EXIT_FAIL


def cmd_signoff(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    try:
        sk = keys.resolve_signing_key(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"approver": args.approver, "stage": args.stage, "note": args.note or ""}
    entry = Ledger(s.ledger_path).append("signoff", payload, sk, spec_id=args.spec_id or "")
    print(
        f"sign-off recorded by {args.approver} for stage '{args.stage}' (ledger seq={entry['seq']})"
    )
    return EXIT_OK


def cmd_advance(args: argparse.Namespace) -> int:
    """Local, CI-independent enforcement (3PWR-FR-041/042)."""
    s = _settings(args.root)
    ledger = Ledger(s.ledger_path)
    reasons: list[str] = []

    # 1. Ledger must verify.
    vres = verify_ledger(s.ledger_path, s.pubkey_path)
    if not vres.ok:
        reasons.append("ledger fails verification")

    # 2. Latest verdict must be green.
    last_verdict = ledger.latest_of("verdict")
    if not last_verdict:
        reasons.append("no verdict recorded")
    elif last_verdict.get("payload", {}).get("result") != STATUS_PASS:
        reasons.append("latest verdict is red")

    # 3. A human sign-off must exist at or after the latest verdict (3PWR-FR-037).
    last_signoff = ledger.latest_of("signoff")
    if not last_signoff:
        reasons.append("no human sign-off recorded")
    elif last_verdict and last_signoff.get("seq", -1) < last_verdict.get("seq", 0):
        reasons.append("sign-off predates the latest verdict")

    if reasons:
        _print(
            {"advanced": False, "stage": args.stage, "reasons": reasons},
            args.json,
            f"REFUSED to advance to '{args.stage}':\n  - " + "\n  - ".join(reasons),
        )
        return EXIT_FAIL

    try:
        sk = keys.resolve_signing_key(s.root)
        entry = ledger.append(
            "stage_advance", {"stage": args.stage}, sk, spec_id=args.spec_id or ""
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    _print(
        {"advanced": True, "stage": args.stage, "ledger_seq": entry["seq"]},
        args.json,
        f"advanced to '{args.stage}' (ledger seq={entry['seq']})",
    )
    return EXIT_OK


def cmd_ledger_show(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    entries = Ledger(s.ledger_path).entries()
    if args.json:
        print(json.dumps(entries, indent=2))
        return EXIT_OK
    for e in entries:
        print(
            f"#{e['seq']:>3} {e['type']:<13} {e['timestamp']} "
            f"{e.get('spec_id', ''):<8} sig={e['signer_key_id']}"
        )
    if not entries:
        print("(empty ledger)")
    return EXIT_OK


def cmd_roles_check(args: argparse.Namespace) -> int:
    """Refuse when oracle and coder share a model family (3PWR-FR-022)."""
    s = _settings(args.root)
    roles = s.load_roles()
    ok = model_diversity_ok(roles, args.role_a, args.role_b)
    _print(
        {"diverse": ok, "role_a": args.role_a, "role_b": args.role_b},
        args.json,
        f"model diversity {args.role_a} vs {args.role_b}: {'OK' if ok else 'VIOLATION'}",
    )
    return EXIT_OK if ok else EXIT_FAIL


def cmd_status(args: argparse.Namespace) -> int:
    """Per-spec lifecycle stage, derived from the ledger (3PWR-FR-011/019)."""
    s = _settings(args.root)
    states = lifecycle.derive(Ledger(s.ledger_path).entries())
    if args.spec_id:
        states = {k: v for k, v in states.items() if k == args.spec_id}
    rows = [
        {
            "spec_id": st.spec_id,
            "stage": st.stage,
            "last_verdict": st.last_verdict,
            "signed_off": st.signed_off,
            "aborted": st.aborted,
        }
        for st in states.values()
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK
    if not rows:
        print("(no tracked specs in the ledger)")
    for r in rows:
        flags = []
        if r["signed_off"]:
            flags.append("signed-off")
        if r["aborted"]:
            flags.append("ABORTED")
        print(
            f"{r['spec_id']:<10} stage={r['stage']:<10} verdict={r['last_verdict']:<5} "
            f"{' '.join(flags)}"
        )
    return EXIT_OK


def cmd_revert(args: argparse.Namespace) -> int:
    """Reverse to a prior recorded state via a signed reversal entry (3PWR-FR-070)."""
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
        sk = keys.resolve_signing_key(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = ledger.append(
        "reversal",
        {"to_seq": args.to, "to_stage": to_stage, "reason": args.reason or ""},
        sk,
        spec_id=spec_id,
    )
    _print(
        {"reverted_to_seq": args.to, "to_stage": to_stage, "ledger_seq": entry["seq"]},
        args.json,
        f"reverted {spec_id or '(global)'} to stage '{to_stage}' (state @seq={args.to}); "
        f"recorded as ledger seq={entry['seq']}",
    )
    return EXIT_OK


def cmd_abort(args: argparse.Namespace) -> int:
    """Record an abort for a spec's run (3PWR-FR-019)."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signing_key(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    entry = Ledger(s.ledger_path).append(
        "abort", {"reason": args.reason or ""}, sk, spec_id=args.spec_id
    )
    print(f"aborted '{args.spec_id}' (ledger seq={entry['seq']})")
    return EXIT_OK


def cmd_coverage_check(args: argparse.Namespace) -> int:
    """Two-way requirement<->task coverage before code (3PWR-FR-015)."""
    from .conformance import two_way_coverage

    s = _settings(args.root)
    spec_path = _resolve_spec(s, args.spec)
    gate = two_way_coverage(spec_path, Path(args.tasks).resolve())
    human = f"coverage-map: {gate.status.upper()} ({gate.details.get('spec_id', '?')})"
    if gate.findings:
        human += "\n  - " + "\n  - ".join(gate.findings)
    _print({"status": gate.status, **gate.details}, args.json, human)
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


def cmd_scope_check(args: argparse.Namespace) -> int:
    """Task requirement-ID + file-scope discipline (3PWR-FR-016/017)."""
    s = _settings(args.root)
    target = Path(args.path).resolve() if args.path else None
    gate = scope.scope_check(Path(args.tasks).resolve(), s.root, base=args.base, target=target)
    human = f"scope-check: {gate.status.upper()}"
    if gate.findings:
        human += "\n  - " + "\n  - ".join(gate.findings)
    _print({"status": gate.status, **gate.details}, args.json, human)
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


def cmd_provenance(args: argparse.Namespace) -> int:
    """Sign build provenance + SBOM for an artifact (3PWR-FR-066/068)."""
    s = _settings(args.root)
    artifact = Path(args.artifact).resolve()
    if not artifact.exists():
        print(f"error: artifact not found: {artifact}", file=sys.stderr)
        return EXIT_USAGE
    target = Path(args.path).resolve() if args.path else s.root
    try:
        sk = keys.resolve_signing_key(s.root)
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
    _print(
        {"artifact": signed["artifact"], "ledger_seq": entry["seq"]},
        args.json,
        f"provenance signed for {artifact.name} ({signed['artifact']['sha256']}); "
        f"{len(signed['sbom']['components'])} SBOM components; ledger seq={entry['seq']}",
    )
    return EXIT_OK


def cmd_deploy_gate(args: argparse.Namespace) -> int:
    """Verify an artifact's provenance; refuse if missing or invalid (3PWR-FR-067)."""
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
    if reasons:
        _print(
            {"deployable": False, "reasons": reasons},
            args.json,
            f"DEPLOY REFUSED for {artifact.name}:\n  - " + "\n  - ".join(reasons),
        )
        return EXIT_FAIL
    _print(
        {"deployable": True, "artifact": digest},
        args.json,
        f"deploy-gate PASS — provenance verified for {artifact.name}",
    )
    return EXIT_OK


def cmd_residual(args: argparse.Namespace) -> int:
    """Record a signed residual review (3PWR-FR-036/037)."""
    s = _settings(args.root)
    try:
        sk = keys.resolve_signing_key(s.root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    payload = {"reviewer": args.reviewer, "note": args.note or "", "findings": args.findings or []}
    entry = Ledger(s.ledger_path).append("residual", payload, sk, spec_id=args.spec_id or "")
    print(f"residual review recorded by {args.reviewer} (ledger seq={entry['seq']})")
    return EXIT_OK


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the prompt/constitution eval set; block on regression (3PWR-FR-050)."""
    from .evals import run_evals

    s = _settings(args.root)
    cases = Path(args.cases).resolve() if args.cases else (s.dir / "eval" / "cases.yaml")
    gate = run_evals(s.root, cases)
    human = f"eval: {gate.status.upper()} ({gate.details.get('passed')}/{gate.details.get('cases')} cases)"
    if gate.findings:
        human += "\n  - " + "\n  - ".join(gate.findings)
    _print({"status": gate.status, **gate.details}, args.json, human)
    return EXIT_OK if gate.status == STATUS_PASS else EXIT_FAIL


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="3pwr", description="3Powers judiciary engine.")
    p.add_argument("--version", action="version", version=f"3pwr {__version__}")
    p.add_argument("--root", help="repository root (defaults to discovery from cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        return sp

    kp = common(sub.add_parser("keygen", help="create the independent signer identity"))
    kp.add_argument("--out", help="private key path (default: outside the repo)")
    kp.add_argument("--force", action="store_true")
    kp.set_defaults(func=cmd_keygen)

    ip = common(sub.add_parser("init", help="ensure the .3powers/ layout exists"))
    ip.set_defaults(func=cmd_init)

    gp = sub.add_parser("gate", help="gate engine")
    gsub = gp.add_subparsers(dest="gate_cmd", required=True)
    gr = common(gsub.add_parser("run", help="run the gate suite and emit a verdict"))
    gr.add_argument("--path", help="target project path (default: repo root)")
    gr.add_argument("--tier", default="Standard", help="risk tier (default: Standard)")
    gr.add_argument("--adapter", help="language adapter (default: auto-detect)")
    gr.add_argument("--spec", help="path to the governing spec.md")
    gr.add_argument("--base", help="git ref for diff-coverage base")
    gr.add_argument("--mutation", action="store_true", help="run the mutation gate")
    gr.add_argument("--no-ledger", action="store_true", help="do not append to the ledger")
    gr.set_defaults(func=cmd_gate_run)

    cp = common(sub.add_parser("conformance", help="spec-conformance trace only"))
    cp.add_argument("--spec", help="path to the governing spec.md")
    cp.add_argument("--tests", nargs="*", help="test roots to scan")
    cp.set_defaults(func=cmd_conformance)

    vp = common(sub.add_parser("verify", help="verify the ledger (offline)"))
    vp.set_defaults(func=cmd_verify)

    sp = common(sub.add_parser("signoff", help="record a signed human sign-off"))
    sp.add_argument("--approver", required=True, help="approver identity (a person)")
    sp.add_argument("--stage", default="review")
    sp.add_argument("--note")
    sp.add_argument("--spec-id", dest="spec_id")
    sp.set_defaults(func=cmd_signoff)

    ap = common(sub.add_parser("advance", help="enforce gate+ledger+sign-off before advancing"))
    ap.add_argument("--stage", required=True)
    ap.add_argument("--spec-id", dest="spec_id")
    ap.set_defaults(func=cmd_advance)

    stp = common(sub.add_parser("status", help="per-spec lifecycle stage from the ledger"))
    stp.add_argument("--spec-id", dest="spec_id")
    stp.set_defaults(func=cmd_status)

    rvp = common(sub.add_parser("revert", help="reverse to a prior recorded state (signed)"))
    rvp.add_argument("--to", type=int, required=True, help="ledger seq to revert to")
    rvp.add_argument("--reason")
    rvp.set_defaults(func=cmd_revert)

    abp = common(sub.add_parser("abort", help="record an abort for a spec's run"))
    abp.add_argument("--spec-id", dest="spec_id", required=True)
    abp.add_argument("--reason")
    abp.set_defaults(func=cmd_abort)

    ccp = common(sub.add_parser("coverage-check", help="two-way requirement<->task coverage"))
    ccp.add_argument("--spec", help="path to the governing spec.md")
    ccp.add_argument("--tasks", required=True, help="path to tasks.md")
    ccp.set_defaults(func=cmd_coverage_check)

    scp = common(sub.add_parser("scope-check", help="task req-id + file-scope discipline"))
    scp.add_argument("--tasks", required=True, help="path to tasks.md")
    scp.add_argument("--base", help="git ref for the changed-file base")
    scp.add_argument("--path", help="restrict the changed-file scan to this dir")
    scp.set_defaults(func=cmd_scope_check)

    pvp = common(sub.add_parser("provenance", help="sign build provenance + SBOM for an artifact"))
    pvp.add_argument("--artifact", required=True)
    pvp.add_argument("--path", help="project dir for the SBOM (default: repo root)")
    pvp.add_argument("--spec-id", dest="spec_id")
    pvp.set_defaults(func=cmd_provenance)

    dgp = common(
        sub.add_parser("deploy-gate", help="verify an artifact's provenance; refuse if bad")
    )
    dgp.add_argument("--artifact", required=True)
    dgp.set_defaults(func=cmd_deploy_gate)

    rsp = common(sub.add_parser("residual", help="record a signed residual review"))
    rsp.add_argument("--reviewer", required=True)
    rsp.add_argument("--note")
    rsp.add_argument("--findings", nargs="*")
    rsp.add_argument("--spec-id", dest="spec_id")
    rsp.set_defaults(func=cmd_residual)

    evp = common(sub.add_parser("eval", help="run the prompt/constitution eval set (FR-050)"))
    evp.add_argument("--cases", help="eval cases.yaml (default: .3powers/eval/cases.yaml)")
    evp.set_defaults(func=cmd_eval)

    lp = sub.add_parser("ledger", help="ledger operations")
    lsub = lp.add_subparsers(dest="ledger_cmd", required=True)
    ls = common(lsub.add_parser("show", help="print the ledger"))
    ls.set_defaults(func=cmd_ledger_show)

    rp = common(
        sub.add_parser("roles-check", help="check model-family diversity between two roles")
    )
    rp.add_argument("--role-a", dest="role_a", default="oracle")
    rp.add_argument("--role-b", dest="role_b", default="coder")
    rp.set_defaults(func=cmd_roles_check)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, LookupError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
