#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B站批量定时投稿（Playwright + 持久化登录 profile）

用法:
  python bilibili_push.py --tasks tasks.json                    # 默认定时=今天+10天 10:00
  python bilibili_push.py --tasks tasks.json --schedule "2026-10-11 20:00"
  python bilibili_push.py --tasks tasks.json --no-submit        # 只填表不提交（试跑）
  python bilibili_push.py --tasks tasks.json --only 0,2         # 只跑指定条目

tasks.json 格式（数组）:
[
  {
    "video": "/abs/path/a.mp4",
    "cover": "/abs/path/cover.png",
    "title": "标题（<=80字）",
    "desc":  "简介（多行）",
    "tags":  ["标签1","标签2"]
  }
]

注意：脚本内含大量针对 B站 Vue 组件的"反直觉"处理，改动前请先读 SKILL.md 的坑位清单。
"""
import argparse
import datetime
import glob
import json
import os
import sys
import time

from playwright.sync_api import sync_playwright

UPLOAD_URL = "https://member.bilibili.com/platform/upload/video/frame?page_from=creative_home_top_upload"
MGR_URL = "https://member.bilibili.com/platform/upload-manager/article"
DEFAULT_PROFILE = os.path.expanduser("~/.workbuddy/bili_profile")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

# 创作声明：与"内容无需标注"一致（B站 copyright=3），转载/自制会要求额外信息
DECLARATION = "内容无需标注"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def find_chrome():
    """优先用 agent-browser 自带的 Chrome for Testing，其次系统 Chrome"""
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


# ---------- JS 片段 ----------

# B站 是 Vue 组件，单纯 el.click() 不触发响应，必须派发完整鼠标事件序列
JS_FIRE = """
(sel) => {
  const e = document.querySelector(sel);
  if (!e) return 'notfound ' + sel;
  ['mouseover','mousedown','mouseup','click'].forEach(t =>
    e.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
  return 'fired ' + sel;
}
"""

JS_FIRE_TEXT = """
(txt) => {
  const els = Array.from(document.querySelectorAll('button,span,div'))
      .filter(e => (e.innerText||'').trim() === txt);
  if (!els.length) return 'notfound ' + txt;
  const e = els[els.length-1];
  ['mouseover','mousedown','mouseup','click'].forEach(t =>
    e.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
  return 'fired ' + txt;
}
"""

JS_PROGRESS = """
() => {
  const body = document.body.innerText || '';
  const m = body.match(/(\\d{1,3})\\s*%/);
  return {
    hasTitle: !!document.querySelector('input[type=text]'),
    pct: m ? m[1] + '%' : null,
    done: body.includes('上传完成') || body.includes('转码完成'),
    fail: body.includes('上传失败')
  };
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


def wait_upload_done(page, max_s=1800):
    start = time.time()
    last = 0
    while time.time() - start < max_s:
        r = page.evaluate(JS_PROGRESS)
        now = time.time()
        if now - last > 20:
            log(f"    上传中 {int(now-start)}s 进度={r['pct']} 完成={r['done']}")
            last = now
        if r["fail"]:
            return False, "上传失败"
        if r["hasTitle"] and r["done"]:
            return True, f"完成({int(now-start)}s)"
        time.sleep(5)
    return False, "等待上传超时"


def fill_basics(page, item):
    """标题 / 简介 / 标签"""
    # 标题
    try:
        page.locator("input[placeholder='请输入稿件标题']").first.fill(item["title"])
        log(f"    标题已填 ({len(item['title'])}字)")
    except Exception as e:
        log(f"    ✗ 标题: {str(e)[:70]}")

    # 简介：Quill，可见的是第 1 个，且里面预置了示例文字，必须先全选清掉
    try:
        ed = page.locator(".ql-editor").first
        ed.click(timeout=15000)
        time.sleep(1)
        page.keyboard.press("Control+a")
        time.sleep(0.5)
        page.keyboard.type(item["desc"], delay=1)
        time.sleep(2)
        ln = page.evaluate("() => { const e=document.querySelectorAll('.ql-editor')[0];"
                           "return e ? (e.innerText||'').length : 0; }")
        log(f"    简介已填 字数={ln} (目标 {len(item['desc'])})")
    except Exception as e:
        log(f"    ✗ 简介: {str(e)[:70]}")

    # 标签
    try:
        ti = page.locator("input[placeholder='按回车键Enter创建标签']").first
        for t in item.get("tags", [])[:8]:
            ti.click()
            ti.type(t, delay=30)
            page.keyboard.press("Enter")
            time.sleep(0.4)
        log(f"    标签已添加 {len(item.get('tags', [])[:8])} 个")
    except Exception as e:
        log(f"    ⚠ 标签(可忽略): {str(e)[:60]}")


def set_declaration(page):
    """创作声明：必填！不选的话点提交会静默失败"""
    page.evaluate(JS_FIRE, "input[placeholder*='创作声明']")
    time.sleep(3)
    r = page.evaluate("""
    () => {
      const i = document.querySelector('input[placeholder*="创作声明"]');
      const wrap = i ? (i.closest('.bcc-select') || i.closest('[class*=select]')) : null;
      const opts = Array.from((wrap || document).querySelectorAll('.bcc-option'));
      const t = opts.find(o => (o.innerText||'').trim().indexOf('%s') === 0);
      if (!t) return 'notfound:' + opts.slice(0,5).map(o=>(o.innerText||'').trim()).join(' / ');
      ['mouseover','mousedown','mouseup','click'].forEach(x =>
        t.dispatchEvent(new MouseEvent(x, {bubbles:true, cancelable:true, view:window, button:0})));
      return 'selected:%s';
    }
    """ % (DECLARATION, DECLARATION))
    time.sleep(2)
    log(f"    创作声明: {r}")


def set_cover(page, cover):
    """封面：打开弹窗 → 上传 → 勾选双比例同步 → 完成"""
    page.evaluate(JS_FIRE, ".edit-text")
    time.sleep(5)
    try:
        page.locator("input[type=file][accept*='image/png']").first.set_input_files(cover, timeout=60000)
        log("    封面文件已上传")
        time.sleep(8)
    except Exception as e:
        log(f"    ✗ 封面上传: {str(e)[:70]}")
        return
    # 双比例同步：是 checkbox 不是 switch
    r = page.evaluate("""
    () => {
      const wraps = document.querySelectorAll('.sync-checkbox-wrapper');
      if (!wraps.length) return 'no sync wrapper';
      let n = 0;
      wraps.forEach(w => {
        const cb = w.querySelector('input[type=checkbox]');
        if (cb && !cb.checked) {
          const label = w.querySelector('.sync-checkbox') || w;
          ['mouseover','mousedown','mouseup','click'].forEach(t =>
            label.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window, button:0})));
          n++;
        }
      });
      return 'toggled ' + n;
    }
    """)
    log(f"    双比例同步: {r}")
    time.sleep(3)
    page.evaluate(JS_FIRE_TEXT, "完成")
    time.sleep(5)


def set_schedule(page, day, hour, minute):
    """定时发布。时间必须分步触发，且选完不能点别处（会取消选择）"""
    page.evaluate(JS_FIRE, ".time-switch-wrp .switch-container")
    time.sleep(3)
    page.evaluate(JS_FIRE, ".date-picker-date")
    time.sleep(3)
    r = page.evaluate("""
    (day) => {
      const els = Array.from(document.querySelectorAll('.date-picker-body-item'));
      const t = els.find(e => (e.innerText||'').trim() === day
                          && !(e.className||'').includes('disabled'));
      if (!t) return 'notfound day ' + day;
      ['mouseover','mousedown','mouseup','click'].forEach(x =>
        t.dispatchEvent(new MouseEvent(x, {bubbles:true, cancelable:true, view:window, button:0})));
      return 'picked day ' + day;
    }
    """, day)
    log(f"    日期: {r}")
    time.sleep(3)

    page.evaluate(JS_FIRE, ".date-picker-timer")
    time.sleep(3)
    # 分步！合并成一次调用会失效
    log(f"    小时: {page.evaluate(JS_PICK_TIME, [hour, 0])}")
    time.sleep(2)
    log(f"    分钟: {page.evaluate(JS_PICK_TIME, [minute, 1])}")
    time.sleep(3)
    shown = page.evaluate("() => Array.from(document.querySelectorAll('.date-show'))"
                          ".map(e=>(e.innerText||'').trim())")
    log(f"    已选时间: {shown}")


def submit_and_verify(page, title_prefix):
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
    log(f"    提交: {r}")
    time.sleep(14)
    return page.evaluate("""
    async (prefix) => {
      const r = await fetch('/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=30&tid=0&order=pubdate',
                            {credentials:'include'});
      const j = await r.json();
      const arc = (j.data && j.data.arc_audits) || [];
      const hit = arc.find(a => String((a.Archive||{}).title||'').indexOf(prefix) === 0);
      if (!hit) return {found:false};
      const A = hit.Archive || {};
      return {found:true, title:A.title, dtime:A.dtime, copyright:A.copyright,
              tid:A.tid, cover:(A.cover||'').slice(-26)};
    }
    """, title_prefix)


def push_one(page, item, sched, submit):
    log(f"===== {item.get('name') or os.path.basename(item['video'])} =====")
    page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=90000)
    time.sleep(6)
    try:
        page.click("text=不用了", timeout=4000)
        time.sleep(2)
    except Exception:
        pass

    # 上传：必须用 file input 索引 0（name=buploader 那个是隐藏诱饵）
    page.locator("input[type=file]").nth(0).set_input_files(item["video"], timeout=180000)
    ok, msg = wait_upload_done(page)
    log(f"  上传: {msg}")
    if not ok:
        return False, msg
    time.sleep(4)

    fill_basics(page, item)
    set_cover(page, item["cover"])
    set_declaration(page)
    set_schedule(page, sched["day"], sched["hour"], sched["minute"])

    if not submit:
        log("  --no-submit，跳过提交")
        return True, "填表完成(未提交)"

    v = submit_and_verify(page, item["title"][:12])
    if v.get("found"):
        dt = v.get("dtime")
        dts = datetime.datetime.fromtimestamp(int(dt)).strftime("%Y-%m-%d %H:%M") if dt else "❌无定时"
        log(f"  ✅ 校验通过 定时={dts} copyright={v.get('copyright')}")
        return True, f"已提交(定时 {dts})"
    log("  ❌ 校验失败：稿件列表未找到该标题（多半是必填项缺失被拦截）")
    return False, "提交后未找到稿件"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True, help="tasks.json 路径")
    ap.add_argument("--schedule", help="定时时间 'YYYY-MM-DD HH:MM'，默认=今天+10天 10:00")
    ap.add_argument("--no-submit", action="store_true")
    ap.add_argument("--only", help="只跑指定条目索引，逗号分隔，如 0,2")
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    args = ap.parse_args()

    with open(args.tasks, encoding="utf-8") as f:
        items = json.load(f)
    if args.only:
        items = [items[int(i)] for i in args.only.split(",")]

    for it in items:
        for k in ("video", "cover", "title", "desc"):
            if not os.path.exists(it[k]) if k in ("video", "cover") else not it.get(k):
                log(f"❌ 字段缺失: {k} @ {it.get('title','?')}")
                sys.exit(1)

    # 定时：默认今天+10天 10:00（B站限制 最早≥5分钟、最晚≤15天）
    if args.schedule:
        d, t = args.schedule.split(" ")
        hh, mm = t.split(":")
        sched = {"day": str(int(d.split("-")[2])), "hour": hh, "minute": mm,
                 "date": d}
    else:
        target = datetime.datetime.now() + datetime.timedelta(days=10)
        sched = {"day": str(target.day), "hour": "10", "minute": "00",
                 "date": target.strftime("%Y-%m-%d")}
    log(f"定时发布: {sched['date']} {sched['hour']}:{sched['minute']}")

    chrome = find_chrome()
    if not chrome:
        log("❌ 未找到 Chrome。先跑 agent-browser install，或安装 Google Chrome")
        sys.exit(1)
    log(f"Chrome: {chrome}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=args.profile, executable_path=chrome, headless=True,
            user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 1000},
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage"],
        )
        page = ctx.new_page()
        results = []
        for it in items:
            ok, msg = push_one(page, it, sched, submit=not args.no_submit)
            results.append((it.get("name") or os.path.basename(it["video"]), ok, msg))
            time.sleep(3)

        print("\n===== 汇总 =====")
        for n, ok, m in results:
            print(f"  {'✅' if ok else '❌'} {n}: {m}")
        ctx.close()


if __name__ == "__main__":
    main()
