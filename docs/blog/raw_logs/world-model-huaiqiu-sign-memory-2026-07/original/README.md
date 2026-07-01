# 槐楸招牌记忆一致性实验 / Huaiqiu Sign Memory Benchmark

一个面向 world model 的小型真实场景 benchmark：测试交互式视频生成模型在移动、转头、离屏再回访后，是否还能记住中文招牌 `槐楸`。

这个目录整理了 Genie3 与 Matrix-Game 3.0 在 `槐楸` 招牌上的记忆一致性实验。

## Motivation

我发现现在的 world model 在处理中文文字记忆时还非常不到位：模型可以生成整体上连续的街景和店面，但一旦经过移动、转头、离屏再回访，中文招牌很容易从可读文字变成乱码、错字，或者变成相似但不同的招牌。

因此我选取了一张自己拍摄的什刹海店面照片作为固定参考目标，重点观察其中的 `槐楸` 中文招牌。这个实验对比了两个系统：

- Genie3：闭源交互式 world model，观察它在自由探索和长时回访中的中文招牌保持能力。
- Matrix-Game 3.0：开源交互式 world model，用同一张首帧图和受控 action script 测试它在可控回访路线下的记忆一致性。

核心问题不是“视频是否真实好看”，而是：模型是否真的记住了同一个中文招牌，以及离开视野以后再回来时，`槐楸` 两个字是否仍然可读。

这个 README 作为实验入口和 reference 索引使用：先看 `00_reference/` 里的指标定义，再看 Genie3、Matrix-Game 3.0 两组结果和总对比。视频文件通过 Git LFS 管理；如果只想快速阅读，可以直接看 contact sheet、抽帧和评估小结。

## 外部结果链接

