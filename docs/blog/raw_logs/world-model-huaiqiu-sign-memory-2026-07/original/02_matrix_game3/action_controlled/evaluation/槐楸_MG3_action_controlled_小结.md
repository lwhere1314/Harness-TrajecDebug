# 槐楸 Matrix-Game 3.0 Action-Controlled 记忆测试

本轮修改了开源推理代码，增加 `--action_script` / `MG3_ACTION_SCRIPT`，让非交互模式可以读取固定 `frames,mouse,key` CSV 轨迹。

## 生成结果

- `huaiqiu_action_yaw_right_return_60s.mp4`
- `huaiqiu_action_retreat_yaw_return_60s.mp4`
- `huaiqiu_action_controlled_contact_sheet.jpg`

## 脚本

- `../../actions/huaiqiu_yaw_right_return_60s.csv`：原地右转离开，约 49 秒转回原店面方向。
- `../../actions/huaiqiu_retreat_yaw_return_60s.csv`：后退离开，再转向，最后转回并前进接近原位置。

## 简化指标

### Yaw Return

- `T_exact = 59s`
- `T_readable = 59s`
- `T_garbled = NA`
- `S_60 = (3, 3)`

结论：原地转头离开再回访时，Matrix-Game 3.0 在 60 秒附近仍能保留 `槐楸` 招牌文字和店面身份。

### Retreat + Yaw Return

- `T_exact = 5s`
- `T_readable = 59s`
- `T_garbled = NA`
- `S_60 = (2, 2)`

结论：包含位移闭环时，模型能回到类似店面并保留 `槐楸` 的主要形状，但严格文字和构图有明显漂移，60 秒附近更像“可认但变形”，不是精确复现。

## 解释

这说明对 Matrix-Game 3.0 来说，纯视角 yaw 回访比带位移的空间闭环容易得多。前者更像从同一位置重新看同一招牌；后者要求同时恢复相机位置、尺度、店面结构和文字细节，因此更容易出现招牌变形、裁切或局部漂移。
