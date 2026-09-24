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
    --max-gap 700 --max-group 7500 --max-words 26
```

`aggregate_srt.py` 把滚动窗口碎片合并成 ~5-9s 的句子级 SRT，并**去重叠**（每条
END = 下一条 START）。**START 永不动**（语音起始点 = 音频对齐锚点）。
`--max-words 26` 是词数硬兜底：即使标点/停顿信号全部失效，单行也不会长到离谱
（真正的语义断句由下一步的 LLM 整理完成）。

> ⚠️ **ASR 拉取被 PO-token 拦截（2026-08 实测）**：默认 web client 可能报
> `There are missing subtitles languages because a PO token was not provided` /
> `There are no subtitles for the requested languages`。此时给同一命令加
> `--extractor-args "youtube:player_client=web_embedded"` 即可取到 en ASR
> （与下载的 bot-check 降级同源；`tv` 客户端会报 "The page needs to be reloaded"，不要用）。

### Step 2.5 — LLM 语义整理（翻译前唯一智能步骤的入口）

> 为什么需要：`aggregate_srt.py` 只认机械信号（标点/静音/`>>`），口语无标点无停顿
> 时单行可达 26 词上限。这一步让 **Agent 的内置模型**基于上下文（GLOBAL CONTEXT +
> PREVIOUS CHUNK）重断句；**时间戳全部由脚本从源碎片继承**，模型只做断句决策、
> 绝不输出时间戳。

> **模式 FULL（默认，全量语义重断句，`prepare-full`）**——所有行由 Agent 语义重构，
> 可**保持/拆分/跨行合并**，修复机械断句把一句话切两半的问题（2026-08 实测：
> B 版开头保留 "…and I hope" 半句，FULL 版合并为完整句）。**2026-08 起作为默认**：
> 跨行断句质量明显优于 B，代价是多一轮全片模型调用（长视频 +30% 耗时，可接受）：
> ```bash
> python3 <skill>/scripts/refine_srt.py prepare-full transcript_official.srt raw_asr.en.srt \
>     --workdir . --lines-per-part 40 --max-words 16
> ```

> **模式 B（可选，只整理超长行）**——低开销，修复"单行 30+ 词"；仅当用户明确要求
> 快速出片或视频极长（>1.5h）且不在乎跨行断句质量时使用：
> ```bash
> python3 <skill>/scripts/refine_srt.py prepare transcript_official.srt raw_asr.en.srt \
>     --workdir . --max-words 16 --max-dur-ms 6000
> ```
> 只把超过阈值的行交给 Agent 断成 2-4 个子句，其余行保持机械边界。

- prepare / prepare-full 输出 `refine_parts/refine_part_NN.txt`（带上下文头的指令
  文件）与 `refine_plan.json`。**没有超长行时 prepare 直接打印 0、无动作**。
- 用 **subagent 并行**处理每个分块：模式 B 读 `<skill>/references/refine_prompt.md`，
  模式 FULL 读 `<skill>/references/refine_prompt_full.md`，整理后写入
  `refine_parts/refined_NN.txt`。
  硬规则：模式 B 输出 `<idx>\t<子句>`（idx 原样）；模式 FULL 输出 `S<seq>\t<句子>`
  （每文件独立编号，可跨行合并）；实词不许增删改、只可加标点、每句 5-16 词、
  **不输出时间戳**。
- **FULL 模式 subagent prompt 必写的第一条硬规则（2026-08 血泪教训）**：
  **"一个词都不能删——包括 uh/um/重复词（the the、to to）、连接词（and/to），
  全部原样保留，只允许加标点"**。FULL 模式 agent 重写句子时天然想"清理"语气词，
  实测 25 块中有 5 块（20%）删了 uh/um/and/to，直接导致时间轴塌缩。这条规则
  必须写在 prompt 最前面，并附一句"上一个 agent 删了 X 个词导致失败"的点名警告
  （若该块曾漂移）。

```bash
# apply 前必做：词集 + 词序双校验（2026-08 实测两个都要查，缺一漏坑）
# 一行命令：模式 FULL 用 --mode full（默认），模式 B 用 --mode b
python3 <skill>/scripts/check_refined.py --workdir . --mode full
# 输出 ALL PASS 才可 apply；DRIFT FOUND 则重派对应分块（见下方警告）
```

```bash
# apply：把整理结果映射回源碎片时间线，产出新的句子级 SRT（两种模式通用）
python3 <skill>/scripts/refine_srt.py apply --workdir . --out transcript_refined.srt
```

- `apply` 用**全局词流贪心匹配**逐句锚定：句子 START = 该句首词所在**源碎片的
  START**（继承，不重算；首词落在碎片内部时按词数比例在碎片内细化，避免重叠/0 时长）。
  校验词流覆盖率（句子必须覆盖全部源词），失败 exit 2。
- **apply 后必查时间轴**（即使 exit 0 也要查——覆盖率校验有盲区）：扫描输出 SRT，
  确认 ① 无连续相同 START 的长 run（塌缩）、② 无 START 递减（倒挂）、③ 无重叠。
  `unmatched sentence words` 大（几千）不必然坏，只要时间轴单调即可；但出现上述
  任一症状就是某块词序错乱，回查该块的词序校验。
- 默认 FULL 模式下全部行都已重写，**Step 3 的输入恒为 `transcript_refined.srt`**；
  仅走模式 B 且无超长行时才继续用 `transcript_official.srt`。

> ⚠️ **FULL 模式词漂移 → 时间轴整体塌缩（2026-08 实测，最坑的失败模式）**：
> 任一 subagent 在重断句时改动/新增/合并了实词（哪怕一个，"Newman"→"Newmann"、
> 多加 18 个词、把 "non googlele" 拼成 "nongooglele"），`apply` 的贪心匹配从该词
> 处开始失配并把 `pos` 直接推到底，**其后所有行塌缩到同一时间戳**（症状：输出里
> 大量 500ms/相同 START/重叠行，且 `unmatched sentence words` 巨大）。而覆盖率
> 校验有个盲区：`pos` 触底时 `consumed=100%` 会跳过检查，`apply` 照样 exit 0。
> **防患于未然（apply 前必做）**：跑上面的**词集 + 词序双校验**，发现漂移就单独
> 重派该分块，并在 prompt 里点名错误类型（如"禁止把 X 写成 Y"、"删了 uh/um 必须
> 补回"）。10-25 块中通常有 1-5 块会漂（FULL 模式删语气词是高频，约 20%），定向
> 修复比重跑全片便宜得多。
> **禁止用脚本机械插词修复漂移（2026-08 实测反例）**：在 refined 里"找前驱词插回"
> 会破坏词序（词集 100% 但 LCS 顺序匹配率掉到 0.92 以下），apply 照样塌缩，白跑
> 一轮。漂移了就直接重派该块，让 agent 用词序与源完全一致的版本重写。

### Step 3 — Split into translation chunks

```bash
python3 <skill>/scripts/split_translation.py "transcript_refined.srt" \
    --lines-per-part 70 --out .
