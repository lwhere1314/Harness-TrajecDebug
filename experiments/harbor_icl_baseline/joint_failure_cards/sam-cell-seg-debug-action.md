# Harness-TrajecDebug Debug-Action Card: sam-cell-seg

## Source Signal

This card is synthesized from two failed trajectories, not from an oracle
solution:

- Claude Code + Kimi-k2.6 produced MobileSAM masks that passed alignment,
  non-rectangle, non-overlap, contiguity, and flat-coordinate gates, but failed
  `test_csv_shape_cols`: it dropped the leading empty/index column and wrote a
  `(32, 10)` table where the verifier expected `(32, 11)`.
- Codex + GPT-5.5 preserved the schema and produced a runnable script, but
  failed `test_mask_alignment`: one mask had IoU `0.4927`, just below the
  required `0.5`, after a score-only / greedy contour selection path.

The combined terminal footprint is complementary:

```text
Kimi:  good mask geometry  + broken CSV contract
Codex: good CSV contract   + weak mask-alignment margin
```

## Critical Step

The binding decision is to satisfy both contracts at once:

> Preserve the input table shape exactly while using MobileSAM-guided mask
> refinement with enough alignment margin; do not trade schema correctness
> against mask quality.

## Action Boundary

Build `/app/convert_masks.py` around these constraints. Do not spend the run
budget searching the web for MobileSAM/SAM examples; use the direct coding plan
below.

1. Parse all four required args: `--weights_path`, `--output_path`,
   `--rgb_path`, and `--csv_path`.
2. Read the CSV and preserve every original column. Do not drop `Unnamed: 0` or
   a leading empty index column. The safest pattern is `out_df = df.copy()` and
   then update only the six coordinate columns.
3. Load MobileSAM `vit_t` on CPU, call `predictor.set_image(image)` once, and
   use each row's bounding box as the main prompt.
4. Avoid a pure "take the highest SAM score" commitment. Rank candidates by
   both SAM score and consistency with the original row mask / box; after
   overlap suppression, keep the largest valid contiguous component.
5. Export contours as parseable flat numeric lists, such as Python list strings
   (`"[1, 2, 3]"`), and update `xmin`, `ymin`, `xmax`, `ymax` from the final
   contour.
6. Save the copied DataFrame with `index=False`.

## Minimal Coding Plan

Use this API shape directly:

```python
from mobile_sam import SamPredictor, sam_model_registry

sam = sam_model_registry["vit_t"](checkpoint=args.weights_path)
sam.to(device="cpu")
sam.eval()
predictor = SamPredictor(sam)
predictor.set_image(rgb_image)
masks, scores, _ = predictor.predict(
    box=np.array([xmin, ymin, xmax, ymax]),
    multimask_output=True,
)
```

The safe artifact pattern is:

```python
df = pd.read_csv(args.csv_path)
out_df = df.copy()
# update only xmin/ymin/xmax/ymax/coords_x/coords_y
out_df.to_csv(args.output_path, index=False)
```

For mask post-processing, first predict all row masks, then suppress overlaps
with a deterministic policy: order candidate masks by quality / area, subtract
pixels already assigned to earlier masks, keep the largest connected component,
and extract the external contour with `cv2.findContours`. If suppression empties
a row, use that row's largest pre-suppression component rather than a rectangle.

## Avoided Failure Patterns

Do not:

- delete or rename columns while "cleaning" the DataFrame;
- return rectangle fallback contours for rows that need SAM refinement;
- rely only on score-order greedy masks when this creates a thin IoU margin;
- use `/app/correct_output.csv` as an input to the solution script;
- finish after checking only that the script runs.

## Self-Check

If the test resources have been copied into `/app`, run the script once and
check the two historical failure modes before final answer:

```bash
python /app/convert_masks.py \
  --csv_path /app/test_metadata.csv \
  --rgb_path /app/test_img.png \
  --weights_path /app/mobile_sam.pt \
  --output_path /app/test_output.csv

python - <<'PY'
import ast
import pandas as pd
out = pd.read_csv('/app/test_output.csv')
ref = pd.read_csv('/app/correct_output.csv')
assert out.shape == ref.shape, (out.shape, ref.shape)
assert list(out.columns) == list(ref.columns)
for col in ['coords_x', 'coords_y']:
    for value in out[col]:
        parsed = ast.literal_eval(str(value))
        assert parsed and all(isinstance(x, (int, float)) for x in parsed)
print('shape/columns and coordinate serialization look safe')
PY
```

Then run the official verifier. The key repair is not one command; it is the
joint constraint: preserve the artifact schema and keep enough MobileSAM
alignment margin.
