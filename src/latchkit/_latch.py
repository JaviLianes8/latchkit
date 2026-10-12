"""A one-shot counting latch that releases its waiters after N signals."""

from __future__ import annotations

from ._scope import SignalScope
from ._state import OPEN, PENDING
from ._sync import SyncOneShot

__all__ = ["CountDownLatch"]


def check_count(count: int) -> int:
    if count < 0:
        raise ValueError("count must be zero or greater")
    return count


def check_step(n: int) -> int:
    if n < 1:
        raise ValueError("n must be one or greater")
    return n


class CountDownLatch(SyncOneShot):
    """Block callers until a fixed number of signals arrive, then stay open.

    Modelled on Java's ``java.util.concurrent.CountDownLatch``. Unlike
    :class:`threading.Barrier`, the threads that call :meth:`count_down` need
    not be the ones that :meth:`wait`, and once the count reaches zero the
    latch is open forever (acyclic). It can also be aborted, which makes every
    waiter raise :class:`~latchkit.BrokenLatchError`.

    Memory ordering: actions in a thread before :meth:`count_down` (or
    :meth:`abort`) happen-before actions following a return from :meth:`wait`
    in another thread, since both go through the same lock.
    """

    def __init__(self, count: int) -> None:
        super().__init__()
        self._remaining = check_count(count)
        if self._remaining == 0:
            self._state = OPEN

    @property
    def remaining(self) -> int:
        """Signals still needed before the latch opens (never negative).

        Java's ``getCount()``. Frozen at its last value once aborted.
        """
        with self._cond:
            return self._remaining

    @property
    def is_open(self) -> bool:
        """Whether the count has reached zero."""
        with self._cond:
            return self._state == OPEN

    def count_down(self, n: int = 1) -> int:
        """Record ``n`` signals and return the signals still needed.

        ``n`` must be at least one. Counting past zero is clamped: the latch
        opens and the count never goes negative. On an open latch this is a
        no-op that returns zero; on an aborted latch it is a no-op that returns
        the frozen count.
        """
        check_step(n)
        with self._cond:
            if self._state != PENDING:
                return self._remaining
            self._remaining = max(0, self._remaining - n)
            if self._remaining == 0:
                self._settle_locked(OPEN)
            return self._remaining

    def try_count_up(self, n: int = 1) -> bool:
        """Raise the count by ``n`` while the latch is still pending.

        Return ``True`` on success. Return ``False``, changing nothing, once the
        latch has opened or broken: a latch never re-opens. This is .NET's
        ``CountdownEvent.TryAddCount``, for work that spawns more work.
        """
        check_step(n)
        with self._cond:
            if self._state != PENDING:
                return False
            self._remaining += n
            return True

    def arrival(self, *, abort_on_error: bool = False) -> SignalScope:
        """Return a context manager that counts down once when its block exits.

        The Python form of ``try { ... } finally { latch.countDown(); }``. With
        ``abort_on_error=True`` a block that raises aborts the latch instead,
        with the exception as reason, so waiters fail fast. The exception still
        propagates. Works with ``with`` and ``async with``.
        """
        on_error = self.abort if abort_on_error else None
        return SignalScope(self.count_down, on_error)

    def _describe_locked(self) -> str:
        if self._state == PENDING:
            return f"remaining={self._remaining}"
        return super()._describe_locked()
