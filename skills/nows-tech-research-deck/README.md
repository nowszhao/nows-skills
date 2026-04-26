# tech-research-deck

把"深度调研一个技术产品 + 出一份技术 PPT"做成两阶段流水线的 Skill。

## 为什么存在

一次性 prompt 写"帮我调研 X 并生成 PPT"有 4 个硬伤：主题硬编码、大纲硬编码、调研深度不可控、排版引擎和内容耦合。本 skill 把这事拆成可复用的两阶段：

```
Phase A  Research  ──►  <product>-research.md   （纯内容，结构化）
                              │
                              ▼
Phase B  Render    ──►  <product>-deck.html     （单文件 HTML PPT）
```

## 触发方式

装好后 Agent 自动发现，典型触发话术：

- 帮我调研 dbt 并生成 PPT
- 深度调研 Dagster，出一份 25 页的技术 slides
- research Snowflake and make a magazine-style deck

## 安装

```bash
# 本 skill 已放在
~/.workbuddy/skills/tech-research-deck/

# 依赖：guizang-ppt-skill 必须先装好
npx skills add https://github.com/op7418/guizang-ppt-skill --skill guizang-ppt-skill
```

## 目录结构

```
tech-research-deck/
├── SKILL.md                         # 主流程、6 问、路由规则
├── LESSONS.md                       # Agent 沉淀的踩坑经验
├── README.md                        # 本文件
├── references/
│   ├── research-framework.md        # 四幕（WHY/HOW/VS/DO）骨架详细定义
│   ├── research-sources.md          # 三源交叉检索清单 + 信源分级
│   ├── competitor-matrix.md         # 竞品 6 维度打分矩阵模板
│   ├── ascii-diagrams.md            # ASCII 架构图规范（禁 Mermaid）+ 5 种范式
│   └── engine-routing.md            # 页面类型 → 引擎 layout 路由表
├── assets/
│   ├── research-template.md         # Phase A 产物骨架（Markdown）
│   └── extra-layouts/               # 技术向扩展 layout，与 guizang 共用 CSS 变量
│       ├── architecture-page.html
│       ├── code-demo-page.html
│       └── comparison-table-page.html
└── scripts/
    ├── research_scaffold.py         # 6 问输入 → 生成 research.md 骨架
    └── render_deck.py               # 解析 research.md → 输出 render-plan.json
```

## 核心原则

1. **调研与排版解耦**：research.md 烂就回 Phase A，HTML 丑就回 Phase B，不混调。
2. **ASCII 不用 Mermaid**：用户偏好 ASCII UI。
3. **竞品要真对比**：同 6 维度打分 + 逐项证据，不写 feature list。
4. **Act 4 必须覆盖"开发/测试/发布/调度"全流程**：这是技术 deck 和营销 deck 的分水岭。
5. **数据有来源**：Appendix 分官方/社区/批评三段登记，每条标级别 S/A/B/C/D。

## 手动调用脚本（可选）

通常 Agent 会自动调用。手动调试时：

```bash
# Phase A：生成骨架
python3 scripts/research_scaffold.py \
  --product "dbt" \
  --website "https://www.getdbt.com/" \
  --repo "https://github.com/dbt-labs/dbt-core" \
  --docs "https://docs.getdbt.com/" \
  --audience "团队分享" \
  --depth standard \
  --competitors "SQLMesh,Dataform,Airflow+SQL" \
  --demo pseudo \
  --theme 靛蓝瓷 \
  --outdir ./workdir

# Phase B：生成渲染计划
python3 scripts/render_deck.py \
  --research ./workdir/dbt-research.md \
  --theme 靛蓝瓷 \
  --outplan ./workdir/dbt-render-plan.json
```

`render_deck.py` 只产出计划（JSON + 页面清单），不直接写 HTML——HTML 的最终填充由 Agent 结合 `guizang-ppt-skill/assets/template.html` 完成，因为文字排版需要上下文感知。

## 维护

- 每次遇到 2 次以上尝试才解决的问题 → 追加到 `LESSONS.md`
- 触发率不理想时 → 在 SKILL.md 的 `description` 里加同义触发词
- 扩展 layout 不够用 → 加新文件到 `assets/extra-layouts/`，同步更新 `engine-routing.md`
