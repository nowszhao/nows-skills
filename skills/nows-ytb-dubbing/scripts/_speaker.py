"""Context-based speaker inference for the speech units the voiceprint pass left open.

The Agent does the judging, always: nothing here picks a speaker by itself and no
human listening step exists. A segment that survives one round comes back in
forced mode, where a decision is mandatory.
"""
from __future__ import annotations

from _export import quality, validate_analysis
from _project import digest, read_json, write_json

CONFIDENCE = ("high", "medium", "low")
MAX_SEGMENTS = 40
MAX_CHARS = 6000
SIDE_UNITS = 3
SNIPPET = 220
FOLDER = ("language", "speaker")


def inferred_words(project):
    record = project.get("speaker_inference") or {}
    return [i for i in record.get("word_ids") or [] if type(i) is int]


def report(analysis, project=None):
    return quality(analysis, inferred_words(project or {}))


def catalog(analysis):
    return {word["word_id"]: word for word in analysis["words"]}


def pending_units(units, words):
    """A unit is open when every one of its words lacks a speaker.

    A unit that mixes identified and unknown speakers means the language layer
    disagrees with the analysis; it is reported rather than silently bound.
    """
    pending = []
    for unit in units:
        ids = unit.get("source_word_ids") or []
        missing = [i for i in ids if i not in words]
        if missing:
            raise ValueError("A speech unit references unknown source words; repair language/units.json")
        speakers = {words[i].get("speaker") for i in ids}
        if None not in speakers:
            continue
        if len(speakers) > 1:
            raise ValueError(
                "A speech unit mixes identified and unknown speakers; repair language/units.json"
            )
        pending.append(unit)
    return pending


def _snippet(text):
    return (text or "").strip()[:SNIPPET]


def _speaker_of(unit, words):
    ids = unit.get("source_word_ids") or []
    return words[ids[0]].get("speaker") if ids else None


def roster(analysis, units, allowed):
    """Every speaker with a qualified reference is a candidate, even if unused yet."""
    words = catalog(analysis)
    items = {
        speaker: dict(speaker_id=speaker, words=0, seconds=0.0, samples=[])
        for speaker in allowed
    }
    for word in analysis["words"]:
        speaker = word.get("speaker")
        if speaker not in items:
            continue
        items[speaker]["words"] += 1
        items[speaker]["seconds"] += word["end"] - word["start"]
    for unit in units:
        speaker = _speaker_of(unit, words)
        if speaker in items and len(items[speaker]["samples"]) < 3:
            sample = _snippet(unit.get("text_en"))
            if sample:
                items[speaker]["samples"].append(sample)
    for item in items.values():
        item["seconds"] = round(item["seconds"], 1)
    return [items[key] for key in sorted(items)]


def _candidates(unit, words):
    scores = {}
    for word_id in unit["source_word_ids"]:
        for item in words[word_id].get("speaker_candidates") or []:
            if isinstance(item, dict):
                speaker = item.get("speaker_id") or item.get("speaker") or item.get("id")
                score = item.get("score")
            else:
                speaker, score = item, None
            if not isinstance(speaker, str):
                continue
            score = score if isinstance(score, (int, float)) else None
            known = scores.get(speaker, "absent")
            if known == "absent":
                scores[speaker] = score
            elif score is not None and (known is None or score > known):
                scores[speaker] = score
    ordered = sorted(scores.items(), key=lambda kv: (-(kv[1] or 0.0), kv[0]))[:3]
    return [dict(speaker_id=speaker, score=score) for speaker, score in ordered]


def speech_text(unit, words):
    return " ".join(words[i]["text"] for i in unit["source_word_ids"])


def context(project):
    metadata = project.get("metadata") or {}
    chapters = metadata.get("chapters") or []
    return dict(
        title=(metadata.get("title") or "").strip()[:200],
        description=(metadata.get("description") or "").strip()[:1200],
        chapters=[
            dict(title=str(chapter.get("title", "")).strip()[:120], start=chapter.get("start"))
            for chapter in chapters[:30]
            if isinstance(chapter, dict)
        ],
    )


def _side(units, words):
    return [
        dict(speaker=_speaker_of(neighbour, words), text=_snippet(neighbour.get("text_en")))
        for neighbour in units
    ]


