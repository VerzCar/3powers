"""Tests for the advisory per-working-tree run lock (``threepowers.runlock``).

The lock is filesystem-only and defensive: a live same-host holder refuses fast, a stale lock (a
dead pid or an mtime past the TTL) self-heals, separate working trees never contend, and any write/
read failure degrades to a warning instead of wedging the run. It is never a gate/verdict/ledger
fact, so these tests exercise the module directly.
"""

from __future__ import annotations

import json
import os
import socket
import time

import pytest

from threepowers import runlock


def _write_raw(path, *, pid, host, started_at):
    """Write a lock file with an explicit identity, bypassing acquire (test fixture)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"pid": pid, "host": host, "started_at": started_at}), encoding="utf-8"
    )


def test_second_acquire_in_one_tree_refuses_naming_holder(tmp_path):
    """Covers: REQ-D — a second acquire in the SAME working tree (live same-host pid) refuses fast
    with a RunLockHeld naming the other run's pid, host, and start time."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    first = runlock.acquire(lock_path)
    assert first.acquired
    assert first.warning is None

    with pytest.raises(runlock.RunLockHeld) as excinfo:
        runlock.acquire(lock_path)

    held = excinfo.value
    assert held.info.pid == os.getpid()
    assert held.info.host == socket.gethostname()
    message = str(held)
    assert str(os.getpid()) in message
    assert socket.gethostname() in message
    assert held.info.started_at in message

    runlock.release(first)


def test_stale_dead_pid_is_reclaimed(tmp_path, monkeypatch):
    """Covers: REQ-D — a same-host lock whose recorded pid is dead is stale: it is reclaimed and the
    run proceeds (the fast self-heal), no exception, no warning."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    _write_raw(lock_path, pid=4242, host=socket.gethostname(), started_at="2020-01-01T00:00:00Z")
    monkeypatch.setattr(runlock, "_pid_alive", lambda pid: False)

    handle = runlock.acquire(lock_path)

    assert handle.acquired
    assert handle.warning is None
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    runlock.release(handle)


def test_stale_mtime_past_ttl_is_reclaimed(tmp_path):
    """Covers: REQ-D — a lock (even from another host, whose pid cannot be verified) whose mtime is
    older than the TTL is stale: it self-heals via the TTL and the run proceeds."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    _write_raw(lock_path, pid=1, host="some-other-host", started_at="2020-01-01T00:00:00Z")
    old = time.time() - 10_000
    os.utime(lock_path, (old, old))

    handle = runlock.acquire(lock_path, ttl_seconds=1.0)

    assert handle.acquired
    assert handle.warning is None
    assert json.loads(lock_path.read_text())["host"] == socket.gethostname()
    runlock.release(handle)


def test_other_host_within_ttl_is_held(tmp_path):
    """Covers: REQ-D — a lock from another host, within the TTL, cannot have its pid checked and so
    is treated as held (it self-heals via the TTL only), refusing the run."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    _write_raw(lock_path, pid=1, host="some-other-host", started_at="2020-01-01T00:00:00Z")

    with pytest.raises(runlock.RunLockHeld):
        runlock.acquire(lock_path, ttl_seconds=10_000)


def test_two_separate_trees_both_acquire(tmp_path):
    """Covers: REQ-D — two separate working trees (clones / git worktrees) each carry their own
    ``.3powers/run.lock`` and both acquire cleanly, never contending."""
    lock_a = tmp_path / "clone-a" / ".3powers" / "run.lock"
    lock_b = tmp_path / "clone-b" / ".3powers" / "run.lock"

    handle_a = runlock.acquire(lock_a)
    handle_b = runlock.acquire(lock_b)

    assert handle_a.acquired and handle_b.acquired
    assert handle_a.warning is None and handle_b.warning is None
    runlock.release(handle_a)
    runlock.release(handle_b)


def test_write_failure_degrades_to_warning(tmp_path, monkeypatch):
    """Covers: REQ-D — a lock-write failure (a read-only filesystem, say) never raises and never
    blocks: it degrades to a warning, the guard is off for the run, and release is a safe no-op."""
    lock_path = tmp_path / ".3powers" / "run.lock"

    def boom(self, *args, **kwargs):
        raise OSError("read-only file system")

    monkeypatch.setattr(runlock.Path, "write_text", boom)

    handle = runlock.acquire(lock_path)  # must not raise

    assert handle.acquired is False
    assert handle.warning is not None
    runlock.release(handle)  # no-op, must not raise


def test_malformed_lock_degrades_and_reclaims(tmp_path):
    """Covers: REQ-D — an unparseable lock file degrades to a warning and is reclaimed rather than
    wedging the run."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("not json {{{", encoding="utf-8")

    handle = runlock.acquire(lock_path)

    assert handle.acquired
    assert handle.warning is not None
    assert json.loads(lock_path.read_text())["pid"] == os.getpid()
    runlock.release(handle)


def test_release_removes_our_own_lock(tmp_path):
    """Covers: REQ-D — releasing a lock this process took removes the lock file."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    handle = runlock.acquire(lock_path)
    assert lock_path.exists()

    runlock.release(handle)

    assert not lock_path.exists()


def test_release_leaves_a_reclaimed_lock_intact(tmp_path):
    """Covers: REQ-D — release never deletes a lock another run legitimately reclaimed: a lock no
    longer recording this process is left untouched."""
    lock_path = tmp_path / ".3powers" / "run.lock"
    handle = runlock.acquire(lock_path)
    # Simulate another run judging us stale and reclaiming the lock with its own identity.
    _write_raw(
        lock_path,
        pid=os.getpid() + 1,
        host=socket.gethostname(),
        started_at="2020-01-01T00:00:00Z",
    )

    runlock.release(handle)

    assert lock_path.exists()
    assert json.loads(lock_path.read_text())["pid"] == os.getpid() + 1


def test_release_is_noop_for_none():
    """Covers: REQ-D — releasing ``None`` (no lock was taken) is a safe no-op."""
    runlock.release(None)
