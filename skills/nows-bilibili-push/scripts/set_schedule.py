#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修改【已投稿/定时中】稿件的定时发布时间。

用法:
  python set_schedule.py --match "关键词" --date 2026-10-08 --time 10:00
  python set_schedule.py --aid 117365551601461,117365568181507 --date 2026-10-08 --time 10:00
  python set_schedule.py --match "NetworkChuck" --date 2026-10-08 --time 10:00 --dry   # 只改不保存

注意：B站限制 最早≥5分钟、最晚≤15天（脚本会先校验）。
"""
import argparse
import datetime
import glob
import os
import time

from playwright.sync_api import sync_playwright

MGR_URL = "https://member.bilibili.com/platform/upload-manager/article"
DEFAULT_PROFILE = os.path.expanduser("~/.workbuddy/bili_profile")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

JS_FIRE = """
(sel) => {
  const e = document.querySelector(sel);
  if (!e) return 'notfound ' + sel;
  ['mouseover','mousedown','mouseup','click'].forEach(t =>
    e.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
  return 'fired ' + sel;
}
"""

JS_PICK_DAY = """
(day) => {
  const els = Array.from(document.querySelectorAll('.date-picker-body-item'));
  const t = els.find(e => (e.innerText||'').trim() === day
                      && !(e.className||'').includes('disabled'));
  if (!t) return 'notfound day ' + day + ' (可选:' +
      els.filter(e => !(e.className||'').includes('disabled'))
         .map(e => (e.innerText||'').trim()).join(',') + ')';
  ['mouseover','mousedown','mouseup','click'].forEach(x =>
    t.dispatchEvent(new MouseEvent(x, {bubbles:true, cancelable:true, view:window, button:0})));
  return 'picked day ' + day;
}
"""

JS_PICK_TIME = """
([val, colIdx]) => {
  const wrp = document.querySelectorAll('.time-picker-panel-select-wrp')[colIdx];
  if (!wrp) return 'no wrp ' + colIdx;
  const it = Array.from(wrp.querySelectorAll('.time-picker-panel-select-item'))
      .find(e => (e.innerText||'').trim() === val);
  if (!it) return 'notfound ' + val;
  const fire = (el) => ['mouseover','mousedown','mouseup','click'].forEach(t =>
    el.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
  fire(it.children.length ? it.children[0] : it);
  fire(it);
  return 'fired ' + val;
}
"""


def find_chrome():
    pats = [
        os.path.expanduser("~/.agent-browser/browsers/chrome-*/"
                           "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for p in pats:
        hit = glob.glob(p)
        if hit:
            return sorted(hit)[-1]
    return None


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def set_one(page, aid, title, day, hour, minute, dry=False):
    log(f"===== {str(title)[:26]}  aid={aid} =====")
    page.goto(f"https://member.bilibili.com/platform/upload/video/frame?type=edit&aid={aid}",
              wait_until="domcontentloaded", timeout=90000)
    time.sleep(13)

    shown0 = page.evaluate("() => Array.from(document.querySelectorAll('.date-show'))"
                           ".map(e=>(e.innerText||'').trim())")
    log(f"  改前: {shown0}")

    st = page.evaluate("() => { const s=document.querySelector('.time-switch-wrp .switch-container');"
                       "return s ? s.className : 'none'; }")
    if "active" not in st:
        page.evaluate(JS_FIRE, ".time-switch-wrp .switch-container")
        time.sleep(3)
        log("  已打开定时开关")

    # 日期
    page.evaluate(JS_FIRE, ".date-picker-date")
    time.sleep(3)
    log(f"  日期: {page.evaluate(JS_PICK_DAY, day)}")
    time.sleep(3)

    # 时间：必须分步触发，且选完不能点别处
    page.evaluate(JS_FIRE, ".date-picker-timer")
    time.sleep(3)
    log(f"  小时: {page.evaluate(JS_PICK_TIME, [hour, 0])}")
    time.sleep(2)
    log(f"  分钟: {page.evaluate(JS_PICK_TIME, [minute, 1])}")
    time.sleep(3)

    shown1 = page.evaluate("() => Array.from(document.querySelectorAll('.date-show'))"
                           ".map(e=>(e.innerText||'').trim())")
    log(f"  改后: {shown1}")

    if dry:
        log("  --dry，不保存")
        return

    r = page.evaluate("""
    () => {
      let b = document.querySelector('.submit-add');
      if (!b) b = Array.from(document.querySelectorAll('.submit-container *'))
          .find(e => { const t=(e.innerText||'').trim();
                       return t && t.length<=10 && /投稿|发布|保存|确定/.test(t); });
      if (!b) return 'no button';
      ['mouseover','mousedown','mouseup','click'].forEach(t =>
        b.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
      return 'clicked:' + (b.innerText||'').trim();
    }
    """)
    log(f"  保存: {r}")
    time.sleep(10)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aid", help="稿件 aid，逗号分隔")
    ap.add_argument("--match", help="标题关键词（与 --aid 二选一）")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--time", default="10:00", help="HH:MM")
    ap.add_argument("--dry", action="store_true", help="只改不保存")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    args = ap.parse_args()

    day = str(int(args.date.split("-")[2]))
    hh, mm = args.time.split(":")

    target = datetime.datetime.strptime(f"{args.date} {args.time}", "%Y-%m-%d %H:%M")
    delta = (target - datetime.datetime.now()).total_seconds()
    if delta < 300:
        log("❌ 定时时间必须距今 ≥5 分钟"); raise SystemExit(1)
    if delta > 15 * 86400:
        log("❌ 定时时间必须在 15 天内"); raise SystemExit(1)

    chrome = find_chrome()
    if not chrome:
        log("❌ 未找到 Chrome"); raise SystemExit(1)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=args.profile, executable_path=chrome, headless=True,
            user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 1000},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(MGR_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(8)

        if args.aid:
            targets = [(a.strip(), "") for a in args.aid.split(",")]
        else:
            items = page.evaluate("""
            async () => {
              const r = await fetch('/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=40&tid=0&order=pubdate',
                                    {credentials:'include'});
              const j = await r.json();
              return ((j.data&&j.data.arc_audits)||[]).slice(0,40).map(a=>({
                  aid:(a.Archive||{}).aid, title:(a.Archive||{}).title}));
            }
            """)
            targets = [(x["aid"], x["title"]) for x in items
                       if args.match in str(x["title"])]
        log(f"目标 {len(targets)} 个 → {args.date} {args.time}")

        for aid, title in targets:
            set_one(page, aid, title, day, hh, mm, dry=args.dry)
            time.sleep(3)

        if not args.dry:
            log("\n===== 复核 =====")
            page.goto(MGR_URL, wait_until="domcontentloaded", timeout=90000)
            time.sleep(8)
            res = page.evaluate("""
            async () => {
              const r = await fetch('/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=40&tid=0&order=pubdate',
                                    {credentials:'include'});
              const j = await r.json();
              return ((j.data&&j.data.arc_audits)||[]).slice(0,40).map(a=>({
                  title:(a.Archive||{}).title, dtime:(a.Archive||{}).dtime}));
            }
            """)
            kw = args.match or ""
            for x in res:
                if not kw or kw in str(x["title"]):
                    dt = x["dtime"]
                    s = datetime.datetime.fromtimestamp(int(dt)).strftime("%Y-%m-%d %H:%M") if dt else "无"
                    print(f"   {str(x['title'])[:34]}: {s}")
        ctx.close()


if __name__ == "__main__":
    main()