def build_request(analysis, units, project, pending, forced):
    words = catalog(analysis)
    allowed = set(analysis.get("references") or {})
    positions = {unit["unit_id"]: number for number, unit in enumerate(units)}
    segments, size = [], 0
    for unit in pending:
        if len(segments) >= MAX_SEGMENTS or size >= MAX_CHARS:
            break
        position = positions[unit["unit_id"]]
        segments.append(
            dict(
                segment_id=unit["unit_id"],
                start=round(words[unit["source_word_ids"][0]]["start"], 3),
                end=round(words[unit["source_word_ids"][-1]]["end"], 3),
                text_en=(unit.get("text_en") or "").strip(),
                text_zh=(unit.get("text_zh") or "").strip(),
                source_words=speech_text(unit, words),
                speaker_candidates=_candidates(unit, words),
                before=_side(units[max(0, position - SIDE_UNITS):position], words),
                after=_side(units[position + 1:position + 1 + SIDE_UNITS], words),
                word_ids=list(unit["source_word_ids"]),
            )
        )
        size += len(unit.get("text_en") or "") + len(unit.get("text_zh") or "")
    request = dict(
        stage="speaker_infer",
        mode="forced" if forced else "context",
        analysis_id=analysis["analysis_id"],
        context=context(project),
        speakers=roster(analysis, units, allowed),
        segments=segments,
        unresolved_total=len(pending),
        batch_size=len(segments),
    )
    request["input_id"] = digest(request)
    return request


def validate_decisions(request, response, allowed):
    if not isinstance(response, dict) or response.get("input_id") != request.get("input_id"):
        raise ValueError("Speaker output input_id differs from the current input")
    decisions = response.get("decisions")
    if not isinstance(decisions, list):
        raise ValueError("Speaker output requires a decisions list")
    segments = {segment["segment_id"]: segment for segment in request["segments"]}
    seen, resolutions = set(), []
    for item in decisions:
        if not isinstance(item, dict):
            raise ValueError("Each speaker decision must be an object")
        segment_id = item.get("segment_id")
        if segment_id not in segments:
            raise ValueError("Unknown segment_id in speaker decisions")
        if segment_id in seen:
            raise ValueError("A segment carries two decisions")
        speaker = item.get("speaker_id")
        if not isinstance(speaker, str) or speaker not in allowed:
            raise ValueError(
                "speaker_id must be an analysed speaker with a qualified reference"
            )
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Every decision needs a short context reason")
        confidence = item.get("confidence", "medium")
        if confidence not in CONFIDENCE:
            raise ValueError("confidence must be high, medium or low")
        seen.add(segment_id)
        resolutions.append(
            dict(
                segment_id=segment_id,
                word_ids=list(segments[segment_id]["word_ids"]),
                speaker_id=speaker,
                confidence=confidence,
                reason=reason.strip()[:400],
            )
        )
    if request.get("mode") == "forced":
        if response.get("unresolved"):
            raise ValueError(
                "Forced inference does not accept unresolved entries; decide every segment"
            )
        left = [item for item in segments if item not in seen]
        if left:
            raise ValueError(
                "Forced inference must decide every requested segment; still open: "
                + ", ".join(left[:8])
            )
        return resolutions
    notes = response.get("unresolved") or []
    if not isinstance(notes, list):
        raise ValueError("unresolved must be a list")
    for note in notes:
        if not isinstance(note, dict) or note.get("segment_id") not in segments:
            raise ValueError("unresolved entries must reference a requested segment_id")
        if not isinstance(note.get("why"), str) or not note["why"].strip():
            raise ValueError("Each unresolved entry needs a why string")
    return resolutions


def folder(work):
    path = work.joinpath(*FOLDER)
    path.mkdir(parents=True, exist_ok=True)
    return path


def merge_resolutions(resolutions, analysis):
    """Send whole server-side unresolved runs when their judgement is uniform.

    A resolved sub-range is accepted more often than a split one, so decided
    words are regrouped into the widest contiguous range with one speaker.
    """
    by_word = {}
    for item in resolutions:
        for word_id in item["word_ids"]:
            by_word[word_id] = item["speaker_id"]
    merged, consumed = [], set()
    for segment in analysis.get("unresolved_segments") or []:
        ids = [i for i in segment.get("word_ids") or [] if type(i) is int]
        if not ids or any(i not in by_word for i in ids):
            continue
        speakers = {by_word[i] for i in ids}
        if len(speakers) != 1:
            continue
        merged.append(dict(word_ids=sorted(ids), speaker_id=next(iter(speakers))))
        consumed.update(ids)
    run, previous = [], None
    for word_id in sorted(i for i in by_word if i not in consumed):
        speaker = by_word[word_id]
        if run and (speaker != previous or word_id != run[-1] + 1):
            merged.append(dict(word_ids=run, speaker_id=previous))
            run = []
        run.append(word_id)
        previous = speaker
    if run:
        merged.append(dict(word_ids=run, speaker_id=previous))
    merged.sort(key=lambda item: item["word_ids"][0])
    return merged


