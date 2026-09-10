# Six-Dimension Scoring System

For standalone close-reading/archival selection (30 → 5 papers), score 0–100 across six dimensions. Research Orchestra nightly radar uses its own authoritative five-dimension rubric; do not replace or mix radar scores with this scale.

## Dimensions

| # | Dimension | Weight | What It Measures |
|---|-----------|:------:|------------------|
| 1 | Topic Match | 35 | How closely the paper aligns with core research questions |
| 2 | Methodological Value | 20 | Quality and applicability of methods (model design, training approach, evaluation) |
| 3 | Source Quality | 15 | Venue prestige (top conferences/journals), citation impact, credibility |
| 4 | Research Network Relevance | 10 | Connections to tracked authors, labs, institutions, or active collaborations |
| 5 | Applied/Engineering Value | 10 | Practical utility: code release, benchmarks, datasets, reproducibility |
| 6 | Archival Value | 10 | Long-term reference value: survey potential, foundational status, teaching utility |

## Scoring Rules

1. Each dimension is capped at its weight — no overshooting (no 11/10)
2. Total score must equal the sum of all six dimensions — recalculate, don't trust agent arithmetic
3. Dimension 1 is the gate: papers scoring <10 on Topic Match are auto-rejected regardless of other scores

## Agent Prompt Template

```
Score each paper on six dimensions (0-100 total):

1. Topic Match (max 35): [research keywords]
2. Methodological Value (max 20): model design, training, evaluation quality
3. Source Quality (max 15): venue, citations, credibility
4. Network Relevance (max 10): [tracked authors/labs/institutions]
5. Applied Value (max 10): code, benchmarks, datasets
6. Archival Value (max 10): long-term reference value

For each paper, output JSON:
{
  "title": "...",
  "scores": {"topic": X, "method": X, "source": X, "network": X, "applied": X, "archival": X},
  "total": X,
  "rationale": "one sentence"
}

Return top {N} papers by total score, sorted descending.
```

## Calibration

After 2-3 pipeline runs, review the score distribution:
- If top papers consistently score 90+, the rubric is too loose
- If no paper breaks 60, keywords may be too narrow
- Adjust weights based on user feedback
