#!/usr/bin/env python3
"""
Extract plain-text show notes from episode_content.md for 小宇宙 injection.

Reads episode_content.md, strips Markdown formatting (`##` → plain text,
skips `#` title header, stops at second `---` separator), and appends the
original podcast link from line 2 of the file.

Usage:
    python3 scripts/extract_show_notes.py episode_content.md > show_notes.txt

The output is plain text ready for direct injection into 小宇宙's Show Notes textbox.
"""

import sys
import json


def extract_show_notes(md_path):
    """Extract plain-text show notes from episode_content.md."""
    with open(md_path) as f:
        notes = f.read()

    lines = notes.split('\n')

    # Get podcast link from line 2 (right after title)
    link_line = lines[1].strip() if len(lines) > 1 else ''
    link_text = link_line.lstrip('*').strip()

    # Find start of content
    content_start = None
    for i, l in enumerate(lines):
        if l.startswith('## 本期核心内容'):
            content_start = i
            break

    if content_start is None:
        raise ValueError("Cannot find '## 本期核心内容' in episode_content.md")

    # Extract body: strip ## → plain text, skip # title, stop at 2nd ---
    show_lines = []
    hr_count = 0
    for l in lines[content_start:]:
        if l.startswith('---'):
            hr_count += 1
            if hr_count >= 2:
                break  # second separator = chapter nav starts
            continue
        if l.startswith('## '):
            show_lines.append(l[3:])  # strip markdown header
        elif l.startswith('# '):
            continue
        else:
            show_lines.append(l)

    # Assemble: body + link
    body = '\n'.join(show_lines).strip()
    full = body + '\n\n原文链接：' + link_text
    return full


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: extract_show_notes.py <episode_content.md>")
        sys.exit(1)

    show_notes = extract_show_notes(sys.argv[1])
    print(show_notes)