- Genie3 槐楸项目：[Project Genie 链接](https://labs.google/fx/projectgenie/zh/tools/projectgenie/9cc50806-81da-4931-969e-07fe8069113a)

一句话总结：

> Genie3 在自由探索中短时保留 `槐楸`，但 60 秒附近中文文字明显漂移；Matrix-Game 3.0 在固定 action script 的纯 yaw 回访下 60 秒仍能清楚读出 `槐楸`，但加入位移闭环后文字和构图会变形。

## Benchmark 定位

这个实验目前更准确地说是 `same-target diagnostic stress test`，不是严格的 `matched head-to-head benchmark`。

它成立的地方：

- 目标对象一致：都围绕同一个中文招牌 `槐楸`。
- 评价问题一致：都看离屏/移动/回访后，中文招牌是否仍可读、是否仍是同一块招牌。
- failure mode 有可比性：可以比较“文字乱码”“店面身份漂移”“未成功回访目标区域”等现象。

它不成立为严格公平 benchmark 的地方：

- Genie3 组是 free navigation / 手动探索，Matrix-Game 3.0 组包含 prompt-only 和固定 action script，动作输入方式不一致。
- Genie3 与 Matrix-Game 3.0 的视频时长并不完全一致；因此不能只用绝对时间点直接排名。
- 两个系统的交互接口不同，不能假设 `WASD/mouse` 在两个系统里对应完全相同的相机运动、速度和视角变化。

因此当前结论应写成：这组实验能说明中文招牌记忆是一个真实且可观察的压力测试，也能展示两个系统在当前使用方式下的失败模式；但不能直接声称 Matrix-Game 3.0 全面优于 Genie3。若要做严格 benchmark，需要统一动作协议、目标可见时间、离屏时间和回访成功标准。

## Preview

Genie3 抽帧对比：

![Genie3 contact sheet](01_genie3/evaluation/槐楸_genie3_contact_sheet.jpg)

Matrix-Game 3.0 action-controlled 抽帧对比：

![Matrix-Game 3.0 action-controlled contact sheet](02_matrix_game3/action_controlled/evaluation/huaiqiu_action_controlled_contact_sheet.jpg)

## 目录结构

- `00_reference/`
  - 原始参考图：`槐楸招牌.jpg`
  - 评分标准：`简单评估标准.md`
  - 指标说明与公开参考：`指标说明与参考.md`
  - 人工标注模板：`人工标注模板.csv`
- `01_genie3/`
  - `videos/`：Genie3 生成的两条实景视频
  - `evaluation/`：抽帧、contact sheet、定性评估小结
- `02_matrix_game3/`
  - `inputs/`：Matrix-Game 首帧裁剪和候选图
  - `actions/`：受控 WASD/camera CSV 脚本和 [trajectory protocol](02_matrix_game3/actions/trajectory_protocol.md)
  - `prompt_only_uncontrolled/`：只靠 prompt 指令的非受控结果
  - `action_controlled/`：使用固定 action script 的受控回访结果
  - `smoke/`：action script smoke test
- `03_comparison/`
  - 总对比小结和指标表
- `05_principles/`
  - Matrix-Game 3.0、Genie 2、Genie 3 的原理学习笔记
- `EXPERIMENT_LIMITATIONS.md`
  - 当前实验的问题记录、有效性边界和下一版 benchmark 设计
- `MEDIA.md`
  - 视频、抽帧、contact sheet 和 LFS 说明

## Reference 使用顺序

1. 先看 [槐楸招牌.jpg](00_reference/槐楸招牌.jpg)，确认目标对象是右侧发光中文招牌 `槐楸`。
2. 快速人工评分时，用 [简单评估标准.md](00_reference/简单评估标准.md)。
3. 如果要写成 benchmark 或论文/面试材料，用 [指标说明与参考.md](00_reference/指标说明与参考.md)，它把可见性、回访有效性、文字记忆、店面身份、几何一致性、时间稳定性和失败类型分开定义。
4. 批量标注新视频时，复制 [人工标注模板.csv](00_reference/人工标注模板.csv) 的列结构。
5. 结果汇总看 [comparison_summary.md](03_comparison/comparison_summary.md) 和 [metric_table.csv](03_comparison/metric_table.csv)。
6. 实验有效性边界看 [EXPERIMENT_LIMITATIONS.md](EXPERIMENT_LIMITATIONS.md)。

## 视频说明

`.mp4` 文件使用 Git LFS 跟踪。克隆后如果只看到 LFS pointer，可以运行：

```bash
git lfs pull
```

不下载视频也可以阅读本 repo：关键帧、contact sheet、评分表和总结都已经直接保存在 git 中。完整媒体清单见 [MEDIA.md](MEDIA.md)。

## 推荐指标

本实验最小报告集：

- `T_exact`：最后一个严格读出 `槐楸` 的时间点。
- `T_readable`：最后一个基本能认出 `槐楸` 的时间点。
- `T_garbled`：第一次稳定变成乱码/不可读的时间点。
- `S_60=(text_score, identity_score)`：60 秒附近可见招牌的文字和店面身份分数。

更严格的 benchmark 建议使用：

- `visible_state`：招牌是否可见，避免把不可见误判成遗忘。
- `action_protocol`：动作协议，例如 `free_navigation`、`yaw_return_60s`、`retreat_yaw_return_60s`。
- `video_duration_s`：视频总时长，避免不同时长直接比较。
- `trajectory_matched`：是否和另一系统使用了语义等价的路线。
- `revisit_score`：是否真的回到同一店面。
- `geometry_score`：招牌、门窗、街景相对位置是否稳定。
- `temporal_stability`：相邻时间点是否跳字、闪烁、换招牌。
- `offscreen_gap_s`：目标离开视野多久后被重新找回。
- `confusion_flag`：标记乱码、换牌、复制、错店、几何漂移等失败类型。

完整定义见 [指标说明与参考.md](00_reference/指标说明与参考.md)。

## 主要结论

最清晰的对比见：

- [comparison_summary.md](03_comparison/comparison_summary.md)
- [metric_table.csv](03_comparison/metric_table.csv)

## 结果阅读提示

- Genie3 组更接近自然自由探索，适合观察长时文字漂移；但如果轨迹不可控，严格比较时需要记录 `revisit_score`。
- Matrix-Game 3.0 prompt-only 组没有稳定回到目标店面，因此主要暴露轨迹可控性问题，不应直接算作招牌记忆失败。
- Matrix-Game 3.0 action-controlled 组更适合作为受控 benchmark，其中 `yaw return` 测离屏转头记忆，`retreat+yaw return` 同时测试位移闭环和几何一致性。
