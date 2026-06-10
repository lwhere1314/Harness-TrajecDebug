#!/usr/bin/env python3
"""Audit local Codex + GPT-5.5 Harbor failure pools.

The scanner is intentionally lightweight: it reads verifier reward files from
local Harbor run roots and emits a Markdown inventory. It does not launch
Docker, Harbor, or model calls.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_RUNS_ROOTS = (Path("/Volumes/SSD/terminal-bench-harbor/harbor/runs"),)


DISPOSITION = {
    "sanitize-git-repo": (
        "closed_loop",
        "One of the verified HTD cases; both oracle_grounded and debug_action reruns passed.",
    ),
    "filter-js-from-html": (
        "closed_loop",
        "One of the verified HTD cases; both oracle_grounded and debug_action reruns passed.",
    ),
    "sam-cell-seg": (
        "closed_loop",
        "One of the verified HTD cases; both oracle_grounded and debug_action reruns passed.",
    ),
    "raman-fitting": (
        "closed_loop",
        "One of the verified HTD cases; both oracle_grounded and debug_action reruns passed.",
    ),
    "pytorch-model-recovery": (
        "closed_loop",
        "One of the verified HTD cases; both oracle_grounded and debug_action reruns passed.",
    ),
    "overfull-hbox": (
        "closed_loop_extension",
        "Sixth verified case; local no-network verifier was used to remove apt/proxy noise.",
    ),
    "make-mips-interpreter": (
        "accepted_pending_kimi",
        "Tracked cards and oracle sanity are ready; Kimi reruns wait on endpoint availability.",
    ),
    "make-doom-for-mips": (
        "accepted_pending_kimi",
        "Tracked cards and oracle sanity are ready; Kimi reruns wait on endpoint availability.",
    ),
    "install-windows-3.11": (
        "deprioritized",
        "QEMU-heavy; keep for later after a timeout-aware harness plan exists.",
    ),
    "mteb-leaderboard": (
        "rejected",
        "Likely fixed leaderboard snapshot / fixed-answer leakage risk.",
    ),
    "nginx-request-logging": (
        "rejected",
        "Historical failure is proxy/verifier contamination rather than clean agent-process error.",
    ),
    "train-fasttext": (
        "superseded_by_clean_pass",
        "Early failed Codex runs were superseded by later clean Codex + GPT-5.5 pass / case-study traces.",
    ),
}


@dataclass(frozen=True)
class RewardRecord:
    root: Path
    task: str
    reward: str
    reward_path: Path
    failed_tests: tuple[str, ...]
    passed_tests: int
    kind: str

    @property
    def failed(self) -> bool:
        return self.reward not in {"1", "1.0"}


def codex_gpt55_roots(runs_roots: Iterable[Path]) -> list[Path]:
    roots = []
    seen: set[Path] = set()
    for runs_root in runs_roots:
        if not runs_root.exists():
            continue
        for path in runs_root.iterdir():
            if not path.is_dir():
                continue
            name = path.name.lower()
            if "codex" not in name or ("gpt55" not in name and "gpt-5" not in name):
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            roots.append(path)
    return sorted(roots, key=lambda p: p.name)


def task_from_reward_path(root: Path, reward_path: Path) -> tuple[str | None, str]:
    rel = reward_path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 4 and parts[0] == "tasks" and parts[2] == "verifier":
        return parts[1], "task"
    if len(parts) >= 7 and parts[0] == "tasks" and parts[2] == "container_artifacts":
        return parts[1], "container_artifact"
    if len(parts) >= 2 and parts[0] == "verifier":
        match = re.match(r"^tb21-(?P<task>.+?)-codex-", root.name)
        return (match.group("task") if match else root.name), "direct"
    return None, "unknown"


def parse_ctrf(ctrf_path: Path) -> tuple[int, tuple[str, ...]]:
    if not ctrf_path.exists():
        return 0, ()
    try:
        data = json.loads(ctrf_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive path for corrupt logs.
        return 0, (f"CTRFPARSE:{exc}",)
    tests = data.get("results", {}).get("tests") or data.get("tests") or []
    passed = 0
    failed: list[str] = []
    for item in tests:
        name = item.get("name") or item.get("testName") or item.get("title") or "unknown"
        status = str(item.get("status") or item.get("outcome") or "").lower()
        if status in {"passed", "pass"}:
            passed += 1
        elif status in {"failed", "fail", "error"}:
            failed.append(str(name))
    return passed, tuple(failed)


def collect_records(roots: Iterable[Path]) -> list[RewardRecord]:
    records: list[RewardRecord] = []
    for root in roots:
        for reward_path in sorted(root.rglob("verifier/reward.txt")):
            task, kind = task_from_reward_path(root, reward_path)
            if task is None:
                continue
            reward = reward_path.read_text(encoding="utf-8", errors="replace").strip()
            passed, failed = parse_ctrf(reward_path.parent / "ctrf.json")
            records.append(
                RewardRecord(
                    root=root,
                    task=task,
                    reward=reward,
                    reward_path=reward_path,
                    failed_tests=failed,
                    passed_tests=passed,
                    kind=kind,
                )
            )
    return records


def canonical_records(records: Iterable[RewardRecord]) -> list[RewardRecord]:
    """Prefer task/direct verifier records over container-artifact duplicates."""

    grouped: dict[tuple[Path, str], list[RewardRecord]] = defaultdict(list)
    for record in records:
        grouped[(record.root, record.task)].append(record)

    priority = {"task": 0, "direct": 1, "container_artifact": 2, "unknown": 3}
    selected = []
    for items in grouped.values():
        selected.append(sorted(items, key=lambda r: (priority.get(r.kind, 9), str(r.reward_path)))[0])
    return sorted(selected, key=lambda r: (r.task, r.root.name))


def disposition(task: str) -> tuple[str, str]:
    return DISPOSITION.get(task, ("unclassified", "Needs manual HTD screening."))


def short_tests(tests: tuple[str, ...], limit: int = 3) -> str:
    if not tests:
        return "-"
    shown = list(tests[:limit])
    if len(tests) > limit:
        shown.append(f"+{len(tests) - limit} more")
    return "<br>".join(shown)


def render_markdown(records: list[RewardRecord], roots: list[Path], runs_roots: list[Path]) -> str:
    canonical = canonical_records(records)
    failures = [record for record in canonical if record.failed]
    passes = [record for record in canonical if not record.failed]
    unique_tasks = sorted({record.task for record in canonical})
    disposition_counts = Counter(disposition(record.task)[0] for record in failures)
    unclassified_count = disposition_counts.get("unclassified", 0)

    lines = [
        "# Codex GPT-5.5 Failure Pool Audit",
        "",
        "This report is generated from local Harbor verifier outputs. It does not",
        "launch Docker, Harbor, or model calls.",
        "",
        "## Scope",
        "",
        "- Run roots searched:",
    ]
    for runs_root in runs_roots:
        lines.append(f"  - `{runs_root}`")
    lines.extend(
        [
        f"- Codex + GPT-5.5 run roots scanned: `{len(roots)}`",
        f"- Canonical task records: `{len(canonical)}`",
        f"- Unique task names: `{len(unique_tasks)}`",
        f"- Canonical reward failures: `{len(failures)}`",
        f"- Canonical reward passes: `{len(passes)}`",
        f"- Unclassified reward failures: `{unclassified_count}`",
            "",
            "## Failure Disposition Counts",
            "",
            "| Disposition | Count |",
            "| --- | ---: |",
        ]
    )
    for label, count in sorted(disposition_counts.items()):
        lines.append(f"| `{label}` | {count} |")
    if not disposition_counts:
        lines.append("| `none` | 0 |")

    lines.extend(
        [
            "",
            "## Canonical Failures",
            "",
            "| Task | Reward | Failed verifier tests | Source run | Current disposition | Note |",
            "| --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for record in failures:
        label, note = disposition(record.task)
        lines.append(
            "| `{task}` | `{reward}` | {tests} | `{root}` | `{label}` | {note} |".format(
                task=record.task,
                reward=record.reward,
                tests=short_tests(record.failed_tests),
                root=record.root.name,
                label=label,
                note=note,
            )
        )

    lines.extend(
        [
            "",
            "## Accepted Pending Candidates",
            "",
            "These are the currently clean next candidates for Kimi reruns once endpoint",
            "preflight is green:",
            "",
            "- `make-mips-interpreter`",
            "- `make-doom-for-mips`",
            "",
            "Run the queued two-method reruns with:",
            "",
            "```bash",
            "scripts/run_candidate_kimi_reruns.sh --dry-run",
            "scripts/run_candidate_kimi_reruns.sh",
            "```",
            "",
            "## Notes",
            "",
            "- `task` records are preferred over `container_artifact` duplicate logs.",
            "- `unclassified` means the task still needs manual HTD screening before it",
            "  should be promoted to a card or rerun. This audit currently has no",
            "  unclassified canonical failures.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runs-root",
        type=Path,
        action="append",
        help=(
            "Harbor runs root to scan. May repeat. Defaults to "
            "/Volumes/SSD/terminal-bench-harbor/harbor/runs."
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    runs_roots = args.runs_root or list(DEFAULT_RUNS_ROOTS)
    roots = codex_gpt55_roots(runs_roots)
    records = collect_records(roots)
    markdown = render_markdown(records, roots, runs_roots)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
