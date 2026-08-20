# Discipline-Specific Writing Patterns

Different fields have different argumentation skeletons. Match your paper to your discipline's expectations. Auto-loaded at S4 (writing) and S7 (polish).

## CS / Engineering
Pattern: System description → Experimental setup → Benchmark results → Ablation studies → Limitations
- The "system" section replaces a traditional Methods section
- Expectation: reproducibility = code available. Without code, claims are unverifiable.
- Common rejection reason: no ablation/sensitivity analysis. Readers expect you to remove components and show each matters.

## Biomedicine
Pattern: Background mechanism → In vitro evidence → In vivo evidence → Clinical relevance → Limitations
- Hierarchy of evidence: in vivo > in vitro. A pure in vitro paper has lower venue ceiling.
- Common rejection reason: mechanism proposed without experimental manipulation. Correlation is not mechanism.

## Social Science
Pattern: Theory → Research design → Main effects → Heterogeneity analysis → Mechanisms → Limitations
- Identification strategy is the centerpiece. "We controlled for..." is not a strategy.
- Expectation: robustness checks (alternative specifications, sub-samples, placebo tests).
- Common rejection reason: endogeneity not addressed. Every observational finding faces "but what about unobserved confounds?"

## Environmental / Geoscience
Pattern: Phenomenon description → Data sources → Spatial/temporal analysis → Attribution → Implications → Limitations
- Maps and time series are primary evidence, not illustrations
- Common rejection reason: confounding between spatial and temporal variation not disaggregated

## Economics
Pattern: Motivation → Institutional context → Data → Identification strategy → Main results → Robustness → Mechanisms → Policy implications
- Identification strategy section is often as long as Results
- Common rejection reason: weak instrument (F < 10) or parallel trends violation

## Usage

These are skeletons — your S3 outline should already follow your discipline's structure. If your paper spans disciplines (e.g., computational social science), pick the primary audience's pattern and acknowledge methodological debts to the secondary field.
