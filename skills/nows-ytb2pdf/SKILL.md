---
name: nows-ytb2pdf
description: 把 YouTube 视频或本地视频中出现过的每一张不同页面/幻灯片自动截图，按播放顺序导出为「一页一张、完整不裁切」的 PDF，并生成全量核对表与机器可核验的覆盖/去重数据。通过逐帧差异检测硬切、掩膜叠加层、稳定段取代表帧、跨段相似度去重，保证不遗漏、不重复。当用户说「把视频里的 PPT/页面导成 PDF」「视频截图合成 PDF」「slides to PDF」「ytb2pdf」「每一页都要有、不要重复」，或给出 YouTube 链接并要求提取幻灯片/截图时使用；也适用于本地录屏、演讲、网课视频。
agent_created: true
version: "1.0.0"
---

# nows-ytb2pdf · 视频页面 → PDF

## 目标

把「视频里出现过的每一张静态页面」变成 PDF 的一页。这里的**页面**指一张幻灯片/文档页/界面页，不是每一帧，也不是镜头。

必须同时满足三条：

1. **不遗漏**——视频中出现过的每张不同页面都在 PDF 里；
2. **不重复**——同一张页面只出现一次（含重复回放、渐进动画、转场中间帧）；
3. **每页完整**——一页对应整张视频画面，不裁切、不拼接、不缩放掉边角，且按播放顺序排列。

默认**保留视频原貌**（章节进度条、右下角演讲者摄像头画中画都属于视频画面）。掩膜只作用于「是否算新页面」的判断，不改变输出图像。用户明确要求「干净幻灯片」时再另行裁剪，不要擅自裁。

## 交付物

| 文件 | 作用 |
|---|---|
| `<标题>_slides.pdf` | 主交付，一页一张全分辨率截图，页面比例跟随源视频（默认 960pt 宽） |
| `页面核对表.html` | 自包含（缩略图内嵌）逐页核对表：页码、时间点、停留时长，可点开原图 |
| `pages_full/pNNN.jpg` | 每张页面的全分辨率原图 |
| `report.json` | 覆盖/去重的机器证据：切换事件、每段稳定性、空白页与重复页处置、PDF 自检结果 |

## 何时使用

- 静态幻灯片录屏、大会演讲、网课讲义、产品演示、文档翻页视频。
- 用户强调「所有页面都要」「不要重复」「一页一张」。
- 输入是 YouTube/其他 yt-dlp 支持的 URL，或本地视频文件。

不适用：需要 OCR 文字或逐页讲解（本 skill 只出截图）；纯动态实拍视频（会产生大量无意义「页面」，先提醒用户并建议限定时间段或改用关键帧方案）。

## 环境依赖

```bash
python3 -m pip install pillow numpy img2pdf pymupdf
python3 -m pip install -U yt-dlp      # 仅 URL 模式
brew install ffmpeg                    # 需 ffmpeg / ffprobe
```

`pymupdf` 只用于 PDF 自检，缺失时脚本会跳过并在 `report.json` 标注。脚本缺依赖时会打印安装命令并退出。

## 快速开始

```bash
SK=~/.workbuddy/skills/nows-ytb2pdf/scripts/ytb2pdf.py

# 标准用法：一条命令跑完下载 → 分析 → 去重 → PDF → 核对表
python3 "$SK" "https://www.youtube.com/watch?v=VIDEO_ID"

# 已有本地视频（永不修改源文件）
python3 "$SK" --video /path/to/talk.mp4 --out-dir ./out

# 调参阶段：只分析并写 report.json，不抽图不生成 PDF
python3 "$SK" "URL" --dry-run
```

在 skill 仓库内开发时，把 `$SK` 换成 `skills/nows-ytb2pdf/scripts/ytb2pdf.py`。

## 工作流

