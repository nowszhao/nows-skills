#!/usr/bin/env python3
"""
fetch_transcript.py — Fetch YouTube's OFFICIAL transcript (转写文稿) via a real
browser and convert it to SRT.

Why: the official transcript is the server-side sentence-aggregated version
(complete sentences, non-overlapping timestamps, start == true speech onset).
yt-dlp's raw caption download is the pre-aggregation rolling window (fragments,
~98% overlapping) and must NOT be used. The library `youtube-transcript-api` is
often IP-blocked; a real browser (agent-browser) is the reliable path.

Workflow (driven via the `agent-browser` CLI):
  1. open the video page
  2. click "...更多" (expand description)
  3. click "内容转文字" / "Show transcript"
  4. read the transcript panel's innerText (structure per block:
     `M:SS` timestamp, `X分钟Y秒钟` duration hint, sentence text)
  5. convert to SRT (segment end = next segment start; last segment +3s)

Usage:
    python3 fetch_transcript.py --url <youtube_url> [--out transcript_official.srt]

Exit codes: 0 ok, 1 fatal (transcript could not be retrieved).
"""

import argparse
import json
import re
import subprocess
import sys
import time


def log(msg: str) -> None:
    print(f"[fetch_transcript] {msg}", flush=True)


def ab(*args: str, timeout: int = 60) -> str:
    """Run an agent-browser command; return stdout."""
    cmd = ["agent-browser", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"agent-browser {' '.join(args)} failed: {r.stderr.strip()[-300:]}")
    return r.stdout


def find_button_ref(snapshot: str, labels: list[str]) -> str | None:
    """Find the ref of a button whose text contains any of the given labels."""
    for line in snapshot.splitlines():
        if "button" in line and any(label in line for label in labels):
            m = re.search(r"ref=(e\d+)", line)
            if m:
                return m.group(1)
    return None


def extract_panel_text() -> str:
    """Read the transcript panel innerText via JS (handles virtual scrolling)."""
    js = (
        "(() => { const el = document.querySelector('.ytSectionListRendererContents'); "
        "return el ? el.innerText : ''; })()"
    )
    out = ab("eval", js)
    try:
        return json.loads(out)
    except Exception:
        return out


def parse_transcript(text: str) -> list[tuple[str, str]]:
    """Parse panel text into [(ts, sentence), ...].

    Block structure per segment:
        M:SS            <- timestamp (e.g. 0:16, 17:46)
        X分钟Y秒钟        <- duration hint (16秒钟 / 1分钟4秒钟 / 3分钟)
        <sentence text>  <- may span multiple lines
    Chapter headings like "第 X 章：..." are skipped.
    """
    lines = text.split("\n")
    TS_RE = re.compile(r"^\d+:\d{2}$")
    DUR_RE = re.compile(r"^\d+分钟\d+秒钟$|^\d+秒钟$|^\d+分钟$")
    CHAPTER_RE = re.compile(r"^(第 \d+ 章|Chapter)")

    segments: list[tuple[str, str]] = []
    cur_ts: str | None = None
    cur_parts: list[str] = []

    def flush():
        nonlocal cur_ts, cur_parts
        if cur_ts is not None:
            sentence = " ".join(p.strip() for p in cur_parts).strip()
            segments.append((cur_ts, sentence))
        cur_ts, cur_parts = None, []

    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if TS_RE.match(ln):
            flush()
            cur_ts = ln
        elif DUR_RE.match(ln) or CHAPTER_RE.match(ln):
            continue
        elif cur_ts is not None:
            cur_parts.append(ln)
    flush()
    return segments


def ts_to_sec(ts: str) -> int:
    m, s = ts.split(":")
    return int(m) * 60 + int(s)


def fmt_srt(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:02d},000"


def to_srt(segments: list[tuple[str, str]]) -> str:
    blocks = []
    for i, (ts, sentence) in enumerate(segments):
        start = ts_to_sec(ts)
        if i + 1 < len(segments):
            end = ts_to_sec(segments[i + 1][0])
        else:
            end = start + 3
        if end <= start:
            end = start + 2
        blocks.append((start, end, sentence))
    out = []
    for i, (start, end, sentence) in enumerate(blocks, 1):
        out.append(f"{i}\n{fmt_srt(start)} --> {fmt_srt(end)}\n{sentence}\n")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True, help="YouTube video URL")
    ap.add_argument("--out", default="transcript_official.srt")
    args = ap.parse_args()

    try:
        log(f"Opening {args.url}")
        ab("open", args.url)
        try:
            ab("wait", "--load", "networkidle", timeout=90)
        except Exception:
            time.sleep(3)
        time.sleep(2)

        # 1. expand description ("更多"/"More")
        snap = ab("snapshot", "-i")
        more_ref = find_button_ref(snap, ["更多", "More"])
        if more_ref:
            ab("click", more_ref)
            time.sleep(1.5)

        # 2. click transcript button ("内容转文字" / "Show transcript")
        snap = ab("snapshot", "-i")
        tr_ref = find_button_ref(snap, ["内容转文字", "Show transcript", "Transcript"])
        if not tr_ref:
            log("Transcript button not found on page.")
            return 1
        ab("click", tr_ref)
        time.sleep(2.5)

        # 3. read full panel text
        text = extract_panel_text()
        if len(text.strip()) < 50:
            log("Transcript panel appears empty.")
            return 1
        log(f"Read {len(text)} chars from transcript panel")

        # 4. parse + write SRT
        segments = parse_transcript(text)
        if not segments:
            log("No segments parsed from transcript panel.")
            return 1
        log(f"Parsed {len(segments)} segments")
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(to_srt(segments))
        log(f"Wrote SRT: {args.out}")
        return 0

    except Exception as e:
        log(f"ERROR: {e}")
        return 1

    finally:
        try:
            ab("close")
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
