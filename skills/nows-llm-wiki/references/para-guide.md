# PARA Adaptation Guide

PARA (Tiago Forte) organizes notes by **actionability**, not by topic. It has four buckets, ordered by time-to-action:

| Bucket | Definition | Examples |
|---|---|---|
| **Projects** | Short-term effort with a clear goal and deadline | "Ship v5.3.2", "Write Q2 review", "Trip to Kyoto" |
| **Areas** | Ongoing responsibility without a deadline | "Health", "Team leadership", "Investing" |
| **Resources** | Topics of interest, reference material | "Rust patterns", "prompt library", "tax templates" |
| **Archive** | Anything inactive from the other three | Completed projects, dropped areas |

## PARA + LLM Wiki: who owns what

| Layer | Owner | Lives in |
|---|---|---|
| PARA Projects / Areas / Resources / Archive | **Human** | `01-Projects/`, `02-Areas/`, `03-Resources/`, `04-Archive/` |
| LLM Wiki raw sources | Human drops them, LLM only adds frontmatter | `00-Inbox/raw/` |
| LLM Wiki synthesis (concepts/entities/synthesis/MOCs) | **LLM** | `wiki/` |
| Schema / conventions | Co-edited | `<vault>/CLAUDE.md` |

This preserves PARA's principle (humans organize by actionability) while granting the LLM a dedicated compounding layer for knowledge.

## Decision tree: where does a note belong?

```
Is this note an active, deadline-bound effort you're working on?
├─ Yes → 01-Projects/<project-name>/
└─ No → continue

Is this an ongoing responsibility you maintain indefinitely?
├─ Yes → 02-Areas/<area-name>/
└─ No → continue

Is this a captured external artifact (web clip, paper, transcript, research note)?
├─ Yes → 00-Inbox/raw/<clippings|research|transcripts|...>/
│         (participates in wiki ingestion)
└─ No → continue

Is this a reusable reference (template, tool guide, checklist)?
├─ Yes → 03-Resources/<topic>/
└─ No → continue

Was this once active but is now inactive?
├─ Yes → 04-Archive/
└─ No → mark "uncertain" in migration plan, ask user
```

## Common ambiguities & resolutions

- **A "research note" that's also for a project.** → Put the raw capture in `00-Inbox/raw/research/`, create a short pointer in the relevant `01-Projects/<proj>/` page that wiki-links to it. Raw stays in raw.
- **An ongoing hobby (e.g., playing guitar).** → `02-Areas/guitar/` (ongoing responsibility for your own growth).
- **A one-off tutorial bookmarked for later.** → `03-Resources/` unless it clearly drives a project → then link from the project page.
- **Daily journal.** → A separate top-level `Daily Note/` folder, NOT inside PARA. Not ingested.
- **Meeting notes for a project.** → Live under the project folder. Do not copy into `raw/`.
- **A MOC the human curates manually (not LLM-generated).** → `02-Areas/<area>/` — it's an ongoing curation responsibility. LLM-generated MOCs live in `wiki/moc/`.

## PARA boundary rules (important)

1. **`01-Projects/` never feeds wiki ingestion.** Active project docs churn daily and would pollute wiki invariants. Project outputs that should become wiki material get **moved** to `00-Inbox/raw/` when the project ends.
2. **`04-Archive/` is ingestable if the user explicitly adds items to `00-Inbox/raw/`.** Archiving doesn't automatically promote content into the wiki.
3. **`02-Areas/` is partially ingestable.** Stable artifacts (e.g., a career philosophy page) can be cited by wiki pages as sources, but the wiki does not rewrite them. Treat them like "sticky raw" — LLM reads but never modifies.
4. **Renumbering is allowed.** Some users prefer `Inbox/`, `Projects/`, `Areas/`, `Resources/`, `Archive/` without numeric prefixes. Both are fine — record the choice in `CLAUDE.md`.

## Weekly review (PARA's heartbeat)

Run `scripts/weekly_review.py <vault>` once a week. It surfaces:

- **Inbox aging**: items in `00-Inbox/` (excluding `raw/`) older than 7 days — capture that wasn't processed.
- **Stale projects**: `01-Projects/*/` with no file modification in 14 days — candidates for archive or reactivation.
- **Neglected areas**: `02-Areas/*/` untouched in 90 days — review the responsibility scope.
- **Archive growth**: diff vs last review.
- **Wiki follow-ups**: Gaps logged in concept pages older than 30 days.

The weekly review document is written to `00-Inbox/reviews/YYYY-MM-DD.md`, NOT committed automatically — the human reads, decides, acts.

## Sizing heuristics

- **Projects**: expect 5–20 active at most. Large fan-out → some should be Areas.
- **Areas**: 5–15. Large fan-out → some are really Projects (have a deadline) or Resources (no responsibility).
- **Resources**: open-ended; reviewed during weekly review.
- **Archive**: monotonically grows. No effort to prune unless storage matters.

## Integration with tags

PARA is the **primary classification** (via folder). Tags are a **secondary** index that cuts across PARA buckets. Example: tag `#db` can appear in both `01-Projects/tbds-insight/` and `03-Resources/postgres-cheatsheet.md`. Keep tags flat (no hierarchies) — the domain axis is already captured by wiki MOCs.
