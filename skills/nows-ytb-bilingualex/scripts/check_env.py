#!/usr/bin/env python3
"""
check_env.py — Ensure yt-dlp and ffmpeg are available for the pipeline.

Runs three probes:
  1. yt-dlp   — on PATH, or install into an isolated venv via pip
  2. ffmpeg   — on PATH (brew/apt), or install the `imageio-ffmpeg` wheel
               and reuse its bundled static binary
  3. Python   — record the interpreter used for later steps

Writes a machine-readable env file (JSON) that every other script in this
skill reads to locate binaries. By default writes to the *current working
directory* as `yt_env.json`, but any path can be given with --env-out.

Usage:
    python3 check_env.py [--env-out <path>] [--venv <path>]

Exit codes:
    0  everything ready
    1  a hard requirement could not be satisfied
"""

import argparse
import json
import os
import shutil
import subprocess
import sys


def log(msg: str) -> None:
    print(f"[check_env] {msg}", flush=True)


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def usable_binary(path: str | None, version_arg: str = "--version") -> bool:
    if not path or not os.path.exists(path):
        return False
    try:
        return run([path, version_arg], timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def probe_yt_dlp(venv_dir: str) -> str | None:
    """Return a usable yt-dlp path, installing into an isolated venv if needed."""
    found = which("yt-dlp")
    if usable_binary(found):
        log(f"yt-dlp found on PATH: {found}")
        return found


    candidate = os.path.join(venv_dir, "bin", "yt-dlp")
    if usable_binary(candidate):
        log(f"yt-dlp found in cached venv: {candidate}")
        return candidate

    log("yt-dlp not on PATH — installing into isolated venv...")
    os.makedirs(venv_dir, exist_ok=True)
    venv_py = os.path.join(venv_dir, "bin", "python")
    if not os.path.exists(venv_py):
        r = run([sys.executable, "-m", "venv", venv_dir])
        if r.returncode != 0:
            log(f"venv creation failed: {r.stderr.strip()}")
            return None
    r = run([venv_py, "-m", "pip", "install", "--quiet", "yt-dlp"])
    if r.returncode != 0:
        log(f"yt-dlp install failed: {r.stderr.strip()}")
        return None
    candidate = which("yt-dlp") or candidate
    log(f"yt-dlp installed at: {candidate}")
    return candidate


def probe_ffmpeg(venv_dir: str) -> str | None:
    """Return a usable ffmpeg path; fall back to imageio-ffmpeg's static binary."""
    found = which("ffmpeg")
    if usable_binary(found, "-version"):
        log(f"ffmpeg found on PATH: {found}")
        return found


    venv_py = os.path.join(venv_dir, "bin", "python")
    if os.path.exists(venv_py):
        code = "import imageio_ffmpeg as i; print(i.get_ffmpeg_exe())"
        cached = run([venv_py, "-c", code])
        exe = cached.stdout.strip()
        if cached.returncode == 0 and usable_binary(exe, "-version"):
            log(f"ffmpeg found in cached venv: {exe}")
            return exe

    log("ffmpeg not on PATH — trying imageio-ffmpeg wheel...")
    if not os.path.exists(venv_py):
        r = run([sys.executable, "-m", "venv", venv_dir])
        if r.returncode != 0:
            log(f"venv creation failed: {r.stderr.strip()}")
            return None
    r = run([venv_py, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"])
    if r.returncode != 0:
        log(f"imageio-ffmpeg install failed: {r.stderr.strip()}")
        return None
    try:
        code = (
            "import imageio_ffmpeg as i; print(i.get_ffmpeg_exe())"
        )
        r = run([venv_py, "-c", code])
        exe = r.stdout.strip()
        if r.returncode == 0 and exe and os.path.exists(exe):
            log(f"ffmpeg via imageio-ffmpeg: {exe}")
            return exe
    except Exception as e:  # pragma: no cover
        log(f"imageio-ffmpeg probe failed: {e}")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--env-out", default="yt_env.json", help="where to write env JSON")
    ap.add_argument(
        "--venv",
        default=os.path.join(
            os.path.expanduser("~"),
            ".workbuddy",
            "binaries",
            "python",
            "envs",
            "ytdlp-env",
        ),
        help="isolated venv dir for yt-dlp / ffmpeg fallback installs",
    )
    args = ap.parse_args()

    # Reuse a valid machine-level result. Work directories can safely copy this
    # JSON instead of repeating package installation on every video.
    if os.path.exists(args.env_out):
        try:
            with open(args.env_out, encoding="utf-8") as f:
                cached = json.load(f)
            if (usable_binary(cached.get("yt_dlp"))
                    and usable_binary(cached.get("ffmpeg"), "-version")):
                log(f"reusing valid environment cache: {args.env_out}")
                return 0
        except (OSError, ValueError):
            pass

    env = {
        "yt_dlp": None,
        "ffmpeg": None,
        "ffprobe": shutil.which("ffprobe"),
        "python": sys.executable,
        "checked_at": __import__("datetime").datetime.now().isoformat(),
    }

    env["yt_dlp"] = probe_yt_dlp(args.venv)
    env["ffmpeg"] = probe_ffmpeg(args.venv)

    with open(args.env_out, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    log(f"env file written: {args.env_out}")

    missing = [k for k in ("yt_dlp", "ffmpeg") if not env[k]]
    if missing:
        log(f"MISSING: {', '.join(missing)}")
        log(
            "Hints: install ffmpeg via `brew install ffmpeg` (macOS) or "
            "`apt install ffmpeg` (Debian/Ubuntu). yt-dlp usually resolves via pip."
        )
        return 1
    log("All requirements satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
