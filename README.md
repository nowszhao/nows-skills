# nows-skills

一个用来存放 **Nows 自定义 Skills** 的仓库。

## 安装

先拉取仓库：

```bash
git clone https://github.com/changhozhao/nows-skills.git
cd nows-skills
```

把需要的 skill 目录复制到你的智能体 skills 目录里，例如：

```bash
# 如果你的智能体 skills 目录在 ~/.skills/
mkdir -p ~/.skills
cp -R skills/nows-tech101 ~/.skills/
cp -R skills/nows-tech-research-deck ~/.skills/
cp -R skills/nows-hunzige-perspective ~/.skills/
cp -R skills/nows-llm-wiki ~/.skills/
cp -R skills/nows-iplus-reading ~/.skills/
cp -R skills/nows-content-distill ~/.skills/
cp -R skills/nows-article-anlyze ~/.skills/
cp -R skills/nows-concept-deptree ~/.skills/
cp -R skills/nows-podcast-publish ~/.skills/
cp -R skills/nows-video-bmxcut ~/.skills/
cp -R skills/nows-industry-insight ~/.skills/
cp -R skills/nows-ytb-bilingualex ~/.skills/
cp -R skills/nows-ytb-vcover ~/.skills/
```

不同智能体的 skills 目录路径不同，请替换为目标路径（如 `~/.workbuddy/skills/`、`~/.claude/skills/` 等）。



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
| `nows-concept-deptree` | 梳理概念的完整前置知识链条，构建从当前水平到目标概念的阶梯学习路径，拆解复杂概念的层级依赖关系 | 想搞清楚「学XX之前需要先会什么」、定位知识断层、生成结构化学习路线时 | 交互式 HTML 报告（dagre 分层拓扑图 + 概念速查表 + 分层详解卡片） | `帮我梳理学大语言模型需要什么前置知识`<br>`从编程基础到 Kubernetes 需要学什么`<br>`拆解 Transformer 的概念层级依赖` |
| `nows-podcast-publish` | 将音频一键发布到小宇宙播客平台：bmx CLI 处理音频 → YouTube 溯源获取封面 → AI 生成标题/介绍/章节 → 浏览器自动化上传发布 | 有音频文件需要发布到小宇宙播客、需要全流程自动化处理时 | bmx 已处理音频 + YouTube 来源映射 + 小宇宙平台已发布单集 | `帮我把这期播客发布到小宇宙`<br>`上传音频到小宇宙`<br>`发布 nows podcast` |
| `nows-screenshot2code` | 把截图、设计稿、UI 图片转换为像素级还原的前端代码，支持 6 种技术栈（html_tailwind / react / vue / bootstrap / ionic），五阶段工作流 + 自检对比循环 | 丢来一张截图 / 设计稿 / UI 图，想要对应的前端代码 / HTML / 页面时 | 单文件自包含 `index.html`（内联 CSS+JS，依赖走 CDN） | `帮我把这张截图还原成 HTML`<br>`screenshot to code`<br>`clone this website`<br>`把这个设计稿转成代码`<br>`一比一还原这个界面` |
| `nows-video-bmxcut` | 将 BiliMix 配音视频通过 ASS 字幕分析智能切分为短视频系列，含标题、简介、标签、推荐指数 | 播客/课程/访谈等长视频需要切成独立短视频分发时 | Markdown 切片方案 + 可选 FFmpeg 切割视频文件 | `帮我把这个视频做切片`<br>`这期播客帮我切短视频`<br>`bmxcut 这个视频` |
| `nows-industry-insight` | 基于《如何快速了解一个行业》方法论，以渗透率判定产业生命周期阶段，按阶段动态分配七大维度（可行性/规模/护城河/盈利/估值/PEST/景气度）分析权重 | 想快速了解一个行业、做投资研究、择业决策、创业评估、建立行业认知时 | 分层级 Markdown 研究报告（快速版/标准版/深度版） | `帮我快速了解新能源汽车行业`<br>`深入调研一下光伏赛道`<br>`预制菜行业怎么样`<br>`SaaS 行业还有没有投资机会` |
| `nows-ytb-bilingualex` | 下载 YouTube 视频 MP4 + 生成双语（EN ‖ ZH）.ass 字幕，翻译面向中文语音合成（配音），复用浏览器登录态以支持会员/年龄限制视频 | 想下载 YouTube 视频并配上自然的中英双语字幕、用于本地观看或中文配音时 | MP4 视频文件 + 双语 .ass 字幕文件（与 MP4 同名） | `帮我下载这个 YouTube 视频并做双语字幕`<br>`把这个 YT 视频配上中英双语字幕`<br>`下载这个演讲视频，翻译成中文做成 .ass` |
| `nows-ytb-vcover` | 把 YouTube 视频/播放列表链接一键转化为社媒发布素材：发布文案（长标题/缩略图小标题/简介含原链接·发布时间·内容提炼·标签）+ B 站风格 1280×720 视频封面 HTML，支持单集与批量模式、按视频 ID 建文件夹 | 想把 YouTube 视频做成公众号/小红书/B站等二次分发素材、生成点击率更高的封面、批量产出系列封面与文案时 | `<视频ID>/文案.md` + `<视频ID>/封面.html`（可一键复制纯文本） | `把这个 YouTube 视频做成 B 站封面`<br>`帮我的视频生成发布文案和封面`<br>`把这期播客的 YouTube 链接转成发布素材`<br>`批量生成这个播放列表的封面和文案` |


## 建议

第一次使用时，先看对应目录下的 `SKILL.md`，再直接用自然语言触发就够了。