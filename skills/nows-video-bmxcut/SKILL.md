---
name: nows-video-bmxcut
description: 将长视频通过 BiliMix 配音 + Agent 字幕分析，智能切分为短视频系列。输出含文件路径和推荐指数的 Markdown 方案。适用于播客/课程/访谈转短视频。
agent_created: true
triggers:
  - "视频切片"
  - "bmxcut"
  - "短视频切割"
  - "生成短视频"
  - "BiliMix 切片"
  - "nows-video-bmxcut"
---

# nows-video-bmxcut

将 BiliMix 配音视频的 ASS 字幕文件交给 Agent 直接分析，智能分段后输出 Markdown 切片方案。Agent 可进一步用 FFmpeg 完成实际切割。

---

## Phase 0: 环境初始化（共 5 步，逐项校验，缺一不可）

Agent 调用本 Skill 后，必须先执行以下 5 项校验，一项通过才能进入下一项。每项失败时向用户报告原因并给出修复命令。**任何一项失败都必须在当前步骤修复完成后才能继续，不允许跳过。**

### 检查 0.1 — bmx CLI 是否安装

```
bmx --help
```

- **通过** → 0.2
- **失败（command not found）** → 找 BiliMix SDK：
  ```
  find ~ -maxdepth 4 -path "*/BiliMix/sdk" -type d 2>/dev/null
  ```
  找到 → `cd <目录> && pip install -e .`
  找不到 → 提示：`git clone https://github.com/nowszhao/BiliMix && cd BiliMix/sdk && pip install -e .`

> 若 bmx 命令不完整（如缺少 `--type video` 参数），改用 `python -m bilimix_cli.cli` 替代 `bmx`。

### 检查 0.2 — bmx 能否连接 BiliMix 服务

```
bmx task list
```

- **返回正常 JSON** → 0.3
- **连接失败 / 超时** → 读 `~/.bilimix/config.json`，交互式询问用户正确的 server 地址：
  ```
  bmx --server <用户输入的地址> task list
  ```

### 检查 0.3 — bmx 是否已认证

```
bmx auth status
```

- **logged_in: true** → 0.4
- **401 / 未登录** → 交互式询问用户名密码：
  ```
  bmx auth login --username <用户> --password <密码>
  ```

### 检查 0.4 — 列出已完成视频任务，让用户选择

Agent 自动获取已完成配音的视频列表：

```
bmx task list
```

从返回结果中筛选 `status: "completed"` 且 `type: "video"` 的任务。

**情况 A：有已完成任务** → 以编号列表呈现，让用户选择：

> "BiliMix 上已完成配音的视频：\n
> 1. {title}（{duration}，{created_at}）— task_id: {id}\n
> 2. {title}（{duration}，{created_at}）— task_id: {id}\n
> 请选择要处理的视频（输入编号）："

**情况 B：无已完成任务** → 告知用户并结束：

> "BiliMix 上暂无已完成的视频任务。请先在 BiliMix Web 端提交视频配音，完成后再次运行本 Skill。"

**情况 C：用户在列表中未找到目标** → 提供两种选项：
> 1. "我先去 BiliMix 提交配音，稍后再来"
> 2. "帮我在本地找一个已有的 MP4 + ASS 字幕文件，跳过 BiliMix 下载步骤"

> **不支持手动输入 task_id 或 YouTube URL**——所有任务通过列表选择。如果用户有本地文件，直接跳过 Phase 1 进入 Phase 2。

### 检查 0.5 — FFmpeg 是否安装

```
ffmpeg -version
```

- **通过** → Phase 0 全部完成，进入 Phase 1
- **失败（command not found）** → 按操作系统引导安装：

  **macOS：**
  ```
  # 先检查 Homebrew 是否安装
  which brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # 安装 ffmpeg
  brew install ffmpeg
  ```

  **Linux（Ubuntu/Debian）：**
  ```
  sudo apt update && sudo apt install -y ffmpeg
  ```

  **Linux（CentOS/RHEL）：**
  ```
  sudo yum install -y epel-release && sudo yum install -y ffmpeg
  ```

  **Windows：**
  > 请访问 https://ffmpeg.org/download.html 下载 Windows 版本，解压后将 `bin` 目录加入系统 PATH。

  安装完成后再次执行 `ffmpeg -version` 验证。

**全通过后 Agent 总结：**

