#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASS / SRT 字幕 → 合规审查用的 transcript

用法:
  python ass_to_transcript.py --sub subtitles.ass
  python ass_to_transcript.py --sub subtitles.ass -o downloads/ --chunk-min 20

产物（默认写到字幕同目录）:
  transcript.json        结构化片段（秒级 start/end），供 trim_video.py 对齐整句
  transcript.txt         整篇文本，每行 [HH:MM:SS] 中文
  transcript.partNN.txt  按 --chunk-min 分块（长视频逐块审查，块间有重叠）

bilingual ASS（BiliMix 风格，同一时间戳 English + Chinese 两行）会自动只取中文行。
"""
import argparse
import json
import os
import re
import sys

CJK = re.compile(r"[\u4e00-\u9fff]")
ASS_TAG = re.compile(r"\{[^}]*\}")
SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)")


def log(m):
    print(m, flush=True)


def clean(text):
    text = ASS_TAG.sub("", text)
    text = text.replace("\\N", " ").replace("\\n", " ").replace("\\h", " ")
    return re.sub(r"\s+", " ", text).strip()


def ts_ass(s):
    """0:00:01.00 → 秒"""
    h, m, sec = s.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(sec)


def ts_srt(s):
    """00:00:01,000 → 秒"""
    h, m, sec, ms = SRT_TIME.search(s).groups()
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms.ljust(3, "0")[:3]) / 1000.0


def fmt(t):
    t = int(round(t))
    return "%02d:%02d:%02d" % (t // 3600, t % 3600 // 60, t % 60)


def parse_ass(path):
    fields = None
    section = ""
    entries = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip().lower()
                continue
            if section != "events":
                continue
            low = line.lower()
            if low.startswith("format:"):
                fields = [x.strip().lower() for x in line.split(":", 1)[1].split(",")]
                continue
            if not low.startswith("dialogue:"):
                continue
            body = line.split(":", 1)[1]
            if not fields:
                fields = ["layer", "start", "end", "style", "name",
                          "marginl", "marginr", "marginv", "effect", "text"]
            parts = body.split(",", len(fields) - 1)
            if len(parts) < len(fields):
                continue
            d = dict(zip(fields, parts))
            try:
                st, en = ts_ass(d["start"]), ts_ass(d["end"])
            except Exception:
                continue
            entries.append({"start": st, "end": en,
                            "style": (d.get("style") or "").strip(),
                            "text": clean(d.get("text", ""))})
    return entries


def parse_srt(path):
    text = open(path, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n")
    entries = []
    for blk in re.split(r"\n\s*\n", text):
        lines = [l.strip() for l in blk.split("\n") if l.strip()]
        if not lines:
            continue
        idx = 0
        if "-->" not in lines[0]:
            if len(lines) > 1 and "-->" in lines[1]:
                idx = 1
            else:
                continue
        try:
            a, b = lines[idx].split("-->")
            st, en = ts_srt(a), ts_srt(b)
        except Exception:
            continue
        entries.append({"start": st, "end": en, "style": "",
                        "text": clean(" ".join(lines[idx + 1:]))})
    return entries


def is_cjk(text):
    n = len(CJK.findall(text))
    total = len(re.sub(r"\s", "", text))
    return n >= 2 and n / max(1, total) >= 0.2


def select(entries):
    """同时间戳的多行（bilingual）只取中文；重复行去重"""
    groups, order = {}, []
    for e in entries:
        if not e["text"]:
            continue
        k = (round(e["start"], 2), round(e["end"], 2))
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(e)

    segs = []
    for k in order:
        cands = groups[k]
        zh = [c for c in cands if is_cjk(c["text"])]
        pool = zh or cands
        texts = []
        for c in pool:
            if c["text"] not in texts:
                texts.append(c["text"])
        txt = " ".join(texts)
        if segs and txt == segs[-1]["text"]:
            continue
        segs.append({"start": k[0], "end": k[1], "text": txt,
                     "style": pool[0]["style"]})
    segs.sort(key=lambda s: s["start"])
    for i, s in enumerate(segs, 1):
        s["i"] = i
        s["time"] = fmt(s["start"])
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", required=True, help="字幕文件 (.ass/.srt)")
    ap.add_argument("-o", "--outdir", help="输出目录，默认=字幕同目录")
    ap.add_argument("--chunk-min", type=float, default=20.0,
                    help="分块审查的每块分钟数，0=不分块")
    ap.add_argument("--chunk-overlap-min", type=float, default=2.0,
                    help="分块之间的重叠分钟数")
    args = ap.parse_args()

    if not os.path.exists(args.sub):
        log("❌ 字幕不存在: %s" % args.sub)
        sys.exit(1)

    ext = os.path.splitext(args.sub)[1].lower()
    entries = parse_ass(args.sub) if ext == ".ass" else parse_srt(args.sub)
    if not entries:
        log("❌ 没解析出任何字幕条目（格式不支持或文件为空）: %s" % args.sub)
        sys.exit(1)

    segs = select(entries)
    if not segs:
        log("❌ 字幕条目全部为空")
        sys.exit(1)

    zh_cnt = sum(1 for s in segs if is_cjk(s["text"]))
    ratio = zh_cnt / len(segs)
    outdir = args.outdir or os.path.dirname(os.path.abspath(args.sub))
    os.makedirs(outdir, exist_ok=True)

    total = segs[-1]["end"]
    data = {
        "source": os.path.abspath(args.sub),
        "duration": round(total, 2),
        "count": len(segs),
        "zh_ratio": round(ratio, 3),
        "segments": segs,
    }
    with open(os.path.join(outdir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    lines = ["[%s] %s" % (s["time"], s["text"]) for s in segs]
    with open(os.path.join(outdir, "transcript.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    parts = []
    if args.chunk_min and args.chunk_min > 0 and total > args.chunk_min * 60:
        span = args.chunk_min * 60
        overlap = args.chunk_overlap_min * 60
        idx, start = 1, 0.0
        while start < total:
            end = start + span
            sel = [s for s in segs if s["start"] < end and s["end"] > start - overlap]
            if sel:
                p = os.path.join(outdir, "transcript.part%02d.txt" % idx)
                with open(p, "w", encoding="utf-8") as f:
                    f.write("# 分块 %02d 覆盖 %s - %s（相邻块有 %.0f 分钟重叠）\n"
                            % (idx, fmt(start), fmt(min(end, total)), args.chunk_overlap_min))
                    f.write("\n".join("[%s] %s" % (s["time"], s["text"]) for s in sel) + "\n")
                parts.append((p, len(sel)))
                idx += 1
            if end >= total:
                break
            start = end - overlap

    log("字幕: %s" % os.path.abspath(args.sub))
    log("条目: %d 条  时长: %s  中文行占比: %.1f%%" % (len(segs), fmt(total), ratio * 100))
    log("输出: %s" % os.path.join(outdir, "transcript.json"))
    log("      %s（%d 行）" % (os.path.join(outdir, "transcript.txt"), len(lines)))
    for p, n in parts:
        log("      %s（%d 行）" % (p, n))
    if ratio < 0.5:
        log("⚠ 中文行占比偏低（<50%%），可能不是中文成片字幕，审查结论不可信 → 向用户确认字幕来源")


if __name__ == "__main__":
    main()
