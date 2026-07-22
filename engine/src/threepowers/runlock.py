"""An advisory, per-working-tree run lock — the concurrent-run guard for ``3pwr run``.

A shared working tree and its single git index make two concurrent ``3pwr run`` invocations in the
**same checkout** unsafe (they would race on the branch, the index, and the run's feature folder).
This module takes a small advisory lock under the working tree's own engine state
(``.3powers/run.lock``, alongside ``gitflow.ENGINE_STATE_PREFIX``) recording ``{pid, host,
started_at}``. The lock scope is the working tree, never the repository or the remote: two clones or
two ``git worktree`` checkouts each carry their own ``.3powers/run.lock`` and never contend.

Contention is resolved conservatively and self-heals:

* the recorded pid is **alive on this host** → the run is refused fast with an actionable message
  naming the other run (:class:`RunLockHeld`);
* the recorded pid is **dead** on this host, or the lock's mtime is older than a generous TTL → the
  lock is treated as stale, reclaimed, and the run proceeds (a crashed run never wedges the next);
* a lock recorded on a **different host** cannot have its pid checked, so it self-heals via the TTL
  only — held within the TTL, reclaimable past it.

The guard is **advisory and defensive** (never load-bearing for correctness): a lock-write failure
(a read-only filesystem, say), an unreadable lock, or a malformed lock file degrades to a warning
and lets the run proceed. It is filesystem-only — never a gate, a verdict, or a ledger entry.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "LOCK_FILENAME",
    "LockHandle",
    "LockInfo",
    "RunLockHeld",
    "acquire",
    "release",
]

# The lock file's name inside the working tree's engine state directory (`.3powers/`). The caller
# owns the directory (via `gitflow.ENGINE_STATE_PREFIX`) and joins this name onto it, so this module
# stays a pure advisory-lock utility with no knowledge of the engine's state layout.
LOCK_FILENAME = "run.lock"

# A generous staleness window: a lock whose mtime is older than this is reclaimed even when its
# recorded host/pid cannot be verified. Long enough that a legitimately slow run is never mistaken
# for stale; short enough that a crash on another host eventually self-heals. The primary, faster
# self-heal is same-host pid-liveness — the TTL is the backstop, not the first line.
DEFAULT_TTL_SECONDS: float = 24 * 60 * 60  # 24 hours


@dataclass(frozen=True)
class LockInfo:
    """The identity a run records in its lock file: which process, on which host, since when.

    Attributes:
        pid: The recording process's id (as seen on ``host``).
        host: The recording host's name (``socket.gethostname()``); a pid is only meaningful on it.
        started_at: An ISO-8601 UTC timestamp of when the lock was taken.
    """

    pid: int
    host: str
    started_at: str


@dataclass
class LockHandle:
    """The result of :func:`acquire`, passed to :func:`release`.

    Attributes:
        path: The lock file's path.
        acquired: ``True`` when this process actually wrote the lock (and so owns removing it);
            ``False`` when the write degraded to a warning and the guard is off for this run.
        warning: A non-fatal degradation message for the caller to surface (an unreadable/malformed
            reclaimed lock, or a failed write), or ``None`` when the lock was taken cleanly.
    """

    path: Path
    acquired: bool
    warning: Optional[str] = None


class RunLockHeld(Exception):
    """Raised by :func:`acquire` when the lock is held by another *live* run in this working tree.

    Carries the holder's :class:`LockInfo` and the lock path so the caller can refuse on the setup
    path with a message naming the other run.
    """

    def __init__(self, info: LockInfo, path: Path) -> None:
        self.info = info
        self.path = path
        super().__init__(
            "another `3pwr run` is already active in this working tree "
            f"(pid {info.pid} on {info.host}, started {info.started_at}); "
            "wait for it to finish. If you are certain it has stopped, "
            f"remove {path} and retry."
        )


def acquire(lock_path: Path, *, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> LockHandle:
    """Take the advisory run lock at ``lock_path``, self-healing a stale one.

    Args:
        lock_path: The lock file to take (typically ``<tree>/.3powers/run.lock``).
        ttl_seconds: The staleness window; a lock whose mtime is older is reclaimed. Defaults to
            :data:`DEFAULT_TTL_SECONDS`.

    Returns:
        A :class:`LockHandle` to pass to :func:`release`. Its ``warning`` is set (and ``acquired``
        may be ``False``) when the guard degraded but the run may still proceed.

    Raises:
        RunLockHeld: When the lock is held by another live run in the same working tree — the caller
            refuses on the setup path.
    """
    warnings: list[str] = []
    info, read_warning = _read_lock(lock_path)
    if read_warning is not None:
        warnings.append(read_warning)
    if info is not None and _is_held(info, lock_path, ttl_seconds):
        raise RunLockHeld(info, lock_path)
    write_warning = _write_lock(lock_path)
    if write_warning is not None:
        warnings.append(write_warning)
    return LockHandle(
        path=lock_path,
        acquired=write_warning is None,
        warning="; ".join(warnings) if warnings else None,
    )


def release(handle: Optional[LockHandle]) -> None:
    """Release a lock taken by :func:`acquire`, best-effort and idempotent.

    Only a lock this process actually wrote is removed, and only when it still records this process
    — so a lock another run legitimately reclaimed (having judged us stale) is never deleted out
    from under it. A failure to remove is swallowed: a leftover lock self-heals on the next run.

    Args:
        handle: The handle from :func:`acquire`, or ``None`` (a no-op).
    """
    if handle is None or not handle.acquired:
        return
    info, _ = _read_lock(handle.path)
    if info is not None and info.pid == os.getpid() and info.host == _this_host():
        try:
            handle.path.unlink(missing_ok=True)
        except OSError:
            pass


def _this_host() -> str:
    """This host's name — the scope on which a recorded pid is meaningful."""
    return socket.gethostname()


