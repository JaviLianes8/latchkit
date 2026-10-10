# latchkit

One-shot thread synchronization primitives: a counting latch and a gate, zero-dependency and typed

## Install

```
pip install latchkit
```

## Usage

Wait for a fixed number of workers to finish before moving on:

```python
import threading
from latchkit import CountDownLatch

latch = CountDownLatch(3)

def worker(i: int) -> None:
    # ... do the work ...
    latch.count_down()

for i in range(3):
    threading.Thread(target=worker, args=(i,)).start()

latch.wait()            # blocks until all three have counted down
print("all workers done")
```

`wait` takes a timeout and returns whether the latch opened in time:

```python
if not latch.wait(timeout=5.0):
    raise TimeoutError("workers did not finish in 5 seconds")
```

A `Gate` is a manual switch that, once opened, stays open for every waiter:

```python
from latchkit import Gate

gate = Gate()
# worker threads call gate.wait(); a controller calls gate.open() once.
gate.open()
gate.wait()             # returns at once, now and forever
```

A `OneShotEvent` fires exactly once and tells the caller who won the race,
which makes run-once initialisation and first-wins handoffs trivial:

```python
from latchkit import OneShotEvent

ready = OneShotEvent()
if ready.set():         # True for the first caller only
    initialise_shared_resource()
ready.wait()            # every other thread blocks until the winner is done
```

## Why

The standard library gives you `threading.Event` and `threading.Barrier`, but
neither is a count-down latch. `Barrier` is reusable and cyclic, and every
participant must both arrive and wait at the same rendezvous, so you cannot have
one thread wait while N unrelated threads each signal once. `Event` is a single
boolean with no counting and can be cleared and reused, so a late waiter can miss
the signal. The classic "wait for N things, then proceed, once" primitive, called
`CountDownLatch` in Java and C#, has no counterpart in Python's stdlib.

There is also no maintained standalone package for it on PyPI: the pattern lives
only embedded inside larger projects (the Hazelcast client, OpenStack taskflow),
so people hand-roll a `Condition` plus a counter in every codebase and get the
edge cases (counting past zero, waking all waiters, timeouts) subtly wrong.

`latchkit` is that primitive done once, correctly: `CountDownLatch` for the
count-down, `Gate` for a one-shot manual event that stays open, and
`OneShotEvent` for fire-once, first-caller-wins handoffs. All three are
`Condition`-based, thread-safe, fully typed, and depend on nothing but the
standard library.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
