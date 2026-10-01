#!/usr/bin/env python3
"""
独立校验:候选视频是否真的来自订阅频道。

candidates.json 里的 channel_id 取自本地订阅表,属于自证。
本脚本对每条视频调用 yt-dlp 拿 YouTube 侧的真实归属频道,
再与订阅表比对,能发现「频道改名/合并/订阅表过期/抓错频道」等问题。

用法: python3 verify_subscriptions.py --dir <工作目录> [--all]
默认只校验 reasons.json 的 picks;--all 校验全部候选。
"""
import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _find_ytdlp():
    p = shutil.which("yt-dlp")
    if p:
        return p
    for c in ("/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp",
              str(Path.home() / "miniconda3/bin/yt-dlp"),
              str(Path.home() / "anaconda3/bin/yt-dlp")):
        if Path(c).exists():
            return c
    return "yt-dlp"


YTDLP = _find_ytdlp()


def load_subs(path: Path):
    subs = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = [p for p in re.split(r"\t|\\t", line.strip()) if p]
        if len(parts) >= 2 and parts[1].strip().startswith("UC"):
            subs[parts[1].strip()] = parts[0].strip()
    return subs


def probe(v):
    """拿 YouTube 侧的真实归属频道。"""
    for extra in (["--cookies-from-browser", "chrome"], []):
        try:
            p = subprocess.run(
                [YTDLP, *extra, "--dump-json", "--no-warnings", "--no-playlist",
                 "--skip-download", v["url"]],
                capture_output=True, text=True, timeout=90)
            d = json.loads(p.stdout)
            return {
                "video_id": v["video_id"],
                "title": v["title"],
                "claimed_channel": v.get("channel"),
                "claimed_id": v.get("channel_id"),
                "real_id": d.get("channel_id"),
                "real_channel": d.get("channel") or d.get("uploader"),
                "ok": None,
            }
        except Exception:  # noqa: BLE001
            continue
    return {"video_id": v["video_id"], "title": v["title"],
            "claimed_channel": v.get("channel"), "claimed_id": v.get("channel_id"),
            "real_id": None, "real_channel": None, "ok": None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--all", action="store_true", help="校验全部候选而非仅 picks")
    args = ap.parse_args()

    base = Path(args.dir).expanduser().resolve()
    subs = load_subs(base / "subscriptions.tsv")
    data = json.loads((base / "candidates.json").read_text(encoding="utf-8"))
    cands = data.get("candidates", [])

    if not args.all:
        rp = base / "reasons.json"
        if rp.exists():
            ids = {p["video_id"] for p in json.loads(
                rp.read_text(encoding="utf-8")).get("picks", [])}
            cands = [c for c in cands if c["video_id"] in ids]

    print(f"[*] 校验 {len(cands)} 条视频的真实归属频道 ...", file=sys.stderr)
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        rows = list(ex.map(probe, cands))

    ok = mismatch = unknown = 0
    for r in rows:
        if not r["real_id"]:
            r["ok"] = "unknown"
            unknown += 1
        elif r["real_id"] == r["claimed_id"]:
            r["ok"] = "ok"
            ok += 1
        else:
            r["ok"] = "mismatch"
            mismatch += 1
            r["in_subs"] = r["real_id"] in subs

    print(f"\n归属一致: {ok} | 不一致: {mismatch} | 查不到: {unknown}\n")
    for r in rows:
        if r["ok"] != "ok":
            flag = "!!" if r["ok"] == "mismatch" else "??"
            print(f"{flag} [{r['ok']}] {r['title'][:50]}")
            print(f"     声称: {r['claimed_channel']} ({r['claimed_id']})")
            print(f"     实际: {r['real_channel']} ({r['real_id']})"
                  f"{' <- 仍在订阅表' if r.get('in_subs') else ' <- 不在订阅表'}")
    if mismatch == 0:
        in_subs = sum(1 for r in rows if r["real_id"] in subs)
        print(f"全部视频均来自订阅频道({in_subs}/{len(rows)} 可在订阅表中找到对应 channel_id)。")
    return 0 if mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
