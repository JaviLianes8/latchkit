"""Argument checks shared by every primitive, with short messages that never echo input."""

from __future__ import annotations

import math
import numbers
import operator

__all__ = ["check_count", "check_step", "count_text", "normalize_timeout", "type_name"]


def type_name(value: object) -> str:
    """The name of ``value``'s type, as plain text of at most 40 characters."""
    try:  # a metaclass may make __name__ anything at all, or raise
        return str.__str__(type(value).__name__)[:40]
    except Exception:
        return "unnamed type"


def _whole(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an int, not bool")
    try:
        return operator.index(value)  # type: ignore[arg-type]
    except TypeError:
        raise TypeError(f"{name} must be an int, not {type_name(value)}") from None


def check_count(count: object) -> int:
    """Return ``count`` as an int that is zero or greater."""
    value = _whole(count, "count")
    if value < 0:
        raise ValueError("count must be zero or greater")
    return value


def check_step(n: object) -> int:
    """Return ``n`` as an int that is one or greater."""
    value = _whole(n, "n")
    if value < 1:
        raise ValueError("n must be one or greater")
    return value


def normalize_timeout(timeout: object) -> float | None:
    """Return the effective timeout in seconds, or ``None`` for "wait forever".

    ``None`` and positive infinity mean forever. Any other real number counts,
    ``bool`` excepted. Negative values behave like zero, as in :mod:`threading`.
    An integer too large for a float is forever (or zero when negative). Large
    finite values are honoured exactly. ``NaN`` raises :class:`ValueError`,
    since the standard library would spin on it.
    """
    if timeout is None:
        return None
    if isinstance(timeout, bool) or not isinstance(timeout, numbers.Real):
        raise TypeError(f"timeout must be a real number or None, not {type_name(timeout)}")
    try:
        value = float(timeout)
    except OverflowError:
        return 0.0 if timeout < 0 else None
    if math.isnan(value):
        raise ValueError("timeout must not be NaN")
    if math.isinf(value) and value > 0:
        return None
    return max(0.0, value)


def count_text(count: int) -> str:
    """Show a count in a repr; counts beyond 64 bits show their size instead."""
    if count.bit_length() > 64:
        return f"<{count.bit_length()}-bit int>"
    return str(count)
