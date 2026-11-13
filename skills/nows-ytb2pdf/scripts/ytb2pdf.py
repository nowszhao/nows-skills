#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Capture every distinct page/slide shown in a video and export a one-page-per-slide PDF.

Pipeline (see references/method-and-tuning.md for the reasoning behind each threshold):

    YouTube URL / local video
      -> probe metadata
      -> stream low-res grayscale frames into numpy
      -> mask overlay regions (top chapter bar, bottom-right webcam PiP, burned subtitles)
      -> detect hard cuts by masked frame difference
      -> split into stable segments, take the median frame of each
      -> drop blank/black frames, merge near-identical duplicate pages
      -> extract full-resolution stills at those timestamps
      -> build a PDF (one full, uncropped image per page)
      -> build a self-contained HTML audit sheet + report.json

Guarantees to check in report.json: every segment is internally static, no two
exported pages are near-identical, no blank or transition-only pages are exported.
"""
from __future__ import annotations

import argparse
import base64
import glob
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_FORMAT = "bestvideo[height<=1080][ext=mp4]/bestvideo[height<=1080]/bestvideo"
BROWSER_FALLBACKS = ["chrome", "edge", "firefox", "brave", "safari"]


def log(msg: str, quiet: bool = False) -> None:
    if not quiet:
        print(msg, flush=True)


# Import lazily-ish so `--help` still works on a machine without the deps installed.
try:
    import img2pdf  # noqa: E402
    import numpy as np  # noqa: E402
    from PIL import Image  # noqa: E402
    DEPS_ERROR = None
except ImportError as exc:  # pragma: no cover
    DEPS_ERROR = str(exc)


def need_imports() -> None:
    if DEPS_ERROR is not None:
        sys.stderr.write(
            "Missing Python package (%s).\n"
            "Install with: python3 -m pip install pillow numpy img2pdf pymupdf\n" % DEPS_ERROR
        )
        sys.exit(2)


def run(cmd: list[str], quiet: bool = False, capture: bool = False):
    if not quiet:
        log("  $ " + " ".join(str(c) for c in cmd), quiet)
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def require_bin(name: str) -> None:
    if shutil.which(name) is None:
        sys.stderr.write(
            f"Missing executable: {name}. "
            "Install ffmpeg/ffprobe (brew install ffmpeg) and yt-dlp (pip install -U yt-dlp).\n"
        )
        sys.exit(2)


# ---------------------------------------------------------------- source ----

def video_id_from_url(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else "video"


def fetch_meta(url: str, browsers: list[str], quiet: bool) -> dict:
    for b in browsers:
        p = run(
            ["yt-dlp", "--no-playlist", "--no-warnings", "--skip-download",
             "--cookies-from-browser", b, "--print",
             "%(title)s|||%(channel)s|||%(id)s|||%(duration)s", url],
            quiet=True, capture=True,
        )
        if p.returncode == 0 and "|||" in p.stdout.strip():
            parts = p.stdout.strip().split("|||")
            return {"title": parts[0], "channel": parts[1] if len(parts) > 1 else "",
                    "id": parts[2] if len(parts) > 2 else video_id_from_url(url),
                    "duration": parts[3] if len(parts) > 3 else "", "browser": b}
    return {"title": video_id_from_url(url), "channel": "", "id": video_id_from_url(url),
            "duration": "", "browser": None}


def download(url: str, work: Path, browsers: list[str], fmt: str, quiet: bool) -> tuple[Path, str | None]:
    """Download video-only stream. Try each browser's cookies, then cookie-less clients."""
    tpl = str(work / "video.%(ext)s")
    errors = []
    for b in browsers:
        for f in glob.glob(str(work / "video.*")):
            os.remove(f)
        p = run(["yt-dlp", "--no-playlist", "--no-part", "--cookies-from-browser", b,
                 "-f", fmt, "-o", tpl, url], quiet=True, capture=True)
        got = [f for f in glob.glob(str(work / "video.*")) if not f.endswith((".part", ".ytdl"))]
        if p.returncode == 0 and got:
            log(f"  downloaded via {b} cookies", quiet)
            return Path(got[0]), b
        errors.append(f"{b}: {(p.stderr or p.stdout).strip()[-220:]}")
    # Last resort: no cookies, alternate player clients.
    for client in ["tv,ios,android_vr", "mweb"]:
        for f in glob.glob(str(work / "video.*")):
            os.remove(f)
        p = run(["yt-dlp", "--no-playlist", "--no-part",
                 "--extractor-args", f"youtube:player_client={client}",
                 "-f", fmt, "-o", tpl, url], quiet=True, capture=True)
        got = [f for f in glob.glob(str(work / "video.*")) if not f.endswith((".part", ".ytdl"))]
        if p.returncode == 0 and got:
            return Path(got[0]), None
        errors.append(f"client {client}: {(p.stderr or p.stdout).strip()[-220:]}")
    raise RuntimeError("All download attempts failed:\n  " + "\n  ".join(errors))


