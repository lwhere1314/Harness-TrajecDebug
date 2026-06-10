# Case Study: Complementary Failure Lifting on `sam-cell-seg`

This case study records the third joint-failure lifting result for
Harness-TrajecDebug.

The interesting part is not that an oracle-grounded hint can rescue the task.
The stronger result is that two failed historical traces exposed complementary
verifier gates, and their combined failure evidence was enough to synthesize a
Debug-Action card that made a fresh Claude Code + `kimi-k2.6` run pass.

```text
Kimi-k2.6 failed: good mask quality, broken CSV schema
GPT-5.5 failed:  good CSV schema, weak mask-alignment margin
HTD card:        preserve schema and raise mask-quality margin at once
Rerun:           reward 1.0, 9/9 verifier tests passed
```

## Task

`sam-cell-seg` asks the agent to write `/app/convert_masks.py`. The script must
convert histopathology cell masks from rectangles to polylines using MobileSAM.

The script receives:

- `--weights_path`
- `--output_path`
- `--rgb_path`
- `--csv_path`

The output CSV must match the input schema while updating only the geometry
columns:

- `xmin`
- `ymin`
- `xmax`
- `ymax`
- `coords_x`
- `coords_y`

The verifier checks several independent contracts: the Python file exists, the
script runs, the output CSV exists, the table shape and columns are correct, all
masks are non-rectangular, the masks align with the reference MobileSAM output,
polylines do not overlap, each mask is contiguous, and coordinate lists are
flat parseable lists.

## Historical Failures

Harness-TrajecDebug used two failed traces:

| Run | Reward | Verifier footprint |
| --- | ---: | --- |
| Claude Code + Kimi-k2.6 | `0.0` | failed `test_csv_shape_cols`; output table was `(32, 10)` while verifier expected `(32, 11)` |
| Codex + GPT-5.5 | `0.0` | failed `test_mask_alignment`; one mask had IoU `0.4927`, below the `0.5` threshold |

The two failures are complementary. Kimi found a mask-generation route that was
good enough geometrically, but it violated the artifact contract by dropping the
leading empty/index column. Codex preserved the schema, but its mask-selection
route left too little alignment margin.

Harness-TrajecDebug therefore labeled the critical action boundary as:

> Preserve the input table shape exactly while using MobileSAM-guided mask
> refinement with enough alignment margin; do not trade schema correctness
> against mask quality.

## Stage A: Oracle-Grounded Card

The oracle-grounded card used the oracle only to define the repair boundary:
solve the task as MobileSAM mask refinement under a strict CSV artifact
contract.

The injected card did not paste a finished solution. It constrained the agent to
preserve every original column, load MobileSAM `vit_t` on CPU, refine every row
from its bounding box, suppress overlaps, keep one contiguous component per
mask, extract external contours, and write the copied DataFrame with
`index=False`.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_oracle_grounded/
  htd-dynamic-icl-prelude-oracle_grounded-sam-cell-seg-kimi-k2-6/
    sam-cell-seg__B8ff4qe

inject_mode = prelude
context_variant = oracle_grounded
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 9/9 tests passed
```

This confirmed that the critical-step framing was executable.

## Stage B: Oracle-Free Debug-Action

The Debug-Action card removed oracle access. Its source signal was only the two
failed verifier footprints:

- Kimi-k2.6: mask geometry passed, schema failed.
- Codex + GPT-5.5: schema passed, mask alignment failed.

The card asked the agent to build `/app/convert_masks.py` around the joint
constraint:

1. read the CSV and preserve every original column;
2. update only the six geometry columns;
3. load MobileSAM `vit_t` on CPU and call `predictor.set_image` once;
4. avoid pure highest-score mask selection by combining SAM score with
   consistency against the original row mask or box;
5. suppress overlaps, keep the largest contiguous component, and extract an
   external contour;
6. serialize coordinates as flat parseable Python list strings and save with
   `index=False`.

Result:

```text
trial: runs/harbor_icl_baseline/harbor_runs_joint_failure/
  htd-dynamic-icl-prelude-debug_action-sam-cell-seg-kimi-k2-6/
    sam-cell-seg__4gAvptg

inject_mode = prelude
context_variant = debug_action
target = Claude Code + kimi-k2.6
reward = 1.0
verifier = 9/9 tests passed
```

The official verifier passed:

```text
PASSED test_python_file_exists
PASSED test_run_script
PASSED test_csv_output_exists
PASSED test_csv_shape_cols
PASSED test_masks_are_no_longer_rect
PASSED test_mask_alignment
PASSED test_no_polyline_overlaps
PASSED test_single_contiguous_mask_per_cell
PASSED test_coords_are_flat_lists
```

## Why This Case Matters

This is stronger than teacher-success replay. There was no successful teacher
trace in the compared pair. Instead, each failed trace exposed a different
piece of the task contract:

- one trace showed that MobileSAM mask quality was reachable;
- the other showed that the CSV schema contract must not be relaxed.

Harness-TrajecDebug converted that contrast into an actionable ICL example. The
result supports the project's central hypothesis:

> Debug-Trajectory examples are useful because they select process evidence,
> not just successful outcomes.

The case is still same-task repair, so it should not be reported as held-out
generalization. But it is a clean mechanism datapoint: complementary failed
traces can contain enough structure to rescue a fresh small-agent run.
