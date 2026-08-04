#!/usr/bin/env python3
"""
download.py — Download a YouTube video (MP4) and its ORIGINAL-language subtitle
(prefer manual upload, fall back to auto-generated ASR), reusing the browser
login session via cookies.

Steps performed:
  1. Probe metadata via `yt-dlp -J` to read title, duration, and the available
     subtitle tracks (manual vs automatic_captions).
  2. Choose the subtitle track: manual first, auto-captions as fallback.
  3. Download the video at the requested quality (interactive choice from the
     user, passed via --quality: best | 1080p | 720p | <height>).
  4. Download the chosen subtitle and convert it to .ass (via ffmpeg).
  5. Write manifest.json with everything later steps need.

Auth: reuses the browser session with --cookies-from-browser. If that fails
(e.g. Keychain permission or no login), retries without cookies for public
videos.

Usage:
    python3 download.py --url <URL> [--quality best|1080p|720p|<height>] \
        [--cookies-browser chrome] [--lang en] [--output <dir>] \
        [--env-out yt_env.json]

Exit codes: 0 ok, 1 fatal, 2 download/subtitle issues that may be retryable.
"""

import argparse
import json
import os
import subprocess
import sys
import glob
import re
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
        # keep the first error for reporting; try next strategy
        last_err = f"{label}: {r.stderr.strip()[-400:]}"
    return None, last_err


def pick_subtitle(info: dict, lang: str) -> dict:
    """Choose the subtitle track: manual first, auto-captions fallback."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    if lang in manual and manual[lang]:
        return {"kind": "manual", "lang": lang, "tracks": manual[lang]}
    if lang in auto and auto[lang]:
        return {"kind": "auto", "lang": lang, "tracks": auto[lang]}
    # language may be stored with region, e.g. en-US
    for key in list(manual) + list(auto):
        if key.split("-")[0] == lang.split("-")[0]:
            if key in manual and manual[key]:
                return {"kind": "manual", "lang": key, "tracks": manual[key]}
            if key in auto and auto[key]:
                return {"kind": "auto", "lang": key, "tracks": auto[key]}
    return {"kind": None, "lang": None, "tracks": []}


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
    # default to best
    return "bv*+ba/b"


def find_subs(directory: str) -> list[str]:
    """Find subtitle files (ass/srt/vtt) in a directory, newest first."""
    found = []
    for ext in ("ass", "srt", "vtt"):
        found += glob.glob(os.path.join(directory, f"*.{ext}"))
    found.sort(key=os.path.getmtime, reverse=True)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--quality", default="best",
                    help="best | 1080p | 720p | 480p | <height>")
    ap.add_argument("--cookies-browser", default="chrome",
                    help="chrome | safari | edge | firefox")
    ap.add_argument("--lang", default="en", help="source subtitle language")
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

    # 2. subtitle track choice
    sub = pick_subtitle(info, args.lang)
    if sub["kind"] is None:
        log(f"WARNING: no subtitle track found for language '{args.lang}' "
            "(manual or auto). Subtitles will be skipped.")
    else:
        log(f"Subtitle: {sub['kind']} ({sub['lang']}) — "
            f"{len(sub['tracks'])} format(s) available")

    # 3. download video
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

    # 4. download subtitle (converted to .ass)
    sub_path = None
    sub_kind = None
    if sub["kind"]:
        sub_dir = os.path.join(args.output, "subs")
        os.makedirs(sub_dir, exist_ok=True)
        out_sub = os.path.join(sub_dir, f"{safe_title}.%(ext)s")
        sub_cmd = [
            yt, "--no-playlist", "--no-warnings",
            "--cookies-from-browser", args.cookies_browser,
            "--skip-download",
            "--sub-langs", sub["lang"],
            "--sub-format", "ass/srt/best",
            "--convert-subs", "ass",
            "-o", out_sub, args.url,
        ]
        # append the write flag at the END; never insert in the middle (the
        # cookies-from-browser pair must stay intact)
        if sub["kind"] == "auto":
            sub_cmd.append("--write-auto-subs")
        else:
            sub_cmd.append("--write-subs")
        rs = run(sub_cmd)
        if rs.returncode == 0:
            found = find_subs(sub_dir)
            if found:
                sub_path = found[0]
                sub_kind = sub["kind"]
                log(f"Subtitle saved: {sub_path} ({sub_kind})")
            else:
                # retry without cookies for public subtitles
                sub_cmd = [c for c in sub_cmd if c not in
                           ("--cookies-from-browser", args.cookies_browser)]
                rs2 = run(sub_cmd)
                found = find_subs(sub_dir)
                if found:
                    sub_path = found[0]
                    sub_kind = sub["kind"]
                    log(f"Subtitle saved (no cookies): {sub_path} ({sub_kind})")
        if not sub_path:
            log("Subtitle download failed; continuing with video only.")

    # 5. manifest
    manifest = {
        "url": args.url,
        "title": title,
        "safe_title": safe_title,
        "duration_sec": duration,
        "video_path": video_path,
        "subtitle_path": sub_path,
        "subtitle_kind": sub_kind,
        "subtitle_lang": sub["lang"],
        "quality": args.quality,
        "downloaded_at": datetime.now().isoformat(),
    }
    with open(os.path.join(args.output, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    log(f"Manifest written: {os.path.join(args.output, 'manifest.json')}")

    if not sub_path:
        log("NOTE: no subtitle — the translation step cannot run without it.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
