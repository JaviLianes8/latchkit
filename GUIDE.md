# latchkit guide

This guide explains what each primitive promises, how to pick one, and the
exact guarantees around failure, timeouts, asyncio and memory ordering.

## The shared model

Every primitive is a tiny state machine with three states and one transition:

```
pending --open--> open      (every current and future wait returns True)
pending --abort-> broken    (every current and future wait raises BrokenLatchError)
```

The first transition wins and is permanent. Nothing ever goes back to pending:
there is no `reset` and no `clear`. That is the point of a one-shot primitive:
a waiter that arrives late sees exactly the same outcome as one that was there
all along.

Shared API on all six classes:

| Member | Meaning |
| --- | --- |
| `wait(timeout=None)` | `True` once open, `False` on timeout, raises `BrokenLatchError` if aborted |
| `wait_or_raise(timeout=None)` | `None` once open, raises `LatchTimeoutError` or `BrokenLatchError` |
| `abort(reason=None)` | Break it; `True` if this call broke it, `False` if already settled |
| `is_broken` | Whether it was aborted |
| `abort_reason` | The reason passed to `abort`, else `None` |

## Choosing a primitive

| You need | Use |
| --- | --- |
| Wait until N independent signals arrive, once | `CountDownLatch(n)` |
| Track work that spawns more work, then wait for all of it | `CountDownLatch` with `try_count_up` |
| A switch someone flips once ("ready", "shutdown started") | `Gate` |
| Run-once initialisation that others wait on | `Gate.opening()` |
| A race where exactly one caller must win | `OneShotEvent.set()` |
| All of the above in asyncio, signalled from any thread | the `Async*` twins |
| A reusable rendezvous of N parties | `threading.Barrier` (stdlib) |
| A resettable flag | `threading.Event` (stdlib) |

## CountDownLatch

Modelled on Java's `java.util.concurrent.CountDownLatch`:

- `count_down(n=1)` lowers the count and returns what is left. Counting past
  zero clamps at zero. On an open latch it returns `0`; on an aborted latch it
  changes nothing and returns the frozen count.
- `remaining` is Java's `getCount()`. `is_open` is `remaining == 0`.
- `CountDownLatch(0)` starts open.
- `try_count_up(n=1)` raises the count while pending and returns `False` once
  open or broken, the .NET `CountdownEvent.TryAddCount` contract. Raise the
  count *before* handing out the new work, from a task that still holds an
  unfinished count of its own, and the latch cannot open early.

`arrival(abort_on_error=False)` is a context manager that counts down once
when its block exits, the equivalent of Java's
`try { ... } finally { latch.countDown(); }`. With `abort_on_error=True` a block
that raises aborts the latch with the exception as reason instead, so waiters
learn about the failure immediately rather than proceeding on partial work.
The exception always propagates.

## Gate and OneShotEvent

`Gate.open()` and `OneShotEvent.set()` perform the same transition and both
return `True` only for the call that performed it. They differ in intent:
a gate is a switch, an event names a winner. `Gate.opening()` opens when its
block succeeds and aborts with the exception when it fails.

## Abort and errors

`abort(reason)` follows the "broken barrier" model of Python's
`threading.Barrier.abort()` and Java's `CyclicBarrier`, and the one-shot
release of Java's `Phaser.forceTermination()`:

- Every waiter blocked at that moment wakes and raises `BrokenLatchError`.
- Every later `wait` raises it too, immediately.
- `error.reason` is the reason object. When it is an exception, it is chained
  as `__cause__`, so tracebacks show the original failure.
- Each waiter gets its own `BrokenLatchError` instance. The `reason` object
  itself (and so `__cause__`) is the same object for every waiter.
- The error message is built in the waiting thread after the primitive's lock
  is released, so a `reason.__str__` that reads the primitive, is slow, or
  raises can never deadlock it or hide the abort.
- After an abort, `open`, `set` and `count_down` are silent no-ops. Signallers
  never fail because a coordinator gave up.

Hierarchy:

```
LatchError(Exception)
├── BrokenLatchError          .reason
└── LatchTimeoutError         also a TimeoutError
```

## Timeouts

- Every deadline uses the monotonic clock (`threading.Condition.wait_for` and
  the event loop's clock), so wall-clock jumps never shorten or extend a wait.
- Spurious wakeups are absorbed: a wait returns only on open, abort or the
  deadline.
- `None` waits forever. Negative values behave like zero, as in `threading`.
- Infinity means "forever". Finite values larger than `threading.TIMEOUT_MAX`
  (about 49.7 days on Windows) are honoured exactly; the stdlib would raise
  `OverflowError` for them.
- `NaN` raises `ValueError`; in the stdlib it makes `Condition.wait_for` spin a
  CPU core forever.
- A wait on an already settled primitive never blocks, whatever the timeout.

## asyncio

`AsyncCountDownLatch`, `AsyncGate` and `AsyncOneShotEvent` have the same
members as their threaded twins; only `wait` and `wait_or_raise` are coroutines.

- Signalling (`count_down`, `try_count_up`, `open`, `set`, `abort`) is a plain,
  non-blocking method, safe to call from the event loop or from any other
  thread, for example inside `loop.run_in_executor`. `asyncio.Event` cannot do
  this.
- Each waiter parks on a future of its own running loop and is woken with
  `loop.call_soon_threadsafe`, so one primitive can serve waiters on several
  event loops in different threads.
- Cancelling a waiting task raises `CancelledError` as usual, removes that
  waiter and leaves the primitive untouched. As everywhere in asyncio, a
  cancel delivered after the primitive opened but before the task resumed
  still wins for that task; every other waiter is still released, since each
  waiter has its own future and no wakeup can be stolen. A timed-out waiter is
  removed too; nothing leaks.
- A waiter whose loop was closed is skipped silently when the primitive
  settles. A waiter whose loop was stopped but not closed stays registered
  until the primitive settles.
- The context helpers work with both `with` and `async with`. They treat any
  exception as a failure, including `CancelledError`, `KeyboardInterrupt` and
  `SystemExit`: a cancelled initialiser inside `opening()` aborts the gate, so
  waiters are told instead of hanging. Use a new gate to retry.

## Memory ordering

Java documents `CountDownLatch` with a happens-before rule; latchkit gives the
same guarantee for every primitive:

> Actions in a thread before it calls `count_down`, `open`, `set` or `abort`
> happen-before the actions that follow a return (or a raise) from the
> matching `wait` in another thread.

For the threaded classes, the state change and the wait both run under the
primitive's single `threading.Condition`; releasing and acquiring that lock is
the synchronisation point. For the asyncio classes, the state lives behind one
`threading.Lock`, the waking goes through `call_soon_threadsafe` (itself
synchronised), and the woken waiter re-reads the state under the lock before
returning. These are lock-based guarantees, so they hold on free-threaded
builds as well as with the GIL.

## Why no reset, barrier or CLI

- **No reset.** Re-arming brings back the race one-shot primitives remove: a
  waiter that arrives just after a reset misses the generation it meant to
  observe. For cyclic rendezvous use `threading.Barrier`; for repeated rounds,
  create a new latch per round.
- **No barrier.** `threading.Barrier` is already correct and complete.
- **No CLI.** The primitives live inside one process; a command line could not
  share them with anything.
