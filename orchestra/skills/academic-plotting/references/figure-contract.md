# Figure contract (before any code or prompt)

## Required fields

```yaml
figure_id: fig:overview
filename: figures/fig_overview
figure_class: evidence-result | concept-method
role: overview | method-detail | result-summary | ablation | failure-analysis | teaser | appendix
message: "One sentence claim the figure supports."
core_conclusion: "The conclusion this figure must make defensible."
evidence_hierarchy:
  hero_evidence: "Primary panel / visual"
  supporting_evidence: "Secondary panels"
entities: []
relationships: []
layout: left-to-right pipeline | grouped bars | line plot | heatmap | ...
backend: deterministic-plot | latex-table | generated-image | tikz | hybrid
source: "CSV/log/script/prompt path"
backup: "optional TikZ/SVG fallback"
caption_takeaway: "Sentence the caption must communicate."
evidence_status: exact-data | illustrative-only | qualitative-example
reviewer_risk: "What a skeptic may attack"
journal_width: single | double
```

Store plans in `figures/figure_plan.md` and/or `figures/figure_specs.yaml`.
Also mirror into `.paper/figure_inventory.md` for academic-latex sessions.

## Contract steps

1. Core conclusion (one sentence).
2. Panel map — drop panels without unique evidence.
3. Evidence hierarchy — hero vs support vs control vs failure.
4. Source traceability.
5. Reviewer risk before styling.
6. Caption takeaway before polish.

## Role taxonomy

| Role | Class | Typical backend |
|------|-------|-----------------|
| overview / framework / pipeline / teaser | concept-method | generated-image or TikZ |
| method-detail | concept-method | generated-image / hybrid |
| result-summary / ablation | evidence-result | deterministic plot or table |
| difficulty breakdown | evidence-result | heatmap / faceted bars |
| failure-analysis | evidence-result | qualitative grid + labels |

Decorative figures that do not earn space are forbidden.
