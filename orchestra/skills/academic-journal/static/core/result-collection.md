# Result Collection Protocol

## 冗余合并协议 (Mode B & Mode C)

When using redundancy-based dispatching, the merge step follows the protocol in `static/core/multi-agent-patterns.md` (see "Consistency Determination" and "Orchestrator Authority" sections). The authoritative consensus table, agreement levels, and orchestrator rules are defined there.

### Output Tags (Result Collection Extension)

All merged outputs carry confidence tags:
- `[AGENT-CONSENSUS × N]` — N agents independently agreed
- `[AGENT-DIVERGENT]` — agents disagreed, user resolved
- `[AGENT-UNILATERAL]` — only 1 of N redundant agents flagged this item (used in S9 review to flag low-confidence findings)
- `[ORCHESTRATOR-DECISION]` — orchestrator chose one version
- `[USER-DECISION]` — user resolved the conflict

### Divergence Logging

When merging Mode B/C outputs, record all divergences in the stage output:

```markdown
**Agent Divergence Report:**
- Item 1: Agent A said X, Agent B said Y → Resolution: PARTIAL, orchestrator selected Agent A's version as better justified → Tag: [ORCHESTRATOR-DECISION]
- Item 2: Agent A said Z, Agent B said Z (same) → Tag: [AGENT-CONSENSUS × 2]
- Item 3: Agent A said P, Agent B said Q → Resolution: LOW, user selected P → Tag: [USER-DECISION]
```

## 原有合并协议（Mode A）

1. All agents complete → collect outputs in a single document
2. Check for conflicts between parallel agents (e.g., two reviewers disagree on novelty → flag and resolve)
3. Synthesize merged findings before showing the user. Never present raw parallel output as-is.
4. If one agent's result invalidates another agent's assumption → resolve the conflict and re-run the affected agent
