# 从一个中文招牌开始，测试世界模型的记忆一致性

我最近在测试交互式世界模型时，遇到一个很具体但很有代表性的问题：模型能不能记住一个真实场景里的中文招牌？

这个实验的目标不是评估视频好不好看，也不是泛泛地比较哪个模型更强。我更关心一个小而硬的能力：当模型从一个店面前离开，过一段时间再回到同一个店面时，它还能不能记住原来的中文文字。

我选的目标是一张自己拍摄的什刹海小酒馆照片。画面里有一个发光招牌，中文是：

```text
槐楸
```

这个例子非常适合作为 stress test。因为中文招牌既是局部细节，又是语义强约束。模型可以大体记住“这里有个咖啡/茶馆”，但如果它把 `槐楸` 变成乱码、伪中文、或者其他字，就说明它在局部文本记忆上已经发生了漂移。

## 原始数据索引

这篇 blog 对应的原始材料都放在：

```text
docs/blog/raw_logs/world-model-huaiqiu-sign-memory-2026-07/
```

关键证据可以直接从正文追到 raw logs：

| 材料 | 路径 |
| --- | --- |
| 原始数据说明 | [raw_logs/world-model-huaiqiu-sign-memory-2026-07/README.md](raw_logs/world-model-huaiqiu-sign-memory-2026-07/README.md) |
| 参考照片 | [original/00_reference/槐楸招牌.jpg](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/00_reference/槐楸招牌.jpg) |
| Genie3 视频 01 | [original/01_genie3/videos/槐楸_genie3_01.mp4](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/videos/槐楸_genie3_01.mp4) |
| Genie3 视频 02 | [original/01_genie3/videos/槐楸_genie3_02.mp4](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/videos/槐楸_genie3_02.mp4) |
| Genie3 关键帧 | [original/01_genie3/evaluation/frames/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/evaluation/frames/) |
| Genie3 评分表 | [original/01_genie3/evaluation/槐楸_genie3_评分表.csv](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/01_genie3/evaluation/槐楸_genie3_评分表.csv) |
| Matrix-Game 3.0 prompt-only 视频 | [original/02_matrix_game3/prompt_only_uncontrolled/videos/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/prompt_only_uncontrolled/videos/) |
| Matrix-Game 3.0 action-controlled 视频 | [original/02_matrix_game3/action_controlled/videos/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/action_controlled/videos/) |
| Matrix-Game 3.0 action scripts | [original/02_matrix_game3/actions/](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/actions/) |
| 对比表 | [original/03_comparison/metric_table.csv](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/03_comparison/metric_table.csv) |
| 实验限制说明 | [original/EXPERIMENT_LIMITATIONS.md](raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/EXPERIMENT_LIMITATIONS.md) |

## 实验问题

我想测试的是：

```text
世界模型在导航离开目标物体之后，能否在回访时保持局部中文文本的一致性？
```

更具体一点：

1. 第一帧里，`槐楸` 招牌是清楚可见的。
2. 视角移动或转动，让招牌离开画面。
3. 等待一段 offscreen memory interval。
4. 再回到店面。
5. 检查招牌是否仍然读作 `槐楸`。

这里的重点不是“生成一个店面”，而是“回到同一个店面时，局部文本有没有被模型遗忘或重写”。

## 为什么这个实验适合放进 Harness-TrajecDebug

Harness-TrajecDebug 原本面向 terminal agent：它读取一段 agent trace，结合 verifier 输出，定位关键失败步骤，再生成可以复用的 Debug-Action card。

这个世界模型实验看上去不是 terminal task，但结构其实很像：

| Harness-TrajecDebug 视角 | terminal agent 里是什么 | 世界模型实验里是什么 |
| --- | --- | --- |
| Reference view | 任务说明、verifier contract、目标 artifact | 目标招牌、期望文字 `槐楸`、参考图、评分规则 |
| State view | 命令输出、文件状态、测试结果 | 视频帧、目标是否可见、招牌 crop、文字评分 |
| Commitment view | agent 的决策、工具调用、最终提交 | WASD/视角动作、离开目标、保持 offscreen、回访目标 |
| Verifier footprint | reward、failed tests、artifact missing | 回访评分、文字漂移、trajectory 是否 matched |

所以这个 case 可以被建模成：

```text
action trajectory -> video observations -> verifier scores -> failure diagnosis
```

这正是 Harness-TrajecDebug 想抽象出来的东西：不只看最终结果，而是看失败发生在轨迹里的哪个位置。

## Genie3 和 Matrix-Game 3.0 怎么比较

我现在有两类系统：

| 系统 | 当前用法 | 优点 | 当前限制 |
| --- | --- | --- | --- |
| Genie3 | 浏览器里交互式导航 | 更接近真实交互体验 | 当前动作是人工控制的，轨迹不容易精确复现 |
| Matrix-Game 3.0 | 初始图 + prompt + action CSV | 可以脚本化控制 `W/A/S/D` 和视角转动 | action 语义不一定和 Genie3 完全一致 |

这意味着当前实验不能直接写成“严格公平的 benchmark 排名”。因为 Genie3 里我的移动动作，和 Matrix-Game 3.0 里的 action CSV，并不是同一条轨迹。

因此更准确的说法是：

```text
当前实验是 same-target diagnostic stress test，
还不是严格 matched head-to-head benchmark。
```

这点很重要。否则一个模型看起来更差，可能只是因为它没有被引导回到可评分的招牌视角；另一个模型看起来更好，也可能只是因为它的动作脚本天然更容易回访目标。

## 当前观察

在 Genie3 的视频里，我的直观观察是：

