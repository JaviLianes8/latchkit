"""The error types: hierarchy, messages, bounds and pickling."""

from __future__ import annotations

import asyncio
import math
import pickle
from fractions import Fraction

import pytest
from _kinds import KIND_IDS, KINDS, Kind

from latchkit import BrokenLatchError, LatchError, LatchTimeoutError


def test_hierarchy() -> None:
    assert issubclass(LatchError, Exception)
    assert issubclass(BrokenLatchError, LatchError)
    assert issubclass(LatchTimeoutError, LatchError)
    assert issubclass(LatchTimeoutError, TimeoutError)
    assert not issubclass(BrokenLatchError, TimeoutError)


@pytest.mark.parametrize(
    ("reason", "message"),
    [
        (None, "aborted"),
        ("stop", "aborted: stop"),
        (ValueError("bad value"), "aborted: bad value"),
        (42, "aborted: 42"),
        ("", "aborted: <str>"),
        (" \n\t", "aborted: <str>"),
        (" x ", "aborted:  x "),
        ("\r\x0b\u00a0\u2003", "aborted: <str>"),
        (asyncio.CancelledError(), "aborted: <CancelledError>"),
    ],
)
def test_message_names_the_reason(reason: object, message: str) -> None:
    error = BrokenLatchError(reason)
    assert str(error) == message
    assert error.reason is reason
    assert error.args == (message,)


def test_message_shows_at_most_200_characters_of_the_reason() -> None:
    exact = BrokenLatchError("x" * 200)
    assert str(exact) == "aborted: " + "x" * 200
    longer = BrokenLatchError("y" * 201)
    assert str(longer) == "aborted: " + "y" * 200 + "..."
    huge = BrokenLatchError("z" * 10_000_000)
    assert len(str(huge)) == len("aborted: ") + 203
    assert huge.reason == "z" * 10_000_000, "the reason itself is kept whole"


def test_a_reason_whose_str_fails_shows_a_bounded_type_name() -> None:
    class Unprintable:
        def __str__(self) -> str:
            raise RuntimeError("no")

    named = type("N" * 300, (Unprintable,), {})
    assert str(BrokenLatchError(Unprintable())) == "aborted: <Unprintable>"
    assert str(BrokenLatchError(named())) == "aborted: <" + "N" * 40 + ">"


def test_a_reason_whose_str_raises_base_exception_propagates() -> None:
    class Interrupting:
        def __str__(self) -> str:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        BrokenLatchError(Interrupting())


@pytest.mark.parametrize(
    "reason", [None, "stop", 7, ("a", 1), ValueError("bad"), BrokenLatchError("inner")]
)
def test_broken_error_pickles_with_its_reason(reason: object) -> None:
    error = BrokenLatchError(reason)
    copy = pickle.loads(pickle.dumps(error))
    assert type(copy) is BrokenLatchError
    assert str(copy) == str(error)
    assert repr(copy.reason) == repr(reason)


def test_timeout_error_pickles() -> None:
    error = LatchTimeoutError("not opened within 1 seconds")
    copy = pickle.loads(pickle.dumps(error))
    assert type(copy) is LatchTimeoutError
    assert str(copy) == str(error)


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
@pytest.mark.parametrize(
    ("timeout", "shown"),
    [
        (0, "0"),
        (-3, "0"),
        (-(10**400), "0"),
        (0.0015, "0.0015"),
        (Fraction(1, 3) / 100, "0.00333333333333333"),
        (-math.inf, "0"),
    ],
)
def test_timeout_message_shows_the_effective_timeout(
    kind: Kind, timeout: float, shown: str
) -> None:
    with pytest.raises(LatchTimeoutError) as info:
        kind.wait_or_raise(kind.make(), timeout)
    assert str(info.value) == f"not opened within {shown} seconds"
    assert info.value.__cause__ is None


def test_long_timeouts_are_shown_in_full_without_an_exponent() -> None:
    from latchkit._errors import timed_out

    assert str(timed_out(1234567.25)) == "not opened within 1234567.25 seconds"
    assert str(timed_out(86400 * 365.0)) == "not opened within 31536000 seconds"


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
def test_wait_or_raise_returns_none_when_open(kind: Kind) -> None:
    prim = kind.make()
    kind.fire(prim)
    assert kind.wait_or_raise(prim, 0) is None  # type: ignore[func-returns-value]
    assert kind.wait_or_raise(prim, None) is None  # type: ignore[func-returns-value]


def test_public_classes_report_the_package_as_their_module() -> None:
    import latchkit

    for name in latchkit.__all__:
        assert getattr(latchkit, name).__module__ == "latchkit", name


class LoudText(str):
    """A str subclass whose own methods would blow every bound if they were used."""

    def __format__(self, spec: str) -> str:
        return "S" * 1_000_000

    def __len__(self) -> int:
        return 0

    def strip(self, chars: str | None = None) -> str:
        raise RuntimeError("strip must not be called")

    def __getitem__(self, key: object) -> str:
        raise RuntimeError("slicing must not be called")


class Speaks:
    def __init__(self, text: str) -> None:
        self.text = text

    def __str__(self) -> str:
        return self.text


def test_a_str_subclass_from_str_is_read_as_plain_text() -> None:
    assert str(BrokenLatchError(LoudText("short"))) == "aborted: short"
    assert str(BrokenLatchError(Speaks(LoudText("x" * 300)))) == "aborted: " + "x" * 200 + "..."
    assert str(BrokenLatchError(Speaks(LoudText("  ")))) == "aborted: <Speaks>"
