#!/usr/bin/env python3
"""
fetch_transcript.py — Fetch YouTube's OFFICIAL transcript (转写文稿) via a
bundled CDP Proxy that drives the user's real Chrome (login state included),
then convert it to SRT.

Why CDP instead of agent-browser / youtube-transcript-api:
  - YouTube's official transcript is the server-side sentence-aggregated version
    (complete sentences, non-overlapping timestamps, start == true speech onset).
    yt-dlp's raw caption download is the pre-aggregation rolling window
    (fragments, ~98% overlapping) and must NOT be used.
  - youtube-transcript-api is frequently IP-blocked even with cookies.
  - A headless automated browser (agent-browser / Playwright default profile)
    triggers the "请登录确认你不是机器人" (bot-check) wall on popular videos.
  - The reliable path is CDP: attach to the user's REAL Chrome, which carries
    their login state and browser fingerprint. The bundled cdp-proxy.mjs exposes
    a small HTTP API (localhost:3456) over the DevTools protocol.

Workflow:
  1. ensure the CDP proxy is running and connected to the user's Chrome
     (one-time setup: chrome://inspect/#remote-debugging -> allow; see SKILL.md)
  2. open the video page in a background tab
  3. expand the description ("更多"), click "内容转文字" / "Show transcript"
  4. wait for the transcript panel to render, then read its innerText
     (each block: `M:SS` timestamp + sentence text; may include a duration hint
     like `X分钟Y秒钟`; recommended-video noise may be appended at the end)
  5. parse into segments (English-only filter + monotonic timestamps), convert
     to SRT (segment end = next segment start; last segment +3s)
  6. close the background tab

Usage:
    python3 fetch_transcript.py --url <youtube_url> [--out transcript_official.srt]
                                 [--proxy-port 3456]

Exit codes: 0 ok, 1 fatal (transcript could not be retrieved), 2 CDP not ready.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.parse
import urllib.request

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY_SCRIPT = os.path.join(SKILL_DIR, "scripts", "cdp-proxy.mjs")
CHECK_SCRIPT = os.path.join(SKILL_DIR, "scripts", "check-deps.sh")


def log(msg: str) -> None:
    print(f"[fetch_transcript] {msg}", flush=True)


# ---------------- CDP proxy helpers ----------------

def _http_get(port: int, path: str, timeout: int = 20) -> str:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def _http_post(port: int, path: str, body: str = "", timeout: int = 30) -> str:
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")[:500]
        log(f"CDP {e.code} from {path} (body={body_text})")
        raise


def _eval(port: int, target: str, js: str, timeout: int = 30) -> str:
    """Run JS in the page context. Return the raw value (string, number,
    or dict/list), unwrapping CDP's {"value": ...} envelope and any
    double-encoded JSON (e.g. JS that returns JSON.stringify(obj))."""
    raw = _http_post(port, f"/eval?target={target}", js, timeout=timeout)
    try:
        envelope = json.loads(raw)
    except Exception:
        return raw
    val = envelope.get("value", "")
    # If the JS returned a string that itself contains JSON, unwrap once more
    if isinstance(val, str) and val.startswith(("{", "[")):
        try:
            return json.loads(val)
        except Exception:
            return val
    return val


def ensure_cdp(port: int) -> bool:
    """Make sure the CDP proxy is up and connected to Chrome. Returns True if ready."""
    # 1. proxy already healthy?
    try:
        health = json.loads(_http_get(port, "/health", timeout=3))
        if health.get("connected"):
            return True
    except Exception:
        pass

    # 2. start proxy (needs Chrome DevToolsActivePort / 9222 to exist)
    if not os.path.exists(PROXY_SCRIPT):
        log(f"Missing {PROXY_SCRIPT}")
        return False
    env = dict(os.environ)
    env["CDP_PROXY_PORT"] = str(port)
    proc = subprocess.Popen(
        ["node", PROXY_SCRIPT],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log(f"Started CDP proxy (pid {proc.pid})")

    # 3. wait for connected (Chrome must have debugging enabled)
    for _ in range(20):
        time.sleep(1)
        try:
            health = json.loads(_http_get(port, "/health", timeout=3))
            if health.get("connected"):
                log("CDP proxy connected to Chrome")
                return True
        except Exception:
            pass
    return False


def check_chrome_debug() -> bool:
    """Check whether Chrome remote debugging is enabled (DevToolsActivePort or 9222)."""
    try:
        r = subprocess.run(["bash", CHECK_SCRIPT], capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        if "connected" in out or "ready" in out:
            return True
    except Exception:
        pass
    # fallback: probe the DevToolsActivePort file directly
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "Library/Application Support/Google/Chrome/DevToolsActivePort"),
        os.path.join(home, "Library/Application Support/Google/Chrome Canary/DevToolsActivePort"),
        os.path.join(home, "Library/Application Support/Chromium/DevToolsActivePort"),
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    port = int(f.readline().strip())
                if port > 0:
                    return True
            except Exception:
                pass
    return False


# ---------------- page automation ----------------

def open_video(port: int, url: str) -> str:
    raw = _http_get(port, f"/new?url={urllib.parse.quote(url, safe='')}", timeout=30)
    try:
        return json.loads(raw).get("targetId", "")
    except Exception:
        return ""


def wait_for_target(port: int, target: str, timeout: int = 60) -> bool:
    """Wait until the page is loaded and has meaningful content."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            info = json.loads(_http_get(port, f"/info?target={target}", timeout=5))
            if info.get("ready") == "complete":
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def find_and_click(port: int, target: str, js_selector_script: str, sleep_after: float = 2.0) -> str:
    """Run a JS snippet that finds the button and clicks it; returns result text."""
    out = _eval(port, target, js_selector_script)
    time.sleep(sleep_after)
    return out


