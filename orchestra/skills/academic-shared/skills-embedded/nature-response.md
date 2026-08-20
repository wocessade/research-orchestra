# Nature Reviewer Response (Embedded)

**Source:** `nature-response` v0.1.0 beta | **Snapshot:** 2026-06-06
**Pipeline usage:** S11 (Post-Submission), S12 (R&R Resubmission)

## Default Stance
- Preserve each reviewer comment faithfully before responding
- Every concern must be answered, cross-referenced, or marked as unresolved
- Map every response to: manuscript evidence, revision location, justified disagreement, or `AUTHOR_INPUT_NEEDED`
- Do NOT invent experiments, analyses, citations, line numbers, or figure panels
- Prefer concise, evidence-linked replies over long defensive explanations
- When disagreeing: acknowledge concern first, give scientific reason

## Response Structure
```
### Reviewer 1, Comment 1 (R1.1)
**Reviewer Comment:** [exact quote]
**Author Response:** [response]
**Changes Made:** [specific manuscript changes]
**Location:** [section, line numbers]
```

## Workflow
1. Identify decision type (minor/major/R&R/transfer)
2. Extract editor instructions → assign IDs (E.1, E.2, ...)
3. Split reviewer comments → assign IDs (R1.1, R1.2, R2.1, ...)
4. Classify each by: category, severity, action label, readiness state
5. Draft responses
6. Map each claimed change to manuscript location
7. Flag missing author input
8. QA: completeness, traceability, factuality, tone
