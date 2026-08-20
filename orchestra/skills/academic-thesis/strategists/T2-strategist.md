# Stage T2: 文献综述 [Strategist]

**Gate:** QT2 (BLOCK)
**Goal:** Produce a comprehensive literature review with gap analysis, saturation assessment, and cross-language coverage.
**Needs Composers:** [literature-precheck]

## Decisions

### Citation Support Bank (P1)

Seed `{paper_dir}/.paper/citation_support_bank.md` during 文献综述 (gap/contrast/method candidates). Protocol: `../academic-shared/citation/citation-support-bank.md`.


### Axis 1: Degree-Differentiated Reference Targets
```
if degree == bachelor:
    target_total = 20+ references
    target_cn = 5+
    target_en = 5+
    depth = "broad survey, representative coverage"
elif degree == master:
    target_total = 30+ references
    target_cn = 10+
    target_en = 10+
    depth = "comprehensive coverage with historical evolution"
```

### Axis 2: Redundant Scheduling — Gap Matrix (DP29)
```
Mode: B x2 (two independent agents)
Execution:
    agent_1 → build gap matrix independently
    agent_2 → build gap matrix independently
    orchestrator → compare cell-by-cell

Outcome:
    if consistent (count_diff <= 2 AND no missed papers):
        → PASS → use merged result
    elif diverging (count_diff > 2 OR at least one misses a paper):
        → HUMAN REVIEW REQUIRED
        → present both matrices side-by-side
        → flag discrepant cells
        → user decides which to keep or merge

Gap matrix dimensions:
    - rows: research questions / sub-topics
    - columns: [C: Chinese lit volume], [W: English lit volume], [Consensus level]
```

### Axis 3: Parallel Search Tracks
Three independent search streams:

1. **English academic** (Google Scholar, Scopus, Web of Science)
   - Search string: derived from topic keywords
   - Target: peer-reviewed journals, conferences

2. **Chinese academic** (CNKI, Wanfang, VIP)
   - Search string: Chinese translation of keywords
   - Target: core journals, CSSCI, degree theses

3. **Policy/Industry/Grey literature** (政府白皮书, 行业报告, 技术标准)
   - Optional for bachelor; required for master
   - Target: recent 3-5 years

### Axis 4: Fallback Logic
```
if English academic search returns < target_en:
    → trigger paper-lookup fallback
    → search by DOI list or specific known papers
    → if still insufficient: [ENGLISH-POOL-INSUFFICIENT] flag
if snowball sampling produces no new papers:
    → try alternate seed DOIs (from Chinese lit references)
    → if still empty: [SNOWBALL-SKIPPED] flag
```

### Axis 5: Chinese Tier-to-Score Mapping
| Tier | Score | Description |
|------|-------|-------------|
| A    | 8.5   | CSSCI / core journal / top conference |
| B    | 6.0   | General journal / university学报 |
| C    | 3.5   | Degree thesis / conference abstract / non-core |

### Axis 6: Dual-Gap Interpretation
Interpretation matrix based on gap_matrix results:

| C volume | W volume | Interpretation |
|----------|----------|----------------|
| 0        | 0        | [HIGHEST VALUE] — genuinely new territory; flag high-risk/high-reward |
| 0        | W:5+     | [PRACTICE-BEFORE-THEORY] — Chinese practice exists but lacks theoretical framing |
| C:5+     | 0        | [DETACHED-FROM-PRACTICE] — English theory exists but not validated in Chinese context |
| 0        | W:1-4    | [EARLY-STAGE] — nascent field in both languages |
| C:5+     | W:5+     | [ESTABLISHED] — need strong niche angle or risk being redundant |

### Axis 7: Cross-Language Deduplication
Three-pass deduplication:
1. **Pass 1 — DOI match**: exact DOI comparison
2. **Pass 2 — English-title match**: normalize and compare English titles (or translated CN titles)
3. **Pass 3 — Author+year match**: same author(s) + same publication year

After dedup, perform **Chinese Citation Tracing** on top-5 CNKI papers:
- Trace forward citations (who cites this paper) and backward citations (what this paper cites)
- Newly discovered papers tagged `[CITATION-TRACE-CN]`
- Add to merged bibliography with quality tiering

### Axis 8: Playwright Fallback → User-as-External-Skill Pattern
```
if CNKI/Wanfang access fails (blocked/requires auth):
    → attempt Playwright-based access via Edge CDP
    → if Playwright also fails:
        → transition to user-as-external-skill pattern
        → user manually searches and provides results
        → user enters: paper title, authors, year, tier
        → strategist validates and scores
```

### T2A: PRISMA Flow Tracking

Record screening workflow in the search protocol:

| Stage | Count | Notes |
|-------|-------|-------|
| Records identified | N | from database searches |
| Records after dedup | N | cross-language + within-language |
| Records screened (title/abstract) | N | relevance filter applied |
| Full-text assessed | N | available for detailed review |
| Included in review | N | final bibliography |

## Gate

### QT2 Gate Checklist
- [ ] PRISMA flow recorded (records identified → included)
- [ ] Target reference count met (20+/30+)
- [ ] Chinese literature target met (5+/10+)
- [ ] English literature target met (5+/10+)
- [ ] Gap matrix completed and consistent (or human review done)
- [ ] Cross-language deduplication completed (DOI → title → author+year)
- [ ] Chinese Citation Tracing complete (top-5 CNKI papers → citations traced, tagged `[CITATION-TRACE-CN]`)
- [ ] Dual-gap interpretation recorded
- [ ] Grey literature searched (master only)
- [ ] All fallbacks documented if triggered

### Gate Failure Route
```
if reference count below target:
    → BLOCK — cannot proceed with insufficient lit base
    → recommend additional search directions
if gap matrix diverges unresolved:
    → BLOCK — human review required
if both Playwright and user-as-external-skill fail:
    → BLOCK — insufficient Chinese literature access
    → recommend alternative library access method
```
