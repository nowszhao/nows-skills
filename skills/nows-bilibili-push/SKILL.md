---
name: nows-bilibili-push
description: 一站式把 BiliMix(bmx) 已完成配音的视频投稿到哔哩哔哩。流程为「列出已完成任务 → 下载视频与字幕 → 内容合规审查（默认开启）→ 裁剪风险片段 → 生成封面与简介 → 上传B站并定时发布」。当用户说「投稿B站」「帮我发到B站」「B站投稿」「发布到哔哩哔哩」「上传B站并设置定时」等，或要求把 bmx/配音视频发布到 B站时使用。默认定时发布为今天起第 10 天 10:00，用户可指定其他时间（B站限制：最早≥5分钟、最晚≤15天）。
agent_created: true
---

# Nows Bilibili Push

把 BiliMix（bmx）里已完成的配音视频，一条龙发布到 B站：**下载 → 合规审查 → 裁剪 → 生成封面/简介 → 投稿 → 定时发布**。

## 关键约束（先读，能省掉几小时调试）

1. **不要用 agent-browser 做上传。** 它内置 MITM 抓包代理，转发大文件时会打满 Node 事件循环，所有 CDP 命令（`get url`/`eval`/`screenshot`）永久挂起，且无关闭开关。改用本 skill 的 Playwright 脚本。
2. **bmx 下载必须前台跑。** 后台 Bash 会被沙箱拦截 bmx 服务器网络（HTTP 403）；前台命令会自动 bypass。
3. **B站定时限制：最早 ≥5 分钟、最晚 ≤15 天。** 默认「今天+10天 10:00」在合法范围内。
4. **创作声明是必填项。** 不选的话点「立即投稿」**不报错但也不提交**，会造成"假成功"。
5. **B站是双封面**：首页推荐 4:3 + 个人空间 16:9。API 的 `cover` 字段返回的是 **16:9 那张**，不能用它判断 4:3 是否成功。
6. **B站 Vue 组件不响应 `el.click()`**，必须派发完整鼠标事件序列。详见 `references/pitfalls.md`。
7. **发布前合规审查默认开启。** 只有用户明确说「跳过审查」才关；审查提示词与判定口径见 `references/compliance-review.md`，**不得自行简化或跳过**。
8. **合规门禁不可绕过。** 每条视频必须有 `<video>.compliance.json`（由 `trim_video.py` 写出）且 `result=pass/trimmed`，`bilibili_push.py` 会在启动浏览器前整体校验。不要改文件名、不要手工伪造该文件。

## 前置条件

- Python 环境已装 playwright：`pip install playwright`（脚本会自动找 Chrome，优先 agent-browser 自带的 Chrome for Testing，其次系统 Chrome）
- `ffmpeg` / `ffprobe`（裁剪视频用）：`ffmpeg -version`
- 已建立登录 profile（首次跑一次即可，之后长期复用）：
  ```bash
  python ~/.workbuddy/skills/nows-bilibili-push/scripts/setup_login.py
  ```
  脚本会生成二维码图片，用 B站 App 扫码确认；登录态存到 `~/.workbuddy/bili_profile`。
- bmx 凭据：`admin / bilimix2024`

## 工作流

### Step 1：列出 bmx 已完成任务
```bash
bmx task list
```
确认哪些是 completed，并记录**任务名（用作下载文件名）**和 task id。

### Step 2：下载视频与字幕（前台执行，别放后台）
```bash
bmx video download --task-id <id> -o "downloads/<任务名>.mp4"
```
多个视频逐个前台下载（并行容易触发 403）。下载完确认是 ISO Media MP4：
```bash
file "downloads/<任务名>.mp4"
```

同时取成片字幕（审查要用，含时间轴）：
```bash
SERVER=$(python3 -c "import json;print(json.load(open('$HOME/.bilimix/config.json'))['server'])")
BASE=<bmx task result <id> 里的 basename>
curl -L -o "downloads/<任务名>.ass" "${SERVER}/api/audio/${BASE}/${BASE}.ass"
```
本地已有 `.ass`/`.srt` 也可直接用。**两者都没有就停下来问用户**（提供字幕，或明确同意关闭审查），不允许「没字幕就当无风险」。

