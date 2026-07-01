# Raw Logs: Huaiqiu Sign World-Model Memory Case

This directory contains the raw materials for:

- [Chinese blog](../../world-model-huaiqiu-sign-memory.zh.md)
- [English blog](../../world-model-huaiqiu-sign-memory.en.md)

The experiment studies whether interactive world models preserve the Chinese
storefront sign text `槐楸` after the camera leaves the storefront and later
returns.

## Layout

```text
original/
  00_reference/                 # reference photo, annotation template, metric notes
  01_genie3/                    # Genie3 videos, sampled frames, qualitative scores
  02_matrix_game3/              # Matrix-Game 3.0 inputs, action scripts, videos, scores
  03_comparison/                # comparison tables and summaries
  04_presentation/              # context photos used for presentation material
  05_principles/                # principle/reference notes
  EXPERIMENT_LIMITATIONS.md     # benchmark caveats and validity notes
  MEDIA.md                      # media inventory from the source experiment
  README.md                     # source experiment README
source_tree.txt                 # generated file list
checksums.sha256                # generated SHA-256 checksums
```

The copied `original/` tree excludes the source folder's `.git/`, `.gitignore`,
and `.gitattributes` metadata. The media and evaluation files themselves are
preserved.

## Key Evidence

| Evidence | Path |
| --- | --- |
| Reference sign photo | [original/00_reference/槐楸招牌.jpg](original/00_reference/槐楸招牌.jpg) |
| Genie3 video 01 | [original/01_genie3/videos/槐楸_genie3_01.mp4](original/01_genie3/videos/槐楸_genie3_01.mp4) |
| Genie3 video 02 | [original/01_genie3/videos/槐楸_genie3_02.mp4](original/01_genie3/videos/槐楸_genie3_02.mp4) |
| Genie3 sampled frames | [original/01_genie3/evaluation/frames/](original/01_genie3/evaluation/frames/) |
| Genie3 qualitative summary | [original/01_genie3/evaluation/槐楸_Genie3_定性评估小结.md](original/01_genie3/evaluation/槐楸_Genie3_定性评估小结.md) |
| Genie3 score sheet | [original/01_genie3/evaluation/槐楸_genie3_评分表.csv](original/01_genie3/evaluation/槐楸_genie3_评分表.csv) |
| Matrix-Game 3.0 prompt-only videos | [original/02_matrix_game3/prompt_only_uncontrolled/videos/](original/02_matrix_game3/prompt_only_uncontrolled/videos/) |
| Matrix-Game 3.0 prompt-only summary | [original/02_matrix_game3/prompt_only_uncontrolled/evaluation/槐楸_MG3_评估小结.md](original/02_matrix_game3/prompt_only_uncontrolled/evaluation/槐楸_MG3_评估小结.md) |
| Matrix-Game 3.0 action-controlled videos | [original/02_matrix_game3/action_controlled/videos/](original/02_matrix_game3/action_controlled/videos/) |
| Matrix-Game 3.0 action-controlled summary | [original/02_matrix_game3/action_controlled/evaluation/槐楸_MG3_action_controlled_小结.md](original/02_matrix_game3/action_controlled/evaluation/槐楸_MG3_action_controlled_小结.md) |
| Matrix-Game 3.0 action scripts | [original/02_matrix_game3/actions/](original/02_matrix_game3/actions/) |
| Matched 70s action plan | [original/02_matrix_game3/actions/huaiqiu_matched_retreat_yaw_return_70s.csv](original/02_matrix_game3/actions/huaiqiu_matched_retreat_yaw_return_70s.csv) |
| Comparison summary | [original/03_comparison/comparison_summary.md](original/03_comparison/comparison_summary.md) |
| Metric table | [original/03_comparison/metric_table.csv](original/03_comparison/metric_table.csv) |
| Experiment limitations | [original/EXPERIMENT_LIMITATIONS.md](original/EXPERIMENT_LIMITATIONS.md) |

## Data Notes

- The current Genie3 and Matrix-Game 3.0 runs are a same-target diagnostic stress
  test, not a strict matched head-to-head benchmark.
- Existing Genie3 movement is human-controlled through the browser UI.
- Matrix-Game 3.0 action-controlled runs use CSV action scripts.
- Runs that do not revisit the sign should be treated as `trajectory_miss`, not
  as direct text-memory failures.
- MP4 files under this directory are tracked with Git LFS via the repository
  `.gitattributes`.

## Integrity

Use `checksums.sha256` to verify copied raw files:

```bash
cd docs/blog/raw_logs/world-model-huaiqiu-sign-memory-2026-07
shasum -a 256 -c checksums.sha256
```
