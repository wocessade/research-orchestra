# Stage T1: 选题开题 [Strategist]

**Gate:** QT1 (BLOCK)
**Goal:** Determine thesis topic viability, scope, and direction through literature landscape scanning and discipline-fit assessment.
**Needs Composers:** none

## Decisions

### Research-engine handoff preload

IF `.research/handoff/` exists at the thesis research root:

1. Load `ready_for_writing.md` before broad topic brainstorming when the user already has registered EXP evidence.
2. Map verified rows into 创新点 candidates; keep NEG forbidden claims out of asserted 创新点.
3. Still require explicit `user_confirmed: true` on `.paper/confirmed_contribution.md` (QT1).
4. See `../academic-research-engine/references/handoff-to-writing.md`.

ELSE → normal T1 landscape scan.

### Axis 0: Contribution Gate (P0)

Before QT1 pass:

1. Write `{paper_dir}/.paper/confirmed_contribution.md` (thesis 创新点 / contributions, 1–3).
2. User must confirm → `user_confirmed: true`.
3. Seed `{paper_dir}/.paper/contribution_experiment_map.md` (chapter / experiment plan).
4. Run `python ../academic-shared/contribution/contribution_check.py …`.
5. Load `../academic-shared/contribution/contribution-gate.md`.

Vague topics ("研究一下大模型应用") → Socratic narrow until claim-first contributions exist.


### Axis 1: Degree Differentiation
```
if degree == bachelor:
    → basic landscape scan (1 round, 10-15 high-level papers)
    → focus on feasibility and clear scope
    → no gap matrix required
elif degree == master:
    → deep scan with gap matrix + competitor analysis (2-3 rounds)
    → 20-30 papers minimum
    → historical evolution of the field required
```

### Axis 2: Saturation Classification
Classify the candidate topic area:
- **Hot** (50+ papers in last 2 years): flag as high-competition; recommend niche specialization or cross-domain angle
- **Moderate** (10-50 papers): standard depth; feasible with clear contribution boundary
- **Underexplored** (<10 papers): flag as high-risk; recommend validating problem significance before proceeding
- **Adjacent applications** (topic in domain A applied to domain B): recommend domain B expert consultation

### Axis 3: Template Routing
```
if user shares a template file (.docx/.tex/.pdf):
    → Option A: extract structure, reproduce format
elif user describes university requirements:
    → Option B: parse requirements into stage checklist
elif user has no template/no description:
    → Option C: use standard format (default university thesis template)
```

### Axis 4: Candidate Provenance Tags
Tag the topic source for traceability:
- `[User Interest]` — self-proposed by student
- `[Literature Gap]` — identified from preliminary reading
- `[Advisor Direction]` — assigned by supervisor
- `[Cross-Domain]` — spans multiple disciplines
- `[Application]` — applies existing method to new domain

### Axis 5: Discipline-Fit Assessment
```
if topic deviates from declared major:
    → emit [WARNING: discipline-mismatch]
    → ask user to confirm or provide justification
    → if justification insufficient → recommend pivot or scope adjustment
```

### Axis 6: Pre-specified Topic Validation
```
if user already has a specific topic:
    → run focused search (5-10 papers) to validate feasibility
    → if validation fails → recommend adjustment or alternatives
    → if validation passes → proceed with confidence note
```

### Axis 7: Advisor Feedback Loop
```
max_rounds = 3
for round in 1..max_rounds:
    present findings to user
    ask user to share with advisor
    if user returns feedback:
        incorporate and proceed to next round
    else:
        → STOP-AND-ASK (user has not consulted advisor)
```

## Gate

### QT1 Gate Checklist
- [ ] Topic is clearly stated as a single sentence
- [ ] Saturation classification completed and documented
- [ ] Provenance tag assigned
- [ ] Discipline-fit assessment passed (or warning acknowledged)
- [ ] Advisor consulted (or STOP-AND-ASK not triggered)
- [ ] Degree-appropriate depth confirmed
- [ ] Candidate provenance documented
- [ ] `confirmed_contribution.md` with `user_confirmed: true` (contribution_check.py OK)
- [ ] `contribution_experiment_map.md` seeded for planned chapters/experiments

### Gate Failure Route
```
if any checklist item fails:
    → report specific failure reason to user
    → offer remediation options
    → user must acknowledge before proceeding past QT1
if discipline-mismatch warning not acknowledged:
    → BLOCK — cannot proceed
if advisor loop exhausted without consultation:
    → BLOCK — user must confirm consultation before T2
```
