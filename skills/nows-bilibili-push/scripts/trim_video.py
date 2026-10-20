#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按合规审查结果裁剪视频，并写出投稿门禁文件（<video>.compliance.json）

用法:
  # 只看计划，不产出视频
  python trim_video.py --video x.mp4 --review x.review.json --transcript transcript.json --dry-run

  # 实际裁剪（无 cut 项时只写 pass 门禁，视频不动）
  python trim_video.py --video x.mp4 --review x.review.json --transcript transcript.json

  # 用户坚持要发超阈值内容
  python trim_video.py --video x.mp4 --review x.review.json --force

退出码:
  0 = pass / trimmed（门禁文件已写）
  2 = 输入或参数错误
  3 = blocked（裁太多/整条不建议发，门禁文件已写 result=blocked）
  4 = 裁剪失败（不写门禁文件，避免误放行）
"""
import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile

CUT_ACTIONS = {"cut", "裁剪"}
BLOCK_ACTIONS = {"block", "blocked", "block_whole"}


def log(m):
    print(m, flush=True)


def ffprobe_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffprobe 读时长失败: %s" % r.stderr.strip()[:300])
    return float(r.stdout.strip())


def has_audio(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    return bool([x for x in r.stdout.split() if x.strip()])


def keyframes(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-skip_frame", "nokey",
         "-show_entries", "frame=pts_time", "-of", "csv=p=0", path],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffprobe 读关键帧失败: %s" % r.stderr.strip()[:300])
    vals = []
    for tok in r.stdout.replace("\n", ",").split(","):
        tok = tok.strip()
        if not tok or tok == "N/A":
            continue
        try:
            vals.append(float(tok))
        except ValueError:
            pass
    return sorted(set(vals))


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def collect_issues(review):
    """兼容 issues / segments 两种字段名，返回 (cut 列表, 是否 block)"""
    raw = review.get("issues") or review.get("segments") or []
    cuts, blocked = [], False
    for it in raw:
        action = str(it.get("action", "review")).strip().lower()
        if action in BLOCK_ACTIONS:
            blocked = True
            continue
        if action not in CUT_ACTIONS:
            continue
        try:
            st = float(it["start"])
            en = float(it["end"])
        except (KeyError, TypeError, ValueError):
            log("⚠ 跳过缺少 start/end 的条目: %s" % json.dumps(it, ensure_ascii=False)[:120])
            continue
        if en <= st:
            log("⚠ 跳过非法区间 %.2f-%.2f" % (st, en))
            continue
        cuts.append({"start": st, "end": en,
                     "level": it.get("level", ""),
                     "reason": it.get("reason", ""),
                     "quote": it.get("quote", "")})
    return cuts, blocked


def align_to_sentences(cuts, transcript_path):
    """把裁剪区间扩展到覆盖所有相交的整句，避免切半句话"""
    data = load_json(transcript_path)
    segs = data.get("segments") or []
    if not segs:
        log("⚠ transcript 无 segments，跳过句边界对齐")
        return cuts
    out = []
    for c in cuts:
        hit = [s for s in segs if float(s["end"]) > c["start"] and float(s["start"]) < c["end"]]
        if hit:
            c = dict(c)
            c["start"] = min(c["start"], min(float(s["start"]) for s in hit))
            c["end"] = max(c["end"], max(float(s["end"]) for s in hit))
            c["sentences"] = len(hit)
        out.append(c)
    return out


def merge_ranges(cuts, pad_before, pad_after, duration):
    spans = []
    for c in cuts:
        st = max(0.0, c["start"] - pad_before)
        en = min(duration, c["end"] + pad_after)
        if en - st < 0.05:
            continue
        spans.append([st, en])
    spans.sort()
    merged = []
    for st, en in spans:
        if merged and st <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], en)
        else:
            merged.append([st, en])
    return merged


def keep_ranges(cuts, duration):
    keeps, cur = [], 0.0
    for st, en in cuts:
        if st - cur > 0.3:
            keeps.append([cur, st])
        cur = max(cur, en)
    if duration - cur > 0.3:
        keeps.append([cur, duration])
    return keeps


def snap_to_keyframes(keeps, kfs, duration):
    """保留段起点向上取整到关键帧、终点向下取整 → 只多切不残留

    首段起点 / 末段终点贴着视频两端时不吸附，否则会白丢开头结尾。
    """
    if not kfs:
        raise RuntimeError("未取到关键帧")
    out = []
    for st, en in keeps:
        if st <= 0.001:
            a = 0.0
        else:
            a = next((k for k in kfs if k >= st - 0.001), None)
        if en >= duration - 0.5:
            b = en
        else:
            b = next((k for k in reversed(kfs) if k <= en + 0.001), None)
        if a is None or b is None or b - a < 0.4:
            log("  ⚠ 保留段 %.2f-%.2f 无合适关键帧，丢弃" % (st, en))
            continue
        out.append([a, b])
    return out


def fmt(t):
    t = int(round(t))
    return "%02d:%02d:%02d" % (t // 3600, t % 3600 // 60, t % 60)


def cut_copy(src, keeps, out_path, tmpdir):
    segs = []
    for i, (st, en) in enumerate(keeps):
        seg = os.path.join(tmpdir, "seg_%03d.mp4" % i)
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", "%.3f" % st, "-i", src,
               "-t", "%.3f" % (en - st),
               "-map", "0:v:0", "-map", "0:a:0?", "-c", "copy",
               "-avoid_negative_ts", "make_zero", seg]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        segs.append(seg)
    if len(segs) == 1:
        shutil.move(segs[0], out_path)
        return
    lst = os.path.join(tmpdir, "list.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in segs:
            f.write("file '%s'\n" % s.replace("'", "'\\''"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", "-movflags", "+faststart", out_path],
                   check=True, capture_output=True, text=True)


def cut_reencode(src, keeps, out_path):
    with_audio = has_audio(src)
    chains, labels = [], []
    for i, (st, en) in enumerate(keeps):
        chains.append("[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[v%d]" % (st, en, i))
        if with_audio:
            chains.append("[0:a]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS[a%d]" % (st, en, i))
            labels.append("[v%d][a%d]" % (i, i))
        else:
            labels.append("[v%d]" % i)
    if with_audio:
        chains.append("%sconcat=n=%d:v=1:a=1[v][a]" % ("".join(labels), len(keeps)))
        maps = ["-map", "[v]", "-map", "[a]"]
    else:
        chains.append("%sconcat=n=%d:v=1:a=0[v]" % ("".join(labels), len(keeps)))
        maps = ["-map", "[v]"]
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", src,
           "-filter_complex", ";".join(chains)] + maps + [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_path]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def write_gate(path, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log("门禁文件: %s（result=%s）" % (path, payload.get("result")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--review", required=True, help="审查结果 review.json")
    ap.add_argument("--transcript", help="transcript.json，用于对齐整句")
    ap.add_argument("-o", "--output", help="输出视频，默认 <原名>.trimmed.mp4")
    ap.add_argument("--pad-before", type=float, default=0.4)
    ap.add_argument("--pad-after", type=float, default=0.5)
    ap.add_argument("--mode", choices=["keyframe", "reencode"], default="keyframe")
    ap.add_argument("--max-keyframe-gap", type=float, default=4.0,
                    help="关键帧间隔超过该值时自动改用重编码")
    ap.add_argument("--max-loss", type=float, default=0.2, help="允许删除的时长比例上限")
    ap.add_argument("--max-cuts", type=int, default=3, help="允许删除的段数上限")
    ap.add_argument("--force", action="store_true", help="越过 loss/段数阈值阻断")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--compliance-file", help="门禁文件，默认 <video>.compliance.json")
    args = ap.parse_args()

    video = os.path.abspath(args.video)
    if not os.path.exists(video):
        log("❌ 视频不存在: %s" % video)
        sys.exit(2)
    if not os.path.exists(args.review):
        log("❌ 审查结果不存在: %s" % args.review)
        sys.exit(2)

    gate_path = args.compliance_file or (video + ".compliance.json")
    base = {"reviewed": True,
            "reviewed_at": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "source_video": video,
            "review_file": os.path.abspath(args.review)}

    review = load_json(args.review)
    cuts, blocked = collect_issues(review)

    if blocked:
        payload = dict(base, result="blocked", video=None,
                       reason="审查结论为整条不建议发布（action=block）", cuts=cuts)
        write_gate(gate_path, payload)
        log("❌ blocked：整条不建议发布，请人工决定是否放弃该视频")
        sys.exit(3)

    if not cuts:
        payload = dict(base, result="pass", video=video, cuts=[],
                       original_duration=round(ffprobe_duration(video), 2),
                       final_duration=round(ffprobe_duration(video), 2))
        if args.dry_run:
            log("dry-run：无 cut 项，正式运行为 result=pass")
            return
        write_gate(gate_path, payload)
        log("✅ 无风险项，视频未改动")
        return

    duration = ffprobe_duration(video)
    out_path = os.path.abspath(args.output or
                               os.path.splitext(video)[0] + ".trimmed.mp4")
    if out_path == video:
        log("❌ 输出路径不能等于输入")
        sys.exit(2)
    # 门禁文件必须贴在「实际要上传的那个文件」旁边，投稿脚本按此校验
    gate_path = args.compliance_file or (out_path + ".compliance.json")

    if args.transcript:
        cuts = align_to_sentences(cuts, args.transcript)

    spans = merge_ranges(cuts, args.pad_before, args.pad_after, duration)
    keeps = keep_ranges(spans, duration)
    lost = 1 - sum(en - st for st, en in keeps) / max(0.01, duration)

    log("原时长: %s  删除 %d 段 / %s" % (fmt(duration), len(spans),
                                    " + ".join("%.1fs" % (en - st) for st, en in spans)))
    for c in cuts:
        log("  ✂ %s-%s [%s] %s" % (fmt(c["start"]), fmt(c["end"]), c["level"],
                                  (c["reason"] or "")[:80]))
    log("保留: " + " | ".join("%s-%s" % (fmt(a), fmt(b)) for a, b in keeps))
    log("预计删除比例: %.1f%%" % (lost * 100))

    if not keeps:
        payload = dict(base, result="blocked", video=None,
                       reason="裁剪后无剩余内容", cuts=cuts)
        write_gate(gate_path, payload)
        log("❌ blocked：裁剪后无剩余内容")
        sys.exit(3)

    if (lost > args.max_loss or len(spans) > args.max_cuts) and not args.force:
        payload = dict(base, result="blocked", video=None, cuts=cuts,
                       original_duration=round(duration, 2),
                       reason="删除比例 %.1f%%（上限 %.0f%%）或段数 %d（上限 %d）超阈值，"
                              "疑似整期内容不成立" % (lost * 100, args.max_loss * 100,
                                                   len(spans), args.max_cuts))
        write_gate(gate_path, payload)
        log("❌ blocked：%s" % payload["reason"])
        log("   如确认仍要发布，加 --force 重跑；否则人工决定是否放弃该视频")
        sys.exit(3)

    mode = args.mode
    kfs = []
    if mode == "keyframe":
        kfs = keyframes(video)
        gaps = [b - a for a, b in zip(kfs, kfs[1:])]
        max_gap = max(gaps) if gaps else 0
        if max_gap > args.max_keyframe_gap:
            log("⚠ 关键帧最大间隔 %.1fs > %.1fs，改用重编码" % (max_gap, args.max_keyframe_gap))
            mode = "reencode"

    if args.dry_run:
        if mode == "keyframe":
            snapped = snap_to_keyframes(keeps, kfs, duration)
            log("dry-run（keyframe）：实际保留 " +
                " | ".join("%s-%s" % (fmt(a), fmt(b)) for a, b in snapped))
        else:
            log("dry-run（reencode）：帧级精确裁剪")
        log("dry-run：未产出视频，未写门禁文件")
        return

    tmpdir = tempfile.mkdtemp(prefix="bili_trim_")
    try:
        if mode == "keyframe":
            snapped = snap_to_keyframes(keeps, kfs, duration)
            try:
                log("裁剪模式: keyframe copy")
                cut_copy(video, snapped, out_path, tmpdir)
                actual_keeps = snapped
            except (subprocess.CalledProcessError, RuntimeError) as e:
                log("⚠ 流复制失败，回退重编码: %s" % str(e)[:200])
                mode = "reencode"
                cut_reencode(video, keeps, out_path)
                actual_keeps = keeps
        else:
            log("裁剪模式: libx264 重编码（可能较慢）")
            cut_reencode(video, keeps, out_path)
            actual_keeps = keeps
    except subprocess.CalledProcessError as e:
        log("❌ 裁剪失败: %s" % (e.stderr or str(e))[-800:])
        sys.exit(4)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    new_duration = ffprobe_duration(out_path)
    expect = sum(en - st for st, en in actual_keeps)
    if abs(new_duration - expect) > 5:
        log("❌ 校验失败：输出 %.1fs，预期 %.1fs（偏差过大）" % (new_duration, expect))
        sys.exit(4)

    payload = dict(base, result="trimmed", video=os.path.abspath(out_path),
                   mode=mode, cuts=cuts,
                   original_duration=round(duration, 2),
                   final_duration=round(new_duration, 2),
                   kept=[{"start": round(a, 3), "end": round(b, 3)} for a, b in actual_keeps])
    write_gate(gate_path, payload)
    log("✅ 已裁剪: %s（%s → %s）" % (out_path, fmt(duration), fmt(new_duration)))


if __name__ == "__main__":
    main()
