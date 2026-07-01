# Testing World-Model Memory Consistency With One Chinese Storefront Sign

I recently tested a very specific but revealing failure mode in interactive
world models: can the model remember a Chinese storefront sign after the camera
moves away and later returns?

This is not meant to be a generic video-quality comparison. The target is much
narrower: local Chinese-text memory under navigation.

The source image is a real photo I took of a cafe near Shichahai. The key target
is a glowing Chinese sign:

```text
槐楸
```

This is a useful stress test because the sign is both a local visual detail and
a semantic constraint. A model may remember that there is a cafe-like storefront,
but if `槐楸` turns into pseudo-Chinese, random strokes, or another phrase after
revisit, the model has lost the local text identity.

## Raw Data Index

The raw materials for this blog are stored under:

```text
docs/blog/raw_logs/world-model-huaiqiu-sign-memory-2026-07/
```

The most important evidence links are:

| Material | Path |
| --- | --- |
| Raw data README | [raw_logs/world-model-huaiqiu-sign-memory-2026-07/README.md](raw_logs/world-model-huaiqiu-sign-memory-2026-07/README.md) |
| Reference photo | [original/00_reference/槐楸招牌.jpg](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/00_reference/槐楸招牌.jpg) |
| Genie3 video 01 | [original/01_genie3/videos/槐楸_genie3_01.mp4](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/videos/槐楸_genie3_01.mp4) |
| Genie3 video 02 | [original/01_genie3/videos/槐楸_genie3_02.mp4](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/videos/槐楸_genie3_02.mp4) |
| Genie3 sampled frames | [original/01_genie3/evaluation/frames/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/evaluation/frames/) |
| Genie3 score sheet | [original/01_genie3/evaluation/槐楸_genie3_评分表.csv](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/evaluation/槐楸_genie3_评分表.csv) |
| Matrix-Game 3.0 prompt-only videos | [original/02_matrix_game3/prompt_only_uncontrolled/videos/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/prompt_only_uncontrolled/videos/) |
| Matrix-Game 3.0 action-controlled videos | [original/02_matrix_game3/action_controlled/videos/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/action_controlled/videos/) |
| Matrix-Game 3.0 action scripts | [original/02_matrix_game3/actions/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/actions/) |
| Comparison table | [original/03_comparison/metric_table.csv](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/03_comparison/metric_table.csv) |
| Experiment limitations | [original/EXPERIMENT_LIMITATIONS.md](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/EXPERIMENT_LIMITATIONS.md) |

## Research Question

The core question is:

```text
After navigating away from a target object, can a world model preserve local
Chinese text when the camera returns to the same object?
```

The desired protocol is:

1. Start from a frame where the `槐楸` sign is visible and scoreable.
2. Move or rotate away until the sign leaves the view.
3. Keep the sign offscreen for a measured memory interval.
4. Return to the storefront.
5. Check whether the revisited sign still reads as `槐楸`.

The goal is not merely to generate a storefront. The goal is to revisit the same
storefront and preserve the specific local text.

## Why This Belongs In Harness-TrajecDebug

Harness-TrajecDebug was originally designed for terminal-agent traces. It reads
an agent trace, combines it with verifier output, localizes the critical failure
step, and turns the evidence into reusable Debug-Action cards.

This world-model experiment looks different on the surface, but the structure
is similar:

| Harness-TrajecDebug view | Terminal-agent setting | World-model setting |
| --- | --- | --- |
| Reference view | Task instruction, verifier contract, target artifact | Target sign, expected text `槐楸`, reference image, scoring rubric |
| State view | Command output, file state, test result | Video frames, target visibility, sign crop, text score |
| Commitment view | Agent decisions, tool calls, final artifact promotion | WASD/camera actions, leaving the target, offscreen interval, revisit segment |
| Verifier footprint | Reward, failed tests, missing artifact | Revisit score, text drift, trajectory-matched flag |

So the case can be represented as:

```text
action trajectory -> video observations -> verifier scores -> failure diagnosis
```

This is the same abstraction Harness-TrajecDebug is meant to capture: not just
whether a run failed, but where the failure became visible in the trajectory.

## Comparing Genie3 And Matrix-Game 3.0

The current experiment uses two kinds of systems:

| System | Current usage | Strength | Current limitation |
| --- | --- | --- | --- |
| Genie3 | Interactive browser navigation | Closer to a real interactive experience | The current movement path is human-controlled and not exactly reproducible |
| Matrix-Game 3.0 | Initial image plus prompt plus action CSV | Scriptable `W/A/S/D` movement and camera control | Its action semantics are not necessarily identical to Genie3 |

This means the current evidence should not be framed as a strict leaderboard.
The Genie3 movement actions and Matrix-Game 3.0 action CSV are not yet the same
trajectory.

The accurate framing is:

```text
This is a same-target diagnostic stress test,
not yet a strict matched head-to-head benchmark.
```

That distinction matters. A system may look worse simply because it was never
guided back to a scoreable view of the target. Another system may look better
because its scripted trajectory naturally revisits the sign.

## Current Observation

In the Genie3 run, my qualitative observation is:

- In the first few seconds, the `槐楸` sign is still readable.
- Near the late 1-minute range, the sign becomes unstable, corrupted, or
  pseudo-text.
