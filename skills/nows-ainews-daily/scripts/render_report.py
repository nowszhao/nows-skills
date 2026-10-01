#!/usr/bin/env python3
"""
把 candidates.json + reasons.json 渲染成一份可点击的 HTML 日报。

reasons.json 格式:
{
  "date": "2026-10-01",
  "digest": "今日综述",
  "picks": [
    {"video_id": "xxx", "priority": "必看", "reason": "为什么值得看...",
     "tags": ["Agent", "工程实践"]}
  ],
  "rejected": [{"video_id": "yyy", "why": "厂商软文"}]
}
rejected 里的视频不出现在报告里(标题带 AI 关键词但实质无关)。
既不在 picks 也不在 rejected 的候选,归入「其他命中」区。
"""
import argparse
import html
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent

PRIORITY_ORDER = {"必看": 0, "值得看": 1, "可选": 2}
PRIORITY_COLOR = {"必看": "#d92b2b", "值得看": "#e8890c", "可选": "#6b7280"}

CSS = """
:root { --bg:#f7f8fa; --card:#ffffff; --ink:#1a1d23; --sub:#6b7280;
        --line:#e5e7eb; --accent:#2563eb; }
* { box-sizing: border-box; }
body { margin:0; padding:32px 20px 64px; background:var(--bg); color:var(--ink);
  font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Helvetica Neue",Arial,sans-serif;
  line-height:1.6; }
.wrap { max-width:1080px; margin:0 auto; }
h1 { font-size:26px; margin:0 0 6px; letter-spacing:-0.3px; }
.meta { color:var(--sub); font-size:13px; margin-bottom:8px; }
.digest { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:16px 18px; margin:18px 0 26px; font-size:15px; }
.stats { display:flex; gap:22px; flex-wrap:wrap; color:var(--sub); font-size:13px;
  margin-bottom:24px; }
.stats b { color:var(--ink); font-size:18px; margin-right:4px; }
h2 { font-size:17px; margin:28px 0 12px; padding-left:9px; border-left:3px solid var(--accent); }
.card { background:var(--card); border:1px solid var(--line); border-radius:12px;
  padding:14px; display:flex; gap:12px; align-items:flex-start; margin-bottom:12px;
  transition:box-shadow .15s, transform .15s; }
.card:hover { box-shadow:0 6px 18px rgba(0,0,0,.08); transform:translateY(-1px); }
.card-main { flex:1; display:flex; gap:14px; min-width:0; text-decoration:none;
  color:inherit; }
.copy { flex:0 0 auto; align-self:flex-start; margin-left:2px; padding:5px 11px;
  font-size:12px; font-family:inherit; color:#374151; background:#f3f4f6;
  border:1px solid var(--line); border-radius:7px; cursor:pointer; white-space:nowrap;
  transition:background .15s, color .15s; }
.copy:hover { background:#e5e7eb; color:var(--ink); }
.copy.ok { background:#16a34a; color:#fff; border-color:#16a34a; }
.thumb { flex:0 0 180px; width:180px; }
.thumb img { width:180px; border-radius:8px; display:block; background:#e5e7eb; }
.body { flex:1; min-width:0; }
.title { font-size:15.5px; font-weight:600; margin:0 0 6px; }
.ch { font-size:13px; color:var(--sub); margin-bottom:8px; }
.reason { font-size:14px; color:#374151; margin:0 0 8px; }
.tags { display:flex; gap:6px; flex-wrap:wrap; }
.tag { font-size:11.5px; padding:2px 8px; border-radius:999px; background:#eef2ff;
  color:#4338ca; }
.pri { font-size:11.5px; padding:2px 8px; border-radius:999px; color:#fff; font-weight:600; }
.kw { font-size:11.5px; padding:2px 8px; border-radius:999px; background:#f3f4f6;
  color:#6b7280; }
.dim { font-size:12.5px; color:var(--sub); }
.empty { color:var(--sub); padding:20px; background:var(--card); border:1px dashed var(--line);
  border-radius:12px; }
"""


COPY_JS = """
document.addEventListener('click', function (ev) {
  var btn = ev.target.closest('.copy');
  if (!btn) return;
  ev.preventDefault();
  ev.stopPropagation();
  var url = btn.dataset.url;
  function done() {
    var old = btn.textContent;
    btn.textContent = '\\u5df2\\u590d\\u5236';
    btn.classList.add('ok');
    setTimeout(function () { btn.textContent = old; btn.classList.remove('ok'); }, 1500);
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = url;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); done(); } catch (err) {}
    document.body.removeChild(ta);
  }
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(url).then(done, fallback);
  } else {
    fallback();
  }
});
"""


def fmt_duration(sec):
    if not sec:
        return ""
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_views(n):
    if not n:
        return ""
    if n >= 10000:
        return f"{n/10000:.1f} 万"
    return str(n)


