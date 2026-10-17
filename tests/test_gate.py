"""Behaviour of Gate and OneShotEvent with real threads."""

from __future__ import annotations

import threading

from _kinds import GUARD, parked, until

from latchkit import Gate, OneShotEvent


def test_gate_releases_a_waiter_when_opened() -> None:
    gate = Gate()
    released = threading.Event()

    def waiter() -> None:
        gate.wait()
        released.set()

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    until(lambda: parked(gate) == 1)
    assert not released.is_set()
    gate.open()
    t.join(GUARD)
    assert released.is_set()


def test_gate_wait_returns_true_after_open() -> None:
    gate = Gate()
    gate.open()
    assert gate.is_open is True
    assert gate.wait(timeout=0.0) is True


def test_gate_wait_returns_false_on_timeout() -> None:
    gate = Gate()
    assert gate.is_open is False
    assert gate.wait(timeout=0.05) is False


def test_gate_open_is_idempotent() -> None:
    gate = Gate()
    gate.open()
    gate.open()
    assert gate.is_open is True


def test_one_shot_event_only_the_first_set_wins() -> None:
    event = OneShotEvent()
    assert event.set() is True
    assert event.set() is False
    assert event.is_set is True


def test_one_shot_event_releases_waiters_on_set() -> None:
    event = OneShotEvent()
    released = threading.Event()

    def waiter() -> None:
        event.wait()
        released.set()

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    until(lambda: parked(event) == 1)
    assert not released.is_set()
    event.set()
    t.join(GUARD)
    assert released.is_set()


def test_one_shot_event_wait_returns_false_on_timeout() -> None:
    event = OneShotEvent()
    assert event.wait(timeout=0.05) is False


def test_one_shot_event_names_a_single_winner_under_contention() -> None:
    event = OneShotEvent()
    start = threading.Barrier(8)
    wins: list[bool] = []
    lock = threading.Lock()

    def racer() -> None:
        start.wait()
        won = event.set()
        with lock:
            wins.append(won)

    threads = [threading.Thread(target=racer, daemon=True) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(GUARD)
    assert wins.count(True) == 1
