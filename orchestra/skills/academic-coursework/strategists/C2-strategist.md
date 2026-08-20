# Stage C2: 文献检索 [Strategist]

**Gate:** QC2 (BLOCK) — 15+ references after screening (A+B only), mixed Chinese/English, each argument has 3+ supporting refs; search protocol written; quality matrix applied
**Goal:** 收集 15 篇以上中英文高质量参考文献，每个论点有 3+ 篇支持。
**Needs Composers:** none (uses tool pipeline, not composers)

## Decisions

### Axis Routing

#### C2A: Search Protocol (NEW — write BEFORE searching)

在启动任何 agent 或工具之前，先生成 `search_protocol.md` 写入 `{output_dir}/`：

```markdown
# C2 Literature Search Protocol

## Core Concepts (Chinese + English)
- Primary concept (CN): [定义核心概念]
- Primary concept (EN): [define in English]
- CN Synonyms: [列出所有中文变体]
- EN Synonyms: [list all English variants]

## Database-Specific Search Strings
### English: OpenAlex / Semantic Scholar / CrossRef
boolean_string_for_english

### Chinese: CNKI / Wanfang
keyword_set_1
keyword_set_2

## Inclusion/Exclusion Criteria
- Include: [criteria]
- Exclude: [criteria]

## Filters
- Year range: YYYY-YYYY
- Language: zh + en
```

**CRITICAL RULE:** Search protocol MUST be written and saved BEFORE any agent or tool is launched. QC2 gate blocks if missing.

#### DP17: Parallel Search Tracks

Two tracks run in parallel:
- **Track 1 (English):** C2B — `literature_search.py` for automated search + quality scoring + snowballing
- **Track 2 (Chinese + Web):** C2C + C2D + C2E agents

#### Track 1: C2B — English Academic Papers (literature_search.py)

**Primary tool:** `{pipeline_root}/../academic-shared/literature/literature_search.py` (multi-source: OpenAlex + Semantic Scholar + CrossRef)

```bash
python {pipeline_root}/../academic-shared/literature/literature_search.py \
  --query "{boolean_search_from_protocol}" \
  --sources openalex,semanticscholar,crossref \
  --years {start_year}-{end_year} \
  --limit 50 \
  --min-score 5.0 \
  --output {output_dir}/c2b_english_search.json
```

After initial search, extract top-10 DOIs for snowballing:

```bash
python -c "
import json
with open('{output_dir}/c2b_english_search.json') as f:
    data = json.load(f)
dois = [p['doi'] for p in data['results'][:10] if p.get('doi')]
with open('{output_dir}/c2_top10_dois.txt', 'w') as f:
    f.write('\n'.join(dois))
"

python {pipeline_root}/../academic-shared/literature/literature_search.py \
  --query "{original_query}" \
  --sources openalex,semanticscholar,crossref \
  --years {start_year}-{end_year} \
  --seed-dois {output_dir}/c2_top10_dois.txt \
  --snowball-depth 1 \
  --min-score 5.0 \
  --output {output_dir}/c2b_english_combined.json
```

**Fallback chain (C2B):**
- Primary: `literature_search.py`
- If JSON is empty or count=0 → fallback to `paper-lookup` tool (see `skills-embedded/paper-lookup.md`)
- Tag fallback entries as `[FALLBACK-PAPER-LOOKUP]`
- If still insufficient → proceed with warning, document in credibility report

**Snowball fallback:**
- If snowball yields no new papers → solicit alternative seed DOIs via STOP-AND-ASK, or skip and mark `[SNOWBALL-SKIPPED]`

#### Track 2: C2C + C2D + C2E

##### C2C — Policy/Legal/Industry Sources

Use `agent-browser` for policy/government/industry websites. Use `WebSearch` only for URL discovery, then `agent-browser` for full extraction.

Requirements:
- Find 5+ policy/legal/regulatory sources
- Each with: title, issuing body, year, URL
- Tag per argument (A1/A2/A3)
- Write to `{output_dir}/c2c_policy_legal.md`