1. **取源。** URL 模式只下载画面轨（默认 ≤1080p，不需要音频），用浏览器 cookies 依次尝试 `chrome → edge → firefox → brave → safari`，全部失败再试无 cookies 的替代客户端；把失败原因完整报给用户，不要假装下载成功。
2. **抽帧 + 掩膜。** 以 2 fps 流式抽取 320×180 灰度帧到内存，屏蔽顶部章节栏（默认 16 行）、右下角摄像头画中画（默认 x≥0.86, y≥0.76）；有烧录字幕时加 `--mask-bottom-px`。掩膜区域只影响相似度计算。
3. **切段。** 计算掩膜后相邻帧平均绝对差（MAD），超过 `--switch-threshold`（默认 1.0）判为硬切；3 帧内的连续事件合并为一次切换（转场余波）；每段取时间中位帧作代表帧，避开转场帧。
4. **去重 + 过滤。** 剔除近乎纯色的空白/黑屏页（对比度 < 2），把与已保留页面全尺寸 MAD < 3.0 的页面合并（保留首次出现），并计算全片最相似页面距离作为「无重复」证据。段内中段出现大幅变化时写入 `warnings`，提示人工复核。
5. **导出。** 按代表帧时间点从原视频抽全分辨率静帧，用无损 JPEG 嵌入方式生成 PDF（不重新压缩、不裁切），页面比例随源视频；再生成 HTML 核对表。
6. **核验再交付。** 读取 `report.json`，确认 `verification.page_count_matches == true`、`warnings` 为空、页数与用户预期量级相符；用 HTML 核对表目视抽检首尾页与疑似重复页。通过后再调用文件呈现，并在回复中报告页数、切换数、剔除/合并数、最相似页面距离。

## 质量红线

- **禁止按固定时间间隔抽帧**（必然漏页且重复），也禁止直接把场景检测出的每一帧都塞进 PDF。必须以画面稳定段为单位。
- **不遗漏的判据**：`switch_events + 1 == segments_total`，且 `segments_total == final_pages + 空白页数 + 重复页数`；段内 `internal_suspicious` 全为 false。数值对不上时先查参数，不要直接交付。
- **不重复的判据**：`min_coarse_pair_distance` 应显著大于 `--dup-threshold`；接近阈值时从 HTML 核对表目视比对那一对页面。
- **每页完整**：检查 `verification.first_page_image_px` 与源视频分辨率一致；PDF 页面比例与源一致。
- `warnings` 非空或 `verification.checked == false` 时，人工抽帧复核并在回复里如实说明，不得静默略过。
- `--max-seconds` 仅供调试，正式交付禁用（会破坏「不遗漏」）。
- 未确认视频类型前不要假设一定是 16:9；脚本按源比例自动决定 PDF 页面尺寸。

## 常用参数

| 参数 | 默认 | 用途 |
|---|---|---|
| `--video PATH` | — | 使用本地视频，跳过下载 |
| `--out-dir DIR` | `./ytb2pdf-<id>` | 输出目录 |
| `--browser LIST` | `chrome` | cookies 浏览器，逗号分隔，失败自动回退其余浏览器 |
| `--fps` | `2` | 分析抽帧率；长视频内存吃紧时降为 1 |
| `--switch-threshold` | `1.0` | 硬切判定的掩膜 MAD 阈值 |
| `--dup-threshold` | `3.0` | 页面合并阈值（调大易误合并模板相似的页） |
| `--mask-top-px` / `--pip-x` / `--pip-y` | `16` / `0.86` / `0.76` | 叠加层掩膜，设 0 或 `--no-mask` 关闭 |
| `--mask-bottom-px` | `0` | 有烧录字幕时设 20～30 |
| `--page-size` | `auto` | `auto`（960pt 宽、源比例）或 `960x540` 等 pt 尺寸 |
| `--keep-blank` | 关 | 保留空白/黑屏页 |
| `--keep-video` | 关 | 保留下载的视频文件 |
| `--dry-run` | 关 | 只分析、写报告 |

完整阈值依据、画面类型适配表、反爬排错与实战基准见 `references/method-and-tuning.md`，遇到非标准视频或参数拿不准时先读它。

## 交付回复

报告清楚：源视频标题与时长、检测到的切换次数、最终页数、剔除的空白页与合并的重复页数、最相似页面距离、PDF 自检结果、是否有待复核警告；点明 PDF 每页是完整原画面（默认含摄像头等叠加层），并给出 PDF 与核对表路径。
