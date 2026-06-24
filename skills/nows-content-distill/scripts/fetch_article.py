#!/usr/bin/env python3
"""Fetch article main content from a URL with graceful fallback.

Usage:
    python fetch_article.py <url>

Output (stdout, plain text):
    === metadata ===
    title:  ...
    url:    ...
    source: jina | trafilatura | readability | raw
    word_count: NNN
    === content ===
    <plain text article body>

Exit codes:
    0 — success
    2 — could not extract usable content (per skill rule, ask user to paste)
    3 — invalid URL or network failure

Strategy (in order):
    1. r.jina.ai prefix proxy — best-effort reader extraction, no auth needed
    2. trafilatura  (pip install trafilatura) — strong heuristic extraction
    3. readability  (pip install readability-lxml) — fallback
    4. raw HTML stripped — last resort

NOTE: per nows-content-distill rule, if extraction yields < 300 Chinese chars
or content looks like nav/menu/cookie banner, exit 2 — the skill must STOP and
ask the user to paste the article body manually, NOT fall back to model priors.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.parse
import urllib.request
from typing import Optional, Tuple

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

MIN_CN_CHARS = 300


def http_get(url: str, timeout: int = 25) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ct = resp.headers.get("Content-Type", "")
            charset_m = re.search(r"charset=([\w-]+)", ct, re.I)
            charset = charset_m.group(1) if charset_m else "utf-8"
            try:
                return raw.decode(charset, errors="replace")
            except LookupError:
                return raw.decode("utf-8", errors="replace")
    except Exception as e:
        sys.stderr.write(f"[fetch_article] http_get failed: {e}\n")
        return None


def count_cn_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fa5]", text))


def looks_like_garbage(text: str) -> bool:
    """Heuristic: nav menus / cookie banners / 404 pages."""
    if not text:
        return True
    sample = text[:500].lower()
    bad_signals = [
        "enable javascript",
        "404 not found",
        "page not found",
        "access denied",
        "are you a robot",
        "cf-error",
        "cookie",
    ]
    hits = sum(1 for s in bad_signals if s in sample)
    if hits >= 2:
        return True
    # if the whole content is a flood of single-line nav links
    lines = [l for l in text.splitlines() if l.strip()]
    if lines and sum(1 for l in lines if len(l) < 12) / len(lines) > 0.7 and len(lines) > 20:
        return True
    return False


# ---------- Path 1: Jina Reader ----------

def try_jina(url: str) -> Optional[Tuple[str, str]]:
    """Returns (title, content) or None."""
    proxy = "https://r.jina.ai/" + url
    text = http_get(proxy)
    if not text:
        return None
    # Jina returns: "Title: ...\nURL Source: ...\n\nMarkdown Content:\n..."
    title_m = re.search(r"^Title:\s*(.+)$", text, re.M)
    title = title_m.group(1).strip() if title_m else ""
    body_m = re.search(r"Markdown Content:\s*\n(.+)$", text, re.S)
    body = body_m.group(1).strip() if body_m else text.strip()
    return title, body


# ---------- Path 2: trafilatura ----------

def try_trafilatura(url: str) -> Optional[Tuple[str, str]]:
    try:
        import trafilatura  # type: ignore
    except ImportError:
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        meta = trafilatura.extract_metadata(downloaded)
        title = (meta.title if meta and meta.title else "") if meta else ""
        body = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if not body:
            return None
        return title or "", body.strip()
    except Exception:
        return None


# ---------- Path 3: readability ----------

def try_readability(url: str) -> Optional[Tuple[str, str]]:
    try:
        from readability import Document  # type: ignore
    except ImportError:
        return None
    html = http_get(url)
    if not html:
        return None
    try:
        doc = Document(html)
        title = (doc.short_title() or "").strip()
        summary_html = doc.summary(html_partial=True)
        body = strip_html(summary_html)
        if not body:
            return None
        return title, body.strip()
    except Exception:
        return None


# ---------- Path 4: raw strip ----------

def try_raw_strip(url: str) -> Optional[Tuple[str, str]]:
    html = http_get(url)
    if not html:
        return None
    title_m = re.search(r"<title[^>]*>(.+?)</title>", html, re.I | re.S)
    title = title_m.group(1).strip() if title_m else ""
    body = strip_html(html)
    if not body:
        return None
    return title, body


def strip_html(html: str) -> str:
    # remove script/style
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.I | re.S)
    # turn block tags into newlines
    html = re.sub(r"</(p|div|li|h[1-6]|tr|br|section|article)>", "\n", html, flags=re.I)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    # strip remaining tags
    text = re.sub(r"<[^>]+>", "", html)
    # decode common entities (cheap)
    text = (text.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
                .replace("&#39;", "'"))
    # collapse whitespace, preserve line breaks
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return "\n\n".join(lines).strip()


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch article main content")
    ap.add_argument("url", help="Article URL")
    args = ap.parse_args()

    parsed = urllib.parse.urlparse(args.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        sys.stderr.write("[fetch_article] invalid URL\n")
        return 3

    attempts = [
        ("jina",         lambda: try_jina(args.url)),
        ("trafilatura",  lambda: try_trafilatura(args.url)),
        ("readability",  lambda: try_readability(args.url)),
        ("raw",          lambda: try_raw_strip(args.url)),
    ]

    last_text: Optional[str] = None
    last_title = ""
    last_source = ""
    for name, fn in attempts:
        try:
            res = fn()
        except Exception as e:
            sys.stderr.write(f"[fetch_article] {name} crashed: {e}\n")
            continue
        if not res:
            continue
        title, body = res
        if not body:
            continue
        last_text = body
        last_title = title
        last_source = name
        cn = count_cn_chars(body)
        # accept if reasonable length (>= 300 cn chars or >= 1500 chars overall) and not garbage
        if (cn >= MIN_CN_CHARS or len(body) >= 1500) and not looks_like_garbage(body):
            emit_ok(title, args.url, name, body)
            return 0

    # if we reach here, nothing produced a clean article
    sys.stderr.write("[fetch_article] FAILED to extract clean article body.\n")
    if last_text:
        sys.stderr.write(
            f"[fetch_article] last attempt was {last_source}, "
            f"got {len(last_text)} chars / {count_cn_chars(last_text)} CN chars; "
            "looks like garbage or too short.\n"
        )
    sys.stderr.write(
        "[fetch_article] Per skill rule: do NOT fall back to model priors.\n"
        "[fetch_article] Please ask the user to paste the article body manually.\n"
    )
    return 2


def emit_ok(title: str, url: str, source: str, body: str) -> None:
    print("=== metadata ===")
    print(f"title:  {title}")
    print(f"url:    {url}")
    print(f"source: {source}")
    print(f"word_count: {count_cn_chars(body)}")
    print()
    print("=== content ===")
    print(body)


if __name__ == "__main__":
    sys.exit(main())
