---
name: tech-research-deck
description: >
  Deep-researches any technical product (framework, tool, platform, language,
  or protocol) and produces a 4-act technical deck covering background,
  architecture, competitive landscape, and end-to-end usage demo. Renders to a
  single-file magazine-style HTML deck via guizang-ppt-skill by default, with
  three technical-oriented extra layouts (architecture, code-demo, comparison-
  table) for pages guizang does not handle well. Use when the user asks to
  research, investigate, survey, or deep-dive a technical product and wants a
  PPT, slides, deck, 幻灯片, or 演示稿 as output. Typical triggers include
  "帮我调研 X 并生成 PPT", "深度调研 X", "X 技术分享 ppt", "给我一份 X 的
  技术调研 slides", "research X and make a deck", "investigate X framework
  presentation", "X 产品分析 PPT", "X 架构介绍 演示稿".
---

# tech-research-deck

把"调研一个技术产品 + 出一份技术 PPT"这件事做成两阶段流水线：
**Phase A 调研**产出结构化 `research.md`（纯内容），
**Phase B 渲染**把 `research.md` 喂给 guizang-ppt-skill 加扩展 layout，出单文件 HTML deck。

调研和排版解耦，每阶段单独可复用、可调试。

---

## 0. 依赖前置

- **必需**：`guizang-ppt-skill` 已安装到 `~/.claude/skills/` 或 `~/.workbuddy/skills/`。
  未安装时先引导用户安装：
  ```
  npx skills add https://github.com/op7418/guizang-ppt-skill --skill guizang-ppt-skill
  ```
- **可选**：`web-access` skill（用于联网调研）。无此 skill 时降级为 `web_search` + `web_fetch`。

---

## 1. 6 问澄清（Phase A 启动前必须全问清）

不要跳问。答不出的项用默认值并**明确告诉用户用了默认值**。

| # | 问题 | 默认值 |
|---|---|---|
| Q1 | 调研对象是？（产品名 + 官网 URL + GitHub 仓库 URL） | 无默认，必须填 |
| Q2 | 受众？（CTO 汇报 / 团队分享 / 外部布道 / 社招面试 / 学习笔记） | 团队分享 |
| Q3 | 深度级别？（`quick` 15 页 / `standard` 25 页 / `deep` 40+ 页） | standard |
| Q4 | 必须覆盖的竞品？（逗号分隔） | 自动挑选 3 个最相关 |
| Q5 | 是否跑 demo？（`real` 真跑 / `pseudo` 伪代码 / `none` 不做） | pseudo |
| Q6 | 主题色？（墨水经典 / 靛蓝瓷 / 森林墨 / 牛皮纸 / 沙丘） | 靛蓝瓷（技术向默认） |

---

## 2. Phase A · 调研流水线（4 步硬约束）

### Step A1 · 三源交叉检索

对调研对象执行**最少三个信源**的检索，不能只看官网：

| 信源类型 | 用途 | 必要性 |
|---|---|---|
| 官网 / Landing | 卖点、核心定位、目标用户 | 必要 |
| 文档站 / Docs | 真实架构、API、工作机制 | 必要 |
| GitHub 仓库 | 活跃度、issues 热点、架构目录 | 必要 |
| 批评性文章 | Hacker News / Reddit / 博客中的"它的问题是什么" | 建议 |
| 竞品官网 | 用来填 Act 3 的对比矩阵 | 必要（至少 3 家）|

详细检索清单见 `references/research-sources.md`。

### Step A2 · 填充"四幕骨架"

打开 `assets/research-template.md`，按 4 幕填内容：

```
Act 1  WHY  — 为什么存在
Act 2  HOW  — 怎么跑通
Act 3  VS   — 凭什么赢
Act 4  DO   — 怎么用起来（开发→测试→发布→调度）
```

每一幕的字段定义和最小信息量见 `references/research-framework.md`。

### Step A3 · 产出 2 类关键结构物

无论调研什么产品，以下两个产物**必须**生成：

1. **一张核心架构 ASCII 图**（用户偏好 ASCII UI，禁用 Mermaid）。
   规范和 5 种范式见 `references/ascii-diagrams.md`。
2. **一张竞品对比矩阵**（≥3 个竞品 × 6 个评分维度）。
   模板见 `references/competitor-matrix.md`。

### Step A4 · Phase A 出关前自检（P0，必过）

在 `research.md` 末尾追加一个 checklist 段落，逐项 ✅/❌：

