# TB2.1 Kimi-k2.6 Raw Log Manifest

Generated on 2026-06-10 21:36 CST from local Harbor result files.

## Final Score Source

- Final computed number: `without TrajectoryDebug = 38/89`, `with TrajectoryDebug = 46/89`, `m = 8`.
- Recompute command:

```bash
PYTHONPATH=src python3 scripts/compute_tb21_kimi_td_lift.py
```

## Local Raw Log Roots

These roots are intentionally not committed because they contain large raw logs
and may include provider/runtime environment details.

| Source | Local path | Size | Integrity |
| --- | --- | ---: | --- |
| Primary 89-task no-TD baseline | `/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy` | `24G` | `state.json sha256 c9104a4539dfb871e8bb45a99f68080cfd65e8cb4d56af35b804a47b09e42b38` |
| Supplemental no-TD baseline fills | `/Volumes/SSD/terminal-bench-harbor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts` | `4.1G` | `state.json sha256 a50bdf53c254b0c234d7ed5a124f20de25c93e3722f33e16c8596e13013bd1e2` |
| TrajectoryDebug and prompt-safe reruns | `/Users/hugo/Documents/Harness-TrajecDebug/runs/harbor_icl_baseline` | `68M` | `tb21_kimi_k26_td_lift.json sha256 46db6833f8cdd585249b571fdb1c4c4497d2e8b40ec958e0e8050d30950cb956` |
| Local archive of TrajectoryDebug and prompt-safe reruns | `/Users/hugo/Documents/Harness-TrajecDebug/runs/raw_log_archives/tb21-kimi-k26-td-lift-20260610T213641.tar.gz` | `35M` | `sha256 f3bfc04f037da39261f8eb7a246a3b4ce8733e11b498129d38f4fca18165aab3` |

Committed report integrity:

- `docs/tb21-kimi-k26-trajectorydebug-lift.md`: `sha256 e9325b75b0ce46ce0933843ebfdd2cf8e717a6601defc530e6c66cbea592d8b0`

## Main TD Agent Lifts

The main lift count includes only Claude Code + Kimi-k2.6 model-agent TD runs
with official reward `1.0` and non-empty `agent_result` metrics.

| Task | Result path | sha256 |
| --- | --- | --- |
| `cancel-async-tasks` | `runs/harbor_icl_baseline/harbor_runs/htd-icl-debug_trajectory-cancel-async-tasks-kimi-k2-6/cancel-async-tasks__7rdwHjo/result.json` | `d3d06c03848e66632ac54268e061fb3b4b5887c6477cf695d9a6c95e03fdb544` |
| `filter-js-from-html` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-filter-js-from-html-kimi-k2-6/filter-js-from-html__J2ZCHGR/result.json` | `e128edea12706d865db2f4515101bbd9a56772ca5025e7c7317327a4394779b4` |
| `gcode-to-text` | `runs/harbor_icl_baseline/harbor_runs_sdk_live/htd-dynamic-icl-sdk_live-debug_action-gcode-to-text-kimi-k2-6/gcode-to-text__XNoLtR8/result.json` | `3bfb96dd7bc893d4a56f30eb3cd85a6fdeecc7d8f3c105d693d384325b564fda` |
| `overfull-hbox` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-overfull-hbox-kimi-k2-6/overfull-hbox__pF92gR3/result.json` | `57cc8db9b006fef8f17d69ce2b3a68c9849dc2f72d26aba14b95c9b4ba2b2a3a` |
| `query-optimize` | `runs/harbor_icl_baseline/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/result.json` | `740459759a3dd03aec9747765f6753e192579c52ef09f62075d59e73bc7977b0` |
| `raman-fitting` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-raman-fitting-kimi-k2-6/raman-fitting__RFdou7e/result.json` | `e56e9bf83d84ebdd48839b43a70a46038706204884d0d52e67d8538f1c58f06d` |
| `sam-cell-seg` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-sam-cell-seg-kimi-k2-6/sam-cell-seg__4gAvptg/result.json` | `7392be9411e7d08bac958b7efd28a7bbc5daa8a9d6985cc9ba796ee9218b1a34` |
| `sanitize-git-repo` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-sdk_live-debug_action-sanitize-git-repo-kimi-k2-6/sanitize-git-repo__JPnpGsH/result.json` | `12b890bdf649810944713feee18c448647941a3ddeb2e5c0aef4614e42af2291` |

## Prompt-Safe No-TD Baseline Fill

`pytorch-model-recovery` was the only remaining invalid primary/supplemental
baseline slot. The invalid record was caused by the task instruction beginning
with `- You are...`, which the Claude CLI parsed as an option before reaching
the model. The prompt-safe rerun changed only that leading hyphen and did not
inject TrajectoryDebug context.

| Task | Status | Result path | sha256 |
| --- | --- | --- | --- |
| `pytorch-model-recovery` | `reward=1.0`, counted as no-TD baseline pass | `runs/harbor_icl_baseline/harbor_runs_no_td_baseline/tb21-pytorch-model-recovery-no-td-prompt-safe-kimi-k2-6/pytorch-model-recovery__TAngPJo/result.json` | `9484d4d0410533fdb8a8f42b8d697f4f337853cad7a7d916b736eb31b6928426` |

Invalid prompt-safe attempt retained locally:

- `/Users/hugo/Documents/Harness-TrajecDebug/runs/harbor_icl_baseline/harbor_runs_no_td_baseline/_archived/tb21-pytorch-model-recovery-no-td-prompt-safe-kimi-k2-6-invalid-x64-20260610T211038`

## Candidate Attempts Not Counted

These attempts are preserved for audit but do not affect the final score.

| Candidate | Outcome | Result path | sha256 |
| --- | --- | --- | --- |
| `make-mips-interpreter / oracle_grounded` | `reward=0.0`, `AgentTimeoutError`, not counted | `runs/harbor_icl_baseline/harbor_runs_oracle_grounded/htd-dynamic-icl-prelude-oracle_grounded-make-mips-interpreter-kimi-k2-6/make-mips-interpreter__krUDou6/result.json` | `e1255e14a9a85f2ef96828f270d2dbdbeca512335cc01b146f75799766582cdd` |
| `make-mips-interpreter / debug_action` | stopped before official result to unblock the no-TD baseline rerun | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-make-mips-interpreter-kimi-k2-6` | `no official result` |

## Expected Files Per Trial

For included local Harbor trials, raw evidence is preserved under each trial
directory:

- `result.json`
- `agent/claude-code.txt`
- `agent/trajectory.json` where available
- `verifier/test-stdout.txt`
- `verifier/reward.txt` where available
- `trial.log`, `job.log`, and `runner.log`
