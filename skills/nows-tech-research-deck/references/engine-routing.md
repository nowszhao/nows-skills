# Engine Routing · 页面类型 → 引擎 Layout 路由表

Phase B 渲染的核心规则：根据页面内容类型，选择**本 skill 内建基础 layout** 或 **本 skill 的 extra layout**。

---

## 路由总表

| 页面类型 | 典型内容 | 引擎 | 对应 Layout |
|---|---|---|---|
| 封面 | 产品名 + 副标题 + 日期 | base | `cover` |
| 章节幕封 | "Act 1 WHY"、"Act 2 HOW" | base | `chapter` |
| 大字报数字页 | "100x faster"、"2016 年诞生" | base | `big-stat` |
| 引用页 | 作者原话、用户证言 | base | `quote` |
| 左文右图 | 痛点举例 + 插图 | base | `text-image` |
| 图片网格 | 多截图并排 | base | `image-grid` |
| 图文混排 | Act 1 的叙事页 | base | `magazine-mix` |
| Before/After 对比 | 用和不用的对比 | base | `before-after` |
| 悬念问题 | "为什么 Airflow 不够？" | base | `question` |
| **架构图页** | ASCII 架构图 + 模块说明 | **extra** | `architecture-page.html` |
| **代码 demo 页** | 长代码 + 输出 | **extra** | `code-demo-page.html` |
| **竞品对比表页** | 6 维度矩阵表 | **extra** | `comparison-table-page.html` |

---

## 页面顺序模板（standard 25 页示例）

```
01  [cover]         封面：产品名 + 一句话定位
02  [chapter]       Act 1 · WHY
03  [magazine-mix]  反面样本（没有它的时候）
04  [text-image]    关键痛点 ①②③
05  [big-stat]      诞生时间线 + 关键数字
06  [chapter]       Act 2 · HOW
07  [text-image]    核心概念（≤5 个）
08  [architecture-page]  ★ 核心架构 ASCII 图
09  [magazine-mix]  模块职责表
10  [magazine-mix]  生命周期叙事
11  [quote]         设计取舍引言（作者原话）
12  [chapter]       Act 3 · VS
13  [comparison-table-page]  ★ 竞品 6 维度矩阵
14  [before-after]  差异化那一招（代码对比）
15  [text-image]    什么时候不该选它
16  [chapter]       Act 4 · DO
17  [code-demo-page]      ★ 开发（Hello World）
18  [code-demo-page]      ★ 测试
19  [code-demo-page]      ★ 发布 / CI
20  [code-demo-page]      ★ 调度
21  [code-demo-page]      ★ 进阶示例（自身优势特性）
22  [quote]         用户证言
23  [big-stat]      核心指标总结
24  [text-image]    推荐用法 / 不推荐用法 清单
25  [cover]         结束页 + QR / 联系方式
```

quick 15 页：砍掉 Act 4 的"发布"和"调度"独立页，合成一页；砍掉证言和大字报重复页。
deep 40+ 页：每个 Act 2 的概念、每个 Act 4 的环节各拆一页，加 Appendix。

---

## 扩展 Layout 使用规范

### architecture-page.html
- 架构图区域占页面 65% 高度
- 右侧或下方放"模块说明"（≤4 条）
- 字体：架构图用等宽（`--font-mono`），说明用正文字体

### code-demo-page.html
- 上方 25%：demo 场景标题 + 一句话说明
- 中间 55%：代码块（支持 horizontal scroll，不换行）
- 下方 20%：输出 / 说明 / 关键点标注
- 语言标签必须有（`sql` / `python` / `yaml` / `bash`）

### comparison-table-page.html
- 表头左侧锁定（竖向维度名不滚动）
- 每个单元格：分数（大字号）+ 一行证据（小字号）
- 最后一行加粗：总分

---

## 主题色与 extra layout 的配合

extra layout 全部使用本 skill 基础模板的 CSS 变量：

```css
:root {
  --ink: ...;
  --paper: ...;
  --accent: ...;
  --muted: ...;
  --font-serif: ...;
  --font-sans: ...;
  --font-mono: ...;
}
```

**不要**在 extra layout 里写死颜色。切主题时只改 `:root{}`，所有页面同步变色。
