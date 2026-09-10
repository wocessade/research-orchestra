# Stage T5: 毕业论文审查 [Strategist]

**Gate:** QT5 (BLOCK)
**Goal:** Run comprehensive multi-agent audit on the complete thesis draft to identify errors, inconsistencies, and quality issues.
**Needs Composers:** [paper-audit-orchestration, factual-accuracy-check, de-ai-detect]

## Decisions

### Axis 1: Tier Routing
Route thesis to appropriate audit tier based on degree and discipline:

```
if degree == "bachelor" AND discipline == "general" (人文社科/经管/教育/艺术):
    tier = "humanities_bachelor"
    agent_count = 9

elif degree == "bachelor" AND discipline == "stem" (理工/医学/农学):
    tier = "stem_bachelor"
    agent_count = 10

elif degree == "master":
    tier = "master"
    agent_count = 11

else:
    → STOP-AND-ASK — cannot classify
    → user must specify degree and discipline
```

### Axis 2: Agent Composition by Tier

**Humanities Bachelor (9 agents):**
1. 结构与逻辑 (Structure & Logic)
2. 论证质量 (Argument Quality)
3. 文献引用 (Citation Quality)
4. 语言表达 (Language & Expression)
5. 格式规范 (Format Compliance)
6. 摘要与结论一致性 (Abstract-Conclusion Alignment)
7. 图表规范性 (Figure & Table Standards)
8. 学术伦理 (Academic Ethics)
9. 创新点评估 (Originality Assessment)

**STEM Bachelor (10 agents):**
All of the above, plus:
10. 数据与方法 (Data & Methodology)

**Master (11 agents):**
All of the above (10), plus:
11. 理论深度 (Theoretical Depth)

### Axis 3: Agent Error Handling
```
for each agent in audit_run:
    try:
        agent.execute()
    catch agent_failure:
        failure_count += 1
        if failure_count == 1:
            → launch replacement agent (same role, different instance)
        elif failure_count == 2:
            → replacement also fails
            → flag [AGENT-FAILED: agent_role]
            → continue without this agent's output
        elif failure_count >= 3:
            → STOP-AND-ASK
            → present: failed agents, impact assessment
            → user decides: retry, skip, or manual review

agent_failure detection:
    - agent returns empty report
    - agent returns error code
    - agent timeout (no response within threshold)
    - agent output is incoherent/self-contradictory
```

### Axis 4: Report Aggregation
```
aggregation_rules:
    - Collect all agent reports
    - Deduplicate overlapping findings (same issue flagged by multiple agents)
    - Priority merge: keep highest severity rating for deduplicated issues
    - Categorize by severity: Critical, Major, Minor
    - Count findings per category
    - Generate summary: top 5 most critical issues
```

### Axis 5: Audit Report Delivery
```
delivery_format:
    1. Executive summary (3-5 sentences)
    2. Severity distribution (Critical: N, Major: N, Minor: N)
    3. Critical issues (detailed, with location references)
    4. Major issues (categorized by chapter)
    5. Minor issues (bulleted list)
    6. Failed agents list (if any)
    7. Grading: quality_score (1-100) based on issue density and severity
```


### Evidence Ledger Audit

Before accepting the current draft, the existing factual/content reviewer loads `../academic-shared/evidence-ledger/ledger-protocol.md`. Compare current prose with the ledger, including uncited numerical, causal, comparative and novelty claims; inspect sources/run artifacts and record pending/orphan/mismatch without fabricating support. Check all core claims and changed claims, record other unchecked items, and merge findings into the cumulative review register. Write `{output_dir}/evidence_audit.md`; schema validity and DOI identity alone do not establish support.

## Gate

### QT5 Gate Checklist
- [ ] Current-manuscript evidence audit completed; core and changed claims checked, missing support recorded in the cumulative issue register
- [ ] Tier correctly identified and routed
- [ ] All agents executed (or failures documented)
- [ ] Agent failures within tolerance (< 3 failures)
- [ ] Report aggregated and deduplicated
- [ ] Critical issues documented
- [ ] Quality score computed
- [ ] Report delivered to user

### Gate Failure Route
```
if 3+ agent failures:
    → BLOCK — STOP-AND-ASK for user decision
if tier cannot be determined:
    → BLOCK — user must specify degree and discipline
if audit produces no findings (suspicious — indicates all agents failed silently):
    → BLOCK — re-run with verbose mode
    → if still empty → manual review required
```
