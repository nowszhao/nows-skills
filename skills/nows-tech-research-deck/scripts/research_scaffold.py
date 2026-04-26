#!/usr/bin/env python3
"""
research_scaffold.py · Phase A 启动脚本

根据 6 问的回答，生成 <product>-research.md 骨架，并在 Phase A 流水线的
每个 step 追加一个 TODO marker，方便 Agent 按 checklist 推进。

用法：
  python3 research_scaffold.py \
    --product "dbt" \
    --website "https://www.getdbt.com/" \
    --repo "https://github.com/dbt-labs/dbt-core" \
    --docs "https://docs.getdbt.com/" \
    --audience "团队分享" \
    --depth standard \
    --competitors "SQLMesh,Dataform,Airflow+SQL" \
    --demo pseudo \
    --theme 靛蓝瓷 \
    --outdir ./workdir

脚本零第三方依赖（只用标准库）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys


TEMPLATE_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "assets"
    / "research-template.md"
)


def slugify(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^\w\-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "product"


def fill_template(template: str, ctx: dict) -> str:
    """
    极简 placeholder 填充：替换形如 `<Product Name>`, `<YYYY-MM-DD>` 的尖括号占位符。
    未在 ctx 中定义的占位符保持原样，由 Agent 在 Phase A 手动填充。
    """
    out = template
    out = out.replace("<Product Name>", ctx["product"])
    out = out.replace("<https://...>", f"<{ctx['website']}>", 1)
    out = out.replace("<https://github.com/.../...>", f"<{ctx['repo']}>", 1)
    out = out.replace("<https://docs.../...>", f"<{ctx['docs']}>", 1)
    out = out.replace("<YYYY-MM-DD>", ctx["date"])
    out = out.replace(
        "<CTO 汇报 / 团队分享 / 外部布道 / 社招面试 / 学习笔记>", ctx["audience"]
    )
    out = out.replace("<quick | standard | deep>", ctx["depth"])
    out = out.replace(
        "<墨水经典 / 靛蓝瓷 / 森林墨 / 牛皮纸 / 沙丘>", ctx["theme"]
    )

    # 把竞品名注入对比矩阵表头
    comps = ctx["competitors"]
    while len(comps) < 3:
        comps.append(f"<竞品 {chr(ord('A') + len(comps))}>")
    out = out.replace("<竞品 A>", comps[0])
    out = out.replace("<竞品 B>", comps[1])
    out = out.replace("<竞品 C>", comps[2])
    out = out.replace("<Product>", ctx["product"])

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase A research scaffold.")
    parser.add_argument("--product", required=True)
    parser.add_argument("--website", required=True)
    parser.add_argument("--repo", default="")
    parser.add_argument("--docs", default="")
    parser.add_argument("--audience", default="团队分享")
    parser.add_argument(
        "--depth", choices=["quick", "standard", "deep"], default="standard"
    )
    parser.add_argument(
        "--competitors",
        default="",
        help="逗号分隔的竞品名；留空则保持占位符交给 Agent 挑选",
    )
    parser.add_argument(
        "--demo", choices=["real", "pseudo", "none"], default="pseudo"
    )
    parser.add_argument(
        "--theme",
        default="靛蓝瓷",
        choices=["墨水经典", "靛蓝瓷", "森林墨", "牛皮纸", "沙丘"],
    )
    parser.add_argument("--outdir", default=".")
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"[ERROR] Template not found: {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    template = TEMPLATE_PATH.read_text(encoding="utf-8")

    ctx = {
        "product": args.product,
        "website": args.website,
        "repo": args.repo,
        "docs": args.docs,
        "date": dt.date.today().isoformat(),
        "audience": args.audience,
        "depth": args.depth,
        "theme": args.theme,
        "competitors": [c.strip() for c in args.competitors.split(",") if c.strip()],
        "demo": args.demo,
    }

    filled = fill_template(template, ctx)

    # 头部追加 Agent 可读的执行上下文块，供 Phase A 推进时回看
    preface = "\n".join(
        [
            "<!--",
            "  Phase A Execution Context",
            f"  product     : {ctx['product']}",
            f"  website     : {ctx['website']}",
            f"  repo        : {ctx['repo']}",
            f"  docs        : {ctx['docs']}",
            f"  date        : {ctx['date']}",
            f"  audience    : {ctx['audience']}",
            f"  depth       : {ctx['depth']}",
            f"  competitors : {', '.join(ctx['competitors']) or '(auto-pick)'}",
            f"  demo_mode   : {ctx['demo']}",
            f"  theme       : {ctx['theme']}",
            "-->",
            "",
        ]
    )
    filled = preface + filled

    outdir = pathlib.Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    outpath = outdir / f"{slugify(args.product)}-research.md"
    outpath.write_text(filled, encoding="utf-8")

    print(str(outpath))
    return 0


if __name__ == "__main__":
    sys.exit(main())
