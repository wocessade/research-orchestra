# Stage D2: Research Question Selection [Strategist]

**Gate:** QD2 (BLOCK) — ONE research question must be selected.
**Goal:** Transform D1 patterns into a single, precise, novel, and answerable research question.
**Needs Composers:** none

## Decisions

### Axis Routing
Single-agent decision tree (NOT Mode B x3 redundancy from DP25; data constraints provide natural validation). No axis/passport branching.

### Sub-Step Execution Order
D2A (Candidate Claims from Patterns) → D2B (Targeted Novelty Check) → D2C (Research Question Selection)

Strictly sequential. Each sub-step depends on the prior.

### Elimination Logic (D2A, lines 49-55)
Remove candidates where:
- Data clearly cannot support them (e.g., outcome variable has 57% missingness, no variation in key predictor)
- Alternative explanation is fatal and unresolvable (D1C findings)
- User confirms it is a known finding in the field
- User says the claim is implausible given domain knowledge

Keep at most 3 candidates for further evaluation.

### STOP-AND-ASK Points
- **D2A (line 30):** For each candidate claim, present to user and ask: (1) does this claim make sense given your domain knowledge? (2) Are there obvious confounds? (3) Is this claim publishable or well-known to domain experts?
- **D2B (line 101):** For each candidate, present novelty assessment and ask which direction seems more promising.
- **D2C (line 165):** Present final research question for explicit user confirmation.

### Passport Update
Write passport fields:
- `research_question`: one-sentence research question
- `research_question_source`: "data-first"
- `key_variables.outcome`, `key_variables.predictor`, `key_variables.covariates`

## Gate

### QD2 Gate Checklist
- [ ] Candidate claims extracted from D1 patterns (D2A)
- [ ] Domain plausibility confirmed by user (D2A)
- [ ] Targeted novelty check completed (D2B) — searches run for each candidate
- [ ] Gap confirmed: at least one candidate has a clearly identifiable gap
- [ ] Candidates ranked and one selected (D2C)
- [ ] Research question is ONE sentence, specific, and testable with available data
- [ ] Data limitations documented
- [ ] `{output_dir}/D2_research_question.md` written
- [ ] User explicitly confirmed the selected question
- [ ] Passport fields written (including research_question for downstream stages)
- [ ] Stage completion log appended

### Gate Failure Route
QD2 is BLOCK — must select a research question to continue.

1. **All candidates fail novelty check** (no gap, all already published, user confirms no novelty) → (a) return to D1 to find more patterns, (b) relax novelty standards (replication study or context extension may be publishable), (c) STOP-AND-ASK whether to consider data-paper route.
2. **User rejects all candidates** → STOP-AND-ASK: ask if new data is available, or switch to Idea-First entry.
