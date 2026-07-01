# 实验问题记录 / Experiment Limitations

这份文件记录当前 `槐楸` 中文招牌记忆一致性实验的有效性边界。目的是避免把一个有价值的 diagnostic stress test 误写成严格公平的模型排行榜。

## 当前实验定位

当前版本应定位为：

```text
same-target diagnostic stress test
```

也就是：用同一个目标对象 `槐楸` 招牌，观察 Genie3 和 Matrix-Game 3.0 在移动、离屏、回访后的中文文字记忆和店面身份保持。

当前版本不应定位为：

```text
matched head-to-head benchmark
```

因为两个系统的动作协议、轨迹、视频时长和回访条件没有完全对齐。

## 主要问题

### 1. 动作协议不一致

Genie3 组来自 free navigation / 手动探索，Matrix-Game 3.0 组包含 prompt-only 和固定 action script。

这意味着：

- 两边不是同一条路线。
- 两边的视角变化、速度、转向幅度不可直接等价。
- 不能默认 Genie3 的移动动作和 Matrix-Game 3.0 的 WASD/mouse action 语义完全一致。

影响：当前结果可以比较 failure mode，但不能直接用 `T_readable` 或 `S_60` 做严格排名。

### 2. 视频时长不一致

现有视频大致为：

- Genie3: 约 71.2 秒。
- Matrix-Game 3.0 action-controlled: 约 59.8 秒。

影响：不能只看 `60s` 或 `70s` 这样的绝对时间点来判断哪个模型更强。更公平的指标应该是：

- 目标离屏多久：`offscreen_gap_s`
- 目标重新可见的时间：`first_valid_revisit_s`
- 回访是否有效：`revisit_score`

### 3. 离屏时间和回访时间不匹配

中文招牌记忆真正要测的是“离开视野以后多久还能恢复”。如果一个视频中招牌一直在附近，另一个视频中招牌离屏很久，二者难度不同。

影响：必须报告 `offscreen_gap_s`，不能只报告视频总时长。

### 4. 回访成功率会污染文字记忆判断

Matrix-Game 3.0 prompt-only 组没有稳定回到目标店面。这种情况不能算作文字记忆失败，而应算作 trajectory / controllability failure。

影响：评分时应先看 `revisit_score`，再看 `text_score`。

### 5. 输入条件和接口不同

Matrix-Game 3.0 使用首帧图像、prompt、WASD/mouse/action script；Genie3 是闭源交互系统，具体内部动作编码、相机响应和记忆机制不可见。

影响：不能声称两个系统在完全相同条件下比较；只能说它们在当前可用接口下进行了同一目标对象测试。

### 6. 中文文字记忆与整体画质不是同一个问题

一个视频可以整体真实、连贯，但招牌文字变成乱码。反过来，招牌可读也不代表整个世界模型更强。

影响：本实验主要评价局部文本记忆和回访一致性，不评价模型整体能力。

## 当前结果可以支持的结论

- 中文招牌是一个有效的 world model 局部记忆压力测试。
- Genie3 在当前 free navigation 视频中出现了长时中文文字漂移。
- Matrix-Game 3.0 在当前 action-controlled 回访视频中能较稳定地保持 `槐楸` 招牌，但带位移闭环时仍出现文字和几何漂移。
- `revisit_score`、`text_score`、`identity_score`、`geometry_score` 比单纯 FVD/整体观感更适合分析这个问题。

## 当前结果不应支持的结论

- 不能声称 Matrix-Game 3.0 全面优于 Genie3。
- 不能声称 Genie3 一定不具备中文招牌记忆能力，因为当前没有 matched action protocol。
- 不能把 “没有回到店面” 写成 “忘记了招牌”。
- 不能把 Matrix-Game 3.0 的纯 yaw 回访结果直接等同于更复杂的自由探索能力。

## 下一版严格 Benchmark 设计

要升级到 `matched protocol benchmark`，建议统一以下条件：

1. 使用同一目标对象和同一初始视角。
2. 设定语义等价动作协议，例如：
   - `look_at_sign_5s`
   - `turn_away_20s`
   - `move_forward_20s`
   - `return_to_sign_20s`
3. 统一视频时长，例如 60 秒、90 秒、120 秒。
4. 统一采样点，例如 `0s, 5s, 10s, 20s, 30s, 45s, 60s`。
5. 记录 `offscreen_gap_s`、`revisit_score`、`trajectory_matched`。
6. 至少每个系统跑 3-5 条重复样本，避免单例偶然性。
7. 对招牌区域做单独 crop，再做人评/OCR/字符编辑距离/局部相似度。

## 建议在 CV 或面试中的表述

推荐表述：

> I designed a same-target diagnostic stress test for Chinese sign memory in interactive world models. The current runs are not trajectory-matched, so I report them as failure-mode analysis rather than a strict model ranking. The study highlights that local Chinese text memory and scene revisitation should be evaluated separately from overall video quality.

不推荐表述：

> Matrix-Game 3.0 beats Genie3 on Chinese text memory.

更稳妥的中文表述：

> 这个实验不是为了直接给 Matrix-Game 3.0 和 Genie3 排名，而是用同一个中文招牌目标暴露交互式 world model 的局部文字记忆和回访一致性问题。当前版本动作轨迹不完全匹配，因此结论聚焦 failure mode；下一版会统一动作协议和离屏时间后再做严格 benchmark。

