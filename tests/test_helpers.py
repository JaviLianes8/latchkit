"""try_count_up, the context-manager helpers and the latch-only accessors."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from latchkit import (
    AsyncCountDownLatch,
    AsyncGate,
    BrokenLatchError,
    CountDownLatch,
    Gate,
    SignalScope,
)

LATCHES = [CountDownLatch, AsyncCountDownLatch]
GATES = [Gate, AsyncGate]


@pytest.mark.parametrize("cls", LATCHES)
def test_try_count_up_raises_the_count_while_pending(cls: Any) -> None:
    latch = cls(1)
    assert latch.try_count_up() is True
    assert latch.try_count_up(3) is True
    assert latch.remaining == 5
    assert latch.count_down(4) == 1
    assert latch.is_open is False
    assert latch.count_down() == 0
    assert latch.is_open is True


@pytest.mark.parametrize("cls", LATCHES)
def test_try_count_up_never_reopens(cls: Any) -> None:
    opened = cls(0)
    assert opened.try_count_up() is False
    assert opened.remaining == 0
    broken = cls(2)
    broken.abort()
    assert broken.try_count_up() is False
    assert broken.remaining == 2


@pytest.mark.parametrize("cls", LATCHES)
def test_try_count_up_rejects_non_positive_steps(cls: Any) -> None:
    with pytest.raises(ValueError):
        cls(1).try_count_up(0)


@pytest.mark.parametrize("cls", LATCHES)
def test_count_down_on_a_broken_latch_returns_the_frozen_count(cls: Any) -> None:
    latch = cls(3)
    latch.count_down()
    latch.abort()
    assert latch.count_down() == 2
    assert latch.remaining == 2
    assert latch.is_open is False


@pytest.mark.parametrize("cls", LATCHES)
def test_repr_shows_the_remaining_count(cls: Any) -> None:
    assert repr(cls(2)) == f"<{cls.__name__} remaining=2>"
    assert repr(cls(0)) == f"<{cls.__name__} open>"


@pytest.mark.parametrize("cls", LATCHES)
def test_arrival_counts_down_on_success_and_on_error(cls: Any) -> None:
    latch = cls(2)
    with latch.arrival():
        pass
    assert latch.remaining == 1
    with pytest.raises(KeyError), latch.arrival():
        raise KeyError("boom")
    assert latch.is_open is True


@pytest.mark.parametrize("cls", LATCHES)
def test_arrival_can_abort_on_error(cls: Any) -> None:
    latch = cls(2)
    with pytest.raises(KeyError), latch.arrival(abort_on_error=True):
        raise KeyError("boom")
    assert latch.is_broken is True
    assert isinstance(latch.abort_reason, KeyError)
    assert latch.remaining == 2


@pytest.mark.parametrize("cls", LATCHES)
def test_arrival_with_abort_on_error_still_counts_down_on_success(cls: Any) -> None:
    latch = cls(1)
    with latch.arrival(abort_on_error=True):
        pass
    assert latch.is_open is True


@pytest.mark.parametrize("cls", GATES)
def test_opening_opens_on_success(cls: Any) -> None:
    gate = cls()
    with gate.opening():
        assert gate.is_open is False
    assert gate.is_open is True


@pytest.mark.parametrize("cls", GATES)
def test_opening_aborts_on_error(cls: Any) -> None:
    gate = cls()
    with pytest.raises(OSError), gate.opening():
        raise OSError("init failed")
    assert gate.is_broken is True
    assert isinstance(gate.abort_reason, OSError)


def test_scopes_work_with_async_with() -> None:
    async def main() -> None:
        latch = AsyncCountDownLatch(1)
        gate = AsyncGate()
        async with latch.arrival():
            pass
        async with gate.opening():
            pass
        assert await latch.wait(0) is True
        assert await gate.wait(0) is True
        failing = AsyncGate()
        with pytest.raises(ValueError):
            async with failing.opening():
                raise ValueError("bad")
        with pytest.raises(BrokenLatchError):
            await failing.wait()

    asyncio.run(main())


def test_signal_scope_is_the_public_return_type() -> None:
    assert isinstance(CountDownLatch(1).arrival(), SignalScope)
    assert isinstance(Gate().opening(), SignalScope)
    scope = SignalScope(lambda: None)
    with scope as entered:
        assert entered is None


def test_gate_open_returns_the_winner_flag() -> None:
    gate = Gate()
    assert gate.open() is True
    assert gate.open() is False
