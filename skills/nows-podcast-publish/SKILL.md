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

### playwright-cli

**小宇宙发布阶段使用 playwright-cli，不使用 agent-browser。** agent-browser 的 `upload` 命令对小宇宙 React 页面完全无效。

```bash
npm install -g @playwright/cli@latest
```

验证：`playwright-cli --version`

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

### 2.3 下载封面图片

从 YouTube URL 提取 11 位 `VIDEO_ID`：

```bash
for size in maxresdefault hqdefault sddefault; do
  curl -s -o /tmp/cover_temp.jpg -L "https://img.youtube.com/vi/{VIDEO_ID}/${size}.jpg"
  python3 -c "from PIL import Image; im=Image.open('/tmp/cover_temp.jpg'); exit(0 if min(im.size)>200 else 1)" && break
done
```

裁剪为 1400×1400 正方形：

```python
from PIL import Image
img = Image.open("/tmp/cover_temp.jpg")
w, h = img.size
s = min(w, h)
img = img.crop(((w-s)//2, (h-s)//2, (w+s)//2, (h+s)//2))
img = img.resize((1400, 1400), Image.LANCZOS)
img.save("{basename}_cover.png")
```

### 2.4 降级方案 — 文字封面

当所有缩略图均 < 200px 时，用 Pillow 生成深色文字封面（具体代码见旧版，保持不变）。

### 2.5 确认溯源结果

展示 YouTube 链接、发布时间、封面路径。用户确认后进入 Phase 3。搜索不到则请用户提供链接。

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

```
原文链接：{YouTube 视频 URL}（发布于 {发布时间}）
```

### 3.5 展示内容预览并确认

将标题和完整内容展示给用户预览。用 `AskUserQuestion` 确认。

### ⚠️ 3.6 内容一致性约束（关键）

**Phase 4 填入小宇宙的内容，必须与 Phase 3.5 用户确认过的内容逐字一致。** 禁止因打字效率、字符限制等原因临时简写、删改内容。若 `playwright-cli type/fill` 对大段文本有限制，使用 `run-code` + `editor.fill()` 直接注入完整文本。

---

## Phase 4: 小宇宙发布

### 概览：双工具协作

| 步骤 | 工具 | 说明 |
|------|------|------|
| 4.1-4.2 登录 | agent-browser | 打开登录页、QR 码展示 |
| 4.3 提取 cookie | agent-browser | 登录后提取 `document.cookie` |
| 4.4-4.10 操作 | **playwright-cli** | 所有上传和表单操作 |

> **为什么不用 agent-browser 全程操作？** agent-browser 的 `upload` 命令对小宇宙页面无效（返回 `✓ Done` 但文件未附加到 DOM）。playwright-cli 的 `setInputFiles` 可以直接操作 hidden file input。

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

### 4.3 提取 Cookie 并切换工具

```bash
# 提取关键 cookies
agent-browser eval "document.cookie"
```

需要提取的 cookie：`x-jike-access-token`、`x-jike-refresh-token`、`_c_WBKFRo`、`_jid`

> **⚠️ Cookie 提取时机**：刚登录时 `document.cookie` 可能不包含 `x-jike-access-token`（httpOnly cookie 在某些时机不可见）。**确认已登录（snapshot 显示播客后台）后再提取**，此时所有 cookie 通常已就绪。若仍缺 token，重试 `agent-browser eval "document.cookie"`。

```bash
# 提取播客 ID — 优先从页面链接提取
agent-browser eval "Array.from(document.querySelectorAll('a')).map(a => ({href: a.href, text: a.textContent?.trim()?.slice(0, 30)})).filter(x => x.href?.includes('/podcast/') && !x.href?.includes('/create'))"
```

记录 24 位 hex 播客 ID。然后关闭 agent-browser：

```bash
agent-browser close
```

### 4.4 启动 playwright-cli 并恢复登录态

```bash
playwright-cli open
```

创建 `playwright-cli.json` 配置 stdout 输出：

```json
{"outputMode": "stdout"}
```

注入 cookies：

```bash
playwright-cli run-code "
async page => {
  await page.context().addCookies([
    {name: 'x-jike-access-token', value: '<token>', domain: '.xiaoyuzhoufm.com', path: '/'},
    {name: 'x-jike-refresh-token', value: '<token>', domain: '.xiaoyuzhoufm.com', path: '/'},
    {name: '_c_WBKFRo', value: '<value>', domain: '.xiaoyuzhoufm.com', path: '/'},
    {name: '_jid', value: '<value>', domain: '.xiaoyuzhoufm.com', path: '/'}
  ]);
  return 'cookies set';
}
"
```

