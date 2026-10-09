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
| 字幕流水线 | `/Users/changhozhao/.workbuddy/skills/nows-ytb-bilingualex` |

下文用 `<YTB>` 代指这个目录。

> ⚠️ **旧文档里的备份版目录 `nows-ytb-bilingualex.backup-20260806-2353` 已于 2026-10 从磁盘消失**
> （原先所有脚本路径都指向它）。现在**只有**上表这一个目录，`download.py` / `split_translation.py`
> / `assemble_final.py` / `refine_srt.py` 全从它取。开工前先 `ls <YTB>/scripts/` 确认，别照抄旧命令。

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
python3 <YTB>/scripts/aggregate_srt.py raw_asr.en.srt transcript_official.srt \
    --max-gap 700 --max-group 7500 --max-words 26
```

`aggregate_srt.py` 把滚动窗口碎片合成 ~5–9 秒的句级行，并**去重叠**（每行 END = 下一行 START）；**START 永不动**，保证与音频对齐。

> 备份版技能写的是用 CDP 驱动 Chrome 抓「内容转文字」面板。**实测该路径已不可用**（Chrome 9222 端口在监听，但 `/json/version`、`/json/list` 全部 404，拿不到任何 target）。官方 ASR 的 timedtext 与转写面板同源，直接用上面的 yt-dlp 方式即可，不要再尝试 CDP。详见 `references/pipeline_notes.md`。

### Step 5 — 确认视频真的有语音（**必做，跳过会白跑一轮**）

聚合后**先扫一眼 `transcript_official.srt` 的实际内容**，确认存在可翻译的台词：

```bash
grep -c "^[0-9]*$" transcript_official.srt     # 行数
python3 -c "print(open('transcript_official.srt').read()[:600])"
```

出现下列任一情况说明**该视频没有可配音的语音**（纯配乐 / 屏幕演示 / 静音片段）：

- 总文本只有几十个字符，内容全是 `[music]`、`Heat.`、`>>` 之类噪声；
- 行数为个位数，或去除噪声后有效单词数 < 20。

此时**不要继续切分翻译，更不要提交 bmx** —— 没有文本就没有配音内容，提交只会浪费服务端资源
（且服务端不去重）。向用户报告并确认后续（跳过 / 换源 / 用简介文案另做）。
可再拉 `en-orig` 轨道交叉验证：
`yt-dlp --write-auto-subs --sub-langs "en-orig" --sub-format json3 --skip-download -o orig.%(ext)s "<URL>"`

### Step 6 — FULL 语义重断句（**默认必走**）

`aggregate_srt.py` 只认机械信号（标点/静音/`--max-words`），会把一句完整的话从中间切成两半，
也会切出大量 1–2 秒碎片行。**实测一部 156 行的片子里有 53 行英文以 and/the/to 结尾、9 行中文
以标点开头** —— 配音时会读成悬空句。这一步让模型按语义重新断句（可跨行合并/拆分），修掉这个问题。

```bash
python3 <YTB>/scripts/refine_srt.py prepare-full transcript_official.srt raw_asr.en.srt \
    --workdir . --lines-per-part 40 --max-words 16
