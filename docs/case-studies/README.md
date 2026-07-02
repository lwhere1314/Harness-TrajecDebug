# Case Studies

This is the entry point for Harness-TrajecDebug case studies, report snapshots,
metrics, repair briefs, and raw evidence bundles.

Use this directory when you need evidence for a claim. Use `docs/blog/` when
you want a shorter narrative explanation of a specific mechanism.

## Main Reports

| Case study | Start here | Evidence |
| --- | --- | --- |
| Kimi Code TB2.1 Meta-Harness sweep | [`kimi-code-tb21-metaharness-sweep-2026-06-10/REPORT.md`](kimi-code-tb21-metaharness-sweep-2026-06-10/REPORT.md) | Metrics, task-pair summaries, raw-log archives, and repair briefs. |
| Cancel-async-tasks 4x reproduction | [`kimi-code-cancel-async-tasks-metaharness-2026-06-10/REPORT.md`](kimi-code-cancel-async-tasks-metaharness-2026-06-10/REPORT.md) | 4x without-context versus 4x with-context reproduction, diffs, commands, and trial summary. |

## Fast Links

| Need | Link |
| --- | --- |
| Sweep metrics | [`kimi-code-tb21-metaharness-sweep-2026-06-10/metrics_summary.json`](kimi-code-tb21-metaharness-sweep-2026-06-10/metrics_summary.json) |
| Task-pair metrics | [`kimi-code-tb21-metaharness-sweep-2026-06-10/metrics_task_pairs.csv`](kimi-code-tb21-metaharness-sweep-2026-06-10/metrics_task_pairs.csv) |
| Repair briefs | [`kimi-code-tb21-metaharness-sweep-2026-06-10/repair-briefs/`](kimi-code-tb21-metaharness-sweep-2026-06-10/repair-briefs/) |
| Raw sweep logs | [`kimi-code-tb21-metaharness-sweep-2026-06-10/raw-logs/`](kimi-code-tb21-metaharness-sweep-2026-06-10/raw-logs/) |
| Cancel-async commands | [`kimi-code-cancel-async-tasks-metaharness-2026-06-10/commands.sh`](kimi-code-cancel-async-tasks-metaharness-2026-06-10/commands.sh) |
| Cancel-async prompt/code diffs | [`kimi-code-cancel-async-tasks-metaharness-2026-06-10/diffs/`](kimi-code-cancel-async-tasks-metaharness-2026-06-10/diffs/) |

## Related Narrative Case Studies

These live under `docs/blog/` because they read more like mechanism writeups
than archive indexes:

| Mechanism | Entry |
| --- | --- |
| Runtime Debug-Action on `query-optimize` | [`../blog/query-optimize-runtime-debug-action.md`](../blog/query-optimize-runtime-debug-action.md) |
| Joint-failure lifting on `sanitize-git-repo` | [`../blog/sanitize-git-repo-joint-failure-lifting.md`](../blog/sanitize-git-repo-joint-failure-lifting.md) |
| Clean-preservation diagnosis on `filter-js-from-html` | [`../blog/filter-js-from-html-clean-preservation.md`](../blog/filter-js-from-html-clean-preservation.md) |
| Axis-critical diagnosis on `raman-fitting` | [`../blog/raman-fitting-axis-critical-step.md`](../blog/raman-fitting-axis-critical-step.md) |
| Forward-API critical step on `pytorch-model-recovery` | [`../blog/pytorch-model-recovery-forward-api-critical-step.md`](../blog/pytorch-model-recovery-forward-api-critical-step.md) |
| Algorithm flow overview | [`../blog/trajectorydebug-algorithm-flow.md`](../blog/trajectorydebug-algorithm-flow.md) |

Raw material for the query-optimize blog bundle starts at
[`../blog/raw_logs/blog_raw_logs/README.md`](../blog/raw_logs/blog_raw_logs/README.md).