### 4.5 进入创建单集页面

```bash
playwright-cli run-code "
async page => {
  await page.goto('https://podcaster.xiaoyuzhoufm.com/podcast/{pid}/episode');
  await page.getByRole('button', { name: '创建单集' }).click();
  await page.waitForTimeout(3000);
  return page.url();
}
"
```

### 4.6 填写标题和 Show Notes

```bash
# 标题 — 直接用 fill 即可
playwright-cli fill 'input[placeholder*="标题"]' "{标题}"

# Show Notes — 必须用 Python + json.dumps 转义后注入
# playwright-cli run-code 中不能使用 require('fs')，Node.js 模块在此上下文中不可用
```

**Show Notes 注入的正确方法**：

```bash
# Step 1: 用 Python 读取内容文件并生成 JS 转义后的代码
python3 << 'PYEOF'
import json
with open('episode_content.md') as f:
    notes = f.read()
# 去掉标题行（已在表单中单独填写），从 ## 本期核心内容 开始
lines = notes.split('\n')
start = next(i for i, l in enumerate(lines) if l.startswith('## 本期核心内容'))
show_notes = '\n'.join(lines[start:])
js_code = f'''
async (page) => {{
  const editor = page.getByRole('textbox').nth(1);
  await editor.click();
  await editor.fill({json.dumps(show_notes)});
  return 'show notes filled';
}}
'''
with open('/tmp/inject_notes.js', 'w') as f:
    f.write(js_code)
PYEOF

# Step 2: 执行注入
playwright-cli run-code "$(cat /tmp/inject_notes.js)"
```

> **为什么不用 `fill` 命令**：`playwright-cli fill` 对大段中文文本可能被截断。`run-code` + `editor.fill()` 避开了这个问题。
>
> **为什么不用 `require('fs')`**：`playwright-cli run-code` 的代码在浏览器 page 上下文执行，没有 Node.js `require`。

### 4.7 上传音频和封面

小宇宙页面有 3 个 `input[type=file]`，全部 hidden。**filechooser 事件不会触发**，直接用 `setInputFiles`：

| 索引 | accept | 用途 |
|------|--------|------|
| 0 | `image/jpeg,image/png,image/webp` | 多图封面 |
| 1 | `audio/*` | 音频 |
| 2 | `image/jpeg,image/png,image/webp` | 单图封面 |

```bash
playwright-cli run-code "
async page => {
  // 上传音频
  await page.locator('input[type=file]').nth(1).setInputFiles('<音频绝对路径>');
  // 上传封面
  await page.locator('input[type=file]').nth(2).setInputFiles('<封面绝对路径>');
  await page.waitForTimeout(3000);
  return 'files uploaded';
}
"
```

> 上传后 `evaluate(el => el.files.length)` 可能返回 0（React 清空），但 UI 会显示文件名即表示成功。

### 4.8 处理裁剪对话框

上传封面后，小宇宙会自动弹出「裁切图片」对话框（封面已是 1400×1400 不需调整）：

```bash
playwright-cli run-code "
async page => {
  await page.getByRole('button', { name: '裁切' }).click({ force: true });
  await page.waitForTimeout(2000);
  return 'cropped';
}
"
```

### 4.9 处理遮挡元素

页面常有多层 overlay 遮挡（Modal overlay、portal divs、toast 提示）。**在点击「创建」之前必须全部清除。** 小宇宙创建页面常见的遮挡包括：

| 遮挡类型 | 按钮文案 | 处理 |
|---------|---------|------|
| 上传后「裁剪图片」 | 裁切 | 直接 `force click` 确认（封面已是 1400×1400） |
| 临时 toast 提示 | 稍后再说 | `force click` 关闭 |
| 设置节目分类 | 稍后再说 / 去设置 | 先点「稍后再说」跳过，继续 |
| 获取更多帮助 | 我知道了 | `force click` 关闭 |
| 未保存内容警告 | 取消/确定关闭 | 点「取消」保留表单数据 |

**务必在每次 upload 之后、点击创建之前，批量检查并关闭这些遮挡**：

