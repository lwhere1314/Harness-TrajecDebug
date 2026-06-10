# Closed-Loop Case Summary

This note is the handoff summary for the currently verified Harness-TrajecDebug
case set.

Definition used here:

```text
historical Codex + GPT-5.5 reward = 0.0
+ HTD critical-step card / Debug-Action card
+ Claude Code + Kimi-k2.6 rerun
+ Harbor / Terminal-Bench task-verifier reward = 1.0
```

Under that definition, the project currently has **6 closed-loop cases**.

| Case | Historical Codex + GPT-5.5 failure | HTD critical step | Kimi-k2.6 rerun evidence |
| --- | --- | --- | --- |
| `sanitize-git-repo` | Over-solved by mutating git history and broke the reference-commit check. | Bound the task to working-tree secret removal while preserving git history. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; official verifier `3/3` passed. |
| `filter-js-from-html` | Removed JavaScript but rewrote clean HTML, failing the clean-preservation gate. | Treat clean preservation as binding: remove only executable constructs and event handlers. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; official verifier `2/2` passed. |
| `sam-cell-seg` | Preserved the CSV schema but had one weak mask-alignment margin. | Satisfy schema preservation and MobileSAM mask quality together, not one at the expense of the other. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; official verifier `9/9` passed. |
| `raman-fitting` | Wrote schema-valid JSON on the wrong x-axis scale after fitting raw instrument coordinates. | Convert `raw_x` using `x = 1e7 / raw_x`, then fit only the converted G and 2D Raman windows. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; official verifier `3/3` passed. |
| `pytorch-model-recovery` | Built a TorchScript artifact with a one-input `forward(self, src)` while the verifier calls `model(src, tgt)`. | Reconstruct the verifier-compatible two-input Transformer API and tune only `output_layer`. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; official verifier `5/5` passed. |
| `overfull-hbox` | Removed all `Overfull \hbox` warnings but used an illegal synonym substitution, `unknown -> new`. | Treat the task as constrained token substitution: every changed word must stay inside the original word's `synonyms.txt` family before trusting the clean LaTeX log. | `oracle_grounded` reward `1.0`; `debug_action` reward `1.0`; local no-network verifier reported `PASS: all verifier gates passed`. |

## Evidence Paths

The successful rerun results are under:

```text
runs/harbor_icl_baseline/harbor_runs_oracle_grounded/
runs/harbor_icl_baseline/harbor_runs_joint_failure/
```

The hand-authored cards are under:

```text
experiments/harbor_icl_baseline/oracle_grounded_cards/
experiments/harbor_icl_baseline/joint_failure_cards/
```

Related case-study notes:

- `docs/blog/sanitize-git-repo-joint-failure-lifting.md`
- `docs/blog/filter-js-from-html-clean-preservation.md`
- `docs/blog/sam-cell-seg-complementary-failure-lifting.md`
- `docs/blog/raman-fitting-axis-critical-step.md`
- `docs/blog/pytorch-model-recovery-forward-api-critical-step.md`

## Current Search Status

The Codex + GPT-5.5 search pool currently covers 51 unique Terminal-Bench 2.1
tasks. Codex passed 40 and failed 11. Some failures are not counted as primary
closed-loop cases because they are QEMU-heavy, verifier-infra contaminated, or
not yet lifted by Kimi reruns.

The next accepted/rejected candidates are tracked in
[`candidate-search-status.md`](candidate-search-status.md). Current accepted
but not yet closed candidates are `make-mips-interpreter` and
`make-doom-for-mips`; both are waiting on endpoint availability before Kimi
reruns can be launched.

`overfull-hbox` is now included as the sixth case. Its original copied verifier
depended on `apt/curl/uvx`, which repeatedly introduced local proxy and mirror
noise. The final successful runs use a no-network verifier script that
implements the same protected-file, compilation, no-overfull, and synonym-family
gates from `tests/test_outputs.py` and writes the standard Harbor reward file.
The tracked copy is
`experiments/harbor_icl_baseline/verifier_patches/overfull-hbox-test.sh`.
