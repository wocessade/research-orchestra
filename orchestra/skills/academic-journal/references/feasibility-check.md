# End-to-End Feasibility Check

## Inter-Stage Dependency Chain

Each stage produces artifacts consumed by downstream stages. If an upstream stage fails, everything downstream breaks.

**Idea-First:**
```
S1: Research question string
  ↓
S0.5: Project sanity check (advisory — 3 questions)
  ↓
S1.5: Research design document (design type + identification strategy [causal only])
  ↓
S2: Gap analysis doc + verified BibTeX library
  ↓
S2.5: Novelty audit (profile + competing papers + contribution type)
  ↓
S3: Claim outline (depends on gap analysis §2D, framed to S2.5 contribution type)
  ↓
S4: Complete manuscript .tex (depends on outline §3B)
  ↓
S5: Figures ─────────────────────┐
S6: Verified references ────────┤ (S5, S6, S6.5 run in parallel after S4)
S6.5: Reproducibility check ────┘   ← DP9, DP10, DP11
  ↓
S7: Polished manuscript (depends on complete text §4 + figures §5)
  ↓
S8.5: Publication strategy (route selection + venue list; depends on S2.5 novelty score.
      NOTE: can start as early as S2.5 in parallel with S3-S7 — no dependency on S4/S5/S6/S7)
  ↓
S8.6: Chinese journal execution layer (if domestic target; 8.6A-8.6G checks) [conditional]
  ↓
S8: Compiled PDF (depends on polished .tex §7 + verified .bib §6 + venue from S8.5)
  ↓
S9: Reviewed manuscript (depends on compiled PDF §8 + venue expectations from S8.5)
      → 4 review personas in parallel (DP30) → convergence check (S9F)
  ↓
S9.5: Reviewer attack drill (2 personas parallel via DP14; depends on §9 reviewed manuscript)
      → convergence check (S9.5D), max 2 rounds
  ↓
S10: Submission package (3 artifacts parallel via DP15; depends on §8 PDF + §9 matrix + §9.5 fixes)
```

**Data-First:**
```
D0: Data inventory + quality report
  ↓
D1: EDA patterns + diagnostic plots + candidate effect sizes
  ↓
D2: ONE research question + 3-5 key papers + preliminary novelty confirmed
  ↓  (merge)
S0.5: Project sanity check on data-driven question
  ↓
S1.5: Research design (identification strategy if causal)
  ↓
S2: Gap analysis doc + verified BibTeX library
  ↓
S2.5-S10: Same as Idea-First
```

## Dead-End Detection

