# latchkit 1.0.0 certification report

Progress:
- [x] Branch `release/1.0.0` created from `main` (0.2.0, f3a13dd; PyPI has 0.2.0)
- [x] Baseline gates run on 0.2.0
- [x] API review and 1.0.0 API changes (item 1)
- [x] Ground truth: reference implementations run live, fetched documentation (item 7)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e and upgrade from PyPI 0.2.0 (items 8, 13, 14)
- [x] Every interpreter on this PC (item 10)
- [x] Five QA lenses report PASS (item 19)
- [x] Independent reviewer (item 16)
- [x] Gates (item 15)
- [x] PR #3 open and trace guard CLEAN (item 17); merge and publish left to the maintainer

## Scorecard

Independent review round 2 at 773f5cf; the commits after it touch only this report and
the README badge.

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: every 0.2.0 name, signature and default kept; signatures frozen by contract; changes in the CHANGELOG, checked against the real 0.2.0 by lenses a and d and the reviewer |
| 2 | `__all__` exact, no private imports in docs | PASS: 10 names, nothing else public |
| 3 | Docstrings with runnable examples, doctests | PASS: every public class, method and property, at least 150 examples run; every README and GUIDE block runs |
| 4 | Typed end to end | PASS: `mypy --strict src tests` clean, `py.typed` shipped, strict external consumer of every name (lens d, reviewer) |
| 5 | Typed, documented, bounded errors | PASS: `TypeError`/`ValueError` with fixed sentences, 40 characters of a type name, 200 of a reason, never the value |
| 6 | Contract asserts the full promise | PASS: 878 tests (862 run by default, 16 opt-in or needing fetched copies) |
| 7 | Real ground truth | PASS: Java 21 and .NET 9 run live (400 and 800 scenarios), stdlib barriers live, fetched sources for C++20 and Go; re-derived by lens b with its own programs |
| 8 | Real e2e incl. PyPI upgrade | PASS: wheel in fresh venvs, external consumer, in-place upgrade from PyPI 0.2.0 (`LATCHKIT_E2E=1`), sdist install; no CLI by design |
| 9 | Seeded fuzz, no crash, hang or blow-up | PASS: seeded model fuzz, hostile arguments and reasons, 10k to 200k waiters linear (lens c) |
| 10 | Every interpreter on this PC | PASS: 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2, 3.14.2t |
| 11 | README | PASS: `twine check --strict`, absolute links, problem, verified why, install, quick start, guide and changelog links |
| 12 | CHANGELOG dated 1.0.0 | PASS: `## [1.0.0] - 2026-10-17` |
| 13 | pyproject | PASS: 1.0.0 from one source, Production/Stable, 3.10 to 3.14, MIT, Homepage/Source/Issues/Changelog, keywords, no dependencies |
| 14 | sdist and wheel contents | PASS: wheel holds the package, `py.typed`, LICENSE; sdist without fetched copies or notes |
| 15 | Gates exit 0 alone | PASS: fresh clone at 773f5cf: format, lint, `mypy --strict src`, `mypy --strict src tests`, `pytest` 862 passed and 16 skipped, build and `twine check --strict` |
| 16 | Independent reviewer | PASS: round 1 FAIL at 4f96f18, round 2 PASS at 773f5cf |
| 17 | PR, trace guard | PR #3 from `release/1.0.0`, trace guard CLEAN; merge and PyPI publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: author 38; lens a 24 + 15; lens b 40 + 5; lens c 40 + 21 + 10 + 2; blind lens e 134 + 8; reviewer 40 + 13; every survivor closed by a contract or argued equivalent |
| 19 | Five QA lenses | PASS: a (round 3), b (round 2), c (round 4), d (round 2), e (round 2) |

## Independent reviewer (item 16)

Round 1 at 4f96f18 re-ran every item: gates on a fresh clone, live Java and .NET oracles,
fetched sources, the opt-in e2e with the upgrade from 0.2.0, the suite on 3.10.19, 3.13.2,
3.14.2 and 3.14.2t, archive contents, hygiene and the trace guard, plus 40 own mutants
(39 killed). It failed items 5, 6 and 18: the promise that the scopes treat
`CancelledError`, `KeyboardInterrupt` and `SystemExit` as failures was not pinned (R31
survived), an argument whose metaclass gives `__name__` a non-string produced a
`ValueError`, plus a narrow `timeout` annotation, a stale checklist and a typo. All fixed in
818f5f5 and 773f5cf. Round 2 at 773f5cf: every finding confirmed, gates green on a fresh
clone, 13 mutants on the changed code all killed, trace guard CLEAN, all 19 items PASS.

