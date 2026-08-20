# Nature Reader (Embedded)

**Source:** `nature-reader` | **Snapshot:** 2026-06-06
**Pipeline usage:** S2 (deep-read top papers), S4 (reference reading during writing)

## Core Principle
Turn a research paper into a complete Markdown reading artifact with:
- Original text + Chinese translation side-by-side at block level
- Figures/tables extracted as assets, placed at first substantive mention
- Stable page/block anchors for traceability

## Output Structure
```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** [source paragraph]
**中文:** [faithful Chinese translation]
```

## Workflow
1. **Identify source & type** — selectable-text PDF, scanned PDF, publisher HTML
2. **Extract text & structure** — section hierarchy, paragraph boundaries
3. **Extract figures/tables** — crop from PDF pages, preserve captions
4. **Build bilingual reader** — paragraph-level alignment
5. **Write artifacts** — `paper.md`, `source_map.json`, `translation_notes.md`, `assets/`

## Non-negotiable
- Translate for meaning, not style
- Preserve structure, evidence, hedging, terminology, equations, units, citations
- Do NOT collapse into bullet points or slide-style notes
