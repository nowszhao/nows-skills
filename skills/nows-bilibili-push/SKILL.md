---
name: nows-bilibili-push
description: 一站式把 BiliMix(bmx) 已完成配音的视频投稿到哔哩哔哩。流程为「列出已完成任务 → 下载视频 → 生成封面与简介 → 上传B站并定时发布」。当用户说「投稿B站」「帮我发到B站」「B站投稿」「发布到哔哩哔哩」「上传B站并设置定时」等，或要求把 bmx/配音视频发布到 B站时使用。默认定时发布为今天起第 10 天 10:00，用户可指定其他时间（B站限制：最早≥5分钟、最晚≤15天）。
agent_created: true
---

# Nows Bilibili Push

把 BiliMix（bmx）里已完成的配音视频，一条龙发布到 B站：**下载 → 生成封面/简介 → 投稿 → 定时发布**。

## 关键约束（先读，能省掉几小时调试）

1. **不要用 agent-browser 做上传。** 它内置 MITM 抓包代理，转发大文件时会打满 Node 事件循环，所有 CDP 命令（`get url`/`eval`/`screenshot`）永久挂起，且无关闭开关。改用本 skill 的 Playwright 脚本。
2. **bmx 下载必须前台跑。** 后台 Bash 会被沙箱拦截 bmx 服务器网络（HTTP 403）；前台命令会自动 bypass。
3. **B站定时限制：最早 ≥5 分钟、最晚 ≤15 天。** 默认「今天+10天 10:00」在合法范围内。
4. **创作声明是必填项。** 不选的话点「立即投稿」**不报错但也不提交**，会造成"假成功"。
5. **B站是双封面**：首页推荐 4:3 + 个人空间 16:9。API 的 `cover` 字段返回的是 **16:9 那张**，不能用它判断 4:3 是否成功。
6. **B站 Vue 组件不响应 `el.click()`**，必须派发完整鼠标事件序列。详见 `references/pitfalls.md`。

## 前置条件

- Python 环境已装 playwright：`pip install playwright`（脚本会自动找 Chrome，优先 agent-browser 自带的 Chrome for Testing，其次系统 Chrome）
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

### Step 2：下载视频（前台执行，别放后台）
```bash
bmx video download --task-id <id> -o "downloads/<任务名>.mp4"
```
多个视频逐个前台下载（并行容易触发 403）。下载完确认是 ISO Media MP4：
```bash
file "downloads/<任务名>.mp4"
```

### Step 3：生成封面与简介
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

### Step 4：组装 tasks.json
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

### Step 5：投稿
```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/bilibili_push.py \
    --tasks tasks.json
```
常用参数：
- `--schedule "2026-10-11 20:00"`：指定定时时间（**默认今天+10天 10:00**）
- `--no-submit`：只填表不提交，用于试跑验证
- `--only 0,2`：只跑指定条目

脚本每投完一个会用 API 校验稿件是否真的进列表，并打印定时时间。

### Step 6：核对
```bash
python ~/.workbuddy/skills/nows-bilibili-push/scripts/check_archives.py --match "关键词"
```
输出定时时间、分区、创作声明、封面宽高比。

## 脚本一览

| 脚本 | 用途 |
|---|---|
| `scripts/setup_login.py` | 首次扫码登录，建立持久化 profile（后续免登录） |
| `scripts/bilibili_push.py` | **主脚本**：读 tasks.json 批量投稿 + 定时 + 自动校验 |
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

详细坑位与 DOM 结构见 `references/pitfalls.md`。
