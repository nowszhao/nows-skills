#!/usr/bin/env python3
"""rewrite_links.py — rewrite wikilinks / embeds / md-links across a vault.

Usage:
  rewrite_links.py <vault_path> <rename_map.json> [--dry-run]

rename_map.json format:
  {
    "old-slug": "new-slug",
    "old name with spaces": "new-name",
    "images/foo.png": "00-Inbox/raw/assets/foo.png"
  }

Keys are matched against:
  - wikilink targets `[[old]]` (with optional `|alias` and `#heading`)
  - embed targets `![[old.png]]`
  - relative markdown links `[x](old.md)` or `[x](images/foo.png)`

Matching is case-insensitive on the basename for md files; exact path for
assets. The script preserves aliases, anchors, and relative path prefixes.

Without --dry-run, files are rewritten in place. A summary is printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def load_map(p: Path) -> dict[str, str]:
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("rename_map must be a JSON object")
    # normalize: lower-case the keys for md targets (basename match)
    out: dict[str, str] = {}
    for k, v in data.items():
        out[k] = v
    return out


def norm_basename(target: str) -> str:
    t = target.strip()
    if t.lower().endswith(".md"):
        t = t[:-3]
    return t.split("/")[-1].lower()


def build_basename_index(rename_map: dict[str, str]) -> dict[str, str]:
    """Map lowercased old basename → new slug (no extension)."""
    idx: dict[str, str] = {}
    for old, new in rename_map.items():
        if old.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".mp3", ".mp4")):
            continue  # handled by path-exact logic
        old_base = norm_basename(old)
        new_base = new
        if new_base.endswith(".md"):
            new_base = new_base[:-3]
        # keep last segment as the display slug; full path not used in wikilinks by default
        idx[old_base] = new_base
    return idx


WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]\|#]+?)(#[^\]\|]*)?(\|[^\]]*)?\]\]")
EMBED_RE = re.compile(r"\!\[\[([^\]\|#]+?)(#[^\]\|]*)?(\|[^\]]*)?\]\]")
MDLINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def rewrite_text(text: str, basename_idx: dict[str, str], path_map: dict[str, str]) -> tuple[str, int]:
    changes = 0

    def sub_wiki(m: re.Match) -> str:
        nonlocal changes
        target, anchor, alias = m.group(1), m.group(2) or "", m.group(3) or ""
        key = norm_basename(target)
        if key in basename_idx:
            changes += 1
            return f"[[{basename_idx[key]}{anchor}{alias}]]"
        return m.group(0)

    def sub_embed(m: re.Match) -> str:
        nonlocal changes
        target, anchor, alias = m.group(1), m.group(2) or "", m.group(3) or ""
        # for assets: match by exact path in path_map
        if target in path_map:
            changes += 1
            return f"![[{path_map[target]}{anchor}{alias}]]"
        # for md: match by basename
        key = norm_basename(target)
        if key in basename_idx:
            changes += 1
            return f"![[{basename_idx[key]}{anchor}{alias}]]"
        return m.group(0)

    def sub_mdlink(m: re.Match) -> str:
        nonlocal changes
        label, target = m.group(1), m.group(2)
        t = target.split("#")[0].split("?")[0]
        if t in path_map:
            new = target.replace(t, path_map[t], 1)
            changes += 1
            return f"[{label}]({new})"
        if t.endswith(".md"):
            key = norm_basename(t)
            if key in basename_idx:
                new_md = basename_idx[key] + ".md"
                # preserve path prefix up to the last segment
                prefix = t.rsplit("/", 1)[0] + "/" if "/" in t else ""
                new_target = target.replace(t, prefix + new_md, 1)
                changes += 1
                return f"[{label}]({new_target})"
        return m.group(0)

    text = WIKILINK_RE.sub(sub_wiki, text)
    text = EMBED_RE.sub(sub_embed, text)
    text = MDLINK_RE.sub(sub_mdlink, text)
    return text, changes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("rename_map", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vault: Path = args.vault.resolve()
    if not vault.is_dir():
        print(f"error: {vault} not a directory", file=sys.stderr)
        return 2

    rename_map = load_map(args.rename_map.resolve())
    basename_idx = build_basename_index(rename_map)
    # asset path map: keys that look like relative paths with extensions
    path_map = {k: v for k, v in rename_map.items() if "/" in k or k.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf"))}

    touched = 0
    total_changes = 0
    files_scanned = 0

    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git", "node_modules"}]
        for f in files:
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            files_scanned += 1
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            new_text, n = rewrite_text(text, basename_idx, path_map)
            if n > 0:
                total_changes += n
                touched += 1
                if not args.dry_run:
                    p.write_text(new_text, encoding="utf-8")

    mode = "dry-run" if args.dry_run else "applied"
    print(f"rewrite_links: {mode} | scanned={files_scanned} touched={touched} changes={total_changes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
