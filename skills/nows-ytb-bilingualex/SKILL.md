---
name: nows-ytb-bilingualex
description: "This skill should be used when the user gives a YouTube video URL and wants (1) the video downloaded as an MP4 file and (2) a bilingual English || Chinese .ass subtitle file for that video. It downloads the ORIGINAL-language subtitle (preferring the creator's manual captions, falling back to YouTube's auto-generated ASR — never YouTube's machine translation), translates it into natural, context-aware, voice-synthesis-ready Chinese using the Agent's built-in model, and assembles a line-by-line bilingual .ass that keeps the original timestamps. It reuses the browser login session (Chrome cookies) so member-only / age-restricted videos can still be fetched. Do not use for plain subtitle translation of files the user already has — use youtube-subtitle-cleaner for cleaning messy .ass files."
agent_created: true
---

# YouTube MP4 + Bilingual ASS

Turn a YouTube URL into two deliverables:
1. **MP4** — the video, at a quality the user chooses interactively.
2. **Bilingual .ass subtitle** — every Dialogue line is `English || Chinese`,
   timestamps taken verbatim from the original subtitle track. The .ass file is
   written with the **same base name as the MP4** (e.g. `Talk.mp4` → `Talk.ass`)
   so the pair stays matched in a media library.

The pipeline is deliberately scripted end-to-end so no step requires
exploration: environment setup, auth reuse, downloading, parsing, splitting,
assembly, and validation are all deterministic scripts. The only step that uses
the Agent's own intelligence is the translation itself.

## When to use

- User pastes a YouTube URL and asks for the video file (MP4), with or without
  subtitles.
- User asks for bilingual (EN || ZH) subtitles for a YouTube video / interview /
  talk / lecture.
- User wants the Chinese translation to sound natural and to be suitable for
  Chinese voice synthesis (配音), not machine-translated.

## Workflow (run in order)

Work in a dedicated working directory (e.g. create one per video). All paths
below are relative to that directory. Run scripts with the managed Python
interpreter. Every script prints progress to stderr/stdout — read it before
continuing.

### Step 0 — Environment check (once per machine)

```bash
python3 <skill>/scripts/check_env.py --env-out yt_env.json
```

Installs `yt-dlp` (into an isolated venv if not on PATH) and ensures `ffmpeg`
exists (for merging video+audio). Writes `yt_env.json` used by later scripts.
If it exits non-zero, resolve the missing binary (hints are printed) before
proceeding.

**CDP prerequisite (one-time setup):** fetching the official transcript drives
your REAL Chrome over the DevTools protocol (CDP) — this is what carries your
YouTube login state and avoids the "confirm you are not a robot" wall that
blocks headless automation on popular videos. The one-time setup:

1. In your Chrome, open `chrome://inspect/#remote-debugging`.
2. Check **"Allow remote debugging for this browser instance"** (may require a
   browser restart; a confirmation dialog may pop up when the proxy connects —
   click **Allow**).
3. You must be logged into YouTube in that Chrome (the video must be watchable
   in your browser without a login wall).

The bundled `scripts/check-deps.sh` verifies the debugging port and the bundled
`scripts/cdp-proxy.mjs` (Node 22+, native WebSocket, no npm deps) provides the
HTTP API. `fetch_transcript.py` starts/attaches the proxy automatically. The
proxy keeps running on `127.0.0.1:3456` so later runs reuse it.

### Step 1 — Ask the user for video quality (interactive)

Before downloading, ask the user which quality they want. Present real options,
e.g.:

- **最高质量** (best available)
- **1080p**
- **720p**
- **480p**
- custom height

Map the answer to `--quality best|1080p|720p|480p|<height>`. Default to **best**
if the user has no preference. For long interviews/talks where file size matters,
recommend 720p.

### Step 2 — Download MP4 + original subtitle

```bash
python3 <skill>/scripts/download.py \
    --url "<youtube_url>" \
    --quality best \
    --cookies-browser chrome \
    --lang en \
    --output . \
    --env-out yt_env.json
```

