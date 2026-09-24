#!/usr/bin/env python3
"""
step55_derive_srt.py — Step 5.5 of the nows-ytb-bilingualex pipeline:
TTS-clean the assembled bilingual .ass and derive the paired bilingual .srt.

What it does (idempotent; safe to re-run):
  1. Cleans stage-direction brackets `\\[[^\\]]*\\]` from every Dialogue Text field
     (TTS-safe). Collapses 2+ spaces. The cleaned .ass is written back in place.
  2. Derives a same-named .srt from the cleaned .ass:
       - ASS time `H:MM:SS.cc` (centiseconds) -> SRT `HH:MM:SS,mmm` (mmm = cc*10)
       - block = `idx\\nstart --> end\\nEN || ZH\\n` with blank-line separators
  3. Runs the收尾 QA and prints a report. Must all pass before delivery:
       - `||` missing = 0 ; bracket residue = 0 ; no-Chinese lines = 0 ; empty-ZH = 0
       - SRT block count == ASS dialogue count
       - timecode regex `^\\d{2}:\\d{2}:\\d{2},\\d{3} --> \\d{2}:\\d{2}:\\d{2},\\d{3}$` all pass
       - person consistency (您 and 你 must not both appear)

Note: a "no-Chinese" line is accepted if it still carries CJK punctuation or a
fullwidth form (e.g. a pure-math formula line `ZH = "(k - 1)²。"` with a Chinese
full stop `。` U+3002 but no Han characters).

Usage:
    python3 step55_derive_srt.py --workdir .
"""
import re, os, sys, glob, argparse


def clean_text(t: str) -> str:
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def ass_to_srt_time(code: str) -> str:
    h, mm, rest = code.split(":")
    s, cs = rest.split(".")
    return f"{int(h):02d}:{int(mm):02d}:{int(s):02d},{int(cs) * 10:03d}"


def parse_ass(path: str):
    out = []
    in_events = False
    for ln in open(path, encoding="utf-8"):
        if ln.strip() == "[Events]":
            in_events = True
            continue
        if not in_events:
            continue
        if ln.startswith("Format:"):
            continue
        if ln.startswith("Dialogue:"):
            body = ln[len("Dialogue:"):]
            parts = body.split(",", 9)
            if len(parts) < 10:
                start, end = parts[1], parts[2]
                text = ",".join(parts[9:]) if len(parts) > 9 else ""
            else:
                start, end, text = parts[1], parts[2], parts[9]
            out.append((start.strip(), end.strip(), text))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", default=".")
    args = ap.parse_args()
    wd = args.workdir

    ass_files = [f for f in glob.glob(os.path.join(wd, "*.ass"))]
    if len(ass_files) != 1:
        print(f"[step5.5] expected exactly 1 .ass in {wd}, found {len(ass_files)}: {ass_files}")
        return 1
    ASS = ass_files[0]
    base = ASS[:-4]
    SRT = base + ".srt"
    print(f"[step5.5] ASS = {os.path.basename(ASS)}")

    dlg = parse_ass(ASS)
    n = len(dlg)
    cleaned = []
    qa = {"no_delim": 0, "bracket_residue": 0, "no_zh": 0, "empty_zh": 0}
    for start, end, text in dlg:
        if " || " not in text:
            qa["no_delim"] += 1
            en, zh = text, ""
        else:
            en, zh = text.split(" || ", 1)
        en_c, zh_c = clean_text(en), clean_text(zh)
        if re.search(r"\[[^\]]*\]", en_c) or re.search(r"\[[^\]]*\]", zh_c):
            qa["bracket_residue"] += 1
        if not re.search(r"[一-鿿\u3000-\u303F\uFF00-\uFFEF]", zh_c):
            qa["no_zh"] += 1
        if zh_c.strip() == "":
            qa["empty_zh"] += 1
        cleaned.append((start, end, en_c, zh_c))

    # rewrite ASS in place with cleaned text
    src = open(ASS, encoding="utf-8").read().splitlines()
    oi = 0
    out_lines = []
    in_events = False
    for ln in src:
        if ln.strip() == "[Events]":
            in_events = True
            out_lines.append(ln)
            continue
        if in_events and ln.startswith("Dialogue:"):
            body = ln[len("Dialogue:"):]
            parts = body.split(",", 9)
            parts[1], parts[2], parts[9] = cleaned[oi][0], cleaned[oi][1], f"{cleaned[oi][2]} || {cleaned[oi][3]}"
            out_lines.append("Dialogue:" + ",".join(parts))
            oi += 1
        else:
            out_lines.append(ln)
    open(ASS, "w", encoding="utf-8").write("\n".join(out_lines) + "\n")

    # derive SRT
    srt = []
    for i, (start, end, en, zh) in enumerate(cleaned, 1):
        srt.append(str(i))
        srt.append(f"{ass_to_srt_time(start)} --> {ass_to_srt_time(end)}")
        srt.append(f"{en} || {zh}")
        srt.append("")
    open(SRT, "w", encoding="utf-8").write("\n".join(srt).rstrip("\n") + "\n")

    # QA
    tc = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")
    blocks = open(SRT, encoding="utf-8").read().rstrip("\n").split("\n\n")
    nb = len([b for b in blocks if b.strip()])
    tc_pass = sum(1 for b in blocks if b.strip() and tc.match(b.split("\n")[1]))
    full = "\n".join(f"{en} || {zh}" for _, _, en, zh in cleaned)
    has_nin, has_ni = "您" in full, "你" in full
    ok = (qa["no_delim"] == 0 and qa["bracket_residue"] == 0 and qa["no_zh"] == 0
          and qa["empty_zh"] == 0 and nb == n and tc_pass == nb and not (has_nin and has_ni))
    print(f"[step5.5] SRT = {os.path.basename(SRT)} ({nb} blocks), ASS dialogue={n}")
    print(f"  || missing={qa['no_delim']}  bracket_res={qa['bracket_residue']}  "
          f"no_zh={qa['no_zh']}  empty_zh={qa['empty_zh']}")
    print(f"  block-match={nb == n}  timecode={tc_pass}/{nb}  "
          f"您={has_nin} 你={has_ni} consistent={not (has_nin and has_ni)}")
    print(f"  FINAL QA: {'ALL PASS ✓' if ok else 'FAIL ✗'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
