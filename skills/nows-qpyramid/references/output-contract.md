# 正式输出契约

## 数据与命令

严格参照 `examples/Lauren-GrokBot-分析数据.json` 构建当前材料的独立 JSON。运行 `python scripts/build_report.py analysis.json report.html`。无网络依赖的 `assets/renderer.html` 是唯一 HTML 视觉模板。

`meta` 必备：`title`、`summary`、`sourceLabel`、`analysisBasis`、`contentScope`、`contentRetelling`、`display`。`contentRetelling` 是约 300 个汉字（构建器校验 280–320；统计汉字，不含标点和英文），只能是忠实于已读材料的一段自然叙述，不得填作者样例。`display` 包含材料相关的 `heroLead`、`heroIntro`、`thesisLead`、`thesisHighlight`、`thesisCaveat` 及 `principles`（每条含 title、description、relatedNode）。

`nodes`：唯一 `id`、`parent`、`question`、`answer`、`argument`、`evidence`、`answerStatus`、`type`、`consensus`、`novelty`、`strength`、`limits`。问题树恰好一个根，最大三层；每个叶子始终在导图中显示。

`insights`：`claim`、`whyItMatters`、`whyDifferent`、`certainty`、`relatedNodes`。写作者真正讲出的具体观点，不拼装假结论。

`criticalGaps`：`question`、`sourceProvides`、`missing`、`sufficiencyCriteria`、`nextSteps`、`priority`、`answerStatus`、`origin`、`relatedNodes`、`evidence`、`basis`。缺口排在页面后半部分，不能盖过原文价值。

`paragraphs`：可追溯的 `id`、`text`；`relations`：有效 `from`、`to`、`type`、`why`。来源不完整时清楚说明覆盖范围。

## 页面布局

1. 作者核心主张（视觉优先）及相关做法
2. 独特洞见（每条可点进证据详情）
3. **内容复述**（按内容重要性取舍、连贯单段、约 300 汉字）
4. **问题导图**（全节点一次绘制，**始终展开且无折叠开关**）/ 论证关系 / 原文溯源
5. 关键追问（单独于作者主张，详情可按需展开）

保留样式：高对比度文字、浅色阅读背景、深色主张卡、细滚动条、横向连线导图、侧栏证据、移动端适配。不可在 HTML 写死任何示例作者信息，页面文字必须由当前 JSON 提供。

## 导图点击稳定性

点击画布内的任意节点只应改变选择高亮并显示详情，不得触发 `renderGraph()`、`centerOn()` 或 `fit()`；保留当前 `camera.x`、`camera.y` 和 `camera.scale`，避免节点重建引发浏览器焦点跳转。非画布链接可在目标不可见时定位。验收时先拖动/缩放，再分别点击根节点、分支节点和叶子节点，比较点击前后的画布 transform，值必须保持一致。

## 复述取舍要求

内容复述应从原始材料中按重要性挑选 3–5 项核心信息：首先交代中心问题、作者回答，再解释最有价值的做法及其关键证据或例子，最后给出必要边界；不按原文篇幅平均分配字数。不得将读者追问或分析者独立补充的方法混写成作者说过的话。

## 最终交付校验：独立原文台账与双向反查

以上结构校验仅是“第一道门槛”。第二道门槛强制参见 `references/reverse-source-audit.md`：

1. 原文预先形成独立 `source-inventory.json`，逐段列出 `core/major/supporting/minor` 要点；`core/major` 必须映射到**可见正文**，仅登记 `paragraphs` 证据不算覆盖。
2. 生成 HTML 后才填写 `audit-review.json`，对每一原文要点做逐项覆盖核查（`items`），再对每个重要 HTML 结论做反向忠实性核查（`claimChecks`，含 FAQ、首页主张、洞见、复述、实践点、论证关系、关键追问）。
3. 用 `scripts/check_coverage.py prepare ...` 建审核模板；人工或 Agent **实际重读原文并打开 HTML** 后完成审核；用 `verify ...` 校验内容 ID、审核状态和哈希绑定。
4. 发现重要遗漏或误读，修改分析 JSON、重建 HTML、重新审核；未满足条件不得交付“完整核对版”。`prepare` 默认产生 `pending`，不可预先全部视作 `pass`。

请勿把 `verify` 的程序通过等同于原文无遗漏。它不能识别语义误读，也不能判断原文台账一开始是否漏掉重要观点。真正的双向读验仍是生成者责任。
