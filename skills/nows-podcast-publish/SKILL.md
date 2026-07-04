---
name: nows-podcast-publish
description: 将音频一键发布到小宇宙播客平台。覆盖全流程：通过 bmx CLI 获取/处理音频 → YouTube 溯源获取原视频链接与封面 → AI 生成单集介绍与章节导航 → 浏览器自动化登录小宇宙后台上传音频、封面并创建单集。当用户提到「发布播客」「上传到小宇宙」「播客单集发布」「nows podcast publish」时使用。
---

# 小宇宙播客发布

将音频文件发布到小宇宙播客平台（podcaster.xiaoyuzhoufm.com），覆盖 bmx 初始化、已处理音频选择、YouTube 溯源、AI 内容生成、浏览器自动化发布的完整流程。

## 前置依赖

### bmx CLI

bmx 是 BiliMix 的命令行工具，用于下载和处理音频。

```bash
pip install git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk
```

验证：`bmx --help`

### agent-browser（浏览器自动化）

小宇宙发布阶段**全程使用 agent-browser**（同一会话内完成登录、填表、上传、发布）。不要切换到 playwright-cli——cookie 转移会导致所有接口返回 500（openresty）而失效。

- `agent-browser` 已在环境中可用，无需额外安装。
- 关键能力：`open` / `eval` / `upload` / `click` / `check` / `fill` / `screenshot` / `snapshot`。
- 给 hidden `input[type=file]` 手动赋 id 后，`agent-browser upload #id <file>` 可正常上传（直接 `upload` 点击上传区 div 会报 "Node is not a file input element"）。

### qrcode（Python）

当小宇宙登录页 canvas QR 码在 headless 下渲染不完整时，用 Python 重新生成。

```bash
pip install qrcode
```

---

## Phase 0: bmx 初始化（首次使用必执行）

每次会话开始时，先检查 bmx 是否已配置。若未配置或认证过期，引导用户完成初始化。

### 0.1 收集用户凭证

通过 `AskUserQuestion` 收集三个配置项：Server、Username、Password。

### 0.2 配置并登录

```bash
bmx config set server <server_url>
bmx auth login --username <username> --password <password>
```

验证：`bmx auth status`，输出应包含 `"authenticated": true`。

### 0.3 确认初始化成功

向用户报告：`✓ bmx 已连接到 {server}，用户 {username} 已登录`

### 0.4 验证 CLI 完整性（关键，易踩坑）

**即使 bmx 已安装，也必须跑一次 `bmx --help` 验证能正常启动。** PyPI 上的 `bilimix-cli` 1.0.0 是损坏版本：在 `build_parser` 阶段引用未定义的 `cmd_vocab_list`，`bmx --help` 或任何子命令都会直接崩溃（Traceback 含 `NameError: cmd_vocab_list`）。

```bash
bmx --help 2>&1 | head -3
```

- 若输出正常列出子命令（auth / task / audio …）→ CLI 完好，继续。
- 若报 `cmd_vocab_list` 未定义或其他 `NameError` / `AttributeError` → **已装的 PyPI 版损坏**，强制从 GitHub 重装（注意 `--force-reinstall --no-cache-dir`，否则 pip 认为已满足而不重装）：

```bash
pip install --force-reinstall --no-cache-dir "git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk"
bmx --help   # 重装后必须再次验证，确认不再报错
```

> ⚠️ 只写 `pip install git+...` 不够：若环境中已存在损坏的 PyPI 版，pip 可能判定"已安装满足要求"而跳过。必须带 `--force-reinstall --no-cache-dir` 并复查 `bmx --help`。

---

## Phase 1: 选择已处理完成的音频

### 1.1 列出已完成任务

```bash
bmx task list
```

筛选条件：`status` 为 `completed`，按 `created_at` 倒序，取前 10 条。

### 1.2 展示任务列表让用户选择

```
[序号] {title}
       任务ID: {task_id}
       完成时间: {created_at}
```

用 `AskUserQuestion` 让用户选择。

### 1.3 确认音频版本并下载

**先询问用户要下载哪个版本：**

- `original` — 原始音频
- `mixed` — 翻译混音版（大多数用户要这个）

```bash
bmx audio download --task-id <task_id> --type <original|mixed> -o <basename>_<type>.mp3
```

### 1.4 获取任务元信息

```bash
# 获取完整结果（包含 segments 字幕数组）
bmx task result <task_id>
```

从返回 JSON 中提取：
- `result.title` — 音频标题
- `result.basename` — 文件名
- `segments` — 字幕段数组，每段含 `start`/`end`/`text`/`speaker`
- `result.original_duration` / `result.mixed_duration` — 时长

