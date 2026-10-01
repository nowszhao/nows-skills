# bmx 命令参考（BiliMix CLI）

本机路径：`/Users/changhozhao/.workbuddy/binaries/python/envs/default/bin/bmx`
（`command -v bmx` 可确认；也支持 `$BILIMIX_SERVER` 指定服务地址。）

通用选项：`--pretty`（美化 JSON）、`-q`（抑制提示，脚本里建议加）、
`--field <嵌套字段>`（**直接提取字段值**，脚本里比解析 JSON 稳，例如
`bmx -q audio upload x.ass --field local_path` 只输出路径字符串）。

## 脚本化调用的两个坑

1. **`--field` 只输出裸值**（如 `239`），不是 JSON。用 Python 封装时，返回值是
   `(json_obj, field_value)` 二元组——**用 `--field` 时要取第二个元素**。
   曾经在这里取错成第一个（恒为 `None`），导致校验恒定失败、误以为服务端有问题。
2. **上传后立刻 parse 可能瞬时失败**（返回空）。`bmx_video_task.py` 内置 3 次重试。
   脚本里建议统一加 `-q`，避免提示信息混进 stdout 干扰解析。

## 认证

```bash
bmx auth status    # {"auth_enabled": false, "authenticated": true} 即可用
bmx auth login     # 未登录时先跑这个
```

服务端可能不开启鉴权（`auth_enabled: false`），此时 `authenticated` 恒为 true。

## 上传（视频和字幕用同一个命令）

```bash
bmx audio upload "<file>" --field local_path
```

- 接受 `.mp4` 和 `.ass`/`.srt`，*没有* 单独的 video upload 子命令。
- 返回：
  ```json
  {"filename": "...", "local_path": "/root/BiliMix/data/downloads/<name>", "ok": true, "size_mb": 125.4}
  ```
- 实测：125 MB 的 MP4 上传约 30 秒；0.1 MB 的 ASS 秒传；49 MB 约 15 秒。
- **文件名已存在时服务端会自动追加 `_<timestamp>` 后缀**（如 `...Arize AI_1790864179.ass`）。
  后续 `subtitle parse` / `task submit` 一律用 upload 返回的 `local_path`，**不要自己拼路径**。

## 字幕校验（提交前必做）

```bash
bmx subtitle parse "<服务端 ass 路径>" --pretty
bmx subtitle parse "<服务端 ass 路径>" --field bilingual_count
```

返回 `count`（总行数）与 `bilingual_count`（识别为 `EN || ZH` 的行数）。
**两者必须相等且非 0**，否则服务端会退化成「重新转录 + 重新翻译」，白做一遍。
不相等时检查每行是否都用 ` || `（空格-竖线-竖线-空格）分隔。

## 提交视频任务

```bash
bmx task submit \
  --type video \
  --server-path "<mp4 服务端路径>" \
  --subtitle-path "<ass 服务端路径>" \
  --subtitle-mode bilingual \
  --title "<标题>" \
  --duration 1894
```

关键参数语义：

| 参数 | 说明 |
| --- | --- |
| `--type video` | 必须显式指定，默认是 `audio` |
| `--server-path` | 服务端**绝对路径**（upload 返回的 `local_path`） |
| `--video-url` | 直接给 YouTube URL，让服务端自己下（本机已能下载时不必用） |
| `--subtitle-path` | 外部双语 ASS；**提供后服务端跳过转录和翻译，直接拿字幕配音** |
| `--subtitle-mode` | `bilingual` / `chinese_only` / `none`，默认 `bilingual` |
| `--subtitle-font-size` | 默认 20 |
| `--duration` | 预知时长，`1894` 或 `01:23:45`，可选但建议给 |
| `--keep-bgm` | **保留原视频背景音乐。不加 = 关闭 BGM（默认行为）** |
| `--skip-confirm` | 跳过人工确认，是默认行为；`--no-skip-confirm` 才要人工确认 |
| `--wait` | 提交后阻塞等待完成（长视频不推荐，用 `task wait` 分开跑） |

**背景音乐**：语义是「默认去除」。用户说「背景音乐默认关闭」时，什么都不用加。

返回：`{"message": "任务已提交", "task_id": "<32位hex>"}`。

**没有任务去重**：同一对文件提交两次 = 两个任务。重跑前先 `bmx task list --limit 10` 看一眼。
建议流程：先 `bmx_video_task.py --no-submit` 预检，通过后再正式提交。

## 跟踪与下载

```bash
bmx task status <task_id>              # {"status":"queued","step":"download","progress":0,...}
bmx task wait <task_id>                # 阻塞轮询直到完成
bmx task result <task_id>              # 完整结果 JSON
bmx task list --limit 10               # 最近任务
bmx video download --task-id <task_id> -o out_dubbed.mp4
bmx video download --path <basename/basename_dubbed.mp4> -o out.mp4
bmx task cancel <task_id>              # 终止
bmx task delete <task_id>              # 删除任务及其文件
```

`status` 取值观察：`queued`（step=download）→ 后续 TTS 合成阶段。31 分钟视频的
TTS 合成通常需要较长时间，**提交后不要把用户挂在这里等**，先回报 task_id。

## 其他可用子命令（本流程未用，备忘）

`audio download` / `audio url`、`translate`、`podcast`、`favorites`、`subscriptions`、
`episodes`、`history`、`recent`、`config`、`api`（API 元信息）、
`file download`（下载目录里的文件）、`task confirm-sentences` / `retry` /
`retry-synthesis` / `reorder` / `redo`（断点续传与重做）。
