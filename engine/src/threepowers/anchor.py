"""Opt-in external anchoring of the ledger head.

Anchoring bounds the one attack tamper-evidence cannot see: a holder of the signing key
regenerating or truncating the ledger wholesale and re-signing it. ``3pwr anchor`` records
the current head — sequence number + entry hash — with an external witness (the reference
witness is a git tag ``3powers/anchor/<seq>``, pushed to a remote the key holder does not
control unilaterally) and appends a local ``anchor`` receipt. ``3pwr verify --anchored``
cross-checks the local chain against the latest anchor and fails on divergence.

Strictly opt-in: plain ``verify`` and ``gate run`` never read or write an anchor and make
no network call. Pushing the tag is the only network-capable operation, and only under the
explicit ``--push`` flag.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

TAG_PREFIX = "3powers/anchor/"


def _git(root: Path, args: list[str]) -> tuple[int, str, str]:
    """Run git; (returncode, stdout, stderr). Never raises on a missing binary."""
    try:
        res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
        return res.returncode, res.stdout, res.stderr
    except OSError as exc:
        return 127, "", str(exc)


def head_of(entries: list[dict[str, Any]]) -> Optional[tuple[int, str]]:
    """The current ledger head: (seq, entry_hash) of the last entry; None when empty."""
    if not entries:
        return None
    last = entries[-1]
    return int(last.get("seq", -1)), str(last.get("entry_hash", ""))


def anchor_message(seq: int, entry_hash: str) -> str:
    """The deterministic witness payload recorded in the tag."""
    return json.dumps({"seq": seq, "entry_hash": entry_hash}, sort_keys=True)


def tag_name(seq: int) -> str:
    return f"{TAG_PREFIX}{seq}"


def create_anchor(
    repo_root: Path, seq: int, entry_hash: str, *, push: bool = False, remote: str = "origin"
) -> tuple[bool, str]:
    """Create the witness tag for the head (and optionally push it). (ok, message)."""
    name = tag_name(seq)
    rc, _out, err = _git(repo_root, ["tag", "-a", name, "-m", anchor_message(seq, entry_hash)])
    if rc != 0:
        return False, f"could not create anchor tag {name}: {err.strip() or 'git failed'}"
    if push:
        rc, _out, err = _git(repo_root, ["push", remote, name])
        if rc != 0:
            return False, (
                f"anchor tag {name} created locally but NOT pushed to '{remote}': "
                f"{err.strip() or 'git push failed'} — push it to complete the witness"
            )
    return True, name


def latest_anchor(repo_root: Path) -> Optional[tuple[int, str]]:
    """The highest-sequence local anchor: (seq, entry_hash); None when no anchor tag exists.

    Reads local tags only — fetching a remote's tags is the operator's explicit act, so this
    stays offline.
    """
    rc, out, _err = _git(repo_root, ["tag", "-l", f"{TAG_PREFIX}*"])
    if rc != 0:
        return None
    best: Optional[int] = None
    for line in out.splitlines():
        tail = line.strip()[len(TAG_PREFIX) :]
        if tail.isdigit():
            best = max(best, int(tail)) if best is not None else int(tail)
    if best is None:
        return None
    rc, msg, _err = _git(repo_root, ["tag", "-l", "--format=%(contents:subject)", tag_name(best)])
    if rc != 0:
        return None
    try:
        data = json.loads(msg.strip() or "{}")
        seq, entry_hash = int(data["seq"]), str(data["entry_hash"])
    except (ValueError, KeyError, TypeError):
        return None
    if seq != best:
        return None  # a tag whose message contradicts its name is no witness
    return seq, entry_hash


@dataclass
class AnchorCheck:
    ok: bool
    problems: list[str]
    anchor_seq: Optional[int] = None


def check_anchored(entries: list[dict[str, Any]], anchor: Optional[tuple[int, str]]) -> AnchorCheck:
    """Cross-check the local chain against the latest anchor.

    Fails when the ledger was truncated behind the anchor or rewritten at the anchored
    sequence — even by an adversary holding the current signing key. A chain that *extends*
    the anchored head passes. Pure and deterministic.
    """
    if anchor is None:
        return AnchorCheck(
            ok=False,
            problems=[
                "no anchor found — run `3pwr anchor` first (and `git fetch --tags` to see a "
                "remote witness)"
            ],
        )
    seq, expected_hash = anchor
    by_seq = {e.get("seq"): e for e in entries}
    at = by_seq.get(seq)
    if at is None:
        return AnchorCheck(
            ok=False,
            problems=[
                f"ledger truncated behind the anchor — anchored seq={seq} is not in the ledger"
            ],
            anchor_seq=seq,
        )
    if at.get("entry_hash") != expected_hash:
        return AnchorCheck(
            ok=False,
            problems=[
                f"ledger diverges from the anchor at seq={seq} — entry_hash does not match "
                "the witnessed head (rewritten history)"
            ],
            anchor_seq=seq,
        )
    return AnchorCheck(ok=True, problems=[], anchor_seq=seq)
