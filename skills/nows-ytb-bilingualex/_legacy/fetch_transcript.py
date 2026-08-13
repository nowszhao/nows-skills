#!/usr/bin/env python3
"""
fetch_transcript.py — Fetch YouTube's OFFICIAL transcript (转写文稿) via a
bundled CDP Proxy that drives the user's real Chrome (login state included),
then convert it to SRT.

Why CDP instead of agent-browser / youtube-transcript-api:
  - YouTube's official transcript is the 转写文稿 panel data. The panel renders
    rolling-window fragments (observed 2026-08; NOT the old sentence-aggregated
    version), so the output SRT is fragmented — run aggregate_srt.py afterwards
    to merge into sentence-level SRT.
    yt-dlp's raw caption download is the same rolling window and must NOT be
    used as the pipeline source.
  - youtube-transcript-api is frequently IP-blocked even with cookies.
  - A headless automated browser (agent-browser / Playwright default profile)
    triggers the "请登录确认你不是机器人" (bot-check) wall on popular videos.
  - The reliable path is CDP: attach to the user's REAL Chrome, which carries
    their login state and browser fingerprint. The bundled cdp-proxy.mjs exposes
    a small HTTP API (localhost:3456) over the DevTools protocol.

Workflow:
  1. ensure the CDP proxy is running and connected to the user's Chrome
     (one-time setup: chrome://inspect/#remote-debugging -> allow; see SKILL.md)
  2. reuse an EXISTING tab on the same watch URL if present (bg tabs may render
     the transcript button invisible), else open a background tab
  3. expand the description ("更多"), click "内容转文字" / "Show transcript"
  4. wait for the transcript panel to render, then read its innerText
     (each block: `M:SS` timestamp + sentence text; may include a duration hint
     like `X分钟Y秒钟`; recommended-video noise may be appended at the end)
  5. parse into segments (English-only filter + monotonic timestamps), convert
     to SRT (segment end = next segment start; last segment +3s)
  6. close the background tab ONLY if we created it (reused tabs are left alone)

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

def open_video(port: int, url: str) -> tuple[str, bool]:
    """Return (target_id, created_by_us). Prefer an EXISTING tab on the same
    watch URL: CDP-created background tabs can render the transcript button
    with rect 0x0 (invisible) and clicks on it never trigger the panel — while
    the user's own tab renders it visible and works (get_transcript 400 / empty
    panel observed on bg tabs). created_by_us=False means the caller must NOT
    close the tab (it's the user's)."""
    try:
        targets = json.loads(_http_get(port, "/targets", timeout=10))
        for t in targets:
            if t.get("type") == "page":
                tu = t.get("url", "")
                # match the watch URL ignoring extra params (e.g. &pp, &t=)
                if url.split("&")[0] in tu.split("&")[0] and "watch" in tu:
                    log(f"Reusing existing tab ({tu[:80]})")
                    return t.get("targetId", ""), False
    except Exception:
        pass
    raw = _http_get(port, f"/new?url={urllib.parse.quote(url, safe='')}", timeout=30)
    try:
        target = json.loads(raw).get("targetId", "")
        if target:
            # Background tabs get throttled by Chrome: YouTube's description
            # area / transcript button can render with rect 0x0 (invisible) and
            # clicks silently do nothing. Bringing the tab to the foreground
            # forces the full layout to render.
            try:
                _http_get(port, f"/activate?target={target}", timeout=10)
            except Exception:
                pass
        return target, True
    except Exception:
        return "", True


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
    """Parse panel innerText into [(timestamp, sentence), ...].

    Structure per block (as rendered by YouTube's transcript panel):
        <chapter heading>          (optional, skipped)
        M:SS | H:MM:SS             (timestamp, e.g. 0:16 / 17:46 / 1:30:14)
        <sentence text>            (one or more lines)
    The panel may be followed by recommended-video noise (Chinese titles,
    viewer counts, etc.) — filter with an English-text heuristic and require
    timestamps to be monotonic (time going backwards = left the transcript).
    The monotonic check (break on a jump backwards >60s) also drops the
    duplicate second pass when the panel re-renders (observed: 861 segments
    rendered twice -> 1722; the jump back to 0:00 stops parsing).
    """
    lines = text.split("\n")
    TS_RE = re.compile(r"^(\d+):(\d{2})(?::(\d{2}))?$")  # M:SS or H:MM:SS
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
            h = int(m.group(1))
            if m.group(3) is not None:      # H:MM:SS
                sec = h * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            else:                            # M:SS
                sec = h * 60 + int(m.group(2))
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
    parts = ts.split(":")
    if len(parts) == 3:                      # H:MM:SS
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(parts[0]) * 60 + int(parts[1])


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


def fetch_timedtext_fallback(port: int, target: str, max_wait: int = 15) -> str | None:
    """Recover the transcript when the panel hangs (spinner) — e.g. the
    get_transcript API is IP-blocked (400 Precondition check failed).

    The frontend still issues a /api/timedtext request when "内容转文字" is
    clicked; its URL shows up in the Performance API. Fetch it (valid signature,
    same login session), aggregate the rolling-window segments into ~6s
    sentences (this is exactly what the transcript panel displays), return SRT.
    """
    try:
        url = _eval(port, target,
            "(() => { const r = performance.getEntriesByType('resource').map(x => x.name); "
            "const u = r.find(n => n.includes('timedtext')); return u || ''; })()")
        if not url or not isinstance(url, str):
            log("  [timedtext fallback] no timedtext URL in performance entries")
            return None
        # kick off the fetch (fire-and-forget), store result on window.__ttFallback
        _eval(port, target,
            "fetch(%s).then(r => r.text()).then(t => { window.__ttFallback = t; })"
            " .catch(() => { window.__ttFallback = ''; }); 'ok'" % json.dumps(url))
        deadline = time.time() + max_wait
        while time.time() < deadline:
            ready = _eval(port, target, "typeof window.__ttFallback !== 'undefined' ? 'yes' : 'no'")
            if ready == "yes":
                break
            time.sleep(1)
        total = ""
        offset = 0
        while True:
            chunk = _eval(port, target, f"window.__ttFallback.substr({offset}, 150000)")
            if not chunk or not isinstance(chunk, str):
                break
            total += chunk
            offset += len(chunk)
            if len(chunk) < 150000:
                break
        if not total or len(total) < 1000:
            log(f"  [timedtext fallback] empty response ({len(total)} chars)")
            return None
        try:
            data = json.loads(total)
        except Exception:
            log("  [timedtext fallback] response is not JSON")
            return None
        events = data.get("events", [])
        texts = []
        for e in events:
            segs = e.get("segs") or []
            t = "".join(s.get("utf8", "") for s in segs)
            if t.strip():
                texts.append((e.get("tStartMs", 0), t))
        if len(texts) < 10:
            log(f"  [timedtext fallback] too few text events ({len(texts)})")
            return None
        # aggregate: ~6s window starting at each sentence's first event
        W = 6000
        sentences: list[tuple[int, str]] = []
        i = 0
        while i < len(texts):
            cur = texts[i][0]
            window_end = cur + W
            parts = []
            while i < len(texts) and texts[i][0] < window_end:
                t = re.sub(r">>\s*", "", texts[i][1])
                t = re.sub(r"\s+", " ", t).strip()
                if t:
                    parts.append(t)
                i += 1
            if parts:
                sentences.append((cur, " ".join(parts)))
        if not sentences:
            log("  [timedtext fallback] aggregation produced nothing")
            return None
        log(f"  [timedtext fallback] aggregated {len(sentences)} sentences from {len(texts)} events")
        blocks = []
        for idx, (start, sent) in enumerate(sentences):
            end = sentences[idx + 1][0] if idx + 1 < len(sentences) else start + 3000
            if end <= start:
                end = start + 2000
            blocks.append((start, end, sent))
        out = []
        for idx, (start, end, sent) in enumerate(blocks, 1):
            out.append(f"{idx}\n{fmt_srt(start // 1000)} --> {fmt_srt(end // 1000)}\n{sent}\n")
        return "\n".join(out) + "\n"
    except Exception as e:
        log(f"  [timedtext fallback] error: {e}")
        return None


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
    tab_created = True
    try:
        log(f"Opening {args.url}")
        target, tab_created = open_video(args.proxy_port, args.url)
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

        # 3. click "内容转文字" / "Show transcript" (the description-area button).
        #    IMPORTANT: do NOT additionally click the "转写文稿" tab afterwards —
        #    that puts the panel into a spinner state where segments NEVER render
        #    (observed repeatedly). The button's own command already selects the
        #    transcript tab; segments render ~30-40s after this single click, and
        #    the poll loop below waits for them.
        find_and_click(
            args.proxy_port, target,
            """(() => {
                const btns = [...document.querySelectorAll('button')];
                const cand = btns.filter(x => {
                    const t = (x.textContent||'');
                    return t.includes('内容转文字') || t.includes('Show transcript') || t.includes('Transcript');
                });
                if (!cand.length) return 'no transcript btn';
                // prefer a VISIBLE instance (bg tabs may hold invisible duplicates with rect 0x0)
                const b = cand.find(x => x.offsetParent !== null) || cand[0];
                b.scrollIntoView({block:'center'});
                b.click();
                return 'clicked transcript btn';
            })()""",
            sleep_after=5,
        )

        # 4. wait for the transcript panel to render — YouTube often loads
        #    the segments lazily after the button is clicked (current layout
        #    takes ~30-40s; the poll loop below handles the wait).
        time.sleep(3)

        # 6. find the best candidate panel (transcript segments — many
        #    timestamps + real English sentences) anywhere in the document
        #    including shadow roots. Priority:
        #    1) ytd-transcript-segment-renderer elements (current layout —
        #       the transcript renders inside ytd-engagement-panel-section-list-renderer)
        #    2) the legacy renderers checked below
        #    3) fallback: scan any element with 20+ timestamps
        js_find = (
            "(() => {"
            " const tsRE = /[0-9]+:[0-9]{2}/g;"
            " const segs = [...document.querySelectorAll('ytd-transcript-segment-renderer')];"
            " if (segs.length >= 20) {"
            "   window.__ytTrans = segs.map(el => (el.innerText || '').trim()).join('\\n');"
            "   return JSON.stringify({found: true, chars: window.__ytTrans.length, ts: segs.length, src: 'ytd-transcript-segment-renderer'});"
            " }"
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
            " let best = null;"
            " for (const el of document.querySelectorAll('div, yt-formatted-string, span')) {"
            "   let t = '';"
            "   try { t = (el.innerText || '').trim(); } catch (_) { continue; }"
            "   if (t.length < 8000) continue;"
            "   const ts = (t.match(tsRE) || []).length;"
            "   if (ts >= 80 && (!best || ts > best.ts)) best = {el, chars: t.length, ts};"
            " }"
            " if (best) { window.__ytTrans = best.el.innerText; return JSON.stringify({found: true, chars: best.chars, ts: best.ts, src: 'fallback-scan'}); }"
            " return JSON.stringify({found: false, segCount: segs.length});"
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
        MAX_ATTEMPTS = 18  # 18 x 5s = 90s; current layout takes ~30-40s to render segments
        for attempt in range(MAX_ATTEMPTS):
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
            log(f"  waiting for transcript panel (attempt {attempt+1}/{MAX_ATTEMPTS}, "
                f"chars={len(text.strip())}, {find_info})")
            time.sleep(5)
        if len(text.strip()) < 300:
            log("Transcript panel appears empty (or not rendered).")
            # FALLBACK: the frontend still issues a /api/timedtext request even
            # when the panel hangs (its URL lands in the Performance API). Fetch
            # it and aggregate the rolling-window segments into ~6s sentences —
            # this bypasses the get_transcript IP-block entirely.
            srt = fetch_timedtext_fallback(args.proxy_port, target)
            if srt:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(srt)
                log(f"FALLBACK: aggregated timedtext -> {args.out}")
                return 0
            try:
                diag = _eval(args.proxy_port, target,
                    "(() => { const tsRE = /[0-9]+:[0-9]{2}/g; const out = []; "
                    "for (const el of document.querySelectorAll('ytd-transcript-segment-renderer, ytd-engagement-panel-section-list-renderer, div')) { "
                    "  let t=''; try { t=(el.innerText||'').trim(); } catch(_) {continue;} "
                    "  const ts=(t.match(tsRE)||[]).length; "
                    "  if (t.length>=100) out.push({tag: el.tagName, cls: (el.className||'').toString().slice(0,50), chars: t.length, ts}); "
                    "} out.sort((a,b)=>b.ts-a.ts); return JSON.stringify(out.slice(0,8)); })()")
                log(f"  candidates: {str(diag)[:300]}")
            except Exception:
                pass
            log("  If you see a 'confirm you are not a robot' wall, make sure you are")
            log("  logged into YouTube in your Chrome, then retry.")
            log("  If the panel shows a spinner that never resolves, the get_transcript API is likely")
            log("  IP-blocked (400 Precondition check failed) — the timedtext fallback above")
            log("  usually recovers the transcript; if it also failed, retry once.")
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
        # Only close a tab WE created — never the user's own reused tab.
        if target and tab_created:
            try:
                _http_get(args.proxy_port, f"/close?target={target}", timeout=5)
                log("Closed the background tab")
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
