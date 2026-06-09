"""Command line interface for Harness-TrajecDebug."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from harness_trajecdebug.diagnose import diagnose_trace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-trajdebug",
        description="Diagnose terminal-agent traces with an explainable critical-step framework.",
    )
    subcommands = parser.add_subparsers(dest="command")

    diagnose = subcommands.add_parser("diagnose", help="Run diagnosis on one trace JSON.")
    diagnose.add_argument("--trace", type=Path, required=True, help="Trace JSON with steps and optional verifierLog.")
    diagnose.add_argument("--run-id", default=None, help="Optional run id for output metadata and joins.")
    diagnose.add_argument("--metrics-csv", type=Path, default=None, help="Optional CSV metadata keyed by run_id.")
    diagnose.add_argument("--case-json", type=Path, default=None, help="Optional viewer case JSON keyed by runId.")
    diagnose.add_argument("--output", type=Path, default=None, help="Write diagnosis JSON to this path.")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "diagnose":
        parser.print_help()
        return

    diagnosis = diagnose_trace(
        trace_path=args.trace.resolve(),
        run_id=args.run_id,
        metrics_csv=args.metrics_csv.resolve() if args.metrics_csv else None,
        case_json=args.case_json.resolve() if args.case_json else None,
    )
    text = json.dumps(asdict(diagnosis), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
