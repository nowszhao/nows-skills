---
name: nows-content-distill
description: |
  把一篇文章 / 一个文章链接 / 一个 YouTube 视频，压缩成"刻进脑子的心理表征"。
  不是摘要工具，是认知刻印器——给自己用，不是给别人看的。
  产出固定的 5 项结构：核心概念、行文逻辑（金字塔）、差异化亮点、值得记住的话、≤500 字最简复述。
  两阶段产物：先生成 Markdown（中间产物，可手工修订），再渲染成单文件、零依赖、笔记风的美观 HTML。
  触发词包括：沉淀这篇、刻印一下、压一下这篇、做心理表征、做认知卡片、distill、提炼、把这篇压成卡片、
  帮我把这篇/这个视频留在脑子里、做一份阅读笔记卡、把这内容内化一下、看完留点东西。
  也适用于：用户丢来一段文章正文 / 一个 URL / 一个 YouTube 链接，明示或暗示"读完想记住、想沉淀、想内化"。
---

# nows-content-distill — 内容萃取与认知刻印

把外部信息流（文章 / YouTube 视频）最快速地转成大脑里能立得住、可被回忆、可被复述的"内部表征"。

## 核心定位

**这是给自己用的"认知刻印器"，不是给别人看的"内容总结器"。**

这个差别决定一切：
- 不追求"覆盖原文所有要点"，追求"留下能在脑子里立住的那一块"
- 不允许"看起来很全面但实际记不住"
- 允许信心不足，但**信心不足必须先调研过**

合格标准：用户合上 HTML 三天后，凭记忆能回答出"这篇讲了什么 / 凭什么成立 / 跟其他怎么不一样 / 哪句话最戳"。做不到就是不合格。

---

## 1. 输入与边界

### 支持的输入

| 类型 | 处理路径 |
|---|---|
| 文章正文（粘贴） | 直接进入处理 |
| 文章链接（URL） | `scripts/fetch_article.py`：WebFetch → r.jina.ai 兜底 |
| YouTube 视频链接 | `scripts/fetch_youtube.py`：youtube-transcript-api → yt-dlp 兜底 |

### 不支持的输入（MVP 边界）

- B 站 / 抖音 / 小红书 / 播客等非 YouTube 视频 → 提示用户**先手工提供转录文本**
- 批量输入（一次多篇） → 一次只做一条
- 图片 / PDF / 截图 → 提示用户**先转成纯文本再来**

### 抓取失败的硬约束

**抓不到内容时必须停下来，禁止用模型先验硬上。**

- YouTube 字幕拿不到 / 抓到的不是目标视频 → 停，让用户提供转录或换视频
- 文章 paywall / 反爬 / 抓回来全是导航菜单 → 停，让用户粘贴正文
- 内容明显残缺（少于 300 字 / 视频少于 1 分钟有效转录） → 停

输入污染 = 认知污染。这条没有商量。

---

## 2. 6 步主流程

### Step 1 · 确认输入并抓取

对每种输入做对应处理：

- **粘贴正文**：直接进入 Step 2
- **文章 URL**：调用 `scripts/fetch_article.py`，把抓回来的正文前 200 字打印给用户确认
- **YouTube URL**：调用 `scripts/fetch_youtube.py`，把视频标题 + 字幕前 200 字打印给用户确认；时长 > 60 分钟时主动询问"全片处理还是分段处理"

抓取细则见 `references/input-handlers.md`。

### Step 2 · 通读 + 一句话定位

完整读完原文后，先写两件东西作为后续处理的锚：

1. **一句话定位**（≤30 字）：这一篇在讲什么、回应什么问题
2. **类型判定**：观点文 / 方法论 / 案例分析 / 教程 / 访谈 / 技术解析 / 评论 / 其他

类型会影响后续 5 项处理的侧重，详见各 reference 文件。

### Step 3 · 强制调研（差异化亮点必须，其他按需）

**这一步不能跳。** 在动手写五项之前，必须完成至少这一轮调研：

- **必做**：针对话题领域，用 web_search 检索 **3+ 个同生态、同类型、同主题**的其他内容，建立"默认认知"基线，供 Step 4 的"差异化亮点"使用
  - **同生态**：同样的内容圈层（如同样是 AI 工程访谈圈，找 a16z / Latent Space / Lenny's / Last Week in AI 这类同生态产物）
  - **同类型**：访谈对访谈、博客对博客、论文对论文，不要拿小红书帖子去和 podcast 对比
  - **同主题**：围绕这一篇的核心议题（不是宽泛领域），比如"AI 时代工程师的角色变化"，不是"AI"
  - **禁止**：用网络口水共识 / 短视频流行观点 / 朋友圈刻板印象当默认基线
