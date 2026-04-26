# Research Sources · 三源交叉检索清单

目标：防止调研变成"只读了官网的软文"。

---

## 信源质量分级（评估每一条资料都按这个打分）

| 级别 | 含义 | 例子 |
|---|---|---|
| S | 第一手 + 权威 | 官方 docs、核心作者博客、源码、RFC |
| A | 第一手或高质量二手 | 官方博客、conference talk、公司 engineering blog |
| B | 高质量社区内容 | Hacker News 高赞评论、知名技术博客、StackOverflow 高赞答案 |
| C | 一般社区内容 | Medium 水文、培训机构教程、翻译二手文 |
| D | 营销 / 过时 / 错误 | 厂商 landing page 的性能对比、2 年以上未更新的博客 |

**规则**：调研引用至少包含 3 条 S/A 级、2 条 B 级、1 条 D 级（用来反推营销话术和实际差距）。

---

## 必查检索清单（每个调研对象都要过一遍）

### 官方侧（S 级）
- [ ] 官网 Landing 的 "What is X / Why X" 页面
- [ ] 文档站的 "Concepts / Architecture / How it works" 章节
- [ ] GitHub 仓库 README
- [ ] GitHub 仓库 `docs/` 或 `architecture/` 目录
- [ ] GitHub 最近 30 天的 closed PR（看真实开发方向）
- [ ] GitHub Issues 里 `good-first-issue` 和 `help-wanted` 标签（看痛点分布）
- [ ] Release Notes 最近 3 个大版本

### 社区侧（A/B 级）
- [ ] Hacker News：搜产品名 + 看高赞评论（反面观点含金量高）
- [ ] Reddit：`r/dataengineering` / `r/programming` 对应社区
- [ ] 技术博客：作者团队成员的个人博客 / 所在公司 engineering blog
- [ ] Conference talks：YouTube / InfoQ / Data Council 上的演讲
- [ ] 中文社区：知乎高赞回答、InfoQ 中文站、公众号（警惕翻译二手）

### 批评性内容（必查，D 级但有用）
- [ ] 搜索：`<product> problems`、`<product> alternatives`、`<product> vs`
- [ ] 搜索：`<product> migration away from`、`why we moved from <product>`
- [ ] 搜索：`<product> limitations`、`<product> cons`

### 竞品侧（每个竞品至少走一遍）
- [ ] 竞品官网的 "Why X instead of <target>" 页面（如果有）
- [ ] 第三方对比文章（≥3 篇不同作者）
- [ ] 迁移故事（A→B 或 B→A 都要读）

---

## 检索时的查询模板

```
<product> architecture
<product> how it works
<product> vs <competitor>
why we chose <product>
why we moved away from <product>
<product> limitations production
<product> github discussions
```

---

## Appendix 产出规范

在 research.md 末尾统一登记，按"官方 / 社区 / 批评"三段分组。每条：

```
- [标题](URL) — S/A/B/C/D — 用途说明（用于哪一幕的哪个段落）
```

示例：
```
### 官方
- [dbt viewpoint](https://docs.getdbt.com/community/resources/viewpoint) — S — Act 1 痛点部分
- [How dbt compiles](https://docs.getdbt.com/guides/best-practices) — S — Act 2 生命周期

### 社区
- [dbt at Scale (Netflix talk)](https://...) — A — Act 4 进阶示例
- [HN: dbt 2 years later](https://news.ycombinator.com/...) — B — Act 3 反面观点

### 批评
- [Why we moved off dbt](https://...) — D — Act 3 "不该选它" 场景
```
