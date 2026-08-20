# Stage T3: 研究方法 [Strategist]

**Gate:** QT3 (BLOCK)
**Goal:** Determine and document the research methodology, ensuring it is appropriate for the thesis type, degree level, and research questions.
**Needs Composers:** none

## Decisions

### Axis 1: Thesis Type Classification
Classify thesis into one dominant type:

1. **Empirical (实证研究)**
   - Characteristics: data-driven, hypothesis testing, quantitative/qualitative analysis
   - Methodology chapter structure: research design → data collection → analysis method → validity/reliability
   - Typical fields: social sciences, education, management, psychology, medicine

2. **Engineering (工程技术)**
   - Characteristics: system design, implementation, algorithm development, performance evaluation
   - Methodology chapter structure: system architecture → algorithm design → implementation → evaluation metrics
   - Typical fields: computer science, engineering, information systems

3. **Humanities (人文社科)**
   - Characteristics: textual analysis, theoretical argument, historical research, critical analysis
   - Methodology chapter structure: theoretical framework → analytical approach → source/material → interpretation method
   - Typical fields: literature, philosophy, history, arts, law

```
classification_rules:
    if thesis combines multiple types:
        → note hybrid type
        → select dominant type for structure
        → flag [HYBRID: secondary_type] for composer awareness
    classification confidence < 0.8:
        → STOP-AND-ASK user to confirm
```

### Axis 2: Type Confirmation
```
[STOP-AND-ASK]
Present to user:
    - Classified thesis type
    - Methodology chapter outline (section headings)
    - Rationale for classification

User must confirm before T3 proceeds.
If user disagrees → adjust classification and re-present.
Max adjustment rounds: 2 → force user to final choice.
```

### Axis 3: Degree-Level Depth
```
if degree == bachelor:
    depth_requirement = "understand method"
    → describe the chosen method
    → explain why it is appropriate
    → cite 2-3 supporting references
    → demonstrate basic competence

if degree == master:
    depth_requirement = "informed choice with justification"
    → compare 2-3 alternative methods
    → justify choice over alternatives (with criteria)
    → discuss limitations and mitigations
    → cite 5+ methodological references
    → demonstrate critical understanding
```

### Axis 4: Advisor Feedback Loop
```
max_rounds = 3
for round in 1..max_rounds:
    present methodology chapter draft to user
    ask user to share with advisor
    if feedback received:
        if feedback is minor → incorporate and proceed
        if feedback requests major restructuring:
            → assess impact on T4 timeline
            → inform user of timeline consequences
            → proceed on user approval
    else:
        → STOP-AND-ASK
        → user must confirm advisor consulted

Advisor feedback severity levels:
    - Critical: methodology fundamentally unsuitable → restart T3
    - Major: methodology needs significant adjustment → revise and re-consult
    - Minor: formatting, clarification → incorporate and proceed
```

## Gate

### QT3 Gate Checklist
- [ ] Thesis type classified and user-confirmed
- [ ] Methodology chapter outline drafted
- [ ] Degree-appropriate depth achieved
- [ ] Method choice justified (master: compared to alternatives)
- [ ] Advisor consulted (or STOP-AND-ASK resolved)
- [ ] Methodology aligns with research questions from T1
- [ ] Hybrid type noted if applicable

### Gate Failure Route
```
if thesis type unconfirmed by user:
    → BLOCK — user confirmation required
if advisor feedback critical (fundamentally unsuitable):
    → BLOCK — restart T3 with new methodology
if max advisor rounds exhausted without consultation:
    → BLOCK — must confirm consultation
if method does not align with T1 research questions:
    → BLOCK — revisit T1 or adjust method
```
