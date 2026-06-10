#!/usr/bin/env python3
"""Extract token and latency metrics for the TB2.1 Meta-Harness study."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO_ROOT / (
    "docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/"
    "tb21_89_audit.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / (
    "docs/case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    audit = json.loads(args.audit_json.read_text())
    rows: list[dict[str, Any]] = []
    for task_row in audit["tasks"]:
        task = task_row["task"]
        baseline_path = task_row.get("baseline_result_path")
        if baseline_path:
            rows.append(
                build_metric_row(
                    task=task,
                    variant="without Meta-Harness",
                    source="claude-code+kimi-k2.6",
                    result_path=Path(baseline_path),
                    counts_for_score=task_row.get("counts_for_without_n"),
                    comparison_status=task_row.get("baseline_status"),
                )
            )
        with_path = task_row.get("with_metaharness_result_path")
        if with_path:
            rows.append(
                build_metric_row(
                    task=task,
                    variant="with Meta-Harness",
                    source="kimi-code+kimi-for-coding",
                    result_path=Path(with_path),
                    counts_for_score=task_row.get("counts_for_m"),
                    comparison_status=task_row.get("with_metaharness_status"),
                )
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "metrics.csv"
    json_path = args.output_dir / "metrics.json"
    summary_path = args.output_dir / "metrics_summary.json"
    pairs_csv_path = args.output_dir / "metrics_task_pairs.csv"
    pairs_json_path = args.output_dir / "metrics_task_pairs.json"
    write_csv(csv_path, rows)
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    pair_rows = build_pair_rows(rows)
    write_csv(pairs_csv_path, pair_rows)
    pairs_json_path.write_text(
        json.dumps(pair_rows, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = summarize(rows, pair_rows)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"Wrote {csv_path}")
    print(f"Wrote {json_path}")
    print(f"Wrote {pairs_csv_path}")
    print(f"Wrote {pairs_json_path}")
    print(f"Wrote {summary_path}")
    return 0


def build_metric_row(
    *,
    task: str,
    variant: str,
    source: str,
    result_path: Path,
    counts_for_score: bool,
    comparison_status: str,
) -> dict[str, Any]:
    data = read_json(result_path)
    verifier = data.get("verifier_result") if isinstance(data.get("verifier_result"), dict) else None
    rewards = verifier.get("rewards") if isinstance(verifier, dict) and isinstance(verifier.get("rewards"), dict) else {}
    exception = data.get("exception_info") if isinstance(data.get("exception_info"), dict) else {}
    agent_result = data.get("agent_result") if isinstance(data.get("agent_result"), dict) else {}
    trial_dir = result_path.parent

    prompt_path = trial_dir / "agent" / "prompt.txt"
    previous_failure_path = trial_dir / "agent" / "previous-failure.txt"
    env_snapshot_path = trial_dir / "agent" / "env-snapshot.txt"
    kimi_stdout_path = trial_dir / "agent" / "kimi-stdout.txt"
    claude_text_path = trial_dir / "agent" / "claude-code.txt"
    trajectory_path = trial_dir / "agent" / "trajectory.json"

    input_tokens = agent_result.get("n_input_tokens")
    cache_tokens = agent_result.get("n_cache_tokens")
    output_tokens = agent_result.get("n_output_tokens")
    total_tokens = sum_ints(input_tokens, output_tokens)
    uncached_input_tokens = token_minus(input_tokens, cache_tokens)
    uncached_input_output_tokens = sum_ints(uncached_input_tokens, output_tokens)

    return {
        "task": task,
        "variant": variant,
        "source": source,
        "trial": trial_dir.name,
        "comparison_status": comparison_status,
        "counts_for_score": bool(counts_for_score),
        "reward": as_float(rewards.get("reward")),
        "exception_type": exception.get("exception_type"),
        "valid_verifier_result": verifier is not None and as_float(rewards.get("reward")) is not None,
        "timeout_upload_result": exception.get("exception_type") == "AgentTimeoutError" and verifier is not None,
        "result_path": str(result_path),
        "wall_duration_sec": duration(data.get("started_at"), data.get("finished_at")),
        "environment_setup_sec": section_duration(data.get("environment_setup")),
        "agent_setup_sec": section_duration(data.get("agent_setup")),
        "agent_execution_sec": section_duration(data.get("agent_execution")),
        "verifier_sec": section_duration(data.get("verifier")),
        "input_tokens": input_tokens,
        "cache_tokens": cache_tokens,
        "output_tokens": output_tokens,
        "token_usage_available": total_tokens is not None,
        "total_input_output_tokens": total_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "uncached_input_output_tokens": uncached_input_output_tokens,
        "cost_usd": agent_result.get("cost_usd"),
        "prompt_chars": file_len(prompt_path),
        "previous_failure_chars": file_len(previous_failure_path),
        "env_snapshot_chars": file_len(env_snapshot_path),
        "injected_context_chars": sum_ints(file_len(previous_failure_path), file_len(env_snapshot_path)),
        "kimi_stdout_bytes": file_len(kimi_stdout_path),
        "kimi_stream_events": line_count(kimi_stdout_path),
        "kimi_tool_call_events": count_jsonl_tool_calls(kimi_stdout_path),
        "claude_log_bytes": file_len(claude_text_path),
        "claude_trajectory_steps": trajectory_steps(trajectory_path),
    }


def build_pair_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        by_task.setdefault(row["task"], {})[row["variant"]] = row

    pairs: list[dict[str, Any]] = []
    for task, variants in sorted(by_task.items()):
        baseline = variants.get("without Meta-Harness")
        with_mh = variants.get("with Meta-Harness")
        if not baseline or not with_mh:
            continue
        pairs.append(
            {
                "task": task,
                "baseline_trial": baseline["trial"],
                "with_trial": with_mh["trial"],
                "baseline_reward": baseline["reward"],
                "with_reward": with_mh["reward"],
                "delta_reward": diff(with_mh["reward"], baseline["reward"]),
                "with_valid_verifier_result": with_mh["valid_verifier_result"],
                "with_timeout_upload_result": with_mh["timeout_upload_result"],
                "baseline_exception_type": baseline["exception_type"],
                "with_exception_type": with_mh["exception_type"],
                "baseline_wall_duration_sec": baseline["wall_duration_sec"],
                "with_wall_duration_sec": with_mh["wall_duration_sec"],
                "delta_wall_duration_sec": diff(
                    with_mh["wall_duration_sec"],
                    baseline["wall_duration_sec"],
                ),
                "baseline_agent_execution_sec": baseline["agent_execution_sec"],
                "with_agent_execution_sec": with_mh["agent_execution_sec"],
                "delta_agent_execution_sec": diff(
                    with_mh["agent_execution_sec"],
                    baseline["agent_execution_sec"],
                ),
                "baseline_verifier_sec": baseline["verifier_sec"],
                "with_verifier_sec": with_mh["verifier_sec"],
                "delta_verifier_sec": diff(with_mh["verifier_sec"], baseline["verifier_sec"]),
                "baseline_total_input_output_tokens": baseline["total_input_output_tokens"],
                "with_total_input_output_tokens": with_mh["total_input_output_tokens"],
                "delta_total_input_output_tokens": diff(
                    with_mh["total_input_output_tokens"],
                    baseline["total_input_output_tokens"],
                ),
                "baseline_uncached_input_output_tokens": baseline[
                    "uncached_input_output_tokens"
                ],
                "with_uncached_input_output_tokens": with_mh["uncached_input_output_tokens"],
                "delta_uncached_input_output_tokens": diff(
                    with_mh["uncached_input_output_tokens"],
                    baseline["uncached_input_output_tokens"],
                ),
                "with_prompt_chars": with_mh["prompt_chars"],
                "with_injected_context_chars": with_mh["injected_context_chars"],
                "with_kimi_tool_call_events": with_mh["kimi_tool_call_events"],
                "with_comparison_status": with_mh["comparison_status"],
            }
        )
    return pairs


def summarize(rows: list[dict[str, Any]], pair_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_variant.setdefault(row["variant"], []).append(row)
    return {
        "row_count": len(rows),
        "variants": {
            variant: {
                "rows": len(items),
                "valid_verifier_results": sum(1 for row in items if row["valid_verifier_result"]),
                "reward_1_count": sum(1 for row in items if row["reward"] == 1.0),
                "token_usage_rows": sum(1 for row in items if row["token_usage_available"]),
                "mean_wall_duration_sec": mean(row["wall_duration_sec"] for row in items),
                "mean_agent_execution_sec": mean(row["agent_execution_sec"] for row in items),
                "mean_verifier_sec": mean(row["verifier_sec"] for row in items),
                "mean_total_input_output_tokens": mean(
                    row["total_input_output_tokens"] for row in items
                ),
                "mean_uncached_input_output_tokens": mean(
                    row["uncached_input_output_tokens"] for row in items
                ),
                "mean_prompt_chars": mean(row["prompt_chars"] for row in items),
                "mean_injected_context_chars": mean(
                    row["injected_context_chars"] for row in items
                ),
            }
            for variant, items in sorted(by_variant.items())
        },
        "paired_diffs": {
            "rows": len(pair_rows),
            "valid_with_verifier_results": sum(
                1 for row in pair_rows if row["with_valid_verifier_result"]
            ),
            "mean_delta_reward": mean(row["delta_reward"] for row in pair_rows),
            "mean_delta_wall_duration_sec": mean(
                row["delta_wall_duration_sec"] for row in pair_rows
            ),
            "mean_delta_agent_execution_sec": mean(
                row["delta_agent_execution_sec"] for row in pair_rows
            ),
            "mean_delta_verifier_sec": mean(row["delta_verifier_sec"] for row in pair_rows),
            "mean_delta_total_input_output_tokens": mean(
                row["delta_total_input_output_tokens"] for row in pair_rows
            ),
            "mean_delta_uncached_input_output_tokens": mean(
                row["delta_uncached_input_output_tokens"] for row in pair_rows
            ),
        },
        "notes": [
            "Token fields are direct Harbor agent_result values when present.",
            "KimiCode rows currently have null token fields because the adapter does not emit provider usage.",
            "uncached_input_output_tokens is computed as input_tokens - cache_tokens + output_tokens.",
            "prompt_chars and injected_context_chars are recorded as observable context-size proxies.",
        ],
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def duration(start: str | None, end: str | None) -> float | None:
    start_dt = parse_time(start)
    end_dt = parse_time(end)
    if not start_dt or not end_dt:
        return None
    return round((end_dt - start_dt).total_seconds(), 3)


def section_duration(section: Any) -> float | None:
    if not isinstance(section, dict):
        return None
    return duration(section.get("started_at"), section.get("finished_at"))


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def sum_ints(*values: Any) -> int | None:
    total = 0
    found = False
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        try:
            total += int(value)
            found = True
        except (TypeError, ValueError):
            continue
    return total if found else None


def token_minus(left: Any, right: Any) -> int | None:
    if left is None or right is None:
        return None
    try:
        return int(left) - int(right)
    except (TypeError, ValueError):
        return None


def diff(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    try:
        return round(float(left) - float(right), 3)
    except (TypeError, ValueError):
        return None


def file_len(path: Path) -> int | None:
    try:
        return path.stat().st_size
    except OSError:
        return None


def line_count(path: Path) -> int | None:
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return None


def count_jsonl_tool_calls(path: Path) -> int | None:
    try:
        total = 0
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("tool_calls"):
                    total += len(event["tool_calls"])
        return total
    except OSError:
        return None


def trajectory_steps(path: Path) -> int | None:
    data = read_json(path)
    steps = data.get("steps")
    return len(steps) if isinstance(steps, list) else None


def mean(values: Any) -> float | None:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return None
    return round(sum(clean) / len(clean), 3)


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
