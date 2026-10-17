"""Every docstring example and every Python block of the README and GUIDE runs."""

from __future__ import annotations

import doctest
import importlib
import inspect
import pkgutil
import re
from pathlib import Path

import pytest

import latchkit

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["latchkit"] + [
    f"latchkit.{info.name}" for info in pkgutil.iter_modules(latchkit.__path__)
]


def public_docstrings() -> dict[str, str]:
    """Every docstring a user can reach: each public class and each public member.

    Members are read straight from the classes (and their package bases), so no
    docstring is missed because the classes report ``latchkit`` as their module.
    """
    docs = {}
    for name in latchkit.__all__:
        cls = getattr(latchkit, name)
        docs[name] = inspect.getdoc(cls) or ""
        for member in dir(cls):
            if member.startswith("_") or member in dir(OSError):
                continue
            static = inspect.getattr_static(cls, member)
            target = static.fget if isinstance(static, property) else getattr(cls, member)
            docs[f"{name}.{member}"] = inspect.getdoc(target) or ""
    return docs


def test_every_public_docstring_example_runs_and_passes() -> None:
    parser = doctest.DocTestParser()
    runner = doctest.DocTestRunner(optionflags=doctest.ELLIPSIS)
    ran = 0
    for name, doc in public_docstrings().items():
        test = parser.get_doctest(doc, {}, name, None, 0)
        result = runner.run(test, clear_globs=True)
        assert result.failed == 0, name
        ran += result.attempted
    assert ran >= 150


def test_every_public_member_shows_more_than_an_import() -> None:
    parser = doctest.DocTestParser()
    thin = []
    for name, doc in public_docstrings().items():
        examples = parser.get_examples(doc)
        if not any(not e.source.startswith(("import ", "from ")) for e in examples):
            thin.append(name)
    assert thin == []


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
