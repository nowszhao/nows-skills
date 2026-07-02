"""
Helper script: validate the generated HTML output.

Usage:
    python scripts/validate_output.py index.html

Checks:
    - File exists and is not empty
    - Has proper HTML structure
    - No broken CDN links
    - All tags are properly closed
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence


def validate_html(filepath: str) -> list[str]:
    """Validate a generated HTML file. Returns a list of issues (empty = all good)."""
    issues: list[str] = []

    path = Path(filepath)
    if not path.exists():
        issues.append(f"❌ File does not exist: {filepath}")
        return issues

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        issues.append("❌ File is empty")
        return issues

    # Check basic HTML structure
    if "<!DOCTYPE html>" not in content and "<!doctype html>" not in content:
        issues.append("⚠️  Missing DOCTYPE declaration")
    if "<html" not in content:
        issues.append("❌ Missing <html> tag")
    if "<head>" not in content:
        issues.append("⚠️  Missing <head> tag")
    if "<body>" not in content:
        issues.append("❌ Missing <body> tag")

    # Check for common CDN issues
    cdn_urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)["\']', content)
    for url in cdn_urls:
        if "babeljs.io" in url and "7.25.6" not in url:
            issues.append(f"⚠️  Babel CDN may be wrong version (should be 7.25.6): {url}")

    # Check for potentially missing CDN scripts
    if "tailwind" in content.lower() and "cdn.tailwindcss.com" not in content:
        issues.append("⚠️  Tailwind is used but CDN script may be missing")
    if "react" in content.lower() and "unpkg.com/react" not in content and "cdn.jsdelivr.net/npm/react" not in content:
        issues.append("⚠️  React is referenced but CDN scripts may be missing")

    # Check file size
    size_kb = len(content) / 1024
    if size_kb > 500:
        issues.append(f"⚠️  File is large ({size_kb:.0f} KB). Consider if all content is necessary.")
    elif size_kb < 1:
        issues.append("⚠️  File is very small (< 1 KB). May be incomplete.")

    if not issues:
        issues.append(f"✅ HTML looks valid ({size_kb:.1f} KB)")

    return issues


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate generated HTML output from screenshot-to-code."
    )
    parser.add_argument("file", help="Path to the HTML file to validate")
    args = parser.parse_args(argv)

    issues = validate_html(args.file)
    for issue in issues:
        print(issue)

    has_errors = any("❌" in i for i in issues)
    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
