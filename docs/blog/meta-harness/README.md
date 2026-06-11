# Meta-Harness Reproduction Notes

This folder collects blog-style notes from the Kimi Code + Meta-Harness
Terminal-Bench 2.1 reproduction. Each note points to expanded raw evidence under
[`../raw_logs/meta-harness/`](../raw_logs/meta-harness/README.md): Harbor trial
directories, agent trajectories, prompts, generated artifacts, verifier stdout,
and reward files.

The current audited sweep result is:

```text
without Meta-Harness: 33/89
with Meta-Harness:    33+10/89 = 43/89
```

Important evaluation boundary: the `with Meta-Harness` condition is not a
blind rerun with the same information budget. It is a failure-informed repair
protocol: the next Kimi Code run receives a prior-failure brief, verifier tail,
and environment context. Therefore the result should be read as "how many
previous failures can be recovered when the harness feeds back structured
failure evidence," not as a claim that the base model solved the same prompt
from scratch. If the brief is manually curated, that curation is part of the
harness condition and must be reported.

Harness and model:

- Harness: Harbor / Terminal-Bench 2.1 proxy tasks.
- Agent adapter: `harbor_adapters.kimi_code_host_agent:KimiCodeHostAgent`.
- Model: `kimi-for-coding`.
- Prior failure source: `claude-code + kimi-k2.6` runs from
  `tb21-kimi-k26-local-019e737a-colima16g-proxy`.

The four main notes are useful examples for explaining how Meta-Harness changes
the run context and trajectory:

| Note | Core evidence |
| --- | --- |
| [`cancel-async-tasks`](cancel-async-tasks.md) | Kimi Code without Meta-Harness fails 4/4 on the cancellation edge; Kimi Code with Meta-Harness passes 4/4. |
| [`sanitize-git-repo`](sanitize-git-repo.md) | The repair brief names the nested escaped-token failure; the Meta-Harness run preserves the base commit and passes 3/3 tests. |
| [`kv-store-grpc`](kv-store-grpc.md) | The without run still routes localhost gRPC through the proxy; the Meta-Harness run patches proxy bypass before verification and passes 7/7. |
| [`git-leak-recovery`](git-leak-recovery.md) | The Meta-Harness rerun recovers the secret, removes unreachable secret objects, and passes 5/5 verifier tests. |

There is also a control note:

| Note | Interpretation |
| --- | --- |
| [`query-optimize`](query-optimize-control.md) | Claude Code's original harness/model row failed; Kimi Code's harness/model row passed even without Meta-Harness. This is not clean evidence that Meta-Harness caused the pass. |

For aggregate data, see:

- Sweep report:
  [`REPORT.md`](../../case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/REPORT.md)
- 89-task audit:
  [`tb21_89_audit.csv`](../../case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/tb21_89_audit.csv)
- Token/latency metrics:
  [`metrics_task_pairs.csv`](../../case-studies/kimi-code-tb21-metaharness-sweep-2026-06-10/metrics_task_pairs.csv)
