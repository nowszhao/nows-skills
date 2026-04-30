#!/usr/bin/env python3
"""lint_vault.py — wiki health check for an Obsidian vault.

Usage: lint_vault.py <vault_path> [--json]

Reports:
  - red wikilinks (unresolved targets)
  - orphans (no inbound links, not in a MOC)
  - notes missing required frontmatter fields (title, type, created, updated)
  - duplicate slugs
  - stale notes (updated >180 days ago) — informational

Read-only. Prints a markdown report to stdout.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
EMBED_RE = re.compile(r"\!\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")

REQUIRED_FIELDS = ["title", "type", "created", "updated"]


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    raw = m.group(1)
    fm: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm


def slugify_link(target: str) -> str:
    t = target.strip()
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.split("/")[-1].lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-days", type=int, default=180)
    args = ap.parse_args()

    vault: Path = args.vault.resolve()
    if not vault.is_dir():
        print(f"error: {vault} not a directory", file=sys.stderr)
        return 2

    md_files: list[Path] = []
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git", "node_modules"}]
        for f in files:
            if f.endswith(".md"):
                md_files.append(Path(root) / f)

    basename_set = {p.stem.lower() for p in md_files}
    basename_to_paths: dict[str, list[Path]] = defaultdict(list)
    for p in md_files:
        basename_to_paths[p.stem.lower()].append(p)

    red_links: list[tuple[str, str]] = []  # (source, target)
    inbound: dict[str, set[str]] = defaultdict(set)
    missing_fm: list[tuple[str, list[str]]] = []
    stale: list[tuple[str, str]] = []
    cutoff = datetime.now() - timedelta(days=args.stale_days)

    moc_links: set[str] = set()

    for p in md_files:
        rel = str(p.relative_to(vault))
        text = read_text(p)
        fm = parse_frontmatter(text)
        missing = [f for f in REQUIRED_FIELDS if f not in fm]
        if missing:
            missing_fm.append((rel, missing))
        if fm.get("updated"):
            try:
                dt = datetime.strptime(fm["updated"].strip().strip("\"'"), "%Y-%m-%d")
                if dt < cutoff:
                    stale.append((rel, fm["updated"]))
            except ValueError:
                pass

        body = text[FRONTMATTER_RE.match(text).end():] if FRONTMATTER_RE.match(text) else text
        is_moc = fm.get("type", "").strip().strip("\"'") == "moc"
        for m in WIKILINK_RE.finditer(body):
            target = slugify_link(m.group(1))
            if target not in basename_set:
                red_links.append((rel, m.group(1)))
            else:
                inbound[target].add(rel)
                if is_moc:
                    moc_links.add(target)
        for m in EMBED_RE.finditer(body):
            target = slugify_link(m.group(1))
            if target not in basename_set:
                # embeds to assets are fine; only flag if it's .md
                if target.endswith(".md") or "." not in m.group(1).split("/")[-1]:
                    red_links.append((rel, m.group(1)))

    orphans: list[str] = []
    for p in md_files:
        slug = p.stem.lower()
        if inbound.get(slug):
            continue
        if slug in moc_links:
            continue
        orphans.append(str(p.relative_to(vault)))

    duplicates = {k: [str(x.relative_to(vault)) for x in v] for k, v in basename_to_paths.items() if len(v) > 1}

    if args.json:
        print(json.dumps({
            "red_links": red_links,
            "orphans": orphans,
            "missing_frontmatter_fields": missing_fm,
            "duplicates": duplicates,
            "stale": stale,
        }, ensure_ascii=False, indent=2))
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    out: list[str] = []
    W = out.append
    W(f"# Vault lint — {today}")
    W("")
    W(f"- Red links: **{len(red_links)}**")
    W(f"- Orphans: **{len(orphans)}**")
    W(f"- Notes missing required frontmatter: **{len(missing_fm)}**")
    W(f"- Duplicate slugs: **{len(duplicates)}**")
    W(f"- Stale notes (>{args.stale_days}d): **{len(stale)}**")
    W("")

    W(f"## Red links (first 50 of {len(red_links)})")
    W("")
    for src, tgt in red_links[:50]:
        W(f"- `{src}` → `[[{tgt}]]`")
    W("")

    W(f"## Orphans (first 50 of {len(orphans)})")
    W("")
    for o in orphans[:50]:
        W(f"- `{o}`")
    W("")

    W(f"## Missing frontmatter fields (first 50 of {len(missing_fm)})")
    W("")
    for path, missing in missing_fm[:50]:
        W(f"- `{path}` — missing: {', '.join(missing)}")
    W("")

    W("## Duplicate slugs")
    W("")
    if duplicates:
        for slug, paths in list(duplicates.items())[:30]:
            W(f"- `{slug}`:")
            for x in paths:
                W(f"  - `{x}`")
    else:
        W("_none_")
    W("")

    W(f"## Stale notes (first 30 of {len(stale)})")
    W("")
    for path, upd in stale[:30]:
        W(f"- `{path}` — last updated `{upd}`")
    W("")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
