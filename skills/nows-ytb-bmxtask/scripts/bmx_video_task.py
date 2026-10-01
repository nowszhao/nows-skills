#!/usr/bin/env python3
"""
bmx_video_task.py — 把「本地 MP4 + 双语 ASS」提交成 BiliMix(bmx) 视频配音任务。

做四件事，全部幂等可重跑：
  1. 校验 bmx 可用并已登录（bmx auth status）
  2. 上传 MP4 与 ASS（bmx audio upload），拿到服务端路径
  3. 用 bmx subtitle parse 校验字幕被识别为双语（count == bilingual_count）
  4. bmx task submit --type video ... 提交任务，打印 task_id

背景音乐：bmx 的语义是「默认去掉原视频 BGM」，只有显式 --keep-bgm 才保留。
本脚本**从不**传 --keep-bgm，即默认关闭背景音乐。确需保留时加 --keep-bgm。

Usage:
    python3 bmx_video_task.py --video X.mp4 --subtitle X.ass \
        [--title "Title"] [--duration 1894] [--keep-bgm] [--dry-run]

Exit codes: 0 ok, 1 致命错误（bmx 缺失/未登录/上传失败/字幕校验失败/提交失败）
"""

import argparse
import json
import shutil
import subprocess
import sys
import time


DEBUG = False


def log(msg: str) -> None:
    print(f"[bmx_video_task] {msg}", flush=True)


def run(cmd: list[str], dry_run: bool) -> subprocess.CompletedProcess:
    log("+ " + " ".join(f"'{c}'" if " " in c else c for c in cmd))
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, capture_output=True, text=True)


def bmx_json(bmx: str, args: list[str], dry_run: bool, field: str | None = None,
             retries: int = 1):
    """Run a bmx subcommand and return (parsed_json_or_None, raw_field_value).

    `retries` > 1 时会重试：刚上传完文件立刻 parse，服务端偶发瞬时失败
    （实测出现过一次空返回），重试即可通过。
    """
    for attempt in range(1, retries + 1):
        cmd = [bmx, *args]
        if field:
            cmd += ["--field", field]
        r = run(cmd, dry_run)
        if dry_run:
            return None, f"<dry-run:{field}>"
        out = (r.stdout or "").strip()
        if DEBUG:
            log(f"  debug: rc={r.returncode} stdout={out!r} stderr={(r.stderr or '')[-200:]!r}")
        if r.returncode != 0 or not out:
            log(f"  命令失败 (exit {r.returncode}, attempt {attempt}/{retries}): "
                f"{(r.stderr or out)[-400:]}")
            if attempt < retries:
                time.sleep(2)
                continue
            return None, None
        if field:
            return None, out
        try:
            return json.loads(out), None
        except json.JSONDecodeError:
            log(f"  无法解析输出: {out[:200]}")
            return None, None
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True, help="本地 MP4 路径")
    ap.add_argument("--subtitle", required=True, help="本地双语 ASS 路径（EN || ZH）")
    ap.add_argument("--title", default=None, help="任务标题（默认取视频文件名）")
    ap.add_argument("--duration", default=None, help="预知时长，如 1894 或 01:23:45")
    ap.add_argument("--subtitle-mode", default="bilingual",
                    choices=["bilingual", "chinese_only", "none"])
    ap.add_argument("--subtitle-font-size", default=None, help="字幕字号，默认 20")
    ap.add_argument("--keep-bgm", action="store_true",
                    help="保留原视频背景音乐（默认关闭）")
    ap.add_argument("--bmx", default=None, help="bmx 可执行文件路径")
    ap.add_argument("--dry-run", action="store_true", help="只打印命令，不实际执行")
    ap.add_argument("--no-submit", action="store_true",
                    help="只上传并校验字幕，不提交任务（排错/预检用）")
    ap.add_argument("--debug", action="store_true", help="打印每条命令的原始返回")
    args = ap.parse_args()

    global DEBUG
    DEBUG = args.debug

    bmx = args.bmx or shutil.which("bmx")
    if not bmx:
        log("找不到 bmx。请确认它在 PATH 上，或用 --bmx 指定绝对路径。")
        return 1
    log(f"bmx: {bmx}")

    # 1. auth
    auth, _ = bmx_json(bmx, ["auth", "status"], args.dry_run)
    if args.dry_run:
        pass
    elif not auth or not auth.get("authenticated"):
        log(f"未登录或服务端不可达: {auth}  → 先跑 `bmx auth login`")
        return 1

    # 2. uploads
    paths = {}
    for kind, path in (("video", args.video), ("subtitle", args.subtitle)):
        _, val = bmx_json(bmx, ["audio", "upload", path], args.dry_run,
                          field="local_path")
        if val is None:
            log(f"{kind} 上传失败: {path}")
            return 1
        paths[kind] = val
        log(f"{kind} 服务端路径: {val}")

    # 3. subtitle validation
    # 注意：bmx_json 返回 (json_obj, field_value)，用 --field 时取第二个元素
    _, cnt_s = bmx_json(bmx, ["subtitle", "parse", paths["subtitle"]],
                        args.dry_run, field="count", retries=3)
    _, bi_s = bmx_json(bmx, ["subtitle", "parse", paths["subtitle"]],
                       args.dry_run, field="bilingual_count", retries=3)
    if not args.dry_run:
        try:
            cnt, bi = int(cnt_s), int(bi_s)
        except (TypeError, ValueError):
            log(f"字幕校验失败：无法读取 count/bilingual_count ({cnt_s}/{bi_s})")
            return 1
        if cnt == 0:
            log("字幕校验失败：服务端解析出 0 行，检查文件是否为有效 ASS。")
            return 1
        if bi != cnt:
            log(f"字幕校验失败：共 {cnt} 行，但只识别出 {bi} 行双语——"
                f"检查是否每行都用 ' || ' 分隔英文和中文。")
            return 1
        log(f"字幕校验通过：{cnt} 行，全部为双语")

    if args.no_submit:
        log("已指定 --no-submit：只上传并校验，不提交任务")
        print(json.dumps({"video_server_path": paths["video"],
                          "subtitle_server_path": paths["subtitle"]},
                         ensure_ascii=False, indent=2))
        return 0

    # 4. submit
    title = args.title or args.video.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    cmd = ["task", "submit", "--type", "video",
           "--server-path", paths["video"]]
    if args.subtitle_mode != "none":
        cmd += ["--subtitle-path", paths["subtitle"],
                "--subtitle-mode", args.subtitle_mode]
    else:
        cmd += ["--subtitle-mode", "none"]
    cmd += ["--title", title]
    if args.duration:
        cmd += ["--duration", str(args.duration)]
    if args.subtitle_font_size:
        cmd += ["--subtitle-font-size", str(args.subtitle_font_size)]
    if args.keep_bgm:
        cmd += ["--keep-bgm"]
    else:
        log("背景音乐：关闭（未传 --keep-bgm）")

    res, _ = bmx_json(bmx, cmd, args.dry_run)
    if args.dry_run:
        log("dry-run：未提交任务")
        return 0
    if not res or not res.get("task_id"):
        log("提交失败，未拿到 task_id")
        return 1
    task_id = res["task_id"]
    log(f"任务已提交: task_id={task_id}")
    log(f"跟踪:  bmx task status {task_id}")
    log(f"等待:  bmx task wait {task_id}")
    log(f"下载:  bmx video download --task-id {task_id} -o <name>_dubbed.mp4")
    print(json.dumps({"task_id": task_id,
                      "video_server_path": paths["video"],
                      "subtitle_server_path": paths["subtitle"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
