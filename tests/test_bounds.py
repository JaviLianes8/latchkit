"""How long waits really wait, and what they leave behind, observed without sleeping.

A wait without a timeout must never pass a finite timeout to its condition; a timed
wait must not return early; a released asyncio waiter must not leave a live timer on
its loop; and racing wake-ups must never raise inside the loop.
"""

from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

import pytest
from _kinds import GUARD, parked, until

from latchkit import (
    AsyncGate,
    AsyncOneShotEvent,
    BrokenLatchError,
    CountDownLatch,
    Gate,
    OneShotEvent,
)


class RecordingCondition(threading.Condition):
    """A real condition that remembers every timeout it was asked to wait for."""

    def __init__(self) -> None:
        super().__init__()
        self.timeouts: list[float | None] = []

    def wait(self, timeout: float | None = None) -> bool:
        self.timeouts.append(timeout)
        return super().wait(timeout)


@pytest.mark.parametrize("make", [lambda: CountDownLatch(1), Gate, OneShotEvent])
@pytest.mark.parametrize("timeout", [None, float("inf"), 10**400])
def test_waiting_forever_never_hands_the_condition_a_deadline(make: Any, timeout: Any) -> None:
    prim = make()
    prim._cond = RecordingCondition()
    results: list[bool] = []
    thread = threading.Thread(target=lambda: results.append(prim.wait(timeout)), daemon=True)
    thread.start()
    until(lambda: parked(prim) == 1)
    with prim._cond:
        prim._settle_locked(1)  # OPEN, through the same path open/set/count_down use
    thread.join(GUARD)
    assert results == [True]
    assert prim._cond.timeouts and set(prim._cond.timeouts) == {None}


def test_a_threaded_timed_wait_never_returns_early() -> None:
    clock = time.get_clock_info("monotonic").resolution
    for timeout in (0.02, 0.05):
        start = time.monotonic()
        assert Gate().wait(timeout) is False
        assert time.monotonic() - start >= timeout - clock


def test_an_asyncio_timed_wait_never_returns_early() -> None:
    async def main() -> None:
        loop = asyncio.get_running_loop()
        resolution = time.get_clock_info("monotonic").resolution
        for timeout in (0.05, 0.2):
            start = loop.time()
            assert await AsyncGate().wait(timeout) is False
            assert loop.time() - start >= timeout - resolution - 1e-3

    asyncio.run(main())


def test_a_released_waiter_leaves_no_live_timer_on_its_loop() -> None:
    async def main() -> None:
        loop = asyncio.get_running_loop()
        gate = AsyncGate()
        task = asyncio.create_task(gate.wait(timeout=10_000))
        await asyncio.sleep(0)
        live = [h for h in loop._scheduled if not h.cancelled()]  # type: ignore[attr-defined]
        assert len(live) == 1, "the waiter armed its timeout"
        gate.open()
        assert await asyncio.wait_for(task, GUARD) is True
        live = [h for h in loop._scheduled if not h.cancelled()]  # type: ignore[attr-defined]
        assert live == [], "the timeout of a released waiter is cancelled"

    asyncio.run(main())


def test_racing_wakeups_never_raise_inside_the_loop() -> None:
    async def main() -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        errors: list[dict[str, Any]] = []
        loop.set_exception_handler(lambda _loop, context: errors.append(context))
        event = AsyncOneShotEvent()
        doomed = asyncio.create_task(event.wait(timeout=10_000))
        await asyncio.sleep(0)
        event.set()  # schedules the wake-up of the parked future
        doomed.cancel()  # cancels that same future before the wake-up runs
        await asyncio.gather(doomed, return_exceptions=True)
        for _ in range(3):
            await asyncio.sleep(0)  # let the scheduled wake-up run on the cancelled future
        return errors

    assert asyncio.run(main()) == []


def test_an_abort_right_after_opening_reaches_no_waiter() -> None:
    async def main() -> list[bool]:
        gate = AsyncGate()
        tasks = [asyncio.create_task(gate.wait()) for _ in range(5)]
        await asyncio.sleep(0)
        assert gate.open() is True
        assert gate.abort("too late") is False  # before any waiter has resumed
        return list(await asyncio.wait_for(asyncio.gather(*tasks), GUARD))

    assert asyncio.run(main()) == [True] * 5
    gate = Gate()
    results: list[bool] = []
    threads = [
        threading.Thread(target=lambda: results.append(gate.wait()), daemon=True) for _ in range(5)
    ]
    for thread in threads:
        thread.start()
    until(lambda: parked(gate) == 5)
    with gate._cond:  # open and abort while every waiter is still parked
        gate._settle_locked(1)
        assert gate._settle_locked(2, "too late") is False
    for thread in threads:
        thread.join(GUARD)
    assert results == [True] * 5


def test_an_asyncio_timed_wait_arms_its_timer_for_exactly_the_timeout() -> None:
    async def main() -> None:
        loop = asyncio.get_running_loop()
        for timeout in (0.5, 30.0, 1e6):
            gate = AsyncGate()
            before = loop.time()
            task = asyncio.create_task(gate.wait(timeout))
            await asyncio.sleep(0)
            after = loop.time()
            timers = [h for h in loop._scheduled if not h.cancelled()]  # type: ignore[attr-defined]
            assert len(timers) == 1
            assert before + timeout <= timers[0].when() <= after + timeout
            gate.open()
            assert await task is True

    asyncio.run(main())


def test_a_base_exception_reason_is_chained_too() -> None:
    gate = Gate()
    reason = asyncio.CancelledError("stop")
    gate.abort(reason)
    with pytest.raises(BrokenLatchError) as info:
        gate.wait(0)
    assert info.value.__cause__ is reason