# ---------------- transcript parsing ----------------

def parse_transcript(text: str) -> list[tuple[str, str]]:
    """Parse panel innerText into [(M:SS timestamp, sentence), ...].

    Structure per block (as rendered by YouTube's transcript panel):
        <chapter heading>          (optional, skipped)
        M:SS                       (timestamp, e.g. 0:16 / 17:46)
        <sentence text>            (one or more lines)
    The panel may be followed by recommended-video noise (Chinese titles,
    viewer counts, etc.) — filter with an English-text heuristic and require
    timestamps to be monotonic (time going backwards = left the transcript).
    """
    lines = text.split("\n")
    TS_RE = re.compile(r"^(\d+):(\d{2})$")
    DUR_RE = re.compile(r"^\d+分钟\d+秒钟$|^\d+秒钟$|^\d+分钟$")

    def is_english(s: str) -> bool:
        s = s.strip()
        if not s:
            return False
        chinese = sum(1 for c in s if "\u4e00" <= c <= "\u9fff")
        letters = sum(1 for c in s if c.isascii() and c.isalpha())
        digits = sum(1 for c in s if c.isdigit())
        if chinese > 5:
            return False
        if letters < 10:
            return False
        if digits > letters:
            return False
        return True

    segments: list[tuple[str, str]] = []
    cur_ts: str | None = None
    cur_parts: list[str] = []
    last_sec = -9999
    in_transcript = False

    def flush():
        nonlocal cur_ts, cur_parts
        if cur_ts is not None:
            sentence = " ".join(p.strip() for p in cur_parts).strip()
            if sentence and is_english(sentence):
                segments.append((cur_ts, sentence))
        cur_ts, cur_parts = None, []

    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        m = TS_RE.match(ln)
        if m:
            sec = int(m.group(1)) * 60 + int(m.group(2))
            # time jumping backwards by >60s means we've left the transcript
            if sec < last_sec - 60:
                break
            if sec > last_sec:
                last_sec = sec
            flush()
            cur_ts = ln
            in_transcript = True
        elif DUR_RE.match(ln):
            continue
        elif cur_ts is not None and is_english(ln):
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


