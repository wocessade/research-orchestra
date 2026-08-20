# Stage C1: 选题与论点 [Strategist]

**Gate:** QC1 (BLOCK)
**Goal:** Define the paper topic and core arguments, ensuring feasibility and user alignment
**Needs Composers:** none

## Decisions

### Axis Routing
- **Language guard:** If axis resolves to `en`:
  - Warn: "Course-Assignment skill is Chinese-only. Proceeding with English topic may produce inconsistent quality."
  - Propose re-route to `academic-journal` (EN mode) OR user confirm to continue in Chinese mode with English topic
- **C1-PRE conditionals:**
  - If user has complete bibliography attached OR topic feasibility is self-evident (known-standard topic, e.g. "Analysis of XXX algorithm"):
    - Skip literature availability check
    - Mark `lit_check_skipped: true` in meta
  - Degenerate case: cursory search finds <10 papers on topic:
    - Record warning `[LOW-LIT-WARNING]` in meta
    - Do NOT block — user may still proceed with sparse literature
- **STOP-AND-ASK — Topic selection:**
  - If user specified a topic → confirm it
  - If user did NOT specify → present 3-5 candidate topics derived from course context, let user pick
- **STOP-AND-ASK — Argument confirmation:**
  - Present proposed thesis statement and 2-4 supporting arguments
  - User must confirm or revise before proceeding

### Composer Sequence
1. *(No composers — pure decision routing)*

## Gate

### QC1 Gate Checklist
- [ ] Topic is clearly defined and scoped to course requirements
- [ ] Core arguments / thesis statement are articulated
- [ ] Language is Chinese (or user explicitly confirmed override)
- [ ] Feasibility is assessed (literature exists OR override acknowledged)
- [ ] User has confirmed both topic and arguments

### Gate Failure Route
- Failed QC1 → identify failing sub-step → fix (redefine topic, rewrite arguments, etc.) → re-evaluate QC1
- 2 consecutive failures → STOP-AND-ASK: present user with diagnostic summary → route back to C1A (fresh start on topic selection)
