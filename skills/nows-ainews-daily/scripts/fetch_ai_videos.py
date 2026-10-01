#!/usr/bin/env python3
"""
扫描 YouTube 订阅频道，召回最近 N 小时内「AI 相关」的视频候选。

阶段 1:并发抓各频道 RSS feed(无需登录,返回最近 15 条视频)
阶段 2:按发布时间窗 + AI 关键词过滤(召回优先,允许一定噪音)
阶段 3:对候选补 yt-dlp 元信息(时长/播放量),供后续排序与写推荐理由

输出: candidates.json
"""
import argparse
import concurrent.futures as cf
import json
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent
SUBS_FILE = BASE / "subscriptions.tsv"
PROFILES_FILE = BASE / "channel_profiles.tsv"
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"


def _find_ytdlp():
    p = shutil.which("yt-dlp")
    if p:
        return p
    for c in ("/opt/homebrew/bin/yt-dlp", "/usr/local/bin/yt-dlp",
              str(Path.home() / "miniconda3/bin/yt-dlp"),
              str(Path.home() / "anaconda3/bin/yt-dlp"),
              str(Path.home() / ".local/bin/yt-dlp")):
        if Path(c).exists():
            return c
    return "yt-dlp"


YTDLP = _find_ytdlp()

# 分层召回策略:关键词只做辅助信号,频道画像才是主判据
#   core / adjacent -> 窗口内视频全部进入候选(交由语义判断筛)
#   general         -> 需 >=1 个 AI 关键词信号
#   none            -> 需 >=2 个关键词命中(仅防漏,正常情况不该出现)
TIER_MIN_HITS = {"core": 0, "adjacent": 0, "general": 1, "none": 2, "unknown": 1}

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
MEDIA = "{http://search.yahoo.com/mrss/}"

# ---- 英文关键词:按词边界匹配,避免 main/said/Thai 之类误伤 ----
WORD_KEYS = [
    "ai", "a.i.", "aigc", "agi", "genai", "llm", "llms", "gpt", "gpts", "chatgpt",
    "claude", "gemini", "llama", "mistral", "qwen", "deepseek", "sora", "grok",
    "copilot", "midjourney", "runway", "pika", "kling", "sun o", "agent", "agents",
    "agentic", "rag", "mcp", "prompt", "prompts", "prompting", "embedding",
    "embeddings", "transformer", "transformers", "diffusion", "neural", "pytorch",
    "tensorflow", "huggingface", "hugging face", "machine learning", "deep learning",
    "fine-tune", "finetune", "fine-tuning", "inference", "tokenizer", "quantization",
    "openai", "anthropic", "nvidia", "cuda", "langchain", "llamaindex", "ollama",
    "comfyui", "stable diffusion", "multimodal", "vlm", "text-to-image", "chatbot",
    "n8n", "autogen", "crewai", "dify", "ragflow", "benchmark", "gpu", "tpu",
    "reinforcement learning", "rlhf", "distillation", "lora", "vibe coding",
]

# ---- 中文关键词:直接子串匹配 ----
SUB_KEYS = [
    "人工智能", "大模型", "大语言模型", "机器学习", "深度学习", "神经网络",
    "智能体", "提示词", "生成式", "多模态", "算力", "微调", "向量数据库",
    "知识库", "文生图", "文生视频", "语音合成", "数字人", "自动化", "AI",
    "AGI", "AIGC", "AI 编程", "模型推理", "预训练", "强化学习", "扩散模型",
    "Transformer", "transformer", "工作流", "开源模型",
]

WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k).replace(r"\ ", r"\s+") for k in WORD_KEYS) + r")\b",
    re.IGNORECASE,
)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def load_subscriptions(path: Path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"\t|\\t", line) if p]
        if len(parts) >= 2:
            name, cid = parts[0].strip(), parts[1].strip()
            if cid.startswith("UC"):
                out.append((name, cid))
    return out


