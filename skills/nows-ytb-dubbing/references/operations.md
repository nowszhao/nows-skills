# 连接、人物推断与恢复

## Connection

需要 Python 3.10+。Skill 内置当前轻量 SDK wheel，`workflow.py setup --workdir <目录>` 将 SDK、yt-dlp 和 FFmpeg 工具安装到该项目 `.tools`，不修改系统或 Agent 的 Python。已有环境可跳过 setup。

使用 `python` 时应选定同一解释器，Windows 可用 `py -3`。`.tools` 是本机依赖，换电脑后重新 setup，不把它作为 Skill 内容分发。

服务器优先采用首次 run 的 --server；未指定时遵循 SDK 的 BILIMIX_SERVER、已保存地址及 localhost 默认值。成功连接后绑定项目，不能把另一服务的上传路径、会话或任务 ID 混用。支持显式 BILIMIX_CLI、BILIMIX_YTDLP、BILIMIX_FFMPEG 指定可执行文件，不填特定电脑路径。

需要认证时，使用项目 `.tools/bin/python`（Windows `.tools/Scripts/python.exe`）调用 `-m bilimix_cli --server <URL> auth login --username <用户名> --password <密码>`；已有环境则用其解释器。只使用用户明确提供的账户，避免把实际密码写进共享文件、Skill、项目 JSON 或回复。SDK 会话保存在用户自己的配置目录，按服务器隔离。

首次 run 可指定：--quality 720p/best、--font-size 40、--keep-bgm、--tts-reference-mode speaker/segment、--width/--height，以及用户允许的 --cookies-browser 或 --cookies-file。这些选项固定在该项目中，之后用不带重复配置的 run 恢复。公开视频默认不使用浏览器 cookies；登录下载只在需要且用户允许时使用。

## Speakers

分析任务 completed 表示分析结束；analysis.dubbing_ready 才表示满足克隆前提。speaker=null 是未知人物，speaker_verified=false 可能是已沿用原生标签但没有通过声纹复核，两者不同。

程序允许未知片段独立完成 FULL 和精翻，人物问题集中在合成前处理。声纹没有给出说话人的完整话语全部由模型按上下文判断，没有人工听审环节：

1. run 返回 `speaker_infer` 时读[人物上下文推断](speakers.md)，把决定写入返回的 output，再运行同一入口。
2. 脚本把决定交服务端回填，依据、置信度与低置信清单一并写入 `output/speaker_inference.json`，随后继续配音流程。

`mode` 为 `context` 时可以留未决；同一批片段第二轮以 `forced` 返回，必须逐条判断，所以流程不会停在等人确认的位置。证据弱时用 `confidence: low` 并在 `reason` 写明依据，交付时如实说明，不把推断说成声纹结论。

推断按原词重新绑定人物，不必重译全部。原先一条未知话语推断后涉及多人时，按报错拆分对应 language/refined.json 和 language/units.json 的受影响话语，保持稳定源 ID、原序与完整覆盖。

`reference_missing` 不能靠选人物解决。列出缺少合格参考的具体人物，交由原声质量或模型分析维护处理；不自动重跑大型分析，不借其他人的声音。

`analysis_not_ready` 表示所有词都有说话人和合格参考，但服务端仍未标记可配音：报告质量摘要，按[恢复说明](#recovery)核对分析任务。

外部重新分析后用 `refresh-analysis --workdir <目录>` 更新本地快照；新分析 ID 会让旧的推断记录失效并重新判断。

## Recovery

`status --workdir <目录>` 只读本地项目，不联网。run 每次推进到需要 Agent 或等待服务端的位置，返回 JSON；等待时适当间隔重跑，不紧密轮询。缺参考等阻塞会以明确的 stage 返回。

- 语言错误：修复当前 input 对应的 output 后继续。输入 input_id 要保持一致。
- 服务端失败：先报告 task_id、step/message；有明确重试依据后执行 `retry --kind analysis|dubbing --workdir <目录>`，继续原任务。不会偷偷创建新任务。
- 提交响应丢失：pending_submission 在发送前已保存，包含提交前已有任务 ID。先用 SDK task list 核对视频标题、媒体路径与任务类型，仅在新增任务中存在唯一匹配时执行 `recover --workdir <目录> --task-id <查到的ID>`。找不到或有多个匹配时保持待核查，不能盲目重发。任务显示视频标题，服务端当前不提供提交原子幂等保证。
- 同一项目不能并发执行，两次运行会由本地进程锁互斥。进程崩溃后系统自动释放锁。
- 改成另一视频、另一服务或另一次配音输出，使用新的工作目录；不复用旧媒体路径和回执。

工作目录只保存当前快照和继续任务所需数据，不写操作流水或历史备份。下载完整后才替换交付文件，中断下载不算完成。
