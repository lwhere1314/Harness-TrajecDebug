#!/usr/bin/env python3
"""Verify that Python release archives contain code, not research assets."""

from __future__ import annotations

import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


MAX_ARCHIVE_BYTES = 2_000_000
FORBIDDEN_PARTS = {
    "docs",
    "experiments",
    "raw-logs",
    "raw_logs",
    "plugins",
    "demo",
    "examples",
}


def archive_names(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            return archive.getnames()
    raise ValueError(f"unsupported distribution format: {path}")


def main(arguments: list[str]) -> int:
    if not arguments:
        print("usage: check_distribution_contents.py DIST [DIST ...]", file=sys.stderr)
        return 2

    errors: list[str] = []
    for value in arguments:
        path = Path(value)
        if path.stat().st_size > MAX_ARCHIVE_BYTES:
            errors.append(
                f"{path.name} is {path.stat().st_size} bytes; limit is {MAX_ARCHIVE_BYTES}"
            )

        for name in archive_names(path):
            parts = PurePosixPath(name).parts
            # Wheels have no archive root; sdists have one generated root.
            relative_parts = parts if path.suffix == ".whl" else parts[1:]
            top_level = relative_parts[0] if relative_parts else ""
            if top_level in FORBIDDEN_PARTS:
                errors.append(
                    f"{path.name} contains research-only path {name!r} "
                    f"({top_level})"
                )

    if errors:
        print("Distribution boundary check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Distribution boundaries OK: release archives contain no research assets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
