"""asyncio-specific behaviour: cancellation, cleanup, threads and several loops."""

from __future__ import annotations

import asyncio
import threading

import pytest

from latchkit import AsyncCountDownLatch, AsyncGate, AsyncOneShotEvent, BrokenLatchError

GUARD = 30.0  # deadlock guard only; never the thing under test


def test_waiters_park_and_release_on_open() -> None:
    async def main() -> None:
        gate = AsyncGate()
        tasks = [asyncio.create_task(gate.wait()) for _ in range(10)]
        await asyncio.sleep(0)
        assert not any(task.done() for task in tasks)
        assert gate.open() is True
        assert await asyncio.wait_for(asyncio.gather(*tasks), GUARD) == [True] * 10
        assert gate._waiters == {}

    asyncio.run(main())


def test_cancelling_a_waiter_leaves_the_primitive_pending_and_clean() -> None:
    async def main() -> None:
        latch = AsyncCountDownLatch(1)
        doomed = asyncio.create_task(latch.wait())
        survivor = asyncio.create_task(latch.wait())
        await asyncio.sleep(0)
        doomed.cancel()
        with pytest.raises(asyncio.CancelledError):
            await doomed
        assert latch.remaining == 1
        assert len(latch._waiters) == 1
        latch.count_down()
        assert await asyncio.wait_for(survivor, GUARD) is True
        assert latch._waiters == {}

    asyncio.run(main())


def test_a_cancel_after_open_wins_for_that_task_only() -> None:
    async def main() -> None:
        event = AsyncOneShotEvent()
        doomed = asyncio.create_task(event.wait())
        others = [asyncio.create_task(event.wait()) for _ in range(5)]
        await asyncio.sleep(0)
        assert event.set() is True
        doomed.cancel()  # same tick: delivered before the task resumes
        with pytest.raises(asyncio.CancelledError):
            await doomed
        assert await asyncio.wait_for(asyncio.gather(*others), GUARD) == [True] * 5
        assert event._waiters == {}

    asyncio.run(main())


def test_a_timed_out_waiter_is_removed() -> None:
    async def main() -> None:
        event = AsyncOneShotEvent()
        assert await event.wait(0.01) is False
        assert event._waiters == {}
        assert event.set() is True
        assert await event.wait(0.01) is True

    asyncio.run(main())


def test_abort_reaches_parked_waiters() -> None:
    async def main() -> None:
        gate = AsyncGate()
        tasks = [asyncio.create_task(gate.wait()) for _ in range(5)]
        await asyncio.sleep(0)
        gate.abort("shutdown")
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), GUARD)
        assert all(isinstance(r, BrokenLatchError) and r.reason == "shutdown" for r in results)

    asyncio.run(main())


def test_worker_threads_can_count_down_into_the_loop() -> None:
    async def main() -> None:
        latch = AsyncCountDownLatch(8)
        loop = asyncio.get_running_loop()
        waiter = asyncio.create_task(latch.wait())
        await asyncio.gather(*(loop.run_in_executor(None, latch.count_down) for _ in range(8)))
        assert await asyncio.wait_for(waiter, GUARD) is True

    asyncio.run(main())


def test_waiters_on_several_loops_are_all_released() -> None:
    gate = AsyncGate()
    loops = 4
    parked = threading.Barrier(loops + 1)
    results: list[list[bool]] = []

    def run_loop() -> None:
        async def main() -> list[bool]:
            tasks = [asyncio.create_task(gate.wait()) for _ in range(5)]
            await asyncio.sleep(0)
            parked.wait(GUARD)  # every task of this loop is now parked
            return list(await asyncio.wait_for(asyncio.gather(*tasks), GUARD))

        results.append(asyncio.run(main()))

    threads = [threading.Thread(target=run_loop, daemon=True) for _ in range(loops)]
    for thread in threads:
        thread.start()
    parked.wait(GUARD)
    assert len(gate._waiters) == loops * 5
    gate.open()
    for thread in threads:
        thread.join(GUARD)
        assert not thread.is_alive()
    assert results == [[True] * 5] * loops


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_a_waiter_on_a_closed_loop_does_not_break_signalling() -> None:
    gate = AsyncGate()
    loop = asyncio.new_event_loop()
    task = loop.create_task(gate.wait())
    loop.run_until_complete(asyncio.sleep(0))
    loop.close()
    task._log_destroy_pending = False  # type: ignore[attr-defined]  # abandoned on purpose
    assert len(gate._waiters) == 1
    assert gate.open() is True
    assert gate.is_open is True
    assert gate._waiters == {}, "settling forgets waiters that can never resume"


def test_settled_primitives_return_without_suspending() -> None:
    async def main() -> None:
        gate = AsyncGate()
        gate.open()
        broken = AsyncGate()
        broken.abort()
        assert await gate.wait() is True
        with pytest.raises(BrokenLatchError):
            await broken.wait()
        assert gate._waiters == {} and broken._waiters == {}

    asyncio.run(main())


def test_a_zero_timeout_on_a_pending_primitive_never_suspends() -> None:
    async def main() -> None:
        for prim in (AsyncGate(), AsyncCountDownLatch(1), AsyncOneShotEvent()):
            for timeout in (0, -1, -0.0):
                coroutine = prim.wait(timeout)
                with pytest.raises(StopIteration) as done:
                    coroutine.send(None)  # finished on the first step: no await happened
                assert done.value.value is False
                assert prim._waiters == {}

    asyncio.run(main())


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_a_closed_loop_waiter_does_not_stop_the_wakeup_of_later_waiters() -> None:
    gate = AsyncGate()
    dead = asyncio.new_event_loop()
    abandoned = dead.create_task(gate.wait())
    dead.run_until_complete(asyncio.sleep(0))
    dead.close()
    abandoned._log_destroy_pending = False  # type: ignore[attr-defined]

    async def live() -> bool:
        task = asyncio.create_task(gate.wait())
        await asyncio.sleep(0)
        assert len(gate._waiters) == 2  # the dead loop's waiter comes first
        threading.Thread(target=gate.open, daemon=True).start()
        return await asyncio.wait_for(task, GUARD)

    assert asyncio.run(live()) is True
