"""Manual one-shot gates: opened once, they stay open for every waiter."""

from __future__ import annotations

from ._scope import SignalScope
from ._state import OPEN
from ._sync import SyncOneShot

__all__ = ["Gate", "OneShotEvent"]


class Gate(SyncOneShot):
    """A manual, one-shot gate: callers :meth:`wait` until someone :meth:`open` s it.

    Like :class:`threading.Event` but acyclic: it cannot be cleared, so a waiter
    that arrives after it opens returns at once and it never closes again. It
    can be aborted instead, which makes every waiter raise
    :class:`~latchkit.BrokenLatchError`.

    Memory ordering: actions before :meth:`open` or :meth:`abort` happen-before
    actions following a return from :meth:`wait` in another thread.
    """

    @property
    def is_open(self) -> bool:
        """Whether the gate has been opened."""
        with self._cond:
            return self._state == OPEN

    def open(self) -> bool:
        """Open the gate and release every waiter. Idempotent.

        Return ``True`` if this call opened it, ``False`` if it was already
        open or had been aborted (an aborted gate never opens).
        """
        with self._cond:
            return self._settle_locked(OPEN)

    def opening(self) -> SignalScope:
        """Return a context manager that opens the gate when its block succeeds.

        If the block raises, the gate is aborted with the exception as reason,
        so waiters fail fast instead of hanging. The exception still propagates.
        This is the run-once initialisation guard. Works with ``with`` and
        ``async with``.
        """
        return SignalScope(self.open, self.abort)


class OneShotEvent(SyncOneShot):
    """An event that fires exactly once and names the caller that fired it.

    The first :meth:`set` returns ``True`` (the winner), later calls return
    ``False`` without reopening anything. This expresses run-once init and
    first-wins races, which :class:`threading.Event` (cyclic, no winner) cannot.

    Memory ordering: actions before :meth:`set` or :meth:`abort` happen-before
    actions following a return from :meth:`wait` in another thread.
    """

    @property
    def is_set(self) -> bool:
        """Whether the event has fired."""
        with self._cond:
            return self._state == OPEN

    def set(self) -> bool:
        """Fire the event. Return ``True`` for the first caller, ``False`` after.

        Also ``False`` once the event has been aborted: it never fires then.
        """
        with self._cond:
            return self._settle_locked(OPEN)
