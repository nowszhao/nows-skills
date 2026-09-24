---
name: nows-ytb-bilingualex
description: "Download a YouTube video as MP4 and create aligned English || Chinese ASS and SRT subtitles from YouTube's official English ASR. Use for YouTube URLs requiring natural, context-aware, TTS-ready Chinese. Do not use for translating an existing local subtitle file."
---

# YouTube MP4 + bilingual subtitles

Produce a matched `.mp4`, bilingual `.ass`, and bilingual `.srt`. Subtitle text is
`English || Chinese`; Chinese must be natural, context-aware, and suitable for TTS.

Use a dedicated directory per video. Scripts own parsing, IDs, timestamps,
assembly, and validation. Models only decide semantic sentence boundaries and
translate text.

## Quality invariants

- Source: YouTube official English auto-ASR, not YouTube machine translation.
- FULL semantic re-segmentation is the default; do not downgrade to mode B merely for speed.
- Source words remain in their original order during FULL re-segmentation.
- Timestamps are generated from canonical subtitle metadata, never authored by a translation worker.
- Output is line-aligned and non-overlapping, with delimiter ` || `.
- Chinese is idiomatic, terminology-consistent, and TTS-safe; remove stage directions.

## 1. Environment and quality

Ask the user for `best-vp9`, `best`, `best-av1`, `1080p`, `720p`, `480p`, or a
height. Use `best-vp9` when the user asks for the highest practical quality.

```bash
python3 <skill>/scripts/check_env.py --env-out yt_env.json
python3 <skill>/scripts/pipeline_metrics.py start --stage download --workdir .
```

`check_env.py` reuses a valid existing environment and installs only missing tools.

## 2. Download and acquire ASR concurrently

Start MP4 download in a persistent background execution, then immediately fetch ASR:

```bash
python3 <skill>/scripts/download.py \
  --url "<youtube_url>" --quality best-vp9 \
  --cookies-browser chrome --output . --env-out yt_env.json
```

The downloader defaults to `mweb`, resumable native yt-dlp fragments, four fragment
connections, and live progress. Do not start a second download while this process is healthy.
When the background process finishes successfully, record it:

```bash
python3 <skill>/scripts/pipeline_metrics.py end --stage download --workdir .
```

In parallel:

```bash
<yt-dlp> --write-auto-subs --sub-langs "en" --sub-format srt \
  --convert-subs srt --skip-download --cookies-from-browser chrome \
  --extractor-args "youtube:player_client=web_embedded" \
  -o "raw_asr.%(ext)s" "<youtube_url>"

python3 <skill>/scripts/aggregate_srt.py raw_asr.en.srt transcript_official.srt \
  --max-gap 700 --max-group 7500 --max-words 26
```

If acquisition or download fails, read [references/troubleshooting.md](references/troubleshooting.md).

## 3. FULL semantic re-segmentation

FULL now sends an annotated word stream to the model. Workers output only sentence-end
word IDs and punctuation, so they cannot delete, rewrite, or reorder source words.

```bash
python3 <skill>/scripts/pipeline_metrics.py start --stage refine --workdir .
python3 <skill>/scripts/refine_srt.py prepare-full \
  transcript_official.srt raw_asr.en.srt --workdir . \
  --words-per-part 1200 --overlap-words 48 --max-words 16
python3 <skill>/scripts/plan_workers.py --stage refine --workers 3 --workdir .
```

Create up to three long-lived workers, never more workers than chunks. Give each
worker the chunks listed for it in `refine_worker_plan.json`; the worker processes its files
sequentially. Each worker reads [references/refine_prompt_full.md](references/refine_prompt_full.md)
once and writes matching `refine_parts/refined_NN.txt` files.

Then validate and apply:

```bash
python3 <skill>/scripts/check_refined.py --workdir . --mode auto
python3 <skill>/scripts/refine_srt.py apply --workdir . --out transcript_refined.srt
python3 <skill>/scripts/pipeline_metrics.py end --stage refine --workdir .
```

Re-dispatch only a failed chunk. Mode B remains available through `refine_srt.py prepare`
only when the user explicitly requests faster, lower-boundary-quality output.

## 4. Translation

Split by English word budget, with a line-count safety cap:

```bash
python3 <skill>/scripts/pipeline_metrics.py start --stage translate --workdir .
python3 <skill>/scripts/split_translation.py transcript_refined.srt \
  --words-per-part 1100 --max-lines-per-part 80 --context-lines 4 --out .
python3 <skill>/scripts/plan_workers.py --stage translate --workers 3 --workdir .
```

Use up to three long-lived workers according to `translate_worker_plan.json`. Each worker reads
[references/translation_prompt.md](references/translation_prompt.md) once, then processes
its assigned files sequentially. For `part_NN.txt`, write `trans_NN.txt` as:

```text
<idx>\t<corrected English>\t<Chinese>
```

Do not ask workers to copy timestamps. The chunk's duration field is context only.

After all workers finish:

```bash
python3 <skill>/scripts/verify_translation.py --workdir .
python3 <skill>/scripts/pipeline_metrics.py end --stage translate --workdir .
```

Re-dispatch only chunks reported by validation.

## 5. Assemble and deliver

```bash
python3 <skill>/scripts/pipeline_metrics.py start --stage assemble --workdir .
python3 <skill>/scripts/assemble_final.py --workdir .
python3 <skill>/scripts/step55_derive_srt.py --workdir .
python3 <skill>/scripts/pipeline_metrics.py end --stage assemble --workdir .
python3 <skill>/scripts/pipeline_metrics.py report --workdir .
```

`assemble_final.py` injects canonical start/end times by idx. It accepts the new compact
three-field translation format and legacy five-field files. Never deliver files rejected
by assemble or final QA.

Ensure the MP4, ASS, and SRT share a basename. Report their paths, selected video quality,
ASR source, and the timing summary from `pipeline_metrics.py`.

## Resources

- `scripts/refine_srt.py`: indexed FULL boundary preparation and timestamp anchoring.
- `scripts/check_refined.py`: deterministic FULL boundary validation; legacy drift validation.
- `scripts/split_translation.py`: word-budget translation chunks with duration context.
- `scripts/plan_workers.py`: balanced three-worker assignment.
- `scripts/pipeline_metrics.py`: stage duration and retry counters.
- `scripts/verify_translation.py`: catches line/content shifts.
- `scripts/assemble_final.py`: injects canonical timestamps and creates ASS.
- `scripts/step55_derive_srt.py`: TTS cleaning, SRT derivation, final QA.
- `references/refine_prompt_full.md`: compact FULL boundary-worker contract.
- `references/translation_prompt.md`: high-quality translation-worker contract.
- `references/troubleshooting.md`: failure-only download and recovery guidance.