> "✅ 环境就绪：bmx ✓ | BiliMix ✓ | 认证 ✓ | 任务 ✓ | FFmpeg ✓ | 开始处理"

---

## Phase 0 总结：校验清单

| 序号 | 校验项 | 命令 |
|------|--------|------|
| 0.1 | bmx 安装 | `bmx --help` |
| 0.2 | BiliMix 连接 | `bmx task list` |
| 0.3 | 认证状态 | `bmx auth status` |
| 0.4 | 选择视频任务 | `bmx task list`（交互式选择） |
| 0.5 | FFmpeg 安装 | `ffmpeg -version` |

**任何一项失败都必须在当前步骤修复后才能继续，不允许跳过。**

---

## Phase 1: bmx 下载文件

根据用户在第 0.4 步选择的 task_id，下载配音视频和字幕：

```bash
mkdir -p outputs

bmx video download --task-id <task_id> -o outputs/dubbed_video.mp4
bmx video download-srt --task-id <task_id> -o outputs/subtitles.ass
```

> 若 bmx 无 video 子命令，改用 `python -m bilimix_cli.cli video download --task-id <task_id> -o ...`
> 下载时显示进度。完成后确认文件存在且大小正常。

---

## Phase 2: Agent 直接读取并解析 ASS 字幕

Agent 使用 Read 工具读取 `outputs/subtitles.ass`。

**ASS 格式说明（BiliMix 双语模式）：**
```
[Events]
Dialogue: 0,0:00:01.00,0:00:04.00,English,,0,0,0,,{\q0}English text
Dialogue: 0,0:00:01.00,0:00:04.00,Chinese,,0,0,0,,{\q1}中文翻译
```

同一时间戳的 English + Chinese 配对为一条对话。若文件过大（几千行），分段读取（每次 500-800 行），累积形成完整对话列表。

> 若是滚动累积式 ASS（FFmpeg 生成的那类），Agent 需先提取完整句子并去重，再进行分析。

---

## Phase 3: Agent 分析内容，生成切片方案

Agent 基于提取的完整对话内容：

1. **通读全部内容**，理解视频的完整叙事结构
2. **识别话题边界**，在自然断点处切分（新概念引入、章节切换、讲述节奏变化）
3. **每段 2-10 分钟**，确保内容闭环（有开头、有核心、有收尾）
4. **全部段落连续覆盖全视频**，无遗漏、无重叠
5. **为每段生成元数据**：

| 字段 | 要求 |
|------|------|
| `start` / `end` | `HH:MM:SS` 格式 |
| `duration` | 如 `5分23秒` |
| `file` | `clips/clip_NNN.mp4` |
| `title` | 吸引力标题，12-25 字，含 emoji 前缀（🎬 常规，🔥 最推荐） |
| `description` | 60-120 字，讲清核心看点和价值，让人想点进去 |
| `tags` | 5-6 个关键词，逗号分隔 |
| `rating` | 1-5 星（★），**仅 1 个五星**——整期最核心、最具传播力的片段 |

### 标题写作规范

**必须吸引眼球但不能标题党。** 好的标题让用户在刷到时停下来、点进去，看完后觉得「确实如标题所说」。

**推荐模式（按优先级排序）：**

| 模式 | 示例 |
|------|------|
| 反常识 / 冲突 | 「为什么最懂技术的人反而不写代码了？」 |
| 权威背书 | 「Netflix CPTO 亲述：AI 时代最值钱的能力不是编程」 |
| 悬念 / 好奇心缺口 | 「大部分人对 AI 的理解都漏掉了最关键的一步」 |
| 具体数据 / 量化 | 「这家公司 20 年前写下的原则，竟完美押中 AI 时代」 |
| 痛点直击 | 「你的职位正在被 AI 模糊掉——该怎么办？」 |
| 场景代入 | 「当你的 PM 开始写代码、设计师开始写 PRD…」 |

**禁止的写法：**
- ❌ 空洞堆砌：`深度解析 AI 时代的组织变革与人才战略`
- ❌ 标题党：`震惊！AI 竟然让这家公司彻底变了`
- ❌ 照搬原标题：`Elizabeth Stone 访谈实录`
- ✅ 正确的：`🔥 Netflix 为什么要「减少专才、增加通才」？CPTO 的答案让人信服`

### 简介写作规范

**60-120 字，三段式结构：**
1. **钩子句（1 句）**：直接点出这段最反直觉或最有价值的一个观点
2. **展开（1-2 句）**：简要说明背景和核心论证
3. **价值承诺（1 句）**：暗示看完能获得什么

