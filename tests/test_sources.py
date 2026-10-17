"""The facts the guide cites from sources that cannot run here, read from the fetched copies.

``scripts/fetch_sources.py`` fetches them into ``tests/sources/`` (git-ignored) and the
tracked ``MANIFEST.json`` records URL, date, size and SHA-256. Without the copies these
tests skip. Each fact below is a short phrase located in the copy, never copied prose.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

import pytest

SOURCES = Path(__file__).resolve().parent / "sources"
MANIFEST = json.loads((SOURCES / "MANIFEST.json").read_text("utf-8"))


def _text(name: str) -> str:
    path = SOURCES / name
    if not path.is_file():
        pytest.skip(f"{name} not fetched (run scripts/fetch_sources.py)")
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == MANIFEST[name]["sha256"], name
    text = data.decode("utf-8")
    if name.endswith(".html"):
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)


def test_the_manifest_records_every_copy() -> None:
    assert len(MANIFEST) == 10
    for entry in MANIFEST.values():
        assert entry["url"].startswith("https://")
        assert set(entry) == {"url", "fetched", "size", "sha256", "licence"}


@pytest.mark.parametrize(
    ("name", "phrase"),
    [
        # Java: await at zero returns at once, a non-positive timeout does not wait,
        # a negative count is refused, and the happens-before rule latchkit mirrors.
        ("java21-CountDownLatch.html", "If the current count is zero then this method returns"),
        ("java21-CountDownLatch.html", "less than or equal to zero, the method will not wait"),
        ("java21-CountDownLatch.html", "IllegalArgumentException - if count is negative"),
        ("java21-CountDownLatch.html", "prior to calling countDown() happen-before"),
        ("java21-CyclicBarrier.html", "BrokenBarrierException"),
        ("java21-Phaser.html", "forceTermination"),
        # C++20: a step larger than the counter is undefined behaviour.
        ("cppreference-latch-count_down.html", "greater than the value of the internal counter"),
        ("cppreference-latch-count_down.html", "the behavior is undefined"),
        ("cppreference-latch-constructor.html", "undefined if expected is negative"),
        # asyncio documents its primitives as not thread-safe.
        ("cpython3.13-asyncio-sync.rst", "asyncio primitives are not thread-safe"),
        # threading.Barrier.abort puts the barrier into the broken state.
        ("cpython3.13-threading.py.txt", "def abort(self):"),
    ],
)
def test_a_cited_fact_is_in_its_source(name: str, phrase: str) -> None:
    assert phrase in _text(name)


def test_go_waitgroup_panics_below_zero_and_is_reusable() -> None:
    source = _text("go1.23-waitgroup.go")
    assert 'panic("sync: negative WaitGroup counter")' in source
    assert "reused to wait for several independent sets of events" in source


def test_dotnet_refuses_signals_beyond_the_count_and_adds_only_while_unset() -> None:
    source = _text("dotnet9-CountdownEvent.cs")
    assert "CountdownEvent_Decrement_BelowZero" in source
    assert "CountdownEvent_Increment_AlreadyZero" in source
    assert "public bool TryAddCount(int signalCount)" in source
