# LESSONS.md · tech-research-deck 踩坑经验池

由 Agent 在多次尝试后自动追加的经验。只有**经过 2 次及以上尝试才解决**的问题才写在这里。

## 记录格式

```
- <日期> · <调研对象或环节>：<经验要点（下次遇到同样情况该怎么做）>
```

---

## 基础经验（skill 初始化时预置）

- 2026-04-26 · render_deck 分类器：ASCII timeline（只有 `─│` 横竖线）不要被判成架构图；architecture-page 必须同时含 `┌┐└┘╔╗╚╝` 方框角字符 **和** `├┤┬┴┼` 分叉字符，两个条件同时满足才算。
- 2026-04-26 · Appendix 三段分节：`### 官方（S 级）`、`### 社区（A/B 级）`、`### 批评 / 反面（D 级但有用）` 是 Appendix 的子标题，不是独立页面，render_deck 必须在 SKIP_HEADINGS 里登记。
- 2026-04-26 · 短 body + 数字：不要用"长度 <80 且含数字"判 big-stat，容易误伤所有占位符骨架；big-stat 只由标题关键词触发（如"时间线"、具体数字大字报的明确标题）。

---

## 调研对象专属经验

（按字母序追加。如果某个产品调研有反复出现的坑，写在下面。）

<!-- 示例：
- 2026-05-01 · dbt：架构讲解要抓"编译器 + 适配器"两个关键词，别跟着官网说"SQL workflow platform"的营销话术。核心是 manifest.json → compiled SQL → adapter 分发这条主线。
- 2026-05-02 · Dagster：别和 Airflow 按 "DAG 调度器" 维度直接对比，要突出 software-defined assets 的差异化定位，否则评分会不公允。
-->
