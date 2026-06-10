# TB2.1 Kimi-k2.6 TrajectoryDebug Lift

This report is generated from local Harbor result files. The main lift
counts only Claude Code + Kimi-k2.6 model-agent runs; deterministic
artifact-closure checks are listed separately and excluded from the main
score.

## Final Number

- without TrajectoryDebug: `38/89`
- with TrajectoryDebug: `46/89`
- effective lift `m`: `8` tasks

## Baseline Coverage

- primary baseline passes: `33/89`
- infra/no-agent baseline fills used: `10`
- final baseline valid tasks: `89/89`

## Baseline Fill Details

Baseline fills are used only where the primary 89-task run did not
produce a valid model-agent result. `prompt_safe_no_td` removes only the
leading-hyphen CLI parsing hazard from the task instruction; it does not
inject any TrajectoryDebug context.

| Task | Fill source | Status | Reward | Result |
| --- | --- | --- | ---: | --- |
| `build-pov-ray` | `supplemental_no_td` | `pass` | `1.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-build-pov-ray-claude-code-k6/build-pov-ray__AAyqAKT/result.json` |
| `crack-7z-hash` | `supplemental_no_td` | `pass` | `1.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-crack-7z-hash-claude-code-k6/crack-7z-hash__zNA2dJd/result.json` |
| `db-wal-recovery` | `supplemental_no_td` | `fail` | `0.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-db-wal-recovery-claude-code-k6/db-wal-recovery__yyq4rrB/result.json` |
| `extract-elf` | `supplemental_no_td` | `pass` | `1.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-extract-elf-claude-code-k6/extract-elf__RyPrLLa/result.json` |
| `gpt2-codegolf` | `supplemental_no_td` | `fail` | `0.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-gpt2-codegolf-claude-code-k6/gpt2-codegolf__YVkCyum/result.json` |
| `install-windows-3.11` | `supplemental_no_td` | `fail` | `0.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-install-windows-3.11-claude-code-k6/install-windows-3.11__NmXw2sf/result.json` |
| `make-doom-for-mips` | `supplemental_no_td` | `fail` | `0.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-make-doom-for-mips-claude-code-k6/make-doom-for-mips__JJWpUMs/result.json` |
| `make-mips-interpreter` | `supplemental_no_td` | `fail` | `0.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-make-mips-interpreter-claude-code-k6/make-mips-interpreter__gAKSenS/result.json` |
| `pytorch-model-recovery` | `prompt_safe_no_td` | `pass` | `1.0` | `runs/harbor_icl_baseline/harbor_runs_no_td_baseline/tb21-pytorch-model-recovery-no-td-prompt-safe-kimi-k2-6/pytorch-model-recovery__TAngPJo/result.json` |
| `reshard-c4-data` | `supplemental_no_td` | `pass` | `1.0` | `/Users/hugo/Desktop/super-refactor/harbor/runs/tb21-kimi-k26-local-019e737a-colima16g-proxy-supplemental-artifacts/jobs/tb21-reshard-c4-data-claude-code-k6/reshard-c4-data__ZrtEKA2/result.json` |

## TrajectoryDebug Agent Lifts

| Task | Baseline reward | TD source | TD result |
| --- | ---: | --- | --- |
| `cancel-async-tasks` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs/htd-icl-debug_trajectory-cancel-async-tasks-kimi-k2-6/cancel-async-tasks__7rdwHjo/result.json` |
| `filter-js-from-html` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-filter-js-from-html-kimi-k2-6/filter-js-from-html__J2ZCHGR/result.json` |
| `gcode-to-text` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_sdk_live/htd-dynamic-icl-sdk_live-debug_action-gcode-to-text-kimi-k2-6/gcode-to-text__XNoLtR8/result.json` |
| `overfull-hbox` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-overfull-hbox-kimi-k2-6/overfull-hbox__pF92gR3/result.json` |
| `query-optimize` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_query_baseline/htd-dynamic-icl-sdk_live-debug_action-query-optimize-kimi-k2-6/query-optimize__aRKxGBq/result.json` |
| `raman-fitting` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-raman-fitting-kimi-k2-6/raman-fitting__RFdou7e/result.json` |
| `sam-cell-seg` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-prelude-debug_action-sam-cell-seg-kimi-k2-6/sam-cell-seg__4gAvptg/result.json` |
| `sanitize-git-repo` | `0.0` | `trajectorydebug_agent` | `runs/harbor_icl_baseline/harbor_runs_joint_failure/htd-dynamic-icl-sdk_live-debug_action-sanitize-git-repo-kimi-k2-6/sanitize-git-repo__JPnpGsH/result.json` |

## Closure-Only Successes

These passed by directly materializing Debug-Action artifacts and do not
enter the main Claude Code + Kimi-k2.6 lift count.

| Task | Result |
| --- | --- |
| `break-filter-js-from-html` | `runs/harbor_icl_baseline/harbor_runs_artifact_closure/htd-artifact-closure-debug_action-break-filter-js-from-html/break-filter-js-from-html__AJcBv8N/result.json` |
| `gcode-to-text` | `runs/harbor_icl_baseline/harbor_runs_artifact_closure/htd-artifact-closure-debug_action-gcode-to-text/gcode-to-text__GFqfbpe/result.json` |
| `headless-terminal` | `runs/harbor_icl_baseline/harbor_runs_artifact_closure/htd-artifact-closure-debug_action-headless-terminal/headless-terminal__bpKVDzx/result.json` |
| `query-optimize` | `runs/harbor_icl_baseline/harbor_runs_artifact_closure/htd-artifact-closure-debug_action-query-optimize/query-optimize__FJSkgkr/result.json` |