```

- 产出 `refine_parts/refine_part_NN.txt`（带上下文头的指令文件）+ `refine_plan.json`。
- 逐块处理，结果写 `refine_parts/refined_NN.txt`，格式为 `S<seq>\t<句子>`（每文件独立编号）。
- **唯一的铁律：一个词都不能删。** 包括 `uh/um`、重复词（`the the`）、连接词（`and/to`）全部原样
  保留，只允许加标点。模型重写句子时天然想清理语气词，**约 20% 的分块会漂**，一旦漂了 `apply`
  的贪心匹配会失配、导致时间轴整体塌缩。指令文件里的 prompt 第一条就要写这条，并点名警告。
- 每个分块只允许 5–16 词一句，**不输出时间戳**（时间戳全部由脚本从源碎片继承）。

```bash
python3 <YTB>/scripts/check_refined.py --workdir . --mode full   # 词集 + 词序双校验，必须 ALL PASS
python3 <YTB>/scripts/refine_srt.py apply --workdir . --out transcript_refined.srt
```

`check_refined.py` 报 `DRIFT FOUND` 时**单独重派那一个分块**（在 prompt 里点名错误类型），
**禁止用脚本机械插词修复**（会破坏词序，白跑一轮）。apply 后即使 exit 0 也要再扫一遍输出 SRT：
无连续相同 START 的长 run、无 START 递减、无重叠。

> 后续 Step 7 的输入恒为 `transcript_refined.srt`，不再用 `transcript_official.srt`。

> ⚠️ **`apply` 会塌缩，即使 `check_refined.py` 报 ALL PASS（2026-10 实测，85 分钟视频）**：
> 27 个分块的词流与源**严格逐词相等**（自己写严格比对验证过，0 块漂移），
> `check_refined.py` 也 ALL PASS，但 `refine_srt.py apply` 仍然把 **859 行锚到同一个
> START（5108.34s）**，前一行甚至出现 1705s→4038s 这种 2300 秒的巨型窗口。
> 根因是它拿 refined 词流去贪心匹配 `raw_asr` 碎片，而 `aggregate_srt.py` 做过去重叠，
> 两侧词流并不一致（`unmatched sentence words 10142` 就是这个症状）。
> **apply 后必须扫时间轴，别信 exit 0：**
> ```bash
> python3 - <<'EOF'
> # 扫 transcript_refined.srt：连续相同 START 的 run / START 递减 / 超长行
> EOF
> ```
> 出现塌缩时的**修复办法**：词流既然严格 1:1，就不必贪心匹配 —— 直接跑
> `python3 <skill>/scripts/refine_apply_exact.py`（本技能自带，工作目录下执行），
> 它按词序把每个句子的首词映射回 `transcript_official.srt` 所属行并**行内按词数比例插值**，
> 句 END = 下一句 START。实测输出 1309 行：**0 个相同 START、0 倒挂、0 超长行**。
> 用法：`cp` 到工作目录或直接在技能目录下用 `--workdir`（脚本默认取自身所在目录为 workdir，
> 放在工作目录里跑最简单）。塌缩时不要回去重派分块 —— 分块没问题，是 apply 的匹配策略问题。

### Step 7 — 切分、翻译、合并

```bash
python3 <YTB>/scripts/split_translation.py transcript_refined.srt \
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

### Step 8 — 提交 bmx 视频任务

#### Step 8.0 — 先定中文任务标题（**不要直传英文原标题**）

`--title` 是这条配音视频后续分发时用的名字，中文平台投放必须是中文标题。
**禁止把 YouTube 英文原标题原样传进去。**

生成规则（与 `nows-ytb-vcover` 共用一套公式库，倍数来自 B 站 2,400 条 AI 视频样本实测）：

- **12-24 字**（推荐流区间；300w+ 层标题中位 24 字，1w 以下层 30 字）；
- 钩子按优先级取：否定反转（×2.42）／具象人物（×2.00）／第一人称＋代价（×1.81）／
  对比跨度（×1.69）／悬念收尾（×1.62）／提问（×1.37）；
- **禁用**「讲透」「全覆盖」「一次讲清」「学会」「全集」等教程承诺词（实测 ×0.64，全模板最低）——
  英文原标题多为 `How we built X` / `A deep dive into Y` 式陈述句，**直译必然落进这个最差区间**；
- 主标题里专名不超过 1 个（实测工具名堆砌 ×0.81）；
- 收尾用 `？` / `！` / 悬念留白，不要平淡陈述句。

| 英文原标题 | 直译（✕ 别用） | 改写（✓） |
| --- | --- | --- |
| How we built our multi-agent research system | 我们如何构建多智能体研究系统 | 三个 Agent 互相纠错，才敢叫研究系统 |
| A deep dive into LLM evaluation | 深入探讨大语言模型评估 | 你的 Eval，可能一直在骗你 |
| Building production agents at Anthropic | 在 Anthropic 构建生产级 Agent | Anthropic 自己，怎么把 Agent 送上生产？ |

