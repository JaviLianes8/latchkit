"""The asyncio counterpart of CountDownLatch, signalled safely from any thread."""

from __future__ import annotations

from ._async_core import AsyncOneShot
from ._check import check_count, check_step, count_text
from ._scope import SignalScope
from ._state import OPEN, PENDING

__all__ = ["AsyncCountDownLatch"]


class AsyncCountDownLatch(AsyncOneShot):
    """An asyncio latch: ``await wait()`` until ``count`` signals arrive.

    Same API and semantics as :class:`~latchkit.CountDownLatch`, except that
    :meth:`wait` and :meth:`wait_or_raise` are coroutines. Unlike
    :class:`asyncio.Event`, :meth:`count_down`, :meth:`try_count_up` and
    :meth:`abort` are thread-safe, so worker threads (for example inside
    ``loop.run_in_executor``) can signal coroutines waiting on any loop.

    >>> import asyncio
    >>> from latchkit import AsyncCountDownLatch
    >>> async def main() -> bool:
    ...     latch = AsyncCountDownLatch(4)
    ...     loop = asyncio.get_running_loop()
    ...     for _ in range(4):
    ...         loop.run_in_executor(None, latch.count_down)
    ...     return await latch.wait(timeout=60)
    >>> asyncio.run(main())
    True
    """

    def __init__(self, count: int) -> None:
        super().__init__()
        self._remaining = check_count(count)
        if self._remaining == 0:
            self._state = OPEN

    @property
    def remaining(self) -> int:
        """Signals still needed before the latch opens (never negative)."""
        with self._lock:
            return self._remaining

    @property
    def is_open(self) -> bool:
        """Whether the count has reached zero."""
        with self._lock:
            return self._state == OPEN

    def count_down(self, n: int = 1) -> int:
        """Record ``n`` signals and return the signals still needed.

        Same rules as :meth:`latchkit.CountDownLatch.count_down`. Never blocks
        and is safe to call from any thread.
        """
        n = check_step(n)
        with self._lock:
            if self._state != PENDING:
                return self._remaining
            self._remaining = max(0, self._remaining - n)
            remaining = self._remaining
            waiters = self._settle_locked(OPEN) if remaining == 0 else None
        if waiters is not None:
            self._wake_all(waiters)
        return remaining

    def try_count_up(self, n: int = 1) -> bool:
        """Raise the count by ``n`` while pending; ``False`` once open or broken."""
        n = check_step(n)
        with self._lock:
            if self._state != PENDING:
                return False
            self._remaining += n
            return True

    def arrival(self, *, abort_on_error: bool = False) -> SignalScope:
        """Return a context manager that counts down once when its block exits.

        Same rules as :meth:`latchkit.CountDownLatch.arrival`; usable with
        ``with`` and ``async with``.
        """
        on_error = self.abort if abort_on_error else None
        return SignalScope(self.count_down, on_error)

    def _describe_locked(self) -> str:
        if self._state == PENDING:
            return f"remaining={count_text(self._remaining)}"
        return super()._describe_locked()
