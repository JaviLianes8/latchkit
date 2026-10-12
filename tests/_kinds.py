"""One uniform driver per primitive, so the contract runs over all six of them.

Async primitives are driven through ``asyncio.run`` so the same assertions apply
to both families without mocks: every wait below is a real wait.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import latchkit


@dataclass(frozen=True)
class Kind:
    name: str
    make: Callable[[], Any]
    fire: Callable[[Any], bool]
    fired: Callable[[Any], bool]
    is_async: bool

    def wait(self, prim: Any, timeout: float | None = None) -> bool:
        if self.is_async:
            return bool(asyncio.run(prim.wait(timeout)))
        return bool(prim.wait(timeout))

    def wait_or_raise(self, prim: Any, timeout: float | None = None) -> None:
        if self.is_async:
            asyncio.run(prim.wait_or_raise(timeout))
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
