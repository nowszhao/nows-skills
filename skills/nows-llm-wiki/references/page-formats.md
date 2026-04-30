# Page Formats (PARA + LLM Wiki)

All generated wiki pages live under `<vault>/wiki/` (NOT nested in PARA; the wiki layer is parallel to PARA). They use Obsidian-flavored markdown: YAML frontmatter, `[[wikilinks]]`, callouts, Dataview fields.

Raw-source frontmatter lives on notes under `<vault>/00-Inbox/raw/…`.

## Frontmatter field conventions

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | Human-readable title; may differ from filename |
| `type` | enum | yes | `entity` \| `concept` \| `synthesis` \| `moc` \| `source` \| `index` \| `log` \| `schema` |
| `aliases` | list[string] | no | Obsidian alias list |
| `tags` | list[string] | recommended | Flat tags, no `#` prefix in YAML |
| `domain` | string | recommended | Primary domain / MOC this page belongs to |
| `sources` | list[wikilink] | required for wiki pages | Raw notes (or other wiki pages) this page draws from |
| `source_count` | int | optional for concepts | How many raw sources were merged into this page |
| `source_kind` | enum | required for raw | `research` \| `clipping` \| `transcript` \| `paper` \| `flash` |
| `created` | date `YYYY-MM-DD` | yes |  |
| `updated` | date `YYYY-MM-DD` | yes | Refreshed on every edit |
| `status` | enum | no | `stub` \| `draft` \| `stable` \| `needs-review` |

---

## Raw source — `00-Inbox/raw/<kind>/<slug>.md`

Only frontmatter is added/normalized; the body is preserved verbatim.

```markdown
---
title: <Original title>
type: source
source_kind: research | clipping | transcript | paper | flash
source_url: <url if available>
author: <author if known>
date: YYYY-MM-DD        # captured date
tags: []
domain: <domain>
status: raw
related:
  - "[[<related-note>]]"
---

<original body, unchanged>
```

---

## Concept page — `wiki/concepts/<slug>.md`

```markdown
---
title: <概念名 / Concept>
type: concept
aliases: []
tags: [concept]
domain: <domain>
source_count: <N>
sources:
  - "[[<raw-note-1>]]"
  - "[[<raw-note-2>]]"
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: draft
---

# <概念名>

## TL;DR
<一句话定义，独立成段>

## 核心定义
<2–3 段清晰定义，中性语气>

## 关键洞察
- <洞察 1>（来源：[[raw-note]]）
- <洞察 2>

## 机制 / 工作原理
<机制、流程、或 Mermaid 图>

## 主要来源
- [[<raw-note-1>]]
- [[<raw-note-2>]]

## 与其他概念的关系
- **上游**：[[<前置概念>]]
- **关联**：[[<相关概念>]]
- **下游应用**：[[<应用场景>]]

## 矛盾与演进 / Contradictions & Evolution
> 参见 contradiction-protocol.md。此 section 仅追加，不修改历史条目。

- ✅ **共识**: <stable conclusion> (sources: [[a]], [[b]])
- ⚠️ **分歧**: <view A> vs <view B> (sources: [[a]] vs [[b]])
- 🔄 **演进**: <old> → <new> (trigger: [[c]], date: YYYY-MM-DD)

## 知识缺口 / Gaps
- <open question 1>
- <open question 2>
```

---

## Entity page — `wiki/entities/<slug>.md`

```markdown
---
title: <Entity name>
type: entity
aliases: []
tags: [entity]
domain: <domain>
sources:
  - "[[<raw-note>]]"
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: draft
---

# <Entity name>

> [!info] TL;DR
> One-sentence summary of who/what this is and why it matters in this vault.

## Overview
<2–4 short paragraphs, neutral tone; cite sources inline with `[[wikilinks]]`>

## Key facts
- ...

## Relations
- Part of: [[<moc-or-parent>]]
- Related: [[<entity-or-concept>]]

## Timeline / evolution (optional)
- YYYY-MM-DD — <milestone>

## 矛盾与演进 / Contradictions & Evolution
- ...

## Sources
- [[<raw-note>]] — what was drawn from it
```

