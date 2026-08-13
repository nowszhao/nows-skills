---
name: nows-ytb-bilingualex
description: "This skill should be used when the user gives a YouTube video URL and wants (1) the video downloaded as an MP4 file and (2) a bilingual English || Chinese .ass subtitle file for that video. The subtitle is built from YouTube's official auto-generated ASR (timedtext — the SAME underlying data the video page's 转写文稿/transcript panel displays), aggregated into sentence-level, non-overlapping lines, translated into natural, context-aware, voice-synthesis-ready Chinese using the Agent's built-in model, and assembled into a line-by-line bilingual .ass that keeps the original start timestamps. It reuses the browser login session (Chrome cookies) so member-only / age-restricted videos can still be fetched. Do not use for plain subtitle translation of files the user already has — use youtube-subtitle-cleaner for cleaning messy .ass files."
agent_created: true
---

# YouTube MP4 + Bilingual ASS

Turn a YouTube URL into two deliverables:
1. **MP4** — the video, at a quality the user chooses interactively.
2. **Bilingual .ass subtitle** — every Dialogue line is `English || Chinese`,
   timestamps taken from the aggregated transcript. The .ass file is written
   with the **same base name as the MP4** (e.g. `Talk.mp4` → `Talk.ass`) so the
   pair stays matched in a media library.

The pipeline is deliberately scripted end-to-end so no step requires
exploration: environment setup, auth reuse, downloading, parsing, aggregation,
splitting, assembly, and validation are all deterministic scripts. The only
step that uses the Agent's own intelligence is the translation itself.

## When to use

- User pastes a YouTube URL and asks for the video file (MP4), with or without
  subtitles.
- User asks for bilingual (EN || ZH) subtitles for a YouTube video / interview /
  talk / lecture.
- User wants the Chinese translation to sound natural and to be suitable for
  Chinese voice synthesis (配音), not machine-translated.

## Subtitle source (canonical)

The subtitle is built from YouTube's **official auto-generated ASR**
(`--write-auto-subs`, `en` track). This is the same underlying data as the
video page's 转写文稿 (transcript) panel — both come from the timedtext ASR
stream. The raw ASR is a **rolling-window fragment stream** (e.g. `0:00 Hi, my
guest today needs almost no` / `0:03 introduction in the data world. He`, with
windows ~2s apart), so it MUST be aggregated into sentence-level lines with
`aggregate_srt.py` before translation. `aggregate_srt.py` also **de-overlaps**
the output (each line's END is set to the next line's START), so the delivered
subtitle is strictly non-overlapping — the same back-to-back convention the
transcript panel displays.

> Why not drive the transcript panel in a browser (CDP/agent-browser)? Tried
> and abandoned (2026-08): CDP-created background tabs render the panel's
> transcript button invisible (rect 0×0), clicks never fire the caption request,
> and the panel only loads in a fully-interactive, logged-in tab that
> automation can't reproduce from scratch. The reliable path is to fetch the
> ASR directly — same data, no UI.

## Workflow (run in order)

Work in a dedicated working directory (create one per video, e.g.
`01_<title>/`). All paths below are relative to that directory. Run scripts
with the managed Python interpreter. Every script prints progress to
stderr/stdout — read it before continuing.

### Step 0 — Environment check (once per machine)

```bash
python3 <skill>/scripts/check_env.py --env-out yt_env.json
```

Installs `yt-dlp` (into an isolated venv if not on PATH) and ensures `ffmpeg`
exists (for merging video+audio). Writes `yt_env.json` used by later scripts.
**For a batch, copy `yt_env.json` into every per-video directory** (it's
machine-specific, not per-video). If it exits non-zero, resolve the missing
binary (hints are printed) before proceeding.

### Step 1 — Ask the user for video quality (interactive)

Before downloading, ask the user which quality they want. Present real options,
e.g.:

- **最高质量** (best available)
- **1080p**
- **720p**
- **480p**
- custom height

Map the answer to `--quality best|1080p|720p|480p|<height>`. Default to **best**
if the user has no preference. For long interviews/talks where file size matters,
recommend 720p.

### Step 2 — Download MP4 (background) + fetch ASR

**先并行启动 MP4 下载（后台），再拉字幕——两者互不依赖。** 用户选定质量后立即启动
下载，让它在字幕/翻译期间并行完成：

```bash
# 后台启动（run_in_background=true，勿用 shell `&`——会被工具会话结束杀掉）
python3 <skill>/scripts/download.py \
    --url "<youtube_url>" \
    --quality 720p \
    --cookies-browser chrome \
    --output . \
    --env-out yt_env.json > download.log 2>&1
```

> ⚠️ **启动后 3–5 秒必须检查 `download.log`**，确认出现 `[download]` 进度输出——
> 防止参数错误/环境问题导致下载**静默失败**。若日志只有 usage/error，立即修复重跑。
>
> `download.py` 用 `--cookies-from-browser chrome` 复用登录态（会员/年龄受限视频
> 可下）。**内置反爬降级**：默认 web client 撞上 "Sign in to confirm you're not
> a bot" 时会自动带 `--extractor-args youtube:player_client=web_embedded` 重试
> （实测绕过，无需人工干预）。若仍失败，把 yt-dlp 错误原样报给用户。

