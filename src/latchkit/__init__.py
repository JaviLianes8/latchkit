"""One-shot synchronization primitives for threads and asyncio: latches and gates."""

from __future__ import annotations

from ._async_gate import AsyncGate, AsyncOneShotEvent
from ._async_latch import AsyncCountDownLatch
from ._errors import BrokenLatchError, LatchError, LatchTimeoutError
from ._gate import Gate, OneShotEvent
from ._latch import CountDownLatch
from ._scope import SignalScope

__version__ = "0.2.0"

__all__ = [
    "AsyncCountDownLatch",
    "AsyncGate",
    "AsyncOneShotEvent",
    "BrokenLatchError",
    "CountDownLatch",
    "Gate",
    "LatchError",
    "LatchTimeoutError",
    "OneShotEvent",
    "SignalScope",
]
