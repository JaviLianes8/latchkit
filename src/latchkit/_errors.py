"""Typed errors and the timeout rules shared by every primitive."""

from __future__ import annotations

import math
import threading

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
        message = "aborted" if reason is None else f"aborted: {reason}"
        super().__init__(message)
        self.reason = reason


class LatchTimeoutError(LatchError, TimeoutError):
    """Raised by ``wait_or_raise`` when the timeout elapses before opening.

    It subclasses :class:`TimeoutError`, so ``except TimeoutError`` catches it.
    """


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

    Negative values behave like zero, as in :mod:`threading`. Infinity and any
    value above :data:`threading.TIMEOUT_MAX` mean "forever" instead of raising
    :class:`OverflowError`. ``NaN`` is rejected with :class:`ValueError`, since
    it would otherwise make ``Condition.wait_for`` spin forever.
    """
    if timeout is None:
        return None
    value = float(timeout)
    if math.isnan(value):
        raise ValueError("timeout must not be NaN")
    if value > threading.TIMEOUT_MAX:
        return None
    return max(0.0, value)
