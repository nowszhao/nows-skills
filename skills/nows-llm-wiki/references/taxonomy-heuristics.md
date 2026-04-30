# Taxonomy Heuristics (PARA + LLM Wiki)

Rules for deciding where an existing note belongs in the hybrid model. Two orthogonal decisions must be made for every note:

1. **PARA bucket** — Projects / Areas / Resources / Archive / Inbox (or Daily Note)
2. **LLM Wiki role** — raw source / wiki page / ignored

Most notes belong to exactly one PARA bucket AND zero-or-one wiki role (most are "ignored" from the wiki perspective — that's fine).

---

## Decision tree A — PARA bucket

```
Is this a daily journal entry (dated filename)?
├─ Yes → Daily Note/
└─ No → continue

Is this an active, deadline-bound effort you're currently working on?
├─ Yes → 01-Projects/<project-name>/
└─ No → continue

Is this an ongoing responsibility (no deadline, maintained indefinitely)?
├─ Yes → 02-Areas/<area-name>/
└─ No → continue

Is this a captured external artifact (web clip, paper, transcript, research report)?
├─ Yes → 00-Inbox/raw/<subkind>/     [also participates in wiki ingestion]
└─ No → continue

Is this a reusable reference (template, checklist, cheatsheet, tool guide)?
├─ Yes → 03-Resources/<topic>/
└─ No → continue

Was this once active but is now complete/abandoned?
├─ Yes → 04-Archive/
└─ No → stays in 00-Inbox/ (unprocessed) — flag in weekly review
```

## Decision tree B — LLM Wiki role

```
Is the note in 00-Inbox/raw/?
├─ Yes → role = raw source (add frontmatter, do NOT rewrite body)
└─ No → continue

Is the note in 01-Projects/?
├─ Yes → role = ignored (PARA boundary; wiki does not ingest active projects)
└─ No → continue

Is the note in 02-Areas/ AND represents a stable long-form artifact (e.g., a career manifesto)?
├─ Yes → role = "sticky raw" (wiki may cite it in sources: but does not rewrite it)
└─ No → continue

Is the note in 03-Resources/?
├─ Yes → role = ignored by default; user may opt specific notes in as "sticky raw"
└─ No → continue

Is the note in 04-Archive/?
├─ Yes → role = ignored by default; user may promote specific notes to 00-Inbox/raw/ for ingestion
└─ No → continue

Is the note in wiki/?
├─ Yes → role = LLM-owned wiki page (concept / entity / synthesis / MOC / index / log)
```

---

## Raw-source sub-classification (inside `00-Inbox/raw/`)

| Kind | Folder | Examples |
|---|---|---|
| `research/` | structured research notes, HV analyses, deep-dive reports, PRD-style writeups |
| `clippings/` | Obsidian Web Clipper output, articles grabbed from the web |
| `transcripts/` | meeting notes, podcast transcripts, interview notes |
| `papers/` | PDFs + companion note files for papers |
| `flash/` | excalidraw sketches, quick drafts not yet classifiable |

## Wiki-page sub-classification (inside `wiki/`)

| Page type | Folder | Criteria |
|---|---|---|
| `concept` | `wiki/concepts/` | A recurring idea / framework / technique cited across multiple sources |
| `entity` | `wiki/entities/` | A person / company / product / tool with its own identity |
| `synthesis` | `wiki/synthesis/` | Cross-concept analysis, comparison, timeline, overview |
| `moc` | `wiki/moc/` | Map-of-Content per domain, with Dataview queries |

---

## Tie-breakers

- A note that cites multiple sources and synthesizes them → **synthesis**, not concept.
- A note that captures a web article but has substantive user commentary → still **raw** (captured under `raw/clippings/`); separate the commentary into a wiki page if it deserves one.
- Zettelkasten-style atomic idea notes → **concept** (`wiki/concepts/`).
- Meeting notes for a specific project → live under the project's `01-Projects/<proj>/` folder. Do NOT copy into `raw/`.
- "Book notes" per chapter → `00-Inbox/raw/research/<book-slug>/`; characters/themes become **entity**/**concept** pages.
- A large LLM-generated report on a single topic → `00-Inbox/raw/research/` (it's raw material), NOT `wiki/synthesis/`. Syntheses are inside the wiki layer and tie ≥2 concepts together.

## Slug rules

- Lowercase, kebab-case, ASCII where possible, e.g. `value-at-risk.md`.
- **CJK titles are acceptable** when the user's vault is predominantly CJK (e.g., `声明式etl.md`). Record the choice in `CLAUDE.md`.
- Strip dates from filenames except in `Daily Note/` and HV reports that conventionally include dates.
- Deduplicate: if two notes would collapse to the same slug, append a disambiguator (`-company`, `-book`, `-2019`) chosen with the user.

## When to create a new entity/concept page (rule of three)

- A wikilink target referenced **≥3 times** across `00-Inbox/raw/` earns its own page.
- A tag applied to **≥10 notes** is a domain candidate → seed a MOC.
- User explicitly requests a page → always honor.
- During ingest: if a new source mentions a person/tool/idea not yet in the wiki, create a **stub** page with `status: stub` and a one-line body. Future ingests flesh it out.

## When NOT to create a page

- One-off mentions with no depth.
- Abbreviations that are aliases of existing entities → add as `aliases:` in the existing page's frontmatter.
- Transient project codenames — leave them in `01-Projects/`.

## Common miscategorizations & corrections

| Symptom | Likely cause | Fix |
|---|---|---|
| `01-Projects/` has many stale project folders | Projects completed but not archived | Move to `04-Archive/`; weekly review catches this |
| `03-Resources/` has captured web articles | Clippings went to Resources instead of `raw/clippings/` | Move to `00-Inbox/raw/clippings/` and re-run ingest |
| `wiki/concepts/` has notes with only 1 source | Premature page creation | Demote to `raw/research/` OR mark `status: stub` and wait for more sources |
| `02-Areas/` has no-op README stubs | Boilerplate left over from setup | Delete or fill with real content; don't carry dead weight |
| Many orphan pages in `wiki/` | Missing MOC or cross-references | Seed a MOC; run lint check #5 |