def load_profiles(path: Path):
    """频道画像:规范化频道名 -> {tier, note}。"""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"\t|\\t", line) if p.strip()]
        if len(parts) < 2:
            continue
        key = norm(parts[0])
        if key and key not in out:
            out[key] = {"tier": parts[1], "note": parts[2] if len(parts) > 2 else ""}
    return out


def norm(name: str) -> str:
    return re.sub(r"\s+", "", name).lower()


def refresh_subscriptions():
    """用 Chrome cookie 重新拉取订阅列表(覆盖 subscriptions.tsv)。"""
    print("[*] 从 Chrome cookie 刷新订阅列表 ...", file=sys.stderr)
    p = subprocess.run(
        [YTDLP, "--cookies-from-browser", "chrome", "--flat-playlist",
         "--print", "%(channel)s\t%(channel_id)s", "--playlist-end", "3000",
         "https://www.youtube.com/feed/channels"],
        capture_output=True, text=True, timeout=300,
    )
    rows = sorted({l.strip() for l in p.stdout.splitlines() if "\t" in l})
    if rows:
        SUBS_FILE.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return [tuple(r.split("\t")[:2]) for r in rows]


def fetch_rss(item):
    name, cid = item
    url = RSS_URL.format(cid=cid)
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
        root = ET.fromstring(raw)
        vids = []
        for e in root.findall(f"{ATOM}entry"):
            vid = e.findtext(f"{YT}videoId")
            title = e.findtext(f"{ATOM}title") or ""
            pub = e.findtext(f"{ATOM}published") or ""
            desc = e.findtext(f"{MEDIA}description") or ""
            if not vid or not pub:
                continue
            try:
                dt = datetime.fromisoformat(pub)
            except ValueError:
                continue
            vids.append({
                "video_id": vid,
                "title": title.strip(),
                "channel": name,
                "channel_id": cid,
                "published": dt.astimezone(timezone.utc).isoformat(),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "description": (desc or "").strip()[:600],
            })
        return name, cid, vids, None
    except Exception as ex:  # noqa: BLE001
        return name, cid, [], f"{type(ex).__name__}: {ex}"


def match_keywords(text: str):
    hits = set()
    for m in WORD_RE.finditer(text):
        hits.add(m.group(0).lower())
    for k in SUB_KEYS:
        if k in text:
            hits.add(k)
    return sorted(hits)


