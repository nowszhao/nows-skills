---
name: nows-ytb-bilingualex
description: Download a YouTube video and produce refined English–Chinese subtitles and complete Chinese dubbing units. Use for YouTube bilingual precision translation and natural spoken Chinese, including the BiliMix audio-first dubbing workflow.
metadata:
  agent_created: "true"
---

# YouTube 精翻与完整话语（音频优先 v1）

保留精翻和语义重组：同一人的多个字幕碎片可合并成完整话语。中文自然语速优先，画面随后变速适配。人物身份、配音话语、显示字幕分别保存；字幕切换不得触发额外 TTS 或句内停顿。

翻译与中文话语重组由本地本 skill 的模型执行；BiliMix 服务端负责原声分析、声线绑定、配音与音画合成。提交 manifest 后不再调用服务端翻译覆盖精翻。

## 环境

- Python >=3.10；本机可用 `/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/python3`。
- 默认 720p；下载使用 `--cookies-browser chrome`。先运行 `scripts/check_env.py`，下载由 `scripts/download.py` 负责。
- ASR、视频简介和章节可用于术语纠错；不用 YouTube 机器翻译。
- 本地脚本以本 skill 所在目录为准，不使用已消失的 backup 目录。

## 用于 BiliMix 多人物配音：先拿人物分析

调用同级 `nows-ytb-bmxtask/scripts/bmx_video_task.py --video <MP4> --analyze-only`。它上传一次并等待异步人物分析，写入视频目录 `analysis.json` 和 `analysis_state.json`；后续提交会复用上传路径。

```bash
python3 <skill>/scripts/import_analysis.py <工作目录>/analysis.json --workdir <工作目录>
python3 <skill>/scripts/refine_srt.py prepare-full <工作目录>/transcript_official.srt <工作目录>/raw_aligned.srt --workdir <工作目录>
```

原始 YouTube ASR 保留供内容核对；配音流程使用后端带词级定位和全片人物身份的 canonical 源行。`>>` 只表示可能换人，不能当作 A/B 的声纹识别。人物未解析或参考不足要报告具体原因，不能借另一人的声线。

检查 `speaker_verification_summary` 和词级 `speaker_verified`。未通过声纹复核的词沿用原生标签，不能把它们描述为人工确认或百分之百正确；交付时列出涉及的源时间和话语，尤其是短答、插话、片尾多人致谢。不得凭问题/回答的语义改写人物标签。这些词不进入克隆参考池。

## FULL 语义整理：必须保留

阅读 `references/refine_prompt_full.md`。模型逐块写 `refine_parts/refined_NN.txt`，格式 `S<seq>	<完整英文话语>`，每块独立连续编号。

- 源词与顺序完全保留（uh/um/重复词也保留），只改标点；真正 ASR 纠错留给翻译。
- 以完整话语为先，5–16 词只是建议；不要为凑词数截断未完成表达。
- 同人相邻源行可以合并；遵守分块头的 speaker/turn 信息，禁止跨人物合成一段。自然短答保持独立，不与另一人合并。
- 不输出时间戳；脚本使用真实词级定位，保存人物与来源所有权。

```bash
python3 <skill>/scripts/check_refined.py --workdir <工作目录> --mode full
python3 <skill>/scripts/refine_srt.py apply --workdir <工作目录>
```

缺块、词序漂移、跨人合句均不可继续。修复对应模型输出后重检，不机械补词掩盖漂移。

## 精翻

```bash
python3 <skill>/scripts/split_translation.py <工作目录>/transcript_refined.srt --lines-per-part 70 --out <工作目录>
```

阅读 `references/translation_prompt.md`，按块写 `parts/trans_NN.txt`：`idx	start	end	修正英文	中文`。保留 idx/工作时间戳/行数，先逐行建立可靠来源；翻译自然口语，术语统一，删除舞台指示和章节泄漏。不为了原时间窗删内容或强行压语速。

```bash
python3 <skill>/scripts/verify_translation.py --workdir <工作目录>
python3 <skill>/scripts/assemble_final.py --workdir <工作目录>
```

ASS Name 继承人物。这个 ASS 是精翻工作产物；最终交付 ASS 由 BiliMix 按实际配音时间重建。`reanchor_timestamps.py` 只能修工作翻译的源时间，不能改最终交付时间轴。

## 中文完整话语组装：配音前必做

```bash
python3 <skill>/scripts/build_dub_manifest.py prepare --workdir <工作目录>
```

通读生成的 `dub_unit_input.json`，模型写 `dub_units_plan.json`：

```json
{"units":[{"source_indices":[1,2],"text_en":"corrected full English","text_zh":"精翻后完整自然的一句话。","boundary_after":"sentence_end","captions":[{"text_en":"...","text_zh":"精翻后完整自然的一句话。"}]}]}
```

- source_indices 按原序完整覆盖全部输入各一次，只合并同人相邻行；不得把 A→B→A 重排。
- 中文可按语义自然重写，不能只把残句用空格拼接；不漏语义、不增加原文没有的信息。
- 一条 unit 是一次 TTS。显示需要多条 captions 时，中文连接必须恰好等于 text_zh；只影响显示，不产生新声音或额外停顿。
- boundary_after 可用 continuation/sentence_end/turn_end；以真实话语关系判断。
- 超出引擎长度时在自然从句边界拆分，不能无限长整段合成。

```bash
python3 <skill>/scripts/build_dub_manifest.py apply --workdir <工作目录>
```

输出 `dub_manifest.json`，包含源媒体哈希、analysis ID、每句人物和源词 ID。由提交脚本送给 BiliMix，不手填或伪造人物/参考质量。

## 只生成字幕

不做配音时仍可从 YouTube 官方 ASR 经 `aggregate_srt.py` → FULL → 精翻 → assemble。缺少音频人物分析的路径只交字幕，不宣称多人物声线已验证。滚动 ASR 的时间单调/格式校验仍需执行。

## 交付

返回 MP4、精翻工作 ASS、dub_manifest。配音完成后返回服务端最终视频和配音时间轴 ASS。明确合成/参考不足等错误，不把缺失台词当成功。
