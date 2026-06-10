# Codex GPT-5.5 Failure Pool Audit

This report is generated from local Harbor verifier outputs. It does not
launch Docker, Harbor, or model calls.

## Scope

- Run roots searched:
  - `/Volumes/SSD/terminal-bench-harbor/harbor/runs`
  - `/Users/hugo/Projects/Harness-TrajecDebug/artifacts/harbor-runs`
- Codex + GPT-5.5 run roots scanned: `16`
- Canonical task records: `56`
- Unique task names: `51`
- Canonical reward failures: `13`
- Canonical reward passes: `43`
- Unclassified reward failures: `0`

## Failure Disposition Counts

| Disposition | Count |
| --- | ---: |
| `accepted_pending_kimi` | 2 |
| `closed_loop` | 5 |
| `closed_loop_extension` | 1 |
| `deprioritized` | 1 |
| `rejected` | 2 |
| `superseded_by_clean_pass` | 2 |

## Canonical Failures

| Task | Reward | Failed verifier tests | Source run | Current disposition | Note |
| --- | ---: | --- | --- | --- | --- |
| `filter-js-from-html` | `0` | test_outputs.py::test_clean_html_unchanged | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `closed_loop` | One of the verified HTD cases; both oracle_grounded and debug_action reruns passed. |
| `install-windows-3.11` | `0` | test_outputs.py::test_qemu_running_with_correct_params | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `deprioritized` | QEMU-heavy; keep for later after a timeout-aware harness plan exists. |
| `make-doom-for-mips` | `0` | test_outputs.py::test_vm_execution | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `accepted_pending_kimi` | Tracked cards and oracle sanity are ready; Kimi reruns wait on endpoint availability. |
| `make-mips-interpreter` | `0` | test_outputs.py::test_vm_execution | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `accepted_pending_kimi` | Tracked cards and oracle sanity are ready; Kimi reruns wait on endpoint availability. |
| `mteb-leaderboard` | `0` | - | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `rejected` | Likely fixed leaderboard snapshot / fixed-answer leakage risk. |
| `nginx-request-logging` | `0` | test_outputs.py::test_nginx_running<br>test_outputs.py::test_index_page_content<br>test_outputs.py::test_custom_404_page<br>+2 more | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `rejected` | Historical failure is proxy/verifier contamination rather than clean agent-process error. |
| `overfull-hbox` | `0` | test_outputs.py::test_input_file_matches | `tb21-supp-real-fails-codex-gpt55-host-20260610-joint-search-3` | `closed_loop_extension` | Sixth verified case; local no-network verifier was used to remove apt/proxy noise. |
| `pytorch-model-recovery` | `0` | test_outputs.py::test_model_loss | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `closed_loop` | One of the verified HTD cases; both oracle_grounded and debug_action reruns passed. |
| `raman-fitting` | `0` | test_outputs.py::test_G_Peak<br>test_outputs.py::test_2D_Peak | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `closed_loop` | One of the verified HTD cases; both oracle_grounded and debug_action reruns passed. |
| `sam-cell-seg` | `0` | test_outputs.py::test_mask_alignment | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `closed_loop` | One of the verified HTD cases; both oracle_grounded and debug_action reruns passed. |
| `sanitize-git-repo` | `0` | test_outputs.py::test_no_other_files_changed | `tb21-k26-true-fails-codex-gpt55-host-20260603-clean4` | `closed_loop` | One of the verified HTD cases; both oracle_grounded and debug_action reruns passed. |
| `train-fasttext` | `0` | - | `tb21-train-fasttext-codex-gpt55-host-20260603T130932` | `superseded_by_clean_pass` | Early failed Codex runs were superseded by later clean Codex + GPT-5.5 pass / case-study traces. |
| `train-fasttext` | `0` | - | `tb21-train-fasttext-codex-gpt55-host-20260603T155328-rerun` | `superseded_by_clean_pass` | Early failed Codex runs were superseded by later clean Codex + GPT-5.5 pass / case-study traces. |

## Accepted Pending Candidates

These are the currently clean next candidates for Kimi reruns once endpoint
preflight is green:

- `make-mips-interpreter`
- `make-doom-for-mips`

Run the queued two-method reruns with:

```bash
scripts/run_candidate_kimi_reruns.sh --dry-run
scripts/run_candidate_kimi_reruns.sh
```

## Notes

- `task` records are preferred over `container_artifact` duplicate logs.
- `unclassified` means the task still needs manual HTD screening before it
  should be promoted to a card or rerun. This audit currently has no
  unclassified canonical failures.