### Step 3：合规审查（默认开启）

详见 `references/compliance-review.md`（含完整提示词、分块规则、review.json 格式）。

```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/ass_to_transcript.py \
    --sub "downloads/<任务名>.ass" --chunk-min 20
```
产出 `transcript.json` / `transcript.txt` / `transcript.partNN.txt`。脚本会打印中文行占比，低于 50% 说明字幕来源不对，先找用户确认。

然后**按提示词逐块审查**（长视频别只审开头），把结果写成 `downloads/<任务名>.review.json`：

```json
{"video": "/abs/x.mp4", "reviewed_at": "2026-10-20T10:00:00",
 "issues": [{"start": 1234.5, "end": 1268.0, "level": "明确风险",
             "action": "cut", "reason": "...", "quote": "..."}]}
```

判定口径：
- 疑似风险 → `action: "review"`，**保留不裁**，汇报里列出交人工核实
- 明确风险但可最小修改 → `action: "review"`，给文案建议，不改画面
- 明确风险且无法忠实修改、但整段可删 → `action: "cut"`
- 删了内容就不成立 → `action: "block"`（该条不上传）

### Step 4：裁剪风险片段

```bash
# 先出计划给用户确认（不产出视频）
python ~/.workbuddy/skills/nows-bilibili-push/scripts/trim_video.py \
    --video "downloads/<任务名>.mp4" --review "downloads/<任务名>.review.json" \
    --transcript "downloads/transcript.json" --dry-run

# 确认后实际裁剪
python ~/.workbuddy/skills/nows-bilibili-push/scripts/trim_video.py \
    --video "downloads/<任务名>.mp4" --review "downloads/<任务名>.review.json" \
    --transcript "downloads/transcript.json"
```

- 无 `cut` 项 → 只写 `result=pass` 门禁，视频不动
- 有 `cut` 项 → 输出 `<任务名>.trimmed.mp4`，门禁写在 `<任务名>.trimmed.mp4.compliance.json`
  （门禁文件永远贴着「实际要上传的那个文件」，投稿脚本按这个路径校验）
- 删除比例 >20% 或删 >3 段 → `result=blocked`，**该条不投**，报告用户；用户坚持才加 `--force`
- 裁剪后自己要复核：新时长、内容是否还成立、标题/简介/封面有没有引用被删片段（引用了就改文案）

**裁剪会把用户的文案与成片对齐的责任交给 Agent，不要发一个和标题不符的视频。**

### Step 5：生成封面与简介
用 `nows-ytb-vcover` skill（输入原 YouTube 链接）产出每个视频的 `文案.md` + `封面.html`，
再用无头 Chrome 把 HTML 渲染成 1280×960 的 `封面.png`：
```bash
CHROME=$(ls -d ~/.agent-browser/browsers/chrome-*/Google\ Chrome\ for\ Testing.app/Contents/MacOS/Google\ Chrome\ for\ Testing | tail -1)
"$CHROME" --headless=new --disable-gpu --no-sandbox --disable-dev-shm-usage \
  --screenshot="封面.png" --window-size=1280,960 --hide-scrollbars "封面.html"
```
⚠️ **必须加 `--disable-gpu`**，否则 GPU 进程崩溃、渲染失败（只输出 HTML 不出图）。
封面 HTML 可直接复用 `vcover/<已有ID>/封面.html` 的样式改文字。
**封面标题默认直接选用「方案一」，不询问用户**（vcover 仍会在 `文案.md` 里产出 3 套方案备查，
但只按方案一渲染 `封面.png`）。仅当用户明确要求换方案、或指定自定义标题时，才改用对应方案。

