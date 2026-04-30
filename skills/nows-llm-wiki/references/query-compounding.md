# Query Compounding Protocol

Karpathy's "compounding" principle: **the wiki gets more valuable with every question asked of it, not just with every source ingested.** When a user asks a question and the LLM produces a good synthesis, that synthesis has lasting value — **file it back**, don't let it die in the chat transcript.

## The decision rubric

After answering a user question, evaluate:

| Criterion | File back? | Location |
|---|---|---|
| Cross-concept synthesis (≥2 wiki pages cited) | ✅ yes | `wiki/synthesis/<slug>.md` |
| Comparison (entity vs entity, concept vs concept) | ✅ yes | `wiki/synthesis/<slug>.md` |
| ≥3 raw sources integrated into one answer | ✅ yes | `wiki/synthesis/<slug>.md` |
| New knowledge gap identified with substantial initial analysis | ✅ yes | update the relevant concept page's `## 知识缺口 / Gaps` section |
| New entity/concept surfaces that deserves its own page | ✅ yes | create stub in `wiki/entities/` or `wiki/concepts/` with `status: stub` |
| Single-source factual lookup (≤1 source cited) | ❌ no | reply only |
| User explicitly asks "don't save this" | ❌ no | reply only |
| Trivial clarification / meta-questions about the vault | ❌ no | reply only |

When in doubt: **file it as a stub**. A one-paragraph synthesis page is better than nothing — future ingests will enrich it.

## Synthesis page format

```markdown
---
title: <concise question-answer title>
type: synthesis
tags: [synthesis]
domain: <primary domain>
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[[<concept-or-entity-or-raw>]]"
  - "[[...]]"
status: draft
---

# <title>

> [!question] Question
> <the user's actual question, paraphrased if needed>

## TL;DR
<1–3 sentence answer>

## Analysis
<structured body: comparison table, timeline, bullets, or prose>

## Implications / Takeaways
1. ...

## Open questions
- ...

## Sources
- [[<source>]] — how it contributed
- [[<source>]] — ...
```

## Trigger checklist (run after every substantive answer)

1. Did the answer cite ≥2 wiki pages or ≥3 raw sources? → file back
2. Did the answer produce a comparison / timeline / architecture? → file back
3. Did the answer surface a gap, contradiction, or new entity? → update the relevant page (plus file-back if it was substantive)
4. Did the answer update the user's mental model in a non-obvious way? → file back as synthesis

After filing, append a `## [YYYY-MM-DD] query | <title>` entry to `wiki/log.md`.

## Anti-patterns

- **Filing every chat back**. The wiki bloats with low-value summaries. Use the rubric above.
- **Filing without sources**. A synthesis without `[[wikilinks]]` to raw/concept/entity pages can't participate in the compounding graph. Either add sources or skip filing.
- **Duplicating a concept page**. If the synthesis is really just the concept, edit the concept page instead of creating a new synthesis.
- **Filing speculation**. Mark highly speculative syntheses with `status: draft` and a `> [!warning] Speculation` callout.