用 Python 将 segments 提取为带时间戳的全文，保存到 `transcript_full.txt`。

> **注意**：`--field transcription` 字段可能返回 `null`，应从 `segments` 数组自行拼装。

> ⚠️ **时间戳精确性**：Phase 3 生成章节导航时，**章节时间戳必须使用 segments 中该话题首次出现的 `start` 秒数**，通过 `{seconds // 60}:{seconds % 60:02d}` 格式化。**禁止估算或自行编造时间戳。** 此外，mixed 版音频时长可能短于原始时长——如果 mixed 版的 segments 没有被单独导出、而是与原始版共用同一套时间戳，则时间戳不需要缩放，直接用原始时间即可。

### 1.5 确认音频文件

向用户展示：文件路径、大小（需 ≤200MB）、时长、字幕段数。确认后进入 Phase 2。

---

## Phase 2: YouTube 溯源

**⚠️ 禁止用浏览器访问 YouTube。** 全部用 WebSearch + YouTube 缩略图 API。

### 2.1 提取搜索关键词

优先级：
1. bmx 任务中的 `source_url`（若为 YouTube 链接则直接使用）
2. 从音频文件名提取：去除扩展名和 bmx 后缀，取播客名 + 年份 + 标题关键词

### 2.2 搜索 YouTube

**搜索策略（关键）：极简命中，不加引号、不加人名。**

```bash
WebSearch "site:youtube.com {频道/会议名} {年份} {标题关键词}"
```

示例：
- ✅ `site:youtube.com Snowflake Summit 2026 Platform Keynote`
- ❌ `site:youtube.com "Snowflake Summit 2026" "Platform Keynote" Benoit Dageville`（引号+人名导致无结果）

**若 `site:youtube.com` 搜索无 YouTube 结果，改用 WebFetch 直接访问 YouTube 搜索页面**：

```bash
WebFetch "https://www.youtube.com/results?search_query={搜索关键词}" "Find the YouTube video titled \"{原标题前15-20个词}\". Give me the full YouTube URL with the video ID."
```

> **为什么 `site:youtube.com` 可能失败**：bmx 中很多任务的 `source_url` 来自 anchor.fm、megaphone.fm 等播客平台而非 YouTube；原始标题也未必是 YouTube 视频标题。此时需要从描述和人名中重新组合搜索关键词。

> **常见失败模式**：对于 bmx 里来自播客平台（anchor.fm 等）的任务，`site:youtube.com` 用原标题搜不到是正常的。优先用 YouTube search page URL + WebFetch。

若以上两步均无结果，请求用户提供 Google 搜索结果截图或手动提供 YouTube 链接。

### 2.3 下载封面图片并智能裁剪

从 YouTube URL 提取 11 位 `VIDEO_ID`：

```bash
for size in maxresdefault hqdefault sddefault; do
  curl -s -o /tmp/cover_temp.jpg -L "https://img.youtube.com/vi/{VIDEO_ID}/${size}.jpg"
  python3 -c "from PIL import Image; im=Image.open('/tmp/cover_temp.jpg'); exit(0 if min(im.size)>200 else 1)" && break
done
```

**⚠️ 关键：必须基于人脸位置裁剪，不能用居中裁剪。** 播客封面（特别是 Lenny's Podcast 这类）嘉宾的脸通常在右侧或左侧而非正中。居中裁剪会把脸截掉一半。

裁剪流程：

1. **用 Read 工具查看 `/tmp/cover_temp.jpg`**（multimodal 视觉模型能看到图片）
2. **大致估读人脸矩形框的像素坐标**（left, top, right, bottom），如 `(620, 0, 1080, 420)`
3. **运行 `scripts/crop_cover.py`** 完成裁剪：

```bash
python3 scripts/crop_cover.py /tmp/cover_temp.jpg 620 0 1080 420 {basename}_cover.png
```

脚本内部逻辑：以人脸中心为锚点，按「脸上 1/3 黄金位」定位正方形裁剪窗，缩放到 1400×1400 并校验人脸未越界。

> **为什么不引入 opencv / mediapipe 做面部检测**：这些库要么 API 变化大（opencv 5 移除了 CascadeClassifier），要么安装包大（mediapipe 几百 MB）。**直接用 multimodal 视觉看图填坐标是最简单稳定的方式**——`crop_cover.py` 内部有 `assert` 校验，人脸越界会直接报错。

### 2.4 降级方案 — 文字封面

当所有缩略图均 < 200px 时，用 Pillow 生成深色文字封面（标题两行 + 副标题）。保存到 `{basename}_cover.png`，后续 Phase 4.7 照常上传：

