"""The complete one-shot promise, asserted identically for all six primitives.

Pending blocks, the first open wins and is permanent, late waiters pass, an
abort is permanent and reaches every waiter with its reason, and timeouts obey
one set of rules. Nothing is mocked.
"""

from __future__ import annotations

import math
import threading
from typing import Any

import pytest
from _kinds import GUARD, KIND_IDS, KINDS, Kind, parked, until

from latchkit import BrokenLatchError, LatchError, LatchTimeoutError

pytestmark = pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)


def test_a_fresh_primitive_is_pending(kind: Kind) -> None:
    prim = kind.make()
    assert kind.fired(prim) is False
    assert prim.is_broken is False
    assert prim.abort_reason is None
    assert kind.wait(prim, 0) is False
    assert kind.wait(prim, 0.01) is False


def test_the_first_open_wins_and_is_permanent(kind: Kind) -> None:
    prim = kind.make()
    assert kind.fire(prim) is True
    assert kind.fire(prim) is False
    assert kind.fired(prim) is True
    for timeout in (None, 0, 0.01, -5.0, math.inf, 1e300):
        assert kind.wait(prim, timeout) is True
    kind.wait_or_raise(prim, 0)


def test_abort_breaks_every_wait_with_its_reason(kind: Kind) -> None:
    prim = kind.make()
    cause = RuntimeError("worker crashed")
    assert prim.abort(cause) is True
    assert prim.is_broken is True
    assert prim.abort_reason is cause
    seen: list[BaseException] = []
    for _ in range(3):
        with pytest.raises(BrokenLatchError) as info:
            kind.wait(prim, None)
        assert info.value.reason is cause
        assert info.value.__cause__ is cause
        seen.append(info.value)
    assert len({id(error) for error in seen}) == 3, "each waiter gets a fresh error"


def test_abort_is_permanent_and_blocks_opening(kind: Kind) -> None:
    prim = kind.make()
    assert prim.abort("first") is True
    assert prim.abort("second") is False
    assert kind.fire(prim) is False
    assert kind.fired(prim) is False
    assert prim.abort_reason == "first"
    with pytest.raises(BrokenLatchError, match="aborted: first"):
        kind.wait_or_raise(prim, 0)


def test_abort_after_open_changes_nothing(kind: Kind) -> None:
    prim = kind.make()
    kind.fire(prim)
    assert prim.abort("too late") is False
    assert prim.is_broken is False
    assert prim.abort_reason is None
    assert kind.wait(prim, 0) is True


def test_abort_without_a_reason(kind: Kind) -> None:
    prim = kind.make()
    prim.abort()
    with pytest.raises(BrokenLatchError, match=r"^aborted$") as info:
        kind.wait(prim, 0)
    assert info.value.reason is None
    assert info.value.__cause__ is None


def test_wait_or_raise_times_out_with_a_typed_error(kind: Kind) -> None:
    prim = kind.make()
    with pytest.raises(LatchTimeoutError) as info:
        kind.wait_or_raise(prim, 0.01)
    assert isinstance(info.value, TimeoutError)
    assert isinstance(info.value, LatchError)


def test_nan_timeout_is_rejected(kind: Kind) -> None:
    with pytest.raises(ValueError):
        kind.wait(kind.make(), math.nan)


def test_negative_timeout_behaves_like_zero(kind: Kind) -> None:
    assert kind.wait(kind.make(), -1.0) is False


@pytest.mark.parametrize("timeout", [None, math.inf, 1e9], ids=["none", "inf", "huge"])
def test_a_blocked_waiter_is_released_by_open(kind: Kind, timeout: float | None) -> None:
    prim = kind.make()
    results: list[bool] = []
    thread = threading.Thread(target=lambda: results.append(kind.wait(prim, timeout)))
    thread.start()
    until(lambda: parked(prim) == 1)  # the waiter is really blocked
    kind.fire(prim)
    thread.join(GUARD)
    assert not thread.is_alive()
    assert results == [True]
    assert parked(prim) == 0


def test_a_blocked_waiter_is_released_by_abort(kind: Kind) -> None:
    prim = kind.make()
    errors: list[BaseException] = []

    def waiter() -> None:
        try:
            kind.wait(prim, None)
        except BrokenLatchError as error:
            errors.append(error)

    thread = threading.Thread(target=waiter)
    thread.start()
    until(lambda: parked(prim) == 1)
    prim.abort("stop")
    thread.join(GUARD)
    assert not thread.is_alive()
    assert [e.reason for e in errors] == ["stop"]  # type: ignore[attr-defined]


def test_a_reason_that_reads_the_primitive_does_not_deadlock(kind: Kind) -> None:
    prim = kind.make()

    class Reason:
        def __str__(self) -> str:
            return f"seen {prim!r}"

    prim.abort(Reason())
    errors: list[BaseException] = []

    def waiter() -> None:
        try:
            kind.wait(prim, 0)
        except BrokenLatchError as error:
            errors.append(error)

    thread = threading.Thread(target=waiter)
    thread.start()
    thread.join(GUARD)
    assert not thread.is_alive(), "waiting deadlocked on the reason's __str__"
    assert str(errors[0]) == f"aborted: seen <{kind.name} broken>"


def test_a_reason_with_a_failing_str_still_raises_broken(kind: Kind) -> None:
    class Reason:
        def __str__(self) -> str:
            raise RuntimeError("bad str")

    prim = kind.make()
    reason = Reason()
    prim.abort(reason)
    with pytest.raises(BrokenLatchError, match=r"^aborted: <Reason>$") as info:
        kind.wait(prim, 0)
    assert info.value.reason is reason


def test_repr_names_the_state(kind: Kind) -> None:
    prim: Any = kind.make()
    assert repr(prim).startswith(f"<{kind.name} ")
    kind.fire(prim)
    assert repr(prim) == f"<{kind.name} open>"
    broken = kind.make()
    broken.abort()
    assert repr(broken) == f"<{kind.name} broken>"
