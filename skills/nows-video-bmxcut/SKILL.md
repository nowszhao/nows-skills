---
name: nows-video-bmxcut
description: 将长视频通过 BiliMix 配音 + Agent 字幕分析，智能切分为短视频系列，并一键批量定时发布到微信视频号。覆盖全流程：BiliMix 下载 → 字幕分析 → 智能分段 → FFmpeg 切割 → 视频号批量定时发表。适用于播客/课程/访谈转短视频并发布。
agent_created: true
triggers:
  - "视频切片"
  - "bmxcut"
  - "短视频切割"
  - "生成短视频"
  - "BiliMix 切片"
  - "nows-video-bmxcut"
  - "发布到视频号"
  - "切片并发布"
  - "切视频发视频号"
---

# nows-video-bmxcut

将 BiliMix 配音视频的 ASS 字幕文件交给 Agent 直接分析，智能分段后输出 Markdown 切片方案。Agent 可进一步用 FFmpeg 完成实际切割，并通过浏览器自动化一键批量定时发布到微信视频号。

## 可配置默认值（视频号发布用）

发布前向用户确认以下参数，用户可按需修改，默认值为上次使用的配置：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 短标题 | `Agentic知识图谱` | 所有切片统一使用 |
| 合集 | `吴恩达-从零开始构建Agent知识图谱` | 视频号合集名 |
| 位置 | `不显示位置` | 固定 |
| 标签 | `#知识图谱 #智能体 #AI #Agent` | 空格分隔 |
| 时间间隔 | 60 分钟 | 相邻视频发表间隔 |
| 起始时间 | 从已发布队列最后时间 + 间隔推算 | 若队列空则询问用户 |
| 描述格式 | `【{N}】{emoji} {标题}\n{简介}\n{标签}` | N 从 0 或 1 起始 |
| 起始切片编号 | 从方案的第 1 个开始 | 用户可指定从第 N 个开始发 |

> 发布前必须呈现完整定时发表预览表，让用户确认后再执行。

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

### 检查 0.6 — agent-browser 是否安装（视频号发布需要）

```
which agent-browser && node -e "console.log('ok')"
```

- **通过** → Phase 0 全部完成
- **失败** → 安装：
  ```
  npm install -g agent-browser
  agent-browser install
  ```

**全通过后 Agent 总结：**

> "✅ 环境就绪：bmx ✓ | BiliMix ✓ | 认证 ✓ | 任务 ✓ | FFmpeg ✓ | agent-browser ✓ | 开始处理"

---

## Phase 0 总结：校验清单

| 序号 | 校验项 | 命令 |
|------|--------|------|
| 0.1 | bmx 安装 | `bmx --help` |
| 0.2 | BiliMix 连接 | `bmx task list` |
| 0.3 | 认证状态 | `bmx auth status` |
| 0.4 | 选择视频任务 | `bmx task list`（交互式选择） |
| 0.5 | FFmpeg 安装 | `ffmpeg -version` |
| 0.6 | agent-browser 安装 | `which agent-browser && node -e "console.log('ok')"` |

**任何一项失败都必须在当前步骤修复后才能继续，不允许跳过。**

---

## Phase 1: 下载文件

根据用户在第 0.4 步选择的 task_id，下载配音视频和字幕。

从 `bmx task result <task_id>` 中提取 basename（如 `audio_xxx_xxx`）。读取 `~/.bilimix/config.json` 获取 server 地址。

**下载 dubbed 视频：** 路径格式为 `/api/audio/{basename}/{basename}_dubbed.mp4`

```bash
mkdir -p outputs
SERVER=$(python3 -c "import json; print(json.load(open('$HOME/.bilimix/config.json'))['server'])")
curl -L -o outputs/dubbed_video.mp4 "${SERVER}/api/audio/{basename}/{basename}_dubbed.mp4"
```

**下载 ASS 字幕：**
```bash
curl -L -o outputs/subtitles.ass "${SERVER}/api/audio/{basename}/{basename}.ass"
```

**下载 dubbed 音频**（备用，用于 FFmpeg 合音轨）：
```bash
bmx audio download --task-id <task_id> --type mixed -o outputs/dubbed_audio.mp3
```

> 若 `_dubbed.mp4` 返回 404，试 `_mixed.mp4` 或从 task list 的 `url` 字段中的原始文件名。
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

## Phase 5: FFmpeg 切割视频

