"""One-shot thread synchronization primitives: a counting latch and gates."""

from __future__ import annotations

from ._gate import Gate, OneShotEvent
from ._latch import CountDownLatch

__version__ = "0.1.0"

__all__ = ["CountDownLatch", "Gate", "OneShotEvent"]
