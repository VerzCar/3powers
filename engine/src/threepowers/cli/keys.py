"""Signer-identity commands: ``keygen`` and ``rotate-key``."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING


from .. import (
    keys,
)
from ..ledger import Ledger, rotation_payload
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


def cmd_keygen(args: argparse.Namespace) -> int:
    s = _settings(args.root)
    role = getattr(args, "role", "ledger")
    if args.out:
        out = Path(args.out).resolve()
    elif role == "oracle":
        out = keys.default_oracle_private_path(s.root)
    else:
        out = keys.default_private_path(s.root)
    pub = s.oracle_pubkey_path if role == "oracle" else s.pubkey_path
    env_var = (
        "THREEPOWERS_ORACLE_SIGNING_KEY_FILE"
        if role == "oracle"
        else "THREEPOWERS_SIGNING_KEY_FILE"
    )
    if keys.inside_working_tree(s.root, out):
        print(
            f"refusing to create a private key INSIDE the repository working tree: {out}\n"
            "  an executive agent with repo access could read it.\n"
            f"  pass --out with a path outside the repo, e.g. {keys.default_private_path(s.root)}",
            file=sys.stderr,
        )
        return EXIT_USAGE
    if out.exists() and not args.force:
        print(f"refusing to overwrite existing key at {out} (use --force)", file=sys.stderr)
        return EXIT_USAGE
    sk = keys.generate()
    keys.write_private(out, sk)
    keys.write_public(pub, sk.verify_key)
    label = "judiciary (oracle) signer" if role == "oracle" else "signer"
    kst = _styler(args)
    print(kst.status_row("pass", f"{label} identity created", sk.key_id))
    print(
        kst.kv(
            [
                ("private key (keep OUTSIDE the repo)", str(out)),
                ("public key  (committed)", str(pub)),
            ]
        )
    )
    print()
    print("  " + kst.dim("Point the engine at the private key with:"))
    print(f'  export {env_var}="{out}"')
    return EXIT_OK


def cmd_rotate_key(args: argparse.Namespace) -> int:
    """Rotate the ledger signer: the OUTGOING key signs its successor.

    Appends a ``key_rotation`` entry authored by the current key and carrying the new public
    key, then installs the successor (private key outside the repo, public key committed).
    ``verify`` thereafter requires the committed key to descend from the genesis key through
    exactly these recorded rotations — a bare pubkey swap becomes a named finding (SC-001).
    """
    s = _settings(args.root)
    try:
        old_sk = keys.resolve_signing_key(s.root)  # rotation needs the software key material
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_USAGE
    if s.pubkey_path.exists():
        committed = keys.load_public(s.pubkey_path)
        if committed.key_id != old_sk.key_id:
            print(
                f"error: the resolved signing key ({old_sk.key_id}) is not the committed "
                f"public key ({committed.key_id}) — a rotation must be authored by the "
                "current key, or verify would report a broken succession",
                file=sys.stderr,
            )
            return EXIT_USAGE
    out = Path(args.out).resolve() if args.out else keys.default_private_path(s.root)
    if keys.inside_working_tree(s.root, out):
        print(
            f"refusing to create a private key INSIDE the repository working tree: {out}\n"
            "  pass --out with a path outside the repo",
            file=sys.stderr,
        )
        return EXIT_USAGE
    new_sk = keys.generate()
    payload = rotation_payload(old_sk.verify_key, new_sk.verify_key, args.reason or "")
    entry = Ledger(s.ledger_path).append("key_rotation", payload, old_sk)
    keys.write_private(out, new_sk)
    keys.write_public(s.pubkey_path, new_sk.verify_key)
    hint = ""
    env_file = os.environ.get("THREEPOWERS_SIGNING_KEY_FILE")
    if env_file and Path(env_file).resolve() != out:
        hint = f'\n  update the pointer:  export THREEPOWERS_SIGNING_KEY_FILE="{out}"'
    rkt = _styler(args)
    rows = [
        rkt.status_row(
            "pass",
            f"key rotated: {old_sk.key_id} → {new_sk.key_id}",
            f"ledger seq={entry['seq']}",
        ),
        rkt.kv(
            [
                ("new private key (OUTSIDE the repo)", str(out)),
                ("committed public key updated", str(s.pubkey_path)),
            ]
        ),
    ]
    if hint:
        rows.append(
            rkt.status_row(
                "warn", f'update the pointer: export THREEPOWERS_SIGNING_KEY_FILE="{out}"'
            )
        )
    _print(
        {
            "rotated": True,
            "previous_key_id": old_sk.key_id,
            "new_key_id": new_sk.key_id,
            "ledger_seq": entry["seq"],
            "private_key": str(out),
        },
        args.json,
        _compose(
            args, rkt, title="rotate-key", subject=f"{old_sk.key_id} → {new_sk.key_id}", rows=rows
        ),
    )
    return EXIT_OK


def _register_keygen(sub: SubParsers, common: AddCommon) -> None:
    kp = common(sub.add_parser("keygen", help="create the independent signer identity"))
    kp.add_argument("--out", help="private key path (default: outside the repo)")
    kp.add_argument("--force", action="store_true")
    kp.add_argument(
        "--role",
        choices=["ledger", "oracle"],
        default="ledger",
        help="which signer to mint: the primary ledger key or a distinct judiciary oracle key",
    )
    kp.set_defaults(func=cmd_keygen)


def _register_rotate_key(sub: SubParsers, common: AddCommon) -> None:
    rk = common(
        sub.add_parser("rotate-key", help="rotate the signer: the outgoing key signs its successor")
    )
    rk.add_argument("--out", help="new private key path (default: outside the repo)")
    rk.add_argument("--reason", help="why the key is being rotated (recorded in the ledger)")
    rk.set_defaults(func=cmd_rotate_key)
