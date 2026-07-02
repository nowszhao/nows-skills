# nows-screenshot2code — AI Agent Skill

将截图、设计稿、UI 图片转换为像素级还原的前端代码。

## 概述

这是一个 **Prompt 型 Skill**，从 [screenshot-to-code](https://github.com/abi/screenshot-to-code) 开源项目中提取核心精华（Prompt 模板 + 技术栈 CDN 配置 + 自检清单）。它指导 AI 按标准化工作流完成截图→代码的转换，无需启动后端服务。

## 目录结构

```
skills/nows-screenshot2code/
├── SKILL.md                    # 🔑 Skill 主指令（AI 加载后会遵循此文件）
├── prompts/
│   ├── __init__.py             # Prompt 模块导出
│   └── templates.py            # System prompt + 用户 prompt 模板 + 技术栈配置
├── scripts/
│   ├── color_extractor.py      # 从截图中提取主色调
│   └── validate_output.py      # 验证生成的 HTML
└── README.md                   # 本文件
```

## 如何安装为 CodeBuddy Skill

1. 将 `skills/nows-screenshot2code/` 目录复制到你的本地 skills 目录中：
   ```bash
   mkdir -p ~/.workbuddy/skills
   cp -R skills/nows-screenshot2code ~/.workbuddy/skills/
   ```
2. 确保 `SKILL.md` 作为 Skill 主文件被识别
3. 在对话中用 `@nows-screenshot2code` 激活，或直接丢截图说"还原成 HTML"

## 支持的技术栈

| Stack | 框架 | 适用场景 |
|-------|------|---------|
| `html_tailwind` | HTML + Tailwind CSS CDN | 大多数设计，快速开发（默认） |
| `html_css` | HTML + CSS + 原生 JS | 简单设计 |
| `react_tailwind` | React 18 + Tailwind CDN | 复杂交互 UI |
| `vue_tailwind` | Vue 3.3 + Tailwind CDN | Vue 项目 |
| `bootstrap` | Bootstrap 5.3 | 标准后台 / 仪表盘 |
| `ionic_tailwind` | Ionic + Tailwind | 移动优先 / App 风格 |

## 工作流

```
截图输入 → 分析 (布局/颜色/字体/间距) → 选择技术栈 → 生成代码 → 自检验证 → 输出
```

详细步骤见 `SKILL.md`。

## 辅助脚本

### 颜色提取

从截图提取主色调（需 `pip install Pillow scipy numpy`）：

```bash
python skills/nows-screenshot2code/scripts/color_extractor.py screenshot.png --count 8
```

### HTML 验证

校验生成的 HTML 结构、CDN 链接、文件大小：

```bash
python skills/nows-screenshot2code/scripts/validate_output.py index.html
```

## 与原始项目的关系

| 原始项目特性 | Skill 中的处理 |
|-------------|---------------|
| WebSocket 实时管线 | → 不适用（Skill 是同步 / 对话模式） |
| 多模型并行（4 变体） | → 单次生成（AI 对话中一次一个） |
| Agent 工具调用循环 | → AI 自我审查循环 |
| Playwright 截图预览 | → 浏览器自动化工具或 `preview_url` |
| Replicate 图片生成 | → 占位图 + 描述替代 |
| Gemini 资产提取 | → AI 视觉分析替代 |
| Prompt 模板 | ✅ **完整提取** |
| 技术栈 CDN 配置 | ✅ **完整提取** |
| 系统提示词 | ✅ **适配后提取** |

## License

与原项目保持一致：MIT
