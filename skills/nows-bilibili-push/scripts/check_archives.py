#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
核对稿件状态：定时时间 / 分区 / 创作声明 / 封面（含宽高比判断是否为自定义封面）

用法:
  python check_archives.py                       # 列出最近 20 条
  python check_archives.py --match "OpenAI"      # 只看标题含关键词的
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

JS_LIST = """
async () => {
  const r = await fetch('/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=40&tid=0&order=pubdate',
                        {credentials:'include'});
  const j = await r.json();
  const arc = (j.data && j.data.arc_audits) || [];
  return arc.slice(0,40).map(a=>({
      title:(a.Archive||{}).title, cover:(a.Archive||{}).cover,
      dtime:(a.Archive||{}).dtime, ptime:(a.Archive||{}).ptime,
      copyright:(a.Archive||{}).copyright, tid:(a.Archive||{}).tid,
      aid:(a.Archive||{}).aid, bvid:(a.Archive||{}).bvid}));
}
"""

JS_IMG = """
async (url) => new Promise(res => {
  const im = new Image();
  im.onload = () => res({w: im.naturalWidth, h: im.naturalHeight});
  im.onerror = () => res({err: 'load fail'});
  setTimeout(() => res({err: 'timeout'}), 15000);
  im.src = url;
})
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


def ts(v):
    if not v:
        return "—"
    return datetime.datetime.fromtimestamp(int(v)).strftime("%Y-%m-%d %H:%M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--match", help="标题关键词过滤")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    args = ap.parse_args()

    chrome = find_chrome()
    if not chrome:
        print("❌ 未找到 Chrome")
        raise SystemExit(1)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=args.profile, executable_path=chrome, headless=True,
            user_agent=UA, locale="zh-CN", viewport={"width": 1280, "height": 800},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(MGR_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(8)

        items = page.evaluate(JS_LIST)
        if args.match:
            items = [x for x in items if args.match in str(x["title"])]

        print(f"共 {len(items)} 条\n")
        for x in items:
            cov = ""
            if x["cover"]:
                base = x["cover"].split("@")[0]
                sz = page.evaluate(JS_IMG, base)
                if not sz.get("err") and sz.get("h"):
                    ratio = sz["w"] / sz["h"]
                    kind = "4:3" if abs(ratio - 4/3) < 0.06 else (
                           "16:9" if abs(ratio - 16/9) < 0.06 else f"{ratio:.2f}")
                    cov = f"{sz['w']}x{sz['h']}({kind})"
            print(f"- {str(x['title'])[:44]}")
            print(f"    定时={ts(x['dtime'])}  发布={ts(x['ptime'])}  "
                  f"声明={x['copyright']} 分区={x['tid']}  封面={cov}")
            print(f"    {x['bvid']}  aid={x['aid']}")
        ctx.close()


if __name__ == "__main__":
    main()
