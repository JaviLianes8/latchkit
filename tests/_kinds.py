"""One uniform driver per primitive, so the contract runs over all six of them.

Async primitives are driven through ``asyncio.run`` so the same assertions apply
to both families without mocks: every wait below is a real wait.
"""

from __future__ import annotations

import asyncio
import atexit
import threading
import time
import weakref
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

import latchkit

GUARD = 60.0
T = TypeVar("T")
_LOOPS = threading.local()


def run_async(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run ``coroutine`` on this thread's own reusable event loop.

    The suite awaits primitives thousands of times. ``asyncio.run`` would build a
    new loop each time, and on Windows every loop opens a loopback socket pair:
    thousands of them can exhaust the ephemeral ports, and CPython 3.13.2 then
    blocks forever in ``accept`` while building the next one. One loop per thread
    keeps that to a handful.
    """
    loop = getattr(_LOOPS, "loop", None)
    if loop is None or loop.is_closed():
        loop = _LOOPS.loop = asyncio.new_event_loop()
        if threading.current_thread() is threading.main_thread():
            atexit.register(loop.close)
        else:
            _LOOPS.finalizer = weakref.finalize(threading.current_thread(), loop.close)
    return loop.run_until_complete(coroutine)


def until(predicate: Callable[[], bool]) -> None:
    """Poll until ``predicate`` holds; the deadline is only a deadlock guard."""
    deadline = time.monotonic() + GUARD
    while not predicate():
        assert time.monotonic() < deadline, "deadlock guard tripped"
        time.sleep(0.001)


def parked(prim: Any) -> int:
    """How many waiters are blocked inside ``prim`` right now."""
    if hasattr(prim, "_waiters"):
        return len(prim._waiters)
    return len(prim._cond._waiters)  # CPython's Condition keeps its waiter deque here


@dataclass(frozen=True)
class Kind:
    name: str
    make: Callable[[], Any]
    fire: Callable[[Any], bool]
    fired: Callable[[Any], bool]
    is_async: bool

    def wait(self, prim: Any, timeout: float | None = None) -> bool:
        if self.is_async:
            return bool(run_async(prim.wait(timeout)))
        return bool(prim.wait(timeout))

    def wait_or_raise(self, prim: Any, timeout: float | None = None) -> None:
        if self.is_async:
            run_async(prim.wait_or_raise(timeout))
        else:
            prim.wait_or_raise(timeout)


def _fire_latch(latch: Any) -> bool:
    if latch.remaining == 0:
        return False
    return bool(latch.count_down() == 0)


KINDS = [
    Kind(
        "CountDownLatch",
        lambda: latchkit.CountDownLatch(1),
        _fire_latch,
        lambda p: p.is_open,
        False,
    ),
    Kind("Gate", latchkit.Gate, lambda p: p.open(), lambda p: p.is_open, False),
    Kind("OneShotEvent", latchkit.OneShotEvent, lambda p: p.set(), lambda p: p.is_set, False),
    Kind(
        "AsyncCountDownLatch",
        lambda: latchkit.AsyncCountDownLatch(1),
        _fire_latch,
        lambda p: p.is_open,
        True,
    ),
    Kind("AsyncGate", latchkit.AsyncGate, lambda p: p.open(), lambda p: p.is_open, True),
    Kind(
        "AsyncOneShotEvent", latchkit.AsyncOneShotEvent, lambda p: p.set(), lambda p: p.is_set, True
    ),
]

KIND_IDS = [kind.name for kind in KINDS]