```bash
mkdir -p outputs/clips

# 按切片方案中的时间批量切割
ffmpeg -y -ss 00:00:00 -i outputs/dubbed_video.mp4 -t 224 -c copy -avoid_negative_ts make_zero outputs/clips/clip_001.mp4
ffmpeg -y -ss 00:03:44 -i outputs/dubbed_video.mp4 -t 350 -c copy -avoid_negative_ts make_zero outputs/clips/clip_002.mp4
# ...
```

优先使用 `-c copy` 流复制（无损快切），失败时回退 `-c:v libx264 -c:a aac`。
验证所有切片文件存在且大小 > 1MB。

---

## Phase 6: 视频号批量定时发布

用户确认发布参数后，通过 agent-browser 自动化 channels.weixin.qq.com 逐个填写表单并定时发表。

> **前置条件**：Phase 0.6 的 agent-browser 已安装，用户已确认发布参数。

### ⚠️ 视频号操作六大原则（吸取自生产环境实战经验）

1. **只用 snapshot + eval，不要依赖截图。** 截图费时且不可靠，用 `snapshot` 读页面文本、用 `snapshot | grep` 提取关键字段、用 `eval` 执行 JS 获取精确值。一切决策基于文本数据，截图仅作辅助确认。

2. **所有表单操作通过 eval 穿透 shadow DOM。** `agent-browser click @ref` 无法穿透 `wujie-app` shadow DOM，会报 "covered by wujie_iframe"。所有点击、赋值用 `eval` 在 `wujie-app.shadowRoot > html > body` 内执行。

3. **file input 先移到 document.body 再 upload。** shadow DOM 内的 `<input type="file">` 对 `agent-browser upload` 不可见。每次上传前：`document.body.appendChild(input)`。

4. **不要让 date picker 悬空。** 改完时间后**立即**点一个安全的 label（如「视频标注」）让 picker 关闭并同步 React state。**绝对不能点「视频管理」标题**——那会触发离开确认弹窗，数��全部丢失。

5. **发表按钮必须 eval 点，不能用 agent-browser click。** 发表按钮被 wujie iframe 覆盖，只能通过 shadow DOM 内的 JS `btn.click()` 触发。

6. **一个 daemon 走到底。** 整个 Phase 6 期间**不要 `agent-browser close`**，保持 daemon 运行使得登录态在所有视频间复用。

### 6.1 登录视频号

```bash
agent-browser open "https://channels.weixin.qq.com/platform/post/create"
agent-browser wait --load load
```

检查是否在登录页：
```bash
agent-browser snapshot | grep "微信快捷登录"
```
若有，点击登录按钮，等待用户扫码。**首次需要扫码，后续切片复用同一 daemon 的登录态。**

> ⚠️ 整个 Phase 6 期间**不要 `agent-browser close`**——保持 daemon 运行，登录状态才能复用。

### 6.2 逐个切片定时发表

对每个待发布的切片（从用户指定的起始编号开始），按以下步骤操作。

**关键架构知识**：视频号助手使用 wujie 微前端，所有表单元素在 `wujie-app` shadow DOM 内的 `<html> > <body>` 下。`agent-browser click @ref` 不穿透此 shadow DOM，必须用 `eval` 执行 JS。详情参见 `references/wujie-dom.md`。

#### Step a: 进入发表动态页

从首页点击「发表视频」按钮：

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const btn = Array.from(body.querySelectorAll('button')).find(b => b.innerText.includes('发表视频')); if (btn) btn.click(); return 'clicked'; })()"
agent-browser wait 2000
```

#### Step b: 上传视频

File input 在 shadow DOM 中，agent-browser 无法直接访问。先 appendChild 到 document.body：

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const input = body.querySelector('input[type=file]'); document.body.appendChild(input); return 'moved'; })()"
agent-browser upload "input[type='file']" "/absolute/path/to/outputs/clips/clip_NNN.mp4"
```

等待上传完成（出现「选择合集」即表示表单就绪）：
```bash
agent-browser wait 3000
agent-browser snapshot | grep "选择合集"
```

#### Step c: 填写视频描述

描述字段是 `contenteditable=""` div class=`input-editor`。逐行 keyboard.type：

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); body.querySelector('.input-editor').focus(); return 'focused'; })()"
agent-browser keyboard type "【{N}】{emoji} {title}"
agent-browser press Enter
agent-browser keyboard type "{description text}"
agent-browser press Enter
agent-browser keyboard type "{tags}"
```

#### Step d: 填写短标题

JS 直接设值比 keyboard.type 更快更稳：
```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const t = body.querySelector('input[placeholder*=\"短标题\"]'); if (t) { t.focus(); t.value = '{短标题}'; t.dispatchEvent(new Event('input', {bubbles: true})); } return 'done'; })()"
```

#### Step e: 位置 → 不显示位置

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const el = body.querySelector('.post-position-wrap .position-display-wrap'); if (el) el.click(); return 'clicked'; })()"
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const all = Array.from(body.querySelectorAll('*')); const item = all.find(e => e.innerText && e.innerText.trim() === '不显示位置' && e.children.length < 5); if (item) item.click(); return 'clicked'; })()"
```

