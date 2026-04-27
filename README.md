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
```

如果你使用的是 `~/.claude/skills/`，把目标目录替换一下就行。

### 额外依赖

- `nows-tech101`：如果需要把 Markdown 转成 PDF，再安装：

```bash
pip install weasyprint markdown --break-system-packages
```

- `nows-tech-research-deck`：需要先安装 `guizang-ppt-skill`：

```bash
npx skills add https://github.com/op7418/guizang-ppt-skill --skill guizang-ppt-skill
```

## 技能使用说明

| 技能 | 是干啥的 | 适合什么时候用 | 默认产出 | 你可以怎么说 |
|---|---|---|---|---|
| `nows-tech101` | 生成某个技术的入门教程 | 想快速了解一个框架、协议、工具、语言特性时 | Markdown 教程 | `帮我写一份 Redis 的 101 教程`<br>`我想快速入门 gRPC，给我整一份 Tech101`<br>`React 是什么，帮我从零讲清楚` |
| `nows-tech-research-deck` | 调研一个技术产品，并生成演示稿 | 要做技术分享、内部汇报、竞品对比时 | `<product>-research.md` 和 `<product>-deck.html` | `帮我调研 dbt 并生成 PPT`<br>`深度调研 Dagster，做一份技术分享 slides`<br>`research Snowflake and make a deck` |


## 建议

第一次使用时，先看对应目录下的 `SKILL.md`，再直接用自然语言触发就够了。