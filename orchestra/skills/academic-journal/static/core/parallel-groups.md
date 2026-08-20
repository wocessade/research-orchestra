# Cross-Stage Parallelism

Stages without mutual dependencies can run concurrently:

| Parallel Group | Stages | Rationale |
|---------------|--------|-----------|
| Group A | S5 + S6 + S6.5(partial) | After S4 completes, launch S5, S6, and S6.5A/C (data backup + seed check) in parallel. S6.5B (code regeneration check) is deferred until S5 finishes — it needs figure-generation code that S5 produces. Run S6.5B after S5 completes, then verify the full Q6.5 gate. |
| Group B | S8.5 with S4-S7 | S8.5 depends ONLY on S2.5 novelty data. It can start BACKGROUND RESEARCH (reading journal homepages, checking scope) after S2.5. The formal S8.5 stage document loads only after Q7 passes — loading both S4-S7 and S8.5 simultaneously would race on `.pipeline_state.json` writes. S8.5's position after S7 in the pipeline is not just logical ordering but also state-safety ordering. |
| Group C | S8.6A + S8.6B | If the user has provided journal guidelines AND 2-3 sample papers before reaching S8.6, run journal qualification (8.6A) and reverse engineering (8.6B) in parallel (DP16). All other S8.6 sub-stages are sequential. |
| Group D | C2B + C2C + C2D + C2E (DP17) | During C2 Literature Search, launch 4 agents in parallel: English tech papers (C2B), policy/legal sources (C2C), Chinese-language papers (C2D), web context/Tavily (C2E). C2A (search protocol) runs sequentially before parallel dispatch. Independent search domains with no cross-dependencies. See `dispatch-points.md` DP17. |
| Group E | C4 review (DP18) | During C4 Review, dispatch all 6 review agents via evaluate module. Independent review lenses on the same draft. See `dispatch-points.md` DP18. |
| Group F | T2B + T2C + T2D (DP19) | During T2 Literature Review, launch 3 agents in parallel: English academic sources (T2B), Chinese academic sources (T2C, incl. 硕博论文), policy/industry/grey literature (T2D). Independent search domains with no cross-dependencies. T2A (search protocol) runs sequentially before the parallel dispatch. Cross-language deduplication runs after all agents complete. See `dispatch-points.md` DP19. |
| Group G | T5A-T5D (DP20) | During T5 Review, dispatch all 9-11 agents (tier-dependent) via evaluate module. Independent review lenses on the same thesis draft. Consensus via evaluate module's merge protocol. See `dispatch-points.md` DP20. |
| Group H | T7B + T7C + T7D (DP21) | During T7 Defense Preparation, launch 3 agents in parallel: PPT generation, defense script, anticipated Q&A. Cross-validated at T7E after all complete (PPT↔script slide markers, Q&A↔thesis weaknesses). See `dispatch-points.md` DP21. |

## Partial Failure Handling

When a parallel group has agents that fail, don't discard successful results. Handle failures proportionally:

### Decision Protocol

```
Parallel group completes. How many agents failed?
├── 0 failures → Normal flow. Evaluate all gates, proceed.
├── 1 failure → Retry the failed agent once (same prompt, same inputs).
│   ├── Retry succeeds → Merge with other results, proceed normally.
│   └── Retry fails → Classify the failed agent's dependency:
│       ├── No downstream dependency (e.g., one figure in S5, one search domain in C2/D/T2)
│       │   → Skip. Log the gap. Proceed with remaining results.
│       └── Has downstream dependency (e.g., S6 citation check, T5 logic review)
│           → Degrade to manual checklist. Present the checklist to user with:
│             "Agent [name] failed after retry. Here's what it would have checked.
│              Please verify these items manually before proceeding."
│             Mark gate as COND. BLOCK — user must confirm manual check complete.
│             (This degrade path applies to non-evaluate agents only. Evaluate/review
│              agents [DP18/DP20] use the replacement-agent protocol in fallback.md.)
└── 2+ failures → STOP-AND-ASK.
    "Multiple parallel agents failed: [list names + brief reason for each].
     Successful results: [list what was saved].
     Options:
     A) Retry all failed agents (preserves successful results)
     B) Retry the entire parallel group from scratch (discards all results)
     C) Degrade all failed to manual checks and proceed
     D) Abort pipeline and exit"
```

### Per-Group Failure Impact

| Parallel Group | 1 Failure — Skip OK? | 1 Failure — Degrade To | 2+ Failures |
|---------------|---------------------|----------------------|-------------|
| Group A (S5+S6+S6.5) | S5 figure: skip. S6.5A/C: skip. | S6: manual citation spot-check (10% sample). S6.5B: manual code regeneration review. | STOP-AND-ASK |
| Group B (S8.5 with S4-S7) | N/A — S8.5 runs alone, not truly parallel | N/A | N/A |
| Group C (S8.6A+S8.6B) | Either: skip that sub-stage | N/A — both are advisory enhancements | STOP-AND-ASK |
| Group D (C2A+C2B+C2C+C2D) | Any one search domain: skip. C2D (DeepSeek): skip — fact-sourcing only, not a citation source. | N/A — independent domains, skip is safe | STOP-AND-ASK (≥2 of C2A/C2B/C2C missing = significant gap; C2D alone not critical) |
| Group E (C4A+C4B+C4C) | C4 review agents: see `fallback.md` §审稿 agent 降级策略 (C4/T5 protocol). | N/A — evaluate agents follow fallback.md replacement-agent protocol | STOP-AND-ASK |
| Group F (T2B+T2C+T2D) | Any one search domain: skip | N/A — independent domains, skip is safe | STOP-AND-ASK (≥2 domains missing is a significant gap) |
| Group G (T5A+T5B+T5C+T5D) | T5 review agents: see `fallback.md` §审稿 agent 降级策略 (C4/T5 protocol). | N/A — evaluate agents follow fallback.md replacement-agent protocol | STOP-AND-ASK |
| Group H (T7B+T7C+T7D) | Any one: skip or manual. PPT missing → user creates manually. Script missing → user writes from outline. Q&A missing → manual brainstorming. | N/A — all have manual fallbacks | STOP-AND-ASK |

### Failure Logging

All partial failures must be recorded in the session state (`{output_dir}/.pipeline_state.json`) under `unresolved_items`:

```json
{
  "unresolved_items": [
    {
      "type": "parallel_agent_failure",
      "group": "Group A",
      "agent": "S6 citation verification",
      "retries": 1,
      "resolution": "degraded_to_manual",
      "checklist": "Manual citation spot-check: verify 10% sample of references for DOI match, author name spelling, year accuracy",
      "timestamp": "2026-06-02T15:30:00"
    }
  ]
}
```

These unresolved items persist in session state and are presented on resume. The pipeline does not block on unresolved items of type `parallel_agent_failure` with resolution `skipped` or `degraded_to_manual`, but the user must acknowledge them before the final gate (Q11/QT7/QC5).
