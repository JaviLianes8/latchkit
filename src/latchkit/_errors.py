"""Typed errors and how a settled state becomes a wait result."""

from __future__ import annotations

from ._state import BROKEN, OPEN

__all__ = ["BrokenLatchError", "LatchError", "LatchTimeoutError"]

REASON_PREVIEW = 200
"""At most this many characters of ``str(reason)`` appear in a message."""


class LatchError(Exception):
    """Base class for every error raised by latchkit.

    >>> from latchkit import BrokenLatchError, LatchError, LatchTimeoutError
    >>> issubclass(BrokenLatchError, LatchError), issubclass(LatchTimeoutError, LatchError)
    (True, True)
    """


class BrokenLatchError(LatchError):
    """Raised by a wait on a primitive that was aborted before it opened.

    ``reason`` is the value passed to ``abort``. When it is an exception it is
    also chained as ``__cause__``, so tracebacks show why the primitive broke.
    Each waiter receives its own instance, never a shared one. The message
    shows at most the first 200 characters of ``str(reason)``, or the type
    name in angle brackets when that text is blank or cannot be computed.

    >>> from latchkit import BrokenLatchError, Gate
    >>> gate = Gate()
    >>> gate.abort("config missing")
    True
    >>> try:
    ...     gate.wait()
    ... except BrokenLatchError as error:
    ...     print(error, "|", error.reason)
    aborted: config missing | config missing
    """

    def __init__(self, reason: object = None) -> None:
        super().__init__(_describe(reason))
        self.reason = reason

    def __reduce__(self) -> tuple[type[BrokenLatchError], tuple[object]]:
        return (type(self), (self.reason,))


class LatchTimeoutError(LatchError, TimeoutError):
    """Raised by ``wait_or_raise`` when the timeout elapses before opening.

    It subclasses :class:`TimeoutError`, so ``except TimeoutError`` catches it.

    >>> from latchkit import CountDownLatch
    >>> try:
    ...     CountDownLatch(1).wait_or_raise(timeout=0)
    ... except TimeoutError as error:
    ...     print(type(error).__name__, "|", error)
    LatchTimeoutError | not opened within 0 seconds
    """


def _describe(reason: object) -> str:
    if reason is None:
        return "aborted"
    try:
        # str.__str__ turns a str subclass into a plain str, so no user method
        # (__format__, strip, __len__, slicing) runs on the text afterwards.
        text = str.__str__(str(reason))
    except Exception:  # a broken __str__ must not hide the abort itself
        text = ""
    if not text.strip():  # a blank text (a bare CancelledError, say) shows the type
        return f"aborted: <{str.__str__(type(reason).__name__)[:40]}>"
    if len(text) > REASON_PREVIEW:
        text = text[:REASON_PREVIEW] + "..."
    return "aborted: " + text


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


def timed_out(limit: float) -> LatchTimeoutError:
    """Build the error raised by ``wait_or_raise`` after waiting ``limit`` seconds."""
    return LatchTimeoutError(f"not opened within {limit:.15g} seconds")