def probe(path: Path) -> dict:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {p.stderr.strip()[:300]}")
    d = json.loads(p.stdout)
    st = (d.get("streams") or [{}])[0]
    return {"width": int(st.get("width") or 1920), "height": int(st.get("height") or 1080),
            "duration": float(d.get("format", {}).get("duration") or 0)}


# --------------------------------------------------------------- analysis ----

def sample_frames(video: Path, fps: float, w: int, h: int,
                  max_seconds: float | None, quiet: bool) -> np.ndarray:
    """Stream grayscale frames from ffmpeg; no temporary image files."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video)]
    if max_seconds:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-vf", f"fps={fps},scale={w}:{h},format=gray",
            "-f", "rawvideo", "-pix_fmt", "gray", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    chunks, size = [], w * h
    assert proc.stdout is not None
    while True:
        buf = proc.stdout.read(size)
        if len(buf) < size:
            break
        chunks.append(np.frombuffer(buf, dtype=np.uint8).reshape(h, w).copy())
    proc.stdout.close()
    err = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
    rc = proc.wait()
    if not chunks:
        raise RuntimeError(f"ffmpeg produced no frames: {err[:400]}")
    a = np.stack(chunks)
    mb = a.nbytes / 1e6
    log(f"  sampled {len(a)} frames ({mb:.0f} MB in memory)", quiet)
    if mb > 800:
        log("  WARNING: large frame buffer; consider --fps 1 for long videos", quiet)
    return a


def build_mask(h: int, w: int, top_px: int, pip_x: float, pip_y: float,
               bottom_px: int) -> np.ndarray:
    """Zero out overlay regions so they cannot be mistaken for a new page."""
    mask = np.ones((h, w), dtype=np.float32)
    if top_px > 0:
        mask[:top_px, :] = 0
    if bottom_px > 0:
        mask[h - bottom_px:, :] = 0
    if pip_x > 0 and pip_y > 0:
        mask[int(h * pip_y):, int(w * pip_x):] = 0
    return mask


def detect_segments(a: np.ndarray, mask: np.ndarray, fps: float, thr: float,
                    merge_gap: int) -> tuple[list[dict], list[dict], np.ndarray]:
    f = a.astype(np.float32)
    diff = np.abs(np.diff(f, axis=0)) * mask
    mean = diff.mean(axis=(1, 2))
    changed = (diff > 18).sum(axis=(1, 2)) / float(mask.sum())
    idx = np.where(mean > thr)[0]
    events, groups = [], []
    for i in idx:
        if groups and i - groups[-1][-1] <= merge_gap:
            groups[-1].append(int(i))
        else:
            groups.append([int(i)])
    for g in groups:
        j = int(g[int(np.argmax(mean[g]))])
        events.append({"t": round(j / fps, 2), "frame": j,
                       "mean": round(float(mean[j]), 2),
                       "changed_frac": round(float(changed[j]), 4),
                       "span": [round(g[0] / fps, 2), round(g[-1] / fps, 2)]})
    bounds = [0] + [g[0] + 1 for g in groups] + [len(a)]
    segs = []
    for k in range(len(bounds) - 1):
        s, e = bounds[k], bounds[k + 1]
        rep = (s + e) // 2
        internal = np.abs((f[s:e] - f[rep]) * mask).mean(axis=(1, 2))
        body = f[rep] * mask
        # Real hard cuts score 10-53 in masked MAD; webcam fades, cursors and
        # subtitle flicker stay around 0.5-1.1. Only flag mid-segment motion
        # well above the cut threshold. A spike confined to the first ~2s is
        # transition afterglow, not an unreported page switch.
        mid_thr = max(1.5, thr * 1.5)
        bad = np.where(internal > mid_thr)[0]
        early_only = bool(len(bad) == 0 or (bad < max(2, int(fps * 2))).all())
        segs.append({
            "i": k, "start": round(s / fps, 2), "end": round(e / fps, 2),
            "t": round(rep / fps, 3), "dur": round((e - s) / fps, 2), "rep": rep,
            "internal_max_mad": round(float(internal.max()), 3),
            "internal_mid_thr": round(mid_thr, 2),
            "internal_over_thr": int(len(bad)), "internal_early_only": early_only,
            "internal_suspicious": bool(len(bad) > 0 and not early_only),
            "std": round(float(body.std()), 2), "brightness": round(float(body.mean()), 2),
        })
    return segs, events, mean


def deduplicate(segs: list[dict], reps_m: np.ndarray, dup_thr: float,
                blank_std: float, keep_blank: bool, thr: float) -> tuple[list[dict], dict]:
    """Drop blank frames and near-identical pages; keep first occurrence of each page."""
    feat = reps_m[:, ::4, ::4]  # coarse 1/4 scale for a cheap all-pairs scan
    coarse = np.full((len(segs), len(segs)), np.inf, dtype=np.float32)
    for i in range(len(segs)):
        coarse[i] = np.abs(feat - feat[i]).mean(axis=(1, 2))
    iu = np.triu_indices(len(segs), 1)
    min_coarse = float(coarse[iu].min()) if len(segs) > 1 else None

    removed_blank, removed_dup, kept = [], [], []
    for s in segs:
        if not keep_blank and s["std"] < blank_std:
            s["status"] = "blank_removed"
            removed_blank.append(s["i"] + 1)
            continue
        dup_of, dup_dist = None, None
        for prev in kept:
            if coarse[s["i"], prev["i"]] > dup_thr * 3:
                continue
            d = float(np.abs(reps_m[s["i"]] - reps_m[prev["i"]]).mean())
            if d < dup_thr:
                dup_of, dup_dist = prev["i"] + 1, round(d, 3)
                break
        if dup_of is not None:
            s["status"] = f"duplicate_of_P{dup_of:02d}"
            s["dup_distance"] = dup_dist
            removed_dup.append({"page": s["i"] + 1, "duplicate_of": dup_of,
                                "distance": dup_dist, "t": s["t"]})
            continue
        s["status"] = "kept"
        if s["internal_suspicious"]:
            s["warning"] = ("segment changes mid-way (possible build animation or a "
                            "missed cut); inspect this segment by hand")
        kept.append(s)
    return kept, {"min_coarse_pair_distance": None if min_coarse is None else round(min_coarse, 3),
                  "blank_removed": removed_blank, "duplicates_removed": removed_dup}


# ----------------------------------------------------------------- output ----

def slug(text: str, limit: int = 60) -> str:
    s = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "_", text).strip("._")
    return (s[:limit] or "slides")


def extract_stills(video: Path, kept: list[dict], pages_dir: Path, quiet: bool) -> list[str]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for k, s in enumerate(kept, 1):
        out = pages_dir / f"p{k:03d}.jpg"
        p = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{s['t']:.3f}",
                 "-i", str(video), "-frames:v", "1", "-q:v", "2", "-y", str(out)],
                quiet=True, capture=True)
        if p.returncode != 0 or not out.exists():
            # Slow but frame-accurate fallback (seek after input).
            run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(video),
                 "-ss", f"{s['t']:.3f}", "-frames:v", "1", "-q:v", "2", "-y", str(out)],
                quiet=True, capture=True)
        if not out.exists():
            raise RuntimeError(f"Failed to extract frame at t={s['t']}s")
        paths.append(str(out))
    log(f"  extracted {len(paths)} full-resolution stills", quiet)
    return paths


def page_size(spec: str, ratio: float) -> tuple[float, float]:
    if spec == "auto":
        return (960.0, round(960.0 / ratio, 2))
    m = re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", spec)
    if not m:
        raise ValueError("--page-size must be 'auto' or WIDTHxHEIGHT in pt, e.g. 960x540")
    return float(m.group(1)), float(m.group(2))


def make_pdf(files: list[str], out: Path, pw: float, ph: float, title: str,
             channel: str, source: str, count: int) -> None:
    layout = img2pdf.get_layout_fun(pagesize=(pw, ph), border=(0, 0),
                                    fit=img2pdf.FitMode.into)
    with open(out, "wb") as f:
        f.write(img2pdf.convert(
            files, layout_fun=layout, title=title, author=channel or "nows-ytb2pdf",
            subject=f"All {count} unique pages captured from {source}, in playback order"))


def verify_pdf(path: Path, expected: int) -> dict:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # type: ignore
        except ImportError:
            return {"checked": False, "reason": "pymupdf not installed"}
    doc = fitz.open(str(path))
    first = doc[0].get_images(full=True)
    return {"checked": True, "pages": len(doc),
            "page_size_pt": [round(doc[0].rect.width, 2), round(doc[0].rect.height, 2)],
            "first_page_image_px": [first[0][2], first[0][3]] if first else None,
            "page_count_matches": len(doc) == expected}


CSS = """body{margin:0;background:#f6f7f9;color:#1a1d24;font:14px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}
header{padding:28px 32px 22px;background:#fff;border-bottom:1px solid #e3e6ea}
h1{margin:0 0 6px;font-size:20px}h2{margin:0 0 10px;font-size:13px;color:#6b7280;font-weight:500}
.meta{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.chip{background:#eef2f7;border:1px solid #dfe5ec;border-radius:6px;padding:4px 10px;font-size:12px;color:#374151}
main{padding:24px 32px 48px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px}
figure{margin:0;background:#fff;border:1px solid #e3e6ea;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.04)}
figure img{display:block;width:100%;height:auto;background:#0b1725}
figcaption{padding:8px 12px;font-size:12px;color:#4b5563;border-top:1px solid #eef0f3}
a{color:inherit;text-decoration:none}.note{margin:0 0 12px;padding:12px 16px;border-radius:8px;font-size:13px}
.ok{background:#eef7f1;border:1px solid #cfe7d9;color:#1f5c3a}.warn{background:#fff6e8;border:1px solid #f2dfba;color:#7a5312}"""


def make_index(path: Path, files: list[str], kept: list[dict], meta: dict,
               report: dict, pdf_name: str) -> None:
    cards = []
    for n, (f, s) in enumerate(zip(files, kept), 1):
        im = Image.open(f).convert("RGB")
        im.thumbnail((440, 248))
        b = io.BytesIO()
        im.save(b, "JPEG", quality=80)
        b64 = base64.b64encode(b.getvalue()).decode()
        t = int(s["t"])
        cards.append(
            f'<figure><a href="pages_full/{Path(f).name}" target="_blank">'
            f'<img src="data:image/jpeg;base64,{b64}" loading="lazy" alt="P{n:02d}"></a>'
            f'<figcaption><b>P{n:02d}</b> · PDF 第 {n} 页 · '
            f'{t//60:02d}:{t%60:02d} · 停留 {s["dur"]:.0f}s · 原片段 P{s["i"]+1:02d}</figcaption></figure>')
    warns = report["warnings"]
    notes = [f'<p class="note ok">{html.escape(report["summary"])}</p>']
    if warns:
        notes.append('<p class="note warn"><b>需人工复核</b><br>' +
                     "<br>".join(html.escape(w) for w in warns) + "</p>")
    chips = [
        f'来源 {html.escape(meta["source"])}',
        f'{meta["width"]}×{meta["height"]} / {int(meta["duration"])//60}:{int(meta["duration"])%60:02d}',
        f'{report["switch_events"]} 次切换 → {report["segments_total"]} 个片段 → {len(kept)} 个唯一页面',
        "按播放顺序排列", f'<a href="{html.escape(pdf_name)}" target="_blank">打开 PDF →</a>',
        '<a href="report.json" target="_blank">核验数据 →</a>',
    ]
    doc = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>视频页面核对表 · {len(kept)} 页</title><style>{CSS}</style></head><body>
<header><h1>视频页面截图 · 全量核对表</h1><h2>{html.escape(meta['title'])}</h2>
<div class="meta">{''.join(f'<span class="chip">{c}</span>' for c in chips)}</div></header>
<main>{''.join(notes)}<div class="grid">{''.join(cards)}</div></main></body></html>"""
    path.write_text(doc, encoding="utf-8")


# ------------------------------------------------------------------- main ----

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Export every distinct page/slide from a video as a PDF (no omissions, no duplicates).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("url", nargs="?", help="YouTube watch URL / any yt-dlp supported URL")
    ap.add_argument("--video", help="Use a local video file instead of downloading (never modified)")
    ap.add_argument("--out-dir", help="Output directory (default: ./ytb2pdf-<video_id>)")
    ap.add_argument("--title", help="Override PDF title metadata")
    ap.add_argument("--browser", default="chrome",
                    help="Browser cookies to try, comma-separated (safari may need macOS permissions)")
    ap.add_argument("--format", default=DEFAULT_FORMAT, help="yt-dlp video-stream format selector")
    ap.add_argument("--fps", type=float, default=2.0, help="Analysis sampling rate (frames/second)")
    ap.add_argument("--sample-width", type=int, default=320, help="Analysis frame width (16:9 assumed)")
    ap.add_argument("--switch-threshold", type=float, default=1.0,
                    help="Masked mean-abs-diff above this value = a hard cut")
    ap.add_argument("--merge-gap", type=int, default=3,
                    help="Merge cut events within N sampled frames (transition afterglow)")
    ap.add_argument("--dup-threshold", type=float, default=3.0,
                    help="Merge pages whose full-res masked MAD is below this value")
    ap.add_argument("--blank-std", type=float, default=2.0,
                    help="Drop pages with body contrast below this value (black/blank frames)")
    ap.add_argument("--keep-blank", action="store_true", help="Keep blank/black pages")
    ap.add_argument("--mask-top-px", type=int, default=16,
                    help="Mask top N analysis rows (chapter bar / progress dots); 0 disables")
    ap.add_argument("--pip-x", type=float, default=0.86,
                    help="Mask right side from this x ratio (webcam PiP); 0 disables")
    ap.add_argument("--pip-y", type=float, default=0.76,
                    help="Mask bottom from this y ratio (webcam PiP); 0 disables")
    ap.add_argument("--mask-bottom-px", type=int, default=0,
                    help="Mask bottom N analysis rows (burned-in subtitles); 0 disables")
    ap.add_argument("--no-mask", action="store_true", help="Disable all overlay masks")
    ap.add_argument("--page-size", default="auto",
                    help="PDF page size in pt: 'auto' (960pt wide, source ratio) or WIDTHxHEIGHT")
    ap.add_argument("--keep-video", action="store_true", help="Keep the downloaded video file")
    ap.add_argument("--reuse-video", action="store_true",
                    help="Reuse an existing video.* in --out-dir instead of downloading")
    ap.add_argument("--no-html", action="store_true", help="Skip the HTML audit sheet")
    ap.add_argument("--dry-run", action="store_true",
                    help="Analyse and write report.json only; do not extract stills or build the PDF")
    ap.add_argument("--max-seconds", type=float, default=None,
                    help="Analyse only the first N seconds (testing/tuning only, breaks full coverage)")
    ap.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = ap.parse_args()
    need_imports()

    if not args.url and not args.video:
        ap.error("Provide a video URL or --video PATH")
    require_bin("ffmpeg")
    require_bin("ffprobe")
    if not args.video:
        require_bin("yt-dlp")

    browsers = [b.strip() for b in args.browser.split(",") if b.strip()]
    for b in BROWSER_FALLBACKS:
        if b not in browsers:
            browsers.append(b)

    vid = video_id_from_url(args.url or "")
    out = Path(args.out_dir).expanduser().resolve() if args.out_dir else Path.cwd() / f"ytb2pdf-{vid}"
    out.mkdir(parents=True, exist_ok=True)
    log(f"[1/6] Source → {out}", args.quiet)

    downloaded, meta = None, {}
    if args.video:
        video = Path(args.video).expanduser().resolve()
        if not video.exists():
            sys.exit(f"Local video not found: {video}")
        meta = {"title": args.title or video.stem, "channel": "", "id": vid,
                "source": str(video), "browser": None}
    else:
        info = fetch_meta(args.url, browsers, args.quiet)
        meta = {"title": args.title or info["title"], "channel": info["channel"],
                "id": info["id"], "source": args.url, "browser": info["browser"]}
        existing = [f for f in glob.glob(str(out / "video.*")) if not f.endswith(".part")]
        if args.reuse_video and existing:
            video = Path(existing[0])
            log(f"  reusing {video.name}", args.quiet)
        else:
            video, used = download(args.url, out, browsers, args.format, args.quiet)
            downloaded = video
            if used:
                meta["browser"] = used
    info = probe(video)
    meta.update({"width": info["width"], "height": info["height"], "duration": info["duration"]})
    log(f"  {meta['width']}×{meta['height']}, {info['duration']:.0f}s — {meta['title']}", args.quiet)

    w = args.sample_width
    h = max(2, round(w * info["height"] / info["width"]))
    top = 0 if args.no_mask else args.mask_top_px
    bottom = 0 if args.no_mask else args.mask_bottom_px
    pip_x = 0 if args.no_mask else args.pip_x
    pip_y = 0 if args.no_mask else args.pip_y

    log("[2/6] Sampling frames", args.quiet)
    a = sample_frames(video, args.fps, w, h, args.max_seconds, args.quiet)
    mask = build_mask(h, w, top, pip_x, pip_y, bottom)

    log("[3/6] Detecting cuts and stable segments", args.quiet)
    segs, events, _ = detect_segments(a, mask, args.fps, args.switch_threshold, args.merge_gap)
    log(f"  {len(events)} cuts → {len(segs)} segments", args.quiet)
    reps_m = np.stack([a[s["rep"]].astype(np.float32) for s in segs]) * mask
    kept, dd = deduplicate(segs, reps_m, args.dup_threshold, args.blank_std,
                           args.keep_blank, args.switch_threshold)
    log(f"  kept {len(kept)} unique pages "
        f"(blank removed: {len(dd['blank_removed'])}, duplicates merged: {len(dd['duplicates_removed'])})",
        args.quiet)

    warnings = []
    for s in kept:
        if s.get("warning"):
            warnings.append(f"P{s['i']+1:02d} (t={s['t']:.0f}s): {s['warning']}；请查看该段前后是否有渐进动画被合并或拆开")
    if args.max_seconds:
        warnings.append(f"--max-seconds {args.max_seconds} 只分析了片段，不代表全片覆盖")
    if dd["duplicates_removed"]:
        warnings.append("有重复页面被自动合并，见 report.json 的 duplicates_removed 列表")
    unstable = [s["i"] + 1 for s in segs if s["internal_suspicious"]]
    log(f"  min coarse pair distance: {dd['min_coarse_pair_distance']}", args.quiet)

    report = {
        "source": meta,
        "params": {"fps": args.fps, "sample": [w, h], "switch_threshold": args.switch_threshold,
                   "merge_gap": args.merge_gap, "dup_threshold": args.dup_threshold,
                   "blank_std": args.blank_std, "mask_top_px": top, "mask_bottom_px": bottom,
                   "pip": [pip_x, pip_y], "page_size": args.page_size,
                   "max_seconds": args.max_seconds},
        "frames_sampled": len(a), "switch_events": len(events), "events": events,
        "segments_total": len(segs), "segments": segs,
        "final_pages": len(kept), "pages": kept,
        "min_coarse_pair_distance": dd["min_coarse_pair_distance"],
        "blank_removed": dd["blank_removed"], "duplicates_removed": dd["duplicates_removed"],
        "segments_with_internal_motion": unstable,
        "warnings": warnings,
        "summary": (f"逐帧比对：{len(events)} 次画面切换切出 {len(segs)} 个片段；"
                    f"剔除 {len(dd['blank_removed'])} 个空白页、合并 {len(dd['duplicates_removed'])} 个重复页，"
                    f"最终 {len(kept)} 个唯一页面；代表帧两两最相似距离 "
                    f"{dd['min_coarse_pair_distance']}（低于 {args.dup_threshold} 才判重复）。"),
        "outputs": {},
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  wrote report.json", args.quiet)

    if args.dry_run:
        log("[dry-run] Stopping before still extraction / PDF. Report written.", args.quiet)
        if downloaded and not args.keep_video:
            downloaded.unlink(missing_ok=True)
        return

    log("[4/6] Extracting full-resolution stills", args.quiet)
    files = extract_stills(video, kept, out / "pages_full", args.quiet)

    log("[5/6] Building PDF", args.quiet)
    pw, ph = page_size(args.page_size, info["width"] / info["height"])
    pdf = out / (slug(meta["title"]) + "_slides.pdf")
    make_pdf(files, pdf, pw, ph, meta["title"], meta.get("channel", ""),
             meta["source"], len(kept))
    report["outputs"]["pdf"] = str(pdf)
    report["outputs"]["pages_dir"] = str(out / "pages_full")
    log(f"  {pdf.name} — {len(files)} pages, {pdf.stat().st_size/1e6:.1f} MB", args.quiet)

    if not args.no_html:
        log("[6/6] Building HTML audit sheet", args.quiet)
        index = out / "页面核对表.html"
        make_index(index, files, kept, meta, report, pdf.name)
        report["outputs"]["html"] = str(index)
    else:
        log("[6/6] HTML audit sheet skipped", args.quiet)

    report["verification"] = verify_pdf(pdf, len(kept))
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    v = report["verification"]
    if v.get("checked") and not v.get("page_count_matches"):
        sys.stderr.write("ERROR: PDF page count does not match the page list.\n")
        sys.exit(1)

    if downloaded and not args.keep_video:
        downloaded.unlink(missing_ok=True)
    log(f"\nDone. PDF: {pdf}", args.quiet)
    if warnings:
        log("Review the warnings above / in report.json before delivering.", args.quiet)


if __name__ == "__main__":
    main()
