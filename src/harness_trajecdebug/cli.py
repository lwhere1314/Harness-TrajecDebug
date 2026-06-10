"""Command line interface for Harness-TrajecDebug."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from harness_trajecdebug.atif_viewer import DEFAULT_VIEWER_ROOT, export_harbor_run_to_viewer, viewer_info
from harness_trajecdebug.diagnose import diagnose_trace
from harness_trajecdebug.harbor import (
    default_datasets_root,
    default_runs_root,
    discover_harbor_tasks,
    discover_harbor_trials,
    write_normalized_harbor_run,
)
from harness_trajecdebug.harnesses import discover_harness_backends


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

    harnesses = subcommands.add_parser("harnesses", help="Discover local harness backends.")
    harnesses.add_argument("--ssd-root", type=Path, default=Path("/Volumes/SSD"), help="SSD root to scan.")

    harbor_tasks = subcommands.add_parser("harbor-tasks", help="List Harbor-compatible task directories.")
    harbor_tasks.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Datasets root. Defaults to the local Harbor datasets directory when available.",
    )
    harbor_tasks.add_argument("--limit", type=int, default=None, help="Optional maximum number of tasks to list.")

    harbor_trials = subcommands.add_parser("harbor-trials", help="List trials in a Harbor run directory.")
    harbor_trials.add_argument(
        "--run",
        type=Path,
        default=None,
        help="Harbor run or trial directory. Defaults to the local Harbor runs directory.",
    )

    harbor_import = subcommands.add_parser("harbor-import", help="Normalize a Harbor run/trial into trace JSON.")
    harbor_import.add_argument("--run", type=Path, required=True, help="Harbor run or trial directory.")
    harbor_import.add_argument("--output-dir", type=Path, required=True, help="Directory for normalized trace JSON files.")
    harbor_import.add_argument(
        "--diagnose",
        action="store_true",
        help="Also run diagnosis for each normalized trace and write diagnoses next to the traces.",
    )

    atif_viewer_info = subcommands.add_parser("atif-viewer-info", help="Inspect an ATIF trajectory viewer checkout.")
    atif_viewer_info.add_argument(
        "--viewer-root",
        type=Path,
        default=DEFAULT_VIEWER_ROOT,
        help="ATIF trajectory viewer root.",
    )

    atif_viewer_export = subcommands.add_parser(
        "atif-viewer-export",
        help="Export a Harbor run/trial into the ATIF trajectory viewer local bundle index.",
    )
    atif_viewer_export.add_argument("--run", type=Path, required=True, help="Harbor run or trial directory.")
    atif_viewer_export.add_argument(
        "--viewer-root",
        type=Path,
        default=DEFAULT_VIEWER_ROOT,
        help="ATIF trajectory viewer root.",
    )
    atif_viewer_export.add_argument("--label", default=None, help="Stable local bundle id to write/update.")
    atif_viewer_export.add_argument(
        "--diagnose",
        action="store_true",
        help="Also write Harness-TrajecDebug diagnoses into the viewer local bundle.",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "harnesses":
        _print_json([backend.to_dict() for backend in discover_harness_backends(args.ssd_root)])
        return

    if args.command == "harbor-tasks":
        root = args.root or default_datasets_root()
        if root is None:
            parser.error("No Harbor datasets root found; pass --root.")
        _print_json([task.to_dict() for task in discover_harbor_tasks(root.resolve(), limit=args.limit)])
        return

    if args.command == "harbor-trials":
        run = args.run or default_runs_root()
        if run is None:
            parser.error("No Harbor runs root found; pass --run.")
        _print_json([trial.to_dict() for trial in discover_harbor_trials(run.resolve())])
        return

    if args.command == "harbor-import":
        written = write_normalized_harbor_run(args.run.resolve(), args.output_dir.resolve())
        diagnoses = []
        if args.diagnose:
            diagnosis_dir = args.output_dir.resolve() / "diagnoses"
            diagnosis_dir.mkdir(parents=True, exist_ok=True)
            for trace_path in written:
                diagnosis = diagnose_trace(trace_path, run_id=trace_path.stem)
                target = diagnosis_dir / f"{trace_path.stem}-diagnosis.json"
                target.write_text(json.dumps(asdict(diagnosis), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                diagnoses.append(target)
        _print_json(
            {
                "traces": [str(path) for path in written],
                "diagnoses": [str(path) for path in diagnoses],
            }
        )
        return

    if args.command == "atif-viewer-info":
        _print_json(viewer_info(args.viewer_root))
        return

    if args.command == "atif-viewer-export":
        _print_json(
            export_harbor_run_to_viewer(
                args.run.resolve(),
                viewer_root=args.viewer_root.resolve(),
                label=args.label,
                diagnose=args.diagnose,
            )
        )
        return

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


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
