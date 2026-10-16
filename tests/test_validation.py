"""Argument rules: what every constructor, signal and wait accepts, and what it refuses."""

from __future__ import annotations

import math
from decimal import Decimal
from fractions import Fraction
from typing import Any

import pytest
from _kinds import KIND_IDS, KINDS, Kind

from latchkit import AsyncCountDownLatch, CountDownLatch, Gate

LATCHES = [CountDownLatch, AsyncCountDownLatch]


class Index:
    """An integer-like object, as numpy integers are: accepted through ``__index__``."""

    def __index__(self) -> int:
        return 3


@pytest.mark.parametrize("cls", LATCHES)
@pytest.mark.parametrize("bad", [2.5, 2.0, True, False, "3", None, Decimal(3), Fraction(3)])
def test_count_must_be_an_int(cls: Any, bad: object) -> None:
    with pytest.raises(TypeError, match=r"^count must be an int, not \w+$"):
        cls(bad)


@pytest.mark.parametrize("cls", LATCHES)
def test_count_accepts_index_objects_and_huge_ints(cls: Any) -> None:
    assert cls(Index()).remaining == 3
    huge = cls(10**400)
    assert huge.remaining == 10**400
    assert huge.count_down(10**400) == 0
    assert huge.is_open is True


@pytest.mark.parametrize("cls", LATCHES)
def test_count_must_not_be_negative(cls: Any) -> None:
    with pytest.raises(ValueError, match=r"^count must be zero or greater$"):
        cls(-1)


@pytest.mark.parametrize("cls", LATCHES)
@pytest.mark.parametrize("method", ["count_down", "try_count_up"])
def test_steps_follow_the_count_rules(cls: Any, method: str) -> None:
    latch = cls(5)
    call = getattr(latch, method)
    for bad in (1.0, True, "1", None):
        with pytest.raises(TypeError, match=r"^n must be an int, not \w+$"):
            call(bad)
    for bad in (0, -1, -(10**400)):
        with pytest.raises(ValueError, match=r"^n must be one or greater$"):
            call(bad)
    assert latch.remaining == 5, "a refused step changes nothing"
    call(Index())
    assert latch.remaining in (2, 8)


@pytest.mark.parametrize("cls", LATCHES)
def test_steps_are_checked_even_after_the_latch_settles(cls: Any) -> None:
    latch = cls(0)
    with pytest.raises(ValueError):
        latch.count_down(0)
    with pytest.raises(TypeError):
        latch.try_count_up(1.5)


def test_the_type_name_in_a_message_is_bounded() -> None:
    long_type = type("T" * 500, (), {})
    with pytest.raises(TypeError) as info:
        CountDownLatch(long_type())
    assert str(info.value) == "count must be an int, not " + "T" * 40
    with pytest.raises(TypeError) as info:
        Gate().wait(long_type())
    assert str(info.value) == "timeout must be a real number or None, not " + "T" * 40


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
@pytest.mark.parametrize("bad", [True, False, "1", b"1", Decimal("0.1"), 1j, [1], object()])
def test_timeout_must_be_a_real_number_or_none(kind: Kind, bad: object) -> None:
    prim = kind.make()
    kind.fire(prim)  # even a settled primitive checks its argument
    with pytest.raises(TypeError, match=r"^timeout must be a real number or None, not \w+$"):
        kind.wait(prim, bad)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        kind.wait_or_raise(prim, bad)  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
def test_real_timeouts_of_every_kind_are_accepted(kind: Kind) -> None:
    prim = kind.make()
    for timeout in (0, 0.0, -0.0, Fraction(1, 1000), -(10**400), -math.inf, -1e308):
        assert kind.wait(prim, timeout) is False  # type: ignore[arg-type]
    kind.fire(prim)
    for timeout in (10**400, Fraction(10**400), math.inf, 1e308):
        assert kind.wait(prim, timeout) is True  # type: ignore[arg-type]


@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
def test_nan_is_refused_by_both_waits(kind: Kind) -> None:
    for wait in (kind.wait, kind.wait_or_raise):
        with pytest.raises(ValueError, match=r"^timeout must not be NaN$"):
            wait(kind.make(), math.nan)
        with pytest.raises(ValueError):
            wait(kind.make(), float("-nan"))


def test_async_wait_checks_its_argument_before_needing_a_loop() -> None:
    latch = AsyncCountDownLatch(1)
    for bad, error in (("1", TypeError), (math.nan, ValueError)):
        coroutine = latch.wait(bad)  # type: ignore[arg-type]
        with pytest.raises(error):
            coroutine.send(None)  # no event loop: the check comes first
    assert latch._waiters == {}


@pytest.mark.parametrize("cls", LATCHES)
def test_repr_shows_counts_up_to_64_bits_and_the_size_beyond(cls: Any) -> None:
    name = cls.__name__
    assert repr(cls(2**64 - 1)) == f"<{name} remaining={2**64 - 1}>"
    assert repr(cls(2**64)) == f"<{name} remaining=<65-bit int>>"
    assert repr(cls(10**5000)) == f"<{name} remaining=<16610-bit int>>"