```

> 输入选择：**默认 FULL 模式下用 `transcript_refined.srt`**（Step 2.5 已重写全部行，
> 行数更短更均匀）；仅当走模式 B 且确无超长行时才用 `transcript_official.srt`。
> 后续 split/assemble 全链路只依赖这一步的输出，与输入文件名无关。

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
> - **时间戳被翻译 agent 改动 / 整体 +1 偏移**（实测在连续 2 个视频复现）：`verify_translation.py`
>   **只校验内容对齐、不校验时间戳**，所以漂移对它隐形；只有 `assemble_final.py` 会报
>   `timestamp changed!`（典型症状：trans[idx] 的时间戳 = 源[idx+1]，文本内容却按 idx 正确）。
>   **修复（机械化，无需重译）**：先备份，再按 idx 从 canonical `subtitle_meta.json` 重锚全部
>   trans 行的时间戳，保留已翻译 EN/ZH 文本：
>   ```bash
>   python3 <skill>/scripts/reanchor_timestamps.py --workdir .   # 自动备份到 parts/trans_backup/ 并重锚
>   ```
>   重锚后重跑 `assemble_final.py` 即通过。⚠️ `verify_translation.py` 通过 ≠ 时间轴正确，
>   组装前务必先 reanchor 一次作为安全网（成本极低，可避免 assemble 失败返工）。
> - **纯音乐行两侧都空**：校验报 `both languages empty`。按 Step 4 的 `... ♪` 规范
>   补上。
> - **纯音乐行两侧都空**：校验报 `both languages empty`。按 Step 4 的 `... ♪` 规范
>   补上。
> - **模式 B 的 1ms 窗口行**（2026-08 实测）：apply 的碎片内词数比例细化可能把某行
>   算成 `559 --> 560`（1ms），split 显示成两位小数后变 `0:38:56.56 -> 0:38:56.56`
>   （start==end），assemble 报 `bad timestamps`。处理：把该行 START/END 改为精确
>   可表示的整 10ms 值（如 `560 --> 57060`，1ms 起点微调无音频影响），重新 split，
>   同步对应 trans 文件的 start/end，再 assemble。
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
  This extends to Step 2.5: a refined clause's START is the START of the source
  fragment holding the clause's first word — `refine_srt.py` anchors it, the
  Agent never writes a timestamp.
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
  moved); `--max-words 26` hard-caps line length as a mechanical safety net;
  run before refine_srt.py
- `refine_srt.py` — **LLM semantic re-splitting of ASR lines**: `prepare` (mode B,
  over-long lines only) and `prepare-full` (mode FULL, every line — keep/split/
  MERGE adjacent lines) write instruction chunks; `apply` anchors each output
  sentence onto the source fragment timeline with a greedy global word-stream
  match (START inherited from the fragment holding the sentence's first word;
  intra-fragment refinement by word-count ratio when the boundary lands inside
  a fragment). The Agent decides WHERE to split, the script owns every
  timestamp. Optional — runs before split_translation.py
- `check_refined.py` — **apply 前词集+词序双校验**（2026-08 新增，FULL 模式必备）：
  对每对 refine_part_NN/refined_NN 检查 ① 词集 Counter 100% 相等、② refined 词流
  相对源流的 LCS 顺序匹配率 >= 0.995；`--mode full|b`（默认 full）。检出漂移
  exit 1 并列出分块号，直接重派该块（禁止机械插词修复，会破坏词序）
- `split_translation.py` — parse SRT/ASS → transcript + chunks + manifest
- `verify_translation.py` — post-translation CONTENT check (token overlap vs
  source); catches off-by-one block shifts that assemble_final can't see; run
  after every translation batch
- `reanchor_timestamps.py` — pre-assemble SAFETY NET (2026-08 新增，连续 2 视频复现
  后固化)：翻译 agent 偶尔改动/整体 +1 偏移时间戳，verify 查不到，assemble 才报
  `timestamp changed`。本脚本按 idx 从 canonical `subtitle_meta.json` 重锚全部 trans
  行时间戳（保留 EN/ZH 文本），自动备份到 parts/trans_backup/；assemble 前跑一次零成本
- `assemble_final.py` — merge translated chunks → bilingual .ass + validation
- `deoverlap.py` — (rare) give windowless lines a minimum visible window; NEVER
  de-overlaps starts, so audio alignment is always preserved

### references/
- `translation_prompt.md` — full translation instructions for any Agent's
  built-in model (context-aware, TTS-ready Chinese, exact formats, worked example)
- `refine_prompt.md` — re-split instructions for the Step 2.5 LLM refine pass,
  mode B (over-long lines only; semantic clause boundaries, word-preservation
  rule, worked example)
- `refine_prompt_full.md` — mode FULL instructions (rewrite the whole block;
  keep / split / merge adjacent lines; per-part S<seq> output; word-preservation
  rule, worked example)