def apply(work, project, client, analysis):
    """Consume a written response, bind it on the server, keep a local receipt."""
    place = folder(work)
    response = read_json(place / "output.json")
    if response is None:
        return analysis
    request = read_json(place / "input.json") or {}
    if response.get("input_id") != request.get("input_id"):
        (place / "output.json").unlink(missing_ok=True)
        return analysis
    words = catalog(analysis)
    allowed = set(analysis.get("references") or {})
    resolutions = validate_decisions(request, response, allowed)
    live = [
        item
        for item in resolutions
        if all(not words[i].get("speaker") for i in item["word_ids"])
    ]
    gate = project.get("speaker_gate") or {}
    if not live:
        # An answer that binds nothing sends the same segments back as forced.
        (place / "output.json").unlink(missing_ok=True)
        project["speaker_gate"] = dict(
            gate, analysis_id=analysis["analysis_id"], stalled=True
        )
        return analysis
    target = place / "resolutions.json"
    write_json(target, merge_resolutions(live, analysis))
    try:
        revised = client.call(
            "video",
            "confirm-speakers",
            "--analysis-id",
            analysis["analysis_id"],
            "--resolutions",
            target,
        )
    except ValueError as error:
        raise ValueError(f"Server rejected the inferred speaker binding: {error}") from error
    updated = revised.get("analysis")
    validate_analysis(updated, analysis["source_media_sha256"])
    if updated["analysis_id"] != analysis["analysis_id"]:
        raise ValueError("Speaker confirmation returned a different analysis")
    unbound = [
        word_id
        for item in live
        for word_id in item["word_ids"]
        if not updated["words"][word_id].get("speaker")
    ]
    if unbound:
        raise ValueError(
            "Server confirmed the request but left source words unbound; inspect the analysis before retrying"
        )
    (place / "output.json").unlink(missing_ok=True)
    write_json(work / "analysis.json", updated)
    ledger = project.setdefault(
        "speaker_inference",
        dict(analysis_id=analysis["analysis_id"], decisions=[], word_ids=[]),
    )
    if ledger.get("analysis_id") != analysis["analysis_id"]:
        ledger.update(analysis_id=analysis["analysis_id"], decisions=[], word_ids=[])
    for item in live:
        ledger["word_ids"] = sorted(set(ledger["word_ids"]) | set(item["word_ids"]))
        ledger["decisions"].append(
            dict(
                segment_id=item["segment_id"],
                speaker_id=item["speaker_id"],
                confidence=item["confidence"],
                reason=item["reason"],
                word_ids=item["word_ids"],
            )
        )
    write_json(
        work / "output" / "speaker_inference.json",
        dict(
            analysis_id=analysis["analysis_id"],
            source="model_context_inference",
            mode=request.get("mode", "context"),
            note="Context-inferred binding; not acoustically verified.",
            decisions=ledger["decisions"],
            low_confidence=[
                dict(segment_id=item["segment_id"], reason=item["reason"])
                for item in ledger["decisions"]
                if item["confidence"] == "low"
            ],
        ),
    )
    # Keep the asked set: a segment that survived a round comes back as forced.
    if gate.get("analysis_id") != analysis["analysis_id"]:
        gate = {}
    project["speaker_gate"] = dict(gate, analysis_id=analysis["analysis_id"], stalled=False)
    return updated


def stage(work, project, analysis):
    """Return the next Agent action while a speaker is still unknown."""
    current = report(analysis, project)
    units = read_json(work / "language" / "units.json", [])
    pending = pending_units(units, catalog(analysis))
    if current["missing_reference_speakers"]:
        return dict(
            stage="reference_missing",
            action="inspect_missing_reference",
            missing_reference_speakers=current["missing_reference_speakers"],
            message="Some speakers have no qualified reference; the dub cannot clone them",
            quality=current,
            instructions="references/operations.md#speakers",
        )
    if not pending:
        return dict(
            stage="analysis_not_ready",
            action="inspect_analysis",
            message="Every word has a speaker and a reference, but the server does not mark this analysis dubbing-ready",
            quality=current,
            instructions="references/operations.md#recovery",
        )
    gate = project.get("speaker_gate") or {}
    if gate.get("analysis_id") != analysis["analysis_id"]:
        gate = {}
    asked = set(gate.get("asked") or [])
    # A segment that already came back once must now be decided.
    forced = bool(gate.get("stalled")) or any(unit["unit_id"] in asked for unit in pending)
    request = build_request(analysis, units, project, pending, forced)
    place = folder(work)
    input_path, output_path = place / "input.json", place / "output.json"
    if (read_json(input_path) or {}).get("input_id") != request["input_id"]:
        output_path.unlink(missing_ok=True)
    write_json(input_path, request)
    project["speaker_gate"] = dict(
        analysis_id=analysis["analysis_id"],
        stalled=False,
        asked=sorted(asked | {segment["segment_id"] for segment in request["segments"]}),
        pending=len(pending),
    )
    return dict(
        stage="speaker_infer",
        action="agent_infer",
        mode=request["mode"],
        input=str(input_path),
        output=str(output_path),
        input_id=request["input_id"],
        instructions="references/speakers.md",
        segments=len(request["segments"]),
        unresolved_total=len(pending),
        quality=current,
    )
