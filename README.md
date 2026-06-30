# nows-skills

一个用来存放 **Nows 自定义 Skills** 的仓库。

## 安装

先拉取仓库：

```bash
git clone https://github.com/changhozhao/nows-skills.git
cd nows-skills
```

把需要的 skill 目录复制到你的本地 skills 目录里，例如：

```bash
mkdir -p ~/.workbuddy/skills
cp -R skills/nows-tech101 ~/.workbuddy/skills/
cp -R skills/nows-tech-research-deck ~/.workbuddy/skills/
cp -R skills/nows-hunzige-perspective ~/.workbuddy/skills/
cp -R skills/nows-llm-wiki ~/.workbuddy/skills/
cp -R skills/nows-iplus-reading ~/.workbuddy/skills/
cp -R skills/nows-content-distill ~/.workbuddy/skills/
cp -R skills/nows-article-anlyze ~/.workbuddy/skills/
cp -R skills/nows-podcast-publish ~/.workbuddy/skills/
```

如果你使用的是 `~/.claude/skills/`，把目标目录替换一下就行。

### 额外依赖

- `nows-tech101`：如果需要把 Markdown 转成 PDF，再安装：

```bash
pip install weasyprint markdown --break-system-packages
```

- `nows-tech-research-deck`：渲染能力已内置，无需再额外安装 PPT skill。

- `nows-content-distill`：可选装抓取依赖：

```bash
pip install youtube-transcript-api yt-dlp trafilatura readability-lxml
```

不装也能跑（文章走 r.jina.ai 兜底；YouTube 抓不到时会直接停下来让用户提供转录）。

- `nows-podcast-publish`：需要安装以下工具：

```bash
# bmx CLI（音频处理）
pip install git+https://github.com/nowszhao/BiliMix.git#subdirectory=sdk

# agent-browser（浏览器自动化）
npm install -g agent-browser
agent-browser install
```

## 技能使用说明

| 技能 | 是干啥的 | 适合什么时候用 | 默认产出 | 你可以怎么说 |
|---|---|---|---|---|
| `nows-tech101` | 生成某个技术的入门教程 | 想快速了解一个框架、协议、工具、语言特性时 | Markdown 教程 | `帮我写一份 Redis 的 101 教程`<br>`我想快速入门 gRPC，给我整一份 Tech101`<br>`React 是什么，帮我从零讲清楚` |
| `nows-tech-research-deck` | 调研一个技术产品，并生成演示稿 | 要做技术分享、内部汇报、竞品对比时 | `<product>-research.md` 和 `<product>-deck.html` | `帮我调研 dbt 并生成 PPT`<br>`深度调研 Dagster，做一份技术分享 slides`<br>`research Snowflake and make a deck` |
| `nows-hunzige-perspective` | 混子哥（陈磊）的思维框架与表达方式，作为思维顾问分析知识传播、产品设计、内容创作问题 | 需要用混子哥的视角分析问题时 | 基于混子哥思维框架的分析和回答 | `用混子哥的视角看看这个问题`<br>`混子哥会怎么看`<br>`切换到混子哥模式` |
| `nows-llm-wiki` | 把现有 Obsidian vault 重组为 `PARA + LLM Wiki` 混合知识库 | 想整理 Obsidian 笔记库、重构目录、补 frontmatter、生成 MOC / 概念页 / 索引页时 | 重组方案、迁移计划、wiki 页面与索引 | `帮我整理一下我的 Obsidian vault`<br>`把我的 vault 按 PARA + LLM Wiki 方式重组`<br>`给我的 vault 生成 MOC / 索引 / 概念页` |
| `nows-iplus-reading` | 基于克拉申 i+1 假设，通过逻辑推理式问答定位认知边界，推荐"刚好能吸收的下一步"精读路径（精确到小节） | 想精读一本书但不知从哪读起、想跳过已懂部分、想系统入门某个领域时 | 诊断结论 + 小节级 i+1 精读 / 略读 / 暂不学习清单 | `帮我精读《思考，快与慢》`<br>`我想搞懂行为经济学，从哪开始`<br>`帮我设计 i+1 阅读路径` |
| `nows-content-distill` | 把一篇文章/一个 YouTube 视频压成"刻进脑子的心理表征"——核心概念、金字塔行文逻辑、差异化亮点、金句锚点、≤500 字最简复述 | 看完一篇/一个视频，想沉淀成自己能复述、能联想、能调用的内化卡片时 | `<slug>-distill.md` 与单文件 `<slug>-distill.html`（笔记风、零依赖、深色模式、打印友好） | `帮我把这篇文章 distill 一下：<URL>`<br>`刻印一下这个 YouTube 视频`<br>`压一下这篇，我想留下心理表征` |
| `nows-article-anlyze` | 把深度文章 / 行业研报 / 产品发布 Keynote 拆成「概念库 + 金字塔 + 可点击流程图 + 原文映射」的可交互单文件 HTML，发布会类还附战略动因卡片、竞争定位矩阵、行业趋势预测 | 想结构化解析一篇长文 / 报告 / 发布会实录，做成可视化、可溯源、可离线分享的工作台时 | 单文件 HTML（深蓝商务质感、零依赖、流程图节点跳转原文锚点） | `帮我把这篇研报拆解成可视化 HTML`<br>`把这场 Keynote 解构成战略 + 竞争分析`<br>`把这篇商业文章做成可点击溯源的卡片` |
| `nows-podcast-publish` | 将音频一键发布到小宇宙播客平台：bmx CLI 处理音频 → YouTube 溯源获取封面 → AI 生成标题/介绍/章节 → 浏览器自动化上传发布 | 有音频文件需要发布到小宇宙播客、需要全流程自动化处理时 | bmx 已处理音频 + YouTube 来源映射 + 小宇宙平台已发布单集 | `帮我把这期播客发布到小宇宙`<br>`上传音频到小宇宙`<br>`发布 nows podcast` |


## 建议

第一次使用时，先看对应目录下的 `SKILL.md`，再直接用自然语言触发就够了。