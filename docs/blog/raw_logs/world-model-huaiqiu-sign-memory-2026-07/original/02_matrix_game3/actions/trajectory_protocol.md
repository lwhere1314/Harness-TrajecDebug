# Matrix-Game 3.0 Action Trajectory Protocol

This note records the Matrix-Game 3.0 action scripts used in the Huaiqiu sign memory experiment and converts frame counts into seconds.

## Action Codebook

Matrix-Game 3.0 action CSV format:

```csv
frames,mouse,key,note
```

The local patched runner repeats each row for `frames` video frames.

Mouse codes:

- `U`: no camera movement
- `L`: yaw right
- `J`: yaw left
- `I`: pitch up
- `K`: pitch down

Keyboard codes:

- `Q`: no movement
- `W`: move forward
- `S`: move backward
- `A`: move left
- `D`: move right

The current generated Matrix-Game 3.0 videos are 17 fps. For the default 25-iteration run:

```text
total_frames = 57 + 24 * 40 = 1017
duration_s = 1017 / 17 = 59.82s
```

For a 30-iteration run:

```text
total_frames = 57 + 29 * 40 = 1217
duration_s = 1217 / 17 = 71.59s
```

The 30-iteration setting is a better duration match for the current Genie3 videos, which are about 71.2s.

## Existing Script: `huaiqiu_yaw_right_return_60s.csv`

This script tests pure camera-yaw revisit memory. The camera turns away from the storefront, keeps the storefront out of view, then turns back near the end.

| Segment | Frames | Start | End | Mouse | Key | Meaning |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | 57 | 0.00s | 3.35s | U | Q | Hold initial storefront view |
| 2 | 40 | 3.35s | 5.71s | L | Q | Yaw right until storefront leaves view |
| 3 | 700 | 5.71s | 46.88s | U | Q | Keep looking away |
| 4 | 40 | 46.88s | 49.24s | J | Q | Yaw left back toward storefront |
| 5 | 180 | 49.24s | 59.82s | U | Q | Hold revisited storefront view |

Interpretation:

- Good for isolating memory under viewpoint rotation.
- Easier than navigation, because position is fixed.
- Should not be directly compared with Genie3 free navigation as a matched trajectory.

## Existing Script: `huaiqiu_retreat_yaw_return_60s.csv`

This script adds position change: move backward while facing the storefront, turn away, wait, turn back, move forward.

| Segment | Frames | Start | End | Mouse | Key | Meaning |
| --- | ---: | ---: | ---: | --- | --- | --- |
| 1 | 57 | 0.00s | 3.35s | U | Q | Hold initial storefront view |
| 2 | 120 | 3.35s | 10.41s | U | S | Walk backward while facing storefront |
| 3 | 40 | 10.41s | 12.76s | L | Q | Yaw right away from storefront |
| 4 | 560 | 12.76s | 45.71s | U | Q | Keep storefront out of view |
| 5 | 40 | 45.71s | 48.06s | J | Q | Yaw left back toward storefront |
| 6 | 120 | 48.06s | 55.12s | U | W | Walk forward toward original position |
| 7 | 80 | 55.12s | 59.82s | U | Q | Hold revisited storefront view |

Interpretation:

- Better stress test than pure yaw because it tests both memory and position loop closure.
- Still not matched to Genie3 free navigation unless Genie3 follows the same semantic path.

## Proposed Matched Protocols

The next strict benchmark should separate two levels:

1. `diagnostic`: same target object, different actions allowed; compare failure modes.
2. `matched`: same target object, approximately matched action trajectory and duration.

### Protocol A: 60s Matched Retreat-Yaw-Return

Use when matching a 60s Matrix-Game 3.0 run:

- 5s hold initial view.
- 6s move backward while facing the sign.
- 2.35s yaw away.
- 32.24s offscreen memory interval.
- 2.35s yaw back.
- 6s move forward.
- 5.88s final hold.

This is more balanced than the current 60s script because it explicitly reserves 5 seconds at the beginning and end for scoring.

CSV file: `huaiqiu_matched_retreat_yaw_return_60s.csv`

### Protocol B: 70s Matched Retreat-Yaw-Return

Use when comparing against the current Genie3 videos, which are about 71.2s:

- Run Matrix-Game 3.0 with `MG3_ITERATIONS=30`.
- 5s hold initial view.
- 10s move backward while facing the sign.
- 2.35s yaw away.
- 35.29s offscreen memory interval.
- 2.35s yaw back.
- 10s move forward.
- 6.59s final hold.

CSV file: `huaiqiu_matched_retreat_yaw_return_70s.csv`

Suggested Matrix-Game 3.0 command shape:

```bash
MG3_ITERATIONS=30 \
MG3_ACTION_SCRIPT="/Users/hugo/Documents/世界模型面试/记忆一致性实验/02_matrix_game3/actions/huaiqiu_matched_retreat_yaw_return_70s.csv" \
MG3_SAVE_NAME=huaiqiu_matched_retreat_yaw_return_70s \
matrix_game3_remote.sh run-custom-pull
```

## Reporting Rules

Every result should report:

- `action_protocol`
- `video_duration_s`
- `trajectory_matched`
- `target_visible_s`
- `offscreen_gap_s`
- `first_valid_revisit_s`
- `revisit_score`

For the current dataset:

- Genie3: `action_protocol=free_navigation`, `trajectory_matched=no`, `video_duration_s≈71.2`.
- Matrix yaw return: `action_protocol=yaw_return_60s`, `trajectory_matched=no`, `video_duration_s≈59.8`.
- Matrix retreat return: `action_protocol=retreat_yaw_return_60s`, `trajectory_matched=no`, `video_duration_s≈59.8`.

Only future runs with the same semantic movement plan should be marked `trajectory_matched=approximate` or `yes`.