```python
python3 - << 'PYEOF'
from PIL import Image, ImageDraw, ImageFont
W = H = 1400
img = Image.new('RGB', (W, H), (18, 18, 22))
d = ImageDraw.Draw(img)
# 标题（换成真实标题，自动按宽度折行）
title = "播客单集标题占位"
sub = "副标题 / 节目名占位"
try:
    f1 = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 96)
    f2 = ImageFont.truetype("/System/Library/Fonts/PingFang.ttc", 48)
except Exception:
    f1 = f2 = ImageFont.load_default()
# 简单居中（标题）
tb = d.textbbox((0, 0), title, font=f1)
d.text(((W - (tb[2]-tb[0]))//2, H//2 - 120), title, fill=(245, 245, 245), font=f1)
sb = d.textbbox((0, 0), sub, font=f2)
d.text(((W - (sb[2]-sb[0]))//2, H//2 + 20), sub, fill=(150, 150, 160), font=f2)
img.save('{basename}_cover.png')
print('saved {basename}_cover.png')
PYEOF
```

### 2.5 获取真实发布日期（精确到日，必须抓取，禁止估算）

**⚠️ 发布时间必须精确到「日」（如 `2026 年 3 月 6 日`），绝不能只写月份。** 该值用于 Phase 3.4 原文链接的「（发布于 …）」，必须来自 YouTube 真实数据，AI 不得估算（实测 AI 曾把 3 月错写成 4 月）。

从 watch 页面抓 `dateText` / `publishDate` 的 `simpleText` 字段（含「年/月/日」中文）：

```bash
curl -sS --noproxy '*' -m 20 "https://www.youtube.com/watch?v={VIDEO_ID}" 2>&1 \
  | grep -oE '"(dateText|publishDate)":\{"simpleText":"[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日"' \
  | grep -oE '[0-9]{4}年[0-9]{1,2}月[0-9]{1,2}日' | head -1
# 期望输出示例: 2026年3月6日
```

> 若上述 grep 无输出（页面结构变化），改用 WebFetch 访问 watch 页并要求提取 `datePublished` / `发布于` 的完整年月日；仍失败则请求用户提供真实发布日期（精确到日）。**无论如何不得用 AI 编造的月份/日期。**

### 2.6 确认溯源结果

展示 YouTube 链接、**真实发布日期（精确到日）**、封面路径。用户确认后进入 Phase 3。搜索不到则请用户提供链接。

---

## Phase 3: 内容生成

生成播客单集所需全部文本。字幕来自 Phase 1 的 segments。

### 3.1 标题翻译与格式化

```
{类型标签} | {中文标题}
```

类型标签：`专访` `峰会` `演讲` `对谈` `圆桌` `讲座` `分享` `对话`

### 3.2 生成单集介绍

加载 `references/content_prompts.md` 中的「单集介绍 Prompt」，将字幕文本替换 `{SUBTITLE_TEXT}` 后生成。

输出三部分：**本期核心内容**（3-5 句）、**你将听到**（6-10 要点）、**适合谁听**（3-5 标签）。

### 3.3 生成章节导航

加载 `references/content_prompts.md` 中「章节导航 Prompt」生成。

**⚠️ 章节内容要求（必须严格遵守）**：

- 每个章节的简介必须是 **1-2 句完整描述**，涵盖该部分的核心内容、关键论点或重要事实。**绝对禁止**只写一个词或短语作为章节简介（如「开场」「定义 agent」），这样的章节导航会在预览阶段被用户驳回。
- 在确认环节展示完整的章节导航给用户预览，因为这是最容易返工的环节。

输出格式严格按：
```
00:00  【章节名】简介内容（1-2句，简洁但完整）... 🧡🧡🧡🧡🧡
```

> **时间戳来源**：所有时间戳必须来自 `transcript_full.txt` 中该话题首句对应的 `[Ns-]` 前缀，通过 `秒数 / 60` 换算为 `MM:SS` 格式。不估算、不编造。

### 3.4 组装原文链接

**原文链接放在 `episode_content.md` 最前面**（紧接标题之后），包含播客节目名称和 YouTube 单集标题：

```
**{播客节目名称}**: {YouTube 视频标题}
{YouTube 视频 URL}（发布于 {真实发布日期，精确到日}）
```

> ⚠️ **`{真实发布日期}` 必须来自 Phase 2.5 从 YouTube 抓取的值，精确到「年/月/日」（如 `2026 年 3 月 6 日`）。禁止只写月份、禁止 AI 估算。**

