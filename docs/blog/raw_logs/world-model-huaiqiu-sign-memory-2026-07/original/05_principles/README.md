# Matrix-Game 3.0 vs Genie 2/3 原理学习笔记

这份笔记服务于 `槐楸` 中文招牌记忆一致性实验：用 Matrix-Game 3.0 的公开论文/代码，以及 Genie 2/3 的 Google DeepMind 官方博客和 model page，理解交互式 world model 的基本原理、能力边界和适合本实验的评价方式。

资料边界：

- Matrix-Game 3.0: [arXiv](https://arxiv.org/abs/2604.08995), [GitHub](https://github.com/SkyworkAI/Matrix-Game), [Matrix-Game-3 README](https://github.com/SkyworkAI/Matrix-Game/tree/main/Matrix-Game-3)
- Genie 2: [Google DeepMind official blog](https://deepmind.google/blog/genie-2-a-large-scale-foundation-world-model/)
- Genie 3: [Google DeepMind official blog](https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/), [Genie model page](https://deepmind.google/models/genie/)

## 一句话框架

这三类系统都可以理解为：给定初始视觉/文本条件和用户动作，持续生成未来视觉观测的交互式 world model。差别在于：

- Matrix-Game 3.0 是公开工程路线：数据、动作条件、memory retrieval、streaming rollout、distillation 和加速策略都有较多披露。
- Genie 2 是从单张 prompt image 进入可玩世界：官方披露为 autoregressive latent diffusion model，但没有公开代码/权重。
- Genie 3 是 text-to-world 的实时交互系统：官方强调 720p、20-24fps、几分钟一致性和 promptable world events，但核心架构与训练 recipe 未公开。

## 对比表

| 维度 | Matrix-Game 3.0 | Genie 2 | Genie 3 |
| --- | --- | --- | --- |
| 开源性 | GitHub 开源，公开 5B base/distilled 权重；更大 MoE/混合数据模型仍未完全发布 | 未开源，仅官方展示 | 非开源，limited research preview / Project Genie |
| 输入 | 初始图像 + text prompt + keyboard/mouse action + camera/pose 条件 | 单张 prompt image + 每步 keyboard/mouse action | 文本 world description / character prompt + 实时导航 + world events |
| 生成方式 | autoregressive multi-segment streaming；首段 I2V，后续段使用 history + memory | autoregressive latent diffusion；用 autoencoder latent + transformer dynamics model | 官方只披露 autoregressive frame generation，未披露具体架构 |
| 记忆机制 | camera-aware memory retrieval；memory/history/current latent 放进 unified self-attention；relative Plucker geometry | 官方称可记住离屏世界部分，最长约 1 分钟 | 官方称 visual memory 可回到约 1 分钟前，几分钟环境一致性；机制未披露 |
| 训练数据 | UE5 synthetic、AAA game 自动采集、real-world videos；目标是 Video-Pose-Action-Prompt quadruplet | large-scale video dataset，细节未披露 | model page 称 grounded in Google Maps Street View data；细节未披露 |
| 实时性 | 论文称 5B 720p up to 40 FPS，依赖 INT8、LightVAE、GPU retrieval、异步 VAE 等 | 实时 playable distilled version，但官方说质量低于 base | 720p, 20-24 FPS，可连续交互几分钟 |
| 官方限制 | 未单独列 limitations；但公开权重/硬件/数据范围有限，40 FPS 依赖多 GPU | 早期研究，实时蒸馏牺牲质量，一致性还有提升空间 | action space 有限、多 agent 难、真实地点不完美、文字渲染受限、只能几分钟 |

## Matrix-Game 3.0：公开工程路线

Matrix-Game 3.0 把自己定位为 memory-augmented interactive world model。它不是传统显式 3D engine，也不是只生成固定视频的 video model，而是在用户动作条件下持续生成视觉世界。

### 数据 Pipeline

论文核心数据目标是 `Video-Pose-Action-Prompt` quadruplet：

- `Video`: 世界视觉观测。
- `Pose`: 相机/角色位姿，支撑可控相机和 memory retrieval。
- `Action`: WASD / mouse 等用户动作。
- `Prompt`: 自动标注生成的场景/事件/相机描述。

三类数据互补：

- UE5 synthetic 数据：优点是 pose/action 精准同步，适合训练动作-相机-视觉之间的因果关系。
- AAA game 自动录制：补足商业游戏级动态、复杂视觉、第三人称/第一人称交互。
- Real-world videos：补真实光照、真实相机轨迹、城市/室内长尾视觉分布。

### 训练机制

官方披露的几个关键点：

- 基于 Wan2.2-TI2V-5B 的 video diffusion backbone。
- keyboard 离散动作通过 cross-attention 注入；mouse 连续控制通过 self-attention 注入。
- residual modeling / self-correction：训练时模拟 autoregressive 推理中的历史误差，让模型学会从不完美 history 中继续生成。
- camera-aware memory：按 camera pose / FOV overlap 检索历史 latent，再用 relative Plucker encoding 对齐几何。
- memory、recent history、current noisy latent 进入同一个 self-attention 空间，模型只预测当前新帧。

### 推理过程

Matrix-Game 3.0 不是逐帧渲染 RGB，而是按短视频 chunk 自回归生成：

- 首段是 image-to-video，无 long-term memory。
- 后续段使用上一段尾部作为 recent history。
- 同时从在线 memory pool 中按当前 camera/FOV 检索历史 latent。
- 生成的新 latent 追加回 memory/history，供后续段继续使用。

公开代码中，常见设置是：

```text
total_frames = 57 + (num_iterations - 1) * 40
```

也就是首段约 57 帧，后续每段新增约 40 帧，中间有重叠 history。

### 实时化

Matrix-Game 3.0 的实时不是单个技巧，而是一组工程优化：

- DMD distillation：把多步 diffusion 压到 few-step streaming inference。
- INT8 quantization：主要量化 DiT attention projection。
- MG-LightVAE：轻量 VAE decoder，减少高分辨率解码瓶颈。
- GPU memory retrieval：让 memory 检索不成为实时生成瓶颈。

对我们的实验来说，这些优化可能影响中文文字细节：distillation、VAE compression 和 pruning 都可能保留大结构但损失细笔画。

## Genie 2：单图进入可玩世界

Genie 2 官方定义为 large-scale foundation world model。它的入口是单张 prompt image：这张图可以来自 Imagen 3，也可以是真实图片。用户或 agent 用 keyboard/mouse action 驱动世界，模型自回归生成后续观察。

官方明确披露：

- 技术类型是 autoregressive latent diffusion model。
- 图像先经 autoencoder 进入 latent space。
- large transformer dynamics model 用 action + past latent frames 预测后续 latent。
- causal mask 支撑按时间推进的生成。
- classifier-free guidance 用来增强 action controllability。

官方能力描述包括：

- 能记住离屏世界部分，并在重新可见时恢复。
- 最长约一分钟一致性，多数展示样例为 10-20 秒。
- 能展示 3D 结构、角色动画、物体 affordance、NPC、简单物理、光照和反射。

但 Genie 2 没有公开代码、权重、训练数据构成、参数量、动作编码细节，也没有专门披露文本/OCR/中文能力。

## Genie 3：文本到实时可探索世界

Genie 3 官方定义为 general-purpose world model。相较 Genie 2，它把入口从 prompt image 推到 text-to-world：用户给世界描述，系统生成一个可实时导航的动态世界。

官方明确能力：

- 720p。
- 20-24 FPS / 24 FPS 实时交互。
- 几分钟环境一致性。
- visual memory 可追溯到约一分钟前。
- 支持 promptable world events，例如改变天气、加入物体或角色。

官方明确限制：

- action space 仍有限。
- 多 agent 共享环境交互仍难。
- 不能完美模拟真实地理位置。
- 文本渲染有限：清晰可读文本通常需要在输入 world description 中提供。
- 连续交互是几分钟，不是数小时。

需要特别保守的一点：Genie 3 官方没有披露具体 memory architecture。我们不能说它用了 Matrix-Game 3.0 式 camera-aware retrieval，只能说它在能力层面展示了 visual memory / consistency。

## 对槐楸招牌实验的解释

`槐楸` 招牌是一个很好的 stress test，因为它把三类能力绑在一起：

1. 视觉局部细节：中文笔画密集，压缩/扩散/蒸馏很容易损失。
2. 空间记忆：离开视野后再回来，招牌必须回到正确位置。
3. 语义身份：不是“像中文”就行，而是必须还是 `槐楸` 两个字。

对应到模型机制：

- Matrix-Game 3.0 的 camera-aware memory retrieval 应该帮助“回到同一视角时恢复同一店面/招牌位置”。
- Matrix-Game 3.0 的 VAE/distillation/pruning 可能是中文小字变形的风险来源。
- Genie 2/3 的官方能力说明支持“离屏记忆”这个实验方向，但不支持声称它们有符号级中文文本记忆。
- Genie 3 官方明确说文本渲染有限，因此 `槐楸` 乱码不是意外边角失败，而是正好命中官方限制。

### 当前实验的有效性边界

当前这组实验是有效的 `same-target diagnostic stress test`，但还不是严格的 `matched head-to-head benchmark`。

它有效，因为目标对象一致，问题一致：都在观察 `槐楸` 这个中文招牌在移动、离屏、回访后的文字可读性和对象身份。

它还不够严格，因为：

- Genie3 的视频来自 free navigation / 手动探索。
- Matrix-Game 3.0 的主要有效结果来自固定 action script。
- 两者动作接口、相机速度、路线形状不完全可比。
- Genie3 视频约 70 秒，Matrix-Game 3.0 主要视频约 60 秒。

因此，当前结果适合比较 failure mode，例如“中文乱码”“几何漂移”“未成功回访”；不适合直接做模型排行榜。若要写进 CV 或面试，可以说：

> I designed a same-target diagnostic benchmark for Chinese sign memory, then documented the caveat that the current Genie3 and Matrix-Game 3.0 runs are not trajectory-matched. The current study compares failure modes; a stricter benchmark would normalize action protocol, video duration, offscreen gap, and revisit success.

## 推荐指标

把现有指标和原理对应起来：

- `text_score`: 测符号/字形保持，不等价于整体画质。
- `identity_score`: 测同一店面/同一招牌身份。
- `action_protocol`: 记录是 free navigation、yaw return 还是 retreat+yaw return。
- `video_duration_s`: 记录视频总时长，避免不同时长直接比较。
- `trajectory_matched`: 标记两个系统是否使用语义等价路线。
- `revisit_score`: 测动作控制和回访是否成功，避免把“没回到店面”误算成“忘记招牌”。
- `geometry_score`: 测招牌、门窗、街道结构关系是否稳定。
- `temporal_stability`: 测相邻帧是否跳字、闪烁、换牌。
- `offscreen_gap_s`: 测真正离屏记忆时间，而不是视频总时长。

更进一步可以做：

- OCR / 人工字符编辑距离：`槐楸` 到生成文字的字符距离。
- sign crop SSIM/LPIPS：只看招牌区域，不让全图质量稀释小文字错误。
- bbox drift：招牌位置是否漂移。
- controlled trajectory success：同一动作脚本下能否稳定回到目标区域。

## 面试 5 分钟讲法

我会这样讲：

> 这个实验的动机是，我发现现有交互式 world model 在整体场景一致性上已经很强，但中文文字这种局部、密集、语义明确的对象仍然很脆弱。所以我没有只看视频好不好看，而是选了一张自己拍摄的什刹海店面照片，固定观察 `槐楸` 招牌，测试模型在移动、转头、离屏再回访后，是否还能保持同一块招牌和同样的中文文字。

然后接 Matrix-Game：

> Matrix-Game 3.0 是适合复现的开源路线。它把交互式 world model 拆成数据、动作条件、记忆检索、streaming rollout 和实时化几个模块。最关键的是 camera-aware memory retrieval：当相机回到过去看过的位置，它会从 memory pool 里取出视角相关的历史 latent，用相机几何编码对齐，再和当前 noisy latent 一起生成后续片段。这解释了为什么我们要设计 yaw return 和 retreat+yaw return 这种受控回访轨迹。

再接 Genie：

> Genie 2/3 更像闭源能力边界展示。Genie 2 从单图进入可玩世界，官方披露为 autoregressive latent diffusion；Genie 3 进一步做 text-to-world，720p 实时交互，并展示几分钟一致性。但 Google 官方也明确说 Genie 3 的文本渲染有限，清晰可读文本通常需要在输入描述中提供。所以我们的中文招牌实验不是随便挑的 case，而是在测一个官方也承认仍困难的局部记忆问题。

最后讲评价：

> 因此我把 benchmark 拆成文字可读性、店面身份、回访有效性、几何一致性、离屏时间和时间稳定性。这样可以区分三种失败：没有回到店面、回到了但店面变了、店面还在但中文变乱码。这比只用 FVD/整体视觉质量更适合评价交互式 world model 的长期记忆。

## 不能过度声称

- 不能说 Matrix-Game 3.0 全面优于 Genie 3；二者没有统一公开 benchmark、硬件、数据和交互协议。
- 不能说 Genie 3 的记忆机制等同于 Matrix-Game 3.0 的 camera-aware retrieval；Google 没有披露内部机制。
- 不能说 Genie 2/3 可复现；它们没有公开代码/权重。
- 不能说 `槐楸` 实验证明模型具备真实物理理解或地图级重建；更稳妥的表述是：它测试局部文字记忆、视觉身份保持、回访一致性和交互控制。
- 不能把 Matrix 论文里的 VAE PSNR/SSIM 直接当成 world model 质量指标；它们主要说明解码器压缩/加速的保真度。

## 后续实验设计

建议扩展为三组：

1. 视角回访：yaw return、retreat+yaw return、绕行 return。
2. 文字难度：大字/小字、中文/英文、常见词/随机汉字、中心/边缘。
3. 干扰事件：下雪、夜晚开灯、路人遮挡、车辆经过、旁边新增招牌。

最有价值的对照：

- Matrix-Game 3.0 base 50-step vs distilled 3-step。
- MG-LightVAE 不同版本。
- 首帧含招牌 vs 中途才出现招牌。
- prompt 明确写 `槐楸` vs 不写。
