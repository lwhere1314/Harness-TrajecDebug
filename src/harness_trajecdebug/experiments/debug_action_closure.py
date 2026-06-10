"""Check whether Debug-Action cards contain materializable task artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


HEREDOC_RE = re.compile(
    r"cat\s+>\s+\"(?P<path>[^\"]+)\"\s+<<'(?P<tag>[^']+)'\n(?P<body>.*?)\n(?P=tag)",
    re.DOTALL,
)


@dataclass
class Artifact:
    path: str
    bytes: int
    sha256: str
    preview: str


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def parse_artifacts(card_text: str) -> list[tuple[str, str]]:
    return [(match.group("path"), match.group("body")) for match in HEREDOC_RE.finditer(card_text)]


def materialize_artifacts(artifacts: list[tuple[str, str]], root: Path) -> list[Artifact]:
    materialized: list[Artifact] = []
    for artifact_path, body in artifacts:
        relative = artifact_path.lstrip("/")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        raw = target.read_bytes()
        materialized.append(
            Artifact(
                path=artifact_path,
                bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(),
                preview=target.read_text(encoding="utf-8", errors="replace")[:120],
            )
        )
    return materialized


def check_query_optimize(root: Path) -> list[Check]:
    path = root / "app" / "sol.sql"
    if not path.exists():
        return [Check("query_optimize_artifact_exists", False, "/app/sol.sql is missing")]
    sql = path.read_text(encoding="utf-8", errors="replace").strip()
    clean = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
    clean = re.sub(r"/\*.*?\*/", "", clean, flags=re.DOTALL)
    normalized = " ".join(clean.split())
    checks = [
        Check("query_optimize_single_statement", normalized.count(";") == 1, f"semicolon_count={normalized.count(';')}"),
        Check("query_optimize_terminated", normalized.endswith(";"), "must end with semicolon"),
        Check("query_optimize_select_only", normalized.upper().startswith(("SELECT", "WITH")), normalized[:40]),
        Check("query_optimize_size", len(sql) <= 2000, f"chars={len(sql)}"),
    ]
    return checks


def check_break_filter(task_dir: Path, root: Path) -> list[Check]:
    out_path = root / "app" / "out.html"
    if not out_path.exists():
        return [Check("break_filter_artifact_exists", False, "/app/out.html is missing")]
    original = out_path.read_text(encoding="utf-8", errors="replace")

    filter_path = task_dir / "tests" / "filter.py"
    if not filter_path.exists():
        return [Check("break_filter_filter_exists", False, f"missing {filter_path}")]

    tmp_html = root / "tmp-filter-check.html"
    tmp_filter = root / "filter.py"
    tmp_html.write_text(out_path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
    shutil.copyfile(filter_path, tmp_filter)
    result = subprocess.run(
        ["python3", str(tmp_filter), str(tmp_html)],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    filtered = tmp_html.read_text(encoding="utf-8", errors="replace")
    return [
        Check("break_filter_filter_runs", result.returncode == 0, result.stderr.strip()[:200]),
        Check(
            "break_filter_parser_differential_pattern",
            "<noscript><style></noscript>" in original and "onerror=alert" in original,
            original[:120],
        ),
        Check(
            "break_filter_browser_verifier_required",
            True,
            "cheap text checks are not equivalent to the Chromium/Selenium verifier",
        ),
        Check("break_filter_filtered_preview_recorded", True, filtered[:120]),
    ]


def check_gcode_to_text(root: Path) -> list[Check]:
    path = root / "app" / "out.txt"
    expected = "flag{gc0d3_iz_ch4LLenGiNg}"
    if not path.exists():
        return [Check("gcode_to_text_artifact_exists", False, "/app/out.txt is missing")]
    value = path.read_text(encoding="utf-8", errors="replace").strip()
    return [
        Check("gcode_to_text_artifact_exists", True, "/app/out.txt"),
        Check("gcode_to_text_exact_flag", value == expected, value[:80]),
    ]


def task_specific_checks(task: str, task_dir: Path, root: Path) -> list[Check]:
    if task == "query-optimize":
        return check_query_optimize(root)
    if task == "break-filter-js-from-html":
        return check_break_filter(task_dir, root)
    if task == "gcode-to-text":
        return check_gcode_to_text(root)
    return [Check("task_specific_check_available", True, "no task-specific cheap check configured")]


def run_closure(pack_dir: Path, task: str, context_variant: str = "debug_action") -> dict[str, Any]:
    card_path = pack_dir / "teacher_cards" / task / f"{context_variant}.md"
    task_dir = pack_dir / "task_variants" / "no_icl" / task
    if not card_path.exists():
        raise FileNotFoundError(f"missing Debug-Action card: {card_path}")
    if not task_dir.exists():
        raise FileNotFoundError(f"missing task dir: {task_dir}")

    card_text = card_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_artifacts(card_text)
    checks = [Check("card_has_artifact_heredoc", bool(parsed), f"artifact_count={len(parsed)}")]
    with tempfile.TemporaryDirectory(prefix=f"htd-closure-{task}-") as tmp:
        root = Path(tmp)
        materialized = materialize_artifacts(parsed, root)
        checks.extend(task_specific_checks(task, task_dir, root))

    ok = all(check.ok for check in checks)
    status = "closure_passed" if ok else "closure_failed"
    if not parsed:
        status = "closure_unavailable"
    return {
        "task": task,
        "context_variant": context_variant,
        "card_path": str(card_path),
        "task_dir": str(task_dir),
        "status": status,
        "ok": ok,
        "artifacts": [asdict(item) for item in materialized],
        "checks": [asdict(item) for item in checks],
    }


def markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Debug-Action Artifact Closure",
        "",
        f"Pack: `{summary.get('pack_dir')}`",
        "",
        "| Task | Status | Artifacts | Checks |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary.get("rows", []):
        artifacts = ", ".join(f"`{item.get('path')}`" for item in row.get("artifacts", []))
        checks = ", ".join(
            f"{item.get('name')}={'ok' if item.get('ok') else 'fail'}"
            for item in row.get("checks", [])
        )
        lines.append(f"| `{row.get('task')}` | `{row.get('status')}` | {artifacts} | {checks} |")
    lines.append("")
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Debug-Action artifact materialization without a model call.")
    parser.add_argument("--pack-dir", type=Path, default=Path("runs/harbor_icl_baseline"))
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--context-variant", default="debug_action")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    rows = [
        run_closure(args.pack_dir, task, context_variant=args.context_variant)
        for task in args.task
    ]
    summary = {
        "pack_dir": str(args.pack_dir),
        "context_variant": args.context_variant,
        "rows": rows,
    }
    output_json = args.output_json or args.pack_dir / "artifact_closure" / "debug_action_closure.json"
    output_md = args.output_md or args.pack_dir / "artifact_closure" / "debug_action_closure.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(markdown(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(row.get("ok") or row.get("status") == "closure_unavailable" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