---

## Synthesis page — `wiki/synthesis/<slug>.md`

```markdown
---
title: <Synthesis title>
type: synthesis
tags: [synthesis]
domain: <domain>
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[[<concept-a>]]"
  - "[[<concept-b>]]"
  - "[[<raw-source>]]"
status: draft
---

# <Synthesis title>

> [!question] Question / Purpose
> <the question this page answers>

## TL;DR
<1–3 sentences>

## Analysis
<comparison table / timeline / bullets / prose>

## Implications
1. ...
2. ...

## Open questions
- ...

## Sources
- [[<page>]] — how it contributed
```

---

## MOC page — `wiki/moc/<domain>.md`

````markdown
---
title: MOC — <Domain>
type: moc
tags: [moc]
domain: <domain>
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

# <Domain> — Map of Content

> [!info] About this MOC
> <One paragraph on scope and the questions this domain covers.>

## Start here
- [[<flagship-concept-or-entity>]] — why it's the entry point
- [[<next>]] — ...

## Concepts
```dataview
TABLE domain, status, source_count
FROM "wiki/concepts"
WHERE domain = "<domain>"
SORT file.name ASC
```

## Entities
```dataview
TABLE domain, updated
FROM "wiki/entities"
WHERE domain = "<domain>"
SORT updated DESC
```

## Syntheses
```dataview
LIST
FROM "wiki/synthesis"
WHERE domain = "<domain>"
SORT updated DESC
```

## Recent raw sources
```dataview
TABLE file.ctime as "Captured"
FROM "00-Inbox/raw"
WHERE contains(domain, "<domain>") OR contains(tags, "<domain>")
SORT file.ctime DESC
LIMIT 10
```
````

---

## Index — `wiki/index.md`

````markdown
---
title: Wiki Index
type: index
updated: YYYY-MM-DD
---

# Wiki Index

## Start here
- [[wiki/moc/<domain-1>|<Domain 1> MOC]]
- [[wiki/moc/<domain-2>|<Domain 2> MOC]]

## All MOCs
```dataview
LIST FROM "wiki/moc" SORT file.name ASC
```

## All concepts
```dataview
TABLE domain, status, source_count
FROM "wiki/concepts"
SORT file.name ASC
```

## All entities
```dataview
TABLE domain, updated
FROM "wiki/entities"
SORT updated DESC
```

## All synthesis
```dataview
TABLE domain, updated
FROM "wiki/synthesis"
SORT updated DESC
```

## Recent raw sources
```dataview
TABLE source_kind, domain, file.ctime as "Captured"
FROM "00-Inbox/raw"
SORT file.ctime DESC
LIMIT 15
```

## Recently updated wiki
```dataview
TABLE file.mtime as "Updated"
FROM "wiki"
SORT file.mtime DESC
LIMIT 15
```
````

---

## Log — `wiki/log.md`

```markdown
---
title: Wiki Operations Log
type: log
---

# Wiki Operations Log

## [YYYY-MM-DD] init | vault reorganization (PARA + LLM Wiki)
Restructured vault into PARA + wiki. Moved N files, renamed M, added frontmatter to K. Generated X MOCs, Y concept pages, Z entity pages, W synthesis pages.

## [YYYY-MM-DD] ingest | <source title>
Ingested `00-Inbox/raw/research/<file>.md`. Touched: [[concept-a]], [[entity-b]], [[wiki/moc/domain]], `wiki/index.md`.

## [YYYY-MM-DD] query | <question title>
Answered cross-concept question. Filed [[wiki/synthesis/<slug>]].

## [YYYY-MM-DD] lint | weekly checklist
Checked 8 items. Findings: <summary>.

## [YYYY-MM-DD] review | weekly PARA review
Inbox aged: N. Projects stale: M. Areas neglected: K. See `00-Inbox/reviews/<date>.md`.
```

Read recent timeline with `grep "^## \[" wiki/log.md | tail -N`.
