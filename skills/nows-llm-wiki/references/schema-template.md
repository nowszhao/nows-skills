# CLAUDE.md template (vault schema)

Write this to `<vault>/CLAUDE.md` at the end of Phase 5. It is the **wiki contract** between human and LLM — every future LLM session reads it first.

Fill the placeholders with the user's actual choices.

```markdown
# CLAUDE.md — Wiki 操作规范 (PARA + Karpathy LLM Wiki)

> 本文件是此 Obsidian vault 的 schema。任何 LLM 每次进入本 vault 时，必须先读取本文件以了解结构、约定和操作流程。
> 最后更新：YYYY-MM-DD

---

## 一、整体架构（PARA + Karpathy LLM Wiki 融合）

```
<vault-name>/
├── CLAUDE.md                    ← 本文件（schema，你正在读）
│
├── 00-Inbox/                    ← 捕获区 + LLM Wiki raw 层
│   ├── AnyWrite.md              ← 快速记录入口（可选）
│   └── raw/                     ← 【LLM Wiki 层 1】immutable，只读
│       ├── research/            ← 结构化研究、HV 分析、PRD 等
│       ├── clippings/           ← 网页剪藏
│       ├── transcripts/         ← 会议/播客转写（可选）
│       └── flash/               ← Excalidraw 草图、快速草稿
│
├── 01-Projects/                 ← P：活跃项目（不纳入 wiki）
├── 02-Areas/                    ← A：持续领域
├── 03-Resources/                ← R：外部参考资料
├── 04-Archive/                  ← 归档
│
├── Daily Note/                  ← 日记（不纳入 wiki）
│
└── wiki/                        ← 【LLM Wiki 层 2】LLM 全权维护
    ├── index.md                 ← 内容目录（每次 ingest 更新）
    ├── log.md                   ← 操作日志（仅追加）
    ├── concepts/                ← 概念页
    ├── entities/                ← 实体页
    ├── moc/                     ← Map of Content
    └── synthesis/                ← 跨概念综合
```

### PARA 与 LLM Wiki 的分工

| 维度 | PARA（行动空间） | LLM Wiki（知识空间） |
|---|---|---|
| 解决什么 | 我的行动在哪 → 项目/领域/资源/归档 | 知识如何合成 → raw → wiki |
| 组织原则 | 按可执行性分层 | 按不可变性分层 |
| 谁来写 | 人 | LLM |
| 核心目录 | `01-Projects/`、`02-Areas/`、`03-Resources/`、`04-Archive/` | `00-Inbox/raw/`、`wiki/` |

### LLM Wiki 三层模型

| 层 | 目录 | 权限 |
|---|---|---|
| Raw Sources | `00-Inbox/raw/` | 只读，LLM 不修改正文，可补 frontmatter |
| Wiki（合成层）| `wiki/` | LLM 全权维护 |
| Schema | `CLAUDE.md` | 人 + LLM 协同 |

> **设计决策**：`raw/` 放在 `00-Inbox/` 下，体现"新材料进来先落 Inbox"的捕获语义；消化后的知识合成进 `wiki/`，形成"捕获 → 合成"的清晰流向。

---

## 二、PARA 约定

- `01-Projects/<project-slug>/` — 每个项目一个子目录
- `02-Areas/<area-slug>/` — 每个领域一个子目录
- `03-Resources/<topic>/` — 按主题归类
- `04-Archive/` — 归档时保留原子目录名，不打平
- **`01-Projects/` 下的文件不纳入 wiki ingestion**。项目完成后再决定是否提升到 `00-Inbox/raw/`

---

## 三、Frontmatter 规范

### Raw 源（`00-Inbox/raw/`）
```yaml
---
title: "笔记标题"
type: source
source_kind: research | clipping | transcript | paper | flash
date: YYYY-MM-DD
tags: []
domain: <主域>
related:
  - "[[相关笔记]]"
