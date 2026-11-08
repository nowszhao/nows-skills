# Question Pyramid · 知识驾驶舱 Skill

分析文章、视频字幕、播客或演讲，生成单文件离线交互 HTML。

**阅读顺序：作者主张 → 独特洞见 → 约 300 字的重点复述 → 永久展开的问题导图 → 关键追问。**

安装：将 `question-pyramid/` 文件夹复制到支持 Agent Skills 的项目目录（如 Cursor 的 `.cursor/skills/`、Claude Code 的 `.claude/skills/` 或 Codex 的 `.agents/skills/`）。

用法：提供完整文章、文件或可获取的字幕，并要求“用 question-pyramid 生成知识驾驶舱 HTML”；直接分析链接的能力由 Agent 所在宿主决定，不能获取全文时须说明。

在任意 Python 3 环境执行：

```bash
python scripts/build_report.py examples/Lauren-GrokBot-分析数据.json my-report.html
```

`my-report.html` 为完全自包含的独立页面，无 JS/CSS CDN 依赖，可本地双击打开。

新版强制要求 `meta.contentRetelling` 为约 300 汉字（校验 280–320 字）、按重要性取舍的自然复述；问题导图全部节点始终显示、不提供折叠功能。
