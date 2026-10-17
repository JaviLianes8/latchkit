# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-16

The API is now stable: every public name, signature, default and error type
below is kept for the 1.x series. Everything written against 0.2.0 keeps
working except the stricter argument checks listed under "Changed".

Stable surface: `CountDownLatch`, `Gate`, `OneShotEvent` and their asyncio
twins `AsyncCountDownLatch`, `AsyncGate`, `AsyncOneShotEvent`, with `wait`,
`wait_or_raise`, `abort`, `is_broken`, `abort_reason`, `count_down`,
`try_count_up`, `remaining`, `is_open`, `arrival`, `open`, `opening`, `set` and
`is_set`; `SignalScope`; the errors `LatchError`, `BrokenLatchError` and
`LatchTimeoutError`.

### Changed (upgrading from 0.2.0)

- `count` and `n` must be integers (`int` or an object with `__index__`). A
  `float` such as `2.5` or `2.0`, a `bool`, a string, a `Decimal` or a
  `Fraction`, all accepted or failing obscurely before, now raise `TypeError`.
  In 0.2.0 `CountDownLatch(2.5)` opened after three signals.
- `timeout` must be `None` or a real number other than `bool`. A string such
  as `"5"`, `True` (waited one second) and a `Decimal`, all accepted in 0.2.0,
  now raise `TypeError` with a short message, even on a settled primitive. An integer too large for a
  float now means "forever" (or zero when negative) instead of raising
  `OverflowError`.
- `BrokenLatchError` messages show at most 200 characters of the reason, and
  the type name in angle brackets when `str(reason)` is blank (a bare
  `CancelledError` from a cancelled `opening()` block, say). Error messages
  about wrong arguments never echo the value.
- The `LatchTimeoutError` message shows the effective timeout (negative values
  read as 0) rather than the argument as given.
- `BrokenLatchError` now pickles cleanly; in 0.2.0 the copy's message read
  `aborted: aborted: ...`.
- The public classes report `latchkit` as their module, and the package no
  longer exposes the stray name `annotations`.
- `repr` of a latch whose count is beyond 64 bits shows the bit size rather
  than every digit.

### Added

- Docstring examples on every public class, method and property, run as
  doctests.
- Ground-truth tests: 400 seeded scenarios recorded from Java 21's
  `CountDownLatch` and 800 from .NET 9's `CountdownEvent`, replayed on both
  latches, plus live checks against `threading.Barrier` and `asyncio.Barrier`.
- `GUIDE.md` sections on argument rules and on how the semantics compare with
  Java, .NET, C++20 and Go.
- Python 3.14 in the classifiers; the development status is now
  Production/Stable.

## [0.2.0] - 2026-10-14

### Added

- `abort(reason=None)` on every primitive: current and future waiters raise
  `BrokenLatchError`, which carries `reason` and chains it as `__cause__` when
  it is an exception. The first transition (open or abort) wins for good.
  New read-only `is_broken` and `abort_reason`.
- Typed errors: `LatchError`, `BrokenLatchError` and `LatchTimeoutError`
  (also a `TimeoutError`).
- `wait_or_raise(timeout=None)` on every primitive.
- asyncio counterparts `AsyncCountDownLatch`, `AsyncGate` and
  `AsyncOneShotEvent` with the same API. Signalling is thread-safe and waiters
  on several event loops are supported.
- `CountDownLatch.try_count_up(n=1)` for work that spawns more work, and
  `CountDownLatch.is_open`.
- Context helpers `CountDownLatch.arrival(abort_on_error=False)` and
  `Gate.opening()`, usable with `with` and `async with`; their return type is
  the exported `SignalScope`.
- Readable `repr` on every primitive.
- `GUIDE.md` with semantics, timeouts, asyncio and happens-before guarantees.

### Changed

- `Gate.open()` now returns `True` if the call opened the gate (previously
  `None`).
- Timeouts are normalized: infinity waits forever, finite values above
  `threading.TIMEOUT_MAX` are honoured instead of raising `OverflowError`, and
  `NaN` raises `ValueError` instead of spinning.
- Abort reasons are formatted outside the primitive's lock, so a reason whose
  `__str__` reads the primitive or raises cannot deadlock or mask the abort.

## [0.1.0] - 2026-10-11 (never published to PyPI)

- First release.
- `CountDownLatch(count)` with `count_down(n=1)`, `wait(timeout=None)` and a
  `remaining` property: block callers until N signals arrive, then stay open.
- `Gate` with `open()`, `wait(timeout=None)` and `is_open`: a one-shot manual
  event that stays open once triggered.
- `OneShotEvent` with `set()`, `wait(timeout=None)` and `is_set`: fires once and
  returns `True` only to the first caller.
