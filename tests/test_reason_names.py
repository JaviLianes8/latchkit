"""A blank reason shows its type name: what happens when reading that name fails."""

from __future__ import annotations

import pytest

from latchkit import BrokenLatchError, Gate


class FailingMeta(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        raise RuntimeError("no name")


class InterruptingMeta(type):
    @property
    def __name__(cls) -> str:  # type: ignore[override]
        raise KeyboardInterrupt


class FailingName(metaclass=FailingMeta):
    def __str__(self) -> str:
        return ""


class InterruptingName(metaclass=InterruptingMeta):
    def __str__(self) -> str:
        return ""


def test_a_type_name_that_raises_still_gives_the_broken_error() -> None:
    gate = Gate()
    gate.abort(FailingName())
    with pytest.raises(BrokenLatchError, match=r"^aborted: <unnamed type>$"):
        gate.wait(0)


def test_a_base_exception_from_the_type_name_propagates() -> None:
    with pytest.raises(KeyboardInterrupt):
        BrokenLatchError(InterruptingName())
