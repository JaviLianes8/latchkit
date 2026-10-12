# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

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

## [0.1.0]

- First release.
- `CountDownLatch(count)` with `count_down(n=1)`, `wait(timeout=None)` and a
  `remaining` property: block callers until N signals arrive, then stay open.
- `Gate` with `open()`, `wait(timeout=None)` and `is_open`: a one-shot manual
  event that stays open once triggered.
- `OneShotEvent` with `set()`, `wait(timeout=None)` and `is_set`: fires once and
  returns `True` only to the first caller.
