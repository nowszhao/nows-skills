---
name: nows-ytb-bmxtask
description: "This skill should be used when the user gives a YouTube video URL (or a video title) and wants the whole chain done end to end — download the video as MP4, produce a bilingual English || Chinese .ass subtitle, and then submit the pair to BiliMix as a video dubbing task via the `bmx` CLI (background music off by default). Trigger phrases include 下载这个 YouTube 视频并配音, 生成双语字幕并建 bmx 任务, 用 bmx 新建视频任务, or any request that combines a YouTube link with bmx/BiliMix. It wraps the nows-ytb-bilingualex subtitle pipeline and then hands off to bmx."
agent_created: true
---

# YouTube → 双语字幕 → bmx 视频任务

一条命令链走完三件事：

1. **下载 YouTube 视频**为 MP4（**默认 720p**，用户明确指定时才改）。
2. **生成双语 .ass**（`英文 || 中文`），TTS 友好、时间戳与官方 ASR 对齐。
3. **提交 bmx 视频配音任务**（上传 MP4 + ASS → 校验 → 提交），**背景音乐默认关闭**。

## When to use

- 用户给一个 YouTube 链接（或视频标题），要求下载 + 生成双语字幕 + 建 bmx 配音任务。
- 用户已经有一对 MP4/ASS，只要求走 bmx 提交 → 跳到 Step 6，直接用 `scripts/bmx_video_task.py`。
- 用户说「用 bmx 新建视频任务」「配音任务」并提到 YouTube 素材。

## 前置（本机已验证）

| 工具 | 路径 |
| --- | --- |
| 托管 Python | `/Users/changhozhao/.workbuddy/binaries/python/versions/3.13.12/bin/python3` |
| yt-dlp | `/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/yt-dlp` |
| bmx | `/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/bmx` |
| 字幕流水线（备份版） | `/Users/changhozhao/.workbuddy/skills/nows-ytb-bilingualex.backup-20260806-2353` |
| 字幕流水线（当前版，提供 `aggregate_srt.py`） | `/Users/changhozhao/.workbuddy/skills/nows-ytb-bilingualex` |

下文用 `<YTB>` 代指备份版目录，`<YTB2>` 代指当前版目录。

## Workflow

### Step 1 — 解析输入（URL 或标题）

- 输入是 `youtube.com/watch?v=...` / `youtu.be/...` → 直接使用。
- 输入是标题或模糊描述 → 用 `yt-dlp "ytsearch1:<title>" --cookies-from-browser chrome -J` 解析出 URL 与标题，**向用户确认**后再继续（搜索结果未必是用户想要的那个）。
- 创建工作目录，建议 `<workspace>/ytb_<video_id>/`，全流程产物都放在这里。

### Step 2 — 画质（默认 720p，不再询问）

**默认直接用 720p，不要停下来问用户。** 配音场景下 720p 的清晰度足够，体积也最划算。

仅当用户**在需求里明确指定**画质时才覆盖，映射为 `--quality best|1080p|720p|<height>`：

| 用户说法 | `--quality` |
| --- | --- |
| 最高质量 / 最佳 / best | `best` |
| 1080p | `1080p` |
| 480p / 更小一点 | `480p` |
| 具体数值（如 1440） | `1440` |
| 未提及画质（默认） | `720p` |

不要在流程里插入画质选择提问；如果用户给的是标题而非链接，那一步才需要确认（见 Step 1）。

### Step 3 — 环境检查 + 元数据探测

```bash
python3 <YTB>/scripts/check_env.py --env-out yt_env.json   # 或用下面一行跳过
cp <上一个视频目录>/yt_env.json .                          # 同机器可复用，无需重跑
yt-dlp -J --cookies-from-browser chrome "<URL>" > meta.json
```

**必须加 `--cookies-from-browser chrome`** —— 不加会撞「Sign in to confirm you're not a bot」，`-J` 直接失败。

从 `meta.json` 读出 `title`、`duration`、`chapters`、`description`。**这是后面 ASR 纠错的关键证据**：YouTube 自动字幕把模型名、人名、专有名词念错的概率极高，而章节标题和简介里的写法是对的。翻译前先把这些正确写法整理成对照表。

### Step 4 — 并行：后台下载 MP4，前台拉字幕

先启动下载（用工具的后台执行机制，**不要用 shell `&`**，会话结束会被杀）：

```bash
python3 <YTB>/scripts/download.py --url "<URL>" --quality 720p \
    --cookies-browser chrome --output . --env-out yt_env.json
```

同时前台拉官方 ASR 并聚合成句级：

```bash
yt-dlp --no-warnings --no-playlist --write-auto-subs --sub-langs "en" \
    --sub-format "srt" --convert-subs srt --skip-download \
    --cookies-from-browser chrome -o "raw_asr.%(ext)s" "<URL>"
python3 <YTB2>/scripts/aggregate_srt.py raw_asr.en.srt transcript_official.srt \
    --max-gap 700 --max-group 7500 --max-words 26
```

