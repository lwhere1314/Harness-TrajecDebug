# Genie3 vs Matrix-Game 3.0 槐楸记忆一致性对比

## 评价对象

目标是 `槐楸` 招牌，重点看：

1. 文字记忆存储时间：`槐楸` 两个字多久还能被读出。
2. 前后一致性：回到店面时是否仍是同一块招牌/同一家店。

快速评分标准见 [简单评估标准.md](../00_reference/简单评估标准.md)。更完整的 benchmark 指标定义见 [指标说明与参考.md](../00_reference/指标说明与参考.md)，其中额外拆分了可见性、回访有效性、几何一致性、时间稳定性和失败类型。

## Benchmark 有效性说明

这组结果应被表述为 `same-target diagnostic stress test`，不是严格的 `matched head-to-head benchmark`。原因是 Genie3 与 Matrix-Game 3.0 的动作输入和视频时长没有完全对齐：

- Genie3 组来自 free navigation / 手动探索，轨迹由实际交互过程决定。
- Matrix-Game 3.0 prompt-only 组没有稳定回到目标店面。
- Matrix-Game 3.0 action-controlled 组使用固定 action script，例如 `yaw return` 和 `retreat+yaw return`。
- Genie3 视频约 70 秒，Matrix-Game 3.0 主要结果约 60 秒，因此不能只按绝对时间直接比较。

因此当前实验可以支持这些结论：

- 中文招牌记忆是一个有效的 world model 压力测试。
- Genie3 在这组自由探索视频中出现了长时中文文字漂移。
- Matrix-Game 3.0 在这组固定回访动作中能更稳定地保持店面/招牌，但位移闭环会带来文字和几何漂移。

当前实验不应支持这些过度结论：

- 不能声称 Matrix-Game 3.0 全面优于 Genie3。
- 不能把 `T_readable` 作为跨系统严格排名，除非同时控制 `action_protocol`、`video_duration_s`、`offscreen_gap_s` 和 `revisit_score`。
- 不能把“没有回到店面”解释成“忘记了招牌”。

## 结果总览

| 系统 | 设置 | T_exact | T_readable | S_60 | 结论 |
| --- | --- | ---: | ---: | --- | --- |
| Genie3 | free navigation | ~5s | ~10-20s | ~(1,2) | 开头可读，60 秒附近招牌变成中文乱码或其他文字 |
| Matrix-Game 3.0 | prompt-only uncontrolled | 0s | 0s | NA | 未按 prompt 回到店面，不能作为严格记忆测试 |
| Matrix-Game 3.0 | action-controlled yaw return | 59s | 59s | (3,3) | 原地转头回访时，60 秒附近仍能读出槐楸 |
| Matrix-Game 3.0 | action-controlled retreat+yaw return | 5s | 59s | (2,2) | 带位移闭环时仍可认，但文字和构图明显漂移 |

说明：`S_60` 只包含文字和身份，适合快速阅读。若用于更严格 benchmark，应同时报告 `revisit_score` 和 `geometry_score`，避免把“没有回到目标区域”和“回到了但忘记招牌”混在一起。

## 关键解释

Genie3 的两条视频更像自然自由探索：场景整体连续性较好，能回到类似中式街区/店铺，但中文文字在长时回访时容易变形。它的主要问题是 `文字身份漂移`。

Matrix-Game 3.0 的 prompt-only 非受控版本不能直接比较记忆，因为相机没有按自然语言 prompt 回到店面。这一组主要说明：如果没有固定动作轨迹，记忆 benchmark 会被轨迹可控性污染。

Matrix-Game 3.0 的 action-controlled 版本才是更严格的对比。结果显示：

- 纯 yaw 回访很强：离开视野后回到原方向，`槐楸` 仍可读。
- 带位移闭环更难：能保留大体店面身份，但严格中文文字和几何位置会漂移。

## 推荐后续实验

1. 对 Genie3 也做同样的固定轨迹或尽量手动复现 yaw-return / retreat-return 两种路线。
2. 对 Matrix-Game 3.0 增加更长 offscreen 间隔：90s、120s。
3. 将中文招牌换成更细粒度目标：门牌号、电话号码、英文+中文混合招牌。
