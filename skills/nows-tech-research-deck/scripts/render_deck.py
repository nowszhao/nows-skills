#!/usr/bin/env python3
"""
render_deck.py · Phase B 渲染脚本

流程：
  1. 读取 Phase A 产出的 research.md
  2. 解析成 section 树
  3. 按 engine-routing.md 的规则，决定每个 section 走本 skill 内建基础 layout
     还是本 skill 的 extra layout
  4. 生成一个 render-plan.json（Agent 再据此用 assets/base-template.html 填充）

**本脚本不直接写出最终 HTML** —— 因为最终填充需要 Agent 结合
assets/base-template.html 做上下文感知的文字排版。本脚本只负责"拆 + 路由"，
把计划交给 Agent 执行。

用法：
  python3 render_deck.py \
    --research ./workdir/dbt-research.md \
    --theme 靛蓝瓷 \
    --outplan ./workdir/dbt-render-plan.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


# ──────────────────────────────────────────────────────────────────
# 1. 主题色 → 内建 deck 主题 key 映射
# ──────────────────────────────────────────────────────────────────
THEME_MAP = {
    "墨水经典": "ink-classic",
    "靛蓝瓷": "indigo-porcelain",
    "森林墨": "forest-ink",
    "牛皮纸": "kraft",
    "沙丘": "dune",
}


# ──────────────────────────────────────────────────────────────────
# 2. section → 页面类型 分类器
#    规则来自 references/engine-routing.md
#    优先级：高优先级规则先匹配；启发式规则放最后
# ──────────────────────────────────────────────────────────────────

# 明确跳过的 section（Appendix 相关不入 deck 正文）
SKIP_HEADINGS = {
    "meta",
    "appendix · 来源",
    "appendix",
    "待验证问题",
    "phase a 自检清单（p0，必过）",
    "phase a 自检清单",
    "官方（s 级）",
    "社区（a/b 级）",
    "批评 / 反面（d 级但有用）",
}

# 标题关键词 → 页面类型（高优先级）
HEADING_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^act\s*[1-4]", re.I), "chapter"),
    (re.compile(r"架构.*图|核心架构"), "architecture-page"),
    (re.compile(r"竞品.*矩阵|竞品.*对比"), "comparison-table-page"),
    (re.compile(r"核心概念"), "magazine-mix"),
    (re.compile(r"模块.*职责|职责表"), "magazine-mix"),
    (re.compile(r"生命周期"), "magazine-mix"),
    (re.compile(r"反面样本|没有它"), "magazine-mix"),
    (re.compile(r"关键痛点|痛点"), "text-image"),
    (re.compile(r"诞生时间线|时间线"), "big-stat"),
    (re.compile(r"一句话定位"), "quote"),
    (re.compile(r"设计取舍"), "text-image"),
    (re.compile(r"差异化"), "before-after"),
    (re.compile(r"不该选|反用例"), "text-image"),
    (re.compile(r"^4\.1|开发"), "code-demo-page"),
    (re.compile(r"^4\.2|测试"), "code-demo-page"),
    (re.compile(r"^4\.3|发布|ci"), "code-demo-page"),
    (re.compile(r"^4\.4|调度|运行时"), "code-demo-page"),
    (re.compile(r"^4\.5|进阶示例"), "code-demo-page"),
]


def classify_section(heading: str, body: str) -> str:
    h = heading.lower().strip()

    # 1. 优先命中标题规则
    for pat, ptype in HEADING_RULES:
        if pat.search(h):
            return ptype

    # 2. body 含 fenced code block + 编程语言标签 → code-demo-page
    code_blocks = re.findall(r"```(\w+)", body)
    if any(
        lang.lower() in {"sql", "python", "py", "yaml", "yml", "bash", "sh", "ts", "go"}
        for lang in code_blocks
    ):
        return "code-demo-page"

    # 3. body 含 ASCII 框线字符（非 timeline）→ architecture-page
    if re.search(r"[┌┐└┘╔╗╚╝]", body) and re.search(r"[├┤┬┴┼]", body):
        return "architecture-page"

    # 4. body 含完整 markdown 表格（3+ 行）且有"维度/总分"→ comparison-table-page
    if re.search(r"\|\s*维度\s*\|", body) and re.search(r"\|\s*总分\s*\|", body):
        return "comparison-table-page"

    # 5. body 以 > 起头 → quote
    if body.strip().startswith(">"):
        return "quote"

    # 6. 默认
    return "text-image"


# ──────────────────────────────────────────────────────────────────
# 3. 解析 markdown → sections
# ──────────────────────────────────────────────────────────────────
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def parse_sections(md: str) -> list[dict]:
    """按 ## 和 ### 切分，每段保留 heading + body。"""
    lines = md.splitlines(keepends=True)
    sections: list[dict] = []
    current = None

    for line in lines:
        m = re.match(r"^(#{2,3})\s+(.+)$", line)
        if m:
            if current:
                sections.append(current)
            current = {
                "level": len(m.group(1)),
                "heading": m.group(2).strip(),
                "body": "",
            }
        else:
            if current is not None:
                current["body"] += line
    if current:
        sections.append(current)

    return sections