- **按需做**：
  - 文中出现新造词或非主流术语 → 检索是否已有标准定义
  - 文中有反直觉论断 → 检索是否真的反共识
  - 文中引用了具体数据 / 案例 → 抽样核对至少 1 条

调研必须留痕（写入 `## 调研记录` 段落，HTML 渲染时不显示但保留在 MD 里），格式：

```markdown
## 调研记录（仅 MD 中保留，HTML 不渲染）
- 检索词：______
- 同生态来源：[标题](URL) / [标题](URL) / [标题](URL)
- 默认认知基线（一句话）：______
- 这一篇相对基线的真实差异（≥3 条简列）：______
```

**校验**：如果"默认认知基线"写出来跟"AI 让人失业 / AI 让人门槛更低 / AI 让 X 变得更容易"这种**网络口水**长得一模一样，**调研不合格，重做**。基线必须是同生态同类内容里**已经在反复讨论**的观点，差异化才有意义。

详见 `references/differentiation-frame.md`。

### Step 4 · 生成 5 项处理（写入 Markdown）

按 `assets/distill-template.md` 的固定骨架填，**章节标题、顺序、frontmatter 字段名一字不改**，渲染脚本和模型都按这个约定吃。

5 项的写作约束分别见：

| 项 | reference |
|---|---|
| 核心概念 | `references/pyramid-structure.md`（含术语层规范） |
| 行文逻辑（金字塔） | `references/pyramid-structure.md` |
| 差异化亮点 | `references/differentiation-frame.md` |
| 值得记住的话 | `references/quote-extraction.md` |
| 最简复述 | `references/recap-writing.md` |

### Step 5 · MD 自检（P0，必过）

对照 `references/quality-checklist.md` 跑一遍。任一 ❌ → 回到对应步骤补，禁止进入 Step 6。

关键硬指标：
- 5 个 H2 章节齐全、顺序正确、无空段
- 最简复述 ≤500 字（必须做 word count 校验），且**无任何 strong/em/b/mark 视觉强调标签**
- 行文逻辑顶层主张是**作者原话或贴近原话的翻译**，不是话题描述句
- 行文逻辑必须有 ASCII 金字塔图 + 论点-论据分层
- 金句**全部能在原文/字幕里 ctrl-F 命中**，视频金句必须配时间戳
- `## 调研记录` 非空，至少 3 个同生态来源 URL
- footer 自检数字与实际产物**一致**（不允许"信心不足 0 处"配空调研记录）
- 信心不足标注必须有调研记录配对，不允许裸标

### Step 6 · 渲染 HTML（按风格规范直接生成）

**不写渲染脚本，由模型直接读 MD 产出 HTML。** 必须严格遵守第 4 节"HTML 风格规范"。完整视觉锚定示例见 `references/html-style-spec.md`，模型生成时以那份示例为视觉参照。

---

## 3. 产物规范

| 产物 | 路径 | 是否必须 |
|---|---|---|
| Markdown 中间产物 | `<workdir>/<slug>-distill.md` | 必须 |
| HTML 最终产物 | `<workdir>/<slug>-distill.html` | 必须 |

`<slug>` 规则：取标题前 6 个有意义中文字 / 8 个英文单词，转 kebab-case，全小写。

交付时同时给两份，并用 `preview_url` 打开 HTML。

---

## 4. HTML 风格规范（硬约束，模型必须遵守）

### 4.1 结构

- 单文件 HTML5，所有 CSS 内联在 `<head><style>` 中，**零外部依赖**：不引 CDN、不引 Google Fonts、不引任何 JS
- 固定 7 块按顺序：
  ```
  <header>            元信息区
  <section data-block="concepts">       核心概念
  <section data-block="logic">          行文逻辑
  <section data-block="diff">           差异化亮点
  <section data-block="quotes">         值得记住的话
  <section data-block="recap">          最简复述
  <footer>            页脚
  ```
- HTML `lang="zh-CN"`，`<meta charset="UTF-8">`，`<meta name="viewport" content="width=device-width, initial-scale=1">`

### 4.2 配色（CSS 变量，命名固定）

```css
:root {
  --paper:  #FAF8F3;
  --ink:    #1A1A1A;
  --muted:  #6B6B6B;
  --accent: #B8742F;
  --rule:   #E5DFD3;
  --card:   #F2EEE5;
  --warn-bg:   #FFF8E0;
  --warn-line: #D4A017;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper:  #1C1A16;
    --ink:    #ECE6D8;
    --muted:  #A09A8A;
    --accent: #D69A55;
    --rule:   #3A362E;
    --card:   #26231D;
    --warn-bg:   #3A2F18;
    --warn-line: #D4A017;
  }
}
```

### 4.3 字体与排版

