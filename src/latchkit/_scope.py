"""A context manager that signals a primitive when its block exits."""

from __future__ import annotations

from collections.abc import Callable
from types import TracebackType

__all__ = ["SignalScope"]


class SignalScope:
    """Run ``on_success`` when the block exits, or ``on_error`` if it raised.

    When ``on_error`` is ``None`` a failing block runs ``on_success`` too, the
    ``try``/``finally`` shape. The exception is never swallowed. Usable with
    both ``with`` and ``async with``, since signalling never blocks.
    """

    __slots__ = ("_on_error", "_on_success")

    def __init__(
        self,
        on_success: Callable[[], object],
        on_error: Callable[[BaseException], object] | None = None,
    ) -> None:
        self._on_success = on_success
        self._on_error = on_error

    def __enter__(self) -> None:
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc is not None and self._on_error is not None:
            self._on_error(exc)
        else:
            self._on_success()

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.__exit__(exc_type, exc, tb)
