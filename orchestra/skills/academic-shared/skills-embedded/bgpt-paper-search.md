# BGPT Paper Search (Embedded)

**Source:** `bgpt-paper-search` | **Snapshot:** 2026-06-06
**Pipeline usage:** S2 — structured experimental data extraction from papers (systematic reviews)

## Purpose
Extract structured experimental data from academic papers for systematic reviews.
Used when the pipeline needs quantitative data extraction from multiple papers
(experimental results, statistical data, methodological details).

## Workflow
1. Input: list of papers (DOIs or titles)
2. For each paper: extract experimental conditions, results, statistics
3. Output: structured table with consistent columns across papers

## Example Extraction Schema

For a systematic review of ML model performance on medical imaging:
```
| DOI | Task | Dataset (N) | Model | Metric | Value | 95% CI | Reported p |
|-----|------|-------------|-------|--------|-------|--------|------------|
| 10.xxx | Pneumonia detection | ChestX-ray14 (112K) | ResNet-152 | AUC | 0.86 | [0.84, 0.88] | <0.001 |
```

The schema MUST be defined before extraction begins. All papers in the review use the same columns. Missing data → leave cell empty, do not invent.

## Anti-Pattern: Too Many Variables
**Symptoms:** Extraction schema has 40+ columns — every possible variable from every paper. **Fix:** Define a minimal core schema (task, dataset, N, model, primary metric, CI) plus 2-3 domain-critical columns. Everything else goes in a free-text `notes` column.

## Output Format
- CSV or Markdown table with identical columns across all papers
- Missing values empty (not "N/A" or "—")
- DOIs as hyperlinks in Markdown, plain text in CSV
