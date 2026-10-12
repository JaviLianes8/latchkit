# Improvements round: latchkit

`latchkit` 0.1.0 ships three correct but minimal primitives: `CountDownLatch`,
`Gate` and `OneShotEvent`. This round turns them into a complete, documented
toolkit for one-shot synchronization in both threaded and asyncio code, while
staying typed, zero-dependency and small.

Everything is additive. Every 0.1.0 signature keeps working. Behaviour changes
only where 0.1.0 failed: a timeout above `threading.TIMEOUT_MAX` used to raise
`OverflowError` and is now honoured, and a `NaN` timeout used to spin forever
and now raises `ValueError`. The one widened return type is `Gate.open()`,
which now returns `bool` (the winner flag) instead of `None`; code that
ignored the result is unaffected.

## Ground truth

The semantics follow the well-known primitives they are modelled on:

- Java `java.util.concurrent.CountDownLatch`: the count only moves down, the
  latch never resets, `await` returns at once when the count is zero, and
  "actions in a thread prior to calling `countDown()` happen-before actions
  following a successful return from a corresponding `await()` in another
  thread". `getCount()` maps to `remaining`.
- Java `CyclicBarrier` and Python `threading.Barrier`: a broken barrier raises
  `BrokenBarrierException` / `BrokenBarrierError` in every current and future
  waiter. `abort()` here borrows exactly that "broken" model.
- Java `Phaser.forceTermination()`: termination releases waiters without the
  normal arrival condition. Our abort is the one-shot analogue.
- .NET `CountdownEvent.TryAddCount`: the count may be raised while the event is
  unset, and the call fails once it has reached zero. Go's `sync.WaitGroup.Add`
  is the same idea.
- Python `threading.Event`, `threading.Condition`, `asyncio.Event`: the stdlib
  building blocks, which we do not duplicate (see "What we deliberately do not
  add").

## Ranked improvements

### 1. Abort with a reason, propagated to every waiter (highest value)
Today a latch whose worker crashes leaves every waiter blocked until its
timeout, or forever. `abort(reason=None)` breaks a primitive: every current and
future waiter raises `BrokenLatchError`, which carries `reason` and, when the
reason is an exception, chains it as `__cause__`. First transition wins: abort
after open is a no-op returning `False`, and open or `count_down` after abort
are no-ops too. Read-only `is_broken` and `abort_reason` complete the picture.

### 2. Typed error hierarchy (high value, prerequisite for 1 and 4)
`LatchError` base, `BrokenLatchError(LatchError)` and
`LatchTimeoutError(LatchError, TimeoutError)`. Callers can catch the library as
a whole or one failure mode, and existing `except TimeoutError` code keeps
working for the raising wait.

### 3. asyncio counterparts with the same API (high value)
`AsyncCountDownLatch`, `AsyncGate` and `AsyncOneShotEvent` mirror the
synchronous classes method for method; only `wait` and `wait_or_raise` are
coroutines. Unlike `asyncio.Event`, signalling is thread-safe: worker threads
(for example inside `run_in_executor`) may call `count_down`, `open`, `set` or
`abort`, and waiters on any event loop are woken through
`call_soon_threadsafe`. That bridges threads into asyncio, which the stdlib
does not offer for these shapes.

### 4. `wait_or_raise(timeout)` (medium value)
Most callers treat a timeout as a failure. `wait_or_raise` returns `None` when
open and raises `LatchTimeoutError` otherwise, removing the
`if not latch.wait(t): raise ...` boilerplate.

### 5. Context-manager helpers (medium value)
`CountDownLatch.arrival(abort_on_error=False)` counts down once when the block
exits, the Python form of Java's `try { ... } finally { latch.countDown(); }`.
With `abort_on_error=True` a failing block aborts the latch with the exception
as reason, so waiters fail fast instead of proceeding on partial work.
`Gate.opening()` opens on success and aborts on error, which is exactly the
run-once initialisation guard. Both work with `with` and `async with`.

### 6. `try_count_up(n=1)` (medium value)
Dynamic work tracking: a task that spawns sub-tasks raises the count before
handing them out. It returns `False` once the latch has opened or broken, so a
latch can never re-open (the .NET `TryAddCount` contract).

### 7. Robust, documented timeouts (medium value)
All waits use the monotonic clock (`threading.Condition.wait_for` and the event
loop clock are monotonic). Timeouts are normalized: negative behaves like zero
(as in `threading`), infinity means "forever", finite values above
`threading.TIMEOUT_MAX` are honoured instead of raising `OverflowError`, and
`NaN` raises `ValueError`
(the stdlib would spin a CPU core forever in `Condition.wait_for` on `NaN`).

### 8. Documented happens-before guarantees (medium value)
State changes and waits go through one lock per primitive, so everything a
thread did before `count_down`, `open`, `set` or `abort` is visible to a waiter
after `wait` returns or raises. Documented in docstrings and the guide,
including the asyncio path and free-threaded builds.

### 9. `is_open` on the latch and readable `repr` (low cost)
`CountDownLatch.is_open` matches `Gate.is_open`, and every primitive has a
`repr` such as `<CountDownLatch remaining=2>` or `<Gate broken>` for logs and
debuggers.

### 10. GUIDE.md and full docstrings (high value for adoption)
A guide that explains when to use each primitive versus the stdlib, abort and
error handling, asyncio and thread bridging, timeouts and memory ordering.

## What we deliberately do not add

- **A resettable or re-armable latch.** Re-arming reintroduces the race that a
  one-shot primitive exists to remove: a waiter that arrives just after a reset
  can miss the generation it meant to observe. Cyclic rendezvous is already
  covered by `threading.Barrier` (and Java's `CyclicBarrier` / `Phaser`); for
  repeated rounds, create a new latch per round, which is cheap and explicit.
- **A barrier.** `threading.Barrier` exists and is correct; duplicating it would
  add surface without value.
- **A CLI.** These are in-process primitives. A command line cannot share a
  latch with anything: each process would get its own. A cross-process latch
  needs files, sockets or shared memory and is a different library. The end to
  end test therefore drives the installed wheel as an external Python consumer.
