#!/usr/bin/env python3
"""audit_vault.py — read-only audit of an Obsidian vault.

Usage: audit_vault.py <vault_path> [--json]

Prints a markdown report to stdout covering:
  - note count, folder histogram, file-size distribution
  - notes without frontmatter
  - wikilink graph: top targets, red links (targets that do not resolve),
    orphans (no inbound/outbound links)
  - duplicate filenames / slugs
  - top tags, top domains (from frontmatter)
  - attachment counts
  - oldest / newest / largest notes

Does NOT modify the vault.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
EMBED_RE = re.compile(r"\!\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")
TAG_RE = re.compile(r"(?<![\w/])#([A-Za-z0-9_\-/]+)")

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
ATTACHMENT_EXTS = IMAGE_EXTS | {".pdf", ".mp3", ".mp4", ".wav", ".mov", ".zip"}


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> tuple[dict, bool]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, False
    raw = m.group(1)
    fm: dict = {}
    # minimal YAML parser (flat keys + list inline / block)
    current_key = None
    for line in raw.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("  - ") or line.startswith("- "):
            if current_key:
                fm.setdefault(current_key, [])
                if isinstance(fm[current_key], list):
                    fm[current_key].append(line.lstrip(" -").strip().strip("\"'"))
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            current_key = k
            if v == "":
                fm[k] = []
            elif v.startswith("[") and v.endswith("]"):
                items = [s.strip().strip("\"'") for s in v[1:-1].split(",") if s.strip()]
                fm[k] = items
            else:
                fm[k] = v.strip("\"'")
    return fm, True


def slugify_link(target: str) -> str:
    """Normalize a wikilink target to compare against filenames (case-insensitive, no extension)."""
    t = target.strip()
    if t.lower().endswith(".md"):
        t = t[:-3]
    # Only keep the last path segment — Obsidian resolves by basename by default
    t = t.split("/")[-1]
    return t.lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of markdown")
    args = ap.parse_args()

    vault: Path = args.vault.resolve()
    if not vault.is_dir():
        print(f"error: {vault} is not a directory", file=sys.stderr)
        return 2

    md_files: list[Path] = []
    attachments: list[Path] = []
    for root, dirs, files in os.walk(vault):
        # skip Obsidian/config/trash dirs
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git", "node_modules"}]
        for f in files:
            p = Path(root) / f
            ext = p.suffix.lower()
            if ext == ".md":
                md_files.append(p)
            elif ext in ATTACHMENT_EXTS:
                attachments.append(p)

    folder_hist: Counter = Counter()
    no_frontmatter: list[str] = []
    basename_to_files: dict[str, list[Path]] = defaultdict(list)
    outbound: dict[str, set[str]] = defaultdict(set)
    inbound: dict[str, set[str]] = defaultdict(set)
    tags: Counter = Counter()
    domains: Counter = Counter()
    types: Counter = Counter()
    link_targets_all: Counter = Counter()

    basename_set = set()
    for p in md_files:
        slug = p.stem.lower()
        basename_to_files[slug].append(p)
        basename_set.add(slug)

    for p in md_files:
        rel = p.relative_to(vault)
        top = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        folder_hist[top] += 1
        text = read_text(p)
        fm, has_fm = parse_frontmatter(text)
        if not has_fm:
            no_frontmatter.append(str(rel))
        if fm:
            d = fm.get("domain")
            if d:
                domains[d if isinstance(d, str) else str(d)] += 1
            t = fm.get("type")
            if t:
                types[t if isinstance(t, str) else str(t)] += 1
            fm_tags = fm.get("tags")
            if isinstance(fm_tags, list):
                for tg in fm_tags:
                    tags[tg] += 1

        body = text[FRONTMATTER_RE.match(text).end():] if FRONTMATTER_RE.match(text) else text
        for m in TAG_RE.finditer(body):
            tags[m.group(1)] += 1
        for m in WIKILINK_RE.finditer(body):
            target = slugify_link(m.group(1))
            outbound[str(rel)].add(target)
            link_targets_all[target] += 1
        for m in EMBED_RE.finditer(body):
            target = slugify_link(m.group(1))
            outbound[str(rel)].add(target)

    # build inbound
    for src, targets in outbound.items():
        for t in targets:
            inbound[t].add(src)

    red_links: list[tuple[str, int]] = []
    for target, count in link_targets_all.most_common():
        if target not in basename_set:
            red_links.append((target, count))

    orphans: list[str] = []
    for p in md_files:
        rel = str(p.relative_to(vault))
        slug = p.stem.lower()
        has_in = bool(inbound.get(slug))
        has_out = bool(outbound.get(rel))
        if not has_in and not has_out:
            orphans.append(rel)

    duplicates = {k: [str(p.relative_to(vault)) for p in v] for k, v in basename_to_files.items() if len(v) > 1}

    # stats
    stats = []
    for p in md_files:
        try:
            st = p.stat()
            stats.append((str(p.relative_to(vault)), st.st_size, st.st_mtime))
        except OSError:
            continue
    largest = sorted(stats, key=lambda x: -x[1])[:10]
    newest = sorted(stats, key=lambda x: -x[2])[:10]
    oldest = sorted(stats, key=lambda x: x[2])[:10]

    if args.json:
        out = {
            "vault": str(vault),
            "md_count": len(md_files),
            "attachment_count": len(attachments),
            "folder_hist": folder_hist.most_common(),
            "no_frontmatter": no_frontmatter,
            "orphans": orphans,
            "duplicates": duplicates,
            "red_links": red_links[:50],
            "top_tags": tags.most_common(30),
            "top_domains": domains.most_common(),
            "top_types": types.most_common(),
            "top_link_targets": link_targets_all.most_common(30),
            "largest": largest,
            "newest": [(n, s, datetime.fromtimestamp(m).isoformat()) for n, s, m in newest],
            "oldest": [(n, s, datetime.fromtimestamp(m).isoformat()) for n, s, m in oldest],
        }
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    # markdown report
    today = datetime.now().strftime("%Y-%m-%d")
    out_lines: list[str] = []
    W = out_lines.append
    W(f"# Vault audit — {today}")
    W("")
    W(f"- Vault: `{vault}`")
    W(f"- Markdown notes: **{len(md_files)}**")
    W(f"- Attachments: **{len(attachments)}**")
    W(f"- Notes without frontmatter: **{len(no_frontmatter)}**")
    W(f"- Orphans (no inbound/outbound links): **{len(orphans)}**")
    W(f"- Duplicate slugs: **{len(duplicates)}**")
    W(f"- Red links (unresolved wikilink targets): **{len(red_links)}**")
    W("")

    W("## Folder histogram (top-level)")
    W("")
    W("| Folder | Notes |")
    W("|---|---:|")
    for name, count in folder_hist.most_common():
        W(f"| `{name}` | {count} |")
    W("")

    if types:
        W("## Frontmatter `type` distribution")
        W("")
        W("| Type | Count |")
        W("|---|---:|")
        for t, c in types.most_common():
            W(f"| `{t}` | {c} |")
        W("")

    if domains:
        W("## Frontmatter `domain` distribution")
        W("")
        W("| Domain | Count |")
        W("|---|---:|")
        for d, c in domains.most_common():
            W(f"| `{d}` | {c} |")
        W("")

    W("## Top tags")
    W("")
    W("| Tag | Count |")
    W("|---|---:|")
    for tag, c in tags.most_common(30):
        W(f"| `#{tag}` | {c} |")
    W("")

    W("## Top wikilink targets")
    W("")
    W("| Target | Links | Resolves? |")
    W("|---|---:|:---:|")
    for target, c in link_targets_all.most_common(30):
        resolves = "✅" if target in basename_set else "❌"
        W(f"| `{target}` | {c} | {resolves} |")
    W("")

    W("## Red links (most-referenced missing targets)")
    W("")
    W("These are candidates for new wiki pages or renames.")
    W("")
    W("| Missing target | References |")
    W("|---|---:|")
    for target, c in red_links[:30]:
        W(f"| `{target}` | {c} |")
    W("")

    W("## Duplicate slugs")
    W("")
    if duplicates:
        for slug, paths in list(duplicates.items())[:30]:
            W(f"- `{slug}`:")
            for p in paths:
                W(f"  - `{p}`")
    else:
        W("_none_")
    W("")

    W(f"## Orphans (first 30 of {len(orphans)})")
    W("")
    for o in orphans[:30]:
        W(f"- `{o}`")
    W("")

    W(f"## Notes missing frontmatter (first 30 of {len(no_frontmatter)})")
    W("")
    for n in no_frontmatter[:30]:
        W(f"- `{n}`")
    W("")

    W("## Largest notes")
    W("")
    W("| Path | Size (bytes) |")
    W("|---|---:|")
    for path, size, _ in largest:
        W(f"| `{path}` | {size} |")
    W("")

    W("## Newest notes")
    W("")
    W("| Path | Modified |")
    W("|---|---|")
    for path, _, mtime in newest:
        W(f"| `{path}` | {datetime.fromtimestamp(mtime).isoformat(timespec='minutes')} |")
    W("")

    W("## Oldest notes")
    W("")
    W("| Path | Modified |")
    W("|---|---|")
    for path, _, mtime in oldest:
        W(f"| `{path}` | {datetime.fromtimestamp(mtime).isoformat(timespec='minutes')} |")
    W("")

    print("\n".join(out_lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
