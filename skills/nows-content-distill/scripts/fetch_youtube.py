#!/usr/bin/env python3
"""Fetch YouTube transcript with graceful fallback.

Usage:
    python fetch_youtube.py <youtube_url> [--lang zh-Hans,zh,en]

Output (stdout, plain text):
    === metadata ===
    title:    ...
    author:   ...
    duration: HH:MM:SS or MM:SS
    url:      ...
    language: ...
    === transcript ===
    [00:00] line one
    [00:12] line two
    ...

Exit codes:
    0 — success
    2 — no transcript available, ask user to provide manually
    3 — invalid URL or video ID

Dependencies (try in order):
    1. youtube-transcript-api  (pip install youtube-transcript-api)
    2. yt-dlp                  (pip install yt-dlp)

If neither is installed, the script prints install instructions and exits 2.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_LANGS = ["zh-Hans", "zh-Hant", "zh", "zh-CN", "en", "en-US"]

YT_ID_PATTERNS = [
    r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})",
    r"^([A-Za-z0-9_-]{11})$",
]


def extract_video_id(url_or_id: str) -> Optional[str]:
    s = url_or_id.strip()
    for pat in YT_ID_PATTERNS:
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fmt_timestamp(seconds: float) -> str:
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    return f"[{m:02d}:{s:02d}]"


# ---------- Path 1: youtube-transcript-api ----------

def try_transcript_api(video_id: str, langs: List[str]) -> Optional[Tuple[str, List[dict]]]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore
        from youtube_transcript_api._errors import (  # type: ignore
            TranscriptsDisabled,
            NoTranscriptFound,
        )
    except ImportError:
        return None

    try:
        listing = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception:
        return None

    # try preferred languages first, then any available
    chosen_lang = None
    transcript_obj = None
    for lang in langs:
        try:
            transcript_obj = listing.find_transcript([lang])
            chosen_lang = lang
            break
        except Exception:
            continue

    if transcript_obj is None:
        # fall back to first available
        try:
            for t in listing:
                transcript_obj = t
                chosen_lang = t.language_code
                break
        except Exception:
            return None

    if transcript_obj is None:
        return None

    try:
        data = transcript_obj.fetch()
    except Exception:
        return None

    return chosen_lang, data


# ---------- Path 2: yt-dlp ----------

def try_yt_dlp(url: str, langs: List[str]) -> Optional[Tuple[dict, str, List[dict]]]:
    if not shutil.which("yt-dlp"):
        return None

    # 1) get video info JSON
    try:
        info_proc = subprocess.run(
            ["yt-dlp", "--dump-single-json", "--skip-download", url],
            capture_output=True, text=True, timeout=60,
        )
        if info_proc.returncode != 0:
            return None
        info = json.loads(info_proc.stdout)
    except Exception:
        return None

    # 2) try to download subtitles to a tmp dir
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        sub_lang = ",".join(langs)
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", sub_lang,
            "--sub-format", "vtt",
            "-o", str(Path(tmpdir) / "%(id)s.%(ext)s"),
            url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            return None

        vtt_files = sorted(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return None

        # pick the first matching preferred language
        chosen_path = None
        chosen_lang = None
        for lang in langs:
            for f in vtt_files:
                if f"{lang}." in f.name or f".{lang}." in f.name:
                    chosen_path = f
                    chosen_lang = lang
                    break
            if chosen_path:
                break
        if chosen_path is None:
            chosen_path = vtt_files[0]
            chosen_lang = chosen_path.stem.split(".")[-1]

        segments = parse_vtt(chosen_path.read_text(encoding="utf-8", errors="ignore"))
        return info, chosen_lang or "unknown", segments


def parse_vtt(content: str) -> List[dict]:
    """Very small VTT parser. Returns list of {start, text}."""
    lines = content.splitlines()
    out: List[dict] = []
    i = 0
    ts_re = re.compile(r"(\d+):(\d+):(\d+)\.(\d+)\s*-->")
    while i < len(lines):
        line = lines[i].strip()
        m = ts_re.search(line)
        if m:
            h, mn, s, _ms = m.groups()
            start = int(h) * 3600 + int(mn) * 60 + int(s)
            i += 1
            text_parts = []
            while i < len(lines) and lines[i].strip() and not ts_re.search(lines[i]):
                # strip vtt tags like <c> </c> <00:00:00.000>
                t = re.sub(r"<[^>]+>", "", lines[i]).strip()
                if t:
                    text_parts.append(t)
                i += 1
            text = " ".join(text_parts).strip()
            if text:
                out.append({"start": start, "text": text})
        else:
            i += 1
    # de-duplicate consecutive identical texts (auto-sub artifact)
    deduped: List[dict] = []
    for seg in out:
        if deduped and deduped[-1]["text"] == seg["text"]:
            continue
        deduped.append(seg)
    return deduped


# ---------- Output ----------

def emit_output(metadata: dict, language: str, segments: List[dict]) -> None:
    print("=== metadata ===")
    print(f"title:    {metadata.get('title', '')}")
    print(f"author:   {metadata.get('author', '')}")
    print(f"duration: {metadata.get('duration', '')}")
    print(f"url:      {metadata.get('url', '')}")
    print(f"language: {language}")
    print()
    print("=== transcript ===")
    for seg in segments:
        ts = fmt_timestamp(seg.get("start", 0))
        text = seg.get("text", "").replace("\n", " ").strip()
        if text:
            print(f"{ts} {text}")


def emit_failure(reason: str) -> None:
    sys.stderr.write(f"[fetch_youtube] FAILED: {reason}\n")
    sys.stderr.write(
        "[fetch_youtube] Per skill rule: do NOT fall back to model priors.\n"
        "[fetch_youtube] Please ask the user to either provide the transcript manually,\n"
        "[fetch_youtube] or pick a different video that has subtitles.\n"
    )


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch YouTube transcript")
    ap.add_argument("url", help="YouTube URL or video ID")
    ap.add_argument(
        "--lang",
        default=",".join(DEFAULT_LANGS),
        help=f"Comma-separated language preference list (default: {','.join(DEFAULT_LANGS)})",
    )
    args = ap.parse_args()

    vid = extract_video_id(args.url)
    if not vid:
        emit_failure("invalid YouTube URL or video ID")
        return 3

    canonical_url = f"https://www.youtube.com/watch?v={vid}"
    langs = [x.strip() for x in args.lang.split(",") if x.strip()]

    # ---- Try Path 1 ----
    res1 = try_transcript_api(vid, langs)
    if res1 is not None:
        chosen_lang, data = res1
        # try to enrich metadata via yt-dlp if available
        info: dict = {"url": canonical_url}
        if shutil.which("yt-dlp"):
            try:
                p = subprocess.run(
                    ["yt-dlp", "--dump-single-json", "--skip-download", canonical_url],
                    capture_output=True, text=True, timeout=60,
                )
                if p.returncode == 0:
                    j = json.loads(p.stdout)
                    info = {
                        "title": j.get("title", ""),
                        "author": j.get("uploader", "") or j.get("channel", ""),
                        "duration": fmt_duration(j.get("duration", 0) or 0),
                        "url": canonical_url,
                    }
            except Exception:
                pass
        else:
            info.setdefault("title", "")
            info.setdefault("author", "")
            info.setdefault("duration", "")

        segments = [{"start": d.get("start", 0), "text": d.get("text", "")} for d in data]
        emit_output(info, chosen_lang, segments)
        return 0

    # ---- Try Path 2 ----
    res2 = try_yt_dlp(canonical_url, langs)
    if res2 is not None:
        info, chosen_lang, segments = res2
        meta = {
            "title": info.get("title", ""),
            "author": info.get("uploader", "") or info.get("channel", ""),
            "duration": fmt_duration(info.get("duration", 0) or 0),
            "url": canonical_url,
        }
        emit_output(meta, chosen_lang, segments)
        return 0

    # ---- All failed ----
    have_api = False
    try:
        import youtube_transcript_api  # noqa: F401
        have_api = True
    except ImportError:
        pass
    have_ytdlp = bool(shutil.which("yt-dlp"))

    parts = []
    if not have_api:
        parts.append("youtube-transcript-api not installed (pip install youtube-transcript-api)")
    if not have_ytdlp:
        parts.append("yt-dlp not installed (pip install yt-dlp)")
    if not parts:
        parts.append("both providers tried but no transcript available for this video")
    emit_failure("; ".join(parts))
    return 2


if __name__ == "__main__":
    sys.exit(main())
