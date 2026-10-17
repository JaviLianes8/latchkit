"""Seeded fuzz: random operations and hostile arguments against an independent model."""

from __future__ import annotations

import asyncio
import math
import random
import time
from decimal import Decimal
from typing import Any

import pytest
from _kinds import KIND_IDS, KINDS, Kind, run_async

from latchkit import AsyncGate, BrokenLatchError, LatchTimeoutError

HOSTILE: list[object] = [
    None, True, False, 1.5, -0.0, math.nan, math.inf, -math.inf, "1", b"1", Decimal(1),
    1j, [1], (), object(), -(10**400), 10**400, 0, -1, 2,
]  # fmt: skip


class Model:
    """What a one-shot primitive must report, written without looking at the library."""

    def __init__(self, count: int | None) -> None:
        self.count = count
        self.state = "open" if count == 0 else "pending"
        self.reason: object = None

    def settle(self, state: str, reason: object = None) -> bool:
        if self.state != "pending":
            return False
        self.state, self.reason = state, reason
        return True


def _apply(kind: Kind, prim: Any, model: Model, rng: random.Random) -> None:
    roll = rng.random()
    latch = model.count is not None
    if roll < 0.2:
        reason = rng.choice([None, "r", ValueError("v"), 0])
        assert prim.abort(reason) is model.settle("broken", reason)
    elif roll < 0.4 and latch:
        k = rng.choice([1, 1, 2, 5, 10**30])
        if model.state == "pending":
            model.count = max(0, model.count - k)  # type: ignore[operator]
            if model.count == 0:
                model.settle("open")
        assert prim.count_down(k) == model.count
    elif roll < 0.5 and latch:
        k = rng.choice([1, 3, 10**30])
        ok = model.state == "pending"
        if ok:
            model.count += k  # type: ignore[operator]
        assert prim.try_count_up(k) is ok
    elif roll < 0.6 and not latch:
        assert kind.fire(prim) is model.settle("open")
    elif roll < 0.75:
        arg = rng.choice(HOSTILE)
        _hostile(kind, prim, arg)
    else:
        _observe(kind, prim, model)


def _blocks(arg: object) -> bool:
    """Whether ``arg`` is a valid timeout that would really wait on a pending primitive."""
    if arg is None:
        return True
    if isinstance(arg, (int, float)) and not isinstance(arg, bool):
        return arg > 0
    return False


def _hostile(kind: Kind, prim: Any, arg: object) -> None:
    if not _blocks(arg):
        try:
            assert kind.wait(prim, arg) in (True, False)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            assert (arg is not None and not isinstance(arg, int)) or isinstance(arg, bool)
        except BrokenLatchError:
            assert prim.is_broken
    if type(arg) is int and arg >= 1:
        return  # a valid step: the model only follows the steps it chose itself
    for name in ("count_down", "try_count_up"):
        if hasattr(prim, name):
            with pytest.raises((TypeError, ValueError)):
                getattr(prim, name)(arg)


def _observe(kind: Kind, prim: Any, model: Model) -> None:
    assert kind.fired(prim) is (model.state == "open")
    assert prim.is_broken is (model.state == "broken")
    assert prim.abort_reason is model.reason
    if model.count is not None:
        assert prim.remaining == model.count
    if model.state == "broken":
        with pytest.raises(BrokenLatchError) as info:
            kind.wait_or_raise(prim, 0)
        assert info.value.reason is model.reason
    elif model.state == "open":
        assert kind.wait(prim, -1) is True
    else:
        with pytest.raises(LatchTimeoutError):
            kind.wait_or_raise(prim, 0)
    assert repr(prim).startswith(f"<{kind.name} ")


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("kind", KINDS, ids=KIND_IDS)
def test_random_operations_match_the_model(kind: Kind, seed: int) -> None:
    rng = random.Random(seed * 1000 + KIND_IDS.index(kind.name))
    is_latch = "Latch" in kind.name
    start = rng.choice([0, 1, 2, 7]) if is_latch else None
    prim = type(kind.make())(start) if is_latch else kind.make()
    model = Model(start)
    for _ in range(60):
        _apply(kind, prim, model, rng)
    _observe(kind, prim, model)


def test_huge_reasons_and_counts_stay_cheap() -> None:
    started = time.perf_counter()
    gate = AsyncGate()
    gate.abort("x" * 50_000_000)
    for _ in range(1000):
        with pytest.raises(BrokenLatchError) as info:
            run_async(gate.wait(0))
        assert len(str(info.value)) == 212
    assert time.perf_counter() - started < 60, "message building is not bounded"


def test_fifty_thousand_parked_coroutines_settle_in_linear_time() -> None:
    async def main(n: int) -> None:
        gate = AsyncGate()
        tasks = [asyncio.create_task(gate.wait()) for _ in range(n)]
        await asyncio.sleep(0)
        assert len(gate._waiters) == n
        gate.open()
        assert all(await asyncio.gather(*tasks))
        assert gate._waiters == {}

    asyncio.run(main(50_000))  # a quadratic wake-up would take minutes here
