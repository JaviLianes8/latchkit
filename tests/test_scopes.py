"""The context helpers treat every exception as a failure, cancellation included."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from latchkit import AsyncCountDownLatch, AsyncGate, CountDownLatch, Gate

GATES = [Gate, AsyncGate]
LATCHES = [CountDownLatch, AsyncCountDownLatch]
ESCAPES = [asyncio.CancelledError("cancelled"), KeyboardInterrupt(), SystemExit(3)]
IDS = ["CancelledError", "KeyboardInterrupt", "SystemExit"]


@pytest.mark.parametrize("error", ESCAPES, ids=IDS)
@pytest.mark.parametrize("cls", GATES)
def test_opening_aborts_on_a_base_exception(cls: Any, error: BaseException) -> None:
    gate = cls()
    with pytest.raises(type(error)), gate.opening():
        raise error
    assert gate.is_broken is True
    assert gate.is_open is False
    assert gate.abort_reason is error


@pytest.mark.parametrize("error", ESCAPES, ids=IDS)
@pytest.mark.parametrize("cls", LATCHES)
def test_arrival_with_abort_on_error_aborts_on_a_base_exception(
    cls: Any, error: BaseException
) -> None:
    latch = cls(1)
    with pytest.raises(type(error)), latch.arrival(abort_on_error=True):
        raise error
    assert latch.is_broken is True
    assert latch.remaining == 1
    assert latch.abort_reason is error


@pytest.mark.parametrize("error", ESCAPES, ids=IDS)
@pytest.mark.parametrize("cls", LATCHES)
def test_plain_arrival_counts_down_on_a_base_exception(cls: Any, error: BaseException) -> None:
    latch = cls(1)
    with pytest.raises(type(error)), latch.arrival():
        raise error
    assert latch.is_open is True


def test_a_cancelled_initialiser_aborts_its_gate_and_tells_the_waiters() -> None:
    async def main() -> tuple[bool, object]:
        gate = AsyncGate()
        started = asyncio.Event()

        async def initialise() -> None:
            async with gate.opening():
                started.set()
                await asyncio.Event().wait()  # never finishes on its own

        task = asyncio.create_task(initialise())
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        try:
            await gate.wait()
        except Exception as error:
            return gate.is_broken, error.__cause__
        return gate.is_broken, None

    broken, cause = asyncio.run(main())
    assert broken is True
    assert isinstance(cause, asyncio.CancelledError)


class NamelessMeta(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        return 1  # type: ignore[return-value]


class Nameless(metaclass=NamelessMeta):
    pass


def test_argument_errors_survive_a_type_without_a_usable_name() -> None:
    with pytest.raises(TypeError, match=r"^count must be an int, not unnamed type$"):
        CountDownLatch(Nameless())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match=r"^timeout must be a real number or None, not unnamed"):
        Gate().wait(Nameless())  # type: ignore[arg-type]