**示例：**
> AI 时代最稀缺的不是代码写得最好的人，而是能跨领域看到全局的人——这就是 Netflix CPTO Elizabeth Stone 的核心论断。她解释了为什么公司正在刻意减少纯专才的招聘，转而押注「系统思考者」。如果你在思考自己的职业方向，这段话可能会改变你的判断。

**评级标准：**
- ★★★★★（仅 1 个）：标题级论点，独立闭环度最高，最具传播力
- ★★★★☆：内容扎实，独立观赏性好，适合系列分发
- ★★★☆☆：过渡性或上下文依赖较强
- 不使用 ★★☆☆☆ 和 ★☆☆☆☆（除非内容确实不适合单独切片）

---

## Phase 4: 输出 Markdown 方案

Agent 输出 Markdown 文件，**仅包含标题 + 副标题 + 表格，不加任何其他内容**：

```markdown
## 📊 短视频切片方案 — {视频标题}

> 来源：{播客名/频道名} · {主讲人} | 总时长：{X时X分X秒} | 切片数：{N} 个

| # | 时间 | 时长 | 文件 | 标题 | 简介 | 标签 | 推荐 |
|---|------|------|------|------|------|------|------|
| 1 | 00:00–02:29 | 2分29秒 | clips/clip_001.mp4 | 🎬 当所有人都在学 AI 时，Netflix 却在偷偷招「不会写代码的人」 | AI 时代每个人都觉得自己必须学编程，但 Netflix CPTO Elizabeth Stone 给出了完全相反的信号——她正在减少纯技术专才的招聘。这个只有 2 分钟的开场告诉你这期节目为什么值得看完。 | Netflix, AI, 招聘趋势, 通才, 职业规划 | ★★★☆☆ |
| 2 | 02:29–08:00 | 5分31秒 | clips/clip_002.mp4 | 🎬 你的职位正在被 AI 吃掉——但这不是坏事 | 「每个人都觉得自己什么都能做了，那还有专业分工吗？」Elizabeth 直面这个问题：AI 让 PM 能写代码、设计师能做数据，但这不是取消责任归属的理由——关键在于知道「谁最后负责」。 | 岗位边界, 职能协作, 产品管理, 设计师, AI影响 | ★★★★☆ |
| 3 | 08:00–14:00 | 6分00秒 | clips/clip_003.mp4 | 🔥 Netflix 为什么开始「反专才」？CPTO 的答案可能改变你的职业选择 | **[本集最推荐]** AI 时代最稀缺的不是代码写得最好的人，而是能跨领域看到全局的系统思考者。她解释了为什么 Netflix 正在刻意减少纯专才的招聘，转而押注「能看到整个棋盘」的人。如果你在思考自己的职业方向，这段话可能会改变你的判断。 | 系统思考, systems thinker, 通才, Netflix, 职业选择 | ★★★★★ |
```

**格式约束（每次必须严格一致）：**
- 8 列表头顺序：`# | 时间 | 时长 | 文件 | 标题 | 简介 | 标签 | 推荐`
- 星级符号：`★` `☆`
- 标题含 emoji 前缀（🎬 常规，🔥 唯一五星）
- 标签逗号分隔，无空格
- 文件路径：`clips/clip_NNN.mp4`
- 文件保存为 `outputs/{主题}_短视频切片方案.md`

---

## Phase 5: FFmpeg 切割视频（可选）

```bash
mkdir -p outputs/clips

# 按 segments.json 中的时间批量切割
ffmpeg -y -ss 00:00:00 -i video.mp4 -t 149 -c copy -avoid_negative_ts make_zero outputs/clips/clip_001.mp4
ffmpeg -y -ss 00:02:29 -i video.mp4 -t 331 -c copy -avoid_negative_ts make_zero outputs/clips/clip_002.mp4
# ...
```

优先使用 `-c copy` 流复制（无损快切），失败时回退 `-c:v libx264 -c:a aac`。

---

## 最终输出

```
outputs/
├── dubbed_video.mp4                       # BiliMix 配音视频
├── subtitles.ass                          # ASS 双语字幕
├── segments.json                          # 分段数据（中间产物，可选保留）
├── {主题}_短视频切片方案.md                # 最终 Markdown 方案
└── clips/
    ├── clip_001.mp4 → clip_012.mp4        # 切片视频
```
