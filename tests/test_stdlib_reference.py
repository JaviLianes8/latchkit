"""Ground truth from the Python standard library, run live on every interpreter.

The abort model is ``threading.Barrier.abort()`` (and ``asyncio.Barrier.abort()`` on
3.11+): parked waiters fail, later waiters fail at once. The timeout rules are those of
``threading`` (negative means zero) minus its two sharp edges, which are shown here too.
"""

from __future__ import annotations

import asyncio
import math
import sys
import threading

import pytest
from _kinds import GUARD, KIND_IDS, KINDS, Kind, parked, until

from latchkit import BrokenLatchError, Gate


def _barrier_waiter_outcome(barrier: threading.Barrier, seen: list[str]) -> None:
    try:
        barrier.wait()
        seen.append("returned")
    except threading.BrokenBarrierError:
        seen.append("broken")


def test_barrier_abort_fails_parked_and_later_waiters() -> None:
    barrier = threading.Barrier(2)
    seen: list[str] = []
    thread = threading.Thread(target=_barrier_waiter_outcome, args=(barrier, seen))
    thread.start()
    until(lambda: barrier.n_waiting == 1)
    barrier.abort()
    thread.join(GUARD)
    _barrier_waiter_outcome(barrier, seen)
    assert seen == ["broken", "broken"]
    assert barrier.broken is True


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
def test_latchkit_abort_matches_the_barrier_model(kind: Kind) -> None:
    prim = kind.make()
    seen: list[str] = []

    def waiter() -> None:
        try:
            kind.wait(prim, None)
            seen.append("returned")
        except BrokenLatchError:
            seen.append("broken")

    thread = threading.Thread(target=waiter)
    thread.start()
    until(lambda: parked(prim) == 1)
    prim.abort()
    thread.join(GUARD)
    waiter()
    assert seen == ["broken", "broken"]
    assert prim.is_broken is True


@pytest.mark.skipif(sys.version_info < (3, 11), reason="asyncio.Barrier is new in 3.11")
def test_asyncio_barrier_abort_fails_parked_and_later_waiters() -> None:
    async def main() -> list[str]:
        barrier = asyncio.Barrier(2)  # type: ignore[attr-defined,unused-ignore]
        broken_error = asyncio.BrokenBarrierError  # type: ignore[attr-defined,unused-ignore]
        seen: list[str] = []

        async def waiter() -> None:
            try:
                await barrier.wait()
                seen.append("returned")
            except broken_error:
                seen.append("broken")

        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        await barrier.abort()
        await asyncio.wait_for(task, GUARD)
        await waiter()
        return seen

    assert asyncio.run(main()) == ["broken", "broken"]


def test_negative_timeouts_mean_zero_in_threading_and_in_latchkit() -> None:
    assert threading.Event().wait(-5) is False
    assert threading.Lock().acquire(timeout=-1) is True  # free lock: -1 is "forever" there
    assert Gate().wait(-5) is False
    assert Gate().wait(-1) is False, "latchkit has no -1 sentinel: None means forever"


def test_condition_wait_for_spins_on_nan_and_latchkit_refuses_it() -> None:
    condition = threading.Condition()
    calls = 0

    def predicate() -> bool:
        nonlocal calls
        calls += 1
        return calls >= 2000

    with condition:
        # A NaN deadline never elapses and never sleeps: the predicate is polled in a loop.
        assert condition.wait_for(predicate, math.nan) is True
    assert calls == 2000
    with pytest.raises(ValueError):
        Gate().wait(math.nan)


def test_infinity_is_forever_for_latchkit_whatever_threading_does() -> None:
    gate = Gate()
    results: list[bool] = []
    thread = threading.Thread(target=lambda: results.append(gate.wait(math.inf)))
    thread.start()
    until(lambda: parked(gate) == 1)
    gate.open()
    thread.join(GUARD)
    assert results == [True]
    outcome: list[str] = []

    def stdlib_wait() -> None:
        try:
            threading.Event().wait(math.inf)
            outcome.append("returned")
        except OverflowError:
            outcome.append("OverflowError")

    probe = threading.Thread(target=stdlib_wait, daemon=True)
    probe.start()
    probe.join(GUARD)
    assert outcome == ["OverflowError"], "the standard library refuses an infinite timeout"
