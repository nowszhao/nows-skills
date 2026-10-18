---
name: nows-ainews-daily
description: 扫描 AI 频道观察名单（164 个精选频道）近 24 小时的视频，用两层判断（频道画像 + 视频语义判断）筛出真正值得看的，生成带推荐理由和可一键复制链接的 HTML 日报。当用户说「今日 AI 视频日报」「YouTube AI 新闻」「抓一下订阅里的 AI 视频」「AI 视频推荐」「AI 日报」时使用。
---

# YouTube AI 视频日报

从一份**精选的 AI 频道观察名单**里挑出真正值得看的 AI 视频，给出具体到「能拿到什么、怎么看」的推荐理由，产出可点击、可复制链接的 HTML 日报。

> 名单不是「我在 YouTube 上随手订阅的 300 个频道」，而是 2026-10-15 调研产出的 AI 观察名单（164 个），来源见下方「订阅表是怎么来的」。这意味着**召回池本身就是高信噪比的**，不需要靠关键词去一堆英语学习、儿童、加密货币频道里捞 AI 内容。

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
| `subscriptions.tsv` | 观察名单（频道名 \t channel_id），`--refresh-subs` 可刷新 |
| `channel_profiles.tsv` | 频道 AI 相关度画像，**第一层判据** |
| `candidates.json` | 当日候选（含 tier、时长、播放量、命中关键词） |
| `reasons.json` | 你的判断产物：picks + rejected |
| `report-YYYY-MM-DD.html` | 最终日报 |

Skill 自带一份**默认订阅表和频道画像**（`references/`），首次运行时自动复制到工作目录，所以新机器、新目录开箱即用，不需要 Chrome 登录态。

| Skill 内置文件 | 作用 |
|---|---|
| `references/subscriptions.default.tsv` | 默认观察名单（164 个） |
| `references/channel_profiles.default.tsv` | 默认频道 AI 画像（与订阅表一一对应） |
| `references/subscriptions.personal-300.archive.tsv` | 归档：改版前的个人真实订阅（300 个），需要时可回滚 |

## 订阅表是怎么来的

2026-10-15 做了一次系统调研，产出 `youtube-ai-channels-top100.html`（Top 100 + 候补 14），逐个实测链接可达后才落表。当前 164 个的构成：

| 来源 | 数量 | 说明 |
|---|---|---|
| Top 100 榜单 | 100 | 资讯趋势 16 / 学术课程 19 / 编程工程 21 / 工具变现 17 / 中文 14 / 垂直 13 |
| 榜单候补 | 14 | a16z、红杉、Jay Alammar、量子位等，体量小或更新不稳但方向口碑好 |
| 旧订阅保留 | 50 | 原 300 个里 AI 相关度 `core`/`adjacent`/`general` 且不在上面两组的（见下） |

**旧订阅保留下来的 50 个**（原 300 里其余 250 个已剔除）：

- `core` 17 个：Arena AI、Greg Kamradt、Prompt Engineering、No Priors、Unsupervised Learning、The Information Bottleneck、Riley Brown、Visual AI、New Machina、Ontologize、Kyle Chalmers、AI DevOps Podcast、ODSC、靜電的AI研习社、数字黑魔法、暗夜飞行、Artificial Intelligence - All in One
- `adjacent` 23 个：Databricks、Palantir、Cloudera、ThoughtSpot、theCUBE、Google、All-In Podcast、Lenny's Podcast、Tiago Forte、CJ Gammon、Zara Zhang、Lisha的数据科学站、氪學家、所长林超、乱翻书、硅谷坐标、Best Partners TV、程式猿（AFA）、Vanyar、Sandeep Swadia、LE、Figure、Unitree Robotics
- `general` 10 个：ByteByteGo、Dagster、ClickHouse、Palantir Developers、Real Engineering、Marques Brownlee、小Lin说、脑总MrBrain、硅谷大舅、Amazon Web Services