把定好的中文标题记在工作目录（如 `title.txt`）备查。`--video` / `--subtitle` 保持 MP4/ASS 的实际文件名
（由下载时的原标题生成，不必重命名），**只有 `--title` 传中文标题**。

#### Step 8.1 — 预检与提交

**必须显式传 `--bmx <venv 路径>`。** 机器上往往存在多个 `bmx`（如 `/opt/homebrew/bin/bmx`），脚本 `shutil.which("bmx")` 可能挑到另一个二进制，它没登录过 → `auth status` 直接 HTTP 403，报错「未登录或服务端不可达」是**假警报**。用前置表格里的 venv 路径，别让脚本自己找。

**先预检，再提交。** 服务端**没有任务去重**，脚本跑两次就会提交两个任务。所以固定两步走：

```bash
BMX=/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/bmx

# 1) 预检：只上传 + 校验，不提交
python3 scripts/bmx_video_task.py --bmx "$BMX" \
    --video "<标题>.mp4" --subtitle "<标题>.ass" --no-submit

# 2) 确认输出「字幕校验通过：N 行，全部为双语」后再真正提交
python3 scripts/bmx_video_task.py --bmx "$BMX" \
    --video "<标题>.mp4" \
    --subtitle "<标题>.ass" \
    --title "<中文任务标题，12-24 字，见 Step 8.0>" \
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

**字幕字号必须显式传 40** —— bmx 服务端的 `--subtitle-font-size` **默认是 20**，偏小。
脚本 `bmx_video_task.py` 已把默认值锁成 `40`（每次都会显式传参），不要再改回 `None`
（不传 = 服务端用 20）。需要别的字号时用 `--subtitle-font-size N` 覆盖。

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
- **中文标点必须全角（2026-10 实测）**：subagent 翻译常输出半角 `,;!?`（一部 1190 行的片子里
  138 行中招，例如「但现在我看到了,那确实不行,对吧？」）。
  **最省事的做法是把它写进翻译 prompt 的硬规则**（"中文标点必须用全角，不要用半角 , . ? !"）——
  写进 prompt 后实测 **0 行需要修正**；事后扫描只是兜底。兜底脚本逻辑：把**前后紧邻汉字**的半角
  标点替换成全角，跳过数字相邻的（避免误伤 `1,000`、`3.5`），改完重新 `assemble_final.py`。
- **背景音乐默认关闭**，除非用户明确要求保留。
- **校验报错先修数据**，不要绕过 `assemble_final.py` 或 `bmx subtitle parse` 硬提交。
- **所有路径都要加引号**：`download.py` 只把 `:` 之类替换成 `_`，标题里的空格和破折号（`—`）会原样保留在文件名里。
- **`--title` 传中文标题，不传英文原标题**（见 Step 8.0）。这条配音视频最终投中文平台，
  用 `How we built X` 直译的陈述句标题等于默认放弃推荐流分发。
- 若后续要用 `nows-ytb-vcover` 做封面与文案，**复用 Step 8.0 定下的中文标题**，
  保证 bmx 任务名、封面主标题、发布长标题三者一致。

## Resources

### scripts/

- `refine_apply_exact.py` — FULL 重断句后 `refine_srt.py apply` 塌缩时的**兜底 apply**。
  放在工作目录里执行即可（读 `transcript_official.srt` + `refine_plan.json` + `refine_parts/refined_*.txt`，
  写 `transcript_refined.srt`）。按词序 1:1 精确映射，不依赖碎片贪心匹配。
- `bmx_video_task.py` — 上传 MP4/ASS → 校验字幕 → 提交 bmx 视频任务。
  `--dry-run` 只打印命令；`--no-submit` 只上传并校验、不提交（排错/预检）；`--debug` 打印每条命令的原始返回。
  注意：服务端对已存在的文件名会自动追加 `_<timestamp>` 后缀，路径以 upload 返回的为准，不要自己拼。

### references/

- `bmx_reference.md` — bmx 命令全貌、参数语义、默认值与实测坑位。
- `pipeline_notes.md` — YouTube 侧实测结论（CDP 不可用、bot 检查、ASR 纠错技巧）。
