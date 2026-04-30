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
```

如果你使用的是 `~/.claude/skills/`，把目标目录替换一下就行。

### 额外依赖

- `nows-tech101`：如果需要把 Markdown 转成 PDF，再安装：

```bash
pip install weasyprint markdown --break-system-packages
```

- `nows-tech-research-deck`：渲染能力已内置，无需再额外安装 PPT skill。

## 技能使用说明

| 技能 | 是干啥的 | 适合什么时候用 | 默认产出 | 你可以怎么说 |
|---|---|---|---|---|
| `nows-tech101` | 生成某个技术的入门教程 | 想快速了解一个框架、协议、工具、语言特性时 | Markdown 教程 | `帮我写一份 Redis 的 101 教程`<br>`我想快速入门 gRPC，给我整一份 Tech101`<br>`React 是什么，帮我从零讲清楚` |
| `nows-tech-research-deck` | 调研一个技术产品，并生成演示稿 | 要做技术分享、内部汇报、竞品对比时 | `<product>-research.md` 和 `<product>-deck.html` | `帮我调研 dbt 并生成 PPT`<br>`深度调研 Dagster，做一份技术分享 slides`<br>`research Snowflake and make a deck` |
| `nows-hunzige-perspective` | 混子哥（陈磊）的思维框架与表达方式，作为思维顾问分析知识传播、产品设计、内容创作问题 | 需要用混子哥的视角分析问题时 | 基于混子哥思维框架的分析和回答 | `用混子哥的视角看看这个问题`<br>`混子哥会怎么看`<br>`切换到混子哥模式` |
| `nows-llm-wiki` | 把现有 Obsidian vault 重组为 `PARA + LLM Wiki` 混合知识库 | 想整理 Obsidian 笔记库、重构目录、补 frontmatter、生成 MOC / 概念页 / 索引页时 | 重组方案、迁移计划、wiki 页面与索引 | `帮我整理一下我的 Obsidian vault`<br>`把我的 vault 按 PARA + LLM Wiki 方式重组`<br>`给我的 vault 生成 MOC / 索引 / 概念页` |


## 建议

第一次使用时，先看对应目录下的 `SKILL.md`，再直接用自然语言触发就够了。