"""Shared core of the thread-based primitives: one lock, one state, one transition."""

from __future__ import annotations

import threading
import time

from ._check import normalize_timeout
from ._errors import outcome, timed_out
from ._state import BROKEN, PENDING, STATE_NAMES

__all__ = ["SyncOneShot"]


class SyncOneShot:
    """Pending until it opens or breaks, exactly once, then fixed forever.

    Every read and write of the state happens under one
    :class:`threading.Condition`, so all actions a thread performs before it
    opens or aborts the primitive happen-before the actions that follow a
    successful return (or a raise) from :meth:`wait` in another thread.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._state = PENDING
        self._abort_reason: object = None

    @property
    def is_broken(self) -> bool:
        """Whether :meth:`abort` broke the primitive before it opened."""
        with self._cond:
            return self._state == BROKEN

    @property
    def abort_reason(self) -> object:
        """The reason given to :meth:`abort`, or ``None`` if it is not broken."""
        with self._cond:
            return self._abort_reason

    def abort(self, reason: object = None) -> bool:
        """Break the primitive: every current and future waiter raises.

        Waiters raise :class:`~latchkit.BrokenLatchError` carrying ``reason``
        (chained as ``__cause__`` when it is an exception). The first
        transition wins: return ``True`` if this call broke it, ``False`` if it
        was already open or broken, in which case nothing changes.

        >>> from latchkit import CountDownLatch
        >>> latch = CountDownLatch(1)
        >>> latch.abort("gave up"), latch.abort("again"), latch.abort_reason
        (True, False, 'gave up')
        >>> latch.is_broken, latch.count_down()
        (True, 1)
        """
        with self._cond:
            return self._settle_locked(BROKEN, reason)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the primitive opens or breaks.

        Return ``True`` once it is open, ``False`` if ``timeout`` seconds
        elapse first, and raise :class:`~latchkit.BrokenLatchError` if it was
        aborted. Returns at once when already settled. ``None`` waits forever;
        the deadline uses the monotonic clock and is immune to wall-clock
        changes and spurious wakeups. Negative timeouts behave like zero,
        infinity means forever, timeouts longer than
        :data:`threading.TIMEOUT_MAX` are honoured, ``NaN`` raises
        :class:`ValueError`, and a ``timeout`` that is not a real number (or is
        a ``bool``) raises :class:`TypeError`.

        >>> from latchkit import Gate
        >>> gate = Gate()
        >>> gate.wait(timeout=0.01)
        False
        >>> gate.open()
        True
        >>> gate.wait()
        True
        """
        return outcome(*self._wait(normalize_timeout(timeout)))

    def wait_or_raise(self, timeout: float | None = None) -> None:
        """Like :meth:`wait`, but raise instead of returning ``False``.

        Raise :class:`~latchkit.LatchTimeoutError` (a :class:`TimeoutError`)
        when ``timeout`` elapses first, and
        :class:`~latchkit.BrokenLatchError` when the primitive was aborted.

        >>> from latchkit import Gate
        >>> gate = Gate()
        >>> gate.abort(RuntimeError("no network"))
        True
        >>> gate.wait_or_raise(timeout=0)
        Traceback (most recent call last):
          ...
        latchkit.BrokenLatchError: aborted: no network
        """
        limit = normalize_timeout(timeout)
        if not outcome(*self._wait(limit)):
            raise timed_out(limit or 0.0)

    def _wait(self, limit: float | None) -> tuple[int, object]:
        with self._cond:
            if limit is None:
                self._cond.wait_for(self._settled)
            else:
                deadline = time.monotonic() + limit
                while not self._settled():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        break
                    self._cond.wait(min(left, threading.TIMEOUT_MAX))
            return self._state, self._abort_reason

    def __repr__(self) -> str:
        with self._cond:
            return f"<{type(self).__name__} {self._describe_locked()}>"

    def _describe_locked(self) -> str:
        return STATE_NAMES[self._state]

    def _settled(self) -> bool:
        return self._state != PENDING

    def _settle_locked(self, state: int, reason: object = None) -> bool:
        if self._state != PENDING:
            return False
        self._state = state
        self._abort_reason = reason if state == BROKEN else None
        self._cond.notify_all()
        return True
