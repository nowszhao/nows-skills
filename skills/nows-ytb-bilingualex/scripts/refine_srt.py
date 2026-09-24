#!/usr/bin/env python3
"""
refine_srt.py — Semantic re-splitting of ASR subtitles using the Agent's own
model for every splitting DECISION and this script for every timestamp
(script-anchored, never model-authored).

Two operation modes (controlled by which prepare subcommand you run):

  MODE B — "over-long only" (default, see `prepare`)
      Only lines longer than --max-words or --max-dur-ms are re-split; other
      lines keep aggregate_srt.py's mechanical boundaries. Fast, low-cost,
      fixes the "one line is 30+ words" problem.

  MODE FULL — indexed semantic boundaries (see `prepare-full`)
      The script labels the immutable global source word stream. The Agent
      returns sentence-end word IDs plus punctuation only; the script rebuilds
      exact source text and timestamps. Overlap context lets decisions cross
      chunk edges without copying or rewriting source words.

The Agent outputs sentence text only — never timestamps. `apply` maps every
output sentence back onto the SOURCE FRAGMENT timeline with a greedy global
word-stream match: sentence START = the START of the fragment holding the
sentence's first word (inherited verbatim; refined by word-count ratio inside
the fragment when the first word sits mid-fragment), END = next sentence's
START (de-overlap).

Pipeline position:
    raw ASR fragments -> aggregate_srt.py -> [THIS STEP] -> split_translation.py
                                             (LLM refine, optional)

Usage:
    # mode B
    python3 refine_srt.py prepare <sentence_level.srt> <fragments.srt> \
        [--workdir .] [--max-words 16] [--max-dur-ms 6000] \
        [--lines-per-part 30] [--context-lines 2]
    # mode FULL
    python3 refine_srt.py prepare-full <sentence_level.srt> <fragments.srt> \
        [--workdir .] [--max-words 16] [--words-per-part 1200] \
        [--overlap-words 48]
    # apply (works for both modes)
    python3 refine_srt.py apply [--workdir .] [--out transcript_refined.srt]

Exit codes: 0 ok, 1 fatal, 2 validation problems in apply (nothing written).
"""

import argparse
import json
import os
import re
import sys


def log(msg: str) -> None:
    print(f"[refine] {msg}", flush=True)


def parse_srt_time(t: str) -> int:
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def fmt_srt_time(ms: int) -> str:
    if ms < 0:
        ms = 0
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    mss = ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{mss:03d}"


def read_captions(in_path: str) -> list[tuple[int, int, str]]:
    """Parse an SRT into (start_ms, end_ms, text) tuples."""
    raw = open(in_path, encoding="utf-8").read()
    blocks = re.split(r"\n\s*\n", raw.strip())
    captions = []
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            start_s, end_s = lines[1].split(" --> ")
            start_ms = parse_srt_time(start_s.strip())
            end_ms = parse_srt_time(end_s.strip())
        except Exception:
            continue
        text = " ".join(lines[2:]).strip()
        if not text:
            continue
        captions.append((start_ms, end_ms, text))
    return captions


def assign_fragments(lines: list[tuple[int, int, str]],
                     frags: list[tuple[int, int, str]]) -> list[list[int]]:
    """Each aggregated line consumes the fragments whose START falls inside its
    window (END is the de-overlapped next-line START, so this is exact)."""
    out: list[list[int]] = []
    fi = 0
    n_frags = len(frags)
    for ls, le, _ in lines:
        idxs = []
        while fi < n_frags and frags[fi][0] < le:
            idxs.append(fi)
            fi += 1
        out.append(idxs)
    return out


