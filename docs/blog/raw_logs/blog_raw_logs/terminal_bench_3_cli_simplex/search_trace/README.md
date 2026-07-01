# `cli-2ph-simplex` Search Trace Evidence

This directory makes the case-study search table directly auditable. Each row
links a search transition to the raw artifact that showed the critical error
step and to the state diff that implemented the next repair.

| Search step | Critical error step located | Raw evidence | Resulting verifier footprint |
| --- | --- | --- | --- |
| `s0_baseline` | First TD artifact still failed; the hint was too broad to identify a committed wrong transition. | [`TD trajectory`](../harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/trajectory.json), [`TD transcript`](../harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/agent/claude-code.txt), [`TD verifier stdout`](../harbor_runs/tb3-cli-2ph-simplex-claude-code-claude-opus-4-7-td-icl-20260701/cli-2ph-simplex__2QHadn3/verifier/test-stdout.txt) | `63 failed, 40 passed` |
| `s1_phase1_sign` | Phase 1 artificial objective sign was inverted in `build_initial_tableau`. | [`ge_bound_respected probe`](../search_probes/ge.txt), [`s0 -> s1 diff`](s0_to_s1_phase1_sign.diff), [`reward path card`](../teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md) | `12 failed, 91 passed` |
| `s2_artificial_cleanup` | Zero-valued artificial basics were dropped instead of pivoted out before removing artificial columns. | [`bounded_fuzz_2 probe`](../search_probes/fuzz2.txt), [`s1 -> s2 diff`](s1_to_s2_artificial_cleanup.diff), [`reward path card`](../teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md) | `7 failed, 96 passed` |
| `s3_protocol_best_effort` | Remaining failures were protocol mismatches: Decimal rounding, literal traceback behavior, and infeasible best-effort output. | [`s2 -> s3 diff`](s2_to_s3_protocol_best_effort.diff), [`debug-action v2`](../teacher_cards/tb3-cli-2ph-simplex-debug-action-v2.md), [`reward path card`](../teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md) | `2 failed, 101 passed` |
| `s4_global_shortest` | `--initial_pivots` minimized Phase 1 and Phase 2 locally rather than the global logged pivot count. | [`s3 -> s4 diff`](s3_to_s4_global_shortest.diff), [`reward path card`](../teacher_cards/tb3-cli-2ph-simplex-mcts-reward1-path.md) | `103 passed` when mounted as `/app` |

The diffs are generated from the raw searched states under
`/data/harbor/td_artifacts/cli_mcts_search/states/` and exclude Python bytecode
caches. They are not hand-written summaries.