## Baseline on 0.2.0 (before any change)

Fresh clone of `main` (f3a13dd) on Elena's PC, CPython 3.14: `ruff format --check .`,
`ruff check .` and `mypy --strict src tests` exit 0; `pytest` 441 passed in 10.6 s. No
doctests. PyPI has 0.2.0 only (uploaded 2026-10-14); 0.1.0 was never published.

## API review (items 1 to 5)

Kept from 0.2.0 with the same names, signatures and defaults: the six primitives,
`wait(timeout=None)`, `wait_or_raise(timeout=None)`, `abort(reason=None)`, `is_broken`,
`abort_reason`, `count_down(n=1)`, `try_count_up(n=1)`, `remaining`, `is_open`,
`arrival(*, abort_on_error=False)`, `open()`, `opening()`, `set()`, `is_set`,
`SignalScope(on_success, on_error=None)` and the three errors. `tests/test_contract.py`
freezes every public signature, the read-only properties, which methods are coroutines,
`__all__` and the absence of any other public name.

Defects of 0.2.0 found by the review and checked against the real 0.2.0 from PyPI:

- `CountDownLatch(2.5)` was accepted and opened after three signals; `True`, `Decimal`,
  `Fraction` and `2.0` were accepted as counts; a string count failed with the
  interpreter's comparison message.
- `wait("0.01")` and `wait(True)` were accepted (the latter waited one second); an
  integer timeout too large for a float raised `OverflowError`.
- A pickled `BrokenLatchError` came back with the message `aborted: aborted: r`.
- Abort messages echoed the whole `str(reason)`; the timeout message echoed the raw
  argument (`not opened within -3 seconds`).
- The public classes reported private module names; `annotations` was a public name.
- `repr` of a latch with a huge count tried to print every digit.

Changed for 1.0.0, all listed in the CHANGELOG: integer-only counts and steps
(`__index__` accepted, `bool` refused), real-number timeouts (`bool`, strings,
`Decimal`, complex refused with `TypeError`), huge integers as forever or zero, bounded
messages (40 characters of a type name, 200 of a reason), the effective timeout in
`LatchTimeoutError`, pickling, public module names, version from one source. Every public
name carries a docstring example (more than 50 examples, run by `tests/test_docs.py`
together with every README and GUIDE block). `mypy --strict src tests` is clean and
`py.typed` ships; `abort_reason` and `reason` are typed `object` on purpose (any value
may be a reason).

## Behaviour changes against PyPI 0.2.0

The CHANGELOG "Changed (upgrading from 0.2.0)" list is the reference. In short: counts
and steps must be integers, timeouts real numbers (not `bool`); bounded messages; the
timeout message shows the effective timeout; `BrokenLatchError` pickles cleanly; public
module names; the repr of a huge count. Everything 0.2.0-style code does with valid
arguments keeps working: the opt-in end-to-end test runs the same consumer against 0.2.0
from PyPI and again after an in-place upgrade to the 1.0.0 wheel.

## Ground truth (item 7)

latchkit mirrors established primitives. Three kinds of truth, none of them its own output:

- **Reference implementations, run live.** `tests/oracle/LatchOracle.java` drives
  `java.util.concurrent.CountDownLatch` (OpenJDK 21.0.8) and `tests/oracle/dotnet/` drives
  `System.Threading.CountdownEvent` (.NET SDK 9.0.315) through seeded scenarios
  (`scripts/capture_oracles.py`, 2026-10-16): 400 shared scenarios (counts -1 to 7,
  steps, reads, zero and negative waits) through both, and 400 more with
  `TryAddCount`, zero steps and over-large signals through .NET. Their output is
  `tests/fixtures/oracle_runs.json`; `tests/test_oracle.py` replays every scenario on
  `CountDownLatch` and `AsyncCountDownLatch`. With `LATCHKIT_LIVE_ORACLES=1` the suite
  compiles and runs both programs on 300 fresh scenarios each.
