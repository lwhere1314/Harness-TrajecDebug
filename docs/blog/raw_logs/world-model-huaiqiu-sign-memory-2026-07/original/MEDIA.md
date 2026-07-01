# Media Manifest

This repository contains a small, real-world benchmark for Chinese sign memory in interactive world models.

## Source And Generated Media

- `00_reference/槐楸招牌.jpg`: original real-world reference photo for the target storefront sign.
- `01_genie3/videos/`: Genie3 generated videos.
- `02_matrix_game3/action_controlled/videos/`: Matrix-Game 3.0 controlled-action revisit videos.
- `02_matrix_game3/prompt_only_uncontrolled/videos/`: Matrix-Game 3.0 prompt-only baseline videos.
- `02_matrix_game3/smoke/`: short smoke-test video for action-script support.
- `04_presentation/`: optional real-world context photos from the same cafe/bar setting.

## Lightweight Review Path

For quick review without downloading videos, use:

- `01_genie3/evaluation/槐楸_genie3_contact_sheet.jpg`
- `02_matrix_game3/action_controlled/evaluation/huaiqiu_action_controlled_contact_sheet.jpg`
- `02_matrix_game3/prompt_only_uncontrolled/evaluation/huaiqiu_mg3_memory_contact_sheet.jpg`
- `03_comparison/comparison_summary.md`

## Git LFS

All `.mp4` files are tracked with Git LFS. If the videos do not appear after cloning, run:

```bash
git lfs pull
```

The image frames and contact sheets are stored directly in git, so the benchmark can still be inspected without LFS.