---
```

### Wiki 概念页（`wiki/concepts/`）
```yaml
---
title: "概念名"
type: concept
domain: <主域>
source_count: <N>
sources:
  - "[[raw-note]]"
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: stub | draft | stable | needs-review
---
```

### 其他类型参见 `page-formats.md`（entity / synthesis / moc / source / index / log）。

### 标签体系
- 类型标签：`调研`、`规划`、`设计`、`产品分析`、`横纵分析`、`剪藏`
- 主题标签：按 vault 实际领域填充
- 状态标签：`stub`、`draft`、`stable`

---

## 四、操作流程

### 4.1 Ingest — 新增 raw 源
1. 将资料放入 `00-Inbox/raw/<子目录>/`
2. LLM 读取并与用户讨论核心要点
3. 为资料补 frontmatter（如缺失）
4. 更新 `wiki/concepts/`、`wiki/entities/`、`wiki/moc/` 中相关页面
5. 更新 `wiki/index.md`
6. 在 `wiki/log.md` 追加日志条目

### 4.2 Query — 查询（⭐ 复利核心）
1. 先读 `wiki/index.md` 和相关 MOC
2. 读相关 `wiki/concepts/` / `wiki/entities/`；必要时下钻到 `00-Inbox/raw/`
3. 合成答案，用 `[[wikilink]]` 引用
4. **按 query-compounding 规则判断是否存回 `wiki/synthesis/`**（≥2 概念或 ≥3 raw 源 ⇒ 存）

### 4.3 Weekly Review — PARA 周回顾
1. 运行 `scripts/weekly_review.py`
2. 处理 7 天未消化的 Inbox 项、14 天无变动的 Projects、90 天无更新的 Areas
3. 周回顾结果落到 `00-Inbox/reviews/YYYY-MM-DD.md`，由用户决定行动

### 4.4 Lint — 系统化健康检查（⭐ Karpathy 8 项）
1. 页面矛盾
2. 过时结论（新 raw 已否定但未标注）
3. 孤立页面（无 `[[双向链接]]`）
4. 缺失概念页（红链 ≥3 次）
5. 缺失交叉引用
6. 知识缺口超 30 天未跟进
7. `index.md` 与文件系统不一致
8. `log.md` 超 7 天未更新

Lint 结果追加到 `wiki/log.md`。

### 4.5 矛盾处理（参见 contradiction-protocol.md）
1. 不删除，只标注 `⚠️ 已过时`
2. 在页面的 `## 矛盾与演进` section 追加条目
3. 跨页传播：受影响的相关页面同步更新

---

## 五、Log 格式（`wiki/log.md`）

```markdown
## [YYYY-MM-DD] <操作类型> | <简述>

操作类型：ingest / query / lint / update / create / restructure / rebuild / review

- 具体操作内容
- 影响的文件
```

---

## 六、核心纪律（不可违反）

### 三层操作权限
1. `00-Inbox/raw/` 正文只读，LLM 不改
2. `wiki/log.md` 仅追加，不修改历史
3. `01-Projects/` 不纳入 wiki ingestion

### 知识复利纪律
4. 好的综合分析存到 `wiki/synthesis/`，而不是仅留在对话中
5. 每次复杂 query 后按 query-compounding 规则评估是否存回
6. 不删除，只标注矛盾；在 `矛盾与演进` section 记录完整演进链
7. 跨页传播：A 的更新影响 B，必须同步更新 B

### 命名与语言
8. 默认语言：<CN|EN|Mixed>（按用户选择填写）
9. 文件 slug：kebab-case；CJK 标题可保留中文
10. 新 raw 资料入 `00-Inbox/raw/<子目录>/`

---

## 七、当前知识库状态

**核心主题**：<此 vault 的主题>

**目录概览**：
- `00-Inbox/raw/research/`：<N> 篇
- `00-Inbox/raw/clippings/`：<N> 篇
- `01-Projects/`：<N> 个活跃项目
- `02-Areas/`：<N> 个领域
- `wiki/concepts/`：<N> 篇概念页
- `wiki/entities/`：<N> 篇实体页
- `wiki/moc/`：<N> 篇 MOC
- `wiki/synthesis/`：<N> 篇综合分析

**已知缺口（Gaps）**：
- ...

**Karpathy 方法论落地状态**：
- ✅ 三层架构（Raw / Wiki / Schema）
- ✅ Ingest / Query / Lint 流程
- ✅ 矛盾标注规范
- ✅ Query 复利原则
- ✅ 系统化 Lint 8 项
- ⏳ 矛盾与演进内容待在实际 ingest 中逐步填充
```

## 使用提示

- **首次建立**：skill 在 Phase 5 写入 `CLAUDE.md`。之后任何 LLM 会话进入本 vault 应先读它。
- **演进**：用户与 LLM 协同编辑 CLAUDE.md。重大结构变化一定记录在 `wiki/log.md`。
- **别把 CLAUDE.md 当索引**：索引在 `wiki/index.md`。CLAUDE.md 只放约定。