##### C2D — Chinese-Language Sources (CNKI/Wanfang via Playwright MCP)

Primary: Playwright MCP headful browser for CNKI/Wanfang. See `references/playwright-browser-automation.md`.

**Chinese Citation Tracing:** After CNKI search, conduct citation tracing for top-5 extracted papers (forward + backward citations). Newly discovered papers tagged `[CITATION-TRACE-CN]`.

Fallback: `user-as-external-skill` — provide CNKI search instructions, ask user to paste results.
Fallback entries tagged `[USER-SOURCED]`.

##### C2E — Web Context Search (Tavily / DeepSeek)

Primary: Tavily API. Fallback: Playwright MCP + DeepSeek Chat. See `references/tavily-search.md`.

Output: `{output_dir}/c2e_web_context.md` with 2D quality scores (domain_authority + content_depth).

**CRITICAL:** Web content is NOT a verified academic source. Every fact entering the paper body must cite a verifiable A/B-tier reference. Web-discovered URLs/papers go to C2F for verification.

### C2F: Credibility Screening + Quality Matrix

#### Credibility Tiers

| Tier | Criteria | Tag | Action |
|------|----------|-----|--------|
| **A — Verified Academic** | DOI resolves via CrossRef/OpenAlex. Author, title, venue, year confirmed. | `[A]` | Pass directly |
| **B — Verifiable Official** | No DOI but URL on official domain (.gov/.edu/.ac.cn/standards body). Title/issuing body consistent. | `[B]` | Pass, URL-verified |
| **C — Unverifiable Source** | URL exists but non-official (Baidu Baike, news, forum). OR metadata gaps. | `[C]` | Capped ≤20% of total |
| **D — Unverifiable/Fabricated** | No DOI, no URL, URL broken. OR exclusively from LLM output. | — | **Auto-reject** |

#### 3D Quality Scoring

For ALL A-tier and B-tier entries:

| Dimension | English Papers | Chinese Papers |
|-----------|---------------|----------------|
| `source_authority` (0.40) | Auto from `literature_search.py` (journal tier, citation count) | Manual: CSSCI/CSCD/北大核心=8-10; standard journal=5-7; dissertation=5-7 |
| `timeliness` (0.25) | Auto (year vs field half-life) | ≤2yr=10, ≤5yr=8, ≤10yr=6, >10yr=4 |
| `relevance` (0.35) | Auto (term overlap with query) | Manual assessment during screening |

**Composite = 0.40 × authority + 0.25 × timeliness + 0.35 × relevance**

#### Chinese Tier-to-Score Mapping

| Chinese Tier | Numeric Score | Tag |
|-------------|--------------|-----|
| A-tier (CSSCI/CSCD/北大核心) | **8.5** | `[SCORE-MAPPED: 8.5]` |
| B-tier (普通期刊) | **6.0** | `[SCORE-MAPPED: 6.0]` |
| C-tier (学位论文/非核心) | **3.5** | `[SCORE-MAPPED: 3.5]` |

#### Quality-Based Tier Adjustments (C2F.2)

For B-tier and C-tier entries from web sources, apply 2D quality scoring (domain_authority × 0.55 + content_depth × 0.45):
- B-tier with composite < 4.0 → **downgrade to C-tier** (weak source)
- C-tier with composite ≥ 7.0 → **upgrade to B-tier** (strong non-traditional source)

#### C-Tier Cap

If C-tier > 20% of total (A+B+C): keep top-ranked C-tier up to 20%, reject rest. Tag: `[C-LEVEL-REJECTED]`.

#### Screening Output

