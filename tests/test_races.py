"""Races the locks exist for, forced deterministically or made overwhelmingly likely.

On correct code each test passes whatever the interleaving; without the lock it
guards, each loses a signal or a wake-up.
"""

from __future__ import annotations

import asyncio
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from _kinds import GUARD

from latchkit import AsyncCountDownLatch, AsyncGate, CountDownLatch


@contextmanager
def tiny_switch_interval() -> Iterator[None]:
    """Make the interpreter switch threads as often as it can (no effect when free-threaded)."""
    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(previous)


@pytest.mark.parametrize("cls", [CountDownLatch, AsyncCountDownLatch])
def test_concurrent_count_downs_are_never_lost(cls: Any) -> None:
    threads, per_thread = 8, 5000
    for _ in range(3):
        latch = cls(threads * per_thread)
        start = threading.Barrier(threads)

        def worker(latch: Any = latch, start: threading.Barrier = start) -> None:
            start.wait(GUARD)
            for _ in range(per_thread):
                latch.count_down()

        with tiny_switch_interval():
            pool = [threading.Thread(target=worker, daemon=True) for _ in range(threads)]
            for thread in pool:
                thread.start()
            for thread in pool:
                thread.join(GUARD)
        assert latch.remaining == 0
        assert latch.is_open is True


def test_a_settle_while_a_waiter_registers_is_not_lost() -> None:
    async def main() -> bool:
        gate = AsyncGate()
        loop = asyncio.get_running_loop()
        real_create_future: Callable[[], asyncio.Future[Any]] = loop.create_future
        opened: list[bool] = []  # one-shot; the gate's own lock is held here, so no reads

        def create_future_while_opening() -> asyncio.Future[Any]:
            # Another thread opens the gate in the middle of the waiter's registration;
            # the gate's lock makes it wait until the waiter is fully registered.
            if sys._getframe(1).f_code.co_name == "_wait" and not opened:
                opened.append(True)
                opener = threading.Thread(target=gate.open, daemon=True)
                opener.start()
                opener.join(0.5)  # bounded: the opener is expected to be blocked here
            return real_create_future()

        loop.create_future = create_future_while_opening  # type: ignore[method-assign]
        try:
            waiting = gate.wait()
            result = await asyncio.wait_for(waiting, GUARD)
        finally:
            del loop.create_future
        return result

    assert asyncio.run(main()) is True
