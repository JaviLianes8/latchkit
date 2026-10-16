# latchkit

One-shot synchronization primitives for threads and asyncio: a count-down
latch, a gate and a fire-once event, each with abort-with-reason, typed errors
and timeouts that behave. Zero dependencies, fully typed, Python 3.10 and up.

## Install

```
pip install latchkit
```

## Quick start

Wait for a fixed number of workers to finish before moving on:

```python
import threading

from latchkit import CountDownLatch

latch = CountDownLatch(3)


def worker(i: int) -> None:
    with latch.arrival():  # counts down when the block exits, even on error
        ...  # do the work


for i in range(3):
    threading.Thread(target=worker, args=(i,)).start()

latch.wait()  # blocks until all three have counted down
```

`wait` takes a timeout and returns whether the latch opened in time;
`wait_or_raise` raises `LatchTimeoutError` (a `TimeoutError`) instead:

```python
if not latch.wait(timeout=5.0):
    print("still waiting")
latch.wait_or_raise(timeout=5.0)
```

When something goes wrong, abort instead of leaving everyone blocked. Every
current and future waiter raises `BrokenLatchError` with your reason:

```python
from latchkit import BrokenLatchError

jobs = CountDownLatch(3)
jobs.abort(RuntimeError("database unreachable"))
try:
    jobs.wait()
except BrokenLatchError as error:
    print(error.reason)  # the RuntimeError, also chained as __cause__
```

A `Gate` is a manual switch that, once opened, stays open for every waiter.
`opening()` guards a run-once initialisation: it opens on success and aborts
on any failure (cancellation included), so waiters never hang on a crashed
initialiser:

```python
from latchkit import Gate

ready = Gate()

with ready.opening():
    ...  # load config, warm caches

ready.wait()  # returns at once, now and forever
```

A `OneShotEvent` fires exactly once and tells the caller who won the race:

```python
from latchkit import OneShotEvent

claimed = OneShotEvent()
if claimed.set():  # True for the first caller only
    print("this thread won")
```

Every primitive has an asyncio twin with the same API. Signalling is
thread-safe, so worker threads can release coroutines:

```python
import asyncio

from latchkit import AsyncCountDownLatch


async def main() -> None:
    latch = AsyncCountDownLatch(4)
    loop = asyncio.get_running_loop()
    for _ in range(4):
        loop.run_in_executor(None, latch.count_down)
    await latch.wait(timeout=10)


asyncio.run(main())
```

The [guide](https://github.com/JaviLianes8/latchkit/blob/main/GUIDE.md) covers
each primitive, abort and errors, argument rules, asyncio and thread bridging,
timeouts, the exact memory-ordering guarantees and how the semantics compare
with Java, .NET, C++ and Go. Changes are listed in the
[changelog](https://github.com/JaviLianes8/latchkit/blob/main/CHANGELOG.md).

## API at a glance

| Thread-based | asyncio | What it is |
| --- | --- | --- |
| `CountDownLatch(n)` | `AsyncCountDownLatch(n)` | Opens after `n` signals: `count_down`, `try_count_up`, `remaining`, `is_open`, `arrival()` |
| `Gate()` | `AsyncGate()` | Opens once on demand: `open`, `is_open`, `opening()` |
| `OneShotEvent()` | `AsyncOneShotEvent()` | Fires once, names the winner: `set`, `is_set` |

All six share `wait(timeout)`, `wait_or_raise(timeout)`, `abort(reason)`,
`is_broken` and `abort_reason`. Errors: `LatchError`, `BrokenLatchError`,
`LatchTimeoutError`. `SignalScope` is the context manager that `arrival()` and
`opening()` return.

## Why

The standard library has `threading.Event`, `threading.Barrier`,
`threading.Condition` and their asyncio cousins, and none of them is a
count-down latch:

- `threading.Barrier` is cyclic and symmetric: every participant must both
  arrive and wait, so one thread cannot wait while N unrelated threads each
  signal once. If you need a rendezvous, use it; latchkit does not duplicate it.
- `threading.Event` and `asyncio.Event` are a single resettable boolean with no
  count, no notion of failure and no winner. A `clear()` can make a late waiter
  miss the signal, and a crashed producer leaves waiters blocked forever.
  asyncio's primitives are documented as not thread-safe, so a worker thread
  cannot set an `asyncio.Event` directly.
- `threading.Condition` is the right building block, which is why people
  hand-roll a counter plus a condition and get the edge cases (counting past
  zero, waking everyone, failure, timeouts) subtly wrong. Even the standard
  waits have sharp edges: on the CPython 3.10 to 3.14 builds we tested (Windows)
  `Event.wait(float("inf"))`
  raises `OverflowError`, and `Condition.wait_for(predicate, float("nan"))`
  spins without ever sleeping. latchkit treats infinity as "forever" and
  refuses NaN.

The "wait for N things, then proceed, once" primitive is `CountDownLatch` in
Java, `CountdownEvent` in .NET and `std::latch` in C++20. latchkit is that
primitive for both threads and asyncio, checked against the Java and .NET
implementations, plus the two one-shot shapes that come up next to it, and an
abort path modelled on `threading.Barrier.abort()` so failures reach waiters
instead of hanging them.

There is no CLI: these are in-process primitives, and a command line could not
share one with anything.

## License

MIT. See [LICENSE](https://github.com/JaviLianes8/latchkit/blob/main/LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
