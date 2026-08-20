# Multi-Agent Orchestration Patterns

> Three patterns for dispatching parallel agents: **divide** (existing), **redundancy** (new), **hybrid** (new).
> The orchestrator (the pipeline) controls prompt quality, output merging, and consistency verification.

---

## Mode A: 分工并行 (Divide & Conquer)

A large task is split into non-overlapping sub-tasks. Each sub-task goes to one agent. Results are concatenated.

```
Task → [Sub-task 1] → Agent 1  ┐
       [Sub-task 2] → Agent 2   ├─→ Merge (concatenate + dedup) → Unified output
       [Sub-task 3] → Agent 3  ┘
```

| Property | Value |
|----------|-------|
| Redundancy | 0 (each sub-task done once) |
| When | Sub-tasks are independent and well-defined |
| Risk | One agent's error propagates undetected |
| Examples | C2/T2 multi-track search (DP17/DP19), S5 figure generation (DP9), S10 submission materials (DP15) |
| Cost | N agents = N× unit cost |

---

## Mode B: 冗余验证 (Redundancy)

**The same task** is given to 2-3 agents independently. The orchestrator compares outputs, assesses consistency, and produces a unified result.

```
Task ──→ Agent 1 ┐
       → Agent 2  ├─→ Orchestrator: compare → consensus → unified output
       → Agent 3 ┘
```

### When to Use

| Factor | Use Mode B |
|--------|-----------|
| Task type | Subjective evaluation, creative generation, strategic decision |
| Consequence of error | High (wrong direction wastes stages of work) |
| No ground truth | Yes — no API/code can verify the answer |
| Inter-rater reliability | Expected to be moderate-to-high among competent agents |

### Consistency Determination

After collecting all agent outputs, the orchestrator compares them:

| Agreement Level | Criteria | Action |
|---------------|----------|--------|
| **HIGH** | >80% overlap in key conclusions / <10% score deviation | Accept. Tag `[AGENT-CONSENSUS × N]`. Proceed. |
| **PARTIAL** | 50-80% overlap / 10-25% score deviation | Take overlap as high-confidence core. Orchestrator resolves differences by selecting best version or producing a merged version. Tag `[ORCHESTRATOR-DECISION]` on resolved items. |
| **LOW** | <50% overlap / >25% deviation / contradictory conclusions | STOP. Present all versions to user. Tag `[AGENT-DIVERGENT]`. User decides. Tag `[USER-DECISION]`. |
| **OUTLIER** | 2 agents agree, 1 differs | Accept majority. Document minority view in footnotes. Tag `[AGENT-CONSENSUS × 2/3]`. |

### Orchestrator Authority (Mode B)

The orchestrator (you, the pipeline) has the authority to:
- Select the best version when one is clearly superior (more complete, more coherent, better justified)
- Merge by taking intersection (overlap = high confidence) + best-of-rest for non-overlapping parts
- Flag disagreements for user resolution

The orchestrator **must NOT**:
- Fabricate new conclusions that no agent produced
- Silently drop a minority finding without documenting it
- Rewrite agent outputs beyond what's needed for formatting consistency

### Output Tags

| Tag | Meaning |
|-----|---------|
| `[AGENT-CONSENSUS × N]` | N agents independently agreed on this |
| `[AGENT-DIVERGENT]` | Agents disagreed — user must decide |
| `[ORCHESTRATOR-DECISION]` | Orchestrator selected one version among diverging outputs |
| `[USER-DECISION]` | User resolved the conflict |

### Cost vs. Confidence Tradeoff

| Redundancy | Cost Multiple | Confidence Gain | Best For |
|------------|--------------|-----------------|----------|
| ×2 | 2× | Catches single-agent blind spots | Important decisions (gap, novelty) |
| ×3 | 3× | Majority voting + outlier detection | Critical decisions (research question, venue) |

---

## Mode C: 冗余 + 分工混合 (Hybrid)

Divide the task into sub-tasks, then assign 2 agents (redundant) to each sub-task.

```
Task → [Sub 1] → Agent 1a ┐          ┌→ Sub 1 consensus
              → Agent 1b  ├──Merge──┼→ Sub 2 consensus  ──→ Unified output
       [Sub 2] → Agent 2a ├─        └→ Sub 3 consensus
              → Agent 2b  ┘
       [Sub 3] → Agent 3a ┐
              → Agent 3b  ┘
```

| Property | Value |
|----------|-------|
| Redundancy | 1 (each sub-task done twice) |
| When | Each sub-task is high-consequence AND independent |
| Cost | 2N agents (vs N for Mode A) |
| Examples | S9 multi-persona review with redundancy per persona (DP30) |

---

## Orchestrator — Execution Protocol

For ALL three modes, the orchestrator follows this protocol:

### 1. Define Context

Before dispatching, define:
- **Task description**: what needs to be done, in one sentence
- **Input context**: what each agent needs to know (shared across redundant agents)
- **Output format**: structured format every agent must follow (same schema for Mode B/C)
- **Evaluation criteria**: how outputs will be judged

### 2. Write Agent Prompt

Each sub-agent receives a self-contained prompt with:
- The task description + output format requirement
- All input context (don't make agents guess or search for missing info)
- The `{output_dir}` path for writing results

### 3. Dispatch

For Mode B: launch N identical copies of the same task.
For Mode A: launch different tasks.
For Mode C: launch 2 copies per sub-task.

All launched in parallel when possible.

### 4. Collect and Compare

- Read all agent outputs
- For Mode A: concatenate, check for conflicts between sub-tasks
- For Mode B: apply consistency determination table
- For Mode C: apply consistency per sub-task, then concatenate

### 5. Produce Unified Output

- One output file per dispatch point
- Tag each conclusion with its confidence level
- Log any divergences or conflicts for the user
- Gate evaluation uses the unified output, not raw agent outputs

---

## When NOT to Use Redundancy

| Scenario | Why Not |
|----------|---------|
| Deterministic operations (DOI verification, data parsing) | API call is more reliable than agent |
| Search/retrieval (finding papers) | Multiple search queries cover more ground than redundancy |
| Simple formatting tasks | Cost exceeds benefit |
| User-provided input processing | User is the authoritative source, not redundant agents |