### Step 6：组装 tasks.json
```json
[
  {
    "name": "便于识别的名字",
    "video": "/绝对路径/a.mp4",
    "cover": "/绝对路径/cover.png",
    "title": "标题（<=80字）",
    "desc": "简介（多行，含原视频地址/内容提炼/标签）",
    "tags": ["标签1", "标签2"]
  }
]
```
简介格式建议与频道既有风格一致：`原视频地址：https://...` 开头。

- `video` 必须指向**审查后实际要发的文件**：裁过的就是 `.trimmed.mp4`（与门禁文件里的 `video` 一致）。
- 可选字段：`"compliance": false`（该条跳过审查，必须用户同意）、`"compliance_file"`（自定义门禁文件路径）。

### Step 7：投稿
```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/bilibili_push.py \
    --tasks tasks.json
```
常用参数：
- `--schedule "2026-10-11 20:00"`：指定定时时间（**默认今天+10天 10:00**）
- `--no-submit`：只填表不提交，用于试跑验证
- `--only 0,2`：只跑指定条目
- `--compliance off`：关闭合规门禁，**仅当用户明确要求时使用**，汇总会标 `[未审查]`

脚本先校验合规门禁（不通过直接退出，不启动浏览器），再逐条投稿、用 API 校验稿件是否真进列表，并打印定时时间。

### Step 8：核对
```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/check_archives.py --match "关键词"
```
输出定时时间、分区、创作声明、封面宽高比。

## 脚本一览

| 脚本 | 用途 |
|---|---|
| `scripts/setup_login.py` | 首次扫码登录，建立持久化 profile（后续免登录） |
| `scripts/ass_to_transcript.py` | ASS/SRT → `transcript.json` + 带时间戳纯文本 + 审查分块 |
| `scripts/trim_video.py` | 按 `review.json` 裁剪视频，写合规门禁文件 |
| `scripts/bilibili_push.py` | **主脚本**：合规门禁校验 + 批量投稿 + 定时 + 自动校验 |
| `scripts/check_archives.py` | 核对稿件：定时时间 / 分区 / 创作声明 / 封面宽高比 |
| `scripts/set_schedule.py` | 修改**已投稿**稿件的定时时间（`--match` 或 `--aid`） |

改时间示例：
```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/set_schedule.py \
    --match "OpenAI" --date 2026-10-08 --time 10:00
```

## 投稿时的默认取值（与既有频道保持一致）

| 项 | 值 | 说明 |
|---|---|---|
| **合规审查** | **开启** | 仅用户明确要求才 `--compliance off` |
| **封面标题** | vcover **方案一** | **默认自动采用，不询问用户**（除非用户明确要换） |
| 创作声明 | 内容无需标注 | B站 copyright=3；选"转载"会要求填来源 |
| 分区 | 保持页面默认（tid=27） | 不要改动 |
| 定时 | 今天+10天 10:00 | 用户可指定，须在 5分钟~15天 内 |

## 已知易错点

- 下载的两个视频若是**同源重复**（文件名只差一个 ID 后缀），只投其中一个，避免重复投稿。
- 调试时**别用真实投稿页反复点提交**——会真的发布出去。需要试跑就用 `--no-submit`。
- 已发布/定时中的稿件删除需要**验证码**，脚本删不掉，只能手动到内容管理删除。
- ⚠️ **编辑已投稿稿件（比如改封面）后再保存，定时日期可能被重置成默认值**。
  改完务必用 `check_archives.py` 复核，不对就用 `set_schedule.py` 改回来。
- ⚠️ **裁完忘了改 tasks.json** 会导致门禁失败（门禁文件里的 `video` 与待上传视频不一致）——这是故意设计的，防止"审查说要裁、实际发原片"。
- ⚠️ 字幕没拿到时**不要**直接关审查：先问用户。审查结论不等于平台审核保证，汇报时如实说明。

详细坑位与 DOM 结构见 `references/pitfalls.md`；合规审查口径见 `references/compliance-review.md`。
