#!/usr/bin/env python3
"""Collect Kimi session wire records referenced by metrics.json."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = REPO_ROOT / (
    "docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/"
    "metrics.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-json", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.metrics_json.read_text())
    args.output_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, Any]] = []
    for row in rows:
        if "kimi-code" not in str(row.get("source", "")):
            continue
        wire_raw = row.get("kimi_wire_path")
        session_id = row.get("kimi_session_id")
        if not wire_raw or not session_id:
            continue
        wire_path = Path(wire_raw)
        if not wire_path.exists():
            continue

        record_dir = args.output_dir / safe_name(f"{row['task']}__{row['trial']}")
        record_dir.mkdir(parents=True, exist_ok=True)
        wire_dest = record_dir / "wire.jsonl"
        shutil.copy2(wire_path, wire_dest)

        state_dest = None
        state_path = wire_path.parents[2] / "state.json"
        if state_path.exists():
            state_dest = record_dir / "state.json"
            shutil.copy2(state_path, state_dest)

        manifest.append(
            {
                "task": row.get("task"),
                "variant": row.get("variant"),
                "trial": row.get("trial"),
                "session_id": session_id,
                "source_wire_path": str(wire_path),
                "archive_wire_path": str(wire_dest.relative_to(args.output_dir)),
                "archive_state_path": (
                    str(state_dest.relative_to(args.output_dir)) if state_dest else None
                ),
                "token_usage_source": row.get("token_usage_source"),
                "input_tokens": row.get("input_tokens"),
                "cache_tokens": row.get("cache_tokens"),
                "output_tokens": row.get("output_tokens"),
                "total_input_output_tokens": row.get("total_input_output_tokens"),
                "uncached_input_output_tokens": row.get(
                    "uncached_input_output_tokens"
                ),
                "kimi_usage_turns": row.get("kimi_usage_turns"),
            }
        )

    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_csv(args.output_dir / "manifest.csv", manifest)
    print(f"Collected {len(manifest)} Kimi session records into {args.output_dir}")
    return 0


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
