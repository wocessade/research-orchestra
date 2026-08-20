# Quick Routing by Entry Type

| Entry Type | First Stage | Description |
|---|---|---|
| **I have a topic, need thesis** | T1 | T1(topic + task document + opening report) -> T1.5(data if hasData) -> T2(lit review) -> T3(methodology) -> T4(writing) -> T5(review) -> T6(convergence) -> T6.5(blind review if master) -> T7(defense) |
| **I have data, need thesis** | T1 | T1(topic with data context) -> T1.5(data exploration) -> T2(lit review) -> ... (same as above) |
| **Chinese thesis (bachelor)** | T1 | Bachelor-level: 15K+ words, 20+ references, 9 review agents. See gate QT4 for full requirements. |
| **Chinese thesis (master)** | T1 | Master-level: 30K+ words, 50+ references, blind review preparation, 11 review agents. |

## P0 contribution gate (thesis)

| Stage | Requirement |
|-------|-------------|
| T1 / QT1 | `.paper/confirmed_contribution.md` confirmed; seed experiment/chapter map |
| T4 | Takeaways in empirical chapters; Final 绪论 after core results |
| Protocol | `../academic-shared/contribution/contribution-gate.md` |

## P1 (thesis)

| Stage | Artifact |
|-------|----------|
| T2 | citation_support_bank.md |
| T4 | issues.csv + results-backfill |
| T6 | rewrite_matrix.md |

## Research engine → thesis

| When | Action |
|------|--------|
| `.research/handoff/` present | T1 preload verified evidence; still QT1 confirm contributions |
| Sync | `../academic-research-engine/scripts/handoff_sync.py --module academic-thesis` |