- [ ] 每一幕都有内容，没有 TODO 占位
- [ ] 架构 ASCII 图存在且不是 Mermaid
- [ ] 竞品矩阵 ≥3 家 × 6 维度
- [ ] Act 4 覆盖"开发 / 测试 / 发布 / 调度"四环节（对应不上的要明确标注 N/A 及原因）
- [ ] 有至少 1 个"体现自身优势"的进阶代码示例
- [ ] 所有数据/声明都有来源链接（Appendix 分三源：官方 / 社区 / 批评）

**任一 ❌ → 回到对应步骤补齐，不准进入 Phase B。**

---

## 3. Phase B · 渲染流水线

### Step B1 · 页面类型路由

把 `research.md` 按 section 拆成页面，每页分配一个"页面类型"，然后按下表路由到引擎。详细路由规则见 `references/engine-routing.md`。

| 页面类型 | 引擎 / Layout |
|---|---|
| 封面、章节幕封、大字报数字页、引用页 | guizang 原生 layout |
| 左文右图、图片网格、图文混排 | guizang 原生 layout |
| **架构图页**（含 ASCII 图） | `assets/extra-layouts/architecture-page.html` |
| **代码 demo 页**（长代码块） | `assets/extra-layouts/code-demo-page.html` |
| **竞品对比表页** | `assets/extra-layouts/comparison-table-page.html` |

扩展 layout 与 guizang 共用 CSS 变量（`--ink`、`--paper`、`--accent`...），视觉一致。

### Step B2 · 调 guizang 生成基础 HTML

复制 `guizang-ppt-skill/assets/template.html` 到工作目录，按 Q6 切主题色，按 guizang 的 6 步流程填充原生 layout 页。

### Step B3 · 注入扩展 layout 页

用 `scripts/render_deck.py` 把架构图页、代码 demo 页、竞品对比表页插入到对应位置。插入规则：

- **架构图页**：放在 Act 2 HOW 的第二页（在"核心概念"之后）
- **竞品对比表页**：放在 Act 3 VS 的第一页
- **代码 demo 页**：Act 4 DO 的每一个环节（开发/测试/发布/调度）至少一页

### Step B4 · 渲染后自检（P0，必过）

对照 `guizang-ppt-skill/references/checklist.md` 跑一遍，额外补 3 条技术向自检：

- [ ] 架构图页能通过浏览器 zoom 150% 清晰阅读（代码字体 ≥14px）
- [ ] 代码块有明确语言标签，长代码有横向滚动而非换行截断
- [ ] 竞品表在 1440 宽屏下不溢出

---

## 4. 产物规范

| 产物 | 路径 | 格式 |
|---|---|---|
| 调研底稿 | `<workdir>/<product>-research.md` | Markdown |
| 最终 PPT | `<workdir>/<product>-deck.html` | 单文件 HTML |
| 来源附录 | `<workdir>/<product>-sources.md` | Markdown（可选） |

交付时用 `deliver_attachments` 一次性把三份都给用户，并用 `preview_url` 打开 HTML deck。

---

## 5. 关键原则

1. **调研与排版解耦**：research.md 烂就回 Phase A，HTML 丑就回 Phase B，不混调。
2. **ASCII 不用 Mermaid**：用户明确偏好，别犯。
3. **竞品要真对比**：同维度打分，不要罗列两家的 feature list 当对比。
4. **demo 要能跑**：`real` 模式下代码必须是真实可运行的，`pseudo` 模式要显式标 "伪代码"。
5. **数据有来源**：每条关键论断配 URL，Appendix 统一登记。
6. **术语一致**：全文统一用一个词（如都叫 `model` 或都叫 `node`，不混用）。
7. **遇到踩坑就写 LESSONS.md**：2 次及以上尝试才搞定的问题必须沉淀。

---

## 6. 反模式（别干）

- ❌ 跳过 6 问直接开始调研
- ❌ 只看官网不看 docs 和 GitHub
- ❌ 竞品对比写成散文段落（必须表格）
- ❌ 把架构图画成 Mermaid 或文字堆
- ❌ Phase A 没过自检就开始写 HTML
- ❌ 在 SKILL.md 里堆长篇大论（保持 ≤500 行，细节放 references/）
- ❌ 时间敏感信息写在正文（放 `## Old patterns` 折叠区或 LESSONS.md）

---

## 7. 经验积累

每次经过 2 次及以上尝试才成功的情况，追加到 `LESSONS.md`。格式见该文件头部。
