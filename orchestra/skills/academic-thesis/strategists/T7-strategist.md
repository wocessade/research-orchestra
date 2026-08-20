# Stage T7: 答辩准备 [Strategist]

**Gate:** QT7 (BLOCK)
**Goal:** Prepare defense materials: presentation slides, defense script, and Q&A preparation simultaneously via parallel agents.
**Needs Composers:** none

## Decisions

### Axis 1: DP21 — Three Parallel Agents
```
Launch 3 agents in parallel:
    agent_ppt:      Presentation slides    (PPT composer)
    agent_script:   Defense script         (spoken presentation)
    agent_qa:       Q&A preparation        (anticipated questions + answers)

parallel_execution:
    - All 3 agents run simultaneously (no sequential dependency)
    - Each agent receives full thesis content as input
    - Each agent operates independently
    - [DP21-PARALLEL] flag to indicate parallel mode
```

### Axis 2: Degree-Differentiated

**Bachelor:**
```
slides:
    target: 15+ slides
    structure:
        1. Title slide (1)
        2. Background & significance (2-3)
        3. Literature review highlights (2-3)
        4. Methodology (2-3)
        5. Results & analysis (3-4)
        6. Conclusion & contributions (1-2)
        7. Q&A / Thank you (1)

script:
    target_length: 15-20 minutes spoken
    pacing: 1-1.5 minutes per slide
    tone: explanatory, focused on demonstrating competence

Q&A:
    total_questions: 15 minimum
    format: 6 categories × minimum 2 questions each + 3 general
```

**Master:**
```
slides:
    target: 20+ slides
    structure:
        1. Title slide (1)
        2. Background & significance (2-3)
        3. Literature review & gap (2-3)
        4. Theoretical framework (1-2)
        5. Methodology (2-3)
        6. Results & analysis (4-5)
        7. Discussion (2-3)
        8. Conclusion, contributions & limitations (2-3)
        9. Future work (1)
        10. Q&A / Thank you (1)

script:
    target_length: 20-30 minutes spoken
    pacing: 1-1.5 minutes per slide
    tone: scholarly, focused on contribution depth and critical thinking

Q&A:
    total_questions: 25 minimum
    format: 6 categories × minimum 3 questions each + 7 general
```

### Axis 3: Q&A Categories (Both Levels)

| # | Category | Description |
|---|----------|-------------|
| 1 | 研究动机与意义 | Motivation and significance |
| 2 | 文献综述与理论 | Literature review and theory |
| 3 | 研究方法 | Research methodology |
| 4 | 结果与讨论 | Results and discussion |
| 5 | 创新点与贡献 | Innovation and contribution |
| 6 | 局限性与未来工作 | Limitations and future work |

For each question, provide:
- Expected answer (2-3 sentences)
- Connection to thesis content
- Difficulty level (basic/intermediate/advanced)

### Axis 4: Cross-Validation
After all 3 agents complete, run 4 validation checks:

1. **PPT-Script Alignment**
   ```
   check: every slide topic appears in script
   if misalignment detected:
       → flag [MISALIGN: slide N not in script]
       → either add to script or remove from slides
   ```

2. **Q&A-T5 Coverage**
   ```
   check: Q&A questions cover all T5 Critical issues
   if T5 Critical issue not addressed in Q&A:
       → flag [QA-GAP: T5-critical not covered]
       → add at least 1 Q&A item per uncovered Critical issue
   ```

3. **Q&A-Thesis Verification**
   ```
   check: each Q&A answer is factually supported by thesis content
   if answer contradicts or is unsupported:
       → flag [QA-FACT-ERROR]
       → correct answer to align with thesis
   ```

4. **Timing Check**
   ```
   check: script_estimated_duration is within target range
   if script too short:
       → flag [TIMING-TOO-SHORT]
       → recommend elaboration on key points
   if script too long:
       → flag [TIMING-TOO-LONG]
       → recommend condensing background/less critical sections
   ```

### Axis 5: T7G — User Choice
```
present options to user:
    A) "交付材料" — Deliver materials as-is
    B) "模拟答辩" — Run mock defense (user practices, agents listen and give feedback)
    C) "逐项审查" — Review specific materials (user selects PPT/Script/Q&A for detailed review)

if user chooses B (mock defense):
    → launch mock_defense mode
    → user speaks through presentation
    → agents evaluate: pacing, completeness, clarity
    → feedback report generated

if user chooses C (review specific):
    → present material list: [PPT, Script, Q&A]
    → user selects one or more
    → detailed review of selected materials

if user chooses A or unspecified:
    → deliver all materials
```

### Axis 6: Delivery Package
```
output_package:
    - thesis_defense.pptx    (presentation slides)
    - thesis_defense_script.md  (spoken script)
    - thesis_defense_qa.md      (Q&A preparation document)
    - thesis_defense_checklist.md (cross-validation results)

file naming: use thesis_short_title or generic if unavailable
```

## Gate

### QT7 Gate Checklist
- [ ] All 3 parallel agents executed (PPT, Script, Q&A)
- [ ] Degree-appropriate targets met (slide count, script length, Q&A count)
- [ ] All 6 Q&A categories populated
- [ ] Cross-validation: PPT-Script alignment passed
- [ ] Cross-validation: Q&A-T5 coverage passed
- [ ] Cross-validation: Q&A-Thesis fact-check passed
- [ ] Cross-validation: Timing check passed (or flagged)
- [ ] T7G user decision made
- [ ] All deliverables generated

### Gate Failure Route
```
if any cross-validation check fails:
    → SOFT BLOCK — must fix flagged issues before delivery
    → user may override individual flags
if 2+ agents fail:
    → BLOCK — stop, diagnose, retry
    → if persistent → manual preparation recommended
if Q&A-T5 gap remains unresolved:
    → SOFT BLOCK — defense committee may ask about T5 Critical issues
    → recommend at minimum adding answers to all Critical issues
```