示例：
```
**Lenny's Podcast**: Why OpenAI is merging Codex and ChatGPT and the future of knowledge work | Andrew Ambrosino
https://www.youtube.com/watch?v=P3KDebPTUrw（发布于 2026 年 6 月 15 日）
```

- 播客节目名称从 YouTube 频道名中提取
- YouTube 视频标题用原始英文标题，不翻译
- 发布日期格式固定为 `YYYY 年 M 月 D 日`，日不带前导零（如 `6 日` 而非 `06 日`）

### 3.5 生成 Show Notes（渲染 episode_content.md 的「预览」HTML）

Show Notes 是小宇宙表单的正文，**必须和小宇宙后台「预览」看到的 episode_content.md 渲染结果完全一致**——保留 **加粗**、段落/换行结构、以及顶部的原文链接部分。

> ⚠️ **历史坑（两种错误都必须避免）**：
> 1. **直接注入原始 Markdown 源码**：`**`、`- `、`---` 会显示为字面量，看起来像乱码。
> 2. **把 Markdown 当纯文本 strip 掉所有标记**：虽然去掉了字面量，但也丢掉了加粗和段落结构，和「预览」不一致。
>
> ✅ **正确做法**：用 `scripts/extract_show_notes.py` 把 Markdown **渲染成 HTML**（`##`→加粗标题、`` ** ``→`<strong>`、`- `→带 `•` 的段落、`` --- ``→`<hr>`），再在 Phase 4.5 用 `innerHTML` 注入 contenteditable。发布的就是带格式、和预览一致的富文本。

渲染后的 HTML 样貌（节选）：

```html
<p><strong>The Analytics Engineering Podcast</strong>: The Iceberg ecosystem today (Anders Swanson)</p>
<p>https://www.youtube.com/watch?v=...</p>
<hr>
<p><strong>本期核心内容</strong></p>
<p>dbt Labs CEO ...</p>
<p><strong>你将听到</strong></p>
<p>• <strong>术语闪电战</strong>：查询引擎...</p>
```

> 注：列表项渲染为 `<p>• <strong>术语</strong>：描述</p>` 而非 `<ul><li>`，是为了在编辑器过滤掉 `<ul>` 时仍能保留 bullet 与换行；加粗始终用 `<strong>`。

生成后在 `episode_content.md` 中保留 Markdown 版本（供留档），注入小宇宙时用 `scripts/extract_show_notes.py` 渲染为 HTML：

```bash
python3 scripts/extract_show_notes.py episode_content.md > show_notes.html
```

脚本自动完成：跳过 `#` 标题（已在「标题」字段）、`##`→加粗标题、`` ** ``→`<strong>`、`- `→带 `•` 的段落、`` --- ``→`<hr>`、逐行成块保留换行、保留 emoji 与 `【章节名】`、顶部原文链接（节目名+URL）原样保留。

### 3.6 展示内容预览并确认

将标题和完整内容展示给用户预览。用 `AskUserQuestion` 确认。

### ⚠️ 3.7 内容一致性约束（关键）

**Phase 4 填入小宇宙的内容，必须与 Phase 3.5 用户确认过的内容逐字一致。** 禁止因打字效率、字符限制等原因临时简写、删改内容。大段正文用 Phase 4.5 的 base64 JS 注入方式完整写入，不要依赖 `type`/`fill` 命令的逐字输入。

---

## Phase 4: 小宇宙发布

### 核心原则

**整个发布流程（登录 → 填表 → 上传 → 创建）都在同一个 agent-browser 会话内完成，绝不要切换 playwright-cli。**

> ⚠️ **已验证的坑**：playwright-cli 通过 cookie 转移恢复登录态后，小宇宙所有接口返回 500（openresty）。agent-browser 的 `upload` 命令对**未赋 id 的 hidden input 或 div 点击区**无效，但给 hidden `input[type=file]` 手动赋 id 后 `agent-browser upload #id` 完全正常。因此正确做法是**全程 agent-browser + 给隐藏 input 赋 id 上传**。

### 4.1 打开登录页（agent-browser）

```bash
agent-browser open https://podcaster.xiaoyuzhoufm.com/
agent-browser snapshot
```

### 4.2 引导用户扫码登录

1. 若显示登录页，快照找到 `radio "扫码登录"` 并点击切换
2. QR 码是 `<canvas>` 元素，headless 模式下渲染常不完整（只显示 1/4）
3. **不要截图 canvas**。改用下面方式提取 QR URL 并重新生成：

