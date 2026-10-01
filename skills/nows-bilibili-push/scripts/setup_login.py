#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首次使用：扫码登录 B站，把登录态存进持久化 profile，后续投稿免登录。

用法:
  python setup_login.py                      # 二维码输出到 ./bili_qr.png，每 8 秒刷新
  python setup_login.py --qr /tmp/qr.png     # 自定义二维码路径

流程：脚本打开登录页 → 截图二维码 → 用户用 B站 App 扫码确认 → 脚本检测到登录成功即退出。
若二维码过期会自动重新截图。
"""
import argparse
import glob
import os
import time

from playwright.sync_api import sync_playwright

LOGIN_URL = "https://passport.bilibili.com/login"
DEFAULT_PROFILE = os.path.expanduser("~/.workbuddy/bili_profile")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qr", default="bili_qr.png")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--wait", type=int, default=300, help="最长等待秒数")
    args = ap.parse_args()

    chrome = find_chrome()
    if not chrome:
        print("❌ 未找到 Chrome")
        raise SystemExit(1)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=args.profile, executable_path=chrome, headless=True,
            user_agent=UA, locale="zh-CN", viewport={"width": 1280, "height": 900},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        page = ctx.new_page()
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
        time.sleep(5)

        if "passport.bilibili.com" not in page.url:
            print(f"✅ 已登录（URL={page.url}），无需扫码")
            ctx.close()
            return

        print(f"请用 B站 App 扫码：{os.path.abspath(args.qr)}")
        page.screenshot(path=args.qr)
        print("（二维码会每 8 秒刷新，过期会自动重新生成）")

        start = time.time()
        while time.time() - start < args.wait:
            time.sleep(8)
            if "passport.bilibili.com" not in page.url:
                print(f"✅ 登录成功！URL={page.url}")
                print(f"登录态已保存到 {args.profile}，后续投稿免扫码")
                ctx.close()
                return
            page.screenshot(path=args.qr)   # 刷新二维码
            print(f"  等待扫码中… ({int(time.time()-start)}s)")

        print("⏰ 等待超时，未检测到登录")
        ctx.close()


if __name__ == "__main__":
    main()
