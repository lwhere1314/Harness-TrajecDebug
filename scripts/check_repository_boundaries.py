#!/usr/bin/env python3
"""Fail when repository-scale research artifacts cross product boundaries."""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAX_GIT_BLOB_BYTES = 5_000_000
LFS_EXTENSIONS = {".mp4", ".zst"}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout


def lfs_filter(path: str) -> str:
    output = git("check-attr", "filter", "--", path).strip()
    return output.rsplit(": ", 1)[-1]


def main() -> int:
    errors: list[str] = []
    tracked = set(git("ls-files").splitlines())

    for path in sorted(tracked):
        if Path(path).suffix in LFS_EXTENSIONS and lfs_filter(path) != "lfs":
            errors.append(f"binary evidence is not covered by Git LFS: {path}")

    for line in git("ls-tree", "-rl", "HEAD").splitlines():
        metadata, path = line.split("\t", 1)
        size_text = metadata.rsplit(" ", 1)[-1]
        if size_text != "-" and int(size_text) > MAX_GIT_BLOB_BYTES:
            if lfs_filter(path) != "lfs":
                errors.append(
                    f"tracked blob exceeds {MAX_GIT_BLOB_BYTES} bytes without Git LFS: {path}"
                )

    if errors:
        print("Repository boundary check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Repository boundaries OK: large evidence is covered by Git LFS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
