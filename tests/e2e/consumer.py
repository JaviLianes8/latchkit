"""An external program that uses the installed wheel exactly as a user would.

Run by tests/test_e2e_wheel.py with the throwaway venv's interpreter. It prints
one line per check and exits non-zero on the first failure.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import latchkit
from latchkit import (
    AsyncCountDownLatch,
    AsyncGate,
    BrokenLatchError,
    CountDownLatch,
    Gate,
    LatchTimeoutError,
    OneShotEvent,
)


def check_install() -> None:
    assert "site-packages" in latchkit.__file__, latchkit.__file__
    assert importlib.metadata.version("latchkit") == latchkit.__version__
    print("install ok", latchkit.__version__)


def check_threads() -> None:
    latch = CountDownLatch(8)
    done: list[int] = []

    def work(i: int) -> None:
        with latch.arrival():
            done.append(i)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for i in range(8):
            pool.submit(work, i)
        latch.wait_or_raise(timeout=60)
    assert sorted(done) == list(range(8))
    print("threads ok")


def check_abort() -> None:
    gate = Gate()
    errors: list[BaseException] = []

    def waiter() -> None:
        try:
            gate.wait()
        except BrokenLatchError as error:
            errors.append(error)

    threads = [threading.Thread(target=waiter) for _ in range(4)]
    for thread in threads:
        thread.start()
    try:
        with gate.opening():
            raise OSError("config missing")
    except OSError:
        pass
    for thread in threads:
        thread.join(60)
    assert len(errors) == 4
    assert all(isinstance(e.__cause__, OSError) for e in errors)
    print("abort ok")


def check_event_and_timeout() -> None:
    event = OneShotEvent()
    assert event.set() is True and event.set() is False
    try:
        CountDownLatch(1).wait_or_raise(timeout=0)
    except LatchTimeoutError:
        pass
    else:
        raise AssertionError("expected a timeout")
    print("event ok")


async def check_asyncio() -> None:
    latch = AsyncCountDownLatch(4)
    loop = asyncio.get_running_loop()
    waiters = [asyncio.create_task(latch.wait()) for _ in range(16)]
    await asyncio.gather(*(loop.run_in_executor(None, latch.count_down) for _ in range(4)))
    assert await asyncio.wait_for(asyncio.gather(*waiters), 60) == [True] * 16
    gate = AsyncGate()
    gate.abort("stop")
    try:
        await gate.wait()
    except BrokenLatchError as error:
        assert error.reason == "stop"
    print("asyncio ok")


def main() -> int:
    check_install()
    check_threads()
    check_abort()
    check_event_and_timeout()
    asyncio.run(check_asyncio())
    print("all ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
