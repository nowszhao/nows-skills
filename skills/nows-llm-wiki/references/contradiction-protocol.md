# Contradiction & Evolution Protocol

Knowledge evolves. Sources disagree. Old conclusions get overturned. **Silent deletion destroys the historical record** — and the user loses the ability to understand why a belief changed.

This protocol defines how to handle contradictions on wiki concept/entity/synthesis pages.

## Three rules (non-negotiable)

### Rule 1 — Don't delete; annotate

When a new raw source contradicts an older claim on a wiki page:
1. **Keep the old claim** in place.
2. Prefix it with `⚠️ 已过时（YYYY-MM-DD）` or `⚠️ superseded (YYYY-MM-DD)`.
3. Add a `[[wikilink]]` to the new source.

Example:

```markdown
## Core claim

- ⚠️ 已过时（2026-05-01）：~~Dagster 的 assets 只能被单一 op 物化~~ — see [[Dagster-2026-multi-asset-RFC]]
- Dagster 2026 起支持 multi-asset ops，允许单次物化多个 asset（[[Dagster-2026-multi-asset-RFC]]）。
```

### Rule 2 — Record evolution explicitly

Every concept/entity/synthesis page has a `## 矛盾与演进 / Contradictions & Evolution` section. Append a new entry whenever a claim changes:

```markdown
## 矛盾与演进 / Contradictions & Evolution

- ✅ **共识**: <stable conclusion> (sources: [[a]], [[b]])
- ⚠️ **分歧**: <view A> vs <view B> (sources: [[a]] vs [[b]])
- 🔄 **演进**: <old> → <new> (trigger source: [[c]], date: YYYY-MM-DD)
```

Entries are **append-only**. Never edit a past entry — if further evolution happens, add a new one that refers to the previous.

### Rule 3 — Propagate across pages

If a change on concept page A affects concept page B (B cites A, or B is in A's "related concepts"):
- Update B's 矛盾与演进 section with a cross-reference: `🔄 see also [[A]] — updated YYYY-MM-DD, affects this page because ...`
- Update the `updated:` frontmatter of B.
- Commit both changes together.

LLMs are good at this because it's mechanical — but only if triggered. **On every concept-page edit, check outbound `[[wikilinks]]` for pages that should be notified.**

## What counts as "superseding" vs "nuance"

- **Superseding**: a later source directly refutes a specific claim. Use the ⚠️/🔄 protocol.
- **Nuance**: a later source adds a caveat without refuting. Inline the nuance with a citation; no 已过时 annotation needed.
- **Orthogonal**: a later source addresses a different angle. Extend the page's scope; cite both.

When unsure, err on the side of 矛盾与演进 — the cost of a spurious evolution entry is tiny; the cost of silently overwriting is high.

## Lint hook

`scripts/lint_vault.py` (item #1 and #2) looks for:
- Pages where two sources give conflicting numbers / dates / definitions but no 矛盾与演进 entry exists → flag as "page-level contradiction".
- Pages citing a raw source dated *before* another raw source in their `sources:` list, without any evolution note → flag as "stale conclusion".

Both are warnings, not errors. The LLM offers to add evolution entries; the human approves.
