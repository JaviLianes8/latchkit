"""One-shot synchronization primitives for threads and asyncio: latches and gates.

>>> import latchkit
>>> latch = latchkit.CountDownLatch(2)
>>> latch.count_down(), latch.count_down()
(1, 0)
>>> latch.wait(timeout=0)
True
"""

from ._async_gate import AsyncGate, AsyncOneShotEvent
from ._async_latch import AsyncCountDownLatch
from ._errors import BrokenLatchError, LatchError, LatchTimeoutError
from ._gate import Gate, OneShotEvent
from ._latch import CountDownLatch
from ._scope import SignalScope

__version__ = "1.0.0"

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

for _name in __all__:
    globals()[_name].__module__ = __name__
del _name