**Subtitle source policy — official transcript only, no fallback:**
The bilingual subtitle MUST be built from YouTube's official **transcript
(转写文稿)** — the server-side sentence-aggregated version shown in the video
page's "Show transcript" panel. YouTube's transcript segments are complete
sentences with non-overlapping timestamps (each segment's start is the true
speech onset, aligned to the audio). Do NOT fall back to yt-dlp's raw caption
download: yt-dlp fetches the pre-aggregation rolling-window captions, which are
fragmented half-sentences with ~98% overlapping windows — they look wrong in
any ASS renderer and break lip-sync perception.

Fetch the transcript with the bundled script. It drives the user's real Chrome
through the bundled CDP proxy (no agent-browser, no external services):

```bash
python3 <skill>/scripts/fetch_transcript.py \
    --url "<youtube_url>" \
    --out transcript_official.srt
```

What it does, automatically:
- Ensures the CDP proxy (`scripts/cdp-proxy.mjs`) is connected to the user's
  Chrome (exits `2` with setup hints if remote debugging isn't enabled).
- Opens the video page in a **background tab** (the user's own tabs are never
  touched), expands the description, clicks "内容转文字" (Show transcript),
  waits for the panel to render, reads its innerText, and writes an SRT
  (segment end = next segment start; last segment +3s).
- Parses the panel text with an English + monotonic-timestamp filter, which
  drops the recommended-video noise appended at the bottom.
- Closes the background tab when done.

If the script exits `2` (CDP not ready), give the user the one-time setup
instructions from Step 0. If it exits `1` (transcript not retrievable) and a
"confirm you are not a robot" wall appears, make sure the user is logged into
YouTube in Chrome, then retry. **Never silently fall back to raw captions.**

Then download the MP4 at the chosen quality:

```bash
python3 <skill>/scripts/download.py \
    --url "<youtube_url>" \
    --quality best \
    --cookies-browser chrome \
    --lang en \
    --output . \
    --env-out yt_env.json
```

`download.py` now downloads the video **only** (no subtitle track): it probes
metadata via `yt-dlp -J` for the title, downloads the MP4 merged at the chosen
quality using `--cookies-from-browser chrome` (auth reuse for member-only /
age-restricted videos), and writes `manifest.json` (title, paths) for later
steps. If the MP4 download fails, surface the yt-dlp error.

### Step 3 — Parse subtitle into a translation work file

```bash
python3 <skill>/scripts/split_translation.py "transcript_official.srt" \
    --lines-per-part 70 --out .
```

Reads the transcript-derived SRT (`.ass` and `.srt` both accepted), strips
ASS override tags, and writes:

- `transcript.txt` — every event on one line: `<idx>\t<start>\t<end>\t<EN>`
- `parts/part_01.txt …` — chunks of ≤120 lines each, **each chunk carrying a
  context header**:
  - `GLOBAL CONTEXT` — the video title / URL / duration / subtitle source
    (read from `manifest.json`), so every chunk is translated with the full
    picture in mind;
  - `PREVIOUS CHUNK` — the last 4 lines of the previous chunk (configurable via
    `--context-lines`, set `0` to disable), so boundary sentences keep their
    continuity. All context lines are prefixed with `#` and are reference-only.
- `parts/manifest.json` — chunk bookkeeping
- `subtitle_meta.json` — original header + events

Adjust `--lines-per-part` for very long videos (smaller chunks = more reliable
translation, more passes).

### Step 4 — Translate with the Agent's built-in model

This is the only intelligence step and it is deliberately model-agnostic: any
Agent with any built-in model can execute it.

For each chunk `parts/part_NN.txt` (sequential, or parallel with separate
subagents when available):

1. Read the instructions in `<skill>/references/translation_prompt.md`.
2. **Read the chunk's context header first** (GLOBAL CONTEXT + PREVIOUS CHUNK)
   — it gives the video topic and the preceding lines for continuity; then
   translate the chunk, honoring **every** rule there — especially:
   - Natural, idiomatic Chinese; **never word-for-word**; resolve pronouns and
     ellipsis from context.
   - Suitable for **Chinese voice synthesis**: complete, spoken-style sentences,
     no translation-ese, length matched to the on-screen time.
   - Keep `<idx>`, `<start>`, `<end>` byte-identical; **never touch timestamps**.
   - Same number of output lines as input; 1:1 mapping.
   - Never translate or echo the `#` context lines.
3. Write the result to `parts/trans_NN.txt` in format
   `<idx>\t<start>\t<end>\t<corrected EN>\t<ZH>` (UTF-8).

The translation prompt includes the user's exact reference example:

```
142	0:47:27.84	0:47:35.75	self-esteem the pretense of self-advocacy and self-respect soon we'll be able to measure that much	自尊——自我主张与自我尊重的伪装。很快我们就能更客观地衡量它了
```

When translating, always read the whole chunk first, keep the video title and
topic in mind for context, and treat the chunk as continuous speech.

### Step 5 — Assemble the bilingual .ass

```bash
python3 <skill>/scripts/assemble_final.py --workdir .
```

Rebuilds the `.ass` with `Text = "EN || ZH"` per line, reusing the original
timestamps. **The output filename automatically matches the MP4's base name**
(read from `manifest.json`): if the video is `Talk.mp4`, the subtitle is written
as `Talk.ass`. Use `--out <name>` to override. Runs validation and **exits
non-zero if anything is wrong**
(missing chunk, line-count mismatch, duplicate/missing idx, `||` inside a
language field, tab inside text, bad timestamps, or a timestamp that was
changed vs. the source — verified against `subtitle_meta.json`). Never deliver a
file this step rejects.

> Note on overlap: YouTube ASR subtitles are a rolling window where adjacent
> lines naturally overlap by 1–2s. **This overlap is normal and must be kept**:
> the start timestamps ARE aligned to the audio (verified empirically — audio
> speech onset 16.318s vs. first caption start 16.32s). Pushing starts forward
> to remove overlap breaks lip-sync, so the validator checks timestamp
> *inheritance* (identical to source) and never enforces monotonicity.

### Step 5.5 — (Rare) fix lines with no visible window

Almost never needed. A line whose whole window lies inside the previous line's
(`end <= previous end`) would show for 0 seconds in a player. Only that case is
fixed, by extending the END forward (start is NEVER touched):

```bash
python3 <skill>/scripts/deoverlap.py "<X>.ass" --min-duration 0.5
```

Do NOT use this to "remove overlap" — de-overlapping breaks lip-sync. Run only
if the user reports missing/blinking subtitle lines, and always keep starts
intact.

### Step 6 — Deliver

Present to the user:

- the MP4 file
- the bilingual `.ass` file
- `manifest.json` summary (title, quality, subtitle source kind)

Tell the user where the files are. If the subtitle came from ASR, mention that
minor recognition errors were corrected during translation (the corrected
English is in the `.ass`).

## Key invariants (do not break)

- **Timestamps are inherited, never recomputed.** The pipeline only reads the
  source timeline and re-emits it. Alignment with the audio is guaranteed by
  construction.
- **Delimiter is ` || `** (space-pipe-pipe-space). It must not appear inside
  either language field. Default ASS style: Noto Sans CJK SC, size 52.
- **Source subtitle is YouTube's official transcript** (sentence-aggregated,
  non-overlapping), never yt-dlp's raw rolling-window captions. Do not "fix"
  overlap — the transcript has none, and pushing starts on raw captions breaks
  lip-sync.
- **Translation is the Agent's job, mechanics are the scripts' job.** Do not
  hand-write parsing/assembly logic that already exists in `scripts/`.

## Resources

### scripts/
- `check_env.py` — probe/install yt-dlp + ffmpeg; write `yt_env.json`
- `check-deps.sh` — verify Chrome remote-debugging (DevToolsActivePort / 9222)
- `cdp-proxy.mjs` — bundled CDP proxy (Node 22+, native WebSocket, no npm deps);
  exposes HTTP API on `127.0.0.1:3456` to drive the user's real Chrome
- `fetch_transcript.py` — fetch YouTube's official transcript (转写文稿) via the
  bundled CDP proxy and write it as SRT (sentence-aggregated, non-overlapping)
- `download.py` — metadata probe, auth reuse, quality select, MP4 download only
- `split_translation.py` — parse SRT/ASS → transcript + chunks + manifest
- `assemble_final.py` — merge translated chunks → bilingual .ass + validation
- `deoverlap.py` — (rare) give windowless lines a minimum visible window; NEVER
  de-overlaps starts, so audio alignment is always preserved

### references/
- `translation_prompt.md` — full translation instructions for any Agent's
  built-in model (context-aware, TTS-ready Chinese, exact formats, worked example)
