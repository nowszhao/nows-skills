# 故障排查

只在对应步骤失败时读取本文件。

## YouTube 探测或下载失败

- 优先使用 Chrome cookies、`player_client=mweb`、可续传的 yt-dlp 原生分片下载。
- 日志出现 `n challenge solving failed` 或格式只剩 `sb0-sb3` 时，在 yt-dlp 环境安装 `yt-dlp-ejs`，并确保 `deno` 位于 PATH。
- ASR 提示缺少 PO token 时，可对字幕获取单独尝试 `player_client=web_embedded`。
- 会员或年龄受限视频不得在未确认授权状态前去掉 cookies。
- 下载完成后用 ffprobe 同时检查 codec、分辨率和时长；时长至少达到元数据的 95%。

## FULL 边界输出失败

- `refined_NN.txt` 只能包含 `W<编号>\t<.?!>`。
- 编号必须位于该文件头部的 `Commit range`，严格递增。
- 覆盖整部视频最后一个词的块必须输出最后词编号。
- 只重派失败块，不重跑全片。

## 翻译校验失败

- 新格式为 `idx\tEN\tZH`，没有时间戳；旧五字段格式仍可组装，但不应继续生成。
- `verify_translation.py` 报内容偏移时，只重派对应块。不要手工整体移动未知范围。
- 组装脚本按 idx 注入权威时间戳，因此无需让翻译 Agent 修复或复制时间码。

## 收尾 QA

- 运行 `assemble_final.py` 后执行 `step55_derive_srt.py`。
- 必须满足：中英分隔符完整、方括号舞台指示为 0、中文非空、ASS/SRT 行数一致、时间码合法、人称不混用。
