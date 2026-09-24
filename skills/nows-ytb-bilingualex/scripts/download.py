#!/usr/bin/env python3
"""
download.py — Download a YouTube video (MP4 ONLY), reusing the browser login
session via cookies. Subtitle acquisition is NO LONGER part of this script:
the bilingual subtitle is built from YouTube's official ASR (timedtext) via
`yt-dlp --write-auto-subs` + `aggregate_srt.py` (see SKILL.md).

Steps performed:
  1. Probe metadata via `yt-dlp -J` to read the title (for file naming).
  2. Download the video at the requested quality (interactive choice from the
     user, passed via --quality: best | 1080p | 720p | <height>).
  3. Write manifest.json with everything later steps need.

Auth: reuses the browser session with --cookies-from-browser. The default mweb
client works with current YouTube challenge solving when yt-dlp-ejs/deno are
available. Failures fall back to the default client, then no cookies for public
videos. Downloads use resumable native fragments and stream progress live.

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
import shutil
import subprocess
import sys
import selectors
import time
from datetime import datetime


def log(msg: str) -> None:
    print(f"[download] {msg}", flush=True)


def run(cmd: list[str], timeout: int = 1800, stream: bool = False) -> subprocess.CompletedProcess:
    log("+ " + " ".join(str(c) for c in cmd))
    if not stream:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    tail: list[str] = []
    started = time.monotonic()
    while proc.poll() is None:
        if time.monotonic() - started > timeout:
            proc.kill()
            proc.wait()
            raise subprocess.TimeoutExpired(cmd, timeout)
        for key, _ in selector.select(timeout=0.5):
            line = key.fileobj.readline()
            if line:
                print(line, end="", flush=True)
                tail.append(line)
                tail = tail[-200:]
    remainder = proc.stdout.read() if proc.stdout else ""
    if remainder:
        print(remainder, end="", flush=True)
        tail.extend(remainder.splitlines(True))
    return subprocess.CompletedProcess(cmd, proc.returncode, "", "".join(tail[-200:]))


# Sandboxes may block yt-dlp's bulk deletion of its own temp fragments after a
# successful merge (count >= 50 triggers a confirmation gate). The MP4 is
# already complete at that point, so it must not be treated as a failure.
SAFE_DELETE_MARKER = "SAFE_DELETE_BULK_CONFIRM_REQUIRED"


def cleanup_blocked_only(r: subprocess.CompletedProcess,
                         required_path: str | None = None) -> bool:
    """True when the run failed *only* because temp cleanup was blocked.

    `required_path` (the expected output MP4) guards against the case where the
    merge itself never happened: if the file is missing, this was a real
    failure and the caller must keep retrying.
    """
    if r.returncode == 0:
        return False
    err = r.stderr or ""
    if SAFE_DELETE_MARKER not in err or "Sign in to confirm" in err:
        return False
    if required_path and not os.path.exists(required_path):
        return False
    return True


def probe_duration(path: str, env: dict) -> float | None:
    """Real media duration in seconds (None if ffprobe is unavailable)."""
    ffprobe = env.get("ffprobe")
    if not ffprobe:
        ffmpeg = env.get("ffmpeg") or "ffmpeg"
        sibling = os.path.join(os.path.dirname(ffmpeg), "ffprobe")
        ffprobe = sibling if os.path.exists(sibling) else shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        r = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    try:
        return float((r.stdout or "").strip().splitlines()[-1])
    except (ValueError, IndexError):
        return None


def load_env(env_out: str) -> dict:
    with open(env_out, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize(name: str) -> str:
    """Filesystem-safe title (keep CJK and alnum, replace separators)."""
    name = re.sub(r'[\\/:*?"<>|#%&\{\}\$!\'@+`=]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or "video"


def fetch_info(yt: str, url: str, cookies_browser: str,
               player_client: str = "mweb") -> tuple[dict | None, str | None]:
    """Return (info_json, error). Tries cookies first, then plain.

    Metadata probing and download must use the same client so the selected
    format remains available in both steps.
    """
    for extra, label in (
        (["--cookies-from-browser", cookies_browser], f"cookies:{cookies_browser}"),
        ([], "no-cookies"),
    ):
        cmd = [yt, "-J", "--no-playlist", *extra, "--no-warnings", url]
        if player_client:
            cmd += ["--extractor-args", f"youtube:player_client={player_client}"]
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
    """Map human quality choice to an f-format selector.

    Recognised keywords (case-insensitive):
      best       — highest resolution/quality available
      best-vp9   — highest VP9 stream + AAC audio (best sharpness/compat
                   trade-off: VP9 1440p runs ~2x the bitrate of AV1 at the
                   same resolution, and decodes on far more players)
      best-av1   — highest AV1 stream + AAC audio (smaller files, needs a
                   recent player for hardware decode)
      1080p / 720p / 480p / <height>
    Any other value is treated as a raw yt-dlp -f selector and passed through.
    """
    q = quality.lower()
    if q == "best":
        return "bv*+ba/b"
    if q == "best-vp9":
        return ("bv*[vcodec^=vp9][height<=1440]+ba[ext=m4a]"
                "/bv*[vcodec^=vp9]+ba/b")
    if q == "best-av1":
        return ("bv*[vcodec^=av01][height<=1440]+ba[ext=m4a]"
                "/bv*[vcodec^=av01]+ba/b")
    if q == "1080p":
        return "bv*[height<=1080]+ba/b[height<=1080]"
    if q == "720p":
        return "bv*[height<=720]+ba/b[height<=720]"
    if q == "480p":
        return "bv*[height<=480]+ba/b[height<=480]"
    if q.isdigit():
        return f"bv*[height<={q}]+ba/b[height<={q}]"
    # Unknown keyword: assume the caller knows yt-dlp format syntax.
    return quality


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--quality", default="best",
                    help="best | 1080p | 720p | 480p | <height>")
    ap.add_argument("--cookies-browser", default="chrome",
                    help="chrome | safari | edge | firefox")
    ap.add_argument("--player-client", default="mweb",
                    help="youtube player_client: mweb (default) | web | "
                         "web_embedded | tv | ios | '' to disable")
    ap.add_argument("--output", default=".", help="working directory")
    ap.add_argument("--env-out", default="yt_env.json")
    ap.add_argument("--download-timeout", type=int, default=0,
                    help="download timeout seconds; 0 selects max(1800, 3x video duration)")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)
    env = load_env(args.env_out)
    yt = env.get("yt_dlp")
    if not yt:
        log("yt-dlp not found. Run check_env.py first.")
        return 1

    # 1. metadata
    info, err = fetch_info(yt, args.url, args.cookies_browser, args.player_client)
    if not info and args.player_client:
        log(f"Metadata probe failed with player_client={args.player_client}; "
            "trying the default client...")
        info, fallback_err = fetch_info(yt, args.url, args.cookies_browser, "")
        if info:
            args.player_client = ""
        else:
            err = f"{err}; default client: {fallback_err}"
    if not info:
        log(f"Failed to fetch metadata: {err}")
        return 1

    title = info.get("title") or "video"
    duration = info.get("duration") or 0
    download_timeout = (args.download_timeout
                        if args.download_timeout > 0
                        else max(1800, int(duration * 3) if duration else 1800))
    safe_title = sanitize(title)
    log(f"Title: {title}")
    log(f"Duration: {duration // 60}m {duration % 60:02d}s")

    # 2. download video (MP4 only)
    out_video = os.path.join(args.output, f"{safe_title}.%(ext)s")
    final_mp4 = os.path.join(args.output, f"{safe_title}.mp4")
    f_sel = quality_format(args.quality)
    log(f"Quality: {args.quality}  ->  format {f_sel}")
    # Native fragment downloads are resumable and avoid restarting a long video
    # after an interrupted ffmpeg stream. ffmpeg is used only for final merge.
    client_args = (["--extractor-args", f"youtube:player_client={args.player_client}"]
                   if args.player_client else [])
    ffmpeg_args = (["--ffmpeg-location", env["ffmpeg"]] if env.get("ffmpeg") else [])
    cmd = [
        yt, "--no-playlist", "--no-warnings",
        "--cookies-from-browser", args.cookies_browser,
        *client_args,
        *ffmpeg_args,
        "--continue", "--part", "--concurrent-fragments", "4",
        "-f", f_sel, "--merge-output-format", "mp4",
        "-o", out_video, args.url,
    ]
    r = run(cmd, timeout=download_timeout, stream=True)
    if r.returncode != 0 and not cleanup_blocked_only(r, final_mp4):
        log(f"Video download failed with player_client={args.player_client}; "
            f"retrying with the default client... ({r.stderr.strip()[-300:]})")
        cmd2 = [
            yt, "--no-playlist", "--no-warnings",
            "--cookies-from-browser", args.cookies_browser,
            *ffmpeg_args, "--continue", "--part", "--concurrent-fragments", "4",
            "-f", f_sel, "--merge-output-format", "mp4",
            "-o", out_video, args.url,
        ]
        r2 = run(cmd2, timeout=download_timeout, stream=True)
        if r2.returncode != 0 and not cleanup_blocked_only(r2, final_mp4):
            # Last resort: drop cookies entirely (works for public videos) —
            # some accounts hit "Sign in to confirm you're not a bot" walls.
            log(f"Video download failed: {r2.stderr.strip()[-500:]}")
            log("Retrying without cookies...")
            cmd3 = [
                yt, "--no-playlist", "--no-warnings",
                *ffmpeg_args, "--continue", "--part", "--concurrent-fragments", "4",
                "-f", f_sel, "--merge-output-format", "mp4",
                "-o", out_video, args.url,
            ]
            r3 = run(cmd3, timeout=download_timeout, stream=True)
            if r3.returncode != 0 and not cleanup_blocked_only(r3, final_mp4):
                log(f"Video download failed (no cookies): {r3.stderr.strip()[-500:]}")
                return 2
            r = r3
        else:
            r = r2
    elif cleanup_blocked_only(r, final_mp4):
        log("Note: yt-dlp finished but was blocked from deleting its temp "
            "fragments; the merged MP4 is intact (fragments left on disk).")

    mp4s = glob.glob(os.path.join(args.output, f"{safe_title}.mp4"))
    if not mp4s:
        mp4s = glob.glob(os.path.join(args.output, "*.mp4"))
    video_path = mp4s[0] if mp4s else None
    if not video_path:
        log("No .mp4 produced — check ffmpeg/merge step.")
        return 2

    # Integrity check. Even a successful network process can leave a truncated
    # file after an upstream disconnect. Compare real duration with metadata and
    # retry the resumable native path when needed.
    if duration:
        actual = probe_duration(video_path, env)
        if actual is not None and actual < duration * 0.95:
            log(f"Truncated MP4: {actual:.1f}s of {duration}s. Retrying with "
                f"the native downloader (resumable, multi-connection)...")
            os.remove(video_path)
            cmd4 = [
                yt, "--no-playlist", "--no-warnings",
                "--cookies-from-browser", args.cookies_browser, *client_args,
                *ffmpeg_args, "--continue", "--part", "--concurrent-fragments", "4",
                "-f", f_sel, "--merge-output-format", "mp4",
                "-o", out_video, args.url,
            ]
            r4 = run(cmd4, timeout=download_timeout, stream=True)
            if r4.returncode != 0 and not cleanup_blocked_only(r4, video_path):
                log(f"Retry failed: {r4.stderr.strip()[-500:]}")
                return 2
            mp4s = glob.glob(os.path.join(args.output, f"{safe_title}.mp4"))
            if not mp4s:
                log("No .mp4 after retry.")
                return 2
            video_path = mp4s[0]
            actual2 = probe_duration(video_path, env)
            if actual2 is not None and actual2 < duration * 0.95:
                log(f"Still truncated after retry: {actual2:.1f}s of {duration}s.")
                return 2
            log(f"Retry OK: {actual2:.1f}s of {duration}s.")
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
