"""Many-coroutine stress, in one loop and bridged from worker threads.

Assertions are about ordering and outcomes, never about elapsed time. Timeouts
appear only as deadlock guards, generous enough that load cannot trip them.
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from latchkit import AsyncCountDownLatch, AsyncGate, AsyncOneShotEvent, BrokenLatchError

GUARD = 60.0
ROUNDS = 25
SIGNALERS = 64
WAITERS = 256


def test_coroutines_release_only_after_every_signal() -> None:
    async def one_round() -> None:
        latch = AsyncCountDownLatch(SIGNALERS)
        signals: list[int] = []

        async def signal() -> None:
            await asyncio.sleep(0)
            signals.append(1)
            latch.count_down()

        async def wait() -> int:
            assert await latch.wait() is True
            return len(signals)

        waiters = [asyncio.create_task(wait()) for _ in range(WAITERS)]
        await asyncio.gather(*(signal() for _ in range(SIGNALERS)))
        seen = await asyncio.wait_for(asyncio.gather(*waiters), GUARD)
        assert seen == [SIGNALERS] * WAITERS
        assert latch._waiters == {}

    async def main() -> None:
        for _ in range(ROUNDS):
            await one_round()

    asyncio.run(main())


def test_worker_threads_signalling_coroutines_lose_no_wakeup() -> None:
    async def one_round(loop: asyncio.AbstractEventLoop) -> None:
        latch = AsyncCountDownLatch(SIGNALERS)
        signals: list[int] = []

        def signal() -> None:
            signals.append(1)
            latch.count_down()

        async def wait() -> int:
            assert await latch.wait() is True
            return len(signals)

        waiters = [asyncio.create_task(wait()) for _ in range(WAITERS)]
        workers = [loop.run_in_executor(None, signal) for _ in range(SIGNALERS)]
        seen = await asyncio.wait_for(asyncio.gather(*waiters, *workers), GUARD)
        assert seen[:WAITERS] == [SIGNALERS] * WAITERS

    async def main() -> None:
        loop = asyncio.get_running_loop()
        for _ in range(ROUNDS):
            await one_round(loop)

    asyncio.run(main())


def test_thread_abort_racing_thread_open_is_consistent_for_every_coroutine() -> None:
    async def one_round(loop: asyncio.AbstractEventLoop) -> None:
        gate = AsyncGate()
        start = threading.Barrier(2)
        wins: dict[str, bool] = {}

        def opener() -> None:
            start.wait(GUARD)
            wins["open"] = gate.open()

        def aborter() -> None:
            start.wait(GUARD)
            wins["abort"] = gate.abort("race")

        waiters = [asyncio.create_task(gate.wait()) for _ in range(WAITERS)]
        racers = [loop.run_in_executor(None, opener), loop.run_in_executor(None, aborter)]
        await asyncio.wait_for(asyncio.gather(*racers), GUARD)
        results = await asyncio.wait_for(asyncio.gather(*waiters, return_exceptions=True), GUARD)
        assert sorted(wins.values()) == [False, True]
        if wins["open"]:
            assert results == [True] * WAITERS
        else:
            assert all(isinstance(r, BrokenLatchError) for r in results)

    async def main() -> None:
        loop = asyncio.get_running_loop()
        for _ in range(ROUNDS):
            await one_round(loop)

    asyncio.run(main())


def test_cancellations_and_timeouts_do_not_leak_or_steal_wakeups() -> None:
    async def one_round() -> None:
        event = AsyncOneShotEvent()
        keep = [asyncio.create_task(event.wait()) for _ in range(WAITERS)]
        doomed = [asyncio.create_task(event.wait()) for _ in range(WAITERS)]
        timed = [asyncio.create_task(event.wait(0.0001)) for _ in range(WAITERS)]
        await asyncio.sleep(0)
        for task in doomed:
            task.cancel()
        await asyncio.gather(*doomed, *timed, return_exceptions=True)
        assert event.set() is True
        assert await asyncio.wait_for(asyncio.gather(*keep), GUARD) == [True] * WAITERS
        assert all(task.cancelled() for task in doomed)
        assert event._waiters == {}

    async def main() -> None:
        for _ in range(ROUNDS):
            await one_round()

    asyncio.run(main())


@pytest.mark.parametrize("round_", range(5))
def test_waiters_on_many_loops_all_release(round_: int) -> None:
    latch = AsyncCountDownLatch(SIGNALERS)
    loops = 8
    parked = threading.Barrier(loops + 1)
    results: list[list[bool]] = []

    def run_loop() -> None:
        async def main() -> list[bool]:
            tasks = [asyncio.create_task(latch.wait()) for _ in range(32)]
            await asyncio.sleep(0)
            parked.wait(GUARD)
            return list(await asyncio.wait_for(asyncio.gather(*tasks), GUARD))

        results.append(asyncio.run(main()))

    threads = [threading.Thread(target=run_loop, daemon=True) for _ in range(loops)]
    for thread in threads:
        thread.start()
    parked.wait(GUARD)
    signalers = [threading.Thread(target=latch.count_down, daemon=True) for _ in range(SIGNALERS)]
    for thread in signalers:
        thread.start()
    for thread in signalers + threads:
        thread.join(GUARD)
        assert not thread.is_alive()
    assert results == [[True] * 32] * loops
