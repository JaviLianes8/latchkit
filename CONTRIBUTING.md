# Contributing

Thanks for taking the time. This project keeps a small, predictable shape.

## Setup

```
pip install -r requirements-dev.txt
```

## Before you open a pull request

- Keep public API in `src/latchkit/__init__.py`; internals live in `_`-prefixed modules.
- Add a test for the behaviour you change. Tests use real threads, real event loops
  and a real wheel install; nothing is mocked. Concurrency tests assert ordering and
  outcomes, never elapsed time, and use timeouts only as deadlock guards.
  Every test is limited to 300 seconds (pytest-timeout, in the dev extra), so a
  deadlock fails the run instead of hanging it.
- Source files stay at or under 200 lines.
- Run `scripts/check.ps1` (format, lint, types, tests) and make sure it passes.
- One logical change per commit, imperative subject line.

Open an issue first if the change is large or shifts the public API.
