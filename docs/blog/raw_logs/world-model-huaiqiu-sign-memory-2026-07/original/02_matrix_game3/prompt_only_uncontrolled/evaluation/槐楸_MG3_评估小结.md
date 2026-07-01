# 槐楸招牌 Matrix-Game 3.0 简化评估小结

输入首帧：`/Users/hugo/Documents/世界模型面试/记忆一致性实验/02_matrix_game3/inputs/huaiqiu_first_frame_1280x704.jpg`

生成视频：

- `../videos/huaiqiu_mg3_memory_01_loop_return.mp4`
- `../videos/huaiqiu_mg3_memory_02_side_revisit.mp4`

抽帧表：

- `huaiqiu_mg3_memory_contact_sheet.jpg`

## 简化评分结论

两条视频在 `0s` 都能清楚看到 `槐楸` 招牌，因此首帧评分为：

- `text_score = 3`
- `identity_score = 3`

但从 `5s` 开始，两条视频都已经离开店面/招牌视野，并且到 `59s` 仍没有返回同一店面。因此：

- `T_exact = 0s`
- `T_readable = 0s`
- `T_garbled = NA`
- `S_60 = NA`

## 解释

这两条不能作为严格的“60 秒后招牌文字是否仍然一致”的记忆测试，因为模型没有完成预期的回访轨迹。更准确的结论是：

> 在当前公开非交互推理脚本下，prompt 中写“离开后回到槐楸店面”并不能可靠控制实际相机轨迹；因此本次实验主要暴露的是轨迹/可控性限制，而不是单纯的文字记忆退化。

要严格评估记忆，需要改成固定 action script 或交互模式录制键鼠轨迹，确保相机真的在 30s/60s 回到同一个招牌视角。
