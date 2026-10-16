"""Fetch the reference documentation and sources the ground-truth tests read.

    python scripts/fetch_sources.py           # fetch and rewrite the manifest
    python scripts/fetch_sources.py --check   # fetch and fail if anything changed

The copies land in ``tests/sources/`` and are git-ignored: third-party text is never
committed or shipped. ``tests/sources/MANIFEST.json`` is tracked and records, for each
file, the URL, the fetch date, size, SHA-256 and licence, never the content. Tests that
read a copy skip when it is missing.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "tests" / "sources"
JAVA = "https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/util/concurrent"
SOURCES = {
    "java21-CountDownLatch.html": (f"{JAVA}/CountDownLatch.html", "Oracle documentation"),
    "java21-CyclicBarrier.html": (f"{JAVA}/CyclicBarrier.html", "Oracle documentation"),
    "java21-Phaser.html": (f"{JAVA}/Phaser.html", "Oracle documentation"),
    "dotnet9-CountdownEvent.cs": (
        "https://raw.githubusercontent.com/dotnet/runtime/v9.0.0/src/libraries/"
        "System.Threading/src/System/Threading/CountdownEvent.cs",
        "MIT",
    ),
    "go1.23-waitgroup.go": (
        "https://raw.githubusercontent.com/golang/go/go1.23.0/src/sync/waitgroup.go",
        "BSD-3-Clause",
    ),
    "cppreference-latch.html": ("https://en.cppreference.com/w/cpp/thread/latch.html", "CC-BY-SA"),
    "cppreference-latch-count_down.html": (
        "https://en.cppreference.com/w/cpp/thread/latch/count_down.html",
        "CC-BY-SA",
    ),
    "cpython3.13-asyncio-sync.rst": (
        "https://raw.githubusercontent.com/python/cpython/v3.13.2/Doc/library/asyncio-sync.rst",
        "PSF-2.0",
    ),
    "cpython3.13-threading.py.txt": (
        "https://raw.githubusercontent.com/python/cpython/v3.13.2/Lib/threading.py",
        "PSF-2.0",
    ),
}


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "latchkit-sources"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return bytes(response.read())


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "MANIFEST.json"
    check = "--check" in sys.argv
    old = json.loads(manifest_path.read_text("utf-8")) if manifest_path.is_file() else {}
    manifest = {}
    for name, (url, licence) in SOURCES.items():
        data = _fetch(url)
        digest = hashlib.sha256(data).hexdigest()
        if check and old.get(name, {}).get("sha256") != digest:
            print(f"{name}: changed since the manifest was written")
            return 1
        (ROOT / name).write_bytes(data)
        manifest[name] = {
            "url": url,
            "fetched": datetime.date.today().isoformat(),
            "size": len(data),
            "sha256": digest,
            "licence": licence,
        }
        print(f"{name}: {len(data)} bytes")
    if not check:
        text = json.dumps(manifest, indent=1, sort_keys=True) + "\n"
        manifest_path.write_text(text, "utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