| Stage | Dependency | If Missing | Recovery |
|-------|-----------|------------|----------|
| D1 | Data inventory (D0) | Can't do EDA without knowing variables | Go back to D0 |
| D2 | EDA patterns (D1) | No candidate claims to select from | Go back to D1, dig deeper |
| S2 (data-first) | Research question from D2 | Can't search literature for undefined question | Go back to D2 |
| S2 (idea-first) | Research question from S1 | Can't define search terms | Go back to S1 |
| S3 | Gap analysis | Outline has no literature grounding | Go back to S2D |
| S4 | Claim outline | Writer produces rambling text | Go back to S3 |
| S5 | Results claims from outline | Figures don't prove anything specific | Go back to S3 §3B claims 6-8 |
| S6 | BibTeX library from S2 | No references to format | Go back to S2 |
| S7 | Complete manuscript | Polishing fragments creates inconsistency | Go back to S4 |
| S8 | Polished .tex + verified .bib | Compile errors cascade from upstream | Trace to source stage |
| S9 | Compiled PDF | Can't review what you can't read | Go back to S8 |
| S10 | Reviewed manuscript | Can't write cover letter without knowing paper's strength | Go back to S9 |
| S0.5 | Honest self-assessment | Proceeding with 2+ "No" answers without acknowledgment | Revisit the three questions. Either change scope or accept the risk explicitly. For Data-First: if data-driven question fails sanity check, return to D2 to select a different pattern/claim from the data. |
| S1.5 (causal) | Identification strategy | "We controlled for confounders" is not a strategy | Return to S1.5B. Find a source of exogenous variation OR downgrade to associational claim. |
| S2.5 | Competing paper analysis | Can't name what's different from published work | Return to S2. Identify your delta or accept incremental contribution. |
| S6.5 | Reproducibility check | Code doesn't run or data can't be accessed | Fix what you can. Document the rest as limitations in the paper. |
| S8.5 | Selected target journal | Formatting without knowing target venue = likely rework | Return to S8.5. Pick at least a provisional venue. |
| S8.6 | Chinese journal adapter | Journal qualification fails (wrong 栏目, no funding, author doesn't meet requirements) | If minor mismatch: adjust target journal within same tier. If major mismatch (different tier/discipline): return to S8.5 for re-selection. |
| S9.5 | Reviewer attack drill | Unfixed fatal flaw that reviewer will find | Fix the flaw before submission. Better to find it now than in peer review. |

## Web-Academic Gap Density Check

Compare two densities for the research topic after collecting both academic and web results:
- **Academic density:** papers found per keyword query via `literature_search.py`
- **Web density:** results found per keyword query via Tavily API

| Pattern | Interpretation |
|---------|---------------|
| High web, low academic | Emerging field / industry-driven — good opportunity, but weak literature base. Gap may be in bridging theory ↔ practice. |
| High academic, low web | Mature field with established literature but limited real-world penetration. Gap may be in translational/applied work. |
| Both low | Niche or very new — feasibility concern. |
| Both high | Competitive/hot field — need sharp differentiation. |

This analysis feeds into S2.5 (novelty check) and T2F (GAP matrix) with concrete evidence: "The field has high web coverage suggesting industry demand, but only {N} peer-reviewed papers, confirming a research-to-practice gap."

## Pathological Loops to Avoid

| Loop | Why It Happens | How to Break It |
|------|---------------|-----------------|
| **Explore-more-explore-more...** (Data-First) | EDA is infinite. "Just one more plot." | Hard cap: D1 stops after all 5 diagnostic plot types done + 10 candidate patterns. More exploration goes to future papers. |
| **Which-question-which-question...** (Data-First) | All patterns look publishable. Indecision. | D2C decision tree is dispositive. If tied, pick the largest effect size. |
| **Polish-review-polish-review...** | Perfectionism. Each polish pass reveals new issues. | Hard cap: 3 passes. **Early stop:** if two consecutive passes produce no new Critical/major items → CONVERGED → stop regardless of pass count. If Critical/major items remain by pass 3, the problem is structural (go back to S3), not cosmetic. |
| **Search-add-search-add...** | Snowballing is infinite. Every paper references more papers. | Hard cap: 3 snowball iterations. Beyond that you're reading for pleasure, not for the paper. |
| **Rewrite Methods for every reviewer** | Reviewer preferences conflict. | Pick the most rigorous reviewer's standard. Document the choice in the response matrix. |
| **Figure-remake loop** | "Just one more tweak." | Set a figure deadline: when captions are written and colors pass accessibility, freeze. Remakes go to supplementary. |
| **Strategy-downgrade-format loop** | S8.5 → S8 → S9 → "wrong journal" → downgrade → re-format | **Cap: 1 downgrade.** If you downgrade once and still want to downgrade again, submit with a "known venue risk" note. Infinite journal-hopping is procrastination. |
| **Review-fix-review-fix loop** | S9 peer review finds issues → fix → re-review → finds more issues → ... | Hard cap: 3 rounds. Use S9F Convergence Check (no new fatal flaws + ≤ 2 new non-fatal). If degenerating (same issues recurring), stop and fix first. After round 3, all remaining issues → limitations. |
| **Attack-fix-attack-fix loop** | S9.5 finds issues → fix → re-run attack → finds more issues → ... | Hard cap: 2 attack rounds. S9.5D convergence: Round 2 finds 0 new fatal + ≤ 2 new non-fatal → CONVERGED. Fix all "Fix Now" items from round 1. After round 2, stop. Every paper has weaknesses. |
