#!/usr/bin/env python3
"""
split_translation.py — Parse a downloaded .ass subtitle into a line-by-line
translation work file, then split it into chunks for parallel/sequential
translation by the Agent's built-in model.

Outputs (all under the working directory):
  transcript.txt            — one line per subtitle event:
                              <idx>\t<start>\t<end>\t<ENGLISH>
  parts/part_01.txt ...     — compact model inputs, sized by English word budget:
                              <idx>\t<duration_seconds>\t<ENGLISH>
                              Each chunk carries a context header:
                                * GLOBAL CONTEXT — video title / URL / duration /
                                  subtitle source (read from the top-level
                                  manifest.json written by download.py), so every
                                  chunk is translated with the full picture in mind
                                * PREVIOUS CHUNK — the last N lines (default 4)
                                  of the previous chunk, so boundary sentences keep
                                  their continuity. Lines are marked with '#',
                                  reference only, never translated.
  parts/manifest.json       — bookkeeping for the assemble step
  subtitle_meta.json        — parsed ASS header + event count

Canonical timestamps are stored in `subtitle_meta.json`; translation workers do
not copy them. The final assembler injects them deterministically by idx.

Usage:
    python3 split_translation.py <subtitle.ass> [--words-per-part 1100]
                                 [--context-lines 4] [--out <dir>]

Exit codes: 0 ok, 1 fatal.
"""

import argparse
import glob
import json
import os
import re


def log(msg: str) -> None:
    print(f"[split] {msg}", flush=True)


ASS_DIALOGUE = re.compile(r"^Dialogue:\s*(?P<layer>[^,]*),"
                          r"(?P<start>[^,]*),(?P<end>[^,]*),"
                          r"(?P<style>[^,]*),(?P<name>[^,]*),"
                          r"(?P<marginl>[^,]*),(?P<marginr>[^,]*),"
                          r"(?P<marginv>[^,]*),(?P<effect>[^,]*),"
                          r"(?P<text>.*)$")

SRT_BLOCK = re.compile(r"^(\d+)\s*$")  # SRT index line (handled line-wise below)


