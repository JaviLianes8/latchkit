"""Every docstring example and every Python block of the README and GUIDE runs."""

from __future__ import annotations

import doctest
import importlib
import pkgutil
import re
from pathlib import Path

import pytest

import latchkit

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["latchkit"] + [
    f"latchkit.{info.name}" for info in pkgutil.iter_modules(latchkit.__path__)
]


def test_every_public_name_carries_doctests_that_pass() -> None:
    # The public classes report ``latchkit`` as their module, so their examples are
    # found (and run) through the package itself.
    finder = doctest.DocTestFinder()
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    tested = [test for test in finder.find(latchkit) if test.examples]
    for test in tested:
        runner.run(test)
    assert runner.summarize(verbose=False).failed == 0
    owners = {test.name.split(".")[1] for test in tested if test.name.count(".") >= 1}
    assert owners >= set(latchkit.__all__)
    assert sum(len(test.examples) for test in tested) >= 50


@pytest.mark.parametrize("name", MODULES)
def test_module_doctests_pass(name: str) -> None:
    module = importlib.import_module(name)
    result = doctest.testmod(module, optionflags=doctest.ELLIPSIS, verbose=False)
    assert result.failed == 0


def python_blocks(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


def test_readme_examples_run_in_order() -> None:
    blocks = python_blocks(ROOT / "README.md")
    assert len(blocks) >= 6
    namespace: dict[str, object] = {"__name__": "readme"}
    for block in blocks:
        exec(compile(block, "README.md", "exec"), namespace)


def test_guide_examples_run_in_order() -> None:
    blocks = python_blocks(ROOT / "GUIDE.md")
    assert blocks, "the guide carries runnable examples"
    namespace: dict[str, object] = {"__name__": "guide"}
    for block in blocks:
        exec(compile(block, "GUIDE.md", "exec"), namespace)


def test_docs_link_to_each_other_with_absolute_urls() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    base = "https://github.com/JaviLianes8/latchkit/blob/main/"
    for target in ("GUIDE.md", "CHANGELOG.md", "LICENSE"):
        assert base + target in readme
    assert not re.search(r"\]\((?!https://)", readme), "relative links break on PyPI"
