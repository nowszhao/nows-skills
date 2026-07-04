#!/usr/bin/env python3
"""
Render episode_content.md to HTML that is FAITHFUL to its Markdown *preview*,
for 小宇宙 Show Notes injection.

⚠️ 关键：发布的 Show Notes 必须和小宇宙后台「预览」看到的一模一样——
保留 **加粗**、段落/换行结构、以及顶部的原文链接部分。因此不能把 Markdown
当成纯文本去 strip，而要把它渲染成 HTML，再用 `innerHTML` 注入（见 SKILL Phase 4.5）。

直接把原始 Markdown 源码（带着 `**`、`- `、`---` 字面量）注入会显示成乱码；
只 strip 掉所有标记变成纯文本又会丢掉加粗和段落结构。正确做法是「渲染成 HTML」。

渲染规则（覆盖 episode_content.md 的全部语法，且对小宇宙 contenteditable 稳健）：
  #  标题          -> 跳过（它已放在小宇宙独立的「标题」字段）
  ## 小节标题      -> <p><strong>小节</strong></p>            （加粗，避免 <h2> 被过滤）
  **加粗**         -> <strong>加粗</strong>
  - / * 列表项     -> <p>• <strong>术语</strong>：描述</p>     （每段一个，bullet 字符 + 加粗，
                                                                  即使 <ul> 被过滤也能保留bullet和换行）
  空行             -> 块分隔
  ---              -> <hr>
  普通行           -> <p>行内加粗处理</p>                       （逐行成块，保留换行）
  裸 URL 行        -> 原样保留为文本（可复制的链接）

输出是 HTML 片段（不含外层 <html>），直接赋给 contenteditable 的 innerHTML。

Usage:
    python3 scripts/extract_show_notes.py episode_content.md > show_notes.html
"""
import sys
import re


def inline(text):
    """把行内 Markdown 渲染成 HTML：加粗 / 斜体 / 行内代码。"""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+?)\*(?!\*)', r'<em>\1</em>', text)
    text = text.replace('`', '')
    return text


def render(md_path):
    with open(md_path, encoding='utf-8') as f:
        lines = f.read().split('\n')

    blocks = []
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if s == '':
            i += 1
            continue
        if s.startswith('# '):
            # H1 标题 -> 跳过（已在小宇宙「标题」字段）
            i += 1
            continue
        if s.startswith('## '):
            blocks.append('<p><strong>' + inline(s[3:].strip()) + '</strong></p>')
            i += 1
            continue
        if s.startswith('---'):
            blocks.append('<hr>')
            i += 1
            continue
        if s.startswith('- ') or s.startswith('* '):
            # 列表项：每条单独成段，带 • bullet + 行内加粗
            while i < n and lines[i].strip().startswith(('- ', '* ')):
                item = lines[i].strip()[2:].strip()
                blocks.append('<p>• ' + inline(item) + '</p>')
                i += 1
            continue
        # 普通行：逐行成块，保留换行 + 行内加粗
        blocks.append('<p>' + inline(s) + '</p>')
        i += 1

    return '\n'.join(blocks)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: extract_show_notes.py <episode_content.md>")
        sys.exit(1)
    print(render(sys.argv[1]))
