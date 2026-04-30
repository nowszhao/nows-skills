---
name: nows-llm-wiki
description: "Reorganize an existing Obsidian vault into a PARA + Karpathy LLM Wiki hybrid: keep PARA (Projects/Areas/Resources/Archive) as the human-facing action layer, and nest an LLM Wiki layer (raw → wiki, concepts/entities/synthesis/MOCs) on top. Audit current notes, propose a migration plan, restructure in place (rename, move, add frontmatter, wikilinks), and generate derived wiki content — with contradiction tracking, query-compounding, and 8-item lint. Use when the user wants to tidy/refactor/整理 an Obsidian vault, adopt PARA+LLM Wiki, build MOCs/concept pages across a vault, or ingest existing notes into an LLM-maintained knowledge base."
agent_created: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Obsidian LLM Wiki — PARA + Karpathy Hybrid

Turn an existing Obsidian vault into a **PARA + Karpathy LLM Wiki hybrid** in place. PARA gives the human an action-space layout (Projects / Areas / Resources / Archive); LLM Wiki gives the LLM a knowledge-space layout (raw → wiki). They coexist in one vault: PARA is the outer skeleton, LLM Wiki is the nervous system.

> Based on [Andrej Karpathy's LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) and [Tiago Forte's PARA](https://fortelabs.com/blog/para/). This skill adapts both to an **existing** Obsidian vault and performs **in-place refactoring** rather than building from scratch.

## When this skill triggers

- "帮我整理一下我的 Obsidian vault / 笔记库"
- "把我的 vault 按 PARA + LLM Wiki 方式重组"
- "给我的 vault 生成 MOC / 索引 / 概念页"
- "清理 / 规范化 vault 的 frontmatter 和 wikilinks"
- "weekly review / 周回顾 / Inbox 清理"
- Any request to audit, refactor, or systematize an existing Obsidian vault

## The hybrid model: PARA outside, LLM Wiki inside

PARA is about **where the human acts**. LLM Wiki is about **where knowledge compounds**. They answer different questions and must not be conflated.

| | PARA (action space) | LLM Wiki (knowledge space) |
|---|---|---|
| What it solves | Where do I act? → Projects / Areas / Resources / Archive | How does knowledge compound? → raw → wiki |
| Organizing axis | Actionability (project → area → resource → archive) | Mutability (raw = immutable, wiki = LLM-owned) |
| Who writes | Human | LLM |
| Core directories | `01-Projects/`, `02-Areas/`, `03-Resources/`, `04-Archive/` | `00-Inbox/raw/`, `wiki/` |
| Review cadence | Weekly review (PARA) | Ingest after each source + periodic lint (Karpathy) |

### Target layout

```
<vault>/
├── CLAUDE.md                    ← schema (the "wiki contract", human + LLM co-edit)
│
├── 00-Inbox/                    ← Capture zone + LLM Wiki raw layer
│   └── raw/                     ← [LLM Wiki layer 1] IMMUTABLE raw sources
├── 01-Projects/                 ← P: active, deadline-bound work (NOT ingested into wiki)
├── 02-Areas/                    ← A: ongoing areas of responsibility
├── 03-Resources/                ← R: external tools, templates, references
├── 04-Archive/                  ← Archive: inactive projects, expired materials
│
├── Daily Note/                  ← daily journal (not ingested)
│
└── wiki/                        ← [LLM Wiki layer 2] LLM-owned synthesis
    ├── index.md                 ← content catalog (updated every ingest)
    ├── log.md                   ← append-only operations log
    ├── concepts/                ← concept / topic pages
    ├── entities/                ← people / companies / products / tools
    ├── moc/                     ← Map of Content per domain
    └── synthesis/                ← cross-concept synthesis pages
```

### Why nest `raw/` under `00-Inbox/`

The "capture → digest" flow becomes physical:
1. New material drops into `00-Inbox/raw/`.
2. LLM reads it, writes/updates pages in `wiki/`.
3. The raw file stays put (immutable source of truth), fully linked from its derived wiki pages.

`01-Projects/` is **deliberately excluded** from wiki ingestion — active project docs evolve daily and would pollute the wiki's compounding invariants.

## Non-negotiable principles

1. **Dry-run first.** Never move or rewrite files before showing a migration plan and getting confirmation.
2. **Preserve links.** Any rename or move MUST update inbound `[[wikilinks]]`, `![[embeds]]`, and markdown links across the vault.
3. **Git-first.** Before bulk operations, verify the vault is under git and has a clean working tree (or stashable). If not under git, require explicit user acknowledgement.
4. **Raw is read-only.** `00-Inbox/raw/` bodies are never rewritten. Only add/normalize frontmatter.
5. **`01-Projects/` is excluded** from wiki ingestion by default. Respect the PARA boundary.
6. **Wiki pages cite sources.** Every concept/entity/synthesis page lists the raw notes it draws from in frontmatter `sources:`.
7. **Contradiction over deletion.** When a new source overturns an older claim, annotate `⚠️ 已过时` and record the evolution in the page's "矛盾与演进 / Contradictions & Evolution" section — never silently delete.
8. **Query-compounding.** Good answers to user questions must be filed back into `wiki/synthesis/` — don't let insight die in chat.
9. **Obsidian-native.** `[[wikilinks]]`, YAML frontmatter, Dataview-friendly fields, callouts, tags.

## Workflow

### Phase 0 — Intake

Ask the user:

1. **Vault absolute path?** (required)
2. **Is the vault under git with a clean working tree?** (if no → warn, propose `git init && git add -A && git commit` or explicit opt-out)
3. **PARA adoption level** — does the vault already use PARA (detect `0?-Inbox`, `0?-Projects`, …)?
   - If yes → **preserve existing PARA folder names** and only supplement the wiki layer
   - If no → propose the numeric-prefix PARA layout above
4. **Primary domains** — the broad topics the vault covers (seeds for MOCs)
5. **Languages** — pure CN / pure EN / mixed (affects frontmatter fields and page language)
6. **Aggressiveness** — tidy-only / moderate / full refactor

Record answers; surface them in `CLAUDE.md` at the end.

### Phase 1 — Audit (read-only)

```bash
python3 "$SKILL_DIR/scripts/audit_vault.py" <vault_path>
```

Output covers: total counts, folder histogram, notes without frontmatter, orphans, red links, duplicates, top tags, top wikilink targets, attachments, largest/oldest/newest.

**Additionally**, run the PARA classifier to suggest how existing notes map to Projects/Areas/Resources/Archive:

```bash
python3 "$SKILL_DIR/scripts/para_classify.py" <vault_path> > /tmp/para-suggestions.md
```

This emits a suggested PARA placement per note based on: folder hints, `status`/`type` frontmatter, filename patterns (project codes, dates), recency, and wikilink centrality. It is **advisory** — the user has final say.

Save both outputs to `<vault>/00-Inbox/audits/audit-YYYY-MM-DD.md` and summarize headline findings to the user.

### Phase 2 — Propose a migration plan

Write `<vault>/00-Inbox/audits/migration-plan-YYYY-MM-DD.md` containing:

- Target folder tree (reflect user's PARA choices)
- **PARA placement table** for every existing note (current path → target PARA bucket)
- **Wiki-layer actions**: which notes become raw sources, which deserve new concept/entity pages, which MOCs to seed
- List of notes that will be **moved** (old path → new path)
- List of notes that will be **renamed** (usually to kebab/slug form; CJK titles may stay as-is if the user prefers)
- List of notes that need **frontmatter added**
- **Planned new wiki pages**: MOCs per domain, entity pages, concept pages derived from frequent wikilinks / tag clusters
- Explicit **risks & exclusions** (notes the LLM is unsure how to classify — always ask, never guess)

**Stop and request user review.** Never proceed to Phase 3 without explicit "go".

### Phase 3 — Execute restructure

Once approved, execute in order:

1. **Create target folders** (`00-Inbox/raw/...`, `01-Projects`, …, `wiki/...`).
2. **Move files** using `git mv` (preserves history). Batches of ≤20 with a commit between each.
3. **Rewrite wikilinks** with `scripts/rewrite_links.py` using the rename map produced in Phase 2.
4. **Normalize frontmatter** with `scripts/add_frontmatter.py` for notes missing it (use templates in `references/page-formats.md`).
5. After each batch, spot-check 3 notes in Obsidian for broken links before committing.

**Small batches.** Max 20 file operations per commit. `git status` must be clean between batches.

### Phase 4 — Generate wiki content

This is where the skill earns its value. Create derived pages in `wiki/`:

- **MOCs** (`wiki/moc/<domain>.md`) — one per primary domain; curated TOC + Dataview queries.
- **Entity pages** (`wiki/entities/<slug>.md`) — for people/companies/products/tools referenced ≥3 times across `00-Inbox/raw/`.
- **Concept pages** (`wiki/concepts/<slug>.md`) — recurring ideas/frameworks/techniques.
- **Syntheses** (`wiki/synthesis/<slug>.md`) — comparisons, overviews, cross-source analyses (on demand or when thematic clusters emerge).

Every generated page:
- Follows the template in `references/page-formats.md`
- Cites raw notes via `sources:` frontmatter **and** an inline "Sources" section with `[[wikilinks]]`
- Includes a "矛盾与演进 / Contradictions & Evolution" section (may be empty initially) — see `references/contradiction-protocol.md`

### Phase 5 — Schema, index, log

1. Write `<vault>/CLAUDE.md` using `references/schema-template.md`, filled with the user's choices. This is the **wiki contract** — every future LLM session reads it first.
2. Write `<vault>/wiki/index.md` — Dataview-first index + a hand-curated "Start here" section linking top MOCs and key concept pages.
3. Write `<vault>/wiki/log.md` — append an entry per operation:
   ```markdown
   ## [YYYY-MM-DD] <operation> | <short title>
   <one-paragraph description and file counts>
   ```
4. Final commit: `wiki: initialize PARA+LLM-Wiki schema, index, log`.

### Phase 6 — Report

Summarize to the user: files moved / renamed / rewritten, wiki pages generated, remaining issues, recommended next ingests, and lint cadence (weekly for full 8-item lint, quick lint after each ingest).

## Ongoing operations (after initial reorganize)

### Ingest a new source
1. Drop the raw file under `00-Inbox/raw/<subfolder>/`.
2. LLM reads it, discusses key takeaways with user.
3. LLM writes/updates: source's frontmatter, related concept & entity pages, relevant MOC, `wiki/index.md`, `wiki/log.md`.
4. A single ingest typically touches 10–15 files. Commit as one logical change.

### Query the wiki (⭐ compounding)
1. Start from `wiki/index.md` → relevant MOCs / concepts.
2. Read those pages; drill into `00-Inbox/raw/` only if needed.
3. Synthesize the answer with `[[wikilink]]` citations.
4. **File good answers back** as a new synthesis page in `wiki/synthesis/` (see `references/query-compounding.md` for the decision rubric — roughly: ≥3 sources or cross-concept insight ⇒ file back).

### Weekly review (PARA cadence)
```bash
python3 "$SKILL_DIR/scripts/weekly_review.py" <vault_path>
```
Produces a review doc covering:
- `00-Inbox/` items older than 7 days (should have been processed)
- `01-Projects/` with no activity in 14 days (candidates for `04-Archive/`)
- `02-Areas/` with no updates in 90 days (review responsibility scope)
- `04-Archive/` growth
- wiki-layer follow-ups from recent log entries

### Lint (⭐ 8-item Karpathy checklist)
```bash
python3 "$SKILL_DIR/scripts/lint_vault.py" <vault_path>
```
Checks:
1. Page-level contradictions (same concept conflicting across pages)
2. Stale conclusions superseded by newer raw sources
3. Orphan pages (no inbound `[[links]]`)
4. Missing concept pages (red links appearing ≥3 times)
5. Missing cross-references (two concept pages mention each other in prose but no wikilink)
6. Open knowledge gaps untouched > 30 days (from Gaps section in concept pages)
7. `index.md` vs filesystem drift
8. `log.md` idle > 7 days

Append findings to `wiki/log.md` under `## [YYYY-MM-DD] lint | ...`.

## Bundled resources

- `scripts/audit_vault.py` — read-only vault audit
- `scripts/para_classify.py` — suggest PARA bucket per note
- `scripts/rewrite_links.py` — apply a rename map across all `.md` files
- `scripts/add_frontmatter.py` — insert default frontmatter where missing
- `scripts/lint_vault.py` — 8-item health check
- `scripts/weekly_review.py` — PARA weekly review report
- `references/page-formats.md` — frontmatter + page templates (concept/entity/synthesis/MOC/source/index/log), incl. 矛盾与演进 section
- `references/schema-template.md` — template for `<vault>/CLAUDE.md`
- `references/taxonomy-heuristics.md` — decision trees for raw vs wiki, and for PARA bucketing
- `references/para-guide.md` — PARA adaptation guide (how Projects/Areas/Resources/Archive map in practice)
- `references/contradiction-protocol.md` — 3 rules for contradictions (don't delete, annotate evolution, propagate across pages)
- `references/query-compounding.md` — rules for when to file a query answer back into the wiki

**Always read the relevant `references/*.md` when executing a phase.** Do not rely on memory.

## Safety rails (restate)

- **Always dry-run → show plan → wait for approval** before moving/renaming files.
- **Git required** for Phase 3. If absent, stop and surface the risk.
- **Never touch `00-Inbox/raw/` bodies** — only frontmatter/tags.
- **`01-Projects/` is off-limits to wiki ingestion** — PARA boundary.
- **Link integrity check after every batch** — grep old slugs; they must be gone (except in migration-plan.md).
- **Small batches (≤20 ops)** with commits between them.
- **Never recursive delete.** Only move/rename — `rm -rf` is forbidden anywhere under the vault.