- 正文：`ui-serif, Georgia, "Source Han Serif SC", "Noto Serif CJK SC", serif`
- 标题 / UI / 标签：`-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif`
- 等宽（ASCII 图、术语原文）：`ui-monospace, "SF Mono", Menlo, Consolas, monospace`
- 正文宽度：`max-width: 720px; margin: 0 auto; padding: 64px 24px;`
- 行高：正文 1.8，标题 1.3
- 字号：H1 32px，H2 22px，H4 18px，正文 17px，最简复述 18px，金句 22px，meta 14px

### 4.4 5 个 section 的视觉处理（不允许自由发挥）

| Section | 视觉处理 |
|---|---|
| **核心概念** | CSS Grid 卡片：`grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`；每卡：粗体术语（无衬线 16px）+ 衬线一句话 + 灰色类比小字；卡片底色 `--card`、圆角 8px、内边距 20px |
| **行文逻辑** | 顶部 `<pre>` 包 ASCII 金字塔图（等宽、`overflow-x: auto`）；下方论点 `<h4>` 16px 加粗 + 琥珀色左边框 3px；论据 `<ul>` 缩进，每条 `<li>` 衬线 16px |
| **差异化亮点** | `display: grid; grid-template-columns: 1fr 1fr; gap: 16px;`；左列灰底（`--card`）"多数人会说"，右列白底 + 琥珀左边框 4px "这一篇说"；下方一行 `<small>` "为什么有价值"；移动端 ≤640px 堆叠为单列 |
| **值得记住的话** | `<blockquote>` 左 4px 琥珀竖条 + 左 padding 20px；引文衬线 22px、行高 1.6；下方 `<small>` 14px 灰字 "为什么值得记"；多个引用之间 32px 间距 |
| **最简复述** | 单栏 `<article>`，纯散文段落（`<p>`），无任何 ul/列表；左侧 4px 琥珀竖条贯穿整段；字号 18px、行高 1.9 |

### 4.5 信心不足标注

- **就近渲染**，不集中到底部
- HTML 结构：
  ```html
  <aside class="warn">
    <strong>⚠️ 信心不足</strong>
    <dl>
      <dt>不确定点</dt><dd>……</dd>
      <dt>已调研</dt><dd>……</dd>
      <dt>推测依据</dt><dd>……</dd>
      <dt>建议核对</dt><dd>……</dd>
    </dl>
  </aside>
  ```
- 样式：`background: var(--warn-bg); border-left: 4px solid var(--warn-line); padding: 16px 20px; border-radius: 4px;`

### 4.6 Header / Footer

- **Header**：H1 标题 + meta 行（`📄 文章` / `🎬 视频` icon + 来源链接 + 处理日期 + 字数/时长）+ 一句话定位（衬线 19px、灰色 muted、italic）
- **Footer**：小字 `本卡片基于 nows-content-distill 生成 · {fetched_at}` + 自检摘要（5 项是否都有内容、信心不足标注数、复述字数）

### 4.7 打印样式

```css
@media print {
  :root { --paper: #fff; --ink: #000; --card: #f5f5f5; }
  footer, aside.warn { break-inside: avoid; }
  section { break-inside: avoid; }
  body { padding: 0; }
}
```

完整可参照 HTML 示例见 `references/html-style-spec.md`，模型生成时**以那份为视觉锚**。

---

## 5. 反模式（禁止）

- ❌ 跳过 Step 3 的调研直接写差异化亮点
- ❌ 用网络口水共识当"默认认知基线"（必须同生态同类内容）
- ❌ 抓取失败时用模型先验硬上（必须停下来）
- ❌ 金句改写或意译（必须逐字摘录）
- ❌ 金句拼接两句不相邻的话伪装成一句
- ❌ 金句无法在原文/字幕里 ctrl-F 命中（疑似模型生成）
- ❌ 视频金句不配时间戳
- ❌ 最简复述用项目符号 / 列表（必须连贯散文）
- ❌ 最简复述用 strong / em / b / mark 等视觉强调标签
- ❌ 行文逻辑顶层主张写成"本篇讨论 X"的话题描述句
- ❌ 行文逻辑只列要点不分层（必须三层金字塔）
- ❌ 核心概念把同一个概念拆成两张卡（如"高能动性" + "高能动性 + 高问责"）
- ❌ 核心概念把"金句 / 文化口号"放进来当术语（应放金句章）
- ❌ 核心概念超过 7 个（认知不下了）
- ❌ HTML 引外部资源（CDN / 字体 / JS / 图片）
- ❌ HTML 偏离 5 个 section 的视觉处理（h2 改色、diff-pair 改成平铺等）
- ❌ 信心不足标注超过 3 处（说明这篇不适合 distill，应换内容）
- ❌ footer 自检写"信心不足 0 处"但调研记录段落空（双重违规）
- ❌ 一篇 HTML 当摘要工具的产物输出（这是认知刻印不是摘要）

---