def strip_ass_tags(text: str) -> str:
    """Remove {\\...} override tags and replace \\N / \\h with plain spaces."""
    text = re.sub(r"\{[^}]*\}", "", text)
    text = text.replace(r"\N", " ").replace(r"\n", " ").replace(r"\h", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def srt_ts_to_ass(ts: str) -> str:
    """'HH:MM:SS,mmm' -> 'H:MM:SS.cc' (ASS centiseconds).

    Carry-safe: rounding can land on exactly 100 cs (e.g. .999 -> 100), which
    must roll over into the next second (.00). The naive
    `f"{round(ms/10):02d}"` produced illegal 3-digit centiseconds like
    '0:24:33.100' and assemble_final.py then rejected the whole file
    (observed 2026-09 on a 70-min video: 16 bad timestamps).
    """
    ts = ts.strip().replace(",", ".")
    h, m, s = ts.split(":")
    sec, _, frac = s.partition(".")
    total_cs = (int(h) * 360000 + int(m) * 6000 + int(sec) * 100
                + round(float(frac[:3]) / 10))
    h2, r = divmod(total_cs, 360000)
    m2, r = divmod(r, 6000)
    s2, cc = divmod(r, 100)
    return f"{h2}:{m2:02d}:{s2:02d}.{cc:02d}"


def ass_time_seconds(ts: str) -> float:
    h, m, s = ts.strip().split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def model_input_line(idx: int, ev: dict) -> str:
    duration = max(0.01, ass_time_seconds(ev["end"]) - ass_time_seconds(ev["start"]))
    return f"{idx}\t{duration:.2f}\t{ev['text']}\n"


def parse_srt(path: str) -> tuple[list[dict], list[str]]:
    """Parse an SRT file into the same event shape as parse_ass."""
    events = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        lines = [ln.rstrip("\n") for ln in f]
    i = 0
    n = len(lines)
    while i < n:
        # skip blank lines
        if not lines[i].strip():
            i += 1
            continue
        if not SRT_BLOCK.match(lines[i].strip()):
            i += 1
            continue
        i += 1
        if i >= n or "-->" not in lines[i]:
            continue
        time_part = lines[i]
        i += 1
        m = re.match(r"^\s*([\d:.,]+)\s*-->\s*([\d:.,]+)", time_part)
        if not m:
            continue
        start = srt_ts_to_ass(m.group(1))
        end = srt_ts_to_ass(m.group(2))
        text_parts = []
        while i < n and lines[i].strip():
            text_parts.append(lines[i])
            i += 1
        text = " ".join(text_parts).strip()
        events.append({
            "layer": "0", "start": start, "end": end,
            "style": "Default", "name": "",
            "marginl": "0", "marginr": "0", "marginv": "0",
            "effect": "", "text": strip_ass_tags(text),
        })
        i += 1
    return events, ["[Script Info]", "ScriptType: v4.00+"]


def parse_ass(path: str) -> tuple[list[dict], list[str]]:
    """Return (events, header_lines). Event text is tag-stripped."""
    events = []
    header = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            m = ASS_DIALOGUE.match(line)
            if m:
                events.append({
                    "layer": m.group("layer"),
                    "start": m.group("start"),
                    "end": m.group("end"),
                    "style": m.group("style"),
                    "name": m.group("name"),
                    "marginl": m.group("marginl"),
                    "marginr": m.group("marginr"),
                    "marginv": m.group("marginv"),
                    "effect": m.group("effect"),
                    "text": strip_ass_tags(m.group("text")),
                })
            else:
                header.append(line)
    return events, header


def parse_any(path: str) -> tuple[list[dict], list[str], str]:
    """Dispatch on extension: .ass -> parse_ass, otherwise try SRT."""
    if path.lower().endswith(".ass"):
        return (*parse_ass(path), "ass")
    return (*parse_srt(path), "srt")


def load_global_context(out_dir: str) -> dict:
    """Read the top-level manifest.json (written by download.py) to build the
    GLOBAL CONTEXT block that gets prepended to every chunk."""
    ctx = {"title": None, "url": None, "duration_sec": None,
           "subtitle_kind": None, "subtitle_lang": None}
    top_manifest = os.path.join(out_dir, "manifest.json")
    if os.path.exists(top_manifest):
        try:
            with open(top_manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ctx:
                ctx[key] = data.get(key)
        except Exception as e:
            log(f"WARN: could not read top-level manifest for context ({e})")
    # fall back to the MP4 filename when there is no manifest
    if not ctx.get("title"):
        mp4s = glob.glob(os.path.join(out_dir, "*.mp4"))
        if mp4s:
            ctx["title"] = os.path.splitext(os.path.basename(mp4s[0]))[0]
    return ctx


def build_chunk_header(ctx: dict, part_no: int, start_idx: int, end_idx: int,
                       prev_lines: list[str]) -> str:
    """Context header for one chunk: GLOBAL CONTEXT + PREVIOUS CHUNK (if any).
    All context lines start with '#' so translators can tell them apart from
    the actual lines to translate."""
    lines = []
    lines.append("# === GLOBAL CONTEXT (reference only — do NOT translate) ===")
    if ctx.get("title"):
        lines.append(f"# Video: {ctx['title']}")
    if ctx.get("url"):
        lines.append(f"# URL: {ctx['url']}")
    if ctx.get("duration_sec"):
        d = ctx["duration_sec"]
        lines.append(f"# Duration: {int(d // 60)}m {int(d % 60):02d}s")
    if ctx.get("subtitle_kind"):
        lines.append(
            f"# Subtitle source: {ctx['subtitle_kind']} ({ctx.get('subtitle_lang')})"
        )
    lines.append(f"# Chunk {part_no}: translate ONLY the lines below "
                 f"(idx {start_idx}-{end_idx})")
    lines.append("# === END GLOBAL CONTEXT ===")
    if prev_lines:
        lines.append("# === PREVIOUS CHUNK (reference only — do NOT translate) ===")
        lines.append("# (the last lines of the previous chunk, for context)")
        for ln in prev_lines:
            lines.append(f"# {ln.rstrip(chr(10))}")
        lines.append("# === END PREVIOUS CHUNK ===")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("subtitle", help="path to the source .ass file")
    ap.add_argument("--words-per-part", type=int, default=1100,
                    help="target English words per translation chunk (default 1100)")
    ap.add_argument("--max-lines-per-part", type=int, default=80,
                    help="safety cap on lines per chunk (default 80)")
    ap.add_argument("--lines-per-part", type=int, default=None,
                    help="legacy fixed-size override; disables word-budget chunking")
    ap.add_argument("--context-lines", type=int, default=4,
                    help="how many tail lines of the previous chunk to inject "
                         "as context (default 4, 0 disables)")
    ap.add_argument("--out", default=".", help="working directory")
    args = ap.parse_args()

    if args.words_per_part < 100:
        log("--words-per-part must be at least 100")
        return 1
    if args.max_lines_per_part < 1:
        log("--max-lines-per-part must be at least 1")
        return 1
    if args.lines_per_part is not None and args.lines_per_part < 1:
        log("--lines-per-part must be at least 1")
        return 1

    if not os.path.exists(args.subtitle):
        log(f"Subtitle file not found: {args.subtitle}")
        return 1

    events, source_header = parse_any(args.subtitle)[:2]
    if not events:
        log("No Dialogue events found in the subtitle file.")
        return 1
    log(f"Parsed {len(events)} events from {args.subtitle}")

    os.makedirs(args.out, exist_ok=True)
    parts_dir = os.path.join(args.out, "parts")
    os.makedirs(parts_dir, exist_ok=True)

    # work file
    work_path = os.path.join(args.out, "transcript.txt")
    with open(work_path, "w", encoding="utf-8") as f:
        for i, ev in enumerate(events, start=1):
            f.write(f"{i}\t{ev['start']}\t{ev['end']}\t{ev['text']}\n")
    log(f"Transcript written: {work_path}")

    model_lines = [model_input_line(i, ev) for i, ev in enumerate(events, start=1)]

    # global context for every chunk
    ctx = load_global_context(args.out)

    # Split by actual English workload instead of a fixed line count. A line
    # cap remains as a guard against off-by-one failures on extremely short ASR
    # lines. The legacy flag preserves old callers.
    total = len(events)
    ranges = []
    if args.lines_per_part:
        n = args.lines_per_part
        ranges = [(s, min(s + n, total)) for s in range(0, total, n)]
    else:
        start = 0
        words = 0
        for i, ev in enumerate(events):
            line_words = max(1, len(ev["text"].split()))
            line_count = i - start
            if i > start and (words + line_words > args.words_per_part
                              or line_count >= args.max_lines_per_part):
                ranges.append((start, i))
                start, words = i, 0
            words += line_words
        if start < total:
            ranges.append((start, total))

    n_parts = len(ranges)
    parts = []
    for p, (start_zero, end_zero) in enumerate(ranges, start=1):
        start_line = start_zero + 1
        end_line = end_zero
        part_path = os.path.join(parts_dir, f"part_{p:02d}.txt")

        # previous-chunk tail lines (context for continuity)
        prev_lines = []
        if args.context_lines > 0 and p > 1:
            prev_start = max(0, start_line - 1 - args.context_lines)
            prev_lines = model_lines[prev_start:start_line - 1]

        chunk_header = build_chunk_header(ctx, p, start_line, end_line, prev_lines)
        with open(part_path, "w", encoding="utf-8") as dst:
            dst.write(chunk_header)
            for line_no in range(start_line, end_line + 1):
                dst.write(model_lines[line_no - 1])
        part_words = sum(max(1, len(events[i]["text"].split()))
                         for i in range(start_zero, end_zero))
        parts.append({
            "file": os.path.basename(part_path),
            "start_idx": start_line,
            "end_idx": end_line,
            "lines": end_line - start_line + 1,
            "words": part_words,
        })
        log(f"  {part_path}: lines {start_line}-{end_line}, {part_words} words"
            f"{' (+context)' if prev_lines or ctx.get('title') else ''}")

    # manifest
    manifest = {
        "source_subtitle": os.path.abspath(args.subtitle),
        "event_count": total,
        "words_per_part": args.words_per_part,
        "max_lines_per_part": args.max_lines_per_part,
        "legacy_lines_per_part": args.lines_per_part,
        "context_lines": args.context_lines,
        "parts": parts,
        "transcript": os.path.basename(work_path),
        "output_format": "<idx>\\t<duration_seconds>\\t<text>",
        "translation_output_format": "<idx>\\t<ENGLISH>\\t<CHINESE>",
    }
    with open(os.path.join(parts_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    meta = {"header": source_header, "events": events}
    with open(os.path.join(args.out, "subtitle_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    log(f"Split into {n_parts} part(s). Translation instructions: "
        "references/translation_prompt.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