Write `{output_dir}/c2f_credibility_report.md`:
```
## Credibility Screening Report
- Total screened: {N}
- A-tier (DOI-verified): {nA}
- B-tier (URL-verified): {nB}
- C-tier (unverifiable): {nC}
- D-tier (rejected): {nD}
- PASS (A+B): {nA+nB}

### Quality Score Distribution (A+B only)
- Excellent (8-10): {n}
- Good (6-8): {n}
- Fair (4-6): {n}
- Poor (0-4): {n}

### Rejected (D-tier)
| # | Title | Reason |
|---|-------|--------|
```

### C2G: Merge, Dedup & Citation Network

1. Load all agent output files (C2B, C2C, C2D, C2E)
2. Apply C2F screening: remove D-tier, flag C-tier, attach quality scores

#### Cross-Language Dedup (NEW)

Before merging, check for duplicates across English and Chinese sets:

1. **DOI matching:** Chinese paper has DOI → check English set. Match → keep richer entry, tag `[CN+EN]`
2. **English-title matching:** Chinese paper's English title → normalize and compare with English-set titles. Match → merge, tag `[CN+EN]`
3. **Author+year matching:** Same author surname + same year + topic overlap → flag `[POSSIBLE-DUP: CN↔EN]` for manual review

3. Merge A+B+C entries, within-language dedup
4. Verify `[USER-SOURCED]` integrity (cross-check against C2B results)
5. Citation network analysis: for English papers, check `citation_network` field. Identify clusters (consensus/controversy/frontier)
6. Sort by argument → composite quality score within each argument
7. Count: total (A+B+C), per-argument, per-language, quality distribution

### C2H: Gap Fill

- Per argument: if < 3 supporting A+B refs with quality score ≥ 5.0 → targeted search
- Global: total A+B < 8 → **CRITICAL** (STOP-AND-ASK); < 15 → **STANDARD** (STOP-AND-ASK, suggest fill)

## Gate

### QC2 Gate Checklist
- [ ] **Search protocol** (`search_protocol.md`) written and saved BEFORE any search
- [ ] Credibility screening (C2F) complete — all entries tiered [A]/[B]/[C] or rejected [D]
- [ ] **Quality matrix** applied — A+B entries have composite scores with dimension breakdown (authority/timeliness/relevance)
- [ ] **Chinese tier-to-score mapping** applied (A=8.5, B=6.0, C=3.5) — every Chinese entry tagged `[SCORE-MAPPED: X.X]`
- [ ] **Snowballing** complete (forward + backward, depth ≥ 1) — results merged into c2b_english_combined.json
- [ ] **Citation network** reviewed — consensus/controversy/frontier clusters identified
- [ ] **Chinese Citation Tracing** complete for top-5 CNKI papers — new entries tagged `[CITATION-TRACE-CN]`
- [ ] **Cross-language dedup** applied (DOI → English-title → Author+year matching)
- [ ] **Web context search** (C2E) complete — c2e_web_context.md written with 2D quality scores
- [ ] **Web-academic cross-reference** done — paper leads from Tavily routed back to paper-lookup
- [ ] **Quality-based tier adjustments** applied — B↔C upgrade/downgrade per C2F.2 thresholds
- [ ] 15+ references after dedup (standard) / 8+ (emergency)
- [ ] A+B tier references ≥ minimum threshold (12 standard / 6 emergency)
- [ ] D-tier entries rejected and documented in credibility report
- [ ] At least 3 Chinese-language sources (A or B tier)
- [ ] At least 3 English-language sources (A or B tier)
- [ ] Each C1 argument has 3+ supporting A+B references (quality score ≥ 5.0 for at least 2 of the 3)
- [ ] All entries have title + author + year (minimum metadata)
- [ ] C-tier entries ≤ 20% of total bibliography
- [ ] Bibliography file written to `{output_dir}/bibliography.md`
- [ ] Credibility report written to `{output_dir}/c2f_credibility_report.md`

### Gate Failure Route
- Failed QC2 → identify failing dimension → route back to corresponding sub-step → re-evaluate QC2
- 2 consecutive failures → STOP-AND-ASK: present literature status report → route to C2B (re-search) or C2D (manual CNKI)
