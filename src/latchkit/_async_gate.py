"""The asyncio counterparts of Gate and OneShotEvent."""

from __future__ import annotations

from ._async_core import AsyncOneShot
from ._scope import SignalScope
from ._state import OPEN

__all__ = ["AsyncGate", "AsyncOneShotEvent"]


class AsyncGate(AsyncOneShot):
    """An asyncio one-shot gate: ``await wait()`` until someone :meth:`open` s it.

    Same API and semantics as :class:`~latchkit.Gate`, except that
    :meth:`wait` and :meth:`wait_or_raise` are coroutines. Unlike
    :class:`asyncio.Event` it can never be cleared, and :meth:`open` and
    :meth:`abort` are safe to call from any thread.
    """

    @property
    def is_open(self) -> bool:
        """Whether the gate has been opened."""
        with self._lock:
            return self._state == OPEN

    def open(self) -> bool:
        """Open the gate; ``True`` if this call opened it, ``False`` otherwise."""
        return self._settle(OPEN)

    def opening(self) -> SignalScope:
        """Return a context manager that opens on success and aborts on error.

        Same rules as :meth:`latchkit.Gate.opening`; usable with ``with`` and
        ``async with``.
        """
        return SignalScope(self.open, self.abort)


class AsyncOneShotEvent(AsyncOneShot):
    """An asyncio event that fires exactly once and names the caller that fired it.

    Same API and semantics as :class:`~latchkit.OneShotEvent`, except that
    :meth:`wait` and :meth:`wait_or_raise` are coroutines. :meth:`set` and
    :meth:`abort` are safe to call from any thread.
    """

    @property
    def is_set(self) -> bool:
        """Whether the event has fired."""
        with self._lock:
            return self._state == OPEN

    def set(self) -> bool:
        """Fire the event. ``True`` for the first caller, ``False`` after or once aborted."""
        return self._settle(OPEN)