同时（前台执行）拉取官方 ASR 并聚合为句级：

```bash
yt-dlp --write-auto-subs --sub-langs "en" --sub-format "srt" --convert-subs srt \
    --skip-download --cookies-from-browser chrome \
    -o "raw_asr.%(ext)s" "<youtube_url>"
python3 <skill>/scripts/aggregate_srt.py raw_asr.en.srt transcript_official.srt \
    --max-gap 700 --max-group 7500
```

`aggregate_srt.py` 把滚动窗口碎片合并成 ~5-9s 的句子级 SRT，并**去重叠**（每条
END = 下一条 START）。**START 永不动**（语音起始点 = 音频对齐锚点）。

### Step 3 — Split into translation chunks

```bash
python3 <skill>/scripts/split_translation.py "transcript_official.srt" \
    --lines-per-part 70 --out .
```

Reads the transcript-derived SRT (`.ass` and `.srt` both accepted), strips
ASS override tags, and writes:

- `transcript.txt` — every event on one line: `<idx>\t<start>\t<end>\t<EN>`
- `parts/part_01.txt …` — chunks of ≤70 lines each, **each chunk carrying a
  context header**:
  - `GLOBAL CONTEXT` — the video title / URL / duration / subtitle source
    (read from `manifest.json`), so every chunk is translated with the full
    picture in mind;
  - `PREVIOUS CHUNK` — the last 4 lines of the previous chunk (configurable via
    `--context-lines`, set `0` to disable), so boundary sentences keep their
    continuity. All context lines are prefixed with `#` and are reference-only.
- `parts/manifest.json` — chunk bookkeeping
- `subtitle_meta.json` — original header + events

Adjust `--lines-per-part` for very long videos (smaller chunks = more reliable
translation, more passes).

### Step 4 — Translate with the Agent's built-in model

This is the only intelligence step and it is deliberately model-agnostic: any
Agent with any built-in model can execute it.

**并行策略（实测优化，省 ~30% 翻译耗时）：**

- **一次性并行派发所有分块**（每个 subagent 2 个分块，全部 agent 在同一轮发出，勿一轮一个串行等），然后逐个验证返回。
- **每个 agent 返回后立即验证行数 + 内容对齐**：
  - 行数：`trans_NN.txt` 行数 = 输入行数（缺失的当场重派）。
  - **内容对齐（强制）**：跑 `verify_translation.py`，逐行对比 trans 的 EN 与源 transcript.txt 的词重叠率，**一轮抓出 off-by-one 整块偏移**（见下）。
- subagent prompt 必须要求**完成后返回输出行数**，便于立即核对。
- 全部批次结束后再做一次全量校验：总行数 = 70×(N-1) + 尾块行数。

```bash
python3 <skill>/scripts/verify_translation.py --workdir .
```

> ⚠️ **已知失败模式：翻译 agent 整块偏移（2026-08 在一个 58 分钟视频里出现 2 次，各浪费 20+ 分钟）**。
> 症状：chunk 中间某一行被**合并/跳过**后，其后所有行内容整体上移一格、末行重复；时间戳可能正确也可能跟着错位——
> 时间戳错位时 assemble 能抓到，但**时间戳正确而内容错位时 assemble 校验通过、只有 verify_translation.py 能发现**。
> 处理：`verify_translation.py` 会提示"内容更接近 src[N]"，据此按以下机械步骤重建（约 5 分钟）：
> 1. 找到偏移起点（某行把源第 N 行并进了 N-1）；
> 2. 起点行裁剪为源内容；起点+1 行补译缺失的一句；其后各行整体下移一格取回正确内容；
> 3. 时间戳一律用 transcript.txt 的源值；
> 4. 重新 verify + assemble。
> 预防：分块越小越不易偏移（`--lines-per-part 50` 更稳，代价是多几个 agent）；翻译 prompt 已加"禁止合并/跳行"硬规则。

For each chunk `parts/part_NN.txt` (parallel with separate subagents, 2 per
agent):

1. Read the instructions in `<skill>/references/translation_prompt.md`.
2. **Read the chunk's context header first** (GLOBAL CONTEXT + PREVIOUS CHUNK)
   — it gives the video topic and the preceding lines for continuity; then
   translate the chunk, honoring **every** rule there — especially:
   - Natural, idiomatic Chinese; **never word-for-word**; resolve pronouns and
     ellipsis from context.
   - Suitable for **Chinese voice synthesis**: complete, spoken-style sentences,
     no translation-ese, length matched to the on-screen time.
   - Keep `<idx>`, `<start>`, `<end>` byte-identical; **never touch timestamps**.
   - Same number of output lines as input; 1:1 mapping.
   - Never translate or echo the `#` context lines.
   - **TTS 净化（实测强制项）**：删除舞台指示（`[cheering]`/`[applause]`/`[music]`
     /`[snorts]` 等及其中译，TTS 会照读）；识别并删除混入句尾的章节标题；行内不拆词
     断句；全片人称统一（访谈/教程用"你"不用"您"）；全面 ASR 纠错（人名/品牌/乱码
     重建/拼写统一）。
   - **纯音乐行（整行只有 `[Music]`）**：EN 列写 `...`，ZH 列写 `♪`（两端都必须有
     内容，否则 assemble 校验报 "both languages empty"）。
