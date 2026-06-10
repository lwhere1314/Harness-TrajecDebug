#!/usr/bin/env python3
"""CLI wrapper for model endpoint preflight."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from harness_trajecdebug.experiments.model_endpoint_preflight import main


if __name__ == "__main__":
    raise SystemExit(main())