def _now_iso() -> str:
    """An ISO-8601 UTC timestamp in the engine's canonical second-precision form."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_lock(path: Path) -> tuple[Optional[LockInfo], Optional[str]]:
    """Read the lock at ``path``.

    Returns:
        ``(info, warning)``. ``info`` is the parsed :class:`LockInfo`, or ``None`` when the lock is
        absent, unreadable, or malformed. ``warning`` is ``None`` for a clean read or a plain
        absence, and a degradation message when the lock existed but could not be read/parsed (the
        caller surfaces it and proceeds to reclaim).
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, None
    except OSError:
        return None, f"warning: could not read the run lock at {path}; proceeding without it"
    try:
        data = json.loads(raw)
        info = LockInfo(
            pid=int(data["pid"]),
            host=str(data["host"]),
            started_at=str(data["started_at"]),
        )
    except (ValueError, TypeError, KeyError):
        return None, f"warning: the run lock at {path} is malformed; reclaiming it"
    return info, None


def _write_lock(path: Path) -> Optional[str]:
    """Write this process's identity to the lock at ``path``.

    Returns:
        ``None`` on success, or a degradation message when the write fails (a read-only filesystem,
        say) — the guard is then off for this run, which proceeds regardless.
    """
    info = LockInfo(pid=os.getpid(), host=_this_host(), started_at=_now_iso())
    payload = json.dumps({"pid": info.pid, "host": info.host, "started_at": info.started_at})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    except OSError:
        return (
            f"warning: could not write the run lock at {path}; "
            "the concurrent-run guard is off for this run"
        )
    return None


def _is_held(info: LockInfo, path: Path, ttl_seconds: float) -> bool:
    """Decide whether an existing lock still holds, or has gone stale and may be reclaimed.

    Held (return ``True``) only for a same-host, still-alive pid within the TTL, or a different-host
    lock within the TTL (whose pid cannot be verified). Stale (return ``False``) once the TTL
    lapses, or immediately for a same-host dead pid — the fast self-heal.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False  # cannot stat the lock we just read → treat it as free
    if _age_seconds(mtime) > ttl_seconds:
        return False  # stale by TTL, regardless of host
    if info.host == _this_host():
        return _pid_alive(info.pid)  # same host: a live pid holds, a dead one is reclaimable now
    return True  # different host, within TTL: cannot check the pid, so it self-heals via TTL only


def _age_seconds(mtime: float) -> float:
    """Seconds elapsed since ``mtime`` (a POSIX timestamp), floored at zero for clock skew."""
    return max(0.0, datetime.now(timezone.utc).timestamp() - mtime)


def _pid_alive(pid: int) -> bool:
    """Whether ``pid`` is a live process on this host, via ``os.kill(pid, 0)``.

    A non-positive pid is never alive. ``PermissionError`` means the process exists but is owned by
    another user (alive); ``ProcessLookupError`` and any other ``OSError`` mean it is gone.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True
