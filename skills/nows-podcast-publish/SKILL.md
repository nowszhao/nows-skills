---
name: nows-podcast-publish
description: 将音频一键发布到小宇宙播客平台。覆盖全流程：通过 bmx CLI 获取/处理音频 → YouTube 溯源获取原视频链接与封面 → AI 生成单集介绍与章节导航 → 浏览器自动化登录小宇宙后台上传音频、封面并创建单集。当用户提到「发布播客」「上传到小宇宙」「播客单集发布」「nows podcast publish」时使用。
---

# 小宇宙播客发布

将音频文件发布到小宇宙播客平台（podcaster.xiaoyuzhoufm.com），覆盖 bmx 初始化、已处理音频选择、YouTube 溯源、AI 内容生成、浏览器自动化发布的完整流程。

## 前置依赖

### bmx CLI

bmx 是 BiliMix 的命令行工具，用于下载和处理音频。安装方式：

```bash
# 从 GitHub 安装
pip install git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk
```

安装后验证：`bmx --help`

### agent-browser

用于浏览器自动化操作小宇宙后台。安装方式：

```bash
npm install -g agent-browser
agent-browser install
```

---

## Phase 0: bmx 初始化（首次使用必执行）

每次会话开始时，先检查 bmx 是否已配置。若未配置或认证过期，引导用户完成初始化。

### 0.1 收集用户凭证

通过 `AskUserQuestion` 向用户收集三个配置项：

| 配置项 | 说明 | 示例 |
|--------|------|------|
| Server | BiliMix 服务地址 | `http://localhost:5000` |
| Username | 登录用户名 | `admin` |
| Password | 登录密码 | `***` |

用 `AskUserQuestion` 一次收集全部三项，问题示例：

**header**: "bmx 配置"
**question**: "请提供 BiliMix 服务的连接信息"
**options**: 三个 text 输入字段（server / username / password）
或分两次询问：先问 server，再问账号密码。

### 0.2 配置并登录

收集到凭证后，依次执行：

```bash
# 1. 配置服务地址
bmx config set server <server_url>

# 2. 登录认证
bmx auth login --username <username> --password <password>
```

验证登录状态：

```bash
bmx auth status
# 输出应包含 "logged_in": true
```

若登录失败（退出码 2），提示用户检查 server 是否可访问、用户名密码是否正确，然后重新收集。

### 0.3 确认初始化成功

向用户报告：`✓ bmx 已连接到 {server}，用户 {username} 已登录`

---

## Phase 1: 选择已处理完成的音频

bmx 登录成功后，列出已完成处理的任务，让用户手动选择要发布的一条。

### 1.1 列出已完成任务

```bash
bmx task list
```

输出为 JSON 数组，每个任务包含 `task_id`、`title`、`status`、`created_at` 等字段。

筛选条件：
- `status` 为 `completed` 或 `done`
- 按 `created_at` 倒序排列（最新的在前）
- 取前 10 条

### 1.2 展示任务列表让用户选择

将筛选后的任务列表以清晰格式展示给用户。每个任务显示：

```
[序号] {title 或 文件名}
       任务ID: {task_id}
       完成时间: {created_at}
```

然后使用 `AskUserQuestion` 让用户选择：

**header**: "选择音频"
**question**: "请选择要发布到小宇宙的任务（序号）"
**options**: 每个已完成任务作为一个选项，label 为标题摘要 + 任务 ID

### 1.3 下载选中的音频

用户选择后，下载原始音频和获取字幕：

```bash
# 下载原始音频（发布用小宇宙用原始版）
bmx audio download --task-id <selected_task_id> --type original -o <basename>_original.mp3

# 获取字幕文本（用于后续内容生成）
bmx task result <selected_task_id> --field transcription
```

同时获取任务元信息：

```bash
bmx task result <selected_task_id> --field title
bmx task result <selected_task_id> --field source_url
```

### 1.4 确认音频文件

向用户展示下载结果：
- 音频文件路径和大小
- 提取到的标题/文件名
- 字幕文本行数

等待用户确认后进入 Phase 2。

---

## Phase 2: YouTube 溯源

从任务元信息或音频文件名提取搜索关键词，搜索 YouTube 原始视频获取视频链接、发布时间和封面图片。

**⚠️ 禁止用 agent-browser 访问 YouTube**，YouTube 对自动化浏览器有严格反机器人检测。全部用 `web_search` + YouTube 缩略图 API 完成。

### 2.1 提取搜索关键词

优先级：
1. bmx 任务中的 `source_url`（若为 YouTube 链接则直接使用）
2. 从音频文件名提取：去除扩展名和 bmx 后缀（`_mixed` / `_original`），取播客名 + 关键词

