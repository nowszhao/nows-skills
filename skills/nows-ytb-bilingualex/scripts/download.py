#!/usr/bin/env python3
"""
download.py — Download a YouTube video (MP4 ONLY), reusing the browser login
session via cookies. Subtitle acquisition is NO LONGER part of this script:
the bilingual subtitle must be built from YouTube's official transcript
(转写文稿), fetched by fetch_transcript.py via the bundled CDP proxy.

Steps performed:
  1. Probe metadata via `yt-dlp -J` to read the title (for file naming).
  2. Download the video at the requested quality (interactive choice from the
     user, passed via --quality: best | 1080p | 720p | <height>).
  3. Write manifest.json with everything later steps need.

Auth: reuses the browser session with --cookies-from-browser. If that fails
(e.g. Keychain permission or no login), retries without cookies for public
videos.

Usage:
    python3 download.py --url <URL> [--quality best|1080p|720p|<height>] \
        [--cookies-browser chrome] [--output <dir>] [--env-out yt_env.json]

Exit codes: 0 ok, 1 fatal, 2 download issues that may be retryable.
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime


def log(msg: str) -> None:
    print(f"[download] {msg}", flush=True)


def run(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    log("+ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def load_env(env_out: str) -> dict:
    with open(env_out, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize(name: str) -> str:
    """Filesystem-safe title (keep CJK and alnum, replace separators)."""
    name = re.sub(r'[\\/:*?"<>|#%&\{\}\$!\'@+`=]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or "video"


def fetch_info(yt: str, url: str, cookies_browser: str) -> tuple[dict | None, str | None]:
    """Return (info_json, error). Tries cookies first, then plain."""
    for extra, label in (
        (["--cookies-from-browser", cookies_browser], f"cookies:{cookies_browser}"),
        ([], "no-cookies"),
    ):
        cmd = [yt, "-J", "--no-playlist", *extra, "--no-warnings", url]
        try:
            r = run(cmd)
        except subprocess.TimeoutExpired:
            return None, f"metadata timeout with {label}"
        if r.returncode == 0 and r.stdout.strip():
            try:
                return json.loads(r.stdout), None
            except json.JSONDecodeError as e:
                return None, f"bad JSON with {label}: {e}"
        last_err = f"{label}: {r.stderr.strip()[-400:]}"
    return None, last_err


def quality_format(quality: str) -> str:
    """Map human quality choice to an f-format selector."""
    q = quality.lower()
    if q == "best":
        return "bv*+ba/b"
    if q == "1080p":
        return "bv*[height<=1080]+ba/b[height<=1080]"
    if q == "720p":
        return "bv*[height<=720]+ba/b[height<=720]"
    if q == "480p":
        return "bv*[height<=480]+ba/b[height<=480]"
    if q.isdigit():
        return f"bv*[height<={q}]+ba/b[height<={q}]"
    return "bv*+ba/b"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--quality", default="best",
                    help="best | 1080p | 720p | 480p | <height>")
    ap.add_argument("--cookies-browser", default="chrome",
                    help="chrome | safari | edge | firefox")
    ap.add_argument("--output", default=".", help="working directory")
    ap.add_argument("--env-out", default="yt_env.json")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)
    env = load_env(args.env_out)
    yt = env.get("yt_dlp")
    if not yt:
        log("yt-dlp not found. Run check_env.py first.")
        return 1

    # 1. metadata
    info, err = fetch_info(yt, args.url, args.cookies_browser)
    if not info:
        log(f"Failed to fetch metadata: {err}")
        return 1

    title = info.get("title") or "video"
    duration = info.get("duration") or 0
    safe_title = sanitize(title)
    log(f"Title: {title}")
    log(f"Duration: {duration // 60}m {duration % 60:02d}s")

    # 2. download video (MP4 only)
    out_video = os.path.join(args.output, f"{safe_title}.%(ext)s")
    f_sel = quality_format(args.quality)
    log(f"Quality: {args.quality}  ->  format {f_sel}")
    cmd = [
        yt, "--no-playlist", "--no-warnings",
        "--cookies-from-browser", args.cookies_browser,
        "-f", f_sel, "--merge-output-format", "mp4",
        "-o", out_video, args.url,
    ]
    r = run(cmd)
    if r.returncode != 0:
        log(f"Video download failed with cookies; retrying without cookies... "
            f"({r.stderr.strip()[-300:]})")
        cmd2 = [
            yt, "--no-playlist", "--no-warnings",
            "-f", f_sel, "--merge-output-format", "mp4",
            "-o", out_video, args.url,
        ]
        r2 = run(cmd2)
        if r2.returncode != 0:
            log(f"Video download failed: {r2.stderr.strip()[-500:]}")
            return 2
        r = r2

    mp4s = glob.glob(os.path.join(args.output, f"{safe_title}.mp4"))
    if not mp4s:
        mp4s = glob.glob(os.path.join(args.output, "*.mp4"))
    video_path = mp4s[0] if mp4s else None
    if not video_path:
        log("No .mp4 produced — check ffmpeg/merge step.")
        return 2
    log(f"Video saved: {video_path} ({os.path.getsize(video_path) / 1e6:.1f} MB)")

    # 3. manifest
    manifest = {
        "url": args.url,
        "title": title,
        "safe_title": safe_title,
        "duration_sec": duration,
        "video_path": video_path,
        "subtitle_path": None,
        "subtitle_kind": None,
        "subtitle_lang": None,
        "quality": args.quality,
        "downloaded_at": datetime.now().isoformat(),
    }
    with open(os.path.join(args.output, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f"Manifest written: {os.path.join(args.output, 'manifest.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