#### Step f: 选择合集

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const el = body.querySelector('.post-album-display-wrap'); if (el) el.click(); return 'clicked'; })()"
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const items = body.querySelectorAll('.option-item'); for (const item of items) { if (item.innerText.includes('{合集名匹配关键词}')) { item.click(); return 'clicked'; } } return 'not found'; })()"
```

#### Step g: 启用定时发表

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const radio = body.querySelectorAll('input[type=radio]')[1]; if (radio) radio.click(); return 'clicked'; })()"
```

#### Step h: 设置定时时间

Focus 主时间字段打开 ant-design date picker，fill 时间输入框，关闭 picker 提交：

```bash
# 1. Focus 主时间输入打开 picker
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const inputs = Array.from(body.querySelectorAll('input')).filter(i => i.value && i.value.includes('2026-')); if (inputs.length > 0) inputs[0].focus(); return 'found'; })()"
agent-browser wait 1000

# 2. 获取 picker 内时间输入框的 ref
agent-browser snapshot | grep "textbox.*请选择时间"  # → ref=e66

# 3. 填入时间
agent-browser fill <ref> "HH:00"

# 4. 关闭 picker（点安全标签如「视频标注」，**千万不要点「视频管理」**）
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const all = Array.from(body.querySelectorAll('*')); const label = all.find(e => e.innerText && e.innerText.trim() === '视频标注'); if (label) label.click(); return 'clicked'; })()"

# 5. 验证时间同步
agent-browser snapshot | grep "发表时间" -A 2
```

**💀 陷阱：** 绝不要点击页面标题"视频管理"来关闭 picker——会触发「将此次编辑保留？」离开确认弹窗，导致数据丢失。

#### Step i: 点击发表

通过 eval 点击（不可用 agent-browser click，被 wujie iframe 遮住）：

```bash
agent-browser eval "(() => { const wa = document.querySelector('wujie-app'); const body = wa.shadowRoot.querySelector('html').querySelector('body'); const btn = Array.from(body.querySelectorAll('button')).find(b => b.innerText === '发表'); if (btn) { btn.click(); return 'clicked'; } return 'not found'; })()"
```

#### Step j: 验证发表成功

```bash
agent-browser wait 2000
agent-browser snapshot | grep "将于2026年"
```

看到新的定时条目（`将于2026年0X月XX日 HH:00发表`）即成功。

### 6.3 重复下一个切片

发表成功后页面回到视频列表。回到 Step a 继续下一个切片，将定时时间按间隔递增。

### 6.4 关闭浏览器

全部完成后：
```bash
agent-browser close
```

### 6.5 常见故障速查

| 现象 | 原因 | 处理 |
|------|------|------|
| "网络出错，请重新上传" | 上传中断或 session 过期 | 删除错误，重新上传 |
| "账号已在其他设备登录" 弹窗 | 会话被检测 | `document.querySelector('.login-modal-wrap .close')?.click()` |
| "将此次编辑保留?" 弹窗 | 误点导航 | 点「不保存」，数据需重新填 |
| 时间 picker 不提交 | 未正确关闭 | 用「视频标注」label 关闭，不要用其他方式 |
| agent-browser click 说 covered | wujie iframe 遮挡 | 改用 eval 在 shadow DOM 内 click |
| file input 找不到 | 在 shadow DOM 里 | 必须先 appendChild 到 document.body |
| 合集下拉有匹配项但 click 不生效 | 合集名可能有拼写偏差（如 `Agenti` 而非 `Agent`） | 用 `includes()` 模糊匹配而非精确匹配 |

---

## 参考文档

- `references/wujie-dom.md` — 视频号助手 wujie shadow DOM 元素选择器速查表

---

## 最终输出

```
outputs/
├── dubbed_video.mp4                       # BiliMix 配音视频
├── subtitles.ass                          # ASS 字幕
├── transcript.json                        # 解析后的字幕 JSON
├── {主题}_短视频切片方案.md                # 最终 Markdown 方案
└── clips/
    ├── clip_001.mp4 → clip_NNN.mp4        # 切片视频
```
