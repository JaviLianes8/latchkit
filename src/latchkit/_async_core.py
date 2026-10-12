"""Shared core of the asyncio primitives: thread-safe signalling, loop-aware waiting."""

from __future__ import annotations

import asyncio
import contextlib
import threading

from ._errors import normalize_timeout, outcome, timed_out
from ._state import BROKEN, PENDING, STATE_NAMES

__all__ = ["AsyncOneShot"]

_Waiters = dict[asyncio.Future[None], asyncio.AbstractEventLoop]


def _resolve(future: asyncio.Future[None]) -> None:
    if not future.done():
        future.set_result(None)


def _wake(waiters: _Waiters) -> None:
    for future, loop in waiters.items():
        # A closed loop raises RuntimeError; its waiting task can never resume.
        with contextlib.suppress(RuntimeError):
            loop.call_soon_threadsafe(_resolve, future)


class AsyncOneShot:
    """Pending until it opens or breaks, exactly once, then fixed forever.

    State lives behind a :class:`threading.Lock` that is never held across an
    ``await``. Signalling methods are plain functions, safe to call from the
    event loop or from any other thread. Each waiter parks on a future of its
    own loop and is woken with ``call_soon_threadsafe``, so waiters on several
    loops are supported. Actions before a signal happen-before the actions
    that follow the matching ``await wait()``.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = PENDING
        self._abort_reason: object = None
        self._waiters: _Waiters = {}

    @property
    def is_broken(self) -> bool:
        """Whether :meth:`abort` broke the primitive before it opened."""
        with self._lock:
            return self._state == BROKEN

    @property
    def abort_reason(self) -> object:
        """The reason given to :meth:`abort`, or ``None`` if it is not broken."""
        with self._lock:
            return self._abort_reason

    def abort(self, reason: object = None) -> bool:
        """Break the primitive: every current and future waiter raises.

        Waiters raise :class:`~latchkit.BrokenLatchError` carrying ``reason``
        (chained as ``__cause__`` when it is an exception). The first
        transition wins: return ``True`` if this call broke it, ``False`` if it
        was already open or broken. Safe to call from any thread.
        """
        return self._settle(BROKEN, reason)

    async def wait(self, timeout: float | None = None) -> bool:
        """Wait until the primitive opens or breaks.

        Return ``True`` once it is open, ``False`` if ``timeout`` seconds
        elapse first, and raise :class:`~latchkit.BrokenLatchError` if it was
        aborted. Returns without suspending when already settled. Cancelling
        the waiting task raises :class:`asyncio.CancelledError` as usual and
        leaves the primitive untouched; a cancel delivered after the primitive
        opened but before the task resumed still wins, as everywhere in
        asyncio. Timeouts follow the same rules as the threaded classes and
        use the event loop's monotonic clock. A waiter whose loop stops
        without closing stays registered until the primitive settles.
        """
        limit = normalize_timeout(timeout)
        loop = asyncio.get_running_loop()
        with self._lock:
            state, reason = self._state, self._abort_reason
            if state == PENDING and limit != 0.0:
                future: asyncio.Future[None] = loop.create_future()
                self._waiters[future] = loop
        if state != PENDING or limit == 0.0:
            return outcome(state, reason)
        timer = None if limit is None else loop.call_later(limit, _resolve, future)
        try:
            await future
        finally:
            if timer is not None:
                timer.cancel()
            with self._lock:
                self._waiters.pop(future, None)
                state, reason = self._state, self._abort_reason
        return outcome(state, reason)

    async def wait_or_raise(self, timeout: float | None = None) -> None:
        """Like :meth:`wait`, but raise instead of returning ``False``.

        Raise :class:`~latchkit.LatchTimeoutError` (a :class:`TimeoutError`)
        when ``timeout`` elapses first, and
        :class:`~latchkit.BrokenLatchError` when the primitive was aborted.
        """
        if not await self.wait(timeout):
            raise timed_out(timeout)

    def __repr__(self) -> str:
        with self._lock:
            return f"<{type(self).__name__} {self._describe_locked()}>"

    def _describe_locked(self) -> str:
        return STATE_NAMES[self._state]

    def _settle(self, state: int, reason: object = None) -> bool:
        with self._lock:
            waiters = self._settle_locked(state, reason)
        if waiters is None:
            return False
        self._wake_all(waiters)
        return True

    @staticmethod
    def _wake_all(waiters: _Waiters) -> None:
        _wake(waiters)

    def _settle_locked(self, state: int, reason: object = None) -> _Waiters | None:
        if self._state != PENDING:
            return None
        self._state = state
        self._abort_reason = reason if state == BROKEN else None
        waiters, self._waiters = self._waiters, {}
        return waiters
