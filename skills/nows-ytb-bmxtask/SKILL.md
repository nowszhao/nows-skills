---
name: nows-ytb-bmxtask
description: Download a YouTube video, refine bilingual subtitles with nows-ytb-bilingualex, analyze source speakers and submit audio-first BiliMix dubbing with complete Chinese utterances and stable per-speaker reference voices.
metadata:
  agent_created: "true"
---

# YouTube 精翻 → 稳定人物声线 → BiliMix（音频优先 v1）

保留 FULL 语义重组和精翻。完整中文话语自然播放优先，画面按配音时长反向变速；显示字幕分行不能成为 TTS 断点。

翻译与中文话语重组由本地精翻 skill 的模型执行；服务端只接收精翻产物进行分析、配音和音画合成，不调用服务端翻译覆盖这些产物。

## 工具

本机 Python >=3.10：`/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/python3`。
`bmx`：`/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/bmx`。
配套精翻 skill：同级 `nows-ytb-bilingualex`；使用当前目录，不引用 backup。

默认720p、BGM关闭、字幕字号40。只有用户指定时覆盖画质。标题搜索结果不明确时才确认视频，不额外询问默认画质。

## 流程

1. 用 sibling skill 的 check_env/download 下载 MP4。Chrome cookies 必须传递；读取 metadata/chapters/description，整理术语。检查确有台词，纯音乐/噪声不提交配音。
2. 预分析（只上传视频，尚不提交配音）：

```bash
python3 <skill>/scripts/bmx_video_task.py --video <MP4> --analyze-only
```

服务端须支持 `bmx api --field dubbing_protocol` 返回1，CLI支持 `bmx video analyze`。分析为异步排队任务；耗时较长时用后台执行并给出任务进展。输出视频目录 analysis.json/analysis_state.json；不要重复提交同一分析。

3. 执行 sibling skill 的音频优先流程：import_analysis → FULL语义整理（词级人物边界）→ 精翻 → 中文完整话语组装 → dub_manifest.json。必须阅读 sibling SKILL.md 和翻译提示词。
4. 预检精翻 ASS/manifest 后提交：

```bash
python3 <skill>/scripts/bmx_video_task.py --video <MP4> --subtitle <精翻ASS> --dub-manifest <dub_manifest.json> --ref-select-mode speaker_global
```

提交复用 analysis_state.json 的视频服务端路径。manifest 的媒体哈希与本地 MP4必须相同；人物身份来自分析，A 的所有话语使用 A 的合格参考，B同理，短答也不借别人的声线。只改 ASS Name 不等于声纹验证。

5. 返回task_id并跟踪 status/result，完成后下载最终视频与服务端生成的ASS。中文音频使用自然语速，源ASS时长不是硬限制。

## 重要边界

- FULL和精翻不可省略。同一人跨机械字幕行合并是预期行为；真实换人不得合成单个单声线请求。
- 参考不足/人物不明/配音缺失是明确失败，不能默默换人或漏句。
- `segment`只用于排错对照，正常配音用已验证人物参考池和speaker_global。
- `--no-submit`仍会上传和校验；`--dry-run`不执行网络动作。
- 服务端配音任务不去重。重跑前查看task list，已有任务用retry或wait；不能无边界反复提交。
- 修改参考后重试必须重新校验内容哈希，不依赖旧索引或同路径缓存。
- 工作ASS用于精翻来源，最终ASS必须对应配音后的时间轴。不要把工作时间戳重锚到最终交付文件。

命令与排错细节见 references/bmx_reference.md。旧 pipeline_notes 仅供历史故障参考，不能覆盖音频优先 v1流程。