def fmt_ago(iso):
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    delta = datetime.now(timezone.utc) - dt
    hrs = delta.total_seconds() / 3600
    if hrs < 1:
        return f"{int(delta.total_seconds()//60)} 分钟前"
    if hrs < 24:
        return f"{int(hrs)} 小时前"
    return f"{int(hrs//24)} 天前"


def card(v, pick=None):
    e = html.escape
    title = e(v["title"])
    ch = e(v.get("channel", ""))
    if v.get("meta_failed"):
        dims = "元信息暂不可用（未开始的直播或已删除） · " + fmt_ago(v.get("published", ""))
    else:
        dims = " · ".join(x for x in [
            fmt_duration(v.get("duration")),
            f"{fmt_views(v.get('view_count'))}播放" if v.get("view_count") else "",
            fmt_ago(v.get("published", "")),
        ] if x)
    reason = e(pick.get("reason", "")) if pick else ""
    tags = ""
    if pick:
        pri = pick.get("priority", "值得看")
        pc = PRIORITY_COLOR.get(pri, "#6b7280")
        tag_html = "".join(f'<span class="tag">{e(t)}</span>' for t in pick.get("tags", []))
        tags = (f'<div class="tags"><span class="pri" style="background:{pc}">{e(pri)}</span>'
                f"{tag_html}</div>")
    else:
        kws = "".join(f'<span class="kw">{e(k)}</span>' for k in v.get("matched_keywords", [])[:6])
        tags = f'<div class="tags">{kws}</div>'
    thumb = v.get("thumbnail") or f"https://i.ytimg.com/vi/{v['video_id']}/hqdefault.jpg"
    return f"""<div class="card">
  <a class="card-main" href="{e(v['url'])}" target="_blank" rel="noopener">
    <div class="thumb"><img src="{e(thumb)}" alt="" loading="lazy"></div>
    <div class="body">
      <p class="title">{title}</p>
      <div class="ch">{ch}{(' · ' + dims) if dims else ''}</div>
      {f'<p class="reason">{reason}</p>' if reason else ''}
      {tags}
    </div>
  </a>
  <button class="copy" type="button" data-url="{e(v['url'])}" title="复制视频地址">复制链接</button>
</div>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="")
    ap.add_argument("--reasons", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--dir", default="", help="工作目录,默认当前目录")
    args = ap.parse_args()

    global BASE
    if args.dir:
        BASE = Path(args.dir).expanduser().resolve()
    cand_path = Path(args.candidates) if args.candidates else BASE / "candidates.json"
    reason_path = Path(args.reasons) if args.reasons else BASE / "reasons.json"

    data = json.loads(cand_path.read_text(encoding="utf-8"))
    cands = data.get("candidates", [])
    by_id = {c["video_id"]: c for c in cands}

    reasons = json.loads(reason_path.read_text(encoding="utf-8")) if reason_path.exists() else {}
    picks = [p for p in reasons.get("picks", []) if p.get("video_id") in by_id]
    picks.sort(key=lambda p: PRIORITY_ORDER.get(p.get("priority", "值得看"), 9))
    picked_ids = {p["video_id"] for p in picks}
    # 被判为「名不副实」的视频不出现在报告里
    rejected = reasons.get("rejected", [])
    rejected_ids = {r["video_id"] if isinstance(r, dict) else r for r in rejected}
    rest = [c for c in cands
            if c["video_id"] not in picked_ids and c["video_id"] not in rejected_ids]

    date = reasons.get("date") or datetime.now().strftime("%Y-%m-%d")
    out = args.out or str(BASE / f"report-{date}.html")

    e = html.escape
    digest = reasons.get("digest", "")
    stats = (f'<div class="stats">'
             f'<span><b>{data.get("channels_scanned", 0)}</b>订阅频道</span>'
             f'<span><b>{data.get("total_new_videos", 0)}</b>近 {data.get("window_hours", 24)}h 新视频</span>'
             f'<span><b>{len(cands)}</b>AI 命中</span>'
             f'<span><b>{len(picks)}</b>精选</span>'
             f'<span><b>{len(rejected_ids & set(by_id))}</b>条判为名不副实已剔除</span></div>')

    body = ""
    for p in picks:
        body += card(by_id[p["video_id"]], p)
    if not picks:
        body += '<div class="empty">今日暂无精选。</div>'

    rest_html = ""
    if rest:
        rest_html = f"<h2>其他命中 ({len(rest)})</h2>" + "".join(card(c) for c in rest)

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>YouTube AI 视频日报 · {e(date)}</title><style>{CSS}</style></head>
<body><div class="wrap">
<h1>YouTube AI 视频日报</h1>
<div class="meta">{e(date)} · 抓取时间 {e(data.get('generated_at','')[:16].replace('T',' '))} UTC ·
窗口 {data.get('window_hours',24)} 小时</div>
{stats}
{f'<div class="digest">{e(digest)}</div>' if digest else ''}
<h2>今日精选 ({len(picks)})</h2>
{body}
{rest_html}
</div>
<script>{COPY_JS}</script>
</body></html>"""
    Path(out).write_text(page, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
