"""Behaviour of CountDownLatch with real threads."""

from __future__ import annotations

import threading
import time

import pytest
from _kinds import GUARD, parked, until

from latchkit import CountDownLatch


def test_waiters_release_only_after_the_last_count_down() -> None:
    latch = CountDownLatch(3)
    released = threading.Event()

    def waiter() -> None:
        latch.wait()
        released.set()

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    until(lambda: parked(latch) == 1)
    latch.count_down()
    latch.count_down()
    assert parked(latch) == 1  # still parked: one signal short, nobody was woken
    assert not released.is_set()
    latch.count_down()
    t.join(GUARD)
    assert released.is_set()


def test_wait_returns_false_on_timeout() -> None:
    latch = CountDownLatch(1)
    start = time.monotonic()
    assert latch.wait(timeout=0.05) is False
    assert time.monotonic() - start >= 0.05


def test_wait_returns_true_once_open() -> None:
    latch = CountDownLatch(1)
    latch.count_down()
    assert latch.wait(timeout=0.0) is True


def test_remaining_tracks_the_count() -> None:
    latch = CountDownLatch(2)
    assert latch.remaining == 2
    assert latch.count_down() == 1
    assert latch.remaining == 1


def test_count_down_past_zero_is_clamped_and_opens() -> None:
    latch = CountDownLatch(2)
    assert latch.count_down(5) == 0
    assert latch.remaining == 0
    assert latch.wait(timeout=0.0) is True


def test_count_down_on_an_open_latch_is_a_noop() -> None:
    latch = CountDownLatch(1)
    latch.count_down()
    assert latch.count_down() == 0
    assert latch.remaining == 0


def test_zero_count_latch_starts_open() -> None:
    latch = CountDownLatch(0)
    assert latch.remaining == 0
    assert latch.wait(timeout=0.0) is True


def test_negative_count_is_rejected() -> None:
    with pytest.raises(ValueError):
        CountDownLatch(-1)


def test_count_down_below_one_is_rejected() -> None:
    latch = CountDownLatch(3)
    with pytest.raises(ValueError):
        latch.count_down(0)


def test_many_waiters_all_release() -> None:
    latch = CountDownLatch(1)
    done = []
    lock = threading.Lock()

    def waiter() -> None:
        assert latch.wait(timeout=GUARD) is True
        with lock:
            done.append(True)

    threads = [threading.Thread(target=waiter, daemon=True) for _ in range(5)]
    for t in threads:
        t.start()
    latch.count_down()
    for t in threads:
        t.join(GUARD)
    assert len(done) == 5