### 2.2 搜索 YouTube

```bash
web_search "site:youtube.com {搜索关键词}"
```

从搜索结果中提取视频链接（`https://www.youtube.com/watch?v=VIDEO_ID`）、发布时间和标题。

### 2.3 下载封面图片

从 URL 提取 11 位 `VIDEO_ID`，通过 YouTube 公开缩略图 API 下载（无需访问页面，零拦截）：

```bash
# 逐级尝试分辨率，取第一个 > 200px 的图像
for size in maxresdefault hqdefault sddefault; do
  curl -s -o /tmp/cover_temp.jpg -L "https://img.youtube.com/vi/{VIDEO_ID}/${size}.jpg"
  python3 -c "from PIL import Image; im=Image.open('/tmp/cover_temp.jpg'); exit(0 if min(im.size)>200 else 1)" && break
done
```

裁剪为 1:1 正方形封面（1400×1400）：

```python
from PIL import Image
img = Image.open("/tmp/cover_temp.jpg")
w, h = img.size
size = min(w, h)
left = (w - size) // 2
top = (h - size) // 2
img_cropped = img.crop((left, top, left + size, top + size))
img_cropped = img_cropped.resize((1400, 1400), Image.LANCZOS)
img_cropped.save("{basename}_cover.png")
```

### 2.4 降级方案 — 文字封面

当所有缩略图分辨率均 < 200px 时（极端情况），用 Pillow 生成深色文字封面：

```python
from PIL import Image, ImageDraw
img = Image.new('RGB', (1400, 1400), (20, 22, 28))
d = ImageDraw.Draw(img)
d.rectangle([50, 50, 1350, 1350], outline=(80, 85, 95), width=3)
title_words = "{视频标题}".split()
lines, cur = [], ""
for w in title_words:
    if len(cur + w) < 25: cur += w + " "
    else: lines.append(cur.strip()); cur = w + " "
lines.append(cur.strip())
y = 550
for line in lines[:3]:
    d.text((700, y), line, fill=(240, 240, 245), anchor="mm")
    y += 80
d.text((700, 850), "YouTube · {发布时间}", fill=(140, 145, 155), anchor="mm")
img.save("{basename}_cover.png")
```

### 2.5 确认溯源结果

向用户展示：YouTube 视频链接、发布时间、封面图片路径。用户确认后进入 Phase 3。若搜索不到，请用户手动提供链接。

---

## Phase 3: 内容生成

生成播客单集所需的全部文本内容。字幕来自 Phase 1 获取的 transcription。

### 3.1 标题翻译与格式化

将任务标题/文件名翻译为地道中文标题，使用格式：

```
{类型标签} | {中文标题}
```

类型标签选项：`专访` `峰会` `演讲` `对谈` `圆桌` `讲座` `分享` `对话`

选择最匹配的标签。标题翻译要求：信达雅、吸引点击、不超过 40 字。

### 3.2 生成单集介绍

加载 `references/content_prompts.md` 中的「单集介绍 Prompt」，将字幕文本替换 `{SUBTITLE_TEXT}` 占位符后，在当前对话中直接生成。

输出包含三个部分：
- **本期核心内容**：3-5 句话概括精华
- **你将听到**：6-10 个要点列表
- **适合谁听**：3-5 个标签

### 3.3 生成章节导航

加载 `references/content_prompts.md` 中的「章节导航 Prompt」，将字幕文本替换 `{SUBTITLE_TEXT}` 占位符后生成。

输出格式严格按照模板：
```
00:00  【章节名】简介... 🧡🧡🧡🧡🧡
```

### 3.4 组装原文链接

```
原文链接：{YouTube 视频 URL}（发布于 {发布时间}）
```

### 3.5 展示内容预览并确认

将生成的标题和完整内容展示给用户预览，使用 `AskUserQuestion` 确认：

**header**: "确认内容"
**question**: "内容是否正确？"
**options**: 「确认，继续发布」/ 「修改标题」/ 「修改正文」/ 「全部重来」

用户可选择修改后继续。

---

## Phase 4: 小宇宙发布

所有浏览器操作使用 `agent-browser` CLI，全程在同一 session 中完成。

### 4.1 打开浏览器并引导用户登录

```bash
agent-browser open https://podcaster.xiaoyuzhoufm.com/
agent-browser wait --load networkidle
agent-browser snapshot
```

**引导登录流程**（关键步骤）：

1. 打开页面后先 `agent-browser snapshot` 判断当前页面状态
2. 若显示登录页面：
   - 执行 `agent-browser screenshot` 截图
   - 将截图展示给用户
   - 明确提示：**「请用微信扫描屏幕上的二维码完成登录，扫码完成后请告诉我。」**
