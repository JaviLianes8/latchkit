"""The public surface: exact names, frozen signatures, version and type information."""

from __future__ import annotations

import importlib.resources
import inspect

import latchkit

PUBLIC_API: list[str] = [
    "AsyncCountDownLatch",
    "AsyncGate",
    "AsyncOneShotEvent",
    "BrokenLatchError",
    "CountDownLatch",
    "Gate",
    "LatchError",
    "LatchTimeoutError",
    "OneShotEvent",
    "SignalScope",
]

SHARED = {
    "abort": "(self, reason: 'object' = None) -> 'bool'",
    "wait": "(self, timeout: 'float | None' = None) -> 'bool'",
    "wait_or_raise": "(self, timeout: 'float | None' = None) -> 'None'",
}
LATCH = {
    "__init__": "(self, count: 'int') -> 'None'",
    "count_down": "(self, n: 'int' = 1) -> 'int'",
    "try_count_up": "(self, n: 'int' = 1) -> 'bool'",
    "arrival": "(self, *, abort_on_error: 'bool' = False) -> 'SignalScope'",
}
GATE = {"open": "(self) -> 'bool'", "opening": "(self) -> 'SignalScope'"}
EVENT = {"set": "(self) -> 'bool'"}
SIGNATURES = {
    "CountDownLatch": {**SHARED, **LATCH},
    "AsyncCountDownLatch": {**SHARED, **LATCH},
    "Gate": {**SHARED, **GATE},
    "AsyncGate": {**SHARED, **GATE},
    "OneShotEvent": {**SHARED, **EVENT},
    "AsyncOneShotEvent": {**SHARED, **EVENT},
    "SignalScope": {
        "__init__": (
            "(self, on_success: 'Callable[[], object]', "
            "on_error: 'Callable[[BaseException], object] | None' = None) -> 'None'"
        )
    },
    "BrokenLatchError": {"__init__": "(self, reason: 'object' = None) -> 'None'"},
}
PROPERTIES = {
    "CountDownLatch": {"remaining", "is_open", "is_broken", "abort_reason"},
    "Gate": {"is_open", "is_broken", "abort_reason"},
    "OneShotEvent": {"is_set", "is_broken", "abort_reason"},
}


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(latchkit.__all__) == sorted(PUBLIC_API)
    assert len(set(latchkit.__all__)) == len(latchkit.__all__)


def test_nothing_else_is_public() -> None:
    visible = {name for name in dir(latchkit) if not name.startswith("_")}
    assert visible == set(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in latchkit.__all__:
        assert hasattr(latchkit, name)


def test_version_is_1_0_0() -> None:
    assert latchkit.__version__ == "1.0.0"


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("latchkit").joinpath("py.typed").is_file()


def test_signatures_are_frozen() -> None:
    for cls_name, methods in SIGNATURES.items():
        cls = getattr(latchkit, cls_name)
        for method, expected in methods.items():
            assert str(inspect.signature(getattr(cls, method))) == expected, (cls_name, method)


def test_async_waits_are_coroutines_and_signals_are_not() -> None:
    for name in ("AsyncCountDownLatch", "AsyncGate", "AsyncOneShotEvent"):
        cls = getattr(latchkit, name)
        assert inspect.iscoroutinefunction(cls.wait)
        assert inspect.iscoroutinefunction(cls.wait_or_raise)
        for signal in ("abort", "count_down", "try_count_up", "open", "set"):
            if hasattr(cls, signal):
                assert not inspect.iscoroutinefunction(getattr(cls, signal))


def test_read_only_properties() -> None:
    for prefix in ("", "Async"):
        for name, props in PROPERTIES.items():
            cls = getattr(latchkit, prefix + name)
            for prop in props:
                attr = inspect.getattr_static(cls, prop)
                assert isinstance(attr, property) and attr.fset is None, (cls, prop)


def test_every_public_name_has_a_docstring_with_an_example() -> None:
    for name in latchkit.__all__:
        doc = getattr(latchkit, name).__doc__ or ""
        assert ">>> " in doc, name
