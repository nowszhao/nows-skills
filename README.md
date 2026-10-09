# nows-skills

存放自定义 Agent Skills 的仓库。每个 Skill 是可被 Agent 直接加载的结构化指令集。

## 安装

```bash
git clone https://github.com/nowszhao/nows-skills.git
cd nows-skills
```

把需要的 skill 目录复制到你的智能体 skills 目录（按实际路径替换 `~/.skills/`，如 `~/.workbuddy/skills/`、`~/.claude/skills/`）：

```bash
SKILLS_DIR=~/.skills
for s in skills/*/; do cp -R "$s" "$SKILLS_DIR/"; done
```

也可只装单个：`cp -R skills/nows-tech101 "$SKILLS_DIR/"`。

## 技能一览

| 技能 | 用途 | 触发示例 |
|---|---|---|
| `nows-tech101` | 生成某技术的入门教程 | `帮我写一份 Redis 的 101 教程` |
| `nows-tech-research-deck` | 调研技术产品并生成演示稿 | `帮我调研 dbt 并生成 PPT` |
| `nows-hunzige-perspective` | 用混子哥（陈磊）视角分析问题 | `用混子哥的视角看看这个问题` |
| `nows-llm-wiki` | 把 Obsidian vault 重组为 PARA + LLM Wiki | `帮我整理一下我的 Obsidian vault` |
| `nows-iplus-reading` | 按 i+1 假设设计小节级精读路径 | `帮我精读《思考，快与慢》` |
| `nows-content-distill` | 把文章/视频压成可复述的内化卡片 | `帮我把这篇文章 distill 一下` |
| `nows-article-anlyze` | 长文/研报/Keynote 拆成可交互单文件 HTML | `帮我把这篇研报拆解成可视化 HTML` |
| `nows-concept-deptree` | 梳理概念前置依赖，生成阶梯学习路径 | `学大语言模型需要什么前置知识` |
| `nows-screenshot2code` | 截图/设计稿转像素级前端代码 | `帮我把这张截图还原成 HTML` |
| `nows-podcast-publish` | 音频一键发布到小宇宙播客 | `帮我把这期播客发布到小宇宙` |
| `nows-video-bmxcut` | 配音长视频按字幕切成短视频系列 | `帮我把这个视频做切片` |
| `nows-industry-insight` | 按渗透率判定产业阶段的行业研究报告 | `帮我快速了解新能源汽车行业` |
| `nows-ytb-bilingualex` | YouTube 视频 + 双语 .ass 字幕 | `帮我下载这个视频并做双语字幕` |
| `nows-ytb-vcover` | YouTube 链接转社媒文案 + B 站封面 | `把这个 YouTube 视频做成 B 站封面` |
| `nows-bilibili-push` | 配音视频一条龙投稿到 B 站（含定时） | `投稿B站` |
| `nows-ytb-bmxtask` | 下载 + 双语字幕 + 提交配音任务 | `把这个 YT 链接做成配音任务` |
| `nows-ainews-daily` | 订阅频道 AI 视频日报 | `今日 AI 视频日报` |

首次使用先读对应目录下的 `SKILL.md`，之后直接用自然语言触发即可。
