"""Manual one-shot gates: opened once, they stay open for every waiter."""

from __future__ import annotations

import threading

__all__ = ["Gate", "OneShotEvent"]


class Gate:
    """A manual, one-shot gate: callers :meth:`wait` until someone :meth:`open` s it.

    Like :class:`threading.Event` but acyclic: it cannot be cleared, so a waiter
    that arrives after it opens returns at once and it never closes again.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._open = False

    @property
    def is_open(self) -> bool:
        """Whether the gate has been opened."""
        with self._cond:
            return self._open

    def open(self) -> None:
        """Open the gate and release every waiter. Idempotent."""
        with self._cond:
            self._open = True
            self._cond.notify_all()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the gate is open.

        Return ``True`` if it is open, ``False`` if ``timeout`` elapsed first.
        A ``None`` timeout waits forever.
        """
        with self._cond:
            return self._cond.wait_for(lambda: self._open, timeout)


class OneShotEvent:
    """An event that fires exactly once and names the caller that fired it.

    The first :meth:`set` returns ``True`` (the winner), later calls return
    ``False`` without reopening anything. This expresses run-once init and
    first-wins races, which :class:`threading.Event` (cyclic, no winner) cannot.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._set = False

    @property
    def is_set(self) -> bool:
        """Whether the event has fired."""
        with self._cond:
            return self._set

    def set(self) -> bool:
        """Fire the event. Return ``True`` for the first caller, ``False`` after."""
        with self._cond:
            if self._set:
                return False
            self._set = True
            self._cond.notify_all()
            return True

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the event fires.

        Return ``True`` if it has fired, ``False`` if ``timeout`` elapsed first.
        A ``None`` timeout waits forever.
        """
        with self._cond:
            return self._cond.wait_for(lambda: self._set, timeout)
