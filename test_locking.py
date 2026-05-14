import os
import time
import multiprocessing as mp
from pathlib import Path

from conductor import inbox_lock, proposals_lock, supermutation


def _hold_inbox_lock(lockdir: str, seconds: float, started_evt):
    """Worker: acquire inbox lock, signal start, sleep, release."""
    os.environ["CONDUCTOR_DIR"] = lockdir
    with inbox_lock():
        started_evt.set()
        time.sleep(seconds)


def test_inbox_lock_serializes_writers(tmp_path: Path, monkeypatch):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))

    started = mp.Event()
    proc = mp.Process(target=_hold_inbox_lock, args=(str(tmp_path), 0.3, started))
    proc.start()
    started.wait(timeout=2)

    t0 = time.monotonic()
    with inbox_lock():
        elapsed = time.monotonic() - t0
    proc.join()

    assert elapsed >= 0.2, f"inbox lock did not block (elapsed={elapsed:.3f}s)"


def test_proposals_lock_independent_of_inbox(tmp_path: Path, monkeypatch):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))

    started = mp.Event()
    proc = mp.Process(target=_hold_inbox_lock, args=(str(tmp_path), 0.3, started))
    proc.start()
    started.wait(timeout=2)

    # proposals_lock should NOT block on inbox_lock
    t0 = time.monotonic()
    with proposals_lock():
        elapsed = time.monotonic() - t0
    proc.join()
    assert elapsed < 0.1, f"proposals_lock blocked on inbox_lock (elapsed={elapsed:.3f}s)"


def test_supermutation_acquires_both(tmp_path: Path, monkeypatch):
    (tmp_path / ".conductor").mkdir()
    (tmp_path / ".conductor" / "inbox.lock").touch()
    (tmp_path / ".conductor" / "proposals.lock").touch()
    monkeypatch.setenv("CONDUCTOR_DIR", str(tmp_path))

    with supermutation():
        # both locks should be held; this is a smoke test
        pass