def build_word_seq(frag_idxs: list[int],
                   frags: list[tuple[int, int, str]]) -> list[tuple[str, int]]:
    """Word stream of one line with its source fragment index:
    [(word, frag_idx), ...]. Speaker markers are stripped (matches aggregate).

    Words hyphen-split across fragments ("open-" + "weight") are rejoined into
    one token, because the refinement agents output the joined form; comparing
    them token-by-token would otherwise fail the whole timeline match.
    """
    words = []
    pending: tuple[str, int] | None = None  # (partial word, frag_idx of its start)
    for fi in frag_idxs:
        for w in frags[fi][2].split():
            w2 = re.sub(r">>\s*", "", w)
            if not w2:
                continue
            if pending is not None:
                w2, fi_eff = pending[0] + w2, pending[1]
                pending = None
            else:
                fi_eff = fi
            if w2.endswith("-"):
                pending = (w2, fi_eff)
                continue
            words.append((w2, fi_eff))
    if pending is not None:
        words.append((pending[0].rstrip("-") or pending[0], pending[1]))
    return words


def load_global_context(workdir: str) -> dict:
    ctx = {"title": None, "url": None, "duration_sec": None}
    top_manifest = os.path.join(workdir, "manifest.json")
    if os.path.exists(top_manifest):
        try:
            with open(top_manifest, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in ctx:
                ctx[key] = data.get(key)
        except Exception as e:
            log(f"WARN: could not read manifest for context ({e})")
    return ctx


def make_chunk_header(ctx: dict, prev_lines: list[str], mode: str,
                      commit_range: tuple[int, int] | None = None) -> str:
    h = ["# === GLOBAL CONTEXT (reference only — do NOT translate) ==="]
    if ctx.get("title"):
        h.append(f"# Video: {ctx['title']}")
    if ctx.get("url"):
        h.append(f"# URL: {ctx['url']}")
    if ctx.get("duration_sec"):
        d = ctx["duration_sec"]
        h.append(f"# Duration: {int(d // 60)}m {int(d % 60):02d}s")
    h.append("# Subtitle source: auto-generated ASR (en), aggregated sentence-level")
    if mode == "full-boundaries":
        first, last = commit_range or (0, 0)
        h += [
            "# Task: choose semantic sentence END positions for the annotated",
            "#       source word stream. Do not rewrite or repeat the source.",
            "# Output: one line per sentence end: W<id>\\t<terminal punctuation>",
            "#       where punctuation is one of . ? !",
            f"# Commit range: W{first:06d}-W{last:06d}. Output ends only in",
            "#       this range; surrounding words are read-only overlap context.",
            "# Target 5-16 words per sentence. Preserve meaning and avoid leaving",
            "#       dangling conjunctions. The final video word must be an end",
            "#       only when it lies inside this file's Commit range.",
        ]
    elif mode == "full":
        h += [
            "# Task: rewrite the WHOLE block below into semantically complete",
            "#       sentences. For each line you may KEEP it, SPLIT it into",
            "#       several clauses, or MERGE it with the NEXT line.",
            "# Output ONE line per final sentence: S<seq>\\t<sentence text>",
            "#       (seq = 1,2,3... in video order, one output line per sentence)",
            "# Keep every word in order across the block (only punctuation may",
            "#       be added); 5-16 words per sentence; NEVER output timestamps.",
        ]
    else:
        h += [
            "# Task: re-split each over-long line below into semantically complete",
            "#       clauses. Output ONE line per clause: <idx>\\t<clause text>",
            "#       Keep idx as-is; keep every word in order (only punctuation",
            "#       may be added); 2-4 clauses per line; 5-16 words per clause;",
            "#       NEVER output timestamps.",
        ]
    h.append("# === END GLOBAL CONTEXT ===")
    if prev_lines:
        h.append("# === PREVIOUS CHUNK (reference only — do NOT translate) ===")
        for ln in prev_lines:
            h.append(f"# {ln.rstrip(chr(10))}")
        h.append("# === END PREVIOUS CHUNK ===")
    if mode == "full-boundaries":
        h.append("# === ANNOTATED WORD STREAM (W<id>:word) ===")
    elif mode == "full":
        h.append("# === LINES TO REWRITE (idx\\tstart\\tend\\ttext) ===")
    else:
        h.append("# === LINES TO RE-SPLIT (idx\\tstart\\tend\\ttext) ===")
    return "\n".join(h) + "\n"


# ---------------------------------------------------------------------------
# prepare (mode B) & prepare-full (mode FULL)
# ---------------------------------------------------------------------------

def _write_plan(plan: dict, workdir: str) -> None:
    with open(os.path.join(workdir, "refine_plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    log(f"Plan written: {os.path.join(workdir, 'refine_plan.json')}")


def _base_plan(args) -> dict:
    return {
        "mode": getattr(args, "mode", "b"),
        "sentence_srt": os.path.abspath(args.sentence),
        "fragments_srt": os.path.abspath(args.fragments),
        "manifest": os.path.abspath(args.manifest) if args.manifest else None,
        "max_words": args.max_words,
        "max_dur_ms": getattr(args, "max_dur_ms", 6000),
        "overlong": [],
        "parts": [],
        "output": args.out,
    }


def _format_annotated_words(stream: list[tuple[str, int, int]],
                            lines: list[tuple[int, int, str]], start: int,
                            end: int, words_per_row: int = 12) -> str:
    """Word IDs plus source-line timing cues for semantic boundary decisions."""
    rows = []
    pos = start
    while pos < end:
        line_idx = stream[pos][2]
        line_start = pos
        while pos < end and stream[pos][2] == line_idx:
            pos += 1
        source_start, source_end, _ = lines[line_idx - 1]
        label = (f"L{line_idx:05d} {fmt_srt_time(source_start)}-"
                 f"{fmt_srt_time(source_end)}")
        first_row = True
        for row_start in range(line_start, pos, words_per_row):
            cells = [f"W{i + 1:06d}:{stream[i][0]}"
                     for i in range(row_start, min(row_start + words_per_row, pos))]
            rows.append(f"{label if first_row else ' ' * len(label)} | "
                        + " ".join(cells))
            first_row = False
    return "\n".join(rows)


def cmd_prepare(args) -> int:
    if not os.path.exists(args.sentence) or not os.path.exists(args.fragments):
        log("sentence-level SRT and fragments SRT are both required.")
        return 1

    lines = read_captions(args.sentence)
    frags = read_captions(args.fragments)
    if not lines or not frags:
        log("No captions parsed from one of the inputs.")
        return 1

    assignment = assign_fragments(lines, frags)
    wordseqs = [build_word_seq(a, frags) for a in assignment]

    overlong: list[int] = []
    for i, ((ls, le, _), wseq) in enumerate(zip(lines, wordseqs), start=1):
        n_words = len(wseq)
        dur = le - ls
        if n_words > args.max_words or dur > args.max_dur_ms:
            overlong.append(i)

    log(f"{len(lines)} aggregated lines, {len(overlong)} over-long "
        f"(words>{args.max_words} or dur>{args.max_dur_ms}ms)")

    plan = _base_plan(args)
    if not overlong:
        _write_plan(plan, args.workdir)
        log("Nothing to refine — write a no-op message and exit 0.")
        return 0

    parts_dir = os.path.join(args.workdir, "refine_parts")
    os.makedirs(parts_dir, exist_ok=True)
    ctx = load_global_context(args.workdir)

    src_lines = []
    for i in range(len(lines)):
        s, e, t = lines[i]
        src_lines.append(f"{i + 1}\t{fmt_srt_time(s)}\t{fmt_srt_time(e)}\t{t}")

    chunks: list[list[int]] = []
    cur: list[int] = []
    for idx in overlong:
        if cur and len(cur) >= args.lines_per_part:
            chunks.append(cur)
            cur = []
        cur.append(idx)
    if cur:
        chunks.append(cur)

    parts = []
    for p, idxs in enumerate(chunks, start=1):
        first = idxs[0]
        prev_start = max(0, first - 1 - args.context_lines)
        prev_lines = src_lines[prev_start:first - 1]
        header = make_chunk_header(ctx, prev_lines, "b")
        body = "\n".join(src_lines[i - 1] for i in idxs)
        fname = f"refine_part_{p:02d}.txt"
        with open(os.path.join(parts_dir, fname), "w", encoding="utf-8") as f:
            f.write(header + body + "\n")
        parts.append({"file": fname, "idxs": idxs})
        log(f"  {fname}: lines {idxs}")

    plan["overlong"] = overlong
    plan["parts"] = parts
    _write_plan(plan, args.workdir)
    log("Next: Agent translates each refine_part_NN.txt into refined_NN.txt "
        "(see references/refine_prompt.md), then run `apply`.")
    return 0


def cmd_prepare_full(args) -> int:
    if not os.path.exists(args.sentence) or not os.path.exists(args.fragments):
        log("sentence-level SRT and fragments SRT are both required.")
        return 1

    if args.words_per_part < 100:
        log("--words-per-part must be at least 100")
        return 1
    if args.overlap_words < 0 or args.overlap_words >= args.words_per_part:
        log("--overlap-words must be >= 0 and smaller than --words-per-part")
        return 1

    lines = read_captions(args.sentence)
    frags = read_captions(args.fragments)
    if not lines or not frags:
        log("No captions parsed from one of the inputs.")
        return 1

    parts_dir = os.path.join(args.workdir, "refine_parts")
    os.makedirs(parts_dir, exist_ok=True)
    ctx = load_global_context(args.workdir)

    assignments = assign_fragments(lines, frags)
    stream, _ = build_global_stream(lines, assignments, frags)
    total_words = len(stream)
    if not total_words:
        log("No words found in source timeline.")
        return 1

    # Core ranges never overlap. Each input includes read-only words on both
    # sides, so the model can make a good decision at a chunk boundary without
    # forcing an artificial sentence break there.
    n = args.words_per_part
    overlap = args.overlap_words
    n_parts = (total_words + n - 1) // n
    parts = []
    for p in range(1, n_parts + 1):
        core_start = (p - 1) * n
        core_end = min(p * n, total_words)
        input_start = max(0, core_start - overlap)
        input_end = min(total_words, core_end + overlap)
        commit = (core_start + 1, core_end)
        header = make_chunk_header(ctx, [], "full-boundaries", commit)
        body = _format_annotated_words(stream, lines, input_start, input_end)
        fname = f"refine_part_{p:02d}.txt"
        with open(os.path.join(parts_dir, fname), "w", encoding="utf-8") as f:
            f.write(header + body + "\n")
        parts.append({
            "file": fname,
            "input_start_word": input_start + 1,
            "input_end_word": input_end,
            "commit_start_word": core_start + 1,
            "commit_end_word": core_end,
            "word_count": input_end - input_start,
        })
        log(f"  {fname}: commit W{core_start + 1:06d}-W{core_end:06d}; "
            f"context W{input_start + 1:06d}-W{input_end:06d}")

    plan = _base_plan(args)
    plan["mode"] = "full-boundaries"
    plan["total_words"] = total_words
    plan["words_per_part"] = n
    plan["overlap_words"] = overlap
    plan["parts"] = parts
    _write_plan(plan, args.workdir)
    log(f"Mode FULL boundary-index: {n_parts} chunks covering {total_words} words.")
    log("Next: Agent writes sentence-end IDs for each refine_part_NN.txt "
        "(see references/refine_prompt_full.md), then run `apply`.")
    return 0


# ---------------------------------------------------------------------------
# apply (works for both modes)
# ---------------------------------------------------------------------------

def parse_refined(path: str) -> list[tuple[str, str]]:
    """Read one refined_NN.txt into [(seq_or_idx, text), ...] preserving order.
    Mode b: seq_or_idx is the source idx; mode full: it is the 'S<seq>' token."""
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            parts = ln.rstrip("\n").split("\t", 1)
            if len(parts) != 2:
                log(f"WARN: bad refined line in {os.path.basename(path)}: {ln[:60]!r}")
                continue
            out.append((parts[0].strip(), parts[1].strip()))
    return out


def parse_boundary_decisions(path: str) -> list[tuple[int, str]]:
    """Read compact FULL output: W<global-word-id>\t<.?!>."""
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            parts = ln.rstrip("\n").split("\t")
            if len(parts) != 2 or not re.fullmatch(r"W\d+", parts[0].strip()):
                log(f"WARN: bad boundary line in {os.path.basename(path)}: {ln[:60]!r}")
                continue
            punct = parts[1].strip()
            if punct not in (".", "?", "!"):
                log(f"WARN: bad punctuation in {os.path.basename(path)}: {punct!r}")
                continue
            out.append((int(parts[0].strip()[1:]), punct))
    return out


def _sentence_from_stream(stream: list[tuple[str, int, int]], start: int,
                          end: int, punct: str) -> str:
    words = [stream[i][0] for i in range(start, end)]
    if not words:
        return ""
    # Preserve every source token; only normalize the terminal punctuation.
    words[-1] = re.sub(r"[.,?!;:]+$", "", words[-1]) + punct
    return " ".join(words)


def norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


# Max stream positions scanned for a single sentence word, and max stream words
# that may be joined to form one sentence word (see match_sentence).
MAX_LOOKAHEAD = 8
MAX_JOIN = 3


def _frag_word_starts(stream: list[tuple[str, int, int]]) -> dict[int, int]:
    """Map each fragment index to its first position in the GLOBAL word stream."""
    starts: dict[int, int] = {}
    for i, (_, fi, _) in enumerate(stream):
        starts.setdefault(fi, i)
    return starts


def _refined_start(stream: list[tuple[str, int, int]],
                   frags: list[tuple[int, int, str]],
                   frag_starts: dict[int, int], pos: int) -> int:
    """START for the word at `pos`: the source fragment's START when the word
    begins that fragment (strict inheritance), otherwise an intra-fragment
    refinement by word-count ratio (only used when a sentence boundary falls
    INSIDE a fragment, which would otherwise produce overlap / 0-length lines).
    """
    _, fi, _ = stream[pos]
    f_start, f_end, ftext = frags[fi]
    offset = pos - frag_starts.get(fi, 0)
    if offset <= 0:
        return f_start
    frag_words = [w for w in (re.sub(r">>\s*", "", x) for x in ftext.split()) if w]
    total = len(frag_words)
    if total <= 1:
        return f_start
    ratio = min(offset / total, 1.0)
    return int(f_start + ratio * (f_end - f_start))


def build_global_stream(lines: list[tuple[int, int, str]],
                        assignments: list[list[int]],
                        frags: list[tuple[int, int, str]]):
    """Concatenate every line's words into one global stream.
    Returns (stream, line_ranges) where each element is (word, frag_idx, line_idx)
    and line_ranges maps line_idx -> (start_pos, end_pos)."""
    stream: list[tuple[str, int, int]] = []
    line_ranges: dict[int, tuple[int, int]] = {}
    for i, a in enumerate(assignments, start=1):
        ws = build_word_seq(a, frags)
        line_ranges[i] = (len(stream), len(stream) + len(ws))
        stream.extend((w, fi, i) for w, fi in ws)
    return stream, line_ranges


def match_sentence(sentence_words: list[str], stream: list[tuple[str, int, int]],
                   pos: int) -> tuple[int, int]:
    """Greedy match a sentence's words against the global stream from `pos`.

    Returns (end_pos, unmatched) where unmatched counts sentence words that
    could not be located.

    Two robustness rules (both matter for real ASR data):
    * Look-ahead is BOUNDED. An unbounded scan lets one unmatched word drag
      `end` to the end of the stream, collapsing every later timestamp.
    * A sentence word may be the join of several stream words: agents write
      "higher-dimensional" where ASR had "higher dimensional", and
      "open-weight" where ASR split the word across fragments.
    """
    end = pos
    unmatched = 0
    n_stream = len(stream)
    for sw in sentence_words:
        nsw = norm_word(sw)
        if not nsw:
            continue
        found = False
        limit = min(end + MAX_LOOKAHEAD, n_stream)
        i = end
        while i < limit:
            if norm_word(stream[i][0]) == nsw:
                end = i + 1
                found = True
                break
            i += 1
        if not found:  # one sentence word spanning several stream words
            for i in range(end, limit):
                for k in range(2, MAX_JOIN + 1):
                    if i + k > n_stream:
                        break
                    joined = "".join(norm_word(stream[j][0]) for j in range(i, i + k))
                    if joined == nsw:
                        end = i + k
                        found = True
                        break
                if found:
                    break
        if not found:
            # Advance nothing: a local mismatch must not shift the timeline.
            unmatched += 1
    return end, unmatched


def build_sentence_texts(mode: str, lines: list[tuple[int, int, str]],
                         overlong_set: set[int],
                         refined: dict[int, list[str]] | None) -> tuple[list[str], list[int]]:
    """Ordered list of sentence texts to emit, plus the source line each
    sentence's first word belongs to (for B mode sanity checks).

    mode 'full': every sentence comes from the Agent's rewrite (may merge lines).
    mode 'b':    non-over-long lines verbatim + over-long lines' clauses.
    """
    if mode == "full":
        if not refined:
            return [], []
        texts, lines_ = [], []
        for seq in sorted(refined.keys(), key=lambda k: _seq_key(k)):
            for t in refined[seq]:
                texts.append(t)
                lines_.append(None)
        return texts, lines_

    texts, lines_ = [], []
    for i, (ls, le, text) in enumerate(lines, start=1):
        if i in overlong_set:
            clauses = (refined or {}).get(i) or [text]
            for c in clauses:
                texts.append(c)
                lines_.append(i)
        else:
            texts.append(text)
            lines_.append(i)
    return texts, lines_


def _seq_key(k) -> int:
    if isinstance(k, int):
        return k
    try:
        return int(str(k).lstrip("S"))
    except ValueError:
        return 10 ** 9


def cmd_apply(args) -> int:
    workdir = args.workdir
    plan_path = os.path.join(workdir, "refine_plan.json")
    if not os.path.exists(plan_path):
        log(f"Plan not found: {plan_path}. Run `prepare` or `prepare-full` first.")
        return 1
    with open(plan_path, "r", encoding="utf-8") as f:
        plan = json.load(f)

    mode = plan.get("mode", "b")
    lines = read_captions(plan["sentence_srt"])
    frags = read_captions(plan["fragments_srt"])
    assignments = assign_fragments(lines, frags)
    stream, _ = build_global_stream(lines, assignments, frags)

    parts_dir = os.path.join(workdir, "refine_parts")
    missing_parts = []
    for part in plan.get("parts", []):
        rname = part["file"].replace("refine_part_", "refined_")
        if not os.path.exists(os.path.join(parts_dir, rname)):
            missing_parts.append(rname)

    problems: list[str] = []
    if missing_parts:
        problems.append(f"missing refined files: {missing_parts}")

    overlong_set = set(plan.get("overlong", []))

    if mode == "full-boundaries":
        decisions: list[tuple[int, str]] = []
        seen: set[int] = set()
        for part in plan.get("parts", []):
            rname = part["file"].replace("refine_part_", "refined_")
            rpath = os.path.join(parts_dir, rname)
            if not os.path.exists(rpath):
                continue
            lo = int(part["commit_start_word"])
            hi = int(part["commit_end_word"])
            part_decisions = parse_boundary_decisions(rpath)
            if not part_decisions:
                problems.append(f"full boundary mode: no decisions in {rname}")
                continue
            for word_id, punct in part_decisions:
                if not lo <= word_id <= hi:
                    problems.append(
                        f"{rname}: W{word_id:06d} outside commit range "
                        f"W{lo:06d}-W{hi:06d}")
                    continue
                if word_id in seen:
                    problems.append(f"duplicate boundary W{word_id:06d}")
                    continue
                seen.add(word_id)
                decisions.append((word_id, punct))

        decisions.sort()
        total_words = len(stream)
        if not decisions or decisions[-1][0] != total_words:
            got = "none" if not decisions else f"W{decisions[-1][0]:06d}"
            problems.append(f"final boundary must be W{total_words:06d}; got {got}")
        texts: list[str] = []
        prev = 0
        for word_id, punct in decisions:
            if word_id <= prev or word_id > total_words:
                problems.append(f"invalid/non-increasing boundary W{word_id:06d}")
                continue
            span = word_id - prev
            if span > max(plan.get("max_words", 16) * 2, 32):
                problems.append(
                    f"sentence ending W{word_id:06d} spans {span} words; "
                    "likely a missing boundary")
            text = _sentence_from_stream(stream, prev, word_id, punct)
            if text:
                texts.append(text)
            prev = word_id
    elif mode == "full":
        # full mode: every refined_NN.txt numbers its sentences S<seq> from 1,
        # so they MUST be read per part (in part order), never merged into one
        # dict (seq keys would collide and later parts would overwrite earlier).
        texts: list[str] = []
        for part in plan.get("parts", []):
            rname = part["file"].replace("refine_part_", "refined_")
            rpath = os.path.join(parts_dir, rname)
            if not os.path.exists(rpath):
                continue
            seq_map: dict[int, list[str]] = {}
            for key, text in parse_refined(rpath):
                seq = _seq_key(key)
                if seq >= 1:
                    seq_map.setdefault(seq, []).append(text)
            if not seq_map:
                problems.append(f"full mode: no sentences in {rname}")
                continue
            n_seq = max(seq_map)
            missing_seq = [k for k in range(1, n_seq + 1) if k not in seq_map]
            if missing_seq:
                problems.append(f"full mode {rname}: missing seq {missing_seq}")
            for seq in sorted(seq_map):
                texts.extend(seq_map[seq])
    else:
        refined_raw: list[tuple[str, str]] = []
        for part in plan.get("parts", []):
            rname = part["file"].replace("refine_part_", "refined_")
            rpath = os.path.join(parts_dir, rname)
            if os.path.exists(rpath):
                refined_raw.extend(parse_refined(rpath))
        refined = {}
        for key, text in refined_raw:
            try:
                idx = int(key)
            except ValueError:
                continue
            refined.setdefault(idx, []).append(text)
        got = set(refined.keys())
        not_refined = sorted(overlong_set - got)
        extra = sorted(got - overlong_set)
        if not_refined:
            problems.append(f"over-long lines with no refined output: {not_refined}")
        if extra:
            problems.append(f"refined output for non-over-long lines: {extra}")
        texts, _ = build_sentence_texts("b", lines, overlong_set, refined)

    if not texts:
        problems.append("no sentences to emit")

    # global greedy match + anchor. Boundary-index mode reconstructs text from
    # the exact source stream, so matching is deterministic and unmatched=0.
    n_stream = len(stream)
    frag_starts = _frag_word_starts(stream)
    anchored: list[tuple[int, int, str]] = []
    pos = 0
    total_unmatched = 0
    for text in texts:
        words = text.split()  # SAME tokenization as the word stream (whitespace)
        if not words:
            continue
        if pos >= n_stream:
            # nothing left to anchor to — append with a degenerate window
            # (END is assigned in the pass below, so use the previous START)
            prev_start = anchored[-1][0] if anchored else 0
            anchored.append((prev_start, None, text.strip()))
            total_unmatched += len(words)
            continue
        start = _refined_start(stream, frags, frag_starts, pos)
        if mode == "full-boundaries":
            end_pos = min(pos + len(words), n_stream)
            unmatched = 0
        else:
            end_pos, unmatched = match_sentence(words, stream, pos)
        total_unmatched += unmatched
        if end_pos <= pos:  # nothing consumed (all reworded) — take word-count fallback
            end_pos = min(pos + len(words), n_stream)
            if end_pos <= pos:
                end_pos = pos + 1
        anchored.append((start, None, text.strip()))
        pos = end_pos

    if pos < n_stream and pos > 0:
        consumed = pos / n_stream
        if consumed < 0.9:
            problems.append(
                f"only {consumed:.0%} of source words consumed by sentences "
                f"({pos}/{n_stream}); sentences may be missing")

    if problems:
        log("VALIDATION PROBLEMS:")
        for p in problems[:40]:
            log(f"  - {p}")
        if len(problems) > 40:
            log(f"  ... and {len(problems) - 40} more")
        return 2

    # END = next START (de-overlap); last = stream end (or +2s for final line)
    if anchored:
        if n_stream:
            last_frag = stream[-1][1]
            stream_end = frags[last_frag][1] + 2000
        else:
            stream_end = lines[-1][1] if lines else 0
        for i in range(len(anchored) - 1):
            s, _, t = anchored[i]
            nxt_s = anchored[i + 1][0]
            if nxt_s <= s:
                nxt_s = s + 500
            anchored[i] = (s, nxt_s, t)
        s, _, t = anchored[-1]
        anchored[-1] = (s, max(stream_end, s + 500), t)

    # de-overlap global pass (defensive; also re-clip any line past its next START)
    for i in range(len(anchored) - 1):
        s, e, t = anchored[i]
        nxt_s = anchored[i + 1][0]
        if e > nxt_s:
            if nxt_s > s:
                anchored[i] = (s, nxt_s, t)
            else:
                anchored[i] = (s, s + 500, t)

    out_path = os.path.join(workdir, args.out)
    out = []
    for k, (s, e, t) in enumerate(anchored, start=1):
        out.append(f"{k}\n{fmt_srt_time(s)} --> {fmt_srt_time(e)}\n{t}\n")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")

    wc = [len(t.split()) for _, _, t in anchored]
    log(f"Wrote {len(anchored)} lines -> {out_path}")
    log(f"Stats: source {len(lines)} lines, {n_stream} words -> {len(anchored)} "
        f"lines; max words {max(wc) if wc else 0}; "
        f"unmatched sentence words {total_unmatched}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("sentence", help="sentence-level SRT from aggregate_srt.py")
    p_prep.add_argument("fragments", help="raw rolling-window ASR SRT")
    p_prep.add_argument("--workdir", default=".")
    p_prep.add_argument("--max-words", type=int, default=16,
                        help="re-split lines above this many words (default 16)")
    p_prep.add_argument("--max-dur-ms", type=int, default=6000,
                        help="re-split lines above this duration in ms (default 6000)")
    p_prep.add_argument("--lines-per-part", type=int, default=30,
                        help="max over-long lines per instruction chunk (default 30)")
    p_prep.add_argument("--context-lines", type=int, default=2,
                        help="tail lines of source shown as PREVIOUS CHUNK (default 2)")
    p_prep.add_argument("--manifest", default=None)
    p_prep.add_argument("--out", default="transcript_refined.srt")
    p_prep.set_defaults(func=cmd_prepare, mode="b")

    p_full = sub.add_parser("prepare-full")
    p_full.add_argument("sentence", help="sentence-level SRT from aggregate_srt.py")
    p_full.add_argument("fragments", help="raw rolling-window ASR SRT")
    p_full.add_argument("--workdir", default=".")
    p_full.add_argument("--max-words", type=int, default=16,
                        help="target cap words per sentence (default 16)")
    p_full.add_argument("--words-per-part", type=int, default=1200,
                        help="committed source words per instruction chunk (default 1200)")
    p_full.add_argument("--overlap-words", type=int, default=48,
                        help="read-only word context on both chunk sides (default 48)")
    p_full.add_argument("--lines-per-part", type=int, default=None,
                        help=argparse.SUPPRESS)
    p_full.add_argument("--context-lines", type=int, default=2,
                        help="tail lines of source shown as PREVIOUS CHUNK (default 2)")
    p_full.add_argument("--manifest", default=None)
    p_full.add_argument("--out", default="transcript_refined.srt")
    p_full.set_defaults(func=cmd_prepare_full, mode="full")

    p_ap = sub.add_parser("apply")
    p_ap.add_argument("--workdir", default=".")
    p_ap.add_argument("--out", default="transcript_refined.srt")
    p_ap.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    if getattr(args, "manifest", None) is None:
        args.manifest = os.path.join(args.workdir, "manifest.json")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
