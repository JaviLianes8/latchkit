# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- First release.
- `CountDownLatch(count)` with `count_down(n=1)`, `wait(timeout=None)` and a
  `remaining` property: block callers until N signals arrive, then stay open.
- `Gate` with `open()`, `wait(timeout=None)` and `is_open`: a one-shot manual
  event that stays open once triggered.
- `OneShotEvent` with `set()`, `wait(timeout=None)` and `is_set`: fires once and
  returns `True` only to the first caller.