```bash
playwright-cli run-code "
async page => {
  // 1. 裁剪对话框（上传封面后出现）
  const cropBtn = page.getByRole('button', { name: '裁切' });
  if (await cropBtn.count() > 0) {
    await cropBtn.click({ force: true });
    await page.waitForTimeout(2000);
  }
  // 2. 稍后再说（分类/toast）
  const dismissBtns = page.getByRole('button', { name: '稍后再说' });
  if (await dismissBtns.count() > 0) {
    await dismissBtns.first().click({ force: true });
    await page.waitForTimeout(1000);
  }
  // 3. 我知道了（帮助提示）
  const gotItBtn = page.getByRole('button', { name: '我知道了' });
  if (await gotItBtn.count() > 0) {
    await gotItBtn.click({ force: true });
    await page.waitForTimeout(1000);
  }
  // 4. 去设置（分类设置，不点，已被稍后再说覆盖）
  // 5. 滚动到底部确保「创建」按钮可见
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.waitForTimeout(1000);
  return 'all overlays cleared';
}
"
```

### 4.10 勾选协议并创建

```bash
playwright-cli run-code "
async page => {
  // 勾选「阅读并同意」
  await page.getByRole('checkbox', { name: '阅读并同意' }).check({ force: true });
  await page.waitForTimeout(500);
  // 点击「创建」— 注意精确匹配，避免点到「创建投票」
  await page.getByRole('button', { name: '创建', exact: true }).click({ force: true });
  await page.waitForTimeout(5000);
  return page.url();  // 应跳转到 /episode/{eid}/stats
}
"
```

### 4.11 发布成功截图

```bash
playwright-cli screenshot
cp .playwright-cli/page-*.png {basename}_publish_success.png
```

---

## Phase 5: 清理

```bash
playwright-cli close
rm -f playwright-cli.json transcript_full.txt xiaoyuzhou_qr.png
```

---

## 交互式确认节点汇总

| 节点 | 位置 | 确认内容 |
|------|------|---------|
| ✅1 | Phase 0.3 | bmx 连接和登录状态 |
| ✅2 | Phase 1.3 | 选择 original 还是 mixed |
| ✅3 | Phase 1.5 | 选中的音频文件和字幕 |
| ✅4 | Phase 2.5 | YouTube 视频链接和封面 |
| ✅5 | Phase 3.5 | 生成的标题和单集内容 |
| ✅6 | Phase 4.2 | 小宇宙已登录 |
| ✅7 | Phase 4.11 | 发布成功截图 |

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| bmx 未安装 | `pip install git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk` |
| bmx 登录失败 | 重新收集用户名密码 |
| bmx 无已完成任务 | 引导用户先提交并处理音频 |
| `--field transcription` 返回 `null` | 从 `segments` 数组提取文本 |
| YouTube `site:` 搜索无结果 | 改用 `WebFetch` 访问 `youtube.com/results` 搜索页；仍无结果则请求用户提供 Google 截图 |
| YouTube 缩略图 404 | 自动降级为 Pillow 文字封面 |
| QR 码 canvas 渲染不全 | 从 React Fiber 提取 URL，Python qrcode 重生成 |
| 登录轮询误判（grep 匹配到 URL query 参数） | 改用 `snapshot` + `grep "创建节目"` 等页面内容词检测 |
| `document.cookie` 缺少 token | 确认已进入后台页面后再试；httpOnly cookie 在页面跳转后可见 |
| agent-browser upload 无效 | **切换到 playwright-cli**，使用 `setInputFiles` |
| playwright-cli `require('fs')` 报错 | `run-code` 在 page 上下文执行，没有 Node.js API；改用 Python 预生成 JS 代码文件 |
| 章节导航预览被用户驳回 | 确保每个章节有 1-2 句完整描述，时间戳来自 segments 的 `start` 字段，重新生成 |
| playwright-cli snapshot 无输出 | 创建 `{"outputMode":"stdout"}` 配置文件 |
| 封面上传后弹出裁剪对话框 | 点击「裁切」确认 |
| 创建前出现「设置分类」/「获取帮助」等遮挡 | 依次 force click「稍后再说」「我知道了」，再滚动到底部找「创建」 |
| 「创建」点击后页面闪烁但 URL 未跳转 | 检查是否有未处理的 overlay（通常有「未保存内容」弹窗），点「取消」保留数据后重新清除遮挡 |
| 「创建」按钮有二义性 | 使用 `exact: true` 精确匹配 |
| 文件大小超限（>200MB） | 提示用户小宇宙限制 ≤200MB |