- The storefront may still look like the same place, but the local Chinese text
  has drifted.

This exposes a typical world-model failure mode:

```text
object identity may survive, while local text identity is lost.
```

For Matrix-Game 3.0, I prefer a scripted action trajectory because it can be
reproduced as a CSV:

```csv
frames,mouse,key,comment
85,U,Q,hold initial storefront view for scoring
170,U,S,walk backward while still facing storefront
40,L,Q,yaw right away from storefront
600,U,Q,keep storefront out of view for memory interval
40,J,Q,yaw left back toward storefront
170,U,W,walk forward toward original position
112,U,Q,hold revisited storefront view for scoring
```

This planned trajectory is about 71.59 seconds, close to the current Genie3
clip length. It is designed to:

1. Hold the storefront for initial scoring.
2. Move backward and yaw away.
3. Keep the sign offscreen for about 35 seconds.
4. Turn back and walk toward the original storefront.
5. Hold the revisited view for final scoring.

The corresponding action CSV is included in the raw logs:

```text
raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/actions/huaiqiu_matched_retreat_yaw_return_70s.csv
```

## Minimal Metrics

I want the first version of this benchmark to stay simple and auditable.

| Metric | Meaning |
| --- | --- |
| `trajectory_matched` | Whether the run follows the agreed leave-and-return trajectory |
| `target_revisit` | Whether the sign becomes visible again after leaving |
| `offscreen_gap_s` | How long the target stays out of view |
| `T_exact_s` | Last timestamp where the sign exactly reads `槐楸` |
| `T_readable_s` | Last timestamp where the sign is still plausibly the same Chinese text |
| `text_score_revisit` | Whether the revisited Chinese text is still correct |
| `identity_score_revisit` | Whether the revisited object is still the same storefront/sign |
| `geometry_score_revisit` | Whether the sign position, shape, and layout remain stable |

The headline metric is:

```text
S_revisit = (text_score_revisit, identity_score_revisit)
```

For example:

```text
S_revisit = (1, 2)
```

This means the storefront identity is still partially preserved, but the local
Chinese text has clearly degraded.

This is more informative than saying "video quality dropped", because it
separates two different failures:

- the model forgot the whole storefront,
- the model remembered the storefront but forgot the exact Chinese text.

## Why The Action Trajectory Is Part Of The Benchmark

The easy mistake is to ignore the action path. But for interactive world models,
the action trajectory is part of the benchmark.

If two systems use different trajectories, they face different memory pressure:

- different offscreen durations,
- different revisit angles,
- different times at which the target leaves the frame,
- different distance and viewpoint when returning.

In Harness-TrajecDebug, this becomes a failure pattern:

```text
action_protocol_mismatch
```

This is not a model failure. It is an experiment-design failure. The memory
score only becomes comparable after the trajectory is normalized.

## Debug-Action Card

This case produces a reusable Debug-Action card:

```text
Before comparing world-model memory, enforce a matched revisit trajectory:
start with a scoreable target crop, move away until the target is out of view,
hold an offscreen interval, return to a scoreable crop, and only then compare
text and identity scores. Mark runs without a valid revisit as trajectory_miss,
not as memory failures.
```

Operationally:

1. Do not rely only on a prompt saying "remember this sign".
2. Ensure the target is visible and scoreable at the start.
3. Ensure the target leaves the frame.
4. Record how long it remains offscreen.
5. Return to a scoreable view.
6. If the target is not revisited, label it `trajectory_miss`, not text-memory
   failure.

The card turns a subjective video observation into a reproducible trajectory
debugging protocol.

## Why This Case Matters

This case is useful for several reasons.

First, it makes "world-model memory" concrete. Instead of asking whether a model
has a world model in the abstract, it asks whether the model can remember one
Chinese sign after about a minute of navigation.

Second, it uses Chinese text as a stress test. Many generative models can create
texture that looks like text, but maintaining exact text identity over time is a
stronger requirement.

Third, it treats interaction as part of evaluation. A world model is not just a
video generator; the user's action trajectory changes the memory challenge.

Fourth, it fits into Harness-TrajecDebug. Each run can be archived as:

```text
prompt + action series + sampled frames + crop scores + diagnosis
```

That turns the experiment from a one-off demo into a benchmark scaffold for
accumulating and debugging failure cases.

## Next Steps

The next step is to make this docs-first case runnable:

1. Run Matrix-Game 3.0 with the 70s matched trajectory for at least two seeds.
2. Export key frames and sign crops from the Genie3 video.
3. Build a lightweight scorer that starts with manual CSV annotation and later
   supports OCR/VLM scoring.
4. Add `trajectory_miss`, `text_garbled_after_revisit`, and
   `geometry_drift_after_loop` to the Harness-TrajecDebug failure taxonomy.
5. Turn this into a reproducible world-model trajectory debugging benchmark.

The current conclusion should remain careful:

```text
Current world models show a clear stress point around local Chinese-text memory.
The Huaiqiu sign experiment provides a reproducible and diagnosable test format.
A strict Genie3 vs Matrix-Game 3.0 comparison requires matched trajectories.
```

I like this case because it is small but real. If an interactive world model is
going to support long-horizon navigation, it should not only remember that
there was a storefront. It should remember what the storefront was called.
