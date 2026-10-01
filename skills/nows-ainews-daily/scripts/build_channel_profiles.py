#!/usr/bin/env python3
"""
采集各频道的内容样本,用于给频道做 AI 相关度画像。

对每个订阅频道抓取最近若干条视频标题,统计 AI 关键词密度作为参考信号,
输出 channel_samples.json 供人工/Agent 判断频道定位。

注意:关键词密度只是参考信号,不是判据——最终定位由语义判断决定。
"""
import concurrent.futures as cf
import json
import re
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

BASE = Path(__file__).resolve().parent
SUBS_FILE = BASE / "subscriptions.tsv"
RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={cid}"

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

WORD_KEYS = [
    "ai", "aigc", "agi", "genai", "llm", "llms", "gpt", "gpts", "chatgpt", "claude",
    "gemini", "llama", "mistral", "qwen", "deepseek", "sora", "grok", "copilot",
    "midjourney", "agent", "agents", "agentic", "rag", "mcp", "prompt", "prompts",
    "prompting", "embedding", "transformer", "diffusion", "neural", "pytorch",
    "machine learning", "deep learning", "fine-tune", "inference", "tokenizer",
    "openai", "anthropic", "nvidia", "langchain", "multimodal", "chatbot",
    "automation", "model", "models", "training", "data",
]
SUB_KEYS = ["人工智能", "大模型", "大语言模型", "机器学习", "深度学习", "神经网络",
            "智能体", "提示词", "生成式", "多模态", "算力", "微调", "AI", "AGI", "AIGC"]

WORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in WORD_KEYS) + r")\b", re.IGNORECASE)


def load_subscriptions(path: Path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p for p in re.split(r"\t|\\t", line) if p]
        if len(parts) >= 2 and parts[1].strip().startswith("UC"):
            out.append((parts[0].strip(), parts[1].strip()))
    return out


def fetch(cid):
    try:
        req = urllib.request.Request(RSS_URL.format(cid=cid), headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            root = ET.fromstring(r.read())
        titles = []
        for e in root.findall(f"{ATOM}entry")[:20]:
            vid = e.findtext(f"{YT}videoId")
            t = (e.findtext(f"{ATOM}title") or "").strip()
            if vid:
                titles.append(t)
        return cid, titles, None
    except Exception as ex:  # noqa: BLE001
        return cid, [], f"{type(ex).__name__}: {ex}"


def density(titles):
    if not titles:
        return 0.0
    hit = 0
    for t in titles:
        blob = t
        if WORD_RE.search(blob) or any(k in blob for k in SUB_KEYS):
            hit += 1
    return round(hit / len(titles), 2)


def main():
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="", help="工作目录,默认当前目录")
    args = ap.parse_args()

    global BASE
    if args.dir:
        BASE = Path(args.dir).expanduser().resolve()
    subs = load_subscriptions(BASE / "subscriptions.tsv")
    print(f"[*] 采集 {len(subs)} 个频道样本 ...", file=sys.stderr)
    out, failed = [], []
    with cf.ThreadPoolExecutor(max_workers=24) as ex:
        results = list(ex.map(lambda s: (s[0], *fetch(s[1])), subs))
    for name, cid_titles_err in [(r[0], r[1:]) for r in results]:
        cid, titles, err = cid_titles_err
        if err:
            failed.append({"channel": name, "channel_id": cid, "error": err})
        out.append({
            "channel": name,
            "channel_id": cid,
            "n_titles": len(titles),
            "ai_kw_density": density(titles),
            "sample_titles": titles[:8],
        })
    out.sort(key=lambda x: (-x["ai_kw_density"], x["channel"].lower()))
    payload = {"channels_scanned": len(subs), "failed": failed, "channels": out}
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "channel_samples.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[+] 写入 channel_samples.json (失败 {len(failed)})", file=sys.stderr)


if __name__ == "__main__":
    main()