`aggregate_srt.py` 把滚动窗口碎片合成 ~5–9 秒的句级行，并**去重叠**（每行 END = 下一行 START）；**START 永不动**，保证与音频对齐。

> 备份版技能写的是用 CDP 驱动 Chrome 抓「内容转文字」面板。**实测该路径已不可用**（Chrome 9222 端口在监听，但 `/json/version`、`/json/list` 全部 404，拿不到任何 target）。官方 ASR 的 timedtext 与转写面板同源，直接用上面的 yt-dlp 方式即可，不要再尝试 CDP。详见 `references/pipeline_notes.md`。

### Step 5 — 切分、翻译、合并

```bash
python3 <YTB>/scripts/split_translation.py transcript_official.srt \
    --lines-per-part 70 --out .
python3 <YTB>/scripts/assemble_final.py --workdir .
```

翻译是**唯一需要模型智能**的步骤，规则全部在 `<YTB>/references/translation_prompt.md`。逐块执行，结果写入 `parts/trans_NN.txt`，每行 `<idx>\t<start>\t<end>\t<修正后英文>\t<中文>`（真实制表符）。

硬性要求：时间戳一个字符都不能改；行数 1:1；字段内不得出现制表符或 `||`；删除舞台指示（`[applause]` 等）和混入句尾的章节标题；全片人称统一用「你」不用「您」；ASR 专名纠错后的英文写入「修正后英文」列。

`assemble_final.py` 会做完整校验并**在有问题时非零退出**；它拒绝的产物不要交付。输出的 `.ass` 自动与 MP4 同名。

合并后跑一次自查（两条 grep 都应有 0 命中，语速 4–6 字/秒为 TTS 舒适区）：

```bash
grep -nE "cheering|applause|laughter|欢呼|掌声|笑声|您" "<标题>.ass"
```

### Step 6 — 提交 bmx 视频任务

**先预检，再提交。** 服务端**没有任务去重**，脚本跑两次就会提交两个任务。所以固定两步走：

```bash
# 1) 预检：只上传 + 校验，不提交
python3 scripts/bmx_video_task.py --video "<标题>.mp4" --subtitle "<标题>.ass" --no-submit

# 2) 确认输出「字幕校验通过：N 行，全部为双语」后再真正提交
python3 scripts/bmx_video_task.py \
    --video "<标题>.mp4" \
    --subtitle "<标题>.ass" \
    --title "<原标题>" \
    --duration <秒数>
```

如果之前已经提交过同一对文件，先 `bmx task list --limit 10` 确认，不要重复提交。
脚本出错时用 `--debug` 看每条命令的原始返回。

脚本行为（详见 `references/bmx_reference.md`）：

1. `bmx auth status` 确认已登录；
2. `bmx audio upload` 上传 MP4 与 ASS（同一个命令，支持视频和字幕），拿到服务端路径；
3. `bmx subtitle parse` 校验：`count` 必须等于 `bilingual_count` 且非 0，否则拒绝提交；
4. `bmx task submit --type video ...` 提交，打印 `task_id` 与后续跟踪/下载命令。

**背景音乐默认就是关闭的** —— bmx 只有显式 `--keep-bgm` 才保留原视频 BGM。脚本从不默认加这个 flag；确需保留时手动加 `--keep-bgm`。

提交后：

```bash
bmx task status <task_id>                                  # 查进度
bmx task wait <task_id>                                    # 阻塞等完成
bmx video download --task-id <task_id> -o <name>_dubbed.mp4
```

## Key invariants（不要破坏）

- **时间戳只继承、不重算。** 字幕质量靠这一点保证，别去「优化」对齐。
- **分隔符是 ` || `**（空格-竖线-竖线-空格），不得出现在任一语言字段内部。
- **交付前自查**：grep 舞台指示（cheering/applause/laughter/欢呼/掌声/笑声）应为 0；grep 「您」应为 0。
- **背景音乐默认关闭**，除非用户明确要求保留。
- **校验报错先修数据**，不要绕过 `assemble_final.py` 或 `bmx subtitle parse` 硬提交。
- **所有路径都要加引号**：`download.py` 只把 `:` 之类替换成 `_`，标题里的空格和破折号（`—`）会原样保留在文件名里。

## Resources

### scripts/

- `bmx_video_task.py` — 上传 MP4/ASS → 校验字幕 → 提交 bmx 视频任务。
  `--dry-run` 只打印命令；`--no-submit` 只上传并校验、不提交（排错/预检）；`--debug` 打印每条命令的原始返回。
  注意：服务端对已存在的文件名会自动追加 `_<timestamp>` 后缀，路径以 upload 返回的为准，不要自己拼。

### references/

- `bmx_reference.md` — bmx 命令全貌、参数语义、默认值与实测坑位。
- `pipeline_notes.md` — YouTube 侧实测结论（CDP 不可用、bot 检查、ASR 纠错技巧）。
