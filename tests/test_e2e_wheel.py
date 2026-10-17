"""Real end-to-end: build the wheel, install it in a fresh venv, use it from outside.

Nothing is mocked. The wheel is built from the repository with pip, installed
into a throwaway virtual environment without access to the source tree, and a
consumer program (tests/e2e/consumer.py) runs against it in a subprocess.

Every child process is bounded. Output goes to a file, never a pipe, and on a
timeout the whole process tree is killed: on Windows a venv's python.exe is a
launcher with a child of its own, which would otherwise keep a pipe open and
hang the test forever.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import latchkit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONSUMER = Path(__file__).resolve().parent / "e2e" / "consumer.py"
_IS_WINDOWS = os.name == "nt"
_CLEAN_ENV = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
UPGRADE = os.environ.get("LATCHKIT_E2E") == "1"
CHECKS = ["threads ok", "abort ok", "event ok", "asyncio ok", "all ok"]


def run(command: list[str], timeout: float, cwd: Path | None = None) -> list[str]:
    """Run ``command`` to completion within ``timeout`` seconds and return its output lines."""
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as out:
        process = subprocess.Popen(
            command, cwd=cwd, env=_CLEAN_ENV, stdout=out, stderr=subprocess.STDOUT
        )
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if _IS_WINDOWS:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                    capture_output=True,
                    timeout=60,
                )
            process.kill()
            process.wait(timeout=60)
            pytest.fail(f"{command[1:4]} did not finish within {timeout} seconds")
        out.seek(0)
        text = out.read()
    assert code == 0, text
    return text.splitlines()


def make_venv(where: Path) -> tuple[Path, list[str]]:
    run([sys.executable, "-m", "venv", str(where)], timeout=300)
    python = where / ("Scripts/python.exe" if _IS_WINDOWS else "bin/python")
    return python, [str(python), "-m", "pip", "-q", "--disable-pip-version-check"]


@pytest.fixture(scope="module")
def venv_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("latchkit_e2e")
    wheels = work / "wheels"
    python, pip = make_venv(work / "venv")
    run([*pip, "wheel", "--no-deps", "-w", str(wheels), str(_REPO_ROOT)], timeout=600)
    built = sorted(wheels.glob("latchkit-*.whl"))
    assert [w.name for w in built] == [f"latchkit-{latchkit.__version__}-py3-none-any.whl"]
    run([*pip, "install", "--no-index", str(built[0])], timeout=300)
    return python


def test_the_installed_wheel_works_for_an_external_consumer(
    venv_python: Path, tmp_path: Path
) -> None:
    lines = run([str(venv_python), "-I", str(_CONSUMER)], timeout=300, cwd=tmp_path)
    assert lines == [f"install ok {latchkit.__version__}", *CHECKS]


def test_the_wheel_ships_type_information(venv_python: Path) -> None:
    code = (
        "import importlib.resources as r; print(r.files('latchkit').joinpath('py.typed').is_file())"
    )
    assert run([str(venv_python), "-I", "-c", code], timeout=60) == ["True"]


@pytest.mark.skipif(not UPGRADE, reason="needs PyPI: set LATCHKIT_E2E=1")
def test_upgrade_in_place_from_the_pypi_release(
    venv_python: Path, tmp_path_factory: pytest.TempPathFactory
) -> None:
    work = tmp_path_factory.mktemp("latchkit_upgrade")
    python, pip = make_venv(work / "venv")
    run([*pip, "install", "latchkit==0.2.0"], timeout=600)
    before = run([str(python), "-I", str(_CONSUMER)], timeout=300, cwd=work)
    assert before == ["install ok 0.2.0", *CHECKS]
    wheels = sorted((venv_python.parents[2] / "wheels").glob("latchkit-*.whl"))
    run([*pip, "install", "--no-index", str(wheels[0])], timeout=300)
    after = run([str(python), "-I", str(_CONSUMER)], timeout=300, cwd=work)
    assert after == [f"install ok {latchkit.__version__}", *CHECKS]
