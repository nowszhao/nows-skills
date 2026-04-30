#!/usr/bin/env python3
"""para_classify.py — suggest a PARA + wiki-role placement for every note.

Usage: para_classify.py <vault_path> [--json]

For every .md file in the vault, emits a suggested:
  - PARA bucket: inbox / projects / areas / resources / archive / daily / wiki / keep
  - wiki role  : raw | wiki | sticky-raw | ignored

Advisory only. Read-only. Output is markdown (or JSON with --json).

Heuristics, in priority order:
  1. Already under a known top-level PARA folder → keep in that bucket
  2. Daily-note filename pattern (YYYY-MM-DD) → daily
  3. Already under wiki/ → wiki
  4. frontmatter type=source / source_kind=* → raw (suggest move to 00-Inbox/raw/<kind>/)
  5. Filename contains project-code tokens (uppercase tokens, codes) → projects (low confidence)
  6. Many recent modifications (<30d) + outbound wikilinks → projects (moderate)
  7. No modification in >180d AND no inbound links → archive
  8. Contains a template marker (/templates/, #template tag) → resources
  9. Otherwise → inbox (needs triage)
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
DAILY_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ _-].*)?$")
WIKILINK_RE = re.compile(r"(?<!\!)\[\[([^\]\|#]+)(?:#[^\]\|]*)?(?:\|[^\]]*)?\]\]")

PARA_PREFIXES = {
    "00-Inbox": "inbox",
    "00-inbox": "inbox",
    "Inbox": "inbox",
    "01-Projects": "projects",
    "01-projects": "projects",
    "Projects": "projects",
    "02-Areas": "areas",
    "02-areas": "areas",
    "Areas": "areas",
    "03-Resources": "resources",
    "03-resources": "resources",
    "Resources": "resources",
    "04-Archive": "archive",
    "04-archive": "archive",
    "Archive": "archive",
    "Daily Note": "daily",
    "daily-note": "daily",
    "wiki": "wiki",
}


def read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(encoding="utf-8", errors="replace")


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm: dict = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip().strip("\"'")
    return fm


def classify(p: Path, vault: Path, inbound_count: int) -> tuple[str, str, str]:
    """Return (para_bucket, wiki_role, reason)."""
    rel = p.relative_to(vault)
    parts = rel.parts

    # (0) root-level schema/readme files stay in place
    if len(parts) == 1:
        stem_lower = p.stem.lower()
        if stem_lower in {"claude", "readme", "readme_zh", "index"}:
            return ("keep", "schema", f"root-level special file ({p.name})")

    # (1) already placed under a PARA folder
    if parts and parts[0] in PARA_PREFIXES:
        bucket = PARA_PREFIXES[parts[0]]
        if bucket == "inbox":
            # inside 00-Inbox/raw/* → wiki role = raw
            if len(parts) >= 2 and parts[1].lower() == "raw":
                return ("inbox", "raw", "already under 00-Inbox/raw/")
            return ("inbox", "ignored", "already in 00-Inbox/")
        if bucket == "wiki":
            return ("wiki", "wiki", "already under wiki/")
        if bucket == "projects":
            return ("projects", "ignored", "already in 01-Projects/")
        if bucket == "areas":
            return ("areas", "sticky-raw", "already in 02-Areas/ (sticky raw by default)")
        if bucket == "resources":
            return ("resources", "ignored", "already in 03-Resources/")
        if bucket == "archive":
            return ("archive", "ignored", "already in 04-Archive/")
        if bucket == "daily":
            return ("daily", "ignored", "daily note folder")

    # (2) daily-note filename
    stem = p.stem
    if DAILY_RE.match(stem):
        return ("daily", "ignored", "daily-note filename pattern")

    # (3) already under wiki/ at any depth (root filenames that look like wiki)
    if any(part == "wiki" for part in parts):
        return ("wiki", "wiki", "inside wiki/")

    # (4) frontmatter
    text = read_text(p)
    fm = parse_frontmatter(text)
    fm_type = fm.get("type", "").lower()
    if fm_type == "source" or fm.get("source_kind"):
        kind = fm.get("source_kind") or "research"
        return ("inbox", "raw", f"frontmatter type=source (source_kind={kind}); suggest 00-Inbox/raw/{kind}/")
    if fm_type in {"concept", "entity", "synthesis", "moc"}:
        return ("wiki", "wiki", f"frontmatter type={fm_type}")

    # (8) template markers
    if "/templates/" in str(rel).lower() or "#template" in text.lower():
        return ("resources", "ignored", "looks like a template")

    # (7) stale & no links
    try:
        mtime = datetime.fromtimestamp(p.stat().st_mtime)
    except OSError:
        mtime = datetime.now()
    age = datetime.now() - mtime
    outbound = len(set(WIKILINK_RE.findall(text)))
    if age > timedelta(days=180) and inbound_count == 0 and outbound == 0:
        return ("archive", "ignored", "no edits in >180d and no links")

    # (6) active note
    if age < timedelta(days=30) and outbound >= 2:
        return ("projects", "ignored", "recent activity + outbound links — possibly a project note")

    # (5) looks like a project code (e.g., TBDS-Insight, PRJ-2026-001)
    if re.match(r"^[A-Z][A-Za-z0-9]+[-_][A-Za-z0-9]+", stem):
        return ("projects", "ignored", "filename looks like a project code")

    # (9) fallback
    return ("inbox", "unknown", "needs triage")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("--json", action="store_true")
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

    # build inbound link graph
    basename_set = {p.stem.lower() for p in md_files}
    inbound: dict[str, int] = defaultdict(int)
    for p in md_files:
        try:
            text = read_text(p)
        except OSError:
            continue
        for m in WIKILINK_RE.finditer(text):
            target = m.group(1).strip()
            if target.lower().endswith(".md"):
                target = target[:-3]
            target = target.split("/")[-1].lower()
            if target in basename_set:
                inbound[target] += 1

    rows: list[dict] = []
    for p in md_files:
        rel = str(p.relative_to(vault))
        slug = p.stem.lower()
        bucket, role, reason = classify(p, vault, inbound.get(slug, 0))
        rows.append({"path": rel, "bucket": bucket, "role": role, "reason": reason, "inbound": inbound.get(slug, 0)})

    # Sort rows: bucket order, then path
    bucket_order = ["projects", "areas", "inbox", "wiki", "daily", "resources", "archive", "keep", "unknown"]
    rows.sort(key=lambda r: (bucket_order.index(r["bucket"]) if r["bucket"] in bucket_order else 99, r["path"]))

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    out: list[str] = []
    W = out.append
    W(f"# PARA classification suggestions — {today}")
    W("")
    W(f"- Vault: `{vault}`")
    W(f"- Notes classified: **{len(rows)}**")
    W("")

    bucket_counts: dict[str, int] = defaultdict(int)
    for r in rows:
        bucket_counts[r["bucket"]] += 1
    W("## Summary")
    W("")
    W("| Bucket | Count |")
    W("|---|---:|")
    for b in bucket_order:
        if bucket_counts.get(b):
            W(f"| {b} | {bucket_counts[b]} |")
    W("")

    W("## Suggestions")
    W("")
    W("| Path | PARA bucket | Wiki role | Inbound | Reason |")
    W("|---|---|---|---:|---|")
    for r in rows:
        W(f"| `{r['path']}` | **{r['bucket']}** | {r['role']} | {r['inbound']} | {r['reason']} |")
    W("")

    W("> These are **advisory only**. Review with the user before executing any move.")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
