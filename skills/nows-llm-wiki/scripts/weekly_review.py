#!/usr/bin/env python3
"""weekly_review.py — PARA weekly review report.

Usage: weekly_review.py <vault_path> [--json] [--inbox-days=7] [--project-days=14] [--area-days=90] [--gap-days=30]

Read-only. Emits a markdown report suitable for saving to
`<vault>/00-Inbox/reviews/YYYY-MM-DD.md`.

Report sections:
  1. Inbox aging — items in 00-Inbox/ (excluding raw/) older than --inbox-days
  2. Stale projects — 01-Projects/<proj>/ folders with no mtime in --project-days
  3. Neglected areas — 02-Areas/<area>/ folders untouched in --area-days
  4. Archive growth — items added to 04-Archive in the last 7 days
  5. Wiki follow-ups — Gaps in wiki/concepts/* older than --gap-days
  6. Recent wiki activity — last 10 log.md entries
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

PARA_FOLDERS = {
    "inbox": ["00-Inbox", "Inbox"],
    "projects": ["01-Projects", "Projects"],
    "areas": ["02-Areas", "Areas"],
    "resources": ["03-Resources", "Resources"],
    "archive": ["04-Archive", "Archive"],
    "wiki": ["wiki"],
}


def find_para(vault: Path, kind: str) -> Path | None:
    for name in PARA_FOLDERS[kind]:
        p = vault / name
        if p.is_dir():
            return p
    return None


def iter_md(root: Path, exclude_subdirs: set[str] | None = None):
    exclude_subdirs = exclude_subdirs or set()
    for r, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git", "node_modules"} and d not in exclude_subdirs]
        for f in files:
            if f.endswith(".md"):
                yield Path(r) / f


def folder_latest_mtime(folder: Path) -> datetime:
    latest = 0.0
    for r, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d not in {".obsidian", ".trash", ".git"}]
        for f in files:
            if f.endswith(".md"):
                try:
                    t = (Path(r) / f).stat().st_mtime
                    latest = max(latest, t)
                except OSError:
                    pass
    if latest == 0:
        try:
            latest = folder.stat().st_mtime
        except OSError:
            latest = 0
    return datetime.fromtimestamp(latest) if latest else datetime.min


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("vault", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--inbox-days", type=int, default=7)
    ap.add_argument("--project-days", type=int, default=14)
    ap.add_argument("--area-days", type=int, default=90)
    ap.add_argument("--gap-days", type=int, default=30)
    args = ap.parse_args()

    vault: Path = args.vault.resolve()
    if not vault.is_dir():
        print(f"error: {vault} not a directory", file=sys.stderr)
        return 2

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")

    # 1. Inbox aging (excluding raw/)
    inbox = find_para(vault, "inbox")
    inbox_aged: list[tuple[str, str]] = []
    if inbox:
        cutoff = now - timedelta(days=args.inbox_days)
        for p in iter_md(inbox, exclude_subdirs={"raw", "audits", "reviews"}):
            try:
                mtime = datetime.fromtimestamp(p.stat().st_mtime)
            except OSError:
                continue
            if mtime < cutoff:
                inbox_aged.append((str(p.relative_to(vault)), mtime.strftime("%Y-%m-%d")))

    # 2. Stale projects (top-level child folders)
    projects = find_para(vault, "projects")
    stale_projects: list[tuple[str, str]] = []
    if projects:
        cutoff = now - timedelta(days=args.project_days)
        for child in sorted(projects.iterdir()):
            if not child.is_dir():
                continue
            latest = folder_latest_mtime(child)
            if latest < cutoff:
                stale_projects.append((str(child.relative_to(vault)), latest.strftime("%Y-%m-%d") if latest > datetime.min else "—"))

    # 3. Neglected areas
    areas = find_para(vault, "areas")
    neglected_areas: list[tuple[str, str]] = []
    if areas:
        cutoff = now - timedelta(days=args.area_days)
        for child in sorted(areas.iterdir()):
            if not child.is_dir():
                continue
            latest = folder_latest_mtime(child)
            if latest < cutoff:
                neglected_areas.append((str(child.relative_to(vault)), latest.strftime("%Y-%m-%d") if latest > datetime.min else "—"))

    # 4. Archive growth (last 7 days)
    archive = find_para(vault, "archive")
    recent_archive: list[tuple[str, str]] = []
    if archive:
        cutoff = now - timedelta(days=7)
        for p in iter_md(archive):
            try:
                ctime = datetime.fromtimestamp(p.stat().st_ctime)
            except OSError:
                continue
            if ctime > cutoff:
                recent_archive.append((str(p.relative_to(vault)), ctime.strftime("%Y-%m-%d")))

    # 5. Wiki follow-ups: Gaps sections in wiki/concepts/ untouched for >gap-days
    wiki = find_para(vault, "wiki")
    stale_gaps: list[tuple[str, str, list[str]]] = []
    GAP_HEADING = re.compile(r"^#{1,6}\s+(?:知识缺口|Gaps|待研究的问题)", re.MULTILINE)
    BULLET = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)
    if wiki:
        concepts_dir = wiki / "concepts"
        cutoff = now - timedelta(days=args.gap_days)
        if concepts_dir.is_dir():
            for p in iter_md(concepts_dir):
                try:
                    mtime = datetime.fromtimestamp(p.stat().st_mtime)
                except OSError:
                    continue
                if mtime >= cutoff:
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                m = GAP_HEADING.search(text)
                if not m:
                    continue
                section = text[m.end():]
                # stop at next heading of same or lower depth — simple approximation: next `## ` or `# `
                next_h = re.search(r"^#{1,6}\s+", section, re.MULTILINE)
                if next_h:
                    section = section[:next_h.start()]
                gaps = [b.group(1).strip() for b in BULLET.finditer(section)]
                gaps = [g for g in gaps if g]
                if gaps:
                    stale_gaps.append((str(p.relative_to(vault)), mtime.strftime("%Y-%m-%d"), gaps[:5]))

    # 6. Recent wiki/log.md entries
    recent_log: list[str] = []
    if wiki:
        log = wiki / "log.md"
        if log.is_file():
            try:
                text = log.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = ""
            entries = re.findall(r"^## \[[0-9]{4}-[0-9]{2}-[0-9]{2}\][^\n]*", text, re.MULTILINE)
            recent_log = entries[-10:]

    if args.json:
        print(json.dumps({
            "date": today,
            "inbox_aged": inbox_aged,
            "stale_projects": stale_projects,
            "neglected_areas": neglected_areas,
            "recent_archive": recent_archive,
            "stale_gaps": [{"path": p, "mtime": m, "gaps": g} for p, m, g in stale_gaps],
            "recent_log": recent_log,
        }, ensure_ascii=False, indent=2))
        return 0

    out: list[str] = []
    W = out.append
    W(f"# Weekly review — {today}")
    W("")
    W(f"- Vault: `{vault}`")
    W(f"- Thresholds: inbox>{args.inbox_days}d, project>{args.project_days}d, area>{args.area_days}d, gaps>{args.gap_days}d")
    W("")

    W(f"## 1. Inbox aging ({len(inbox_aged)})")
    W("")
    if inbox_aged:
        W("| Path | Last modified |")
        W("|---|---|")
        for path, mtime in inbox_aged[:30]:
            W(f"| `{path}` | {mtime} |")
    else:
        W("_all inbox items fresh_")
    W("")

    W(f"## 2. Stale projects ({len(stale_projects)})")
    W("")
    if stale_projects:
        W("| Project | Latest mtime |")
        W("|---|---|")
        for path, mtime in stale_projects:
            W(f"| `{path}` | {mtime} |")
    else:
        W("_no stale projects_")
    W("")

    W(f"## 3. Neglected areas ({len(neglected_areas)})")
    W("")
    if neglected_areas:
        W("| Area | Latest mtime |")
        W("|---|---|")
        for path, mtime in neglected_areas:
            W(f"| `{path}` | {mtime} |")
    else:
        W("_all areas recently touched_")
    W("")

    W(f"## 4. Archive growth (last 7 days, {len(recent_archive)})")
    W("")
    if recent_archive:
        W("| Path | Added |")
        W("|---|---|")
        for path, ct in recent_archive[:30]:
            W(f"| `{path}` | {ct} |")
    else:
        W("_no new archives this week_")
    W("")

    W(f"## 5. Wiki follow-ups — stale Gaps ({len(stale_gaps)})")
    W("")
    if stale_gaps:
        for path, mtime, gaps in stale_gaps[:20]:
            W(f"### `{path}` — last updated {mtime}")
            for g in gaps:
                W(f"- {g}")
            W("")
    else:
        W("_no stale knowledge gaps_")
    W("")

    W("## 6. Recent wiki log entries (last 10)")
    W("")
    if recent_log:
        for e in recent_log:
            W(f"- {e.lstrip('# ').strip()}")
    else:
        W("_log.md not found or empty_")
    W("")

    W("---")
    W("")
    W("> Save this report to `00-Inbox/reviews/{date}.md`. Decide actions with the user; the report itself is not committed automatically.".format(date=today))

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