- 前几秒，`槐楸` 招牌仍然比较清楚。
- 到后期，大约 1 分钟附近，招牌从中文变成了不稳定的乱码或伪文字。
- 店面整体可能还像原来的店面，但局部中文文字已经发生了漂移。

这说明 Genie3 在这个 case 上出现了一个很典型的世界模型问题：

```text
object identity 可能还在，但 local text identity 已经丢了。
```

Matrix-Game 3.0 这边，我更倾向于用 action script 做复现。因为它可以把动作写成 CSV，例如：

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

这条轨迹大约是 71.59 秒，更接近当前 Genie3 视频长度。它的设计目标是：

1. 起始 5 秒固定看店面，方便评分。
2. 后退并转向，让招牌离开画面。
3. 保持约 35 秒 offscreen interval。
4. 转回并前进，回到原来的店面。
5. 最后 hold 住回访画面，方便裁剪招牌评分。

对应的 action CSV 已经放在 raw logs 里：

```text
raw_logs/world-model-huaiqiu-sign-memory-2026-07/original/02_matrix_game3/actions/huaiqiu_matched_retreat_yaw_return_70s.csv
```

## 简化评估指标

我不想一开始就把指标做得过重。这个 case 最重要的是让结果可解释、可人工复核。

我目前设计的核心指标是：

| 指标 | 含义 |
| --- | --- |
| `trajectory_matched` | 这段视频是否遵守了预设的离开-回访轨迹 |
| `target_revisit` | 招牌是否在离开后重新出现在画面里 |
| `offscreen_gap_s` | 招牌离开画面到重新出现之间隔了多少秒 |
| `T_exact_s` | 最后一次能精确读作 `槐楸` 的时间 |
| `T_readable_s` | 最后一次还能看作同一个中文招牌的时间 |
| `text_score_revisit` | 回访时中文文字是否仍然正确 |
| `identity_score_revisit` | 回访时是否仍然是同一个店面/招牌 |
| `geometry_score_revisit` | 招牌位置、形状、布局是否稳定 |

最核心的 headline metric 是：

```text
S_revisit = (text_score_revisit, identity_score_revisit)
```

例如：

```text
S_revisit = (1, 2)
```

意思是：回访时店面身份还有点像原来的，但是中文文字已经明显损坏。

这比只写“视频质量下降”更有信息量。因为它区分了两种不同失败：

- 模型忘记了整个店面。
- 模型记住了店面，但忘记了局部中文文本。

## 为什么动作轨迹必须被纳入 benchmark

这个实验里最容易被忽略的一点是：动作本身就是 benchmark 的一部分。

如果两个系统的 action trajectory 不一样，那么它们经历的记忆压力也不一样：

- 离开画面的时间不同。
- 回访角度不同。
- 目标在画面里消失的时间不同。
- 回到目标时的距离和视角不同。

所以我在 Harness-TrajecDebug 里把这类问题记录成一个 failure pattern：

```text
action_protocol_mismatch
```

它不是模型失败，而是实验设计失败。只有先把轨迹对齐，后面的 memory score 才有比较意义。

## Debug-Action card

这个 case 也可以产生一个通用的 Debug-Action card：

```text
Before comparing world-model memory, enforce a matched revisit trajectory:
start with a scoreable target crop, move away until the target is out of view,
hold an offscreen interval, return to a scoreable crop, and only then compare
text and identity scores. Mark runs without a valid revisit as trajectory_miss,
not as memory failures.
```

翻译成实验操作就是：

1. 不要只靠 prompt 说“记住这个招牌”。
2. 必须让目标先清楚可见。
3. 必须让目标离开画面。
4. 必须记录目标离开了多久。
5. 必须回到一个可评分视角。
6. 没有回访成功的视频，不应该被算作文本记忆失败，而应该被标记为 `trajectory_miss`。

这个 card 的意义在于：它把一个主观视频观察，变成一个可以被复现、诊断、迭代的实验协议。

## 这个 case study 的价值

我觉得这个 case 有几个价值：

第一，它把世界模型的“记忆”问题具体化了。不是抽象地说模型有没有 world model，而是问它能不能在 1 分钟导航之后记住一个中文招牌。

第二，它把中文文本作为 stress test。很多模型能生成“像文字的纹理”，但不一定能长期保持具体文字身份。

第三，它把交互动作纳入评估。世界模型不是单纯 video generation，用户的动作轨迹会改变模型面对的记忆压力。

第四，它可以接入 Harness-TrajecDebug。未来每个 run 都可以被保存成：

```text
prompt + action series + sampled frames + crop scores + diagnosis
```

这让它不只是一个 demo，而是一个可以积累 failure cases 的 benchmark scaffold。

## 下一步

下一步我会把这个 case 从 docs-first 推到 runnable：

1. 用 70s matched trajectory 跑 Matrix-Game 3.0，至少两个 seed。
2. 对 Genie3 视频导出关键帧和招牌 crop。
3. 做一个轻量 scorer，先支持人工评分 CSV，再接 OCR/VLM。
4. 把 `trajectory_miss`、`text_garbled_after_revisit`、`geometry_drift_after_loop` 写进 Harness-TrajecDebug 的 failure taxonomy。
5. 最终让这个 case 成为一个可以自动复跑的 world-model trajectory debugging benchmark。

这个实验的结论目前应当谨慎表述：

```text
现有世界模型在中文局部文本记忆上存在明显 stress point；
槐楸招牌实验提供了一个可复现、可诊断、可扩展的测试方式；
严格 Genie3 vs Matrix-Game 3.0 对比需要 matched trajectory 后再下结论。
```

我喜欢这个 case 的原因是它很小，但问题很真。一个世界模型如果真的能支持长时交互，它不应该只记得“那里有一家店”，还应该记得那家店叫什么。
