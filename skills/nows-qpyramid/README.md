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

## 最终反向核对（强制）

新增终审：生成 HTML 后，对照**原文要点台账**做双向检查。先核对原文主要内容是否在最终报告中得到充分表达，再从 HTML 的每条重要结论反查原文出处。发现遗漏、误读、证据错配或重要条件丢失时，先修改 JSON、重新生成 HTML，再复核新成品；未解决的核心/重大问题不得被标为通过。

```bash
python scripts/check_coverage.py prepare source-inventory.json analysis.json report.html audit-review.json
# 结合原文逐条完成 audit-review.json 审核记录，不能直接填 pass
python scripts/check_coverage.py verify source-inventory.json analysis.json report.html audit-review.json
```

审核表必须绑定 HTML 和原文台账的哈希：更新 HTML 后需重新核对。工具只验证字段、引用和审核闭环，**不能自动证明语义正确或绝无遗漏**。原始材料不完整时只能声明有限核对。

详见 `references/reverse-source-audit.md`。
