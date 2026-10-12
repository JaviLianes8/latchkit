"""Many-thread stress: no lost wakeups, no premature release, consistent aborts.

Assertions are about ordering and outcomes, never about elapsed time. Timeouts
appear only as deadlock guards, generous enough that load cannot trip them.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

import pytest

from latchkit import BrokenLatchError, CountDownLatch, Gate, OneShotEvent

GUARD = 60.0
ROUNDS = 40
SIGNALERS = 16
WAITERS = 16
ROUNDS_PARAM = pytest.mark.parametrize("round_", range(ROUNDS))


def run_all(targets: Sequence[Callable[[], object]]) -> None:
    """Start every target behind one barrier, then join them under a guard."""
    start = threading.Barrier(len(targets))

    def gated(target: Callable[[], object]) -> Callable[[], None]:
        def run() -> None:
            start.wait(GUARD)
            target()

        return run

    threads = [threading.Thread(target=gated(t)) for t in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(GUARD)
        assert not thread.is_alive(), "deadlock guard tripped"


@ROUNDS_PARAM
def test_latch_releases_every_waiter_only_after_every_signal(round_: int) -> None:
    latch = CountDownLatch(SIGNALERS)
    signals: list[int] = []
    seen: list[int] = []

    def signal() -> None:
        signals.append(1)  # happens-before the waiter's return
        latch.count_down()

    def wait() -> None:
        assert latch.wait(GUARD) is True
        seen.append(len(signals))

    run_all([signal] * SIGNALERS + [wait] * WAITERS)
    assert seen == [SIGNALERS] * WAITERS
    assert latch.remaining == 0


@ROUNDS_PARAM
def test_short_timeouts_never_report_a_premature_open(round_: int) -> None:
    latch = CountDownLatch(SIGNALERS)
    signals: list[int] = []
    outcomes: list[tuple[bool, int]] = []

    def signal() -> None:
        signals.append(1)
        latch.count_down()

    def poll() -> None:
        opened = latch.wait(0.0005)
        outcomes.append((opened, len(signals)))

    run_all([signal] * SIGNALERS + [poll] * WAITERS)
    assert all(count == SIGNALERS for opened, count in outcomes if opened)
    assert latch.wait(0) is True


@ROUNDS_PARAM
def test_open_racing_abort_gives_every_waiter_the_same_outcome(round_: int) -> None:
    latch = CountDownLatch(SIGNALERS)
    outcomes: list[str] = []
    abort_won: list[bool] = []

    def wait() -> None:
        try:
            outcomes.append("open" if latch.wait(GUARD) else "timeout")
        except BrokenLatchError as error:
            assert error.reason == "race"
            outcomes.append("broken")

    run_all(
        [latch.count_down] * SIGNALERS
        + [lambda: abort_won.append(latch.abort("race"))]
        + [wait] * WAITERS
    )
    expected = "broken" if abort_won == [True] else "open"
    assert outcomes == [expected] * WAITERS
    assert latch.is_broken is (expected == "broken")
    assert latch.is_open is (expected == "open")


@ROUNDS_PARAM
def test_gate_releases_every_waiter(round_: int) -> None:
    gate = Gate()
    opens: list[bool] = []
    results: list[bool] = []
    run_all(
        [lambda: opens.append(gate.open())] * 4
        + [lambda: results.append(gate.wait(GUARD))] * WAITERS
    )
    assert opens.count(True) == 1
    assert results == [True] * WAITERS


@ROUNDS_PARAM
def test_exactly_one_transition_wins_among_set_and_abort(round_: int) -> None:
    event = OneShotEvent()
    wins: list[bool] = []
    run_all([lambda: wins.append(event.set())] * 8 + [lambda: wins.append(event.abort("race"))] * 8)
    assert wins.count(True) == 1
    assert event.is_set is not event.is_broken


@ROUNDS_PARAM
def test_count_up_racing_count_down_never_opens_with_work_in_flight(round_: int) -> None:
    latch = CountDownLatch(1)
    started: list[int] = []
    finished: list[int] = []
    snapshot: list[tuple[int, int]] = []

    def spawn() -> None:
        if latch.try_count_up():
            started.append(1)
            finished.append(1)
            latch.count_down()

    def wait() -> None:
        assert latch.wait(GUARD) is True
        snapshot.append((len(started), len(finished)))

    run_all([spawn] * SIGNALERS + [latch.count_down] + [wait] * 4)
    assert len(snapshot) == 4
    assert all(s == f for s, f in snapshot)
    assert latch.try_count_up() is False