- **The Python standard library, live on every interpreter.** `threading.Barrier.abort()`
  and `asyncio.Barrier.abort()` (3.11+) fail parked and later waiters, as latchkit's
  abort does; negative timeouts mean zero; `Condition.wait_for` polls without sleeping
  on a NaN deadline; `Event.wait(inf)` raises `OverflowError` on the Windows builds.
- **Fetched sources for what cannot run here.** `scripts/fetch_sources.py` fetches the
  Java 21 pages for `CountDownLatch`, `CyclicBarrier` and `Phaser`, .NET 9's
  `CountdownEvent.cs`, Go 1.23's `sync/waitgroup.go`, cppreference's `std::latch` pages
  and CPython 3.13.2's `asyncio-sync.rst` and `threading.py` into the git-ignored
  `tests/sources/`; `MANIFEST.json` records URL, date, size, SHA-256 and licence.
  `tests/test_sources.py` locates each fact the GUIDE cites in its copy and skips without
  it. Go is not installed on any machine here and the C++ compiler on this PC predates
  C++20, so those two columns of the GUIDE come from these sources and are labelled so.

What the comparison established:

| Property | Result |
| --- | --- |
| Java, 400 scenarios | identical output on both latches, including counting past zero (Java's repeated `countDown()` at zero is a no-op, latchkit clamps), zero and negative waits, and a negative initial count refused |
| .NET, 800 scenarios | identical wherever .NET accepts the call; .NET throws `InvalidOperationException` exactly where a step exceeds the remaining count or the event is set (latchkit clamps), `ArgumentOutOfRangeException` for zero steps, a negative count and a negative wait (latchkit: `ValueError`, `ValueError`, waits zero); `TryAddCount` equals `try_count_up` |
| Threads | Java and .NET keep four waiters parked through signals 1 and 2 of 3 and release all four on the third, as `tests/test_latch.py` asserts for latchkit |
| Abort | a broken `CyclicBarrier` and a terminated `Phaser` fail or release every later wait at once, the model `abort` follows |

## Author mutation round (item 18)

Each mutant applied alone to a fresh clone of the pushed branch, `pytest -x` with no
bytecode and a 240 second limit per run (a hang counts as killed), baseline green before
and after. Round 1 at d69f8c6 on Elena's PC (CPython 3.14): 38 mutants. The wheel test
failed there for reasons of the machine (not of the mutants: the equivalent control A34
"failed" it too), so the eight mutants it caught and the three survivors were rerun at
6f2ea26 without that test, after contracts for A10 and A30; A31 survived and got a
contract in e46b791. Final: 36 killed, 2 equivalent.

| Id | File | Mutation | Caught by |
| --- | --- | --- | --- |
| A01 | `_check.py` | `bool` accepted as a count | `tests/test_fuzz.py::test_random_operations_match_the_model[CountDownLatch-1]` |
| A02 | `_check.py` | count of -1 accepted | `tests/test_latch.py::test_negative_count_is_rejected` |
| A03 | `_check.py` | step of zero accepted | `tests/test_fuzz.py::test_random_operations_match_the_model[CountDownLatch-0]` |
| A04 | `_check.py` | `bool` timeout accepted | `tests/test_validation.py::test_timeout_must_be_a_real_number_or_none[True-CountDownLatch]` |
| A05 | `_check.py` | huge negative integer waits forever | time limit (hang) |
| A06 | `_check.py` | NaN accepted | `tests/test_promise.py::test_nan_timeout_is_rejected[CountDownLatch]` |
| A07 | `_check.py` | infinity kept as a float instead of `None` | equivalent: both waits then wait forever (the threaded loop sleeps in `TIMEOUT_MAX` chunks, the loop timer never fires) |
| A08 | `_check.py` | negative timeout kept negative | `tests/test_errors.py::test_timeout_message_shows_the_effective_timeout[-3-0-CountDownLatch]` |
| A09 | `_check.py` | type preview one character longer | `tests/test_validation.py::test_the_type_name_in_a_message_is_bounded` |
| A10 | `_check.py` | repr bound off by one | `tests/test_validation.py::test_repr_shows_counts_up_to_64_bits_and_the_size_beyond[CountDownLatch]` (added) |
| A11 | `_errors.py` | reason preview off by one | `tests/test_errors.py::test_message_shows_at_most_200_characters_of_the_reason` |
| A12 | `_errors.py` | pickle drops the reason | `tests/test_errors.py::test_broken_error_pickles_with_its_reason[None]` |
| A13 | `_errors.py` | reason not chained as `__cause__` | `tests/test_docs.py::test_guide_examples_run_in_order` |
| A14 | `_errors.py` | broken read as a timeout | `tests/test_async.py::test_abort_reaches_parked_waiters` |
| A15 | `_errors.py` | timeout message precision | `tests/test_errors.py::test_timeout_message_shows_the_effective_timeout[timeout4-0.00333333-CountDownLatch]` |
| A16 | `_sync.py` | deadline test `<` instead of `<=` | time limit (hang) |
| A17 | `_sync.py` | `notify` instead of `notify_all` | time limit (hang) |
| A18 | `_sync.py` | a second transition overrides the first | `tests/test_docs.py::test_every_public_name_carries_doctests_that_pass` |
| A19 | `_sync.py` | `wait_or_raise` never times out | `tests/test_docs.py::test_every_public_name_carries_doctests_that_pass` |
| A20 | `_sync.py` | no `TIMEOUT_MAX` chunking | `tests/test_promise.py::test_a_blocked_waiter_is_released_by_open[huge-CountDownLatch]` |
| A21 | `_latch.py` | count goes negative | `tests/test_docs.py::test_guide_examples_run_in_order` |
| A22 | `_latch.py` | broken latch reports zero | `tests/test_docs.py::test_module_doctests_pass[latchkit._sync]` |
| A23 | `_latch.py` | count up after open | `tests/test_docs.py::test_guide_examples_run_in_order` |
| A24 | `_latch.py` | `abort_on_error` inverted | time limit (hang) |
| A25 | `_latch.py` | zero count starts pending | `tests/test_docs.py::test_every_public_name_carries_doctests_that_pass` |
| A26 | `_gate.py` | `opening` opens on error | `tests/test_helpers.py::test_opening_aborts_on_error[Gate]` |
| A27 | `_scope.py` | `async with` exit signals nothing | `tests/test_helpers.py::test_scopes_work_with_async_with` |
| A28 | `_async_core.py` | a closed loop breaks signalling | `tests/test_async.py::test_a_waiter_on_a_closed_loop_does_not_break_signalling` |
| A29 | `_async_core.py` | finished waiter stays registered | `tests/test_async.py::test_cancelling_a_waiter_leaves_the_primitive_pending_and_clean` |
| A30 | `_async_core.py` | zero timeout suspends | `tests/test_async.py::test_a_zero_timeout_on_a_pending_primitive_never_suspends` (added) |
| A31 | `_async_core.py` | settling keeps waiters registered | `tests/test_async.py::test_a_waiter_on_a_closed_loop_does_not_break_signalling` (strengthened) |
| A32 | `_async_core.py` | woken waiter reports stale state | `tests/test_async.py::test_waiters_park_and_release_on_open` |
| A33 | `_async_core.py` | loop timer not cancelled | time limit (hang) |
| A34 | `_async_latch.py` | `remaining + 0 * n` | equivalent control |
| A35 | `_async_latch.py` | async latch never reaches zero | `tests/test_async.py::test_cancelling_a_waiter_leaves_the_primitive_pending_and_clean` |
| A36 | `_async_gate.py` | async `open` breaks | `tests/test_async.py::test_waiters_park_and_release_on_open` |
| A37 | `__init__.py` | private module names | `tests/test_docs.py::test_every_public_name_carries_doctests_that_pass` |
| A38 | `_async_latch.py` | async count up unchecked | `tests/test_fuzz.py::test_random_operations_match_the_model[AsyncCountDownLatch-0]` |

## Supported Pythons (item 10)

`requires-python = ">=3.10"`. Wheel and sdist built from a fresh clone, `twine check
--strict` passed; the sdist's suite run against the installed wheel (`-I`, source path
removed) on every interpreter of this PC from 3.10 up, each test limited to 180 s and each
interpreter to 900 s, at 818f5f5: CPython 3.10.19 (861 passed, 17 skipped: no
`asyncio.Barrier`), 3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2 free-threaded (862 passed,
16 skipped each: opt-in e2e, live oracles, fetched copies absent). Lens d ran the same
matrix independently at f08b2cb with `LATCHKIT_E2E=1`. 3.8 and 3.9 are installed but below
`requires-python` (pip refuses both archives on 3.9).

