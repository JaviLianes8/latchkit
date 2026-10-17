"""Record what Java 21 and .NET 9 latches do on seeded scenarios.

    python scripts/capture_oracles.py

Needs ``javac``/``java`` and the ``dotnet`` SDK on PATH. Writes
``tests/fixtures/oracle_runs.json``: program output only, nothing hand-written.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from _oracles import run_dotnet, run_java, scenarios  # noqa: E402

SEED_SHARED = 20261016
SEED_DOTNET = 20261017
COUNT = 400


def main() -> int:
    shared = scenarios(SEED_SHARED, COUNT, count_up=False)
    dotnet_only = scenarios(SEED_DOTNET, COUNT, count_up=True)
    java_lines, java_version = run_java(shared)
    dotnet_lines, dotnet_version = run_dotnet(shared + dotnet_only)
    fixture = {
        "captured": datetime.date.today().isoformat(),
        "java": java_version,
        "dotnet": dotnet_version,
        "seeds": {"shared": SEED_SHARED, "dotnet": SEED_DOTNET},
        "shared": [
            {"ops": ops, "java": java, "dotnet": dotnet}
            for ops, java, dotnet in zip(shared, java_lines, dotnet_lines, strict=False)
        ],
        "dotnet_only": [
            {"ops": ops, "dotnet": dotnet}
            for ops, dotnet in zip(dotnet_only, dotnet_lines[COUNT:], strict=False)
        ],
        "probes": {
            "java": java_lines[COUNT:],
            "dotnet": dotnet_lines[2 * COUNT :],
        },
    }
    assert len(java_lines) == COUNT + 3 and len(dotnet_lines) == 2 * COUNT + 1
    path = ROOT / "tests" / "fixtures" / "oracle_runs.json"
    path.write_text(json.dumps(fixture, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{path.name}: {COUNT} shared, {COUNT} .NET-only scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
