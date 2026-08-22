#!/usr/bin/env python3
"""Fetch YouTube metadata for a single video or an entire playlist.

Wraps yt-dlp with browser cookies to bypass bot verification.
Output: single video -> one JSON object; playlist -> JSON array, records
separated by "###SPLIT###" on stdout, plus a "PLAYLIST_META|name|channel|count" line.
"""
import argparse
import json
import subprocess
import sys


def run_ytdlp(url: str) -> str:
    """Return raw --dump-json output for one video."""
    cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "--skip-download",
        "--no-warnings",
        "--dump-json",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip()
        raise RuntimeError(f"yt-dlp failed for {url}: {err[:500]}")
    return proc.stdout


def clean_id(raw: str) -> str:
    """Extract bare video id from full watch URL (strip &list/&t etc.)."""
    return raw.split("?v=")[-1].split("&")[0] if "?v=" in raw else raw


def fetch_playlist(playlist_url: str) -> list:
    """Fetch all video ids in a playlist, then fetch each video's full metadata."""
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s",
        playlist_url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp flat-playlist failed: {proc.stderr[:500]}")
    ids = [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]

    videos = []
    for vid in ids:
        try:
            videos.append(json.loads(run_ytdlp(f"https://www.youtube.com/watch?v={vid}")))
        except Exception as e:
            sys.stderr.write(f"WARN: {vid} -> {e}\n")
    return videos


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch YouTube video/playlist metadata")
    parser.add_argument("url", help="YouTube watch URL (optionally with &list=) or playlist URL")
    args = parser.parse_args()

    if "list=" in args.url:
        list_param = [p for p in args.url.split("&") if p.startswith("list=")][0]
        pl_url = f"https://www.youtube.com/playlist?{list_param}"
        videos = fetch_playlist(pl_url)
        # emit playlist summary line (once)
        if videos:
            print(f"PLAYLIST_META|{videos[0].get('channel', '')}|{len(videos)}")
        for d in videos:
            print(json.dumps(d, ensure_ascii=False))
            print("###SPLIT###")
    else:
        raw = run_ytdlp(args.url)
        d = json.loads(raw)
        print(json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    main()
