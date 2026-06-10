# Oracle-Grounded Critical-Step Card: sam-cell-seg

## Oracle Ground Truth Signal

The oracle-level signal is not "draw any non-rectangular contour." It is:

- preserve the input CSV schema exactly, including the leading empty/index
  column if it exists;
- use MobileSAM with the provided bounding boxes as prompts;
- refine all rows into one contiguous external polyline per cell;
- suppress overlaps across masks after prediction;
- write only the updated coordinate columns back to the same table shape.

So the critical step is a task-framing decision:

> Treat the task as MobileSAM mask refinement under a strict CSV artifact
> contract, not as a loose contour-generation task.

## Corrective Direction

Use the oracle as a ground-truth constraint on the repair path. Do not spend
budget searching the web for SAM examples; the needed API shape is already
known:

1. Read the input CSV with pandas, but do not drop unnamed or empty index
   columns. The verifier checks that the output has the same shape and columns
   as the reference output.
2. Load MobileSAM through `sam_model_registry["vit_t"]` on CPU, set the image
   once with `SamPredictor.set_image`, and process every row.
3. Convert each row's `(xmin, ymin, xmax, ymax)` into a box prompt. A useful
   implementation can batch boxes or iterate rows, but every row must be
   refined through MobileSAM rather than returning rectangles unchanged.
4. From the predicted masks, keep one contiguous component and export its
   external contour as list-like `coords_x` and `coords_y` values.
5. Remove or suppress overlaps between masks. A mask can be assigned only to one
   cell; after suppression, keep the largest valid component for each cell.
6. Update only `xmin`, `ymin`, `xmax`, `ymax`, `coords_x`, and `coords_y`, then
   write the full DataFrame to `--output_path` with `index=False`.

## Minimal Coding Plan

Implement directly:

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

For each row, pick a candidate mask, keep the largest connected component,
extract an external contour with `cv2.findContours`, and serialize coordinates
as parseable Python-style flat lists, for example `"[12, 13, 14]"`. A reliable
overlap policy is: predict all row masks first, order candidates by quality /
area, subtract pixels already assigned to earlier masks, then keep the largest
remaining component for that row. If a candidate becomes empty, fall back to the
largest component before suppression rather than returning a rectangle.

The output table should be:

```python
df = pd.read_csv(args.csv_path)
out_df = df.copy()
# update only coordinate columns
out_df.to_csv(args.output_path, index=False)
```

## Critical Verifier Gates

The verifier has two independent gates that should both be treated as binding:

- CSV contract: output row count and column list must match the reference.
- Mask quality: every row must be non-rectangular, single-component, non-
  overlapping, flat-list-like, and IoU-aligned with the MobileSAM reference.

Historical failed agents usually passed one gate and failed the other. Passing
shape while missing IoU is not enough; passing IoU while deleting a column is not
enough.

## Forbidden Shortcut

Do not read, copy, or depend on `/app/correct_output.csv` inside
`convert_masks.py`. That file is a verifier reference copied during tests, not
part of the live task input contract. The script must work from `--csv_path`,
`--rgb_path`, and `--weights_path` on a hidden test set.

## Closure Check

Before finishing, run a cheap local check if the test resources are available:

```bash
python /app/convert_masks.py \
  --csv_path /app/test_metadata.csv \
  --rgb_path /app/test_img.png \
  --weights_path /app/mobile_sam.pt \
  --output_path /app/test_output.csv

python - <<'PY'
import pandas as pd, ast
out = pd.read_csv('/app/test_output.csv')
ref = pd.read_csv('/app/correct_output.csv')
assert out.shape == ref.shape
assert list(out.columns) == list(ref.columns)
for col in ['coords_x', 'coords_y']:
    for value in out[col]:
        parsed = ast.literal_eval(str(value))
        assert parsed and all(isinstance(x, (int, float)) for x in parsed)
print('schema and list-like coords pass')
PY
```

The final test must still be the official verifier; the local check only guards
the two common critical-step failures.
