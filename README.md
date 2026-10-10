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

Python's stdlib has `threading.Event` and `threading.Barrier`, but no count-down
latch. `latchkit` fills that gap with one correct, typed, zero-dependency
implementation.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