3. 等待用户回复「已登录」/「好了」/「完成」等确认后，继续下一步
4. 执行 `agent-browser snapshot` 验证已进入后台首页

**不要**在用户未确认登录前继续执行任何操作。登录态由 agent-browser session 保持。

### 4.1a 提取播客 ID

登录后进入播客管理后台。小宇宙是 SPA，URL 形如 `/podcast/{24位hex ID}`。若在 dashboard 页面，用 JS 提取：

```bash
agent-browser eval "Array.from(document.querySelectorAll('a')).find(a => a.textContent.includes('科技'))?.href"
# 返回: https://podcaster.xiaoyuzhoufm.com/podcast/6a27fa4840f10adfcec1a5e1
```

记录 24 位 hex 播客 ID，后续页面 URL 格式为 `/podcast/{pid}/{section}`。

### 4.2 上传音频到资源库

资源库 URL 为 `/podcast/{pid}/library`（非 `/assets`）：

1. 直接导航到资源库：
```bash
agent-browser open "https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/library"
agent-browser wait --load networkidle
```

2. 找到页面上 `input[type=file][accept="audio/*"]`，使用 `upload` 命令直接上传：

```bash
agent-browser upload 'input[accept="audio/*"]' <音频文件路径>
agent-browser wait --load networkidle
```

3. 上传完成后页面会显示新音频条目，记录其在列表中的位置。

### 4.3 上传封面图片

在资源库中为刚上传的音频关联 Phase 2 生成的正方形封面：

1. 定位到刚上传的音频条目
2. 点击封面区域，上传 `{basename}_cover.png`
3. 等待上传完成

### 4.4 创建单集

1. 导航到内容管理 → 创建单集：
```bash
agent-browser open "https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/episode"
agent-browser wait --load networkidle
agent-browser snapshot -i
```

2. 点击「创建单集」按钮，进入表单页面。

3. 表单字段及填写方式：

| 字段 | 查找方式 | 操作 |
|------|---------|------|
| **标题** | `textbox "输入单集标题"` | `agent-browser type <ref> "{标题}"` |
| **简介/内容** | `textbox`（紧随标题下方） | `agent-browser type <ref> "{完整内容}"` |
| **音频** | `input[accept="audio/*"]` | `agent-browser upload 'input[accept="audio/*"]' <文件路径>` |
| **封面** | `input[accept="image/jpeg,image/png,image/webp"][multiple]` | `agent-browser upload 'input[accept="image/jpeg,image/png,image/webp"][multiple]' <封面路径>` |

**注意**：页面有 2-3 个 `input[type=file]`，需要用 `accept` 属性区分：
- `audio/*` → 音频
- `image/jpeg,image/png,image/webp` 且 `multiple=true` → 封面

4. 勾选「阅读并同意」checkbox，点击「创建」按钮发布。

### 4.5 发布单集

点击「发布」或「保存」按钮完成发布。

### 4.6 发布成功截图

**发布完成后必须执行**：

```bash
agent-browser screenshot
```

截图保存为 `{basename}_publish_success.png`，作为发布成功的凭证展示给用户。

---

## Phase 5: 清理

```bash
agent-browser close
```

---

## 交互式确认节点汇总

| 节点 | 位置 | 确认内容 |
|------|------|---------|
| ✅1 | Phase 0.3 | bmx 连接和登录状态 |
| ✅2 | Phase 1.4 | 选中的音频文件和字幕 |
| ✅3 | Phase 2.4 | YouTube 视频链接和封面 |
| ✅4 | Phase 3.5 | 生成的标题和单集内容 |
| ✅5 | Phase 4.1 | 小宇宙已登录 |
| ✅6 | Phase 4.6 | 发布成功截图 |

每个确认点若用户不满意，回退到对应阶段重新执行。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| bmx 未安装 | 提示执行 `pip install git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk` |
| bmx 登录失败（退出码 2）| 重新收集用户名密码 |
| bmx 无已完成任务 | 引导用户先用 bmx 提交并处理音频，或提供本地文件路径 |
| bmx 服务不可用 | 提示检查 server 地址，确保服务运行中 |
| YouTube 搜索无结果 | 请用户手动提供视频链接和发布时间 |
| YouTube 缩略图不可用（< 200px） | 自动降级为 Pillow 文字封面 |
| 小宇宙登录超时 | 重新截图展示登录二维码 |
| 上传失败 | 检查文件大小（小宇宙限制 ≤200MB），检查网络，重试 |
| agent-browser daemon 崩溃 | `agent-browser close` 清理后重新 `open` |
| 发布按钮不可点击 | `snapshot -i` 重新获取元素状态，检查必填字段是否已填 |
