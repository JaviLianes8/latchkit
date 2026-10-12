"""Typed errors and the timeout rules shared by every primitive."""

from __future__ import annotations

import math

from ._state import BROKEN, OPEN

__all__ = ["BrokenLatchError", "LatchError", "LatchTimeoutError"]


class LatchError(Exception):
    """Base class for every error raised by latchkit."""


class BrokenLatchError(LatchError):
    """Raised by a wait on a primitive that was aborted before it opened.

    ``reason`` is the value passed to ``abort``. When it is an exception it is
    also chained as ``__cause__``, so tracebacks show why the primitive broke.
    Each waiter receives its own instance, never a shared one.
    """

    def __init__(self, reason: object = None) -> None:
        super().__init__(_describe(reason))
        self.reason = reason


class LatchTimeoutError(LatchError, TimeoutError):
    """Raised by ``wait_or_raise`` when the timeout elapses before opening.

    It subclasses :class:`TimeoutError`, so ``except TimeoutError`` catches it.
    """


def _describe(reason: object) -> str:
    if reason is None:
        return "aborted"
    try:
        return f"aborted: {reason}"
    except Exception:  # a broken __str__ must not hide the abort itself
        return f"aborted: <{type(reason).__name__}>"


def outcome(state: int, reason: object) -> bool:
    """Turn a state read under the lock into a wait result, outside the lock.

    ``True`` when open, ``False`` when still pending, and a fresh
    :class:`BrokenLatchError` raised when broken. Callers release the lock
    first, so user code in ``reason.__str__`` never runs while it is held.
    """
    if state == OPEN:
        return True
    if state == BROKEN:
        raise broken(reason)
    return False


def broken(reason: object) -> BrokenLatchError:
    """Build a fresh error for one waiter, chaining ``reason`` if it is an exception."""
    error = BrokenLatchError(reason)
    if isinstance(reason, BaseException):
        error.__cause__ = reason
    return error


def timed_out(timeout: float | None) -> LatchTimeoutError:
    """Build the error raised by ``wait_or_raise``."""
    return LatchTimeoutError(f"not opened within {timeout} seconds")


def normalize_timeout(timeout: float | None) -> float | None:
    """Return the effective timeout in seconds, or ``None`` for "wait forever".

    Negative values behave like zero, as in :mod:`threading`. Infinity means
    "forever". Large finite values are honoured exactly (the threaded wait
    sleeps in chunks of at most :data:`threading.TIMEOUT_MAX`). ``NaN`` is
    rejected with :class:`ValueError`, since it would otherwise make
    ``Condition.wait_for`` spin forever.
    """
    if timeout is None:
        return None
    value = float(timeout)
    if math.isnan(value):
        raise ValueError("timeout must not be NaN")
    if math.isinf(value) and value > 0:
        return None
    return max(0.0, value)