3. Write the result to `parts/trans_NN.txt` in format
   `<idx>\t<start>\t<end>\t<corrected EN>\t<ZH>` (UTF-8).

The translation prompt includes the user's exact reference example:

```
142	0:47:27.84	0:47:35.75	self-esteem the pretense of self-advocacy and self-respect soon we'll be able to measure that much	自尊——自我主张与自我尊重的伪装。很快我们就能更客观地衡量它了
```

When translating, always read the whole chunk first, keep the video title and
topic in mind for context, and treat the chunk as continuous speech.

### Step 5 — Assemble the bilingual .ass

```bash
python3 <skill>/scripts/assemble_final.py --workdir .
```

Rebuilds the `.ass` with `Text = "EN || ZH"` per line, reusing the original
timestamps. **The output filename automatically matches the MP4's base name**
(read from `manifest.json`): if the video is `Talk.mp4`, the subtitle is written
as `Talk.ass`. Use `--out <name>` to override. Runs validation and **exits
non-zero if anything is wrong**
(missing chunk, line-count mismatch, duplicate/missing idx, `||` inside a
language field, tab inside text, bad timestamps, or a timestamp that was
changed vs. the source — verified against `subtitle_meta.json`). Never deliver a
file this step rejects.

> **已知的两个校验失败场景及处理**：
> - **时间戳被翻译 agent 改动**（实测出现过 5 次）：校验报 `timestamp changed!`。
>   用 `grep -n "^<idx>\t" transcript.txt` 找回源时间戳，改回 trans 文件后重跑。
> - **纯音乐行两侧都空**：校验报 `both languages empty`。按 Step 4 的 `... ♪` 规范
>   补上。
>
> 注意：`assemble_final.py` 只校验**时间戳继承**（与源一致），不校验重叠——去重叠
> 由 `aggregate_srt.py` 在源头保证。

### Step 6 — Deliver

Present to the user:

- the MP4 file
- the bilingual `.ass` file
- `manifest.json` summary (title, quality, subtitle source kind)

Tell the user where the files are. If the subtitle came from ASR, mention that
minor recognition errors were corrected during translation (the corrected
English is in the `.ass`).

## Key invariants (do not break)

- **START timestamps are inherited, never recomputed or shifted.** The pipeline
  reads the ASR fragment timeline and re-emits each sentence's first-fragment
  start verbatim. Alignment with the audio is guaranteed by construction —
  pushing starts (e.g. to remove overlap) breaks lip-sync and is FORBIDDEN.
- **Output is strictly non-overlapping.** Each line's END = next line's START
  (set by `aggregate_srt.py`; same convention as the transcript panel). An
  overlapping batch observed 2026-08 had 3844 overlapping pairs — never deliver
  overlapping lines.
- **Delimiter is ` || `** (space-pipe-pipe-space). It must not appear inside
  either language field. Default ASS style: Noto Sans CJK SC, size 52.
- **Source subtitle is YouTube's official ASR (timedtext), aggregated
  sentence-level.** Never use YouTube's machine translation; never hand-edit
  timestamps to "fix" overlap.
- **Translation is the Agent's job, mechanics are the scripts' job.** Do not
  hand-write parsing/assembly logic that already exists in `scripts/`.
- **Delivered .ass is TTS-safe:** stage directions (`[music]`, `[snorts]`,
  "（欢呼声）" etc.), leaked chapter headings, and mid-word line breaks must be
  cleaned during translation — the .ass contains only spoken lines a voice
  synthesizer can read aloud.

## Resources

### scripts/
- `check_env.py` — probe/install yt-dlp + ffmpeg; write `yt_env.json`
- `download.py` — metadata probe, auth reuse (Chrome cookies), quality select,
  MP4 download only; auto-falls back to `player_client=web_embedded` on
  bot-check
- `aggregate_srt.py` — merge rolling-window ASR fragments into sentence-level
  SRT and **de-overlap** (each line's END = next line's START; starts never
  moved); run before split_translation
- `split_translation.py` — parse SRT/ASS → transcript + chunks + manifest
- `verify_translation.py` — post-translation CONTENT check (token overlap vs
  source); catches off-by-one block shifts that assemble_final can't see; run
  after every translation batch
- `assemble_final.py` — merge translated chunks → bilingual .ass + validation
- `deoverlap.py` — (rare) give windowless lines a minimum visible window; NEVER
  de-overlaps starts, so audio alignment is always preserved

### references/
- `translation_prompt.md` — full translation instructions for any Agent's
  built-in model (context-aware, TTS-ready Chinese, exact formats, worked example)