# ──────────────────────────────────────────────────────────────────
# 4. 构建 render plan
# ──────────────────────────────────────────────────────────────────
def build_plan(sections: list[dict], theme: str) -> dict:
    pages: list[dict] = []

    # 封面（从 Meta 的"产品名"和"一句话定位"里抽）
    meta_body = ""
    for s in sections:
        if s["heading"].lower() == "meta":
            meta_body = s["body"]
            break

    product_m = re.search(r"\*\*产品名\*\*[:：]\s*(.+)", meta_body)
    tagline_m = re.search(r"一句话定位.*?[:：]\s*(.+)", meta_body, re.DOTALL)

    pages.append(
        {
            "type": "cover",
            "layout": "cover",
            "engine": "base",
            "title": (product_m.group(1).strip() if product_m else "Untitled"),
            "subtitle": (tagline_m.group(1).strip().splitlines()[0] if tagline_m else ""),
        }
    )

    # 正文
    for s in sections:
        if s["heading"].lower().strip() in SKIP_HEADINGS:
            continue

        ptype = classify_section(s["heading"], s["body"])
        page = {
            "type": ptype,
            "layout": ptype,
            "engine": "extra" if ptype.endswith("-page") else "base",
            "title": s["heading"],
            "body_excerpt": s["body"][:200],
            "body_full": s["body"],
        }
        pages.append(page)

    # 结束页
    pages.append(
        {
            "type": "cover",
            "layout": "cover-end",
            "engine": "base",
            "title": "Thanks",
            "subtitle": "Q&A / Discussion",
        }
    )

    return {
        "theme": theme,
        "theme_key": THEME_MAP.get(theme, "indigo-porcelain"),
        "total_pages": len(pages),
        "pages": pages,
        "notes": [
            "engine=base 的页面交由 Agent 使用 assets/base-template.html 填充",
            "engine=extra 的页面使用本 skill assets/extra-layouts/ 下对应 HTML 模板",
            "所有扩展 layout 与基础模板共用 CSS 变量 (--ink, --paper, --accent ...)",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build render plan from research.md")
    ap.add_argument("--research", required=True, help="Phase A research.md path")
    ap.add_argument(
        "--theme",
        default="靛蓝瓷",
        choices=list(THEME_MAP.keys()),
    )
    ap.add_argument("--outplan", required=True, help="output render-plan.json path")
    args = ap.parse_args()

    research_path = pathlib.Path(args.research).expanduser().resolve()
    if not research_path.exists():
        print(f"[ERROR] research.md not found: {research_path}", file=sys.stderr)
        return 1

    md = research_path.read_text(encoding="utf-8")
    sections = parse_sections(md)
    plan = build_plan(sections, args.theme)

    out = pathlib.Path(args.outplan).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # 打印摘要给 Agent
    print(f"[ok] render plan written: {out}")
    print(f"[ok] total pages: {plan['total_pages']}")
    for i, p in enumerate(plan["pages"], 1):
        print(f"  {i:02d}  [{p['engine']:>7s}]  {p['layout']:<24s}  {p.get('title','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
