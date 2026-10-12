"""Real end-to-end: build the wheel, install it in a fresh venv, use it from outside.

Nothing is mocked. The wheel is built from the repository with pip, installed
into a throwaway virtual environment without access to the source tree, and a
consumer program (tests/e2e/consumer.py) runs against it in a subprocess.
"""

from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path

import pytest

import latchkit

_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONSUMER = Path(__file__).resolve().parent / "e2e" / "consumer.py"
_IS_WINDOWS = os.name == "nt"


@pytest.fixture(scope="module")
def venv_python(tmp_path_factory: pytest.TempPathFactory) -> Path:
    work = tmp_path_factory.mktemp("latchkit_e2e")
    wheels = work / "wheels"
    env_dir = work / "venv"
    venv.create(env_dir, with_pip=True)
    bin_dir = env_dir / ("Scripts" if _IS_WINDOWS else "bin")
    python = bin_dir / ("python.exe" if _IS_WINDOWS else "python")
    pip = [str(python), "-m", "pip", "-q", "--disable-pip-version-check"]
    subprocess.run(
        [*pip, "wheel", "--no-deps", "-w", str(wheels), str(_REPO_ROOT)], check=True, timeout=600
    )
    built = sorted(wheels.glob("latchkit-*.whl"))
    assert [w.name for w in built] == [f"latchkit-{latchkit.__version__}-py3-none-any.whl"]
    subprocess.run([*pip, "install", "--no-index", str(built[0])], check=True, timeout=300)
    return python


def test_the_installed_wheel_works_for_an_external_consumer(
    venv_python: Path, tmp_path: Path
) -> None:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    result = subprocess.run(
        [str(venv_python), "-I", str(_CONSUMER)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    lines = result.stdout.splitlines()
    assert lines[0] == f"install ok {latchkit.__version__}"
    assert lines[1:] == ["threads ok", "abort ok", "event ok", "asyncio ok", "all ok"]


def test_the_wheel_ships_type_information(venv_python: Path) -> None:
    code = (
        "import importlib.resources as r; print(r.files('latchkit').joinpath('py.typed').is_file())"
    )
    result = subprocess.run(
        [str(venv_python), "-I", "-c", code], capture_output=True, text=True, timeout=60, check=True
    )
    assert result.stdout.strip() == "True"