```bash
# 切换扫码登录后等 5 秒，从 React Fiber 提取 QR URL
agent-browser eval "
const canvas = document.querySelector('canvas[class*=\"qr\"]');
let qrUrl = '';
let node = canvas;
for (let i = 0; i < 20; i++) {
  const key = Object.keys(node).find(k => k.startsWith('__reactFiber'));
  if (key) {
    let fiber = node[key];
    for (let j = 0; j < 30; j++) {
      if (fiber?.memoizedProps?.value) { qrUrl = fiber.memoizedProps.value; break; }
      fiber = fiber?.return;
    }
    break;
  }
  node = node.parentElement;
  if (!node) break;
}
qrUrl
"
# 返回: https://h5.xiaoyuzhoufm.com/oauth?qrcode_id=6a43...
```

然后用 Python 生成清晰 QR 码：

```bash
python3 -c "
import qrcode
qr = qrcode.QRCode(version=1, box_size=12, border=4)
qr.add_data('<qrUrl>')
qr.make(fit=True)
img = qr.make_image(fill_color='black', back_color='white')
img.save('xiaoyuzhou_qr.png')
"
```

用 `present_files` 展示 `xiaoyuzhou_qr.png` 给用户扫码。

**等待登录**：不要用 `grep "podcast"` 检测 URL（会误匹配 redirectURL 参数中的 "podcast" 造成假登录），改用 `snapshot` 检查页面是否出现播客列表中的实际内容。

```bash
# 轮询检查登录（每 5 秒 snapshot，检查是否出现「创建节目」等已登录特征）
for i in $(seq 1 24); do
  sleep 5
  if agent-browser snapshot 2>&1 | grep -q "创建节目"; then
    echo "✅ LOGGED IN!"
    break
  fi
done
```

确认登录后，告知用户「已登录」，进入 Phase 4.3。

### 4.3 进入创建单集页

登录后直接进入创建单集页（用 4.2 记录的播客 ID）：

```bash
agent-browser open "https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/episode/create"
agent-browser wait 3000
```

> 也可从播客后台点「创建单集」进入，但直链更稳。进入后确认标题输入框（placeholder 含「标题」）和正文编辑区可见。

### 4.4 填写标题

```bash
agent-browser fill 'input[placeholder*="标题"]' "{标题}"
```

### 4.5 注入 Show Notes（contenteditable，innerHTML 富文本）

小宇宙 Show Notes 是 `contenteditable` 富文本 div，**不能用 `type`/`fill` 命令直接填**。用 base64 编码 JS 注入 HTML（`innerHTML`，保留加粗/段落/列表结构，与预览一致），绕过特殊字符导致的 shell 展开失败：

```bash
# 1) 用 Python 把 HTML 版 show_notes.html 塞进一段 JS（必须用 IIFE 包裹，否则 agent-browser eval 会报 Illegal return statement），写文件避免 shell 展开问题
python3 - << 'PYEOF'
import json
html = open('show_notes.html', encoding='utf-8').read()
js = (
    "(()=>{"
    "const ed = document.querySelector('[contenteditable=true]');"
    "if(!ed){return 'NO_EDITOR';}"
    "ed.focus();"
    "ed.innerHTML = " + json.dumps(html, ensure_ascii=True) + ";"
    "ed.dispatchEvent(new Event('input', {bubbles: true}));"
    "return 'filled ' + ed.innerHTML.length;"
    "})()"
)
open('/tmp/inject_js.txt', 'w', encoding='utf-8').write(js)
PYEOF

# 2) base64 编码后用 agent-browser eval 执行
B64=$(base64 < /tmp/inject_js.txt | tr -d '\n')
agent-browser eval "eval(atob('$B64'))"
# 期望输出: filled <HTML 字符数>
```

> ⚠️ **IIFE 必须包裹**：`agent-browser eval` 将代码作为顶层脚本执行，顶层 `return` 会报 `Illegal return statement`。JS 必须写成 `(()=>{ ... return xxx; })()` 的 IIFE 形式。

> ⚠️ **必须用 `ensure_ascii=True`（关键）**：`json.dumps(html, ensure_ascii=True)` 将所有中文等非 ASCII 字符转成 `\uXXXX` 转义序列（纯 ASCII），确保经过 shell→base64→eval 传输链路后浏览器端能正确还原。**绝对不能用 `ensure_ascii=False`**——原始 UTF-8 多字节字符在这条链路中会被截断/误解码，导致发布后中文显示为乱码（如 `本期核心内容` → `å¼ å§æ ¸å¿ƒå… å®¹`）。

