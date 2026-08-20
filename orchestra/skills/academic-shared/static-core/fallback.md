# "I Don't Know" Fallback Protocol

When the user can't answer a required question, do not dead-end. Offer three options:

1. **Best-Guess:** "I'll make a best guess based on [observable evidence / public data / typical practice in this field]. You approve or correct it."
2. **Skip with Reduced Confidence:** "Skip this check and proceed with reduced confidence. The limitation will be documented in the paper."
3. **Defer:** "Defer this — we'll come back to it at [next relevant stage]. The paper will carry a [DEFERRED] marker."

**Rules for guesses:**
- Every guess is explicitly tagged `[UNCONFIRMED: user did not verify]` in the output
- Guess-based claims get an automatic Limitations entry: "[Claim/assumption] was not independently verified by the authors"
- If >3 guesses accumulate → **HARD STOP** → user must review all guesses before continuing
- Guesses must be based on observable evidence (data patterns, public information, field norms), never fabricated
- Deferred items must be resolved before the gate that depends on them (e.g., deferred data format question must be resolved before QD1)

## 审稿 agent 降级策略 / Parallel Agent Failure Recovery

When one agent in a parallel dispatch (DP17 C2, DP18 C4, DP19 T2, DP20 T5) returns empty results or fails:

### 1. Diagnose

Check the failed agent's output file for an explicit error message or empty content. Determine whether the failure is:
- **Search returned 0 results** (recoverable — try broader terms)
- **Agent error / timeout** (unrecoverable in parallel — agent cannot be restarted in same dispatch)
- **Output file missing** (unrecoverable — agent never wrote output)

### 2. Recoverable: Retry with Broader Terms

If the failure is recoverable (0 results):
1. Re-dispatch the failed agent with broader/looser search terms
2. If retry succeeds → merge output normally with other agents' results
3. If retry also fails → proceed to step 3

### 3. Unrecoverable: Proportional Accept

If unrecoverable or retry also failed:

**For literature search (C2/T2):**
- 1 of 4 agents failed (DP17/DP19: C2B/C2C/C2D/C2E or T2A/T2B/T2C/T2D) → reduce total target proportionally to 3/4 of original
  - C2: original 15+ → new target 12+ refs
  - T2 bachelor: original 20+ → new target 15+ refs
  - T2 master: original 30+ → new target 23+ refs
- 2 of 4 agents failed → STOP-AND-ASK with remaining results

**For review (C4/T5):**
- 1 agent failed → **immediately dispatch a replacement agent** with same persona/input; tag output `[AGENT-REPLACEMENT: {agent_name}]`. If replacement also fails → continue without that lens; document: "[AGENT-FAILED: {agent_name}] — [reason]"
- 2+ agents failed → STOP-AND-ASK: present the available review results and ask whether to proceed or re-run

**For Mode C (DP30 S9 — 4 personas × 2 redundancy = 8 agents):**
- One agent in a persona pair fails → the other agent in the same pair still produced output. Document the missing redundancy: "Persona [X]: only 1/2 agents completed — findings may miss items the redundant agent would have caught." Proceed with single-agent output for that persona.
- Both agents in a persona pair fail → that persona is missing entirely. Check the EAP agent's output (generalist or editor perspective). If EAP exists, it partially covers the gap. Document: "Persona [X] unavailable — [reason]." Proceed with remaining 3 personas.
- 2+ personas entirely missing → STOP-AND-ASK: "2 of 4 review personas are unavailable. Want to retry, proceed with reduced coverage, or escalate to user-directed review?"
- See DP30 in `static/core/dispatch-points.md` for Mode C dispatch details.

### 4.5 Low-Confidence Handling (NEW)

如果 agent 成功产出了输出（没有失败）但 scoring.py 检测到 median_confidence < 5：
- 不触发 re-dispatch（agent 没有真正的失败）
- 在最终报告中对 LOW_CONFIDENCE 的 dimension 注释：`[⚠ 低置信度 — 建议人工复审]`
- 在 pipeline 状态中记录 `unresolved_items` 供 resume 时优先处理

### 4. Critical Threshold

STOP-AND-ASK if remaining results fall below critical threshold:
- **C2:** < 10 unique refs after merge
- **T2 bachelor:** < 15 unique refs after merge
- **T2 master:** < 20 unique refs after merge
- **C4/T5:** only 1 or fewer review lenses available

### 5. Document

Record the failure in the stage output with:
- Which agent failed (e.g., C2C, T2B)
- Failure type and error message (if any)
- Recovery action taken (retry / proportional accept / skip)
- Impact on quality (reduced reference count, missing review lens, etc.)
