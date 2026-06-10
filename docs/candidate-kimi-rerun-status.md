# Candidate Kimi Rerun Status

This report summarizes the accepted pending candidates for the
two-method Harness-TrajecDebug rerun queue. It is generated from local
Harbor result files and does not launch model calls.

- Closed-loop candidates in this queue: `0`
- Closed tasks: `none`

| Task | Context | Status | Reward | Trial | Verifier | Note |
| --- | --- | --- | ---: | --- | --- | --- |
| `make-mips-interpreter` | `oracle_grounded` | `not_started` | - | - | - | Expected job directory does not exist. |
| `make-mips-interpreter` | `debug_action` | `not_started` | - | - | - | Expected job directory does not exist. |
| `make-doom-for-mips` | `oracle_grounded` | `incomplete` | - | `make-doom-for-mips__X9UcJJ4` | - | Job directory exists but Harbor did not write a result.json. |
| `make-doom-for-mips` | `debug_action` | `not_started` | - | - | - | Expected job directory does not exist. |

Run or rerun the queue with:

```bash
scripts/run_candidate_kimi_reruns.sh --dry-run
scripts/run_candidate_kimi_reruns.sh
```

`run_candidate_kimi_reruns.sh` regenerates this report after a
non-dry-run queue completes. You can also rerun this summarizer
directly when inspecting existing Harbor outputs.