# ---------------- main ----------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True, help="YouTube video URL")
    ap.add_argument("--out", default="transcript_official.srt")
    ap.add_argument("--proxy-port", type=int, default=3456)
    ap.add_argument("--skip-cdp-check", action="store_true",
                    help="skip the pre-flight Chrome debugging check")
    args = ap.parse_args()

    if not args.skip_cdp_check and not check_chrome_debug():
        log("Chrome remote debugging is NOT enabled.")
        log("  Please open chrome://inspect/#remote-debugging in your Chrome and")
        log("  check 'Allow remote debugging for this browser instance', then")
        log("  click Allow on the confirmation dialog.")
        return 2

    if not ensure_cdp(args.proxy_port):
        log("CDP proxy failed to connect to Chrome. Is Chrome running with remote debugging?")
        return 2

    target = ""
    try:
        log(f"Opening {args.url}")
        target = open_video(args.proxy_port, args.url)
        if not target:
            log("Failed to create a browser tab.")
            return 1
        if not wait_for_target(args.proxy_port, target):
            log("Timed out waiting for the page to load.")
            return 1

        # 1. wait for the SPA to fully render the video page (look for the
        #    <video> element, then give YouTube a few more seconds to mount
        #    the rest of the chrome — description, tabs, etc.)
        for _ in range(15):
            time.sleep(1)
            has_video = _eval(args.proxy_port, target, "!!document.querySelector('video')")
            if has_video and has_video != "false":
                break
        time.sleep(5)

        # 2. expand description — look for any button whose text/aria-label is
        #    "更多" / "展开" / "More" / "Show more" (different videos use
        #    different labels; the aria-label is usually the most stable).
        find_and_click(
            args.proxy_port, target,
            """(() => {
                const btns = [...document.querySelectorAll('button, [role=button]')];
                const match = btns.find(x => {
                    const t = (x.textContent||'').trim();
                    const a = (x.getAttribute('aria-label')||'').trim();
                    return a === '更多' || t === '展开' || t === '更多' || t === '...更多'
                        || /show more|more information/i.test(a)
                        || /\\.\\.\\.更多$/.test(t);
                });
                if (match) { match.click(); return 'clicked expand: ' + ((match.textContent||'').trim().slice(0,20)) + ' (aria=' + (match.getAttribute('aria-label')||'') + ')'; }
                return 'no expand btn';
            })()""",
            sleep_after=1.5,
        )

        # 3. click "内容转文字" / "Show transcript" (the description-area button)
        find_and_click(
            args.proxy_port, target,
            """(() => {
                const btns = [...document.querySelectorAll('button')];
                const b = btns.find(x => {
                    const t = (x.textContent||'');
                    return t.includes('内容转文字') || t.includes('Show transcript') || t.includes('Transcript');
                });
                if (b) { b.click(); return 'clicked transcript btn'; }
                return 'no transcript btn';
            })()""",
            sleep_after=5,
        )

        # 4. activate the "转写文稿" tab inside the "在此视频中" tab bar
        #    (some videos render the transcript inside a tab rather than the
        #     description panel)
        find_and_click(
            args.proxy_port, target,
            """(() => {
                const tabs = [...document.querySelectorAll('yt-tab-shape, [role=tab], button, tp-yt-paper-tab')];
                const t = tabs.find(x => (x.textContent||'').trim() === '转写文稿'
                    || (x.textContent||'').trim() === 'Transcript');
                if (t) { t.click(); return 'clicked transcript tab'; }
                return 'no transcript tab';
            })()""",
            sleep_after=2,
        )

        # 5. wait for the transcript panel to render — YouTube often loads
        #    the segments lazily after the tab is shown.
        time.sleep(10)

        # 6. find the best candidate panel (transcript segments — many
        #    timestamps + real English sentences) anywhere in the document
        #    including shadow roots. Some YouTube layouts render the
        #    transcript inside <ytd-transcript-segment-list-renderer> in a
        #    shadow tree, or as button labels (virtual-scroll scroller).
        # 6. find the transcript panel. YouTube renders the actual segments
        #    into one of three places; pick the first with content.
        js_find = (
            "(() => {"
            " const tsRE = /[0-9]+:[0-9]{2}/g;"
            " const checks = ['ytd-transcript-segment-list-renderer', 'ytd-transcript-search-panel-renderer', 'ytd-transcript-renderer', 'ytd-video-description-transcript-section-renderer', '.ytSectionListRendererContents'];"
            " for (const sel of checks) {"
            "   let el = null;"
            "   try { el = document.querySelector(sel); } catch (_) { continue; }"
            "   if (!el) continue;"
            "   let t = '';"
            "   try { t = (el.innerText || '').trim(); } catch (_) { continue; }"
            "   if (t.length < 100) continue;"
            "   const ts = (t.match(tsRE) || []).length;"
            "   if (ts < 20) continue;"
            "   window.__ytTrans = t;"
            "   return JSON.stringify({found: true, chars: t.length, ts, src: sel});"
            " }"
            " return JSON.stringify({found: false});"
            " })()"
        )
        # Read the stored transcript in chunks of ~15k chars. CDP can
        # return values up to ~25k chars reliably, so we use 15k for safety.
        js_read_chunk = (
            "((start) => {"
            " const s = window.__ytTrans || '';"
            " return s.substr(start, 15000);"
            " })"
        )

        text = ""
        for attempt in range(8):
            find_raw = _eval(args.proxy_port, target, js_find)
            if attempt == 0:
                log(f"js_find raw: {repr(find_raw)[:200]}")
            try:
                find_info = json.loads(find_raw) if isinstance(find_raw, str) else (find_raw or {})
            except Exception:
                find_info = {}
            if find_info.get("found"):
                log(f"Transcript panel found ({find_info.get('chars')} chars, {find_info.get('ts')} timestamps, src={find_info.get('src')})")
                chunks = []
                offset = 0
                while True:
                    chunk = _eval(args.proxy_port, target, js_read_chunk + f"({offset})")
                    if not chunk:
                        break
                    chunks.append(chunk)
                    offset += len(chunk)
                    if len(chunk) < 15000:
                        break
                text = "".join(chunks)
                if text and len(text.strip()) >= 500:
                    break
            log(f"  waiting for transcript panel (attempt {attempt+1}/8, "
                f"chars={len(text.strip())}, {find_info})")
            time.sleep(10)
        if len(text.strip()) < 300:
            log("Transcript panel appears empty (or not rendered).")
            log("  If you see a 'confirm you are not a robot' wall, make sure you are")
            log("  logged into YouTube in your Chrome, then retry.")
            return 1
        log(f"Read {len(text)} chars from transcript panel")

        # 5. parse + write SRT
        segments = parse_transcript(text)
        if not segments:
            log("No segments parsed from transcript panel.")
            return 1
        log(f"Parsed {len(segments)} segments ({segments[0][0]} -> {segments[-1][0]})")
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(to_srt(segments))
        log(f"Wrote SRT: {args.out}")
        return 0

    except Exception as e:
        log(f"ERROR: {e}")
        return 1

    finally:
        if target:
            try:
                _http_get(args.proxy_port, f"/close?target={target}", timeout=5)
                log("Closed the background tab")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
