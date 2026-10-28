---
name: nows-ytb-dubbing
description: 为 YouTube 或本地英文视频制作精翻双语字幕及中文配音。当前 Code Agent 完成 FULL 断句、人物上下文推断和中文精翻，BiliMix 完成人物声纹分析、参考音频选择、TTS、混音和画面变速；支持只生成字幕。
---

# 视频精翻与中文配音

主流程：**视频 → 人物分析 → FULL 完整断句 → 中文精翻 → 人物上下文推断 → 服务端配音 → 交付**。

翻译和人物上下文推断使用当前 Agent 的模型；BiliMix 负责声纹分析、参考音频选择、TTS、混音和画面变速。需要能读写文件、执行 Python 3.10+ 命令的 Agent。客户端不需要模型或 Hugging Face token。

## 开始

每个视频一个工作目录。`<skill>` 是本次实际安装目录，`python` 是本次选定解释器。先选用现有可用环境；缺 SDK/下载工具时执行一次 `setup`，依赖只安装到工作目录 `.tools`：

```text
python <skill>/scripts/workflow.py setup --workdir <工作目录>
python <skill>/scripts/workflow.py run --input <YouTube网址或本地视频> --server <BiliMix地址> --workdir <工作目录>
```

已有 SDK 和工具可直接 `run`。服务器来自用户配置、环境变量或 SDK 配置，不猜 IP。需要登录时阅读 [连接与恢复](references/operations.md#connection)。默认 720p、关闭背景混音、字幕字号 40，可在首次 `run` 时覆盖。

默认 `--tts-reference-mode speaker`，同一人物使用固定优质参考。用户选择分段复刻时，首次 `run` 传 `--tts-reference-mode segment`：按精翻完整配音句选择对应原声，尽量保留语气和节奏；太短、重叠或不合格参考回退同一人物固定参考，任务结果 `tts_reference_manifest` 记录实际选择。模式随项目保存，重试沿用；客户端和服务端均需支持此选项。

分析和配音任务名称均使用 YouTube 原始视频标题；本地视频使用文件名（去扩展名）。内部项目 ID 不放进显示名称。

## 按返回结果推进

后续只需重复：`python <skill>/scripts/workflow.py run --workdir <工作目录>`。

| 返回 stage | 当前 Agent 的下一步 |
|---|---|
| `full` | 阅读 [FULL 规则](references/language.md#full) 和返回的 input，写入指定 output |
| `translate` | 阅读 [精翻规则](references/language.md#translate)，直接产出完整中文配音话语 |
| `analysis_waiting` / `dubbing_waiting` | 告知当前阶段，适当间隔后继续同一项目；不要新建任务 |
| `speaker_infer` | 读[人物上下文推断](references/speakers.md)，按字幕上下文判断声纹未定的话语，写入指定 output 后重跑同一入口；`mode=forced` 必须逐条给出结论 |
| `reference_missing` | 报告缺少合格同人参考；停止配音，不能借其他声线 |
| `analysis_not_ready` | 报告质量摘要，按[恢复说明](references/operations.md#recovery)核对分析任务，不要靠重复推断绕过 |
| `submission_unknown` / `*_failed` / `error` | 按[恢复说明](references/operations.md#recovery)处理原任务 |
| `completed` | 交付返回的 artifacts |

脚本负责下载、上传、校验、时间继承、ASS/manifest 生成、任务记录与结果下载。不要手工拼这些步骤，也不直接调用服务端翻译。脚本本身不会调用 Agent 模型；`agent_write` / `agent_infer` 需要你完成语言或人物判断后再继续。

## 必须保留的质量约束

- FULL 全量处理，保留源词与顺序，只调整标点及话语边界；ASR 纠错在精翻中完成。
- 同一人物的相邻内容可组成完整话语；真实换人和待确认片段必须分开。分块大小不决定断句。
- 精翻直接写完整、自然、口语化中文，不为原时间窗删内容或加速。保持全片术语一致。
- 声纹未定的话语由模型按上下文判断并写明依据与置信度；候选人顺序、声学分数和相邻同人不能代替证据。没有人工听审环节，`forced` 轮必须给出最可能的结论并标低置信。
- 上下文推断与声纹复核分开记录；不把推断说成声学验证。
- 一个完整中文话语一次 TTS；显示字幕独立分页，每种语言最多两行、合计四行、高度预算 25%。
- 音频优先，视频适配音频。工作 ASS 用于导入，成片须使用服务端返回的最终字幕。

## 交付与其他模式

正常交付 `output/dubbed.mp4`、`dubbed.mp3`、`dubbed.ass` 和实际参考选择报告 `tts_references.json`；工作 ASS 和 manifest 保存在同目录供审校。人物绑定情况按 `output/speaker_inference.json`（上下文推断，含依据、置信度与低置信清单）和 quality 摘要说明：哪些片段只得上下文推断、哪些是低置信、哪些只完成声纹复核，都要点明，不把人物绑定描述成百分之百准确。根据返回的 `tts_reference_quality` 报告真实逐段参考数量及回退数量，打开 segment 模式不等于每句都逐段复刻。

只生成字幕时，在新项目首次运行中指定 `--mode subtitles`，按[纯字幕说明](references/subtitles.md)执行；该模式不连接 BiliMix。状态查询 `workflow.py status --workdir <工作目录>` 只读取本地项目。

`project.json` 管进度，`analysis.json` 保存源分析，`language/` 保存两步语言结果与 `language/speaker/` 人物推断请求，`output/` 保存交付与 `speaker_inference.json` 人物推断记录。来源 ID 和时间由程序维护，不删改词来绕过校验，不在 Skill 或项目中保存密码、Token 或会话。
