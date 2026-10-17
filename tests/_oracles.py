"""Drive the reference latches (Java 21, .NET 9) and replay their scenarios on latchkit.

The programs live in ``tests/oracle/``. ``scripts/capture_oracles.py`` records their
output in ``tests/fixtures/oracle_runs.json``; ``tests/test_oracle.py`` replays that
fixture and, when asked to, runs the programs live on fresh scenarios.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

ORACLE = Path(__file__).resolve().parent / "oracle"


def scenarios(seed: int, count: int, *, count_up: bool) -> list[str]:
    """Seeded scenarios: an initial count, then ops (see the oracle programs)."""
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        parts = [str(rng.choice([-1, 0, 0, 1, 2, 3, 4, 5, 7]))]
        for _ in range(rng.randint(3, 14)):
            roll = rng.random()
            if roll < 0.45:
                parts.append(
                    f"d{rng.choice([0, 1, 1, 1, 2, 3, 6]) if count_up else rng.randint(1, 4)}"
                )
            elif count_up and roll < 0.65:
                parts.append(f"u{rng.choice([0, 1, 1, 2, 3])}")
            elif roll < 0.8:
                parts.append("r")
            elif roll < 0.93:
                parts.append("w")
            else:
                parts.append("n")
        out.append(" ".join(parts))
    return out


def _feed(command: list[str], lines: list[str], cwd: str) -> list[str]:
    stdin = "".join(line + "\n" for line in lines) + "\n"
    result = subprocess.run(
        command, input=stdin, capture_output=True, text=True, timeout=600, cwd=cwd, check=True
    )
    return result.stdout.splitlines()


def run_java(lines: list[str]) -> tuple[list[str], str]:
    """Compile and run LatchOracle.java; return its lines and the Java version."""
    with tempfile.TemporaryDirectory() as work:
        subprocess.run(
            ["javac", "-d", work, str(ORACLE / "LatchOracle.java")], check=True, timeout=600
        )
        version = subprocess.run(
            ["java", "-version"], capture_output=True, text=True, timeout=60, check=True
        ).stderr.splitlines()[0]
        return _feed(["java", "-cp", work, "LatchOracle"], lines, work), version


def run_dotnet(lines: list[str]) -> tuple[list[str], str]:
    """Build and run the CountdownEvent program; return its lines and the runtime version."""
    with tempfile.TemporaryDirectory() as work:
        for name in ("LatchOracle.csproj", "Program.cs"):
            shutil.copy(ORACLE / "dotnet" / name, work)
        env = {**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}
        subprocess.run(
            ["dotnet", "build", "-c", "Release", "-o", "out", "-v", "q"],
            cwd=work,
            env=env,
            capture_output=True,
            check=True,
            timeout=600,
        )
        version = subprocess.run(
            ["dotnet", "--version"], capture_output=True, text=True, timeout=60, check=True
        ).stdout.strip()
        return _feed(["dotnet", str(Path(work, "out", "LatchOracle.dll"))], lines, work), version


Wait = Callable[[object, float], bool]


def replay(scenario: str, make: Callable[[int], object], wait: Wait, *, refuse: bool) -> str:
    """Run one scenario on a latchkit latch and print it the way the oracles do.

    With ``refuse`` (the .NET convention) a step beyond the remaining count, a step
    on an open latch and a negative wait print the .NET error and change nothing,
    which latchkit itself never does: the caller checks those spots separately.
    """
    parts = scenario.split(" ")
    try:
        latch: object = make(int(parts[0]))
    except ValueError:
        return "E:ArgumentOutOfRangeException" if refuse else "E:IllegalArgumentException"
    out = []
    for op in parts[1:]:
        out.append(_step(latch, op, wait, refuse))
    return " ".join(out)


def _step(latch: object, op: str, wait: Wait, refuse: bool) -> str:
    remaining: int = latch.remaining  # type: ignore[attr-defined]
    if op[0] in "du" and op[1:] == "0":
        try:
            getattr(latch, "count_down" if op[0] == "d" else "try_count_up")(0)
        except ValueError:
            return "E:ArgumentOutOfRangeException"
        raise AssertionError("a zero step was accepted")
    if op[0] == "d":
        k = int(op[1:])
        if refuse and k > remaining:
            return "E:InvalidOperationException"
        return str(latch.count_down(k))  # type: ignore[attr-defined]
    if op[0] == "u":
        return "T" if latch.try_count_up(int(op[1:])) else "F"  # type: ignore[attr-defined]
    if op == "r":
        return str(remaining)
    if op == "n" and refuse:
        return "E:ArgumentOutOfRangeException"
    return "T" if wait(latch, 0.0 if op == "w" else -0.005) else "F"