def enrich(v):
    """用 yt-dlp 补时长 / 播放量。优先带 Chrome cookie,失败则降级为匿名、再失败就跳过。"""
    v.setdefault("thumbnail", f"https://i.ytimg.com/vi/{v['video_id']}/hqdefault.jpg")
    v.setdefault("duration", None)
    v.setdefault("view_count", None)
    for extra in (["--cookies-from-browser", "chrome"], []):
        try:
            p = subprocess.run(
                [YTDLP, *extra, "--dump-json", "--no-warnings", "--no-playlist",
                 "--skip-download", v["url"]],
                capture_output=True, text=True, timeout=90,
            )
            d = json.loads(p.stdout)
            v["duration"] = d.get("duration")
            v["view_count"] = d.get("view_count")
            v["like_count"] = d.get("like_count")
            v["channel_follower_count"] = d.get("channel_follower_count")
            v["categories"] = d.get("categories")
            if v["duration"]:
                return v
        except Exception:  # noqa: BLE001
            continue
    # 两条路径都拿不到元信息:通常是尚未开始的直播或已删除的视频
    if not v.get("duration") and not v.get("view_count"):
        v["meta_failed"] = True
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=24, help="时间窗口(小时)")
    ap.add_argument("--refresh-subs", action="store_true", help="先从 Chrome 重新拉订阅")
    ap.add_argument("--out", default="")
    ap.add_argument("--no-enrich", action="store_true", help="跳过 yt-dlp 补全(更快)")
    ap.add_argument("--dir", default="", help="工作目录(存放 tsv/json/html),默认当前目录")
    args = ap.parse_args()

    global BASE, SUBS_FILE, PROFILES_FILE
    if args.dir:
        BASE = Path(args.dir).expanduser().resolve()
        BASE.mkdir(parents=True, exist_ok=True)
    SUBS_FILE = BASE / "subscriptions.tsv"
    PROFILES_FILE = BASE / "channel_profiles.tsv"
    out_path = Path(args.out) if args.out else BASE / "candidates.json"

    subs = []
    if args.refresh_subs:
        try:
            subs = refresh_subscriptions()
        except Exception as ex:  # noqa: BLE001
            print(f"[!] 刷新订阅失败,回退本地列表: {ex}", file=sys.stderr)
    if not subs:
        subs = load_subscriptions(SUBS_FILE)
    if not subs:
        print("[!] 订阅列表为空", file=sys.stderr)
        sys.exit(1)
    print(f"[*] 扫描 {len(subs)} 个频道 ...", file=sys.stderr)

    all_vids, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        for name, cid, vids, err in ex.map(fetch_rss, subs):
            if err:
                failed.append({"channel": name, "channel_id": cid, "error": err})
            all_vids.extend(vids)
    print(f"[*] RSS 拿到 {len(all_vids)} 条视频条目", file=sys.stderr)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    fresh = [v for v in all_vids if datetime.fromisoformat(v["published"]) >= cutoff]
    print(f"[*] {args.hours}h 内新视频: {len(fresh)} 条", file=sys.stderr)

    # ---- 分层召回:频道画像是主判据,关键词只做辅助信号 ----
    profiles = load_profiles(PROFILES_FILE)
    tier_stat, unprofiled = {}, []
    cands = []
    seen = set()
    for v in fresh:
        if v["video_id"] in seen:
            continue
        seen.add(v["video_id"])
        key = norm(v.get("channel", ""))
        prof = profiles.get(key)
        tier = prof["tier"] if prof else "unknown"
        v["tier"] = tier
        v["channel_note"] = prof["note"] if prof else "未画像"
        hits = match_keywords(v["title"] + " " + v["description"])
        v["matched_keywords"] = hits
        if not prof:
            unprofiled.append(v["channel"])
        if len(hits) < TIER_MIN_HITS.get(tier, 1):
            continue
        cands.append(v)
        tier_stat[tier] = tier_stat.get(tier, 0) + 1
    print(f"[*] 分层召回: {tier_stat}", file=sys.stderr)
    if unprofiled:
        print(f"[!] 未画像频道 {len(set(unprofiled))} 个: "
              f"{sorted(set(unprofiled))[:10]}", file=sys.stderr)

    if cands and not args.no_enrich:
        with cf.ThreadPoolExecutor(max_workers=16) as ex:
            cands = list(ex.map(enrich, cands))

    tier_rank = {"core": 0, "adjacent": 1, "general": 2, "unknown": 2, "none": 3}
    cands.sort(key=lambda v: (
        tier_rank.get(v.get("tier"), 2),
        1 if "vendor" in (v.get("channel_note") or "") else 0,
        -(v.get("view_count") or 0),
    ))

    # 每频道每日上限:避免厂商/高产量频道刷屏(按播放量取头部)
    counted, kept = {}, []
    for v in cands:
        n = counted.get(v["channel"], 0)
        limit = 2 if "vendor" in (v.get("channel_note") or "") else 4
        if n >= limit:
            continue
        counted[v["channel"]] = n + 1
        kept.append(v)
    cands = kept

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_hours": args.hours,
        "channels_scanned": len(subs),
        "channels_failed": failed,
        "total_new_videos": len(fresh),
        "tier_stat": tier_stat,
        "unprofiled_channels": sorted(set(unprofiled)),
        "candidates": cands,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] 写入 {out_path}", file=sys.stderr)
    print(json.dumps({
        "channels_scanned": len(subs),
        "rss_failures": len(failed),
        "new_videos_in_window": len(fresh),
        "candidates_by_tier": tier_stat,
        "ai_candidates": len(cands),
        "unprofiled": sorted(set(unprofiled)),
    }, ensure_ascii=False, indent=2))
    print("\n--- 候选清单(供语义判断) ---")
    for c in cands:
        print(f"[{c['tier']:8s}] {c['channel'][:20]:20s} | {c['title'][:70]}")


if __name__ == "__main__":
    main()
