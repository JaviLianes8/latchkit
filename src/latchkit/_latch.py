"""A one-shot counting latch that releases its waiters after N signals."""

from __future__ import annotations

import threading

__all__ = ["CountDownLatch"]


class CountDownLatch:
    """Block callers until a fixed number of signals arrive, then stay open.

    Unlike :class:`threading.Barrier`, the threads that call :meth:`count_down`
    need not be the ones that :meth:`wait`, the count only moves down, and once
    it reaches zero the latch is open forever (acyclic).
    """

    def __init__(self, count: int) -> None:
        if count < 0:
            raise ValueError("count must be zero or greater")
        self._remaining = count
        self._cond = threading.Condition()

    @property
    def remaining(self) -> int:
        """Signals still needed before the latch opens (never negative)."""
        with self._cond:
            return self._remaining

    def count_down(self, n: int = 1) -> int:
        """Record ``n`` signals and return the signals still needed.

        ``n`` must be at least one. Counting past zero is clamped: the latch
        opens and the count never goes negative. Calling an already open latch
        is a no-op that returns zero.
        """
        if n < 1:
            raise ValueError("n must be one or greater")
        with self._cond:
            if self._remaining == 0:
                return 0
            self._remaining = max(0, self._remaining - n)
            if self._remaining == 0:
                self._cond.notify_all()
            return self._remaining

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the latch opens.

        Return ``True`` if the latch is open, ``False`` if ``timeout`` elapsed
        first. A ``None`` timeout waits forever. Returns at once when the latch
        is already open.
        """
        with self._cond:
            return self._cond.wait_for(lambda: self._remaining == 0, timeout)
