---
name: nows-ainews-daily
description: 扫描 YouTube 订阅频道近 24 小时的 AI 相关视频，用两层判断（频道画像 + 视频语义判断）筛出真正值得看的，生成带推荐理由和可一键复制链接的 HTML 日报。当用户说「今日 AI 视频日报」「YouTube AI 新闻」「抓一下订阅里的 AI 视频」「AI 视频推荐」「AI 日报」时使用。
---

# YouTube AI 视频日报

从用户的 YouTube 订阅里挑出真正值得看的 AI 视频，给出具体到「能拿到什么、怎么看」的推荐理由，产出可点击、可复制链接的 HTML 日报。

## 核心原则：关键词不是判据

筛 AI 相关视频靠两层判断，关键词只做辅助信号：

1. **频道层**：先给每个订阅频道做 AI 相关度画像（`channel_profiles.tsv`），定召回范围。
2. **视频层**：对每条候选做语义判断——结合标题、描述、频道定位，判断「这条到底是不是在讲 AI、有没有价值」。

关键词会导致两类错误，都必须避免：
- **误收**：厂商软文、政治脱口秀、加密货币视频标题里带 AI 字样就被收进来。
- **漏收**：真正讲 AI 的视频标题里没有任何关键词。

## 目录约定

工作目录默认 `./youtube-digest`（可用 `--dir` 指定别处）。所有数据都在里面：

| 文件 | 作用 |
|---|---|
| `subscriptions.tsv` | 订阅频道（频道名 \t channel_id），`--refresh-subs` 可刷新 |
| `channel_profiles.tsv` | 频道 AI 相关度画像，**第一层判据** |
| `candidates.json` | 当日候选（含 tier、时长、播放量、命中关键词） |
| `reasons.json` | 你的判断产物：picks + rejected |
| `report-YYYY-MM-DD.html` | 最终日报 |

## 首次初始化（只需做一次）

```bash
mkdir -p youtube-digest
python3 scripts/fetch_ai_videos.py --dir youtube-digest --refresh-subs --no-enrich
python3 scripts/build_channel_profiles.py --dir youtube-digest   # 产出 channel_samples.json
```

然后**逐个频道做画像**：看 `channel_samples.json` 里的频道名和最近视频标题样本（关键词密度只作参考），判断定位，写入 `channel_profiles.tsv`：

```
# 频道名 <TAB> tier <TAB> 备注
Andrej Karpathy	core
a16z	adjacent
ByteByteGo	general
English with Lucy	none
Lex Fridman	adjacent
Cloudera, Inc.	adjacent	vendor
```

**tier 定义**：
- `core` — AI 主业。模型发布、AI 工程、AI 研究、AI 产品。
- `adjacent` — 非纯 AI 但 AI 高频出现。科技播客、创投、数据工程、具身智能机器人、AI 工具测评。
- `general` — 技术 / 商业类，偶发 AI。系统设计、云厂商、科普、数码评测。
- `none` — 基本无关。英语学习、儿童、加密货币、历史、政治、读书、旅行。

备注写 `vendor` 表示该频道厂商软文偏多（每日限 2 条、排序靠后）。

## 每日流程

**第 1 步：抓候选**

```bash
python3 scripts/fetch_ai_videos.py --dir youtube-digest --hours 24 --refresh-subs
```

并发扫各频道 RSS feed（300 个频道约 1 分钟）。分层召回：`core`/`adjacent` 全量进候选，`general` 需 ≥1 个关键词，`none` 需 ≥2 个（仅防漏）。每频道每日上限 4 条、`vendor` 限 2 条。脚本会打印候选清单，`tier` 字段是参考，不是结论。

**第 2 步：逐条语义判断**（这一步是重点，不能省）

对每条候选判断「值不值得看」，产出三类：

- **picks**（8-18 条）：真 AI 相关且有价值。
- **rejected**：名不副实的，必须写明原因。
- **其余**：真 AI 相关但价值一般 —— 不写进 `reasons.json`，自动归入报告「其他命中」区。

典型该剔除的：
- 厂商采访 / 发布会切片 / 产品发布（标题带 AI，实质是推销）。这一类是最大的噪音源。
- 机器人硬件更新、具身智能演示（与 AI 软件无关）。
- 政治脱口秀、加密货币、泛商业访谈、纯新闻播报。
- 泛谈「AI 改变一切」但没有任何具体信息增量的长视频。

宁可多剔，不要放水。

**第 3 步：写 `reasons.json`**

```json
{
  "date": "2026-10-01",
  "digest": "3-5 句当日综述：点出主线、反常之处，并说明今天剔了多少条、主要是什么类型。不要罗列视频。",
  "picks": [
    {"video_id": "xxx", "priority": "必看", "reason": "...", "tags": ["Agent", "工程落地"]}
  ],
  "rejected": [
    {"video_id": "yyy", "why": "厂商采访（CoreWeave），软文"}
  ]
}
```

`priority`：`必看`（3-5 条）/ `值得看` / `可选`。

**推荐理由写法**（质量红线）：
- 必须写清：这条讲了什么 + 为什么现在值得看 + 建议怎么看（完整看 / 1.5 倍速 / 跳到某段 / 只看结论）。
- 禁止复述标题，禁止「值得一看」「不容错过」这类空话。
- 该下判断就下判断：标题党、软文、信息增量低，直接点出来。
- 同一频道最多精选 3 条。

**第 4 步：渲染**

```bash
python3 scripts/render_report.py --dir youtube-digest
```

生成 `report-YYYY-MM-DD.html`：卡片式、缩略图可点击直达、每条右侧有「复制链接」按钮。

**第 5 步：交付**

用 `present_files` 展示 HTML，并在对话里给摘要：今日主线一句话 + 精选清单（频道 / 标题 / 一句话理由 / 时长）+ 剔除说明。

## 校验归属（可选，出问题或抽查时跑）

`candidates.json` 里的 `channel_id` 取自本地订阅表，属于自证。要独立确认「报告里的视频确实来自用户订阅的频道」：

```bash
python3 scripts/verify_subscriptions.py --dir youtube-digest --all
```

它对每条视频调 yt-dlp 拿 YouTube 侧的真实归属频道再比对，能发现频道改名/合并、订阅表过期、抓错频道等问题。不传 `--all` 只校验 `reasons.json` 里的 picks。

已知的正常告警：`meta_failed`（拿不到元信息）通常是**尚未开始的直播**或**已删除的视频**，不是抓错了频道，报告里会标注而不是显示成假的「0 播放」。

## 维护

- 脚本输出「未画像频道」说明有新订阅：基于该频道最近视频标题判断定位，追加进 `channel_profiles.tsv`。
- 频道画像是长期资产，判断错了直接改那一行即可。
- 若 `--refresh-subs` 失败（Chrome cookie 不可用），会自动回退到已有 `subscriptions.tsv`，不影响主流程。

## 环境问题

- 拉订阅和取视频元信息需要 Chrome 登录态（`--cookies-from-browser chrome`）。匿名请求会被 YouTube 的 bot-check 拦掉。
- 脚本自动查找 `yt-dlp`（PATH → homebrew → conda）。找不到就先装：`pip install -U yt-dlp`。
- `none` 档频道偶尔进候选是正常的（防漏机制），逐条判断时剔掉即可。
