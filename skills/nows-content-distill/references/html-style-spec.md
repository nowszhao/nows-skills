# HTML Style Spec · 完整视觉锚定

**模型生成 HTML 时以本文件的示例为视觉参照。** 不要自由发挥配色、版式、字号。

## 一、设计原则（先看再写）

1. **Reader Mode + 知识卡片**：参照 Readwise Reader / Notion，单栏、留白大、低密度，反复读不累
2. **零外部依赖**：所有 CSS 内联，不引 CDN / Google Fonts / JS / 图片
3. **可重复 = 风格固定**：颜色、字体、间距用 CSS 变量，5 个 section 视觉处理写死
4. **认知优先于装饰**：所有视觉元素服务"留下心理表征"，不为美而美

## 二、完整可参照 HTML 示例

下面这份是**视觉锚**，模型生成时按这套 CSS 变量、字体栈、5 个 section 的视觉处理来。内容部分按真实 distill 内容替换。

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{title}} · Distill</title>
<style>
  :root {
    --paper:     #FAF8F3;
    --ink:       #1A1A1A;
    --muted:     #6B6B6B;
    --accent:    #B8742F;
    --rule:      #E5DFD3;
    --card:      #F2EEE5;
    --warn-bg:   #FFF8E0;
    --warn-line: #D4A017;

    --font-serif: ui-serif, Georgia, "Source Han Serif SC", "Noto Serif CJK SC", serif;
    --font-sans:  -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    --font-mono:  ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --paper:     #1C1A16;
      --ink:       #ECE6D8;
      --muted:     #A09A8A;
      --accent:    #D69A55;
      --rule:      #3A362E;
      --card:      #26231D;
      --warn-bg:   #3A2F18;
      --warn-line: #D4A017;
    }
  }

  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body {
    font-family: var(--font-serif);
    background: var(--paper);
    color: var(--ink);
    font-size: 17px;
    line-height: 1.8;
    -webkit-font-smoothing: antialiased;
  }
  main {
    max-width: 720px;
    margin: 0 auto;
    padding: 64px 24px 96px;
  }

  /* ---------- Header ---------- */
  header.distill-head { border-bottom: 1px solid var(--rule); padding-bottom: 32px; margin-bottom: 48px; }
  header.distill-head h1 {
    font-family: var(--font-sans);
    font-size: 32px;
    line-height: 1.3;
    margin: 0 0 12px;
    letter-spacing: -0.01em;
  }
  .meta {
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--muted);
    margin-bottom: 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
  .meta a { color: var(--muted); text-decoration: none; border-bottom: 1px solid var(--rule); }
  .meta a:hover { color: var(--accent); border-color: var(--accent); }
  .one-liner {
    font-style: italic;
    color: var(--muted);
    font-size: 19px;
    line-height: 1.6;
    margin: 0;
  }

  /* ---------- Section base ---------- */
  section { margin: 56px 0; }
  section > h2 {
    font-family: var(--font-sans);
    font-size: 22px;
    line-height: 1.3;
    margin: 0 0 24px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--rule);
    letter-spacing: -0.005em;
  }

  /* ---------- 1. 核心概念 ---------- */
  .concepts-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px;
  }
  .concept-card {
    background: var(--card);
    border-radius: 8px;
    padding: 20px;
  }
  .concept-card .term {
    font-family: var(--font-sans);
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 8px;
    color: var(--ink);
  }
  .concept-card .term .tag-new {
    font-family: var(--font-sans);
    font-size: 11px;
    color: var(--accent);
    background: transparent;
    border: 1px solid var(--accent);
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: 6px;
    font-weight: normal;
    vertical-align: middle;
  }
  .concept-card .gloss { font-size: 15px; line-height: 1.7; margin: 0 0 8px; }
  .concept-card .analogy {
    font-size: 13px;
    color: var(--muted);
    line-height: 1.6;
    margin: 0;
    font-family: var(--font-sans);
  }

  /* ---------- 2. 行文逻辑 ---------- */
  .pyramid {
    background: var(--card);
    border-radius: 8px;
    padding: 20px;
    overflow-x: auto;
    font-family: var(--font-mono);
    font-size: 13px;
    line-height: 1.5;
    margin: 0 0 32px;
    white-space: pre;
  }
  .logic-claim {
    font-family: var(--font-sans);
    font-size: 18px;
    font-weight: 600;
    border-left: 4px solid var(--accent);
    padding: 4px 0 4px 16px;
    margin: 0 0 24px;
  }
  .argument { margin: 0 0 24px; }
  .argument h4 {
    font-family: var(--font-sans);
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 8px;
    padding-left: 12px;
    border-left: 3px solid var(--accent);
  }
  .argument ul { margin: 0; padding-left: 28px; }
  .argument li { margin: 6px 0; font-size: 16px; }

  /* ---------- 3. 差异化亮点 ---------- */
  .diff-item { margin: 0 0 32px; }
  .diff-item h3 {
    font-family: var(--font-sans);
    font-size: 17px;
    margin: 0 0 12px;
  }
  .diff-pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 12px;
  }
  .diff-pair .col {
    padding: 16px 18px;
    border-radius: 6px;
    font-size: 15px;
    line-height: 1.7;
  }
  .diff-pair .col .label {
    font-family: var(--font-sans);
    font-size: 12px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    display: block;
    margin-bottom: 6px;
  }
  .diff-pair .col.default { background: var(--card); }
  .diff-pair .col.unique  { background: transparent; border-left: 4px solid var(--accent); padding-left: 14px; }
  .diff-why {
    font-size: 14px;
    color: var(--muted);
    font-family: var(--font-sans);
    margin: 0;
  }
  .diff-why strong { color: var(--ink); font-weight: 600; }
  @media (max-width: 640px) {
    .diff-pair { grid-template-columns: 1fr; }
  }

  /* ---------- 4. 值得记住的话 ---------- */
  .quote-block { margin: 0 0 32px; }
  .quote-block blockquote {
    margin: 0 0 8px;
    padding: 4px 0 4px 20px;
    border-left: 4px solid var(--accent);
    font-family: var(--font-serif);
    font-size: 22px;
    line-height: 1.6;
    color: var(--ink);
    font-style: normal;
  }
  .quote-block .why {
    font-family: var(--font-sans);
    font-size: 14px;
    color: var(--muted);
    padding-left: 24px;
    margin: 0;
  }
  .quote-block .why strong { color: var(--ink); font-weight: 600; }
  .quote-block .source {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--muted);
    padding-left: 24px;
    display: block;
    margin-top: 4px;
  }

  /* ---------- 5. 最简复述 ---------- */
  article.recap {
    border-left: 4px solid var(--accent);
    padding: 4px 0 4px 24px;
  }
  article.recap p {
    font-size: 18px;
    line-height: 1.9;
    margin: 0 0 18px;
  }
  article.recap p:last-child { margin-bottom: 0; }

  /* ---------- 信心不足标注 ---------- */
  aside.warn {
    background: var(--warn-bg);
    border-left: 4px solid var(--warn-line);
    padding: 16px 20px;
    border-radius: 4px;
    margin: 16px 0;
    font-family: var(--font-sans);
    font-size: 14px;
    line-height: 1.7;
  }
  aside.warn strong { display: block; margin-bottom: 8px; font-size: 15px; }
  aside.warn dl { margin: 0; }
  aside.warn dt {
    display: inline-block;
    width: 80px;
    color: var(--muted);
    vertical-align: top;
  }
  aside.warn dd { display: inline; margin: 0; }
  aside.warn dd::after { content: ""; display: block; height: 4px; }

  /* ---------- Footer ---------- */
  footer.distill-foot {
    margin-top: 80px;
    padding-top: 24px;
    border-top: 1px solid var(--rule);
    font-family: var(--font-sans);
    font-size: 13px;
    color: var(--muted);
    line-height: 1.7;
  }
  footer.distill-foot .selfcheck {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 8px;
  }
  footer.distill-foot .selfcheck span {
    background: var(--card);
    padding: 4px 10px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 12px;
  }

  /* ---------- Print ---------- */
  @media print {
    :root { --paper: #fff; --ink: #000; --card: #f5f5f5; }
    body { font-size: 12pt; }
    main { padding: 0; max-width: none; }
    section, aside.warn, .quote-block, article.recap { break-inside: avoid; }
    footer.distill-foot { display: none; }
  }
</style>
</head>
<body>
<main>

<header class="distill-head">
  <h1>{{title}}</h1>
  <div class="meta">
    <span>📄 文章</span>
    <a href="{{source_url}}">{{source_url_short}}</a>
    <span>{{fetched_at}}</span>
    <span>原文 {{word_count}} 字</span>
  </div>
  <p class="one-liner">{{one_liner}}</p>
</header>

<!-- 1. 核心概念 -->
<section data-block="concepts">
  <h2>核心概念</h2>
  <div class="concepts-grid">
    <div class="concept-card">
      <p class="term">术语 A <span class="tag-new">新</span></p>
      <p class="gloss">一句话人话解释，≤30 字。</p>
      <p class="analogy">类比：……</p>
    </div>
    <div class="concept-card">
      <p class="term">术语 B</p>
      <p class="gloss">一句话人话解释。</p>
    </div>
    <!-- ... -->
  </div>
</section>

<!-- 2. 行文逻辑 -->
<section data-block="logic">
  <h2>行文逻辑</h2>
  <pre class="pyramid">                    ┌──────────────────────────────┐
                    │      顶层主张，≤30 字          │
                    └───────────────┬──────────────┘
                                    │
            ┌───────────────────────┼──────────────────────┐
            ▼                       ▼                      ▼
    ┌──────────────┐        ┌──────────────┐       ┌──────────────┐
    │ 论点 A        │        │ 论点 B        │       │ 论点 C        │
    └──────┬───────┘        └──────┬───────┘       └──────┬───────┘
           │                       │                      │
           ▼                       ▼                      ▼
        论据 a1/a2/a3           论据 b1/b2              论据 c1/c2</pre>

  <p class="logic-claim">顶层主张写在这里，必须可证伪。</p>

  <div class="argument">
    <h4>论点 A — 论点标题</h4>
    <ul>
      <li>论据 a1：……</li>
      <li>论据 a2：……</li>
    </ul>
  </div>
  <!-- 更多 argument ... -->
</section>

<!-- 3. 差异化亮点 -->
<section data-block="diff">
  <h2>差异化亮点</h2>

  <div class="diff-item">
    <h3>亮点 1：一句话标题</h3>
    <div class="diff-pair">
      <div class="col default">
        <span class="label">多数人会说</span>
        ……
      </div>
      <div class="col unique">
        <span class="label">这一篇说</span>
        ……
      </div>
    </div>
    <p class="diff-why"><strong>为什么有价值：</strong>……</p>
  </div>

  <!-- 信心不足就近渲染示例 -->
  <aside class="warn">
    <strong>⚠️ 信心不足</strong>
    <dl>
      <dt>不确定点</dt><dd>……</dd>
      <dt>已调研</dt><dd>检索词 / <a href="#">来源 1</a> / <a href="#">来源 2</a></dd>
      <dt>推测依据</dt><dd>……</dd>
      <dt>建议核对</dt><dd>……</dd>
    </dl>
  </aside>
</section>

<!-- 4. 值得记住的话 -->
<section data-block="quotes">
  <h2>值得记住的话</h2>

  <div class="quote-block">
    <blockquote>原文金句逐字摘录。</blockquote>
    <p class="why"><strong>为什么值得记：</strong>戳到了 X 普遍误区。</p>
  </div>

  <div class="quote-block">
    <blockquote>另一句金句。</blockquote>
    <p class="why"><strong>为什么值得记：</strong>揭示了 Y 核心机制。</p>
    <span class="source">视频 [12:34]</span>
  </div>
</section>

<!-- 5. 最简复述 -->
<section data-block="recap">
  <h2>最简复述</h2>
  <article class="recap">
    <p>第一段：问题。这一篇在回应什么？……</p>
    <p>第二段：主张。作者的核心判断是……</p>
    <p>第三段：证据。作者凭什么这么说？最有说服力的论据是……</p>
    <p>第四段：结论。所以呢？读者应该……</p>
  </article>
</section>

<footer class="distill-foot">
  <div>本卡片基于 nows-content-distill 生成 · {{fetched_at}}</div>
  <div class="selfcheck">
    <span>5 项齐全 ✓</span>
    <span>信心不足 0 处</span>
    <span>复述 487 字</span>
  </div>
</footer>

</main>
</body>
</html>
```

## 三、生成时的取舍指南

- **核心概念只有 3 个**：grid 自动收缩，不要硬塞占位卡
- **没有信心不足标注**：直接不渲染 `<aside class="warn">`，不要留空容器
- **金句是事实型**：在 `.why` 后面追加 `<span class="source">` 显示出处
- **视频内容**：header meta 的 `📄 文章` 改为 `🎬 视频`，字数 / 时长字段对应替换
- **打印场景**：footer 的 selfcheck 信息会自动隐藏，不需要单独处理

## 四、严禁的视觉自由发挥

- ❌ 改 CSS 变量名
- ❌ 引外部字体 / 图片 / 图标库
- ❌ 加 emoji 装饰（除 header meta 的 📄 / 🎬 外）
- ❌ 加动画 / hover 特效（除链接颜色变化外）
- ❌ 改 5 个 section 的视觉处理（grid 卡片 / pyramid pre / 左右对照 / blockquote / 单栏 recap）
- ❌ 加 sidebar / TOC / 浮动导航
