# Stage S2: Literature Review & Gap Analysis [Strategist]

**Gate:** Q2 (BLOCK) — gap analysis exists with 10+ verified citations, no unverified DOIs.
**Goal:** Systematic literature search with reproducible methodology.
**Needs Composers:** none (uses literature search tools, not composers)

## Decisions

### Citation Support Bank (P1)

1. Create `{paper_dir}/.paper/citation_support_bank.md` from `../academic-shared/citation/citation_support_bank.template.md`.
2. For each gap / contrast / method claim in the lit review, add candidate rows (`verified=false` until S6).
3. Protocol: `../academic-shared/citation/citation-support-bank.md`.
4. Do not invent BibTeX keys — titles + DOI/arXiv only until verification.


### Axis Routing
No axis/passport branching. Standard routing for all paper types.

### Chinese Domestic Routing — CNKI Search Integration
When `venue=chinese-domestic` (i.e., targeting Chinese journals), the literature review MUST include Chinese databases. The standard English databases (OpenAlex, Semantic Scholar, CrossRef, Google Scholar) have poor coverage of Chinese journals — relying on them alone is a critical gap.

**Routing logic:**
```
IF venue IN [chinese-domestic, chinese-conference]:
    Execute 2B (English) + 2B-CNKI (Chinese) in sequence
    Merged results → continue to 2C
ELSE:
    Execute 2B (English only) → continue to 2C
```

**2B-CNKI substep:**
1. Run `literature_search.py --sources cnki --cnki-query "<Chinese keywords>" --output {output_dir}/cnki_instructions.json`
2. This prints manual search instructions and writes `cnki_import_template.json` in the output directory
3. Present the CNKI search instructions to the user. Explain: "CNKI/万方/维普 没有公开 API，需要您手动检索并填写模板。模板已保存在 `{output_dir}/cnki_import_template.json`。"
4. WAIT for user to complete manual search and fill the template
5. Run `literature_search.py --import-cnki "{output_dir}/cnki_import_template.json" --cnki-query "<Chinese keywords>" --output {output_dir}/cnki_results.json`
6. CNKI results are scored with tier-aware authority (CSCD > CSSCI > 北大核心 > 普通期刊) and merged with English results
7. Combined results proceed through dedup → snowballing → verification

**CNKI tier-aware quality scoring (applied automatically by `compute_quality_scores_cnki`):**
| Tier | Journal Classification | Authority Score |
|------|----------------------|-----------------|
| A | 顶刊 (中国社会科学 etc.) | 10.0 |
| B1 | CSSCI 核心 + 学科权威 | 9.0 |
| B2 | CSSCI / CSCD 核心 | 8.0 |
| B3 | CSSCI 扩展版 / 北大核心 | 7.0 |
| C1 | 大学学报 (核心收录) | 5.0 |
| C2 | 大学学报 (普通) | 3.5 |
| C3 | 普通期刊 / 特色期刊 | 2.0 |
| D | 会议论文 | 1.5 |

**Chinese keyword strategy:** If user hasn't provided Chinese keywords, derive them from the English query + topic. Chinese academic papers use different terminology than direct translations — prefer discipline-standard Chinese terms. The `--cnki-query` accepts Chinese characters.

### Sub-Step Execution Order
2A (Search Protocol) → 2B (Multi-Source Search) → [2B-CNKI if Chinese domestic] → 2C (Snowballing) → 2D (Citation Network Analysis) → 2D.5 (Citation Verification) → 2E (Deep Reading & Tagging) → 2F (Gap Analysis Output)

Strictly sequential with embedded conditional fallbacks.

### Search Procedure & Fallback Logic (S2, lines 80-93)
Primary tool: `../academic-shared/literature/literature_search.py` (multi-source: OpenAlex + Semantic Scholar + CrossRef + Google Scholar + CNKI when venue=chinese-domestic).

**Fallback trigger:** After running search command, orchestrator MUST check output JSON:
- IF `results` is empty OR `count` is 0 → trigger fallback:
  1. Load `skills-embedded/paper-lookup.md` for manual per-database search procedures
  2. Use `agent-browser` to manually search each database (OpenAlex, Semantic Scholar, CrossRef, Google Scholar)
  3. Aggregate fallback results into `{output_dir}/search_results_fallback.json`
  4. Tag ALL entries as `[FALLBACK-PAPER-LOOKUP]`
  5. Proceed to quality filtering using fallback results
- IF both primary AND fallback return < 10 papers → STOP-AND-ASK (section 2G)

### Snowballing Fallback (S2, lines 190-192)
After running snowball command, check `{output_dir}/snowball_results.json`:
- IF results empty or count is 0 → solicit alternative seed DOIs from user, or skip snowballing and document as `[SNOWBALL-SKIPPED]` in gap analysis.
- IF results exist but fewer than expected (<5 per seed on average) → note limitation but proceed.

### Citation Verification Routing (S2, lines 240-256)
After `verify_citations.py` batch check, per-entry verdicts:
- `true` → proceed normally
- `false` (DOI existed but no API matched) → STOP-AND-ASK: confirm whether to replace with real source or provide correct DOI
- `unresolvable` (no DOI + title search failed) → tag as `[待用户确认]`; manual review before including
- `contamination_level=high` → log to audit trail for S6 follow-up

### Redundancy Strategy (DP26, Mode B x2)
Gap statement generation uses Mode B x2 redundancy (DP26, S2 lines 13-16):
- 2 agents independently generate gap statements from same literature collection and search protocol.
- Orchestrator compares:
  - High agreement → pass through directly
  - Partial agreement → merge intersection
  - Low agreement → user decides

### STOP-AND-ASK Points
- **2B fallback trigger:** If both primary and fallback return < 10 papers → "N papers found, need X A+B tier. Widen scope or accept current results?"
- **2C snowball fallback:** If snowball returns empty → ask user for alternative seed DOIs or skip.
- **2D.5 citation verification `false`:** Confirm fabricated DOI suspicion with user.
- **Q2 failure (after 2 fix attempts):** Ask user: expand scope, relax standards, or proceed-as-is.

## Gate

### Q2 Gate Checklist
- [ ] Search protocol (search_protocol.md) written and saved
- [ ] Multi-source search complete via literature_search.py (3+ databases)
- [ ] Quality matrix generated — top papers filtered by composite score >= 6.0
- [ ] Snowballing complete (backward + forward, depth >= 1)
- [ ] Citation network analysis reviewed — clusters labeled (consensus/controversy/frontier)
- [ ] Top 10 papers deep-read
- [ ] Gap analysis document produced (done / missing / where you fit)
- [ ] Thematic literature synthesis produced
- [ ] verify_citations.py batch verification complete — no false verdicts remain
- [ ] Top 10 papers metadata cross-checked against API results
- [ ] 10+ citations verified by DOI
- [ ] [Chinese domestic] CNKI/万方 search complete — Chinese-language papers imported and scored
- [ ] [Chinese domestic] Combined English + Chinese results cover both international and domestic literature
- [ ] [Chinese domestic] Domestic literature gap identified (for S2.5 DomesticGap dimension)
- [ ] Stage completion log appended

### Gate Failure Route
Q2 is BLOCK.

1. First failure → identify which check items failed → route back to corresponding sub-step → re-run → re-evaluate gate.
2. After 2 fix attempts still fail → STOP-AND-ASK: expand scope, relax standards, or proceed-as-is (route back to S2A, adjust search terms, re-execute S2B-S2D).
