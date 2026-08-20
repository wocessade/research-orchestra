# Evidence Hierarchy Grading

**Purpose:** Operationalize GRADE and the 7-level Study Design Hierarchy for literature quality assessment.
**Used by:** C2 (Literature Search — quality matrix enhancement), C3 (Writing — claim-to-citation alignment), factual_accuracy agent

## 7-Level Study Design Hierarchy

| Level | Study Design | Bias Risk | Example |
|-------|-------------|-----------|---------|
| I | Systematic review / meta-analysis of RCTs | Lowest | Cochrane Review |
| II | Individual RCT with narrow CI | Low | Parallel-arm drug trial |
| III | Non-randomized controlled (cohort, case-control) | Moderate | Prospective cohort study |
| IV | Case series, cross-sectional | Moderate-High | Prevalence survey |
| V | Animal studies, in vitro | High | Mouse model, cell line study |
| VI | Expert opinion, textbook | Highest | Narrative review, textbook chapter |
| VII | Unpublished data, personal communication | Not rateable | "Data on file", personal correspondence |

## GRADE Quality Ratings

Convert the initial Level to a GRADE rating, then apply adjustments:

### Initial GRADE by Level
| Level | Initial GRADE |
|-------|--------------|
| I | HIGH |
| II | HIGH |
| III | MODERATE |
| IV | LOW |
| V | LOW |
| VI | VERY LOW |
| VII | VERY LOW |

### Upgrade Factors (+1 level each, max +2)
- **Large effect** (RR > 2 or RR < 0.5, Cohen's d > 0.8)
- **Dose-response gradient** — increasing exposure associated with increasing effect
- **Plausible confounding** would reduce demonstrated effect (i.e., the true effect is likely larger than observed)

### Downgrade Factors (-1 or -2 levels each)
| Factor | -1 | -2 |
|--------|-----|-----|
| Risk of bias | Serious limitations (no blinding, incomplete outcome data) | Very serious limitations (no randomization, no control) |
| Inconsistency | Moderate heterogeneity (I² 50-75%) | High heterogeneity (I² > 75%), contradictory results |
| Indirectness | Population/intervention/outcome differs from target | Multiple or major indirectness issues |
| Imprecision | Wide CI includes both benefit and harm | Very wide CI, small sample size, few events |
| Publication bias | Funnel plot asymmetry suspected | Strong evidence of publication bias (missing studies) |

### Final GRADE Categories
| Final Grade | Definition |
|-------------|-----------|
| HIGH | Further research is very unlikely to change confidence |
| MODERATE | Further research is likely to have an important impact |
| LOW | Further research is very likely to change confidence |
| VERY LOW | Any estimate is very uncertain |

## Usage in Quality Assessment

For each included study (after quality assessment), assign an evidence grade:

```
{source_id, initial_level, upgrades[], downgrades[], final_grade}
```

### Example
```yaml
source_id: "smith2023"
initial_level: II           # Individual RCT
upgrades: ["large_effect"]  
downgrades: ["imprecision"] # -1 for wide CI
final_grade: HIGH           # HIGH +1-1 = HIGH
```

### Evidence Distribution

In quality assessment, report the aggregate distribution:

```
## Evidence Grade Distribution
- HIGH (Grade I-II): 12 篇
- MODERATE (Grade III-IV): 8 篇  
- LOW (Grade V-VI): 5 篇
- VERY LOW (Grade VII): 2 篇
```

Use this distribution to:
1. **Weight conclusions** — claims supported mainly by LOW/VERY LOW evidence should be flagged as tentative
2. **Identify evidence gaps** — a well-studied area should have majority HIGH/MODERATE evidence; if it doesn't, the research gap is partly "insufficient reliable evidence"
3. **Support recommendations** — high-confidence recommendations should trace to HIGH-grade evidence