> ⚠️ **必须用 `innerHTML`（富文本）**，不要用 `textContent`——后者会把加粗/段落结构全抹成纯文本，和预览不一致。若页面有多个 contenteditable，改用更精确的选择器（如 `.mantine-Textarea-input` 或第 2 个 `[role=textbox]`）。注入后用 `snapshot` 核对内容已进入表单、加粗标记保留。

### 4.6 上传音频

页面有 3 个 hidden `input[type=file]`，顺序固定：

| 索引 | accept | 用途 | 父链特征 |
|------|--------|------|----------|
| 0 | image/* | Show Notes 富文本「插图」上传（正文里插图片用） | 位于 `_richEditor` 工具栏内 |
| 1 | audio/* | **音频** | 位于右侧栏 |
| 2 | image/* | **单集封面** | 父链含「单集封面 点击上传封面 或打开资源库」 |

> ⚠️ **上传前务必确认索引**：小宇宙曾改版，不同页面（创建页 / 编辑页）或不同时间 input 数量可能不同。上传封面前先用下面 eval 确认 `[2]` 确实是封面（父链文本含「单集封面」），避免传错位置导致封面静默失效：

```bash
agent-browser eval "(()=>{const inp=document.querySelectorAll('input[type=file]')[2]; let n=inp,chain=[]; for(let i=0;i<4;i++){n=n.parentElement; if(!n)break; chain.push((n.innerText||'').replace(/\\s+/g,' ').slice(0,20));} return JSON.stringify({accept:inp.accept, chain});})()"
# 期望 chain 含 '单集封面 点击上传封面...' → 这才是封面 input
```

**先给音频 input 赋 id，再 upload**：

```bash
agent-browser eval "document.querySelectorAll('input[type=file]')[1].id='xyAudio'; 'ok'"
agent-browser upload "#xyAudio" "<音频绝对路径>"
# 期望输出: ✓ Done
```

> 不要点「点击上传音频」的 div 后用 `upload`——那是 div 不是 input，会报 "Node is not a file input element"。必须直接操作隐藏的 `input[type=file]`。

> ⚠️ **点击封面上传区 div 不会打开文件框**：用 `agent-browser click` 点「点击上传封面」会弹出一个选图弹窗（资源库），且不会直接暴露 file input；用 JS `.click()` 连弹窗都不出。正确做法始终是：**直接 `agent-browser upload` 到隐藏的封面 `input[type=file]`（已确认是 idx 2）**。

### 4.7 上传封面 + 裁切对话框

```bash
agent-browser eval "document.querySelectorAll('input[type=file]')[2].id='xyCover'; 'ok'"
agent-browser upload "#xyCover" "<封面绝对路径>"
# 期望输出: ✓ Done
sleep 3
```

> ⚠️ **「裁切图片」弹窗必须出现——它是上传成功的唯一可靠信号。** 上传成功后小宇宙**必然**弹出裁切对话框（标题「裁切图片」，显示「当前尺寸：1500px*1500px 最小尺寸：360x360px」等）。**如果等 3 秒后没有任何裁切弹窗，说明上传根本没生效**（常见原因：idx 2 不是封面 input、或该 input 在创建页尚未渲染、或文件格式/大小被拒）。此时不要继续点创建——先回到 4.6 重新确认封面 input 索引，再重传。
>
> 判断弹窗是否出现的可靠 eval：
> ```bash
> agent-browser eval "(()=>{const m=[...document.querySelectorAll('.mantine-Modal-root,[role=dialog]')].find(x=>x.offsetParent!==null && x.innerText.includes('裁切图片')); return m?'CROP_MODAL_OPEN':'NO_CROP_MODAL';})()"
> ```

弹窗出现后，点击「裁切」确认（封面已是方形，无需调整）：

```bash
agent-browser eval "(()=>{const m=[...document.querySelectorAll('.mantine-Modal-root,[role=dialog]')].find(x=>x.innerText.includes('裁切图片')); if(!m)return 'no crop modal'; const b=[...m.querySelectorAll('button')].find(x=>x.innerText.trim()==='裁切'); if(b){b.click(); return 'cropped';} return 'no 裁切 btn';})()"
sleep 2
```

> ⚠️ **必须点「裁切」才会真正写入封面。** 只上传不点裁切，封面不会保存（会静默回退成默认图或留空）。点完裁切后，新封面会以一个 1500px 左右的 `image.xyzcdn.net/...jpg` 出现在页面（旧默认封面可能仍以小缩略图形式残留在顶部 header，属正常，以编辑页校验为准）。

### 4.8 清除遮挡 tip banner

创建页常有多层 tip banner 遮挡「创建」按钮（如 `set-podcast-category-tip` 的「稍后再说」、`show-support-tip` 的「我知道了」）。**每次点创建前必须全部关闭**：

```bash
agent-browser eval "(()=>{const tips=[...document.querySelectorAll('[id]')].filter(e=>/tip$/.test(e.id)&&e.offsetParent!==null); let n=0; for(const t of tips){const b=[...t.querySelectorAll('button')].find(x=>['稍后再说','我知道了'].includes(x.innerText.trim())); if(b){b.click(); n++;}} return 'dismissed '+n+' tips';})()"
```

### 4.9 勾选协议 + 点击创建（带重试）

```bash
for i in 1 2 3 4 5; do
  # 关闭所有可见 tip
  agent-browser eval "(()=>{const tips=[...document.querySelectorAll('[id]')].filter(e=>/tip$/.test(e.id)&&e.offsetParent!==null); for(const t of tips){const b=[...t.querySelectorAll('button')].find(x=>['稍后再说','我知道了'].includes(x.innerText.trim())); if(b)b.click();} return tips.length;})()"
  # 勾选「阅读并同意」
  agent-browser eval "(()=>{const lab=[...document.querySelectorAll('label')].find(l=>l.innerText.includes('阅读并同意')); const cb=lab?(lab.querySelector('input[type=checkbox]')||(lab.getAttribute('for')?document.getElementById(lab.getAttribute('for')):null)):null; if(cb&&!cb.checked)cb.click();})()"
  # 定位并点击创建（精确匹配文本「创建」，避免误点「创建投票」等）
  agent-browser eval "(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.innerText.trim()==='创建'); if(b){b.id='xyCreate'; return true;} return false;})()"
  if agent-browser click "#xyCreate" 2>/dev/null; then echo "CLICKED on attempt $i"; break; fi
  sleep 1
done
```

> 若 `agent-browser click` 仍报 "covered by ... tip"，说明又有新 tip 出现，循环会自动重新关闭并重试。

### 4.10 成功校验 + 截图

点击后 URL 应跳转到 `/episode/{eid}/stats`。校验并截图：

```bash
sleep 3
agent-browser get url
# 期望: https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/episode/{eid}/stats
agent-browser screenshot publish_success.png
```

用 `present_files` 展示 `publish_success.png`。确认标题、封面、描述均正确即发布成功。

### 4.10.5 回编辑页校验封面（关键兜底）

封面最容易"假成功"——上传/裁切任一步没真正写入，发布后封面会静默回退成默认图，肉眼不易察觉。发布后**必须**回编辑页确认封面上传区实际显示的是预期图：

```bash
agent-browser open "https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/episode/{eid}/edit"
sleep 3
agent-browser eval "(()=>{const area=document.querySelector('._root_1m0ke_1'); if(!area)return 'NO_COVER_AREA'; const img=area.querySelector('img'); return JSON.stringify({areaText:area.innerText.slice(0,20), hasImg:!!img, imgSrc:img?img.src:null});})()"
# 期望: { "areaText":"单集封面", "hasImg":true, "imgSrc":"https://image.xyzcdn.net/<新hash>.jpg@small" }
```

判读：
- `hasImg: true` 且 `imgSrc` 是新的 `xyzcdn.net` 链接 → 封面已正确写入，✅ 完成。
- `areaText` 仍含「点击上传封面」或 `imgSrc` 是旧的/默认图 → **封面没生效**。回到 4.7 重新上传并点裁切，再点编辑页的「更新」提交（编辑页提交按钮文本是「更新」而非「创建」）。
- 公网页 `og:image` 短暂显示旧图是 CDN 缓存，只要编辑页 `hasImg:true` 即可，缓存会自然刷新。

> ⚠️ 若发布后发现封面错误（如本次实战）：直接在编辑页 `/episode/{eid}/edit` 重传封面（4.7 同样流程）→ 点「裁切」→ 点「更新」即可，无需重新创建单集。

---

## Phase 5: 清理

```bash
rm -f /tmp/inject_js.txt transcript_full.txt xiaoyuzhou_qr.png
# 浏览器会话可保留供用户查看；如需关闭：agent-browser close
```

---

## 交互式确认节点汇总

| 节点 | 位置 | 确认内容 |
|------|------|---------|
| ✅1 | Phase 0.3 | bmx 连接和登录状态 |
| ✅2 | Phase 1.3 | 选择 original 还是 mixed |
| ✅3 | Phase 1.5 | 选中的音频文件和字幕 |
| ✅4 | Phase 2.6 | YouTube 视频链接、真实发布日期（精确到日）、封面 |
| ✅5 | Phase 3.5 | 生成的标题和单集内容 |
| ✅6 | Phase 4.2 | 小宇宙已登录 |
| ✅7 | Phase 4.10 | 发布成功截图 |
| ✅8 | Phase 4.10.5 | 回编辑页校验封面已正确写入（`hasImg:true` 且为新 `xyzcdn` 图，非默认图） |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| bmx 未安装 / 已装但损坏 | `pip install --force-reinstall --no-cache-dir "git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk"`；重装后必须 `bmx --help` 复查。PyPI 版 `bilimix-cli` 1.0.0 缺 `cmd_vocab_list` 会直接崩，只能从 GitHub 装 |
| bmx 登录失败 | 重新收集用户名密码 |
| bmx 无已完成任务 | 引导用户先提交并处理音频 |
| `--field transcription` 返回 `null` | 从 `segments` 数组提取文本 |
| YouTube `site:` 搜索无结果 | 改用 `WebFetch` 访问 `youtube.com/results` 搜索页；仍无结果则请求用户提供 Google 截图 |
| YouTube 缩略图 404 | 自动降级为 Pillow 文字封面 |
| QR 码 canvas 渲染不全 | 从 React Fiber 提取 URL，Python qrcode 重生成 |
| 登录轮询误判（grep 匹配到 URL query 参数） | 改用 `snapshot` + `grep "创建节目"` 等页面内容词检测 |
| 登录超时（轮询未进入后台） | 用 AskUserQuestion 询问「重新生成二维码」，重跑 4.2 |
| `agent-browser upload` 报 "Node is not a file input element" | 那是 div 点击区；给隐藏 `input[type=file]` 赋 id 后 `agent-browser upload #id` |
| Show Notes 注入后内容为空 | Show Notes 是 contenteditable，用 4.5 的 base64 JS 注入，勿用 `type`/`fill` |
| Show Notes 含 `**` / `- ` / `---` 等 Markdown 字面量（发布后像乱码） | 不能用 `textContent` 注入纯文本，也不能直接注入原始 Markdown。用 `extract_show_notes.py` 渲染成 HTML，并在 4.5 用 `innerHTML` 注入，保留加粗/段落/链接 |
| 章节导航预览被用户驳回 | 确保每个章节有 1-2 句完整描述，时间戳来自 segments 的 `start` 字段，重新生成 |
| 封面上传后**未**弹出「裁切图片」对话框 | 上传没生效。先按 4.6 的 eval 确认 `input[type=file][2]` 父链含「单集封面」（创建页 input 可能尚未渲染/索引不同）；确认无误后重传，必须等到裁切弹窗出现 |
| 创建前出现「设置分类」/「获取帮助」等 tip 遮挡 | 用 4.8 的 eval 批量关闭「稍后再说」「我知道了」，再点创建 |
| 「创建」点击报 "covered by ... tip" | 仍有 tip 遮挡，重跑 4.9 重试循环自动关闭后点击 |
| 「创建」按钮有二义性 | 按 `textContent.trim()==='创建'` 精确匹配，避免误点「创建投票」 |
| 发布后封面是默认图/与原图不符 | 上传封面后没点「裁切」或传错 input。回编辑页 `/episode/{eid}/edit` 重传封面（4.7 流程）→ 点「裁切」→ 点「更新」提交；用 4.10.5 的 eval 校验 `._root_1m0ke_1` 内 `img.src` 是否为预期图 |
| 编辑页提交按钮文本是「更新」而非「创建」 | 编辑/改封面时用「更新」按钮；创建新单集时才用「创建」 |
| 文件大小超限（>200MB） | 提示用户小宇宙限制 ≤200MB |
| `agent-browser open` 报 `ERR_PROXY_CONNECTION_FAILED`（浏览器继承系统代理但代理不可达，如 ClashX 关闭） | 先 `agent-browser close`，再用 `agent-browser open --args "--no-proxy-server" URL` 直连；直连前用 `curl -sS --noproxy '*' -m 8` 验证目标站可达 |
| `agent-browser eval` 报 `Illegal return statement`（顶层 return 在脚本上下文非法） | 注入 JS 必须包成 IIFE：`(()=>{ ... return xxx; })()`，见 4.5 示例代码 |
| Show Notes 中文显示乱码（如 `本期核心内容` → `å¼ å§æ ¸å¿ƒå… å®¹`），英文/URL 正常 | `json.dumps` **必须用 `ensure_ascii=True`**（不能 False）；False 时原始 UTF-8 多字节字符在 shell→base64→eval 链路中被截断误解码；True 时所有非 ASCII 转为 `\uXXXX` 纯 ASCII，浏览器端正确还原 |