**剔除的约 250 个全是零 AI 价值的**：英语学习（约 30）、儿童动画（约 20）、中文读书/讲书（约 20）、加密货币（约 16）、投资理财、旅行生活、政治脱口秀、宗教、航天科普、泛娱乐等。它们原本在 `none` 档靠「命中 2 个关键词」防漏，实际上一年也贡献不了几条真 AI 视频，却要占掉大半抓取时间。

## 首次初始化

换机器或新目录时，只要跑一次抓取就会自动补齐这两个文件：

```bash
mkdir -p youtube-digest
python3 scripts/fetch_ai_videos.py --dir youtube-digest   # 自动从 references/ 复制订阅表与画像
```

**日常跑不要加 `--refresh-subs`**。原因有两个：一是省一次抓取、不依赖登录态；二是 `--refresh-subs` 会用你在 YouTube 上**真实订阅的频道（目前 300 个，含大量英语学习/儿童/加密货币）整个覆盖**这份精选名单，等于把信噪比打回原形。

只有在你**确实想在 YouTube 上新增订阅后同步过来**时才加，且加完要手工把 `none` 档频道删掉、并补画像。

只有当需要**从零重建频道画像**时（例如接手一个全新的订阅列表）才跑：

```bash
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
python3 scripts/fetch_ai_videos.py --dir youtube-digest --hours 24
```

并发扫各频道 RSS feed（164 个频道约 40 秒）。分层召回：`core`/`adjacent` 全量进候选，`general` 需 ≥1 个关键词，`none` 需 ≥2 个（仅防漏）。每频道每日上限 4 条、`vendor` 限 2 条。脚本会打印候选清单，`tier` 字段是参考，不是结论。

名单里 `core` 有 114 个、`adjacent` 40 个、`general` 10 个、**没有 `none` 档**——所以候选量大概率比改版前更集中，第 2 步的判断要更严格，别因为池子干净就放水。

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

- **改版已有的工作目录要手工同步名单**：`ensure_seeded` 只在 `subscriptions.tsv` / `channel_profiles.tsv` **不存在**时才从 `references/` 复制。改版前建的工作目录（如 300 频道旧表）不会被自动升级，需手动 `cp references/*.default.tsv <dir>/` 并去掉 `.default` 后缀，旧表先留档。
- 脚本输出「未画像频道」说明有新订阅：基于该频道最近视频标题判断定位，追加进 `channel_profiles.tsv`。
- 频道画像是长期资产，判断错了直接改那一行即可。改完记得同步一份到 `references/channel_profiles.default.tsv`，换机器时才能带上。
- **新增/删除频道要同时改两张表**：`subscriptions.default.tsv` 加行，`channel_profiles.default.tsv` 也要加对应 tier，且**频道名必须完全一致**（脚本按规范化后的名字匹配，不一致就命中不了画像、会退化成未画像频道）。
- 需要 channel_id 时，抓频道页取 `youtube.com/channel/UCxxx` 即可：`curl -sL -A "<浏览器 UA>" "https://www.youtube.com/@handle" | grep -o 'youtube.com/channel/UC[A-Za-z0-9_-]\{22\}'`。用不存在的 handle 对照（应返回 404）能验证检测有效。
- 若 `--refresh-subs` 失败（Chrome cookie 不可用），会自动回退到已有 `subscriptions.tsv`，不影响主流程。
- 注意：`references/` 里的订阅表是个人数据，推送到公开仓库前先确认。

## 环境问题

- 拉订阅和取视频元信息需要 Chrome 登录态（`--cookies-from-browser chrome`）。匿名请求会被 YouTube 的 bot-check 拦掉。
- 脚本自动查找 `yt-dlp`（PATH → homebrew → conda）。找不到就先装：`pip install -U yt-dlp`。
- 当前名单没有 `none` 档频道。若以后 `--refresh-subs` 拉回了真实订阅，`none` 档偶尔进候选是正常的（防漏机制），逐条判断时剔掉即可。
