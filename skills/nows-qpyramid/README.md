# Question Pyramid Visual

基于现有问题金字塔 Skill 的升级版：默认以带原文证据的互动 HTML 作为主要阅读产物。

## 安装

将整个 `question-pyramid-visual-skill` 目录重命名为 `question-pyramid-visual`，放入你的 Agent Skills 目录（如 `.cursor/skills/`、`.claude/skills/`、`.agents/skills/`）。

## 对 Agent 说

> 使用 question-pyramid-visual 解析我提供的完整文章/字幕/文件。先建立全部实质性 FAQ，逐项记录答案、论证、原始来源位置；标注观点差异、共识状态和可信度，然后生成 analysis.json 和可离线打开的 report.html。未经外部验证的共识状态只能写待核验。

## 手动体验

- 双击 `assets/renderer.html`：看到虚构示例的完整交互体验。
- 在打开的页面顶部点击“导入分析 JSON”，可将结构化分析结果导入页面。
- 从示例 JSON 生成独立报告：

```bash
python scripts/build_report.py examples/sample-report.json output/report.html
```

浏览器离线打开 `output/report.html`，不依赖 CDN。`report.html` 内嵌 JSON，便于发送分享。

## 界面

- 增量雷达：优先呈现作者的差异化观点，避免把新颖误认为正确。
- 问题金字塔：核心问题 → 一级问题 → 关键追问，点击可查看证据。
- 论证关系：支持、限定、前提。
- 原文溯源：点击证据定位来源文字及时间戳（若源材料可用）。
- JSON 导入导出、关键词搜索、只看差异观点。

## 限制

此包不包含视频下载、转写、网页抓取、实时共识验证能力。原文可读范围取决于宿主 Agent 的工具和用户提供的材料。
目前内置 HTML 聚焦三层问题树与精选关系；超大型文章可继续扩展为 React Flow + ELKjs 的专业图谱方案。
