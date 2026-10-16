"""Ground truth: the latch semantics of Java 21, .NET 9 and the Python standard library.

``tests/fixtures/oracle_runs.json`` is the output of ``tests/oracle/`` programs run on
java.util.concurrent.CountDownLatch and System.Threading.CountdownEvent (see
``scripts/capture_oracles.py``). Every scenario is replayed on both latchkit latches.
With ``LATCHKIT_LIVE_ORACLES=1`` and the toolchains on PATH, fresh scenarios also run live.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

import pytest
from _oracles import replay, run_dotnet, run_java, scenarios

from latchkit import AsyncCountDownLatch, CountDownLatch

FIXTURE = json.loads(
    (Path(__file__).resolve().parent / "fixtures" / "oracle_runs.json").read_text("utf-8")
)


def _sync_wait(latch: Any, timeout: float) -> bool:
    return bool(latch.wait(timeout))


def _async_wait(latch: Any, timeout: float) -> bool:
    return bool(asyncio.run(latch.wait(timeout)))


LATCHES = [(CountDownLatch, _sync_wait), (AsyncCountDownLatch, _async_wait)]
IDS = ["CountDownLatch", "AsyncCountDownLatch"]


@pytest.mark.parametrize(("make", "wait"), LATCHES, ids=IDS)
def test_every_shared_scenario_matches_java_exactly(make: Any, wait: Any) -> None:
    assert len(FIXTURE["shared"]) == 400
    for row in FIXTURE["shared"]:
        assert replay(row["ops"], make, wait, refuse=False) == row["java"], row["ops"]


@pytest.mark.parametrize(("make", "wait"), LATCHES, ids=IDS)
def test_every_scenario_matches_dotnet_where_dotnet_accepts_the_call(make: Any, wait: Any) -> None:
    rows = FIXTURE["shared"] + FIXTURE["dotnet_only"]
    assert len(rows) == 800
    for row in rows:
        assert replay(row["ops"], make, wait, refuse=True) == row["dotnet"], row["ops"]


def test_the_fixture_exercises_every_difference_and_agreement() -> None:
    java = " ".join(row["java"] for row in FIXTURE["shared"])
    dotnet = " ".join(row["dotnet"] for row in FIXTURE["shared"] + FIXTURE["dotnet_only"])
    for token in ("E:InvalidOperationException", "E:ArgumentOutOfRangeException", " T ", " F "):
        assert token in dotnet
    assert "E:IllegalArgumentException" in java
    ops = " ".join(row["ops"] for row in FIXTURE["dotnet_only"])
    assert " u0" in ops and " d0" in ops and " u3" in ops


def test_the_recorded_thread_probes_agree_with_latchkit_semantics() -> None:
    # Java and .NET: 4 waiters stay parked after signals 1 and 2 of 3, all 4 return after 3.
    assert FIXTURE["probes"]["java"][0] == "parked 4 4 4"
    assert FIXTURE["probes"]["dotnet"] == ["parked 4 4 4"]
    # A broken CyclicBarrier stays broken: a later await raises at once.
    assert FIXTURE["probes"]["java"][1] == "barrier interrupted true broken"
    # A terminated Phaser releases its waiter and every later await or arrive.
    assert FIXTURE["probes"]["java"][2] == "phaser true true true true"


LIVE = os.environ.get("LATCHKIT_LIVE_ORACLES") == "1"


@pytest.mark.skipif(not (LIVE and shutil.which("javac")), reason="live Java oracle not requested")
def test_live_java_agrees_on_fresh_scenarios() -> None:
    fresh = scenarios(7, 300, count_up=False)
    lines, _ = run_java(fresh)
    for ops, expected in zip(fresh, lines, strict=False):
        assert replay(ops, CountDownLatch, _sync_wait, refuse=False) == expected, ops
    assert lines[300:] == FIXTURE["probes"]["java"]


@pytest.mark.skipif(not (LIVE and shutil.which("dotnet")), reason="live .NET oracle not requested")
def test_live_dotnet_agrees_on_fresh_scenarios() -> None:
    fresh = scenarios(8, 300, count_up=True)
    lines, _ = run_dotnet(fresh)
    for ops, expected in zip(fresh, lines, strict=False):
        assert replay(ops, CountDownLatch, _sync_wait, refuse=True) == expected, ops
    assert lines[300:] == FIXTURE["probes"]["dotnet"]
