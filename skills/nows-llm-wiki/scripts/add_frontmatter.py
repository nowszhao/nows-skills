#!/usr/bin/env python3
"""add_frontmatter.py — insert default YAML frontmatter into notes that lack it.

Usage:
  add_frontmatter.py <vault_path> [--type=source] [--domain=general] [--dry-run] [--only=<relpath-or-glob>]

Behavior:
  - Only touches files that do NOT already start with `---`.
  - Inserts a minimal frontmatter block using:
      title:   from the first H1 if present, else the filename stem
      type:    --type value (default: source)
      created: file ctime (YYYY-MM-DD)
      updated: today
      tags:    []
      domain:  --domain value (if provided)
  - Existing frontmatter is never modified by this script.
"""
from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from datetime import datetime
from pathlib import Path

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") or text.startswith("---\r\n")


def build_frontmatter(title: str, type_: str, domain: str | None, created: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = ["---", f"title: {title}", f"type: {type_}"]
    if domain:
        lines.append(f"domain: {domain}")
    lines.append("tags: []")
    lines.append(f"created: {created}")
    lines.append(f"updated: {today}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("--type", dest="type_", default="source")
    ap.add_argument("--domain", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", default=None, help="glob relative to vault; if set, only matching files are touched")
    args = ap.parse_args()

    vault: Path = args.vault.resolve()
    if not vault.is_dir():
        print(f"error: {vault} not a directory", file=sys.stderr)
        return 2

    touched = 0
    scanned = 0
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git", "node_modules"}]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            rel = str(p.relative_to(vault))
            if args.only and not fnmatch.fnmatch(rel, args.only):
                continue
            scanned += 1
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if has_frontmatter(text):
                continue
            m = H1_RE.search(text)
            title = m.group(1).strip() if m else p.stem
            try:
                ctime = datetime.fromtimestamp(p.stat().st_ctime).strftime("%Y-%m-%d")
            except OSError:
                ctime = datetime.now().strftime("%Y-%m-%d")
            fm = build_frontmatter(title, args.type_, args.domain, ctime)
            new_text = fm + "\n" + text
            if not args.dry_run:
                p.write_text(new_text, encoding="utf-8")
            touched += 1

    mode = "dry-run" if args.dry_run else "applied"
    print(f"add_frontmatter: {mode} | scanned={scanned} touched={touched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