A first matrix run hung on CPython 3.13.2. The stack dump showed `asyncio.run` blocked in
`accept` inside the loopback socket pair every new Windows event loop opens: the suite
created thousands of loops. Tests now reuse one loop per thread (`tests/_kinds.py`), every
test thread is a daemon, every child process of the wheel test is bounded and killed as a
tree on timeout, and `faulthandler_timeout = 120` makes any slow test dump its stacks.
The same run exposed that the wheel test passed the Windows venv launcher's variable to
its children and could build from a tree without sources; both are fixed and pinned.

## QA lenses (item 19)

Five independent reviews, one at a time, each reading the certification rules, running
the code and reporting only to the maintainer. Later rounds confirm the earlier findings
and sweep at most 40 new mutations on the code changed since.

| Lens | Round | Head | Verdict | Findings and outcome |
| --- | --- | --- | --- | --- |
| a. API and docs | 1 | 3d653fc | FAIL | 31 public members without their own example; a CHANGELOG line claiming a change 0.2.0 already had; complex timeouts listed as newly refused; `aborted: ` with an empty reason; exponent form in long timeout messages; status classifier not in the CHANGELOG. Fixed in aa5efb7 |
| a | 2 | aa5efb7 | FAIL | all six confirmed; the examples of 12 public methods never ran (the doctest finder skips methods of classes that report another module); 24 mutants, 2 needing contracts. Fixed in cac0939 (every public docstring run directly, each must show more than an import) |
| a | 3 | cac0939 | PASS | 15 mutants: 10 killed, 4 equivalent, 1 (other whitespace as blank) closed by a contract in 1ef651e and dcdb0c3 |
| b. Correctness and ground truth | 1 | dcdb0c3 | FAIL | own Java, .NET and Python reference programs agree with latchkit everywhere, 0 undocumented differences; the project fixture reproduces byte for byte; 40 mutants on the semantic core, 4 needing contracts (a wait without timeout giving up, an asyncio timeout 100 times early, the double-resolve guard, the timer cancel) and 2 equivalent; the C++ negative-count fact cited from a page that does not state it. Fixed in 816ab20 and b7c2ab4 (constructor page fetched and tested; abort after open documented) |
| b | 2 | b7c2ab4 | PASS | the four survivors and a slow hang now fail within a second |
| c. Adversarial and robustness | 1 | b7c2ab4 | FAIL | 126 to 144 hostile probes per interpreter, 10k to 200k waiters linear, no leak over 40k waits, 150 contention rounds on 3.14t, 28 full suites under load without a flake; a lost wake-up past a closed loop not pinned; a `str` subclass from `__str__` bypassing the message bound; closed-loop waiters undocumented; hangs not failing. Fixed in 28dd7bf (pytest-timeout, 300 s per test) |
| c | 2 | 28dd7bf | FAIL | all four confirmed; 21 mutants, the type name of a blank reason not read as plain text. Fixed in 42b667b |
| c | 3 | 42b667b | FAIL | 10 mutants, 2 needing contracts (a type name that raises). Added in f08b2cb |
| c | 4 | f08b2cb | PASS | both killed |
| d. Packaging and real e2e | 1 | f08b2cb | FAIL | wheel and sdist contents and metadata clean, `twine check --strict`, the sdist suite against the installed wheel with the wheel e2e and the upgrade from PyPI 0.2.0 on 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2 and 3.14.2t, sdist install, a strict typed consumer of every name, every CHANGELOG item against the real 0.2.0; `release.ps1` carried on when the gate failed; the gate used whatever tools came first on PATH; counts typed narrower than accepted. Fixed in 7ea79cd and 8a7a285 |
| d | 2 | 7ea79cd | PASS | the release stops on a failing gate (10 script mutants caught); counts accept `SupportsIndex` for type checkers; 3.13.2 rerun green |
| e. Contract strength (blind) | 1 | 8a7a285 | FAIL | 134 own mutants over every module: 126 killed (5 by the time limit), 3 equivalent (state constant values, a lock-free single read, a deadline compared with `<`), 5 needing contracts: chaining of a `BaseException` reason, a settle while a waiter registers, the asyncio timer deadline, lost count-downs under threads, slotted scopes. Added in 3e6673e |
| e | 2 | 3e6673e | PASS | all five killed, the three equivalents argued |
