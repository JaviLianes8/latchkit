"""A one-shot counting latch that releases its waiters after N signals."""

from __future__ import annotations

from ._check import check_count, check_step, count_text
from ._scope import SignalScope
from ._state import OPEN, PENDING
from ._sync import SyncOneShot

__all__ = ["CountDownLatch"]


class CountDownLatch(SyncOneShot):
    """Block callers until a fixed number of signals arrive, then stay open.

    Modelled on Java's ``java.util.concurrent.CountDownLatch``. Unlike
    :class:`threading.Barrier`, the threads that call :meth:`count_down` need
    not be the ones that :meth:`wait`, and once the count reaches zero the
    latch is open forever (acyclic). It can also be aborted, which makes every
    waiter raise :class:`~latchkit.BrokenLatchError`.

    ``count`` must be an ``int`` (a ``bool`` or a ``float`` raises
    :class:`TypeError`) that is zero or greater (:class:`ValueError`
    otherwise). A count of zero starts open.

    Memory ordering: actions in a thread before :meth:`count_down` (or
    :meth:`abort`) happen-before actions following a return from :meth:`wait`
    in another thread, since both go through the same lock.

    >>> import threading
    >>> from latchkit import CountDownLatch
    >>> latch = CountDownLatch(3)
    >>> for _ in range(3):
    ...     threading.Thread(target=latch.count_down).start()
    >>> latch.wait(timeout=60)
    True
    >>> latch.remaining, latch.is_open
    (0, True)
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

        >>> from latchkit import CountDownLatch
        >>> CountDownLatch(2).remaining
        2
        """
        with self._cond:
            return self._remaining

    @property
    def is_open(self) -> bool:
        """Whether the count has reached zero.

        >>> from latchkit import CountDownLatch
        >>> CountDownLatch(0).is_open, CountDownLatch(1).is_open
        (True, False)
        """
        with self._cond:
            return self._state == OPEN

    def count_down(self, n: int = 1) -> int:
        """Record ``n`` signals and return the signals still needed.

        ``n`` must be an ``int`` of at least one (same errors as ``count``).
        Counting past zero is clamped: the latch opens and the count never
        goes negative. On an open latch this is a no-op that returns zero; on
        an aborted latch it is a no-op that returns the frozen count.

        >>> from latchkit import CountDownLatch
        >>> latch = CountDownLatch(2)
        >>> latch.count_down(), latch.count_down(5), latch.count_down()
        (1, 0, 0)
        """
        n = check_step(n)
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
        ``CountdownEvent.TryAddCount``, for work that spawns more work. ``n``
        follows the rules of :meth:`count_down`.

        >>> from latchkit import CountDownLatch
        >>> latch = CountDownLatch(1)
        >>> latch.try_count_up(2), latch.remaining
        (True, 3)
        >>> latch.count_down(3), latch.try_count_up()
        (0, False)
        """
        n = check_step(n)
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

        >>> from latchkit import CountDownLatch
        >>> latch = CountDownLatch(2)
        >>> with latch.arrival():
        ...     pass
        >>> latch.remaining
        1
        """
        on_error = self.abort if abort_on_error else None
        return SignalScope(self.count_down, on_error)

    def _describe_locked(self) -> str:
        if self._state == PENDING:
            return f"remaining={count_text(self._remaining)}"
        return super()._describe_locked()
