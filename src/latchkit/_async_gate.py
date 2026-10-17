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

    >>> import asyncio
    >>> from latchkit import AsyncGate
    >>> async def main() -> bool:
    ...     gate = AsyncGate()
    ...     asyncio.get_running_loop().call_soon(gate.open)
    ...     return await gate.wait(timeout=60)
    >>> asyncio.run(main())
    True
    """

    @property
    def is_open(self) -> bool:
        """Whether the gate has been opened.

        >>> from latchkit import AsyncGate
        >>> AsyncGate().is_open
        False
        """
        with self._lock:
            return self._state == OPEN

    def open(self) -> bool:
        """Open the gate; ``True`` if this call opened it, ``False`` otherwise.

        >>> from latchkit import AsyncGate
        >>> gate = AsyncGate()
        >>> gate.open(), gate.open(), gate.is_open
        (True, False, True)
        """
        return self._settle(OPEN)

    def opening(self) -> SignalScope:
        """Return a context manager that opens on success and aborts on error.

        Same rules as :meth:`latchkit.Gate.opening`; usable with ``with`` and
        ``async with``.

        >>> import asyncio
        >>> from latchkit import AsyncGate
        >>> async def main() -> bool:
        ...     gate = AsyncGate()
        ...     async with gate.opening():
        ...         pass
        ...     return await gate.wait(timeout=0)
        >>> asyncio.run(main())
        True
        """
        return SignalScope(self.open, self.abort)


class AsyncOneShotEvent(AsyncOneShot):
    """An asyncio event that fires exactly once and names the caller that fired it.

    Same API and semantics as :class:`~latchkit.OneShotEvent`, except that
    :meth:`wait` and :meth:`wait_or_raise` are coroutines. :meth:`set` and
    :meth:`abort` are safe to call from any thread.

    >>> import asyncio
    >>> from latchkit import AsyncOneShotEvent
    >>> async def main() -> list[bool]:
    ...     event = AsyncOneShotEvent()
    ...     return [event.set(), event.set(), await event.wait(timeout=0)]
    >>> asyncio.run(main())
    [True, False, True]
    """

    @property
    def is_set(self) -> bool:
        """Whether the event has fired.

        >>> from latchkit import AsyncOneShotEvent
        >>> AsyncOneShotEvent().is_set
        False
        """
        with self._lock:
            return self._state == OPEN

    def set(self) -> bool:
        """Fire the event. ``True`` for the first caller, ``False`` after or once aborted.

        >>> from latchkit import AsyncOneShotEvent
        >>> event = AsyncOneShotEvent()
        >>> event.set(), event.set(), event.is_set
        (True, False, True)
        """
        return self._settle(OPEN)
